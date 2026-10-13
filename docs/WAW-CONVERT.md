# WaW viewmodel + animation conversion (2026-10-07)

Owned WaW assets (OAT v0.33.0 dump in `.work/assets/`) are converted to UE4-ready FBX in `.work/fbx/{ray_gun,tesla}/`.
Those files are git-ignored and never committed. Rebuild in about 15 s with:
```
ASSETS=.work/assets/nazi_zombie_factory OUT=.work/fbx tools/waw_convert/run_all.sh
```
Tools: Blender 5.2.0 LTS (headless, no render) and the scripts in `tools/waw_convert/`.
`waw_xanim.py` is an independent reimplementation that follows OAT's GPL-3.0 loader, so treat it as GPL-3.0-compatible.

## Format (OAT "compiled xanim", v17, little-endian)
- **Header:** `u16 version | u16 numFrames(+1 if not looped) | u16 boneCount | u8 flags (1 looped, 2 delta) | u8 assetType | u16 fps`.
- **After the header:** the flip and half-quat bitmasks, the bone names, then per-bone quat and trans tracks.
- **Track count:** 0 = bind pose, 1 = constant, more = keyed with u8/u16 frame indices.
- **Quat:** 3×int16 with `w = sqrt(0x3FFF0001 − x²−y²−z²)`, divided by 32767. Half-quat is (0,0,z,w).
- **Trans:** `min + size × raw`, with raw ×1/255 (u8) or ×1/65535 (u16).
- **Notetracks:** `u8 count`, then `name` + `u16 frame`.

## Output
- **Ray Gun:** 81 bones (`tag_view` root; `j_gun` under `tag_weapon`), arms `viewmodel_usa_marine_arms`.
  - 9 anims at 30 fps: idle, fire 0.40 s, reload 3.97 s, raise 1.0, quick_raise 0.33, drop 0.67, quick_drop 0.33, ads_up 0.27, ads_down 0.30.
- **Wunderwaffe:** 82 bones.
  - 11 anims: idle, fire 0.57, ads_fire 0.33, reload 6.57, first_raise 2.67, pullout 1.17, pullout_fast 0.47, putaway 0.83, putaway_fast 0.33, ads_up/down 0.5.
- Pack-a-Punch meshes are exported too; they share the same skeleton.
- **Units and axes:** WaW inches × 2.54 = cm. FBX Up=+Z, Front=−Y, so the barrel points along +X. Leave UE4's "Force Front X Axis" off.
- **Notetracks** (JSON):
  - Ray Gun reload: open@12, battery_out@39, battery_in@71, close@95.
  - Wunderwaffe reload: foley@3, switch_off@24, handle_pullback@50, clip_in@91, handle_release@117, switch_on@149, to_idle@172.

## Verification (headless Blender)
| Check | Result |
|---|---|
| Bone heads vs forward kinematics of the decoded xanim, two importers | max error ≤ 0.0002 cm |
| Skinned mesh vs numpy skinning | 0.0001 cm |
| Bones moved per animation | 41–76 (idle: 0) |
| UE4 import | **not yet tested** |

## Gaps
- No UE4 import test yet.
- Notetracks are JSON only.
- ads_up/down key only `tag_torso`, so they're baked over the idle pose.
- Arms were chosen by bone-set match.
- 8 `d_sleave_reshape_*` tracks were dropped (no bone in any model).
- Only base-colour textures are linked.
- LOD0 only.
