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
    """从 concept.md / worldbuilding.md 数据驱动提取三个维度的盘点目标。

    解析策略（启发式，解析不了就返回空——空维度会渲染「手工填写」占位行，
    门禁依然要求 agent 补齐，不会虚过）：
      - 势力：worldbuilding「势力」节的表格行首列 / 【势力名】标记 / 「X会|X门|X宗|X组织」高频词
      - 时代：全文四位年（1800-2200）
      - 家族：出现 ≥2 次的「X家」与已有卡的「·X氏」
    """
    dims: dict[str, list[str]] = {"势力": [], "时代": [], "家族": []}

    concept = root / "concept.md"
    wb = root / "worldbuilding.md"
    concept_text = concept.read_text(encoding="utf-8") if concept.exists() else ""
    wb_text = wb.read_text(encoding="utf-8") if wb.exists() else ""
    full_text = concept_text + "\n" + wb_text

    # 势力：①worldbuilding「势力」节内表格行首列；②「【势力名】」标记
    faction = ""
    for line in wb_text.splitlines():
        if re.match(r"^#{1,3}\s*.*势力", line):
            faction = line
            continue
        if faction:
            if line.startswith("#"):
                faction = ""
                continue
            m = re.match(r"^\|\s*([^|·\-]{2,12}?)\s*\|", line)
            if m and not set(m.group(1)) <= set("- ") and "势力" not in m.group(1):
                dims["势力"].append(m.group(1).strip())
    for m in re.finditer(r"【([\u4e00-\u9fff\w]{2,10})】", full_text):
        name = m.group(1)
        if name not in dims["势力"]:
            dims["势力"].append(name)
    # 兜底：全文高频（≥3 次）的「X组织/X公会/X协会」
    freq: dict[str, int] = {}
    for m in re.finditer(r"([\u4e00-\u9fff]{1,4}?)(?:组织|公会|协会)", full_text):
        freq[m.group(0)] = freq.get(m.group(0), 0) + 1
    for word, n in sorted(freq.items(), key=lambda kv: -kv[1]):
        if n >= 3 and word not in dims["势力"]:
            dims["势力"].append(word)

    # 时代：全文四位年（1800-2200），去重保序
    for m in re.finditer(r"(?<!\d)(18\d{2}|19\d{2}|20\d{2}|21\d{2})(?!\d)", full_text):
        yr = m.group(1)
        if yr not in dims["时代"]:
            dims["时代"].append(yr)

    # 家族：高频「X家」（≥2 次，非「专家/大家/国家/商家」等常用词）+ 卡名「·X氏」
    fam_freq: dict[str, int] = {}
    for m in re.finditer(r"([\u4e00-\u9fff])家", full_text):
        fam_freq[m.group(1) + "家"] = fam_freq.get(m.group(1) + "家", 0) + 1
    for w, n in fam_freq.items():
        if n >= 2 and w not in ("专家", "大家", "国家", "商家", "哪家", "谁家", "自家", "人家", "本家", "管家", "当家", "回家", "在家", "搬家", "成家", "养家", "分家", "安家", "持家", "宜家") and w not in dims["家族"]:
            dims["家族"].append(w)
    chars_dir = root / "characters"
    if chars_dir.exists():
        for p_ in chars_dir.glob("*.md"):
            m = re.search(r"·([\u4e00-\u9fff])氏", p_.name)
            if m:
                fam = m.group(1) + "氏"
                if fam not in dims["家族"]:
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
            # 空维度也必须渲染占位行：否则无 _待盘点_ 占位 → 门禁虚过
            lines.append(f"### {dim_name}（脚本未能自动提取——手工补维度行再盘点）")
            lines.append("")
            lines.append("| 项目 | 应有人物（agent 推断） | 已有卡 | 缺卡 | 决策 |")
            lines.append("|------|----------------------|--------|------|------|")
            lines.append("| （从 concept/worldbuilding 手工填） | （待推断） | （无） | （待推断） | _待盘点_ |")
            lines.append("")
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