#!/bin/sh
# pickasset.sh <dropdown-x> <dropdown-y> <search> : open an asset dropdown (has Edit/Copy/Paste/Clear rows), filter, click first result
I=/Users/YOU/ark-mashup/.work/inp; W=/Users/YOU/ark-mashup/.work
$I click "$1" "$2"; sleep 3
$I type "$3"; sleep 4
L=$($W/winid UE4Editor.exe | awk '$4==308' | head -1); [ -z "$L" ] && { echo "no picker"; exit 1; }
set -- $L; $I click $(( $2 + 90 )) $(( $3 + 167 )); sleep 2.5
