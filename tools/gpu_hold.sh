#!/bin/sh
# gpu_hold.sh start|stop : hold one gpu-slot capture slot for the ARK editor/game session (one UE4 renderer at a time).
F=/Users/YOU/ark-mashup/.work/GPU_HOLD
# Optional: needs the gpu-slot helper (~/.cache/gpu-slot). Without it this is a no-op.
[ -f ~/.cache/gpu-slot/bin/gpu_slot.sh ] || { echo "gpu_hold: no gpu-slot helper installed, skipping"; exit 0; }
case "$1" in
  start) touch "$F"; GPU_SLOT_CAPTURE_MAX_HOLD=14400 nohup sh ~/.cache/gpu-slot/bin/gpu_slot.sh capture --label ark-mashup-editor -- \
           sh -c "while [ -f '$F' ]; do sleep 5; done" > /Users/YOU/ark-mashup/.work/gpu_hold.log 2>&1 &
         for i in $(seq 1 120); do grep -q " run child_pid" /Users/YOU/ark-mashup/.work/gpu_hold.log 2>/dev/null && break; sleep 5; done
         grep -E "event=(run|wait|acquire)" /Users/YOU/ark-mashup/.work/gpu_hold.log | tail -2 | cut -c1-160;;
  stop) rm -f "$F"; sleep 8; sh ~/.cache/gpu-slot/bin/gpu_status.sh | sed -n 2,5p;;
esac
