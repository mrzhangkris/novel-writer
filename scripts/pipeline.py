#!/usr/bin/env python3
"""pipeline.py — 小说写作流水线 · 流程编排与门禁脚本（防跳步核心）

设计理念：脚本当导演，agent 当演员。
  agent 执行任何步骤前必须先过 gate 门禁；门禁不过 → exit 1 物理阻断。

四把锁防跳步：
  锁1 顺序锁：状态机记录每步 pending/done，前置步骤未完成 → 拒绝
  锁2 文件锁：该步所需文件不存在 → 拒绝并列出缺失清单
  锁3 检查点锁：存在 waiting 状态的检查点 → 拒绝，直到老板 clear
  锁4 校验锁：上一步产出未通过 checks.py 校验 → 拒绝（advance 时自动跑）

用法：
  pipeline.py init <项目名> [--genre 题材] [--platform 平台]
                      初始化新项目（CP1 选题确认置为 waiting）
  pipeline.py status  查看当前进度与卡点
  pipeline.py gate <step>
                      门禁检查（不过 → exit 1，打印卡点）
  pipeline.py advance <step>
                      推进步骤（跑产出校验 + 标记 done + 触发检查点）
  pipeline.py checkpoint clear <id>
                      老板确认后清除检查点
  pipeline.py next-chapter
                      本章归档完成后进入下一章（重置步骤 + 章节号 +1）

状态文件：.story/pipeline.json（脚本维护，请勿手改）
"""

from __future__ import annotations

import argparse
import re
import json
import subprocess
import sys
from datetime import datetime
import hashlib
from pathlib import Path

from _common import PIPELINE_FILE, STORY_DIR, find_project_root

# 5 步状态机（review 已拆解：脚本校验内嵌 draft advance，冷读由 AI 在 draft 后做，revise 条件触发）
STEPS = ["setup", "outline", "draft", "revise", "archive"]

# 锁1 顺序锁：每个步骤的前置步骤
PREREQUISITES: dict[str, list[str]] = {
    "setup": [],
    "outline": ["setup"],
    "draft": ["outline"],
    "revise": ["draft"],
    "archive": ["draft"],
}

# 锁2 文件锁：每个步骤执行前必须存在的文件/目录（相对项目根）
REQUIRED_FILES: dict[str, list[str]] = {
    "setup": [],
    "outline": ["concept.md"],
    "draft": ["concept.md", "outline.md"],
    "revise": ["chapters"],
    "archive": ["chapters"],
}

# 锁3 检查点：advance 某步完成后触发的检查点。
# 决策 13（质量闸门替代检查点）：CP2（大纲）/CP3（每章）已关闭，改由客观质量闸门把关；仅保留 CP1（选题）。
CHECKPOINT_AFTER: dict[str, str] = {}

# 检查点说明（给老板看的）
CHECKPOINT_NOTE: dict[str, str] = {
    "cp1": "选题确认（类型/题材/平台/核心卖点）",
}

STORY_DIR = ".story"
PIPELINE_FILE = ".story/pipeline.json"




def load_state(root: Path) -> dict:
    """读取流程状态。"""
    p = root / PIPELINE_FILE
    if not p.exists():
        return _default_state()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"⚠️  状态文件损坏：{p}")
        sys.exit(1)


def _default_state() -> dict:
    return {
        "project": None,
        "genre": None,
        "platform": None,
        "type": "长篇小说",
        "chapter": 0,
        "steps": {s: "pending" for s in STEPS},
        "checkpoints": {k: "none" for k in CHECKPOINT_NOTE},
        "repair_attempts": 0,
        "rewrite_rounds": 0,
        "failed_chapters": [],
        "soft_short_streak": 0,
        "soft_long_streak": 0,
        "last_update": None,
    }


def save_state(root: Path, state: dict) -> None:
    state["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    story = root / STORY_DIR
    story.mkdir(parents=True, exist_ok=True)
    (root / PIPELINE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _waiting_checkpoints(state: dict) -> list[str]:
    """返回所有 waiting 状态的检查点 id。"""
    return [k for k, v in state["checkpoints"].items() if v == "waiting"]


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    if find_project_root(root) is not None:
        if getattr(args, "force_rebuild", False):
            # 状态文件损坏时的官方恢复路径：旧 .story/ 整体备份改名（不删除任何数据），
            # 再重建全新状态机。账本 tracking/ 不动——账本数据通常完好，重建的只是 pipeline.json。
            import time as _time
            story = root / ".story"
            backup = root / f".story.bak-{_time.strftime('%Y%m%d-%H%M%S')}"
            story.rename(backup)
            print(f"   ♻️ 旧 .story/ 已备份为 {backup.name}（含损坏的 pipeline.json）")
        else:
            print(f"❌ 当前目录已在项目中（{find_project_root(root)}）")
            print("   不能嵌套初始化。请换一个目录，用 pipeline.py status 查看现状；")
            print("   若状态文件损坏无法读取，用 pipeline.py init --force-rebuild <项目名> 重建（旧 .story/ 会备份）")
            return 1

    state = _default_state()
    state["project"] = args.project
    state["genre"] = args.genre
    state["platform"] = args.platform
    state["type"] = args.type
    state["chapter"] = 1
    state["checkpoints"]["cp1"] = "waiting"  # 选题确认
    save_state(root, state)

    print(f"✅ 项目已初始化：{args.project}")
    if args.genre:
        print(f"   题材：{args.genre}")
    if args.platform:
        print(f"   平台：{args.platform}")
    if args.type:
        print(f"   类型：{args.type}")
    print(f"\n🔒 检查点 CP1 已锁定：{CHECKPOINT_NOTE['cp1']}")
    print("   老板确认后执行：pipeline.py checkpoint clear cp1")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 当前不在任何项目中（找不到 .story/pipeline.json）")
        print(
            "   开新书：pipeline.py init <项目名> [--genre 题材] [--platform 平台] [--type 类型]"
        )
        return 1

    state = load_state(root)
    print(f"📖 项目：{state['project']}（第 {state['chapter']} 章）")
    # 章号对账警告：pipeline.chapter 与账本 last_committed_chapter 错位时提示
    #（防「pipeline 显示第 5 章可写、账本停在第 2 章」的静默窗口——提交时才会 fail-closed）
    ledger_path = root / "tracking" / "_tracking-state.json"
    if ledger_path.exists():
        try:
            import json as _json
            last_committed = int(
                _json.loads(ledger_path.read_text(encoding="utf-8")).get(
                    "last_committed_chapter"
                )
                or 0
            )
            if last_committed + 1 < int(state["chapter"]):
                print(
                    f"   ⚠️ 章号错位：pipeline 在第 {state['chapter']} 章，"
                    f"但账本只提交到第 {last_committed} 章——"
                    f"第 {last_committed + 1} 章-{int(state['chapter']) - 1} 章的事务未提交，先补交再写作"
                )
        except (OSError, ValueError):
            pass
    print(
        f"   题材：{state['genre'] or '未定'} | "
        f"类型：{state.get('type') or '长篇小说'} | "
        f"平台：{state['platform'] or '未定'}"
    )
    print("\n流程步骤：")
    for i, s in enumerate(STEPS, 1):
        mark = "✅" if state["steps"][s] == "done" else "⬜"
        print(f"   {mark} {i}. {s}  [{state['steps'][s]}]")

    waiting = _waiting_checkpoints(state)
    if waiting:
        print("\n🔒 待确认检查点：")
        for k in waiting:
            print(f"   - {k}: {CHECKPOINT_NOTE[k]}")
        print("   老板确认：pipeline.py checkpoint clear <id>")
    else:
        print("\n✅ 无待确认检查点")

    # 冷读质量趋势（quality_trend.py 记录；这里只读展示）
    trend_file = root / ".story" / "quality-trend.json"
    if trend_file.exists():
        try:
            trend = json.loads(trend_file.read_text(encoding="utf-8"))
            chapters = trend.get("chapters", [])
            if chapters:
                recent = chapters[-5:]
                avgs = [c.get("avg", 0) for c in recent]
                overall = round(sum(avgs) / len(avgs), 2)
                flag = "🟢" if overall >= 4.0 else ("🟠" if overall >= 3.5 else "🔴")
                print(
                    f"\n📊 冷读质量趋势：近 {len(recent)} 章均分 {overall} {flag}"
                    f"（共 {len(chapters)} 章记录）"
                )
        except (json.JSONDecodeError, OSError):
            pass
    return 0


def cmd_wordcount(args: argparse.Namespace) -> int:
    """查询平台×类型的字数标准（选题确认时，类型定了自动带出字数）。"""
    wc_file = Path(__file__).resolve().parent.parent / "references" / "word-count.json"
    try:
        wc = json.loads(wc_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"⚠️  读取 word-count.json 失败：{e}")
        return 1

    plat = wc.get(args.platform)
    if not plat:
        print(f"❌ word-count.json 无平台「{args.platform}」")
        print(f"   可选平台：{', '.join(k for k in wc if not k.startswith('_'))}")
        return 1
    cfg = plat.get(args.type) or {}
    per = cfg.get("每章", [])
    total = cfg.get("总字数", [])

    print(f"📏 {args.platform} · {args.type}")
    if per:
        print(f"   每章字数：{per[0]}-{per[1]} 字")
    else:
        print("   每章字数：未配置")
    if total:
        lo, hi = total
        print(f"   总字数：{lo}-{hi} 字（约 {lo // 10000}万-{hi // 10000}万）")
    else:
        print("   总字数：未配置")
    return 0


def _extra_gate_checks(state: dict, step: str) -> list[str]:
    problems = []
    if step == "revise" and state["steps"]["revise"] == "skipped":
        problems.append("revise 已跳过（冷读通过），无需修改")
    if step == "archive" and state["steps"]["revise"] == "pending":
        problems.append("revise 未完成（冷读打回需先修改，或冷读通过后先 skip revise）")
    return problems


def cmd_gate(args: argparse.Namespace) -> int:
    step = args.step
    if step not in STEPS:
        print(f"❌ 未知步骤：{step}。可选：{', '.join(STEPS)}")
        return 1

    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中。先 pipeline.py init <项目名>")
        return 1

    state = load_state(root)
    problems: list[str] = []

    # 锁1 顺序锁
    for pre in PREREQUISITES[step]:
        if state["steps"][pre] != "done":
            problems.append(f"顺序锁：前置步骤「{pre}」未完成（{state['steps'][pre]}）")
    problems.extend(_extra_gate_checks(state, step))

    # 锁3 检查点锁
    for cid in _waiting_checkpoints(state):
        problems.append(f"检查点锁：{cid}（{CHECKPOINT_NOTE[cid]}）等待老板确认")

    # 锁2 文件锁
    for f in REQUIRED_FILES[step]:
        if not (root / f).exists():
            problems.append(f"文件锁：缺少 {f}")

    if problems:
        print(f"❌ 门禁拒绝：{step}")
        for p in problems:
            print(f"   - {p}")
        return 1

    print(f"✅ 门禁通过：{step}（可执行）")
    return 0


def cmd_advance(args: argparse.Namespace) -> int:
    step = args.step
    if step not in STEPS:
        print(f"❌ 未知步骤：{step}")
        return 1

    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中。先 pipeline.py init <项目名>")
        return 1

    state = load_state(root)

    # advance 前先跑一次 gate（复用门禁逻辑，确保不跳步）
    problems: list[str] = []
    for pre in PREREQUISITES[step]:
        if state["steps"][pre] != "done":
            problems.append(f"顺序锁：前置步骤「{pre}」未完成")
    problems.extend(_extra_gate_checks(state, step))
    for cid in _waiting_checkpoints(state):
        problems.append(f"检查点锁：{cid} 等待老板确认")
    if problems:
        print(f"❌ 无法推进 {step}：")
        for p in problems:
            print(f"   - {p}")
        return 1

    # 锁4 校验锁：advance 前跑 checks.py 做确定性校验（checks.py 未就绪时跳过）
    ok, zone = _run_checks(root, step)
    if not ok:
        print(f"❌ 校验锁：{step} 产出未通过 checks.py 校验")
        return 1

    # 软区连续计数（仅 draft 且本章首次推进时更新；重复 advance 不重复计数）
    if step == "draft" and state["steps"]["draft"] != "done" and zone:
        if zone == "soft_low":
            state["soft_short_streak"] = state.get("soft_short_streak", 0) + 1
        elif zone == "soft_high":
            state["soft_long_streak"] = state.get("soft_long_streak", 0) + 1
        else:
            state["soft_short_streak"] = 0
            state["soft_long_streak"] = 0
        print(
            f"   连续计数：短 {state.get('soft_short_streak', 0)} / 长 {state.get('soft_long_streak', 0)}"
        )

    state["steps"][step] = "done"
    print(f"✅ 完成步骤：{step}")

    # ── 正文指纹防线：防「draft 过门后偷换正文绕过质量门」──
    # draft 通过时固化指纹；revise/archive 时核对，改过稿就必须重新过 checks.py draft 全套。
    ch_dir = root / f"chapters/chapter-{state['chapter']:03d}"
    draft_file = ch_dir / "draft.md"
    def _draft_hash() -> str:
        return hashlib.sha256(
            (draft_file.read_text(encoding="utf-8") if draft_file.exists() else "").encode("utf-8")
        ).hexdigest()[:16]

    if step == "draft" and state["steps"]["draft"] == "done":
        state["draft_hash"] = _draft_hash()
    elif step in ("revise", "archive") and state.get("draft_hash"):
        if _draft_hash() != state["draft_hash"]:
            print("⚠️  draft.md 在 advance draft 之后被修改过——重跑全套内容校验（checks.py draft）")
            ok2, _ = _run_checks(root, "draft")
            if not ok2:
                print(f"❌ 校验锁：改稿后未通过 checks.py draft 复检")
                state["steps"][step] = "pending"
                save_state(root, state)
                return 1
            state["draft_hash"] = _draft_hash()
            print("   ✅ 改稿复检通过，指纹已更新")

    # 触发检查点
    cid = CHECKPOINT_AFTER.get(step)
    if cid and state["checkpoints"][cid] == "none":
        state["checkpoints"][cid] = "waiting"
        print(f"🔒 检查点 {cid} 已锁定：{CHECKPOINT_NOTE[cid]}")
        print(f"   老板确认：pipeline.py checkpoint clear {cid}")

    save_state(root, state)
    return 0


def _run_checks(root: Path, step: str) -> tuple[bool, str | None]:
    """锁4 校验锁：仅 outline/draft/archive 三步调用 checks.py。

    advance outline → checks.py outline（大纲合格）
    advance draft   → checks.py draft（字数 + 去AI味 + 跨章 + 元标注 + 软区趋势）
    advance archive → checks.py archive（一致性 verify）

    返回 (是否通过, 字数分区 zone)。zone 用于 advance 时更新软区连续计数。
    """
    if step not in ("outline", "draft", "archive"):
        return True, None
    # 归档前置断言：本章事务必须已提交进账本（漏提交会一路冻结归档，
    # 直到下一章 gen_commit 章号不匹配才暴露，届时上一章已归档无法回补）。
    if step == "archive":
        ledger_path = root / "tracking" / "_tracking-state.json"
        if ledger_path.exists():
            try:
                import json as _json
                last_committed = int(
                    _json.loads(ledger_path.read_text(encoding="utf-8")).get(
                        "last_committed_chapter"
                    )
                    or 0
                )
                if last_committed < load_state(root)["chapter"]:
                    print(
                        f"   ✗ 第 {load_state(root)['chapter']} 章事务尚未提交进账本"
                        f"（last_committed_chapter={last_committed}）——先跑 tracking_commit.py commit 再归档"
                    )
                    return False, None
            except (OSError, ValueError):
                print("   ⚠️ 账本不可读，归档一致性校验可能不完整")
    checks_script = Path(__file__).parent / "checks.py"
    if not checks_script.exists():
        print("   ✗ 错误：checks.py 不存在，校验锁无法执行——禁止放行（fail-closed）")
        return False, None
    try:
        result = subprocess.run(
            [sys.executable, str(checks_script), step],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = result.stdout or ""
        if stdout:
            print(stdout.strip())
        zone = None
        for line in stdout.splitlines():
            if line.startswith("ZONE:"):
                zone = line.split(":", 1)[1].strip() or None
        if result.returncode != 0:
            if result.stderr:
                print(result.stderr.strip())
            return False, zone
        return True, zone
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"⚠️  校验脚本执行异常：{e}")
        return False, None


def cmd_checkpoint(args: argparse.Namespace) -> int:
    if args.action != "clear":
        print("❌ checkpoint 仅支持 clear（老板确认后清除）")
        return 1

    cid = args.id
    if cid not in CHECKPOINT_NOTE:
        print(f"❌ 未知检查点：{cid}。可选：{', '.join(CHECKPOINT_NOTE)}")
        return 1

    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)
    if state["checkpoints"][cid] != "waiting":
        print(f"⚠️  检查点 {cid} 当前不在等待状态（{state['checkpoints'][cid]}）")
        return 0
    state["checkpoints"][cid] = "cleared"
    save_state(root, state)
    print(f"✅ 检查点 {cid} 已确认（{CHECKPOINT_NOTE[cid]}）")
    return 0


def cmd_next_chapter(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)

    # 本章必须全部完成
    unfinished = [s for s in STEPS if state["steps"][s] not in ("done", "skipped")]
    if unfinished:
        print(f"❌ 本章未完成，无法进入下一章。未完成步骤：{', '.join(unfinished)}")
        return 1

    state["chapter"] += 1
    # 只重置每章循环的步骤；setup/outline 是全书级步骤，保持 done 不重考
    state["steps"] = {
        s: ("done" if s in ("setup", "outline") else "pending") for s in STEPS
    }
    state["repair_attempts"] = 0
    state["rewrite_rounds"] = 0
    save_state(root, state)
    print(f"✅ 进入第 {state['chapter']} 章（draft/revise/archive 已重置，setup/outline 保持 done）")
    return 0


def _verify_review_integrity(root: Path, chapter: int) -> str | None:
    """校验 review.md 评分的完整性，返回拒绝原因或 None。

    三道防线（按序）：
    1. draft 指纹一致：review.md 必须由 coldread_material.py 对当前 draft.md 生成
       （draft-hash 匹配）——防手写评分文件、防改稿后拿旧评分过关；
    2. 材料在评分之前：指纹必须出现在「评分：」行之前——防 agent 在文件末尾
       补贴指纹伪装成脚本产物（脚本生成时指纹在文件头部）；
    3. 评分格式合法：四维 1-5（0 视为占位伪造）。
    """
    review = root / f"chapters/chapter-{chapter:03d}/review.md"
    if not review.exists():
        return "冷读未完成（review.md 不存在）：先跑 coldread_material.py + 冷读裁判"
    text = review.read_text(encoding="utf-8")
    m = re.search(r"评分：(\d),(\d),(\d),(\d)", text)
    if not m and not re.search(r"翻页欲 \d", text):
        return "冷读未完成（review.md 无四维评分）：先跑冷读裁判，不能跳过 revise"
    draft = root / f"chapters/chapter-{chapter:03d}/draft.md"
    body_hash = hashlib.sha256(
        (draft.read_text(encoding="utf-8") if draft.exists() else "").encode("utf-8")
    ).hexdigest()[:16]
    hm = re.search(r"<!-- draft-hash:([0-9a-f]{16}) -->", text)
    if hm is None:
        return "review.md 缺少脚本指纹（draft-hash）：评分不是 coldread_material.py 产物，疑为手写伪造"
    if hm.group(1) != body_hash:
        return "review.md 正文指纹与当前 draft.md 不一致：改稿后必须重跑冷读（coldread_material.py --write-review --force）"
    score_pos = m.start() if m else re.search(r"翻页欲 \d", text).start()
    if score_pos < hm.end():
        return "review.md 指纹出现在评分之后：评分段疑似手写拼接，不视为冷读产物"
    if m and any(int(x) < 1 or int(x) > 5 for x in m.groups()):
        return "冷读四维评分越界（1-5）：review.md 疑似伪造，不能跳过 revise"
    return None


def cmd_skip(args: argparse.Namespace) -> int:
    step = args.step
    if step != "revise":
        print("❌ 仅 revise 可跳过（冷读通过后跳过修改）")
        return 1

    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)
    if state["steps"]["draft"] != "done":
        print("❌ draft 未完成，不能跳过 revise")
        return 1
    # 冷读门禁：评分完整性三道防线（指纹一致 + 指纹在评分前 + 格式合法）
    reason = _verify_review_integrity(root, state.get("chapter", 0))
    if reason:
        print(f"❌ {reason}")
        return 1
    if state["steps"]["revise"] == "done":
        print("ℹ️  revise 已为 done（真修订过），保持 done 不改标 skipped")
        return 0
    state["steps"]["revise"] = "skipped"
    save_state(root, state)
    print("✅ revise 已跳过（冷读通过，直接归档）")
    return 0


def cmd_fail(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)
    state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    if state["repair_attempts"] >= 3:
        state["rewrite_rounds"] = state.get("rewrite_rounds", 0) + 1
        state["repair_attempts"] = 0
        if state["rewrite_rounds"] >= 3:
            print("🔴 本章已重写 3 轮仍失败，执行：pipeline.py skip-chapter 标记失败章")
        else:
            print(
                f"🔄 修复 3 次仍失败，舍弃本章进入第 {state['rewrite_rounds']} 轮重写"
            )
    else:
        print(f"📝 修复失败第 {state['repair_attempts']} 次（共 3 次机会）")
    save_state(root, state)
    return 0


def cmd_skip_chapter(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)
    # 熔断前置：skip-chapter 是重写 3 轮仍失败后的最后手段，不是绕过质量门的捷径。
    # 未触发熔断（rewrite_rounds < 3）时必须走 fail → 修复/重写循环。
    if state.get("rewrite_rounds", 0) < 3:
        print(
            f"❌ skip-chapter 仅在重写 3 轮仍失败后可用（当前 rewrite_rounds={state.get('rewrite_rounds', 0)}）。"
            "本章校验不过时先修内容，修不动跑 pipeline.py fail 记录失败，3 次触发重写轮。"
        )
        return 1
    chapter = state["chapter"]
    # 章号断层防护：skip 的必须是账本最后一章（chapter == last_committed_chapter + 1）。
    # 否则下一章 append 永远不满足「chapter == last+1」，账本永久卡死无法自愈。
    ledger_path = root / "tracking" / "_tracking-state.json"
    last_committed = None
    if ledger_path.exists():
        try:
            import json as _json
            ledger = _json.loads(ledger_path.read_text(encoding="utf-8"))
            last_committed = int(ledger.get("last_committed_chapter") or 0)
        except (OSError, ValueError):
            last_committed = None
    if last_committed is not None and chapter != last_committed + 1:
        print(
            f"❌ skip-chapter 拒绝：第 {chapter} 章不是账本最后一章"
            f"（账本 last_committed_chapter={last_committed}），直接跳过会让后续章 append 永久卡死。"
            "先补交缺失章的事务（tracking_commit.py commit）再 skip"
        )
        return 1
    failed = state.get("failed_chapters", [])
    failed.append(chapter)
    state["failed_chapters"] = failed
    state["chapter"] += 1
    state["steps"] = {
        s: ("done" if s in ("setup", "outline") else "pending") for s in STEPS
    }
    state["repair_attempts"] = 0
    state["rewrite_rounds"] = 0
    save_state(root, state)
    print(
        f"⏭️  第 {chapter} 章标记为失败章，进入第 {state['chapter']} 章（书尾用 pipeline.py failed 汇总）"
    )
    return 0


def cmd_failed(args: argparse.Namespace) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1

    state = load_state(root)
    failed = state.get("failed_chapters", [])
    if not failed:
        print("✅ 无失败章")
    else:
        print(f"🔴 失败章清单（共 {len(failed)} 章，需人工补写）：")
        for ch in failed:
            print(f"   - 第 {ch} 章")
    return 0


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="小说写作流水线 · 流程编排门禁脚本")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="初始化新项目")
    p_init.add_argument("project", help="项目名")
    p_init.add_argument("--genre", help="题材（如 都市/玄幻/甜宠）")
    p_init.add_argument("--platform", help="平台（如 番茄/起点/知乎）")
    p_init.add_argument("--force-rebuild", action="store_true",
                        help="状态文件损坏时：备份旧 .story/ 并重建（账本 tracking/ 不动）")
    p_init.add_argument("--type", help="类型（长篇小说/短故事）", default="长篇小说")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="查看进度")
    p_status.set_defaults(func=cmd_status)

    p_wc = sub.add_parser("wordcount", help="查询平台×类型的字数标准")
    p_wc.add_argument(
        "--platform", required=True, help="平台（番茄/起点/知乎/七猫/晋江）"
    )
    p_wc.add_argument("--type", required=True, help="类型（长篇小说/短故事）")
    p_wc.set_defaults(func=cmd_wordcount)

    p_gate = sub.add_parser("gate", help="门禁检查")
    p_gate.add_argument("step", choices=STEPS, help="步骤名")
    p_gate.set_defaults(func=cmd_gate)

    p_adv = sub.add_parser("advance", help="推进步骤")
    p_adv.add_argument("step", choices=STEPS, help="步骤名")
    p_adv.set_defaults(func=cmd_advance)

    p_cp = sub.add_parser("checkpoint", help="检查点操作")
    p_cp.add_argument("action", choices=["clear"], help="clear=老板确认后清除")
    p_cp.add_argument("id", help="检查点 id（cp1/cp2/cp3）")
    p_cp.set_defaults(func=cmd_checkpoint)

    p_next = sub.add_parser("next-chapter", help="进入下一章")
    p_next.set_defaults(func=cmd_next_chapter)

    p_skip_revise = sub.add_parser("skip", help="跳过 revise（冷读通过后）")
    p_skip_revise.add_argument("step", choices=["revise"], help="仅 revise 可跳过")
    p_skip_revise.set_defaults(func=cmd_skip)

    p_fail = sub.add_parser(
        "fail", help="记录一次修复失败（3 次触发重写，3 轮触发失败章）"
    )
    p_fail.set_defaults(func=cmd_fail)

    p_skip = sub.add_parser("skip-chapter", help="标记当前章为失败章并跳过")
    p_skip.set_defaults(func=cmd_skip_chapter)

    p_failed = sub.add_parser("failed", help="列出失败章清单")
    p_failed.set_defaults(func=cmd_failed)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
