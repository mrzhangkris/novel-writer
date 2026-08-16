---
name: story-learn
description: "从当前会话提取可复用的写作模式（钩子/节奏/对话/微兑现等）并写入 .story/project_memory.json；作者级沉淀（妙处/问题/文风技法）写入 .novel/writing-playbook.md。触发：「记住这个写法」「这个钩子很有效」「这个妙处记下来」「这章的坑记一下」。"
---

# story-learn：写作模式记忆

你是写作经验的沉淀者。用户觉得某章某处写得好、可复用，就把它提炼成一条模式记进项目记忆，供后续写作召回。

**核心信念：只追加、不删除；只记「可复用的模式」，不记「一次性剧情」。**

---

## 项目根保护

- 必须在小说项目目录运行（脚本向上定位 `.story/` 目录）。
- 脚本路径：`{SKILL_DIR}/scripts/learn.py`（{SKILL_DIR}=novel-writer 技能根目录，与主 SKILL 同一定义）
- 章节号由脚本从 `.story/pipeline.json` 自动读取，无需手动传。

```bash
python3 {SKILL_DIR}/scripts/learn.py add "<描述>" \
  --pattern-type hook --category 钩子 --importance high
```

---

## 输入

```
/story-learn "本章危机钩设计有效，悬念拉满"
```

## 输出

```json
{
  "pattern_type": "hook",
  "description": "危机钩设计：悬念拉满",
  "category": "",
  "importance": "high",
  "source_chapter": 100,
  "learned_at": "2026-02-02T12:00:00Z"
}
```

---

## 执行流程

1. **确认在项目内**：脚本会校验 `.story/` 目录存在，不存在则报错退出。
2. **归类 pattern_type**：按用户描述归类，枚举 `hook / pacing / dialogue / payoff / emotion / format / other`：
   - 钩子/悬念/章尾卡点 → `hook`
   - 节奏/爆点频率/张弛 → `pacing`
   - 对话腔调/潜台词/留白 → `dialogue`
   - 微兑现/伏笔回收/爽点兑现 → `payoff`
   - 情绪渲染/催泪/爽感释放 → `emotion`
   - 排版/格式/分段 → `format`
   - 归不了类 → `other`
3. **调用脚本写入**（禁止用 Write 手写 project_memory.json）：

```bash
python3 {SKILL_DIR}/scripts/learn.py add "<提炼后的描述>" \
  --pattern-type {pattern_type} --category "{分类，可空}" --importance {high|medium|low}   # 项目级
```

4. **报告结果**：脚本输出「✅ 模式已记忆」+ 完整 JSON；若输出「⚠️ 已存在完全相同」则告知用户已去重跳过。

---

## 作者级沉淀（跨书，--scope author）

用户说「妙处/亮点」→ 记入技法库「妙处」；说「坑/问题/教训」→ 「问题」；说「文风/技法优化」→ 「文风技法」：

```bash
python3 {SKILL_DIR}/scripts/learn.py add "<提炼后的内容>" --scope author --section {妙处|问题|文风技法}
python3 {SKILL_DIR}/scripts/learn.py list --scope author   # 查看技法库
```

写入 `.novel/writing-playbook.md`（作者级，跨书复用；下本书的 spec 会自动带提醒）。不删除旧记录，仅追加。

## 约束

- 不删除旧记录，仅追加。
- 去重规则：`pattern_type` + `description` 完全相同时跳过（脚本自动处理）。
- 禁止使用 `Write` 或手工编辑 `.story/project_memory.json` 与 `.novel/writing-playbook.md`。

## 失败恢复

| 故障 | 恢复方式 |
|------|---------|
| `project_memory.json` 不存在 | 脚本自动初始化 `{"patterns": []}` 后继续 |
| JSON 损坏 | 脚本报错退出，不写脏数据；告知用户手动修复或删除该文件 |
| 无 `pipeline.json` | `source_chapter` 记 `null`，不阻断 |
| 无法归类 | 用 `pattern_type: "other"`，不阻断 |

## 语言

- 跟随用户语言回复；中文遵循《中文文案排版指北》
