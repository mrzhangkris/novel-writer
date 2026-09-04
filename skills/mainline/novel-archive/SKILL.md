---
name: novel-archive
description: |
  归档：一致性校验 → 归档本章 → 模式沉淀 → 进下一章。novel-writer 流水线第 5 步。
  触发词：归档、本章完成、验收、进下一章。
---

# novel-archive · 归档（第 5 步）

> 校验一致性，归档本章，沉淀模式，进下一章。G3 门禁在此终检。

```
pipeline.py gate archive    # 顺序锁：draft done + revise done/skipped
```

## 执行步骤

### 1. 一致性校验 + 平台审稿

```
python3 {SKILL_DIR}/scripts/tracking_commit.py check --project .    # G3 硬终检
python3 {SKILL_DIR}/scripts/check_continuity.py --project .         # 连续性 advisory
python3 {SKILL_DIR}/scripts/check_seam.py --project .               # 跨章拼接断裂 advisory
python3 {SKILL_DIR}/scripts/outline_drift.py --project .            # 大纲-正文漂移
python3 {SKILL_DIR}/scripts/platform_review.py --chapter N          # 平台审稿（确定性部分）
```

- `check` 报错（派生视图不一致/记录缺失）→ 先修再归档，**check 未过绝不归档**
- check_continuity 报 advisory → 逐条判断：真问题回修并提交 revision 事务；误报（如角色暂退场非死亡）注明即可
- check_seam 报 seam-conflict/时间跳跃 → 词表法有噪声，逐条人工终判：真断裂回修改写交接段（地点/人物/时间至少一项接住上章结尾）；有意转场注明放行
- outline_drift 报漂移 → 每章二选一：回正文补（补履约/补钩子）或改大纲（走 novel-revise 大纲修订模式），不许静默漂移
- platform_review 命中敏感词 → 逐条判断语境（对话/引用可放行并注明）；其余对照 `references/platform-review.md` 四类红线；成书时再跑 `--book` 全本扫描

### 2. 归档

```
pipeline.py advance archive    # checks.py archive 校验，不过就卡住
```

归档后本章正文冻结；改动走新的 revise 流程。

### 3. 模式沉淀

从本章 review.md 与正文提炼一条「可复用写法」：

```
python3 {SKILL_DIR}/scripts/learn.py add "<提炼后的写法>" --pattern-type {hook|pacing|dialogue|payoff|emotion|format|other} --importance {high|medium|low}
```

- 只记可复用模式（钩子设计/回收节奏/对话技巧），不记一次性剧情；没有值得记的就跳过，不强凑
- **跨书沉淀**：眼前一亮的妙处/踩过的坑/文风技法 → `learn.py add "…" --scope author --section {妙处|问题|文风技法}`（写入 `.novel/writing-playbook.md`，下本书 spec 自动带提醒）
- 记完同步给作者（全自动模式下汇报带一句，模式定义见 novel-init 偏好设置）

### 4. 进下一章

```
pipeline.py next-chapter    # 重置 draft/revise/archive，章节号 +1
```

next-chapter 后 → 回到根 SKILL.md 入口跑 status，路由回 novel-draft 写下一章（书完跑 book_finish.py 收尾）。

### 5. 全书收尾（仅最后一章）

```
python3 {SKILL_DIR}/scripts/book_finish.py --project .    # 导出成书 → 全本审稿 → 账本终检 → 趋势汇总
```

跑完把导出路径与全本审稿结论汇报给作者。单独导出用 `export_book.py --project . --output 成书稿.md`。

## 失败分支

- check 报错 → 按报错修账本再归档
- advance 卡住 → 看 checks.py archive 输出处理一致性问题
- next-chapter 报「本章未完成」→ status 看哪步没 done/skipped

## 铁律

- check 未过不归档，绝不带病归档
- 归档后正文冻结，不直接改
- 不手改 tracking 账本
