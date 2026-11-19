#!/bin/sh
# Compile every golden program with the given compiler, run it twice with
# a fresh history, and compare everything it says with what was recorded.
core=$1
here=$(cd "$(dirname "$0")/.." && pwd)
cc=${CC:-cc}
flags="-std=c11 -D_POSIX_C_SOURCE=200809L -D_DEFAULT_SOURCE -O1 -w -I$here/runtime"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
"$cc" $flags -c "$here/runtime/amae.c" -o "$work/runtime.o" || exit 1
pass=0
fail=0
for case in "$here"/tests/golden/*/; do
    name=$(basename "$case")
    out="$work/$name"
    mkdir -p "$out"
    input=/dev/null
    [ -f "$case/input" ] && input="$case/input"
    patience=""
    [ -f "$case/patience" ] && patience="--patience=$(cat "$case/patience")"
    ok=1
    if AMAE_LIB="$here/lib" AMAE_MEMORY="$out/memory.json" AMAE_HISTORY="$out/compiler.json" "$core" < "$case/prog.amae" > "$out/prog.c" 2> "$out/compile.err"; then
        if ! "$cc" $flags "$out/prog.c" "$work/runtime.o" -o "$out/prog" -lm 2> "$out/cc.err"; then
            echo "FAIL $name: the C did not build"; head -5 "$out/cc.err"; fail=$((fail + 1)); continue
        fi
        for k in 0 1; do
            (cd "$out" && AMAE_HISTORY="$out/history.json" "$out/prog" --feelings $patience < "$input" > "$out/out$k" 2> "$out/err$k")
            printf "%s" $? > "$out/code$k"
        done
    else
        code=$?
        for k in 0 1; do
            : > "$out/out$k"
            cp "$out/compile.err" "$out/err$k"
            printf "%s" $code > "$out/code$k"
        done
    fi
    for part in out0 err0 code0 out1 err1 code1; do
        if ! cmp -s "$case/$part" "$out/$part"; then
            [ $ok = 1 ] && echo "FAIL $name"
            ok=0
            diff "$case/$part" "$out/$part" | head -6 | sed "s/^/    $part /"
        fi
    done
    if [ $ok = 1 ]; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
done
echo "$pass passed, $fail failed"
[ $fail = 0 ]
