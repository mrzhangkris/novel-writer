---
name: novel-init
description: |
  小说初始化：扫描目录 → 建作者工作区骨架 → 对话式定方向（9 问）→ 书级建目录。novel-writer 流水线第 1 步。
  触发词：开新书、初始化、新建小说、建小说项目、准备写书、导入旧书继续写（存量书导入见「扫描目录」的存量素材分支——大篇幅旧书推荐先用 story-long-analyze 拆书吸收，再新开项目）。
---

# novel-init · 初始化（第 1 步）

> 顺序不可颠倒：**先建骨架**（作者级通用资产），**再定方向**（具体故事）。

## 执行步骤

### 1. 扫描目录

| 检测项 | 走向 |
|---|---|
| `.novel/` 不存在 | 第 2 步建骨架；已存在则跳过 |
| 有书目录（含 `.story/pipeline.json`）且 setup 已 done | 交回主 skill 续写，不重建 |
| 有书目录但 setup pending | concept 已补全 → 跳到第 5 步；未补全 → 从第 3 步继续 |
| 有存量素材（世界观/角色卡/大纲/章节） | 问用户是否导入；导入旧书人物卡时必须补「穿越适配」节并由作者确认（人格保留，执念在新世界重定向） |

### 2. 建骨架 + 问偏好

```
python3 {SKILL_DIR}/skills/mainline/novel-init/scripts/setup.py --root-dir {写作根目录}
```

脚本直接初始化：目录 + `style-anchor.md` + `templates/`（6 模板）+ `banned-words.txt` + `active.md` + `preferences.md`。人物卡不在这步建（outline 第 2 步建，init 只交接模板）。

然后问作者偏好（每次一问，选择题优先，写入 preferences.md）：
1. 写作模式？（A 逐章确认 B 连写 N 章 C 写完一卷暂停 D 全自动）
2. 扫榜？（启用/停用）
3. 考据？（启用/停用）
4. 其他习惯（人称/每章字数/禁忌）

### 3. 定方向（9 问，对话式）

**每次只问一个问题，选择题优先**，每题三种回答方式：导入文件 / 直接输入 / 不确定（AI 提议）。

**首次 vs 之后**：preferences.md 无「默认选题」→ 完整 9 问，定完把可复用项存为默认；已有默认 → 先问「沿用吗」，沿用则只问「这次讲什么新故事」。

9 问：
1. **故事火花**：一个句子/画面/情绪。⚠️ 选项必含「没头绪，扫榜推荐」→ 走 `skills/branch/story-long-scan/SKILL.md`（委派子代理跑，主线程禁裸 web 搜索——番茄/头条有反爬），产出题材候选再让用户定。若工作区已有 `topic-decision.md`（扫榜 Phase 5 产出），先读它把推荐选题列为选项（每个选题附「能爆的原因」与对标拆书候选），用户选定后按该选题继续
2. **形态**：长篇（升级体系/爽感节奏）还是短故事（脑洞/反转，≤8 万字）
3. **题材**：奇幻/科幻/悬疑/言情/历史/现实/其他
4. **核心冲突**：谁 vs 谁，争什么
5. **情感内核**：读者读完要什么感觉
6. **平台**：严格按形态过滤——短故事只列知乎盐选/番茄短故事；长篇只列起点/番茄/晋江/七猫/刺猬猫（刺猬猫无字数标准，字数闸门自动跳过），禁止混列
7. **篇幅**：短故事 3-8 万字；长篇 15 万字起
8. **一句话概要**：「在[世界]中，[主角]必须[核心行动]，否则[代价]」
9. **故事名**：作者给 / AI 提议 3-5 个 / 暂定

**对标拆书**（9 问后默认建议走，作者明确跳过才省略）：问有没有对标书 → 走 `skills/branch/story-long-analyze/SKILL.md`，产出 `deconstruct/{书名}/`（文风样本留在 `deconstruct/{书名}/文风.md`，与 `.novel/style-anchor.md` 不混写）；爽点/节奏结论写进 concept「对标与差异化」。

**方法论按需加载**：题材框架/核心梗/读者心理需要时查 `references/writing-methods/INDEX.md` 再读单份。

产出 `concept.md` 蓝本：一句话概要 + 核心冲突 + 主题 + 开篇钩子 + 目标读者 + 篇幅 + 叙事人称。**蓝本是契约，用户确认才进第 4 步。**

### 4. 书级初始化

```
python3 {SKILL_DIR}/scripts/book_init.py --root-dir {写作根目录} --slug my-book --title "书名" --genre 都市脑洞 [--platform 番茄] [--type 短故事]
```

自动生成：书目录全部骨架 + 题材卡匹配拷贝（多张命中时脚本列候选，`--genre-card` 指定）。agent 把第 3 步结论填进 concept.md。

### 5. 补契约（CP1 之后）

🔴 **CP1 选题确认（唯一人工 checkpoint）**：
```
pipeline.py checkpoint clear cp1    # 用户明确确认后才执行
pipeline.py gate setup
```

补两个文件的内容（骨架已由 book_init 生成）：
1. `worldbuilding.md`：按 `references/worldbuilding-schema.md`——自由叙事（力量体系/时代/势力）+「硬规则清单」表（禁止/上限/唯一）+「能力白名单」表；常见题材可从 `references/worldbuilding-templates/` 取对应骨架起步，再按本书设定改写（不强制）。后续打破硬规则不改表，走当章事务 `rule_overrides` 登记
2. `reader-contract.md`：核心期待 + 兑现方式 + 红线 + 主角代理权（四节模板）

```
pipeline.py advance setup
```

### 6. 校验

```
python3 {SKILL_DIR}/skills/mainline/novel-init/scripts/validate.py --root-dir {根目录} --book my-book
```

init 完成 → 回到根 SKILL.md 入口跑 status，路由到 novel-outline。

## 失败分支

- setup.py 报错 → 查 `--root-dir` 与写权限
- book_init 报错 → slug 必须英文；书目录已存在用 `--force` 补建
- validate 报错 → 按提示补缺文件
- 用户「没头绪」→ 走扫榜分线（委派子代理，禁主线程裸搜）

## 铁律

- 先骨架后方向，顺序不可颠倒；`.novel/` 只建一次
- 每次只问一个问题；蓝本未经确认不往下走
- 平台选项严格按形态过滤
- 路径用英文，中文书名写进 `--title`
