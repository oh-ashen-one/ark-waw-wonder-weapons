# Editor build queue: zombies, round system, arc chain, WaW sounds and viewmodels

Everything that can be done without the editor is done:
- Logic is generated as paste-ready Blueprint text by `tools/graphs/*.py` into `.work/graphs/`.
- Imports are staged in `.work/ue_import/`. Both are git-ignored.

Only the steps below need the ModKit editor. They need mouse and keyboard, so they run only when the owner
isn't using the Mac.

How the graph text works:
- The generator is `tools/bpgen.py` plus `tools/bpc.py`. The format was verified by round-tripping nodes through
  the editor on 2026-10-08: Ctrl+V pastes into a graph and Ctrl+C copies node text back.
- Most variables are **store events**: a `Set_<Name>(<Name>)` custom event whose parameter persists per actor. They
  are pasteable, so they need no UI. Only arrays and values that other Blueprints read are real variables.
- `tools/bp_probe.py` checks function pin names in a scratch graph.

## 0. Verify the unknowns first (scratch graph, about 10 min)
1. Run `bp_probe.py` over every function the graphs use. Check the `Array_Get` output name ("Item"?), the
   cast output pin names (`CAST_PIN_OVERRIDES` in `bpc.py`), and the `BPFiredWeapon` and
   `BPStartEquippedNotify` signatures (events, not functions).
2. Paste a two-node test: a `Set_X` custom event with a parameter, plus a call to it. Compile, and confirm the
   call keeps its parameter link. If links are dropped, paste the custom events first, compile, then paste the
   callers.

## 1. Imports (Content Browser, Mods/ArkMashup, Import)
Select several files by typing `"a" "b" …` in the file dialog.
- `ue_import/sounds/*.wav` (56). These become SoundWaves named S_*.
- `ue_import/zombie/SK_WaWZombie.fbx`:
  - Skeletal mesh, new skeleton. Leave "Import Animations" off.
  - Physics asset on.
  - Leave Force Front X off.
- `ue_import/zombie/anims/*.fbx` (33). Import them as animations on `SK_WaWZombie_Skeleton`. Check the asset names:
  they should be `A_Zmb_*`; rename them if UE appends the take name.
- `ue_import/vm_RayGun/SK_RayGun_VM.fbx` and `anims/*`, then `ue_import/vm_Waffe/SK_Waffe_VM.fbx` and `anims/*`.
  Each gets a new skeleton.

## 2. New Blueprints (`tools/newbp.sh` and `newchild.sh`)
| Asset | Parent | Real variables to add (My Blueprint, + Variable) |
|---|---|---|
| `DmgType_WaW_TeslaKill` | `ShooterDamageType` | none |
| `BP_TeslaChain` | Actor | Candidates, HitList, Remaining: Character[]; EnemiesHit: int; Shooter: Pawn; SearchActive: bool |
| `BP_TeslaKill` | Actor | Found: Character[]; Done: bool |
| `BP_WaWZombie` | Character | none |
| `BP_WaWRoundManager` | Actor | Zombies: BP_WaWZombie[] |

Create all five before pasting, because they reference each other. Then for each one:
1. Paste `.work/graphs/<name>.txt` into the Event Graph.
2. Strict Compile.
3. Fix whatever the compiler lists. Fix it in the generator, then re-paste.
4. Save.

## 3. Existing Blueprints
- `ProjWunderwaffe`:
  - Paste `ProjWunderwaffe.txt` and `ProjWunderwaffe_loop.txt`.
  - Defaults: Direct Damage 1, Explosion Damage 1 (the WaW weapon file). The chain now does the killing.
- `ProjRayGun`: paste `ProjRayGun.txt`.
- `WeapRayGun` and `WeapWunderwaffe`:
  1. Components: add a SkeletalMesh `WaWViewModel` with `SK_<gun>_VM`.
  2. Paste `Weap<gun>_VM.txt`.
  3. Override the `BPRequestReload` function: call `WaWReload` and return the parent's value.
  4. Defaults: clear the flare gun's `FireSound` and `MuzzleFX`.

## 4. Cook, install, test in ARK (tools/rebuild_and_play.sh)
Tests:
1. Start rounds: `cheat SpawnActor "Blueprint'/Game/Mods/ArkMashup/BP_WaWRoundManager.BP_WaWRoundManager'" 0 0 0`.
2. Round 1: 5 zombies rise around you, walk at their WaW speeds, swipe for 60, and die to the Ray Gun.
3. A Wunderwaffe shot into a group chains through up to 4 arcs and 20 kills, and Rex packs die along the chain.
4. Sounds and viewmodel animations play on fire, reload and raise.

## Known approximations (flag to the owner)
- Zombies spawn on the ground 15–40 m from the player. WaW uses map spawners.
- Dog rounds are not built: every round is a zombie round.
- The arc bolt FX is a vanilla ARK electric burst (`P_ElectricSurge`), a placeholder. The plan is to replace it
  with a beam built from WaW's tesla textures.
- Melee-forward anims play in place, so they don't lunge forward.
- One body/head combination for now. WaW picks one of 4 bodies × 24 heads.
- The round number is shown with PrintString instead of WaW's chalk HUD.
- Zombie hits go through ARK's damage, so player armour reduces the 60.
