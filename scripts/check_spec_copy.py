#!/usr/bin/env python3
"""check_spec_copy.py — 细纲照搬检测（oh-story check-outline-copy 本地化轻量版）

检测正文 draft.md 是否把 spec.md 大纲要点/关键事件的句子逐字誊抄进正文
（连续重合 ≥15 字即判誊抄）。细纲是给作者的执行指令，正文照搬 = 写成
「成品散文的清单」，不是故事。

用法：
  check_spec_copy.py --project {书目录} --chapter N [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import find_project_root

MIN_OVERLAP = 15

OPEN_QUOTE = "「『“\"‘"
CLOSE_QUOTE = "」』”\"’"
# 专名单位词（地名/机构名后缀）：命中片段含其一才考虑专名豁免——纯名词性但
# 无单位词的短语（如「林默的妹妹的病房」）不豁免，宁报勿漏。
PROPER_NOUN_SUFFIX = re.compile(
    r"(医院|卫生院|诊所|中心|学校|学院|大学|中学|小学|幼儿园|大厦|广场|公园"
    r"|车站|地铁站|机场|家属院|家属区|等候区|小区|街道|社区|路|街|巷|弄"
    r"|馆|局|所|院|楼|堂|寺|庙|桥|村|镇|县|市|区|号楼|号院|店|厂|公司)"
)
# 常见动词（叙述句必含动词谓语；「等」不收——「等候区」是高频地名成分）
VERB_CHARS = set(
    "去来进出回走跑打杀死吃喝买卖开关坐站躺写读听想做用放收送"
    "追逃藏帮救抓推拉接问喊叫冲跳爬挖搬抬扛挤闯抢偷递扶拖拽按握挥踢撞摔躲数停发看说给带找拿"
)
VERB_WORDS = (
    "执行", "进行", "开始", "继续", "完成", "发现", "察觉", "观察", "确认",
    "决定", "准备", "安排", "通知", "提醒", "回复", "回答", "知道", "觉得",
    "感觉", "以为", "希望", "担心", "害怕", "来到", "到达", "回到", "进入",
    "离开", "通过", "穿过", "越过",
)


def spec_sentences(spec_text: str) -> list[str]:
    """从 spec 的「大纲要点」节提取条目句子（去勾选符与注解）。"""
    out = []
    in_block = False
    for line in spec_text.splitlines():
        s = line.strip()
        if s.startswith("## 大纲要点"):
            in_block = True
            continue
        if in_block and s.startswith("## "):
            break
        if in_block and s.startswith("-"):
            s = re.sub(r"^-\s*\[[ x]\]\s*", "", s)
            s = re.sub(r"（.*?）", "", s)  # 去括号注解（AI 可能照抄注解也算）
            s = s.strip()
            if len(s) >= MIN_OVERLAP:
                out.append(s)
    return out


def longest_common(text: str, sentence: str) -> str:
    """两个字符串的最长公共子串（小文本暴力即可）。"""
    best = ""
    for i in range(len(sentence) - MIN_OVERLAP + 1):
        for j in range(len(sentence), i + len(best), -1):
            if sentence[i:j] in text:
                best = sentence[i:j]
                break
    return best


def _is_quoted(text: str, start: int, end: int) -> bool:
    """命中片段是否为引号内原文（对话/短信原文与 spec 逐字一致是合法一致）。

    覆盖三种形态：① 片段整体被引号对包裹；② 引文独立成段（片段自带「…」，
    首尾是换行）；③ 片段带短引导前缀（如「发了条短信：」），引号主体占 ≥3/4。
    混合形态（引号+大段叙述）不豁免。
    """
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    if before in OPEN_QUOTE and after in CLOSE_QUOTE:
        return True
    frag = text[start:end]
    # lcs 的首/尾引号可能落在片段外一位（spec 与正文的引导语字数不同），并入再找完整引号对
    for cand in (before + frag, frag + after, frag):
        for oq, cq in (("「", "」"), ("『", "』"), ("“", "”"), ('"', '"')):
            i, j = cand.find(oq), cand.rfind(cq)
            if 0 <= i < j:
                lead = len(cand[:i]) + len(cand[j + 1:])
                if lead <= len(cand) * 0.25:
                    return True
    return False


def _is_proper_noun(frag: str) -> bool:
    """纯专名短语：无动词谓语的名词性短语（地名/机构名，如「城西第七人民医院
    家属等候区东侧」）。含专名单位词且不含常见动词才算——只缩命中面，不改阈值。"""
    if not PROPER_NOUN_SUFFIX.search(frag):
        return False
    if any(w in frag for w in VERB_WORDS):
        return False
    return not (VERB_CHARS & set(frag))


def _is_legitimate(text: str, frag: str) -> bool:
    """命中片段是否属合法一致（引号内原文 / 纯专名短语）：任一出现位置合法即豁免。"""
    if _is_proper_noun(frag):
        return True
    start = text.find(frag)
    while start != -1:
        if _is_quoted(text, start, start + len(frag)):
            return True
        start = text.find(frag, start + 1)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="细纲照搬检测")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中")
        return 1
    spec = root / f"chapters/chapter-{args.chapter:03d}/spec.md"
    draft = root / f"chapters/chapter-{args.chapter:03d}/draft.md"
    if not spec.exists() or not draft.exists():
        print("❌ spec 或 draft 不存在")
        return 1
    text = draft.read_text(encoding="utf-8")
    hits = []
    for sent in spec_sentences(spec.read_text(encoding="utf-8")):
        lcs = longest_common(text, sent)
        if len(lcs) < MIN_OVERLAP:
            continue
        if _is_legitimate(text, lcs):
            continue  # 引号内对话/短信原文、纯专名短语：与 spec 一致是必须的，不算照搬
        hits.append({"spec": sent, "copied": lcs})
    if args.json:
        print(json.dumps({"chapter": args.chapter, "hits": hits}, ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print(f"✓ 第 {args.chapter} 章无细纲照搬（正文与 spec 大纲要点无 ≥{MIN_OVERLAP} 字重合）")
        return 0
    print(f"⚠️ 第 {args.chapter} 章发现 {len(hits)} 处细纲照搬（spec 句子逐字出现在正文）：")
    for h in hits:
        print(f"  - spec「{h['spec'][:30]}…」→ 正文照搬「{h['copied']}」")
    print("  细纲是作者指令不是正文：把要点展开成场景/动作/对话，别逐字誊抄。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
