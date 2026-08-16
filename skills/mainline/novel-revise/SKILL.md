---
name: novel-revise
description: |
  修改：按冷读意见（chapters/chapter-NNN/review.md）修改正文。novel-writer 流水线第 4 步（条件触发：冷读打回才走）。
  触发词：改一下第X章、改稿、修改、改这一章、按审稿意见改、返修、改大纲、大纲要调、换地图、砍支线、人物下线、剧情调整。
  依赖：pipeline.py gate revise / advance revise。
---

# novel-revise · 修改（第 4 步，条件触发）

> novel-writer 流水线第 4 步。**条件触发**：只在冷读裁判打回（四维度有 ≤2 分）时才走；冷读通过则 `pipeline.py skip revise` 跳过，直接进 archive。
> **大纲修订模式**：用户说「改大纲/大纲要调/换地图/砍支线/人物下线」时，走本文「大纲修订模式」一节（不依赖冷读打回，主动触发）。

## 脚本路径

```
{SKILL_DIR}/scripts/pipeline.py
{SKILL_DIR}/scripts/outline_revise.py
```

## 前置门禁

```
pipeline.py gate revise    # 顺序锁：draft done；冷读打回才进入本步
```

## 执行步骤

### 1. 读冷读意见

读 `chapters/chapter-NNN/review.md`（冷读报告），按优先级处理：
1. 🔴 硬伤（必须修，脚本检出或冷读严重不达标）
2. 🟠 审美问题（建议修）

### 2. 编辑自检（六条 + 工艺总纲红线，修改前后各过一遍）

读 `{SKILL_DIR}/references/editor-checklist.md`，逐条过：
伏笔一致 / 知情边界 / 时间线 / 称谓与数字 / 状态连续 / 钩子落点。
每条要么改掉，要么在 review.md 注明「无需处理」的理由——防止「修一处、坏三处」。

再读 `{SKILL_DIR}/references/craft-canon.md` 第二部分红线 12 条，逐条扫本章：
机械降神 / 信息倾倒 / 无后果 / 崩人设（对照人物卡底线）/ 误会驱动 / 工具人 / 说教 / 陈词滥调 / 视角漂移 / 节奏失衡 / 主角无能动性 / 章内无变化。
同样：改掉，或在 review.md 注明「无需处理」理由。

### 3. 修改正文

改 `chapters/chapter-NNN/draft.md`，只动 review 指出的问题，不做无关重构。

**若修改涉及状态变化**（改了角色状态/伏笔/时间线/打破世界规则），提交 `mode=revision` 的 JSON 事务（见 novel-draft 第 4 步；打破硬规则必须在 `rule_overrides` 登记）。

### 4. 改完回冷读重审

```
advance revise
```

改完回到 novel-draft 第 6 步冷读裁判重审：仍打回则继续 revise，通过则 `pipeline.py skip revise` 进 archive。

## 大纲修订模式（主动触发：改大纲/换地图/砍支线/人物下线/剧情调整）

> 长篇写到中途方向要调，先跑冲突检测，再改大纲，最后对账——顺序不可颠倒。

### A. 跑冲突检测（改大纲前）

```
python3 {SKILL_DIR}/scripts/outline_revise.py --project {书目录} [--from-chapter N]
```

产出 `outline-revision-report.md`：伏笔对账（旧伏笔新大纲是否接得住）+ 章节冲突（已写章 vs 新大纲同章条目）+ 人物下线（活跃角色是否被新大纲抛弃）。

### B. 改 outline.md

按报告逐条处理，每条冲突二选一：
- **改大纲**：把冲突条目补回新大纲（伏笔续接、角色返场、章纲保留）
- **改声明**：显式声明废弃（伏笔 delete / 角色退役 / 旧章重写）

改大纲纪律：
- 章纲重排后，**伏笔规划表同步更新**（埋设章/回收章跟着新章序走）
- 已写章节的章纲**不许删**——写成「已写（第 N 章，原目标：…）」留档，防后文与旧章矛盾
- 结构标记/情绪曲线/概念预算与章纲同步调整

### C. 对账（改大纲后）

1. 重跑 `outline_revise.py`——报告应显示「无冲突」或只剩已声明的废弃项
2. 提交 `mode=revision` 事务登记所有废弃项：伏笔走 `foreshadow_changes action=delete`，角色下线走 `retired_characters`
3. 涉及已写章节内容与新大纲矛盾的 → 逐章走 revise 流程重写，不许「假装旧章没写过」

## 失败分支

- `gate revise` 报「已跳过」→ 无需修改，直接 `pipeline.py skip revise` 进 archive
- `gate revise` 报「draft 未完成」→ 回 novel-draft 完成 draft
- 修改后冷读仍打回 → 继续改，或回 novel-draft 重新冷读
- 大纲修订后 `outline_revise.py` 仍报冲突 → 回到 B 步处理未对账条目

## 铁律（不要做什么）

- ❌ 不顺手重写整章（只改 review 指出的问题，避免引入新问题）
- ❌ 修改涉及状态变化不提交 revision 事务（否则账本和正文脱节）
- ❌ 不直接改 tracking 账本
- ❌ 大纲修订不先跑 `outline_revise.py`（否则伏笔断裂/角色悬空在几十章后才爆雷）
- ❌ 已写章节的章纲直接删除（必须留档「已写」标记，防后文与旧章矛盾）
