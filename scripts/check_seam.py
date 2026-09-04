#!/usr/bin/env python3
"""check_seam.py — 跨章拼接断裂检测（seam-check，纯文本零 LLM）

双窗对账：前章末 3 段 vs 后章首 3 段（单窗 ≤600 字符，尾窗截尾/首窗截头；
全文无换行退化为头/尾各 300；整行章标题「第X章」且 ≤16 字跳过再取窗），
提取四维指纹：

  地点  方位短语「X里/X中/X上/X内」的名词核心 + 场景词表兜底
  人物  tracking/characters/*.md 文件名（角色名）；目录缺失则该维跳过
  道具  tracking/ledger.md「## 道具」节条目名；缺失则该维跳过
  时间  窗口内「第N天」最大序数（中文数字支持到百）

判定（宁缺毋滥；词表法有噪声，advisory 交人工终判）：
  地点/人物/道具  双侧非空且无交集 → ⚠️ seam-conflict；任一侧空 → 不判
  时间            后章首窗天数 − 前章尾窗天数 ≥ 3 → ⚠️ 时间跳跃
  降级            地点突变 + 后章首窗含时间跳跃词（次日/X天后/入夜…）→
                  seam-conflict 从 med 降为 info（疑似有意转场，M3 八章实测降噪）
  仅相邻章（章号差 = 1）对账；只读两章窗口文本，禁止全本扫描。

用法：
  check_seam.py --project {书目录} [--chapter N] [--json]
  无 --chapter 时自动对账最近两章。退出码恒 0（advisory 不拦门禁）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ── 参数（liyu seamChecker 实证值）─────────────────────────────────
PARA_WINDOW = 3           # 各取末/首 N 段
MAX_WINDOW_CHARS = 600    # 单窗字符上限（尾窗截尾 / 首窗截头）
FALLBACK_CHARS = 300      # 全文无换行时退化：头/尾各 300
TITLE_MAX_LEN = 16        # 章标题行长度上限（超过视为正文）
TIME_JUMP_DAYS = 3        # 天数差 ≥ 3 → 时间跳跃 warning

TITLE_RE = re.compile(r"^第[\d零一二两三四五六七八九十百]+章")
LOC_SUFFIX_RE = re.compile(r"([\u4e00-\u9fff]{2,4})(里|中|上|内|下)")
DAY_RE = re.compile(r"第([\d零一二两三四五六七八九十百]+)天")

# 时间跳跃词白名单（M3 八章连载实测：seam-conflict 8 章误报 6+ 次全是「有意转场」，
# 人工复核疲劳）。后章首窗出现时间跳跃词且地点突变共现时，该条从 med 降为 info
# 并标注「疑似有意转场」——时间跳跃天然伴随场景切换，是转场的强信号；
# 无时间跳跃词的地点突变仍保持 med 原判（未知情况不降级）。
TIME_JUMP_WORDS_RE = re.compile(
    r"次日|翌日|第二天|[一二两三四五六七八九十百半数几\d]+(?:天|日)后"
    r"|当晚|入夜|清晨|黄昏|拂晓|翌晨"
)

# 方位短语核心的尾字黑名单：身体部位/抽象/时间词，压词面噪声（宁缺毋滥）。
# 注意：核心 ≥2 字已天然滤掉「马上/地上/心里」等单字惯用语。
LOC_CORE_BAD_TAILS = set(
    "心眼嘴口手脸脑耳梦话信身脚腿头齿背肩腰发光神意声气忆闻"
    "间程事群伍夜昼其此当之彼书报剧歌曲诗文画图影音钟表账债"
    "局面行列期届轮番份则条项档卷页册幕"
)

# 场景词表兜底（古今通用 ≥2 字词，单字「塔/桥」噪声高不收）
SCENE_WORDS = (
    "会议室", "大厅", "大殿", "厨房", "卧室", "山洞", "城门", "街道", "客栈",
    "营地", "广场", "书房", "院子", "客厅", "走廊", "地下室", "屋顶", "码头",
    "集市", "酒馆", "茶馆", "店铺", "医院", "寺庙", "祠堂", "皇宫", "宫殿",
    "军营", "山谷", "悬崖", "草原", "墓地", "牢房", "船舱", "甲板", "马厩",
    "矿洞", "隧道", "城墙", "教室", "车间", "病房", "河边",
)

_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_to_int(s: str) -> int | None:
    """中文/阿拉伯数字 → int（支持到百，含「两」）；解析失败返回 None。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    total, num = 0, 0
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
        elif ch == "十":
            total += (num or 1) * 10
            num = 0
        elif ch == "百":
            total += (num or 1) * 100
            num = 0
        else:
            return None
    return total + num


# ── 双窗提取 ────────────────────────────────────────────────────────
def strip_annotations(text: str) -> str:
    """剥 HTML 注释：<!-- --> 是给 AI 的标注不是读者内容，不参与指纹。"""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def is_title_line(line: str) -> bool:
    return len(line) <= TITLE_MAX_LEN and bool(TITLE_RE.match(line))


def make_window(text: str, side: str) -> str:
    """side='tail' 取末窗（末 3 段，超长截尾）；side='head' 取首窗（首 3 段，超长截头）。"""
    if "\n" not in text:  # 无换行分隔 → 退化为头/尾各 300
        return text[-FALLBACK_CHARS:] if side == "tail" else text[:FALLBACK_CHARS]
    paras = [ln.strip() for ln in text.splitlines()]
    paras = [p for p in paras if p and not is_title_line(p)]  # 跳过章标题行再取窗
    picked = paras[-PARA_WINDOW:] if side == "tail" else paras[:PARA_WINDOW]
    window = "\n".join(picked)
    return window[-MAX_WINDOW_CHARS:] if side == "tail" else window[:MAX_WINDOW_CHARS]


# ── 四维指纹 ────────────────────────────────────────────────────────
def _norm_core(core: str) -> str:
    """核心词归一：剥前导虚词/指示词（在这条街→条街），提升跨章字面差异下的交集率。"""
    for lead in ("在", "这", "那", "从", "到", "了", "把", "的"):
        while core.startswith(lead):
            core = core[len(lead):]
    return core


def extract_locations(window: str) -> set[str]:
    locs: set[str] = set()
    for core, _suffix in LOC_SUFFIX_RE.findall(window):
        core = _norm_core(core)
        if len(core) >= 2 and core[-1] not in LOC_CORE_BAD_TAILS:  # 归一后仍需 ≥2 字
            locs.add(core)
    for word in SCENE_WORDS:
        if word in window:
            locs.add(word)
    return locs


def extract_max_day(window: str) -> int | None:
    days = [d for d in (cn_to_int(s) for s in DAY_RE.findall(window)) if d is not None]
    return max(days) if days else None


def load_character_names(project: Path) -> tuple[list[str], str | None]:
    """角色名 = tracking/characters/*.md 文件名（stem）。目录缺失 → 降级说明。"""
    d = project / "tracking" / "characters"
    if not d.is_dir():
        return [], "人物维跳过：tracking/characters/ 不存在（未登记角色，无法对账）"
    names = sorted(p.stem for p in d.glob("*.md")
                   if not p.name.startswith(".") and len(p.stem) >= 2)
    return names, None


def load_item_names(project: Path) -> tuple[list[str], str | None]:
    """道具名 = tracking/ledger.md「## 道具」节条目名。缺失 → 降级说明。"""
    f = project / "tracking" / "ledger.md"
    if not f.exists():
        return [], "道具维跳过：tracking/ledger.md 不存在（未建道具台账，无法对账）"
    m = re.search(
        r"^## 道具[^\n]*\n(.*?)(?=^## |\Z)",
        f.read_text(encoding="utf-8"),
        flags=re.DOTALL | re.MULTILINE,
    )
    if not m:
        return [], "道具维跳过：ledger.md 无「## 道具」节"
    names = []
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if not ln.startswith("-"):
            continue
        name = ln.lstrip("-").strip().split("｜")[0].strip()
        if name and name != "（暂无）" and len(name) >= 2:
            names.append(name)
    return names, None


def relates(a: set[str], b: set[str]) -> bool:
    """模糊交集：子串包含即算关联（「议事大厅」vs「大厅」不误报）。"""
    return any(x in y or y in x for x in a for y in b)


# ── 章节定位 ────────────────────────────────────────────────────────
def draft_path(project: Path, n: int) -> Path:
    return project / "chapters" / f"chapter-{n:03d}" / "draft.md"


def latest_chapter(project: Path) -> int | None:
    chapters = project / "chapters"
    if not chapters.is_dir():
        return None
    nums = [
        int(m.group(1))
        for d in chapters.glob("chapter-*")
        if (m := re.fullmatch(r"chapter-(\d{3,})", d.name))
        and d.is_dir() and (d / "draft.md").exists()
    ]
    return max(nums) if nums else None


# ── 对账主流程 ──────────────────────────────────────────────────────
def run(project: Path, chapter: int | None, as_json: bool) -> int:
    if chapter is None:
        chapter = latest_chapter(project)
        if chapter is None:
            msg = "seam 跳过：chapters/ 下无 chapter-NNN/draft.md"
            print(json.dumps({"warnings": [], "degraded": [msg]}, ensure_ascii=False)) if as_json else print(msg)
            return 0
    prev_no = chapter - 1
    if prev_no < 1:
        msg = f"seam 跳过：第 {chapter} 章是首章，无前章可对账"
        print(json.dumps({"warnings": [], "degraded": [msg]}, ensure_ascii=False)) if as_json else print(msg)
        return 0
    prev_file, curr_file = draft_path(project, prev_no), draft_path(project, chapter)
    missing = prev_file if not prev_file.exists() else None
    missing = missing or (curr_file if not curr_file.exists() else None)
    if missing:
        msg = f"seam 跳过：缺少 {missing}，只对账相邻章（章号差=1）"
        print(json.dumps({"warnings": [], "degraded": [msg]}, ensure_ascii=False)) if as_json else print(msg)
        return 0

    prev_text = strip_annotations(prev_file.read_text(encoding="utf-8"))
    curr_text = strip_annotations(curr_file.read_text(encoding="utf-8"))
    tail_win = make_window(prev_text, "tail")
    head_win = make_window(curr_text, "head")

    char_names, char_note = load_character_names(project)
    item_names, item_note = load_item_names(project)
    degraded = [n for n in (char_note, item_note) if n]

    prev_loc, curr_loc = extract_locations(tail_win), extract_locations(head_win)
    prev_char = {n for n in char_names if n in tail_win}
    curr_char = {n for n in char_names if n in head_win}
    prev_item = {n for n in item_names if n in tail_win}
    curr_item = {n for n in item_names if n in head_win}
    prev_day, curr_day = extract_max_day(tail_win), extract_max_day(head_win)

    warnings: list[dict] = []

    def judge_dim(dim: str, label: str, prev: set[str], curr: set[str],
                  transitional: bool = False) -> str:
        if not prev or not curr:
            return "unknown"
        if relates(prev, curr):
            return "ok"
        if transitional:
            # 时间跳跃词共现：疑似有意转场，降级 info 提示复核，不再按 med 催人工
            warnings.append({
                "dim": dim,
                "type": "seam-conflict",
                "severity": "info",
                "message": (
                    f"seam-conflict（{label}）：前章尾窗「{'、'.join(sorted(prev))}」 vs "
                    f"后章首窗「{'、'.join(sorted(curr))}」——{label}突变，"
                    "但首窗含时间跳跃词，疑似有意转场（词表法有噪声，可放行）"
                ),
            })
            return "conflict"
        warnings.append({
            "dim": dim,
            "type": "seam-conflict",
            "severity": "med",
            "message": (
                f"seam-conflict（{label}）：前章尾窗「{'、'.join(sorted(prev))}」 vs "
                f"后章首窗「{'、'.join(sorted(curr))}」——{label}突变，请人工复核"
                "（词表法有噪声，有意转场可放行）"
            ),
        })
        return "conflict"

    # 时间跳跃白名单只作用于地点维：地点突变 + 首窗时间跳跃词 = 疑似有意转场。
    time_jump_word = bool(TIME_JUMP_WORDS_RE.search(head_win))
    verdicts = {
        "location": judge_dim("location", "地点", prev_loc, curr_loc, time_jump_word),
        "characters": judge_dim("characters", "人物", prev_char, curr_char),
        "items": judge_dim("items", "道具", prev_item, curr_item),
    }
    if prev_day is not None and curr_day is not None:
        time_verdict = "jump" if curr_day - prev_day >= TIME_JUMP_DAYS else "ok"
        if time_verdict == "jump":
            warnings.append({
                "dim": "time",
                "type": "time-jump",
                "severity": "med",
                "message": (
                    f"时间跳跃：前章尾窗最远「第{prev_day}天」 → 后章首窗最远「第{curr_day}天」"
                    f"（相差 {curr_day - prev_day} 天）——若为有意跳时请忽略"
                ),
            })
    else:
        time_verdict = "unknown"

    if as_json:
        print(json.dumps({
            "prev_chapter": prev_no,
            "curr_chapter": chapter,
            "prev_window_chars": len(tail_win),
            "curr_window_chars": len(head_win),
            "dimensions": {
                "location": {"prev": sorted(prev_loc), "curr": sorted(curr_loc), "verdict": verdicts["location"]},
                "characters": {"prev": sorted(prev_char), "curr": sorted(curr_char), "verdict": verdicts["characters"]},
                "items": {"prev": sorted(prev_item), "curr": sorted(curr_item), "verdict": verdicts["items"]},
                "time": {"prev_day": prev_day, "curr_day": curr_day, "verdict": time_verdict},
            },
            "warnings": warnings,
            "degraded": degraded,
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"seam 对账：chapter-{prev_no:03d} → chapter-{chapter:03d}（尾窗 {len(tail_win)} 字 / 首窗 {len(head_win)} 字）")
    for note in degraded:
        print(f"（{note}）")
    for w in warnings:
        print(f"⚠️  [{w.get('severity', 'med')}][seam] {w['message']}")
    if not warnings:
        print("✅ seam 通过：相邻章拼接无断裂（证据不足的维度不判）")
    return 0  # advisory：恒 0，不拦门禁


def main() -> int:
    ap = argparse.ArgumentParser(description="跨章拼接断裂检测（advisory，退出码恒 0）")
    ap.add_argument("--project", required=True, help="书目录（含 .story/ 的项目根）")
    ap.add_argument("--chapter", type=int, default=None, help="后章章号（默认对账最近两章）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()
    project = Path(args.project)
    if not (project / ".story").exists():
        msg = f"seam 跳过：{project} 下无 .story/（不是项目根）"
        print(json.dumps({"warnings": [], "degraded": [msg]}, ensure_ascii=False)) if args.json else print(msg)
        return 0
    return run(project, args.chapter, args.json)


if __name__ == "__main__":
    sys.exit(main())
