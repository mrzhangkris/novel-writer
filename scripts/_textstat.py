"""文本测量公共层：CJK 计数 / 句切分 / 量化基线实测。

此前 CJK 计数在 4 个脚本、句切分在 5 处、style-anchor 基线正则在 3 处各自实现
（同语义不同代码，改一处漏一处），统一收敛到这里。语义与原实现逐一对齐：
  - split_sentences 用 [。！？；\\n] 切分并丢弃句末标点（style_baseline /
    platform_review burstiness / writer_profile calibrate 同款）；
    style_profile 的保留标点切分（(?<=[。！？!?…])）语义不同，仍在该脚本本地。
"""

from __future__ import annotations

import re

CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# style-anchor / writer.md 量化基线行（「平均句长：约 18~25 字」，间隔符兼容 ~ - 到 至）
BASELINE_SENT_RE = r"平均句长：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*字"
BASELINE_DIALOG_RE = r"对话占比：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*%"
BASELINE_PARA_RE = r"段落中位长度：约\s*(\d+)\s*[-~到至]\s*(\d+)\s*行"


def cjk_len(text: str) -> int:
    return len(CJK_RE.findall(text))


def split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"[。！？；\n]", text) if s.strip()]


def baseline_range(text: str, pattern: str) -> tuple[int, int] | None:
    """从锚/档案文本解析一个「约 N~M」基线区间，返回 (min, max)。"""
    m = re.search(pattern, text)
    if not m:
        return None
    lo, hi = int(m.group(1)), int(m.group(2))
    return (min(lo, hi), max(lo, hi))


def measure_baseline(text: str) -> dict:
    """按 style-anchor / 写手档案同语义实测三项量化基线。"""
    cjk = cjk_len(text)
    lens = [cjk_len(s) for s in split_sentences(text)]
    avg_sent = sum(lens) / len(lens) if lens else 0.0
    quoted = sum(cjk_len(m) for m in re.findall(r"「[^」]*」", text))
    dialog_pct = quoted / cjk * 100 if cjk else 0.0
    paras = sorted(p.count("\n") + 1 for p in re.split(r"\n\s*\n", text) if p.strip())
    med_para = paras[len(paras) // 2] if paras else 0
    return {"avg_sent": avg_sent, "dialog_pct": dialog_pct, "med_para": med_para}
