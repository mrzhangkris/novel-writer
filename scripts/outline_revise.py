#!/usr/bin/env python3
"""outline_revise.py — 大纲中途修订冲突检测

长篇写到中途改大纲（换地图/砍支线/人物下线/势力合并）时，旧章与新大纲的冲突必须显形。
本脚本对照「已写章节记录」与「新 outline.md」，产出 outline-revision-report.md：

  1. 伏笔对账：旧伏笔规划里已埋/已收的伏笔，新大纲是否还接得住
  2. 章节冲突：已写章节的「本章目标/关键事件」与新大纲同章条目是否矛盾
  3. 人物下线：新大纲不再出现的核心角色，是否已在账本退役

用法：
  outline_revise.py --project 书目录 [--from-chapter N]
  --from-chapter：只检查从第 N 章起（默认全书）；修订后半段时用它缩小范围。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import EXEMPTIONS_FILE, find_project_root, read_json

REPORT_FILE = "outline-revision-report.md"
EXEMPT_TYPE = "outline-revise"


def parse_outline_entries(outline: str) -> dict[int, dict[str, str]]:
    """解析 outline.md 每章条目：章号 -> {本章目标, 关键事件}。"""
    entries: dict[int, dict[str, str]] = {}
    for m in re.finditer(
        # 锚定行首（可带 ### 标题前缀）：防止总纲表格里的「第 3 章末」被误当章条目
        r"(?m)^(?:#{2,4}\s*)?第\s*(\d+)\s*章[^\n]*\n(.*?)(?=\n(?:#{2,4}\s*)?第\s*\d+\s*章|\Z)",
        outline,
        flags=re.DOTALL,
    ):
        chapter = int(m.group(1))
        # 跳过已写章节的留档条目（「已写（第 N 章，原目标：…）」标记）——
        # 已写章与新大纲的比对走 parse_written_results（chapter-deltas），不走章纲
        title_line = m.group(0).splitlines()[0]
        if "已写" in title_line:
            continue
        body = m.group(2)
        entry: dict[str, str] = {}
        for field in ("本章目标", "关键事件", "章末钩子"):
            fm = re.search(rf"{field}[：:]\s*(.+?)(?=\n|$)", body)
            if fm:
                entry[field] = fm.group(1).strip()
        entries[chapter] = entry
    return entries


def parse_written_results(root: Path) -> dict[int, str]:
    """从 chapter-deltas 提取已写章节的「结果」。"""
    results: dict[int, str] = {}
    deltas_dir = root / "tracking" / "chapter-deltas"
    if not deltas_dir.exists():
        return results
    for p in deltas_dir.glob("*.md"):
        m = re.match(r"chapter-(\d+)\.md", p.name) or re.match(r"第(\d+)章", p.name)
        if not m:
            continue
        chapter = int(m.group(1))
        text = p.read_text(encoding="utf-8")
        rm = re.search(r"-\s*结果[：:]\s*(.*)", text)
        if rm:
            results[chapter] = rm.group(1).strip()
    return results


def parse_foreshadow_state(root: Path) -> dict[str, dict]:
    """从账本读伏笔表：id -> {status, planted, planned_resolution}。"""
    state = read_json(root / "tracking" / "_tracking-state.json")
    if not isinstance(state, dict):
        return {}
    return state.get("foreshadow", {})


def foreshadow_in_outline(fid: str, outline: str) -> bool:
    """伏笔 id 是否仍出现在新大纲里。编号归一化比对：
    账本 F002 vs 大纲 F2 是同一伏笔（int 相等即命中），防格式差异假阳性。"""
    m = re.fullmatch(r"F(\d+)", fid)
    if not m:
        return fid in outline
    num = int(m.group(1))
    if f"F{num:03d}" in outline or f"F{num}" in outline:
        return True
    # 大纲伏笔表格式「| F2 |」/「F2：」按编号token比对
    return any(
        re.fullmatch(rf"F{num:03d}|F{num}", tok)
        for tok in re.findall(r"F\d+", outline)
    )


def load_exemptions(root: Path) -> list[dict]:
    """读豁免清单（.story/exemptions.json，由 checks.py exempt 写入）。

    比对类检查对「文字不同但实质一致」的条目存在假冲突（M3 实测 5 条假冲突
    一直挂账），人工确认后记豁免，命中即不再报。文件缺失/损坏按空清单处理
    （豁免是降噪手段，不因清单问题中断修订检查）。"""
    data = read_json(root / EXEMPTIONS_FILE, default=[])
    if not isinstance(data, list):
        return []
    return [
        x for x in data
        if isinstance(x, dict) and x.get("type") == EXEMPT_TYPE and x.get("key")
    ]


def detect_conflicts(root: Path, from_chapter: int) -> list[tuple[str, str]]:
    """返回 (key, 描述) 列表；key 是稳定豁免锚（checks.py exempt outline-revise <key>）。"""
    outline_path = root / "outline.md"
    if not outline_path.exists():
        return [("outline-missing", "大纲文件不存在")]
    outline = outline_path.read_text(encoding="utf-8")
    entries = parse_outline_entries(outline)
    written = parse_written_results(root)
    foreshadows = parse_foreshadow_state(root)
    conflicts: list[tuple[str, str]] = []

    # 1. 伏笔对账
    for fid, row in foreshadows.items():
        if from_chapter > 1 and int(row.get("planted_chapter", 0)) < from_chapter:
            continue
        if not foreshadow_in_outline(fid, outline):
            conflicts.append((
                f"foreshadow:{fid}",
                f"伏笔 {fid}（第{row.get('planted_chapter', '?')}章埋，状态「{row.get('status', '?')}」）"
                "在新大纲中消失——要么补回新大纲，要么在 revise 时声明废弃",
            ))

    # 2. 已写章节与新大纲条目矛盾（无法自动判语义矛盾，列出已写章 + 新纲目标题供人工比对）
    for chapter in sorted(written):
        if chapter < from_chapter:
            continue
        if chapter in entries:
            goal = entries[chapter].get("本章目标", "")
            if goal:
                conflicts.append((
                    f"chapter-goal:{chapter}",
                    f"第{chapter}章已写（结果：{written[chapter][:40]}…）"
                    f"vs 新大纲本章目标：{goal[:40]}——人工比对是否冲突",
                ))

    # 3. 活跃核心角色 vs 新大纲提及（粗检：角色名在 outline 里出现次数为 0 且有账本快照 → 疑似被大纲抛弃）
    state = read_json(root / "tracking" / "_tracking-state.json")
    if isinstance(state, dict):
        active = state.get("context", {}).get("active_character_names", [])
        for name in active:
            if name not in outline:
                conflicts.append((
                    f"character-missing:{name}",
                    f"活跃核心角色「{name}」在新大纲中未再出现——若已下线，"
                    "在修订事务中登记退役（retired_characters），否则读者会等他返场",
                ))
    return conflicts


def render_report(
    conflicts: list[tuple[str, str]],
    exempted: list[tuple[str, str]],
    from_chapter: int,
) -> str:
    lines = [
        "# 大纲修订冲突报告（outline-revision-report）",
        "",
        f"> 检查范围：第 {from_chapter} 章起。生成时间由 revise 流程触发。",
        "",
        "## 冲突清单",
        "",
    ]
    if not conflicts:
        lines.append("✅ 无冲突：新大纲与已写章节/伏笔/角色对账一致，可继续写。")
    else:
        for i, (key, text) in enumerate(conflicts, 1):
            lines.append(f"{i}. ⚠️ [{key}] {text}")
    lines.append("")
    lines.append("## 处理动作")
    lines.append("")
    if conflicts:
        lines.append("每条冲突二选一：")
    lines.append("- **改大纲**：把冲突条目补回新大纲（伏笔续接、角色返场、章纲保留）")
    lines.append("- **改声明**：在 revise 事务里显式声明废弃（伏笔 delete / 角色退役 / 旧章重写）")
    if conflicts:
        lines.append(
            "- **确认误报**：文字不同但实质一致的条目（人工比对后），记入豁免清单，下次不再报：\n"
            f"  `python3 scripts/checks.py exempt {EXEMPT_TYPE} <方括号里的key> --reason \"比对说明\"`"
        )
    if exempted:
        shown = [f"[{key}]" for key, _ in exempted]
        lines.append("")
        lines.append(
            f"> 已按豁免清单跳过 {len(exempted)} 条（{EXEMPTIONS_FILE}）：{'、'.join(shown)}"
            "——复核豁免用 `checks.py exempt list`"
        )
    lines.append("")
    lines.append("> 修订大纲时同步更新 tracking 账本：伏笔变更走 delta.foreshadow_changes，")
    lines.append("> 角色下线走 delta.retired_characters，不静默丢弃。")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="大纲中途修订冲突检测")
    parser.add_argument("--project", default=".", help="书目录")
    parser.add_argument("--from-chapter", type=int, default=1, help="只检查从第 N 章起")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    proj = find_project_root(root)
    if proj is None:
        print(f"[错误] 找不到项目根（无 .story/）：{root}", flush=True)
        return 1

    conflicts = detect_conflicts(proj, args.from_chapter)
    # 豁免过滤：命中清单的假冲突不再报，但报告中留痕（防豁免变成无声丢弃）
    exempt_keys = {x.get("key") for x in load_exemptions(proj)}
    active = [c for c in conflicts if c[0] not in exempt_keys]
    exempted = [c for c in conflicts if c[0] in exempt_keys]
    report = render_report(active, exempted, args.from_chapter)
    report_path = proj / REPORT_FILE
    report_path.write_text(report, encoding="utf-8")
    print(f"[ok] 报告：{report_path}", flush=True)
    summary = f"     冲突 {len(active)} 条" + ("（无冲突 ✅）" if not active else "")
    if exempted:
        summary += f"；按豁免清单跳过 {len(exempted)} 条"
    print(summary, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())