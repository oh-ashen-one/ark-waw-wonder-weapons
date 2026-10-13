#!/bin/sh
# editor_restart.sh : SIGTERM the ModKit editor (unsaved changes are discarded), relaunch, wait until idle.
W=/Users/YOU/ark-mashup/.work
pgrep -f 'Z:.*[U]E4Editor' | while read p; do kill -TERM $p; done
for i in $(seq 1 30); do pgrep -f 'Z:.*[U]E4Editor' >/dev/null || break; sleep 2; done
R=$W/runs/ed-$(date +%H%M%S); mkdir -p $R; CX=~/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin
(cd ~/ARKDevKit && nohup $CX/wine --bottle ark-modkit --workdir "$PWD" 'Z:\Users\YOU\ARKDevKit\Engine\Binaries\Win64\UE4Editor.exe' 'Z:\Users\YOU\ARKDevKit\Projects\ShooterGame\ShooterGame.uproject' -NoCrashReports > $R/wine.log 2>&1 &)
until $W/winid UE4Editor.exe | awk '$4>1000' | grep -q .; do sleep 4; done; sleep 60
P=$(ps -axo pid,rss,command | grep "Z:.*[U]E4Editor.exe" | sort -k2 -n -r | awk '{print $1}' | head -1); n=0; low=0
until [ $low -ge 3 ] || [ $n -ge 40 ]; do c=$(ps -o %cpu= -p $P | cut -d. -f1 | tr -d ' '); [ "${c:-100}" -lt 30 ] && low=$((low+1)) || low=0; n=$((n+1)); sleep 5; done
rm -f $W/inp_lastpos
$W/winid UE4Editor.exe
