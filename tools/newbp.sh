#!/bin/sh
# newbp.sh <parent class search> <row-index 0-based among results> <new asset name>
# Main editor at (12,230); Content Browser New button at window (45,332). Picker search box at (1710, Y+343).
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work; E=/Users/YOU/ark-mashup/tools/ed.sh
$E click 45 332; sleep 1.5; $E click 80 474
for i in $(seq 1 40); do L=$($W/winid UE4Editor.exe | grep "Pick Parent Class") && break; sleep 2; done
[ -z "$L" ] && { echo "no picker"; exit 1; }
Y=$(echo $L | cut -d' ' -f3); sleep 1
$I click 1710 $((Y+343)); sleep 0.6; $I type "$1"; sleep 4
sh /Users/YOU/ark-mashup/tools/shot.sh -x -R1440,$((Y-12)),540,800 $W/captures/newbp-picker.png
echo "picker_y=$Y"
