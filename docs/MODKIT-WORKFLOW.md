# ASE ModKit: local-only mod workflow (research 2026-10-06; P = local files/DLL strings, C = forum/community)

**Never click "Upload". Never enter Steam credentials. Never create Workshop items.**

Install notes (P):
- Slim install with no `Content/Mods`, `GenericMod` or `TestMapArea`, so the skeleton is built from scratch.
- `BASE_PrimalGameData_BP` references Aberration engrams, which are absent, so expect warnings.
- Wine drives in bottle `ark-modkit`: `Y:` = `/Users/YOU`, `Z:` = `/`.
- Console key in PIE: Tab.

## A. Skeleton (`<ModName>` = `ArkMashup`)
1. Content Browser: create folders `Mods/ArkMashup`. Only `Mods/<ModName>` is cooked.
2. File → New Level, then save as `Mods/ArkMashup/ArkMashup.umap` (the cook needs a map in the mod folder).
3. Child of `PrimalEarth/CoreBlueprints/PrimalGameData_BP`: `PrimalGameData_BP_ArkMashup`. Set
   `ModName` and `ModDescription`. Fallback parent: C++ `PrimalGameData`.
4. Child of `CoreBlueprints/TestGameMode`: `TestGameMode_ArkMashup`.
5. Level → World Settings: Primal Game Data Override = GameData BP, Game Mode Override = test
   GameMode, Force Load Map Name blank. Add a floor, a PlayerStart and a light, then save.

## B. Weapon (Ray Gun from the Tek chain)
6. Children in `Mods/ArkMashup/Weapon`:
   - `PrimalItem_TekRifle` → `PrimalItem_RayGun`
   - `WeapTekRifle` (parent `ShooterWeapon_Projectile`) → `WeapRayGun`
   - `/Game/PrimalEarth/Test/ProjTekRifle` → `ProjRayGun`
7. Item: `Weapon Template` = `WeapRayGun_C`.
8. Weapon: `Ammo Per Clip`, `Time Between Shots`, `Weapon Ammo Item Template`, `Projectile Class`.
   The Tek overheat fields need neutralising.
9. Projectile: `ProjectileComp` Initial/Max Speed. `WeaponConfig`: Direct Damage, Explosion Damage,
   Explosion Radius, Projectile Life, Direct Damage Type.
10. Engram: duplicate `EngramEntry_TekRifle` and set `BluePrintEntry`, then add it to
    `Additional Engram Blueprint Classes` in GameData.
11. PIE test: Tab, then
    `cheat giveitem "Blueprint'/Game/Mods/ArkMashup/Weapon/PrimalItem_RayGun.PrimalItem_RayGun'" 1 0 0`.

## C. Cook, no upload
- **Editor:** toolbar "Steam Upload" (tab `CookAndUploadModsTools`), then:
  1. Refresh, pick the mod.
  2. Maps = exact .umap basename.
  3. Test Mod Output Directory = `Y:\ark-mashup\.work\modtest-out`.
  4. Leave the Steam fields EMPTY.
  5. Save All, then **Cook Game Mod**, then wait for "Job Successful!!".
- **Output (C):** `123456789.mod` and `123456789/` (`mod.info`, `modmeta.info`). If the cooked files
  land only in `<ModName>/`, copy them into `123456789/`.
- **Headless alternative (P strings, untested):**
  `UE4Editor-Cmd.exe "ShooterGame\ShooterGame.uproject" -run=Cook -Map=<m> -CookCultures=en -TargetPlatform=WindowsNoEditor -ModDir=<d> -GameMod -ModGUID=<32hex> -pkgnfo="<root>/PackageInfo.bin" -Output="..."`.
  Then write `mod.info`, `modmeta.info` and `<id>.mod` by hand. The `.mod` layout follows arkmanager:
  1. u32 id, then u32 0
  2. lp-string name, then lp-string `../../../ShooterGame/Content/Mods/<id>`
  3. u32 map count, then the lp-string maps
  4. bytes `33 FF 22 FF 02 00 00 00 01`
  5. modmeta

## D. Install into the client (bottle `Steam`)
- Copy `123456789/` and `123456789.mod` to `.../common/ARK/ShooterGame/Content/Mods/`. There's no ID
  clash today.
- With the game closed, add `ActiveMods=123456789` under `[ServerSettings]` in
  `ShooterGame/Saved/Config/WindowsNoEditor/GameUserSettings.ini`.
- Back up that ini first. Rollback = remove the line and the two Mods entries.
