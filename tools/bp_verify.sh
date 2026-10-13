#!/bin/sh
# bp_verify.sh <graph.txt> : copy the whole open graph and compare node/link counts with the generated text.
I=/Users/YOU/ark-mashup/.work/inp
$I click 1008 131; sleep 2.5   # Graph mode (the editor flips to Defaults after paste/compile)
pbcopy </dev/null; $I click 1000 950; sleep 0.5; $I key a ctrl; sleep 1; $I key c ctrl; sleep 6; $I click 1000 950
pbpaste | tr -d '\r' > /Users/YOU/ark-mashup/.work/refl/live.txt
echo "nodes gen=$(grep -c '^Begin Object Class=K2Node' "$1") live=$(grep -c '^Begin Object Class=K2Node' /Users/YOU/ark-mashup/.work/refl/live.txt)  links gen=$(grep -c LinkedTo "$1") live=$(grep -c LinkedTo /Users/YOU/ark-mashup/.work/refl/live.txt)"
