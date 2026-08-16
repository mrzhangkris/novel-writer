#!/usr/bin/env python3
"""check_engine.py — 通用规则检查引擎（与领域无关）

「通用引擎 + 领域数据」分层：本文件只实现规则的解释执行，
**不含任何领域内容**（没有写作词表、没有安全规则）。
领域技能在 `references/check-rules/*.json` 提供数据，引擎按声明跑；
换一个领域（如安全审查）只需喂另一套 JSON，引擎一行不改。

规则 JSON 格式（完整说明见 references/architecture.md 第三节）：

1. presence（advisory，只提示不拦截，返回 0）
   {"type": "pair",      "wrong": "…", "right": "…", "hint": "…{wrong}…{right}…"}
   {"type": "regex",     "pattern": "…", "hint": "…{g0}…{g1}…", "sample_context": N}
   {"type": "wordlist",  "words": ["…"], "hint": "…{word}…"}
2. count_threshold（信号词计数 + 阈值：hits>=block 拦截返回 1，hits>=warn 警告返回 0）
   {"type": "count_threshold", "patterns": ["…"], "warn": N, "block": M,
    "warn_hint": "…{hits}…{samples}…", "block_hint": "…{hits}…{samples}…",
    "sample_context": K, "max_samples": S}

hint 占位符：{g0}=整段命中，{g1..gn}=正则捕获组，{wrong}/{right}/{word}/{hits}/{samples}。
用法：
  from check_engine import load_rules, run_rules, run_count_rule
  run_rules(text, load_rules("typo-rules"))          # presence 类，advisory
  return run_count_rule(text, load_rules("sermon-rules"))  # 阈值类，可拦截
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# 规则数据目录：本文件上一级的 references/check-rules/（引擎自定位，不硬编码绝对路径）
RULES_DIR = Path(__file__).resolve().parent.parent / "references" / "check-rules"


def load_rules(name: str) -> dict:
    """按名加载规则 JSON（如 "typo-rules" → check-rules/typo-rules.json）。

    返回 (rules, ok)：ok=False 表示拦截级规则缺失/损坏——调用方必须按失败处理，
    不得把「没检查」当「通过」。
    """
    p = RULES_DIR / f"{name}.json"
    if not p.exists():
        print(f"✗ 规则文件不存在：{p}——该检查按失败处理（fail-closed）")
        return {}, False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"✗ 规则文件损坏：{p}（{e}）——该检查按失败处理（fail-closed）")
        return {}, False
    if not isinstance(data, dict):
        print(f"✗ 规则文件格式错误：{p}——该检查按失败处理（fail-closed）")
        return {}, False
    return data, True


def _fmt(hint: str, m: re.Match | None = None, **extra: str) -> str:
    """hint 占位符替换：{g0}/{g1..gn} 来自正则匹配，其余来自 extra 键值。"""
    data: dict[str, str] = dict(extra)
    if m is not None:
        data["g0"] = m.group(0)
        for i in range(1, len(m.groups()) + 1):
            data[f"g{i}"] = m.group(i) or ""
    try:
        return hint.format(**data)
    except (KeyError, IndexError, AttributeError):
        return hint


def run_rules(text: str, rules: dict) -> int:
    """执行 presence 类规则（pair / regex / wordlist），全部 advisory，返回 0。"""
    for r in rules.get("rules", []):
        t = r.get("type")
        if t == "pair":
            wrong = r.get("wrong", "")
            if wrong and wrong in text:
                print("⚠️  " + _fmt(r.get("hint", ""), wrong=wrong, right=r.get("right", "")))
        elif t == "regex":
            pat = re.compile(r.get("pattern", ""))
            # 上下文宽度：条目级优先，回退文件级 sample_context，再回退 0
            ctx = r.get("sample_context", rules.get("sample_context", 0))
            for m in pat.finditer(text):
                hint = _fmt(r.get("hint", ""), m)
                if ctx:
                    start = max(0, m.start() - ctx)
                    hint += f" —— …{text[start:m.end() + ctx]}…"
                print("⚠️  " + hint)
        elif t == "wordlist":
            for w in r.get("words", []):
                if w in text:
                    print("⚠️  " + _fmt(r.get("hint", ""), word=w))
    return 0


def run_count_rule(text: str, rule: dict) -> int:
    """执行 count_threshold 类：hits>=block 拦截(1)，hits>=warn 警告(0)，否则静默(0)。"""
    if rule.get("type") != "count_threshold":
        return 0
    hits = 0
    samples: list[str] = []
    ctx = rule.get("sample_context", 8)
    max_samples = rule.get("max_samples", 3)
    for pat in rule.get("patterns", []):
        for m in re.finditer(pat, text):
            hits += 1
            if len(samples) < max_samples:
                start = max(0, m.start() - ctx)
                samples.append(f"…{text[start:m.end() + ctx]}…")
    if hits < rule.get("warn", 1):
        return 0
    detail = "；".join(samples)
    if hits >= rule.get("block", 0):
        print("❌ " + _fmt(rule.get("block_hint", ""), hits=hits, samples=detail))
        return 1
    print("⚠️  " + _fmt(rule.get("warn_hint", ""), hits=hits, samples=detail))
    return 0
