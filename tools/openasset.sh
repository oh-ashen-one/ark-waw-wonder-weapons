#!/bin/sh
# openasset.sh <AssetName> : main editor File > Open Asset; puts the asset window at virtual (12,30) (second monitor via display_offset).
E=/Users/YOU/ark-mashup/tools/ed.sh; I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
/Users/YOU/ark-mashup/tools/raise.sh >/dev/null 2>&1
for t in 1 2 3; do
  $E click 19 38; sleep 1.5; $E click 79 185
  for i in $(seq 1 15); do $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break; sleep 1; done
  $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break
  $I key escape; sleep 1
done
$I type "$1"; sleep 3; $I key return
for i in $(seq 1 80); do $W/winid UE4Editor.exe | grep -q " $1" && break; sleep 3; done
sleep 4
L=$($W/winid UE4Editor.exe | awk -v n="$1" '$6==n || $6==n"*"' | head -1); set -- "$1" $L
if [ -n "$3" ] && [ "$3" != "12" ]; then
  osascript -e "tell application \"System Events\" to tell process \"UE4Editor.exe\" to set position of window \"$1\" to {$(( 12 + $(cut -d" " -f1 /Users/YOU/ark-mashup/.work/display_offset) )), $(( 30 + $(cut -d" " -f2 /Users/YOU/ark-mashup/.work/display_offset) ))}" >/dev/null 2>&1; sleep 2
  L=$($W/winid UE4Editor.exe | awk -v n="$1" '$6==n || $6==n"*"' | head -1); set -- "$1" $L
fi
if [ -n "$5" ] && [ "$5" -gt 1070 ]; then $I drag 13 700 280 700; sleep 2
  osascript -e "tell application \"System Events\" to tell process \"UE4Editor.exe\" to set position of window \"$1\" to {$(( 12 + $(cut -d" " -f1 /Users/YOU/ark-mashup/.work/display_offset) )), $(( 30 + $(cut -d" " -f2 /Users/YOU/ark-mashup/.work/display_offset) ))}" >/dev/null 2>&1; sleep 2; fi
$W/winid UE4Editor.exe | head -2
