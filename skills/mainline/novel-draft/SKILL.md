---
name: novel-draft
description: |
  写正文：开章（脚本组装 spec 蓝图）→ 只读 spec 写 draft + 填 CHANGES 事务 → 收尾（门禁 + 冷读）。novel-writer 流水线第 3 步。
  触发词：写正文、写这一章、写下一章、继续写、写番外（番外按普通章流程，章纲标注「番外」，走完整门禁）。
---

# novel-draft · 写正文（第 3 步）

> 每章一个文件夹（`chapters/chapter-NNN/`）。流程：**开章 → 写正文 → 收尾**，生成类动作全部由 `chapter_flow.py` 代跑，agent 只做判断与写作。CHANGES 事务协议见 `references/architecture.md`。

## 三段式（权威路径，`chapter_flow.py status` 随时可查进度）

### 1. 开章

```
python3 {SKILL_DIR}/scripts/chapter_flow.py prepare --project {书目录}
```

自动完成：建章节文件夹 → `assemble_spec.py` 组装 spec 蓝图（大纲要点/角色状态/前情衔接/知情边界/时间线定位/伏笔指令/题材要点/风格指令/规则注入）。

> **两段式注意**：prepare 需跑两次——第一次只组装 spec（组装后返回，提示补判断项）；补完 spec 判断项后**再跑一次 prepare**，此时才生成 CHANGES 事务骨架（`.story/tx-chapter-NNN.json`）。**首章前置**：状态账本未初始化时 prepare 会要求先跑 `gen_transaction.py init` + `tracking_commit.py init`（按报错指引做一次即可，之后不再需要）。

agent 只补 spec 判断项（写入 `chapters/chapter-NNN/spec.md`）：

- **履约清单**：本章目标/场景/关键事件/章末钩子，逐条 `[ ]`（写完勾 `[x]`，G6 校验 ≥80%）
- **本章净变化**：状态/信息/关系/资源至少其一（防水章，先答再写）
- **五问闸门**：①读者期待什么爽点 ②在哪个情节点兑现 ③兑现前垫了什么情绪 ④是否连续三章同型爽点（打脸=当众受辱后反杀、升级=境界/能力/地位跃迁、收获=宝物/机缘/认可到手、扮猪=藏拙后被逼亮底牌、揭底=隐瞒信息当众揭开、救场=绝境时赶到，六类轮换；判据=兑现机制的爽感来源，不是情节内容）⑤章末钩子勾住什么（危机/悬念/渴望/情绪四类轮换）

### 2. 写正文

**只读 `spec.md`**，写 `chapters/chapter-NNN/draft.md`。不重读 concept/worldbuilding 全文（防信息倾泻）；查设定一律走 `story_query.py`（`--grep`/`--character`/`--foreshadow`/`--timeline`），不用 grep/read 翻账本。**draft.md 是纯正文**：不写 `#` 章节标题、不写元标注/创作笔记（G3 元标注校验会拒收）。

**写前三查 + 动笔避开项**：
1. **主动选择+代价**：本章主角的主动选择是什么？代价是什么（`references/craft-canon.md` 特质 10 条）？答不出回大纲补
2. **人物底线**：出场核心角色的行为撞不撞人物卡「底线」（`story_query.py --character 角色名` 查卡+快照）？撞了必须写出动机。再对照卡上优缺点——本章主角的挫折是否源于 flaw、高光是否源于 strength；违反则在 spec 注明理由（软对账，不硬拦）
3. **世界观传达**：设定只通过角色行动/对话/观察传达，禁止旁白讲解
4. **动笔就避开**（G5 阻断项，写满 2000 字再改要批量返工）：① 破折号「——」一处不用（对话打断用动作/短句）；② 「不是 X，是 Y」否定对比禁用；③ markdown 加粗/标题不进正文

**写时同步填事务**（`.story/tx-chapter-NNN.json` 骨架已预填，只改变化部分）：角色变化、时间线（objective_fact + reader_knowledge 双视图）、伏笔动作、道具/秘密/誓约、`new_abilities`、该登记的 `rule_overrides`。

**写时同步填事务**（`.story/tx-chapter-NNN.json` 骨架已预填，只改变化部分）：角色变化、时间线（fact + reader_knowledge 双视图）、伏笔动作、道具/秘密/誓约、`new_abilities`、该登记的 `rule_overrides`。

**新角色当场建卡**：本章首次出现、有名有姓、预计跨章复用（≥2 场戏或推进剧情的台词）→ 当场建卡：与主角/详卡有直接关系 → 详卡模板；见证者/信息提供者 → 简卡模板；一次性龙套不建卡。简卡角色本章与主角建立直接关系 → 写完立即升级详卡，不留到下一章。

**技法按需加载**：先查 `references/writing-methods/INDEX.md` 匹配主题再读单份（钩子/对话/反转/打脸等），不整库预读；动作/战斗腔调按需读 `references/author-styles/author-dna.md`。

**写完自校三步**（生成时的你会脑补「想写的」，必须换身份重读文本）：
1. 读者身份：Read draft.md 从头读，逐句连读两遍，不顺就标
2. 编辑身份：对照 spec「语病避雷」扫定式病句；发现清单外新模式先登记 `references/issue-patterns.md` 再改
3. 收手原则：只改病句不改剧情风格（一个 pass 只干一件事），改完 `checks.py draft` 复验

### 3. 收尾

```
python3 {SKILL_DIR}/scripts/chapter_flow.py finish --project {书目录}
```

自动完成：commit 事务（G1 协议/G2 引用）→ 一致性合并（G3）→ 门禁（字数/G4 未知实体/G6 履约/风格基线 G5/去AI味）→ 生成冷读材料。冷读评分后 `finish --coldread 分1,分2,分3,分4` → 记趋势 → 分流 revise/archive。

## 提交事务（填骨架时的硬约束，填错被拒收）

协议全文见 `references/architecture.md`，填骨架时最常踩的：

- 提交前 `tracking_commit.py check` 拿 `state_revision` 填 `expected_state_revision`
- `active_character_names` 必须恰好等于 `character_snapshots` 集合（少报缺快照/多报非核心）
- 多线叙事必填 `context.thread`（缺省「主线」）；切线时 assemble_spec 自动带停点进下章 spec
- `timeline` 每条分「客观事实 fact」与「读者认知 reader_knowledge」——写清读者此刻知道什么
- `delta.result` ≤480 字节；`constraints` 一条一句只收字符串；delta 总字节 >3072 拒收、>1536 警告
- **30 万字连载的字节预算经验**：每章事务按「≤2 条 timeline_events + ≤2 条 character_changes + ≤1 条 foreshadow_change」配额填写，超出必撞 3072 红线；角色 knowledge 数组是最容易膨胀的字段（每条都计字节）
- spec 模板与正文都不写「——」；spec 里的协议条款/设定原文（如附则三全文）会被 check_spec_copy 判照搬——spec 引用设定时用概括而非全文抄录
- 删改 `continuity_risks` 旧条目必须把原文逐字放进 `delta.retired_context_items`
- 正文出现世界观敏感词：无意打破 → 改掉词面；有意打破 → `rule_overrides` 登记（同章 ≤3 条）
- 未登记说话人（G4）：临时龙套可忽略（正文把「老人」类称谓改成名字可消警）；常驻角色必须进快照+changes+当场建卡

## 字数闸门

按平台×类型标准生效（`pipeline.py status` 可查本书平台）：低于硬下限 70% 或超硬上限 130% 硬拦；软区只警告，连续 3 章同软区升级硬拦；未选平台整体跳过（其余校验照跑）。**首稿按目标字数写足，禁止先写短稿再补字——补字=重写段落，不插入零句。**

> 选角出场检查是**单向核对**（spec 名单 → 正文是否出现）；反向「正文冒出名单外角色」由 G4 未登记说话人提示兜底（advisory）。

## 冷读裁判（独立子代理，默认路径）

> 用户明确要求跳过冷读时：先说明冷读防「作者记忆脑补」的设计理由；用户坚持则照办并在 review.md 首行标注「用户要求跳过」（用户主权优先，但须留痕）。

门禁全过后，spawn **干净上下文**的子代理做冷读：只读正文切片 + 前情速记，禁止读任何创作蓝图（防作者记忆脑补）。

- 材料由 `coldread_material.py --chapter N --write-review` 拼装（原文切片，非 AI 转述；前情速记取 spec 历史快照，不用账本滚动值——防补跑时剧透）
- **分级**：脚本全过 → 轻量冷读（开头 300 字+章末钩子+前情速记）；被门禁打回或存疑 → 全文冷读
- 子代理 prompt 已写入 review.md，四维各 1-5 分：翻页欲（未解答问题 2-4 个）/ 认知负荷（首 500 字 >3 个未铺垫新元素=过载）/ 共情验证（能否一句话概括主角此刻想要什么）/ 节奏感受（想跳过或没看懂的地方）
- 证据纪律：低于 4 分必须贴正文原句，写不出句子不许扣分

**inline 降级**（仅子代理起不来时，不得跳过冷读）：以冷读者身份只用「开头 300 字+章末钩子+前情速记」评分，review.md 首行标注「inline 降级」。

评分记趋势：`quality_trend.py record --scores 翻页欲,认知负荷,共情验证,节奏感受`

冷读回收后，主线程对照 review.md 末尾的「蓝图兑现复盘」节，逐条判本章目标 done/thin/miss（冷读者不读蓝图，预期对照由你做；miss 的要点走 novel-revise 补写或回 spec 注明）。

**分流**：无 ≤2 分 → `pipeline.py skip revise` 进 archive；有 ≤2 分 → 走 novel-revise。

## 失败处理（自动修复循环 + 熔断）

advance draft 被拒时：读失败信息针对性修复 → 重跑 advance → 仍失败 `pipeline.py fail` 记一次再修 → 提示进入第 N 轮重写 → 舍弃本章从 spec 重写 → 已重写 3 轮仍失败 → `pipeline.py skip-chapter` 标记失败章进下一章。书尾 `pipeline.py failed` 列出失败章供人工补写。

## 铁律

- 开章 → 写正文 → 收尾，顺序不可颠倒；写作阶段只读 spec.md
- 本章必须有净变化（先答再写）；打回属逻辑/时序/事实矛盾 → 整段含过渡重写，禁局部补丁
- 冷读独立子代理 + 干净上下文，禁止读创作蓝图
- 派生视图（context.md/foreshadows.md/characters//timeline/）脚本生成，禁止手改
- spec 履约清单调整要回 spec 改勾选并注明，不删条目
