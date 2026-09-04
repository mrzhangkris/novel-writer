"""novel-writer 脚本公共层：项目根定位与 JSON 读写。

本技能所有脚本共用的基础函数。各脚本以薄壳方式调用：
    from _common import find_project_root, read_json, write_json

约定：项目根 = 向上最近的包含 .story/ 的目录（或 .story/pipeline.json）。
"""

from __future__ import annotations

import json
from pathlib import Path

STORY_DIR = ".story"
PIPELINE_FILE = ".story/pipeline.json"
TREND_FILE = ".story/quality-trend.json"
MEMORY_FILE = ".story/project_memory.json"
# 检查豁免清单（人工复核确认的假冲突挂账；写入方 checks.py exempt，消费方各比对类检查）
EXEMPTIONS_FILE = ".story/exemptions.json"


def find_project_root(start: Path, child: str = STORY_DIR) -> Path | None:
    """从 start 向上找包含 child（相对路径，可为目录或文件）的目录。"""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / child).exists():
            return cur
        cur = cur.parent
    return None


def read_json(path: Path, default: object = None) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
