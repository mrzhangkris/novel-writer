"""novel-writer 状态账本·渲染层：派生 Markdown 视图。"""

from __future__ import annotations

from typing import Any

from _tracking.schema import (
    CONTEXT_HEADINGS,
    CONTEXT_MAX_BYTES,
    DELTA_MAX_BYTES,
    FORESHADOW_IMPORTANCE,
    SNAPSHOT_MAX_BYTES,
    byte_size,
    require,
)

def render_snapshot(
    name: str, snapshot: dict[str, Any], through_chapter: int, revision: int
) -> str:
    def section(title: str, values: list[str]) -> list[str]:
        return [f"## {title}", *(f"- {item}" for item in values or ["无"]), ""]

    lines = [
        f"# {name}｜当前状态",
        "",
        f"- 状态修订：{revision}",
        f"- 截至章节：第{through_chapter}章",
        f"- 身份：{snapshot['identity']}",
        f"- 位置：{snapshot['location']}",
        f"- 当前目标：{snapshot['goal']}",
        f"- 身心状态：{snapshot['state']}",
        "",
    ]
    lines.extend(section("能力与资源", snapshot["abilities_resources"]))
    lines.extend(section("关键关系", snapshot["relationships"]))
    lines.extend(section("已知信息", snapshot["knowledge"]))
    lines.extend(section("未结事项", snapshot["open_threads"]))
    payload = "\n".join(lines).rstrip() + "\n"
    require(
        byte_size(payload) <= SNAPSHOT_MAX_BYTES,
        f"character snapshot {name} exceeds hard cap of {SNAPSHOT_MAX_BYTES} bytes",
    )
    return payload

def render_foreshadow(rows: dict[str, dict[str, Any]], revision: int) -> str:
    lines = [
        "# 伏笔当前状态",
        "",
        f"> 状态修订：{revision}。每个 ID 只保留一行当前状态；历史变化见 `chapter-deltas/`。",
        "",
        "| ID | 内容 | 埋设章 | 计划回收章 | 状态 | 重要度 | 最近变更章 |",
        "|---|---|---:|---:|---|---|---:|",
    ]
    for identifier in sorted(rows):
        row = rows[identifier]
        planned = (
            f"第{row['planned_resolution_chapter']}章"
            if row["planned_resolution_chapter"]
            else "—"
        )
        lines.append(
            f"| {identifier} | {row['summary']} | 第{row['planted_chapter']}章 | {planned} | "
            f"{row['status']} | {row['importance']} | 第{row['updated_chapter']}章 |"
        )
    return "\n".join(lines) + "\n"

def render_timeline_views(
    events: dict[str, dict[str, Any]], revision: int
) -> tuple[str, str]:
    author_lines = [
        "# 作者真相时间线",
        "",
        f"> 状态修订：{revision}。客观事实与读者认知的权威对照；未来揭示计划仍留在大纲。",
        "",
        "| ID | 首次登记章 | 故事时间 | 客观事实 | 读者当前认知 | 揭示状态 | 实际揭示章 |",
        "|---|---:|---|---|---|---|---:|",
    ]
    reader_lines = [
        "# 读者已知时间线",
        "",
        f"> 状态修订：{revision}。只呈现读者截至当前章节已经知道或相信的内容，不泄露作者侧客观真相。",
        "",
        "| ID | 读者当前认知 | 认知截至章 |",
        "|---|---|---:|",
    ]
    for identifier in sorted(events):
        event = events[identifier]
        reveal = (
            f"第{event['reveal_chapter']}章" if event.get("reveal_chapter") else "—"
        )
        characters = "、".join(event.get("characters", []))
        objective = event["objective_fact"] + (
            f"（涉及：{characters}）" if characters else ""
        )
        author_lines.append(
            f"| {identifier} | 第{event['first_recorded_chapter']}章 | {event['story_time']} | {objective} | "
            f"{event['reader_knowledge']} | {event['reveal_status']} | {reveal} |"
        )
        reader_lines.append(
            f"| {identifier} | {event['reader_knowledge']} | 第{event['updated_chapter']}章 |"
        )
    return "\n".join(author_lines) + "\n", "\n".join(reader_lines) + "\n"

def active_foreshadow_lines(rows: dict[str, dict[str, Any]]) -> list[str]:
    importance = {value: index for index, value in enumerate(FORESHADOW_IMPORTANCE)}
    candidates = [row for row in rows.values() if row["status"] == "已埋"]
    candidates.sort(
        key=lambda row: (
            importance[row["importance"]],
            row["planned_resolution_chapter"] or 10**12,
            row["id"],
        )
    )
    result = []
    for row in candidates[:8]:
        planned = (
            f"第{row['planned_resolution_chapter']}章"
            if row["planned_resolution_chapter"]
            else "回收章未定"
        )
        result.append(
            f"{row['id']}｜{row['summary']}｜埋第{row['planted_chapter']}章｜{planned}｜{row['importance']}"
        )
    return result

def render_context(state: dict[str, Any]) -> str:
    context = state["context"]
    position = context["position"]
    current_chapter = (
        "尚未开篇"
        if state["last_committed_chapter"] == 0
        else f"第{state['last_committed_chapter']}章"
    )
    character_lines = [
        f"{name}｜{state['characters'][name]['identity']}｜{state['characters'][name]['state']}｜"
        f"目标：{state['characters'][name]['goal']}"
        for name in context["active_character_names"]
    ]
    sections: list[tuple[str, list[str]]] = [
        (
            "## 当前位置",
            [
                f"当前章：{current_chapter}",
                f"线程：{context.get('thread', '主线')}",
                f"卷：{position['volume']}（始于第{position['volume_start_chapter']}章）",
                f"故事时间：{position['story_time']}",
                f"场景：{position['scene']}",
            ],
        ),
        ("## 长期约束", context["long_term_constraints"]),
        ("## 核心角色状态", character_lines),
        ("## 活跃伏笔", active_foreshadow_lines(state["foreshadow"])),
        (
            "## 近三章速记",
            [
                f"第{item['chapter']}章｜{item['summary']}"
                for item in context["recent_chapters"]
            ],
        ),
        ("## 下一章承诺", context["next_chapter_commitments"]),
        ("## 连贯性风险", context["continuity_risks"]),
    ]
    lines = [
        f"# 写作连续性上下文 — {state['book_title']}",
        "",
        f"> 状态修订：{state['state_revision']}。截至当前章的续写状态卡，只放下一章真正需要的连续性状态。",
        "",
    ]
    for heading, values in sections:
        lines.append(heading)
        lines.extend(f"- {value}" for value in values or ["无"])
        lines.append("")
    payload = "\n".join(lines).rstrip() + "\n"
    headings = tuple(line for line in payload.splitlines() if line.startswith("## "))
    require(
        headings == CONTEXT_HEADINGS,
        "generated context headings do not match the seven-section schema",
    )
    require(
        byte_size(payload) <= CONTEXT_MAX_BYTES,
        f"hot context exceeds {CONTEXT_MAX_BYTES} bytes",
    )
    return payload

def render_delta(
    chapter: int, title: str, delta: dict[str, Any], core_names: set[str]
) -> str:
    lines = [
        f"# 第{chapter:03d}章 · {title}",
        f"- 结果：{delta['result']}",
        "- 下一章承诺：" + ("；".join(delta["next_chapter_commitments"]) or "无"),
        "",
        "## 角色变化",
    ]
    lines.extend(
        f"- {item['name']}｜{'核心' if item['name'] in core_names else '临时'}｜{item['change']}"
        for item in delta["character_changes"]
    )
    if not delta["character_changes"]:
        lines.append("- 无")
    lines.extend(["", "## 伏笔变化"])
    for item in delta["foreshadow_changes"]:
        if item["action"] == "delete":
            lines.append(f"- {item['id']}｜删除当前登记")
        else:
            planned = (
                f"第{item['planned_resolution_chapter']}章"
                if item["planned_resolution_chapter"]
                else "未定"
            )
            lines.append(
                f"- {item['id']}｜{item['status']}｜{item['summary']}｜回收{planned}"
            )
    if not delta["foreshadow_changes"]:
        lines.append("- 无")
    lines.extend(["", "## 时间与揭示"])
    for item in delta["timeline_events"]:
        if item["action"] == "delete":
            lines.append(f"- {item['id']}｜删除当前登记")
        else:
            lines.append(
                f"- {item['id']}｜{item['story_time']}｜事实：{item['objective_fact']}｜"
                f"读者：{item['reader_knowledge']}｜{item['reveal_status']}"
            )
    if not delta["timeline_events"]:
        lines.append("- 无")
    lines.extend(["", "## 连贯性约束"])
    lines.extend(f"- {item}" for item in delta["constraints"])
    if not delta["constraints"]:
        lines.append("- 无")
    retired = delta.get("retired_context_items", []) + [
        f"角色状态：{name}" for name in delta.get("retired_characters", [])
    ]
    if retired:
        # 退役条目在此留档，续写状态卡收缩后仍可回查当初撤下了什么。
        lines.extend(["", "## 本章退役登记"])
        lines.extend(f"- {item}" for item in retired)
    if delta.get("new_abilities"):
        lines.extend(["", "## 本章新能力/概念声明"])
        lines.extend(f"- {item}" for item in delta["new_abilities"])
    if delta.get("rule_overrides"):
        lines.extend(["", "## 本章规则突破登记（Override）"])
        lines.extend(
            f"- 第{row['effective_chapter']}章｜{row['rule']}｜理由：{row['reason']}｜代价：{row['payback']}"
            for row in delta["rule_overrides"]
        )
    payload = "\n".join(lines) + "\n"
    size = byte_size(payload)
    require(
        size <= DELTA_MAX_BYTES,
        f"chapter delta is {size} bytes; hard cap is {DELTA_MAX_BYTES}",
    )
    return payload

def render_overrides(overrides: list[dict[str, Any]], revision: int) -> str:
    lines = [
        "# 设定演进账本（Overrides）",
        "",
        f"> 状态修订：{revision}。剧情合法打破世界硬规则时在此登记；未登记的规则突破会被拒收。",
        "",
        "| 生效章 | 打破的规则 | 剧情理由 | 代价/收束 |",
        "|---|---:|---|---|",
    ]
    for row in overrides:
        lines.append(
            f"| 第{row['effective_chapter']}章 | {row['rule']} | {row['reason']} | {row['payback']} |"
        )
    return "\n".join(lines) + "\n"

def render_threads(state: dict[str, Any]) -> str:
    """线束视图：每条叙事线的停点快照。多线书切线时先读这个。"""
    threads = state.get("threads", {})
    current = state["context"].get("thread", "主线")
    lines = [
        "# 叙事线束（threads）",
        "",
        "> 每条线一行：上次停点 + 本线角色 + 未答悬念。切回某条线前先读对应行。",
        "> 当前线程：" + current + "。",
        "",
    ]
    if not threads:
        lines.append("（无——单线叙事，或尚未提交过带 thread 的事务）")
        return "\n".join(lines) + "\n"
    lines.append("| 线名 | 停在第几章 | 场景 | 本线角色 | 未答悬念 |")
    lines.append("|------|-----------|------|---------|---------|")
    for name, entry in sorted(threads.items()):
        marker = "▶" if name == current else " "
        lines.append(
            f"| {marker} {name} | {entry['last_stop_chapter']} | "
            f"{entry['position']['scene'] or entry['position']['story_time'] or '—'} | "
            f"{'、'.join(entry['active_character_names']) or '—'} | "
            f"{'；'.join(entry['open_questions']) or '—'} |"
        )
    return "\n".join(lines) + "\n"

def render_views(state: dict[str, Any]) -> dict[str, str]:
    revision = state["state_revision"]
    views = {
        "context.md": render_context(state),
        "foreshadows.md": render_foreshadow(state["foreshadow"], revision),
        "overrides.md": render_overrides(state["overrides"], revision),
        "threads.md": render_threads(state),
    }
    author, reader = render_timeline_views(state["timeline"], revision)
    views["timeline/author-truth.md"] = author
    views["timeline/reader-known.md"] = reader
    for name, snapshot in state["characters"].items():
        views[f"characters/{name}.md"] = render_snapshot(
            name, snapshot, state["last_committed_chapter"], revision
        )
    return views

