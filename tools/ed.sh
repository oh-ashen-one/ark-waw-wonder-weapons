#!/bin/sh
# ed.sh <action> [x y] ... : window-relative input for the editor (origin read live); actions mirror inp.
W=/Users/YOU/ark-mashup/.work
set -- "$@"
O=$($W/winid UE4Editor.exe | sort -k4 -n -r | head -1)
OX=$(echo $O | cut -d' ' -f2); OY=$(echo $O | cut -d' ' -f3)
act=$1; shift
case $act in
  click|dclick|rclick|move) $W/inp $act $((OX+$1)) $((OY+$2));;
  drag) $W/inp drag $((OX+$1)) $((OY+$2)) $((OX+$3)) $((OY+$4));;
  *) $W/inp $act "$@";;
esac
