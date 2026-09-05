#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new.py — 开新书（书级，每本书跑一次）。

在写作根目录建一本书的目录，从 .novel/templates/ 拷贝书级模板，并把当前书登记到 .novel/active.md。

先决条件：写作根目录已跑过 setup.py（存在 .novel/）。

创建内容：
  {slug}/
  ├── concept.md            # 作品定位（预填书名/类型）
  ├── reader-contract.md    # 读者契约
  ├── worldbuilding.md      # 世界观
  ├── characters/           # 角色（空，用模板建）
  ├── outline/              # 大纲（空，用模板建）
  ├── chapters/             # 正文
  └── tracking/             # 状态账本（tracking_commit 生成）+ pacing.md（节奏）

用法：
  python3 scripts/new.py my-novel --title "我的小说" --genre 悬疑
  python3 scripts/new.py my-novel --root-dir ~/novels

退出码：0 = 成功；1 = 目录已存在且非空（未 --force）；2 = 参数/文件错误。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# novel-writer/scripts/pipeline.py（书级状态机，在书目录建 .story/pipeline.json）
PIPELINE_SCRIPT = os.path.normpath(
    os.path.join(_SCRIPT_DIR, "..", "..", "..", "..", "scripts", "pipeline.py")
)

# 书级设定模板（拷到书目录根）
BOOK_SETTING_FILES = [
    "concept.md",
    "reader-contract.md",
    "worldbuilding.md",
]

# 书级追踪模板（拷到书目录 tracking/）
BOOK_TRACKING_FILES = [
    "pacing.md",
]

BOOK_DIRS = ["characters", "outline", "chapters", "tracking"]


def find_story_root(start):
    """从 start 向上找含 .novel/ 的写作根目录，找不到返回 None。"""
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".novel")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def copy_file(src, dst):
    if os.path.exists(dst):
        return "skipped"
    shutil.copyfile(src, dst)
    return "created"


def fill_concept(path, title, genre):
    """对 concept.md 做轻量预填。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except OSError:
        return
    if title:
        text = re.sub(
            r"^- 书名：.*$", f"- 书名：{title}", text, count=1, flags=re.MULTILINE
        )
    if genre:
        text = re.sub(
            r"^- 类型：.*$", f"- 类型：{genre}", text, count=1, flags=re.MULTILINE
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def update_active(active_path, slug, title, genre):
    """把当前书登记到 .novel/active.md（多书切换时更新当前书登记，打印提示不静默）。"""
    try:
        with open(active_path, "r", encoding="utf-8-sig") as f:
            text = f.read()
    except OSError:
        return
    m = re.search(r"^- slug:\s*(.+)$", text, flags=re.MULTILINE)
    if m and m.group(1).strip() != slug:
        print(f"  ℹ️ active.md 当前书已从「{m.group(1).strip()}」切换为「{slug}」"
              "（多书并行时注意：脚本按运行目录定位项目，切书写作用 cd 到对应书目录）")
    text = re.sub(r"^- slug:.*$", f"- slug: {slug}", text, count=1, flags=re.MULTILINE)
    text = re.sub(
        r"^- 书名:.*$", f"- 书名: {title or slug}", text, count=1, flags=re.MULTILINE
    )
    text = re.sub(r"^- 类型:.*$", f"- 类型: {genre}", text, count=1, flags=re.MULTILINE)
    with open(active_path, "w", encoding="utf-8") as f:
        f.write(text)


def init_pipeline(book_root, slug, genre, platform, type_):
    """调用 pipeline.py init 在书目录建书级 .story/pipeline.json。"""
    cmd = [
        sys.executable,
        PIPELINE_SCRIPT,
        "init",
        slug,
        "--genre",
        genre,
        "--type",
        type_,
    ]
    if platform:
        cmd += ["--platform", platform]
    return subprocess.run(cmd, cwd=book_root).returncode


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    ap = argparse.ArgumentParser(
        description="开新书（书级，从 .novel/templates/ 拷模板）"
    )
    ap.add_argument("slug", help="英文目录名（建议 kebab-case，如 my-novel）")
    ap.add_argument(
        "--title", default="", help="书名（中文书名，预填到 concept.md；默认 = slug）"
    )
    ap.add_argument("--genre", default="", help="类型（预填 concept.md）")
    ap.add_argument(
        "--platform", default="", help="平台（可选；写网文时填，通用小说留空）"
    )
    ap.add_argument("--type", default="长篇小说", help="类型（长篇小说/短故事）")
    ap.add_argument(
        "--root-dir", default=None, help="写作根目录（默认从 cwd 向上找 .novel/）"
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="书目录已存在时补建缺失的模板（不动 chapters/outline）",
    )
    args = ap.parse_args()

    # 1. 定位写作根目录（含 .novel/）
    root = args.root_dir or find_story_root(os.getcwd())
    if not root:
        print("错误：找不到 .novel/，请先在写作根目录跑 setup.py", file=sys.stderr)
        return 2
    story_dir = os.path.join(root, ".novel")
    templates_dir = os.path.join(story_dir, "templates")
    if not os.path.isdir(templates_dir):
        print(f"错误：模板库不存在：{templates_dir}，请先跑 setup.py", file=sys.stderr)
        return 2

    # 2. slug 合法性：目录名只允许英文/数字/-/_（防路径穿越与平台差异）
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.slug or ""):
        print(
            f"错误：slug 只允许英文字母/数字/-/_（1-64 位），收到「{args.slug}」；中文书名请用 --title",
            file=sys.stderr,
        )
        return 2

    # 3. 防覆盖
    book_root = os.path.join(root, args.slug)
    if os.path.isdir(book_root) and os.listdir(book_root) and not args.force:
        print(
            f"错误：书目录已存在且非空：{book_root}（用 --force 补建缺失）",
            file=sys.stderr,
        )
        return 1

    created, skipped = [], []

    for d in BOOK_DIRS:
        os.makedirs(os.path.join(book_root, d), exist_ok=True)

    # 3. 从模板库拷书级模板
    for name in BOOK_SETTING_FILES:
        status = copy_file(
            os.path.join(templates_dir, name), os.path.join(book_root, name)
        )
        (created if status == "created" else skipped).append(name)

    for name in BOOK_TRACKING_FILES:
        status = copy_file(
            os.path.join(templates_dir, name), os.path.join(book_root, "tracking", name)
        )
        (created if status == "created" else skipped).append(f"tracking/{name}")

    # 4. 预填 + 登记入口
    fill_concept(
        os.path.join(book_root, "concept.md"), args.title or args.slug, args.genre
    )
    update_active(
        os.path.join(story_dir, "active.md"),
        args.slug,
        args.title or args.slug,
        args.genre,
    )

    # 5. 建书级流程状态（pipeline.py init 在书目录建 .story/pipeline.json）
    type_aliases = {"长篇": "长篇小说", "短篇": "短故事"}
    rc = init_pipeline(book_root, args.slug, args.genre, args.platform, type_aliases.get(args.type, args.type))
    if rc != 0:
        print(f"✗ pipeline init 失败（exit {rc}）——书目录已建但状态文件未就绪，请修复后重试", file=sys.stderr)
        return rc

    print(f"新书已建立：{os.path.abspath(book_root)}")
    if created:
        print(f"  新建：{'、'.join(created)}")
    if skipped:
        print(f"  跳过：{'、'.join(skipped)}")
    print()
    print("下一步：")
    print("  1. 补全 concept.md（一句话卖点/目标读者/篇幅）")
    print("  2. 填 reader-contract.md 与 worldbuilding.md")
    print("  3. 人物卡与大纲在 outline 阶段建（advance setup 后走 novel-outline）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
