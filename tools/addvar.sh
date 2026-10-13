#!/bin/sh
# addvar.sh <Name> <type search> <row> [array] : My Blueprint "+ Variable", name it, pick type (picker row index,
# 0 = first result), optionally toggle array. BP window at (12,30). Captures the details panel afterwards.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
$I move 700 1100; sleep 0.5; $I click 52 222; sleep 2; $I type "$1"; $I key return; sleep 1.5
$I click 150 879; sleep 2
P=$($W/winid UE4Editor.exe | awk '$4==308' | head -1); set -- "$1" "$2" "$3" "$4" $P
$I type "$2"; sleep 2.5
sh /Users/YOU/ark-mashup/tools/shot.sh -x -R$6,$7,308,434 $W/captures/addvar_pick.png
$I click $(( $6 + 100 )) $(( $7 + 39 + $3 * 20 )); sleep 2
[ "$4" = "array" ] && { $I click 215 879; sleep 1.5; }
$I move 700 1100; sleep 1; sh /Users/YOU/ark-mashup/tools/shot.sh -x -R12,790,240,120 $W/captures/addvar_$1.png
