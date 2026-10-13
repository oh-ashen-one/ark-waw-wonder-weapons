#!/bin/sh
# bp_pastetest.sh <file> : paste text into the open (empty) graph, print live node count, then clear.
I=/Users/YOU/ark-mashup/.work/inp
$I click 1008 131; sleep 2; sed 's/$/\r/' "$1" | pbcopy; sleep 3; $I click 700 600; sleep 0.4; $I click 700 600; sleep 0.4; $I key v ctrl; sleep 5
pbcopy </dev/null; $I click 1000 950; sleep 0.4; $I key a ctrl; sleep 0.8; $I key c ctrl; sleep 3
n=$(pbpaste | grep -c "^Begin Object Class=K2Node"); echo "$n"
$I key forwarddelete; sleep 2
