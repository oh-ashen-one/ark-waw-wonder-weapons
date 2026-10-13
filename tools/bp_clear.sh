#!/bin/sh
# bp_clear.sh : delete every node in the open graph (two passes: the first click often only focuses the editor).
I=/Users/YOU/ark-mashup/.work/inp
$I click 1008 131; sleep 2.5   # Graph mode (the editor flips to Defaults after paste/compile)
for t in 1 2; do
  for k in $(seq 1 15); do $I scroll 780 600 -5; sleep 0.05; done; sleep 1
  $I click 1000 950; sleep 0.5; $I click 1000 950; sleep 0.5; $I key a ctrl; sleep 1; $I key forwarddelete; sleep 5
  for k in $(seq 1 15); do $I scroll 780 600 5; sleep 0.05; done; sleep 1
done
