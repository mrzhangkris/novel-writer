---
name: novel-writer
disable-model-invocation: true
description: |
  Use when writing novels, web novels, or long-form fiction with structured pipelines.
  Triggers: write novel, start new book, write web novel, write outline, continue writing, write next chapter, fix chapter X, rewrite chapter N, import existing novel, rename book, write side story/extra chapter, scan trends, analyze golden chapters, remove AI smell, query settings, polish chapter, fix grammar, archive, complete chapter, accept, proceed to next chapter, plot explosion, too boring, intensify, Save the Cat, 15 beats, story archetype, revise outline, adjust outline, change map, cut subplot, character exit, plot adjustment.
  NOT for: code implementation review (→ code-review-checklist); skill evaluation and optimization (→ darwin-skill).
---

# novel-writer · 小说写作编排层

> **脚本是导演，agent 是演员。** 确定性动作（组装/校验/记账）全部交给脚本，agent 只做需要理解力的事（写正文、冷读、剧情判断）。
> 每步的详细指令在各子技能 SKILL.md，编排层不重复。

## 处理三原则（总纲）

| 判定 | 处理者 |
|---|---|
| 算法能判定的 | 纯脚本，LLM 不出场 |
| 脚本可先提取的 | 脚本组装结构化结果 → LLM 消费 |
| 必须 LLM 理解的 | LLM（低频：写正文/冷读/剧情判断） |

一致性不靠记忆靠账本：每章写完提交 CHANGES 事务申报「本章改变了什么」，脚本过六道门禁（G1 协议 / G2 引用 / G3 一致性 / G4 未知实体 / G5 描写 / G6 履约）后合并进状态账本；下一章 spec 由脚本从账本组装。协议细节见 `references/architecture.md`。

## 术语速查

- **状态账本**：`tracking/_tracking-state.json` 唯一权威，只进不改；context.md 等皆其派生视图。改账本只能提交 JSON 事务，手改派生视图 = 账本作废。
- **gate / advance**：gate = 入口检查（上一步没完不放行）；advance = 出口质量校验（门禁不过不放行）。
- **冷读**：独立子代理以「没读过任何创作蓝图的普通读者」身份只读正文评分（四维：翻页欲/认知负荷/共情验证/节奏感受），≤2 分打回 revise。
- **stale**：事务带旧版本号提交会被拒（expected_state_revision 不匹配），防互相覆盖。

## 状态机 + 子技能路由

| 步骤 | 子技能 | 进入条件 |
|---|---|---|
| 1. init | `skills/mainline/novel-init/SKILL.md` | 未初始化 |
| 2. outline | `skills/mainline/novel-outline/SKILL.md` | setup done |
| 3. draft | `skills/mainline/novel-draft/SKILL.md` | outline done |
| 4. revise | `skills/mainline/novel-revise/SKILL.md` | 冷读打回才走，否则 skip |
| 5. archive | `skills/mainline/novel-archive/SKILL.md` | draft done + revise done/skipped |

分支请求不查状态机，直接读对应分支子技能：
扫榜→`skills/branch/story-long-scan`；拆书→`skills/branch/story-long-analyze`；去AI味→`skills/branch/story-deslop`；查设定→`skills/branch/story-query`；记技法→`skills/branch/story-learn`；润色/改病句→`skills/branch/story-polish`。

**消歧**：「润色第X章」=文句通顺（polish）；「去AI味」=AI痕迹（deslop）；「改第X章」=剧情结构修改（novel-revise）；「改大纲/换地图/砍支线/人物下线」=novel-revise 大纲修订模式。

## 目录结构（两层）

```
{写作根目录}/
├── .novel/           # 作者级资产，init 一次跨书复用
│   ├── preferences.md  style-anchor.md  writing-playbook.md
│   ├── templates/  banned-words.txt  active.md
└── {slug}/           # 书级，每本一个
    ├── concept.md  reader-contract.md  worldbuilding.md  题材卡.md
    ├── outline.md  characters/  chapters/chapter-NNN/{spec,draft,review}.md
    ├── tracking/     # 状态账本（脚本生成，禁止手改）
    │   ├── _tracking-state.json（唯一权威）
    │   └── context.md  foreshadows.md  overrides.md  threads.md  ledger.md  characters/  timeline/
    └── .story/       # 流程状态：pipeline.json（5 步状态机）+ tx-*.json
```

## 入口流程（每次固定，不协商）

1. 只跑这一条命令判断状态（`{SKILL_DIR}` = 本技能仓库根，全文同义）：
   ```
   python3 {SKILL_DIR}/scripts/pipeline.py status
   ```
2. 按输出路由：不在项目里 → 读 novel-init；有 pending 步骤 → 读对应子技能执行；分支请求 → 直接读分支子技能。
3. 写每章前先跑 `chapter_flow.py status --project {书目录}` 拿剩余步骤命令清单，照做即可。
4. 子技能执行完回到第 1 步。

**反模式（禁止）**：不预读全部子技能（只 Read 当前路由到的）；status 之前不 ls/不翻目录；不并行执行多个子技能；不凭探索获知状态（status 就是事实）。

**失败分支**：状态文件损坏 → `pipeline.py init --force-rebuild <项目名>` 重建（旧 .story/ 自动备份，账本 tracking/ 不动）；「不在项目里」但用户要续写 → cd 到含 `.story/` 的书目录；子技能文件读取异常 → 重跑 status 确认，不反复读同一文件。

## 铁律

**违反规则的字面就是违反规则的精神。** 无例外：

1. 每步前 `pipeline.py gate <step>`（exit 1 = 停），完成后 `pipeline.py advance <step>`
2. checkpoint（仅 CP1 选题）必须等用户明确确认，不等待 = 卡住，不绕过
3. 账本只能 JSON 事务驱动，禁止手改 `tracking/` 下脚本生成的派生视图（_tracking-state.json/context.md/foreshadows.md/overrides.md/threads.md/ledger.md/characters/、timeline/）；`pacing.md` 是唯一手写例外
4. 打破世界观硬规则必须在 `rule_overrides` 登记（理由+代价），否则 G3 拒收
5. 冷读必须独立子代理 + 干净上下文（不读 concept/outline/spec/worldbuilding）
6. 不读 spec.md 不写正文；履约清单勾选率 <80% 不放行
7. 打回原因属逻辑/时序/事实矛盾 → 整段含过渡重写，禁止局部补丁插入
8. 字数硬线不达标不推进；首稿按目标字数写足，补字=重写段落
9. 步骤细节只在子技能里，编排层不重复也不跳读

常见借口对照：「太短不用走全流程」→ 短篇照样吃连续性矛盾，轻量模式也跑门禁；「我记得设定不用查」→ 你记得读者不记得，查 `story_query.py`；「AI 味回头再改」→ 回头=永远不；「配角不用建卡」→ 配角会变主角，卡防吃书。

## 轻量模式

完整流程为长篇连载设计。轻量场景仍跑状态机与门禁（status 判定 + checks 校验不豁免）：

| 场景 | 跑什么 | 跳过什么 |
|---|---|---|
| 短篇 | init → outline → draft → archive | 拆书/完整 revise；大纲用 scaffold 轻骨架 |
| 续写 | draft → revise(条件) → archive | init/outline（前提：账本就绪） |
| 微调 | revise 精准修 | 完整 revise 循环 |

前提不满足就回完整流程：短篇需题材+平台（不确定先扫榜）；续写需 status 显示大纲已完成；微调需目标章 draft 存在。

## 脚本速查

| 脚本 | 命令 | 用途 |
|---|---|---|
| `pipeline.py` | init/status/gate/advance/skip/skip-chapter/checkpoint clear/next-chapter/fail/failed/wordcount | 状态机 + 门禁 |
| `chapter_flow.py` | prepare/finish/status | 每章三段式批量执行器 |
| `tracking_commit.py` | init/commit/check | 状态账本（G1–G3） |
| `gen_transaction.py` | init/commit [--revision] | 事务骨架自动生成，agent 只改变化部分 |
| `checks.py` | outline/draft/archive/wordcount/deai/verify | 门禁校验（G4–G6 + 字数） |
| `assemble_spec.py` | --chapter N | spec 蓝图确定性组装（含规则注入） |
| `scaffold_outline.py` | --project | 大纲骨架（按篇幅算章数） |
| `characters_pool_generator.py` | --project | 三维人物盘点矩阵（outline 硬门禁） |
| `coldread_material.py` | --chapter N [--write-review] | 冷读材料拼装（干净上下文） |
| `quality_trend.py` | record/show | 冷读分数趋势 |
| `story_query.py` | --grep/--character/--foreshadow/--timeline | 查设定唯一入口 |
| `book_init.py` / `new_chapter.py` / `export_book.py` / `book_finish.py` | 见各子技能 | 建书/建章/导出/收尾 |
| `outline_revise.py` / `outline_drift.py` / `check_continuity.py` | 见 novel-revise / archive | 大纲修订/漂移/连续性 |
| `check_seam.py` | --project [--chapter N] | 跨章拼接断裂检测（advisory） |
| `writer_profile.py` | calibrate/show | 写手档案（yeyue/M3 单写手：基线/AI味阈值/写前避开项） |
| `platform_review.py` / `polish_apply.py` / `check_spec_copy.py` / `learn.py` | 见对应子技能 | 平台审稿/病句落盘/照搬检测/技法沉淀 |

规则与阈值全是数据：改 `references/writing-rules.json`（写作纪律双投影）、`references/check-rules/*.json`（机械病句）、`references/word-count.json`（平台字数），不改代码。协议与架构详见 `references/architecture.md`。
