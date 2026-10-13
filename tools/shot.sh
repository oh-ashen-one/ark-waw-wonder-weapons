#!/bin/sh
# shot.sh <sh /Users/YOU/ark-mashup/tools/shot.sh args...> : screencapture, with any -Rx,y,w,h shifted by .work/display_offset (virtual coords).
O=/Users/YOU/ark-mashup/.work/display_offset; DX=0; DY=0
[ -f "$O" ] && { DX=$(cut -d' ' -f1 "$O"); DY=$(cut -d' ' -f2 "$O" | tr -d '\n'); }
args=""
for x in "$@"; do
  case "$x" in
    -R*) r=${x#-R}; X=${r%%,*}; r=${r#*,}; Y=${r%%,*}; r=${r#*,}; x="-R$((X+DX)),$((Y+DY)),$r";;
  esac
  args="$args '$x'"
done
eval screencapture $args
