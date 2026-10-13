#!/bin/sh
# import_fbx_anims.sh <windows folder> <skeleton search> : CB Import every file in folder as animations on that skeleton.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh
DIR="$1"; SKEL="$2"
$E click 128 369; sleep 4; $I click 323 534; sleep 0.5; $I type "$DIR"; $I key return; sleep 2
$I click 193 275; sleep 0.5; $I key end shift; sleep 1; $I click 518 536
for i in $(seq 1 40); do $W/winid UE4Editor.exe | grep -q "FBX Import" && break; sleep 3; done
L=$($W/winid UE4Editor.exe | grep "FBX Import"); set -- $L; X=$2; Y=$3; sleep 2
$I click $((X+232)) $((Y+101)); sleep 3; $I type "$SKEL"; sleep 3
P=$($W/winid UE4Editor.exe | awk '$4==308' | head -1); set -- $P; $I click $(( $2 + 70 )) $(( $3 + 144 )); sleep 2
$I click $((X+236)) $((Y+264)); sleep 10
for i in $(seq 1 150); do $W/winid UE4Editor.exe | grep -q -E "FBX Import| 510 110" || break; sleep 4; done
