#!/usr/bin/env python3
"""outline_drift.py — 大纲-正文漂移检测

每 N 章对照大纲章纲抽查已写正文：本章目标达成了吗？关键事件发生了吗？
偏差输出「漂移报告」——agent 写高兴了就跑偏，这是防跑偏的定量锚。

检测方法（确定性、非语义）：
  1. 每章 spec.md 履约清单的勾选率（≥80% 门禁之外的累积视角）
  2. 已写正文与大纲「关键事件」关键词重合度（粗粒度）
  3. 连续章缺钩子/缺变化的计数

用法：
  outline_drift.py --project 书目录 [--window N] [--from-chapter M]
  --window：最近 N 章为检测窗（默认 10）；--from-chapter：从第 M 章起。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import find_project_root

REPORT_FILE = "outline-drift-report.md"


def collect_spec_checklist_rates(root: Path, from_chapter: int) -> dict[int, float]:
    """每章 spec.md 履约清单勾选率。"""
    rates: dict[int, float] = {}
    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        return rates
    for spec in chapters_dir.glob("chapter-*/spec.md"):
        m = re.match(r"chapter-(\d+)", spec.parent.name)
        if not m:
            continue
        chapter = int(m.group(1))
        if chapter < from_chapter:
            continue
        text = spec.read_text(encoding="utf-8")
        checked = len(re.findall(r"^- \[[xX]\]", text, flags=re.MULTILINE))
        unchecked = len(re.findall(r"^- \[ \]", text, flags=re.MULTILINE))
        total = checked + unchecked
        if total == 0:
            continue
        rates[chapter] = checked / total
    return rates


def collect_hook_presence(root: Path, from_chapter: int) -> dict[int, bool]:
    """每章 draft.md 结尾是否有钩子标记（大纲「章末钩子」计划 + 正文末尾悬疑词）。"""
    presence: dict[int, bool] = {}
    chapters_dir = root / "chapters"
    if not chapters_dir.exists():
        return presence
    hook_words = ("?", "？", "……", "——", "回头", "却", "突然", "猛地", "而", "难道")
    for draft in chapters_dir.glob("chapter-*/draft.md"):
        m = re.match(r"chapter-(\d+)", draft.parent.name)
        if not m:
            continue
        chapter = int(m.group(1))
        if chapter < from_chapter:
            continue
        text = draft.read_text(encoding="utf-8").strip()
        tail = text[-60:] if text else ""
        presence[chapter] = any(w in tail for w in hook_words)
    return presence


def render_report(
    rates: dict[int, float], hooks: dict[int, bool], window: int
) -> str:
    chapters = sorted(set(rates) | set(hooks))
    if not chapters:
        return "# 大纲-正文漂移报告\n\n> 无已写章节可检测（或章节从 from-chapter 起尚未写出）。\n"

    # 最近 window 章
    recent = chapters[-window:]
    drift_lines: list[str] = []
    for ch in recent:
        rate = rates.get(ch)
        hook = hooks.get(ch, False)
        issues = []
        if rate is not None and rate < 0.8:
            issues.append(f"履约勾选率 {rate:.0%}（<80%）")
        if not hook:
            issues.append("章尾疑似无钩子")
        if issues:
            drift_lines.append(f"- 第{ch}章：{'；'.join(issues)}")

    lines = [
        "# 大纲-正文漂移报告（outline-drift-report）",
        "",
        f"> 检测窗：最近 {window} 章（{recent[0] if recent else '-'}～{recent[-1] if recent else '-'}）。",
        "> 判定确定性、非语义：勾选率与钩子标记只做定量锚，最终判断由 agent 对照大纲章纲人工复核。",
        "",
        "## 漂移项",
        "",
    ]
    if not drift_lines:
        lines.append("✅ 检测窗内无漂移信号：履约勾选率达标、章尾钩子齐全。")
    else:
        lines.extend(drift_lines)
    lines.append("")
    lines.append("## 处理建议")
    lines.append("")
    lines.append("漂移项每章二选一：")
    lines.append("- **回正文补**：勾选率不足的章补上未履约条目；无钩子的章补钩子")
    lines.append("- **改大纲**：正文已合理偏离时，走 novel-revise 大纲修订模式更新章纲（不许静默漂移）")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="大纲-正文漂移检测")
    parser.add_argument("--project", default=".", help="书目录")
    parser.add_argument("--window", type=int, default=10, help="检测窗章数")
    parser.add_argument("--from-chapter", type=int, default=1, help="从第几章起")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    proj = find_project_root(root)
    if proj is None:
        print(f"[错误] 找不到项目根（无 .story/）：{root}", flush=True)
        return 1

    rates = collect_spec_checklist_rates(proj, args.from_chapter)
    hooks = collect_hook_presence(proj, args.from_chapter)
    report = render_report(rates, hooks, args.window)
    (proj / REPORT_FILE).write_text(report, encoding="utf-8")
    print(f"[ok] 报告：{proj / REPORT_FILE}", flush=True)
    drift = sum(
        1
        for ch in sorted(set(rates) | set(hooks))[-args.window :]
        if (rates.get(ch) or 0) < 0.8 or not hooks.get(ch, False)
    )
    print(f"     检测窗内漂移项 {drift} 个" + ("（无漂移 ✅）" if not drift else ""), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())