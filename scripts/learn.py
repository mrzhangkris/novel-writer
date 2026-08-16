#!/usr/bin/env python3
"""learn.py — 写作模式记忆（project_memory）

从会话中提取可复用的写作模式（钩子/节奏/对话/微兑现等），
追加到 .story/project_memory.json，供后续写作复用。

用法：
  learn.py add "<描述>" [--pattern-type hook] [--category xxx] [--importance high]
  learn.py list   列出所有已学习的模式
  learn.py init   初始化 project_memory.json（通常自动）

pattern_type：hook/pacing/dialogue/payoff/emotion/format/other
importance：high/medium/low

状态文件：.story/project_memory.json（脚本维护，请勿手改）
章节号来源：.story/pipeline.json 的 chapter 字段（缺失则记 null）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import STORY_DIR, find_project_root

MEMORY_FILE = ".story/project_memory.json"
PIPELINE_FILE = ".story/pipeline.json"

PATTERN_TYPES = {"hook", "pacing", "dialogue", "payoff", "emotion", "format", "other"}
IMPORTANCE_LEVELS = {"high", "medium", "low"}

DEFAULT_MEMORY: dict = {"patterns": []}




def load_memory(root: Path) -> dict:
    p = root / MEMORY_FILE
    if not p.exists():
        return json.loads(json.dumps(DEFAULT_MEMORY))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("patterns"), list):
            data["patterns"] = []
        return data
    except (json.JSONDecodeError, OSError):
        print(f"⚠️  记忆文件损坏：{p}")
        print("   不写入脏数据。请手动修复或删除该文件后重试。")
        sys.exit(1)


def save_memory(root: Path, memory: dict) -> None:
    story = root / STORY_DIR
    story.mkdir(parents=True, exist_ok=True)
    (root / MEMORY_FILE).write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def current_chapter(root: Path) -> int | None:
    """从 pipeline.json 读当前章节号；缺失/损坏返回 None。"""
    p = root / PIPELINE_FILE
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ch = data.get("chapter")
        return ch if isinstance(ch, int) else None
    except (json.JSONDecodeError, OSError):
        return None


def _normalize_pattern_type(raw: str | None) -> str:
    """非法/缺失的 pattern_type 归为 other（容错，不阻断）。"""
    if raw and raw in PATTERN_TYPES:
        return raw
    return "other"


def _normalize_importance(raw: str | None) -> str:
    if raw and raw in IMPORTANCE_LEVELS:
        return raw
    return "medium"


def _is_duplicate(memory: dict, pattern_type: str, description: str) -> bool:
    for pat in memory["patterns"]:
        if (
            pat.get("pattern_type") == pattern_type
            and pat.get("description") == description
        ):
            return True
    return False


def cmd_add(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中（找不到 .story/ 目录）")
        print("   先开新书：pipeline.py init <项目名>")
        return 1

    pattern_type = _normalize_pattern_type(args.pattern_type)
    importance = _normalize_importance(args.importance)

    memory = load_memory(root)
    if _is_duplicate(memory, pattern_type, args.description):
        print(f"⚠️  已存在完全相同的模式（{pattern_type}），跳过追加")
        return 0

    pattern = {
        "pattern_type": pattern_type,
        "description": args.description,
        "category": args.category or "",
        "importance": importance,
        "source_chapter": current_chapter(root),
        "learned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    memory["patterns"].append(pattern)
    save_memory(root, memory)

    print("✅ 模式已记忆：")
    print(json.dumps(pattern, ensure_ascii=False, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中（找不到 .story/ 目录）")
        return 1

    memory = load_memory(root)
    patterns = memory["patterns"]
    if not patterns:
        print("📭 暂无已记忆的写作模式")
        return 0

    print(f"📚 已记忆 {len(patterns)} 条写作模式：")
    for i, pat in enumerate(patterns, 1):
        ch = pat.get("source_chapter")
        ch_s = f"第{ch}章" if ch else "—"
        cat = f"｜{pat['category']}" if pat.get("category") else ""
        print(
            f"  {i}. [{pat.get('pattern_type')}][{pat.get('importance')}] "
            f"{pat.get('description')}（{ch_s}{cat}）"
        )
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中（找不到 .story/ 目录）")
        return 1

    p = root / MEMORY_FILE
    if p.exists():
        print(f"⚠️  已存在 {MEMORY_FILE}，不覆盖")
        return 0
    save_memory(root, json.loads(json.dumps(DEFAULT_MEMORY)))
    print(f"✅ 已初始化 {MEMORY_FILE}")
    return 0


PLAYBOOK_SECTIONS = ("妙处", "问题", "文风技法")


def author_root(root: Path) -> Path | None:
    cur = root
    while cur != cur.parent:
        if (cur / ".novel").is_dir():
            return cur
        cur = cur.parent
    return None


def playbook_path(root: Path) -> Path | None:
    a = author_root(root)
    return (a / ".novel" / "writing-playbook.md") if a else None


def cmd_add_author(args: argparse.Namespace) -> int:
    """作者级跨书沉淀：写入 .novel/writing-playbook.md 的 妙处/问题/文风技法 小节。"""
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    p = playbook_path(root)
    if p is None:
        print("❌ 未找到作者工作区 .novel/（先跑 novel-init 的 setup.py）")
        return 1
    section = args.section if args.section in PLAYBOOK_SECTIONS else "妙处"
    if not p.exists():
        p.write_text(
            "# 写作技法库（作者级，跨书复用）\n\n"
            "> 妙处：让人眼前一亮的设计，下次写作时主动复用。\n"
            "> 问题：踩过的坑，下次写作时主动避开。\n"
            "> 文风技法：优化文风与技法的经验，写正文时对照。\n\n"
            "## 妙处\n\n## 问题\n\n## 文风技法\n",
            encoding="utf-8",
        )
    text = p.read_text(encoding="utf-8")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pipe = root / ".story" / "pipeline.json"
    book, chapter = "?", "?"
    try:
        data = json.loads(pipe.read_text(encoding="utf-8"))
        book = str(data.get("project") or "?")
        chapter = data.get("chapter")
    except (OSError, json.JSONDecodeError):
        pass
    src = f"（{book}·第{chapter}章）" if chapter else f"（{book}）"
    entry = f"- [{date}] {src} {args.description}"
    if entry in text:
        print(f"⚠️  技法库已存在相同条目，跳过")
        return 0
    marker = f"## {section}\n"
    idx = text.index(marker) + len(marker)
    # 插到该小节末尾（下一个 ## 之前）
    nxt = text.find("\n## ", idx)
    if nxt == -1:
        nxt = len(text)
    text = text[:nxt] + entry + "\n" + text[nxt:]
    p.write_text(text, encoding="utf-8")
    print(f"✅ 已沉淀到作者技法库 [{section}]：{args.description}")
    print(f"   文件：{p}")
    return 0


def cmd_list_author(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    p = playbook_path(root)
    if p is None or not p.exists():
        print("📭 作者技法库为空（learn.py add --scope author 沉淀）")
        return 0
    print(p.read_text(encoding="utf-8"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="写作模式记忆（project_memory）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="追加一条写作模式")
    p_add.add_argument("description", help="模式描述（用户输入或提炼后的完整描述）")
    p_add.add_argument(
        "--scope",
        choices=["project", "author"],
        default="project",
        help="project=本书项目记忆（默认）；author=作者级技法库（跨书）",
    )
    p_add.add_argument(
        "--pattern-type",
        help="模式类型（hook/pacing/dialogue/payoff/emotion/format/other）",
    )
    p_add.add_argument("--category", help="分类（项目级自由文本，可空；作者级忽略）")
    p_add.add_argument(
        "--section",
        choices=list(PLAYBOOK_SECTIONS),
        default="妙处",
        help="作者级小节：妙处/问题/文风技法（默认妙处）",
    )
    p_add.add_argument("--importance", help="重要度（high/medium/low）")
    p_add.set_defaults(func=lambda a: cmd_add_author(a) if a.scope == "author" else cmd_add(a))

    p_list = sub.add_parser("list", help="列出所有已记忆的模式")
    p_list.add_argument(
        "--scope",
        choices=["project", "author"],
        default="project",
        help="project=本书项目记忆（默认）；author=作者级技法库（跨书）",
    )
    p_list.set_defaults(func=lambda a: cmd_list_author(a) if a.scope == "author" else cmd_list(a))

    p_init = sub.add_parser("init", help="初始化 project_memory.json")
    p_init.set_defaults(func=cmd_init)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
