#!/usr/bin/env python3
"""migration_upgrade.py — 一次性回炉脚本

将现有 characters/ 下的所有卡按新规则升级：
  1. 按「关系网锚点」自动判定详/简
  2. 详卡：自动补「个人故事」四件套骨架（每个字段留 TODO）
  3. 简卡：自动压缩到 character-card-simple.md 模板
  4. 输出 migration-report.md 让作者人工 review

详/简自动判定规则（启发式 v1）：
  - 详卡：卡内含 5+ 行的「##」级小节（基本信息/核心性格/动机/底线/口癖/能力/关系网），
          **且**「关系网」非空（至少 1 条 - 与X：... 行）
  - 简卡：其他情况（信息稀疏 / 关系网为空 / 不符合详卡模板）

判定有歧义时（详卡可能错判为简卡），脚本会在 report 中标 ❓，由作者人工确认。

用法：
  migration_upgrade.py --project 书目录 [--apply] [--dry-run]
  --dry-run 默认：只生成 report，不动文件
  --apply：实际修改文件
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from _common import find_project_root

CHAR_DIR = "characters"
REPORT_FILE = "migration-report.md"

# 详卡模板骨架（用于补 4 字段）
DETAILED_PERSONAL_STORY = """## 个人故事（详卡专属）

> 写「这个人的人生」，不是「这个人在这本书里的功能」。
> 这四个字段强制你回答：哪怕这本书完结、TA 是什么样的人？

- **出身与来处**：TODO（哪里人、什么家世、怎么走到现在）
- **关键转折**：TODO（一生中 1-2 个改变命运的事件，不一定是这本书里发生的）
- **未了的执念**：TODO（哪怕这本书完结、TA 还想做的事）
- **独处时的样子**：TODO（TA 不演给别人看的那一面——性格深挖）
"""

# 简卡模板（用于压缩）
SIMPLE_TEMPLATE = """# 人物卡（简）：{name}

> 本卡由 migration_upgrade.py 从旧版压缩而来。需人工核对「一句话功能」与「与详卡的关系」。
> 详/简判定标准见 `references/writing-methods/character-design-methods.md`「双层卡设计」。

## 基本信息

- 姓名：{name}
- 一句话功能：TODO（TA 在这本书里做什么——推动剧情/衬托主角/提供信息/见证者）
- 标记标签：TODO（一句话内辨识）

## 与详卡的关系

- TODO（至少 1 条，如：受{{详卡角色名}} 指挥 / 给{{详卡角色名}} 提供线索）
"""


def parse_sections(text: str) -> dict[str, str]:
    """把 markdown 切成 '## 段落名' -> '段落内容'。"""
    sections: dict[str, str] = {}
    cur_name: str | None = None
    cur_lines: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if cur_name is not None:
                sections[cur_name] = "\n".join(cur_lines).strip()
            cur_name = m.group(1).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    if cur_name is not None:
        sections[cur_name] = "\n".join(cur_lines).strip()
    return sections


def has_relation_entries(relations_text: str) -> bool:
    """检查「关系网」段落是否有至少 1 条 - 与X：... 行。"""
    if not relations_text:
        return False
    for line in relations_text.splitlines():
        if re.match(r"^\s*-\s*与[\u4e00-\u9fff]", line):
            return True
    return False


def classify_card(text: str) -> tuple[str, str]:
    """返回 (判定: 'detail' | 'simple' | 'ambiguous', 理由)。"""
    sections = parse_sections(text)
    section_names = set(sections.keys())

    # 详卡特征：核心性格 / 动机与目标 / 底线与恐惧 三件套都有
    detail_keys = {"核心性格", "动机与目标", "底线与恐惧"}
    has_detail_keys = detail_keys.issubset(section_names)
    has_relations = has_relation_entries(sections.get("关系网", ""))

    if has_detail_keys and has_relations:
        return ("detail", "三件套齐全 + 关系网非空")
    if has_detail_keys and not has_relations:
        return ("ambiguous", "三件套齐全但关系网为空——可能是核心配角但未对账关系")
    if not has_detail_keys and has_relations:
        return ("ambiguous", "关系网非空但缺三件套——可能是被对账的配角但字段未补全")
    return ("simple", "三件套缺失 + 关系网为空")


def upgrade_to_detailed(text: str, name: str) -> str:
    """详卡：在文件末尾追加「个人故事」四件套骨架（若已存在则不重复）。"""
    if "## 个人故事" in text:
        return text  # 已升级，跳过
    # 找到「## 关系网」之前插入
    if "## 关系网" in text:
        idx = text.index("## 关系网")
        return text[:idx] + DETAILED_PERSONAL_STORY + "\n" + text[idx:]
    # 没有关系网段，append 到末尾
    return text.rstrip() + "\n\n" + DETAILED_PERSONAL_STORY


def compress_to_simple(text: str, name: str) -> str:
    """简卡：用简卡模板替换（旧内容备份到文件名前缀 .bak）。"""
    return SIMPLE_TEMPLATE.format(name=name)


def process_card(card_path: Path, apply: bool) -> dict:
    """处理单张卡，返回 report 行信息。"""
    text = card_path.read_text(encoding="utf-8")
    name = card_path.stem
    cls, reason = classify_card(text)

    action: str
    new_content: str | None = None
    backup: str | None = None

    if cls == "detail":
        new_content = upgrade_to_detailed(text, name)
        action = "升级（补个人故事四件套）"
        if apply:
            if new_content != text:
                backup = ".bak-" + name + ".md"
                (card_path.parent / backup).write_text(text, encoding="utf-8")
                card_path.write_text(new_content, encoding="utf-8")
    elif cls == "simple":
        new_content = compress_to_simple(text, name)
        action = "压缩为简卡"
        if apply:
            backup = ".bak-" + name + ".md"
            (card_path.parent / backup).write_text(text, encoding="utf-8")
            card_path.write_text(new_content, encoding="utf-8")
    else:  # ambiguous
        action = "❓ 歧义（需人工判定详/简）"
        new_content = None

    return {
        "name": name,
        "class": cls,
        "reason": reason,
        "action": action,
        "backup": backup,
        "would_change": new_content is not None and new_content != text,
    }


def render_report(items: list[dict], dry_run: bool) -> str:
    lines = ["# 人物卡迁移报告（migration-report）", ""]
    lines.append(f"> 模式：{'dry-run（未改文件）' if dry_run else 'apply（已改文件）'}")
    lines.append("")
    lines.append("## 统计")
    detail = sum(1 for it in items if it["class"] == "detail")
    simple = sum(1 for it in items if it["class"] == "simple")
    ambig = sum(1 for it in items if it["class"] == "ambiguous")
    lines.append(f"- 总计：{len(items)} 张")
    lines.append(f"- 升级为详卡：{detail} 张")
    lines.append(f"- 压缩为简卡：{simple} 张")
    lines.append(f"- ❓ 歧义（需人工判定）：{ambig} 张")
    lines.append("")
    lines.append("## 详情")
    lines.append("")
    lines.append("| 角色 | 判定 | 理由 | 操作 | 备份 |")
    lines.append("|------|------|------|------|------|")
    for it in items:
        cls_icon = {"detail": "📖详", "simple": "📄简", "ambiguous": "❓歧"}.get(it["class"], "?")
        lines.append(
            f"| {it['name']} | {cls_icon} | {it['reason']} | {it['action']} | {it['backup'] or '—'} |"
        )
    lines.append("")
    if ambig:
        lines.append("## 歧义项处理建议")
        lines.append("")
        for it in items:
            if it["class"] == "ambiguous":
                lines.append(f"### {it['name']}")
                lines.append(f"- 理由：{it['reason']}")
                lines.append("- 处理：人工判断这张卡是否该升详卡——")
                lines.append("  - 若与主角/详卡有直接关系 → 升级，手动补个人故事四件套")
                lines.append("  - 若纯龙套/边缘出场 → 简卡化，删除 .bak 文件")
                lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="人物卡一次性回炉脚本")
    parser.add_argument("--project", default=".", help="书目录")
    parser.add_argument("--apply", action="store_true", help="实际修改文件（默认 dry-run）")
    args = parser.parse_args()

    root = Path(args.project).resolve()
    proj = find_project_root(root)
    if proj is None:
        print(f"[错误] 找不到项目根（无 .story/）：{root}", flush=True)
        return 1

    chars_dir = proj / CHAR_DIR
    if not chars_dir.exists():
        print(f"[错误] {chars_dir} 不存在", flush=True)
        return 1

    cards = sorted(chars_dir.glob("*.md"))
    # 跳过 .bak 备份文件 + 非人物卡文件（速查库/清单/索引等）
    NON_CARD_KEYWORDS = ["速查", "清单", "索引", "目录", "总表", "库"]
    cards = [
        c for c in cards
        if not c.name.startswith(".bak-")
        and not any(kw in c.name for kw in NON_CARD_KEYWORDS)
    ]

    if not cards:
        print(f"[提示] {chars_dir} 下无卡可处理", flush=True)
        return 0

    items = [process_card(c, apply=args.apply) for c in cards]
    report = render_report(items, dry_run=not args.apply)

    report_path = proj / REPORT_FILE
    report_path.write_text(report, encoding="utf-8")
    print(f"[ok] 报告：{report_path}", flush=True)
    print(f"     详 {sum(1 for it in items if it['class']=='detail')} / "
          f"简 {sum(1 for it in items if it['class']=='simple')} / "
          f"歧 {sum(1 for it in items if it['class']=='ambiguous')}", flush=True)
    if not args.apply:
        print("     提示：当前为 dry-run，未改文件。加 --apply 实际执行。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())