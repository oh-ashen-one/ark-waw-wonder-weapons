# WaW → ARK mapping (draft, read from ModKit file names only; editor not opened yet)

Scale: 1 WaW unit = 2.54 UE cm. All values come from `WAW-SPEC.md`. Rules apply literally to every creature.

| WaW piece | Nearest ARK base (ModKit 361.4) | What changes |
|---|---|---|
| Ray Gun | `PrimalItem_TekRifle` / `WeapTekRifle` + `Test/ProjTekRifle` (energy projectile, explodes on impact) | New item, weapon and projectile BPs. Speed 3200→8128 cm/s, lifetime 10 s, fire every 0.33 s, clip 20 / max 160, reload 3 s. Direct 1000. Radial 1500→300 over 64→162.6 cm. |
| Wunderwaffe DG-2 | `WeapTekRifle` fire path + `ProjGrenadeTek` / `ClientExplodingProjectile` | Projectile at 2250→5715 cm/s, lifetime 30 s. On impact it spawns a chain actor: a search from the head socket, radius (300−20·arc)·2.54 cm, line-of-sight trace, ≤4 arc generations, ≤20 kills, 0.5 s travel per arc. Each hit is a kill (health+666, applied through an armor-ignoring damage type so ARK resistances can't block it). Clip 3 / max 15, reload 6 s. |
| Self-damage | ARK player damage | Wunderwaffe: max(25, 25% max HP), never lethal. Ray Gun splash capped at 75 while HP > 75. |
| Zombies | Human rig (`PrimalEarth/Human`, which has a zombie-walk emote anim) or a new `PrimalDinoCharacter` subclass; `ZombieDodo_Character_BP` is an existing zombie-creature precedent | WaW zombie model and anims from the owner's install (OAT XModel/XAnim). Round spawner with health 150/+100/+10%, 24 base count, ≤32 alive, 2 s ×0.95 spawn delay. |
| HUD / viewmodel | Tek rifle FPV rig (`TekRifle_FPV_RIG`) as the socket template | WaW viewmodels and anims from the owner's install. WaW ammo counter in ARK HUD. |

Open items:
- WaW lightning and FX: OAT can't dump T4 FX, so these get recreated to match footage. Needs owner OK.
- Sounds: OAT dumps T4 LoadedSound.
- Whether the slim ModKit (DLC folders excluded) loads and cooks cleanly.
