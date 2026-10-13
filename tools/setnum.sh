#!/bin/sh
# setnum.sh <screen-x> <screen-y> <value> : replace a numeric field value in the focused UE4 window
I=/Users/YOU/ark-mashup/.work/inp
$I dclick "$1" "$2"; sleep 0.3; $I key a ctrl; $I type "$3"; $I key return; sleep 0.6
