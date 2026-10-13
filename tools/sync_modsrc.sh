#!/bin/sh
# Mirror our AUTHORED mod assets (ModKit Content/Mods/ArkMashup) into the repo (modsrc/ArkMashup).
# Allowlist only: Blueprints/data we wrote. Everything imported from the owner's World at War copy (meshes,
# skeletons, animations, sounds, textures, FBX-generated materials) is never synced (see modsrc/WAW_DERIVED.txt).
set -e
SRC="$HOME/ARKDevKit/Projects/ShooterGame/Content/Mods/ArkMashup/"
DST="$(cd "$(dirname "$0")/.." && pwd)/modsrc/ArkMashup/"
mkdir -p "$DST"
EXCL="$(dirname "$DST")/WAW_DERIVED.txt"
rsync -a --delete --exclude-from="$EXCL" \
  --include='Weap*.uasset' --include='Proj*.uasset' --include='PrimalItem*.uasset' --include='EngramEntry*.uasset' \
  --include='PrimalGameData*.uasset' --include='BP_*.uasset' --include='DmgType_*.uasset' --include='M_AM_*.uasset' \
  --include='TestGameMode*.uasset' --include='*.umap' --exclude='*' "$SRC" "$DST"
ls -la "$DST"
