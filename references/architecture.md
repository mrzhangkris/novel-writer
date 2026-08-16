# novel-writer 架构分层（通用层 + 写作特定层）

> 原则：**通用引擎与领域数据分离，路径零硬编码**。
> 本技能 = 一套与领域无关的流程/检查机械 + 一套写作领域的数据与模块。
> 换领域（如安全审查技能）时：通用层整层复用，只换「领域数据 + 特定模块」。

## 一、通用层（与写作无关，可整体复用于任何领域技能）

| 资产 | 职责 | 与领域无关的部分 |
|---|---|---|
| `scripts/check_engine.py` | **规则检查引擎**：解释执行 `check-rules/*.json`，三类规则（presence 词表/词对、regex 正则+提示、count_threshold 计数+阈值）。引擎内零领域词表 | 全部 |
| `scripts/pipeline.py` | 步骤状态机 + 门禁（gate 顺序锁/文件锁、advance 质量校验、checkpoint 人工确认点） | 机制本身；步骤语义（init/outline/draft…）是领域编排 |
| `scripts/tracking_commit.py`（+ `_tracking/`） | 状态账本：JSON 事务 → 单一权威 state → 派生 Markdown 视图，stale 防覆盖 | 机制本身；账本字段（伏笔/角色/能力）是领域 schema |
| `scripts/chapter_flow.py` | 流程仪表盘：按状态打印剩余步骤命令清单，批量执行确定性动作 | 机制本身；打印的步骤清单是领域编排 |
| `scripts/check_spec_copy.py` | 细纲照搬检测（连续重合 ≥15 字判定） | 判定机制通用（任何「计划文档 vs 产出文档」场景） |
| 规则数据目录 `references/check-rules/` | 规则 JSON（见第三节） | 格式通用；**内容**是写作领域数据 |

## 二、写作特定层（领域数据 + 领域模块）

| 类别 | 资产 | 说明 |
|---|---|---|
| 检查规则数据 | `check-rules/typo-rules.json`（错字对/的地得/赘余词）、`prose-rules.json`（语病正则）、`sermon-rules.json`（说教信号词+阈值） | 喂给 check_engine；加一条检查=加一条 JSON，不改引擎 |
| 其他规则数据 | `platform-sensitive-words.txt`（敏感词）、`word-count.json`（平台字数标准）、`.novel/banned-words.txt`（作者禁用词） | 同样是数据驱动 |
| 领域检查模块 | `checks.py` 的 cmd_outline（章节条目/伏笔/概念/人物卡/总纲）、cmd_wordcount、cmd_style_baseline、cmd_world_rules_advisory、cmd_unknown_speakers、cmd_cross_chapter、cmd_spec_fulfillment、cmd_pacing_balance、cmd_meta_mark、cmd_deai（调 check-ai-patterns.js） | 依赖写作概念（章节/伏笔/人物卡/世界观），不可通用 |
| 领域流程 | 五步主线子技能（init/outline/draft/revise/archive）+ 六支线（扫榜/拆书/去AI味/查询/记忆/润色） | 编排的是写作语义 |
| 领域知识 | `writing-methods/`（34 份方法论）、`genre-prose-cards/`（32 题材卡）、`author-styles/`、`craft-canon.md`（审美总纲）、`editor-checklist.md`、`platform-review.md` | 纯知识资产 |
| 领域检测器 | `skills/branch/story-deslop/scripts/check-ai-patterns.js` | AI 味规则与校准注释深度绑定，作为独立检测器保留（输入已数据化：whitelist/extra-words 文件） |

## 三、check-rules JSON 格式（通用引擎的输入契约）

规则文件放 `references/check-rules/{名}.json`，一个文件一类检查。三类规则可混排在 `"rules"` 数组：

```json
{
  "domain": "领域名（文档用途）",
  "sample_context": 10,
  "rules": [
    {"type": "pair", "wrong": "必竟", "right": "毕竟",
     "hint": "用词检测：「{wrong}」疑为「{right}」的错写"},
    {"type": "regex", "pattern": "通过.{0,20}(?:使|让|使得)[^，。]{2,}",
     "hint": "主语残缺：…删『通过』让主语站出来"},
    {"type": "wordlist", "words": ["凯旋归来", "免费赠送"],
     "hint": "成分赘余「{word}」——删掉赘余部分"}
  ]
}
```

计数阈值类（独立顶层对象，不放在 rules 数组）：

```json
{
  "type": "count_threshold",
  "patterns": ["这意味着", "换句话说"],
  "warn": 1, "block": 4,
  "sample_context": 8, "max_samples": 3,
  "warn_hint": "…{hits} 处（{samples}）——建议…",
  "block_hint": "…{hits} 处（{samples}）——必须改…"
}
```

- hint 占位符：`{g0}` 整段命中、`{g1..gn}` 捕获组、`{wrong}/{right}/{word}`、`{hits}/{samples}`
- presence 类全部 advisory（打印 ⚠️，返回 0）；count_threshold 类 hits≥block 拦截（打印 ❌，返回 1）
- 引擎 API：`load_rules(名)` / `run_rules(text, rules)` / `run_count_rule(text, rule)`
- **改阈值/加词表/加规则 = 改 JSON，零代码改动**；规则文件缺失/损坏时引擎降级为提示跳过，不炸流程

## 四、扩展方式

1. **写作域加一条检查**：在对应 JSON 加条目（如新错字对 → typo-rules.json）；全新检查类别 → 新 JSON + checks.py 加一个三行封装 cmd。
2. **换领域复用**（如安全审查）：复制通用层（check_engine/pipeline/tracking_commit/chapter_flow），提供自己的 `check-rules/*.json`（如 secret-patterns.json、danger-calls.json）+ 自己的领域模块（如 cmd_secret_scan），领域知识放自己的 references。
3. **路径纪律**：SKILL.md 只用 `{SKILL_DIR}` 占位符；脚本只用 `Path(__file__)` 自定位；绝不写死任何机器绝对路径。
