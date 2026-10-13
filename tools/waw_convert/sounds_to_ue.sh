#!/bin/sh
# Convert the WaW sounds used by the mod (owner's copy, extracted to .work) to 16-bit PCM WAV for UE4 import.
# Output: .work/ue_import/sounds/<UEName>.wav  (never committed)
set -e
W=/Users/YOU/ark-mashup/.work; F=$W/sounds/localized_nazi_zombie_factory/sfx; R=$W/assets/nazi_zombie_factory/sound/sfx/weapon/ray_gun
O=$W/ue_import/sounds; mkdir -p "$O"
c() { ffmpeg -v error -y -i "$1" -ac 1 -ar 44100 -c:a pcm_s16le "$O/$2.wav"; }
# Ray Gun
c $R/wpn_ray_mn.wav S_RayGun_Fire; c $R/wpn_ray_exp.wav S_RayGun_Explode; c $R/wpn_ray_loop.wav S_RayGun_ProjLoop
c $R/wpn_ray_reload_open.wav S_RayGun_ReloadOpen; c $R/wpn_ray_reload_battery_out.wav S_RayGun_BatteryOut
c $R/wpn_ray_reload_battery.wav S_RayGun_BatteryIn; c $R/wpn_ray_reload_close.wav S_RayGun_ReloadClose
# Wunderwaffe DG-2
T=$F/weapon/tesla
c $T/new/wpn_tesla_fire_mn_f.wav S_Waffe_Fire; c $T/new/wpn_tesla_fire_mn_lst.wav S_Waffe_FireLast
c $T/projectile/proj_loop.wav S_Waffe_ProjLoop; c $T/projectile/proj_impact.wav S_Waffe_Impact
c $T/bounce/bounce_00.wav S_Waffe_Bounce0; c $T/bounce/bounce_01.wav S_Waffe_Bounce1
c $F/levels/zombie/maps/asylum/traps/zom_arc/zom_arc_00.wav S_Waffe_ArcSizzle
c $T/reload/gr_tesla_start.wav S_Waffe_Raise; c $T/reload/tesla_switch_flip_off.wav S_Waffe_SwitchOff
c $T/reload/tesla_handle_pullback.wav S_Waffe_HandlePull; c $T/reload/tesla_clip_in.wav S_Waffe_ClipIn
c $T/reload/tesla_handle_release.wav S_Waffe_HandleRelease; c $T/reload/tesla_switch_flip_on.wav S_Waffe_SwitchOn
c $T/wpn_tesla_idle_d.wav S_Waffe_Idle
# Zombie vocals (all variants per category)
V=$F/levels/zombie/new_zombie_vox
for cat in Ambient:ambient Attack:attack Behind:behind Crawl:crawl Death:death Elec:elec Sprint:n/sprint; do
  name=${cat%%:*}; dir=${cat#*:}; n=0
  for f in $(ls $V/$dir/*.wav | sort | head -4); do c "$f" "S_Zmb_${name}_$n"; n=$((n+1)); done
done
ls "$O" | wc -l
# Zombie footsteps (step_zombie -> sfx/levels/zombie/steps) and melee whoosh (attack_whoosh -> sfx/levels/zombie/whoosh)
n=0; for f in $(ls $F/levels/zombie/steps/*.wav | sort | head -4); do c "$f" "S_Zmb_Step_$n"; n=$((n+1)); done
n=0; for f in $(ls $F/levels/zombie/whoosh/*.wav | sort | head -3); do c "$f" "S_Zmb_Whoosh_$n"; n=$((n+1)); done
ls "$O" | wc -l
