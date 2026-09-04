# novel-writer 架构与协议（权威文档）

> 本文档是技能的协议权威：CHANGES 变更申报、六道门禁、规则库双投影、架构分层。
> 其他文档与本文件冲突时，以本文件为准。
> 设计源流：liyu 平台（事实状态机 + 门禁 + 同源双投影）+ 通用引擎与领域数据分离原则。

## 〇、处理三原则（总纲）

所有动作先问由谁做，顺序如下：

| 判定 | 处理者 | 例子 |
|---|---|---|
| 算法能判定的（有标准答案） | 纯脚本，LLM 不出场 | 门禁校验、字数、错字、履约率、伏笔逾期 |
| 脚本先提取、LLM 消费结构化结果 | 脚本组装 → LLM 只做判断 | spec 蓝图组装、冷读材料拼装、事务骨架生成 |
| 必须 LLM 理解的 | LLM（低频） | 写正文、冷读评分、剧情判断 |

推论：agent 不手抄确定性内容（脚本组装）、不手改派生视图（脚本渲染）、不凭记忆查设定（走 story_query CLI）。

## 一、CHANGES 变更申报协议（schema v2）

**事实状态不靠模型记忆，靠外部账本。** 每章写完，agent 提交一份 JSON 事务申报「本章改变了什么」；脚本校验通过后合并进唯一权威 `tracking/_tracking-state.json`，再渲染出派生视图（context.md / foreshadows.md / timeline/ 等）。下一章的 spec 蓝图由脚本从账本组装——一致性建立在申报-校验-合并循环上，不建立在上下文记忆上。

### 事务结构

```json
{
  "schema_version": 2,
  "mode": "append",
  "chapter": 10,
  "chapter_title": "…",
  "expected_state_revision": 9,
  "delta": {
    "result": "本章结果一句话（≤480 字节）",
    "character_changes": [{"name": "…", "change": "…"}],
    "plot_points":  ["本章推进/新增的情节点（≤8 条）"],
    "foreshadow_changes": [{"action": "upsert|delete", "id": "F027（三位格式 F\\d{3}）", "summary": "…",
                      "planted_chapter": 10, "planned_resolution_chapter": 15,
                      "status": "已埋|已回收|已过期|放弃", "importance": "高|中|低"}],
    "timeline_events": [{"action": "upsert|delete", "id": "E001",
                      "story_time": "…", "objective_fact": "客观事实",
                      "reader_knowledge": "读者此刻知道的", "characters": ["涉及角色"],
                      "reveal_status": "未揭示|部分揭示|已揭示",
                      "reveal_chapter": 10}],
    # id 必填且格式 E001；reveal_status=部分揭示/已揭示 时 reveal_chapter 必填
    "items":   [{"action": "upsert|delete", "name": "道具名", "holder": "现持有者", "note": "…"}],
    "secrets": [{"action": "upsert", "name": "秘密名", "known_by": "知情者，顿号分隔", "revealed": false}],
    "pledges": [{"action": "upsert", "name": "誓约名", "due_chapter": 15, "status": "未兑现|已兑现|已破誓"}],
    "constraints":  ["长期约束，一条一句"],
    "next_chapter_commitments": ["下一章必须接住的承诺"],
    "new_abilities": ["本章新引入的能力/概念（≤12 条）"],
    "rule_overrides": [{"rule": "被打破的硬规则原文", "reason": "剧情理由",
                        "effective_chapter": 10, "payback": "代价/收束"}]
  },
  "context": {
    "position": {"volume": "…", "volume_start_chapter": 1, "story_time": "…", "scene": "…"},
    "active_scene": "当前场景锚点：地点+在场人物+关键道具状态（可选）",
    "thread": "主线",
    "long_term_constraints": ["…"],
    "active_character_names": ["…"],
    "continuity_risks": ["…"]
  },
  "character_snapshots": {
    "角色名": {"identity": "…", "location": "…", "goal": "…", "state": "…",
               "alive": true,
               "abilities_resources": ["…"], "relationships": ["…"],
               "knowledge": ["…"], "open_threads": ["…"]}
  }
}
```

### delta 十二类变更（对齐 liyu CHANGES）

| 类别 | 字段 | 防什么 |
|---|---|---|
| 角色状态 | `character_changes[].change` + 快照 `location`/`alive` | 死者移动（死亡铁律：已死者 location 变化即拒收；置 `alive:false` 必须有明确死亡宣告） |
| 情节/冲突 | `plot_points` | 冲突悬空不推进 |
| 伏笔 | `foreshadow_changes`（状态机：已埋→已回收/已过期/放弃） | 埋而不收、收而不埋；已回收的悬念进 spec 反向提示「严禁重复写」 |
| 时间线（双视图） | `timeline_events[].{objective_fact,reader_knowledge}` | 作者视角泄露（读者不该知道的提前知道） |
| 道具 | `items[].{holder}` | 道具分身、凭空易手 |
| 秘密 | `secrets[].{known_by,revealed}` | 秘密对不知情者泄露 |
| 誓约 | `pledges[].{due_chapter,status}` | 立誓不还（「第N章前兑现」章口径，账本记录，逾期复核靠 G3 advisory） |
| 长期约束 | `constraints` | 倒计时/期限被遗忘 |
| 下章承诺 | `next_chapter_commitments` | 断章不接 |
| 能力边界 | `new_abilities` | 能力体系无中生有 |
| 规则突破 | `rule_overrides`（理由+代价，登记进 overrides.md） | 长篇吃书 |
| 结果 | `result` | 水章（无净变化） |

### 修订旧章的「此刻」保护

修订非末章（chapter < last_committed_chapter）时，提交的 `character_snapshots` 与 `context` **不落当前状态**——快照与 context 是「此刻」事实，回头改旧稿不代表写作位置回退；该章的变化只落章级 delta 存档（chapter-deltas/）。仅 append 或修订恰为末章时才推进快照与 context。因此：**角色退役（retired_characters）只能走 append 事务**，revision 携带会被拒收。

### 版本兼容

- 事务 `schema_version` 接受 1 与 2（v1 无 items/secrets/pledges/plot_points，全部可选字段，旧事务草稿照常提交）
- 账本文件接受 v4 与 v5：v4 缺 items/secrets/pledges 键按空账处理，首次 commit 后自动升 v5
- `tracking/ledger.md`（道具/秘密/誓约派生视图）为 v5 新增，首次 `tracking_commit.py check` 自动补写

### 硬约束速查

- 提交前先 `tracking_commit.py check` 拿 `state_revision` 填 `expected_state_revision`（不匹配 = stale 拒收）
- `active_character_names` ⊆ `character_snapshots`（恰好相等：少报缺快照，多报非核心）
- `character_snapshots` 必须恰好等于本章出场核心角色集合（未出场者两边都不进）
- `context.thread` 多线叙事必填，缺省「主线」；`active_scene` 可选但推荐每章更新（写前核对上一章锚点）
- `delta.result` ≤480 字节；`constraints` 只收字符串
- 替换/删除 `continuity_risks` 旧条目必须把原文逐字放进 `delta.retired_context_items`
- `rule_overrides` 同章最多 3 条；未登记的硬规则突破会被 G3 拒收
- ID 格式：伏笔 `F` + 三位数字（F001）；时间线 `E` 开头同理。delta 总字节 >1536 会有体积警告（长期超标请精简）
- `reveal_status` 为「部分揭示/已揭示」时 `reveal_chapter` 必填
- **新增伏笔（账本中无此 ID）必须填 `planned_resolution_chapter`**，否则 G3 拒收（强制回收计划）

### 场景锚点与死亡铁律

**场景锚点（active_scene）**：每章 `context` 维护（推荐）：地点 + 在场人物 + 关键道具状态。章节开头读上一章锚点核对，结尾提交更新。道具状态变化（获得/丢失/损毁）必须记入 `delta.items`——防「上一章丢了下一章又掏出来」。

**死亡铁律（G3 硬拦）**：快照 `alive:false` 的角色 location 再变化 → 拒收（复活须走 `rule_overrides` 登记）；`alive` 置 false 时 `change` 必须含「{角色名}」与硬死亡词的邻近共现（词表 `references/death-lexicon.json` 三闸：硬词=宣告、软词「假死/昏迷」不算、硬词+推测词「差点/传闻」=推测语境不算）——自由文本含糊描述不翻转存活，宁缺毋滥不猜死活。

## 二、六道门禁（G1–G6）

对应 liyu 的 6 道生成门禁，挂载在各 `advance` 检查点与事务提交上。**error 拦截，warning 放行。**

| 门禁 | 含义 | 实现挂载点 |
|---|---|---|
| G1 协议解析 | 事务 JSON 合法（schema v2 白名单校验） | `tracking_commit.py` normalize |
| G2 引用校验 | 快照恰好等于本章变更角色集合、F 编号格式合法、退役/删除引用真实存在 | `tracking_commit.py`（active_character_names ⊆ snapshots、FORESHADOW_ID 格式） |
| G3 一致性校验 | 变更与快照矛盾：死亡铁律（死者移动/无宣告置死）、关系极性翻转无因果、伏笔状态机、硬规则突破未登记 | `_tracking/merge.py` + `check_continuity.py` |
| G4 未知实体 | 正文出场的有名角色必须申报（快照+changes），临时龙套豁免 | `checks.py unknown_speakers` |
| G5 描写一致性 | 风格基线偏差 + AI 味 + 语病/说教密度（规则库检查侧） | `checks.py style_baseline/deai` + `check_engine.py` |
| G6 履约检查 | spec 履约清单勾选率 ≥80% + 选角出场核对（计划出场的角色是否真在正文出现，缺席 ≥ max(2, ⌈2n/3⌉) 拦截） | `checks.py spec_fulfillment` + `cast_presence` + `check_spec_copy.py` |

连续性 advisory 分两路，均带 RIX 风险两级（med=强证据建议回修，low=提示复核）：check_continuity.py（med：死者活跃/誓约逾期/秘密不变式/时间算术；low：伏笔逾期/堆积/编号缺口/规则未验证/死者遗物挂账/文本承诺逾期）与 check_seam.py（med：拼接断裂 seam-conflict 与时间跳跃）。单段检测故障降级为一条 internal-error 不中断其余检测。

字数闸门独立于 G1–G6（按平台×类型生效：硬下限 70%/硬上限 130% 拦截，软区警告，连续 3 章同软区升级拦截；未选平台整体跳过）。

## 三、写作规则库（同源双投影）

**一份规则同时投射到写前与写后**——写前注入 prompt（防患），写后同一份规则做检查（验收）。加规则只改 JSON，零代码。

`references/writing-rules.json`（下为格式示意，实际内容以文件为准）：

```json
{
  "rules": [
    {
      "id": "hook-ending",
      "name": "章末钩子",
      "tier": "standard",
      "scope": ["generate", "rewrite"],
      "platform": "番茄",
      "guide": "章末以危机/悬念/渴望/情绪四类钩子之一收尾（四类轮换，不连章同型），禁止总结式收尾",
      "check": {"type": "regex", "pattern": "(总结|综上所述|这一夜.{0,10}想了很多)$", "hint": "章末疑似总结式收口，缺钩子"}
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `id` / `name` | 标识与展示名 |
| `tier` | `core`（红线，恒查恒注入）/ `standard`（按平台与场景） |
| `scope` | 适用场景：`generate` / `rewrite` / `polish` / `outline` |
| `platform` | `all` 或 番茄/起点/晋江/知乎/七猫 |
| `guide` | 写前祈使句——`assemble_spec.py` 按场景+平台过滤后渲染进 spec.md「规则注入」节 |
| `check` | 检查项——check_engine 三类格式（pair/regex/wordlist），按平台过滤后跑 G5 |

与 `check-rules/*.json`（typo/prose/sermon，纯机械病句）的关系：机械病句无「写前指导」语义，留在 check-rules；writing-rules.json 收**写作纪律**（钩子/爽点/对话比例/节奏）。两处都是数据驱动，改 JSON 不改代码。

## 四、架构分层（通用层 + 领域层）

原则：**通用引擎与领域数据分离，路径零硬编码**。换领域时通用层整层复用，只换领域数据与特定模块。

### 通用层（与写作无关）

| 资产 | 职责 |
|---|---|
| `scripts/pipeline.py` | 步骤状态机 + 门禁（gate 顺序锁/文件锁、advance 质量校验、checkpoint） |
| `scripts/tracking_commit.py`（+ `_tracking/`） | 状态账本：CHANGES 事务 → 唯一权威 state → 派生视图，stale 防覆盖（G1–G3） |
| `scripts/check_engine.py` | 规则检查引擎：解释执行 JSON 规则，零领域词表 |
| `scripts/chapter_flow.py` | 流程仪表盘：按状态打印剩余命令，批量执行确定性动作 |
| `scripts/check_spec_copy.py` | 计划文档 vs 产出文档 照搬检测 |

### 领域层（写作数据 + 模块）

| 类别 | 资产 |
|---|---|
| 规则数据 | `writing-rules.json`（纪律双投影）、`check-rules/*.json`（机械病句）、`platform-sensitive-words.txt`、`word-count.json` |
| 领域检查 | `checks.py`（G4–G6 + 字数 + outline 校验）、`check_continuity.py`（G3 advisory） |
| 领域流程 | 五步主线（init/outline/draft/revise/archive）+ 六分支（scan/analyze/deslop/query/learn/polish） |
| 领域知识 | `writing-methods/`（34 方法论，先查 INDEX）、`genre-prose-cards/`（32 题材卡）、`author-styles/`、`craft-canon.md`、`editor-checklist.md`、`platform-review.md` |
| 领域检测器 | `skills/branch/story-deslop/scripts/check-ai-patterns.js`（AI 味正则，G5 调用） |

### 路径纪律

SKILL.md 只用 `{SKILL_DIR}` 占位符（以技能加载时注入的 Base 目录为准）；脚本内部 `Path(__file__).resolve()` 自定位；绝不写死机器路径。项目目录由脚本从 cwd 向上找 `.story/` 自动定位。

## 五、扩展方式

1. **加一条写作纪律**：`writing-rules.json` 加一条（guide + check 双投影自动生效）
2. **加一条机械检查**：`check-rules/` 对应 JSON 加条目；全新类别 → 新 JSON + checks.py 三行封装
3. **换领域复用**：复制通用层五脚本，提供自己的规则 JSON 与领域模块
