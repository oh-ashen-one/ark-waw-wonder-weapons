#!/bin/sh
# arklook.sh <dx> [dy] : turn the ARK camera by sweeping the cursor inside the game window in 24px steps,
# silently warping back to the window centre between sweeps (no event -> no reverse turn). ~4.8 px/degree.
I=/Users/YOU/ark-mashup/.work/inp; export INP_TARGET=ShooterGame.exe
CX=1720; CY=676; DX=${1:-0}; DY=${2:-0}
while [ "$DX" -ne 0 ] || [ "$DY" -ne 0 ]; do
  sx=$DX; [ $sx -gt 600 ] && sx=600; [ $sx -lt -600 ] && sx=-600
  sy=$DY; [ $sy -gt 300 ] && sy=300; [ $sy -lt -300 ] && sy=-300
  $I warp $CX $CY; sleep 0.05
  n=$(( ( (sx<0?-sx:sx) > (sy<0?-sy:sy) ? (sx<0?-sx:sx) : (sy<0?-sy:sy) ) / 24 + 1 ))
  i=1; while [ $i -le $n ]; do $I move $((CX + sx*i/n)) $((CY + sy*i/n)); sleep 0.02; i=$((i+1)); done
  DX=$((DX - sx)); DY=$((DY - sy))
done
$I warp $CX $CY
