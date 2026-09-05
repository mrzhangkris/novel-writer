#!/usr/bin/env python3
"""writer_profile.py — 写手档案：yeyue（Minimax M3）单写手的文风基线与 AI 味校准。

背景：本书写手固定为 yeyue 子代理（Minimax M3）。AI 味与文风纠缠——同一破折号
判据，猫腻腔是文风、电报腔是 AI 味。检测基线/写前避开项按写手实测存档案，
替换全局一刀切。

用法：
  writer_profile.py calibrate [--project 书目录] [--chapters 1,2] [--draft 文件.md]
      实测 yeyue 已写章节 → 生成/更新 .novel/writer.md：
      量化基线自动实测；AI 味倾向表给实测密度（豁免/盯防裁定是文风决策，人工确认）；
      重校准保留人工裁定（豁免/阈值=N 的备注不覆盖）
  writer_profile.py show [--project 书目录]
      查看档案摘要

上手顺序：yeyue 写出 2-3 章正稿 → calibrate → 人工核订倾向表（豁免=文风合法形态）。
不 calibrate 也能用（档案缺失回退作者级 style-anchor + 全局默认阈值）。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from _common import find_project_root
from _textstat import (
    BASELINE_DIALOG_RE,
    BASELINE_PARA_RE,
    BASELINE_SENT_RE,
    baseline_range,
    cjk_len,
    measure_baseline,
)

WRITER_NAME = "yeyue"
WRITER_MODEL = "Minimax M3"
PROFILE_SUBDIR = Path(".novel")
PROFILE_FILE = Path(".novel") / "writer.md"

# 处置表行：`- em-dash ｜ 盯防 ｜ 实测 3.1/千字`（全角｜分隔，防与正文冲突）
VERDICT_RE = re.compile(r"^- ([A-Za-z0-9-]+) ｜ (豁免|盯防) ｜ (.+?)\s*$", re.MULTILINE)

DESLOP_JS = (
    Path(__file__).resolve().parent.parent
    / "skills/branch/story-deslop/scripts/check-ai-patterns.js"
)

HEADER = f"""# 写手档案：{WRITER_NAME}（{WRITER_MODEL}）

> 本书写手固定为 {WRITER_NAME}。档案存在即生效：风格基线检查、AI 味提醒阈值、
> spec 写前避开项按本档案执行；删除本文件即回退作者级 style-anchor + 全局默认。
> 「豁免」= 该模式属本写手文风的合法形态，检测降 advisory；「盯防」= 顽固 AI 味，阈值可自定义（备注写 阈值=N）。
"""


def author_root(start: Path) -> Path | None:
    """从 start 向上找作者级工作区（含 .novel/ 的目录）。"""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".novel").is_dir():
            return cur
        cur = cur.parent
    return None


def profile_path(author: Path) -> Path:
    # author 惯例是「作者根目录」（.novel 的父目录）；误传 .novel 目录本身时兜底上溯
    base = author.parent if author.name == ".novel" else author
    return base / PROFILE_FILE


def load_profile(author: Path | None) -> dict | None:
    """读 yeyue 写手档案并解析。档案不存在 → None（调用方走回退逻辑）。

    返回 {"path", "text", "verdicts": {类型: {"verdict", "note"}},
          "avoid": [写前避开项], "sent"/"dialog"/"para": (lo,hi) | None}。"""
    if author is None:
        return None
    path = profile_path(author)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    verdicts = {
        m[0]: {"verdict": m[1], "note": m[2]} for m in VERDICT_RE.findall(text)
    }
    avoid: list[str] = []
    in_avoid = False
    for line in text.splitlines():
        if line.startswith("## 写前避开项"):
            in_avoid = True
            continue
        if line.startswith("## "):
            in_avoid = False
        if in_avoid and line.startswith("- ") and len(line) > 2:
            avoid.append(line[2:].strip())

    return {
        "path": path,
        "text": text,
        "verdicts": verdicts,
        "avoid": avoid,
        "sent": baseline_range(text, BASELINE_SENT_RE),
        "dialog": baseline_range(text, BASELINE_DIALOG_RE),
        "para": baseline_range(text, BASELINE_PARA_RE),
    }


def verdict_threshold(verdict: dict | None, default: float) -> float | None:
    """该写手某检测类型的生效阈值：备注含「阈值=N」用 N；豁免 → None（跳过）；
    其余（含无档案）→ default。"""
    if verdict is None:
        return default
    if verdict["verdict"] == "豁免":
        return None
    m = re.search(r"阈值[=：:]\s*(\d+(?:\.\d+)?)", verdict["note"])
    return float(m.group(1)) if m else default


def measure_ai_patterns(drafts: list[Path], total_cjk: int) -> dict[str, int]:
    """跑 deslop 检测器，返回 {检测类型: 命中计数}。node 缺失/超时返回空表。"""
    counts: dict[str, int] = {}
    for draft in drafts:
        try:
            r = subprocess.run(
                ["node", str(DESLOP_JS), "--check", "--json", str(draft)],
                capture_output=True, text=True, timeout=60,
            )
            findings = json.loads(r.stdout or "{}").get("findings", [])
        except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
            return {}
        for f in findings:
            ftype = f.get("type", "")
            if not ftype:
                continue
            m = re.search(r"(\d+) 处", f.get("message", ""))
            counts[ftype] = counts.get(ftype, 0) + (int(m.group(1)) if m else 1)
    return counts


def render_profile(base: dict, samples_note: str,
                   old: dict | None, pattern_counts: dict[str, int],
                   total_cjk: int, n_chapters: int) -> str:
    """组装档案全文。old 存在时保留人工裁定（豁免 / 含 阈值= 的备注 / 避开项）。"""
    avg = base["avg_sent"]
    dialog = base["dialog_pct"]
    para = base["med_para"]
    sent_lo, sent_hi = max(5, round(avg * 0.8)), round(avg * 1.2)
    dia_lo, dia_hi = max(0, round(dialog) - 10), min(100, round(dialog) + 10)
    para_lo, para_hi = max(1, para - 1), para + 2

    lines = [
        HEADER,
        "## 元信息",
        f"- 写手：{WRITER_NAME}（{WRITER_MODEL}）",
        f"- 校准样本：{samples_note}",
        f"- 校准时间：{date.today().isoformat()}（writer_profile.py calibrate 实测）",
        "",
        "## 量化基线",
        f"- 平均句长：约 {sent_lo}~{sent_hi} 字",
        f"- 对话占比：约 {dia_lo}~{dia_hi}%",
        f"- 段落中位长度：约 {para_lo}~{para_hi} 行",
        "",
        "## AI 味倾向（校准实测 + 处置裁定）",
        "格式：`- 检测类型 ｜ 豁免|盯防 ｜ 备注（可含 阈值=N）`",
    ]
    old_verdicts = old["verdicts"] if old else {}
    rows = []
    for ftype, count in sorted(pattern_counts.items(), key=lambda kv: -kv[1]):
        density = round(count * 1000 / total_cjk, 1) if total_cjk else 0.0
        prev = old_verdicts.get(ftype)
        if prev and (prev["verdict"] == "豁免" or "阈值=" in prev["note"] or "阈值：" in prev["note"]):
            rows.append(f"- {ftype} ｜ {prev['verdict']} ｜ {prev['note']}")
        else:
            hint = "；若属本写手文风腔调（参照猫腻腔 em-dash 实例）人工改「豁免」" if ftype == "em-dash" else ""
            rows.append(f"- {ftype} ｜ 盯防 ｜ 实测 {density}/千字（{count} 处/{n_chapters} 章）{hint}")
    for ftype, prev in old_verdicts.items():  # 上次有、本次未检出的：保留人工裁定
        if ftype not in pattern_counts and (prev["verdict"] == "豁免" or "阈值=" in prev["note"]):
            rows.append(f"- {ftype} ｜ {prev['verdict']} ｜ {prev['note']}")
    lines.extend(rows or ["- （本次样本未检出 AI 味模式；档案先建，检出后重跑 calibrate 补表）"])
    lines.append("")
    lines.append("## 写前避开项（注入 spec 风格指令，每章生效）")
    old_avoid = old["avoid"] if old else []
    lines.extend(f"- {a}" for a in old_avoid)
    if not old_avoid:
        lines.append("> 待补：该写手高频但检测器测不到的 habit——写成 `- 规则` 一行一条才会注入 spec")
    lines.append("")
    return "\n".join(lines)


def cmd_calibrate(args) -> int:
    root = find_project_root(args.project or Path.cwd())
    if root is None:
        print("❌ 不在项目中（--project 或 cd 到书目录）")
        return 1
    author = author_root(root)
    if author is None:
        print("❌ 向上找不到 .novel/（先跑 novel-init setup）")
        return 1

    drafts: list[Path] = []
    if args.draft:
        drafts.append(args.draft)
    if args.chapters:
        for n in [c for c in re.split(r"[,，\s]+", args.chapters.strip()) if c]:
            p = root / "chapters" / f"chapter-{int(n):03d}" / "draft.md"
            if not p.exists():
                print(f"❌ 样本章不存在：{p}")
                return 1
            drafts.append(p)
    drafts = list(dict.fromkeys(drafts))
    if not drafts:
        print("❌ 未指定样本：--chapters 1,2,3（推荐 2-3 章正稿）或 --draft 文件")
        return 1

    texts = [d.read_text(encoding="utf-8") for d in drafts]
    full_text = "\n\n".join(texts)
    total_cjk = cjk_len(full_text)
    base = measure_baseline(full_text)
    counts = measure_ai_patterns(drafts, total_cjk)

    old = load_profile(author)
    profile_file = profile_path(author)
    profile_file.parent.mkdir(parents=True, exist_ok=True)
    samples_note = (
        f"指定章节 {args.chapters}" if args.chapters else drafts[0].name
    ) + f"（共 {len(drafts)} 章，{total_cjk} 汉字）"
    profile_file.write_text(
        render_profile(base, samples_note, old, counts, total_cjk, len(drafts)),
        encoding="utf-8",
    )

    print(f"✅ 写手档案已生成：{profile_file}")
    print(f"   量化基线：句均 {base['avg_sent']:.1f} 字 / 对话 {base['dialog_pct']:.1f}% / 段落中位 {base['med_para']} 行")
    if counts:
        top = "、".join(f"{t}×{c}" for t, c in sorted(counts.items(), key=lambda kv: -kv[1])[:5])
        print(f"   AI 味检出：{top}")
    else:
        print("   AI 味检出：无（node 缺失或零命中）")
    print("   下一步：①人工核订倾向表（豁免=文风合法，盯防可写 阈值=N）②补写前避开项")
    return 0


def cmd_show(args) -> int:
    root = find_project_root(args.project or Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    author = author_root(root)
    prof = load_profile(author)
    print(f"本书写手：{WRITER_NAME}（{WRITER_MODEL}）")
    if prof is None:
        pp = profile_path(author) if author else Path(PROFILE_FILE)
        print(f"  档案：不存在（{pp}）——按回退逻辑执行（作者级 style-anchor + 全局默认）")
        print(f"  校准：writer_profile.py calibrate --chapters 1,2")
        return 0
    print(f"  档案：{prof['path']}")
    if prof["sent"]:
        parts = [f"句长 {prof['sent'][0]}~{prof['sent'][1]} 字"]
        if prof["dialog"]:
            parts.append(f"对话 {prof['dialog'][0]}~{prof['dialog'][1]}%")
        if prof["para"]:
            parts.append(f"段落 {prof['para'][0]}~{prof['para'][1]} 行")
        print("  量化基线：" + " / ".join(parts))
    if prof["verdicts"]:
        v = "、".join(f"{k}({d['verdict']})" for k, d in prof["verdicts"].items())
        print(f"  处置表：{v}")
    if prof["avoid"]:
        print(f"  写前避开项：{len(prof['avoid'])} 条")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=f"写手档案（{WRITER_NAME}/{WRITER_MODEL} 文风与AI味校准）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cal = sub.add_parser("calibrate", help="实测样本生成/更新写手档案")
    p_cal.add_argument("--project", type=Path, default=None)
    p_cal.add_argument("--chapters", type=str, default=None, help="样本章号，如 1,2,3")
    p_cal.add_argument("--draft", type=Path, default=None, help="单文件样本")
    p_cal.set_defaults(func=cmd_calibrate)

    p_show = sub.add_parser("show", help="查看写手档案")
    p_show.add_argument("--project", type=Path, default=None)
    p_show.set_defaults(func=cmd_show)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
