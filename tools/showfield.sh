#!/bin/sh
# showfield.sh <search> <capname> : search the open Blueprint's defaults and capture the top of the panel
I=/Users/YOU/ark-mashup/.work/inp
$I click 600 198; $I key a ctrl; $I type "$1"; sleep 2.5
sh /Users/YOU/ark-mashup/tools/shot.sh -x -R12,180,1330,${3:-420} "/Users/YOU/ark-mashup/.work/captures/$2.png"
