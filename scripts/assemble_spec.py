#!/usr/bin/env python3
"""assemble_spec.py — 章节蓝图组装器（把确定性组装从 AI 手里接过来）

读 tracking 账本 + outline + 题材卡 + 文风锚，把 spec.md 的确定性部分
自动填好：大纲要点、概念预算提示、角色要点、前情衔接、知情边界、
时间线定位、伏笔指令、题材要点、风格指令。AI 只补判断项（概念取舍、
本章时间推进、钩子设计），不再手工抄文件——抄写是 AI 出错的重灾区。

用法：
  assemble_spec.py --chapter N [--project 书目录] [--force]
  （先 new_chapter.py --chapter N 建模板，再跑本脚本填内容）

只填充空位：已写内容（含 AI 之前的创作）不被覆盖。spec 已被 AI 填写判断项
（五问闸门/净变化/时间线等有值）时整次跳过，防覆盖丢稿；--force 强制重组装。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import PIPELINE_FILE, find_project_root, read_json
from writer_profile import WRITER_MODEL, WRITER_NAME, author_root, load_profile

SPEC_DIR_TMPL = "chapters/chapter-{chapter:03d}"
SECTION_RE = re.compile(r"^## (.+)$")
WRITING_RULES_FILE = Path(__file__).resolve().parent.parent / "references" / "writing-rules.json"


def writing_rule_lines(root: Path, scope: str = "generate") -> list[str]:
    """写作规则库写前投影：读 references/writing-rules.json，
    按 scope + platform 过滤（tier=core 恒注入；standard 需平台匹配），返回 guide 行。
    规则缺失/损坏时静默降级为空（不阻塞蓝图组装）。"""
    data = read_json(WRITING_RULES_FILE)
    if not isinstance(data, dict):
        return []
    state = read_json(root / PIPELINE_FILE, default={}) or {}
    platform = state.get("platform") if isinstance(state, dict) else None
    lines: list[str] = []
    for rule in data.get("rules", []):
        if not isinstance(rule, dict) or not rule.get("guide"):
            continue
        if scope not in rule.get("scope", ["generate"]):
            continue
        rule_platform = rule.get("platform", "all")
        if rule.get("tier") != "core" and platform and rule_platform != "all" and rule_platform != platform:
            continue
        tag = "红线" if rule.get("tier") == "core" else "标准"
        name = rule.get("name", "")
        lines.append(f"- [{tag}·{name}] {rule['guide']}")
    return lines


def playbook_reminders(root: Path) -> list[str]:
    """作者技法库提醒：最近的技术经验与踩过的坑，各最多 2 条。"""
    a = author_root(root)
    if a is None:
        return []
    pb = a / ".novel" / "writing-playbook.md"
    if not pb.exists():
        return []
    text = pb.read_text(encoding="utf-8")
    out = []
    for section, label in (
        ("妙处", "技法库·可复用妙处"),
        ("文风技法", "技法库·最近经验"),
        ("问题", "技法库·避开"),
    ):
        m = re.search(rf"^## {section}\n(.*?)(?=^## |\Z)", text, flags=re.MULTILINE | re.DOTALL)
        if not m:
            continue
        entries = [l.strip() for l in m.group(1).splitlines() if l.strip().startswith("- ")]
        if entries:
            out.append(f"- （{label}）")
            out.extend(f"  {e}" for e in entries[-2:])
    return out


def book_root(args) -> Path | None:
    start = Path(args.project) if args.project else Path.cwd()
    return find_project_root(start, child=".story")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_outline_chapter(outline: str, chapter: int) -> dict[str, str]:
    """解析 outline.md 的「### 第N章：标题」块，返回四字段。"""
    blocks = re.split(r"(?m)^### ", outline)
    fields = {}
    for block in blocks:
        m = re.match(r"第\s*(\d+)\s*章[：:·]", block)
        if not m or int(m.group(1)) != chapter:
            continue
        for line in block.splitlines():
            fm = re.match(r"-\s*(本章目标|场景安排|关键事件|章末钩子|新概念)[：:]\s*(.*)", line)
            if fm:
                fields[fm.group(1)] = fm.group(2).strip()
    return fields


def parse_concept_budget(outline: str, chapter: int) -> str:
    """解析概念预算行「- 第N章：引入「X」…」，返回提示文本。"""
    for line in outline.splitlines():
        if not line.lstrip().startswith("- ") or ("引入" not in line and "概念" not in line):
            continue
        for m in re.finditer(r"第\s*(\d+)\s*章[：:]\s*([^；;]+)", line):
            if int(m.group(1)) == chapter:
                return m.group(2).strip()
    return ""


def parse_outline_foreshadows(outline: str, chapter: int) -> list[str]:
    """解析伏笔规划表里「埋设章==本章」的行，返回植入指令。"""
    hits = []
    for line in outline.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"F\d+", cells[0]):
            continue
        planted = cells[2] if len(cells) > 2 else ""
        m = re.search(r"(\d+)", planted)
        if not m or int(m.group(1)) != chapter:
            continue
        fid = pad_fid(cells[0])
        content = cells[1] if len(cells) > 1 else "（见大纲）"
        planned = cells[3] if len(cells) > 3 else "未定"
        ftype = cells[4] if len(cells) > 4 else "未定"
        hits.append(f"- 植入 {fid}：{content}（计划回收 {planned}，类型 {ftype}）")
    return hits


def pad_fid(fid: str) -> str:
    m = re.match(r"F(\d+)", fid.strip())
    return f"F{int(m.group(1)):03d}" if m else fid.strip()


def parse_foreshadow_table(text: str) -> list[dict]:
    """兼容账本两种表结构（ID 可能 F01 或 F001、列数 5-8）。

    planted/planned 保留原字符串（gen_transaction 用）；*_no 是 int（check_continuity 用）。
    progress_note 是「推进」态的进度载体（v2 新列，旧表无该列时为空串）。
    """
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5 or not re.fullmatch(r"F\d{1,4}", cells[0]):
            continue
        def num(s):
            mm = re.search(r"\d+", s)
            return int(mm.group()) if mm else 0
        progress = cells[7] if len(cells) > 7 else ""
        rows.append({
            "id": cells[0], "summary": cells[1],
            "planted": cells[2], "planned": cells[3], "status": cells[4],
            "importance": cells[5] if len(cells) > 5 else "中",
            "planted_no": num(cells[2]), "planned_no": num(cells[3]),
            "progress_note": "" if progress in ("", "—") else progress,
        })
    return rows


def chapter_in(text: str, chapter: int) -> bool:
    return bool(re.search(rf"第\s*{chapter}\s*章", text))


FILLED_FIELD_RE = re.compile(r"-\s*(变化项|主角代价/取舍|本章开头时间点|距上章过去)[：:]\s*(.*)")
GATE_SECTION_RE = re.compile(r"(?m)^## 五问闸门结果[^\n]*\n(.*?)(?=\n## |\Z)", re.DOTALL)


def spec_filled(spec: str) -> bool:
    """spec 是否已被 AI 填写过判断项（模板与 assemble 自动填充均不算）。

    判据（任一命中即算已填写）：
    1. 「五问闸门结果」节存在且非空——new_chapter 模板没有该节，出现即 AI 亲手加的；
    2. 判断项字段已填值——模板/assemble 的占位均为空标签、「待定」或（括号说明）。
    误判「已填」的代价是少组装一次（--force 可重跑）；误判「未填」会走原路径，
    各节有 section_empty 守卫兜底，不会覆盖 AI 内容。
    """
    m = GATE_SECTION_RE.search(spec)
    if m and m.group(1).strip():
        return True
    for line in spec.splitlines():
        fm = FILLED_FIELD_RE.match(line.strip())
        if not fm:
            continue
        value = fm.group(2).strip()
        if value and value != "待定" and not value.startswith("（"):
            return True
    return False


def parse_pacing_stance(root: Path, chapter: int) -> dict | None:
    """解析 tracking/pacing.md 中对本章的节奏定位（强度 + 显式「不推进」的伏笔）。

    返回 {"intensity": "低/中/高"|None, "holds": {FID,...}}；pacing.md 缺失、
    为空或两者都解析不出时返回 None——冲突检测是 advisory，宁缺勿误报。
    """
    text = read_text(root / "tracking" / "pacing.md")
    if not text.strip():
        return None
    intensity = None
    m = re.search(rf"^\|\s*第\s*{chapter}\s*章\s*\|\s*(低|中|高)\s*\|", text, flags=re.MULTILINE)
    if m:
        intensity = m.group(1)
    holds: set[str] = set()
    # 「不推进 F00x」只在与本章号同句时才算对本章的安排（按 。；\n 分句），
    # 避免把「第 8 章……F006 不推进」误当成第 9 章的约束。
    for seg in re.split(r"[。；\n]", text):
        if not re.search(rf"第\s*{chapter}\s*章", seg):
            continue
        if re.search(r"不(?:直接)?推进?|慢热", seg):
            holds.update(pad_fid(f) for f in re.findall(r"F\d{1,4}", seg))
    if intensity is None and not holds:
        return None
    return {"intensity": intensity, "holds": holds}


def pacing_conflict_lines(root: Path, chapter: int, actions: dict[str, str]) -> list[str]:
    """pacing 定位与伏笔台账本章动作冲突时，返回 spec 伏笔指令区的警告行。

    pacing 是节奏最高权威：冲突不替 AI 仲裁，但必须显式摆进 spec——
    靠 agent 自己翻 pacing 发现冲突是赌运气（M3 第 9 章 F006 实证）。
    """
    stance = parse_pacing_stance(root, chapter)
    if stance is None:
        return []
    out = []
    for fid in sorted(actions):
        action = actions[fid]
        if stance["intensity"] == "低":
            out.append(
                f"- ⚠️ pacing 冲突：pacing 将第 {chapter} 章定位为低强度缓冲章，"
                f"但 {fid} 计划本章{action}——先人工核订 pacing.md 该行（可能是自动投影初稿），再定伏笔动作"
            )
        if fid in stance["holds"]:
            out.append(
                f"- ⚠️ pacing 冲突：pacing 第 {chapter} 章安排不推进 {fid}，"
                f"但本指令要求{action}——先人工核订 pacing.md 该行（可能是自动投影初稿），再定伏笔动作"
            )
    return out


def parse_inventions(root: Path) -> list[dict]:
    """读账本里的写手发明申报（[{chapter, text}]）。

    发明是写手在正文中确立的计划外设定，进账本后从这里注入后续章 spec——
    防写手发明与章纲/后文静默冲突（M3 第 3 章「601 哑巴孙女」实证）。"""
    state = read_json(root / "tracking" / "_tracking-state.json")
    if isinstance(state, dict):
        inv = state.get("inventions")
        if isinstance(inv, list):
            return [i for i in inv if isinstance(i, dict) and i.get("text")]
    return []


def parse_context(root: Path) -> dict:
    text = read_text(root / "tracking" / "context.md")
    pos = {"当前章": "", "卷": "", "故事时间": "", "场景": ""}
    in_pos = False
    recent = []
    for line in text.splitlines():
        if line.startswith("## 当前位置"):
            in_pos = True
            continue
        if line.startswith("## "):
            in_pos = False
        if in_pos:
            m = re.match(r"-\s*([^：:]+)[：:]\s*(.*)", line)
            if m:
                key = m.group(1).strip()
                if key in pos:
                    pos[key] = m.group(2).strip()
        m = re.match(r"-\s*第\s*(\d+)\s*章[｜|]\s*(.*)", line)
        if m:
            recent.append(f"第{m.group(1)}章｜{m.group(2)}")
    return {"position": pos, "recent": recent}


def parse_thread_stop(root: Path) -> str | None:
    """读 threads.md，返回当前线程（▶ 标记）的停点摘要；无则 None。"""
    threads_path = root / "tracking" / "threads.md"
    if not threads_path.exists():
        return None
    for line in threads_path.read_text(encoding="utf-8").splitlines():
        if "▶" in line:
            return line.strip()
    return None


def parse_timeline(root: Path) -> tuple[list[str], list[str]]:
    known = []
    for line in read_text(root / "tracking/timeline/reader-known.md").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"E\d+", cells[0]):
            known.append(f"{cells[0]}：{cells[1]}（读者已知，截至 {cells[2]}）")
    unknown = []
    for line in read_text(root / "tracking/timeline/author-truth.md").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and re.fullmatch(r"E\d+", cells[0]) and cells[5] == "未揭示":
            unknown.append(f"{cells[0]}：{cells[2]}（读者暂不知道）")
    return known, unknown


def active_characters(root: Path) -> list[str]:
    state = read_json(root / "tracking/_tracking-state.json")
    if not isinstance(state, dict):
        return []
    names = state.get("context", {}).get("active_character_names", [])
    return [n for n in names if isinstance(n, str)]


def character_line(root: Path, name: str) -> str:
    text = read_text(root / "tracking" / "characters" / f"{name}.md")
    fields = {}
    for line in text.splitlines():
        m = re.match(r"-\s*(身份|位置|当前目标|身心状态)[：:]\s*(.*)", line)
        if m:
            fields[m.group(1)] = m.group(2).strip()
    parts = []
    if fields.get("位置"):
        parts.append(f"位置：{fields['位置']}")
    if fields.get("身心状态"):
        parts.append(f"状态：{fields['身心状态']}")
    if fields.get("当前目标"):
        parts.append(f"目标：{fields['当前目标']}")
    return f"- {name}｜{'；'.join(parts)}" if parts else f"- {name}（见 tracking/characters/{name}.md）"


def anchor_lines(root: Path) -> list[str]:
    """作者级 style-anchor 的可注入行（人称/视角纪律 + 本书不用的腔调）。

    未填锚的占位/示例行（____、{如…}，含「- {如…}」形式）一律跳过，防泄漏进 spec。"""
    anchor = read_text(root / ".novel" / "style-anchor.md")
    lines = []
    for line in anchor.splitlines():
        if "____" in line or "（第一/第三）" in line or "单视角 / 多视角" in line or "{如" in line:
            continue
        m = re.match(r"-\s*(人称|视角纪律)[：:]\s*(.*)", line)
        if m:
            lines.append(f"- {m.group(1)}：{m.group(2).strip()}")
    in_banned = False
    for line in anchor.splitlines():
        if "____" in line or "{如" in line:
            continue
        if line.startswith("## 本书不用的腔调"):
            in_banned = True
            continue
        if line.startswith("## "):
            in_banned = False
        if in_banned and line.startswith("- "):
            lines.append(line)
            if len(lines) >= 6:
                break
    return lines


# 语病避雷（写作时必守，前置约束；checks 语病模式扫描兜底。清单 ≤8 条，
# 全部「症状→正解」格式且可 grep 二值验证——约束越多模型越无视，不堆禁令）。
# 作为独立小节落盘，不嵌进风格指令节内容（防节边界解析错位）。
YUBING_HEADER = "## 语病避雷（写作时必守，写完自校）"
YUBING_LINES = [
    "- 主语让位给「通过/随着」：不写「通过改革使公司变好」→写「改革让公司变好」",
    "- 句式不杂糅：不写「据数据显示/原因是由于/目的是为了」→各留一个（数据显示/原因是/目的是）",
    "- 否定只加一层：不写「避免不迟到」→写「避免迟到」",
    "- 数量表达说人话：不写「降低三倍/大约五十人左右」→写「降到三分之一/大约五十人」",
    "- 不写悬空同位语：「需求文档，第十七版。」→写「已经改到第十七版」",
    "- 数量与并列不冲突：不写「就剩他一个，和灯」→写「只剩他和灯」或拆成两句",
    "- 数量定语放对位置：不写「亮着三分之一的灯」→写「还有三分之一的灯亮着」",
    "- 关联词不错配：不写「不仅…但…」→写「不仅…而且…」",
    "- 比喻不与本体重复：不写「亮着一半，像一盏半明半暗的灯」→换喻体或删",
    "- 不堆砌赘余词：不写「凯旋归来/免费赠送/十分非常」→写「凯旋/赠送/非常」",
    "- 用字不混：的得地分清（跑得很快/轻轻地说）；不写「既使/按装/必竟」→「即使/安装/毕竟」",
    "- 写完换读者身份用 Read 重读 draft.md：先逐句读通顺，再对照本清单扫一遍，不通的当场改（开头 500 字逐句精读）",
]


def style_lines(root: Path) -> list[str]:
    """兼容入口：anchor 行 + 语病避雷整节（旧调用方语义）。"""
    return anchor_lines(root) + [YUBING_HEADER] + YUBING_LINES


def card_hook_lines(root: Path) -> list[str]:
    card = read_text(root / "题材卡.md")
    lines, in_hook = [], False
    for line in card.splitlines():
        if line.startswith("## 章尾钩子"):
            in_hook = True
            continue
        if line.startswith("## "):
            in_hook = False
        if in_hook and line.strip() and not line.startswith("#"):
            lines.append(line)
    return lines


def foreshadow_lines(root: Path, chapter: int, outline_plants: list[str]) -> tuple[list[str], dict[str, str]]:
    rows = parse_foreshadow_table(read_text(root / "tracking" / "foreshadows.md"))
    lines = []
    closed = []
    actions: dict[str, str] = {}  # FID → 本章动作（回收/推进），供 pacing 冲突比对
    for row in rows:
        fid = pad_fid(row["id"])
        if row["status"] == "已埋":
            if chapter_in(row["planned"], chapter):
                lines.append(f"- 回收 {row['id']}：{row['summary'][:40]}（计划回收 {row['planned']}）")
                actions[fid] = "回收"
            elif chapter_in(row["planned"], chapter + 1) or chapter_in(row["planned"], chapter + 2):
                lines.append(f"- 推进 {row['id']}：临近回收（{row['planned']}），本章为回收铺垫")
                actions[fid] = "推进"
        elif row["status"] == "推进":
            # 进度注记：让「推进」态有进度载体，spec 里与「已埋」有本质区别
            # （推进到哪里、还差什么）；未填时退回无注记的通用指令。
            progress = f"，进度：{row['progress_note']}" if row.get("progress_note") else ""
            lines.append(
                f"- 继续推进 {row['id']}：{row['summary'][:40]}（引信已落地{progress}，"
                f"本章保持可见或再推进一步，计划回收 {row['planned']}）"
            )
            actions[fid] = "推进"
        elif row["status"] in ("已回收", "已过期", "放弃"):
            closed.append(f"{row['id']}（{row['summary'][:30]}）")
    lines.extend(outline_plants)
    # 反向提示：已回收/已过期/放弃的悬念严禁重复写——长篇隔几十章后重提已揭晓悬念是高频吃书点。
    # 上限 20 条：数百条全列会稀释关键信息；超出时只列最近 20 条（按编号最大优先）。
    if closed:
        shown = closed[-20:]
        suffix = f"（共 {len(closed)} 条，仅列最近 {len(shown)} 条）" if len(closed) > 20 else ""
        lines.append(f"- ⛔ 已了结，本章严禁重复写或再当悬念用{suffix}：{'、'.join(shown)}")
    return lines, actions


LABEL_ONLY = re.compile(r"^- ?(读者已知|读者不知|故事时间|距上章过去|本章目标|场景安排|关键事件|章末钩子|新概念)[：:]?$")


def section_empty(content: str) -> bool:
    """小节是否「空」：只有空行、单独破折号或标签占位行。"""
    for line in content.splitlines():
        s = line.strip()
        if not s or s == "-":
            continue
        if LABEL_ONLY.match(s):
            continue
        return False
    return True


def assemble(root: Path, chapter: int, force: bool = False) -> tuple[Path, bool]:
    """组装 spec 的确定性部分。返回 (spec 路径, 是否跳过)。

    spec 已被 AI 填写判断项时跳过（防覆盖丢稿——M3 第 9 章被迫「备份→跑→恢复」
    绕过的正是这条路径）；--force 保留强制重组装能力（逐节 section_empty
    守卫仍在，AI 填过的节也不会被覆盖）。
    """
    spec_path = root / SPEC_DIR_TMPL.format(chapter=chapter) / "spec.md"
    if not spec_path.exists():
        print(f"❌ spec 不存在：{spec_path}（先跑 new_chapter.py --chapter {chapter}）")
        raise SystemExit(1)
    spec = read_text(spec_path)
    if spec_filled(spec) and not force:
        print("✅ spec 已填写，跳过重新组装（保留 AI 判断项；如需重置用 --force）")
        return spec_path, True

    outline = read_text(root / "outline.md")
    fields = parse_outline_chapter(outline, chapter)
    budget = parse_concept_budget(outline, chapter)
    plants = parse_outline_foreshadows(outline, chapter)
    ctx = parse_context(root)
    known, unknown = parse_timeline(root)
    chars = active_characters(root)
    author = author_root(root)
    style = anchor_lines(author) if author else []
    # 写手档案（AI 味与文风纠缠，按写手实测校准）：spec 标注本书写手，并把
    # 写前避开项注入风格指令——检测分层在写后，这里管写前
    writer_prof = load_profile(author)
    if writer_prof:
        style.insert(0, f"- 当前写手：{WRITER_NAME}（{WRITER_MODEL}；风格基线与 AI 味提醒阈值按写手档案校准）")
        style.extend(f"- 写手避开：{item}" for item in writer_prof["avoid"])
    hooks = card_hook_lines(root)
    fores, fid_actions = foreshadow_lines(root, chapter, plants)
    # pacing 冲突警告是机器生成的动态行：单独计算，供已组装 spec 刷新旧警告用
    pacing_warnings = pacing_conflict_lines(root, chapter, fid_actions)

    def section(title: str) -> str:
        """返回该小节的当前内容（标题行之后、下一个标题之前）。"""
        m = re.search(rf"(?m)^## {re.escape(title)}(?:（[^）]*）)?\s*\n(.*?)(?=\n## |\Z)", spec, flags=re.DOTALL)
        return m.group(1) if m else ""

    def replace_section(title: str, content: str) -> None:
        nonlocal spec
        m = re.search(rf"(?m)^## {re.escape(title)}(?:（[^）]*）)?\s*\n(.*?)(?=\n## |\Z)", spec, flags=re.DOTALL)
        if not m:
            return
        spec = spec[: m.start()] + f"## {title}\n{content}\n" + spec[m.end() :]

    # 大纲要点：只填空位；未开写章（无 [x] 勾选）内容随新大纲自动刷新——
    # 已写章的履约清单是写作存档不动；防「改了大纲旧 spec 还指旧计划」
    checklist = section("大纲要点")
    fresh_points = "\n".join(
        f"- [ ] {label}：{fields[label]}"
        for label in ("本章目标", "场景安排", "关键事件", "章末钩子")
        if label in fields
    )
    if (
        fresh_points
        and checklist.strip()
        and "[x]" not in checklist
        and checklist.strip() != fresh_points
    ):
        checklist = fresh_points + "\n"
        replace_section("大纲要点", checklist)
        print("   大纲要点已随新大纲更新（本章未开写）")
    for label in ("本章目标", "场景安排", "关键事件", "章末钩子"):
        if label not in fields:
            continue
        pat = re.compile(rf"^(- \[ \]) {re.escape(label)}：\s*$", flags=re.MULTILINE)
        if pat.search(checklist):
            checklist = pat.sub(rf"\1 {label}：{fields[label]}", checklist)
    replace_section("大纲要点", checklist)

    # 概念要点：给预算提示（不覆盖 AI 已写内容）
    conc = section("概念要点")
    if budget and section_empty(conc):
        replace_section("概念要点", f"- （大纲概念预算：{budget}）\n")

    # 角色要点
    rp = section("角色要点")
    if section_empty(rp):
        lines = [character_line(root, n) for n in chars] or ["- （无活跃核心角色，按大纲本章出场补充）"]
        replace_section("角色要点", "\n".join(lines) + "\n")

    # 出场角色清单（选角出场检查的依据：checks.py cast_presence 比对正文）
    cp = section("出场角色")
    if section_empty(cp) and chars:
        replace_section("出场角色", "\n".join(f"- {n}" for n in chars) + "\n")

    # 前情衔接
    pre = section("前情衔接")
    if section_empty(pre):
        lines = ["- 上章结尾（近三章速记）："]
        if ctx["recent"]:
            lines.extend(f"  - {r}" for r in ctx["recent"][-3:])
        else:
            lines.append("  - （无，第 1 章）")
        # 多线叙事：本线停点（切线续写时必须从这里接）
        thread_stop = parse_thread_stop(root)
        if thread_stop and "▶" in thread_stop:
            lines.append("- 本线停点（切回这条线时从这里接，见 tracking/threads.md）：")
            lines.append(f"  - {thread_stop}")
        if chapter > 1:
            prev_draft = read_text(root / f"chapters/chapter-{chapter-1:03d}/draft.md")
            if prev_draft.strip():
                tail = prev_draft.strip()[-120:]
                lines.append("- 上章结尾原文（衔接锚，本章开头必须从这里延续）：")
                lines.append(f"  「{tail}」")
        inv = parse_inventions(root)
        if inv:
            lines.append("- 写手发明（前文计划外确立的设定/人物/事实，本章不得与之矛盾）：")
            lines.extend(f"  - （第{i['chapter']}章）{i['text']}" for i in inv[-6:])
        replace_section("前情衔接", "\n".join(lines) + "\n")

    # 知情边界
    kb = section("知情边界")
    if section_empty(kb):
        lines = ["- 读者已知："]
        if known:
            lines.extend(f"  - {k}" for k in known)
        else:
            lines.append("  - （暂无时间线记录）")
        lines.append("- 读者不知：")
        if unknown:
            lines.extend(f"  - {u}" for u in unknown)
        else:
            lines.append("  - （暂无未揭示事实）")
        replace_section("知情边界", "\n".join(lines) + "\n")

    # 时间线定位
    tl = section("时间线定位")
    if section_empty(tl):
        lines = [f"- 故事时间：上章为「{ctx['position']['故事时间']}」，本章待定", "- 距上章过去：待定"]
        replace_section("时间线定位", "\n".join(lines) + "\n")

    # 伏笔指令
    fi = section("伏笔指令")
    if section_empty(fi):
        fores = fores + pacing_warnings
        replace_section("伏笔指令", ("\n".join(fores) + "\n") if fores else "- 本章无伏笔动作\n")
    else:
        # 已组装过的 spec：①剔除陈旧的 pacing 冲突警告（机器生成行，按最新 pacing.md
        # 重算——人工核订 pacing 后旧警告不得残留误导写手）②只补缺失的「植入」行
        # （随新大纲新增的伏笔），不覆盖 AI 注记
        kept = [l for l in fi.splitlines() if "⚠️ pacing 冲突" not in l]
        changed = kept != fi.splitlines()
        missing = [
            line
            for line in fores
            if line.startswith("- 植入 ") and line.split("：", 1)[0] not in fi
        ]
        if changed or missing or pacing_warnings:
            new_fi = "\n".join(kept).rstrip("\n")
            add = missing + pacing_warnings
            if add:
                new_fi = new_fi + "\n" + "\n".join(add)
            replace_section("伏笔指令", new_fi + "\n")
            why = "、".join(x for x in ("陈旧警告清理" if changed else "", "缺失植入行" if missing else "", "pacing 冲突刷新" if pacing_warnings else "") if x)
            print(f"   伏笔指令已更新（{why}）")

    # 题材要点
    tp = section("题材要点")
    if hooks and section_empty(tp):
        replace_section("题材要点", "（题材卡「章尾钩子」节，按本章择用）\n" + "\n".join(hooks) + "\n")

    # 硬规则清单注入（每章必见——「戒不可脱」类永久锁死规则漏检一次就是 bug）
    wb_path = root / "worldbuilding.md"
    if wb_path.exists():
        wb_text = wb_path.read_text(encoding="utf-8")
        wm = re.search(r"##\s*硬规则清单[^\n]*\n(.*?)(?=\n## |\Z)", wb_text, flags=re.DOTALL)
        hard_rules = [
            l.strip()
            for l in (wm.group(1).splitlines() if wm else [])
            if l.strip().startswith("|") and "禁止" in l or l.strip().startswith("|") and "上限" in l or l.strip().startswith("|") and "唯一" in l
        ]
        if hard_rules and section("硬规则（本章不得违反）") == "" or not section("硬规则（本章不得违反）").strip():
            replace_section(
                "硬规则（本章不得违反）",
                "\n".join(f"- {r}" for r in hard_rules[:8]) + "\n",
            )

    # 规则注入（写作规则库写前投影：core 恒注入，standard 按平台过滤）
    rl = section("规则注入")
    if section_empty(rl):
        rule_lines = writing_rule_lines(root)
        if rule_lines:
            replace_section("规则注入", "\n".join(rule_lines) + "\n")

    # 质量反哺：上一章冷读低分 → 本章 spec 提示（趋势数据消费，防低分被淹没）
    trend_file = root / ".story" / "quality-trend.json"
    try:
        import json as _json
        trend = _json.loads(trend_file.read_text(encoding="utf-8")) if trend_file.exists() else {}
        recent = trend.get("chapters", [])[-3:]
        if recent:
            low = [c for c in recent if c.get("avg", 5) < 3.5 or any(s <= 2 for s in c.get("scores", []))]
            if low:
                last = low[-1]
                ch = last.get("chapter")
                dims = [d for d, s in zip(("翻页欲", "认知负荷", "共情验证", "节奏感受"), last.get("scores", [])) if s <= 2]
                style.append(f"- （质量反哺）第{ch}章冷读低分{('，短板：' + '/'.join(dims)) if dims else ''}——本章针对性补强该维度")
    except (ValueError, OSError, ImportError):
        pass

    # 风格指令（写手行 + anchor 腔调行）；语病避雷独立成节，见下
    st = section("风格指令")
    if section_empty(st) and not style:
        style.insert(0, "- ⚠️ 文风锚为空模板：本书暂无文风约束，AI 生成易滑向单一腔调。建议尽快回填 .novel/style-anchor.md（腔调 3 词 + 样板段落）")
    if section_empty(st):
        style += playbook_reminders(root)
        replace_section("风格指令", "\n".join(style) + "\n")
    if YUBING_HEADER not in spec:
        # 语病避雷独立小节：紧跟风格指令节追加，不覆盖 AI 填过的内容。
        # 双重防重：全 spec 已有该节就不再追加（历史上 replace 目标不匹配会
        # 静默失败 → 每次重跑堆积一份）
        extra = [l for l in style if l.startswith("- （质量反哺）")]
        block = "\n".join([YUBING_HEADER] + YUBING_LINES + extra)
        st2 = section("风格指令")
        anchor_head = f"## 风格指令\n{st2}" if st2 else None
        if anchor_head and anchor_head in spec:
            spec = spec.replace(anchor_head, anchor_head.rstrip("\n") + "\n\n" + block + "\n")
            print("   已追加：语病避雷（写作时必守）+ 质量反哺")

    # 本章净变化 + 主角代价（红线 3 无后果 / 特质 3 选择有代价 的落点字段）
    net = section("本章净变化")
    if not net:
        spec += "\n## 本章净变化\n- 变化项：\n- 主角代价/取舍：\n"
    elif section_empty(net):
        replace_section("本章净变化", "- 变化项：\n- 主角代价/取舍：\n")

    # 章节定位（红线 10 节奏失衡 / 特质 7 张弛呼吸 的落点字段；checks.py 按最近 5 章查平衡）
    loc = section("章节定位")
    if not loc:
        spec += "\n## 章节定位\n- （铺垫 / 推进 / 高潮 / 收束，四选一，按大纲结构标记）\n"
    elif section_empty(loc):
        replace_section("章节定位", "- （铺垫 / 推进 / 高潮 / 收束，四选一，按大纲结构标记）\n")

    spec_path.write_text(spec, encoding="utf-8")
    return spec_path, False


def main() -> int:
    parser = argparse.ArgumentParser(description="组装章节蓝图（确定性部分自动填）")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--force", action="store_true",
                        help="spec 已填写时仍强制重组装（已填节仍有守卫，不覆盖判断项）")
    args = parser.parse_args()
    root = book_root(args)
    if root is None:
        print("❌ 不在项目中")
        return 1
    out, skipped = assemble(root, args.chapter, force=args.force)
    if skipped:
        return 0
    print(f"✅ spec 已组装：{out}")
    print("   已自动填：大纲要点/概念预算提示/角色要点/前情衔接/知情边界/时间线定位/伏笔指令/题材要点/风格指令/规则注入")
    print("   AI 只需补：概念取舍、本章故事时间推进、钩子设计等判断项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
