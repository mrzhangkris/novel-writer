#!/usr/bin/env python3
"""assemble_spec.py — 章节蓝图组装器（把确定性组装从 AI 手里接过来）

读 tracking 账本 + outline + 题材卡 + 文风锚，把 spec.md 的确定性部分
自动填好：大纲要点、概念预算提示、角色要点、前情衔接、知情边界、
时间线定位、伏笔指令、题材要点、风格指令。AI 只补判断项（概念取舍、
本章时间推进、钩子设计），不再手工抄文件——抄写是 AI 出错的重灾区。

用法：
  assemble_spec.py --chapter N [--project 书目录]
  （先 new_chapter.py --chapter N 建模板，再跑本脚本填内容）

只填充空位：已写内容（含 AI 之前的创作）不被覆盖。
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import PIPELINE_FILE, find_project_root, read_json

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


def author_root(root: Path) -> Path | None:
    cur = root
    while cur != cur.parent:
        if (cur / ".novel").is_dir():
            return cur
        cur = cur.parent
    return None


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
    """兼容账本两种表结构（ID 可能 F01 或 F001、列数 5-7）。

    planted/planned 保留原字符串（gen_transaction 用）；*_no 是 int（check_continuity 用）。
    """
    rows = []
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5 or not re.fullmatch(r"F\d{1,4}", cells[0]):
            continue
        def num(s):
            mm = re.search(r"\d+", s)
            return int(mm.group()) if mm else 0
        rows.append({
            "id": cells[0], "summary": cells[1],
            "planted": cells[2], "planned": cells[3], "status": cells[4],
            "importance": cells[5] if len(cells) > 5 else "中",
            "planted_no": num(cells[2]), "planned_no": num(cells[3]),
        })
    return rows


def chapter_in(text: str, chapter: int) -> bool:
    return bool(re.search(rf"第\s*{chapter}\s*章", text))


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


def style_lines(root: Path) -> list[str]:
    anchor = read_text(root / ".novel" / "style-anchor.md")
    lines = []
    for line in anchor.splitlines():
        if "____" in line or "（第一/第三）" in line or "单视角 / 多视角" in line or line.startswith("{如"):
            continue
        m = re.match(r"-\s*(人称|视角纪律)[：:]\s*(.*)", line)
        if m:
            lines.append(f"- {m.group(1)}：{m.group(2).strip()}")
    in_banned = False
    for line in anchor.splitlines():
        if "____" in line or line.startswith("{如"):
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
    # 语病避雷（写作时必守，前置约束；checks 语病模式扫描兜底。清单 ≤8 条，
    # 全部「症状→正解」格式且可 grep 二值验证——约束越多模型越无视，不堆禁令）
    lines.append("## 语病避雷（写作时必守，写完自校）")
    lines.extend([
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
    ])
    return lines


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


def foreshadow_lines(root: Path, chapter: int, outline_plants: list[str]) -> list[str]:
    rows = parse_foreshadow_table(read_text(root / "tracking" / "foreshadows.md"))
    lines = []
    closed = []
    for row in rows:
        if row["status"] == "已埋":
            if chapter_in(row["planned"], chapter):
                lines.append(f"- 回收 {row['id']}：{row['summary'][:40]}（计划回收 {row['planned']}）")
            elif chapter_in(row["planned"], chapter + 1) or chapter_in(row["planned"], chapter + 2):
                lines.append(f"- 推进 {row['id']}：临近回收（{row['planned']}），本章为回收铺垫")
        elif row["status"] == "推进":
            lines.append(f"- 继续推进 {row['id']}：{row['summary'][:40]}（引信已落地，本章保持可见或再推进一步，计划回收 {row['planned']}）")
        elif row["status"] in ("已回收", "已过期", "放弃"):
            closed.append(f"{row['id']}（{row['summary'][:30]}）")
    lines.extend(outline_plants)
    # 反向提示：已回收/已过期/放弃的悬念严禁重复写——长篇隔几十章后重提已揭晓悬念是高频吃书点。
    # 上限 20 条：数百条全列会稀释关键信息；超出时只列最近 20 条（按编号最大优先）。
    if closed:
        shown = closed[-20:]
        suffix = f"（共 {len(closed)} 条，仅列最近 {len(shown)} 条）" if len(closed) > 20 else ""
        lines.append(f"- ⛔ 已了结，本章严禁重复写或再当悬念用{suffix}：{'、'.join(shown)}")
    return lines


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


def assemble(root: Path, chapter: int) -> str:
    spec_path = root / SPEC_DIR_TMPL.format(chapter=chapter) / "spec.md"
    if not spec_path.exists():
        print(f"❌ spec 不存在：{spec_path}（先跑 new_chapter.py --chapter {chapter}）")
        raise SystemExit(1)
    spec = read_text(spec_path)

    outline = read_text(root / "outline.md")
    fields = parse_outline_chapter(outline, chapter)
    budget = parse_concept_budget(outline, chapter)
    plants = parse_outline_foreshadows(outline, chapter)
    ctx = parse_context(root)
    known, unknown = parse_timeline(root)
    chars = active_characters(root)
    author = author_root(root)
    style = style_lines(author) if author else []
    hooks = card_hook_lines(root)
    fores = foreshadow_lines(root, chapter, plants)

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

    # 大纲要点：只填空位
    checklist = section("大纲要点")
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
        replace_section("伏笔指令", ("\n".join(fores) + "\n") if fores else "- 本章无伏笔动作\n")

    # 题材要点
    tp = section("题材要点")
    if hooks and section_empty(tp):
        replace_section("题材要点", "（题材卡「章尾钩子」节，按本章择用）\n" + "\n".join(hooks) + "\n")

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

    # 风格指令
    st = section("风格指令")
    if section_empty(st):
        style += playbook_reminders(root)
        replace_section("风格指令", "\n".join(style) + "\n")
    elif "语病避雷" not in st and "## 语病避雷" not in spec:
        # 已组装的 spec：追加语病避雷节（含质量反哺），不覆盖 AI 填过的内容。
        # 双重防重：风格指令节内与全 spec 任一位置已有该节都不再追加
        #（历史上 replace 目标不匹配会静默失败 → 每次重跑堆积一份）
        # 与主路径同源：读作者级 style-anchor（root 参数是历史误用，书根无 .novel/）
        avoid = style_lines(author) if author else []
        if "## 语病避雷（写作时必守，写完自校）" in avoid:
            avoid = [l for l in avoid if l.startswith("## ") or l.startswith("- ")]
            block = "\n".join(l for l in avoid[avoid.index("## 语病避雷（写作时必守，写完自校）"):])
        else:
            block = ""
        extra = [l for l in style if l.startswith("- （质量反哺）")]
        if extra:
            block += "\n" + "\n".join(extra)
        if block.strip() and ("## 风格指令\n" + st) in spec:
            spec = spec.replace("## 风格指令\n" + st, "## 风格指令\n" + st.rstrip("\n") + "\n\n" + block + "\n")
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
    return spec_path


def main() -> int:
    parser = argparse.ArgumentParser(description="组装章节蓝图（确定性部分自动填）")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--project", type=Path, default=None)
    args = parser.parse_args()
    root = book_root(args)
    if root is None:
        print("❌ 不在项目中")
        return 1
    out = assemble(root, args.chapter)
    print(f"✅ spec 已组装：{out}")
    print("   已自动填：大纲要点/概念预算提示/角色要点/前情衔接/知情边界/时间线定位/伏笔指令/题材要点/风格指令/规则注入")
    print("   AI 只需补：概念取舍、本章故事时间推进、钩子设计等判断项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
