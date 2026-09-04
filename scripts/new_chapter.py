#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_chapter.py — 初始化章节文件夹（每章写正文前必须调用）。

创建 chapters/chapter-NNN/ 目录 + spec.md 空蓝图模板。幂等：已存在则跳过不覆盖。

用法：
  python3 new_chapter.py --chapter N [--root-dir 书目录]

退出码：0 = 成功（或已存在）；1 = 参数错误。
"""

import argparse
import json
import os
import sys
from pathlib import Path

from _common import PIPELINE_FILE, find_project_root, read_json

SPEC_TEMPLATE = """# 第 {n} 章写作蓝图

> 草稿预审阶段 A 产出。写作阶段 C 只读本文件，不重新读设定全文。
> 大纲要点是「履约清单」：写 draft 前把每条勾成 [x]，advance draft 时脚本校验履约率 ≥80%（写正文时如调整了计划，回来改勾选并注明，不删条目）。

## 大纲要点（履约清单，逐条勾选）
- [ ] 本章目标：
- [ ] 场景安排：
- [ ] 关键事件：
- [ ] 章末钩子：

## 概念要点（本章引入/深化，标注来源）
- 

## 角色要点（出场角色当前状态）
- 

## 出场角色（本章计划出场的核心角色，一行一名，可带别名如「张三（火哥）」）
- 

## 前情衔接（上章结尾状态，伤势/情绪/位置必须延续；附上章结尾原文锚）
- 

## 本章净变化（本章结束时至少改变一项：状态/信息/关系/资源；防「水章」）
- 变化项：
- 主角代价/取舍：（本章主角付出了什么；纯奖励章必须写明理由，否则回大纲补代价）

## 章节定位（铺垫 / 推进 / 高潮 / 收束，四选一；与大纲结构标记对齐；连爆 3 章必放 1 章）
- 

## 知情边界（本章读者知道什么、不知道什么——防止作者视角泄露）
- 读者已知：
- 读者不知：

## 时间线定位（本章故事时间，与 tracking/timeline 双视图对齐）
- 故事时间：
- 距上章过去：
- 本章目标字数：（按平台区间取中值，如 1500-2500 写足 2000；首稿一次写足，禁止先写短稿再补）

## 在场与时间闸门（写前必答；不答完不动笔。防「只有主角一人后又有人已到岗」「凌晨三点发消息却未加班」「先走上台又写上台前」类矛盾）
- 本章开头时间点：
- 本章开头谁在场、在何处（与上章结尾逐人核对）：
- 谁不在场、从哪一刻起出现（每个新出场者必须交代入场动作或时间过渡）：
- 各时间节点核对（本章内出现的每个「几点几分」与场景动作是否吻合、与自然常识是否吻合）：

## 伏笔指令（植入/推进/回收，编号对齐大纲伏笔规划）
- 

## 题材要点（本章相关条目，摘书目录题材卡.md）
- 

## 风格指令（视角/腔调/禁止）
- 

## 规则注入（写作规则库写前投影，assemble_spec 自动填充；逐条对照执行）
- 

## 设定五问（设定侧判断，区别于写前爽点五问——爽点/兑现/情绪垫/同型/钩子在开章节）
- 概念预算：/ 服务冲突：/ 揭示方式：/ 概念深化：/ 认知负载：
- 时间在场：/ 时序一致：/
"""




def main():
    ap = argparse.ArgumentParser(
        description="初始化章节文件夹（chapters/chapter-NNN/）"
    )
    ap.add_argument("--chapter", type=int, required=True, help="章节号")
    ap.add_argument("--root-dir", default=".", help="书目录（默认当前目录）")
    args = ap.parse_args()

    if args.chapter < 1:
        print("❌ 章节号必须 ≥1", file=sys.stderr)
        return 1

    # 章号防呆：必须与状态机的当前章节一致，防止「建了 N+1 章却校验了 N 章」
    root = find_project_root(Path(args.root_dir), child=PIPELINE_FILE)
    current = None
    if root is not None:
        pipe = read_json(root / PIPELINE_FILE)
        if isinstance(pipe, dict) and isinstance(pipe.get("chapter"), int):
            current = pipe["chapter"]
    if current is not None and args.chapter != current:
        print(
            f"❌ 章节号与状态机不符：pipeline 当前是第 {current} 章，"
            f"你传的是第 {args.chapter} 章",
            file=sys.stderr,
        )
        print(
            f"   新章节先跑 pipeline.py next-chapter，续写已有章节直接用对应章号",
            file=sys.stderr,
        )
        return 1

    chapter_dir = os.path.join(args.root_dir, "chapters", f"chapter-{args.chapter:03d}")
    spec_path = os.path.join(chapter_dir, "spec.md")

    os.makedirs(chapter_dir, exist_ok=True)

    if os.path.exists(spec_path):
        print(f"⚠️  章节文件夹已存在：{chapter_dir}（spec.md 已存在，跳过）")
        return 0

    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(SPEC_TEMPLATE.format(n=args.chapter))

    print(f"✅ 章节文件夹已创建：{chapter_dir}")
    print(f"   spec.md（空蓝图）已就位，接下来做草稿预审填写蓝图")
    return 0


if __name__ == "__main__":
    sys.exit(main())
