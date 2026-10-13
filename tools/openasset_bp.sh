#!/bin/sh
# openasset_bp.sh <AssetName> : Open Asset from the File menu of the Blueprint window already at (12,30)
# (openasset.sh's main-window menu clicks land in that BP window when it is on top), then place the new window
# like openasset.sh does.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
for t in 1 2 3; do
  $I click 36 82; sleep 1.5; $I click 85 147
  for i in $(seq 1 15); do $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break; sleep 1; done
  $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break
  $I key escape; sleep 1
done
$W/winid UE4Editor.exe | awk '$4==608' | grep -q . || { echo "picker did not open"; exit 1; }
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
$W/winid UE4Editor.exe | head -3
