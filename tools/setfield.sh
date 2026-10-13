#!/bin/sh
# setfield.sh <search text> <value-x> <value-y> <value> : in the focused Blueprint defaults panel (window at 12,30),
# search for a property, then replace the text value at screen (x,y). Screen coords are absolute.
I=/Users/YOU/ark-mashup/.work/inp
$I click 600 199; $I key a ctrl; $I type "$1"; sleep 2.5
$I dclick "$2" "$3"; sleep 0.4; $I key a ctrl; $I type "$4"; $I key return; sleep 1
