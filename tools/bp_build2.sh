#!/bin/sh
# bp_build2.sh <graph.txt> : bp_build, then retry (clear + rebuild) until the live node count equals the generated one.
T=/Users/YOU/ark-mashup/tools
for a in 1 2 3; do
  r=$(sh $T/bp_build.sh "$1" 2>&1 | tail -1); echo "try $a: $r"
  g=$(echo "$r" | sed -n 's/.*nodes gen=\([0-9]*\) live=\([0-9]*\).*links gen=\([0-9]*\) live=\([0-9]*\).*/\1 \2 \3 \4/p')
  set -- "$1" $g; [ "$2" = "$3" ] && [ "$4" = "$5" ] && break
done
