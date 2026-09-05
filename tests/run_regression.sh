#!/usr/bin/env bash
# novel-writer 一键回归测试
#
# 从零建一本迷你书，跑通完整主线：init → outline（情绪曲线）→ 两章
# （spec 履约清单 + 事务 + 全部闸门 + 冷读趋势 + 归档 + 模式沉淀）→
# 导出成书 → 账本终检。任何一步失败即退出非零。
#
# 另覆盖六个新机制：
#   1. ledger.md 派生视图（items/secrets/pledges 提交后落视图 + check 自动补写 + 篡改拒收）
#   2. 誓约/秘密检测（check_continuity 报 pledge-overdue / secret-invariant）
#   3. 死亡铁律（死者移动/无宣告/软词拒收，硬词放行，复活须登记）
#   4. 选角出场检查（失约拦截 / 全员未出现降 warning / 旧 spec 跳过）
#   5. writing-rules.json 双投影（spec 规则注入 + 写后 check 真实执行）
#   6. check_seam.py 跨章拼接（延续通过 / 突变告警 / 退出码恒 0）
#
# 用法：bash {SKILL_DIR}/tests/run_regression.sh
# 依赖：python3、node（去AI味检测用）。改动任何脚本后跑一遍。

set -euo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

pass() { echo "✓ $1"; }
fail() { echo "✗ $1"; exit 1; }

echo "=== 回归测试（工作目录 ${WORK}）==="

# ---- init ----
python3 "$SKILL_DIR/skills/mainline/novel-init/scripts/setup.py" --root-dir "$WORK" >/dev/null || fail "setup.py"
python3 "$SKILL_DIR/skills/mainline/novel-init/scripts/new.py" rg1 --title "回归测试" --genre 都市脑洞 --platform 番茄 --type 短故事 --root-dir "$WORK" >/dev/null || fail "new.py"
cd "$WORK/rg1"
python3 "$SKILL_DIR/scripts/pipeline.py" checkpoint clear cp1 >/dev/null || fail "cp1 clear"

# 题材卡融入
cp "$SKILL_DIR/references/genre-prose-cards/都市脑洞.md" 题材卡.md || fail "题材卡"
pass "init + 题材卡"

# ---- setup：世界观硬规则 + 契约 ----
cat > worldbuilding.md <<'EOF'
# 世界观
## 自由叙事
现代都市，普通生活规则。
## 硬规则清单
| 类型 | 规则 | 触发词 |
|------|------|--------|
| 禁止 | 此世界无超自然力量 | 魔法、法术、异能 |
## 能力白名单
| 能力名 | 类型 | 等级 | 归属 |
|--------|------|------|------|
| 经商头脑 | 其他 | 无等级 | 主角 |
EOF
python3 - <<'PY'
t = open('reader-contract.md', encoding='utf-8').read()
for k, v in [('读者来看什么：{}','读者来看什么：都市脑洞爽文'),('这本书承诺给读者什么体验：{}','这本书承诺给读者什么体验：每章一个脑洞反转'),('兑现节奏：{}','兑现节奏：每章都有'),('绝不写什么：{}','绝不写什么：无超自然'),('读者雷点：{}','读者雷点：无'),('题材禁区：{}','题材禁区：无'),('因果权：{}','因果权：主角决策'),('结算权：{}','结算权：收益归主角')]:
    t = t.replace(k, v)
open('reader-contract.md', 'w', encoding='utf-8').write(t)
PY
python3 "$SKILL_DIR/scripts/pipeline.py" advance setup >/dev/null || fail "advance setup"
pass "setup 推进"

# ---- outline（含情绪曲线）----
cat > outline.md <<'EOF'
# 大纲
## 章纲
### 第1章：旧街降价
- 本章目标：主角发现旧街集体降价，察觉异常
- 场景安排：旧街夜市
- 关键事件：蹲点发现凌晨货车送货
- 章末钩子：司机是失踪三年的房东
- 新概念：旧街
### 第2章：房东归来
- 本章目标：周四海摊牌
- 场景安排：旧街西头槐树下
- 关键事件：安置费真相
- 章末钩子：旧街拆迁在即
- 新概念：无
## 结构标记
- 起：第1章；承：第2章
## 情绪曲线
- 第1章紧张、第2章爽
## 伏笔规划
| 编号 | 内容 | 埋设章 | 计划回收章 | 类型 |
|---|---|---|---|---|
| F1 | 神秘房东周四海 | 第1章 | 第2章 | 人物 |
## 概念预算
- 第1章：引入「旧街」1 个；第2章：0 个
EOF
# ---- 人物卡（outline 门禁：长期目标/底线/个人故事四件套 非空；主角 + 核心配角各一张）----
cat > characters/陆川.md <<'EOF'
# 人物卡：陆川

## 核心性格

1. 较真——被骗一车货后，坚持五年把旧街的每笔账弄清楚
2. 念旧——守着旧街杂货店不肯搬
3. 怂中有勇——平时怕事，该出头时第一个顶上

## 动机与目标

- 长期目标：在旧街把日子过明白，弄清旧街背后的真相
- 当前目标：搞清夜运现金是谁在背后操盘

## 底线与恐惧

- 底线：不坑街坊，不做昧良心的事
- 恐惧/软肋：怕旧街散伙，怕欠人情还不上

## 能力

- 初始能力：经商头脑

## 个人故事（详卡专属）

- 出身与来处：旧街杂货店老板，五年前被骗一车货后来旧街落脚
- 关键转折：被周四海借三万块救急、连欠条都没让打——从此把旧街当家
- 未了的执念：想在旧街拆迁前把五年来的每笔账都记完
- 独处时的样子：打烊后坐在柜台后数账本，一页一页翻，像在数旧街的命
EOF
cat > characters/周四海.md <<'EOF'
# 人物卡：周四海

## 核心性格

1. 重情——还清高利贷后第一件事是回旧街还人情
2. 隐忍——三年不联系任何街坊
3. 体面——再难也不在街坊面前露穷

## 动机与目标

- 长期目标：把欠旧街的人情全部还清
- 当前目标：把安置费安全发到每户手上

## 底线与恐惧

- 底线：不连累旧街，不把债主引到街坊面前
- 恐惧/软肋：怕街坊知道自己落魄的那三年

## 能力

- 初始能力：货车驾驶、境外人脉

## 个人故事（详卡专属）

- 出身与来处：旧街老房东，旧街十七家铺子的租约都捏在他手里
- 关键转折：欠两百万高利贷被迫出国三年，白天送外卖晚上跑货车还清债
- 未了的执念：把当年街坊帮他看铺子、留卤味的情一一还清
- 独处时的样子：一个人看旧街全景照片，边角磨得发毛也舍不得换
EOF
# ---- 三维盘点（outline 第 1.5 步硬门禁：characters-pool.md 存在 + 决策列非空）----
cat > characters-pool.md <<'EOF'
# 人物池盘点（characters-pool）

> 回归测试最小盘点：单线短篇，2 张详卡覆盖全部应有人物。

## 三维盘点矩阵

### 势力

| 项目 | 应有人物（agent 推断） | 已有卡 | 缺卡 | 决策 |
|------|----------------------|--------|------|------|
| 旧街街坊 | 陆川、周四海、老周、马婶 | 陆川, 周四海 | 老周、马婶 | 建简卡（老周、马婶为见证者，第 2 章后按 draft 纪律补卡） |

### 时代

| 项目 | 应有人物（agent 推断） | 已有卡 | 缺卡 | 决策 |
|------|----------------------|--------|------|------|
| 当代 | 无跨时代 | （无） | （无） | 不建卡（单时代短篇） |

### 家族

| 项目 | 应有人物（agent 推断） | 已有卡 | 缺卡 | 决策 |
|------|----------------------|--------|------|------|
| 无家族设定 | （无） | （无） | （无） | 不建卡 |

## 盘点决策记录

（回归测试：2 张详卡 + 2 个简卡待 draft 阶段补）
EOF
python3 "$SKILL_DIR/scripts/pipeline.py" advance outline >/dev/null || fail "advance outline"
pass "outline 推进（情绪曲线）"
# pacing 自动投影：情绪曲线 → tracking/pacing.md 初稿（幂等 upsert；爽→高、紧张→中）
grep -q "| 第2章 | 高 | 爽" tracking/pacing.md || fail "pacing 情绪强度未投影"

# ---- 章函数：写一章的完整闭环 ----
write_chapter() {
  local N="$1"
  python3 "$SKILL_DIR/scripts/new_chapter.py" --chapter "$N" >/dev/null || fail "new_chapter $N"
  python3 "$SKILL_DIR/scripts/assemble_spec.py" --chapter "$N" >/dev/null || fail "assemble_spec $N"
  python3 -c 'import sys; from pathlib import Path; p = Path("chapters/chapter-" + f"{int(sys.argv[1]):03d}" + "/spec.md"); t = p.read_text(encoding="utf-8"); t = t.replace("- [ ] ", "- [x] "); p.write_text(t, encoding="utf-8")' "$N" || fail "spec tick $N"
  cat >> "chapters/chapter-$(printf %03d "$N")/spec.md" <<'EOF'
# 写作蓝图
## 大纲要点（履约清单，逐条勾选）
- [x] 本章目标：推进主线
- [x] 场景安排：旧街
- [x] 关键事件：核心冲突发生
- [x] 章末钩子：悬念
## 概念要点
- 旧街（深化）
## 角色要点
- 陆川：警觉
## 前情衔接
- 无
## 知情边界
- 读者已知：旧街异常
- 读者不知：真相
## 时间线定位
- 故事时间：周五夜
- 距上章过去：-
## 伏笔指令
- 推进 F1
## 题材要点
- 生活脑洞
## 风格指令
- 短句
EOF
  python3 - <<PY
paras = [
"周五晚上九点，旧街的灯一盏接一盏灭下去。",
"陆川蹲在杂货店门口，数着对面那排铺子。水果店半价，卤味店买一送一。",
"他在旧街开了五年店，这条街的老板们什么脾气他门儿清。",
"陆川回了店里，把卷帘门拉下一半，猫在门后。",
"凌晨两点半，街口传来发动机的声音，压得很低。",
"一辆厢式货车拐进旧街，没开车灯。",
"货车在每家店门口停两分钟，往下塞纸箱。",
"陆川数了数，一共十七家店，一家没落下。",
"轮到他的杂货店时，他屏住呼吸。脚步声停在门口。",
"「开门，陆川。」那声音落进卷帘门后的黑暗里，像块石头砸在水面上。陆川浑身一激灵。",
"这个声音他听过，三年前听过。",
"他慢慢抬起头，从门缝往外看。货车司机站在路灯下，摘下帽子。",
"是周四海。旧街的房东。三年前说要出国，再没回来的人。",
"三年前，周四海走得很突然。旧街十七家铺子的租约都捏在他手里。",
"陆川当时还去派出所问过。民警说，人自己办的出国手续，不是失踪。",
"可人回来了。半夜两点半，开着一辆黑灯货车，往租户店里塞纸箱。",
"陆川没开门。他贴着门缝，看着周四海把最后一只纸箱塞进隔壁卤味店。",
"那一眼，陆川看得清楚：周四海的右脸上，多了一道疤，从眉骨拉到嘴角。",
"货车重新发动，从街尾拐了出去。陆川等了十分钟，才把卷帘门拉开一条缝。",
"卤味店的纸箱还在地上。他摸黑拆开，伸手进去。里面是一捆一捆的现金。",
"陆川把手缩回来，后脑勺发凉。家家户户都在干同一件事：分钱。",
"他蹲在卤味店门口，把纸箱原样封好。手机忽然震了一下。",
"陌生号码发来短信：「看见什么了，就当作没看见。明晚，老地方见。」落款一个字：周。",
"陆川盯着屏幕，拇指停在拨号键上。报警，还是不报？",
"凌晨三点整，街口的灯熄了。陆川慢慢起身往回走。",
"杂货店的卷帘门上，贴着一张便签纸。纸上写着三个字：别回头。",
"陆川把便签纸撕下来，捏在手心里。纸还是温的。",
"他猛地回头。街面上空空荡荡，路灯把他的影子抻得老长。",
"风从街尾卷过来，卷着一股没散尽的柴油味。那一夜陆川没睡。",
"他坐在柜台后面，把三年前的事翻来覆去地想。",
"周四海是旧街的老房东，也是旧街的活账本。谁家进货缺钱，找他周转。",
"陆川刚来旧街那年，被人骗了一车货，是周四海借他三万块，连欠条都没让打。",
"「街坊之间，讲这个就见外了。」周四海当时说。",
"可就是这样一个把街坊挂在嘴边的人，三年前一声不吭出了国。",
"走之前那个月，他天天晚上在旧街转悠，一家店一家店地看，像要把什么记进眼睛里。",
"陆川当时以为他是舍不得。现在想想，那眼神不像告别，像数数。",
"天蒙蒙亮的时候，陆川拉开卷帘门。老周已经在水果店门口摆摊了。",
"「老周。」陆川走过去，压低声音，「昨晚上你收到什么了？」",
"老周的手在哈密瓜上停了一拍。「什么昨晚上？」他抬起头，笑得跟平时一样，「我九点就睡了。」",
"陆川盯着他看了两秒，没再问。他转身往回走，听见身后老周轻轻叹了口气。",
"回到店里，他给自己倒了杯凉水，一口灌下去。手机又响了。",
"还是那个陌生号码：「老周嘴严。你学学他。今晚十二点，旧街西头那棵槐树下。一个人来。」",
"陆川把手机扣在柜台上，屏幕的光慢慢暗下去。他知道，今晚必须去。",
"有些事，躲是躲不掉的。他在这条街上住了五年，该还的，该问的，都该有个说法。",
]
text = "\n\n".join(paras) + "\n"
open("chapters/chapter-$(printf %03d "$N")/draft.md", "w", encoding="utf-8").write(text)
print(len([c for c in text if '\u4e00' <= c <= '\u9fff']))
PY
  python3 "$SKILL_DIR/scripts/gen_transaction.py" commit --project . >/dev/null || fail "gen tx $N"
  python3 - <<PY
import json
tx = json.load(open(".story/tx-chapter-$(printf %03d "$N").json", encoding="utf-8"))
names = tx["context"]["active_character_names"] or ["陆川"]
tx["delta"]["result"] = f"第${N}章：旧街夜运现金，房东周四海归来，陆川收到警告便签。"
tx["delta"]["character_changes"] = [{"name": n, "change": "目睹夜运现金"} for n in names]
tx["context"]["active_character_names"] = names
tx["character_snapshots"] = {
  names[0]: {"identity": "旧街杂货店老板", "location": "旧街", "goal": "弄清真相",
             "state": "警觉", "abilities_resources": ["经商头脑"], "relationships": ["周四海：房东"],
             "knowledge": ["旧街集体分钱"], "open_threads": ["周四海的来意"]}
}
json.dump(tx, open(".story/tx-chapter-$(printf %03d "$N").json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
  python3 "$SKILL_DIR/scripts/tracking_commit.py" validate --project . --input ".story/tx-chapter-$(printf %03d "$N").json" >/dev/null || fail "validate $N"
  python3 "$SKILL_DIR/scripts/tracking_commit.py" commit --project . --input ".story/tx-chapter-$(printf %03d "$N").json" >/dev/null || fail "commit $N"
  python3 "$SKILL_DIR/scripts/pipeline.py" advance draft >/dev/null || fail "advance draft $N"
  python3 "$SKILL_DIR/scripts/coldread_material.py" --chapter "$N" --write-review >/dev/null || fail "coldread $N"
  python3 -c 'import sys; from pathlib import Path; p = Path("chapters/chapter-" + f"{int(sys.argv[1]):03d}" + "/review.md"); t = p.read_text(encoding="utf-8"); t = t.replace("> 冷读方式：独立子代理（本文件由 coldread_material.py 生成，材料为原文切片）", "> 冷读方式：inline 降级（回归测试）"); t += "\n- 翻页欲：4 分\n- 认知负荷：4 分\n- 共情验证：4 分\n- 节奏感受：4 分\n结论：通过（无 ≤2 分）\n"; p.write_text(t, encoding="utf-8")' "$N" || fail "review fill $N"
  python3 "$SKILL_DIR/scripts/quality_trend.py" record --scores 4,4,4,4 >/dev/null || fail "trend $N"
  printf '评分：4,4,4,4\n' >> "chapters/chapter-$(printf %03d "$N")/review.md"
  python3 "$SKILL_DIR/scripts/pipeline.py" skip revise >/dev/null || fail "skip revise $N"
  python3 "$SKILL_DIR/scripts/pipeline.py" advance archive >/dev/null || fail "advance archive $N"
  python3 "$SKILL_DIR/scripts/learn.py" add "回归测试模式 $N" --pattern-type other --importance low >/dev/null || fail "learn $N"
  pass "第 $N 章完整闭环"
}

# ---- 第 1 章 ----
python3 "$SKILL_DIR/scripts/gen_transaction.py" init --project . >/dev/null || fail "gen init"
python3 "$SKILL_DIR/scripts/tracking_commit.py" init --project . --input .story/tx-init.json >/dev/null || fail "tracking init"
write_chapter 1

# ---- 第 2 章（含 rule_overrides 登记）----
python3 "$SKILL_DIR/scripts/pipeline.py" next-chapter >/dev/null || fail "next-chapter"
python3 "$SKILL_DIR/scripts/new_chapter.py" --chapter 2 >/dev/null || fail "new_chapter 2"
python3 - <<'PY'
from pathlib import Path
Path("chapters/chapter-002/spec.md").write_text(
"""# 写作蓝图
## 大纲要点（履约清单，逐条勾选）
- [x] 本章目标：周四海摊牌
- [x] 场景安排：旧街
- [x] 关键事件：真相揭示
- [x] 章末钩子：反转
## 知情边界
- 读者已知：夜运现金
- 读者不知：动机
## 时间线定位
- 故事时间：周六夜
## 伏笔指令
- 回收 F1
""", encoding="utf-8")
draft = "\n\n".join([
"周六夜里，陆川提前到了槐树下。",
"风从街尾卷过来，卷着没散尽的柴油味。路灯把他的影子拉得一会儿长一会儿短。",
"他等了二十分钟。槐树的叶子在风里沙沙响，像有什么人在暗处翻纸。",
"十一点五十八分，街口传来脚步声。不快，每一步都踩得很实。",
"周四海从树影里走出来，脸上的疤在月光下发亮。",
"「钱，是我从境外带回来的。」他说，「旧街要拆了。这笔钱，是给街坊们的安置费。」",
"陆川愣住：「那你为什么半夜偷偷发？」",
"周四海沉默了几秒：「因为白天发，会被我欠的那些人追上门。三年前我出国，是为了还债。现在债清了，钱也带回来了。」",
"他顿了顿：「最后一个要还的人情，是这条街。」",
"「三年前，我欠了两百万高利贷。」周四海的声音很平，「债主天天堵在旧街。我要是不走，这条街就完了。我走的时候，什么都没带，就带了一张旧街的全景照片。」",
"他说着，从风衣内兜里掏出一张照片，边角已经磨得发毛。照片上是三年前的旧街，十七家铺子，招牌一个不缺。",
"「在国外这些年，我白天送外卖，晚上跑货车。钱还清了，又攒了一笔。回来一看，旧街要拆了。」",
"陆川接过照片，指腹擦过照片上自己杂货店的招牌。他忽然有点想哭。",
"陆川看着他，忽然想起三年前那个天天在旧街转悠的背影。那是告别，挨家挨户地看，把每张脸都记进眼睛里。",
"「明天开始，钱的事公开。」周四海说，「你替我告诉大家。」",
"陆川点点头。他回头望了一眼旧街，十七家铺子的灯，一盏接一盏亮起来。",
"「那你这三年，过得怎么样？」陆川问。",
"周四海笑了笑，那道疤跟着动了动：「头两年最难。语言不通，送外卖被客人骂，晚上跑货车，一跑就是十二个小时。有几次在车上睡着，差点开进沟里。」",
"「我就想着一件事。」他说，「等钱还清了，回旧街，把欠街坊的都补上。当年他们没人催过我，这情，我记一辈子。」",
"「其实你不欠我们什么。」陆川说。",
"「欠。」周四海摇头，「我走的那年，老周的水果烂了半车，就为了帮我看着铺面。马婶的卤味摊天天给我留一碗。这些账，你们不算，我算。」",
"两个人靠着槐树坐下。夜风把旧街吹得静悄悄的，像一条睡着了的河。",
"「明天，我请大家吃饭。」周四海说，「就在旧街口，摆一长条桌。到时候你帮我张罗。」",
"「行。」陆川说，「老周的哈密瓜管够，马婶的卤味管够。」",
"天快亮的时候，周四海起身告辞。走出几步，他又回过头。",
"「陆川。」他说，「这条街要拆了。但旧街的人，不会散。」",
"陆川站在原地，看着他的背影消失在街口。东边的天，透出了一线白。",
"他低头看了一眼手机。凌晨五点。再过一会儿，整条旧街就要醒过来了。",
"陆川收起那张全景照片，往自己店里走。卷帘门上的便签纸已经被风吹掉了，只剩一点胶痕。",
"他没有再贴新的。回到店里，他把那半张纸压在柜台玻璃下。有些话，不用贴在门上。",
"六点整，旧街的第一盏灯亮了。是马婶的卤味摊。",
"接着是第二盏，第三盏。卖早点的，开杂货的，修鞋的，一家一家把卷帘门拉起来。",
"陆川站在自家店门口，把招牌擦了一遍，又擦了一遍。",
"他忽然觉得，这一晚的旧街，比过去五年任何一个夜晚都要亮。",
"老周推着水果车经过，冲他点了点头。马婶远远地喊：「小陆，来碗卤味面！」",
"「来了！」陆川应了一声，往卤味摊走。",
"晨光铺在旧街的石板路上，把每一个人的影子都照得清清楚楚。",
"新的一天，开始了。旧街的早晨，热气腾腾。",
])
Path("chapters/chapter-002/draft.md").write_text(draft + "\n", encoding="utf-8")
n = len([c for c in draft if '\u4e00' <= c <= '\u9fff'])
print(n)
PY
python3 "$SKILL_DIR/scripts/gen_transaction.py" commit --project . >/dev/null || fail "gen tx 2"
python3 - <<'PY'
import json
tx = json.load(open(".story/tx-chapter-002.json", encoding="utf-8"))
names = tx["context"]["active_character_names"] or ["陆川"]
tx["delta"]["result"] = "周四海摊牌：夜运现金是旧街拆迁安置费，三年前出国是为还债；他请陆川转告街坊。"
tx["delta"]["character_changes"] = [{"name": n, "change": "得知真相，答应转告"} for n in names]
tx["delta"]["foreshadow_changes"] = [
  {"action": "upsert", "id": "F001", "summary": "周四海归来真相：还债后带安置费回国", "planted_chapter": 1, "planned_resolution_chapter": 2, "status": "已回收", "importance": "高"}
]
tx["delta"]["rule_overrides"] = [
  {"rule": "禁止：此世界无超自然力量", "reason": "回归测试：验证设定演进账本登记", "effective_chapter": 2, "payback": "无实际打破，仅测试登记"}
]
# 台账事务（ledger.md 派生视图数据源）：誓约限期第1章（第2章已逾期）、
# 一个合规秘密、一件道具（违规秘密 known_by 为空会被 G1 入口拒收，单独验证见下）。
tx["delta"]["items"] = [
  {"action": "upsert", "name": "旧街全景照片", "holder": "陆川", "note": "周四海随身三年"}
]
tx["delta"]["secrets"] = [
  {"action": "upsert", "name": "还债三年经历", "revealed": True, "known_by": "陆川"}
]
tx["delta"]["pledges"] = [
  {"action": "upsert", "name": "替周四海转告街坊", "due_chapter": 1, "status": "未兑现"}
]
tx["context"]["active_character_names"] = names
tx["character_snapshots"] = {
  names[0]: {"identity": "旧街杂货店老板", "location": "旧街", "goal": "转告街坊", "state": "释然",
             "abilities_resources": ["经商头脑"], "relationships": ["周四海：房东"], "knowledge": ["安置费真相"],
             "open_threads": []}
}
json.dump(tx, open(".story/tx-chapter-002.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
python3 "$SKILL_DIR/scripts/tracking_commit.py" commit --project . --input .story/tx-chapter-002.json >/dev/null || fail "commit 2"
python3 "$SKILL_DIR/scripts/pipeline.py" advance draft >/dev/null || fail "advance draft 2"
python3 "$SKILL_DIR/scripts/coldread_material.py" --chapter 2 --write-review >/dev/null || fail "coldread 2"
printf '评分：4,4,4,4\n' >> chapters/chapter-002/review.md
python3 "$SKILL_DIR/scripts/pipeline.py" skip revise >/dev/null || fail "skip revise 2"
python3 "$SKILL_DIR/scripts/pipeline.py" advance archive >/dev/null || fail "advance archive 2"
grep -q "第2章" tracking/overrides.md || fail "overrides.md 登记"
pass "第 2 章闭环 + override 账本"

# ================ 新机制回归 1：ledger.md 派生视图 ================
# 含 items/secrets/pledges 的事务提交后，tracking/ledger.md 应出现且与账本一致
# （一致性由终检 check 的视图 diff 兜底，这里先断言视图内容）。
test -f tracking/ledger.md || fail "ledger.md 未生成"
grep -q "## 道具（name | 持有者 | 备注）" tracking/ledger.md || fail "ledger.md 缺道具节"
grep -q "旧街全景照片｜陆川" tracking/ledger.md || fail "ledger.md 道具条目不符"
grep -q "还债三年经历｜陆川｜已揭示" tracking/ledger.md || fail "ledger.md 秘密条目不符"
grep -q "替周四海转告街坊｜第1章前｜未兑现" tracking/ledger.md || fail "ledger.md 誓约条目不符"
pass "ledger.md 派生视图（道具/秘密/誓约）"

# ================ 新机制回归 2：誓约/秘密检测 ================
# 誓约 status=未兑现 且 due_chapter(1) < 当前章(2) → check_continuity 报 pledge-overdue；
# 合规秘密（known_by 非空）不得误报。
python3 "$SKILL_DIR/scripts/check_continuity.py" --project . > "$WORK/continuity.txt" 2>&1 || fail "check_continuity 应退出 0（advisory）"
grep -q "pledge-overdue" "$WORK/continuity.txt" || fail "未报 pledge-overdue"
grep -q "替周四海转告街坊" "$WORK/continuity.txt" || fail "pledge-overdue 未指名誓约"
if grep -q "还债三年经历" "$WORK/continuity.txt"; then fail "合规秘密（known_by 非空）被误报 invariant"; fi
pass "誓约逾期检测 + 合规秘密不误报"

# 违规秘密（revealed=true 且 known_by 空）应被账本 schema 入口拒收（fail-closed）。
# 断言报错含「known_by must not be empty」——证明拒绝的是不变式而非 JSON 语法，
# 且被拒事务不得污染 state。
python3 - <<PY
import json
st = json.load(open("tracking/_tracking-state.json", encoding="utf-8"))
base = json.load(open(".story/tx-archive/tx-chapter-002.json", encoding="utf-8"))
base["mode"] = "append"
base["chapter"] = 3
base["expected_state_revision"] = st["state_revision"]
base["delta"]["character_changes"] = []
base["delta"]["secrets"] = [{"action": "upsert", "name": "安置费来源", "revealed": True, "known_by": ""}]
base["delta"]["pledges"] = []
base["delta"]["items"] = []
base["delta"]["rule_overrides"] = []
base["delta"]["foreshadow_changes"] = []
base["character_snapshots"] = {}
json.dump(base, open(".story/tx-secret-bad.json", "w", encoding="utf-8"), ensure_ascii=False)
PY
python3 "$SKILL_DIR/scripts/tracking_commit.py" commit --project . --input .story/tx-secret-bad.json > "$WORK/secret-bad.txt" 2>&1 && fail "违规秘密（revealed 且 known_by 空）未被 schema 拒收"
grep -q "known_by must not be empty" "$WORK/secret-bad.txt" || fail "拒收原因不是 known_by 不变式"
if grep -q "安置费来源" tracking/_tracking-state.json; then fail "被拒事务污染了 state"; fi
rm -f .story/tx-secret-bad.json
pass "违规秘密 schema 入口拒收（不变式 fail-closed）"

# 存量旧数据/手改账本兜底：state 里出现 revealed=true 且 known_by 空 → secret-invariant
cp tracking/_tracking-state.json "$WORK/state.bak"
python3 - <<'PY'
import json
p = "tracking/_tracking-state.json"
st = json.load(open(p, encoding="utf-8"))
st["secrets"]["安置费来源"] = {"name": "安置费来源", "known_by": "", "revealed": True, "updated_chapter": 2}
json.dump(st, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2, sort_keys=True)
PY
python3 "$SKILL_DIR/scripts/check_continuity.py" --project . > "$WORK/continuity-secret.txt" 2>&1 || fail "check_continuity 应退出 0"
grep -q "secret-invariant" "$WORK/continuity-secret.txt" || fail "未报 secret-invariant"
grep -q "安置费来源" "$WORK/continuity-secret.txt" || fail "secret-invariant 未指名秘密"
mv "$WORK/state.bak" tracking/_tracking-state.json
pass "秘密不变式检测（存量坏数据兜底）"

# ================ 新机制回归 3：死亡铁律（内联合并层，精确构造事务） ================
python3 - <<PY
import sys
sys.path.insert(0, "$SKILL_DIR/scripts")
from _tracking.merge import _require_alive_discipline
from _tracking.schema import TrackingError

def snap(alive, location="旧街"):
    return {"identity": "旧街工人", "location": location, "goal": "g", "state": "s",
            "abilities_resources": [], "relationships": [], "knowledge": [],
            "open_threads": [], "alive": alive}

def tx(change, snapshot, overrides=None):
    return {"delta": {"character_changes": [{"name": "王铁柱", "change": change}],
                      "rule_overrides": overrides or []},
            "snapshots": {"王铁柱": snapshot}}

def expect_reject(tag, state, transaction, keyword):
    try:
        _require_alive_discipline(state, transaction)
    except TrackingError as e:
        assert keyword in str(e), f"{tag}: 报错缺关键字「{keyword}」：{e}"
        return
    raise AssertionError(f"{tag}: 应拒收却放行")

def expect_accept(tag, state, transaction):
    _require_alive_discipline(state, transaction)

alive_state = {"characters": {"王铁柱": snap(True)}}
dead_state = {"characters": {"王铁柱": snap(False)}}
# 1 已死者 location 变化 → 拒收（死者 location 冻结）
expect_reject("死者移动", dead_state,
              tx("王铁柱的遗体被运往县城", snap(False, location="县城医院")), "不得移动")
# 2 alive 置 false 无硬词死亡宣告 → 拒收
expect_reject("无宣告死亡", alive_state, tx("王铁柱伤重", snap(False)), "死亡宣告")
# 3 软词「昏厥」不算宣告 → 拒收（宁缺毋滥不猜死活）
expect_reject("软词昏厥", alive_state, tx("王铁柱昏厥倒地", snap(False)), "死亡宣告")
# 4 硬词「身亡」邻近共现 → 放行
expect_accept("硬词身亡", alive_state, tx("王铁柱当场身亡", snap(False)))
# 4.5 硬词+软词同窗（「死了——其实是假死」）→ 拒收：验证 death-lexicon.json 真被加载
# 若 JSON 加载失败降级内置词表（soft 空），此用例必失败——防词表路径 bug 漏网
from _tracking.merge import LEXICON
assert LEXICON["soft"], "death-lexicon.json 未加载（soft 词表为空）——检查 merge.py 词表路径"
expect_reject("硬词+软词同窗", alive_state, tx("王铁柱死了——其实是假死", snap(False)), "死亡宣告")
# 5 复活无 rule_overrides → 拒收
expect_reject("复活无登记", dead_state, tx("王铁柱醒了过来", snap(True)), "复活")
# 6 复活同章 rule_overrides 登记 → 放行
expect_accept("复活已登记", dead_state,
              tx("王铁柱醒了过来", snap(True),
                 overrides=[{"rule": "死者不可复生", "reason": "回归测试", "effective_chapter": 3, "payback": "p"}]))
print("死亡铁律 7 场景全部符合预期")
PY
pass "死亡铁律（移动/无宣告/软词/硬词/软词闸/复活）"

# ================ 新机制回归 4：选角出场检查 ================
# 回归书故意写短章，此时 soft_short_streak 已达 2——第 3 次 checks draft 会触发趋势拦截。
# 选角测试与字数无关，先把趋势计数清零（定向测试操作）。
python3 -c "import json; from pathlib import Path; p = Path('.story/pipeline.json'); d = json.loads(p.read_text()); d['soft_short_streak'] = 0; d['soft_long_streak'] = 0; p.write_text(json.dumps(d, ensure_ascii=False, indent=2))"
# 第 2 章 spec 当前无「出场角色」节（旧模板形态）：基线 checks draft 应绿。
rc=0; python3 "$SKILL_DIR/scripts/checks.py" draft > "$WORK/cast-baseline.txt" 2>&1 || rc=$?
[ "$rc" -eq 0 ] || { cat "$WORK/cast-baseline.txt"; fail "选角基线：checks draft 应通过"; }
# 失约拦截：3 人计划、正文只出现 1 人（陆川），缺席 2 ≥ max(2, ⌈2·3/3⌉) → 拦截
cat >> chapters/chapter-002/spec.md <<'EOF'
## 出场角色
- 陆川
- 王铁柱
- 李铁柱
EOF
rc=0; python3 "$SKILL_DIR/scripts/checks.py" draft > "$WORK/cast-missing.txt" 2>&1 || rc=$?
[ "$rc" -eq 1 ] || { cat "$WORK/cast-missing.txt"; fail "选角失约应 return 1"; }
grep -q "选角失约" "$WORK/cast-missing.txt" || fail "未报「选角失约」"
grep -q "王铁柱" "$WORK/cast-missing.txt" && grep -q "李铁柱" "$WORK/cast-missing.txt" || fail "失约名单缺人"
# 全员 0 次出现 → 降级 warning 不拦（第一人称/代词化叙事兜底）
python3 - <<'PY'
from pathlib import Path
p = Path("chapters/chapter-002/spec.md")
t = p.read_text(encoding="utf-8")
t = t.replace("## 出场角色\n- 陆川\n- 王铁柱\n- 李铁柱\n", "## 出场角色\n- 王铁柱\n- 李铁柱\n- 赵铁柱\n")
p.write_text(t, encoding="utf-8")
PY
rc=0; python3 "$SKILL_DIR/scripts/checks.py" draft > "$WORK/cast-all-missing.txt" 2>&1 || rc=$?
[ "$rc" -eq 0 ] || { cat "$WORK/cast-all-missing.txt"; fail "全员未出现应只 warning 不拦"; }
grep -q "全部未按名出现" "$WORK/cast-all-missing.txt" || fail "未报全员未出现 warning"
# 旧版 spec（无「出场角色」节）→ 跳过；删节即还原基线状态
python3 - <<'PY'
import re
from pathlib import Path
p = Path("chapters/chapter-002/spec.md")
t = p.read_text(encoding="utf-8")
t = re.sub(r"## 出场角色[^\n]*\n(.*?)(?=\n## |\Z)", "", t, flags=re.S)
p.write_text(t, encoding="utf-8")
PY
rc=0; python3 "$SKILL_DIR/scripts/checks.py" draft > "$WORK/cast-legacy.txt" 2>&1 || rc=$?
[ "$rc" -eq 0 ] || { cat "$WORK/cast-legacy.txt"; fail "旧 spec 无出场角色节应跳过不拦"; }
grep -q "旧版模板" "$WORK/cast-legacy.txt" || fail "旧 spec 未提示跳过"
pass "选角出场检查（失约拦截/warning 降级/旧 spec 跳过）"

# ================ 新机制回归 5：writing-rules.json 双投影 ================
# 写前投影：assemble_spec 后第 1 章 spec 有「规则注入」节，core 全注入；
# 非「番茄」平台的 standard 规则（起点推进）被过滤，匹配的（番茄节奏）注入。
grep -q "## 规则注入" chapters/chapter-001/spec.md || fail "spec 缺「规则注入」节"
grep -q "红线·转折连接词密度" chapters/chapter-001/spec.md || fail "core 转折词规则未注入"
grep -q "红线·章内净变化" chapters/chapter-001/spec.md || fail "core 净变化规则未注入"
grep -q "标准·番茄节奏" chapters/chapter-001/spec.md || fail "平台匹配的 standard 规则未注入"
if grep -q "起点推进" chapters/chapter-001/spec.md; then fail "非当前平台的 standard 规则未被过滤"; fi
# 写后投影：cmd_writing_rules 对含 check 字段的规则真实执行——
# 转折词密度超 block(8) 拦截返回 1；干净正文返回 0。
python3 - <<PY
import sys
sys.path.insert(0, "$SKILL_DIR/scripts")
from pathlib import Path
from checks import cmd_writing_rules

root = Path(".").resolve()
clean = root / "chapters/chapter-002/draft.md"
assert cmd_writing_rules(root, clean) == 0, "干净正文被 writing-rules 误拦"

noisy = root / ".story" / "regression-transition.txt"
noisy.write_text("然而他没有退。但是他记得那笔账。不过旧街的灯还亮着。却没有人应门。" * 3, encoding="utf-8")
try:
    rc = cmd_writing_rules(root, noisy)
    assert rc == 1, f"转折词超 block 应拦截（rc={rc}）"
finally:
    noisy.unlink()
print("writing-rules 双投影：写前注入 + 写后拦截均生效")
PY
pass "writing-rules.json 双投影（规则注入 + 写后执行）"

# ================ 新机制回归 6：check_seam.py 跨章拼接 ================
# 延续（第1→2章同一场景线）→ 无 seam-conflict；退出码恒 0（advisory）。
python3 "$SKILL_DIR/scripts/check_seam.py" --project . --chapter 2 > "$WORK/seam-ok.txt" 2>&1 || fail "check_seam 退出码应恒 0"
grep -q "seam 通过" "$WORK/seam-ok.txt" || fail "延续场景未通过 seam 对账"
if grep -q "seam-conflict" "$WORK/seam-ok.txt"; then fail "延续场景误报 seam-conflict"; fi
# 场景突变：第3章开篇跳到皇宫 → 地点指纹无交集 → seam-conflict warning
mkdir -p chapters/chapter-003
cat > chapters/chapter-003/draft.md <<'EOF'
皇宫的清晨，钟声回荡在太和殿里。
皇帝坐在大殿深处的龙椅上，面色阴沉，谁也不敢抬头。
太监总管低着头，一路小跑穿过长长的宫道，去传今日的第一道旨意。
EOF
python3 "$SKILL_DIR/scripts/check_seam.py" --project . --chapter 3 > "$WORK/seam-conflict.txt" 2>&1 || fail "check_seam 退出码应恒 0（突变场景）"
grep -q "seam-conflict" "$WORK/seam-conflict.txt" || fail "场景突变未报 seam-conflict"
rm -rf chapters/chapter-003
pass "check_seam 跨章拼接（延续通过/突变告警/退出码恒 0）"

# ---- 写手发明申报：tx 填报 → 账本 → context.md → 下章 spec 自动带出 ----
# （放在 seam 之后：secret-bad 块要求第 3 章未提交以测 known_by 拒收口径）
python3 "$SKILL_DIR/scripts/pipeline.py" next-chapter >/dev/null || fail "next-chapter (inv)"
python3 "$SKILL_DIR/scripts/new_chapter.py" --chapter 3 >/dev/null || fail "new_chapter (inv)"
python3 "$SKILL_DIR/scripts/gen_transaction.py" commit --project . >/dev/null || fail "gen tx (inv)"
python3 - <<'PY'
import json
from pathlib import Path
p = Path(".story/tx-chapter-003.json")
tx = json.loads(p.read_text(encoding="utf-8"))
tx["delta"]["result"] = "第3章：验证写手发明申报链路"
tx["delta"]["inventions"] = ["主角家有一台红灯牌老收音机（计划外设定）"]
tx["delta"]["character_changes"] = []
tx["character_snapshots"] = {}
tx["context"]["active_character_names"] = []
p.write_text(json.dumps(tx, ensure_ascii=False, indent=2), encoding="utf-8")
PY
python3 "$SKILL_DIR/scripts/tracking_commit.py" validate --project . --input .story/tx-chapter-003.json >/dev/null || fail "validate (inv)"
python3 "$SKILL_DIR/scripts/tracking_commit.py" commit --project . --input .story/tx-chapter-003.json >/dev/null || fail "commit (inv)"
# 直接手建第 4 章最小 spec（绕过状态机；只验证 assemble 的发明注入），断言后清理
mkdir -p chapters/chapter-004
printf '# 第 4 章写作蓝图\n## 大纲要点\n- [ ] 本章目标：\n## 前情衔接\n- \n' > chapters/chapter-004/spec.md
SKILL_DIR="$SKILL_DIR" python3 - <<'PY' || fail "写手发明申报链路"
import json, os, subprocess, sys
from pathlib import Path
skill = os.environ["SKILL_DIR"]
state = json.loads(Path("tracking/_tracking-state.json").read_text(encoding="utf-8"))
inv = state.get("inventions") or []
assert any(i["chapter"] == 3 and "红灯牌" in i["text"] for i in inv), state.get("inventions")
ctx = Path("tracking/context.md").read_text(encoding="utf-8")
assert "## 写手发明" in ctx and "红灯牌" in ctx, ctx[:400]
r = subprocess.run([sys.executable, f"{skill}/scripts/assemble_spec.py",
                    "--chapter", "4", "--project", "."], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
spec4 = Path("chapters/chapter-004/spec.md").read_text(encoding="utf-8")
assert "写手发明" in spec4 and "红灯牌" in spec4, spec4[:600]
print("✓ 写手发明申报：tx → 账本 → context.md → 下章 spec 自动带出")
PY
rm -rf chapters/chapter-003 chapters/chapter-004 .story/tx-chapter-003.json

# ---- 终检 ----
# 旧项目缺 ledger.md（v5 之前的老账本）：首次 check 应自动补写、不报错
rm -f tracking/ledger.md
python3 "$SKILL_DIR/scripts/tracking_commit.py" check --project . > "$WORK/check-backfill.txt" 2>&1 || fail "缺 ledger.md 的 check 应自动补写"
test -f tracking/ledger.md || fail "check 未补写 ledger.md"
pass "ledger.md 缺失自动补写（旧项目迁移）"
# 派生视图与账本强一致：手改 ledger.md 后 check 必须拒绝
cp tracking/ledger.md "$WORK/ledger.bak"
printf '\n- 手改条目｜某人｜回归测试\n' >> tracking/ledger.md
rc=0; python3 "$SKILL_DIR/scripts/tracking_commit.py" check --project . > "$WORK/check-tamper.txt" 2>&1 || rc=$?
[ "$rc" -ne 0 ] || fail "篡改 ledger.md 未被 check 拒绝"
grep -q "derived view differs" "$WORK/check-tamper.txt" || fail "篡改报错缺「derived view differs」"
mv "$WORK/ledger.bak" tracking/ledger.md
python3 "$SKILL_DIR/scripts/tracking_commit.py" check --project . >/dev/null || fail "账本终检"
pass "ledger.md 篡改拒收 + 账本终检"
python3 "$SKILL_DIR/scripts/export_book.py" --project . --output 成书稿.md >/dev/null || fail "导出"
python3 "$SKILL_DIR/scripts/pipeline.py" status >/dev/null || fail "status"
python3 "$SKILL_DIR/scripts/quality_trend.py" show >/dev/null || fail "趋势"

# ---- deslop 检测器回归（正例命中/负例不误伤/BOM 豁免）----
bash "$SKILL_DIR/tests/test_deslop_patterns.sh" || fail "deslop 检测器回归"

# ---- M3 九章实测五缺陷修复回归（独立 mini 项目，不碰主线 rg1）----
# 1. 归档提醒句均长判据（电报体：句均 < 基线下限×0.7 触发）
# 2. assemble_spec 已填写 spec 跳过重组装（--force 不丢 AI 判断项）
# 3. pacing 与伏笔计划冲突显式警告（缺失/无冲突不误报）
# 4. schema 360B 字段超长报错带实际/上限字节数
# 5. check_spec_copy 豁免引号内原文与纯专名短语（叙述句仍报）
# 6. 写手档案：calibrate 实测基线 / 检测分层（基线/豁免/阈值）/ use 登记
SKILL_DIR="$SKILL_DIR" WORK="$WORK" python3 - <<'PY' || fail "M3 九章实测五缺陷修复回归"
import json, os, shutil, subprocess, sys
from pathlib import Path

SKILL = Path(os.environ["SKILL_DIR"])
SCRIPTS = SKILL / "scripts"
BASE = Path(os.environ["WORK"]) / "m3fix"
if BASE.exists():
    shutil.rmtree(BASE)
BASE.mkdir(parents=True)
sys.path.insert(0, str(SCRIPTS))

# ---- 1. 句均长判据 ----
import chapter_flow
book = BASE / "book"
(book / "chapters/chapter-001").mkdir(parents=True)
author = BASE / ".novel"
author.mkdir()
(author / "style-anchor.md").write_text("- 平均句长：约 18~25 字\n", encoding="utf-8")
telegraph = "林默出门。雨在下。他没带伞。巷口有人。他停下。听骨开。心跳声。六只。屋檐下。他数完。他记下。他走。"
(book / "chapters/chapter-001/draft.md").write_text(telegraph, encoding="utf-8")
alert = chapter_flow._sentence_len_alert(book, 1)
assert alert and "电报体" in alert and "18" in alert, f"电报体应触发: {alert}"
normal = ("林默把电动车停在巷口第三家面馆门口，抬头看了眼招牌上褪色的灯箱，确认接头人还没到。\n" * 4)
(book / "chapters/chapter-001/draft.md").write_text(normal, encoding="utf-8")
assert chapter_flow._sentence_len_alert(book, 1) is None, "正常句长不应触发"
print("✓ 1. 句均长判据：电报体触发 / 正常句长不触发")

# ---- 2. assemble_spec 防覆盖 ----
from new_chapter import SPEC_TEMPLATE
proj = BASE / "assemblespec"
(proj / ".story").mkdir(parents=True)
ch = proj / "chapters/chapter-002"
ch.mkdir(parents=True)
(ch / "spec.md").write_text(SPEC_TEMPLATE.format(n=2), encoding="utf-8")

def run_assemble(*extra):
    r = subprocess.run([sys.executable, str(SCRIPTS / "assemble_spec.py"),
                        "--chapter", "2", "--project", str(proj), *extra],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout

run_assemble()
t = (ch / "spec.md").read_text(encoding="utf-8") + "\n## 五问闸门结果\n- 一问：通过\n"
t = t.replace("- 变化项：", "- 变化项：林默拿到接头地点")
(ch / "spec.md").write_text(t, encoding="utf-8")
before = (ch / "spec.md").read_text(encoding="utf-8")
out = run_assemble()
assert "跳过重新组装" in out and "--force" in out, out
assert (ch / "spec.md").read_text(encoding="utf-8") == before, "已填写 spec 被改动"
out = run_assemble("--force")
after = (ch / "spec.md").read_text(encoding="utf-8")
assert "林默拿到接头地点" in after and "## 五问闸门结果" in after, "--force 丢了 AI 判断项"
print("✓ 2. assemble_spec：已填写跳过且逐字不变；--force 重组装不丢判断项")

# ---- 3. pacing 冲突警告 ----
foreshadows = """| ID | 内容 | 埋设章 | 计划回收章 | 状态 | 重要度 | 最近变更章 | 进度注记 |
|---|---|---|---|---|---|---|---|
| F006 | 苏九给病房换小纸鹤——折法复制林家血脉 | 第1章 | 第3章 | 推进 | 中 | 第1章 | |
"""
pacing = """## 节奏检查
- 第 2 章建议强度：「中」+ 不直接推 F006 真相（让 F006 继续慢热，第 3 章或第 4 章再兑现）。
"""
p2 = BASE / "pacing"
(p2 / ".story").mkdir(parents=True)
(p2 / "tracking").mkdir(parents=True)
(p2 / "tracking/foreshadows.md").write_text(foreshadows, encoding="utf-8")
(p2 / "tracking/pacing.md").write_text(pacing, encoding="utf-8")
ch2 = p2 / "chapters/chapter-002"
ch2.mkdir(parents=True)
(ch2 / "spec.md").write_text(SPEC_TEMPLATE.format(n=2), encoding="utf-8")
r = subprocess.run([sys.executable, str(SCRIPTS / "assemble_spec.py"),
                    "--chapter", "2", "--project", str(p2)], capture_output=True, text=True)
assert r.returncode == 0, r.stdout + r.stderr
spec = (ch2 / "spec.md").read_text(encoding="utf-8")
fi = spec.split("## 伏笔指令")[1].split("## 题材要点")[0]
assert "继续推进 F006" in fi, fi
assert "⚠️ pacing 冲突：pacing 第 2 章安排不推进 F006" in fi, fi
# pacing.md 缺失 → 静默跳过不误报
p3 = BASE / "pacing-missing"
(p3 / ".story").mkdir(parents=True)
(p3 / "tracking").mkdir(parents=True)
(p3 / "tracking/foreshadows.md").write_text(foreshadows, encoding="utf-8")
ch3 = p3 / "chapters/chapter-002"
ch3.mkdir(parents=True)
(ch3 / "spec.md").write_text(SPEC_TEMPLATE.format(n=2), encoding="utf-8")
r = subprocess.run([sys.executable, str(SCRIPTS / "assemble_spec.py"),
                    "--chapter", "2", "--project", str(p3)], capture_output=True, text=True)
assert r.returncode == 0
assert "pacing 冲突" not in (ch3 / "spec.md").read_text(encoding="utf-8")
print("✓ 3. pacing 冲突：显式警告入 spec；缺失时静默跳过")

# ---- 4. schema 360B 报错 ----
sys.path.insert(0, str(SCRIPTS / "_tracking"))
import schema
try:
    schema.clean_text("测" * 124, "context.recent_chapters[0].summary", max_bytes=360)
    raise AssertionError("370B 汉字 summary 未被拒收")
except schema.TrackingError as e:
    msg = str(e)
    assert "372 字节" in msg and "360 字节" in msg and "压缩" in msg, msg
print("✓ 4. schema 超长报错带实际/上限字节数与压缩指引")

# ---- 5. check_spec_copy 豁免 ----
cp = BASE / "copy"
(cp / ".story").mkdir(parents=True)
ch5 = cp / "chapters/chapter-001"
ch5.mkdir(parents=True)
(ch5 / "spec.md").write_text("""## 大纲要点（履约清单，逐条勾选）
- [ ] 本章目标：林默把电动车停在巷口第三家面馆门口等接头人出现
- [ ] 场景安排：城西第七人民医院家属等候区东侧的老街巷口
- [ ] 关键事件：周琳给林默发短信「明晚 22:00 双井口旧街 23 号锚点见面别迟到」约定接头
""", encoding="utf-8")
(ch5 / "draft.md").write_text("""林默把电动车停在巷口第三家面馆门口，抬头看了眼招牌。
他在城西第七人民医院家属等候区东侧那条老街的东头巷口下了车。
周琳给他发了条短信：「明晚 22:00 双井口旧街 23 号锚点见面别迟到」。
""", encoding="utf-8")
r = subprocess.run([sys.executable, str(SCRIPTS / "check_spec_copy.py"),
                    "--project", str(cp), "--chapter", "1", "--json"],
                   capture_output=True, text=True)
hits = json.loads(r.stdout)["hits"]
assert len(hits) == 1 and "把电动车停在巷口第三家面馆门口" in hits[0]["copied"], hits
print("✓ 5. check_spec_copy：动作句仍报；专名地名与引号内短信原文豁免")

# ---- 6. 写手档案（yeyue/Minimax M3 单写手）----
cal = BASE / "cal"
wbook = cal / "book"
(wbook / ".story").mkdir(parents=True)
(wbook / "chapters/chapter-001").mkdir(parents=True)
cal_author = cal / ".novel"
cal_author.mkdir(parents=True)
# 作者锚基线 18~25（触发线 12.6）；写手样本句均 12 字 → 档案基线 10~14（触发线 7.0）
(cal_author / "style-anchor.md").write_text("- 平均句长：约 18~25 字\n", encoding="utf-8")
sample = "他沿着长街一直往前跑过去。\n" * 5
(wbook / "chapters/chapter-001/draft.md").write_text(sample, encoding="utf-8")

def run_wp(*extra):
    r = subprocess.run([sys.executable, str(SCRIPTS / "writer_profile.py"), *extra],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout

run_wp("calibrate", "--project", str(wbook), "--chapters", "1")
prof_file = cal_author / "writer.md"
assert prof_file.exists(), "写手档案未生成"
prof_text = prof_file.read_text(encoding="utf-8")
assert "平均句长：约 10~14 字" in prof_text, prof_text

# 基线分层：句均 8 字——作者锚会报（8<12.6），写手档案不报（8≥7.0）
from writer_profile import load_profile, verdict_threshold
(wbook / "chapters/chapter-001/draft.md").write_text("他沿着长街一路跑。\n" * 5, encoding="utf-8")
assert chapter_flow._sentence_len_alert(wbook, 1) is None, "写手档案基线未生效（按作者锚误报）"
(wbook / "chapters/chapter-001/draft.md").write_text("他跑。雨大。\n" * 5, encoding="utf-8")
alert = chapter_flow._sentence_len_alert(wbook, 1)
assert alert and "yeyue" in alert and "电报体" in alert, alert

# 豁免/阈值分层：档案登记 em-dash 豁免 → _style_anchor_allows_dash 真值优先于作者锚
prof_file.write_text(prof_text.replace(
    "## AI 味倾向（校准实测 + 处置裁定）\n格式：`- 检测类型 ｜ 豁免|盯防 ｜ 备注（可含 阈值=N）`",
    "## AI 味倾向（校准实测 + 处置裁定）\n格式：`- 检测类型 ｜ 豁免|盯防 ｜ 备注（可含 阈值=N）`\n"
    "- em-dash ｜ 豁免 ｜ 该写手文风合法形态"), encoding="utf-8")
import checks as _checks
assert _checks._style_anchor_allows_dash(wbook) is True, "写手档案 em-dash 豁免未生效"
assert verdict_threshold({"verdict": "盯防", "note": "阈值=14"}, 8) == 14.0
assert verdict_threshold({"verdict": "豁免", "note": ""}, 8) is None
assert verdict_threshold(None, 8) == 8

# show 回读（未校准的书 → 回退提示；独立作者根避免共享上面的档案）
assert "本书写手：yeyue" in run_wp("show", "--project", str(wbook))
empty_root = cal.parent / "cal-empty"
(empty_root / ".novel").mkdir(parents=True)
empty_book = empty_root / "book"
(empty_book / ".story").mkdir(parents=True)
assert "回退" in run_wp("show", "--project", str(empty_book))
print("✓ 6. 写手档案：calibrate 实测基线 / 检测分层（基线/豁免/阈值）/ show 回读")
PY

echo
echo "🎉 回归测试全部通过：init → outline → 2 章闭环 → override 账本 →"
echo "   ledger 派生视图 → 誓约/秘密检测 → 死亡铁律 → 选角出场 → 规则双投影 → seam 拼接 →"
echo "   导出 → 终检（含 ledger 补写/篡改拒收）→ deslop 检测器 → M3 五缺陷修复 → 写手档案"
