# 写手执行规约（writer-brief）

> 本文件是写手子代理（yeyue / Minimax M3）的唯一执行规约：委派任务书只给指针，规约全在这里。
> 改写作纪律只改本文件；写手必须逐节执行，不得凭记忆替代。

## 1. 输入（只读这些，禁止扩展）

- 委派任务书给出的 `spec.md` 路径：唯一写作蓝图，大纲要点/净变化/时间闸门/伏笔指令/语病避雷/规则注入全在里面。写正文只依据它，不重读 concept/worldbuilding 全文
- 委派任务书给出的 tx 事务骨架路径（`.story/tx-chapter-NNN.json`）
- 查设定走 `story_query.py`（`--grep/--character/--foreshadow/--timeline`，脚本目录见任务书），禁止 grep/翻账本派生视图

## 2. 写前三查（不答完不动笔）

1. **主动选择+代价**：本章主角的主动选择是什么？代价是什么（对照 `references/craft-canon.md` 特质条目）？答不出 → 停笔回报委派方
2. **人物底线**：出场角色行为不得撞人物卡「底线」（`characters/{角色名}.md`，路径相对书目录）；主角挫折源于 flaw、高光源于 strength
3. **世界观传达**：设定只通过角色行动/对话/观察呈现，禁止旁白讲解

## 3. 动笔硬规约（检测器会拦，违反=批量返工）

- 全文禁用破折号「——」（对话打断用动作/短句）
- 禁用「不是 X，是 Y」否定对比句式
- 正文纯文本：无 `#` 标题、无 markdown 加粗、无元标注/创作笔记
- 单场景转折连接词（然而/但是/却/不过）≤1 次；禁否定排比（不X，不Y，不Z）
- 段落 1-3 行为主；每 500 字至少一个信息增量或情绪波动
- 字数：按 spec「本章目标字数」，首稿一次写足，禁止先写短稿再补
- 章末按 spec 五问闸门第 5 问收钩子：以动作或对话定格，禁总结/感慨/升华式收口
- spec 风格指令区「写手避开」行逐条执行（这是你的实测档案，不是泛泛建议）

## 4. 写时同步填事务（骨架已预填，只改变化部分）

| 字段 | 纪律 |
|---|---|
| `character_changes` / `character_snapshots` | 快照集合必须恰好等于 changes 的角色集合（少报缺快照，多报非核心）；快照字段白名单：identity/location/goal/state/alive(布尔)/abilities_resources/relationships/knowledge/open_threads |
| `timeline_events`（≤2 条） | 字段仅 `id(E00x)/story_time/objective_fact/reader_knowledge/characters/reveal_status`；部分揭示或已揭示必填 `reveal_chapter`(数字)。**禁止发明白名单外字段**（如 event_id/chapter） |
| `plot_points`（≤4 条） | 纯字符串数组，每个元素一句话，禁止对象/嵌套 |
| `items`/`secrets`/`pledges` | 有变动才填，形状见 `references/architecture.md` |
| `next_chapter_commitments` | 下章开头必须接住的事 |
| `context.active_scene` | 一句话场景锚 ≤240 字节；`active_character_names` 恰好等于快照集合 |
| `delta.inventions` | 正文确立了 spec 之外的新设定/人物/事实时**必须逐条申报**（一句一条，≤6 条）——不申报，下一章蓝图不知道，冲突后爆 |
| 字节预算 | delta 总量 ≤4096 字节（>1536 警告）；knowledge 每条一行以内 |

新角色当场建卡：首次出现、有名有姓、预计跨章复用（≥2 场戏或推进剧情的台词）→ 建卡（与主角/详卡有直接关系 → 详卡模板；见证者/信息提供者 → 简卡模板；一次性龙套不建卡）。简卡角色本章与主角建立直接关系 → 写完立即升级详卡，不留到下一章。

填完跑：`python3 {scripts目录}/tracking_commit.py validate --project {书目录} --input {tx路径}`（G1 全字段校验，不落账），报错改到通过。注意 `check` 只查账本不校验事务，别拿它当自查。

## 5. 勾履约清单

spec「大纲要点」逐条改 `[x]`；写作中调整了计划的就地注明，不删条目。

## 6. 写完自校三步（换身份重读——生成时的你会脑补「想写的」）

1. 读者身份：从头通读（重点：与上章结尾锚的过渡），逐句读两遍，不顺就改
2. 编辑身份：对照 spec「语病避雷」扫描（开头 500 字逐句精读）；发现清单外的新病句模式，先登记 `references/issue-patterns.md` 再改
3. 收手原则：只改病句不改剧情风格（一个 pass 只干一件事）

技法按需加载：先查 `references/writing-methods/INDEX.md` 匹配主题再读单份（钩子/对话/反转/打脸等），不整库预读；动作/战斗腔调按需读 `references/author-styles/author-dna.md`。

## 7. 返回汇报格式（固定五项）

1. draft.md 的 CJK 字数
2. 本章净变化一句话
3. validate 关键输出行
4. 写前三查逐条一句话结论
5. 最得意的 1 处 + 最没把握的 1 处
