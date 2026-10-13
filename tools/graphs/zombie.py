"""BP_WaWZombie (parent: Character) and BP_WaWRoundManager (parent: Actor): Der Riese rules ported from
maps/_zombiemode.gsc, _zombiemode_spawner.gsc and nazi_zombie_factory.gsc (see docs/ZOMBIE-DESIGN.md).

Animation is driven like WaW: one clip at a time (SkeletalMeshComponent.PlayAnimation, single-node mode).
Locomotion speed = the clip's measured root-motion speed (converter report), so feet don't slide.
Timings (rise, melee hit frames, vocal notetracks, deaths) come from .work/ue_import/zombie/anim_table.json.
"""
import json
import os
import sys

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpc import (T as TP, DINO, cls_ref, GLOBAL_TYPES, ACTOR, BOOL, CHAR, CMC, FLOAT, GS, INT, KSL, MATH, PAWN, SKM, BP, OBJ, Obj, VEC,  # noqa
                 asset, bpclass)

U = 2.54
STR = "/Script/Engine.KismetStringLibrary"
T = json.load(open("/Users/YOU/ark-mashup/.work/ue_import/zombie/anim_table.json"))
ZOMBIE = bpclass("BP_WaWZombie")
MGR = bpclass("BP_WaWRoundManager")
SHOOTER = "/Script/ShooterGame.ShooterCharacter"
CAPSULE = "/Script/Engine.CapsuleComponent"
SC = "/Script/Engine.SceneComponent"
ATT_ZMB = Obj("SoundAttenuation'/Game/PrimalEarth/General/DefaultSoundAttenuationMedium.DefaultSoundAttenuationMedium'")
LOCO = ["Walk1", "Walk2", "Walk3", "Walk4", "Walk5", "Walk6", "Walk7", "Run1", "Run2", "Run3", "Run4", "Run5",
        "Sprint1", "Sprint2"]
RISE = ["RiseWalk", "RiseRun", "RiseSprint"]
MELEE = ["Melee0", "Melee1", "Melee2", "Melee3", "Melee2", "Melee5", "Melee6"]   # _zombie_melee[0..6]
DEATH = ["Death0", "Death1", "Death2", "Death3"]
TESLA = ["Tesla0", "Tesla1", "Tesla2", "Tesla3", "Tesla4"]
MELEE_RANGE = 64 * U
# Showcase spawns (owner request 2026-10-12, not WaW rules): an opening horde of zombies and wild ARK dinosaurs when
# the rounds start, then extra dinosaurs every round alongside the WaW zombie count.
HORDE_ZOMBIES = 24
HORDE_DINOS = 16
DINOS = [("Rex", "Rex"), ("Raptor", "Raptor"), ("Raptor", "Raptor"), ("Carno", "Carno"), ("Allosaurus", "Allo"),
         ("Spino", "Spino"), ("Trike", "Trike"), ("Stego", "Stego"), ("Ankylo", "Ankylo"), ("Saber", "Saber"),
         ("Direwolf", "Direwolf"), ("Dilo", "Dilo"), ("Sauropod", "Sauropod"), ("Giganotosaurus", "Gigant")]


def dino_class(folder, name):
    return f"/Game/PrimalEarth/Dinos/{folder}/{name}_Character_BP.{name}_Character_BP_C"


def ground_point(bp, flow, pl, var, dmin, dmax):
    """Random point dmin..dmax from the player, traced down onto the ground within 10 m of the player's height.
    Returns (grounded_flow, miss_flow, impact_point)."""
    ang = bp.m("RandomFloatInRange", Min=0.0, Max=6.2831853)
    d = bp.m("RandomFloatInRange", Min=dmin, Max=dmax)
    pv = bp.purenode(MATH, "BreakVector", InVec=bp.pure(ACTOR, "K2_GetActorLocation", self=pl))
    px = bp.m("Add_FloatFloat", A=pv.out("X"), B=bp.m("Multiply_FloatFloat", A=d, B=bp.m("Cos", A=ang)))
    py = bp.m("Add_FloatFloat", A=pv.out("Y"), B=bp.m("Multiply_FloatFloat", A=d, B=bp.m("Sin", A=ang)))
    flow.set(var, bp.m("MakeVector", X=px, Y=py, Z=pv.out("Z")), VEC)
    xy = bp.purenode(MATH, "BreakVector", InVec=bp.var(var))
    top = bp.m("MakeVector", X=xy.out("X"), Y=xy.out("Y"), Z=bp.m("Add_FloatFloat", A=xy.out("Z"), B=5000.0))
    bot = bp.m("MakeVector", X=xy.out("X"), Y=xy.out("Y"), Z=bp.m("Subtract_FloatFloat", A=xy.out("Z"), B=5000.0))
    tr = flow.call(KSL, "LineTraceSingle_DEPRECATED", Start=top, End=bot, TraceChannel="ECC_Visibility", bTraceComplex=False, bIgnoreSelf=True)
    hitp = bp.purenode(GS, "BreakHitResult", Hit=tr.out("OutHit")).out("ImpactPoint")
    hz = bp.purenode(MATH, "BreakVector", InVec=hitp).out("Z")
    near_z = bp.m("LessEqual_FloatFloat", A=bp.m("Abs", A=bp.m("Subtract_FloatFloat", A=hz, B=pv.out("Z"))), B=1000.0)
    grounded, miss = flow.branch(bp.m("BooleanAND", A=tr.out("ReturnValue"), B=near_z))
    return grounded, miss, hitp


def spawn_class(bp, flow, cls_pin, xfm):
    """SpawnActorFromClass with the class wired from a pin (a random pick), so ReturnValue is a plain Actor."""
    x, y = bp._xy()
    n = bp.g.node("K2Node_SpawnActorFromClass", [], x, y)
    n.inp("Class").ptype = TP("class", cls_ref(ACTOR))
    n.inp("SpawnTransform").ptype = TP("struct", "ScriptStruct'/Script/CoreUObject.Object:Transform'")
    xfm.ptype = n.inp("SpawnTransform").ptype
    n.out("ReturnValue").ptype = OBJ(ACTOR)
    bp.g.link(cls_pin, n.inp("Class"))
    bp.g.link(xfm, n.inp("SpawnTransform"))
    bp._apply(n, {"SpawnEvenIfColliding": True})
    return flow._exec(n)
PLAYER_HIT = 60.0


def anim(name):
    return asset("AnimSequence", f"A_Zmb_{name}")


def snd(bp, kind, n=4):
    """Random variant of S_Zmb_<kind>_0..n-1 (WaW aliases pick a random file)."""
    arr = bp.make_array([asset("SoundWave", f"S_Zmb_{kind}_{i}") for i in range(n)])
    return bp.arr("Array_Get", out="Item", TargetArray=arr, Index=bp.m("RandomIntegerInRange", Min=0, Max=n - 1))


def play(flow, bp, sound, at=None):
    loc = at if at is not None else bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())
    flow.call(GS, "PlaySoundAtLocation", Sound=sound, Location=loc, AttenuationSettings=ATT_ZMB)


def fl_arr(bp, vals):
    return bp.make_array([float(v) for v in vals])


def dist(bp, a, b):
    """|a - b| (GetDistanceTo is an exec node in UE4.5, so it can't be used as a pure value)."""
    return bp.m("VSize", A=bp.m("Subtract_VectorVector", A=bp.pure(ACTOR, "K2_GetActorLocation", self=a),
                                B=bp.pure(ACTOR, "K2_GetActorLocation", self=b)))


def mesh(bp):
    return bp.member("Mesh")


SPC = "/Script/ShooterGame.ShooterPlayerController"


def say(bp, flow, text, color="(R=0.6,G=0.0,B=0.0,A=1.0)", secs=5.0, scale=1.6):
    """On-screen message via ARK's own HUD notification (PrintString is stripped in shipping ARK)."""
    pc = bp.pure(GS, "GetPlayerController", PlayerIndex=0)
    ok, _, spc = flow.cast(SPC, pc)
    ok.call(SPC, "ClientServerNotification", target=spc, MessageText=text, MessageColor=color,
            DisplayScale=scale, DisplayTime=secs)
    return ok


def build_zombie():
    bp = BP(real_vars=set())
    MG = OBJ(MGR)
    # ---------------- Init (called by the round manager right after spawning) ----------------
    f = bp.custom("Init", [("ManagerIn", MG), ("HealthIn", FLOAT), ("SpeedIn", INT)])
    ev = f
    f.set("Manager", ev.p("ManagerIn"), MG)
    f.set("Health", ev.p("HealthIn"), FLOAT)
    f.set("Dead", False, BOOL)
    f.set("Busy", True, BOOL)
    f.call(SKM, "SetSkeletalMesh", target=mesh(bp), NewMesh=asset("SkeletalMesh", "SK_WaWZombie"))
    f.call(SC, "SetRelativeLocationAndRotation", target=mesh(bp),
           NewLocation=bp.m("MakeVector", X=0.0, Y=0.0, Z=-91.44), NewRotation=bp.m("MakeRot", Pitch=0.0, Yaw=0.0, Roll=0.0))
    f.call(CAPSULE, "SetCapsuleSize", target=bp.member("CapsuleComponent"), InRadius=16 * U, InHalfHeight=36 * U)
    # ARK projectiles collide with ARK's own pawn/mesh object channels; a plain Character capsule ignores them, so the
    # Ray Gun's projectile flew through (2026-10-10 test: no damage). Block everything except Visibility
    # (as UE's Pawn preset; traces such as the tesla line-of-sight check must still pass zombies).
    prim = "/Script/Engine.PrimitiveComponent"
    f.call(prim, "SetCollisionResponseToAllChannels", target=bp.member("CapsuleComponent"), NewResponse="ECR_Block")
    f.call(prim, "SetCollisionResponseToChannel", target=bp.member("CapsuleComponent"), Channel="ECC_Visibility",
           NewResponse="ECR_Ignore")       # (ARK renamed ECC_Camera; it is not a valid enumerant there)
    f.call(PAWN, "SpawnDefaultController")
    noctl, _ = f.branch(bp.m("Not_PreBool", A=bp.pure(KSL, "IsValid", Object=bp.member("Controller"))))
    aic = noctl.spawn("/Script/AIModule.AIController", bp.m("MakeTransform", Location=bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_()),
                      Rotation=bp.m("MakeRot", Pitch=0.0, Yaw=0.0, Roll=0.0), Scale=bp.m("MakeVector", X=1.0, Y=1.0, Z=1.0)))
    noctl.call("/Script/Engine.Controller", "Possess", target=aic.out("ReturnValue"), inPawn=bp.self_())
    noctl.callself("PickClass")
    _.callself("PickClass")
    f = bp.custom("PickClass")
    # speed class (sp L224-241): rand = randomintrange(speed, speed+35)  [max exclusive]
    r = bp.m("RandomIntegerInRange", Min=ev.p("SpeedIn"), Max=bp.m("Add_IntInt", A=ev.p("SpeedIn"), B=34))
    f.set("Roll", r, INT)
    walk, notwalk = f.branch(bp.m("LessEqual_IntInt", A=bp.var("Roll"), B=35))
    walk.set("MoveClass", 0, INT)
    walk.set("LocoIdx", bp.m("RandomIntegerInRange", Min=0, Max=6), INT)        # walk1-7
    walk.callself("Rise")
    run, sprint = notwalk.branch(bp.m("LessEqual_IntInt", A=bp.var("Roll"), B=70))
    run.set("MoveClass", 1)
    run.set("LocoIdx", bp.m("RandomIntegerInRange", Min=7, Max=11))           # run1-5
    run.callself("Rise")
    sprint.set("MoveClass", 2)
    sprint.set("LocoIdx", bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([12, 12, 13]),
                                 Index=bp.m("RandomIntegerInRange", Min=0, Max=2)))   # sprint1-3
    sprint.callself("Rise")

    # ---------------- standalone (console-spawned) zombies start themselves ----------------
    bpl = bp.event("ReceiveBeginPlay", ACTOR)
    bpl.delay(0.3)
    solo, _ = bpl.branch(bp.m("Not_PreBool", A=bp.pure(KSL, "IsValid", Object=bp.var("Manager"))))
    solo.callself("Init", HealthIn=150.0, SpeedIn=1)

    # ---------------- Rise from the ground (sp L3313, L3570) ----------------
    r = bp.custom("Rise")
    r.set("LastPos", bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_()), VEC)
    r.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="Think", Time=0.1, bLooping=True)
    r.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="VoxTick", Time=1.0, bLooping=True)
    r.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="StuckCheck", Time=30.0, bLooping=True)
    rise_anim = bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([anim(n) for n in RISE]), Index=bp.var("MoveClass"))
    r.call(SKM, "PlayAnimation", target=mesh(bp), NewAnimToPlay=rise_anim, bLooping=False)
    r.delay(bp.arr("Array_Get", out="Item", TargetArray=fl_arr(bp, [T[n]["dur"] for n in RISE]), Index=bp.var("MoveClass")))
    r.set("Busy", False)
    r.callself("StartLoco")

    # ---------------- Locomotion ----------------
    s = bp.custom("StartLoco")
    alive, _ = s.branch(bp.m("Not_PreBool", A=bp.var("Dead")))
    idx = bp.var("LocoIdx")
    alive.call(SKM, "PlayAnimation", target=mesh(bp), bLooping=True,
               NewAnimToPlay=bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([anim(n) for n in LOCO]), Index=idx))
    alive.set("CurSpeed", bp.arr("Array_Get", out="Item", TargetArray=fl_arr(bp, [T[n]["speed"] for n in LOCO]), Index=idx), FLOAT)
    durs = bp.arr("Array_Get", out="Item", TargetArray=fl_arr(bp, [T[n]["dur"] for n in LOCO]), Index=idx)
    nsteps = [max(1, len(T[n]["steps"])) for n in LOCO]
    alive.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="LocoVocal", Time=durs, bLooping=True)
    alive.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="Step", bLooping=True,
               Time=bp.arr("Array_Get", out="Item", TargetArray=fl_arr(bp, [T[n]["dur"] / k for n, k in zip(LOCO, nsteps)]), Index=idx))

    # amb_vocals / sprint_vocals notetrack, once per cycle
    v = bp.custom("LocoVocal")
    kind = [1 if any(x[0] == "amb_vocals" for x in T[n]["vocal"]) else 2 if any(x[0] == "sprint_vocals" for x in T[n]["vocal"]) else 0 for n in LOCO]
    k = bp.arr("Array_Get", out="Item", TargetArray=bp.make_array(kind), Index=bp.var("LocoIdx"))
    can = bp.m("BooleanAND", A=bp.m("Not_PreBool", A=bp.var("Dead")), B=bp.m("Not_PreBool", A=bp.var("Busy")))
    go, _ = v.branch(can)
    amb, other = go.branch(bp.m("EqualEqual_IntInt", A=k, B=1))
    play(amb, bp, snd(bp, "Ambient"))
    spr, _ = other.branch(bp.m("EqualEqual_IntInt", A=k, B=2))
    play(spr, bp, snd(bp, "Sprint"))

    st = bp.custom("Step")
    go, _ = st.branch(can)
    play(go, bp, snd(bp, "Step"))

    # ---------------- Think: find_flesh (sp L2914-3001) ----------------
    t = bp.custom("Think")
    go, _ = t.branch(can)
    now = bp.pure(GS, "GetRealTimeSeconds")
    tgt = bp.var("Target", OBJ(CHAR))
    tgt_ok = bp.m("BooleanAND", A=bp.pure(KSL, "IsValid", Object=tgt), B=bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=tgt)))
    repick = bp.m("BooleanOR", A=bp.m("GreaterEqual_FloatFloat", A=now, B=bp.var("NextPick", FLOAT)), B=bp.m("Not_PreBool", A=tgt_ok))
    pick, keep = go.branch(repick)
    pick.set("BestD", 1.0e12, FLOAT)
    players = pick.call(GS, "GetAllActorsOfClass", ActorClass=Obj(cls_ref(SHOOTER)))
    lb, pel, _ = pick.foreach(players.out("OutActors"))
    cok, _, pch = lb.cast(CHAR, pel)
    d = dist(bp, bp.self_(), pch)
    better, _ = cok.branch(bp.m("BooleanAND", A=bp.m("Less_FloatFloat", A=d, B=bp.var("BestD")),
                                B=bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=pch))))
    better.set("BestD", d)
    better.set("Target", pch)
    pick.set("NextPick", bp.m("Add_FloatFloat", A=now, B=bp.m("RandomFloatInRange", Min=1.0, Max=3.0)))   # sp L3001
    pick.callself("Chase")

    keep.callself("Chase")

    c = bp.custom("Chase")
    tgt = bp.var("Target")
    has, _ = c.branch(bp.pure(KSL, "IsValid", Object=tgt))
    me_loc = bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())
    t_loc = bp.pure(ACTOR, "K2_GetActorLocation", self=tgt)
    look = bp.m("FindLookAtRotation", Start=me_loc, Target=t_loc)
    yaw = bp.purenode(MATH, "BreakRot", InRot=look).out("Yaw")
    has.call(ACTOR, "SetActorRotation", NewRotation=bp.m("MakeRot", Pitch=0.0, Yaw=yaw, Roll=0.0))
    near, far = has.branch(bp.m("LessEqual_FloatFloat", A=dist(bp, bp.self_(), tgt), B=MELEE_RANGE))
    near.callself("Attack")
    dv = bp.m("Subtract_VectorVector", A=t_loc, B=me_loc)
    bv = bp.purenode(MATH, "BreakVector", InVec=dv)
    flat = bp.m("Normal", A=bp.m("MakeVector", X=bv.out("X"), Y=bv.out("Y"), Z=0.0))
    # WaW AI travel = the anim's root motion: step CurSpeed * tick toward the target, snapped to the ground below
    step = bp.m("Multiply_VectorFloat", A=flat, B=bp.m("Multiply_FloatFloat", A=bp.var("CurSpeed"), B=0.1))
    nxt = bp.m("Add_VectorVector", A=me_loc, B=step)
    nv = bp.purenode(MATH, "BreakVector", InVec=nxt)
    top = bp.m("MakeVector", X=nv.out("X"), Y=nv.out("Y"), Z=bp.m("Add_FloatFloat", A=nv.out("Z"), B=60.0))
    bot = bp.m("MakeVector", X=nv.out("X"), Y=nv.out("Y"), Z=bp.m("Subtract_FloatFloat", A=nv.out("Z"), B=250.0))
    tr = far.call(KSL, "LineTraceSingle_DEPRECATED", Start=top, End=bot, TraceChannel="ECC_Visibility", bTraceComplex=False,
                  bIgnoreSelf=True, ActorsToIgnore=bp.make_array([bp.self_(), tgt]))
    gp = bp.purenode(GS, "BreakHitResult", Hit=tr.out("OutHit")).out("ImpactPoint")
    gz = bp.purenode(MATH, "BreakVector", InVec=gp).out("Z")
    onground, nofloor = far.branch(tr.out("ReturnValue"))
    onground.call(ACTOR, "K2_SetActorLocation", NewLocation=bp.m("MakeVector", X=nv.out("X"), Y=nv.out("Y"),
                  Z=bp.m("Add_FloatFloat", A=gz, B=36 * U + 8.0)), bSweep=True)
    if os.environ.get("ZDEBUG"):
        st = bp.var("DbgN", INT)
        onground.set("DbgN", bp.m("Add_IntInt", A=st, B=1))
        show, _ = onground.branch(bp.m("EqualEqual_IntInt", A=bp.var("DbgN"), B=30))
        say(bp, show, bp.pure(STR, "Concat_StrStr", A="debug: zombie step speed ",
            B=bp.pure(STR, "Conv_FloatToString", InFloat=bp.var("CurSpeed"))), color="(R=0.0,G=0.8,B=0.0,A=1.0)", secs=3.0, scale=1.0)
        say(bp, nofloor, "debug: zombie step found no floor", secs=1.0, scale=1.0)
    else:
        nofloor.end()

    # ---------------- Melee (zm L738-744; damage on each 'fire' notetrack) ----------------
    a = bp.custom("Attack")
    a.set("Busy", True)
    a.call("/Script/Engine.Controller", "StopMovement", target=bp.member("Controller"))
    a.set("MeleeIdx", bp.m("RandomIntegerInRange", Min=0, Max=6), INT)
    flow = a
    uniq = []
    for i, m in enumerate(MELEE):
        if m in uniq:
            continue
        uniq.append(m)
        ids = [j for j, x in enumerate(MELEE) if x == m]
        cond = bp.m("EqualEqual_IntInt", A=bp.var("MeleeIdx"), B=ids[0])
        if len(ids) > 1:
            cond = bp.m("BooleanOR", A=cond, B=bp.m("EqualEqual_IntInt", A=bp.var("MeleeIdx"), B=ids[1]))
        yes, flow = flow.branch(cond)
        yes.callself(f"Attack_{m}")
    flow.end()
    for m in uniq:
        e = bp.custom(f"Attack_{m}")
        e.call(SKM, "PlayAnimation", target=mesh(bp), NewAnimToPlay=anim(m), bLooping=False)
        events = sorted([(t_, "hit") for t_ in T[m]["fire"]] + [(t_, "vox") for (_, t_) in T[m]["vocal"]])
        tnow = 0.0
        for t_, kind_ in events:
            if t_ > tnow:
                e.delay(round(t_ - tnow, 3))
                tnow = t_
            if kind_ == "hit":
                e.callself("MeleeHit")
            else:
                play(e, bp, snd(bp, "Attack"))
        e.delay(round(max(0.05, T[m]["dur"] - tnow), 3))
        e.callself("AttackDone")
    ad = bp.custom("AttackDone")
    ok, _ = ad.branch(bp.m("Not_PreBool", A=bp.var("Dead")))
    ok.set("Busy", False)
    ok.callself("StartLoco")

    h = bp.custom("MeleeHit")
    tgt = bp.var("Target")
    inr = bp.m("BooleanAND", A=bp.pure(KSL, "IsValid", Object=tgt),
               B=bp.m("LessEqual_FloatFloat", A=dist(bp, bp.self_(), tgt), B=MELEE_RANGE))
    ok, _ = h.branch(bp.m("BooleanAND", A=inr, B=bp.m("Not_PreBool", A=bp.var("Dead"))))
    play(ok, bp, snd(bp, "Whoosh", 3))
    # No instigator/causer: when the hit kills the player, ARK awards the killer XP through its status
    # component, and a plain Character has none (crash in UPrimalCharacterStatusComponent::AddExperience,
    # 2026-10-10 12:17). With both null ARK treats it like fall damage.
    ok.call(GS, "ApplyDamage", DamagedActor=tgt, BaseDamage=PLAYER_HIT)

    # ---------------- Damage and death (sp L2833 death_vocals; tesla deaths L787-799) ----------------
    dmg = bp.event("ReceiveAnyDamage", ACTOR)
    dmg.node.out("DamageCauser").ptype = OBJ(ACTOR)
    dmg.node.out("Damage").ptype = FLOAT
    alive, _ = dmg.branch(bp.m("Not_PreBool", A=bp.var("Dead")))
    alive.set("Health", bp.m("Subtract_FloatFloat", A=bp.var("Health"), B=dmg.p("Damage")))
    if os.environ.get("ZDEBUG"):
        txt = bp.pure(STR, "Concat_StrStr", A=bp.pure(STR, "Concat_StrStr", A="debug: zombie hit ",
                      B=bp.pure(STR, "Conv_FloatToString", InFloat=dmg.p("Damage"))),
                      B=bp.pure(STR, "Concat_StrStr", A=" hp ", B=bp.pure(STR, "Conv_FloatToString", InFloat=bp.var("Health"))))
        dbg, alive = alive.seq(2)
        say(bp, dbg, txt, color="(R=1.0,G=0.6,B=0.0,A=1.0)", secs=2.0, scale=1.0)
    dies, _ = alive.branch(bp.m("LessEqual_FloatFloat", A=bp.var("Health"), B=0.0))
    # tesla death = the arc chain's damage type (not its actor class: zombie <-> BP_TeslaKill would be a
    # cross-Blueprint reference cycle, which the cook leaves NULL)
    dmg.node.out("DamageType").ptype = OBJ("/Script/Engine.DamageType")
    tesla = bp.m("ClassIsChildOf", TestClass=bp.pure(GS, "GetObjectClass", Object=dmg.p("DamageType")),
                 ParentClass=Obj(cls_ref(bpclass('DmgType_WaW_TeslaKill'))))
    dies.set("TeslaDeath", tesla, BOOL)
    dies.callself("Die")

    di = bp.custom("Die")
    di.set("Dead", True)
    di.set("Busy", True)
    for tm in ["Think", "VoxTick", "StuckCheck", "LocoVocal", "Step"]:
        di.call(KSL, "K2_ClearTimer", Object=bp.self_(), FunctionName=tm)
    di.call("/Script/Engine.Controller", "StopMovement", target=bp.member("Controller"))
    di.call(CMC, "DisableMovement", target=bp.member("CharacterMovement"))
    di.call(ACTOR, "SetActorEnableCollision", bNewActorEnableCollision=False)
    hasm, nom = di.branch(bp.pure(KSL, "IsValid", Object=bp.var("Manager")))
    if not os.environ.get("NO_MGR_CALL"):
        hasm.call(MGR, "ZombieDied", target=bp.var("Manager"), Zombie=bp.self_())
    hasm.callself("DieAnim")
    nom.callself("DieAnim")
    di = bp.custom("DieAnim")
    te, normal = di.branch(bp.var("TeslaDeath"))
    te.call(SKM, "PlayAnimation", target=mesh(bp), bLooping=False,
            NewAnimToPlay=bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([anim(n) for n in TESLA]),
                                 Index=bp.m("RandomIntegerInRange", Min=0, Max=4)))
    play(te, bp, snd(bp, "Elec"))
    te.call(ACTOR, "SetLifeSpan", InLifespan=12.0)
    normal.call(SKM, "PlayAnimation", target=mesh(bp), bLooping=False,
                NewAnimToPlay=bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([anim(n) for n in DEATH]),
                                     Index=bp.m("RandomIntegerInRange", Min=0, Max=3)))
    play(normal, bp, snd(bp, "Death"))
    normal.call(ACTOR, "SetLifeSpan", InLifespan=12.0)

    # ---------------- behind_vocals (fac L1370-1397), once a second ----------------
    vt = bp.custom("VoxTick")
    tgt = bp.var("Target")
    ok, _ = vt.branch(bp.m("BooleanAND", A=can, B=bp.pure(KSL, "IsValid", Object=tgt)))
    lim = bp.arr("Array_Get", out="Item", TargetArray=fl_arr(bp, [200 * U, 250 * U, 275 * U]), Index=bp.var("MoveClass"))
    tl = bp.pure(ACTOR, "K2_GetActorLocation", self=tgt)
    ml = bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())
    to_me = bp.m("Subtract_VectorVector", A=ml, B=tl)
    tv = bp.purenode(MATH, "BreakVector", InVec=to_me)
    flat = bp.m("MakeVector", X=tv.out("X"), Y=tv.out("Y"), Z=0.0)
    d2 = bp.m("VSize", A=flat)
    fwd = bp.pure(ACTOR, "GetActorForwardVector", self=tgt)
    # |yaw to spot| > 95 deg  <=>  dot(forward, dir) < cos 95
    behind = bp.m("Less_FloatFloat", A=bp.m("Dot_VectorVector", A=fwd, B=bp.m("Normal", A=flat)), B=-0.08716)
    yes, _ = ok.branch(bp.m("BooleanAND", A=bp.m("Less_FloatFloat", A=d2, B=lim), B=behind))
    play(yes, bp, snd(bp, "Behind"))

    # ---------------- stuck failsafe (zm L2153-2197) ----------------
    sc = bp.custom("StuckCheck")
    ok, _ = sc.branch(can)
    here = bp.pure(ACTOR, "K2_GetActorLocation", self=bp.self_())
    stuck, moved = ok.branch(bp.m("Less_FloatFloat", A=bp.m("VSize", A=bp.m("Subtract_VectorVector", A=here, B=bp.var("LastPos"))), B=24 * U))
    stuck.set("TeslaDeath", False)
    stuck.callself("Die")
    moved.set("LastPos", here)

    # ---------------- last zombie sprints (zm L1624-1640) ----------------
    ms = bp.custom("MakeSprint")
    ms.set("MoveClass", 2)
    ms.set("LocoIdx", bp.arr("Array_Get", out="Item", TargetArray=bp.make_array([12, 12, 13]),
                             Index=bp.m("RandomIntegerInRange", Min=0, Max=2)))
    free, _ = ms.branch(bp.m("Not_PreBool", A=bp.var("Busy")))
    free.callself("StartLoco")
    return bp


def build_manager():
    """BP_WaWRoundManager (parent Actor). Start in game: cheat SpawnActor "Blueprint'/Game/Mods/ArkMashup/
    BP_WaWRoundManager.BP_WaWRoundManager'" 0 0 0"""
    bp = BP(real_vars={"Zombies"})
    f = bp.event("ReceiveBeginPlay", ACTOR)
    f.set("CurrentRound", 1, INT)
    f.set("ZombieHealth", 150.0, FLOAT)          # zombie_health_start
    f.set("SpawnDelay", 2.0, FLOAT)              # zombie_spawn_delay
    f.set("MoveSpeed", 1, INT)                   # sp L9
    f.set("FirstRound", True, BOOL)
    f.set("Alive", 0, INT)
    f.set("HordeLeft", HORDE_ZOMBIES, INT)       # showcase: first HORDE_ZOMBIES zombies of round 1 spawn fast
    f.set("DinoTotal", HORDE_DINOS, INT)         # showcase: dinosaurs waiting to spawn
    f.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="WatchPlayers", Time=1.0, bLooping=True)
    f.callself("DinoTick")
    f.callself("StartRound")

    s = bp.custom("StartRound")
    rnd = bp.var("CurrentRound")
    s = say(bp, s, bp.pure(STR, "Concat_StrStr", A="ROUND ", B=bp.pure(STR, "Conv_IntToString", InInt=rnd)), secs=6.0, scale=3.0)
    # chalk / round intro (zm L1824-1945): 6.75 s on round 1, 0.5 s otherwise
    s.delay(bp.m("SelectFloat", A=6.75, B=0.5, bPickA=bp.var("FirstRound")))
    # ai_calculate_health (zm L2135-2150)
    rf = bp.m("Conv_IntToFloat", InInt=rnd)
    hp = bp.var("ZombieHealth")
    later, _ = s.branch(bp.m("GreaterEqual_IntInt", A=rnd, B=2))
    lin, geo = later.branch(bp.m("Less_IntInt", A=rnd, B=10))
    lin.set("ZombieHealth", bp.m("Add_FloatFloat", A=hp, B=100.0))
    lin.callself("CountRound")
    geo.set("ZombieHealth", bp.m("Add_FloatFloat", A=hp, B=bp.m("Conv_IntToFloat", InInt=bp.m("FFloor", A=bp.m("Multiply_FloatFloat", A=hp, B=0.1)))))
    geo.callself("CountRound")
    _.callself("CountRound")

    # zombie count (zm L1469-1529), solo
    c = bp.custom("CountRound")
    m = bp.m("FMax", A=1.0, B=bp.m("Divide_FloatFloat", A=rf, B=5.0))
    m = bp.m("SelectFloat", A=bp.m("Multiply_FloatFloat", A=m, B=bp.m("Multiply_FloatFloat", A=rf, B=0.15)), B=m,
             bPickA=bp.m("GreaterEqual_IntInt", A=rnd, B=10))
    mx = bp.m("Add_IntInt", A=24, B=bp.m("FFloor", A=bp.m("Multiply_FloatFloat", A=3.0, B=m)))
    mxf = bp.m("Conv_IntToFloat", InInt=mx)
    scale = bp.m("SelectFloat", A=0.2, bPickA=bp.var("FirstRound"),
                 B=bp.m("SelectFloat", A=0.4, bPickA=bp.m("Less_IntInt", A=rnd, B=3),
                        B=bp.m("SelectFloat", A=0.6, bPickA=bp.m("Less_IntInt", A=rnd, B=4),
                               B=bp.m("SelectFloat", A=0.8, B=1.0, bPickA=bp.m("Less_IntInt", A=rnd, B=5)))))
    c.set("ZombieTotal", bp.m("Add_IntInt", A=bp.m("FFloor", A=bp.m("Multiply_FloatFloat", A=mxf, B=scale)),
                                 B=bp.var("HordeLeft")), INT)
    # showcase: 2 + 2 x round dinosaurs come in with each round's zombies
    c.set("DinoTotal", bp.m("Add_IntInt", A=bp.var("DinoTotal"), B=bp.m("Add_IntInt", A=2, B=bp.m("Multiply_IntInt", A=rnd, B=2))))
    c.callself("SpawnTick")

    # spawn loop (zm L1536-1622)
    sp = bp.custom("SpawnTick")
    more, done = sp.branch(bp.m("Greater_IntInt", A=bp.var("ZombieTotal"), B=0))
    done.callself("WaitRoundEnd")
    full, room = more.branch(bp.m("Greater_IntInt", A=bp.var("Alive"), B=31))
    full.delay(0.1)
    full.callself("SpawnTick")
    room.callself("SpawnOne")

    so = bp.custom("SpawnOne")
    pl = bp.pure(GS, "GetPlayerCharacter", PlayerIndex=0)
    ok, _ = so.branch(bp.pure(KSL, "IsValid", Object=pl))
    ang = bp.m("RandomFloatInRange", Min=0.0, Max=6.2831853)
    dist = bp.m("RandomFloatInRange", Min=1500.0, Max=4000.0)
    pv = bp.purenode(MATH, "BreakVector", InVec=bp.pure(ACTOR, "K2_GetActorLocation", self=pl))
    px = bp.m("Add_FloatFloat", A=pv.out("X"), B=bp.m("Multiply_FloatFloat", A=dist, B=bp.m("Cos", A=ang)))
    py = bp.m("Add_FloatFloat", A=pv.out("Y"), B=bp.m("Multiply_FloatFloat", A=dist, B=bp.m("Sin", A=ang)))
    ok.set("SpawnXY", bp.m("MakeVector", X=px, Y=py, Z=pv.out("Z")), VEC)
    xy = bp.purenode(MATH, "BreakVector", InVec=bp.var("SpawnXY"))
    top = bp.m("MakeVector", X=xy.out("X"), Y=xy.out("Y"), Z=bp.m("Add_FloatFloat", A=xy.out("Z"), B=5000.0))
    bot = bp.m("MakeVector", X=xy.out("X"), Y=xy.out("Y"), Z=bp.m("Subtract_FloatFloat", A=xy.out("Z"), B=5000.0))
    tr = ok.call(KSL, "LineTraceSingle_DEPRECATED", Start=top, End=bot, TraceChannel="ECC_Visibility", bTraceComplex=False, bIgnoreSelf=True)
    hitp = bp.purenode(GS, "BreakHitResult", Hit=tr.out("OutHit")).out("ImpactPoint")
    hz = bp.purenode(MATH, "BreakVector", InVec=hitp).out("Z")
    near_z = bp.m("LessEqual_FloatFloat", A=bp.m("Abs", A=bp.m("Subtract_FloatFloat", A=hz, B=pv.out("Z"))), B=1000.0)
    grounded, miss = ok.branch(bp.m("BooleanAND", A=tr.out("ReturnValue"), B=near_z))
    miss.delay(0.05)
    miss.callself("SpawnTick")
    xfm = bp.m("MakeTransform", Location=bp.m("Add_VectorVector", A=hitp, B=bp.m("MakeVector", X=0.0, Y=0.0, Z=92.0)),
               Rotation=bp.m("MakeRot", Pitch=0.0, Yaw=0.0, Roll=0.0), Scale=bp.m("MakeVector", X=1.0, Y=1.0, Z=1.0))
    z = grounded.spawn(ZOMBIE, xfm, bNoCollisionFail=True)
    grounded.set("Alive", bp.m("Add_IntInt", A=bp.var("Alive"), B=1))
    grounded.set("ZombieTotal", bp.m("Subtract_IntInt", A=bp.var("ZombieTotal"), B=1))
    grounded.arr("Array_Add", TargetArray=bp.var("Zombies", OBJ(ZOMBIE, True)), NewItem=z.out("ReturnValue"))
    grounded.call(ZOMBIE, "Init", target=z.out("ReturnValue"), ManagerIn=bp.self_(), HealthIn=bp.var("ZombieHealth"),
                  SpeedIn=bp.var("MoveSpeed"))
    if os.environ.get("ZDEBUG"):
        valid = bp.pure(KSL, "IsValid", Object=z.out("ReturnValue"))
        okz, badz = grounded.branch(valid)
        grounded = say(bp, okz, "debug: zombie spawned", color="(R=0.0,G=0.8,B=0.0,A=1.0)", secs=2.0, scale=1.0)
        say(bp, badz, "debug: zombie spawn FAILED", secs=2.0, scale=1.0)

    grounded.delay(bp.m("SelectFloat", A=0.15, B=bp.m("Add_FloatFloat", A=bp.var("SpawnDelay"), B=0.05),
                        bPickA=bp.m("Greater_IntInt", A=bp.var("HordeLeft"), B=0)))
    grounded.set("HordeLeft", bp.m("Max", A=bp.m("Subtract_IntInt", A=bp.var("HordeLeft"), B=1), B=0))
    grounded.callself("SpawnTick")

    # showcase dinosaurs: one every 0.3 s while DinoTotal > 0, 25-70 m from the player, random species
    dt = bp.custom("DinoTick")
    has, idle = dt.branch(bp.m("Greater_IntInt", A=bp.var("DinoTotal"), B=0))
    idle.delay(1.0)
    idle.callself("DinoTick")
    pl = bp.pure(GS, "GetPlayerCharacter", PlayerIndex=0)
    okp, nopl = has.branch(bp.pure(KSL, "IsValid", Object=pl))
    nopl.delay(1.0)
    nopl.callself("DinoTick")
    dg, dmiss, dhit = ground_point(bp, okp, pl, "DinoXY", 2500.0, 7000.0)
    dmiss.delay(0.05)
    dmiss.callself("DinoTick")
    classes = bp.make_array([Obj(cls_ref(dino_class(*d))) for d in DINOS], elem=TP("class", cls_ref(DINO)))
    pick = bp.arr("Array_Get", out="Item", TargetArray=classes, Index=bp.m("RandomIntegerInRange", Min=0, Max=len(DINOS) - 1))
    dx = bp.m("MakeTransform", Location=bp.m("Add_VectorVector", A=dhit, B=bp.m("MakeVector", X=0.0, Y=0.0, Z=400.0)),
              Rotation=bp.m("MakeRot", Pitch=0.0, Yaw=bp.m("RandomFloatInRange", Min=0.0, Max=360.0), Roll=0.0),
              Scale=bp.m("MakeVector", X=1.0, Y=1.0, Z=1.0))
    d = spawn_class(bp, dg, pick, dx)
    dg.set("DinoTotal", bp.m("Subtract_IntInt", A=bp.var("DinoTotal"), B=1))
    isd, notd, dpawn = dg.cast(PAWN, d.out("ReturnValue"))
    isd.call(PAWN, "SpawnDefaultController", target=dpawn)
    isd.delay(0.3)
    isd.callself("DinoTick")
    notd.delay(0.3)
    notd.callself("DinoTick")

    zd = bp.custom("ZombieDied", [("Zombie", OBJ(ZOMBIE))])
    ev = zd
    zd.set("Alive", bp.m("Subtract_IntInt", A=bp.var("Alive"), B=1))
    zd.arr("Array_RemoveItem", TargetArray=bp.var("Zombies"), Item=ev.p("Zombie"))
    last = bp.m("BooleanAND", A=bp.m("Greater_IntInt", A=bp.var("CurrentRound"), B=3),
                B=bp.m("BooleanAND", A=bp.m("EqualEqual_IntInt", A=bp.var("Alive"), B=1),
                       B=bp.m("LessEqual_IntInt", A=bp.var("ZombieTotal"), B=0)))
    yes, _ = zd.branch(last)
    yes.call(ZOMBIE, "MakeSprint", target=bp.arr("Array_Get", out="Item", TargetArray=bp.var("Zombies"), Index=0))

    # round_wait (zm L2201-2234)
    w = bp.custom("WaitRoundEnd")
    w.delay(1.0)
    w.callself("PollRoundEnd")
    p = bp.custom("PollRoundEnd")
    over, notover = p.branch(bp.m("BooleanAND", A=bp.m("LessEqual_IntInt", A=bp.var("Alive"), B=0),
                                  B=bp.m("LessEqual_IntInt", A=bp.var("ZombieTotal"), B=0)))
    notover.delay(0.5)
    notover.callself("PollRoundEnd")
    over.set("FirstRound", False)
    over.delay(10.0)                                     # zombie_between_round_time
    over.set("SpawnDelay", bp.m("Multiply_FloatFloat", A=bp.m("FMax", A=bp.var("SpawnDelay"), B=0.08), B=0.95))
    over.set("MoveSpeed", bp.m("Multiply_IntInt", A=bp.var("CurrentRound"), B=8))
    over.set("CurrentRound", bp.m("Add_IntInt", A=bp.var("CurrentRound"), B=1))
    over.callself("StartRound")

    # game over (zm L2661, L2716): every player dead -> 15 s, then clear the zombies and stop
    wp = bp.custom("WatchPlayers")
    pl = bp.pure(GS, "GetPlayerCharacter", PlayerIndex=0)
    dead, _ = wp.branch(bp.m("BooleanOR", A=bp.m("Not_PreBool", A=bp.pure(KSL, "IsValid", Object=pl)),
                             B=bp.pure(ACTOR, "IsDead", self=pl)))
    dead.call(KSL, "K2_ClearTimer", Object=bp.self_(), FunctionName="WatchPlayers")
    dead = say(bp, dead, bp.pure(STR, "Concat_StrStr", A="GAME OVER - you survived ",
               B=bp.pure(STR, "Concat_StrStr", A=bp.pure(STR, "Conv_IntToString", InInt=bp.var("CurrentRound")), B=" rounds")),
               secs=15.0, scale=2.5)
    dead.delay(15.0)
    body, zel, _ = dead.foreach(bp.var("Zombies"))
    body.call(ACTOR, "K2_DestroyActor", target=zel)
    dead.call(ACTOR, "K2_DestroyActor")
    return bp


if __name__ == "__main__":
    out = "/Users/YOU/ark-mashup/.work/graphs"
    os.makedirs(out, exist_ok=True)
    built = [(name, fn()) for name, fn in [("BP_WaWZombie", build_zombie), ("BP_WaWRoundManager", build_manager)]]
    for name, b in built:
        open(f"{out}/{name}.txt", "w").write(b.text())
        print(f"{name}: {len(b.g.nodes)} nodes; vars: {list(b.vars)}")
