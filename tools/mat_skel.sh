#!/bin/sh
# mat_skel.sh <MaterialName> : open a material, tick Usage > Used with Skeletal Mesh, Apply+Save, close tab.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
sh /Users/YOU/ark-mashup/tools/bpopen.sh "$1" >/dev/null 2>&1
for i in $(seq 1 30); do $W/winid UE4Editor.exe | grep -q " $1" && break; sleep 2; done; sleep 4
$I click 92 834; sleep 0.5; $I type "Skeletal"; sleep 2.5
$I move 101 887; sleep 1; $I lmbdown; sleep 0.15; $I lmbup; sleep 2; $I move 700 1100; sleep 1
$I click 157 114; sleep 5; $I click 33 114; sleep 6
$I click 33 114; sleep 4; $I move 700 1100; sleep 1; sh /Users/YOU/ark-mashup/tools/shot.sh -x -R12,790,220,160 $W/captures/matskel_$1.png
