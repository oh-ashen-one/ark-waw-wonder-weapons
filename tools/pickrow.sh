#!/bin/sh
# pickrow.sh <row-x> <row-y> <NewName> : click a class row in the open picker, wait for load, click Select (found by layout), name asset
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh
for t in 1 2 3; do
  $I click "$1" "$2"; sleep 1.5; $I move 1700 520
  for i in $(seq 1 100); do $W/winid UE4Editor.exe | awk '$4==510 && $5==110' | grep -q . || break; sleep 3; done; sleep 1.5
  L=$($W/winid UE4Editor.exe | grep "Pick Parent Class"); [ -z "$L" ] && break
  PY=$(echo $L | cut -d' ' -f3); PH=$(echo $L | cut -d' ' -f5)
  $I click 1841 $((PY+PH-27)); for i in $(seq 1 15); do $W/winid UE4Editor.exe | grep -q "Pick Parent" || break; sleep 1.5; done
  $W/winid UE4Editor.exe | grep -q "Pick Parent" || break
done
$W/winid UE4Editor.exe | grep -q "Pick Parent" && { echo "PICKER STILL OPEN"; exit 1; }
sleep 2; $E type "$3"; $E key return; sleep 2; echo "created $3"
