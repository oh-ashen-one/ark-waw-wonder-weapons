#!/bin/sh
# pickclass.sh <dropdown-x> <dropdown-y> <class name> : open a class dropdown in the defaults panel, filter, pick first match
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
$I click "$1" "$2"; sleep 2.5
$I type "$3"; sleep 3
L=$($W/winid UE4Editor.exe | awk '$4==280' | head -1)   # the class-picker popup is 280 px wide
[ -z "$L" ] && { echo "no popup"; exit 1; }
set -- $L "$3"; X=$2; Y=$3
$I click $((X+68)) $((Y+48)); sleep 2
