#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setup.py — 初始化 .novel/ 写作基础设施（作者级，跨所有书复用）。

只跑一次：在写作根目录建 .novel/，装入「通用资产」——文风锚、模板库、禁用词、入口文件。
之后开每本书不再重复这些。

创建内容：
  .novel/
  ├── preferences.md       # 作者偏好（写作模式/调研偏好/其他习惯）
  ├── style-anchor.md     # 文风锚（作者级，一份跨书）
  ├── banned-words.txt    # 作者级禁用词
  ├── active.md           # 入口：当前正在写哪本书
  └── templates/          # 通用模板库（开新书（book_init.py）时从这里拷贝）
      ├── concept.md、reader-contract.md、worldbuilding.md   # 书级设定
      ├── character-card.md                                       # 建角色用（outline 阶段拷贝）
      └── pacing.md                                       # 书级追踪（其余走 tracking_commit）

幂等：已存在的文件跳过不覆盖；--force 补建缺失。

用法：
  python3 scripts/setup.py --root-dir ~/novels
  python3 scripts/setup.py --force

退出码：0 = 成功；1 = 已存在且非空（未 --force）；2 = 参数/文件错误。
"""

import argparse
import os
import shutil
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.normpath(os.path.join(_SCRIPT_DIR, os.pardir, "templates"))

# 文风锚：作者级资产，拷到 .novel/style-anchor.md（不在模板库里）
STYLE_FILE = "style-anchor.md"

# 模板库：跨书复用的空模板，拷到 .novel/templates/
TEMPLATE_FILES = [
    # 书级设定（开新书时拷到书目录根）
    "concept.md",
    "reader-contract.md",
    "worldbuilding.md",
    # 建角色时用（留在模板库，outline 阶段拷贝）
    "character-card.md",
    "character-card-simple.md",
    # 书级追踪（开新书时拷到书目录 tracking/；其余走 tracking_commit）
    "pacing.md",
]

PLAYBOOK_TEMPLATE = """# 写作技法库（作者级，跨书复用）

> 妙处：让人眼前一亮的设计，下次写作时主动复用。
> 问题：踩过的坑，下次写作时主动避开。
> 文风技法：优化文风与技法的经验，写正文时对照。

## 妙处

## 问题

## 文风技法
"""


BANNED_TEMPLATE = """# Banned words & personal taboos (one per line; # starts a comment)
# Section 1: words/styles the author personally avoids (never use in prose).
# Section 2: genre clichés and AI-flavored filler to avoid.
"""

ACTIVE_TEMPLATE = """# 当前书（Active）

> 写作入口：记录当前正在写哪本书。切换书时更新本文件（或重新跑 new.py）。

- slug:
- 书名:
- 类型:
- 状态: 初始化
- 当前章节:
"""

PREFERENCES_TEMPLATE = """# 作者偏好与能力索引

> 写作工作区的作者级配置。「作者偏好」建骨架时询问，「能力索引」是已有能力清单。

## 作者偏好（建骨架时询问，可随时改）
- 写作模式：
- 扫榜：
- 考据：
- 其他习惯：

## 能力索引（已有能力，无需选择）
- 调研：story-long-scan（扫榜）+ search 技能（多引擎搜索榜单/考据）
- 文风：style-anchor.md（本目录）+ genre-prose-cards/（32 题材）+ story-long-analyze（拆书蒸馏）
- 去AI味：banned-words.txt（本目录，用户自定义词表扩展位——当前去AI味闸门以 check-ai-patterns.js 内置词表为准，此文件尚未接入引擎）+ skills/branch/story-deslop/references/banned-words.md + check-ai-patterns.js
- 方法论：references/writing-methods/（34 份）+ references/editor-checklist.md（编辑自检六条）
- 字数：references/word-count.json（平台）+ concept.md 目标篇幅（通用）
"""


def copy_file(src, dst):
    """幂等拷贝：目标已存在返回 'skipped'，否则拷贝返回 'created'。"""
    if os.path.exists(dst):
        return "skipped"
    shutil.copyfile(src, dst)
    return "created"


def write_file(path, content):
    """幂等写文件：已存在返回 'skipped'，否则写入返回 'created'。"""
    if os.path.exists(path):
        return "skipped"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return "created"


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(
        description="初始化 .novel/ 写作基础设施（作者级，跨书复用）"
    )
    ap.add_argument("--root-dir", default=".", help="写作根目录（.novel/ 建在这里）")
    ap.add_argument(
        "--force",
        action="store_true",
        help="已初始化时补建缺失的文件（不覆盖已有内容）",
    )
    args = ap.parse_args()

    story_dir = os.path.join(args.root_dir, ".novel")
    templates_dir = os.path.join(story_dir, "templates")

    if os.path.isdir(story_dir) and os.listdir(story_dir) and not args.force:
        print(
            f"提示：.novel/ 已初始化：{story_dir}（用 --force 补建缺失文件）",
            file=sys.stderr,
        )
        return 1

    created, skipped = [], []

    os.makedirs(templates_dir, exist_ok=True)

    # 1. 文风锚（作者级资产）
    status = copy_file(
        os.path.join(TEMPLATE_DIR, STYLE_FILE), os.path.join(story_dir, STYLE_FILE)
    )
    (created if status == "created" else skipped).append(f".novel/{STYLE_FILE}")

    # 2. 模板库
    for name in TEMPLATE_FILES:
        status = copy_file(
            os.path.join(TEMPLATE_DIR, name), os.path.join(templates_dir, name)
        )
        (created if status == "created" else skipped).append(f".novel/templates/{name}")

    # 3. 禁用词 + 入口 + 作者偏好（内嵌生成）
    for name, content in [
        ("banned-words.txt", BANNED_TEMPLATE),
        ("active.md", ACTIVE_TEMPLATE),
        ("preferences.md", PREFERENCES_TEMPLATE),
        ("writing-playbook.md", PLAYBOOK_TEMPLATE),
    ]:
        status = write_file(os.path.join(story_dir, name), content)
        (created if status == "created" else skipped).append(f".novel/{name}")

    print(f"写作基础设施已初始化：{os.path.abspath(story_dir)}")
    if created:
        print(f"  新建：{'、'.join(created)}")
    if skipped:
        print(f"  跳过：{'、'.join(skipped)}")
    print()
    print("下一步：开新书用 new.py，例如：")
    print('  python3 scripts/new.py my-novel --title "我的小说" --genre 悬疑')
    return 0


if __name__ == "__main__":
    sys.exit(main())
