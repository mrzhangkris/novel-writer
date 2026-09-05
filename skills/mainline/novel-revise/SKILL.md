---
name: novel-revise
description: |
  修改：按冷读意见修改正文；或主动修订大纲（换地图/砍支线/人物下线）。novel-writer 流水线第 4 步（冷读打回才走，否则 skip）。
  触发词：改一下第X章、改稿、修改、返修、改大纲、大纲要调、换地图、砍支线、人物下线、剧情调整。
---

# novel-revise · 修改（第 4 步，条件触发）

> 冷读打回才进本步；通过则 `pipeline.py skip revise`。用户说「改大纲/换地图/砍支线/人物下线」时直接走本文「大纲修订模式」。

## 正文修改

### 1. 读冷读意见

读 `chapters/chapter-NNN/review.md`，按优先级处理：🔴 硬伤必须修 → 🟠 审美问题建议修。

### 2. 双清单自检（修改前后各过一遍）

- `references/craft-canon.md`：修改前编辑清单六条（伏笔一致/知情边界/时间线/称谓与数字/状态连续/钩子落点）+ 红线 12 条：机械降神/信息倾倒/无后果/崩人设/误会驱动/工具人/说教/陈词滥调/视角漂移/节奏失衡/主角无能动性/章内无变化

每条要么改掉，要么在 review.md 注明「无需处理」理由——防「修一处坏三处」。

### 3. 修改正文

只动 review 指出的问题，不做无关重构。涉及状态变化（角色/伏笔/时间线/破硬规则）→ 提交 `mode=revision` 事务（协议见 `references/architecture.md`；破硬规则必须 `rule_overrides` 登记）。**revision 事务的快照口径与 append 不同**：`character_snapshots` 须恰好等于 `character_changes` 的改动角色集合（append 才是「本章出场核心角色集合」）；修订非末章时快照与 context 不落当前状态（只落章级存档）。

**打回原因属逻辑/时序/在场/事实矛盾 → 整段（含前后过渡）重写，禁止局部补丁插入**——补丁式插入是时序矛盾的最大来源。

### 4. 重审

```
pipeline.py advance revise
```

改完回冷读重审：仍打回继续改；通过 → `pipeline.py skip revise` 进 archive。

## 历史章修订（修订非当前章）

用户要求重写/修订**已归档的历史章**（如「前 10 章设定改了，重写第 3 章」）时：

1. 确保该章 spec 存在（无则按 novel-draft 开章流程补建）
2. `gen_transaction.py commit --revision --chapter N` 生成该章 revision 事务（N ≤ 账本最后提交章）
3. 填事务、提交、重写 draft、重跑该章 checks 与冷读

**设计约束（账本章号连续性）**：已归档章的**章号不可合并/重排**（append 强制 last+1，合并会导致账本永久卡死）。叙事上的「两章合并」用 revision 重写实现——两章都保留，内容合并进前一章、后一章重写为过渡。

## 扩写与字数上限

「扩写到 3000 字」类请求：若目标超平台硬上限（130%），字数闸门会硬拦且无覆盖通道——设计立场是「超限即分章」。向用户说明并建议分章，不绕闸。

## 大纲修订模式（主动触发）

> 顺序不可颠倒：**先冲突检测 → 再改大纲 → 后对账**。

### A. 冲突检测

```
python3 {SKILL_DIR}/scripts/outline_revise.py --project {书目录} [--from-chapter N]
```

产出 `outline-revision-report.md`：伏笔对账（旧伏笔新大纲接不接得住）+ 章节冲突（已写章 vs 新大纲）+ 人物下线（活跃角色被抛弃）。

### B. 改 outline.md

每条冲突二选一：**改大纲**（伏笔续接/角色返场/章纲保留）或 **改声明**（伏笔 delete/角色退役/旧章重写）。

纪律：伏笔规划表随新章序同步更新；**已写章节的章纲不许删**——改写为「已写（第 N 章，原目标：…）」留档；结构/情绪/概念预算同步调整。

### C. 对账

1. 重跑 outline_revise.py，报告应无冲突（或只剩已声明废弃项）
2. 提交废弃登记：伏笔走 revision 事务 `foreshadow_changes action=delete`（修订可登记废弃）；角色下线属于「从此刻起」的状态变化，必须走 append 事务的 `retired_characters`（merge 拒收 revision 携带角色退役）
3. 已写章与新大纲矛盾 → 逐章走 revise 重写，不许假装旧章没写过

## 失败分支

- gate 报「已跳过」→ 直接 skip 进 archive
- gate 报「draft 未完成」→ 回 novel-draft
- 大纲修订后仍报冲突 → 回 B 步处理未对账条目

## 铁律

- 不顺手重写整章；状态变化不提交 revision 事务 = 账本与正文脱节
- 大纲修订不先跑 outline_revise.py = 伏笔断裂/角色悬空在几十章后爆雷
- 已写章纲直接删除禁止（必须留档）
