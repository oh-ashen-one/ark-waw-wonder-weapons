#!/bin/bash
# Rebuild + verify both weapons.  Usage:
#   ASSETS=<oat dump>/nazi_zombie_factory OUT=<outdir> ./run_all.sh
# Needs: Blender (headless, no GPU/render), python3.  The OAT dump itself comes from
#   Unlinker.exe (OpenAssetTools v0.33.0) run on the owner's own nazi_zombie_factory.ff.
set -euo pipefail
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
HERE="$(cd "$(dirname "$0")" && pwd)"
: "${ASSETS:?set ASSETS to the OAT dump dir containing model_export/ xanim/ images/}"
: "${OUT:?set OUT}"
for w in ray_gun tesla; do
  "$BLENDER" -b --factory-startup --python "$HERE/waw_viewmodel_fbx.py" -- \
      --assets "$ASSETS" --out "$OUT/$w" --weapon "$w" --png-textures
  "$BLENDER" -b --factory-startup --python "$HERE/verify_fbx.py" -- \
      --assets "$ASSETS" --dir "$OUT/$w" --weapon "$w" \
      | grep -v '^Info:\|^Blender\|^$\|^FBX import\|^Read\|^FBX version' | tee "$OUT/$w/verify_$w.log"
  "$BLENDER" -b --factory-startup --python "$HERE/verify_ufbx.py" -- \
      --assets "$ASSETS" --dir "$OUT/$w" --weapon "$w" \
      | grep '^\[ufbx\]' | tee "$OUT/$w/verify_ufbx_$w.log"
done
# Pack-a-Punched gun meshes (same skeleton + animations as the base weapons): model FBX only
for w in ray_gun_upgraded tesla_upgraded; do
  base="${w%_upgraded}"
  "$BLENDER" -b --factory-startup --python "$HERE/waw_viewmodel_fbx.py" -- \
      --assets "$ASSETS" --out "$OUT/$base" --weapon "$w" --png-textures
  "$BLENDER" -b --factory-startup --python "$HERE/verify_fbx.py" -- \
      --assets "$ASSETS" --dir "$OUT/$base" --weapon "$w" --model-only \
      | grep -v '^Info:\|^Blender\|^$\|^FBX import\|^Read\|^FBX version' | tee "$OUT/$base/verify_$w.log"
done
