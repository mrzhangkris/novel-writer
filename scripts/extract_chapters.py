#!/usr/bin/env python3
"""extract_chapters.py — 章节边界识别（story-long-analyze Stage 0 的确定性部分）

从拆书原文中识别章节标题行，产出章号序列与边界表，替代 AI 手工 regex 切片。
只做识别与落表，不替代 Stage 1 之后的任何分析判断。

能力（含 felixchaos/zh-chapter-splitter 移植项）：
- 编码自动识别：BOM 快路径 → utf-8 → gb18030 → gbk → big5（GBK 网文 txt 不再崩）
- 标题识别：`第{N}章/回`（阿拉伯/汉字/全角数字）、`Chapter {N}`、收紧数字标题
  （排除小数 3.14、年份 2024. 等误切）
- 番外/序章/作者注标注（非正文标题单独标记，不进章号序列）

用法：
  extract_chapters.py --input 原文.txt [--output _progress.md] [--json]
  默认把边界表追加写进 --output 指定的 _progress.md；--json 只打印结构不写盘。
"""

from __future__ import annotations

import argparse
import codecs
import json
import re
import sys
from pathlib import Path

DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
         "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# 全角数字与半角归一
FULLWIDTH_DIGIT = str.maketrans("０１２３４５６７８９", "0123456789")

# 番外/非正文标题关键词（标注但不入章号序列）
SIDESTORY_RE = re.compile(
    r"(番外|完本感言|上架感言|楔子|序章|序言|前言|后记|作者的话|请假条|更新说明)",
)


def decode_bytes(data: bytes) -> str:
    """编码自动识别链（zh-chapter-splitter 移植）：BOM 快路径 → utf-8 → gb18030 → gbk → big5。"""
    for bom, enc in ((codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
                     (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"),
                     (codecs.BOM_UTF8, "utf-8-sig")):
        if data.startswith(bom):
            return data.decode(enc, errors="ignore")
    for enc in ("utf-8", "gb18030", "gbk", "big5"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def read_text_auto(path: Path) -> str:
    return decode_bytes(path.read_bytes())


def cn_to_int(s: str) -> int:
    if s.isdigit():
        return int(s)
    section = 0
    number = 0
    for ch in s:
        if ch in DIGIT:
            number = DIGIT[ch]
        elif ch == "十":
            section += (number if number else 1) * 10
            number = 0
        elif ch == "百":
            section += number * 100
            number = 0
        elif ch == "千":
            section += number * 1000
            number = 0
    return section + number


CHAPTER_RE = re.compile(
    r"^\s*(?:第\s*([0-9０-９]+|[零〇一二两三四五六七八九十百千]+)\s*[章回](?:\s+.{0,38})?$"
    r"|Chapter\s+([0-9]+)(?:\s+.{0,38})?$"
    r"|([0-9０-９]{1,3})\s*[、.．](?![0-9０-９])\s*\S.{0,38})$",
    re.IGNORECASE,
)


def parse_chapter_no(s: str) -> int | None:
    s = s.strip().translate(FULLWIDTH_DIGIT)
    if not s:
        return None
    if re.fullmatch(r"[0-9]+", s):
        return int(s)
    if re.fullmatch(rf"[{''.join(DIGIT)}十百千]+", s):
        return cn_to_int(s)
    return None


def scan(text: str) -> list[dict]:
    """返回 [{chapter, line, title, sidestory}]"""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if len(stripped) > 40:
            continue
        is_sidestory = bool(SIDESTORY_RE.search(stripped))
        m = CHAPTER_RE.match(stripped)
        if not m:
            continue
        n = None
        for grp in m.groups():
            if grp is not None:
                n = parse_chapter_no(grp)
                break
        if n is None:
            continue
        out.append({"chapter": n, "line": lineno, "title": stripped, "sidestory": is_sidestory})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="章节边界识别")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=None, help="_progress.md 路径（追加边界表）")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        text = read_text_auto(args.input)
    except OSError as exc:
        print(f"❌ 无法读取原文：{exc}")
        return 1
    entries = scan(text)
    if not entries:
        print("❌ 未识别到任何章节标题（支持：第N章/第N回/Chapter N/数字标题）")
        return 1

    # 番外/序章等非正文标题单独列出，不进章号序列
    main = [e for e in entries if not e["sidestory"]]
    side = [e for e in entries if e["sidestory"]]
    nums = [e["chapter"] for e in main]
    dup = sorted({n for n in nums if nums.count(n) > 1})

    payload = {
        "chapters": [{"chapter": e["chapter"], "line": e["line"], "title": e["title"]} for e in main],
        "sidestory": [{"line": e["line"], "title": e["title"]} for e in side],
        "count": len(main),
        "duplicates": dup,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"✓ 识别到 {len(main)} 章" + (f"（另有 {len(side)} 个番外/序章/作者注标题）" if side else ""))
    if dup:
        print(f"⚠️ 章号重复：{dup}（需人工核对后删重）")
    # 连续性检查（允许序章/番外打断，仅提示）
    seq = sorted(set(nums))
    gaps = [i for i in range(seq[0], seq[-1] + 1) if i not in set(nums)]
    if gaps:
        print(f"⚠️ 章号缺口：{gaps}（可能有序章/番外/脱漏，需人工核对）")

    if args.output:
        out = args.output
        block = ["", "## 章节边界（extract_chapters.py 生成，Stage 1/2/6 唯一切片真值）", ""]
        block.append("| 章号 | 起始行 | 标题 |")
        block.append("|---|---|---|")
        for e in main:
            block.append(f"| {e['chapter']} | {e['line']} | {e['title']} |")
        if side:
            block.append("")
            block.append("非正文标题（不入章号序列）：")
            for e in side:
                block.append(f"- 第{e['line']}行：{e['title']}")
        block.append("")
        if out.exists():
            existing = out.read_text(encoding="utf-8")
            marker = "## 章节边界（extract_chapters.py"
            if marker in existing:
                # 只替换旧边界块（marker 到下一个 ## 节之间），其余节保留
                head = existing.split(marker)[0]
                tail = existing[len(head) + len(marker):]
                next_section = tail.find("\n## ", 1)
                rest = tail[next_section + 1:] if next_section >= 0 else ""
                with open(out, "w", encoding="utf-8") as f:
                    f.write(head.rstrip("\n") + "\n" + "\n".join(block) + ("\n" + rest.lstrip("\n") if rest else ""))
                print(f"✓ 边界表已更新（仅替换边界块）：{out}")
                return 0
        with open(out, "w" if not out.exists() else "a", encoding="utf-8") as f:
            f.write("\n".join(block))
        print(f"✓ 边界表已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
