# novel-writer

> 长篇网文辅助创作系统：解决 AI 写作中的「遗忘」和「幻觉」问题，支持百万字量级连载创作。

## 核心机制

- **事实状态机**：每章写完提交 CHANGES 事务申报「本章改变了什么」（13 类变更：角色/情节/伏笔/时间线双视图/道具/秘密/誓约/约束/下章承诺/能力/规则突破/写手发明/结果），脚本过六道门禁（G1 协议/G2 引用/G3 一致性/G4 未知实体/G5 描写/G6 履约）后合并进状态账本——一致性靠申报-校验-合并循环，不靠模型记忆
- **处理三原则**：算法能判定的脚本做；脚本可提取的脚本组装后给 LLM；必须 LLM 理解的才用 LLM
- **写作规则库同源双投影**：`references/writing-rules.json` 一份规则同时供写前注入（进 spec 蓝图）与事后检查（G5），加规则只改 JSON
- **写手档案**：本书写手固定为 yeyue 子代理（Minimax M3）——正文委派 yeyue 执笔，主 agent 编排与校验；AI 味与文风纠缠，检测基线与写前避开项按写手实测校准（`writer_profile.py calibrate` → `.novel/writer.md`），档案缺失回退全局默认
- **委派契约**：写手规约收敛在 `references/writer-brief.md`（输入范围/硬规约/事务字段白名单/自校/汇报格式），委派任务书只传四行指针——给 AI 消费的文件以「机器好执行」为准，不随章重述
- **冷读裁判**：独立子代理干净上下文四维评分，≤2 分打回

协议与架构详见 [references/architecture.md](references/architecture.md)。

## 主线流程

```
init → outline → draft → revise → archive
```

脚本硬校验 + 状态账本 + 冷读裁判；支持续写、改稿、查设定、剧情爆破等全流程操作。

## 支线能力

| 支线 | 能力 |
|---|---|
| `story-long-scan` | 扫榜：什么题材火、平台排行 |
| `story-long-analyze` | 拆书：黄金三章分析 |
| `story-deslop` | 去 AI 味：unslop gap 分析 + 禁用词检测 |
| `story-query` | 查设定：角色状态、伏笔追踪、境界查询 |
| `story-learn` | 记忆：好写法、有效钩子沉淀 |
| `story-polish` | 润色：修病句、改稿 |

## 触发场景

- 「写小说」「开新书」「写大纲」「继续写」「写下一章」「改第 X 章」
- 「扫榜」「什么题材火」「去 AI 味」「拆书」「查设定」「润色」「修病句」

## 安装

```bash
git clone https://github.com/mrzhangkris/novel-writer.git
# 把 novel-writer/SKILL.md 复制到你所用 runtime 的技能目录即可
```

各 runtime 技能目录速查：

| Runtime | 技能目录 |
|---|---|
| DSH | `~/.dsh/skills/` |
| Claude Code | `~/.claude/skills/` |
| Codex / Cursor / OpenClaw 等 | 按各自 skills 根目录约定 |

## 上游署名

本技能由 [oh-story-claudecode](https://github.com/worldwonderer/oh-story-claudecode)（worldwonderer）→ [oh-story-opencode](https://github.com/wyouwd1/oh-story-opencode)（wyouwd1）迁移改造，并融合 webnovel-writer、ai-fiction-writer 方法论。详见 [ATTRIBUTION.md](ATTRIBUTION.md)。

## 许可

MIT © 2026 mrzhangkris
