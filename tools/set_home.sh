#!/bin/sh
# Point the hard-coded paths at your machine. The scripts assume this repo lives at ~/ark-mashup and the
# ARK DevKit at ~/ARKDevKit. Run once after cloning:  sh tools/set_home.sh
cd "$(dirname "$0")/.." || exit 1
grep -rlI '/Users/YOU\|\\Users\\YOU' tools docs | while read -r f; do
  LC_ALL=C sed -i '' -e "s#/Users/YOU#$HOME#g" -e "s#\\\\Users\\\\YOU#\\\\Users\\\\$(basename "$HOME")#g" "$f"
done
echo "paths now point at $HOME"
