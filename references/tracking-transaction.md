# 追踪状态协议

`tracking/` 使用“一个结构化权威状态 + 多个确定性派生视图”。模型只提交一份语义 JSON，不分别 `Write/Edit/echo >>` 多个追踪文件。

## 权威层与派生层

| 层级 | 文件 | 语义 |
|---|---|---|
| 唯一权威 | `_tracking-state.json` | schema、最后提交章、导入截止章、状态修订号、上下文结构、全部当前角色/伏笔/时间线状态 |
| 章节记录 | `chapter-deltas/第NNN章.md` | 本章对未来连续性有用的紧凑变化；目标 ≤1536 字节，硬上限 3072 字节；导入范围内修订写成覆盖记录 |
| 派生视图 | `context.md`、`characters/{角色名}.md`、`foreshadows.md`、`timeline/author-truth.md`、`timeline/reader-known.md` | 完全从 `_tracking-state.json` 生成；禁止手改，不作为程序输入 |

Markdown 只负责给作者和 Agent 阅读，工具不再反向解析 Markdown。`check` 直接从 `_tracking-state.json` 重渲染并逐文件比较。未来“第几章揭示”的计划写在卷纲/细纲，不写成时间线既成事实。
chapter-deltas只是便于人阅读的紧凑变化记录，不承诺单独无损重建全部当前状态；完整当前语义以 `_tracking-state.json` 为准。

## 运行工具

先按运行环境探测 Python 3 解释器（依次尝试 `python3`、`python`、`py -3`），再用当前 skill 根目录执行：

```text
{PYTHON} {当前 skill 根}/scripts/tracking_commit.py init   --project {书项目根} --input {初始化事务.json}
{PYTHON} {当前 skill 根}/scripts/tracking_commit.py commit --project {书项目根} --input {逐章事务.json}
{PYTHON} {当前 skill 根}/scripts/tracking_commit.py check  --project {书项目根}
```

- `init`：只在 `_tracking-state.json` 不存在时执行，绝不覆盖已初始化项目。
- `commit`：读取唯一权威状态，在内存中完成合并、引用检查、全部视图渲染和容量检查；随后写chapter-deltas与派生视图，最后原子替换 `_tracking-state.json` 作为唯一提交点。
- `check`：严格验证 state schema、chapter-deltas连续性/规范名/体积、固定 7 栏、角色快照硬上限、派生文件集合，以及所有派生视图与 state 的逐字一致性。

同一本书只允许工作流串行提交，不支持多个 Agent 或终端并发写。`expected_state_revision` 用于拒绝基于旧状态构造的顺序 stale transaction，不是并发锁。

事务 JSON 在成功前必须保留。若文件写入失败，`_tracking-state.json` 尚未推进；修正环境后直接重跑**同一份** `commit`。append 重跑只接受内容完全相同的既有chapter-deltas，不维护 `dirty/pending/repair` 状态机。

校验失败与写入失败处理方式不同：校验失败（字段非法、退役结构、容量超限）要按报错改事务本身，重跑同一份结果不变。派生视图被手改或外部改动导致 `check` 报 `derived view differs from _tracking-state.json` 时，重新提交**该章**的 `mode=revision` 事务让工具整份重建，`expected_state_revision` 取 `tracking/_tracking-state.json` 的 `state_revision` 字段——`check` 失败时只往 stderr 打 ERROR，不输出 JSON；不手改派生文件，也不删 `_tracking-state.json` 重来。手写出的chapter-deltas会让同章 `append` 永久报 `chapter delta N already exists with different content`——删掉那个手写文件后重跑原事务即可。

本工具不解析旧 `_tracking-meta.json`、`时间线/事件库.json` 或更早追踪结构，不提供语义兼容层。`init` 遇到这类旧文件时，先把它们按原样整体移入 `tracking/_legacy/`，再在原地建当前协议：旧内容留给作者查阅，不参与解析，当前状态完全以 init 输入为准。校验失败的 `init` 不移动任何文件。`commit` 与 `check` 仍直接拒绝旧结构——它们只在已建协议的项目上运行。

## 初始化事务

新书从第 0 章初始化。导入已有小说时（导入功能暂未内置：需按下方「初始化事务」手工构造 `last_chapter=N` 的 init 输入）把最后完整章写入 `last_chapter=N`；第 1..N 章不伪造日更记录，常规续写从 N+1 章开始。

```json
{
  "schema_version": 1,
  "book_title": "让你管账号，你高燃混剪炸全网",
  "last_chapter": 0,
  "context": {
    "position": {
      "volume": "第一卷·军宣整顿",
      "volume_start_chapter": 1,
      "story_time": "江晨到火箭军文工团报到前",
      "scene": "火箭军文工团"
    },
    "long_term_constraints": ["军宣爽点要用作品效果和围观反应链兑现，不能只靠系统播报"],
    "active_character_names": [],
    "continuity_risks": [],
    "recent_chapters": [],
    "next_chapter_commitments": ["让江晨报到，并落下五天百万粉的新手任务"]
  },
  "character_snapshots": {},
  "foreshadow": [],
  "timeline_events": []
}
```

导入初始化时直接传入当前核心角色快照、伏笔当前行、时间线事件和固定 7 栏状态输入。阶段/卷级回看按需查询正文，不作为每章强一致追踪产物。

## 逐章事务

```json
{
  "schema_version": 1,
  "mode": "append",
  "chapter": 10,
  "chapter_title": "专业团队拍得还不如他拍的好？",
  "expected_state_revision": 9,
  "delta": {
    "result": "专业团队重拍的高清版在高层看片会上被判定缺了灵魂，张耀祖拍板继续采用江晨的手机原版。",
    "character_changes": [
      {"name": "江晨", "change": "作品价值获军内高层确认，从爆款新人升为不可替代的军宣创作者"}
    ],
    "foreshadow_changes": [
      {
        "action": "upsert",
        "id": "F027",
        "summary": "专业团队仍拍不出江晨原版的灵魂，继续验证其创作能力不可复制",
        "planted_chapter": 10,
        "planned_resolution_chapter": null,
        "status": "已埋",
        "importance": "中"
      }
    ],
    "timeline_events": [
      {
        "action": "upsert",
        "id": "E010",
        "story_time": "实弹训练两天后",
        "objective_fact": "文工团高层否决专业重拍版，决定沿用江晨手机拍摄的原版视频",
        "reader_knowledge": "读者已看到周薄森指出专业版缺了灵魂，张耀祖当场拍板用回原版",
        "reveal_status": "已揭示",
        "reveal_chapter": 10,
        "characters": ["江晨", "周薄森", "张耀祖"]
      }
    ],
    "constraints": ["后续继续用作品落地效果和围观反应放大江晨的高光，不能只写系统奖励数字"],
    "next_chapter_commitments": ["结算五天百万粉任务，并承接老兵主题的新任务"]
  },
  "context": {
    "position": {
      "volume": "第一卷·军宣整顿",
      "volume_start_chapter": 1,
      "story_time": "实弹训练两天后",
      "scene": "火箭军文工团高层看片会"
    },
    "long_term_constraints": ["军宣爽点要用作品效果和围观反应链兑现，不能只靠系统播报"],
    "active_character_names": ["江晨"],
    "continuity_risks": ["钟嘉嘉说江晨只猜对一半，未公开的培养安排不能被当成读者已知事实"]
  },
  "character_snapshots": {
    "江晨": {
      "identity": "火箭军文工团宣传兵；军宣爆款创作者",
      "location": "火箭军文工团高层看片会",
      "goal": "完成五天百万粉任务，持续做出真正能打的军宣内容",
      "state": "专业团队反向验证原版价值，军内认可继续抬升",
      "abilities_resources": ["前世MCN爆款运营经验", "《中国军魂》伴奏", "大师级导演能力"],
      "relationships": ["钟嘉嘉持续提供军报资源", "周薄森和张耀祖已明确认可其创作能力"],
      "knowledge": ["《军报》采访稿已经过审", "原版视频将继续作为正式军宣内容"],
      "open_threads": ["五天百万粉任务尚未结算", "钟嘉嘉所谓只猜对一半仍未解释"]
    }
  }
}
```

约束：

- 构造事务前运行 `check`，把当前 `state_revision` 原样写入 `expected_state_revision`；若状态已经变化，重新读取 state 并重构事务。
- `context` 的允许字段随子命令不同：`init` 收 `position`、`long_term_constraints`、`active_character_names`、`continuity_risks`、`recent_chapters`、`next_chapter_commitments`、`threads` 七项；`commit` 只收前五项（`recent_chapters` 与 `next_chapter_commitments` 由工具派生；`thread` 为可选线名）。`recent_chapters` 与 `next_chapter_commitments` 在 commit 时由工具从当前视图和本章 `delta` 派生，手填会在任何写入前被拒（`context contains unsupported fields: ...`，exit 2）。照 init 示例套 commit 事务是最容易踩的一处。
- `character_snapshots` 中出现的角色视为核心复用角色，必须同时出现在 `character_changes`；已经建立快照的核心角色再次变化时必须提交新快照。
- 角色快照的四个列表不限制条数，只限制单项长度和最终文件总字节：目标 ≤4096 字节，超过警告；硬上限 8192 字节，超过则在任何写入前拒绝。
- 没有快照的角色变化视为临时角色，不建立状态文件；`context.active_character_names` 最多 6 人且必须已有当前快照。
- `context.long_term_constraints` 和 `context.continuity_risks` 是整份提交的当前值。凡是上一版有、本次没有的条目，必须逐条列进 `delta.retired_context_items`，否则工具在任何写入前拒绝——漏写不会被当成删除。实际退役的条目由工具写进本章chapter-deltas的 `## 本章退役登记`，随后仍可回查。
- 不再复用的核心角色写进 `delta.retired_characters`：工具删除其当前快照与 `characters/{角色名}.md`，并在chapter-deltas留档。同一事务里不能既退役又提交快照，也不能退役仍列在 `context.active_character_names` 的角色。角色阵亡/退场这一章，把变化照写进 `character_changes` 即可，本章退役的角色不必再交一份马上要删的快照，chapter-deltas仍按核心角色标注。退役只表示不再进入热上下文，正文与chapter-deltas不受影响。
- 两类退役都只能在 `mode=append` 提交。退役表示「从此刻起离开当前状态」，而修订事务的chapter-deltas属于被改写的旧章，落在那里会谎报退役发生的章节；`mode=revision` 必须原样重交当前全部上下文条目，需要退役就放到下一次 append。
- `foreshadows.md` 只呈现已经埋设过的当前状态。未来规划仍留在大纲。
- `timeline_events.action` 可为 `upsert/delete`。`未揭示` 的 `reveal_chapter` 必须为 `null`；部分/完全揭示只能填写已经发生的实际章节。
- `mode=revision` 时，chapter-deltas必须重算为修订后该章仍然成立的完整连续性记录；当前角色、伏笔、时间线和上下文则提交受影响对象截至最新已写章的当前值。
- 修订导入截止章内的正文时，会新增或覆盖该章的chapter-deltas；`imported_through_chapter` 不变。
- `delta.new_abilities`（可选）：本章新引入的能力/概念声明，每项 ≤120 字节、最多 12 条。声明进本章chapter-deltas的 `## 本章新能力/概念声明`，供离奇判定与后续查设定回溯。
- `delta.rule_overrides`（可选，每章最多 3 条）：剧情合法打破 `worldbuilding.md` 硬规则清单中的规则时，必须逐条登记 `rule`（被打破的规则原文）、`reason`（剧情理由）、`effective_chapter`（生效章）、`payback`（代价/收束，缺省「未定」）。工具把登记追加进 `tracking/overrides.md`（设定演进账本）；同章同规则重复登记被拒。**未登记的规则突破不会在提交时被正文扫描硬拦（正文是自由文本），但会让后续设定矛盾失去解释依据——把 override 当成「改世界规则的唯一合法出口」，任何打破硬规则的章都必须走这里。**

## 设定演进账本（overrides.md）

`tracking/overrides.md` 是派生视图，从 `_tracking-state.json` 的 `overrides` 生成，逐条记录「哪一章、打破了哪条规则、为什么、代价是什么」。长篇连载时这是防「吃书」的审计账：后续章节写作时读它，能立刻知道哪些旧规则已失效、以什么代价失效。

## 叙事线束（threads.md，多线书专用）

`tracking/threads.md` 是派生视图，从 `_tracking-state.json` 的 `threads` 生成：每条叙事线一行「停在第几章 / 场景 / 本线角色 / 未答悬念」。多线叙事（双主角线、跨时代线、多视角）切线时靠它兜连续性：

- `context.thread`（可选，缺省「主线」）：本事务所属的线名。`mode=append` 提交后，工具自动把本线停点写进 `threads`（`last_stop_chapter` = 本章、`position` = 本事务 position、`active_character_names` = 本事务活跃角色、`open_questions` = 本章 `next_chapter_commitments`）。
- `mode=revision` 不更新停点（修订旧章不改变「线停在哪」）。
- 切回某条线时：`assemble_spec.py` 会把 `threads.md` 里该线的停点带进 spec「前情衔接」，写手照停点接续，不许凭记忆重开。
- `context.md` 的「当前位置」块含 `线程：{当前线名}`，写正文时先看自己站在哪条线上。

## 续写状态卡固定格式

`context.md` ≤12288 字节，由 state 整份生成，只含以下 7 个顶层区块：

1. `## 当前位置`
2. `## 长期约束`
3. `## 核心角色状态`
4. `## 活跃伏笔`
5. `## 近三章速记`
6. `## 下一章承诺`
7. `## 连贯性风险`

其中活跃角色最多 6 人、活跃伏笔确定性选取最多 8 条、近章只保留 3 章。这些是下一章热上下文容量，不是完整characters的容量限制。

## 证据锚定与改编边界（2026-08-15 借鉴 novel-to-game 来源锚定）

每项设定/伏笔/人物特征在事务里必须挂**证据位置**：`source_chapter`（首次出现的章节）+ `source_note`（一句话原文定位）。无证据位置的条目视为发明，draft 冷读可打回。

改编边界四类标签（写进设定条目 `boundary` 字段）：

| 标签 | 含义 | 处理 |
|---|---|---|
| immutable | 不可变核心（主线因果/人物核心动机/世界观硬规则） | 改动必须走 rule_overrides 登记 |
| adaptable | 可变细节（外观/次要称呼/场景布置） | 可直接改，记入 delta |
| open | 未定可发明 | 首次使用时定案并标证据位置 |
| conflicted | 冲突待裁决（前后不一致） | 标注冲突双方证据位置，等作者裁决；裁决前不写入正文 |

## 活跃场景锚点（2026-08-15 借鉴 shuohao 场景/道具一致性）

每章事务 `context` 维护 `active_scene`（推荐）：地点 + 在场人物 + 关键道具状态（谁拿着/放在哪/是否损坏）。章节开头读上一章锚点核对，结尾提交更新。道具状态变化（获得/丢失/损毁）必须记入 delta——防「上一章丢了下一章又掏出来」。
