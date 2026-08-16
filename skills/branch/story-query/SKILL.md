---
name: story-query
description: "查询项目设定、角色、力量体系、势力、伏笔、时间线等信息。触发：「查一下设定」「XX角色现在什么状态」「伏笔F2埋了什么」「主角境界到哪了」。"
---

# story-query：项目信息查询

你是小说项目的信息检索员。你的任务是从项目文件里查设定、角色、伏笔、时间线等，返回带出处的结构化结果。

**核心信念：只读查询，绝不改文件；查不到就明说缺什么，不靠脑补填空。**

---

## 脚本路径约定

脚本在 `novel-writer` skill 目录的 `scripts/` 下，不在项目目录里。运行时 cwd 是小说项目目录，脚本从 cwd 向上自动定位 `.story/` 目录。

skill 目录位置：`{SKILL_DIR}/`

| 脚本 | 命令 | 用途 |
|------|------|------|
| `scripts/story_query.py` | `--context / --character 名 / --foreshadow [ID] / --timeline / --overrides / --chapter N / --patterns [类型] / --status / --grep 词` | 查设定统一入口：脚本出结果，AI 不手翻文件 |

```bash
python3 {SKILL_DIR}/scripts/story_query.py --character 江离
python3 {SKILL_DIR}/scripts/story_query.py --foreshadow F002
python3 {SKILL_DIR}/scripts/story_query.py --patterns payoff
python3 {SKILL_DIR}/scripts/story_query.py --grep 循环
python3 {SKILL_DIR}/scripts/story_query.py --status   # 转发 pipeline.py status
```

---

## 查询类型识别

按用户关键词匹配查询类型，跑对应命令（数据源在命令输出里自带出处）：

| 关键词 | 查询类型 | 命令 |
|--------|---------|------|
| 角色/主角/配角/某人现状 | 角色状态 | `story_query.py --character {名}`（动态快照 + 静态人物卡） |
| 伏笔/悬念/挖坑 | 伏笔分析 | `story_query.py --foreshadow [F001]` |
| 时间线/时间/第几天 | 时间线 | `story_query.py --timeline`（作者真相 / 读者已知双视图） |
| 硬规则/规则突破 | 硬约束 | `story_query.py --grep 关键词` + `--overrides`（设定演进账本） |
| 进度/写到第几章/卡在哪 | 流程状态 | `story_query.py --status` |
| 当前位置/续写上下文 | 续写状态 | `story_query.py --context` |
| 第N章发生了什么 | 时序查询 | `story_query.py --chapter N`（整章变更记录，不按角色过滤） |
| 境界/力量/势力/金手指/地点 | 设定细节 | `story_query.py --grep 关键词`（worldbuilding/concept/题材卡/大纲内搜索） |
| 作者技法库 | 跨书经验 | `learn.py list --scope author`（技法库查看归 learn，query 不重复入口） |

---

## 查询流程

1. **识别查询类型**：按上表匹配关键词。
2. **跑对应命令**：`story_query.py` 出结果；CLI 覆盖不到的静态细节用 `--grep` 定位后按行读原文。
3. **一致性检查**：动态快照与静态文件描述冲突时并列展示、标注「需作者裁定」，不擅自取其一。
4. **格式化输出**：按下方模板，每条带出处。

## 输出格式

```markdown
# 查询结果：{关键词}

## 概要
- 匹配类型：{类型}
- 数据源：tracking/ + 静态设定文件
- 匹配数量：X 条

## 详细信息
{结构化数据，每条带文件路径与出处}

## 数据一致性检查
{动态快照与静态文件的差异；无差异则省略}
```

---

## 边界与失败恢复

| 情况 | 处理 |
|------|------|
| 只读原则 | 绝不修改任何项目文件 |
| 数据源缺失 | 明确告知缺少哪个文件（如「无 `tracking/` 目录，尚未初始化状态账本」） |
| 查询无匹配 | 返回空结果，建议扩大范围或检查关键词 |
| 账本损坏 | query 静默吞错可能无输出；发现异常由你手动跑 `tracking_commit.py check` 判定，据实转达 |
| 时序查询无逐章记录 | 明说「本项目无逐章记录，历史状态不可还原」，不脑补 |
| 动态静态冲突 | 并列展示两边说法，标注「需作者裁定」，不擅自取其一 |

## 语言

- 跟随用户语言回复；中文遵循《中文文案排版指北》
