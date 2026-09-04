#!/usr/bin/env python3
"""book_init.py — 书级初始化批量骨架生成器

new.py 只建目录，剩下的骨架文件原来靠 AI 逐个写。本脚本在定方向（9 问）
之后一次生成全部确定性骨架，AI 只填内容：

- 按题材自动匹配并拷贝题材卡（解析 genre-prose-cards.md 索引表）
- concept.md 补蓝本空结构（一句话概要/核心冲突/主题/开篇钩子/目标读者/篇幅/叙事人称）
- worldbuilding.md 骨架（叙事占位 + 硬规则清单「类型|规则|触发词」/能力白名单两张空表）
- reader-contract.md 骨架（核心期待/兑现方式/红线/主角代理权四节）

用法（novel-init 第 4 步，定方向完成后）：
  book_init.py --root-dir {写作根目录} --slug my-book --title "书名" --genre 都市脑洞 \\
               [--platform 番茄] [--type 短故事] [--genre-card 都市脑洞.md  # 跳过自动匹配]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys as _sys
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFERENCES = HERE.parent / "references"

CONCEPT_TEMPLATE = """
## 蓝本（定方向结论，待 AI 填）

- 一句话概要：（在[世界]中，[主角]必须[核心行动]，否则[代价]）
- 核心冲突：
- 主题：
- 开篇钩子：
- 目标读者：
- 篇幅：
- 叙事人称：
"""

WORLDBUILDING_TEMPLATE = """# 世界观

> 待 AI 填：先写自由叙事（力量体系 / 时代背景 / 社会势力，人读），
> 再补下面两张表（脚本读，用于离奇判定）。

## 硬规则清单

| 类型（禁止/上限/唯一） | 规则 | 触发词 |
|---|---|---|
| （待填） |  |  |

## 能力白名单

| 能力名 | 类型 | 等级 | 归属 |
|---|---|---|---|
| （待填） |  |  |  |
"""

READER_CONTRACT_TEMPLATE = """# 读者契约

- 核心期待：（待填）
- 兑现方式：（待填）
- 红线：（待填）
- 主角代理权：（待填）
"""


def parse_card_index() -> list[tuple[str, str, str]]:
    """解析 genre-prose-cards.md 索引表 → [(卡名, 文件名, 别名串, 置信度)]。"""
    index = REFERENCES / "genre-prose-cards.md"
    if not index.exists():
        return []
    rows = []
    for line in index.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| \[([^\]]+)\]\(genre-prose-cards/([^)]+)\) \| ([^|]+) \| ([^|]+) \|$", line.strip())
        if m:
            rows.append((m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()))
    return rows


def match_card(genre: str) -> tuple[str, str] | None:
    """genre 与卡名/别名匹配，返回 (卡名, 文件路径)；多义时返回 None 并打印候选。"""
    g = genre.strip()
    if not g:
        return None
    hits = []
    for name, fname, aliases, conf in parse_card_index():
        tokens = [name] + [a.strip() for a in aliases.split("/")]
        if g == name or g == fname.removesuffix(".md"):
            # 精确命中立即返回：不受后续别名子串的宽泛命中污染成多义
            path = REFERENCES / "genre-prose-cards" / fname
            return name, str(path)
        for t in tokens:
            if t and (t in g or g in t):
                hits.append((name, fname, conf))
                break
    if len(hits) == 1:
        name, fname, conf = hits[0]
        path = REFERENCES / "genre-prose-cards" / fname
        return name, str(path)
    if len(hits) > 1:
        print("  ⚠️ 题材命中多张卡，请用 --genre-card 指定：")
        for name, fname, conf in hits[:5]:
            print(f"     - {name}（{fname}，{conf}置信）")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="书级初始化批量骨架生成器")
    parser.add_argument("--root-dir", type=Path, required=True, help="写作根目录（含 .novel）")
    parser.add_argument("--slug", type=str, required=True, help="书目录名")
    parser.add_argument("--title", type=str, required=True)
    parser.add_argument("--genre", type=str, default="", help="题材（题材卡名或别名）")
    parser.add_argument("--platform", type=str, default="")
    parser.add_argument("--type", type=str, default="长篇小说")
    parser.add_argument("--genre-card", type=str, default=None, help="直接指定题材卡文件名，跳过自动匹配")
    args = parser.parse_args()

    book = (args.root_dir / args.slug).resolve()
    if not (book / ".story" / "pipeline.json").exists():
        init_script = HERE.parent / "skills" / "mainline" / "novel-init" / "scripts" / "new.py"
        print(f"  ▶ new.py {args.slug}")
        rc = subprocess.run(
            [sys.executable, str(init_script), args.slug,
             "--title", args.title, "--genre", args.genre or "其他",
             "--platform", args.platform, "--type", args.type, "--root-dir", str(args.root_dir)],
        ).returncode
        if rc != 0:
            print("  ❌ new.py 失败")
            return rc
    else:
        print(f"  ✓ 书目录已存在，跳过 new.py")

    # 1) 题材卡（确定性拷贝）
    if args.genre_card:
        card_path = REFERENCES / "genre-prose-cards" / args.genre_card
        if not card_path.exists():
            print(f"  ❌ 题材卡不存在：{card_path}")
            return 1
        hit = (card_path.stem, str(card_path))
    else:
        hit = match_card(args.genre)
    card_target = book / "题材卡.md"
    if card_target.exists() and card_target.stat().st_size > 100:
        print("  ⚠️ 题材卡.md 已存在，跳过拷贝（重跑不覆盖人工改动）")
    elif hit:
        name, path = hit
        card_target.write_text((Path(path)).read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  ✓ 题材卡已拷贝：《{name}》→ 题材卡.md")
    else:
        card_target.write_text("自创题材，无对应卡\n", encoding="utf-8")
        print("  ⚠️ 无匹配题材卡：题材卡.md 已写占位，AI 可手动补")

    # 2) concept.md 补蓝本结构（保留 new.py 预填，不覆盖已有内容）
    concept = book / "concept.md"
    base = concept.read_text(encoding="utf-8") if concept.exists() else f"# 书名：{args.title}\n"
    if "## 蓝本" not in base:
        concept.write_text(base.rstrip() + "\n" + CONCEPT_TEMPLATE, encoding="utf-8")
        print("  ✓ concept.md 蓝本结构已补")

    # 3) worldbuilding.md：new.py 模板已有叙事骨架；这里只补脚本读的两张空表（离奇判定依赖）
    wb = book / "worldbuilding.md"
    if not wb.exists():
        wb.write_text(WORLDBUILDING_TEMPLATE, encoding="utf-8")
        print("  ✓ worldbuilding.md 骨架（硬规则清单 + 能力白名单空表）")
    else:
        content = wb.read_text(encoding="utf-8")
        appended = []
        if "## 硬规则清单" not in content:
            appended.append("## 硬规则清单\n\n| 类型（禁止/上限/唯一） | 规则 | 触发词 |\n|---|---|---|\n| （待填） |  |  |\n")
        if "## 能力白名单" not in content:
            appended.append("## 能力白名单\n\n| 能力名 | 类型 | 等级 | 归属 |\n|---|---|---|---|\n| （待填） |  |  |  |\n")
        if appended:
            wb.write_text(content.rstrip() + "\n\n" + "\n".join(appended), encoding="utf-8")
            print("  ✓ worldbuilding.md 已追加硬规则清单/能力白名单空表")

    # 4) reader-contract.md 骨架
    rc_file = book / "reader-contract.md"
    if not rc_file.exists():
        rc_file.write_text(READER_CONTRACT_TEMPLATE, encoding="utf-8")
        print("  ✓ reader-contract.md 骨架（四节空模板）")

    print()
    print("  接下来 AI 只需填内容：concept 蓝本 → worldbuilding 叙事+两张表 → reader-contract 四节")
    print("  → pipeline.py checkpoint clear cp1 → pipeline.py advance setup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
