#!/usr/bin/env python3
"""gen_transaction.py — 追踪事务生成器（初稿，agent 修改后提交）

把「手写事务 JSON」变成「生成 → 改 → 提交」：
  1. 读状态机（pipeline.json）与状态账本（_tracking-state.json）
  2. 按 references/architecture.md 的 CHANGES 协议生成结构完整的事务初稿：
     - expected_state_revision 自动填当前修订号
     - context 的 long_term_constraints / continuity_risks / position / active_character_names 原样带回
     - 每个活跃角色生成 character_changes 占位 + 快照预填当前值
     - 新增伏笔/时间线/退役字段留空（提示打到 stdout）
  3. 写入 {项目}/.story/tx-chapter-NNN.json，打印下一步命令

用法：
  gen_transaction.py init    --project <书目录>      生成第 0 章初始化事务
  gen_transaction.py commit  --project <书目录>      生成下一章 append 事务
  gen_transaction.py commit  --project <书目录> --revision  生成当前章 revision 事务

注意：生成的是初稿。占位「（待填…）」必须替换；事务提交前请按
references/architecture.md 校验语义（退役声明、快照⊆changes 等已由
本脚本保证结构正确，语义正确性由 agent 填写时负责）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import PIPELINE_FILE, STORY_DIR, read_json
from assemble_spec import (
    chapter_in,
    pad_fid,
    parse_foreshadow_table,
    parse_outline_chapter,
    parse_outline_foreshadows,
)

STATE_FILE = "tracking/_tracking-state.json"
PLACEHOLDER = "（待填）"




def book_title(root: Path) -> str:
    concept = root / "concept.md"
    if concept.exists():
        text = concept.read_text(encoding="utf-8")
        m = re.search(r"^- 书名：(.+)$", text, flags=re.MULTILINE)
        if m:
            return m.group(1).strip()
    return "（待填：书名）"


def chapter_title_from_outline(root: Path, chapter: int) -> str:
    outline = root / "outline.md"
    if not outline.exists():
        return PLACEHOLDER
    text = outline.read_text(encoding="utf-8")
    # 「### 第N章：标题」或「### 尾声：标题」
    for m in re.finditer(r"^###\s*(第\s*(\d+)\s*章|尾声)\s*[：:·]\s*(.+)$", text, flags=re.MULTILINE):
        if m.group(1).startswith("尾声"):
            num = None
        else:
            num = int(re.sub(r"\s", "", m.group(2)))
        if (num is None and chapter == 0) or num == chapter:
            return m.group(3).strip()
    return PLACEHOLDER


def gen_init(root: Path, pipe: dict) -> dict:
    return {
        "schema_version": 2,
        "book_title": book_title(root),
        "last_chapter": 0,
        "context": {
            "position": {
                "volume": "（待填：卷名）",
                "volume_start_chapter": 1,
                "story_time": "（待填：开篇故事时间）",
                "scene": "（待填：开篇场景）",
            },
            "long_term_constraints": [],
            "active_character_names": [],
            "continuity_risks": [],
            "recent_chapters": [],
            "next_chapter_commitments": ["（待填：第一章承诺）"],
        },
        "character_snapshots": {},
        "foreshadow": [],
        "timeline_events": [],
    }


def _read_spec(root: Path, chapter: int) -> str:
    p = root / f"chapters/chapter-{chapter:03d}/spec.md"
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return ""


def _spec_checklist(spec: str) -> dict[str, str]:
    """解析 spec 履约清单的 [x]/[ ] 行，返回 {标签: 内容}。"""
    out = {}
    for line in spec.splitlines():
        m = re.match(r"^- \[[ xX]\] (本章目标|场景安排|关键事件|章末钩子)[：:]\s*(.*)", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _spec_result(checklist: dict[str, str]) -> str:
    """从履约清单预填 result（≤100 字，满足近三章速记 360 字节上限）。"""
    parts = []
    if checklist.get("关键事件"):
        parts.append(checklist["关键事件"])
    if checklist.get("章末钩子"):
        parts.append("章末钩子：" + checklist["章末钩子"])
    text = "。".join(p for p in parts if p)
    if not text:
        return PLACEHOLDER
    return text[:100]


def _spec_position(spec: str, checklist: dict[str, str]) -> tuple[str, str]:
    story_time, scene = PLACEHOLDER, PLACEHOLDER
    if checklist.get("场景安排"):
        scene = checklist["场景安排"][:40]
    for line in spec.splitlines():
        m = re.match(r"-\s*故事时间[：:]\s*(.*)", line)
        if m:
            val = m.group(1).strip()
            if val and "待定" not in val:
                story_time = val[:40]
    return story_time, scene


def _spec_new_abilities(spec: str) -> list[str]:
    """概念要点中标注「引入」的条目 → new_abilities 候选。"""
    out = []
    for line in spec.splitlines():
        m = re.match(r"-\s*(.+?)[（(]引入[)）]", line)
        if m:
            out.append(m.group(1).strip()[:60])
    return out[:12]


def _foreshadow_candidates(root: Path, chapter: int, state: dict) -> list[dict]:
    """伏笔变更候选：本章应收的（账本）+ 本章应埋的（大纲），AI 只删不改。"""
    out = []
    rows = parse_foreshadow_table(
        (root / "tracking/foreshadows.md").read_text(encoding="utf-8")
        if (root / "tracking/foreshadows.md").exists()
        else ""
    )
    for row in rows:
        if row["status"] == "已埋" and chapter_in(row["planned"], chapter):
            out.append(
                {
                    "action": "upsert",
                    "id": row["id"],
                    "summary": row["summary"][:60],
                    "planted_chapter": int(re.search(r"\d+", row["planted"]).group())
                    if re.search(r"\d+", row["planted"])
                    else chapter,
                    "planned_resolution_chapter": int(re.search(r"\d+", row["planned"]).group())
                    if re.search(r"\d+", row["planned"])
                    else None,
                    "status": "已回收",
                    "importance": row["importance"] if row["importance"] in ("高", "中", "低") else "中",
                }
            )
    outline = (root / "outline.md").read_text(encoding="utf-8") if (root / "outline.md").exists() else ""
    for line in outline.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"F\d+", cells[0]):
            continue
        if not chapter_in(cells[2], chapter):
            continue
        planned = re.search(r"\d+", cells[3]) if len(cells) > 3 else None
        out.append(
            {
                "action": "upsert",
                "id": pad_fid(cells[0]),
                "summary": (cells[1] if len(cells) > 1 else "（见大纲）")[:60],
                "planted_chapter": chapter,
                "planned_resolution_chapter": int(planned.group()) if planned else None,
                "status": "已埋",
                "importance": "中",  # outline 伏笔表第 5 列是「类型」非「重要度」，统一默认中
            }
        )
    return out


def gen_commit(root: Path, pipe: dict, revision: bool, chapter_override: int | None = None) -> dict:
    state_path = root / STATE_FILE
    if not state_path.exists():
        print("❌ 状态账本未初始化（tracking/_tracking-state.json 不存在）")
        print("   先跑 gen_transaction.py init 生成初始化事务并提交 tracking_commit.py init")
        raise SystemExit(2)
    state = read_json(state_path)
    if state is None or not isinstance(state, dict):
        print(f"❌ 状态账本损坏或不可读：{root / 'tracking/_tracking-state.json'}——先修账本再生成事务")
        raise SystemExit(2)

    last = state["last_committed_chapter"]
    revision_no = state["state_revision"]
    chapter = int(pipe.get("chapter", 1))

    if revision and chapter_override is not None:
        # 历史章修订：显式指定已写章号（如「前 10 章设定改了，重写第 3 章」）。
        # 协议层允许 revision chapter <= last（schema 校验），工具层此前只为当前章生成。
        if not (1 <= chapter_override <= last):
            print(f"❌ --chapter {chapter_override} 超出可修订范围（1-{last}）")
            raise SystemExit(2)
        chapter = chapter_override

    if revision:
        if chapter > last:
            print(f"❌ revision 模式要求修订已写章节：当前章 {chapter} > 最后提交章 {last}")
            raise SystemExit(2)
    else:
        if chapter != last + 1:
            print(
                f"❌ 章号不匹配：pipeline 当前第 {chapter} 章，append 应提交第 {last + 1} 章"
            )
            print("   先 pipeline.py next-chapter 或检查章节号")
            raise SystemExit(2)

    active_names = state["context"]["active_character_names"]
    snapshots = {name: state["characters"][name] for name in active_names}

    # ── 从 spec 与账本自动预填（AI 只改变化部分）────────────────────────
    spec = _read_spec(root, chapter)
    spec_fields = parse_outline_chapter(spec, 0)  # 占位：spec 无「### 第N章」头，走专用解析
    spec_checklist = _spec_checklist(spec)
    result = _spec_result(spec_checklist)
    story_time, scene = _spec_position(spec, spec_checklist)
    new_abilities = _spec_new_abilities(spec)
    foreshadow_candidates = _foreshadow_candidates(root, chapter, state)

    tx = {
        "schema_version": 2,
        "mode": "revision" if revision else "append",
        "chapter": chapter,
        "chapter_title": chapter_title_from_outline(root, chapter),
        "expected_state_revision": revision_no,
        "delta": {
            "result": result,
            "character_changes": [
                {"name": name, "change": PLACEHOLDER} for name in active_names
            ],
            "foreshadow_changes": foreshadow_candidates,
            "timeline_events": [],
            "plot_points": [],
            # 道具/秘密/誓约：本章有变动才填，形状见 references/architecture.md
            # items:   {"action": "upsert", "name": "…", "holder": "现持有者", "note": "…"}
            # secrets: {"action": "upsert", "name": "…", "known_by": "知情者，顿号分隔", "revealed": false}
            # pledges: {"action": "upsert", "name": "…", "due_chapter": 15, "status": "未兑现"}
            "items": [],
            "secrets": [],
            "pledges": [],
            "constraints": [],
            "next_chapter_commitments": [],
            "retired_context_items": [],
            "retired_characters": [],
            "new_abilities": new_abilities,
            "rule_overrides": [],
            # 写手发明申报：正文确立的计划外设定/人物/事实，一句一条（≤6 条 × 360B）。
            # 不申报 = 下一章章纲/账本不知道，冲突后爆；申报后进 context.md 供下章 spec 组装。
            "inventions": [],
        },
        "context": {
            "position": {
                **dict(state["context"]["position"]),
                "story_time": story_time,
                "scene": scene,
            },
            "active_scene": state["context"].get("active_scene", ""),
            "long_term_constraints": list(
                state["context"]["long_term_constraints"]
            ),
            "active_character_names": list(active_names),
            "continuity_risks": list(state["context"]["continuity_risks"]),
        },
        "character_snapshots": snapshots,
    }
    return tx


def main() -> int:
    parser = argparse.ArgumentParser(description="生成追踪事务初稿")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("init", "commit"):
        p = sub.add_parser(cmd)
        p.add_argument("--project", type=Path, required=True, help="书项目根")
    sub.choices["commit"].add_argument(
        "--revision", action="store_true", help="生成 revision 事务（修订已写章节）"
    )
    sub.choices["commit"].add_argument(
        "--chapter", type=int, default=None,
        help="revision 时指定历史章号（默认当前章；配合 --revision 修订任意已写章，该章 spec 需存在）"
    )
    args = parser.parse_args()

    root = args.project
    if not (root / STORY_DIR).is_dir():
        print(f"❌ 不是书项目根（缺 .story/）：{root}")
        return 1
    pipe = read_json(root / PIPELINE_FILE)
    if pipe is None:
        print(f"❌ pipeline.json 损坏或不可读：{root / PIPELINE_FILE}——先修状态文件再生成事务")
        return 1

    if args.command == "init":
        tx = gen_init(root, pipe)
        out = root / STORY_DIR / "tx-init.json"
    else:
        tx = gen_commit(root, pipe, args.revision, args.chapter)
        out = root / STORY_DIR / f"tx-chapter-{tx['chapter']:03d}.json"

    payload = json.dumps(tx, ensure_ascii=False, indent=2)
    out.write_text(payload, encoding="utf-8")

    print(f"✅ 事务初稿已生成：{out}")
    if args.command == "commit":
        print(f"   模式：{tx['mode']} | 第 {tx['chapter']} 章 | expected_state_revision={tx['expected_state_revision']}")
        print(f"   已自动带入：长期约束 {len(tx['context']['long_term_constraints'])} 条、"
              f"连贯风险 {len(tx['context']['continuity_risks'])} 条、"
              f"活跃角色快照 {len(tx['character_snapshots'])} 个")
        if tx["delta"]["result"] != PLACEHOLDER:
            print("   已按 spec 预填：result、场景（scene）、新能力候选、伏笔变更候选（应收/应埋）")
        print("   待你填写：每个角色的 change、时间线事件、constraints、next_chapter_commitments；")
        print("   伏笔候选只删不改（没发生的回收删掉）；story_time 按本章更新")
        print("   注意：如需退役 continuity_risks / long_term_constraints 条目，逐条填进 retired_context_items")
        print("   新增能力/概念填入 new_abilities；剧情打破世界硬规则时必须在 rule_overrides 登记（rule/reason/effective_chapter/payback）")
        print("   填表约束：result ≤480 字节；constraints 只收字符串；character_snapshots 恰好等于 character_changes 的角色；退役条目须与账本原文逐字一致")
        print("   ── 字段速查（schema 白名单，填错拒收）──")
        print("   snapshot 字段：identity / location / goal / state / alive(布尔) / abilities_resources / relationships / knowledge / open_threads")
        print("   timeline 字段：id(E001) / story_time / objective_fact(非 fact) / reader_knowledge / characters(数组) / reveal_status / reveal_chapter(部分揭示|已揭示必填)")
        print("   foreshadow 字段：id(F001) / summary / planted_chapter / planned_resolution_chapter / status(已埋|推进|已回收|已过期|放弃) / importance；「推进」态建议填 progress_note（如「第3章主角已注意到戒指发烫，尚未知晓功能」，≤360 字节）")
        print("   items: name+holder+note ｜ secrets: name+known_by+revealed(布尔) ｜ pledges: name+due_chapter(数字)+status(未兑现|已兑现|已破誓)")
    here = Path(__file__).resolve().parent
    print(f"   提交：python3 {here / 'tracking_commit.py'} "
          f"{'init' if args.command == 'init' else 'commit'} --project {root} --input {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
