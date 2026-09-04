#!/usr/bin/env python3
"""quality_trend.py — 冷读质量趋势（每章四维分数的落盘与查看）

冷读裁判的四维分数（翻页欲/认知负荷/共情验证/节奏感受）写入
.story/quality-trend.json，pipeline status 显示最近 5 章均值与趋势，
防止「每章都放水通过」被淹没在流程里。

用法：
  quality_trend.py record --project <书目录> --scores 4,4,5,4 [--note 备注]
  quality_trend.py show   --project <书目录>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _common import TREND_FILE, find_project_root

DIMENSIONS = ("翻页欲", "认知负荷", "共情验证", "节奏感受")




def load_trend(root: Path) -> dict:
    p = root / TREND_FILE
    if not p.exists():
        return {"chapters": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("chapters"), list):
            data["chapters"] = []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"❌ 趋势文件损坏（{exc}）：先备份 .story/quality-trend.json 再重跑，勿让损坏数据被覆盖")
        raise SystemExit(1)


def _root_of(args: argparse.Namespace) -> Path | None:
    start = Path(args.project) if args.project else Path.cwd()
    return find_project_root(start, child=".story")


def save_trend(root: Path, data: dict) -> None:
    p = root / TREND_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_record(args: argparse.Namespace) -> int:
    root = _root_of(args)
    if root is None:
        print("❌ 不在项目中（找不到 .story/）")
        return 1
    parts = [s.strip() for s in args.scores.split(",")]
    if len(parts) != 4:
        print("❌ --scores 需要 4 个分数（翻页欲,认知负荷,共情验证,节奏感受）")
        return 1
    try:
        scores = [int(p) for p in parts]
    except ValueError:
        print("❌ 分数必须是整数")
        return 1
    if any(not (1 <= s <= 5) for s in scores):
        print("❌ 分数必须在 1-5 之间")
        return 1
    # 章节号：显式 --chapter 优先，否则取 pipeline.json（若有）
    chapter = args.chapter
    if chapter is None:
        pipe_file = root / ".story" / "pipeline.json"
        if pipe_file.exists():
            try:
                chapter = json.loads(pipe_file.read_text(encoding="utf-8")).get("chapter")
            except (json.JSONDecodeError, OSError):
                chapter = None
    data = load_trend(root)
    # 按章去重：重跑 finish 时同章覆盖，不重复记账污染近 5 章均分
    data["chapters"] = [c for c in data["chapters"] if c.get("chapter") != chapter]
    data["chapters"].append(
        {
            "chapter": chapter,
            "scores": scores,
            # 均分统一「越高越好」：认知负荷（第 2 维）越低越好，取反后参与平均
            "avg": round((sum(scores) - scores[1] + (6 - scores[1])) / len(scores), 2),
            "note": args.note or "",
        }
    )
    save_trend(root, data)
    print(f"✅ 已记录第 {chapter} 章冷读分数：{'/'.join(parts)}（均分 {data['chapters'][-1]['avg']}）")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    root = _root_of(args)
    if root is None:
        print("❌ 不在项目中（找不到 .story/）")
        return 1
    data = load_trend(root)
    chapters = data["chapters"]
    if not chapters:
        print("📭 暂无冷读分数记录（写章后跑 quality_trend.py record）")
        return 0
    recent = chapters[-5:]
    print(f"📊 冷读质量趋势（共 {len(chapters)} 章，显示最近 {len(recent)} 章）：")
    for item in recent:
        ch = item.get("chapter")
        ch_s = f"第{ch}章" if ch else "—"
        dims = " | ".join(f"{d}={s}" for d, s in zip(DIMENSIONS, item["scores"]))
        print(f"   {ch_s}  均分 {item['avg']}  （{dims}）")
    avgs = [c["avg"] for c in recent]
    overall = round(sum(avgs) / len(avgs), 2)
    flag = ""
    if overall < 3.5:
        flag = "🔴 近章质量偏低，建议回头 revise"
    elif overall < 4.0:
        flag = "🟠 近章质量一般，留意冷读低分项"
    else:
        flag = "🟢 近章质量稳定"
    print(f"   近 {len(recent)} 章总均分：{overall} {flag}")
    # 全量质量债曝光：低分章/平庸章清单（防「全通过但平庸」被均分掩盖）
    low = [c for c in chapters if c.get("avg", 5) < 4.0]
    mid = [c for c in chapters if 4.0 <= c.get("avg", 5) < 4.5]
    if low or mid:
        print("   ── 质量债清单（全量）──")
        if low:
            print(f"   🔴 低分章（均分<4.0，重写候补）：" + "、".join(f"第{c['chapter']}章({c['avg']})" for c in low))
        if mid:
            print(f"   🟡 平庸章（均分 4.0-4.5，可打磨）：" + "、".join(f"第{c['chapter']}章({c['avg']})" for c in mid))
    else:
        print("   ✅ 质量债清单：无低分/平庸章")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="冷读质量趋势")
    sub = parser.add_subparsers(dest="command", required=True)
    p_rec = sub.add_parser("record", help="记录一章的四维分数")
    p_rec.add_argument("--project", type=Path, default=None, help="书项目根（可选，默认从 cwd 向上找）")
    p_rec.add_argument("--scores", required=True, help="四个 1-5 分，逗号分隔：翻页欲,认知负荷,共情验证,节奏感受")
    p_rec.add_argument("--note", default="", help="备注（可选）")
    p_rec.add_argument("--chapter", type=int, default=None, help="章号覆盖（重打分/补记已归档章时用；默认取 pipeline.json 当前章）")
    p_rec.set_defaults(func=cmd_record)
    p_show = sub.add_parser("show", help="查看趋势")
    p_show.add_argument("--project", type=Path, default=None)
    p_show.set_defaults(func=cmd_show)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
