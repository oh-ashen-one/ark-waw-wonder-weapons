# Ray Gun + Wunderwaffe DG-2: ARK ModKit Blueprint design (2026-10-07)

This is a design only. Nothing has been built and the editor has not been opened. The rules are WaW's, applied
literally to every creature (owner decision), so a Wunderwaffe arc kills a Giganotosaurus.
Units: 1 WaW unit = 2.54 cm, and HP values carry over unchanged. Numbers come from `WAW-SPEC.md` and the
extracted files under `.work/extracted/nazi_zombie_factory*/`. Script text is not copied here: this document
describes the behaviour and cites the file and line.

Evidence tags:
- **P-pdb**: a type or member record in `Projects/ShooterGame/Binaries/Win64/UE4Editor-ShooterGame.pdb`.
- **P-refl**: a UTF-16 reflection name in `UE4Editor-ShooterGame.dll` or `Engine/.../UE4Editor-Engine.dll`.
- **P-exec**: an `exec<Name>@<Class>` UFUNCTION thunk. The function is reflected; BP-callability is likely but
  unconfirmed.
- **P-asset**: the name table of the vanilla `.uasset`.
- **C**: a community or forum claim. **U**: unknown, to be verified in the editor or in game.

---

## 1. Class chains

| Role | Ray Gun | Wunderwaffe DG-2 | Parent (evidence) |
|---|---|---|---|
| Item | `PrimalItem_RayGun` | `PrimalItem_Wunderwaffe` | `PrimalItemWeaponGenericGun` (BP, the parent of `PrimalItem_TekRifle`; P-asset) |
| Weapon | `WeapRayGun` | `WeapWunderwaffe` | **`ShooterWeapon_Projectile`** (native; `Default__ShooterWeapon_Projectile` appears in `WeapTekRifle`'s table, P-asset) |
| Projectile | `ProjRayGun` | `ProjWunderwaffe` | `ShooterProjectile` (native, P-pdb `AShooterProjectile`) |
| Ammo | `PrimalItemAmmo_RayGun` | `PrimalItemAmmo_Wunderwaffe` | `PrimalItemAmmo_Base` (BP, P-asset) |
| Damage types | `DmgType_WaW_*` (§2.4) | same | native `ShooterDamageType` (P-pdb) |
| Chain actor | none | `BP_TeslaChain` (+ `BP_TeslaBolt` for FX) | `Actor` |
| Buffs | `Buff_WaWExact`, `Buff_WaWElectrocuted` | same | `PrimalBuff` (P-pdb `APrimalBuff`) |

**Decision: do not parent the weapons to `WeapTekRifle`.** Its BP adds overheat logic (`AddHeat`,
`GetIs Overheated`, a `BPWeaponCanFire` override), the Element ammo, a percent-style clip display and the
`Buff_TekRifleScope` targeting buff (all P-asset). A plain `ShooterWeapon_Projectile` child avoids all of
that. Borrow only the Tek FPV rig and sockets as references. If the team falls back to `WeapTekRifle`, these
fields must be neutralised:

| Field (P-asset in WeapTekRifle) | Value |
|---|---|
| `OverheatAmountPerShot` | 0 |
| `OverheatReducePerSecond` | any (unused) |
| `OverheatReduceAfterShotInterval` | 0 |
| `OverheatedDelayInterval` | 0 |
| `TimeAfterOverheatingToAllowFire` | 0 |
| `bShowAmmoInClipAsPercent` | false |
| `WeaponAmmoItemTemplate` | our ammo item (not `PrimalItemResource_Element`) |
| Targeting scope buff / `bUseScopeOverlay` | off |

On the item, also set `bTekItem` = false (P-refl), so Tek engram gating doesn't apply.

### 1.1 Item defaults
| Property | Ray Gun | DG-2 | Note |
|---|---|---|---|
| `WeaponTemplate` | `WeapRayGun_C` | `WeapWunderwaffe_C` | P-refl |
| `bNewWeaponAutoFillClipAmmo` | true | true | Starts with a full clip, as WaW does. P-refl |
| `bUseItemDurability` | false | false | WaW guns don't wear out |
| `bTekItem`, `EquippingRequiresEngrams` | false, empty | same | |
| `DescriptiveNameBase` | "Ray Gun" | "Wunderwaffe DG-2" | |
| Weight | 0 (owner may change) | 0 | Not a WaW rule |

### 1.2 Weapon defaults (FWeaponData members are P-pdb; AShooterWeapon fields are P-refl)
| Property | Ray Gun | DG-2 | WaW source |
|---|---|---|---|
| `WeaponConfig.AmmoPerClip` | 20 (upgraded: 40) | 3 (DG-3: 6) | `clipSize` |
| `AmmoPerShot` | 1 | 1 | |
| `TimeBetweenShots` | 0.33 | 1.0 | `fireTime` |
| Full auto | hold to fire: `bAutoRefire`=true (U semantics) | same | `fireType` Full Auto |
| `bUsesAmmo` / `bInfiniteAmmo` / `bNeverReload` | true / false / false | same | |
| `bForceReloadDuration` + `NoAnimReloadDuration` | true + 3.0 | true + 6.0 (DG-3: 4.7) | `reloadTime` |
| `ReloadDurationPerAmmoCount`, `bLoopedReloadAnim` | 0, false | same | |
| `bShowAmmoInClipAsPercent` | false | false | |
| `WeaponAmmoItemTemplate` | `PrimalItemAmmo_RayGun_C` | `PrimalItemAmmo_Wunderwaffe_C` | |
| `ProjectileClass` | `ProjRayGun_C` | `ProjWunderwaffe_C` | |
| `EquipTime` | 0.8 | 0.9 | `raiseTime` |
| `WeaponUnequipDelay` | 0.8 | 0.83 | `dropTime` |
| `MeleeDamageAmount` | 150 (via the exact path, §2.4) | 150 | `meleeDamage` |
| `ProjectileSpreadYaw/Pitch` | hip spread 1→2, decay 3.25 (unit mapping U), ADS 0 | U | `hipSpread*` |
| `ItemDurabilityToConsumePerShot` | 0 | 0 | |

Reload timing caveat: the DG-2 has `reloadAddTime` 2.65 s, so WaW refills the clip 2.65 s into a 6 s reload.
ARK adds ammo at the end of the reload. The two only differ if a reload is cancelled, and that difference is
flagged (§5). The Ray Gun has `reloadAddTime` 0.

### 1.3 Ammo decision: **use an ammo item, not the ammoless or stored-charge pattern**
- WaW guns run dry. The clip plus reserve is the gun's real economy: Ray Gun 20 + 160 = 180 rounds, DG-2 3 + 15 = 18
  (`clipSize`/`maxAmmo`; `startAmmo` = `maxAmmo`).
- With an ammo item, the native code handles a lot for free: the HUD shows clip and reserve
  (`WeaponTotalAmmo`), reloads pull from the inventory, ammo persists in saves, and a later "Max Ammo" power-up
  is just one inventory set.
- An infinite-ammo gun with a hidden counter loses the HUD and the native reload path.
- Setup: the ammo item has `MaxItemQuantity` = 160 (DG-2: 15), no engram and no crafting. Giving the weapon also
  gives 160 (or 15) ammo.
- `WaW_SetReserve(n)` clamps the total across stacks to the WaW max (160/200 or 15/30). It is the only refill
  path. **Risk:** ARK lets a player hold extra stacks from other sources (§5).

### 1.4 Projectile defaults
| Property | ProjRayGun | ProjWunderwaffe | Source |
|---|---|---|---|
| `ProjectileComp` InitialSpeed = MaxSpeed | 8128 cm/s (upgraded 10668) | 5715 cm/s | 3200/4200/2250 u/s |
| `ProjectileGravityScale` | 0 (U, see §5) | **U: 0 or WaW grenade gravity** | DG-2 `projExplosionType grenade` |
| `WeaponConfig.ProjectileLife` | 10 | 30 | `projectileLifetime` |
| `WeaponConfig.DirectDamage` | **0**, applied in BP (§2) | 0 | Stops native bone/armor scaling |
| `WeaponConfig.ExplosionDamage` | **0**, applied in BP | 0 | |
| `WeaponConfig.ExplosionRadius` | 162.56 (FX scale only) | 279.4 (DG-3: 381) | 64 / 110 / 150 u |
| `bExplodeOnImpact` | true | true | `projImpactExplode 1` |
| `bExplodeOnLifeTimeEnd` | false (U) | false (U) | |
| `bIgnoreDirectImpactRadialDamage` | n/a (our BP handles it, §2.2) | n/a | P-refl |
| `CollisionComp` radius | ~2.5 cm (CoD projectiles are point traces) | same | |
| `DirectDamageType` / `DamageType` | `DmgType_WaW_Impact` / `DmgType_WaW_Splash` | `DmgType_WaW_TeslaShot` | |
| Hook | override event `OnExplode(Result)` (P-refl; `ProjTekRifle` uses it) | same | |

All damage logic runs only on the authority (`HasAuthority`).

---

## 2. Ray Gun damage

### 2.1 Direct hit
When `OnExplode` fires and `Result.HitActor` is an `APrimalCharacter`, the direct victim takes
`WaW_DealExact(victim, 1000, DmgType_WaW_Impact)`. That damage counts as `MOD_PROJECTILE`, so the round
bonus (§2.3) follows it.

### 2.2 Splash: custom BP, because the falloff function can't be called from BP
- `UGameplayStatics::ApplyRadialDamageWithFalloff` exists natively, but **has no exec thunk**, so BP can't call
  it. Only `ApplyRadialDamage` and `ApplyRadialDamageIgnoreDamageActors` are BP-exposed (P-exec, Engine).
- Stock `ApplyRadialDamage` falls off linearly to 0 at the radius, which gives the wrong curve here.

`WaW_RadiusDamage(origin, R=162.56, inner=1500, outer=300, type)`:
1. Collect characters with `SphereOverlapActors_NEW` or `UVictoryCore::OverlappingActorsBP` (P-exec), radius R
   plus the largest capsule radius.
2. For each one, `d` = distance from the origin to the **closest point on its capsule**: the distance to the
   capsule axis segment minus the capsule radius, clamped to ≥ 0. Use `GetCharacterCapsuleSize` (P-exec).
   WaW measures to the closest point on the bounding box, a Quake-lineage claim (C). Skip any target with d > R.
3. Line of sight: trace from the origin, pushed 2.54 cm along the impact normal, to the closest point. Use the
   world-geometry object types only, so creatures don't block.
4. `dmg = outer + (inner − outer)·(1 − d/R)`, which is `1500 − 1200·d/162.56` (upgraded: `2000 − 1700·d/R`).
5. Call `WaW_DealExact(target, int(dmg), DmgType_WaW_Splash)`, then add the round bonus for creatures.
- Default: the direct-hit victim is left out of the splash (`bSplashIgnoresDirectVictim` = true, Quake-lineage
  behaviour, C). Whether WaW stacks direct and splash damage is **U**. It needs owner research or a test in WaW
  developer mode.

| d (cm) | 0 | 40.64 | 81.28 | 121.92 | 162.56 | >162.56 |
|---|---|---|---|---|---|---|
| Splash | 1500 | 1200 | 900 | 600 | 300 | 0 |

### 2.3 Round bonus
- WaW (`_zombiemode_spawner.gsc` L2691–2700, inside `zombie_damage` L2644): every `MOD_PROJECTILE`,
  `MOD_EXPLOSIVE` or `MOD_PROJECTILE_SPLASH` event on a zombie adds a second hit of
  `round_number × randomintrange(0,100)`, which is an integer from 0 to 99.
- ARK: after each impact or splash event on a **creature** (not a player), deal
  `Round × RandomIntegerInRange(0,99)` with `DmgType_WaW_RoundBonus`.
- `Round` = `BP_WaWRoundManager.CurrentRound` from the planned zombie round system, looked up once and cached.
  **Default 1** when there is no manager. The test rig can override it.

### 2.4 Exact damage, so ARK armour and resistances can't change the numbers
ARK's damage hooks that could scale the numbers:
- `DamageTypeAdjusters` and `BoneDamageAdjusters` on characters (P-refl).
- `FDamageTypeAdjuster` entries, matched by damage-type inheritance (C, wikily damage calculator).
- Game-mode multipliers: `PlayerDamageMultiplier`, `DinoResistanceMultiplier`, `DinoClassResistanceMultipliers`
  and others (P-pdb `AShooterGameMode`).
- Buffs: `ReceiveDamageMultiplier` and `BuffAdjustDamage` (P-pdb).
- Equipped armour on players: `GetEquippedArmorRating` (P-pdb).

There is **no `bIgnoreArmor` flag** in this build (absent from both binaries).

Design:
1. `DmgType_WaW_Base` is a child of **native `ShooterDamageType`**, not of `DmgType_Explosion`, so
   class-matched adjusters keyed on vanilla types don't match it. Set `DamageTorpidityIncreaseMultiplier` = 0,
   `bDamageInstigator` = true and `DamageInstigatorPercentage` = 1 (self-splash is allowed; semantics C), and
   `bUseBPAdjustDamage` = true. Its `BPAdjustDamage(Victim, IncomingDamage, …)` (P-pdb params) only logs the
   incoming value for diagnostics. Children: `_Impact`, `_Splash`, `_RoundBonus`, `_TeslaShot`, `_TeslaKill`,
   `_Self`, `_Melee`.
2. Damage goes in through `UGameplayStatics::ApplyDamage` (P-exec), not point damage. That way no hit bone
   reaches `BoneDamageAdjusters`.
3. `Buff_WaWExact` sits on the victim. It is added with `APrimalBuff::StaticAddBuff` (P-exec), or reused via
   `GetBuff` (P-exec).
   - Set `bPreventOnBossDino`, `bPreventOnBigDino`, `bPreventOnDino` and `bPreventOnPlayer` all to false (P-refl).
   - Set `DeactivateAfterTime` / `DeactivationLifespan` to 2 s, refreshed on each use.
   - Its `BuffAdjustDamage(Damage, HitInfo, EventInstigator, DamageCauser, TheDamgeType) → float` (P-pdb)
     returns the `PendingExact` value when the type is a child of `DmgType_WaW_Base`.
4. Call order of `WaW_DealExact(T, A, Type)`:
   1. Read `H0 = GetHealth()`.
   2. Set `Buff.PendingExact = A`.
   3. Call `ApplyDamage`.
   4. Read `H1`.
   5. Log `class, H0, A, H0−H1`.
   6. If `A ≥ H0` and `IsAlive()` is still true, use the fallback kill (§3.5).
   7. If `H0−H1 ≠ min(A, H0)`, log `EXACT_MISMATCH`. Test T10 fails on that line.
- **U:** whether `BuffAdjustDamage` runs after armour and the game-mode multipliers. If it runs before them,
  the server multipliers must stay at 1.0, and that is checked in T10.

### 2.5 Player self-damage
- WaW rule (`_zombiemode.gsc` L2604–2611): on any `MOD_PROJECTILE`, `MOD_PROJECTILE_SPLASH`, `MOD_GRENADE` or
  `MOD_GRENADE_SPLASH` damage to a player, if health is above 75 the final damage is 75. Otherwise the full
  damage applies (L2614 onwards). Because splash is always at least 300, a hit at or below 75 HP downs the player.
- ARK: inside `WaW_RadiusDamage`, a player victim (the shooter or a co-op player) is handled in the projectile
  BP: `A = (H > 75) ? 75 : rawSplash`, delivered through `WaW_DealExact` with `DmgType_WaW_Self`. No bonus
  applies to players. No player-pawn subclass is needed.
- **Flag:** WaW downs the player (last stand), but ARK has no last stand, so the player dies. Owner to confirm.
- The ray gun file also has `playerDamage 0`, whose SP meaning is U. The script-level cap above is what the
  game implements.

---

## 3. Wunderwaffe: `BP_TeslaChain`

### 3.1 Trigger
`ProjWunderwaffe.OnExplode`:
1. Deal 1 damage to the direct victim and to everything within 279.4 cm with line of sight (`damage` and
   `explosionInner/OuterDamage` are 1, `explosionRadius` 110). Use `_TeslaShot`.
2. Pick the root. In WaW the root is the first zombie whose damage callback fires (spawner L2670–2673, tesla
   L46–79). Here: **the direct victim if it is a creature; otherwise the nearest creature in the splash.**
   WaW's order is effectively entity order (arbitrary), so nearest-first is a deterministic stand-in (flag).
3. Per-player lock (tesla L50–54): if this player's previous chain is still in its search phase, ignore the
   shot. The lock clears when the search (depth-first) finishes, not when the kills finish. A root that is
   already marked as hit is also ignored (L56–60).
4. Players inside the splash get the self or PvP effect (§3.6).
5. Spawn `BP_TeslaChain` with Root, Player and ArcNum = 1.

### 3.2 Constants (tesla L32–40)
| Var | WaW | ARK |
|---|---|---|
| `tesla_max_arcs` | 5 (stop when the next arc_num ≥ 5, so arcs 1–4 exist) | 5 |
| `tesla_max_enemies_killed` | 20 | 20 |
| Search radius at arc n | `300 − 20·n` u | n=1: 711.2, n=2: 660.4, n=3: 609.6, n=4: 558.8 cm |
| `tesla_arc_travel_time` | 0.5 s | 0.5 s |
| `tesla_min_fx_distance` | 128 u | 325.12 cm (shorter arcs skip both the bolt and the 0.5 s wait) |
| `tesla_head_gib_chance` | 50 | 50 |
| `tesla_kills_for_powerup` | 15 | 15 (log only) |
| `tesla_network_death_choke` | 4 | 4 |
| `NetFrame` (`wait_network_frame`) | U: its definition isn't in the extracted zones | 0.1 s, configurable |

### 3.3 Algorithm (depth-first, matching the order in L83–115)
- **Candidate cache** (L154–158): on the first search, take every hostile creature and sort it by distance from
  the root's head. Reuse that list for the whole chain, so creatures that arrive later are ignored.
  - ARK candidates: every living `APrimalCharacter` that is not a player and not on the shooter's
    `TargetingTeam` (wild dinos and WaW zombies).
  - Pre-filter with an overlap of radius 7,500 cm around the root, for performance (deviation is only possible
    if a creature moves more than about 50 m mid-chain).
- **`ArcDamage(node, src, n)`**, a state machine driven by timers because BP has no coroutines:
  1. Mark `node.hit`.
  2. **Wait one NetFrame.**
  3. Start `KillTask(node, src, n)`, which runs in parallel.
  4. Search from `Head(node)` with radius `(300−20n)·2.54`.
  5. Mark every candidate found as hit.
  6. For each candidate, in cached distance order: if the end condition is met, unmark it and continue.
     Otherwise `EnemiesHit++` and run `ArcDamage(cand, node, n+1)` to completion before moving to the next
     sibling (an explicit stack).
- **End condition** (L118–142): `n+1 ≥ 5`, or `EnemiesHit ≥ 20`, or the radius ≤ 0. `EnemiesHit` starts at 1,
  for the root.
- **Search filter** (L164–194): skip candidates that are invalid, dead or already hit. Keep a candidate when
  `|Head(c) − origin|² ≤ r²` and the line-of-sight trace (world geometry only, characters ignored, as in
  `BulletTracePassed(…, false, …)`) reaches it.
- **`KillTask`** (L217–310):
  1. If n > 1, wait `RandomFloatInRange(0.2, 0.6) × n`.
  2. If the node is dead, abort.
  3. If `src ≠ node`, run the arc counter: when it exceeds 3, wait one NetFrame and reset it to 0, then add 1.
     Then play the bolt from `src` to the node. This **blocks for 0.5 s** unless the body-centre distance is
     under 325.12 cm.
  4. Death choke: while `ChokeCount > 4`, wait 0.05 s. `ChokeCount` is reset to 0 every 2 NetFrames
     (L569–583), so at most 5 kills happen per window. Keep this in single player: WaW applies it in solo too,
     and it shapes the timing.
  5. Run the death FX (L313–343). The head-gib roll happens here: on a hit (`RandomInt(100) < 50`), wait
     `RandomFloatInRange(0.53, 1.0)` and gib. **The kill waits for that delay.** On a miss, play the eye FX.
  6. Kill: a boss takes `WaW_DealExact(1000)`. Anything else takes `WaW_DealExact(GetHealth() + 666,
     _TeslaKill)` (L290–301).
  7. Power-up check (L304–309): when `EnemiesHit ≥ 15`, log the power-up once per shot.

### 3.4 Head origin (`j_head` stand-in)
The vanilla skeletons were sampled (P-asset):
- Rex, Raptor, Stego and Human use `Cnt_Head_JNT_SKL`.
- Giga, Dodo, Gorilla, Spider-Large, Dragon and Trike use `c_head`.
- `BuffSocketHeadDynamic` appears in every one; `HeadSocket` in most.

`Head(c)`:
1. Take the first name in `[c_head, Cnt_Head_JNT_SKL, head, Head, HeadSocket, BuffSocketHeadDynamic]` for
   which `Mesh.DoesSocketExist` (P-exec) is true, and use `GetSocketLocation`.
2. Otherwise use the capsule top (location + up × half-height).
3. Cache the result per class.

Bolt and arc distances use the capsule centre in place of `J_SpineUpper`.

### 3.5 Instakill, bosses and the fallback
- The primary kill is the exact damage of `health + 666`.
- Fallback if the target is still alive: `APrimalDinoCharacter::Die(KillingDamage, DamageEvent, Killer,
  DamageCauser)`, which is a UFUNCTION (P-exec; signature from the PDB). Otherwise
  `UVictoryCore::KillTargetCharacterOrStructure(AActor*, AActor*, bool)` (P-exec; parameter meaning C/U).
- **Boss = `APrimalCharacter::IsBossDino()`** (P-exec; `bIsBossDino` P-refl). That covers the arena bosses:
  `SpiderL_*`, `Gorilla_*`, `Dragon_Character_BP_Boss*`, `BossDinopithecus_*` and so on.
- Alphas (`MegaRex`, `MegaRaptor`, `MegaCarno`, `MEgaMegalodon`, `Mega_Tusoteuthis`) and the Giga count as
  normal creatures and are instakilled. Toggle: `bTreatAlphasAsBoss`, default false. **Owner approval needed.**

### 3.6 Player effect (tesla L485–532)
- A player hit by the projectile or inside its splash gets the effect.
- **Self only:** `dmg = max(25, int(MaxHP·0.25))`, clamped so health never drops below 1 (`dmg = min(dmg,
  H−1)`), through the exact path.
- **Every player hit:** `Buff_WaWElectrocuted`, `DeactivateAfterTime` = 1.0. Its parameters come from
  `shock/electrocution.shock`:
  - blur, blend-in 0.4 s and fade 1 s, through `BuffPostProcessEffect` (P-refl)
  - view kick, period 0.75 and radius 0.05, fading over 3 s, through `ClientPlayCameraShake` (P-exec)
  - look speed capped at 90°/s and sensitivity ×0.5, fading over 2 s
  - audio ducked to 0.5
- **Flag:** this is a recreation. Look-rate control from a buff is U.

### 3.7 Head-gib substitute (needs owner approval before it ships)
- ARK has no gibbing. Proposal: at the gib moment, call `HideBoneByName(<head bone>)` (P-exec, Engine) and
  spawn a blood-burst emitter at `Head(c)`.
- Ship with `bHeadGibVisual` = false until the owner approves.
- **The 0.53–1.0 s death delay is kept either way**, because it is gameplay timing.

---

## 4. Verification plan

The mod logs to `ShooterGame.log`:
- `WAW_DMG`: class, H0, intended, delta, type, t.
- `WAW_ARC`: node, parent, n, t_visit, t_kill, gib.

Commands (P = present in `UShooterCheatManager`; argument syntax is C,
[wikily SpawnDino](https://wikily.gg/ark-survival-ascended/commands/spawndino/),
[arkcheat](https://arkcheat.com/commands/spawndino)):
- `cheat SpawnDino "Blueprint'/Game/PrimalEarth/Dinos/Giganotosaurus/Gigant_Character_BP.Gigant_Character_BP'" 1000 0 0 1`
  (distance in cm)
- `cheat SpawnExactDino`
- `cheat DestroyWildDinos`
- `cheat ToggleDamageNumbers`, `cheat ToggleDamageLogging`
- `cheat SetGodMode 0/1`, `cheat InfiniteStats`, `cheat EnemyInVisible true`, `cheat LeaveMeAlone`
- `cheat WhatIsMyTarget`, `cheat DebugMyTargetPrint`, `cheat SetMyTargetSleeping`
- `cheat ListMyTargetBuffs`, `cheat ForceGiveBuff`
- `cheat SetTimeOfDay 12:00`, `cheat TPCoords`, `cheat Slomo 0.25`
- `cheat giveitem "<path>" 1 0 0`

`GetAllState` doesn't exist in this build, and `ForceTame` is unsuitable because it changes the team and the
resistances. For measured distances, **`BP_WaWTestRig`** in `ArkMashup.umap` spawns creatures without AI
controllers (so they stand still) at exact offsets, and sets the debug `Round`.

| # | Test (real keyboard/mouse input) | Pass if |
|---|---|---|
| T1 | 50 direct Ray Gun hits on a level-1 Giga, Round 1 | each delta ∈ [1000, 1099], bonus mean ≈ 49.5 |
| T2 | Ground shots at d = 0, 40.64, 81.28, 121.92, 162.56, 170 cm from a Giga's capsule | splash = 1500/1200/900/600/300/0 (±1), plus bonus |
| T3 | Hold fire for 10 s | 31 ±1 shots; clip empty at 6.27 s; reload 3.00 s ±0.05 (DG-2: 1 s and 6 s) |
| T4 | Empty all ammo | 180 shots (DG-2: 18); refill caps at 160/15 |
| T5 | Self-splash at 100 HP, then at 25 HP | first delta = 75; second is lethal |
| T6 | Chain geometry: B at 700 or 715 cm head-to-head from root A; C at 655 or 665 from B | hit/miss at each boundary as §3.2 predicts |
| T7 | Line of 7 dodos at 400 cm spacing | exactly 4 die (arcs 1–4) |
| T8 | Cluster of 30 dodos | exactly 20 die; one power-up log line at 15 |
| T9 | Wall between A and B | B survives |
| T10 | Level-150 Giga root; Broodmother and Megapithecus roots; armoured player self-hit; `DinoResistanceMultiplier`=2 test ini | Giga delta = H+666, dead; bosses −1000; no `EXACT_MISMATCH` |
| T11 | Second DG-2 shot during the first chain's search | no second chain |
| T12 | Timing A/B: ARK at 60 fps vs WaW Der Riese footage | match frame-counted on root death (1 NetFrame, +0.53–1.0 s on gib), bolt travel 0.5 s, and arc-n kill ≥ NetFrame + 0.2n (+0.5); also projectile drop over 1,000 u (gravity check) |

---

## 5. Risks and unknowns
1. **Exactness:** where `BuffAdjustDamage` sits in the call order is U. Fallback: the server multipliers stay
   at 1.0, and the logged mismatch tells us how big the error is. Blueprint can't override native
   `TakeDamage`.
2. **Falloff:** the native falloff isn't BP-callable, so the radial damage is custom BP. Its distance metric
   (closest point on the capsule) is an approximation of WaW's bounding box. Large ARK hit volumes are part
   mesh, part capsule.
3. **Unknown WaW engine behaviour:** whether direct and splash damage stack; projectile gravity for "none" and
   "grenade" types; how long `wait_network_frame` is; how `reloadAddTime` 0 behaves; what `playerDamage 0`
   means.
4. **Kill fallbacks:** `Die` and `KillTargetCharacterOrStructure` exist, but their BP-callability and
   parameter meaning are U until the editor confirms them.
5. **Bosses:** some may have native damage caps or `bPreventOnBossDino` buffs. T10 covers this.
6. **Odd skeletons:** fish, Basilisk and some DLC creatures fall back to the capsule top.
7. **Performance:** sorting every creature on a full map. Mitigated by the 75 m pre-filter and per-class head
   caching.
8. **Ammo cap:** ARK lets a player hold extra stacks of the ammo item. The 160/15 cap is only enforced through
   `WaW_SetReserve`.
9. **Recreations that need owner approval:** the head gib, the electrocution feel, the lightning FX, death
   instead of last stand, alphas treated as non-boss, and the nearest-root rule.
10. **Native side effects:** a native impact with `DirectDamage` 0 may still play the hurt animation or trigger
    aggro. The tesla's 1-damage hit also aggros wild creatures, which is faithful.
11. **Blueprint-only limits:** there are no coroutines, so everything runs on timers and explicit stacks. There
    is also no native console-command hook for `Round`, so the test rig sets it instead.
