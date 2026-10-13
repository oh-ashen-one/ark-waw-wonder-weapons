#!/bin/sh
# raise.sh [ProcessName] : bring a Wine app (no bundle id) to front via System Events (needs its macOS-registered pid)
N=${1:-UE4Editor.exe}
P=$(osascript -e "tell application \"System Events\" to get unix id of first process whose name is \"$N\"" 2>/dev/null)
[ -z "$P" ] && { echo "no process $N"; exit 1; }
osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $P) to true"
