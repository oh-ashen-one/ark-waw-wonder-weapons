"""WaW first-person viewmodels (arms + gun, own skeleton and xanims) on the Ray Gun and Wunderwaffe.

CoD viewmodels are authored in view space (origin = eye, +X forward), so the WaW viewmodel component is moved
to the player camera every tick. While the gun is out, the ARK body mesh is hidden from its owner
(SetOwnerNoSee) so ARK's arms don't overlap the WaW arms; others still see the third-person character.

Components to add in the editor (once per weapon BP): SkeletalMeshComponent "WaWViewModel"
(mesh SK_<gun>_VM, Only Owner See). The flare-gun static mesh (StaticMesh1) is hidden while it is used.
Anims (imported onto the viewmodel skeleton): A_<gun>_VM_Idle/Fire/Reload/Raise.
"""
import json
import os
import sys

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpc import cls_ref, GLOBAL_TYPES, ACTOR, GS, KSL, SKM, BP, OBJ, Obj, asset, INT, MATH, VEC  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weapons import start_rounds  # noqa: E402  (this graph replaces weapons.py's Weap* graph: same events)

WEAP = "/Script/ShooterGame.ShooterWeapon"
SC = "/Script/Engine.SceneComponent"
PCM = "/Script/Engine.PlayerCameraManager"
PRIM = "/Script/Engine.PrimitiveComponent"
CHAR = "/Script/Engine.Character"
SKMC = "/Script/Engine.SkeletalMeshComponent"
SMC = "/Script/Engine.StaticMeshComponent"
STR = "/Script/Engine.KismetStringLibrary"
SPC = "/Script/ShooterGame.ShooterPlayerController"
ATT_W = Obj("SoundAttenuation'/Game/PrimalEarth/General/DefaultSoundAttenuationHigh.DefaultSoundAttenuationHigh'")


def durations(gun):
    a = json.load(open(f"/Users/YOU/ark-mashup/.work/fbx/{gun}/{gun}_animations.json"))["animations"]
    return {k: round(v["duration_s"], 3) for k, v in a.items()}


def build(prefix, gun, reload_sounds, raise_anim="raise", fire="", last=None, raise_sounds=()):
    """reload_sounds: [(time_s, sound asset name)] from the reload xanim notetracks."""
    bp = BP(real_vars=set())
    dur = durations(gun)

    def comp():
        n = bp.g.get("WaWViewModel", x=0, y=0)
        o = n.out("WaWViewModel")
        o.ptype = OBJ(SKMC)
        return o

    def play(f, name, loop):
        f.call(SKM, "PlayAnimation", target=comp(), NewAnimToPlay=asset("AnimSequence", f"A_{prefix}_VM_{name}"), bLooping=loop)

    # equip: raise, hide ARK body + flare/static meshes for the owner, start following the camera
    e = bp.event("BPStartEquippedNotify", WEAP)
    e0, e = e.seq(2)
    start_rounds(bp, e0)
    owner = bp.pure(WEAP, "GetPawnOwner", self=bp.self_())
    body = bp.g.get("Mesh", cls=CHAR)
    bp.g.link(owner, body.inp("self"))
    body.inp("self").ptype = OBJ(CHAR)
    body.out("Mesh").ptype = OBJ(SKMC)
    e.call(PRIM, "SetOwnerNoSee", target=body.out("Mesh"), bNewOwnerNoSee=True)
    for sm in ("Mesh1P", "StaticMesh1"):   # ARK flare-gun FPV arms + the old stand-in static gun
        n = bp.g.get(sm, x=0, y=0)
        n.out(sm).ptype = OBJ(SC)
        e.call(SC, "SetVisibility", target=n.out(sm), bNewVisibility=False, bPropagateToChildren=False)
    # ARK's native equip runs after this event and makes the 1P meshes visible again, so the hide above doesn't
    # stick (owner saw the old static gun overlapping the WaW viewmodel, 2026-10-12). Clear the old 1P static gun's
    # mesh outright, and keep the third-person one (StaticMesh2, for other players) out of the owner's view.
    sm1 = bp.g.get("StaticMesh1", x=0, y=0)
    sm1.out("StaticMesh1").ptype = OBJ(SMC)
    e.call(SMC, "SetStaticMesh", target=sm1.out("StaticMesh1"), NewMesh=None)
    sm2 = bp.g.get("StaticMesh2", x=0, y=0)
    sm2.out("StaticMesh2").ptype = OBJ(PRIM)
    e.call(PRIM, "SetOwnerNoSee", target=sm2.out("StaticMesh2"), bNewOwnerNoSee=True)
    e.call(PRIM, "SetOnlyOwnerSee", target=comp(), bNewOnlyOwnerSee=True)
    # follow the camera from the first frame: until Tick moves it, the component sits in Mesh1P's socket frame
    # (sideways, lower right). ARK only calls this event when the weapon default bUseBPStartEquippedNotify is on.
    e.set("Equipped", True, "(PinCategory=\"bool\")")
    play(e, "Raise", False)
    t0 = 0.0
    for t, snd in raise_sounds:
        e.delay(round(t - t0, 3))
        t0 = t
        e.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", snd), AttenuationSettings=ATT_W,
               Location=bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_()))
    e.delay(round(max(0.05, dur[raise_anim] - t0), 3))
    e.callself("BackToIdle")

    i = bp.custom("BackToIdle")
    play(i, "Idle", True)

    # fire
    f = bp.event("BPFiredWeapon", WEAP)
    f0, f = f.seq(2)
    start_rounds(bp, f0)
    here = bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())
    if last:
        empty = bp.m("LessEqual_IntInt", A=bp.pure(WEAP, "GetCurrentAmmoInClip", self=bp.self_()), B=0)
        lst, nrm = f.branch(empty)
        lst.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", last), Location=here, AttenuationSettings=ATT_W)
        lst.callself("WaWFireAnim")
        nrm.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", fire), Location=here, AttenuationSettings=ATT_W)
        nrm.callself("WaWFireAnim")
    else:
        f.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", fire), Location=here, AttenuationSettings=ATT_W)
        f.callself("WaWFireAnim")
    f = bp.custom("WaWFireAnim")
    # reload start: ShooterWeapon.bIsReloading is not Blueprint-visible and no event fires when a reload starts, so
    # the WaW reload plays when a shot empties the clip (ARK then auto-reloads). Manual reloads with ammo left: TODO
    # via a BPRequestReload override.
    empty2, notempty = f.branch(bp.m("LessEqual_IntInt", A=bp.pure(WEAP, "GetCurrentAmmoInClip", self=bp.self_()), B=0))
    empty2.callself("WaWReload")
    play(notempty, "Fire", False)
    notempty.call(KSL, "RetriggerableDelay", Duration=dur["fire"])
    notempty.callself("BackToIdle")

    # reload (called from the BPRequestReload override in the editor; see BUILD-QUEUE)
    r = bp.custom("WaWReload")
    play(r, "Reload", False)
    t0 = 0.0
    for t, s in reload_sounds:
        r.delay(round(t - t0, 3))
        t0 = t
        r.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", s), AttenuationSettings=ATT_W,
               Location=bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_()))
    r.delay(round(max(0.05, dur["reload"] - t0), 3))
    r.callself("BackToIdle")

    # follow the camera (view-space model)
    tk = bp.event("ReceiveTick", ACTOR)
    if os.environ.get("VMDEBUG"):
        # where the viewmodel really is at render time, in camera space (tick runs before the camera update, so
        # this is last frame's camera against wherever the attach parent left the component)
        dbg, tk = tk.seq(2)
        dbg.set("DbgN", bp.m("Add_IntInt", A=bp.var("DbgN", INT), B=1), INT)
        show, _ = dbg.branch(bp.m("EqualEqual_IntInt", A=bp.m("Percent_IntInt", A=bp.var("DbgN"), B=60), B=0))
        c0 = bp.pure(GS, "GetPlayerCameraManager", PlayerIndex=0)
        cl, cr = bp.pure(PCM, "GetCameraLocation", self=c0), bp.pure(PCM, "GetCameraRotation", self=c0)

        def camspace(v):
            u = bp.m("LessLess_VectorRotator", A=bp.m("Subtract_VectorVector", A=v, B=cl), B=cr)
            u.ptype = VEC
            return bp.pure(STR, "Conv_VectorToString", InVec=u)
        txt = bp.pure(STR, "Concat_StrStr", A="vm eq ", B=bp.pure(STR, "Concat_StrStr",
              A=bp.pure(STR, "Conv_BoolToString", InBool=bp.var("Equipped")), B=bp.pure(STR, "Concat_StrStr",
              A=" org ", B=bp.pure(STR, "Concat_StrStr", A=camspace(bp.pure(SC, "K2_GetComponentLocation", self=comp())),
              B=bp.pure(STR, "Concat_StrStr", A=" weap ", B=camspace(bp.pure(SC, "GetSocketLocation", self=comp(),
              InSocketName="tag_weapon")))))))
        pc = bp.pure(GS, "GetPlayerController", PlayerIndex=0)
        ok, _, spc = show.cast(SPC, pc)
        ok.call(SPC, "ClientServerNotification", target=spc, MessageText=txt, MessageColor="(R=0.0,G=0.8,B=0.0,A=1.0)",
                DisplayScale=1.0, DisplayTime=1.5)
    on, _ = tk.branch(bp.var("Equipped"))
    cam = bp.pure(GS, "GetPlayerCameraManager", PlayerIndex=0)
    on.call(SC, "SetWorldLocationAndRotation", target=comp(),
            NewLocation=bp.pure(PCM, "GetCameraLocation", self=cam), NewRotation=bp.pure(PCM, "GetCameraRotation", self=cam),
            bSweep=False)

    # unequip / destroyed: give the ARK body back to the owner
    d = bp.event("ReceiveDestroyed", ACTOR)
    body2 = bp.g.get("Mesh", cls=CHAR)
    bp.g.link(bp.pure(WEAP, "GetPawnOwner", self=bp.self_()), body2.inp("self"))
    body2.inp("self").ptype = OBJ(CHAR)
    body2.out("Mesh").ptype = OBJ(SKMC)
    d.call(PRIM, "SetOwnerNoSee", target=body2.out("Mesh"), bNewOwnerNoSee=False)
    return bp


if __name__ == "__main__":
    out = "/Users/YOU/ark-mashup/.work/graphs"
    os.makedirs(out, exist_ok=True)
    ray = [(0.4, "S_RayGun_ReloadOpen"), (1.3, "S_RayGun_BatteryOut"), (2.367, "S_RayGun_BatteryIn"), (3.167, "S_RayGun_ReloadClose")]
    waffe = [(0.8, "S_Waffe_SwitchOff"), (1.667, "S_Waffe_HandlePull"), (3.033, "S_Waffe_ClipIn"),
             (3.9, "S_Waffe_HandleRelease"), (4.967, "S_Waffe_SwitchOn")]
    for name, b in [("WeapRayGun_VM", build("RayGun", "ray_gun", ray, fire="S_RayGun_Fire")),
                    ("WeapWunderwaffe_VM", build("Waffe", "tesla", waffe, raise_anim="first_raise", fire="S_Waffe_Fire",
                                                       last="S_Waffe_FireLast",
                                                       raise_sounds=[(0.767, "S_Waffe_Raise"), (1.233, "S_Waffe_SwitchOn")]))]:
        open(f"{out}/{name}.txt", "w").write(b.text())
        print(name, len(b.g.nodes))
