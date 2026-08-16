#!/usr/bin/env python3
"""characters_pool_generator.py — 三维人物盘点生成器

按「势力 × 时代 × 家族」三个维度自动盘点人物池，产出 characters-pool.md。
每个格子列出「应有人物」+「已有卡」+ 决策列（建详卡 / 建简卡 / 不建卡 / 合并到X）。

agent 据此人工盘点，写回决策列。这是根治「漏识别该建卡的人」的关键一步。

用法：
  characters_pool_generator.py --project 书目录 [--force]
  默认不覆盖已有 characters-pool.md；--force 强制重生成。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import find_project_root

POOL_FILE = "characters-pool.md"


def detect_dimensions(root: Path) -> dict[str, list[str]]:
    """从 concept.md / worldbuilding.md 解析三个维度的盘点目标。

    解析策略（启发式 v2，克制版）：
      - 势力：硬编码常见阵营列表 + concept.md 中匹配
      - 时代：concept.md 「升级方向」段中的四位年（1800-2200）
      - 家族：只识别「沈/周/陈」三姓（来自 concept.md 关键人物段的三姓守局）+ worldbuilding 中显式出现的「X氏」

    解析失败时返回空列表，由 agent 手动补充。
    """
    dims: dict[str, list[str]] = {"势力": [], "时代": [], "家族": []}

    # 势力候选：硬编码常见阵营（避免误判）
    faction_candidates = ["纪末会", "长历学会", "玛雅遗族", "晨雾院", "守局", "孤儿院"]

    concept = root / "concept.md"
    wb = root / "worldbuilding.md"
    concept_text = concept.read_text(encoding="utf-8") if concept.exists() else ""
    wb_text = wb.read_text(encoding="utf-8") if wb.exists() else ""

    # 势力：从 concept.md / worldbuilding.md 中匹配候选
    for kw in faction_candidates:
        if kw in concept_text or kw in wb_text:
            if kw not in dims["势力"]:
                dims["势力"].append(kw)

    # 时代：识别概念中明确提到的时代跳跃点（克制）
    # 策略 1：从「升级方向」行提取（支持 - **升级方向**：xxx / ## 升级方向 段）
    upgrade_section = ""
    for line in concept_text.splitlines():
        if "升级方向" in line:
            upgrade_section += line + "\n"
            continue
        if upgrade_section and line.startswith("##") and "升级方向" not in line:
            break
        if upgrade_section:
            upgrade_section += line + "\n"
    # 策略 2：抓「X年前夜/战场/失败/破局」修饰词所在的四位年
    upgrade_full = upgrade_section if upgrade_section else concept_text
    # 优先匹配带修饰词的（说明是时代跳跃点）
    era_patterns = [
        r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b[^\n]*?(?:前夜|布局|事件|大阵|战场|循环|纪末|破局)",
        r"(?:前夜|布局|事件|大阵|战场|循环|纪末|破局)[^\n]*?\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b",
    ]
    for pat in era_patterns:
        for m in re.finditer(pat, upgrade_full):
            yr = m.group(1)
            if yr not in dims["时代"]:
                dims["时代"].append(yr)
    # 如果策略 2 没匹配到，回退到升级段所有四位年
    if not dims["时代"]:
        for m in re.finditer(r"\b(18\d{2}|19\d{2}|20\d{2}|21\d{2})\b", upgrade_section):
            yr = m.group(1)
            if yr not in dims["时代"]:
                dims["时代"].append(yr)

    # 家族：只识别明确三姓（沈/周/陈）+ worldbuilding 中的「X氏」白名单姓氏
    if "三姓" in concept_text or "守局" in concept_text or "三姓守局" in concept_text:
        for sname in ["沈家", "周家", "陈家"]:
            if sname not in dims["家族"]:
                dims["家族"].append(sname)
    # 从已有卡名提取「X氏」（仅采纳文件名中出现的姓氏，跳过非人物卡文件）
    chars_dir = root / "characters"
    if chars_dir.exists():
        NON_CARD_KEYWORDS = ["速查", "清单", "索引", "目录", "总表", "库"]
        seen: set[str] = set()
        for p in chars_dir.glob("*.md"):
            if p.name.startswith(".bak-") or any(kw in p.name for kw in NON_CARD_KEYWORDS):
                continue
            m = re.search(r"·([\u4e00-\u9fff])氏", p.name)
            if m:
                fam = m.group(1) + "氏"
                if fam not in seen:
                    seen.add(fam)
                    dims["家族"].append(fam)

    return dims


def list_existing_cards(root: Path) -> list[str]:
    """列出 characters/ 下所有已建卡的角色名（跳过备份与非人物卡文件）。"""
    chars_dir = root / "characters"
    if not chars_dir.exists():
        return []
    NON_CARD_KEYWORDS = ["速查", "清单", "索引", "目录", "总表", "库"]
    return sorted(
        p.stem
        for p in chars_dir.glob("*.md")
        if not p.name.startswith(".bak-")
        and not any(kw in p.name for kw in NON_CARD_KEYWORDS)
    )


def render_pool_table(root: Path, dims: dict[str, list[str]]) -> str:
    """渲染三维盘点表（势力/时代/家族 × 应有人物/已有卡/缺卡/决策）。"""
    existing = list_existing_cards(root)
    lines: list[str] = []
    lines.append("# 人物池盘点（characters-pool）")
    lines.append("")
    lines.append("> **本文件是 outline 第 1.5 步的产物，由 `characters_pool_generator.py` 自动生成骨架，agent 人工盘点决策。**")
    lines.append(">")
    lines.append("> 每个格子必须给出决策：**建详卡** / **建简卡** / **不建卡** / **合并到 X**。")
    lines.append("> advance outline 会校验本文件存在 + 每个格子决策列非空（硬门禁）。")
    lines.append("")
    lines.append("## 三维盘点矩阵")
    lines.append("")
    for dim_name, dim_list in dims.items():
        if not dim_list:
            continue
        lines.append(f"### {dim_name}")
        lines.append("")
        lines.append("| 项目 | 应有人物（agent 推断） | 已有卡 | 缺卡 | 决策 |")
        lines.append("|------|----------------------|--------|------|------|")
        for item in dim_list:
            # 简单匹配：卡名含维度关键字
            matched = [c for c in existing if item in c]
            missing = []  # agent 需自己推断
            existing_str = ", ".join(matched) if matched else "（无）"
            lines.append(
                f"| {item} | （待推断） | {existing_str} | （待推断） | _待盘点_ |"
            )
        lines.append("")

    lines.append("## 现有卡清单（自动扫描 characters/）")
    lines.append("")
    if existing:
        for c in existing:
            lines.append(f"- {c}")
    else:
        lines.append("（无）")
    lines.append("")
    lines.append("## 盘点决策记录")
    lines.append("")
    lines.append("> 在每个格子后面填上决策后，下方写明本次盘点的关键判断：哪些格子应该合并？哪些应建但被遗漏？")
    lines.append("")
    lines.append("（待 agent 填）")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="三维人物盘点生成器")
    parser.add_argument("--project", default=".", help="书目录（含 .story/）")
    parser.add_argument("--force", action="store_true", help="覆盖已有 characters-pool.md")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    proj = find_project_root(root)
    if proj is None:
        print(f"[错误] 找不到项目根（无 .story/）：{root}", flush=True)
        return 1

    pool_path = proj / POOL_FILE
    if pool_path.exists() and not args.force:
        print(f"[提示] {pool_path} 已存在（不覆盖）。用 --force 强制重生成。", flush=True)
        return 0

    dims = detect_dimensions(proj)
    content = render_pool_table(proj, dims)
    pool_path.write_text(content, encoding="utf-8")
    print(f"[ok] 生成 {pool_path}（维度：势力 {len(dims['势力'])} / 时代 {len(dims['时代'])} / 家族 {len(dims['家族'])}）", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())