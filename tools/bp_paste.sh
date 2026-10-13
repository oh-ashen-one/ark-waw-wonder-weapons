#!/bin/sh
# bp_paste.sh <graph.txt> [noclear] : (clear graph) paste generated graph, compile, Refresh All nodes, compile; print errors.
# The Blueprint editor window must be in front at (12,30) with the Event Graph showing.
I=/Users/YOU/ark-mashup/.work/inp; T=/Users/YOU/ark-mashup/tools
waitidle() { python3 -c "import sys; sys.path.insert(0,'$T'); import bp_probe; bp_probe.wait_idle(900)"; }
$I click 1000 900; sleep 0.5
if [ "$2" != "noclear" ]; then $I key a ctrl; sleep 0.5; $I key forwarddelete; sleep 2; waitidle; fi
sleep 3; sed 's/$/\r/' "$1" | pbcopy; sleep 2; $I click 700 140; sleep 1; $I click 1000 900; sleep 0.3; $I key v ctrl; sleep 5; waitidle; sleep 2
$I move 700 1000; $I click 50 100; sleep 8; waitidle
$I click 36 82; sleep 1.5; W=/Users/YOU/ark-mashup/.work; $W/winid UE4Editor.exe | grep -q " 180 245" || { $I click 36 82; sleep 1.5; }; $I click 80 279; sleep 20; waitidle
$I move 700 1000; $I click 50 100; sleep 8; waitidle; sleep 2
$I move 700 1000; sleep 1; sh /Users/YOU/ark-mashup/tools/shot.sh -x -R232,1150,830,230 /Users/YOU/ark-mashup/.work/captures/compile_result.png
L=$(ls -t ~/ARKDevKit/Projects/ShooterGame/Saved/Logs/ShooterGame*.log | head -1)
tail -c 900000 "$L" | tr '\r' '\n' | grep -a "LogBlueprint" | python3 -c "
import sys
L=sys.stdin.read().splitlines(); idx=[i for i,l in enumerate(L) if 'Compile of' in l]
a=idx[-2]+1 if len(idx)>1 else 0; b=idx[-1] if idx else len(L)
from collections import Counter
c=Counter(l.split('[compiler] ',1)[-1] for l in L[a:b] if 'deprecated' not in l)
for k,v in c.most_common(40): print(v,k[:220])
print(L[b] if idx else '')"
