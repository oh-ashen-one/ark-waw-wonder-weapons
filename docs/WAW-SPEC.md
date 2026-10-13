# World at War wonder weapons + zombies: verified spec

Source: the owner's Steam copy of WaW (app 10090, build 252004), extracted on 2026-10-06 with
OpenAssetTools v0.33.0 (`Unlinker.exe`, Windows zip sha256 `4bf366ce…a4f5`) running in the CrossOver
26.3 bottle `ark-mashup-tools`.
- Zones: `nazi_zombie_factory.ff` (Der Riese), `nazi_zombie_factory_patch.ff` (its scripts are
  identical to the base ones) and `common.ff` (`mp/zombiemode.csv`).
- This file records numbers only. The extracted files stay in the git-ignored `.work/extracted/` and
  are never committed.

Units: WaW units (1 unit ≈ 2.54 cm, so multiply by 2.54 for UE cm). Rules apply **literally to every
ARK creature** (owner decision).

## Ray Gun (`weapons/ray_gun`)

| Field | Base | Upgraded (`ray_gun_upgraded`) |
|---|---|---|
| Type | projectile, Full Auto | same |
| Fire time | 0.33 s | 0.33 s |
| Reload | 3 s | 3 s |
| Clip / max ammo | 20 / 160 | 40 / 200 |
| Projectile speed | 3200 u/s | 4200 u/s |
| Lifetime | 10 s | 10 s |
| Explodes on impact | yes | yes |
| Direct damage | 1000 | 1000 |
| Splash radius | 64 | 64 |
| Splash damage, inner / outer | 1500 / 300 | 2000 / 300 |
| Melee damage | 150 | 150 |

- Script bonus, **verified** (`_zombiemode_spawner.gsc` ~L2695; the patch version is identical): on
  `MOD_PROJECTILE`, `MOD_EXPLOSIVE` and `MOD_PROJECTILE_SPLASH` the zombie also takes
  `round_number × randomintrange(0,100)`.
- Player self-damage: the script caps splash damage at 75 while health is above 75.

## Wunderwaffe DG-2 (`weapons/tesla_gun`, logic in `maps/_zombiemode_tesla.gsc`)

| Field | DG-2 | DG-3 JZ (`tesla_gun_upgraded`) |
|---|---|---|
| Fire time | 1 s | 1 s |
| Reload | 6 s | 4.7 s |
| Clip / max ammo | 3 / 15 | 6 / 30 |
| Projectile speed | 2250 u/s | 2250 u/s |
| Lifetime | 30 s | 30 s |
| Explodes on impact | yes (grenade-type) | yes |
| Splash radius | 110 | 150 |
| Weapon damage | 1 (cosmetic; the kills come from script) | same |

Chain (script variables):
- `tesla_max_arcs` 5 (stops when `arc_num >= 5`)
- `tesla_max_enemies_killed` 20
- `tesla_radius_start` 300, `tesla_radius_decay` 20 × arc_num. The search runs from the hit target's
  head (`j_head`) and requires line of sight.
- `tesla_arc_travel_time` 0.5 s
- `tesla_kills_for_powerup` 15
- `tesla_network_death_choke` 4

Behavior:
- Each struck enemy dies: `DoDamage(health + 666)`. **Verified** in the extracted script:
  - `tesla_head_gib_chance` 50, with the head gib delayed `RandomFloat(0.53,1.0)` s
  - boss exception: a fixed 1000 damage
  - arcs after the first wait `RandomFloat(0.2,0.6) × arc_num`
- Player self-damage, **verified**: only on the player's own projectile or splash hit. It deals
  `max(25, int(maxhealth × 0.25))` and never drops health below 1, followed by `setelectrified(1.0)`
  and the `electrocution` shellshock for 1.0 s.

## Zombies (`maps/_zombiemode.gsc` + `mp/zombiemode.csv`)

| Variable | Value | Source |
|---|---|---|
| Start health | 150 | script default |
| Health increase per round | +100 (rounds 2–9) | csv, same as script |
| Health increase from round 10 | +10% | csv, same as script |
| `zombie_max_ai` | 24 | script default; count formula per the research |
| Spawn delay | 2 s | script default |

- The csv also defines score values (kill 50, damage 5, headshot bonus 50…) and weapon costs (Ray Gun
  10000).
- **Count, verified** (`_zombiemode.gsc` ~L1469–1529):
  - `max = 24 + int(0.5 × 6 × mult)` solo, or `+ int((players−1) × 6 × mult)` with more players
  - `mult = max(1, round/5)`; from round 10, `mult *= round × 0.15`
  - early-round scaling: round 1 ×0.2, round 2 ×0.4, round 3 ×0.6, round 4 ×0.8
- **Spawn delay** is multiplied by 0.95 each round. **Move speed** is `round × 8`, mapped to the
  walk1–4 / run1–3 / sprint1–4 animation sets.
- **Corrections from the zombie design pass (`_zombiemode.gsc`):**
  - The max-alive cap of 32 is **verified** (L1551).
  - The intermission between rounds is **10 s** (L521, L2716). The csv value of 15 is the game-over screen.
  - The speed roll in round N is `(N−1)×8`. The variants are walk 1–7, run 1–5 and sprint 1–3.
  - Health does not increase on hellhound rounds (L1458).
  - Crawler rounds are disabled in Der Riese.
