"""WaW sounds on the Ray Gun and Wunderwaffe (weapon fire, projectile loop, impact), using the weapon's
BPFiredWeapon / BPStartEquippedNotify hooks and the projectiles' BeginPlay/Destroyed events.
Sound aliases (from the owner's zones): wpn_ray_fire_plr -> wpn_ray_mn, wpn_ray_exp, wpn_ray_loop;
wpn_tesla_fire_plr -> fire_mn_f, ..._last -> fire_mn_lst, wpn_tesla_proj_loop, wpn_tesla_proj_impact."""
import os
import sys

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpc import cls_ref, GLOBAL_TYPES, ACTOR, GS, BP, Obj, asset  # noqa: E402

WEAP = "/Script/ShooterGame.ShooterWeapon"
ATT_W = Obj("SoundAttenuation'/Game/PrimalEarth/General/DefaultSoundAttenuationHigh.DefaultSoundAttenuationHigh'")
ATT_X = Obj("SoundAttenuation'/Game/PrimalEarth/General/DefaultSoundAttenuation_Explosion.DefaultSoundAttenuation_Explosion'")


def here(bp):
    return bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())


MGR = "/Game/Mods/ArkMashup/BP_WaWRoundManager.BP_WaWRoundManager_C"


def start_rounds(bp, flow):
    """WaW rounds start the first time a wonder weapon is equipped (and the manager gets cooked)."""
    from bpc import cls_ref, OBJ, ACTOR
    mg = flow.call(GS, "GetAllActorsOfClass", ActorClass=Obj(cls_ref(MGR)))
    none, _ = flow.branch(bp.m("EqualEqual_IntInt", A=bp.arr("Array_Length", TargetArray=mg.out("OutActors")), B=0))
    xf = bp.m("MakeTransform", Location=bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_()),
              Rotation=bp.m("MakeRot", Pitch=0.0, Yaw=0.0, Roll=0.0), Scale=bp.m("MakeVector", X=1.0, Y=1.0, Z=1.0))
    none.spawn(MGR, xf)


def weapon(fire, last=None, raise_=None):
    bp = BP()
    f = bp.event("BPFiredWeapon", WEAP)
    f0, f = f.seq(2)
    start_rounds(bp, f0)
    if last:
        empty = bp.m("LessEqual_IntInt", A=bp.pure(WEAP, "GetCurrentAmmoInClip", self=bp.self_()), B=0)
        lst, nrm = f.branch(empty)
        lst.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", last), Location=here(bp), AttenuationSettings=ATT_W)
        nrm.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", fire), Location=here(bp), AttenuationSettings=ATT_W)
    else:
        f.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", fire), Location=here(bp), AttenuationSettings=ATT_W)
    e = bp.event("BPStartEquippedNotify", WEAP)
    if raise_:
        e.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", raise_), Location=here(bp), AttenuationSettings=ATT_W)
    start_rounds(bp, e)
    return bp


def projectile(loop, impact):
    bp = BP()
    b = bp.event("ReceiveBeginPlay", ACTOR)
    b.call(GS, "PlaySoundAttached", Sound=asset("SoundWave", loop),
           AttachToComponent=bp.member("RootComponent"), AttenuationSettings=ATT_W, bStopWhenAttachedToDestroyed=True)
    if impact:
        d = bp.event("ReceiveDestroyed", ACTOR)
        d.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", impact), Location=here(bp), AttenuationSettings=ATT_X)
    return bp


if __name__ == "__main__":
    out = "/Users/YOU/ark-mashup/.work/graphs"
    os.makedirs(out, exist_ok=True)
    jobs = {
        "WeapRayGun": weapon("S_RayGun_Fire"),
        "WeapWunderwaffe": weapon("S_Waffe_Fire", last="S_Waffe_FireLast", raise_="S_Waffe_Raise"),
        "ProjRayGun": projectile("S_RayGun_ProjLoop", "S_RayGun_Explode"),
        # ProjWunderwaffe's impact sound is in tesla.py (its ReceiveDestroyed also starts the chain)
        "ProjWunderwaffe_loop": projectile("S_Waffe_ProjLoop", None),
    }
    for name, b in jobs.items():
        open(f"{out}/{name}.txt", "w").write(b.text())
        print(name, len(b.g.nodes))
