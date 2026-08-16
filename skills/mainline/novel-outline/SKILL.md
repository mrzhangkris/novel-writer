---
name: novel-outline
description: |
  小说大纲：写 outline.md（章纲 / 结构标记 / 伏笔规划）。novel-writer 流水线第 2 步。
  触发词：写大纲、列章纲、规划结构、设计伏笔、剧情爆破、太平了、不够炸、来点狠的、上强度、爆一下剧情、Save the Cat、15 节拍、故事母型。
  依赖：pipeline.py gate outline / advance outline。
---

# novel-outline · 大纲（第 2 步）

> novel-writer 流水线第 2 步。把契约 concept.md 展开成可逐章执行的章纲 + 伏笔规划。

## 脚本路径

```
{SKILL_DIR}/scripts/pipeline.py        # gate / advance
{SKILL_DIR}/scripts/scaffold_outline.py # 大纲骨架（按篇幅自动算章数）
```

## 前置门禁

```
pipeline.py gate outline    # 顺序锁：setup 必须 done；文件锁：concept.md 必须存在
```

exit 1 就停下，先完成上一步（setup）。

## 执行步骤

### 1. 读契约

先读 `concept.md`（卖点/核心冲突）+ `worldbuilding.md`（硬规则），大纲必须服从契约，不得冲突。

### 1.5. 三维盘点（强制，硬门禁）

**这一步不许跳过**——直接决定后面建多少张卡，也是「漏识别该建卡的人」的根治手段。

**先跑盘点脚本**：

```
python3 {SKILL_DIR}/scripts/characters_pool_generator.py --project {书目录}
```

脚本读取 `concept.md`（核心冲突、势力、家族）+ `worldbuilding.md`（硬规则/觉醒/血脉）+ `characters/`（已有卡名），自动产出 `{书目录}/characters-pool.md`——一份**势力 × 时代 × 家族**三维盘点矩阵：

```
| 维度 | 已识别 | 应有人物 | 已有卡 | 缺卡 |
| 势力 1（纪末会） | 5 个执行位 | 7 个（主席 + 副会长 + 技术总监 + 3 基层 + 孤儿院系统） | 3 张 | 4 张 |
| 时代 1952 | 大雾事件遗孤 | 12 个（孤儿 + 孤儿院系统 + 国师谱系） | 5 张 | 7 张 |
| 家族 陈家 | 司时投机派 + 守旧派 | 4 代 × 2 派 = 8 个核心 + 6 旁支 | 2 张 | 12 张 |
| ... |
```

agent 据此**人工盘点**「该有人物」格子——逐格判断：
- **建详卡**：与主角/详卡有直接关系网
- **建简卡**：出场 2-3 场 / 影响 1 个核心事件 / 见证者
- **不建卡**：纯龙套（一次性提到、无姓名/无台词）
- **合并**：某格子人物与另一格子人物重合（如反派手下与孤儿院基层），合并到一张卡

agent 盘点结果写回 `characters-pool.md`：把每行决策列的 `_待盘点_` 占位符替换为实际决策（`建详卡` / `建简卡` / `不建卡` / `合并到X`）。

**门禁**：`advance outline` 校验 `characters-pool.md` 存在 + **每个格子都有决策**（决策列非空）。缺决策 = 卡住，不许往下走。

### 2. 建人物卡（双层卡：详卡 + 简卡）

**先读方法论**：`{SKILL_DIR}/references/writing-methods/character-design-methods.md`（三层标签反差人设法、配角功能化设计、**双层卡设计**、立体 vs 扁平人物），按需再读 `character-basics.md` / `character-relations.md`。

按 1.5 步盘点结果建卡，写入 `{书目录}/characters/{角色名}.md`：

- **详卡**（与主角/详卡有直接关系网）→ 模板 `.novel/templates/character-card.md`
- **简卡**（边缘出场、功能单一）→ 模板 `.novel/templates/character-card-simple.md`

**详卡必填三件套**（checks.py outline 校验非空）：
1. 核心性格：≤3 个词，每个词配一条 TA 的行为示例
2. 动机与目标：长期目标 + 当前目标
3. 底线与恐惧：底线（TA 绝不做的事，OOC 试金石）+ 恐惧/软肋

**详卡必填个人故事四件套**（checks.py outline 校验非空，**这是「每个人物都有自己故事」的强制机制**）：
1. 出身与来处
2. 关键转折
3. 未了的执念
4. 独处时的样子

**简卡必填两项**（checks.py outline 校验非空）：
1. 基本信息（含一句话功能 + 标记标签）
2. 与详卡的关系（至少 1 条）

通用纪律（详卡简卡都适用）：
- 卡只记**静态不变量**——无论剧情怎么走都不该变的东西；当前处境/伤势/能力变化写 tracking 快照，不写进卡
- 关系网两两对账：A 卡里写与 B 的关系，B 卡里要有对应（或至少一方写明旧账）
- 关系网对账后，自动识别「详卡 ↔ 详卡」关系——这些角色全部锁详卡，不能降为简卡

**升级机制**：简卡角色若后续在剧情中与详卡建立直接关系（师徒/仇人/血脉），agent 应**升级为详卡**（重命名 + 切换模板 + 补个人故事四件套）。

### 3. 写 outline.md

**先让脚本搭骨架**（章数按 concept 篇幅 ÷ 平台每章字数自动算，AI 不数章数、不写重复框架）：

```
python3 {SKILL_DIR}/scripts/scaffold_outline.py --project {书目录}   # 已存在则拒绝覆盖
```

**写章纲前先答三根问题**（vibe-noveling novel-plan 吸收；答不上就停下补设定，不硬写）：

1. 这一章为什么必须存在？跳过它读者损失什么？
2. 本章的本质变化是什么（起→止的具体变化）？
3. 主角的牛逼体现在哪（本章给了他什么主动推动局面的机会）？

然后在 `outline.md` 骨架里填写六块内容（第 0 块由 scaffold 生成，其余五块为原骨架）：

0. **总纲**（scaffold 已生成空框）：一句话主线（谁，想做什么，遇到什么阻碍，最终如何）+ 结构划分 + 关键转折点表 + 结局锚点。这是主题统一的锚——写正文时不断回看，防跑偏。
1. **章纲**：逐章列「本章目标 / 关键事件 / 章尾钩子 / 新概念」。章数按 `concept.md` 的目标篇幅推算（总字数 ÷ 每章字数）。
2. **结构标记**：标注起承转合、高潮点、卷/幕分界，让节奏可见。长篇标全书 beat 落点与分卷职责（三层用法见 save-the-cat-beats.md：全书层完整 15 beats / 分卷层 6 问 / 章节层 1 主 1 副职责），不每章硬套。
3. **情绪曲线**：按章列出情绪高低点（如 第1章紧张→第4章温情→第9章冲击→第14章爆点），保证「松-紧-松」呼吸感（脚本只提示缺失，不拦截）。**同步填 `tracking/pacing.md`**：全书节奏蓝图（高压/推进/呼吸/低压分级），与情绪曲线对齐，draft 时按章回看。
4. **伏笔规划**：列出计划埋设的伏笔（编号 F1、F2…），每条标注「埋设章 / 计划回收章 / 类型」。
5. **概念预算**（防信息倾泻）：每章标注「引入的新概念」——第一章 ≤3 个，后续每章 ≤2 个（可以为 0）；优先深化已引入的概念，而非引入全新概念。

**写大纲前，按需加载方法论**（分线知识，只读当次要用的，不整库加载）：

- 章纲节奏 → `{SKILL_DIR}/references/writing-methods/outline-rhythm.md`（起承转合比例、章间钩子）
- 情绪曲线 → `{SKILL_DIR}/references/writing-methods/emotional-arc-design.md`
- 核心冲突 → `{SKILL_DIR}/references/writing-methods/outline-conflict.md`
- 卖点与大结构 → `{SKILL_DIR}/references/writing-methods/commercial-core-methods.md`（按需）
- 全书节奏蓝图/故事母型 → `{SKILL_DIR}/references/writing-methods/save-the-cat-beats.md`（15 节拍三层用法 + 10 母型；长篇结构标记时按需，不每章硬套）
- 剧情太平/冲突不够 → `{SKILL_DIR}/references/writing-methods/plot-booming.md`（剧情爆破器：10 套走向 + 结构改写验证）
- 题材写法 → 书目录 `题材卡.md`（init 时已拷入，题材禁忌与爽点落到章纲里）
- 以上没覆盖到的主题（开篇设计/悬念编排/反转工具箱等）→ 先查 `{SKILL_DIR}/references/writing-methods/INDEX.md` 匹配再 Read 单份，不整库预读

### 4. 推进（质量闸门）

```
advance outline    # 自动跑 checks.py outline（章节条目 + 伏笔规划 + 概念预算 + 人物卡 + 三维盘点），不过就卡住
```

## 失败分支

- `gate outline` 报「setup 未完成」→ 回 novel-init 完成 setup
- `advance outline` 报「大纲不合格」（缺章节/伏笔/概念）→ 补上缺失部分，重跑 advance
- `advance outline` 报「人物卡缺失/字段未填」→ 按步骤 2 补卡（详卡：长期目标 + 底线 + 个人故事四件套；简卡：基本信息 + 与详卡关系），重跑 advance
- `advance outline` 报「characters-pool.md 缺失/格子无决策」→ 跑步骤 1.5 盘点脚本 + 人工盘点决策列，重跑 advance

新增校验项（v2）：
- `characters-pool.md` 存在 + 每个格子都有决策（硬门禁）
- 详卡个人故事四件套非空（硬门禁）
- 详卡/简卡分层与关系网对账一致（硬门禁）

## 铁律（不要做什么）

- ❌ 不写与契约冲突的大纲（卖点/核心冲突对不上）
- ❌ 伏笔规划不写死细节（留 draft 发挥空间），但「埋哪、收哪」必须清晰
- ❌ 大纲与契约冲突时，改大纲，不改契约
- ❌ 不手改 pipeline.json / tracking 账本
- ❌ 人物卡写动态处境（当前伤势/位置/心情）——动态归 tracking 快照，卡只记静态不变量
- ❌ 龙套建卡——预计复用 ≥2 场、影响主线的才建卡

## 章纲信号纪律（plot-signal-vs-spoiler 吸收）

大纲/章纲是给**作者**的执行指令，不是给读者的预告：
- 写「王强深夜打来电话，语气反常」——不写「这通电话暴露了王强是内鬼」；
- 写「陈默在抽屉里发现半张旧照片」——不写「这张照片将揭晓他的身世」；
- 禁止把读者反应（读者此刻会紧张/心疼）、后期反转、伏笔答案写进章纲。

**大纲级 AI 味检查**（vibe-noveling planning-checks 吸收）：否定排比（不 X，不 Y，不 Z）改正面陈述；单场景内转折连接词（然而/不过/但是/却）≤1 次；空泛转场（随后/经过一番周折）必须补出谁做了什么才切场。

