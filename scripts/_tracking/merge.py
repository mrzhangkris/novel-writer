"""novel-writer 状态账本·合并层：事务合并进权威状态。"""

from __future__ import annotations

import copy
from pathlib import Path
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

def _require_alive_discipline(
    state: dict[str, Any], transaction: dict[str, Any]
) -> None:
    """死亡铁律（G3）：已死者不得移动、不得再更新快照；置 false 须有本人死亡宣告；复活须登记。

    - 本章新死亡（old_alive=true → false）：change 须含「{name}」与死亡词的邻近共现；
      自由文本含糊描述（昏倒/假死）不翻转存活——宁缺毋滥不猜死活。
    - 已死者 location 变化 → 拒收。
    - 复活（old_alive=false → true）→ 必须同章 rule_overrides 登记，否则拒收。
    """
    changes = {
        item["name"]: item["change"]
        for item in transaction["delta"]["character_changes"]
    }
    overrides = transaction["delta"].get("rule_overrides") or []
    for name, new_snapshot in transaction["snapshots"].items():
        change_text = changes.get(name, "")
        old_snapshot = state["characters"].get(name)
        old_alive = old_snapshot.get("alive", True) if old_snapshot else True
        declared_death = _declares_death(name, change_text)
        now_alive = new_snapshot.get("alive", True)
        if old_alive and not now_alive and not declared_death:
            raise TrackingError(
                f"角色「{name}」alive 置为 false，但 change 缺少针对「{name}」本人的明确死亡宣告"
                f"（需写明「{name}」死亡的因果），拒绝提交——防止误标死亡"
            )
        if not old_alive and now_alive:
            require(
                overrides,
                f"角色「{name}」从死亡状态复活：复活属于打破「死者不可复生」硬规则的剧情事件，"
                "必须在本章事务 delta.rule_overrides 登记（rule/reason/effective_chapter/payback）",
            )
        if not old_alive and not now_alive:
            old_location = old_snapshot.get("location", "").strip()
            new_location = new_snapshot.get("location", "").strip()
            require(
                not new_location
                or not old_location
                or new_location == old_location,
                f"已死亡角色「{name}」不得移动（location '{old_location}' → '{new_location}'）——"
                "死亡铁律：死者 location 冻结在死亡地点；复活须走 rule_overrides 登记",
            )


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

DEATH_WORDS = ("死亡", "身亡", "死了", "死去", "毙命", "陨落", "丧命", "当场死亡", "dead")


_DEATH_LEXICON_PATH = Path(__file__).resolve().parent.parent.parent / "references" / "death-lexicon.json"


def _load_death_lexicon() -> dict[str, tuple[str, ...]]:
    """死亡词表三闸：硬词=明确宣告；软词（假死/昏迷类）不算宣告；推测词与硬词共现=推测语境。

    词表缺失/损坏时降级为内置最小集，不阻塞账本合并。"""
    default = {
        "hard": DEATH_WORDS,
        "soft": (),
        "speculative": ("差点", "以为", "似乎", "仿佛", "好像", "疑似", "传闻", "据说"),
    }
    try:
        import json as _json
        data = _json.loads(_DEATH_LEXICON_PATH.read_text(encoding="utf-8"))
        return {
            "hard": tuple(data.get("hard") or DEATH_WORDS),
            "soft": tuple(data.get("soft") or ()),
            "speculative": tuple(data.get("speculative") or ()),
        }
    except (OSError, ValueError):
        return default


LEXICON = _load_death_lexicon()


def _declares_death(name: str, change_text: str) -> bool:
    """change 文本是否包含针对「name」本人的明确死亡宣告（三闸判定）。

    ①硬词命中且窗口内有角色名；②窗口内命中软词（假死/昏迷类）→ 不算宣告；
    ③硬词窗口内同现推测词（差点/传闻类）→ 推测语境不算。口径从严：
    解析不了就跳过不猜。"""
    for word in LEXICON["hard"]:
        start = 0
        while True:
            idx = change_text.find(word, start)
            if idx < 0:
                break
            window = change_text[max(0, idx - 20) : idx + len(word) + 20]
            if name not in window:
                start = idx + len(word)
                continue
            if any(sw in window for sw in LEXICON["soft"]):
                return False  # 软词闸：假死/昏迷类不构成死亡宣告
            if any(sw in window for sw in LEXICON["speculative"]):
                start = idx + len(word)
                continue  # 推测语境：不算宣告
            return True
    return False


def merge_transaction(
    state: dict[str, Any], transaction: dict[str, Any]
) -> dict[str, Any]:
    next_state = copy.deepcopy(state)
    chapter = transaction["chapter"]
    is_revision = transaction["mode"] == "revision"
    current_last = state["last_committed_chapter"]
    if transaction["mode"] == "append":
        next_state["last_committed_chapter"] = chapter
    next_state["state_revision"] += 1
    # 修订非末章（回头改旧稿）不代表「当前写作位置」回到旧章：
    # 快照与 context 是「此刻」状态，只有 append 或修订恰为末章时才允许推进/覆盖。
    touches_present = (not is_revision) or chapter == current_last
    if touches_present:
        next_state["characters"].update(transaction["snapshots"])
    _require_alive_discipline(state, transaction)
    _require_transition_events(state, transaction)

    next_context = transaction["context"]
    # 退役说的是「从此刻起离开当前状态」，只有 append 的逐章记录代表此刻；
    # 修订记录属于被改写的旧章，落在那里会谎报退役发生的章节。
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

    # 道具/秘密/誓约台账（by-name upsert/delete）：长篇吃书高发区的结构化对账底账。
    # 增量 upsert：漏写的字段继承旧值——否则 bool/int 缺省值（revealed=false、
    # due_chapter=None）会把历史状态静默回退（如已设限期的誓约漏写 due_chapter）。
    for key in ("items", "secrets", "pledges"):
        for change in transaction["delta"][key]:
            bucket = next_state[key]
            if change["action"] == "delete":
                bucket.pop(change["name"], None)
                continue
            existing = bucket.get(change["name"])
            if existing is not None:
                for field, value in existing.items():
                    # None = 未提供（int 缺省），继承旧值防历史状态静默回退
                    if field == "updated_chapter":
                        continue
                    if field not in change or change[field] is None:
                        change[field] = value
            bucket[change["name"]] = checkpoint_record(
                change, chapter, existing
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

    # 写手发明申报：正文确立的计划外设定按章记账；修订该章时整章替换（防改稿后发明悬空）。
    # 章级事实不随 touches_present 回退——改旧稿不改变「那章发明过什么」。
    if transaction["delta"].get("inventions"):
        prior = [
            item
            for item in next_state.get("inventions", [])
            if item["chapter"] != chapter
        ]
        prior.extend(
            {"chapter": chapter, "text": text}
            for text in transaction["delta"]["inventions"]
        )
        next_state["inventions"] = sorted(
            prior, key=lambda item: (item["chapter"], item["text"])
        )

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

    if not touches_present:
        # 修订非末章：账本仍是「此刻」的事实源，context/threads 保持现状，
        # 只落章级 delta 存档（该章改了什么看 chapter-deltas/）。
        return normalize_state(next_state)

    next_state["context"] = {
        **next_context,
        "recent_chapters": recent,
        "next_chapter_commitments": next_commitments,
    }
    return normalize_state(next_state)

