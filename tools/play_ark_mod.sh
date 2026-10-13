#!/bin/sh
# Launch ARK: Survival Evolved (CrossOver bottle "Steam") offline, no BattlEye, on The Island with the ArkMashup mod (id 123456789).
# Needs: the mod installed (tools/ark_mod_install.py install ...). Starts the bottle's Steam silently if it isn't running.
CX="$HOME/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin"
# ARK writes [WindowsApplication.Accessibility] into Saved Engine.ini on exit; under Wine the next start then
# crashes in FConfigCacheIni::Flush (heap fault, seen 2026-10-08 x3). Strip that section before every launch.
ENG="$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/ARK/ShooterGame/Saved/Config/WindowsNoEditor/Engine.ini"
[ -f "$ENG" ] && python3 -I - "$ENG" <<'EOF'
import re, sys
p = sys.argv[1]; s = open(p, newline='').read()
t = re.sub(r'\[WindowsApplication\.Accessibility\]\r?\n(?:[^\[\r\n][^\r\n]*\r?\n)*(?:\r?\n)*', '', s)
if t != s: open(p, 'w', newline='').write(t); print("stripped Accessibility section from Engine.ini")
EOF
if ! pgrep -f "[s]teamwebhelper" >/dev/null; then
  nohup "$CX/wine" --bottle Steam 'C:\Program Files (x86)\Steam\steam.exe' -silent >/dev/null 2>&1 &
  echo "starting Steam..."; sleep 40
fi
cd "$HOME/Library/Application Support/CrossOver/Bottles/Steam/drive_c/Program Files (x86)/Steam/steamapps/common/ARK/ShooterGame/Binaries/Win64" || exit 1
nohup "$CX/wine" --bottle Steam --workdir "$PWD" 'C:\Program Files (x86)\Steam\steamapps\common\ARK\ShooterGame\Binaries\Win64\ShooterGame.exe' \
  'TheIsland?GameModIds=123456789' -NoBattlEye -windowed -ResX=${ARK_RESX:-1600} -ResY=${ARK_RESY:-900} -nosplash -log >/dev/null 2>&1 &
echo "ARK launching (first load ~10 min). In game: Tab, then:"
echo "  cheat giveitem \"Blueprint'/Game/Mods/ArkMashup/PrimalItem_RayGun.PrimalItem_RayGun'\" 1 0 0"
echo "  cheat giveitem \"Blueprint'/Game/Mods/ArkMashup/PrimalItemAmmo_RayGun.PrimalItemAmmo_RayGun'\" 160 0 0"
echo "  cheat giveitem \"Blueprint'/Game/Mods/ArkMashup/PrimalItem_Wunderwaffe.PrimalItem_Wunderwaffe'\" 1 0 0"
echo "  cheat giveitem \"Blueprint'/Game/Mods/ArkMashup/PrimalItemAmmo_Wunderwaffe.PrimalItemAmmo_Wunderwaffe'\" 200 0 0"
echo "  cheat god                     (once; it toggles. The opening horde of dinosaurs kills you in seconds otherwise)"
echo "  cheat settimeofday 12:00      (daylight; The Island save may load at night)"
echo "Firing or equipping either gun starts the rounds: an opening horde of 24 zombies + 16 dinosaurs, then zombies plus 2 + 2 x round dinosaurs each round."
