# Feasibility plan — ARK × Skate 3 × CoD: World at War wonder weapons

> 2026-10-06 update: the source game switched from BO1 to **World at War** (Ray Gun + Wunderwaffe DG-2). The BO1 sections below are kept as reference. The WaW equivalent is pending research, but the approach is the same: extract the owned weapon defs and GSC, port them, then A/B against footage.

Owner decisions (2026-10-06):
- Fortnite building is dropped.
- Skating on structures is not required: skate on ARK's terrain.
- BO1 rules apply literally to all creatures.
- BO1 zombies are added.
- More wonder weapons come after the Ray Gun and Thundergun.
- None of the games are owned yet.

Status: research only, 2026-10-06. Nothing has been installed or run.
Labels:
- **P**: proven by docs or code.
- **C**: claimed by a repo or report, not yet verified.
- **H**: our hypothesis, untested.
- **U**: unknown.

## 1. Host choice: ASE (Windows) in CrossOver 26.3

| | ASE Windows in CrossOver | ASA Windows in CrossOver | ASE native Mac |
|---|---|---|---|
| Runs here | "Runs Great", CrossOver 25.1.1 (P, CodeWeavers DB) | "Runs Well", 1 rating; M-series reports range from 2 to 120 fps (C) | 2023 build, Intel-only, crashes reported (P) |
| Graphics API | D3D11 (DXMT/DXVK path) | D3D12 (D3DMetal 3.0) | OpenGL |
| Install size | 166 GiB base (P, SteamDB) | 212 GiB base (P) | 91 GiB |
| Mod tooling | ASE ModKit (UE4, ~60 GB claimed). In CrossOver: **U**, the most plausible | ASA DevKit (UE5.5, 1.2–1.5 TB, DX12). In CrossOver: unlikely | — |
| Offline | Single-player with "Start without BattlEye" (P) | Offline mods since 1.075.022 (P); BattlEye in Wine: U | — |

Neither DevKit is proven anywhere except on Windows. If the ASE ModKit fails in CrossOver, the
fallback is a Windows x64 PC (32 GB RAM, 2 TB NVMe, RTX 3060-class GPU). Nothing will be purchased
without the owner's decision.

## 2. Who owns what

```
 controller/kb ─► ARK client (CrossOver bottle "ark-mashup")
                    │ native seam (H: AseApi plugin on a local private server, or a client proxy DLL)
                    ▼
                 bridge helper (same bottle) ◄──localhost UDP, SK8 protocol v12──► SK8-ENGINE (same bottle)
                    ▲  pad state via \\.\pipe\Skate3InputLab ──────────────────────────────┘
```

| Concern | On foot / building / shooting | Skating |
|---|---|---|
| **Input** | ARK | ARK window keeps focus. The seam forwards pad state to SK8 through the Input Lab pipe (P that the pipe exists; H that it works under Wine). Flick-it needs a physical gamepad. |
| **Movement** | ARK CharacterMovement | SK8 simulates. The ARK character becomes kinematic and follows SK8's root pose (60 Hz). On dismount or bail, control returns to ARK at SK8's last position and velocity. |
| **Camera** | ARK | ARK camera placed at Skate 3's camera transform. **U:** protocol v12 sends root pose and bones, not the camera. Read the camera from SK8 instead (H), or else it is a recreation that needs approval. |
| **Rendering** | ARK | ARK draws the skater. SK8 runs alongside, off-screen or minimised. Whether SK8 can render cheaply or not at all is **U** (there is no null-render mode today). |
| **Collision** | ARK | SK8 uses a mirror of ARK geometry (§3). ARK collision stays authoritative for creatures and damage. |
| **Damage** | ARK, always: weapons, creatures, fall damage | Bails are SK8 physics. Whether a bail or impact deals ARK damage is a design decision. |
| **Saving** | ARK save: structures, inventory, ammo | The SK8 world is session-only and rebuilt from ARK state on load (SK8 edits are session-only anyway, P). |

**The native seam is required.** ARK mods are Blueprint-only: they have no sockets and no native
code. Two candidates, both used offline only with BattlEye off through the official launch option:
- **N1:** AseApi C++ plugin on a local private ASE dedicated server, with the client connecting to
  localhost. The server binary has full game state. **Risk:** AseApi's last release is 3.56
  (2024-03); the community wiki calls it "unsupported" after the Aquatica update (2025).
- **N2:** client proxy DLL, the same pattern as DSR×MW2's XInput proxy, with hooks found through
  Ghidra + ghidra-mcp. **Risk:** no symbols are known for the client (U).

## 3. Mechanics

### Skating surface

- **Terrain.** An ARK terrain patch around the play area is exported once from the ModKit into an SK8
  `.skate` world. Swapping the whole map restarts SK8 (P). Phase 1 covers one test area, not all of
  The Island.

### Skate × ARK actors

- Creatures are not in SK8's world.
- The seam sends nearby creature capsules as moving `.skateobj` blockers: **H**, and costly at
  64 MiB-per-package granularity. Collisions therefore play out in SK8.
- Damage is applied in ARK.
- First version: creatures as ARK-only obstacles. On contact the player is forced to bail.

### World at War weapons (source game since 2026-10-06; P = from stock scripts and weapon files)

- **No source code exists.** There is no T4 decompile or source release. The behavior lives in plain-text
  GSC scripts and weapon files that ship with the official Mod Tools and in the game's fastfiles, so we
  port from those.
- **Mod Tools reupload.** It contains `raw/maps/_zombiemode{,_tesla,_weapons,_spawner}.gsc`,
  `raw/weapons/sp/{ray_gun,tesla_gun}{,_upgraded}` and loose WAVs for both weapons. The scripts match
  Der Riese's shipped scripts.
- **Ownership.** We re-extract `RawFile` and `WeaponDef` from the owner's Steam install with
  OpenAssetTools v0.33 (T4 supports XModel/XAnim/WeaponDef/RawFile/LoadedSound) to confirm the values.

**Ray Gun**
- Direct damage 1000.
- Splash radius 64, inner/outer damage 1500/300.
- Fire time 0.33 s.
- Projectile speed 3200, lifetime 10 s.
- Clip 20, max ammo 160, reload 3 s.
- Bonus damage per hit: `round_number × RandInt(0,100)`.
- Upgraded: splash inner 2000, speed 4200, clip 40, max ammo 200.

**Wunderwaffe DG-2**
- Ammo: clip 3, max ammo 15. Fire time 1.0 s, reload 6.0 s.
- Projectile: speed 2250, splash radius 110.
- Chain lightning:
  - It branches as a tree, up to 4 arc generations and a cap of 20 kills.
  - Radius is 300 − 20 per arc, measured head to head and requiring line of sight.
  - Each arc takes 0.5 s to travel. Arcs after the first wait `rand(0.2,0.6) × arc_num`.
- Each hit is an **instakill**: `health + 666`.
  - Applied literally to ARK, so a Giga hit by an arc dies.
- Self-damage: max(25, 25% of max health), never lethal, plus 1 s electrified/shellshock.
- Upgraded (DG-3 JZ): clip 6, max ammo 30, reload 4.7 s, splash radius 150.

**Zombies (`_zombiemode.gsc`)**
- Health: 150, +100 per round up to round 9, then +10% per round.
- Count: 24 plus a player term, scaled by round, with early-round multipliers.
- At most 32 alive. Spawn delay 2 s × 0.95 per round.
- Speed tiers (walk/run/sprint) are rolled from `round × 8`.
- Open: `zombiemode.csv` may override some of these values. Confirm from the owner's install.

**Platform and licence**
- WaW (Steam 10090, ~9.8 GB) is ProtonDB Gold and "Runs Well" in CrossOver (C). Not yet tested on
  this Mac.
- Mod Tools EULA: personal and non-commercial only. Keep everything private, and never distribute
  extracted assets.

**Earlier BO1 reference** (superseded)


- **Why it's a port.** Pass-through is not possible: T5 is a closed 32-bit Windows executable, and the
  weapons call native engine functions (P). Instead we would port the original data faithfully.
- **Data source.** Extract the vanilla `weapons/sp/ray_gun_zm`, `thundergun_zm`, their
  Pack-a-Punched versions and `_zombiemode_weap_thundergun.gsc` from the owner's BO1 copy with
  OpenAssetTools. The public Jbleezy repo is mod-tuned, so it is not usable as vanilla.
- **Ray Gun.**
  - Full auto, ~0.33 s.
  - Projectile at its defined speed.
  - Explodes on impact with splash: radius 64, inner/outer damage.
  - ARK projectile class with radial damage.
- **Thundergun.**
  - Instant on fire: a cylinder 1200 long and 180 radius in front of the muzzle, checked for line
    of sight.
  - Distance bands (BO1 units, 480 = 40 ft):

    | Distance | Effect |
    |---|---|
    | < 480 | kill + fling |
    | 480–900 | knockdown + gib |
    | 900–1200 | knockdown |

  - Fling = 100 + 100·(1−d²/480²).
  - Scale: 1 BO1 unit ≈ 2.54 ARK cm.
  - **Literal rules (owner):** the BO1 bands apply to every creature. A Giga inside 480 units dies
    and gets flung, the same as a zombie.
  - The Ray Gun deals its original damage and splash, unscaled. Against ARK's large health pools
    that means many hits, which is intended.
  - ARK has no zombie knockdown, so "knockdown" maps to ARK's own stun/knockback plus the BO1 fling
    impulse.
- **Viewmodel / HUD.** Weapon models (XModel) and animations (XAnim) come from the owner's install
  through OAT or Greyhound. They become ARK first-person meshes, with the BO1 ammo counter and
  crosshair recreated in the ARK HUD.
  - Gap: OAT cannot dump T5 sound banks, and BassDrop on BO1 is U.
- **Verification.** A/B against recorded BO1 footage: fire rate, projectile travel, Thundergun bands
  at measured distances.

### Zombies in ARK (WaW)

- **Same approach as the weapons.** The zombie AI and rules are ported from the owner's BO1 scripts
  (`_zombiemode*.gsc` spawner, round and damage logic), and the models and animations are extracted
  from the owner's install.
- **In ARK** each zombie becomes an ARK creature (Blueprint AI), so ARK damage, death and saving
  work natively.
- **Default behavior, matching BO1:**
  - Round-based spawning, with health and count scaling taken from the script.
  - Zombies chase players only. Whether dinosaurs fight zombies is an open question for the owner.

### More wonder weapons

The same pipeline as above: extract the weapon def and its GSC, port it, then A/B it against
footage. Ray Gun and Thundergun first. Candidates afterwards include the Wunderwaffe DG-2, Winter's
Howl, Scavenger, Wave Gun, V-R11, 31-79 JGb215, Monkey Bomb, Gersh Device and QED. Each one is a
separate milestone.

## 4. Proven vs hypothetical; full-fidelity blockers

- **P:**
  - SK8-ENGINE keeps the original Skate 3 skater, board, tricks, physics, camera and grinds, and
    accepts arbitrary triangle collision and polyline rails, including live append.
  - SK8's D3D12 path needs only feature level 11_0 with SM5 (fits D3DMetal).
  - ASE runs in CrossOver.
  - The weapon parameters sit in readable defs and GSC.
- **H:**
  - SK8 runs under CrossOver (zero reports).
  - An external helper can speak protocol v12 and the Input Lab pipe under Wine.
  - A native seam into ASE: N1 or N2.
  - The ASE ModKit runs in CrossOver.
  - OAT runs in CrossOver.
  - Two engines together at playable frame rates.
- **Blockers to 100% fidelity:**
  - BO1 weapon behavior is a faithful port, not the T5 runtime (the same approach other games'
    wonder-weapon mods use).
  - The Skate camera inside ARK (U).
  - The Skate skater appearance inside ARK: the ARK body retargeted to Skate bones, or the extracted
    skater mesh.
  - BO1 sounds.
  - ≥1 frame of extra latency across processes.
  - The GPU cap.
  - Disk: ~300 GB needed.

## 5. Smallest experiment, then milestones

**Exp-0 tests the hardest assumption:** "the original Skate runtime runs on this Mac, accepts our
geometry live, and exposes pose". If it fails, original skating is impossible regardless of ARK.
1. Set up a new CrossOver bottle `sk8-exp0`, SK8-ENGINE v0.1.0-preview.18 (D3D12) and the owner's
   Skate 3 Xbox 360 ISO with Title Update 3.
2. Load the Feature Park.
3. A script generates 2 `.skateobj` files: an ARK-foundation-sized ramp, and a wall with a top-edge rail.
4. Spawn them live (G → E) without restarting.
5. Skate them with a real gamepad and record it.
6. A helper in the bottle reads skater pose over localhost UDP v12 and logs it.

Pass criteria:
- 30 fps or better, with frame times recorded
- the ramp is rideable
- the rail latches and grinds
- pose stream at 55 Hz or better, consistent with the video
- no restart

Peak use is ~20 GB and one renderer.

**Milestones** (each one ends with input-driven evidence and an owner check):
- **M0:** Prerequisites.
  - The disk space is confirmed claimable.
  - The owned-copies list is confirmed.
  - Approvals 2–4 from CLAUDE.md.
  - The huge-dinosaur rule.
- **M1:** Exp-0.
- **M2:** ARK host.
  - ASE in a new bottle `ark-mashup`, offline, no BattlEye, with frame times measured.
  - The ModKit in the bottle cooks a trivial mod that loads in-game.
  - Seam probe: N1 or N2 logs player position at 60 Hz.
- **M3:** Bridge v0 on flat ground.
  - The ARK player's position seeds SK8; SK8's pose drives the ARK character.
  - Pad routing works.
  - Two renderers, which needs the cap exception.
- **M4:** Skating on an ARK terrain patch, with the Skate camera.
- **M5:** Ray Gun, then Thundergun. Owned-file extraction, ARK weapons, viewmodel HUD, footage A/B.
  This can run before M3/M4: it needs only ASE and BO1.
- **M5b:** BO1 zombies in ARK, with round spawning and literal BO1 stats.
- **M5c+:** further wonder weapons, one at a time.
- **M6:** Integration.
  - Terrain patch, Skate camera, mode switching, save/load round-trip.
  - Frame-time target 16.7 ms, or an honest measured number.
  - Opus critic pass, full playtest.

## 6. Dependencies, versions, licenses, hardware, rollback

| Item | Version | License / terms | Status |
|---|---|---|---|
| macOS | 27.0.1. Do not upgrade to 28, which drops Rosetta | — | installed |
| CrossOver | 26.3 (D3DMetal 3.0, Wine 11.0, DXMT 0.72). Not 27 preview | commercial | installed |
| ARK: Survival Evolved (Steam 346110, Windows) | 361.4 (2025-12-23) | Steam EULA; Wildcard mod terms | **not owned**. Steam price $9.89 (34% off, 2026-10-06) |
| ASE ModKit (Epic) | current | Wildcard/Epic EULA | Windows-only (P); CrossOver U |
| AseApi (N1 option) | 3.56 (2024-03-23) | MIT (AsaApi; AseApi U) | stale post-Aquatica |
| SK8-ENGINE | v0.1.0-preview.18, commit `311cd40e` | MIT own code; runtime fork BSD-3; upstream skate3recomp `f6e0ae87f` has no license | dormant since 2026-08-28 |
| Skate 3 | Xbox 360 ISO + TU3, owner-dumped | owned copy | **not owned**. Needs a physical Xbox 360 disc plus Xbox 360 disc-dumping hardware (U: method to confirm) |
| Call of Duty: Black Ops (Steam 42700, Windows) | current | Activision EULA | **not owned**. Steam price $39.99 (2026-10-06); Proton gold; CrossOver U |
| OpenAssetTools | v0.33.0 (Win x86 zip) | GPL-3.0 | CrossOver U |
| Greyhound (Wraith fork) | latest | GPL-3.0 | BO1 support U |
| Ghidra + ghidra-mcp (N2 option) | Ghidra 12.1.4, JDK 21 | Apache-2.0 | not installed |
| Gamepad | Xbox or DualSense | — | needed for flick-it |

- **Hardware.**
  - M3 Ultra / 256 GB is ample for RAM.
  - GPU: ARK + SK8 at once is the risk to measure.
  - Disk: ~300 GB, made up of ASE 166 + ModKit 60–100 + Skate ~20 + BO1 ~15 + tools ~30.
- **Rollback.**
  - Every component lives in its own new CrossOver bottle. A bottle is one directory: archive or
    delete it to undo. The existing bottles are never touched.
  - Copy ARK saves before every run.
  - Native seam is opt-in by file presence: delete the DLL or plugin to return to vanilla.
  - Git tag per milestone.
  - Nothing installed system-wide.
  - Versions pinned as above.
