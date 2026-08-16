---
name: novel-writer
description: |
  小说写作流水线（编排层 + 5 步主线 + 6 支线，模块化，通用为主、平台可选）。脚本门禁 + 状态账本 + 冷读裁判。
  触发词：写小说、开新书、写网文、写个都市文、写个玄幻、写大纲、继续写、写下一章、改一下第X章、扫榜、什么题材火、帮我看看最近什么火、长篇/短故事什么火、起点排行、去AI味、这篇太AI了、拆书/拆文/分析黄金三章、查一下设定、XX角色现在什么状态、伏笔F2埋了什么、主角境界到哪了、记住这个写法、这个钩子很有效、这个妙处记下来、这章的坑记一下、润色第X章、这章读着不通、句子不通顺、修病句、改稿、归档、本章完成、验收、进下一章、剧情爆破、太平了、不够炸、来点狠的、上强度、Save the Cat、15 节拍、故事母型、改大纲、大纲要调、换地图、砍支线、人物下线、剧情调整。
  流程：主线 init → outline → draft → revise → archive（脚本硬校验 + 冷读裁判内嵌 draft，revise 条件触发）；支线 story-{long-scan 扫榜, long-analyze 拆书, deslop 去AI味, query 查询, learn 记忆, polish 润色修病句} 按请求路由。
  子技能是包内 skills/{mainline,branch}/ 下的 SKILL.md 文件，按路由用 Read 工具只读当前那一个，不预读全部。
  NOT for：代码实现审查（→ code-review-checklist）；技能评估打分与优化（→ darwin-skill）。主线单环节（写大纲/写正文）也走本技能路由。
---

# novel-writer · 小说写作（编排层）

> **脚本当导演，agent 当演员。** 本 skill 是编排层，只做三件事：读状态机 → 路由到对应子技能 → 门禁把关。
> 每一步的详细指令在 `skills/mainline/novel-{step}/SKILL.md` 里，别把步骤指令写在编排层。

## 脚本路径约定（重要）

脚本在本 skill 目录的 `scripts/` 下，**不在小说项目目录里**。agent 运行时 cwd 是小说项目目录，调用脚本要用绝对路径。

**`{SKILL_DIR}` 是占位符**，表示本技能根目录，**一律以 skill 工具加载本技能时注入的 Base directory 为准**，不要猜路径、不要在文档里写死任何机器的路径。脚本内部已全部自定位（`Path(__file__).resolve().parent`），换机器、换路径零改动。

```
python3 {SKILL_DIR}/scripts/pipeline.py status
python3 {SKILL_DIR}/scripts/tracking_commit.py check --project .
```

小说项目目录由脚本从 cwd 向上自动定位（找 `.story/`），agent 只需 cd 到小说项目目录再调脚本。

## 术语速查（骨架词一次讲清，别让读者猜）

- **状态账本**：一本只能往后写、不能涂改的流水账。`tracking/_tracking-state.json` 是原件，context.md/foreshadows.md 等是它自动算出的副本；想改必须提交一笔 JSON 事务（说清改了什么），脚本校验通过才落账。手改副本=账本作废。
- **闸门/门禁/gate**：三个词指同一套「脚本挡住不许往下走」机制。`gate`=入口检查（顺序锁：上一步没完成不放行；文件锁：必需文件不在不放行）；`advance`=出口质量校验（字数/去AI味/语病/履约等 checks）。统称门禁。
- **冷读**：让一个从没看过你大纲/设定/蓝图的「普通读者」（独立子代理）来读正文评分，防止带着作者记忆脑补正文没写出来的东西。四维评分（翻页欲/认知负荷/共情验证/节奏感受）+ 红线标签 6 项（机械降神/无后果/崩人设/误会驱动/工具人/说教，标「有」须贴原句，随评分提交作者）。
- **离奇判定**：脚本核对正文有没有用出 worldbuilding 硬规则清单（禁止/上限/唯一）与能力白名单之外的设定；用了且没在 rule_overrides 登记就卡住。
- **风格基线**：把正文的视角/腔调/禁用语与 .novel/style-anchor.md 逐条对照算出的偏离度，偏了软警告。
- **stale**：拿旧版本号提交事务会被拒（expected_state_revision 对不上），防两人/两次改动互相覆盖。
- **履约清单**：spec 里大纲要点的逐条勾选框，脚本校验勾选率 ≥80%。

## 铁律（全局，所有子技能遵守）

1. 每一步前先跑 `pipeline.py gate <step>`，exit 1 就不能做
2. 每一步完成后跑 `pipeline.py advance <step>`
3. 检查点必须等老板 `checkpoint clear`，不等确认 = 卡死，不许绕
4. 状态账本 `tracking/_tracking-state.json` 由 tracking_commit 维护，agent 只提交 JSON 事务，绝不手改
5. 步骤详细指令只写在各子技能 SKILL.md，编排层不重复

## 状态机 + 子技能路由

| 步骤 | 子技能 | 进入条件 |
|---|---|---|
| 1. init | `skills/mainline/novel-init` | 未初始化（无 `.novel/` 作者级资产，或无 `.story/pipeline.json`） |
| 2. outline | `skills/mainline/novel-outline` | setup 已 done |
| 3. draft | `skills/mainline/novel-draft` | outline 已 done（含脚本校验 + 冷读裁判） |
| 4. revise | `skills/mainline/novel-revise` | 冷读打回才走（否则 skip） |
| 5. archive | `skills/mainline/novel-archive` | draft done + revise done/skipped |

## 目录结构（两层）

```
{写作根目录}/
├── .novel/           # 作者级资产（init 一次，跨所有书复用）
│   ├── preferences.md  style-anchor.md  writing-playbook.md（技法库）
│   ├── templates/  banned-words.txt  active.md
└── {slug}/           # 书级（每本书）
    ├── concept.md  reader-contract.md  worldbuilding.md  题材卡.md
    ├── outline.md  chapters/chapter-NNN/{spec,draft,review}.md  reviews/
    ├── tracking/    # 状态账本（tracking_commit 生成，禁止手改）
    │   ├── _tracking-state.json（唯一权威）  context.md  foreshadows.md  overrides.md
    │   ├── characters/  timeline/  chapter-deltas/
    │   └── pacing.md（节奏，手写）
    └── .story/       # 流程状态
        ├── pipeline.json（5 步状态机）
        └── quality-trend.json（冷读趋势）  tx-*.json（事务草稿）
```

技能目录内通用层/特定层划分与规则数据格式见 `references/architecture.md`。

## 进入流程（每次触发第一步，固定序列，不可协商）

1. 执行且**只执行**这一条命令判定现状：
   ```
   python3 {SKILL_DIR}/scripts/pipeline.py status
   ```
2. 按 status 输出路由（status 自动向上找 `.story/`，无需手动确认目录）。子技能是本 skill 包内的 SKILL.md 文件，用 **Read 工具**读对应文件并按其指令执行（文件路径均相对 skill 根 `{SKILL_DIR}/`）：
   - 输出「不在任何项目」→ 读 `skills/mainline/novel-init/SKILL.md`
   - 输出含步骤列表 → 看哪个步骤是 `pending`，读对应子技能：
     setup→`skills/mainline/novel-init/SKILL.md`、outline→`skills/mainline/novel-outline/SKILL.md`、draft→`skills/mainline/novel-draft/SKILL.md`、revise→`skills/mainline/novel-revise/SKILL.md`、archive→`skills/mainline/novel-archive/SKILL.md`
   - 支线请求不查状态机，直接读对应支线子技能：
     扫榜→`skills/branch/story-long-scan/SKILL.md`、拆书/拆文→`skills/branch/story-long-analyze/SKILL.md`、去AI味→`skills/branch/story-deslop/SKILL.md`、查设定→`skills/branch/story-query/SKILL.md`、记住写法→`skills/branch/story-learn/SKILL.md`、润色/修病句→`skills/branch/story-polish/SKILL.md`、改稿/改一下第X章→`skills/mainline/novel-revise/SKILL.md`（主动改稿；冷读打回也走它）、改大纲/大纲要调/换地图/砍支线/人物下线→`skills/mainline/novel-revise/SKILL.md`（大纲修订模式，先跑 outline_revise.py 冲突检测）
     消歧：「润色第X章」=通顺度（polish）；「去AI味」=AI 味（deslop）；「改一下第X章」=剧情/结构修订（novel-revise）；「改大纲/换地图/砍支线」=大纲修订模式（novel-revise）。别混。
   - 每章写稿前先跑 `python3 {SKILL_DIR}/scripts/chapter_flow.py status --project {书目录}` 拿剩余步骤命令清单，照着跑，不用记流程
3. 子技能执行完，回到第 1 步（再跑 status）看下一步。

### 反例黑名单（绝不执行）

- ❌ 不预读全部子技能 SKILL.md——按路由用 Read 工具只读当前那一个
- ❌ 不在 status 前 ls 技能目录、ls 项目目录、find `.story`/`.novel`
- ❌ 不预先读 `.novel/` 下的文件——作者资产由子技能自己读
- ❌ 不并行执行多个子技能——串行，一次一个

现状由 `pipeline.py status` 判定，路由由上表决定，不存在需要「探查」才能知道的信息。

### 失败分支

- status 报「状态文件损坏」→ 提示用户 `.story/pipeline.json` 损坏，用 `pipeline.py init` 重建
- status 报「不在任何项目」但用户想续写 → 确认 cwd 是否在书项目根（含 `.story/` 的目录），不在则 cd 过去
- 读子技能 SKILL.md 报错/内容异常 → 回到第 1 步重跑 status 确认状态，不重复读同一文件

## 轻量模式（短篇/续写/微调，按需跳过）

完整流程面向长篇连载。以下场景按需精简，但**状态机与门禁仍照跑**（status 判定 + checks.py 校验不因轻量而豁免）：

| 场景 | 触发示例 | 走哪些 | 跳过哪些 |
|---|---|---|---|
| **短篇** | 「写个短篇，都市灵异」 | init → outline → draft → polish → archive | long-analyze（拆书）、完整 revise 循环；outline 用 `scaffold_outline.py` 轻量骨架 |
| **续写** | 「继续写第 N 章」 | draft → revise（条件）→ archive | init / outline（前提：`.story/` 与账本已就绪） |
| **微调** | 「改一下第 3 章结尾」 | revise（精准改，不跑完整 revise 循环） | 完整 revise 循环、re-review |

**前置条件**（不满足则回退完整流程）：
- 短篇：用户已给题材 + 平台（或「没想好」则先走 long-scan）
- 续写：`status` 显示项目存在且 outline 已完成
- 微调：目标章节草稿已存在

**轻量模式仍遵守**：子技能串行执行、评分标准、`checks.py` 门禁（draft/archive 校验不豁免）。

## 脚本速查

| 脚本 | 命令 | 用途 |
|------|------|------|
| `scripts/pipeline.py` | init / status / wordcount / gate / advance / checkpoint clear / next-chapter | 流程门禁 + 状态机（next-chapter 只重置 draft/revise/archive，setup/outline 全书只做一次；status 附带冷读质量趋势） |
| `scripts/tracking_commit.py` | init / commit / check | 状态账本（唯一权威 JSON + 派生视图，含设定演进账本 overrides.md） |
| `scripts/gen_transaction.py` | init / commit [--revision] | 事务生成器：读状态机+账本自动产出事务初稿（修订号/约束/快照自动带入），agent 只改变化部分 |
| `scripts/checks.py` | draft / archive / wordcount / deai / verify | 确定性校验（字数软硬线+趋势拦截、履约清单≥80%、离奇判定、风格基线、未登记说话人） |
| `scripts/quality_trend.py` | record / show | 冷读质量趋势：每章四维分数落盘，status 显示近 5 章均分与红黄绿标记 |
| `scripts/assemble_spec.py` | --chapter N | 章节蓝图组装：大纲要点/角色/前情/知情边界/时间线/伏笔/题材/风格从账本+大纲+锚自动填，AI 只补判断项 |
| `scripts/scaffold_outline.py` | --project | 大纲骨架：按篇幅自动算章数，生成每章四字段框架，AI 只填内容 |
| `scripts/characters_pool_generator.py` | --project | 三维人物盘点：势力 × 时代 × 家族矩阵 + 决策列，产出 characters-pool.md（outline 第 1.5 步，硬门禁） |
| `scripts/migration_upgrade.py` | --project [--apply] | 人物卡一次性回炉：自动判定详/简、详卡补个人故事四件套骨架、简卡压缩，产出 migration-report.md（存量书升级用） |
| `scripts/outline_revise.py` | --project [--from-chapter N] | 大纲中途修订冲突检测：伏笔对账 + 章节冲突 + 人物下线，产出 outline-revision-report.md（novel-revise 大纲修订模式） |
| `scripts/outline_drift.py` | --project [--window N] | 大纲-正文漂移检测：最近 N 章履约勾选率 + 章尾钩子，产出 outline-drift-report.md（挂 novel-archive 步骤 1） |
| `scripts/book_init.py` | --root-dir … --slug … | 书级初始化批量骨架生成器（init 子技能调用，生成书目录全部确定性骨架） |
| `scripts/extract_chapters.py` | 文件路径 | 章节边界识别（story-long-analyze Stage 0 的确定性部分） |
| `scripts/export_book.py` | --project | 合成出书：串全部章节成单文件（挂 novel-archive 步骤 5，仅最后一章） |
| `scripts/polish_apply.py` | 输入文件 | 病句批量替换（story-polish 支线的落盘动作） |
| `scripts/check_spec_copy.py` | --chapter N | 细纲照搬检测（spec 与大纲原文重合度，防 AI 偷懒照抄章纲） |
| `scripts/coldread_material.py` | --chapter N [--write-review] | 冷读材料：原文切片+速记+评分提示词的干净上下文拼装 |
| `scripts/story_query.py` | 多种查询 | 查设定 CLI：角色/伏笔/时间线/上下文/overrides/逐章记录/项目模式记忆/关键词搜索，脚本出结果 |
| `scripts/platform_review.py` | --chapter N / --book | 平台审稿（确定性）：敏感词/连接词密度/句长突发性扫描 + 四类低质红线自检入口 |

## 状态账本（tracking_commit，draft / revise 共用）

写完一章，提交 JSON 事务驱动状态账本（完整协议见 `references/tracking-transaction.md`）：

- `_tracking-state.json` 是唯一权威；`context.md` / `foreshadows.md` / `overrides.md` / `characters/` / `timeline/` 全是派生视图，禁止手改
- 事务含 `delta`（本章变化 + `new_abilities` 能力声明 + `rule_overrides` 规则突破登记）+ `context`（position + long_term_constraints/active_character_names/continuity_risks 三个列表字段）+ `character_snapshots`（核心角色快照）
- 提交前先 `check` 拿 `state_revision` 填 `expected_state_revision`（对不上被拒，防 stale）
- 时间线分「作者真相 / 读者已知」双视图——写清楚读者此刻知道什么，防信息泄露
- 打破 worldbuilding 硬规则必须登记 `rule_overrides`（理由+代价），记入 `tracking/overrides.md`，防长篇「吃书」
- **证据锚定**：设定/伏笔挂 `source_chapter` 证据位置 + immutable/adaptable/open/conflicted 四类边界；场景/道具状态走 `active_scene` 锚点（协议见 tracking-transaction.md 末两节）
- 具体字段和示例见 `skills/mainline/novel-draft/SKILL.md` 第 4 步

## 检查点

仅 **CP1（选题确认）** 保留人工把关：init 完成后 `pipeline.py checkpoint clear cp1` 才进 outline。

CP2（大纲）、CP3（每章）**已废弃**——由质量闸门（`checks.py` 的 outline/draft/archive 校验）自动把关，不再等人工确认。

## 题材与文风（全局资源）

**平台**：通用小说不绑平台；写网文可选番茄/起点/知乎/七猫/晋江（选了才用 word-count.json 字数标准）。

**题材**（三种来源）：用户指定 / 扫榜推荐（story-long-scan 分线：没头绪时自动触发，产出 topic-decision）/ AI 推荐。选定后从 genre-prose-cards 匹配 1 张题材卡拷入书目录 `题材卡.md`，大纲与每章 spec 摘用。

**文风**（三个来源）：
1. 作者级文风锚 → `.novel/style-anchor.md`（novel-init 建立，跨书复用）
2. 对标拆书 → `skills/branch/story-long-analyze`（方法论对照查 `references/writing-methods/INDEX.md` 索引）（拆书提炼文风，留 deconstruct/{书名}/文风.md，novel-draft 按需读）
3. 作家文风 DNA 库 → `references/author-styles/author-dna.md`（金庸/古龙/辰东等 9 位，含原文样本+结构公式+禁区+叠加规则；动作/战斗段按需参照，如金庸「对话短→动作长→结果短」三段式）

## 资产索引

| 能力 | 资产 | 来源 |
|------|------|------|
| 状态追踪 + 设定演进 | `references/tracking-transaction.md` + `scripts/tracking_commit.py`（含 overrides 账本） | oh-story + webnovel-writer 借鉴 + 本技能 |
| 大纲履约 | `scripts/new_chapter.py`（spec 履约清单）+ `scripts/checks.py`（≥80% 校验） | webnovel-writer「大纲履约校验」借鉴 |
| 编辑自检 | `references/editor-checklist.md`（六条） | rubric 14 维精简 + ai-fiction-writer |
| 工艺总纲 | `references/craft-canon.md`（特质 10 条 + 红线 12 条，审美层判据） | 本技能（挂 revise 必过 + draft 写前对照 + 冷读参考） |
| 架构分层 | `references/architecture.md`（通用层/写作特定层/check-rules 格式/扩展方式） | 本技能 |
| 通用检查引擎 | `scripts/check_engine.py` + `references/check-rules/*.json`（规则数据驱动，改规则不改代码） | 本技能（领域无关，可复用于其他领域技能） |
| 冷读趋势 | `scripts/quality_trend.py` | ai-fiction-writer humanizer 借鉴 |
| 平台审稿 | `references/platform-review.md` + `scripts/platform_review.py` | 番茄官方低质治理公告 + 公开实战分析 |
| 连续性 advisory | `scripts/check_continuity.py`（伏笔过期/无主、疑亡又活跃、硬规则突破） | 本技能（挂 novel-archive 步骤 1） |
| 全书收尾 | `scripts/book_finish.py`（串 export_book 导出 → 全本审稿 → 终检 → 趋势） | 本技能（挂 novel-archive 步骤 5，仅最后一章） |
| 文风画像 | `scripts/style_profile.py`（story-long-analyze 包内 SOP：style-profile-generator.md） | 本技能 |
| 作者技法库 | `.novel/writing-playbook.md` + `scripts/learn.py --scope author` | 本技能（跨书沉淀：妙处/问题/文风技法） |
| 字数标准 | `references/word-count.json` | 本技能 |
| 防跳步门禁 | `scripts/pipeline.py`（四把锁） | 本技能 |
| 作家文风 DNA | `references/author-styles/author-dna.md`（9 作家 + 叠加规则 + 自定义蒸馏 7 步） | writing-legacy 备份（yeyue 工作区） |

**知识库归属（决策 11，主线融入版）**：`references/writing-methods/`（34 份方法论，召回先查 INDEX.md）与 `references/genre-prose-cards/`（32 题材卡）是**分线知识**，但已挂到主线固定节点：题材卡→init 定方向后拷入书目录；大纲方法论→outline 阶段按需加载；写作技法→draft 阶段按需加载（先查 INDEX 再 Read 单份）；拆书/扫榜→init 定方向时自动触发。写正文阶段仍**默认不加载**（只读 spec），保持主线上下文精简；缺合适内容则走「搜 + 蒸馏」补充。
