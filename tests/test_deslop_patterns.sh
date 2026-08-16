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

[ $fail -eq 0 ] && echo "✓ deslop 检测器回归通过（正例命中/负例不误伤/BOM 豁免）" || echo "✗ deslop 检测器回归失败"
exit $fail
