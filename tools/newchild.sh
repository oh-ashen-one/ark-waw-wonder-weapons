#!/bin/sh
# newchild.sh <ParentClassName> : New > Blueprint in current CB folder; expand All Classes if needed; type parent into search; capture picker
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh; PARENT="$1"
$E click 45 351; sleep 1.5; $E click 80 490
for i in $(seq 1 60); do $W/winid UE4Editor.exe | grep -q "Pick Parent Class" && break; sleep 2; done
L=$($W/winid UE4Editor.exe | grep "Pick Parent Class"); PX=$(echo $L | cut -d' ' -f2); PY=$(echo $L | cut -d' ' -f3); PH=$(echo $L | cut -d' ' -f5)
[ -z "$PX" ] && { echo "no picker"; exit 1; }
if [ "$PH" -lt 500 ]; then $I click $((PX+50)) $((PY+323)); sleep 3; L=$($W/winid UE4Editor.exe | grep "Pick Parent Class"); PY=$(echo $L | cut -d' ' -f3); fi
$I click $((PX+498)) $((PY+343)); sleep 1; $I click $((PX+242)) $((PY+343)); sleep 0.6; $I type "$PARENT"; sleep 4
sh /Users/YOU/ark-mashup/tools/shot.sh -x -R$((PX-18)),$((PY-12)),540,800 $W/captures/newchild-picker.png
echo "picker at $PX,$PY"
