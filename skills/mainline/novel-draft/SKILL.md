---
name: novel-draft
description: |
  写正文：创建章节文件夹 → 草稿预审写 spec.md 蓝图 → 只读 spec.md 写 draft.md → 提交 JSON 事务 → 冷读裁判。novel-writer 流水线第 3 步。
  触发词：写正文、写这一章、写下一章、继续写。
  依赖：pipeline.py gate draft / advance draft、tracking_commit.py commit / check。
---

# novel-draft · 写正文（第 3 步）

> novel-writer 流水线第 3 步。每章一个文件夹（`chapters/chapter-NNN/`），先草稿预审写 spec.md 蓝图，再只读蓝图写 draft.md，提交 JSON 事务，最后冷读裁判把关（独立子代理真冷读）。

## 三段式流程（chapter_flow 批量执行，**权威路径**；下方各节 7 步手动流程是降级/排错参考，与 chapter_flow 冲突时以 chapter_flow 为准）

每章只需 3 个动作，生成类动作全部由 `chapter_flow.py` 批量代跑：

1. **开章**：`chapter_flow.py prepare --project {书目录}`
   → 自动 new_chapter + assemble_spec + 生成 tx 骨架（预填 result/场景/能力/伏笔候选）；AI 只需补 spec 判断项（净变化/五问闸门/勾履约清单）。
2. **写正文**：写 draft.md，**同时**在 tx 骨架里填变化字段（角色变化/时间线/伏笔兑现/退役声明）。动笔前先过：① craft-canon 特质对照——本章主角的**主动选择 + 代价**（`references/craft-canon.md` 第一部分）；② 人物卡底线自检——出场核心角色的行为撞不撞卡上「底线」（`story_query.py --character 角色名` 查静态卡 + 动态快照）；③ 需要技法先查 `writing-methods/INDEX.md` 再读单份，不整库预读。
   **④ 新角色建卡纪律**（写正文时冒出来的角色）：本章首次出现、有名有姓的角色，若预计跨章复用（≥2 场戏或有推进剧情的台词），**当场建卡**——与主角/详卡有直接关系（师徒/仇人/血脉/合作）→ 详卡模板 `character-card.md`；只做见证者/信息提供者 → 简卡模板 `character-card-simple.md`。一次性龙套（无姓名/无台词）不建卡。建卡当场完成，不留到下一章。
   **⑤ 简卡升级检查**：写前自检时若发现某简卡角色本章与主角/详卡建立直接关系（师徒/仇人/血脉/合作），本章写完**立即升级为详卡**（备份原简卡 → 切换详卡模板 → 补个人故事四件套），不留到下一章。
3. **收尾**：`chapter_flow.py finish --project {书目录}`
   → 自动 commit tx → 闸门（字数/去AI味/衔接/履约/风格基线/说教密度/章节定位）→ 生成冷读材料；冷读评分后 `finish --coldread 分1,分2,分3,分4` → 自动记趋势 → revise → archive → 平台审稿 + 连续性检查 → 进入下一章。

`chapter_flow.py status --project {书目录}` 随时查看进度与剩余命令。下面各节是每个动作的展开细节（finish 中断时报错看对应节）。

## 脚本路径

```
{SKILL_DIR}/scripts/chapter_flow.py      # 三段式批量执行器（prepare/finish/status）
{SKILL_DIR}/scripts/pipeline.py          # gate / advance / fail / skip-chapter
{SKILL_DIR}/scripts/new_chapter.py       # 建章节文件夹（章号防呆）
{SKILL_DIR}/scripts/assemble_spec.py     # 蓝图确定性组装
{SKILL_DIR}/scripts/gen_transaction.py   # 事务初稿生成（含 spec 预填）
{SKILL_DIR}/scripts/tracking_commit.py   # 状态账本 init / commit / check（提交后 tx 自动归档）
{SKILL_DIR}/scripts/coldread_material.py # 冷读材料拼装
{SKILL_DIR}/scripts/quality_trend.py     # 冷读分数落盘
```

## 前置门禁

```
pipeline.py gate draft    # 顺序锁：outline done；文件锁：concept.md + outline.md
```

## 章节文件夹

每章一个文件夹 `chapters/chapter-NNN/`（NNN 三位补零），自包含：

```
chapters/chapter-NNN/
├── spec.md    # 草稿预审蓝图（本步阶段 A 产出）
├── draft.md   # 正文（阶段 C 产出）
└── review.md  # 冷读报告（冷读裁判产出）
```

## 执行步骤

### 1. 创建章节文件夹（脚本强制）

写第 N 章前，先跑脚本创建章节文件夹 + spec.md 空蓝图：

```
python3 {SKILL_DIR}/scripts/new_chapter.py --chapter N
```

脚本幂等创建 `chapters/chapter-NNN/`（含 spec.md 空蓝图），已存在则跳过不覆盖。

### 2. 草稿预审（阶段 A：脚本组装 → AI 补判断项）

**先让脚本把确定性部分装好**（抄写是 AI 出错重灾区，全部交给脚本）：

```
python3 {SKILL_DIR}/scripts/assemble_spec.py --chapter N   # 自动填：大纲要点/概念预算/角色要点/前情衔接/知情边界/时间线定位/伏笔指令/题材要点/风格指令
```

然后 AI 只补判断项（写入 `chapters/chapter-NNN/spec.md`）：

| 要点 | 来源 | 提取什么 |
|---|---|---|
| 大纲要点 | `outline.md` 本章条目 | 本章目标 / 场景安排 / 关键事件 / 章末钩子（**履约清单**，写完勾 `[x]`，脚本校验 ≥80%） |
| 概念要点 | `worldbuilding.md` + `concept.md` | 本章引入/深化的设定，标注「引入/深化」+ 来源 |
| 角色要点 | `tracking/characters/{名}.md` + `tracking/context.md` | 出场角色当前状态（位置/能力/关系） |
| 前情衔接 | `tracking/context.md` 近三章速记 | 上章结尾状态（伤势/情绪/位置必须延续） |
| 知情边界 | `tracking/timeline/reader-known.md` | 读者已知/不知什么——防止作者视角泄露 |
| 时间线定位 | `tracking/context.md` | 本章故事时间 + 距上章间隔 |
| 伏笔指令 | `tracking/foreshadows.md` | 本章要植入/推进/回收的伏笔 |
| 题材要点 | 书目录 `题材卡.md` | 摘本章相关的 2-4 条（题材禁忌/爽点/禁止漂移） |
| 风格指令 | `.novel/style-anchor.md` | 视角 / 腔调 / 禁止 |

spec.md 结构（`new_chapter.py` 自动生成模板，含履约清单 + 知情边界 + 时间线定位）：

```markdown
# 第 N 章写作蓝图

## 大纲要点（履约清单，逐条勾选）
- [ ] 本章目标：
- [ ] 场景安排：
- [ ] 关键事件：
- [ ] 章末钩子：

## 概念要点（本章引入/深化，标注来源）
## 角色要点
## 前情衔接
## 本章净变化（状态/信息/关系/资源至少其一，防「水章」）
## 知情边界（读者已知 / 读者不知）
## 时间线定位（故事时间 / 距上章过去）
## 伏笔指令
## 题材要点（本章相关条目）
## 风格指令
## 五问闸门结果
```

### 3. 写作（阶段 C：只读 spec.md → 写 draft.md）

**只读 `spec.md`**，写 `chapters/chapter-NNN/draft.md`。不重新读 concept.md / worldbuilding.md 全文。

遵守：
- 写前五问（爽点硬校验，动笔前先答，答不出重看大纲）：①本章读者期待什么爽点？②爽点在哪个情节点兑现？③兑现前垫了什么情绪？④有没有连续三章同类型爽点（需轮换：打脸/升级/收获/扮猪/揭底/救场）？⑤章末钩子勾住的是什么？（钩子分类：危机钩=命悬一线、悬念钩=信息差未解、渴望钩=目标差一步、情绪钩=关系张力，四类轮换，别连章同型）
- 覆盖 spec.md 大纲要点（脚本硬校验履约率 ≥80%，勾选由 advance draft 检查）
- 本章净变化先答后写：结束时要改变至少一项（状态/信息/关系/资源）
- 写前对照 `{SKILL_DIR}/references/craft-canon.md` 第一部分特质 10 条：本章主角的**主动选择**是什么？**代价**是什么？（答不上就回大纲补，答上写进 spec「角色要点」）
- 人物底线自检：本章每个核心角色的行为撞不撞人物卡「底线」？撞了必须写出动机（`story_query.py --character 角色名` 可查静态卡 + 动态快照）
- 世界观信息只能通过角色行动/对话/观察传达，**禁止旁白讲解**
- 对话比例、段落长度、感官描写自然达标（advance 时的风格基线会提示偏差）

**技法按需加载**（不整库预读）：
- 需要具体技法时先查 `{SKILL_DIR}/references/writing-methods/INDEX.md` 匹配主题，再 Read 单份（钩子→hooks-chapter/hooks-paragraph/hooks-suspense、对话→dialogue-mastery、白描/五感→style-craft、打脸爽点→style-combat-face、反转→reversal-toolkit 等）
- 动作/战斗/对话腔调段按需读 `{SKILL_DIR}/references/author-styles/author-dna.md` 对应作家（9 位文风 DNA；自定义蒸馏 7 步见文件内，速查 `character-distill-quick.md`）

**写完自校三步**（写 draft 后、进闸门前必做——生成时的你记得「想写什么」会脑补正确性，必须换身份重读文本）：

1. **读者身份**：用 Read 工具把 draft.md 从头读一遍（读文件不是回忆），逐句连读两遍，不顺就标；
2. **编辑身份**：对照 spec 的「语病避雷」清单扫一遍定式病句（主语淹没/句式杂糅/多重否定/数量表达/悬空同位语/并列冲突），命中就按「→」后的正解改；发现清单外的新病句模式，先登记到 `{SKILL_DIR}/references/issue-patterns.md` 再改（沉淀给检测脚本补正则）；
3. **收手原则**：只改病句，不顺手改剧情与风格（Self-Refine 纪律：评判与修改分开，一个 pass 只干一件事）；改完跑 `checks.py draft` 复验，开头 500 字逐句精读别放过。

**查设定一律走 story-query CLI**（确定性输出+出处，别用 grep/read 绕过；查询不占写作上下文）：

```
python3 {SKILL_DIR}/scripts/story_query.py --project {书目录} --grep 关键词      # 全文搜
python3 {SKILL_DIR}/scripts/story_query.py --project {书目录} --character 角色名  # 角色当前状态
python3 {SKILL_DIR}/scripts/story_query.py --project {书目录} --foreshadow        # 伏笔表（含状态）
python3 {SKILL_DIR}/scripts/story_query.py --project {书目录} --timeline          # 时间线
```

### 4. 提交 JSON 事务（驱动状态账本）

**首次写第 1 章前，先初始化状态账本**（此时 `tracking/_tracking-state.json` 尚不存在，直接 commit 会被拒）：

1. 用生成器产初稿：`python3 {SKILL_DIR}/scripts/gen_transaction.py init --project {书目录}`（生成 `.story/tx-init.json`，`context.position` 填第 1 卷信息；`character_snapshots`/`foreshadow`/`timeline_events` 可留空，核心角色快照留到第 1 章事务里建）
2. 执行 `tracking_commit.py init --project {书目录} --input {书目录}/.story/tx-init.json`
3. 之后每章只需 commit，无需再 init

写事务 JSON，提交给 tracking_commit（完整协议见 `{SKILL_DIR}/references/tracking-transaction.md`）。**不要手写全量 JSON**：先用生成器产初稿，再改：

```
python3 {SKILL_DIR}/scripts/gen_transaction.py commit --project {书目录}
# 生成 .story/tx-chapter-NNN.json，已按 spec 自动预填：
#   result（关键事件+章末钩子）、场景 scene、new_abilities 候选、
#   foreshadow_changes 候选（本章应收的自动标「已回收」、本章应埋的自动带回收计划）
# 只改变化的部分；候选只删不改；修订已写章节时加 --revision
```

```json
{
  "schema_version": 1,
  "mode": "append",
  "chapter": 10,
  "chapter_title": "…",
  "expected_state_revision": 9,
  "delta": {
    "result": "…",
    "character_changes": [{"name": "…", "change": "…"}],
    "foreshadow_changes": [{"action": "upsert", "id": "F027", "summary": "…", "planted_chapter": 10, "planned_resolution_chapter": 15, "status": "已埋", "importance": "中"}],
    "timeline_events": [{"action": "upsert", "id": "E010", "story_time": "…", "objective_fact": "…", "reader_knowledge": "…", "reveal_status": "已揭示", "reveal_chapter": 10}],
    "constraints": ["…"],
    "next_chapter_commitments": ["…"],
    "new_abilities": ["本章新引入的能力/概念声明"],
    "rule_overrides": [{"rule": "被打破的硬规则原文", "reason": "剧情理由", "effective_chapter": 10, "payback": "代价/收束"}]
  },
  "context": {
    "position": {"volume": "…", "volume_start_chapter": 1, "story_time": "…", "scene": "…"},
    "thread": "沈舟线",
    "long_term_constraints": ["…"],
    "active_character_names": ["…"],
    "continuity_risks": ["…"]
  },
  "character_snapshots": {
    "角色名": {"identity": "…", "location": "…", "goal": "…", "state": "…", "abilities_resources": ["…"], "relationships": ["…"], "knowledge": ["…"], "open_threads": ["…"]}
  }
}
```

关键约束（实战踩坑速查，gen_transaction.py 预填不覆盖，填错会被 tracking_commit 拒收）：
- 提交前先跑 `tracking_commit.py check --project {书目录}` 拿 `state_revision` 填 `expected_state_revision`
- `active_character_names` 里的角色必须有 `character_snapshots` 快照
- **多线叙事必填 `context.thread`**（如「沈舟线」「周晓线」「1952线」，缺省「主线」）：账本按线程自动记录「本线停点」（见 `tracking/threads.md`），切回该线时 assemble_spec 会自动把停点带进 spec「前情衔接」
- `timeline_events` 分「客观事实」和「读者认知」——写清读者此刻知道什么
- `delta.result` ≤ 360 字节（超了压短）；`delta` 总字节 ≤ 1536（超出只警告，但别长期超标）
- `constraints` 只收**字符串**，每条一句（如「王强限今天下班前查出内鬼（周五下班前）」），不收对象
- `character_snapshots` 必须**恰好等于** `character_changes` 里的角色集合：少了报「no current snapshot」，多了报「exactly the core characters」；未出场角色不进 changes 也不进快照
- 旧 `context.continuity_risks` 条目被替换/删除时，必须把**原文逐字**放进 `delta.retired_context_items`，否则报「dropped without being declared」；字符串不全会导致反复拒收
- 正文出现世界敏感词（如「魔法」等 HOSTILE_WORDS）且剧情无意打破硬规则 → 改写掉词面；有意打破 → `rule_overrides` 登记
- 未登记说话人（checks 软警告）：临时龙套可忽略（正文里把「老人」「方姐」类称谓改成角色名可消警）；常驻角色必须进快照+changes，**且当场建卡**（简卡起步，与主角/详卡直接相关则详卡——见写正文第 ④ 条纪律）
- `new_abilities`：本章新引入的能力/概念逐条声明（最多 12 条）
- `rule_overrides`：剧情**打破 worldbuilding 硬规则清单里的规则**时，必须在此登记（rule/reason/effective_chapter/payback），账本记入 `tracking/overrides.md`；未登记的规则突破会在后续被拒收。同一章最多 3 条

```
tracking_commit.py commit --project {书目录} --input {事务.json}
```

### 5. 推进（自动校验）

```
advance draft    # 自动跑 checks.py draft（字数 + 去AI味 + 跨章衔接 + 元标注 + 履约清单 + 离奇判定 + 风格基线 + 未登记说话人），不过就卡住
```

**字数闸门条件速查**（什么条件下哪条线生效）：
- 未选平台（通用）→ 字数闸门整体跳过，其余校验照跑；
- 选了平台×类型 → 目标区间生效：低于硬下限 70% 或超硬上限 130% 硬拦；软区只警告；连续 3 章同软区升级硬拦；
- 若你不确定本书选了哪个平台：先 `pipeline.py status` 看「平台/类型」，别凭感觉卡字数。

**字数不达标（硬下限）→ 卡住，不能进下一章。**（风格基线与未登记说话人是软警告：前者对照文风锚量化基线，后者防随手造龙套） 补足字数再 advance。（字数闸门按平台×类型标准生效；软线只警告，连续 3 章同软区才拦截；通用小说未选平台时该闸门跳过，去AI味/跨章/元标注/履约校验照跑）

### 6. 冷读裁判（写完后，spawn 独立子代理真冷读）

`advance draft` 通过后，**spawn 独立子代理**做真冷读——关键：**干净上下文**，只读正文 + 前情摘要，**不读任何创作蓝图**（concept.md / outline.md / spec.md / worldbuilding.md），防止带着作者记忆脑补正文没写出来的东西。独立子代理是**默认路径**，inline 只是降级。

**inline 降级**（仅当子代理确实起不来时，不得跳过冷读）：

- 调用子代理失败（报错/超时）→ 降级为 **inline 冷读**：以「从未读过本书创作蓝图的冷读者」身份，**只用**「本章开头 300 字 + 章末钩子 + 前情速记」按下方四维评分，**禁止**参考 concept/outline/spec/worldbuilding 与自己写稿时的任何判断
- inline 冷读同样按 ≤2 分分流（打回就走 revise），并在 review.md 首行标注「冷读方式：inline 降级（子代理不可用）」，让作者知道该章冷读置信度低于独立子代理
- 打分时对自己写的稿子**从严且可验证**：每维低于 4 分必须写明「正文哪一句导致扣分」（贴原句）；写不出具体句子就不许扣分，也禁止凭空给 4+ 分

**分级冷读**（降本）：
- 脚本全过、无硬伤 → **轻量冷读**：只给子代理「本章开头 300 字 + 章末钩子 + 前情速记」
- 脚本打回 / 质量存疑 → **全文冷读**：给本章 draft.md 全文 + 前情速记

冷读材料由脚本拼装（保证干净上下文、原文切片，不是 AI 转述）：

```
python3 {SKILL_DIR}/scripts/coldread_material.py --chapter N --write-review
# 生成 review.md：内含开头/章末 300 字原文切片 + 前情速记 + 评分提示词
# spawn 子代理时让子代理读该文件并填写；子代理不可用则 inline 冷读并改首行标注
```

> 前情速记来源：脚本读该章 spec.md 的「前情衔接」历史快照（不是账本当前滚动值——补跑冷读时账本已推进到后文，滚动速记会剧透）。

子代理 prompt 要点（已写入 review.md，逐字传达）：

```
你是冷读者，从未读过本书的创作蓝图（大纲/设定/写作蓝图）。只凭提供给你的正文片段与前情速记，以普通读者视角逐段读，四维度各评 1-5 分并给一句理由：
1. 翻页欲：读完是否想继续？（理想「未解答问题」2-4 个）
2. 认知负荷：信息是否过载？（越低越好；首 500 字 >3 个未铺垫新元素 = 过载）
3. 共情验证：仅凭已读内容，能否一句话概括角色此刻想要什么？概括不出 = 共情失败。
4. 节奏感受：有没有「想跳过这段」或「等等刚才发生了什么」的地方？
```

冷读后把四维分数记入质量趋势（供 `pipeline.py status` 查看，防止逐章放水）：

```
python3 {SKILL_DIR}/scripts/quality_trend.py record \
  --scores {翻页欲},{认知负荷},{共情验证},{节奏感受}
```

然后按结果分流：
- **无 ≤2 分** → `pipeline.py skip revise`（跳过修改，直接进 archive）
- **有 ≤2 分** → 走 revise（见 novel-revise），改完回冷读重审

### 7. 失败处理（自动修复循环 + 熔断）

`advance draft` 被校验锁拒绝时，按以下循环自动处理：

1. 读校验失败信息，**针对性修复**（字数不够补写、去AI味重跑、跨章重复改开头、元标注清理）
2. 修复后重跑 `advance draft`
3. 仍失败 → `pipeline.py fail` 记录一次，回到第 1 步继续修
4. `fail` 提示「进入第 N 轮重写」→ **舍弃本章**，重新走「写这一章」流程（从草稿预审写 spec.md 开始）
5. `fail` 提示「已重写 3 轮仍失败」→ `pipeline.py skip-chapter` 标记失败章，进下一章

书尾汇总失败章：`pipeline.py failed`（列出所有失败章，供人工补写）。

## 铁律

- 每章先创建章节文件夹，再草稿预审写 spec.md，再只读 spec.md 写 draft.md。
- 写作阶段**只读 spec.md**，不重新读全文设定（防信息倾泻）。
- spec 的履约清单勾选率必须 ≥80%（脚本拦截）；写正文时调整了计划要回 spec 改勾选并注明，不删条目。
- 本章必须改变至少一项（状态/信息/关系/资源），spec 的「本章净变化」先答再写，防「水章」。
- 打破 worldbuilding 硬规则必须登记 `rule_overrides`，否则账本拒收后续矛盾设定。
- 冷读裁判必须独立子代理 + 干净上下文，禁止读创作蓝图；子代理不可用时按降级规则 inline 冷读并标注。
- 字数不达标不推进（硬下限拦截）。
- 打回原因属于逻辑/时序/在场/事实矛盾类 → **整段（含前后过渡）重写，禁止局部补丁插入**；补丁式插入是时序矛盾的最大来源（历次质检 19/31 条问题均为插入补丁制造）。
- 正文首稿即按目标字数写足（1500-2500），禁止「先写短稿再补字」；补字=重写段落，不插入零句。
- 派生视图（context.md、foreshadows.md、overrides.md、characters/、timeline/）由 tracking_commit 生成，**禁止手改**。
