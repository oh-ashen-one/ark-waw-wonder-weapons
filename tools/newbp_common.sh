#!/bin/sh
# newbp_common.sh <Name> <Actor|Pawn|Character> : CB New > Blueprint, pick a Common Classes parent, name it.
# Content Browser must be showing the target folder. Main editor at (12,230).
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh
case "$2" in Actor) dy=69;; Pawn) dy=120;; Character) dy=171;; *) echo "bad parent"; exit 2;; esac
$I move 700 1000; $E click 45 369; sleep 1.5; $E click 80 511
for i in $(seq 1 80); do L=$($W/winid UE4Editor.exe | grep "Pick Parent Class") && break; sleep 3; done
[ -z "$L" ] && { echo "no picker"; exit 1; }
set -- "$1" $L; sleep 1
$I click $(( $3 + 81 )) $(( $4 + dy )); sleep 3; $I type "$1"; $I key return; sleep 3
$I move 700 1000
