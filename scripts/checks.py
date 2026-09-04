#!/usr/bin/env python3
"""checks.py — 确定性校验脚本（字数 / 去AI味 / 一致性）

校验入口（pipeline 用）：
  outline     大纲合格（章节条目/伏笔/概念预算/人物卡/盘点）
  draft       门禁全组（字数/去AI味/跨章/履约/风格基线/说话人/语病/说教/规则库/选角出场/seam）
  archive     一致性 verify

独立子命令：
  wordcount   CJK 字数，对照 references/word-count.json 的平台×类型范围。
              硬线（70%/130%）拦截；软区（目标线到硬线之间）只警告放行，
              由 pipeline 记录连续计数：连续 3 章落在同一软区 → 升级硬拦截。
  deai        去 AI 味，调用 check-ai-patterns.js（oh-story 成熟检测，20+ 类 AI 模式）
  verify      一致性，调用 tracking_commit.py check
  exempt      检查豁免清单管理：exempt <type> <key> --reason "…"/exempt list，
              记入 .story/exemptions.json（{type, key, reason, date}），
              供 outline_revise 等比对类检查跳过人工确认过的假冲突

两种调用方式：
  checks.py draft                pipeline 用：校验当前章草稿（wordcount + deai + 趋势）
  checks.py archive              pipeline 用：校验一致性（verify）
  checks.py wordcount <文件> [--platform X --type Y]
  checks.py deai <文件>
  checks.py verify
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from _common import EXEMPTIONS_FILE, STORY_DIR, find_project_root
from check_engine import load_rules, run_count_rule, run_rules

SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCES_DIR = SCRIPT_DIR.parent / "references"
WORD_COUNT_FILE = REFERENCES_DIR / "word-count.json"
TRACKING_SCRIPT = SCRIPT_DIR / "tracking_commit.py"
PIPELINE_FILE = ".story/pipeline.json"

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
CROSS_CHAPTER_WINDOW = 300
CROSS_CHAPTER_MIN_MATCH = 20
META_MARKDOWN_RE = re.compile(
    r"^\s*#{1,6}\s|\*\*|^\s*\|[^\n]*\|[^\n]*$|\[[^\]]*\]\([^)]*\)",
    flags=re.MULTILINE,
)


def _find_common_substring(a: str, b: str, min_len: int) -> str | None:
    """返回 a 与 b 之间第一条连续 min_len 字相同的子串（用于报错定位），无则 None。"""
    if len(a) < min_len or len(b) < min_len:
        return None
    substrings = {a[i : i + min_len] for i in range(len(a) - min_len + 1)}
    for i in range(len(b) - min_len + 1):
        sub = b[i : i + min_len]
        if sub in substrings:
            return sub
    return None


def _has_common_substring(a: str, b: str, min_len: int) -> bool:
    return _find_common_substring(a, b, min_len) is not None




def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"⚠️  配置文件缺失：{path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        print(f"⚠️  配置文件损坏：{path}")
        return {}


def count_cjk(text: str) -> int:
    return len(CJK_RE.findall(text))


def load_pipeline(root: Path) -> dict:
    return load_json(root / PIPELINE_FILE)


def find_chapter_body(root: Path, chapter: int) -> Path | None:
    for name in (
        f"chapters/chapter-{chapter:03d}/draft.md",
        f"chapters/第{chapter}章.md",
        f"chapters/chapter-{chapter:03d}.md",
    ):
        p = root / name
        if p.exists():
            return p
    return None


def resolve_platform(root: Path | None, platform: str | None) -> str | None:
    if platform:
        return platform
    if root:
        return load_pipeline(root).get("platform")
    return None


def cmd_wordcount(path: str, platform: str | None, type_: str) -> tuple[int, str]:
    """字数校验。返回 (exit_code, zone)。

    zone: ok / soft_low / soft_high / hard_low / hard_high / none（无平台配置）
    软区（soft_*）只警告不拦截；硬区（hard_*）拦截。
    连续 3 章落在同一软区 → 由 run_step 升级为硬拦截（见 run_step draft）。
    """
    p = Path(path)
    if not p.exists():
        print(f"❌ 文件不存在：{p}")
        return 1, "none"
    # 剥离 HTML 注释后再计数：<!-- --> 是给 AI 的标注不是读者内容，不剥离则可被用来凑字数
    text = re.sub(r"<!--.*?-->", "", p.read_text(encoding="utf-8"), flags=re.DOTALL)
    n = count_cjk(text)

    root = find_project_root(Path.cwd())
    platform = resolve_platform(root, platform)
    wc = load_json(WORD_COUNT_FILE)
    plat_cfg = wc.get(platform) if platform else None
    if not plat_cfg:
        # 字数校验锁不得静默放行：配置缺失时明确告知「未校验」，让 AI 决定是否修配置
        print(f"⚠️  word-count.json 无平台「{platform}」配置——字数校验未执行（不是通过）。")
        print(f"   请检查 {WORD_COUNT_FILE} 是否损坏/缺平台；修复后重跑。当前 CJK 字数：{n}")
        return 0, "none"
    type_cfg = plat_cfg.get(type_)
    if type_cfg is None:
        valid = "、".join(k for k in plat_cfg if not k.startswith("_"))
        print(
            f"❌ {platform} 无「{type_}」类型，可选：{valid}（当前 CJK 字数 {n}，无法校验）"
        )
        return 1, "none"
    rng = type_cfg.get("每章", []) if isinstance(type_cfg, dict) else type_cfg
    if not rng:
        print(f"⚠️  {platform}·{type_} 无每章字数配置，仅统计不校验")
        print(f"   当前 CJK 字数：{n}")
        return 0, "none"

    lo, hi = rng
    hard_lo, hard_hi = int(lo * 0.7), int(hi * 1.3)
    print(f"📏 字数校验（{platform}·{type_}）：目标 {lo}-{hi}，实际 {n}")

    if n < hard_lo:
        print(f"❌ 严重不足（{n} < 硬下限 {hard_lo}），必须扩充：检查是否遗漏关键情节")
        return 1, "hard_low"
    if n < lo:
        print(
            f"⚠️ 略短（{n} < 目标下限 {lo}），放行但计入连续计数；连续 3 章将升级拦截"
        )
        return 0, "soft_low"
    if n > hard_hi:
        print(f"❌ 严重超长（{n} > 硬上限 {hard_hi}），必须分章或删非必要支线")
        return 1, "hard_high"
    if n > hi:
        print(
            f"⚠️ 略长（{n} > 目标上限 {hi}），放行但计入连续计数；连续 3 章将升级拦截"
        )
        return 0, "soft_high"
    print("✅ 字数达标（目标区间内）")
    return 0, "ok"


def _style_anchor_allows_dash(root: Path) -> bool:
    """style-anchor 已填写（非空模板）且未禁破折号/电报体 → True。

    空模板（含 ___ 占位）一律不允许（无约束状态按最严口径）。"""
    author = root
    while author != author.parent and not (author / ".novel").is_dir():
        author = author.parent
    anchor = author / ".novel" / "style-anchor.md"
    if not anchor.exists():
        return False
    try:
        text = anchor.read_text(encoding="utf-8")
    except OSError:
        return False
    if "___" in text:  # 空模板
        return False
    m = re.search(r"## 本书不用的腔调\n(.*?)(?=\n## |\Z)", text, flags=re.S)
    banned = m.group(1) if m else ""
    return not any(w in banned for w in ("破折号", "电报体", "——"))


def cmd_deai(path: str) -> int:
    p = Path(path)
    if not p.exists():
        print(f"❌ 文件不存在：{p}")
        return 1
    body = p.read_text(encoding="utf-8").split("---CHANGES---")[0]

    import tempfile

    fd, tmp = tempfile.mkstemp(suffix=".md", text=True)
    try:
        with open(fd, "w", encoding="utf-8") as f:
            f.write(body)
        node_script = (
            SCRIPT_DIR.parent
            / "skills/branch/story-deslop/scripts/check-ai-patterns.js"
        )
        result = subprocess.run(
            ["node", str(node_script), "--check", "--fail-on=blocking", tmp],
            capture_output=True,
            text=True,
        )
        output = (result.stdout or result.stderr).strip()
        if output:
            print(output)
        if result.returncode != 0:
            # 文风锚联动：style-anchor 已填写且「本书不用的腔调」未禁破折号时，
            # em-dash blocking 降为 advisory（猫腻腔等插入语风格天然多用破折号，
            # 一刀切 blocking 会对这类文风全部误伤——M3 猫腻腔重写实验实证）
            # 从 draft 路径冒泡定位项目根（独立子命令 deai 无 root 变量）
            deai_root = p.parent
            while deai_root != deai_root.parent and not (deai_root / ".story").is_dir():
                deai_root = deai_root.parent
            if _style_anchor_allows_dash(deai_root):
                lines = output.splitlines()
                dash_lines = [l for l in lines if "em-dash" in l and "blocking" in l]
                other_blocking = [l for l in lines if "blocking" in l and "em-dash" not in l]
                if dash_lines and not other_blocking:
                    for l in dash_lines:
                        print("⚠️  " + l.replace("[blocking]", "[advisory·文风豁免]"))
                    print("✅ 去 AI 味通过（em-dash 已按文风锚降为 advisory，其余无 blocking）")
                    return 0
            print("❌ 去 AI 味未通过（check-ai-patterns.js 检出 blocking 项）")
            return 1
        print("✅ 去 AI 味通过（无 blocking 项）")
        return 0
    finally:
        Path(tmp).unlink(missing_ok=True)


def cmd_cross_chapter(body: Path, prev_body: Path | None) -> int:
    if prev_body is None:
        return 0
    cur_head = body.read_text(encoding="utf-8")[:CROSS_CHAPTER_WINDOW]
    prev_tail = prev_body.read_text(encoding="utf-8")[-CROSS_CHAPTER_WINDOW:]
    dup = _find_common_substring(prev_tail, cur_head, CROSS_CHAPTER_MIN_MATCH)
    if dup:
        print(
            f"❌ 跨章衔接重复：本章开头与上一章结尾存在连续 ≥{CROSS_CHAPTER_MIN_MATCH} 字相同的句子："
            f"「{dup}」——改写本章开头（或上一章结尾），保留信息更换措辞"
        )
        return 1
    print("✅ 跨章衔接通过（无重复）")
    return 0


def cmd_seam(root: Path, chapter: int) -> int:
    """跨章拼接断裂检测（advisory）：seam 四维指纹（地点/人物/道具/时间）
    对账前后章交接窗，恒 0 不拦门禁，命中交人工终判。

    subprocess 调 check_seam.py（同 cmd_deai 调 node 脚本模式）；
    脚本只读两章窗口文本，轻量，60s timeout 兜底。
    """
    if chapter <= 1:
        return 0
    seam_script = SCRIPT_DIR / "check_seam.py"
    try:
        result = subprocess.run(
            [sys.executable, str(seam_script), "--project", str(root), "--chapter", str(chapter)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"⚠️  seam 检测未执行（{type(e).__name__}: {e}），advisory 降级不拦门禁")
        return 0
    output = (result.stdout or result.stderr).strip()
    if output:
        print(output)
    return 0


def cmd_meta_mark(body: Path) -> int:
    text = re.sub(r"<!--.*?-->", "", body.read_text(encoding="utf-8"), flags=re.DOTALL)
    if META_MARKDOWN_RE.search(text):
        print(
            "❌ 元标注违规：正文含 markdown 标记（标题/加粗/表格/链接），正文应纯文本（仅 `<!-- -->` 标注允许）"
        )
        return 1
    print("✅ 元标注通过（纯文本）")
    return 0


def cmd_outline(outline_path: Path) -> int:
    if not outline_path.exists():
        print(f"❌ 大纲文件不存在：{outline_path}")
        return 1
    text = outline_path.read_text(encoding="utf-8")
    problems = []
    if not re.search(r"第\s*[0-9一二三四五六七八九十百千]+\s*章", text):
        problems.append("缺章节条目（第N章）")
    if "伏笔" not in text and not re.search(r"F\d+", text):
        problems.append("缺伏笔规划")
    if "概念" not in text:
        problems.append("缺概念预算")

    # 人物卡校验（红线 4 崩人设 / 红线 6 工具人 的基线：没卡就没有 OOC 判据）
    chars_dir = outline_path.parent / "characters"
    cards = sorted(chars_dir.glob("*.md")) if chars_dir.exists() else []
    # 跳过 .bak 备份文件 + 非人物卡文件（T3 速查库/清单/索引等）
    NON_CARD_KEYWORDS = ["速查", "清单", "索引", "目录", "总表", "库"]
    cards = [
        c for c in cards
        if not c.name.startswith(".bak-")
        and not any(kw in c.name for kw in NON_CARD_KEYWORDS)
    ]
    valid_cards = []
    detailed_cards = []
    simple_cards = []
    card_problems = []
    for c in cards:
        t = c.read_text(encoding="utf-8")
        def filled(pat: str) -> bool:
            m = re.search(pat, t, flags=re.MULTILINE)
            if not m:
                return False
            val = m.group(1).strip()
            return bool(val) and not val.startswith("（") and not val.startswith("TODO")
        is_simple_card = "人物卡（简）" in t or "人物卡(简)" in t

        if is_simple_card:
            # 简卡必填：基本信息 + 与详卡的关系
            has_basic = "## 基本信息" in t and filled(r"-\s*姓名[:：]\s*(\S.*)")
            has_relation = re.search(r"-\s*与[\u4e00-\u9fff]+", t) is not None
            if has_basic and has_relation:
                simple_cards.append(c.name)
            else:
                card_problems.append(f"简卡 {c.name}：缺「基本信息-姓名」或「与详卡的关系」")
        else:
            # 详卡必填：长期目标 + 底线 + 个人故事四件套（字段值非空且非 TODO 占位）
            has_goal = filled(r"长期目标[:：]\s*(\S.*)")
            has_bottom = filled(r"底线[:：]\s*(\S.*)")
            # 个人故事四件套：字段名存在 + 值非空 + 值非 TODO 占位
            personal_story_fields = ["出身与来处", "关键转折", "未了的执念", "独处时的样子"]
            missing = []
            if not has_goal:
                missing.append("长期目标")
            if not has_bottom:
                missing.append("底线")
            story_missing = []
            for field in personal_story_fields:
                # 兼容模板加粗「- **出身与来处**：」与普通「- 出身与来处：」两种格式
                m = re.search(rf"{field}\*{{0,2}}[：:]\s*(.+)", t)
                if not m:
                    story_missing.append(field)
                    continue
                val = m.group(1).strip()
                if not val or val.startswith("TODO") or val == "（待填）":
                    story_missing.append(field)
            if story_missing:
                missing.append(
                    "个人故事四件套（"
                    + "、".join(story_missing)
                    + " 未填或仍为 TODO 占位）"
                )
            if missing:
                card_problems.append(f"详卡 {c.name}：缺 {', '.join(missing)}")
            else:
                valid_cards.append(c.name)
                detailed_cards.append(c.name)

    if not valid_cards:
        problems.append("人物卡缺失或核心字段未填（characters/ 下需 ≥1 张含「长期目标」+「底线」+「个人故事四件套」的详卡）")
    if card_problems:
        problems.append(f"人物卡字段缺失：{'；'.join(card_problems[:5])}{'…' if len(card_problems) > 5 else ''}")

    # 三维盘点门禁（v2 硬门禁）
    pool_path = outline_path.parent / "characters-pool.md"
    if not pool_path.exists():
        problems.append(f"人物池盘点缺失：{pool_path}（outline 第 1.5 步必须跑 `characters_pool_generator.py` + 人工盘点决策列）")
    else:
        pool_text = pool_path.read_text(encoding="utf-8")
        # 检查每个格子决策列非空（"_待盘点_" 是占位符）
        pending = len(re.findall(r"_待盘点_", pool_text))
        if pending > 0:
            problems.append(f"人物池盘点未完成：还有 {pending} 个格子未填决策（建详卡/建简卡/不建卡/合并到X）")

    if problems:
        print("❌ 大纲不合格：" + "、".join(problems))
        return 1
    if re.search(r"一句话主线：谁，想做什么", text):
        print("⚠️  建议：总纲的「一句话主线」还是占位符——填实（谁，想做什么，遇到什么阻碍，最终如何）")
    if len(valid_cards) < 2:
        print("⚠️  建议：只有 1 张人物卡，核心配角也应有卡（短篇单人物可豁免）")
    if "情绪曲线" not in text:
        print("⚠️  建议：大纲缺「情绪曲线」节（起承转合的情绪高低点），不拦截但建议补齐")
    print(f"✅ 大纲合格（章节条目 + 伏笔规划 + 概念预算 + 人物卡 {len(valid_cards)} 张）")
    return 0


def cmd_spec_fulfillment(spec_path: Path) -> int:
    """大纲履约校验：spec.md 的「履约清单」勾选率 ≥80% 才放行。

    写前计划（大纲要点 [ ] 项）与实际执行（[x] 勾选）的结构化 diff 的轻量版：
    逼 agent 在写正文前后明确「计划写什么、实际写没写」，防止漏写关键伏笔/事件
    还悄无声息地滑进下一章。无勾选行（旧版 spec）时跳过并提示，兼容存量书。
    """
    if not spec_path.exists():
        print(f"⚠️  无 spec.md（{spec_path}），跳过履约校验")
        return 0
    text = spec_path.read_text(encoding="utf-8")
    checked = len(re.findall(r"^- \[[xX]\]", text, flags=re.MULTILINE))
    unchecked = len(re.findall(r"^- \[ \]", text, flags=re.MULTILINE))
    total = checked + unchecked
    if total == 0:
        print("⚠️  履约清单：spec.md 无 [ ] 勾选行（旧版模板），跳过履约校验")
        return 0
    rate = checked / total
    print(f"📋 履约清单：{checked}/{total} 已勾选（{rate:.0%}），要求 ≥80%")
    if rate < 0.8:
        print("❌ 履约不足：大纲要点勾选率 <80%。要么补写漏掉的关键事件，要么回 spec 改计划并注明原因")
        return 1
    return 0


def cmd_cast_presence(root: Path, chapter: int, draft_path: Path) -> int:
    """选角出场检查（liyu G6 本体）：spec「出场角色」清单里的角色是否真的在正文出现。

    阈值取 liyu 实证参数：缺席 ≥ max(2, ⌈2n/3⌉) 拦截（大面积剧情失约）；
    全员 0 次出现降级 warning（第一人称/代词化是正常叙事选择，宁漏勿错杀）；
    仅出场 1 次记「叙事力度不足」提示。别名「张三（火哥）」任一命中即算出场。
    """
    spec_path = root / f"chapters/chapter-{chapter:03d}/spec.md"
    if not spec_path.exists():
        print("⚠️  选角出场：spec.md 不存在，跳过（不拦门禁）")
        return 0
    spec = spec_path.read_text(encoding="utf-8")
    m = re.search(r"## 出场角色[^\n]*\n(.*?)(?=\n## |\Z)", spec, flags=re.S)
    if not m:
        print("⚠️  选角出场：spec 无「出场角色」节（旧版模板），跳过；建议重新跑 chapter_flow prepare")
        return 0  # 旧版 spec 无此节，跳过
    names: list[tuple[str, list[str]]] = []
    for line in m.group(1).splitlines():
        line = line.strip().lstrip("-").strip()
        if not line:
            continue
        # 容忍 AI 补写：取冒号/逗号/空格前的名字段（「- 张三：本章受伤」→「张三」）
        line = re.split(r"[：:，,、\s]", line, 1)[0].strip()
        alias_match = re.fullmatch(r"([\u4e00-\u9fffA-Za-z0-9·]{1,12})(?:[（(]([^）)]{1,12})[）)])?", line)
        if not alias_match:
            continue
        real, alias = alias_match.group(1), alias_match.group(2)
        if len(real) < 2:
            continue  # 单字名子串匹配几乎必命中，无检查价值
        aliases = [real] + ([alias] if alias else [])
        # ≥4 字人名补核心名（身份+人名切尾 2/3 字），如「国师玄冥」→「玄冥」
        if len(real) >= 4:
            aliases.extend({real[-2:], real[-3:]})
        names.append((real, aliases))
    if not names:
        return 0
    body = draft_path.read_text(encoding="utf-8")
    missing = [real for real, aliases in names if not any(a in body for a in aliases)]
    total = len(names)
    if not total:
        return 0
    # 全员 0 次出现 = 多半是第一人称/代词化叙事，降级 warning 不拦（宁漏勿错杀）
    if len(missing) == total:
        print("⚠️  出场角色全部未按名出现（可能第一人称/代词化叙事）：确认是否刻意为之")
        return 0
    threshold = max(2, -(-2 * total // 3))
    if len(missing) >= threshold:
        print(
            f"❌ 选角失约：spec 计划出场的 {total} 人中 {len(missing)} 人未在正文出现"
            f"（{'、'.join(missing)}）——要么补写其戏份，要么回 spec 更新出场名单并注明"
        )
        return 1
    for real, aliases in names:
        hits = sum(body.count(a) for a in aliases)
        if 0 < hits <= 2:
            print(f"⚠️  「{real}」正文仅出现 {hits} 次：计划出场角色叙事力度不足，确认是否有戏")
            break
    return 0


def cmd_style_baseline(draft_path: Path) -> int:
    """风格量化基线软校验 + 文风锚完整性硬校验。

    1) 文风锚完整性（硬拦截，返回 1）：样板段落必须是真实原文（不许占位符），
       必须有正向示范（句式示范或样板段落）；这是「电报体/没味道」的根因闸门。
    2) 量化基线软校验（警告不拦截）：对照 style-anchor 的句长/对话/段落基线。
    """
    root = find_project_root(Path.cwd())
    if root is None:
        return 0
    author = root
    while author != author.parent and not (author / ".novel").is_dir():
        author = author.parent
    anchor_path = author / ".novel" / "style-anchor.md"
    if not anchor_path.exists():
        print("⚠️  文风锚缺失：.novel/style-anchor.md 不存在，写作无风格依据（建议 novel-init 补建）")
        return 0
    anchor_text = anchor_path.read_text(encoding="utf-8")
    if "____" in anchor_text and "平均句长：约 ___ 字" in anchor_text:
        return 0  # 基线未填，跳过

    # ── 文风锚完整性硬校验 ──
    integrity_fail = 0
    sample_m = re.search(r"## 样板段落(.*?)(?=\n## |\Z)", anchor_text, re.S)
    sample = sample_m.group(1) if sample_m else ""
    has_placeholder = ("后续写" in sample) or ("___" in sample) or ("（第" in sample and "章" in sample)
    has_real_sample = len(re.findall(r"[\u4e00-\u9fff]", sample)) >= 60
    positive_m = re.search(r"## 句式示范(.*?)(?=\n## |\Z)", anchor_text, re.S)
    positive = positive_m.group(1) if positive_m else ""
    has_positive = len(re.findall(r"[\u4e00-\u9fff]", positive)) >= 30
    if has_placeholder:
        print("❌ 文风锚样板段落未填（仍是「第 N 章写完后续写」占位）：先回填一段最能代表文风的真实原文，再写正文")
        integrity_fail = 1
    if not has_real_sample and not has_positive:
        print("❌ 文风锚没有正向示范（样板段落空 + 无句式示范）：纯负向清单写不出有味道的正文，先补正向样例")
        integrity_fail = 1
    # 主角名绑定检查：作者级锚不应绑定单书主角（「贴陈默」类历史 bug 的复发检测）
    protag = re.search(r"贴([\u4e00-\u9fff]{1,4})", anchor_text)
    if protag:
        name = protag.group(1)
        chars_dir = root / "tracking" / "characters"
        char_files = list(chars_dir.glob("*.md")) if chars_dir.is_dir() else []
        if char_files and name not in {f.stem for f in char_files}:
            print(f"⚠️  文风锚绑定主角「{name}」与本书角色不符：作者级锚建议写「贴主角」而非具体人名")
    if integrity_fail:
        return 1

    def rng(pattern):
        m = re.search(pattern, anchor_text)
        if not m:
            return None
        lo = int(m.group(1)); hi = int(m.group(2))
        return (min(lo, hi), max(lo, hi))

    sent = rng(r"平均句长：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*字")
    dialog = rng(r"对话占比：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*%")
    para = rng(r"段落中位长度：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*行")
    if not (sent or dialog or para):
        return 0

    text = draft_path.read_text(encoding="utf-8")
    cjk = count_cjk(text)
    # 句长：按句末标点切分
    sents = [s for s in re.split(r"[。！？；\n]", text) if s.strip()]
    sents_cjk = [count_cjk(s) for s in sents]
    avg_sent = round(sum(sents_cjk) / len(sents_cjk), 1) if sents_cjk else 0
    # 对话占比：引号内 CJK / 总 CJK
    quoted = sum(count_cjk(m) for m in re.findall(r"「[^」]*」", text))
    dialog_ratio = round(quoted / cjk * 100, 1) if cjk else 0
    # 段落中位长度（行）
    paras = [par.count("\n") + 1 for par in re.split(r"\n\s*\n", text) if par.strip()]
    paras.sort()
    med_para = paras[len(paras) // 2] if paras else 0

    print("🎨 风格基线校验（对照 style-anchor 量化基线）：")
    if sent and avg_sent:
        lo, hi = int(sent[0] * 0.8), int(sent[1] * 1.3)
        flag = "✅" if lo <= avg_sent <= hi else "⚠️"
        print(f"   {flag} 平均句长 {avg_sent} 字（基线 {sent[0]}-{sent[1]}，容差后 {lo}-{hi}）")
    if dialog and cjk:
        lo, hi = dialog[0] - 15, dialog[1] + 15
        flag = "✅" if lo <= dialog_ratio <= hi else "⚠️"
        print(f"   {flag} 对话占比 {dialog_ratio}%（基线 {dialog[0]}-{dialog[1]}%，容差后 {lo}-{hi}%）")
    if para and med_para:
        lo, hi = max(1, para[0] - 1), para[1] + 2
        flag = "✅" if lo <= med_para <= hi else "⚠️"
        print(f"   {flag} 段落中位 {med_para} 行（基线 {para[0]}-{para[1]} 行，容差后 {lo}-{hi}）")
    return 0


def cmd_unknown_speakers(draft_path: Path) -> int:
    """未登记说话人提示：对话引导词（」后紧跟 说/问/道/喊/应/叫 等）提取说话人名，
    对照 tracking 角色表 + spec 角色要点 + 大纲，未命中 → 警告（防实体幻觉/随手造龙套）。
    只提示不拦截：临时角色可能是有意为之。"""
    root = find_project_root(Path.cwd())
    if root is None:
        return 0
    text = draft_path.read_text(encoding="utf-8")
    # 说话人：」后 2-4 个 CJK 紧跟引导动词
    ADVERBS = {"小声", "低声", "轻声", "回头", "转头", "连忙", "赶紧", "忽然", "顿时", "立刻", "马上", "冷冷", "淡淡", "缓缓", "慢慢", "轻轻", "忽然", "突然", "随即"}
    speakers = set()

    def _known_adverb(name: str) -> bool:
        if name in ADVERBS or name[-1] in "先又也都才便就忙急再":
            return True
        if name[0] in "他她它" and (name[1:] in ADVERBS or not name[1:]):
            return True
        return False

    for m in re.finditer(r"」([\u4e00-\u9fff]{2,3}?)[说问道喊应叫笑骂]", text):
        name = m.group(1)
        if not _known_adverb(name):
            speakers.add(name)
    # 前置式：「马六说道」「马六问」——原实现只认后置式，前置式全部漏检
    for m in re.finditer(r"([\u4e00-\u9fff]{2,3}?)(?:说道|问道|喊道|应道|答道|喝道|骂道|笑道|叫道|低声道|沉声道|开口道)", text):
        name = m.group(1)
        if not _known_adverb(name):
            speakers.add(name)
    if not speakers:
        return 0
    # 已知名单：tracking 角色 + 大纲 + 通用人称
    known = {"他", "她", "他们", "她们", "众人", "大家", "两人", "男人", "女人", "老头", "司机"}
    state_file = root / "tracking" / "_tracking-state.json"
    state = load_json(state_file)
    if isinstance(state, dict):
        known.update(state.get("characters", {}).keys())
    # 人物卡目录（含简卡）——已建卡的角色视为已知
    chars_dir = root / "characters"
    if chars_dir.exists():
        for p in chars_dir.glob("*.md"):
            if not p.name.startswith(".bak-"):
                known.add(p.stem)
    outline = root / "outline.md"
    if outline.exists():
        known.update(re.findall(r"[\u4e00-\u9fff]{2}", outline.read_text(encoding="utf-8")))
    spec = root / draft_path.parent / "spec.md"
    if spec.exists():
        known.update(re.findall(r"[\u4e00-\u9fff]{2}", spec.read_text(encoding="utf-8")))
    unknown = sorted(s for s in speakers if s not in known)
    if unknown:
        print(f"⚠️  未登记说话人：{'、'.join(unknown)}——若为临时龙套可忽略；若为常驻角色请登记进事务 character_snapshots，并按双层卡纪律建卡（与主角/详卡直接相关→详卡 character-card.md；仅见证/提供信息→简卡 character-card-simple.md，写入 characters/）")
    return 0


def cmd_world_rules_advisory(draft_path: Path) -> int:
    """离奇判定（建议级）：正文命中 worldbuilding 硬规则清单「禁止」行的触发词时警告。

    仅提示不拦截（正文是自由文本，词表匹配可能误伤对话/引用）；
    若本章事务已在 tracking 登记 rule_overrides，提示「已登记 override」。
    硬拦截落在事务层：tracking_commit 拒收未登记的规则突破声明。
    """
    root = find_project_root(Path.cwd())
    if root is None:
        return 0
    wb = root / "worldbuilding.md"
    if not wb.exists():
        return 0
    text = wb.read_text(encoding="utf-8")
    m = re.search(r"## 硬规则清单(.*?)(?=## |\Z)", text, flags=re.DOTALL)
    if not m:
        return 0
    draft = draft_path.read_text(encoding="utf-8")
    hits = []
    for row in m.group(1).splitlines():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 3 and cells[0] == "禁止" and cells[2]:
            for word in re.split(r"[、,，]", cells[2]):
                word = word.strip()
                if word and word in draft:
                    hits.append((word, cells[1]))
    if not hits:
        return 0
    overrides = []
    state_file = root / "tracking" / "_tracking-state.json"
    if state_file.exists():
        state = load_json(state_file)
        overrides = state.get("overrides", [])
    for word, rule in hits:
        if any(rule and rule in o.get("rule", "") for o in overrides):
            print(f"⚠️  离奇判定：正文命中禁止触发词「{word}」（{rule}），但已有 override 登记，放行")
        else:
            print(
                f"⚠️  离奇判定：正文命中禁止触发词「{word}」（{rule}）。"
                "若剧情有意打破该规则，必须在事务 delta.rule_overrides 登记理由，否则后续账本拒收矛盾设定"
            )
    return 0


def cmd_exempt(type_: str, key: str | None, reason: str | None) -> int:
    """检查豁免清单管理（.story/exemptions.json，条目格式 {type, key, reason, date}）。

    文本比对类检查（outline_revise 等）对「文字不同但实质一致」的条目存在假冲突，
    人工比对确认无冲突后记入豁免清单，比对方命中该 key 即不再报：
      checks.py exempt outline-revise chapter-goal:5 --reason "措辞不同，实质一致"
      checks.py exempt list
    reason 必填：无理由的豁免是坏账，日后无法审计当初为何放行。
    """
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    path = root / EXEMPTIONS_FILE
    try:
        items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, json.JSONDecodeError):
        print(f"⚠️  豁免清单损坏：{path}——先修复或删除该文件再操作")
        return 1
    if not isinstance(items, list):
        print(f"⚠️  豁免清单格式错误（应为数组）：{path}")
        return 1
    if type_ == "list":
        if not items:
            print("（豁免清单为空）")
            return 0
        for it in items:
            print(f"- [{it.get('type', '?')}] {it.get('key', '?')}｜{it.get('date', '?')}｜{it.get('reason', '')}")
        return 0
    if not key or not reason:
        print('用法：checks.py exempt <type> <key> --reason "人工复核理由"；或 checks.py exempt list')
        return 1
    dup = next((it for it in items if it.get("type") == type_ and it.get("key") == key), None)
    if dup:
        print(f"⚠️  已存在同 key 豁免：[{type_}] {key}（{dup.get('reason', '')}），未重复添加")
        return 0
    from datetime import date
    items.append({"type": type_, "key": key, "reason": reason, "date": date.today().isoformat()})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✅ 已豁免：[{type_}] {key}——比对方检查命中该条时不再报")
    return 0


def cmd_verify() -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    result = subprocess.run(
        [sys.executable, str(TRACKING_SCRIPT), "check", "--project", str(root)],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())
    return result.returncode


def cmd_typo_issues(body: Path) -> int:
    """用词检测（advisory）：高频同音混用与「的/地/得」误用。

    规则数据在 references/check-rules/typo-rules.json（通用引擎 check_engine.py 执行）。
    只查高精度定式，语义层（词不达意）归冷读/polish。命中是候选，语境终判归人。
    """
    rules, ok = load_rules("typo-rules")
    if not ok:
        return 1  # 规则缺失/损坏 = 该检查未执行，按失败处理（fail-closed）
    return run_rules(body.read_text(encoding="utf-8"), rules)


def cmd_writing_rules(root: Path, draft_path: Path) -> int:
    """写作规则库写后投影（G5）：执行 writing-rules.json 的 check 字段。

    写前投影（guide → spec.md「规则注入」节）由 assemble_spec.py 完成；
    本函数补写后投影——同一份规则写前注入、写后检查。规则损坏降级提示不阻断
    （规则库是纪律提示，非账本一致性）。"""
    rules_file = Path(__file__).resolve().parent.parent / "references" / "writing-rules.json"
    if not rules_file.exists():
        print("⚠️  writing-rules.json 缺失：写作规则库检查侧未执行")
        return 0
    try:
        data = json.loads(rules_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"⚠️  writing-rules.json 损坏（{e}）：写作规则库检查侧未执行")
        return 0
    platform = load_pipeline(root).get("platform")
    text = draft_path.read_text(encoding="utf-8")
    rc = 0
    for rule in data.get("rules", []):
        check = rule.get("check")
        if not isinstance(check, dict):
            continue
        rule_platform = rule.get("platform", "all")
        if rule_platform != "all" and rule_platform != platform:
            continue
        if check.get("type") == "count_threshold":
            rc = max(rc, run_count_rule(text, check))
        else:
            run_rules(text, {"rules": [check]})
    return rc


def cmd_prose_issues(body: Path) -> int:
    """语病模式扫描（advisory）：高频「短句压缩过度」错位模式 + CLG-CGEC 定式病句。

    规则数据在 references/check-rules/prose-rules.json（通用引擎执行）。
    来源：实战踩坑 + CLG-CGEC 六类语病统计。只做词面模式，不替代逐句自校
    与 story-polish 子代理；命中只是候选，语境终判归人。
    """
    rules, ok = load_rules("prose-rules")
    if not ok:
        return 1  # 规则缺失/损坏 = 该检查未执行，按失败处理（fail-closed）
    return run_rules(body.read_text(encoding="utf-8"), rules)


def cmd_sermon_density(body: Path) -> int:
    """说教/解释腔密度（红线 7）：直接告诉读者道理与情绪的信号词统计。

    规则数据在 references/check-rules/sermon-rules.json（通用引擎执行，
    warn/block 阈值在 JSON 里，改阈值不改代码）。
    与 deslop 支线的 reasoning-chain 检测同源，但走主线 draft 闸门。
    修法：把判断落到动作/物件/对话，让读者自己得出道理。
    """
    rules, ok = load_rules("sermon-rules")
    if not ok:
        return 1  # 规则缺失/损坏 = 该检查未执行，按失败处理（fail-closed）
    return run_count_rule(body.read_text(encoding="utf-8"), rules)


def cmd_pacing_balance(root: Path, chapter: int) -> int:
    """章节定位平衡（红线 10 节奏失衡 + 特质 7 张弛呼吸）：读最近 5 章 spec 的
    「章节定位」字段，同一定位 ≥4 章 → 软警告（连爆 3 章必放 1 章的纪律）。
    旧书 spec 无该字段时静默跳过（兼容存量）。
    """
    import re
    values = []
    for n in range(max(1, chapter - 4), chapter + 1):
        spec = root / f"chapters/chapter-{n:03d}" / "spec.md"
        if not spec.exists():
            continue
        m = re.search(
            r"^## 章节定位[^\n]*\n(.*?)(?=\n## |\Z)",
            spec.read_text(encoding="utf-8"),
            flags=re.DOTALL,
        )
        if not m:
            continue
        for line in m.group(1).splitlines():
            line = line.strip()
            if line.startswith("-"):
                line = line[1:].strip()
            mm = re.search(r"(铺垫|推进|高潮|收束)", line)
            if mm:
                values.append(mm.group(1))
                break
    if len(values) >= 4 and len(set(values)) == 1:
        print(f"⚠️  章节定位失衡：最近 {len(values)} 章全是「{values[0]}」——连爆 3 章必放 1 章，下一章换定位")
    return 0


def run_step(step: str) -> int:
    root = find_project_root(Path.cwd())
    if root is None:
        print("❌ 不在项目中")
        return 1
    pipe = load_pipeline(root)

    if step == "outline":
        return cmd_outline(root / "outline.md")

    if step == "draft":
        chapter = pipe.get("chapter", 1)
        body = find_chapter_body(root, chapter)
        if body is None:
            print(f"❌ 未找到第 {chapter} 章正文（chapters/），无法校验")
            return 1
        prev_body = find_chapter_body(root, chapter - 1) if chapter > 1 else None
        print("── 字数闸门（平台×类型）──")
        rc1, zone = cmd_wordcount(
            str(body), pipe.get("platform"), pipe.get("type") or "长篇小说"
        )
        print("── G5 描写一致性（去AI味）──")
        rc2 = cmd_deai(str(body))
        print("── G3 一致性（跨章衔接）──")
        rc3 = cmd_cross_chapter(body, prev_body)
        cmd_seam(root, chapter)
        rc4 = cmd_meta_mark(body)
        print("── G6 履约检查（spec 勾选率 ≥80%）──")
        rc5 = cmd_spec_fulfillment(root / f"chapters/chapter-{chapter:03d}/spec.md")
        rc5 = max(rc5, cmd_cast_presence(root, chapter, body))
        print("── G3 一致性（世界规则 advisory）──")
        cmd_world_rules_advisory(body)
        print("── G5 描写一致性（风格基线）──")
        rc6 = cmd_style_baseline(body)
        print("── G4 未知实体（未登记说话人）──")
        cmd_unknown_speakers(body)
        print("── G5 描写一致性（语病/说教/规则库，规则检查侧）──")
        cmd_prose_issues(body)
        cmd_typo_issues(body)
        rc7 = cmd_sermon_density(body)
        rc7 = max(rc7, cmd_writing_rules(root, body))
        cmd_pacing_balance(root, chapter)

        # 连续软区趋势防线：连续 3 章落在同一软区 → 升级为硬拦截。
        # 计数由 pipeline.py advance 在通过后更新；checks 只读不写。
        blocked = 0
        if zone == "soft_low" and pipe.get("soft_short_streak", 0) >= 2:
            print(
                f"❌ 趋势拦截：连续第 {pipe.get('soft_short_streak', 0) + 1} 章低于目标下限，"
                "本章必须补足到目标区间，否则全书篇幅会持续缩水"
            )
            blocked = 1
        elif zone == "soft_high" and pipe.get("soft_long_streak", 0) >= 2:
            print(
                f"❌ 趋势拦截：连续第 {pipe.get('soft_long_streak', 0) + 1} 章超过目标上限，"
                "本章必须压回目标区间，否则全书注水膨胀"
            )
            blocked = 1
        print(f"ZONE:{zone}")
        return 1 if (rc1 or rc2 or rc3 or rc4 or rc5 or rc6 or rc7 or blocked) else 0

    if step == "archive":
        return cmd_verify()

    print(f"❌ 未知 step：{step}（支持 draft / archive）")
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    if args[0] in ("outline", "draft", "archive"):
        return run_step(args[0])

    parser = argparse.ArgumentParser(description="确定性校验脚本")
    sub = parser.add_subparsers(dest="command", required=True)

    p_wc = sub.add_parser("wordcount", help="CJK 字数校验")
    p_wc.add_argument("file")
    p_wc.add_argument("--platform")
    p_wc.add_argument("--type", default="长篇小说")
    p_wc.set_defaults(
        func=lambda a: cmd_wordcount(a.file, a.platform, a.type)[0]
    )

    p_deai = sub.add_parser("deai", help="去 AI 味检测")
    p_deai.add_argument("file")
    p_deai.set_defaults(func=lambda a: cmd_deai(a.file))

    p_verify = sub.add_parser("verify", help="一致性校验")
    p_verify.set_defaults(func=lambda a: cmd_verify())

    p_exempt = sub.add_parser("exempt", help="检查豁免清单管理（list / 添加）")
    p_exempt.add_argument("type", help="检查类型（如 outline-revise），或 list 列出全部")
    p_exempt.add_argument("key", nargs="?", default=None, help="冲突条目 key（list 时省略）")
    p_exempt.add_argument("--reason", default=None, help="人工复核理由（添加时必填）")
    p_exempt.set_defaults(func=lambda a: cmd_exempt(a.type, a.key, a.reason))

    a = parser.parse_args(args)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
