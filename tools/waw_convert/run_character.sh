#!/bin/bash
# Rebuild + verify the WaW zombie character and all AI animations (headless Blender, no rendering).
#   ASSETS=<oat dump>/nazi_zombie_factory SCRIPTS=<extracted>/nazi_zombie_factory OUT=<outdir> ./run_character.sh
# Optional: BLENDER=/path/to/blender  SHARDS=3 (parallel Blender processes for anim stage / verify)  NICE=10
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1   # keep tools/waw_convert free of __pycache__
BLENDER="${BLENDER:-$(command -v blender || echo /Applications/Blender.app/Contents/MacOS/Blender)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${ASSETS:?set ASSETS to the OAT dump dir containing model_export/ xanim/ images/}"
: "${OUT:?set OUT (e.g. .work/fbx/zombie)}"
SCRIPTS="${SCRIPTS:-}"
SHARDS="${SHARDS:-3}"
NICE="${NICE:-10}"
mkdir -p "$OUT"
B() { nice -n "$NICE" "$BLENDER" -b --factory-startup --python "$@"; }
FILT='^Info:\|^Blender\|^$\|^FBX import\|^Read\|^FBX version\|^FBX export\|^export fin'

# 1. character FBXes (+ parts) + textures
B "$HERE/waw_character_fbx.py" -- --assets "$ASSETS" --scripts "$SCRIPTS" --out "$OUT" --stage model --png-textures --parts \
    | grep -v "$FILT" | tee "$OUT/build_model.log"
# 2. animations, SHARDS parallel Blender processes
rm -f "$OUT"/zombie_animations.shard*.json
pids=()
for ((i = 0; i < SHARDS; i++)); do
  B "$HERE/waw_character_fbx.py" -- --assets "$ASSETS" --scripts "$SCRIPTS" --out "$OUT" --stage anim --shard "$i/$SHARDS" \
      2>&1 | grep -v "$FILT" > "$OUT/build_anim_shard$i.log" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
cat "$OUT"/build_anim_shard*.log | grep '^wrote\|skip\|Error\|Traceback' | sort > "$OUT/build_anim.log"
# 3. merge JSON + notetracks
python3 -B "$HERE/waw_character_report.py" merge --out "$OUT" --assets "$ASSETS"
# 4. verification (re-import the FBXes with both Blender importers, compare to decoded xanim)
B "$HERE/verify_character.py" -- --assets "$ASSETS" --dir "$OUT" --stage model | grep -v "$FILT" | tee "$OUT/verify_character_model.log"
pids=()
for ((i = 0; i < SHARDS; i++)); do
  B "$HERE/verify_character.py" -- --assets "$ASSETS" --dir "$OUT" --stage anim --shard "$i/$SHARDS" \
      2>&1 | grep -v "$FILT" > "$OUT/verify_character_anim_shard$i.log" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
B "$HERE/verify_character.py" -- --assets "$ASSETS" --dir "$OUT" --stage skin | grep -v "$FILT" | tee "$OUT/verify_character_skin.log"
python3 -B "$HERE/waw_character_report.py" report --out "$OUT" --assets "$ASSETS"
