#!/usr/bin/env python3
"""Maintain one structured story state and its deterministic Markdown views.

CLI 薄壳：文件 I/O、命令入口与「先渲染后提交」的落盘顺序。
协议校验在 `_tracking/schema.py`，视图渲染在 `_tracking/render.py`，
事务合并在 `_tracking/merge.py`。
"""

from __future__ import annotations

from typing import Any

import argparse
import json
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from _tracking.merge import merge_transaction
from _tracking.render import render_delta, render_views
from _tracking.schema import (
    CONTEXT_TARGET_BYTES,
    DELTA_MAX_BYTES,
    DELTA_TARGET_BYTES,
    RETIRED_ARCHIVE_DIR,
    RETIRED_TRACKING_PATHS,
    SNAPSHOT_TARGET_BYTES,
    TrackingError,
    as_int,
    byte_size,
    normalize_initial_document,
    normalize_state,
    normalize_transaction,
    require,
)

def emit(text: str, *, error: bool = False) -> None:
    """Write UTF-8 bytes directly.

    Windows 的文本 stdout 是 cp1252（含中文即 UnicodeEncodeError），stderr 默认
    backslashreplace（中文被转义成反斜杠码位，作者看不懂）。两条路都要绕开。
    """
    stream = sys.stderr if error else sys.stdout
    stream.flush()
    stream.buffer.write((text + "\n").encode("utf-8"))
    stream.buffer.flush()

def read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrackingError(f"unable to read JSON {path}: {exc}") from exc

def json_payload(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def write_if_changed(path: Path, payload: str) -> None:
    try:
        if path.read_text(encoding="utf-8") == payload:
            return
    except FileNotFoundError:
        pass
    atomic_write_text(path, payload)

def tracking_root(project: Path) -> Path:
    return project.resolve() / "tracking"

def state_path(project: Path) -> Path:
    return tracking_root(project) / "_tracking-state.json"

def delta_path(tracking: Path, chapter: int) -> Path:
    width = max(3, len(str(chapter)))
    return tracking / "chapter-deltas" / f"第{chapter:0{width}d}章.md"

def find_retired_tracking_paths(tracking: Path) -> list[str]:
    found = [
        relative
        for relative in RETIRED_TRACKING_PATHS
        if (tracking / relative).exists()
    ]
    found.extend(sorted(path.name for path in tracking.glob("基线_截至第*章.md")))
    return found

def require_no_retired_tracking_paths(tracking: Path) -> None:
    found = find_retired_tracking_paths(tracking)
    require(not found, f"retired tracking files are not supported: {', '.join(found)}")

def archive_retired_tracking_paths(tracking: Path) -> list[str]:
    """Move a pre-transaction tracking/ aside so init can build the current protocol in place.

    Nothing is parsed or converted: the old files are kept verbatim for the author to
    consult, and the new state is reconstructed from the init document alone.
    """
    retired = find_retired_tracking_paths(tracking)
    if not retired:
        return []
    archive = tracking / RETIRED_ARCHIVE_DIR
    for relative in retired:
        require(
            not (archive / relative).exists(),
            f"tracking/{RETIRED_ARCHIVE_DIR}/{relative} already exists; move it away before initializing",
        )
    # 先全量校验再搬运；中断后重跑时已搬走的条目不再出现在待搬列表里，可直接续做。
    for relative in retired:
        target = archive / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tracking / relative, target)
    return retired

def load_state(project: Path) -> dict[str, Any]:
    path = state_path(project)
    require(path.exists(), "tracking state is missing; run init first")
    return normalize_state(read_json(path))

def initialize(project: Path, document: object) -> dict[str, Any]:
    tracking = tracking_root(project)
    require(
        not state_path(project).exists(),
        "tracking state already exists; init never overwrites project state",
    )
    state = normalize_initial_document(document)
    views = render_views(state)
    state_payload = json_payload(state)

    # 输入全部校验通过后才动用户文件，失败的 init 不会挪走任何东西。
    archived = archive_retired_tracking_paths(tracking)
    for directory in (
        tracking / "chapter-deltas",
        tracking / "characters",
        tracking / "timeline",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    write_views(tracking, views)
    atomic_write_text(state_path(project), state_payload)
    warn_sizes(views)
    if archived:
        emit(
            f"NOTE: 旧追踪结构已原样移入 tracking/{RETIRED_ARCHIVE_DIR}/：{', '.join(archived)}；"
            "当前状态以本次 init 输入为准，旧文件不参与解析。",
            error=True,
        )
    return state

def _archive_tx_after_commit(project: Path, input_path: Path) -> None:
    """提交成功后把事务中间产物移入 .story/tx-archive/，.story 目录只留最新一个。

    账本（tracking/chapter-deltas + _tracking-state.json）已固化本章全部 delta，
    tx JSON 不再被任何流程读取；归档保留原件供回滚/重提交参照，不再堆积。
    """
    src = Path(input_path)
    if not src.exists():
        return
    archive = project.resolve() / ".story" / "tx-archive"
    archive.mkdir(parents=True, exist_ok=True)
    dst = archive / src.name
    if dst.exists():
        dst.unlink()  # 重提交同章时覆盖旧归档
    shutil.move(str(src), str(dst))
    emit(f"NOTE: 事务已归档至 .story/tx-archive/{src.name}（账本已固化，tx 不再堆积）")


def apply_transaction(project: Path, document: object) -> dict[str, Any]:
    tracking = tracking_root(project)
    require_no_retired_tracking_paths(tracking)
    state = load_state(project)
    transaction = normalize_transaction(state, document)
    next_state = merge_transaction(state, transaction)

    delta_payload = render_delta(
        transaction["chapter"],
        transaction["title"],
        transaction["delta"],
        # 本章退役的角色在 next_state 里已被删除，但本章记录里仍应标为核心。
        set(next_state["characters"]) | set(transaction["delta"]["retired_characters"]),
    )
    views = render_views(next_state)
    next_state_payload = json_payload(next_state)
    path = delta_path(tracking, transaction["chapter"])
    if transaction["mode"] == "append" and path.exists():
        require(
            path.read_text(encoding="utf-8") == delta_payload,
            f"chapter delta {transaction['chapter']} already exists with different content",
        )

    write_if_changed(path, delta_payload)
    write_views(tracking, views)
    # 唯一权威文件最后落盘；在此之前失败可用同一事务直接重跑。
    atomic_write_text(state_path(project), next_state_payload)
    warn_sizes(views, delta_payload)
    return next_state

def check_project(project: Path) -> dict[str, Any]:
    tracking = tracking_root(project)
    require_no_retired_tracking_paths(tracking)
    state = load_state(project)
    last_chapter = state["last_committed_chapter"]
    required_delta_start = state["imported_through_chapter"] + 1
    for chapter in range(required_delta_start, last_chapter + 1):
        require(
            delta_path(tracking, chapter).exists(),
            f"chapter delta {chapter} is missing",
        )
    for path in (tracking / "chapter-deltas").glob("第*章.md"):
        match = re.fullmatch(r"第(\d+)章\.md", path.name)
        require(
            match is not None, f"chapter delta has an invalid filename: {path.name}"
        )
        chapter = as_int(int(match.group(1)), f"chapter delta {path.name}", minimum=1)
        require(
            path == delta_path(tracking, chapter),
            f"chapter delta {chapter} filename is not canonical",
        )
        require(
            chapter <= last_chapter,
            f"chapter delta {chapter} exceeds last_committed_chapter",
        )
        require(
            path.stat().st_size <= DELTA_MAX_BYTES,
            f"chapter delta {chapter} exceeds {DELTA_MAX_BYTES} bytes",
        )

    expected_views = render_views(state)
    # 旧协议迁移：老状态文件没有 overrides 键（v4 之前），首次 check 时补写空账本视图。
    raw_state = read_json(state_path(project))
    if isinstance(raw_state, dict) and "overrides" not in raw_state:
        write_if_changed(tracking / "overrides.md", expected_views["overrides.md"])
    # v5 迁移：ledger.md（道具/秘密/誓约台账视图）是新增派生视图，首次 check 补写，不报缺失。
    if not (tracking / "ledger.md").exists():
        write_if_changed(tracking / "ledger.md", expected_views["ledger.md"])
    for relative, expected in expected_views.items():
        path = tracking / relative
        require(path.exists(), f"derived view is missing: {relative}")
        require(
            path.read_text(encoding="utf-8") == expected,
            f"derived view differs from _tracking-state.json: {relative}",
        )
    expected_character_files = {
        Path(relative).name
        for relative in expected_views
        if relative.startswith("characters/")
    }
    actual_character_files = {
        path.name for path in (tracking / "characters").glob("*.md")
    }
    require(
        actual_character_files == expected_character_files,
        "character snapshot files differ from tracking state",
    )

    # Claremont 系数：未推进的已埋伏笔 - 已回收。「推进」态已确认在收敛，不计入堆积
    active = sum(1 for f in state["foreshadow"].values() if f.get("status") == "已埋")
    resolved = sum(
        1 for f in state["foreshadow"].values() if f.get("status") == "已回收"
    )
    advancing = sum(1 for f in state["foreshadow"].values() if f.get("status") == "推进")
    claremont = active - resolved
    if claremont > 2:
        hint = f"（另有 {advancing} 条推进中）" if advancing else ""
        emit(
            f"WARNING: Claremont 系数 = {claremont}（已埋 {active} - 已回收 {resolved}）{hint}，伏笔债务过高，建议优先回收旧伏笔",
            error=True,
        )
    elif active > 5 and resolved == 0:
        emit(
            f"WARNING: 已埋伏笔 {active} 个但零回收，建议尽快安排回收",
            error=True,
        )
    return state

def write_views(tracking: Path, views: dict[str, str]) -> None:
    # 上下文携带 next revision，先写它；任何后续失败都会让 hook/check 发现
    # 上下文 revision 与最后提交的 _tracking-state.json 不一致。
    write_if_changed(tracking / "context.md", views["context.md"])
    for relative in sorted(path for path in views if path != "context.md"):
        write_if_changed(tracking / relative, views[relative])
    expected_character_files = {
        Path(relative).name for relative in views if relative.startswith("characters/")
    }
    character_dir = tracking / "characters"
    character_dir.mkdir(parents=True, exist_ok=True)
    for path in character_dir.glob("*.md"):
        if path.name not in expected_character_files:
            path.unlink()


def warn_sizes(views: dict[str, str], delta_payload: str | None = None) -> None:
    if delta_payload is not None and byte_size(delta_payload) > DELTA_TARGET_BYTES:
        emit(
            f"WARNING: chapter delta is {byte_size(delta_payload)} bytes; target is <= {DELTA_TARGET_BYTES}",
            error=True,
        )
    context_size = byte_size(views["context.md"])
    if context_size > CONTEXT_TARGET_BYTES:
        emit(
            f"WARNING: hot context is {context_size} bytes; target is <= {CONTEXT_TARGET_BYTES}",
            error=True,
        )
    for relative, payload in views.items():
        if not relative.startswith("characters/"):
            continue
        size = byte_size(payload)
        if size > SNAPSHOT_TARGET_BYTES:
            emit(
                f"WARNING: character snapshot {Path(relative).stem} is {size} bytes; target is <= {SNAPSHOT_TARGET_BYTES}",
                error=True,
            )

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("init", "commit"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument(
            "--project",
            type=Path,
            required=True,
            help="book project root containing tracking/",
        )
        subparser.add_argument(
            "--input", type=Path, required=True, help="UTF-8 JSON input document"
        )
    check_parser = subparsers.add_parser("check")
    check_parser.add_argument(
        "--project",
        type=Path,
        required=True,
        help="book project root containing tracking/",
    )
    rename_parser = subparsers.add_parser(
        "rename", help="改书名（账本 book_title 字段的合法修改入口，避免手改账本）"
    )
    rename_parser.add_argument(
        "--project", type=Path, required=True, help="book project root containing tracking/"
    )
    rename_parser.add_argument("--title", required=True, help="新书名")
    return parser

def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "init":
            result = initialize(args.project, read_json(args.input))
        elif args.command == "commit":
            result = apply_transaction(args.project, read_json(args.input))
            _archive_tx_after_commit(args.project, args.input)
        elif args.command == "rename":
            state_path = args.project / "tracking" / "_tracking-state.json"
            state = read_json(state_path)
            if not isinstance(state, dict):
                raise TrackingError("账本不可读，无法改名")
            state["book_title"] = str(args.title).strip()[:240]
            normalized = normalize_state(state)
            state_path.write_text(json_payload(normalized), encoding="utf-8")
            for relative, content in render_views(normalized).items():
                target = args.project / "tracking" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            print(f'✅ 书名已改为「{args.title}」（concept.md 如需同步请手动更新）')
            return 0
        else:
            result = check_project(args.project)
    except (TrackingError, OSError, UnicodeError) as exc:
        emit(f"ERROR: {exc}", error=True)
        return 2
    emit(
        json.dumps(
            {
                "last_committed_chapter": result["last_committed_chapter"],
                "state_revision": result["state_revision"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

