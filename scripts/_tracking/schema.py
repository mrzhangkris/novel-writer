"""novel-writer 状态账本·协议层：常量、校验与规范化。

本模块只做纯函数校验/规范化，不做任何文件读写与渲染。
tracking_commit.py（CLI）、_tracking/merge.py、_tracking/render.py 共享本层。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

INPUT_SCHEMA_VERSION = 2  # v1 事务（无 items/secrets/pledges/plot_points）仍被接受
TRACKING_SCHEMA_VERSION = 5  # v5：+items/secrets/pledges 维度、snapshot.alive、context.active_scene；v4 账本缺省键按空处理
DELTA_TARGET_BYTES = 1536
# 4096：双伏笔章实测 3072 差 1 字节爆表（knowledge 数组是大头）；1536 仍为软目标
DELTA_MAX_BYTES = 4096
CONTEXT_TARGET_BYTES = 8192
CONTEXT_MAX_BYTES = 12288
SNAPSHOT_TARGET_BYTES = 4096
SNAPSHOT_MAX_BYTES = 8192

CONTEXT_HEADINGS = (
    "## 当前位置",
    "## 长期约束",
    "## 核心角色状态",
    "## 活跃伏笔",
    "## 写手发明",
    "## 近三章速记",
    "## 下一章承诺",
    "## 连贯性风险",
)
FORESHADOW_STATUSES = ("已埋", "推进", "已回收", "已过期", "放弃")
FORESHADOW_IMPORTANCE = ("高", "中", "低")
REVEAL_STATUSES = ("未揭示", "部分揭示", "已揭示")
HOSTILE_WORDS = (
    "敌对",
    "反目",
    "死敌",
    "宿敌",
    "为敌",
    "仇视",
    "结怨",
    "仇人",
    "敌人",
    "对立",
)
FRIENDLY_WORDS = (
    "结盟",
    "和解",
    "和好",
    "结义",
    "交好",
    "同盟",
    "盟友",
    "友人",
    "挚友",
    "化敌为友",
)
CAUSAL_WORDS = (
    "因为",
    "由于",
    "经过",
    "一番",
    "一场",
    "之后",
    "于是",
    "最终",
    "化解",
    "转变",
    "从而",
    "致使",
    "导致",
    "从此",
)
INVALID_FILE_CHARS = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")
FORESHADOW_ID = re.compile(r"^F\d{3,}$")
EVENT_ID = re.compile(r"^E\d{3,}$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}
RETIRED_TRACKING_PATHS = (
    "_tracking-meta.json",
    "阶段摘要.md",
    "角色状态.md",
    "时间线.md",
    "摘要",
    "时间线/事件库.json",
)
RETIRED_ARCHIVE_DIR = "_legacy"


class TrackingError(ValueError):
    """Expected validation or tracking-state error."""

def require(condition: bool, message: str) -> None:
    if not condition:
        raise TrackingError(message)

def as_mapping(value: object, label: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{label} must be a JSON object")
    return value

def as_list(value: object, label: str) -> list[Any]:
    require(isinstance(value, list), f"{label} must be a JSON array")
    return value

def as_int(value: object, label: str, *, minimum: int = 0) -> int:
    require(
        isinstance(value, int) and not isinstance(value, bool),
        f"{label} must be an integer",
    )
    require(value >= minimum, f"{label} must be >= {minimum}")
    return value

def require_known_keys(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = set(mapping) - allowed
    require(
        not unknown,
        f"{label} contains unsupported fields: {', '.join(sorted(unknown))}",
    )

def clean_text(
    value: object, label: str, *, allow_empty: bool = False, max_bytes: int = 768
) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    cleaned = " ".join(value.replace("|", "｜").split())
    require(allow_empty or bool(cleaned), f"{label} must not be empty")
    cleaned_bytes = len(cleaned.encode("utf-8"))
    require(
        cleaned_bytes <= max_bytes,
        f"{label} 超长：实际 {cleaned_bytes} 字节 / 上限 {max_bytes} 字节，请压缩（如 summary 只留本章净变化）",
    )
    return cleaned

def clean_string_list(
    value: object,
    label: str,
    *,
    maximum: int | None = None,
    item_max_bytes: int = 384,
) -> list[str]:
    values = as_list(value, label)
    if maximum is not None:
        require(len(values) <= maximum, f"{label} may contain at most {maximum} items")
    return [
        clean_text(item, f"{label}[{index}]", max_bytes=item_max_bytes)
        for index, item in enumerate(values)
    ]

def safe_file_component(value: object, label: str) -> str:
    name = unicodedata.normalize("NFC", clean_text(value, label, max_bytes=180))
    require(
        not INVALID_FILE_CHARS.search(name),
        f"{label} contains an invalid filename character",
    )
    require(
        name not in {".", ".."} and not name.endswith((".", " ")),
        f"{label} is not a safe filename",
    )
    require(
        name.split(".", 1)[0].upper() not in WINDOWS_RESERVED_NAMES,
        f"{label} is reserved on Windows",
    )
    return name

def portable_name_key(name: str) -> str:
    return unicodedata.normalize("NFC", name).casefold()

def byte_size(text: str) -> int:
    return len(text.encode("utf-8"))

def validate_position(value: object, label: str = "context.position") -> dict[str, Any]:
    position = as_mapping(value, label)
    require_known_keys(
        position, {"volume", "volume_start_chapter", "story_time", "scene"}, label
    )
    return {
        "volume": safe_file_component(position.get("volume"), f"{label}.volume"),
        "volume_start_chapter": as_int(
            position.get("volume_start_chapter"),
            f"{label}.volume_start_chapter",
            minimum=1,
        ),
        "story_time": clean_text(
            position.get("story_time"), f"{label}.story_time", max_bytes=240
        ),
        "scene": clean_text(position.get("scene"), f"{label}.scene", max_bytes=240),
    }

def validate_thread_entry(value: object, label: str) -> dict[str, Any]:
    """单条线束记录：某条叙事线上次停点的完整快照。"""
    entry = as_mapping(value, label)
    require_known_keys(
        entry,
        {"last_stop_chapter", "position", "active_character_names", "open_questions"},
        label,
    )
    return {
        "last_stop_chapter": as_int(
            entry.get("last_stop_chapter"), f"{label}.last_stop_chapter", minimum=0
        ),
        "position": validate_position(entry.get("position"), f"{label}.position"),
        "active_character_names": [
            safe_file_component(name, f"{label}.active_character_names[{index}]")
            for index, name in enumerate(
                as_list(
                    entry.get("active_character_names", []),
                    f"{label}.active_character_names",
                )
            )
        ],
        "open_questions": clean_string_list(
            entry.get("open_questions", []), f"{label}.open_questions", maximum=6
        ),
    }

def validate_threads(value: object) -> dict[str, dict[str, Any]]:
    """线束表：线名 -> 线束记录。缺省空表（单线书不需要）。"""
    raw = as_mapping(value, "tracking state.threads")
    threads: dict[str, dict[str, Any]] = {}
    for name, entry in raw.items():
        threads[safe_file_component(name, "threads key")] = validate_thread_entry(
            entry, f"threads.{name}"
        )
    return threads

def normalize_snapshot(value: object, label: str) -> dict[str, Any]:
    snapshot = as_mapping(value, label)
    require_known_keys(
        snapshot,
        {
            "identity",
            "location",
            "goal",
            "state",
            "alive",
            "abilities_resources",
            "relationships",
            "knowledge",
            "open_threads",
        },
        label,
    )
    alive_raw = snapshot.get("alive", True)
    require(
        isinstance(alive_raw, bool),
        f"{label}.alive must be a boolean (角色是否在世；死亡即写 false)",
    )
    return {
        "identity": clean_text(
            snapshot.get("identity"), f"{label}.identity", max_bytes=240
        ),
        "location": clean_text(
            snapshot.get("location"), f"{label}.location", max_bytes=240
        ),
        "goal": clean_text(snapshot.get("goal"), f"{label}.goal", max_bytes=300),
        "state": clean_text(snapshot.get("state"), f"{label}.state", max_bytes=300),
        "alive": alive_raw,
        "abilities_resources": clean_string_list(
            snapshot.get("abilities_resources", []), f"{label}.abilities_resources"
        ),
        "relationships": clean_string_list(
            snapshot.get("relationships", []), f"{label}.relationships"
        ),
        "knowledge": clean_string_list(
            snapshot.get("knowledge", []), f"{label}.knowledge"
        ),
        "open_threads": clean_string_list(
            snapshot.get("open_threads", []), f"{label}.open_threads"
        ),
    }

def normalize_snapshots(
    value: object, label: str = "character_snapshots"
) -> dict[str, dict[str, Any]]:
    snapshots = as_mapping(value, label)
    normalized: dict[str, dict[str, Any]] = {}
    portable_names: set[str] = set()
    for raw_name, raw_snapshot in snapshots.items():
        name = safe_file_component(raw_name, f"{label} character name")
        key = portable_name_key(name)
        require(
            key not in portable_names,
            f"{label} contains a cross-platform duplicate character {name}",
        )
        portable_names.add(key)
        normalized[name] = normalize_snapshot(raw_snapshot, f"{label}.{name}")
    return normalized

def normalize_foreshadow_change(
    value: object,
    label: str,
    *,
    allow_delete: bool,
    through_chapter: int,
) -> dict[str, Any]:
    row = as_mapping(value, label)
    require_known_keys(
        row,
        {
            "action",
            "id",
            "summary",
            "planted_chapter",
            "planned_resolution_chapter",
            "status",
            "importance",
            "progress_note",
        },
        label,
    )
    action = clean_text(row.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(
        action in ({"upsert", "delete"} if allow_delete else {"upsert"}),
        f"{label}.action is invalid",
    )
    identifier = clean_text(row.get("id"), f"{label}.id", max_bytes=24)
    require(
        FORESHADOW_ID.fullmatch(identifier) is not None,
        f"{label}.id must look like F001",
    )
    if action == "delete":
        return {"action": action, "id": identifier}
    planted_chapter = as_int(
        row.get("planted_chapter"), f"{label}.planted_chapter", minimum=1
    )
    require(
        planted_chapter <= through_chapter,
        f"{label}.planted_chapter cannot be in the future",
    )
    planned_raw = row.get("planned_resolution_chapter")
    planned_chapter = (
        None
        if planned_raw is None
        else as_int(planned_raw, f"{label}.planned_resolution_chapter", minimum=1)
    )
    require(
        planned_chapter is None or planned_chapter >= planted_chapter,
        f"{label}.planned_resolution_chapter cannot precede planted_chapter",
    )
    status = clean_text(row.get("status"), f"{label}.status", max_bytes=24)
    importance = clean_text(row.get("importance"), f"{label}.importance", max_bytes=12)
    require(
        status in FORESHADOW_STATUSES,
        f"{label}.status must be one of {FORESHADOW_STATUSES}",
    )
    require(
        importance in FORESHADOW_IMPORTANCE,
        f"{label}.importance must be one of {FORESHADOW_IMPORTANCE}",
    )
    # 可选进度注记（「推进」态的进度载体）：缺省 None 表示「本章未更新进度」，
    # 声明式覆盖旧值——陈旧进度比空进度更误导。
    raw_progress = row.get("progress_note")
    progress_note = (
        None
        if raw_progress is None
        else clean_text(raw_progress, f"{label}.progress_note", max_bytes=360)
    )
    return {
        "action": action,
        "id": identifier,
        "summary": clean_text(row.get("summary"), f"{label}.summary", max_bytes=360),
        "planted_chapter": planted_chapter,
        "planned_resolution_chapter": planned_chapter,
        "status": status,
        "importance": importance,
        "progress_note": progress_note,
    }

def normalize_foreshadow_state(
    value: object, last_chapter: int
) -> dict[str, dict[str, Any]]:
    rows = as_mapping(value, "tracking state.foreshadow")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_row in rows.items():
        identifier = clean_text(
            raw_identifier, "tracking state.foreshadow ID", max_bytes=24
        )
        row = as_mapping(raw_row, f"tracking state.foreshadow.{identifier}")
        require_known_keys(
            row,
            {
                "id",
                "summary",
                "planted_chapter",
                "planned_resolution_chapter",
                "status",
                "importance",
                "updated_chapter",
                "progress_note",
            },
            f"tracking state.foreshadow.{identifier}",
        )
        require(
            row.get("id") == identifier,
            f"tracking state.foreshadow.{identifier}.id does not match its key",
        )
        change = normalize_foreshadow_change(
            {
                "action": "upsert",
                **{
                    key: value for key, value in row.items() if key != "updated_chapter"
                },
            },
            f"tracking state.foreshadow.{identifier}",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        change.pop("action")
        updated = as_int(
            row.get("updated_chapter"),
            f"tracking state.foreshadow.{identifier}.updated_chapter",
            minimum=1,
        )
        require(
            updated <= last_chapter,
            f"foreshadow {identifier} updates after current chapter",
        )
        change["updated_chapter"] = updated
        normalized[identifier] = change
    return normalized

def normalize_timeline_change(
    value: object,
    label: str,
    *,
    allow_delete: bool,
    through_chapter: int,
) -> dict[str, Any]:
    event = as_mapping(value, label)
    require_known_keys(
        event,
        {
            "action",
            "id",
            "story_time",
            "objective_fact",
            "reader_knowledge",
            "reveal_status",
            "reveal_chapter",
            "characters",
        },
        label,
    )
    action = clean_text(event.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(
        action in ({"upsert", "delete"} if allow_delete else {"upsert"}),
        f"{label}.action is invalid",
    )
    identifier = clean_text(event.get("id"), f"{label}.id", max_bytes=24)
    require(
        EVENT_ID.fullmatch(identifier) is not None, f"{label}.id must look like E001"
    )
    if action == "delete":
        return {"action": action, "id": identifier}
    reveal_status = clean_text(
        event.get("reveal_status"), f"{label}.reveal_status", max_bytes=24
    )
    require(
        reveal_status in REVEAL_STATUSES,
        f"{label}.reveal_status must be one of {REVEAL_STATUSES}",
    )
    reveal_raw = event.get("reveal_chapter")
    reveal_chapter = (
        None
        if reveal_raw is None
        else as_int(reveal_raw, f"{label}.reveal_chapter", minimum=1)
    )
    if reveal_status == "未揭示":
        require(
            reveal_chapter is None,
            f"{label} must not put a future reveal chapter in established timeline facts",
        )
    else:
        require(
            reveal_chapter is not None,
            f"{label}.reveal_chapter is required once revealed",
        )
        require(
            reveal_chapter <= through_chapter,
            f"{label}.reveal_chapter cannot be in the future",
        )
    return {
        "action": action,
        "id": identifier,
        "story_time": clean_text(
            event.get("story_time"), f"{label}.story_time", max_bytes=240
        ),
        "objective_fact": clean_text(
            event.get("objective_fact"), f"{label}.objective_fact", max_bytes=480
        ),
        "reader_knowledge": clean_text(
            event.get("reader_knowledge"), f"{label}.reader_knowledge", max_bytes=480
        ),
        "reveal_status": reveal_status,
        "reveal_chapter": reveal_chapter,
        "characters": clean_string_list(
            event.get("characters", []),
            f"{label}.characters",
            maximum=12,
            item_max_bytes=120,
        ),
    }

def normalize_timeline_state(
    value: object, last_chapter: int
) -> dict[str, dict[str, Any]]:
    events = as_mapping(value, "tracking state.timeline")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_identifier, raw_event in events.items():
        identifier = clean_text(
            raw_identifier, "tracking state.timeline ID", max_bytes=24
        )
        event = as_mapping(raw_event, f"tracking state.timeline.{identifier}")
        require_known_keys(
            event,
            {
                "id",
                "story_time",
                "objective_fact",
                "reader_knowledge",
                "reveal_status",
                "reveal_chapter",
                "characters",
                "first_recorded_chapter",
                "updated_chapter",
            },
            f"tracking state.timeline.{identifier}",
        )
        require(
            event.get("id") == identifier,
            f"tracking state.timeline.{identifier}.id does not match its key",
        )
        change = normalize_timeline_change(
            {
                "action": "upsert",
                **{
                    key: value
                    for key, value in event.items()
                    if key not in {"first_recorded_chapter", "updated_chapter"}
                },
            },
            f"tracking state.timeline.{identifier}",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        change.pop("action")
        first = as_int(
            event.get("first_recorded_chapter"),
            f"tracking state.timeline.{identifier}.first_recorded_chapter",
            minimum=1,
        )
        updated = as_int(
            event.get("updated_chapter"),
            f"tracking state.timeline.{identifier}.updated_chapter",
            minimum=1,
        )
        require(
            first <= last_chapter,
            f"timeline event {identifier} starts after current chapter",
        )
        require(
            updated <= last_chapter,
            f"timeline event {identifier} updates after current chapter",
        )
        change["first_recorded_chapter"] = first
        change["updated_chapter"] = updated
        normalized[identifier] = change
    return normalized

def validate_context_input(
    value: object, *, include_initial_fields: bool
) -> dict[str, Any]:
    context = as_mapping(value, "context")
    allowed = {
        "position",
        "long_term_constraints",
        "active_character_names",
        "continuity_risks",
        "thread",
        "active_scene",
    }
    if include_initial_fields:
        allowed.update({"recent_chapters", "next_chapter_commitments"})
    require_known_keys(context, allowed, "context")
    normalized: dict[str, Any] = {
        "position": validate_position(context.get("position")),
        "active_scene": clean_text(
            context.get("active_scene", ""),
            "context.active_scene",
            allow_empty=True,
            max_bytes=240,
        ),
        "long_term_constraints": clean_string_list(
            context.get("long_term_constraints", []),
            "context.long_term_constraints",
            maximum=6,
        ),
        "active_character_names": [
            safe_file_component(name, f"context.active_character_names[{index}]")
            for index, name in enumerate(
                as_list(
                    context.get("active_character_names", []),
                    "context.active_character_names",
                )
            )
        ],
        "continuity_risks": clean_string_list(
            context.get("continuity_risks", []), "context.continuity_risks", maximum=5
        ),
        "thread": clean_text(
            context.get("thread", "主线"), "context.thread", max_bytes=80
        ),
    }
    require(
        len(normalized["active_character_names"]) <= 6,
        "context.active_character_names may contain at most 6 names",
    )
    require(
        len({portable_name_key(name) for name in normalized["active_character_names"]})
        == len(normalized["active_character_names"]),
        "context.active_character_names contains cross-platform duplicates",
    )
    if include_initial_fields:
        recent: list[dict[str, Any]] = []
        for index, raw_item in enumerate(
            as_list(context.get("recent_chapters", []), "context.recent_chapters")
        ):
            item = as_mapping(raw_item, f"context.recent_chapters[{index}]")
            require_known_keys(
                item, {"chapter", "summary"}, f"context.recent_chapters[{index}]"
            )
            recent.append(
                {
                    "chapter": as_int(
                        item.get("chapter"),
                        f"context.recent_chapters[{index}].chapter",
                        minimum=1,
                    ),
                    "summary": clean_text(
                        item.get("summary"),
                        f"context.recent_chapters[{index}].summary",
                        max_bytes=360,
                    ),
                }
            )
        require(len(recent) <= 3, "context.recent_chapters may contain at most 3 items")
        normalized["recent_chapters"] = recent
        normalized["next_chapter_commitments"] = clean_string_list(
            context.get("next_chapter_commitments", []),
            "context.next_chapter_commitments",
            maximum=5,
        )
    return normalized

LEDGER_CHANGE_ACTIONS = ("upsert", "delete")


def normalize_ledger_change(
    value: object,
    label: str,
    fields: dict[str, type],
    *,
    allow_delete: bool,
) -> dict[str, Any]:
    """items/secrets/pledges 三类台账变更的通用归一化：按名 upsert/delete。

    fields 声明额外字段及类型：str 必填、bool/int 可选（bool 缺省 False、int 缺省 None）。"""
    row = as_mapping(value, label)
    allowed = {"action", "name", *fields}
    require_known_keys(row, allowed, label)
    action = clean_text(row.get("action", "upsert"), f"{label}.action", max_bytes=24)
    require(
        action in (LEDGER_CHANGE_ACTIONS if allow_delete else ("upsert",)),
        f"{label}.action is invalid",
    )
    name = safe_file_component(row.get("name"), f"{label}.name")
    if action == "delete":
        return {"action": action, "name": name}
    result: dict[str, Any] = {"action": action, "name": name}
    for field, field_type in fields.items():
        if field_type is bool:
            raw = row.get(field, False)
            require(
                isinstance(raw, bool), f"{label}.{field} must be a boolean"
            )
            result[field] = raw
        elif field_type is int:
            raw = row.get(field)
            result[field] = (
                None
                if raw is None
                else as_int(raw, f"{label}.{field}", minimum=1)
            )
        else:
            result[field] = clean_text(
                row.get(field), f"{label}.{field}", max_bytes=360
            )
    return result


def normalize_ledger_state(
    value: object,
    label: str,
    fields: dict[str, type],
    last_chapter: int,
) -> dict[str, dict[str, Any]]:
    rows = as_mapping(value, label)
    normalized: dict[str, dict[str, Any]] = {}
    for raw_name, raw_row in rows.items():
        row = as_mapping(raw_row, f"{label}.{raw_name}")
        require_known_keys(row, {"name", "updated_chapter", *fields}, f"{label}.{raw_name}")
        require(
            row.get("name") == raw_name,
            f"{label}.{raw_name}.name does not match its key",
        )
        change = normalize_ledger_change(
            {"action": "upsert", **{k: v for k, v in row.items() if k != "updated_chapter"}},
            f"{label}.{raw_name}",
            fields,
            allow_delete=False,
        )
        change.pop("action")
        updated = as_int(
            row.get("updated_chapter"), f"{label}.{raw_name}.updated_chapter", minimum=1
        )
        require(
            updated <= last_chapter,
            f"{raw_name} updates after current chapter ({label})",
        )
        change["updated_chapter"] = updated
        normalized[change["name"]] = change
    return normalized


# 三类台账的字段契约：道具（持有者）/秘密（知情者+是否揭示）/誓约（兑现章+状态）
ITEM_FIELDS: dict[str, type] = {"holder": str, "note": str}
SECRET_FIELDS: dict[str, type] = {"known_by": str, "revealed": bool}
PLEDGE_FIELDS: dict[str, type] = {"due_chapter": int, "status": str}
PLEDGE_STATUSES = ("未兑现", "已兑现", "已破誓")

def normalize_rule_override(
    value: object, label: str, *, through_chapter: int
) -> dict[str, Any]:
    row = as_mapping(value, label)
    require_known_keys(
        row, {"rule", "reason", "effective_chapter", "payback"}, label
    )
    return {
        "rule": clean_text(row.get("rule"), f"{label}.rule", max_bytes=240),
        "reason": clean_text(row.get("reason"), f"{label}.reason", max_bytes=360),
        "effective_chapter": as_int(
            row.get("effective_chapter"),
            f"{label}.effective_chapter",
            minimum=1,
        ),
        "payback": clean_text(
            row.get("payback", "未定"),
            f"{label}.payback",
            allow_empty=False,
            max_bytes=360,
        ),
    }

def normalize_overrides_state(
    value: object, last_chapter: int
) -> list[dict[str, Any]]:
    rows = as_list(value, "tracking state.overrides")
    overrides: list[dict[str, Any]] = []
    for index, raw in enumerate(rows):
        row = normalize_rule_override(
            raw, f"tracking state.overrides[{index}]", through_chapter=last_chapter
        )
        require(
            row["effective_chapter"] <= last_chapter,
            f"override {index} effective_chapter exceeds current chapter",
        )
        overrides.append(row)
    return overrides

def normalize_inventions_state(
    value: object, last_chapter: int
) -> list[dict[str, Any]]:
    """写手发明申报的存量账：[{chapter, text}]，按章记录（修订整章替换）。"""
    inventions = as_list(value, "tracking state.inventions")
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(inventions):
        item = as_mapping(raw, f"tracking state.inventions[{index}]")
        require_known_keys(
            item, {"chapter", "text"}, f"tracking state.inventions[{index}]"
        )
        chap = as_int(item.get("chapter"), f"tracking state.inventions[{index}].chapter")
        require(
            1 <= chap <= last_chapter,
            f"tracking state.inventions[{index}] chapter {chap} exceeds last committed chapter",
        )
        out.append(
            {
                "chapter": chap,
                "text": clean_text(
                    item.get("text"),
                    f"tracking state.inventions[{index}].text",
                    max_bytes=360,
                ),
            }
        )
    return out

def normalize_delta(
    value: object,
    *,
    through_chapter: int,
    snapshots: dict[str, dict[str, Any]],
    existing_core_names: dict[str, str],
) -> dict[str, Any]:
    delta = as_mapping(value, "delta")
    require_known_keys(
        delta,
        {
            "result",
            "character_changes",
            "foreshadow_changes",
            "timeline_events",
            "plot_points",
            "items",
            "secrets",
            "pledges",
            "constraints",
            "next_chapter_commitments",
            "retired_context_items",
            "retired_characters",
            "new_abilities",
            "rule_overrides",
            "inventions",
        },
        "delta",
    )
    retired_characters = [
        safe_file_component(name, f"delta.retired_characters[{index}]")
        for index, name in enumerate(
            as_list(delta.get("retired_characters", []), "delta.retired_characters")
        )
    ]
    retired_keys = [portable_name_key(name) for name in retired_characters]
    require(
        len(retired_keys) == len(set(retired_keys)),
        "delta.retired_characters contains duplicate characters",
    )
    retiring = set(retired_keys)
    character_changes: list[dict[str, Any]] = []
    for index, raw_change in enumerate(
        as_list(delta.get("character_changes", []), "delta.character_changes")
    ):
        change = as_mapping(raw_change, f"delta.character_changes[{index}]")
        require_known_keys(
            change, {"name", "change"}, f"delta.character_changes[{index}]"
        )
        name = safe_file_component(
            change.get("name"), f"delta.character_changes[{index}].name"
        )
        existing = existing_core_names.get(portable_name_key(name))
        is_core = name in snapshots or existing is not None
        # 本章退役的角色记录最后一次变化即可，不必再交一份马上要删的快照。
        require(
            not is_core or name in snapshots or portable_name_key(name) in retiring,
            f"core character {name} changed but has no current snapshot",
        )
        character_changes.append(
            {
                "name": name,
                "change": clean_text(
                    change.get("change"),
                    f"delta.character_changes[{index}].change",
                    max_bytes=360,
                ),
            }
        )
    character_keys = [portable_name_key(item["name"]) for item in character_changes]
    require(
        len(character_keys) == len(set(character_keys)),
        "delta.character_changes contains duplicate characters",
    )
    foreshadow_changes = [
        normalize_foreshadow_change(
            raw,
            f"delta.foreshadow_changes[{index}]",
            allow_delete=True,
            through_chapter=through_chapter,
        )
        for index, raw in enumerate(
            as_list(delta.get("foreshadow_changes", []), "delta.foreshadow_changes")
        )
    ]
    timeline_events = [
        normalize_timeline_change(
            raw,
            f"delta.timeline_events[{index}]",
            allow_delete=True,
            through_chapter=through_chapter,
        )
        for index, raw in enumerate(
            as_list(delta.get("timeline_events", []), "delta.timeline_events")
        )
    ]
    require(
        len({item["id"] for item in foreshadow_changes}) == len(foreshadow_changes),
        "delta.foreshadow_changes contains duplicate IDs",
    )
    require(
        len({item["id"] for item in timeline_events}) == len(timeline_events),
        "delta.timeline_events contains duplicate IDs",
    )
    require(
        set(snapshots).issubset({item["name"] for item in character_changes}),
        "character_snapshots must contain exactly the core characters changed by this transaction",
    )
    new_abilities = clean_string_list(
        delta.get("new_abilities", []),
        "delta.new_abilities",
        maximum=12,
        item_max_bytes=120,
    )
    plot_points = clean_string_list(
        delta.get("plot_points", []),
        "delta.plot_points",
        maximum=8,
        item_max_bytes=200,
    )
    ledger_changes: dict[str, list[dict[str, Any]]] = {}
    for key, fields in (
        ("items", ITEM_FIELDS),
        ("secrets", SECRET_FIELDS),
        ("pledges", PLEDGE_FIELDS),
    ):
        ledger_changes[key] = [
            normalize_ledger_change(
                raw,
                f"delta.{key}[{index}]",
                fields,
                allow_delete=True,
            )
            for index, raw in enumerate(as_list(delta.get(key, []), f"delta.{key}"))
        ]
        require(
            len({item["name"] for item in ledger_changes[key]}) == len(ledger_changes[key]),
            f"delta.{key} contains duplicate names",
        )
    pledges = ledger_changes["pledges"]
    require(
        len(pledges) <= 5,
        "delta.pledges may contain at most 5 items per chapter",
    )
    for change in pledges:
        if change["action"] == "delete":
            continue
        require(
            change.get("status") in PLEDGE_STATUSES,
            f"delta.pledges[{change['name']}].status must be one of {PLEDGE_STATUSES}",
        )
    rule_overrides = [
        normalize_rule_override(
            raw,
            f"delta.rule_overrides[{index}]",
            through_chapter=through_chapter,
        )
        for index, raw in enumerate(
            as_list(delta.get("rule_overrides", []), "delta.rule_overrides")
        )
    ]
    require(
        len(rule_overrides) <= 3,
        "delta.rule_overrides may contain at most 3 items per chapter",
    )
    return {
        # result 同时渲染为下一章的 recent_chapters.summary（上限 360B），两处共用同一上限
        "result": clean_text(delta.get("result"), "delta.result", max_bytes=360),
        "character_changes": character_changes,
        "foreshadow_changes": foreshadow_changes,
        "timeline_events": timeline_events,
        "plot_points": plot_points,
        "items": ledger_changes["items"],
        "secrets": ledger_changes["secrets"],
        "pledges": pledges,
        "constraints": clean_string_list(
            delta.get("constraints", []), "delta.constraints", maximum=6
        ),
        "next_chapter_commitments": clean_string_list(
            delta.get("next_chapter_commitments", []),
            "delta.next_chapter_commitments",
            maximum=5,
        ),
        "retired_context_items": clean_string_list(
            delta.get("retired_context_items", []),
            "delta.retired_context_items",
            maximum=11,
        ),
        "retired_characters": retired_characters,
        "new_abilities": new_abilities,
        "rule_overrides": rule_overrides,
        # 写手发明申报：正文确立的计划外设定/人物/事实（一句一条，≤6 条）。
        # 进账本后下一章 spec 组装可见——防写手发明与后续章纲静默冲突。
        "inventions": clean_string_list(
            delta.get("inventions", []),
            "delta.inventions",
            maximum=6,
            item_max_bytes=360,
        ),
    }

def normalize_state(document: object) -> dict[str, Any]:
    root = as_mapping(document, "tracking state")
    require_known_keys(
        root,
        {
            "schema_version",
            "book_title",
            "last_committed_chapter",
            "imported_through_chapter",
            "state_revision",
            "context",
            "characters",
            "foreshadow",
            "timeline",
            "items",
            "secrets",
            "pledges",
            "overrides",
            "threads",
            "inventions",
        },
        "tracking state",
    )
    require(
        root.get("schema_version") in (4, TRACKING_SCHEMA_VERSION),
        "tracking state schema is unsupported",
    )
    last_chapter = as_int(
        root.get("last_committed_chapter"), "tracking state.last_committed_chapter"
    )
    imported_through = as_int(
        root.get("imported_through_chapter"), "tracking state.imported_through_chapter"
    )
    require(
        imported_through <= last_chapter,
        "imported chapter cutoff exceeds current chapter",
    )
    context = validate_context_input(root.get("context"), include_initial_fields=True)
    require(
        context["position"]["volume_start_chapter"] <= max(1, last_chapter),
        "context.position.volume_start_chapter is after the current writing position",
    )
    recent_numbers = [item["chapter"] for item in context["recent_chapters"]]
    require(
        recent_numbers == sorted(recent_numbers),
        "context.recent_chapters must be ordered",
    )
    require(
        len(recent_numbers) == len(set(recent_numbers)),
        "context.recent_chapters contains duplicates",
    )
    require(
        all(chapter <= last_chapter for chapter in recent_numbers),
        "context.recent_chapters cannot include future chapters",
    )
    characters = normalize_snapshots(
        root.get("characters", {}), "tracking state.characters"
    )
    for name in context["active_character_names"]:
        require(
            name in characters, f"active core character {name} has no current snapshot"
        )
    foreshadow = normalize_foreshadow_state(root.get("foreshadow", {}), last_chapter)
    timeline = normalize_timeline_state(root.get("timeline", {}), last_chapter)
    items = normalize_ledger_state(
        root.get("items", {}), "tracking state.items", ITEM_FIELDS, last_chapter
    )
    secrets = normalize_ledger_state(
        root.get("secrets", {}), "tracking state.secrets", SECRET_FIELDS, last_chapter
    )
    pledges = normalize_ledger_state(
        root.get("pledges", {}), "tracking state.pledges", PLEDGE_FIELDS, last_chapter
    )
    overrides = normalize_overrides_state(root.get("overrides", []), last_chapter)
    if last_chapter == 0:
        require(
            not foreshadow, "a chapter-0 project cannot have planted foreshadow facts"
        )
        require(
            not timeline, "a chapter-0 project cannot have established timeline facts"
        )
        require(
            not overrides, "a chapter-0 project cannot have rule overrides"
        )
    return {
        "schema_version": TRACKING_SCHEMA_VERSION,
        "book_title": clean_text(
            root.get("book_title"), "tracking state.book_title", max_bytes=240
        ),
        "last_committed_chapter": last_chapter,
        "imported_through_chapter": imported_through,
        "state_revision": as_int(
            root.get("state_revision"), "tracking state.state_revision"
        ),
        "context": context,
        "characters": characters,
        "foreshadow": foreshadow,
        "timeline": timeline,
        "items": items,
        "secrets": secrets,
        "pledges": pledges,
        "overrides": overrides,
        "threads": validate_threads(root.get("threads", {})),
        "inventions": normalize_inventions_state(
            root.get("inventions", []), last_chapter
        ),
    }

def normalize_initial_document(document: object) -> dict[str, Any]:
    root = as_mapping(document, "init input")
    require_known_keys(
        root,
        {
            "schema_version",
            "book_title",
            "last_chapter",
            "context",
            "character_snapshots",
            "foreshadow",
            "timeline_events",
            "threads",
        },
        "init input",
    )
    require(
        isinstance(root.get("schema_version"), int)
        and root.get("schema_version") in (1, INPUT_SCHEMA_VERSION),
        "init input schema_version is unsupported (accept 1 or 2)",
    )
    last_chapter = as_int(root.get("last_chapter"), "last_chapter")
    context = validate_context_input(root.get("context"), include_initial_fields=True)
    snapshots = normalize_snapshots(root.get("character_snapshots", {}))
    foreshadow: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(as_list(root.get("foreshadow", []), "foreshadow")):
        row = normalize_foreshadow_change(
            raw_row,
            f"foreshadow[{index}]",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        require(row["id"] not in foreshadow, f"duplicate foreshadow ID {row['id']}")
        row.pop("action")
        row["updated_chapter"] = max(1, last_chapter)
        foreshadow[row["id"]] = row
    timeline: dict[str, dict[str, Any]] = {}
    for index, raw_event in enumerate(
        as_list(root.get("timeline_events", []), "timeline_events")
    ):
        event = normalize_timeline_change(
            raw_event,
            f"timeline_events[{index}]",
            allow_delete=False,
            through_chapter=last_chapter,
        )
        require(
            event["id"] not in timeline, f"duplicate timeline event ID {event['id']}"
        )
        event.pop("action")
        event["first_recorded_chapter"] = max(1, last_chapter)
        event["updated_chapter"] = max(1, last_chapter)
        timeline[event["id"]] = event
    return normalize_state(
        {
            "schema_version": TRACKING_SCHEMA_VERSION,
            "book_title": clean_text(
                root.get("book_title"), "book_title", max_bytes=240
            ),
            "last_committed_chapter": last_chapter,
            "imported_through_chapter": last_chapter,
            "state_revision": 0,
            "context": context,
            "characters": snapshots,
            "foreshadow": foreshadow,
            "timeline": timeline,
            "overrides": [],
            "threads": root.get("threads", {}),
        }
    )

def normalize_transaction(state: dict[str, Any], document: object) -> dict[str, Any]:
    root = as_mapping(document, "transaction")
    require_known_keys(
        root,
        {
            "schema_version",
            "mode",
            "chapter",
            "chapter_title",
            "expected_state_revision",
            "delta",
            "context",
            "character_snapshots",
        },
        "transaction",
    )
    require(
        isinstance(root.get("schema_version"), int)
        and root.get("schema_version") in (1, INPUT_SCHEMA_VERSION),
        "transaction schema_version is unsupported (accept 1 or 2)",
    )
    mode = clean_text(root.get("mode"), "mode", max_bytes=24)
    require(mode in {"append", "revision"}, "mode must be append or revision")
    chapter = as_int(root.get("chapter"), "chapter", minimum=1)
    expected_revision = as_int(
        root.get("expected_state_revision"), "expected_state_revision"
    )
    require(
        expected_revision == state["state_revision"],
        "tracking state changed since this transaction was prepared",
    )
    last = state["last_committed_chapter"]
    if mode == "append":
        require(
            chapter == last + 1, f"append chapter must be {last + 1}, got {chapter}"
        )
    else:
        require(
            chapter <= last,
            f"cannot revise unwritten chapter {chapter}; last committed chapter is {last}",
        )
    context = validate_context_input(root.get("context"), include_initial_fields=False)
    snapshots = normalize_snapshots(root.get("character_snapshots", {}))
    existing_names = {portable_name_key(name): name for name in state["characters"]}
    for name in snapshots:
        existing = existing_names.get(portable_name_key(name))
        require(
            existing is None or existing == name,
            f"character {name} conflicts with existing character {existing}",
        )
    through_chapter = chapter if mode == "append" else last
    delta = normalize_delta(
        root.get("delta"),
        through_chapter=through_chapter,
        snapshots=snapshots,
        existing_core_names=existing_names,
    )
    return {
        "mode": mode,
        "chapter": chapter,
        "title": clean_text(root.get("chapter_title"), "chapter_title", max_bytes=240),
        "delta": delta,
        "context": context,
        "snapshots": snapshots,
    }

