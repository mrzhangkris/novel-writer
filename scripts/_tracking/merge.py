"""novel-writer 状态账本·合并层：事务合并进权威状态。"""

from __future__ import annotations

import copy
from typing import Any

from _tracking.schema import (
    CAUSAL_WORDS,
    FRIENDLY_WORDS,
    HOSTILE_WORDS,
    TrackingError,
    normalize_state,
    portable_name_key,
    require,
)

def checkpoint_record(
    change: dict[str, Any],
    chapter: int,
    previous: dict[str, Any] | None,
    *,
    keep_first_chapter: bool = False,
) -> dict[str, Any]:
    current = {key: value for key, value in change.items() if key != "action"}
    current["updated_chapter"] = max(
        previous["updated_chapter"] if previous else chapter, chapter
    )
    if keep_first_chapter:
        current["first_recorded_chapter"] = (
            previous["first_recorded_chapter"] if previous else chapter
        )
    return current

def _relationship_polarity(relationships: list[str]) -> str | None:
    text = "".join(relationships)
    hostile = any(word in text for word in HOSTILE_WORDS)
    friendly = any(word in text for word in FRIENDLY_WORDS)
    if hostile and not friendly:
        return "hostile"
    if friendly and not hostile:
        return "friendly"
    return None

def _require_transition_events(
    state: dict[str, Any], transaction: dict[str, Any]
) -> None:
    changes = {
        item["name"]: item["change"]
        for item in transaction["delta"]["character_changes"]
    }
    for name, new_snapshot in transaction["snapshots"].items():
        old_snapshot = state["characters"].get(name)
        if old_snapshot is None:
            continue
        old_polarity = _relationship_polarity(old_snapshot["relationships"])
        new_polarity = _relationship_polarity(new_snapshot["relationships"])
        if old_polarity is None or new_polarity is None or old_polarity == new_polarity:
            continue
        change_text = changes.get(name, "")
        if not any(word in change_text for word in CAUSAL_WORDS):
            raise TrackingError(
                f"角色「{name}」关系极性翻转（{old_polarity}→{new_polarity}），"
                "change 缺少转变事件的因果说明，拒绝提交"
            )

def merge_transaction(
    state: dict[str, Any], transaction: dict[str, Any]
) -> dict[str, Any]:
    next_state = copy.deepcopy(state)
    chapter = transaction["chapter"]
    if transaction["mode"] == "append":
        next_state["last_committed_chapter"] = chapter
    next_state["state_revision"] += 1
    next_state["characters"].update(transaction["snapshots"])
    _require_transition_events(state, transaction)

    next_context = transaction["context"]
    # 退役说的是「从此刻起离开当前状态」，只有 append 的逐章记录代表此刻；
    # 修订记录属于被改写的旧章，落在那里会谎报退役发生的章节。
    is_revision = transaction["mode"] == "revision"
    require(
        not (is_revision and transaction["delta"]["retired_characters"]),
        "retired_characters must be committed in an append transaction, not a revision",
    )
    for name in transaction["delta"]["retired_characters"]:
        require(
            name in next_state["characters"],
            f"retired character {name} has no current snapshot",
        )
        require(
            name not in transaction["snapshots"],
            f"character {name} cannot be retired and updated in the same transaction",
        )
        require(
            name not in next_context["active_character_names"],
            f"retired character {name} is still listed in context.active_character_names",
        )
        next_state["characters"].pop(name)

    # 上下文条目是整份提交的；漏写会静默丢历史裁定，因此掉落必须显式声明。
    previous_items = set(state["context"]["long_term_constraints"]) | set(
        state["context"]["continuity_risks"]
    )
    dropped = previous_items - (
        set(next_context["long_term_constraints"])
        | set(next_context["continuity_risks"])
    )
    require(
        not (is_revision and dropped),
        "a revision must resubmit every current context item; retire them in an append transaction instead: "
        + "；".join(sorted(dropped)),
    )
    undeclared = sorted(dropped - set(transaction["delta"]["retired_context_items"]))
    require(
        not undeclared,
        "context items were dropped without being declared in delta.retired_context_items: "
        + "；".join(undeclared),
    )
    transaction["delta"]["retired_context_items"] = sorted(dropped)

    for change in transaction["delta"]["foreshadow_changes"]:
        if change["action"] == "delete":
            next_state["foreshadow"].pop(change["id"], None)
        else:
            existing = next_state["foreshadow"].get(change["id"])
            # 决策 2（伏笔白名单 + 强制回收计划）：新增伏笔（此前未登记）必须填计划回收章，
            # 否则拒绝提交——「能解释」从软约束升级为硬拦截。
            if existing is None and change["planned_resolution_chapter"] is None:
                raise TrackingError(
                    f"新增伏笔 {change['id']} 必须填写计划回收章（planned_resolution_chapter），否则拒绝提交"
                )
            next_state["foreshadow"][change["id"]] = checkpoint_record(
                change, chapter, existing
            )
    for change in transaction["delta"]["timeline_events"]:
        if change["action"] == "delete":
            next_state["timeline"].pop(change["id"], None)
        else:
            next_state["timeline"][change["id"]] = checkpoint_record(
                change,
                chapter,
                next_state["timeline"].get(change["id"]),
                keep_first_chapter=True,
            )

    # 设定演进账本：剧情合法打破世界硬规则必须显式登记（rule/reason/生效章/代价），
    # 否则同一规则被反复打破却无人知晓 = 静默漂移 = 长篇崩盘头号病因。
    existing_overrides = {
        (o["rule"], o["effective_chapter"]) for o in next_state["overrides"]
    }
    for override in transaction["delta"]["rule_overrides"]:
        key = (override["rule"], override["effective_chapter"])
        require(
            key not in existing_overrides,
            f"rule override duplicate: {override['rule']} already registered for chapter {override['effective_chapter']}",
        )
        existing_overrides.add(key)
        next_state["overrides"].append(override)

    recent_by_chapter = {
        item["chapter"]: item for item in state["context"]["recent_chapters"]
    }
    if chapter in recent_by_chapter or transaction["mode"] == "append":
        recent_by_chapter[chapter] = {
            "chapter": chapter,
            "summary": transaction["delta"]["result"],
        }
    recent = sorted(recent_by_chapter.values(), key=lambda item: item["chapter"])[-3:]
    current_last = next_state["last_committed_chapter"]
    next_commitments = (
        transaction["delta"]["next_chapter_commitments"]
        if transaction["mode"] == "append" or chapter == current_last
        else state["context"]["next_chapter_commitments"]
    )

    # 线束（threads）：按当前线程记录「本线停点」——多线叙事切线的连续性靠它兜底。
    # append 事务才更新停点（修订旧章不改变"线停在哪"）；线程缺省「主线」。
    thread_name = next_context.get("thread", "主线")
    if transaction["mode"] == "append":
        threads = dict(next_state.get("threads", {}))
        threads[thread_name] = {
            "last_stop_chapter": chapter,
            "position": next_context["position"],
            "active_character_names": list(next_context["active_character_names"]),
            "open_questions": list(transaction["delta"]["next_chapter_commitments"]),
        }
        next_state["threads"] = threads

    next_state["context"] = {
        **next_context,
        "recent_chapters": recent,
        "next_chapter_commitments": next_commitments,
    }
    return normalize_state(next_state)

