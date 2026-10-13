#!/bin/sh
# bpopen.sh <AssetName> : from the Blueprint editor window (12,30), File > Open Asset with retries; refuses to type unless dialog is up
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
/Users/YOU/ark-mashup/tools/raise.sh >/dev/null 2>&1
for t in 1 2 3 4; do
  $I move 900 1300; sleep 1.5
  $I click 36 82; sleep 1.5
  $W/winid UE4Editor.exe | awk '$4==180' | grep -q . || continue
  $I click 76 150
  for i in $(seq 1 15); do $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break; sleep 1; done
  $W/winid UE4Editor.exe | awk '$4==608' | grep -q . && break
done
$W/winid UE4Editor.exe | awk '$4==608' | grep -q . || { echo "OPEN ASSET DIALOG NOT SHOWN"; exit 1; }
$I type "$1"; sleep 3; $I key return
for i in $(seq 1 80); do $W/winid UE4Editor.exe | grep -q " $1" && break; sleep 3; done
sleep 3; $W/winid UE4Editor.exe | head -1
