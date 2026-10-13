#!/bin/sh
# bp_refresh.sh : Refresh All nodes + compile the front Blueprint, report errors.
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; T=/Users/YOU/ark-mashup/tools
waitidle() { python3 -c "import sys; sys.path.insert(0,'$T'); import bp_probe; bp_probe.wait_idle(900)"; }
ncomp() { tr '\r' '\n' < $(ls -t ~/ARKDevKit/Projects/ShooterGame/Saved/Logs/ShooterGame*.log | head -1) | grep -a -c "Compile of"; }
for t in 1 2 3; do $I click 36 82; sleep 2; $W/winid UE4Editor.exe | grep -q " 180 245" && break; done
$I click 80 279; sleep 30; waitidle
n=$(ncomp); $I move 700 1000; $I click 50 100; sleep 10; waitidle
sh $T/bp_errors.sh $((n+1))
