#!/bin/sh
# import_fbx_mesh.sh <windows path to fbx> : CB Import a skeletal mesh FBX with default options (new skeleton) and wait.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh
$E click 128 369; sleep 4; $I click 323 534; sleep 0.5; $I type "$1"; $I key return
for i in $(seq 1 40); do $W/winid UE4Editor.exe | grep -q "FBX Import" && break; sleep 3; done
L=$($W/winid UE4Editor.exe | grep "FBX Import"); set -- $L; sleep 2
$I click $(( $2 + 303 )) $(( $3 + 432 )); sleep 8
for i in $(seq 1 150); do $W/winid UE4Editor.exe | grep -q -E "FBX Import| 510 110" || break; sleep 4; done
