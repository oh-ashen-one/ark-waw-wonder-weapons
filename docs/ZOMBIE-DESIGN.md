# WaW Der Riese zombies + round system in ARK: ModKit design (2026-10-07)

This is a design only. Nothing has been built, launched or opened in the editor. The rules are Der Riese's,
ported literally from the owner's extracted scripts. Units: 1 WaW unit = 2.54 cm.

Script abbreviations (all under `.work/extracted/`; the `_patch` copies are identical to the base ones for
these functions):
- `zm`: `nazi_zombie_factory_patch/maps/_zombiemode.gsc`
- `sp`: `nazi_zombie_factory_patch/maps/_zombiemode_spawner.gsc`
- `dogs`: `nazi_zombie_factory_patch/maps/_zombiemode_dogs.gsc`
- `pw`: `nazi_zombie_factory/maps/_zombiemode_powerups.gsc`
- `fac`: `nazi_zombie_factory/maps/nazi_zombie_factory.gsc`
- `util`: `nazi_zombie_factory/maps/_zombiemode_utility.gsc`
- `csv`: `common/mp/zombiemode.csv`

Evidence tags follow `WEAPON-BP-DESIGN.md`: **P-pdb** (member or function record in
`UE4Editor-ShooterGame.pdb`), **P-exec** (an `exec<Name>@<Class>` UFUNCTION thunk), **P-refl** (UTF-16
reflection name in the ShooterGame, Engine or AIModule DLL), **P-asset** (vanilla `.uasset` name table),
**C** (claim or inference) and **U** (unknown; check in the editor or in game).

## 0. Corrections to the brief and to WAW-SPEC.md

| Item | Brief / WAW-SPEC | Script says |
|---|---|---|
| Time between rounds | "15 s from csv" | **10 s** (`zombie_between_round_time`, zm L521, used at L2083). It is not in the csv. The csv's 15 s `zombie_intermission_time` is the **game-over** screen (zm L522, L2716). |
| Max alive | "32, unverified" | **Verified 32.** The spawn loop waits while `get_enemy_count() > 31` (zm L1551). Dogs count too. |
| Speed roll | "round × 8" | During round N it is `(N−1)·8`, because it is set just before the round increments (zm L2096–2098). Round 1 uses 1 (sp L9). |
| Variant sets | walk1–4 / run1–3 / sprint1–4 | Rolled: **walk1–7, run1–5, sprint1–3** (sp L224–241). Anims: zm L682–699, L748–751, fac L349–356. |
| Health from r10 | "×1.1" | `h += int(h·0.1)`, so the increment is truncated (zm L2138–2141). |
| Health on dog rounds | not mentioned | `ai_calculate_health` only runs inside `round_spawning` (zm L1458). Dog rounds use another spawn function, so **zombie health does not rise on a dog round.** |
| Crawler rounds | implied | Disabled in Der Riese (`crawlers_enabled` is commented out, fac L20; zm L140). Crawlers only come from leg gibs. |

---

## 1. Zombie class

### 1.1 Parent: a `PrimalDinoCharacter` child, not a human
- ARK humans are player pawns (`AShooterCharacter`). This build has no AI controller for them; the only AI
  controllers are `APrimalDinoAIController` and `APrimalBotAIController` (P-pdb vtables).
- Precedent: Genesis `Bot_Character_BP` (P-asset) is a human-shaped NPC. Its parent is native
  `PrimalBotCharacter`, and it is built on the dino framework (`PrimalDinoCharacter`,
  `DinoCharacterStatusComponent_BP_Bot`, `BaseHumanAnimBP`, run by `Bot_AIController_BP` with a behaviour tree).
  Bipedal dinos (`Bigfoot_Character_BP`, `Yeti_Character_BP`, `Gorilla_*`) and `ZombieDodo_Character_BP` +
  `ZombieDodo_AnimBlueprint` (all P-asset, `PrimalEarth/Dinos/...`) show the same pattern.
- **Decision:** `WaWZombie_Character_BP`, a child of `PrimalEarth/CoreBlueprints/Dino_Character_BP` (P-asset). It is
  not parented to `PrimalBotCharacter`, which adds dino claiming and riding that we don't need.
  - Controller: `WaWZombie_AIController_BP`, a child of `PrimalEarth/CoreAI/Dino_AIController_BP` (P-asset), with
    its own BT/BB (`WaWZombie_BT`, cloned from `Dino_BT`/`Dino_BB`).
  - Status: `DinoCharacterStatusComponent_BP_WaWZombie`.
- The vanilla human zombie emote (`PrimalEarth/Human/*/Animations/TPV_NoWeapon_*Emote_Zombie*`, P-asset) is **not
  used**. It is a player-skeleton emote, and using it would be the canned-anim substitution that CLAUDE.md forbids.

### 1.2 Class defaults
| Property | Value | Evidence |
|---|---|---|
| `bForceDisablingTaming`; `bCanBeTamed` | true; false | P-pdb (`APrimalDinoCharacter`) |
| `bPreventMating`, `bIgnoreAllWhistles` | true | P-pdb |
| `bUniqueDino`, `bIsBossDino` | false | P-pdb. Not a boss, so a Wunderwaffe arc instakills it. |
| `bPreventStasis` | true while it belongs to a manager | P-pdb. A stasised zombie would stall `round_wait`. |
| `bPreventSaving` | true (§4) | P-refl, Engine. Owner class C. |
| `bAllowCorpseDestructionWithPreventSaving` | true | P-pdb (`APrimalCharacter`) |
| `CorpseLifespan` | U, matched to footage | P-refl |
| `bDisableHarvesting`, `bNoKillXP` | true / owner decision (§6) | P-refl |
| Capsule | radius 40.64 cm, half-height 91.44 cm | aitype box 32×32×72 u (`aitype/axis_zombie_ger_ber_sshonor.gsc` L2) |
| Health | set per spawn: `SetMaxStatusValue(Health, H)`, then `ModifyCurrentStatusValue` to full | P-exec (`UPrimalCharacterStatusComponent`) |
| Level | 1 via `SpawnDino(..., bOverrideBaseNPCLevel)`; level stats are irrelevant because health is overwritten | P-exec, P-pdb parameter names |

### 1.3 Skeleton, mesh and anims
- Import the WaW `generic_human` skeleton (sp L6) as a **new skeleton**, `SK_WaWZombie_Skeleton`. Mesh:
  `char_ger_honorgd_bodyz{1,2}_1` plus one of the 24 heads `char_ger_honorgd_zombiehead{1–4}_{1–6}`, chosen at
  random as WaW does (`character/char_ger_honorguard*_zombies.gsc`, `xmodelalias/*`).
- **Add `j_head` to the front of the weapon design's `Head(c)` socket list** (WEAPON-BP-DESIGN §3.4), so the
  tesla chain searches from the zombie's real head bone. `J_Eyeball_LE` is the eye-FX bone (`_zombiemode_tesla.gsc` L340).
- Input: `.work/fbx/zombie/*.fbx` plus the converter's report (that folder is **still empty**). The converter
  must export notetracks too, as it already does for the Ray Gun (`ray_gun_notetracks.json`).

**AnimBP `WaWZombie_AnimBP`** (parent AnimInstance; whether ARK requires a specific anim-instance parent is U).
Its state is chosen in code, not by blend space:

| State | Anims (zm lines) | Selection rule |
|---|---|---|
| Rise | `traverse_ground_v1_walk` / `_v1_run` / `_climbout_fast`, `v2_walk_altA` (L822–834) | By speed tier at spawn (sp L3313, L3570) |
| Walk | walk1–7 → `walk_v1,v2,v3,v4,v6,v7,v8` (L682–685, L748–751) | 1/7 each; walk8 (`v9`) is never rolled |
| Run | run1–5 → `walk_fast_v1–v3`, `run_v2`, `run_v4` (L687–691) | 1/5 each; run6 is never rolled |
| Sprint | sprint1–3 → `sprint_v1`, `sprint_v2`, `sprint_v1` (L696–699) | So `v1` 2/3, `v2` 1/3 |
| Attack | 7 entries over `attack_forward_v1/v2`, `attack_v1/v2/v4/v6` (L738–744) | Random; damage on the `fire` notetrack (C, per the window variant sp L828–834) |
| Crawl / crawl attack | crawl1–5 (L705–709), `attack_crawl`, `_lunge` (L769–770) | Set after a leg gib (§1.5) |
| Death | `ch_dazed_a–d_death` (L807–810); crawl deaths (fac L660–698) | Random at spawn (sp L215–217) |
| Tesla death | `tesla_death_a–e`, `tesla_crawl_death_a/b` (L787–799) | Chosen by the tesla chain |

### 1.4 Movement speed per variant: placeholders from the converter report
- T4 AI move along their animation's root motion. Each variant's speed is the converter's measured root
  displacement over the cycle length, ×2.54.
- At spawn, set `CharacterMovement.MaxWalkSpeed` to that value and play the cycle at rate 1.0, so feet don't slide.
- Set `bAllowRunning` = false (P-refl): ARK's own run modifier is never used.

| Variant | Anim | cm/s (fill from report) |
|---|---|---|
| walk1–7 | v1, v2, v3, v4, v6, v7, v8 | `TBD_W1` … `TBD_W7` |
| run1–5 | fast_v1, fast_v2, fast_v3, run_v2, run_v4 | `TBD_R1` … `TBD_R5` |
| sprint1–3 | sprint_v1, sprint_v2, sprint_v1 | `TBD_S1`, `TBD_S2` |
| crawl1–5 | crawl, crawl_v1 … v3, v4 | `TBD_C1` … `TBD_C5` |

### 1.5 Gibs and crawlers
- WaW turns a zombie into a crawler when a leg-location gib happens on a non-lethal hit (sp L1523–1640, gate
  L1739). A projectile with no hit location derives its gib refs from the impact point (sp ~L1625–1631). The
  crawler's health is capped at 50 (fac L700–705).
- In ARK, our damage goes through `ApplyDamage` with no bone (WEAPON-BP-DESIGN §2.4), so hit locations must be
  computed from the impact point against the WaW bone positions.
- Visual: `HideBoneByName` (P-exec, Engine) is a recreation, so it ships behind `bCrawlerGibs` = false until the
  owner approves it.

---

## 2. AI

### 2.1 Targeting: players only
- WaW: `find_flesh` (sp L2914) targets the closest valid player and re-picks every `RandomFloatRange(1,3)` s
  (sp L3001). `goalradius` is 32 u.
- ARK, on the controller:
  - `bForceOnlyTargetingPlayerOrTamed` = true (P-pdb, `APrimalDinoAIController`)
  - `bUseBPTargetingDesire` = true, and `BPGetTargetingDesire` (both P-pdb) returns 1 for an alive
    `ShooterCharacter` and 0 for everything else, tamed dinos included
  - a timer every `RandomFloatInRange(1,3)` s calls `SetTarget(closest alive player)` (P-exec)
  - `bNotifyNeighborsWithoutDamage` = false (P-pdb), so zombies don't recruit neighbours
- **Default (flag):** zombies ignore dinos and don't retaliate against them.
  - Whether ARK's aggro table can still override a 0 desire after a dino hits a zombie is **U** (test Z12).
    Fallback: call `ClearFromAggroEntries` (P-exec) on any non-player attacker.
  - Dinos may still attack zombies through their own ARK targeting (C). Owner decision.
- Rider: a player on a dino is still the target. WaW has no equivalent (flag).

### 2.2 Pathing
- Use ARK's navmesh through the cloned `Dino_BT`.
- WaW's breadcrumb fallback (sp L3015–3160) is dropped: ARK's nav pathing replaces it.
- Keep WaW's **stuck failsafe** literally (zm L2153–2197):
  - every 30 s, if the zombie has moved less than 60.96 cm (24 u, L2186), kill it with `health + 100`
  - also kill it if it falls below the world (L2179)
  - it is **not** respawned, so the round count drops, exactly as in WaW.

### 2.3 Melee attack
| WaW rule | Value | Source | ARK |
|---|---|---|---|
| Attack distance | 64 u = 162.56 cm | sp L2901–2902 | `AttackInfos[0].AttackRange` = 162.56 (P-refl) |
| Damage to player | **60** per hit (C) | kar98k `meleeDamage` 150 (`weapons/kar98k`) × `player_meleeDamageMultiplier` 0.4 (`_gameskill.gsc` L428). The mechanism is the code comment at dogs L17 | Applied at the `fire` notetrack through `WaW_DealExact(player, 60, DmgType_WaW_ZombieMelee)`, so ARK armour can't change it. Native `MeleeDamageAmount` = 0. |
| Same attacker re-hit | ignored for 0.4 s | zm L2553–2567, L2585–2595 | per-player map from attacker to time |
| Swing rate | the anim's length | engine | taken from the converter's anim lengths, U until imported |
| Player HP | 100 (Juggernog 160 is out of scope) | `_zombiemode_perks.gsc` L824, L69 | owner decision (§6) |
| Touch exploit | touching for 5 s within 88.9 cm (35 u) kills the player | sp L161–207 | ported, behind a flag (owner) |

- `FDinoAttackInfo` has `bOnlyUseWithPlayers` and `bUseBlueprintCanAttack` (P-pdb). Set the first one true.

### 2.4 Barrier and level features that are dropped
Windows and board tearing (sp L264–880) are dropped, along with:
- the carpenter power-up and the rebuild reward (zm L2050–2053)
- the zone manager, doors and debris (sp L28–58)
- perks, the Mystery Box, teleporters, the power switch and traps
- last stand and revive
- spectator respawn (zm L1235)
- the WaW score HUD

Zombies go straight to `find_flesh`, as risers do.

---

## 3. Round system: `BP_WaWRoundManager`
This is the brief's `BP_ZombieRoundManager`. It keeps the name that WEAPON-BP-DESIGN §2.3 already reads
`CurrentRound` from.

### 3.1 State and rules
| Var | Init | Rule (source) |
|---|---|---|
| `CurrentRound` | 1 | Incremented **after** the 10 s break (zm L2098). The Ray Gun bonus reads it live, so during the break it is still the round just finished. |
| `ZombieHealth` | 150 | At each zombie round's start (zm L1458, L2135–2150): r = 1 no change; 2–9 +100; ≥ 10 `h += int(h·0.1)`. |
| `SpawnDelay` | 2.0 | After each round: `d = max(d, 0.08) × 0.95` (zm L2086–2093). |
| `MoveSpeed` | 1 | After each round: `(round)·8`, before the increment (zm L2096). |
| `ZombieTotal` | count | Decremented on each spawn (zm L1616). |
| `bFirstRound` | true | Cleared after the first round (zm L2076). |

**Count** (zm L1469–1529), with `P` = players in session:
- `m = max(1, round/5)` (float division, C: it matches the community counts 27/28/28/29/33 for r6–10)
- if `round ≥ 10`: `m *= round·0.15`
- `max = 24 + int(3·m)` solo, or `24 + int((P−1)·6·m)`
- then `×0.2` (first round), `×0.4` (r < 3), `×0.6` (r < 4), `×0.8` (r < 5), each `int()`

### 3.2 Loop (zm L2044–2101), driven by timers
1. **Chalk:** the round-1 intro takes 6.75 s (1 + 0.5 + 3 + 0.25 + 2, zm L1824–1945). Later rounds take 0.5 s.
   `powerup_round_start` resets the drop count (zm L2062).
2. **Spawn loop** (zm L1536–1622):
   1. Wait while alive > 31.
   2. Pick a spawn point (§3.3), re-rolling once if it repeats the last one (L1539–1548).
   3. Call `SpawnDino` (P-exec, static `APrimalDinoCharacter`), set health, roll the speed (§3.4), play the rise anim.
   4. `ZombieTotal--`.
   5. Wait `SpawnDelay` + one NetFrame (U, 0.1 s as in the weapon design).
3. **Last zombie** (round > 3): when exactly one zombie with legs is left, it switches to sprint1–3 (L1624–1640).
4. **Round end** (`round_wait`, zm L2201–2234): wait 1 s, then poll every 0.5 s until alive = 0 and
   `ZombieTotal` = 0.
5. **Break:** 10 s. Then update `SpawnDelay` and `MoveSpeed`, increment `CurrentRound`, and loop.
6. **Game over** (all players dead; zm L2661, L2716): 15 s intermission, then despawn everything and reset to
   round 1. The exact ARK behaviour is an owner decision (§6).

Alive count: zombies register with the manager, and death or `Destroyed` unregisters them. That covers
`cheat DestroyWildDinos` too.

### 3.3 Spawn points in ARK terrain (no WaW equivalent: owner approval)
WaW spawns at map-placed spawners in active zones, plus rise points (fac L24). In ARK, the manager builds
points around the target player:
- `UNavigationSystem::GetRandomReachablePointInMinMaxRadius` (P-exec, Engine; an ARK addition) gives a
  reachable point between `SpawnMinR` = 1,200 cm and `SpawnMaxR` = 3,500 cm. Both are placeholders for the owner.
- Reject the point if:
  - `ProjectPointToNavigation` (P-exec) moves it more than 100 cm
  - it is in water
  - its ground slope is over 35°
  - it is within 300 cm of a structure
  - a camera-to-chest trace from the player has line of sight **and** it is inside the view cone (the
    `bDontSpawnOutOfView` / `DontSpawnOutOfViewCheckRadius` idea from `SupplyCrate_Base_Horde`, P-asset)
- Try 12 times, then accept the best point rejected only by visibility.
- Every zombie spawns with the original WaW **rise** anim (sp L3313–3426), so nothing pops in.
- ARK precedents (P-asset):
  - Extinction `SupplyCrate_Base_Horde` (`CurrentWave`, `MaxNPC`, `SpawnDino`, `AddToAggro`) and
    `HordeSpawnNetwork` (`GetPointsInRadius`, `InnerRadiusDistance`, `MaxDistanceFromSpawn`)
  - Genesis `MissionType_GauntletWaves_*` and `MissionServerSidePoint_HordeDinoSpawner`
  - These are read for patterns only and not reused, because their difficulty scaling isn't WaW's.

### 3.4 Speed roll (sp L244–261)
- `r = RandomIntegerInRange(MoveSpeed, MoveSpeed+34)`. Walk if `r ≤ 35`, run if `r ≤ 70`, otherwise sprint.
- Then pick the variant uniformly (§1.3), and set `MaxWalkSpeed` and the anim state.

### 3.5 Dog rounds (Der Riese has hellhounds): **out of MVP, plan only**
- Rules:
  - First dog round at 5–7, then every 4–5 rounds (dogs L465–505).
  - Count 6·P for the first two dog rounds, then 8·P (L134–141). At most 2·P alive (L166).
  - Health 400/900/1300/1600, capped at 1600 (L437–461), ×4 while walking until the dog runs (L33–35, L633–639,
    L920–931).
  - Spawn wait is 3/2.5/2/1.5 s minus `count/max` (L217–239).
  - A 7 s intro (L130). The last dog drops Max Ammo (L270–282).
  - Mixed dog spawns from round 16 (zm L1557–1612, fac L21).
- Needs the WaW dog mesh and anims (a separate converter job) and a quadruped parent (C: a `Dino_Character_BP` child).
- **Owner decision:** without dogs, health rises every round. That is not Der Riese's real curve, because Der
  Riese skips the increase on dog rounds.

### 3.6 Power-ups: scope
- Der Riese includes nuke, insta-kill, double points, full ammo and carpenter (fac L605–612).
- Drops (pw L371–512):
  - a 3% random chance per kill (`rand_drop ≤ 2`), or a score threshold: 2,000 points, rising ×1.14 each time
  - at most 4 per round
  - a power-up times out after 15 s (pw L990)
- That needs WaW points (csv: kill 50, damage 5, headshot 50).
- MVP proposal: **out**. Phase 2: points, plus Max Ammo through `WaW_SetReserve`. Insta-kill and nuke under
  "literal for every creature" would kill a Giga, so the owner must rule on them. Carpenter and double points are
  dropped.

---

## 4. Save/load, single player, performance
- **Saving:** WaW has no saves. Zombies set `bPreventSaving`, so they are never written into the ARK save.
  - Default: the manager is not saved either, so loading a save means no zombies and round 1 on the next start.
    (Owner option: persist `CurrentRound` and restart that round from its beginning.)
  - On `BPPostLoadedFromSaveGame` (`bUseBPPostLoadedFromSaveGame`, P-pdb on `APrimalCharacter`), any zombie
    that somehow loads destroys itself.
- **Bootstrap:** `PrimalGameData_BP_ArkMashup.AdditionalDefaultBuffs` (P-refl) gives each player
  `Buff_WaWBootstrap`. On the server, it spawns one manager if none exists. Start is gated by the owner's choice
  of trigger (§6).
- **Single player:** ASE single player is a listen server, so all logic runs under `HasAuthority`. `P` counts
  connected `ShooterCharacter`s (1). Timers use game time (`Slomo` affects them).
- **Performance, M3 Ultra under CrossOver.** The literal cap is 32 alive (24 is the count base, not a cap).
  Budget:
  - no per-tick BP: retargeting every 1–3 s, BT services ≥ 0.25 s
  - short corpse life
  - pool nothing (a fresh `SpawnDino` each time, as WaW does)
  - Measure (Z15). If 32 alive drops below the agreed fps, **report it to the owner; don't silently lower the cap.**

---

## 5. Verification plan
- Logs: `WAW_ROUND` (round, count, health, delay, movespeed, t), `WAW_SPAWN` (id, variant, speed, pos,
  dist, t) and `WAW_KILL`.
- `BP_WaWTestRig` adds: SetRound(n), KillAllZombies (via the exact path), and spawn-point visualisation.
- Proof follows CLAUDE.md: real keyboard and mouse input, compared against Der Riese footage.

| # | Test | Pass if |
|---|---|---|
| Z1 | Fresh start, solo | Round 1 spawns exactly **5**, each at 150 HP. First spawn 6.75 s ± 0.2 after start. |
| Z2 | SetRound 1–20 + KillAll each | Count, health and delay equal the table below for every round |
| Z3 | Round-1 zombie: exact 149, then 1 | Alive after 149, dead after 1. Round 10: 1044 then 1. |
| Z4 | Spawn spacing, rounds 1 and 10 | Gaps = delay + NetFrame ± 0.05 s (2.10 / 1.36) |
| Z5 | Round 20 solo (60), no kills | Alive never exceeds 32 (sampled every 0.1 s); spawning resumes on kill |
| Z6 | 200 spawns at r1 and r3 | r1 100% walk; r3 57/43 walk/run (χ², p > 0.05); sprint variant v1:v2 ≈ 2:1 |
| Z7 | Each variant on flat ground | Ground speed = report value ± 5%; no visible foot slide vs WaW clip |
| Z8 | Last kill to next first spawn | 11.0–11.6 s (1 + ≤ 0.5 poll + 10 + 0.5 chalk + NetFrame) |
| Z9 | Stand in melee | 60 per hit, no repeat by the same zombie within 0.4 s, swing period = anim length |
| Z10 | Round ≥ 4, leave one zombie | It switches to sprint |
| Z11 | Trap a zombie (pillar) 30 s | Killed by the failsafe; the round still completes |
| Z12 | Wild Rex near zombies | Matches the owner's dino-interaction decision; zombie keeps the player as target |
| Z13 | Ray Gun 50 hits at r10 | Mean bonus ≈ 495 (WEAPON T1 with the live round) |
| Z14 | Save mid-round, reload | No zombies saved; manager per decision; no duplicates |
| Z15 | fps at 0/8/16/24/32 alive (`hudstats.py`) | Owner-agreed floor (proposal ≥ 30 fps, 1% low ≥ 20) |

**Expected values, no dog rounds.** `P`: count per player number. `Delay` is in seconds. Walk/run/sprint gives
the chance of each speed tier. Bonus is the Ray Gun's mean round bonus.

| Round | Health | P=1 | P=2 | P=4 | Delay | MoveSpeed | Walk/run/sprint % | Bonus |
|---|---|---|---|---|---|---|---|---|
| 1 | 150 | 5 | 6 | 8 | 2.000 | 1 | 100/0/0 | 49.5 |
| 2 | 250 | 10 | 12 | 16 | 1.900 | 8 | 80/20/0 | 99.0 |
| 3 | 350 | 16 | 18 | 25 | 1.805 | 16 | 57/43/0 | 148.5 |
| 4 | 450 | 21 | 24 | 33 | 1.715 | 24 | 34/66/0 | 198.0 |
| 5 | 550 | 27 | 30 | 42 | 1.629 | 32 | 11/89/0 | 247.5 |
| 6 | 650 | 27 | 31 | 45 | 1.548 | 40 | 0/89/11 | 297.0 |
| 7 | 750 | 28 | 32 | 49 | 1.470 | 48 | 0/66/34 | 346.5 |
| 8 | 850 | 28 | 33 | 52 | 1.397 | 56 | 0/43/57 | 396.0 |
| 9 | 950 | 29 | 34 | 56 | 1.327 | 64 | 0/20/80 | 445.5 |
| 10 | 1045 | 33 | 42 | 78 | 1.260 | 72 | 0/0/100 | 495.0 |
| 11 | 1149 | 34 | 45 | 89 | 1.197 | 80 | 0/0/100 | 544.5 |
| 12 | 1263 | 36 | 49 | 101 | 1.138 | 88 | 0/0/100 | 594.0 |
| 13 | 1389 | 39 | 54 | 115 | 1.081 | 96 | 0/0/100 | 643.5 |
| 14 | 1527 | 41 | 59 | 129 | 1.027 | 104 | 0/0/100 | 693.0 |
| 15 | 1679 | 44 | 64 | 145 | 0.975 | 112 | 0/0/100 | 742.5 |
| 16 | 1846 | 47 | 70 | 162 | 0.927 | 120 | 0/0/100 | 792.0 |
| 17 | 2030 | 50 | 76 | 180 | 0.880 | 128 | 0/0/100 | 841.5 |
| 18 | 2233 | 53 | 82 | 198 | 0.836 | 136 | 0/0/100 | 891.0 |
| 19 | 2456 | 56 | 88 | 218 | 0.794 | 144 | 0/0/100 | 940.5 |
| 20 | 2701 | 60 | 96 | 240 | 0.755 | 152 | 0/0/100 | 990.0 |

With dog rounds, every later zombie round's health shifts back one step per dog round passed (§0).

---

## 6. Owner decisions needed
1. **Dinos vs zombies.** The default is that zombies ignore dinos and never retaliate, and dinos attack zombies
   per ARK aggro. Alternatives: full mutual combat, or both ignore each other.
2. **Targets.** Should tamed dinos be targets? (WaW has players only.) Riders: attack the rider, or drop the target?
3. **Hellhound rounds:** in or out. If out, accept the non-Der-Riese health curve.
4. **Player damage:** 60 per hit absolute, as WaW does, with ARK HP and armour bypassed (literal), or scaled to the
   player's ARK HP? Death instead of last stand (also open in the weapon design). Port the touch-kill failsafe?
5. **Start trigger** (item, map-load or test rig) and **game over** (reset to round 1 with a 15 s intermission,
   or keep ARK respawn).
6. **Spawn ring:** min/max radius, the visibility rule, and all zombies using the rise anim (replacing windows).
7. **Power-ups / points:** MVP out? Phase 2 list? Do insta-kill and nuke apply to every creature?
8. **Gib visuals** (crawler legs, head): approve the `HideBoneByName` recreation.
9. **Saving:** reset to round 1 on load (default), or persist the round number.
10. **ARK rewards:** kill XP and corpse harvesting off?
11. **Perf floor** and what happens if 32 alive misses it.

## 7. Blockers and unknowns
- `.work/fbx/zombie/` is empty: speeds, attack lengths and notetracks are still TBD.
- Whether GSC division is float (assumed, C), and the length of the NetFrame: both U.
- The zombie melee value of 60 is derived, not stated in the script (C).
- `BPGetTargetingDesire` versus the aggro table, ARK navmesh coverage far from the player, and the AnimBP parent
  class: all U until the editor is open.

## Addendum, 2026-10-07: measured values from the converter (`.work/fbx/zombie/REPORT.txt`)
- **Model.** The real Der Riese AI zombie (`aitype/axis_zombie_ger_ber_sshonor`) is the honor-guard body
  `char_ger_honorgd_bodyz{1,2}_{1,2}` with one of 24 `zombiehead*` heads, and no hat. It has a 96-bone skeleton
  rooted at `tag_origin`.
- **Root motion.** It lives in the xanim delta track; hips don't travel. 118 root-motion twins are exported.
  Zombie anims (assetType 2) store translation as an offset from the bind pose.
- **Locomotion speeds** (cycle distance ÷ duration). These replace the speed placeholders above:

| Alias | Anim | cm/s |
|---|---|---|
| walk1 | walk_v1 | 95.6 |
| walk2 | walk_v2 | 99.0 |
| walk3 | walk_v3 | 95.2 |
| walk4 | walk_v4 | 121.2 |
| run1 | walk_fast_v1 | 166.2 |
| run2 | walk_fast_v2 | 205.2 |
| run3 | walk_fast_v3 | 199.4 |
| sprint1 | sprint_v1 | 360.9 |
| sprint2 | sprint_v2 | 354.2 |

  Speeds for walk5–8, run_v1–4 and the crawls are in the report.
- **Melee hit frames** (notetrack `fire`, 30 fps):
  - attack_forward_v1: 29, 42
  - attack_forward_v2: 26, 42
  - attack_v1: 25, 39
  - attack_v2: 21, 70, 115, 134, 160
  - attack_v4: 8
  - attack_v6: 3, 49
  - run_attack_v1–4: 14 / 5 / 3 / 16
  - walk_attack_v1–4: 6 / 28 / 14 / 19
  - attack_crawl: 24, 54
  - lunge: 12
- **Content flag.** The body texture carries swastika and SS insignia. It's fine for private use, but needs a reskin
  before anything is ever shared.
