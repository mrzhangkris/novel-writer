#!/usr/bin/env python3
"""chapter_flow.py — 章节流程仪表盘：显示当前章状态与剩余步骤命令清单

把 novel-draft 的固定流程固化为确定性输出，AI 不用再记命令顺序，
每章盯着仪表盘往下跑即可。所有命令都打印绝对路径，直接复制执行。

用法：
  chapter_flow.py status --project {书目录}
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import find_project_root

STEPS = ["setup", "outline", "draft", "revise", "archive"]
STEP_LABEL = {
    "setup": "设定",
    "outline": "大纲",
    "draft": "草稿+冷读",
    "revise": "修订",
    "archive": "归档",
}


def load_pipeline(root: Path) -> dict:
    p = root / ".story/pipeline.json"
    if not p.exists():
        return {"chapter": 0, "steps": {}, "project": root.name}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"✗ 状态文件损坏：{p}（{e}）——拒绝继续，请从 git 恢复或重跑 init", file=sys.stderr)
        sys.exit(1)


def chapter_dir(root: Path, n: int) -> Path:
    return root / f"chapters/chapter-{n:03d}"


def spec_complete(root: Path, n: int) -> bool:
    """五问闸门与净变化都填了才算 spec 完成。"""
    spec = chapter_dir(root, n) / "spec.md"
    if not spec.exists():
        return False
    t = spec.read_text(encoding="utf-8")
    return "## 五问闸门结果" in t and "通过" in t and "待定" not in t.split("## 五问闸门结果")[-1][:600]


def plan(root: Path) -> list[str]:
    here = Path(__file__).resolve().parent
    SK = str(here)
    ROOT = str(root)
    pipe = load_pipeline(root)
    chapter = int(pipe.get("chapter") or 0)
    steps = pipe.get("steps") or {}
    if chapter <= 0:
        return ["python3 {SK}/gen_transaction.py init --project {ROOT} → 填 init 事务 → {SK}/tracking_commit.py init --project {ROOT} --input .story/tx-init.json",
                "之后：{SK}/pipeline.py next-chapter 正式开局"]
    ch = chapter_dir(root, chapter)
    cname = f"第 {chapter} 章"
    out = []
    if not ch.exists() or not (ch / "spec.md").exists():
        out.append(f"{cname}尚未初始化：{SK}/new_chapter.py --chapter {chapter}")
        out.append(f"组装 spec：{SK}/assemble_spec.py --chapter {chapter}（AI 补判断项：概念取舍/净变化/时间线/五问闸门，勾履约清单）")
        return out
    draft = ch / "draft.md"
    if not draft.exists():
        if not spec_complete(root, chapter):
            out.append(f"{cname} spec 未填完：补「本章净变化」与「五问闸门结果」，勾履约清单")
        else:
            out.append(f"{cname} 写 draft.md（只读 spec.md 写作，目标字数按 word-count.json）")
            out.append("   写前：① 主角主动选择+代价（craft-canon 特质对照）② 人物卡底线自检（story_query.py --character 查卡）③ 技法先查 writing-methods/INDEX.md 再读单份")
        return out
    if steps.get("draft") != "done":
        out.append(f"1) 生成并填事务：{SK}/gen_transaction.py commit --project {ROOT}")
        out.append("   填 tx（result≤480B、constraints 只收字符串、快照=changes 角色、退役逐字）")
        out.append(f"   提交：{SK}/tracking_commit.py commit --project {ROOT} --input .story/tx-chapter-{chapter:03d}.json")
        out.append(f"2) 闸门：{SK}/pipeline.py advance draft（字数/去AI味/衔接/履约/风格基线/说教密度/章节定位）")
        out.append(f"3) 冷读：{SK}/coldread_material.py --chapter {chapter} --write-review → spawn 子代理读 draft+review.md 评分（四维 + 红线标签 6 项）")
        out.append(f"   记趋势：{SK}/quality_trend.py record --project {ROOT} --scores 翻页,认知,共情,节奏")
        out.append(f"4) 收尾：{SK}/pipeline.py advance revise → advance archive")
        out.append(f"   平台审稿：{SK}/platform_review.py --chapter {chapter} --project {ROOT}")
        out.append(f"   连续性：{SK}/check_continuity.py --project {ROOT}（advisory，finish 自动跑）")
        out.append(f"   沉淀：{SK}/learn.py add（妙处/坑）→ {SK}/pipeline.py next-chapter")
        return out
    if steps.get("revise") != "done":
        out.append(f"{cname} draft 已过闸门但 revise 未完成：冷读通过则 skip revise（记 skipped），打回则先改 draft（真改过才 advance revise）")
        return out
    if steps.get("archive") != "done":
        out.append(f"{cname} 等待归档：{SK}/pipeline.py advance archive → platform_review → learn → next-chapter")
        return out
    done_chapters = len([p for p in (root / "chapters").glob("chapter-*/draft.md")]) if (root / "chapters").exists() else 0
    if done_chapters >= chapter and steps.get("archive") == "done":
        out.append(f"{cname} 已归档，全书 {chapter} 章完成。")
        out.append(f"导出成书：{SK}/export_book.py --project {ROOT} --output {ROOT}/成书-书名.md")
        out.append(f"全本扫描：{SK}/platform_review.py --book --project {ROOT}；终检：{SK}/tracking_commit.py check --project {ROOT}")
    else:
        out.append(f"{cname} 已归档 → {SK}/pipeline.py next-chapter 进入下一章")
    return out


def run(script: str, *args: str, cwd: Path) -> int:
    """跑同目录脚本，非零退出即停并报告。"""
    here = Path(__file__).resolve().parent
    import subprocess
    import sys as _sys
    cmd = [_sys.executable, str(here / script), *args]
    print("  ▶ " + " ".join(str(c) for c in cmd))
    r = subprocess.run(cmd, cwd=str(cwd))
    return r.returncode


def prepare(root: Path, chapter: int) -> int:
    """开章批量生成：new_chapter + assemble_spec + gen_transaction 骨架。"""
    steps = load_pipeline(root).get("steps") or {}
    ch = chapter_dir(root, chapter)
    if steps.get("archive") == "done" and (ch / "draft.md").exists():
        print("  本章已归档。开新章：pipeline.py next-chapter，再跑 prepare")
        return 0
    # 首章防呆：状态账本未初始化时先 init，否则 commit 必被拒
    if not (root / "tracking/_tracking-state.json").exists():
        print("  ⚠️ 状态账本未初始化（首章前置）：")
        print(f"  1) {Path(__file__).resolve().parent / 'gen_transaction.py'} init --project {root} 生成 init 事务")
        print("  2) 填 init 事务 context 后：tracking_commit.py init --project {root} --input .story/tx-init.json")
        print("  3) 再回来跑 prepare")
        return 1
    if not (ch / "spec.md").exists():
        rc = run("new_chapter.py", "--chapter", str(chapter), cwd=root)
        if rc != 0:
            return rc
    if not spec_complete(root, chapter):
        rc = run("assemble_spec.py", "--chapter", str(chapter), cwd=root)
        if rc != 0:
            return rc
        print("  ⚠️ spec 已组装：补「本章净变化」「五问闸门结果」并勾履约清单，再回来跑 prepare")
        return 0
    tx = root / ".story" / f"tx-chapter-{chapter:03d}.json"
    if not tx.exists():
        rc = run("gen_transaction.py", "commit", "--project", str(root), cwd=root)
        if rc != 0:
            return rc
    print()
    print("  ✍️ 现在写 draft.md，同时在 tx 里填变化字段（character_changes/时间线/伏笔兑现/退役声明）。")
    print("     写前：① 主角主动选择+代价（craft-canon 特质对照）② 人物卡底线自检（story_query.py --character 查卡）③ 技法先查 writing-methods/INDEX.md 再读单份")
    print("  写完跑：chapter_flow.py finish --project {root}".format(root=root))
    return 0


def _scores_from_review(root: Path, chapter: int) -> str | None:
    """从 review.md 解析子代理落盘的独立评分（翻页/认知/共情/节奏）。

    优先新格式「评分：X,X,X,X」；回退旧格式「翻页欲 X｜认知负荷 Y｜…」。
    """
    p = chapter_dir(root, chapter) / "review.md"
    if not p.exists():
        return None
    import re
    text = p.read_text(encoding="utf-8")
    m = re.findall(r"评分：(\d),(\d),(\d),(\d)", text)
    if m:
        return ",".join(m[-1])
    m = re.findall(
        r"翻页欲 (\d)｜认知负荷 (\d)｜共情验证 (\d)｜节奏感受 (\d)",
        text,
    )
    if not m:
        return None
    return ",".join(m[-1])  # 取最后一次（复评优先于初评）


def finish(root: Path, chapter: int, coldread: str | None) -> int:
    """收尾批量执行：commit tx → 闸门 → 冷读材料；再跑趋势→归档→审稿→下一章。

    冷读分数来源：--coldread 参数 > review.md 里子代理已落盘的独立评分
    （自动解析，AI 不用再手动传参；inline 降级格式不匹配时才需 --coldread）。
    """
    steps = load_pipeline(root).get("steps") or {}
    if coldread is None and steps.get("draft") == "done":
        coldread = _scores_from_review(root, chapter)
    if coldread is None:
        tx = root / ".story" / f"tx-chapter-{chapter:03d}.json"
        if tx.exists() and steps.get("draft") != "done":
            rc = run("tracking_commit.py", "commit", "--project", str(root), "--input", str(tx), cwd=root)
            if rc != 0:
                print("  ❌ 事务被拒：按报错修 tx 后重跑 finish")
                return rc
        if steps.get("draft") != "done":
            rc = run("pipeline.py", "advance", "draft", cwd=root)
            if rc != 0:
                print("  ❌ 闸门未过：按报错改 draft 后重跑 finish")
                return rc
        rc = run("check_spec_copy.py", "--project", str(root), "--chapter", str(chapter), cwd=root)
        if rc != 0:
            return rc
        rc = run("coldread_material.py", "--chapter", str(chapter), "--write-review", cwd=root)
        if rc != 0:
            return rc
        print()
        print("  ✍️ 病句自扫（每章必做）：spawn 子代理按 story-polish 协议读 draft.md 挑病句（开头 500 字必精读），")
        print("     采纳项写清单后用 polish_apply.py 批量替换；同时作者（你）用 Read 重读一遍 draft 自校。")
        print("  🧊 冷读：spawn 子代理读 draft.md + review.md 评分。")
        print("  子代理把四维分数落进 review.md 后，直接重跑 finish（自动解析分数），")
        print(f"  或显式传分：chapter_flow.py finish --project {root} --coldread 翻页分,认知分,共情分,节奏分")
        return 0
    # 冷读段：先校验分数 → 打回判定 → 落 review.md → 趋势 → 审稿 → revise/archive → 下一章
    # 顺序纪律：非法分数绝不落盘（防坏分污染 review.md 后 _verify_review_integrity 恒拒）；
    # 结论与实际一致：≤2 分打回时落盘的结论写「打回」，不写「通过」。
    print(f"  🧊 冷读分数：{coldread}")
    try:
        parts = [int(x) for x in coldread.split(",")]
        if len(parts) != 4:
            raise ValueError
    except ValueError:
        print(f"  ❌ 冷读分数格式错误：「{coldread}」应为四个 1-5 整数（翻页欲,认知负荷,共情验证,节奏感受）")
        return 1
    if any(not (1 <= p <= 5) for p in parts):
        print(f"  ❌ 冷读分数越界（须 1-5）：{coldread}")
        return 1
    rejected = any(p <= 2 for p in parts)
    review_path = root / f"chapters/chapter-{chapter:03d}/review.md"
    if review_path.exists() and not re.search(r"评分：\s*\d", review_path.read_text(encoding="utf-8")):
        # 分数同步落 review.md：skip revise 校验 review.md 有真实评分行，
        # 只记 trend 不落 review 会导致「下一章闭环在 skip 处死锁」。
        verdict = "打回（有维度 ≤2 分）" if rejected else "通过（无 ≤2 分，分数由 finish --coldread 落盘）"
        with review_path.open("a", encoding="utf-8") as fh:
            fh.write(f"\n评分：{coldread}\n结论：{verdict}\n")
    if rejected:
        print("  ❌ 冷读有维度 ≤2 分：本章打回。按 novel-revise 改 draft（打回原因见 review.md），改完重跑 finish 一段")
        return 1
    rc = run("quality_trend.py", "record", "--project", str(root), "--scores", coldread, cwd=root)
    if rc != 0:
        return rc
    # 审稿与连续性检查放在归档之前（先处理再归档，归档即冻结）
    rc = run("platform_review.py", "--chapter", str(chapter), "--strict", "--project", str(root), cwd=root)
    if rc != 0:
        print("  ⚠️ 平台审稿有告警：逐条判断语境（对话/引用可放行并在 review.md 注明），确认后再归档")
        return rc
    rc = run("check_continuity.py", "--project", str(root), cwd=root)
    if rc != 0:
        return rc
    if steps.get("revise") != "done" and steps.get("revise") != "skipped":
        rc = run("pipeline.py", "skip", "revise", cwd=root)  # 冷读通过=跳过修订（记 skipped），真改过才 advance revise
        if rc != 0:
            print("  ❌ skip revise 失败")
            return rc
    if steps.get("archive") != "done":
        rc = run("pipeline.py", "advance", "archive", cwd=root)
        if rc != 0:
            print("  ❌ advance archive 失败")
            return rc
    pipe = load_pipeline(root)
    if int(pipe.get("chapter") or 0) == chapter:
        rc = run("pipeline.py", "next-chapter", cwd=root)
        if rc != 0:
            return rc
    print(f"  ✅ 第 {chapter} 章闭环完成。下一章：chapter_flow.py prepare --project {root}")
    # 文风锚校准提醒（第 3 章后触发一次：量化基线应已可实测）
    anchor = root.parent / ".novel" / "style-anchor.md"
    if anchor.exists() and "___" in anchor.read_text(encoding="utf-8"):
        print("  💡 文风锚量化基线仍是空模板：已写 3 章，建议实测句长/对话占比回填 style-anchor.md（防后续文风漂移无约束）")
    print("  💡 本章有妙处/坑？learn.py add --scope project/author 沉淀一条；全书完跑 book_finish.py --project 收尾")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="章节流程仪表盘与批量执行器")
    parser.add_argument("command", choices=["status", "prepare", "finish"])
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--coldread", type=str, default=None, help="finish 用：四维分数，逗号分隔")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在书项目中（找不到 .story/）")
        return 1
    pipe = load_pipeline(root)
    chapter = int(pipe.get("chapter") or 0)
    steps = pipe.get("steps") or {}
    here = Path(__file__).resolve().parent
    if args.command == "prepare":
        print(f"📖 《{pipe.get('project', root.name)}》 开章批量生成：第 {chapter} 章")
        return prepare(root, chapter)
    if args.command == "finish":
        print(f"📖 《{pipe.get('project', root.name)}》 收尾批量执行：第 {chapter} 章")
        return finish(root, chapter, args.coldread)
    print(f"📖 《{pipe.get('project', root.name)}》 进度：第 {chapter} 章")
    print("   步骤：" + " → ".join(
        f"{STEP_LABEL.get(k, k)}{'✅' if v == 'done' else '…'}" for k, v in steps.items() if k in STEP_LABEL
    ))
    print()
    print("下一步：")
    for line in plan(root):
        print("  " + line.replace("{SK}", str(here)).replace("{ROOT}", str(root)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
