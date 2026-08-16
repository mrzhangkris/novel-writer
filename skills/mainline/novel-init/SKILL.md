---
name: novel-init
description: |
  小说初始化：扫描目录 → 建作者工作区骨架 → 对话式定方向（火花→蓝本）→ 书级建目录。
  novel-writer 流水线第 1 步。触发词：开新书、初始化、新建小说、建小说项目、准备写书。
  脚本：scripts/setup.py（建 .novel/）+ scripts/new.py（开新书 + 建 .story/）+ scripts/validate.py（校验）。
---

# novel-init · 初始化（第 1 步）

> 顺序：**先建骨架（作者工作区基础设施），再定方向（对话式引导）**。骨架是帮助后面写作的通用资产，不涉及具体故事；定方向才把模糊灵感变成自洽蓝本。

## 脚本路径

```
{SKILL_DIR}/skills/mainline/novel-init/scripts/setup.py
{SKILL_DIR}/skills/mainline/novel-init/scripts/new.py
{SKILL_DIR}/skills/mainline/novel-init/scripts/validate.py
```

## 两层结构

| 层 | 目录 | 内容 | 跑几次 |
|---|---|---|---|
| 作者级 | `.novel/` | 作者偏好、文风锚、模板库、禁用词、入口 active.md | 一次，跨所有书复用 |
| 书级 | `{slug}/` + `.story/` | 书目录（设定/追踪）+ 流程状态 pipeline.json | 每本书一次 |

## 执行步骤

### 第 1 步：扫描目录（检测现状）

扫描当前目录（或用户指定目录），检测：

| 检测项 | 判断 | 走向 |
|---|---|---|
| `.novel/` 作者工作区 | 是否已初始化 | 没有 → 第 2 步建骨架；有 → 跳过 |
| 书目录（含 `.story/pipeline.json`） | 是否有已有项目 | 有且 setup 已 done → 交回主 skill 走续写，不重建；有但 setup 仍 pending（上次中断）→ concept.md 蓝本已补全则直接跳到第 5 步补全契约，未补全则从第 3 步定方向继续 |
| 已有素材（世界观文档/角色卡/大纲/手写章节） | 是否有要导入的 | 有 → 问用户是否导入 |

### 第 2 步：建骨架（直接初始化基础设施 + 问作者偏好）

```
python3 .../setup.py --root-dir {写作根目录}
```

setup.py **直接初始化基础设施（不问）**：目录 + `style-anchor.md`（文风锚）+ `templates/`（6 个模板：concept/reader-contract/worldbuilding/character-card（详卡）/character-card-simple（简卡）/pacing）+ `banned-words.txt`（禁用词）+ `active.md`（入口）+ `preferences.md`（空偏好 + 能力索引）。

> 注：**人物卡不在本步建**——`character-card.md` / `character-card-simple.md` 模板由本步拷入 `.novel/templates/`，实际建卡在 outline 第 1.5 步盘点 + 第 2 步建卡（novel-outline），init 只交接不建卡。

然后**问作者偏好**（写入 preferences.md，每次一问、选择题优先）：

1. **写作模式**？（A 逐章确认 B 连写 N 章 C 写完一卷暂停 D 全自动）
2. **扫榜**？（启用 / 停用——是否用 search 技能查热门题材）
3. **考据**？（启用 / 停用——是否用 web search 查真实细节）
4. **其他习惯**？（作者自定义：人称、每章字数、禁忌等）

已初始化时跳过问偏好（作者已答过，可自行改 preferences.md）。

### 第 3 步：定方向（对话式引导，独立环节）

骨架就绪后，**对话式引导**把模糊灵感变成自洽蓝本。**每次只问一个问题，选择题优先**，从大到小收窄。

**首次 vs 之后**（首次拍板 + 之后默认复用）：
- **首次**（`.novel/preferences.md` 无「默认选题」）：完整走下面 9 问；定完后把可复用的（形态/题材/平台/篇幅/文风）写入 preferences.md 作为「默认选题」。
- **之后**（preferences.md 已有「默认选题」）：先问「沿用默认选题吗？（题材 X / 平台 Y / 篇幅 Z / 文风 W）」——
  - **是** → 跳过形态/题材/平台/篇幅/文风，只问「这次讲什么新故事」（故事火花 + 核心冲突 + 故事名）
  - **否** → 完整走 9 问，并更新默认选题

9 问：

1. **故事火花**：你脑子里有什么？（一个句子 / 画面 / 情绪）
   ⚠️ 选项里**必须**包含「没头绪，扫榜推荐」——用户选它就走扫榜分线：
   用 Read 工具读 `skills/branch/story-long-scan/SKILL.md` 并按其执行（多引擎搜榜单/市场趋势），
   产出 `topic-decision.md`（含「能爆的原因」+ 差异化）或 2-3 个题材候选，再让用户定；不能只给固定题材方向让用户硬选

**对标拆书（9 问后默认建议走；仅当作者明确跳过时省略）**：
- 优先问「有没有想对标/学习的小说（书名或文本文件路径）？没有的话，从扫榜候选里挑一本拆」——**不默认跳过**，拆书是文风锚与差异化判断的主要输入源；
- 作者明确不想拆 → 在 `.novel/preferences.md` 记「对标拆书：跳过」，之后不再问；
- 有对标书 → 用 Read 工具读 `skills/branch/story-long-analyze/SKILL.md` 并按其执行（黄金三章 → 全文拆解），
  产出 `deconstruct/{书名}/`（拆文报告 + 章节摘要 + 文风.md）；
- 拆出的**文风**留在 `deconstruct/{书名}/文风.md`（对标文风样本，novel-draft 按需读；作者级文风锚由 novel-init 维护 `.novel/style-anchor.md`，两者不混写）；爽点/节奏结论写进 concept.md 的「对标与差异化」。
2. **形态**：长篇（升级体系 / 爽感节奏 / 金手指）还是短故事（脑洞 / 反转 / 信息差，最多 8 万字）？
3. **类型（题材）**：A 奇幻 B 科幻 C 悬疑 D 言情 E 历史 F 现实 G 其他
4. **核心冲突**：谁 vs 谁，争什么？（人vs人 / 人vs自然 / 人vs社会 / 人vs自我 / 人vs命运）
5. **情感内核**：读者读完想有什么感觉？
6. **目标读者 + 平台**：写给谁、发哪？平台选项**严格按第 2 问已选的形态过滤**——
   - 短故事 → 只列：知乎盐选、番茄短故事
   - 长篇 → 只列：起点、番茄、晋江、七猫、刺猬猫
   ⚠️ 禁止混入另一形态的平台（选了短故事，就不得再出现「起点/晋江」等长篇平台）
7. **篇幅**：按形态自动带出——短故事 3-8 万字，长篇 15 万字起
8. **一句话概要**：用公式「在[世界]中，[主角]必须[核心行动]，否则[代价]」串起来
9. **故事名**：作者给 / AI 提议 3-5 个候选 / 暂定名

每个问题都提供三种回答方式：📄 导入文件 / ✏️ 直接输入 / 🤷 不确定（AI 提建议）。

**题材/梗设计按需加载**：类型（第 3 问）、核心冲突、金手指/核心梗设计需要方法论时，查 `{SKILL_DIR}/references/writing-methods/INDEX.md` 匹配再 Read 单份（题材框架→genre-catalog、核心梗→genre-core-mechanics、题材公式→genre-writing-formulas、读者心理→genre-readers），不整库预读。

产出蓝本（写入 `concept.md`）：一句话概要 + 核心冲突 + 主题 + 开篇钩子 + 目标读者 + 篇幅 + 叙事人称。

**蓝本是契约**：用户确认后才进入第 4 步。

### 第 4 步：书级初始化（建书目录 + 批量生成骨架）

定方向完成后，一条命令把书目录与全部确定性骨架生成好（题材卡自动匹配拷贝、concept 蓝本结构、worldbuilding 两张空表、reader-contract 四节模板）：

```
python3 {SKILL_DIR}/scripts/book_init.py --root-dir {写作根目录} --slug my-book --title "我的书" --genre 都市脑洞 [--platform 番茄] [--type 短故事]
# 题材卡自动按索引匹配；命中多张卡时脚本列候选，加 --genre-card 都市脑洞.md 直接指定
```

AI 接下来只填内容：把第 3 步定方向结论填进 `concept.md` 蓝本各条。

### 第 5 步：补全契约（setup 步骤）

🔴 CHECKPOINT CP1（选题确认，唯一人工把关）：老板确认后执行
```
pipeline.py checkpoint clear cp1    # 老板确认选题
pipeline.py gate setup              # 门禁：CP1 已 clear
```

concept.md 已在定方向时填好，这里补另外两个文件的内容（骨架已由 book_init 生成，只填内容）：

1. `worldbuilding.md`：**结构化世界观**，按 `{SKILL_DIR}/references/worldbuilding-schema.md` 填——先写自由叙事（力量体系 / 时代背景 / 社会势力，人读），再填「## 硬规则清单」和「## 能力白名单」两张表（脚本读，用于离奇判定；硬规则类型限 `禁止/上限/唯一`，能力白名单四列 `能力名/类型/等级/归属`）。**后续剧情要打破硬规则时，不用回来改表**：在当章事务的 `rule_overrides` 登记（理由+代价），账本自动记入 `tracking/overrides.md`
2. `reader-contract.md`：核心期待 + 兑现方式 + 红线 + 主角代理权（四节模板填内容）

`题材卡.md` 已由 book_init 按题材自动拷贝；没匹配到卡时（脚本已写「自创题材，无对应卡」占位）跳过。

文风不写在这里——作者级文风锚在 `.novel/style-anchor.md`（跨书复用）；对标拆书文风样本在 `deconstruct/{书名}/文风.md`（analyze 支线产出）。

```
pipeline.py advance setup    # 标记 setup done，进入 outline
```

### 第 6 步：校验

```
python3 .../validate.py --root-dir {根目录} --book my-book
```

## 目录结构

```
{写作根目录}/
├── .novel/                      # 作者级资产（一次，跨书）
│   ├── preferences.md           #   作者偏好（写作模式/调研偏好/习惯）
│   ├── style-anchor.md          #   文风锚
│   ├── writing-playbook.md      #   技法库（妙处/问题/文风技法，跨书沉淀）
│   ├── templates/               #   模板库（6 个：concept/reader-contract/worldbuilding/character-card 详卡/character-card-simple 简卡/pacing）
│   ├── banned-words.txt         #   禁用词
│   └── active.md                #   入口：当前书
└── {slug}/                      # 书级（每本书）
    ├── concept.md               #   作品定位（定方向产出：概要/冲突/主题/开篇钩子）
    ├── reader-contract.md       #   读者契约
    ├── worldbuilding.md         #   世界观
    ├── 题材卡.md                #   题材卡（从 genre-prose-cards 匹配拷入）
    ├── characters/ outline/ chapters/ reviews/
    ├── tracking/                #   状态账本（tracking_commit 生成，禁止手改）
    │   ├── _tracking-state.json #   唯一权威
    │   ├── context.md  foreshadows.md  overrides.md（设定演进账本）
    │   ├── characters/  timeline/  chapter-deltas/
    │   └── pacing.md            #   节奏（手写）
    └── .story/                  #   流程状态
        └── pipeline.json        #   5 步状态机
```

## 失败分支

- `setup.py` 报错 → 检查 `--root-dir` 是否正确、目录是否有写权限
- `new.py` 报错 → 检查 slug 是否英文、书目录是否已存在（已存在用 `--force` 补建）
- `validate.py` 报错 → 看缺哪个文件，补上再校验
- 定方向用户「不确定」→ 走「没头绪，扫榜推荐」分线（读 `{SKILL_DIR}/skills/branch/story-long-scan/SKILL.md` 执行，多引擎搜榜单），给候选。**⚠️ 扫榜必须委派 `subagent_minimax`（M3 长文）或走 `search` 技能；主线程禁止自己 web_search/web_fetch 裸搜——番茄/头条有 cross-origin redirect 反爬，裸抓必撞墙且白烧 token。**

## 铁律（不要做什么）

- ❌ 顺序不可颠倒：先建骨架（通用资产），再定方向（具体故事）
- ❌ 作者级资产 `.novel/` 只建一次；开新书不重复建文风/模板/偏好
- ❌ 定方向不一次问一堆问题（每次只问一个，选择题优先）
- ❌ 蓝本未经用户确认不往下走
- ❌ 文件系统路径用中文（一律英文，中文书名写进 `--title`）
