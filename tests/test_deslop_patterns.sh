#!/bin/bash
# deslop 检测器回归（2026-08-15 融合 unslop 后固化）：正例命中 + 负例不误伤 + BOM 豁免。
# 由 run_regression.sh 在主线回归后调用；也可单独运行。
set -u
SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/skills/branch/story-deslop/scripts/check-ai-patterns.js"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
fail=0

note() { printf '  %s\n' "$1"; }

# 1. 段落起手词重复（同一连接词 ≥3 段开头 → advisory）
printf '然而他推开门。\n然而墙角灯还亮着。\n然而桌上有半杯茶。\n然而他转身走了。\n' > "$T/opener.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/opener.txt")
echo "$out" | grep -q 'para-opener-repeat' || { note "✗ 起手词重复未命中"; fail=1; }

# 2. 散文式收口（总结腔起手 + 4-8 段短文 → blocking）
printf '他等了一夜。\n\n门始终没有响。\n\n他走到窗边。\n\n综上所述，这一夜改变了一切。\n' > "$T/essay.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/essay.txt"); rc=$?
[ $rc -eq 1 ] && echo "$out" | grep -q 'essay-shape-zh' || { note "✗ 散文式收口未 blocking"; fail=1; }

# 3. 零宽字符（正文内部 U+200B → blocking）
python3 -c "open('$T/zw.txt','w').write('隐藏字符：\u200b前后各一个。\n')"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/zw.txt"); rc=$?
[ $rc -eq 1 ] && echo "$out" | grep -q 'zero-width-char' || { note "✗ 零宽字符未 blocking"; fail=1; }

# 4. BOM 豁免（utf-8-sig 文件头 ≠ 隐写，不得报 zero-width）——2026-08-15 修复回归
python3 -c "open('$T/bom.txt','w',encoding='utf-8-sig').write('他推开门，屋里没人。\n桌上放着一封信。\n')"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/bom.txt"); rc=$?
[ $rc -eq 0 ] || { note "✗ BOM 文件误报 zero-width"; fail=1; }

# 5. 项目级扩展禁用词（--extra-words 聚集 ≥2 处 → advisory；单处不报）
printf '项目禁用词 甲乙丙\n项目禁用词 甲乙丙\n' > "$T/extra.txt"
printf '项目禁用词\n' > "$T/extra-words.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking --extra-words "$T/extra-words.txt" "$T/extra.txt")
echo "$out" | grep -q 'local-extra-word' || { note "✗ 扩展禁用词未命中"; fail=1; }
printf '项目禁用词 一次\n' > "$T/extra-one.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking --extra-words "$T/extra-words.txt" "$T/extra-one.txt")
[ -z "$out" ] || { note "✗ 扩展禁用词单处误报"; fail=1; }

# 6. 正常负例（台词「总之」+ 然而×2 + 正常段落 → 零 findings）
printf '陈默走进巷子，雨丝斜着打下来。\n\n然而他没打伞。\n\n「总之，这件事你别管了。」林姨走了。\n\n陈默捏着伞。\n\n然而巷口那盏灯还亮着。\n' > "$T/neg.txt"
out=$(node "$SCRIPT" --check "$T/neg.txt")
[ -z "$out" ] || { note "✗ 正常文本误报：$out"; fail=1; }

# 7. whitelist 与 extra-words 同用时，白名单豁免优先
printf '项目禁用词\n' > "$T/wl.txt"
out=$(node "$SCRIPT" --check --whitelist "$T/wl.txt" --extra-words "$T/extra-words.txt" "$T/extra.txt")
[ -z "$out" ] || { note "✗ 白名单豁免失效：$out"; fail=1; }

# ---- 8-12. M3 指纹新规则（2026-09：时间戳段/一拍词/他没X/引号混用/micro-action 收紧）----
# 8. 时间戳转场段（≥4 处独立「HH:MM。」→ advisory；3 处不报）
printf '18:30。\n他推开酒馆的门。\n\n19:00。\n雨还没停。\n\n19:30。\n他数着盘子里的花生。\n\n20:00。\n街口的灯灭了。\n' > "$T/ts.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/ts.txt")
echo "$out" | grep -q 'timestamp-para-tic' || { note "✗ 时间戳转场段未命中"; fail=1; }
printf '18:30。\n他推开酒馆的门，雨丝斜着打下来，街口的灯一盏一盏灭下去。\n' > "$T/ts-neg.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/ts-neg.txt")
echo "$out" | grep -q 'timestamp-para-tic' && { note "✗ 时间戳单处误报"; fail=1; }

# 9. 一拍节拍词（≥2 处 → advisory；1 处不报；台词内不计数）
printf '他的手指在名字上停了一拍。\n\n她顿了半拍，才接过信。\n\n他把信折好，放进内兜。\n' > "$T/beat.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/beat.txt")
echo "$out" | grep -q 'beat-pause-tic' || { note "✗ 一拍节拍词未命中"; fail=1; }
printf '「他顿了一拍才说话。」她转述道。\n\n他接过信，拆开，只有一行字。\n' > "$T/beat-neg.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/beat-neg.txt")
echo "$out" | grep -q 'beat-pause-tic' && { note "✗ 台词内一拍被误计"; fail=1; }

# 10. 「他没X」否定短句起手（段首 ≥3 处 → advisory；句中转述不收）
printf '他没开灯。\n\n他没睡。\n\n他没回头。\n\n夜风卷着窗帘。\n' > "$T/negshort.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/negshort.txt")
echo "$out" | grep -q 'negation-short-tic' || { note "✗ 他没X否定短句未命中"; fail=1; }
printf '他说他没吃饭。\n\n他没说话，只是把杯子推过去，玻璃在桌面上划出一道很长的水痕。\n' > "$T/negshort-neg.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/negshort-neg.txt")
echo "$out" | grep -q 'negation-short-tic' && { note "✗ 句中他没X被误收"; fail=1; }

# 11. 章内引号体系混用（英式与直角对话各 ≥3 处 → advisory；单体系不报）
printf '他说"我明天就走"。\n她说"路上小心"。\n他答"放心"。\n「信我烧了。」她说。\n「烧了？」\n「烧了。」\n' > "$T/qmix.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/qmix.txt")
echo "$out" | grep -q 'quote-mix-tic' || { note "✗ 引号体系混用未命中"; fail=1; }
printf '「信我烧了。」她说。\n「烧了？」他问。\n「烧了。」\n「什么时候？」\n' > "$T/qmix-neg.txt"
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/qmix-neg.txt")
echo "$out" | grep -q 'quote-mix-tic' && { note "✗ 纯直角引号误报混用"; fail=1; }

# 12. micro-action 阈值 6.0→4.0/千字收紧（构造 4.0-6.0 区间密度：旧阈值漏检、新阈值命中）
python3 - "$T/micro.txt" <<'PY'
import sys
plain = "他沿着河堤往上游走，风把成片的芦苇压得很低，水面上一片碎光跟着晃动，对岸有人喊了什么，声音散在风里听不真切。"
hit = "他停下来看了一眼远处的渡口。"
paras = [plain] * 25
for i in (2, 7, 12, 17, 22):
    paras[i] = hit
open(sys.argv[1], "w", encoding="utf-8").write("\n\n".join(paras) + "\n")
PY
out=$(node "$SCRIPT" --check --fail-on=blocking "$T/micro.txt")
echo "$out" | grep -q 'micro-action-tic' || { note "✗ micro-action 4.0-6.0/千字区间未命中（阈值收紧未生效）"; fail=1; }
density=$(echo "$out" | grep -o '[0-9.]*\/千字' | head -1 | cut -d/ -f1)
python3 -c "assert 4.0 <= float('$density') < 6.0, '密度 $density 不在 4.0-6.0 区间'" || { note "✗ micro-action 测试密度区间构造失效"; fail=1; }

[ $fail -eq 0 ] && echo "✓ deslop 检测器回归通过（正例命中/负例不误伤/BOM 豁免）" || echo "✗ deslop 检测器回归失败"
exit $fail
