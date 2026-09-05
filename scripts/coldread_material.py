#!/usr/bin/env python3
"""coldread_material.py — 冷读材料生成器（干净上下文的确定性拼装）

把「轻量冷读」所需的材料从账本与正文里拼出来，保证冷读者：
1. 只看本章开头 500 字 + 中段切片（长文自动补）+ 章末 300 字 + 前情速记，看不到创作蓝图；
2. 拿到的材料不是 AI 转述（转述会夹带作者记忆），而是原文切片。

用法：
  coldread_material.py --chapter N [--project 书目录] [--write-review]
  默认打印到 stdout（AI 复制进子代理 prompt）；--write-review 把材料与
  评分提示词一起写进 chapters/chapter-NNN/review.md（供子代理填写）。

review.md 首行会自动标注冷读方式，AI 在子代理不可用时按 inline 降级规则
覆盖为「inline 降级」。
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

from _common import find_project_root

COLD_READ_PROMPT = """你是冷读者，从未读过本书的创作蓝图（大纲/设定/写作蓝图）。只凭下面提供给你的正文片段与前情速记评分——你看到开头/章末原文与若干中段切片，切片之间的正文未提供，凡需要切片外上下文才能下的结论不要下。以普通读者视角逐段读，四维度各评 1-5 分并给一句理由。**四个维度统一口径：分越高=该维度表现越好**：
1. 翻页欲：读完是否想继续？（理想「未解答问题」2-4 个）
2. 认知负荷：读来是否轻松跟得上？（信息过载=低分：首 500 字 >3 个未铺垫新元素；信息清晰不堆=高分。不要反向打分）
3. 共情验证：仅凭已读内容，能否一句话概括角色此刻想要什么？概括不出 = 共情失败（低分）。
4. 节奏感受：有没有「想跳过这段」或「等等刚才发生了什么」的地方？（没有=高分）
5. 文笔与自洽硬检（逐句过一遍；任一命中，总结论必须「打回」，并贴出原句与位置；同时把「节奏感受」维度评 ≤2 分并在理由注明命中的硬检项——自动化门禁按分数打回，分数不够低打回不会生效）：
   a. 指代悬空：「这/那+名词」首次出现，但前文没有对应物（例：前文只写了文件名，却写「他盯着那行字」）。注意：前情速记只覆盖近三章，「那/这+名词」若可能是更早章节埋设的跨章道具/事件（如「那封辞职信」「那通电话」），且本章正文内也有细节能推定其存在，不算悬空，不判打回；拿不准就放行，不要误打；
   b. 事实矛盾：时间点与常识冲突（几点几分的天亮天黑/作息习惯；季节/地区不明时无把握不判）；在场状态冲突（「只有主角一个人」后，同段又出现别人已经到岗/凌晨还在发消息）；动作时序颠倒（先写「走上台」又写「上台前」）；
   c. 比喻意象打架：比喻让读者先想到另一件事（用食物充饥意象写情绪，读成「吃撑了」）；
   d. 病句错字：语序/成分残缺/搭配不当/指代错乱/标点断错造成歧义、同音混用、的得地误用。
6. 红线标签（每条标「有」或「无」；标「有」必须贴原句与位置，并说明为什么构成该红线；任一「有」随四维评分一起提交给作者判断，不单独打回）：
   a. 机械降神：本章困境是否由前文未铺垫的新人物/新能力/偶然事件解决？
   b. 无后果：角色惹祸/冲突/胜利是否没有留下任何后果？
   c. 崩人设：角色行为是否违背人物卡底线/一贯性格且无动机支撑？（人物卡在 characters/{角色名}.md，未提供时跳过）
   d. 误会驱动：本章冲突是否靠某角色隐瞒可一句话说清的信息维持？
   e. 工具人：出场配角是否有自己的立场与目的，删掉他本章是否成立？
   f. 说教：是否出现替读者总结道理/情绪的句子？
请输出：四个维度各一行「维度名：X分——理由」，然后一行总结论：「通过」或「打回」，打回必须说明具体位置和问题。
最后必须单独输出一行机器可解析的评分（顺序固定：翻页欲,认知负荷,共情验证,节奏感受）：
评分：X,X,X,X"""


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _recent_from_spec(root: Path, chapter: int) -> list[str]:
    """从该章 spec 的「前情衔接」节恢复当时的近三章速记。

    补跑冷读时账本已推进到后续章节，tracking/context.md 的滚动速记会
    剧透后文；spec 是组装时刻的历史快照，取它才与冷读者视角一致。
    """
    spec = read_text(root / f"chapters/chapter-{chapter:03d}/spec.md")
    out: list[str] = []
    in_block = False
    in_recent = False
    for line in spec.splitlines():
        s = line.strip()
        if s == "## 前情衔接":
            in_block = True
            continue
        if not in_block:
            continue
        if s.startswith("## "):
            break
        if s.startswith("- 上章结尾（近三章速记）"):
            out.append("## 近三章速记")
            in_recent = True
            continue
        if in_recent:
            if s.startswith("- 第") and "章｜" in s:
                out.append(s)
                continue
            in_recent = False  # 速记列表结束，进入锚/原文等其他行
    if out == ["## 近三章速记"]:
        return []  # 只有标题没有条目（如第 1 章）
    return out


def _recent_from_context(root: Path) -> list[str]:
    """回退：账本当前渲染视图的滚动速记（旧项目 spec 无前情节时）。"""
    ctx = read_text(root / "tracking/context.md")
    recent = []
    for line in ctx.splitlines():
        if line.startswith("## 近三章速记"):
            recent.append("## 近三章速记")
        elif recent and line.startswith("## "):
            break
        elif recent:
            recent.append(line)
    return recent


def material(root: Path, chapter: int) -> str:
    body = read_text(root / f"chapters/chapter-{chapter:03d}/draft.md")
    recent = _recent_from_spec(root, chapter)
    if not recent and chapter > 1:
        recent = _recent_from_context(root)
    speed = "\n".join(recent) if recent else "（无前文，这是全书第 1 章）"

    import re as _re
    body = _re.sub(r"<!--[\s\S]*?-->", "", body)  # 剥 HTML 创作标注，保持冷读上下文干净

    # 中段切片：轻量冷读只看首尾会让「中间一两千字」成为无人读过的盲区——
    # 长文按 1/4、3/4 处补两个连续 500 字切片，成本几乎不变
    mid_slices: list[str] = []
    total = len(body)
    if total > 1600:
        mid_slices.append(f"中段切片 1（约 1/4 处起连续 500 字）：\n{body[total // 4 : total // 4 + 500]}")
    if total > 2600:
        mid_slices.append(f"中段切片 2（约 3/4 处起连续 500 字）：\n{body[3 * total // 4 : 3 * total // 4 + 500]}")
    mid_block = ("\n\n" + "\n\n".join(mid_slices) + "\n") if mid_slices else ""

    return (
        f"正文开头 500 字：\n{body[:500]}"
        f"{mid_block}\n"
        f"章末 300 字：\n{body[-300:]}\n\n"
        f"前情速记：\n{speed}\n\n"
        f"{COLD_READ_PROMPT}"
    )


def _blueprint_section(root: Path, chapter: int) -> str:
    """蓝图兑现复盘材料（主线程填，冷读子代理不读）：spec 的目标/关键事件行。

    复盘与冷读分离是刻意的：冷读必须干净上下文，蓝图预期由主线程事后对照。"""
    spec_path = root / f"chapters/chapter-{chapter:03d}/spec.md"
    if not spec_path.exists():
        return ""
    try:
        spec = spec_path.read_text(encoding="utf-8")
    except OSError:
        return ""
    goals = []
    m = re.search(r"## 大纲要点[^\n]*\n(.*?)(?=\n## |\Z)", spec, flags=re.S)
    if m:
        for line in m.group(1).splitlines():
            line = line.strip().lstrip("-").strip()
            if line and not line.endswith("：") and not line.endswith(":"):
                goals.append(re.sub(r"^\[[ xX]\]\s*", "", line))
    if not goals:
        return ""
    rows = "\n".join(f"- {g}" for g in goals)
    return (
        "\n## 蓝图兑现复盘（主线程填，冷读者跳过本节）\n\n"
        "对照本章蓝图承诺逐条判定（done=兑现且力度够 / thin=写到但敷衍 / miss=未兑现）：\n"
        f"{rows}\n\n"
        "- 人物卡对照（主线程）：出场核心角色的行为撞卡上底线/优缺点吗？\n"
        "- 复盘结论：\n"
    )


def write_review(root: Path, chapter: int, force: bool = False) -> Path:
    p = root / f"chapters/chapter-{chapter:03d}/review.md"
    if not force and p.exists() and (re.search(r"评分：\s*\d", p.read_text(encoding="utf-8")) or "均分" in p.read_text(encoding="utf-8")):
        print(f"⚠️ {p} 已有评分，跳过重写（重跑不冲掉子代理已填内容；改稿后重读加 --force 刷新正文切片）")
        return p
    body = read_text(root / f"chapters/chapter-{chapter:03d}/draft.md")
    # 正文指纹：skip revise 时核对 review 材料与当前 draft 一致，防「改稿后拿旧评分过关」
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    content = (
        f"# 第 {chapter} 章冷读报告\n\n"
        f"> 冷读方式：独立子代理（本文件由 coldread_material.py 生成，材料为原文切片）\n"
        f"<!-- draft-hash:{body_hash} -->\n\n"
        f"{material(root, chapter)}\n"
        f"{_blueprint_section(root, chapter)}"
    )
    p.write_text(content, encoding="utf-8")
    return p


def main() -> int:
    parser = argparse.ArgumentParser(description="冷读材料生成器")
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--write-review", action="store_true")
    parser.add_argument("--force", action="store_true", help="改稿后重读：覆盖已有评分重生成正文切片")
    args = parser.parse_args()
    start = args.project if args.project else Path.cwd()
    root = find_project_root(start, child=".story")
    if root is None:
        print("❌ 不在项目中")
        return 1
    if args.write_review:
        out = write_review(root, args.chapter, args.force)
        print(f"✅ review.md 已生成（含材料与评分提示）：{out}")
        return 0
    print(material(root, args.chapter))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
