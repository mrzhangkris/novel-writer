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

### 2. 写正文（委派 yeyue）

**本书写手固定为 yeyue（Minimax M3）**：正文一律 spawn `yeyue` 子代理执笔，主 agent 只做编排与校验。委派任务书固定为四行指针（规约细节全在 `references/writer-brief.md`，由写手自行读取，不随章重述）：

```
① 规约：读 {SKILL_DIR}/references/writer-brief.md，逐节严格执行
② 蓝图：{书目录}/chapters/chapter-NNN/spec.md（唯一写作输入）
③ 事务：填 {书目录}/.story/tx-chapter-NNN.json，改完跑 {SKILL_DIR}/scripts/tracking_commit.py validate --project {书目录} 修到通过
④ 交付：draft.md + 填好的 tx + spec 履约勾选 + 按 brief 第 7 节格式返回汇报
```

主 agent 接手：跑 `chapter_flow.py finish` 校验（写手不自己验收）→ 冷读。子代理起不来时主线程亲写（同规约，同纪律）。

写手中的事务填写/新角色建卡/技法按需加载/自校三步细节全在 `references/writer-brief.md`，主 agent 不复述、不代劳；只需知道：写手会当场建新角色卡（G4 口径）、按 writing-methods/INDEX 按需读技法、写完自校后才返回。

### 3. 收尾

```
python3 {SKILL_DIR}/scripts/chapter_flow.py finish --project {书目录}
```

自动完成：commit 事务（G1 协议/G2 引用）→ 一致性合并（G3）→ 门禁（字数/G4 未知实体/G6 履约/风格基线 G5/去AI味）→ 生成冷读材料。冷读评分后 `finish --coldread 分1,分2,分3,分4` → 记趋势 → 分流 revise/archive。

## 写手档案（yeyue / Minimax M3）

本书写手固定为 yeyue，其文风基线与 AI 味处置记在单一档案 `.novel/writer.md`（AI 味与文风纠缠：同一破折号判据，猫腻腔是文风、电报腔是 AI 味，豁免/盯防按档案裁定，不全局一刀切）：

- 校准：写出 2-3 章正稿后 `writer_profile.py calibrate --chapters N,M`——量化基线与 AI 味检出表自动实测；「豁免/盯防」裁定是文风决策，人工核订（豁免=文风合法形态，盯防可写 `阈值=N` 覆盖默认提醒线）；「写前避开项」每章自动注入 spec 风格指令
- 不校准也能写：档案缺失自动回退作者级 style-anchor + 全局默认阈值；查看 `writer_profile.py show`

## 提交事务（填骨架时的硬约束，填错被拒收）

协议全文与硬约束速查见 `references/architecture.md`，写章时最容易踩的：

- 填完先自查：`tracking_commit.py validate --project . --input .story/tx-chapter-NNN.json`（G1 全字段校验，不落账）——`check` 只查账本不校验事务，别拿它当自查
- 提交前 `tracking_commit.py check` 拿 `state_revision` 填 `expected_state_revision`
- **30 万字连载的字节预算经验**：每章事务按「≤2 条 timeline_events + ≤2 条 character_changes + ≤1 条 foreshadow_change」配额填写，超出必撞 4096 红线（>1536 警告）；角色 knowledge 数组是最容易膨胀的字段（每条都计字节）
- **写手发明必须申报**：正文确立了 spec 之外的设定/人物/事实（新地点、人物关系、口癖、物件来历），逐条填 `delta.inventions`（一句一条，≤6 条）——不申报下一章不知道，冲突后爆；申报后进 context.md「写手发明」节，后续 spec 自动带出
- spec 模板与正文都不写「——」；spec 里的协议条款/设定原文（如附则三全文）会被 check_spec_copy 判照搬——spec 引用设定时用概括而非全文抄录
- 正文出现世界观敏感词：无意打破 → 改掉词面；有意打破 → `rule_overrides` 登记（同章 ≤3 条）

## 字数闸门

按平台×类型标准生效（`pipeline.py status` 可查本书平台）：低于硬下限 70% 或超硬上限 130% 硬拦；软区只警告，连续 3 章同软区升级硬拦；未选平台整体跳过（其余校验照跑）。**首稿按目标字数写足，禁止先写短稿再补字——补字=重写段落，不插入零句。**

> 选角出场检查是**单向核对**（spec 名单 → 正文是否出现）；反向「正文冒出名单外角色」由 G4 未登记说话人提示兜底（advisory）。

## 冷读裁判（独立子代理，默认路径）

> 用户明确要求跳过冷读时：先说明冷读防「作者记忆脑补」的设计理由；用户坚持则照办并在 review.md 首行标注「用户要求跳过」（用户主权优先，但须留痕）。

门禁全过后，spawn **干净上下文**的子代理做冷读（不得用 yeyue——写手不冷读自己的稿）。冷读委派任务书固定三行：

```
① 身份：独立冷读者，普通读者视角，从未读过本书任何创作蓝图；只允许读 chapters/chapter-NNN/review.md 与 chapters/chapter-NNN/draft.md，书内其他文件一律不读
② 执行：按 review.md 内置评审指引做全文冷读（指引与评分格式已写入该文件）
③ 落盘与返回：把「评分：X,X,X,X」+ 结论 + 冷读意见追加到 review.md 末尾；返回四维分数 + 一句话总评
```

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
- 本章必须有净变化（先答再写）；spec 履约清单调整要回 spec 改勾选并注明，不删条目
