---
name: novel-archive
description: |
  归档：一致性校验（tracking_commit.py check（硬终检）+ check_continuity.py --project .（伏笔/角色/时间算术 advisory，advisory 发现由你判断是否回修） + checks.py archive）+ 归档本章 + 进下一章。novel-writer 流水线第 5 步。
  触发词：归档、本章完成、验收、进下一章。
  依赖：pipeline.py gate archive / advance archive / next-chapter、tracking_commit.py check。
---

# novel-archive · 归档（第 5 步）

> novel-writer 流水线最后一步。校验一致性，归档本章，进入下一章。

## 脚本路径

```
{SKILL_DIR}/scripts/pipeline.py         # gate / advance / next-chapter
{SKILL_DIR}/scripts/tracking_commit.py  # check
{SKILL_DIR}/scripts/check_continuity.py # 连续性确定性检查（伏笔过期/无主、角色疑亡又活跃、硬规则突破未登记）
{SKILL_DIR}/scripts/outline_drift.py    # 大纲-正文漂移检测（最近 N 章履约率 + 钩子）
{SKILL_DIR}/scripts/platform_review.py  # 平台审稿（敏感词/连接词/句长突发性）
{SKILL_DIR}/scripts/learn.py            # 模式沉淀（项目级 / 作者级）
```

## 前置门禁

```
pipeline.py gate archive    # 顺序锁：draft done + revise done/skipped；文件锁：chapters/ 存在
```

## 执行步骤

### 1. 一致性校验 + 平台审稿

```
tracking_commit.py check --project .    # 派生视图一致 / 逐章记录规范 / 容量达标
check_continuity.py --project .         # 伏笔过期/无主、角色疑亡又活跃、硬规则突破未登记（advisory，发现由你判断是否回修）
outline_drift.py --project .            # 大纲-正文漂移（最近 10 章履约率 + 章尾钩子；漂移项对照大纲人工复核）
platform_review.py --chapter N          # 平台视角：敏感词/连接词密度/句长突发性（确定性部分）
```

- `check` 报错（派生视图与 state 不一致、逐章记录缺失等）→ 先处理再归档
- check_continuity 报 advisory → 逐条判断：确认是问题就回修并提交 revision 事务，误报（如「角色暂退场非死亡」）注明即可
- outline_drift 报漂移项 → 每章二选一：回正文补（补未履约条目/补钩子），或改大纲（正文已合理偏离时走 novel-revise 大纲修订模式更新章纲，不许静默漂移）
- platform_review 命中敏感词 → 逐条判断语境（对话/引用可放行并注明）；连接词密度/句长均匀 → 按提示改；其余判断项对照 `{SKILL_DIR}/references/platform-review.md` 四类红线过一遍
- 发布前（成书时）再跑一次 `platform_review.py --book` 全本扫描

### 2. 归档推进（自动校验）

```
advance archive    # 自动跑 checks.py archive（一致性），不过就卡住
```

### 3. 模式沉淀（每章一条；写作模式 D 全自动时必做）

从本章 review.md 与正文提炼一条「可复用写法」，用 learn.py 记入项目记忆（跨章/跨书召回）：

```
python3 {SKILL_DIR}/scripts/learn.py add "<提炼后的写法>" \
  --pattern-type {hook|pacing|dialogue|payoff|emotion|format|other} --importance {high|medium|low}
```

- 只记「可复用的模式」（钩子设计、回收节奏、对话技巧、微兑现等），不记一次性剧情
- 本章没有值得记的就跳过，不强凑；去重由脚本自动处理
- **作者级沉淀（跨书）**：发现「眼前一亮的妙处」「踩过的坑」「文风技法经验」时写入 `.novel/writing-playbook.md`（下本书的 spec 会自动带提醒）：

```
python3 {SKILL_DIR}/scripts/learn.py add "<妙处/坑/技法>" --scope author --section {妙处|问题|文风技法}
```
- 记完把内容同步给作者看（模式 D 下只需在汇报里带一句）

### 4. 进下一章

```
next-chapter    # 重置 draft/revise/archive，章节号 +1（setup/outline 保持 done）
```

### 5. 全书收尾（仅最后一章归档后跑一次）

```
python3 {SKILL_DIR}/scripts/book_finish.py --project .   # 导出成书 → 全本平台审稿 → 账本终检 → 质量趋势汇总
```

- book_finish 内部串起 `export_book.py`（成书稿导出）等收尾动作；跑完把导出文件路径与全本审稿结论汇报给作者
- 单独导出也可直接用 `python3 {SKILL_DIR}/scripts/export_book.py --project . --output 成书稿.md`

## 失败分支

- `check` 报错 → 按报错修账本（缺逐章记录补记录、派生视图不一致重跑 tracking_commit），修完再归档
- `advance archive` 卡住 → 看 checks.py archive 输出，处理一致性问题
- `next-chapter` 报「本章未完成」→ 回 status 看哪个步骤没 done/skipped

## 铁律（不要做什么）

- ❌ `check` 未过不归档，绝不带病归档
- ❌ 归档后本章正文冻结，不直接改；改动走新的 revise 流程
- ❌ 不手改 tracking 账本（_tracking-state.json + 派生视图）
