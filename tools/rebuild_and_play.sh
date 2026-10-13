#!/bin/sh
# Close the ARK Dev Kit editor, cook ArkMashup headlessly, install into the ARK client, launch ARK with the mod.
set -u
CX="$HOME/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/bin"; W=/Users/YOU/ark-mashup/.work
stop_procs() { # $1 = grep pattern (bracketed), SIGTERM and wait up to 60 s
  ps -axo pid,command | grep -E "$1" | awk '{print $1}' | while read p; do kill -TERM "$p" 2>/dev/null; done
  i=0; while ps -axo command | grep -q -E "$1" && [ $i -lt 30 ]; do sleep 2; i=$((i+1)); done; }
"$CX/wine" --bottle ark-modkit taskkill /IM UE4Editor.exe >/dev/null 2>&1; sleep 20; stop_procs 'Z:.*[U]E4Editor.exe'
stop_procs 'C:.*[S]hooterGame.exe'
rm -rf "$W/modtest-out/ArkMashup" "$W/modtest-out/123456789"
R="$W/runs/cook-$(date +%H%M%S)"; mkdir -p "$R"
"$CX/wine" --bottle ark-modkit --workdir "$HOME/ARKDevKit/Engine/Binaries/Win64" 'Z:\Users\YOU\ARKDevKit\Engine\Binaries\Win64\UE4Editor-Cmd.exe' 'Z:\Users\YOU\ARKDevKit\Projects\ShooterGame\ShooterGame.uproject' -run=Cook -Map=ArkMashup -CookCultures=en -TargetPlatform=WindowsNoEditor -ModDir=123456789 -GameMod -ModGUID=62EB98BF421FCFFACF77DA8BF8A076B1 '-pkgnfo=Z:/Users/YOU/ARKDevKit/PackageInfo.bin' -OriginalModDir=ArkMashup '-Output=Y:/ark-mashup/.work/modtest-out' -unattended -NoCrashReports -stdout -FullStdOutLogOutput > "$R/cook.log" 2>&1
F=$(ls -t "$HOME/ARKDevKit/Projects/ShooterGame/Saved/Logs/"ShooterGame*.log | head -1)
grep -a -q "Critical error" "$F" && { echo "COOK CRASHED"; exit 1; }
grep -a -E "LogInit:Display: (Success|Failure)" "$F" | tail -1
python3 -I /Users/YOU/ark-mashup/tools/ark_mod_install.py install "$W/modtest-out/ArkMashup" --id 123456789 --name ArkMashup --map ArkMashup | tail -1
[ -n "${NO_PLAY:-}" ] || /Users/YOU/ark-mashup/tools/play_ark_mod.sh | head -1
