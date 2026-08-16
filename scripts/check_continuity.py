#!/usr/bin/env python3
"""check_continuity.py — 连续性确定性检查（非 LLM 规则，零 token）

从状态账本派生视图里自动抓几类确定性矛盾，作为章节闸门的补充（advisory 级别，
不做硬拦截——语义判断仍归冷读/作者）：

1. 伏笔过期：status=已埋 且 planned_resolution_chapter < 当前章 → 该回收没回收
2. 伏笔无主：foreshadows 表里 ID 缺失/跳号
3. 角色疑亡又活跃：character_snapshots 里「状态」含死亡/退场类词，却仍在
   active_character_names / 后续章快照里出现
4. 硬规则突破未登记：context.md 的硬规则清单 vs overrides 表核对（提示人工复核）

用法：
  check_continuity.py --project {书目录} [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import find_project_root, read_json
from assemble_spec import parse_foreshadow_table

DEATH_WORDS = ("死亡", "去世", "离世", "牺牲", "殒命", "退场", "下线", "入狱")



def chapter_no(state: dict | None) -> int:
    if isinstance(state, dict):
        try:
            return int(state.get("last_committed_chapter") or state.get("imported_through_chapter") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="连续性确定性检查")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="连未登记的硬规则也报（噪音大，默认关）")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中（找不到 .story/）")
        return 1

    state = read_json(root / "tracking/_tracking-state.json")
    current = chapter_no(state)
    issues: list[dict] = []

    # 1/2. 伏笔检查
    fw_path = root / "tracking/foreshadows.md"
    if fw_path.exists():
        rows = parse_foreshadow_table(fw_path.read_text(encoding="utf-8"))
        ids = [r["id"] for r in rows]
        for r in rows:
            if r["status"] == "已埋" and current and 0 < r["planned_no"] < current:
                issues.append({
                    "kind": "foreshadow-overdue",
                    "detail": f"{r['id']} 计划第{r['planned']}章回收，现已到第{current}章仍未回收：{r['summary'][:40]}",
                })
        nums = sorted(int(i[1:]) for i in ids if i.startswith("F") and i[1:].isdigit())
        if nums:
            width = max(len(i) - 1 for i in ids)
            missing = [f"F{n:0{width}d}" for n in range(nums[0], nums[-1] + 1) if f"F{n:0{width}d}" not in ids]
            if missing:
                issues.append({"kind": "foreshadow-gap", "detail": f"伏笔编号缺口：{missing}"})

    # 2.5 Claremont 系数（dreampowers 吸收）：已埋-已回收 >2 预警伏笔堆积
    if fw_path.exists():
        rows = parse_foreshadow_table(fw_path.read_text(encoding="utf-8"))
        buried = sum(1 for r in rows if r["status"] == "已埋")
        resolved = sum(1 for r in rows if r["status"] == "已回收")
        cc = buried - resolved
        if cc > 2:
            issues.append({
                "kind": "claremont-coefficient",
                "detail": f"Claremont 系数 {cc}（已埋 {buried} - 已回收 {resolved}）> 2：伏笔堆积，读者记不住；后续章节优先安排回收",
            })

    # 3. 角色疑亡又活跃
    if isinstance(state, dict):
        chars = state.get("characters") or {}
        active = state.get("context", {}).get("active_character_names") or []
        for name, snap in chars.items():
            if not isinstance(snap, dict):
                continue
            st = str(snap.get("state", ""))
            if any(w in st for w in DEATH_WORDS) and name in active:
                issues.append({
                    "kind": "dead-character-active",
                    "detail": f"角色「{name}」状态含死亡/退场类词（{st}），但仍在活跃角色名单中",
                })

    # 4. 硬规则 vs overrides（仅 --strict 报：未打破的规则会产生噪音，打破与否需语义判断）
    if args.strict:
        ov_path = root / "tracking/overrides.md"
        wb_path = root / "worldbuilding.md"
        if ov_path.exists() and wb_path.exists():
            ov = ov_path.read_text(encoding="utf-8")
            wb = wb_path.read_text(encoding="utf-8")
            # 硬规则表：| 类型 | 规则 | 触发词 |（跳过分隔行与表头）
            for m in re.finditer(r"^\|\s*(禁止|上限|唯一)\s*\|\s*([^|]+?)\s*\|", wb, re.MULTILINE):
                rule = m.group(2).strip()
                if not rule or set(rule) <= set("-| "):
                    continue
                if rule not in ov:
                    issues.append({
                        "kind": "rule-unverified",
                        "detail": f"硬规则「{rule}」在 overrides 账本中无记录——若正文未打破则忽略；若打破了必须登记 rule_overrides",
                    })

    # 5. 章内时间算术一致性（ch2 睡觉时长 bug 类）：时长声明与前后时间点差明显不符
    for ch_dir in sorted((root / "chapters").glob("chapter-*")):
        draft = ch_dir / "draft.md"
        if not draft.exists():
            continue
        ch_no = int(ch_dir.name.split("-")[1])
        text = draft.read_text(encoding="utf-8")
        timepoints = []
        for m in re.finditer(r"(\d{1,2})点(半|\d{1,2})?分?", text):
            hour = int(m.group(1))
            raw_min = m.group(2)
            minute = 0 if raw_min is None else (30 if raw_min == "半" else int(raw_min))
            timepoints.append((m.start(), hour * 60 + minute))
        for m in re.finditer(r"(?:睡了|过了|花了|等了|用了)\s*(\d+)\s*个?\s*小时(?:(\d+)\s*分)?", text):
            dur = int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)
            before = [t for t in timepoints if t[0] < m.start()]
            after = [t for t in timepoints if t[0] > m.start()]
            if before and after:
                a = before[-1][1]
                b = after[0][1]
                if abs((b - a) - dur) > 45:
                    issues.append({
                        "kind": "time-arithmetic",
                        "detail": f"第{ch_no}章：时间点差 {b - a} 分钟与时长声明 {dur} 分钟差 {abs((b - a) - dur)} 分钟（{a // 60}点{a % 60}分 → {b // 60}点{b % 60}分 却说「{dur // 60}小时」），人工核对",
                    })

    if args.json:
        print(json.dumps({"current_chapter": current, "issues": issues}, ensure_ascii=False, indent=2))
        return 0

    if not issues:
        print(f"✓ 连续性检查通过（第 {current} 章，无确定性矛盾）")
        return 0
    print(f"⚠️ 连续性检查发现 {len(issues)} 项（advisory，语义终判归冷读/作者）：")
    for i in issues:
        print(f"  - [{i['kind']}] {i['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
