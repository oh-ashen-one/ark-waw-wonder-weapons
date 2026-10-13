#!/bin/sh
# bp_build.sh <graph.txt> : clear the open Event Graph, paste, compile, Refresh All nodes (verified), compile, report.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; T=/Users/YOU/ark-mashup/tools
waitidle() { python3 -c "import sys; sys.path.insert(0,'$T'); import bp_probe; bp_probe.wait_idle(900)"; }
ncomp() { tr '\r' '\n' < $(ls -t ~/ARKDevKit/Projects/ShooterGame/Saved/Logs/ShooterGame*.log | head -1) | grep -a -c "Compile of"; }
if [ "$2" != "noclear" ]; then sh $T/bp_clear.sh; waitidle; fi
$I click 1008 131; sleep 2.5; sed 's/$/\r/' "$1" | pbcopy; sleep 4; $I click 700 600; sleep 0.4; $I click 700 600; sleep 0.4; $I key v ctrl; sleep 8; waitidle; sleep 3
$I move 700 1000; $I click 50 100; sleep 10; waitidle
for t in 1 2 3; do $I click 36 82; sleep 2; $W/winid UE4Editor.exe | grep -q " 180 245" && break; done
$I click 80 279; sleep 40; waitidle
n=$(ncomp); $I move 700 1000; $I click 50 100; sleep 10; waitidle
sh $T/bp_errors.sh 0 >/dev/null
$I move 700 1000; sleep 1; sh /Users/YOU/ark-mashup/tools/shot.sh -x -R232,170,1100,1210 $W/captures/build_result.png
sh $T/bp_verify.sh "$1"
