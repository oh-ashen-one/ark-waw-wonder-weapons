#!/bin/sh
# cap.sh <name> : capture the largest UE4Editor window to .work/captures/<name>.png, print its screen origin
W=/Users/YOU/ark-mashup/.work
L=$($W/winid UE4Editor.exe | sort -k4 -n -r | head -1)
set -- "$1" $L
sh /Users/YOU/ark-mashup/tools/shot.sh -x -o -l "$2" "$W/captures/$1.png" && echo "win=$2 origin=$3,$4 size=$5x$6 title=$7"
