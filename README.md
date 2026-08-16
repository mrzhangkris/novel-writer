# novel-writer

> 长篇网文辅助创作系统：解决 AI 写作中的「遗忘」和「幻觉」问题，支持百万字量级连载创作。

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
