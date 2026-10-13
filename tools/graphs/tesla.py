"""Wunderwaffe DG-2 arc chain, ported from maps/_zombiemode_tesla.gsc (Der Riese).

Actors (2026-10-10 layout: no Blueprint references itself or the other one back; the earlier one-actor-per-node
design needed cross-instance calls/reads on its own class, which UE 4.5 resolves as self-context and drops, and its
BP_TeslaChain <-> BP_TeslaKill cycle left one class NULL in the cook):
  BP_TeslaKill   one per shot. Runs WaW's recursive arc_damage() search as an explicit depth-first stack (same
                 visiting order, one network frame per arc_damage call) and holds the chain state: candidate cache
                 sorted by distance from the root's head, hit marks, enemies_hit, the shooter.
  BP_TeslaChain  one per hit creature: that node's tesla_do_damage() kill task (bolt, travel time, gib roll, kill).
ProjWunderwaffe  on destroy: per-player lock (L50-54), then root = direct victim, else the first creature within the
                 110 u splash with line of sight; spawns the BP_TeslaKill.

Constants (tesla L32-40): max arcs 5, max kills 20, radius (300 - 20*arc) u, travel 0.5 s, min fx distance
128 u, head-gib chance 50. Network frame = 0.05 s (single player).
"""
import os
import sys

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpc import (cls_ref, GLOBAL_TYPES, ACTOR, BOOL, CHAR, FLOAT, GS, INT, KSL, MATH, PAWN, PRIMAL, VICTORY, BP, OBJ, Obj,  # noqa
                 asset, bpclass)

U = 2.54
NETFRAME = 0.05
KILL = bpclass("BP_TeslaKill")      # search (one per shot)
TASK = bpclass("BP_TeslaChain")     # kill task (one per hit creature)
ZOMBIE = bpclass("BP_WaWZombie")
DMG_KILL = bpclass("DmgType_WaW_TeslaKill")
BOLT_FX = "ParticleSystem'/Game/Abyss/Effects/Particles/P_ElectricSurge.P_ElectricSurge'"   # placeholder bolt
HEAD_SOCKETS = ["j_head", "c_head", "Cnt_Head_JNT_SKL", "head", "Head", "HeadSocket", "BuffSocketHeadDynamic"]
CHR = OBJ(CHAR)
CHR_ARR = OBJ(CHAR, True)
INT_ARR = "(PinCategory=\"int\",bIsArray=True)"
GLOBAL_TYPES.update({"Candidates": CHR_ARR, "HitList": CHR_ARR, "Remaining": CHR_ARR, "EnemiesHit": INT,
                     "Shooter": OBJ(PAWN), "SearchActive": BOOL, "Found": CHR_ARR,
                     "StNode": CHR_ARR, "StArc": INT_ARR, "StIdx": INT_ARR, "StEnd": INT_ARR})
SEARCH_VARS = {"Candidates", "HitList", "Remaining", "EnemiesHit", "Shooter", "SearchActive", "Found",
               "StNode", "StArc", "StIdx", "StEnd"}


def loc(bp, a):
    return bp.pure(ACTOR, "K2_GetActorLocation", self=a)


def head_of(bp, ch):
    """Head(c) (design 3.4): first existing head socket on the character mesh, else location + 80 cm."""
    mesh = bp.var_of(ch, "Mesh", CHAR)
    best = bp.m("Add_VectorVector", A=loc(bp, ch), B=bp.m("MakeVector", X=0.0, Y=0.0, Z=80.0))
    for s in reversed(HEAD_SOCKETS):
        has = bp.pure("/Script/Engine.SceneComponent", "DoesSocketExist", self=mesh, InSocketName=s)
        sl = bp.pure("/Script/Engine.SceneComponent", "GetSocketLocation", self=mesh, InSocketName=s)
        best = bp.m("SelectVector", A=sl, B=best, bPickA=has)
    return best


def is_creature(bp, ch, shooter):
    """A living PrimalCharacter or WaW zombie that is not a player and not the shooter."""
    cls = bp.pure(GS, "GetObjectClass", Object=ch)
    primal = bp.m("ClassIsChildOf", TestClass=cls, ParentClass=Obj(cls_ref(PRIMAL)))
    zombie = bp.m("ClassIsChildOf", TestClass=cls, ParentClass=Obj(cls_ref(ZOMBIE)))
    player = bp.m("ClassIsChildOf", TestClass=cls, ParentClass=Obj("Class'/Script/ShooterGame.ShooterCharacter'"))
    c = bp.m("BooleanOR", A=primal, B=zombie)
    c = bp.m("BooleanAND", A=c, B=bp.m("Not_PreBool", A=player))
    c = bp.m("BooleanAND", A=c, B=bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=ch)))
    c = bp.m("BooleanAND", A=c, B=bp.m("NotEqual_ObjectObject", A=ch, B=shooter))
    return bp.m("BooleanAND", A=bp.pure(KSL, "IsValid", Object=ch), B=c)


def xform(bp, at):
    return bp.m("MakeTransform", Location=at, Rotation=bp.m("MakeRot", Pitch=0.0, Yaw=0.0, Roll=0.0),
                Scale=bp.m("MakeVector", X=1.0, Y=1.0, Z=1.0))


def los_clear(bp, flow, a, b, ignore):
    """BulletTracePassed(a, b, false): trace world geometry; returns (clear_flow, blocked_flow)."""
    tr = flow.call(KSL, "LineTraceSingle_DEPRECATED", Start=a, End=b, TraceChannel="ECC_Visibility",
                   bTraceComplex=False, bIgnoreSelf=True, ActorsToIgnore=bp.make_array(ignore))
    return flow.branch(bp.m("Not_PreBool", A=tr.out("ReturnValue")))


# ------------------------------------------------------------------------------------------------
def last(bp, name):
    """Last element of a real array variable (the top of a stack)."""
    v = bp.var(name)
    return bp.arr("Array_Get", out="Item", TargetArray=v,
                  Index=bp.m("Subtract_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var(name)), B=1))


def pop(bp, flow, name):
    flow.arr("Array_Remove", TargetArray=bp.var(name),
             IndexToRemove=bp.m("Subtract_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var(name)), B=1))


def build_search():
    """BP_TeslaKill: WaW arc_damage() recursion as an explicit stack. One frame per arc_damage call:
    StNode (its creature), StArc (arc_num), StIdx (next index into Found), StEnd (end of its slice of Found).
    A frame's slice of Found starts where the frame below it ends (or at 0), because deeper frames are popped and
    their slices truncated before a sibling is visited."""
    bp = BP(real_vars=SEARCH_VARS)
    f = bp.custom("StartChain", [("RootIn", CHR), ("ShooterIn", OBJ(PAWN))])
    ev = f
    f.set("Root", ev.p("RootIn"), CHR)
    f.set("Shooter", ev.p("ShooterIn"), OBJ(PAWN))
    f.set("SearchActive", True, BOOL)
    f.set("EnemiesHit", 1, INT)                                    # L72: the root counts as one
    for a in ("HitList", "Remaining", "Candidates", "Found", "StNode", "StArc", "StIdx", "StEnd"):
        f.arr("Array_Clear", TargetArray=bp.var(a))
    f.call(ACTOR, "SetLifeSpan", InLifespan=30.0)
    rootpos = head_of(bp, bp.var("Root"))
    # candidate cache (L154-158): every hostile creature (pre-filtered to 75 m around the root)
    allc = f.call(GS, "GetAllActorsOfClass", ActorClass=Obj(cls_ref(CHAR)))
    body, el, _ = f.foreach(allc.out("OutActors"))
    ok, _, asch = body.cast(CHAR, el)
    near = bp.m("LessEqual_FloatFloat", A=bp.m("VSize", A=bp.m("Subtract_VectorVector", A=loc(bp, asch), B=rootpos)), B=7500.0)
    keep, _ = ok.branch(bp.m("BooleanAND", A=is_creature(bp, asch, bp.var("Shooter")), B=near))
    keep.arr("Array_Add", TargetArray=bp.var("Remaining"), NewItem=asch)
    # get_array_of_closest(root head): selection sort Remaining -> Candidates
    loop = f.whileloop(bp.m("Greater_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var("Remaining")), B=0))
    loop.set("BestI", 0, INT)
    loop.set("BestD", 1.0e12, FLOAT)
    b2, el2, i2 = loop.foreach(bp.var("Remaining"))
    d = bp.m("VSize", A=bp.m("Subtract_VectorVector", A=loc(bp, el2), B=rootpos))
    better, _ = b2.branch(bp.m("Less_FloatFloat", A=d, B=bp.var("BestD")))
    better.set("BestD", d)
    better.set("BestI", i2)
    loop.arr("Array_Add", TargetArray=bp.var("Candidates"),
             NewItem=bp.arr("Array_Get", out="Item", TargetArray=bp.var("Remaining"), Index=bp.var("BestI")))
    loop.arr("Array_Remove", TargetArray=bp.var("Remaining"), IndexToRemove=bp.var("BestI"))
    # L74: arc_damage(root, player, 1)
    f.arr("Array_Add", TargetArray=bp.var("HitList"), NewItem=bp.var("Root"))
    f.callself("Visit", NodeIn=bp.var("Root"), SrcIn=bp.var("Root"), ArcIn=1)

    # arc_damage(node, src, arc): wait_network_frame (a timer: Visit runs again from inside its own continuation)
    v = bp.custom("Visit", [("NodeIn", CHR), ("SrcIn", CHR), ("ArcIn", INT)])
    v.set("VNode", v.p("NodeIn"), CHR)
    v.set("VSrc", v.p("SrcIn"), CHR)
    v.set("VArc", v.p("ArcIn"), INT)
    v.call(KSL, "K2_SetTimer", Object=bp.self_(), FunctionName="VisitNow", Time=NETFRAME, bLooping=False)

    w = bp.custom("VisitNow")
    node, arc = bp.var("VNode"), bp.var("VArc")
    # L90: thread tesla_do_damage(node, arc, player)
    t = w.spawn(TASK, xform(bp, loc(bp, node)))
    w.call(TASK, "KillTask", target=t.out("ReturnValue"), NodeIn=node, SrcIn=bp.var("VSrc"), ArcIn=arc,
           ShooterIn=bp.var("Shooter"))
    # L96-107: enemies in range of this node's head, all marked hit
    w.set("SegStart", bp.arr("Array_Length", TargetArray=bp.var("Found")), INT)
    radius = bp.m("Multiply_FloatFloat", B=U, A=bp.m("Subtract_FloatFloat", A=300.0,
                  B=bp.m("Multiply_FloatFloat", A=20.0, B=bp.m("Conv_IntToFloat", InInt=arc))))
    ends = bp.m("BooleanOR", A=bp.m("GreaterEqual_IntInt", A=bp.m("Add_IntInt", A=arc, B=1), B=5),
                B=bp.m("GreaterEqual_IntInt", A=bp.var("EnemiesHit"), B=20))
    # if the end condition holds for every candidate the search only marks then unmarks: skip it (same result)
    stop, go = w.branch(bp.m("BooleanOR", A=ends, B=bp.m("LessEqual_FloatFloat", A=radius, B=0.0)))
    stop.callself("Push")
    origin = head_of(bp, node)
    body, c, _ = go.foreach(bp.var("Candidates"))
    hc = head_of(bp, c)
    ok = bp.m("BooleanAND", A=is_creature(bp, c, bp.var("Shooter")),
              B=bp.m("Not_PreBool", A=bp.arr("Array_Contains", TargetArray=bp.var("HitList"), ItemToFind=c)))
    ok = bp.m("BooleanAND", A=ok, B=bp.m("LessEqual_FloatFloat", A=bp.m("VSize", A=bp.m("Subtract_VectorVector", A=hc, B=origin)), B=radius))
    cand, _ = body.branch(ok)
    clear, _ = los_clear(bp, cand, origin, hc, [node, c])
    clear.arr("Array_Add", TargetArray=bp.var("Found"), NewItem=c)
    clear.arr("Array_Add", TargetArray=bp.var("HitList"), NewItem=c)   # L107: mark everything found as hit
    go.callself("Push")

    p = bp.custom("Push")
    p.arr("Array_Add", TargetArray=bp.var("StNode"), NewItem=bp.var("VNode"))
    p.arr("Array_Add", TargetArray=bp.var("StArc"), NewItem=bp.var("VArc"))
    p.arr("Array_Add", TargetArray=bp.var("StIdx"), NewItem=bp.var("SegStart"))
    p.arr("Array_Add", TargetArray=bp.var("StEnd"), NewItem=bp.arr("Array_Length", TargetArray=bp.var("Found")))
    p.callself("Advance")

    # the loop over this frame's enemies (L109-130); a child frame runs to completion before the next sibling
    a = bp.custom("Advance")
    empty, live = a.branch(bp.m("LessEqual_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var("StNode")), B=0))
    empty.set("SearchActive", False)                               # releases the per-player lock
    more, done = live.branch(bp.m("Less_IntInt", A=last(bp, "StIdx"), B=last(bp, "StEnd")))
    more.set("Cur", bp.arr("Array_Get", out="Item", TargetArray=bp.var("Found"), Index=last(bp, "StIdx")), CHR)
    more.set("NextIdx", bp.m("Add_IntInt", A=last(bp, "StIdx"), B=1), INT)
    pop(bp, more, "StIdx")
    more.arr("Array_Add", TargetArray=bp.var("StIdx"), NewItem=bp.var("NextIdx"))
    endc = bp.m("BooleanOR", A=bp.m("GreaterEqual_IntInt", A=bp.m("Add_IntInt", A=last(bp, "StArc"), B=1), B=5),
                B=bp.m("GreaterEqual_IntInt", A=bp.var("EnemiesHit"), B=20))
    skip, take = more.branch(endc)
    skip.arr("Array_RemoveItem", TargetArray=bp.var("HitList"), Item=bp.var("Cur"))   # L127
    skip.callself("Advance")
    take.set("EnemiesHit", bp.m("Add_IntInt", A=bp.var("EnemiesHit"), B=1))
    take.callself("Visit", NodeIn=bp.var("Cur"), SrcIn=last(bp, "StNode"),
                  ArcIn=bp.m("Add_IntInt", A=last(bp, "StArc"), B=1))
    # frame finished: truncate its slice of Found, pop it, continue with the parent's loop
    n = bp.m("Subtract_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var("StEnd")), B=2)
    below = bp.arr("Array_Get", out="Item", TargetArray=bp.var("StEnd"), Index=n)
    done.set("SegStart", bp.m("SelectInt", A=below, B=0, bPickA=bp.m("GreaterEqual_IntInt", A=n, B=0)))
    tr = done.whileloop(bp.m("Greater_IntInt", A=bp.arr("Array_Length", TargetArray=bp.var("Found")), B=bp.var("SegStart")))
    pop(bp, tr, "Found")
    for st in ("StNode", "StArc", "StIdx", "StEnd"):
        pop(bp, done, st)
    done.callself("Advance")
    return bp


# ------------------------------------------------------------------------------------------------
def build_task():
    """BP_TeslaChain: tesla_do_damage (L217-310) for one creature."""
    bp = BP(real_vars=set())
    f = bp.custom("KillTask", [("NodeIn", CHR), ("SrcIn", CHR), ("ArcIn", INT), ("ShooterIn", OBJ(PAWN))])
    f.set("NodeRef", f.p("NodeIn"), CHR)
    f.set("SrcRef", f.p("SrcIn"), CHR)
    f.set("ArcRef", f.p("ArcIn"), INT)
    f.set("ShooterRef", f.p("ShooterIn"), OBJ(PAWN))
    f.call(ACTOR, "SetLifeSpan", InLifespan=10.0)
    later, root = f.branch(bp.m("Greater_IntInt", A=bp.var("ArcRef"), B=1))
    later.delay(bp.m("Multiply_FloatFloat", A=bp.m("RandomFloatInRange", Min=0.2, Max=0.6),
                     B=bp.m("Conv_IntToFloat", InInt=bp.var("ArcRef"))))
    later.callself("KillBolt")
    root.callself("KillBolt")

    t = bp.custom("KillBolt")
    nd, sr = bp.var("NodeRef"), bp.var("SrcRef")
    alive = bp.m("BooleanAND", A=bp.pure(KSL, "IsValid", Object=nd), B=bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=nd)))
    ok2, _ = t.branch(alive)
    bolt, nob = ok2.branch(bp.m("NotEqual_ObjectObject", A=sr, B=nd))
    bolt.call(GS, "SpawnEmitterAtLocation", EmitterTemplate=Obj(BOLT_FX), Location=loc(bp, nd), bAutoDestroy=True)
    bolt.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", "S_Waffe_Bounce0"), Location=loc(bp, nd))
    far, nearf = bolt.branch(bp.m("GreaterEqual_FloatFloat", B=128.0 * U,
                                  A=bp.m("VSize", A=bp.m("Subtract_VectorVector", A=loc(bp, sr), B=loc(bp, nd)))))
    far.delay(0.5)                                                 # tesla_arc_travel_time
    far.callself("KillGib")
    nearf.callself("KillGib")
    nob.callself("KillGib")

    g = bp.custom("KillGib")                                       # L313-343 head gib roll
    gib, eye = g.branch(bp.m("Less_IntInt", A=bp.m("RandomInteger", Max=100), B=50))
    gib.delay(bp.m("RandomFloatInRange", Min=0.53, Max=1.0))
    gib.callself("KillNow")
    eye.callself("KillNow")

    kn = bp.custom("KillNow")                                      # L290-301
    nd2 = bp.var("NodeRef")
    alive2 = bp.m("BooleanAND", A=bp.pure(KSL, "IsValid", Object=nd2), B=bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=nd2)))
    go2, _ = kn.branch(alive2)
    go2.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", "S_Waffe_ArcSizzle"), Location=loc(bp, nd2))
    ctrl = bp.var_of(bp.var("ShooterRef"), "Controller", PAWN)
    dino, notdino, asp = go2.cast(PRIMAL, nd2)
    boss, normal = dino.branch(bp.pure(PRIMAL, "IsBossDino", self=asp))
    boss.call(GS, "ApplyDamage", DamagedActor=asp, BaseDamage=1000.0, EventInstigator=ctrl, DamageCauser=bp.self_(),
              DamageTypeClass=Obj(cls_ref(DMG_KILL)))
    normal.call(GS, "ApplyDamage", DamagedActor=asp, EventInstigator=ctrl, DamageCauser=bp.self_(),
                BaseDamage=bp.m("Add_FloatFloat", A=bp.pure(PRIMAL, "GetHealth", self=asp), B=666.0),
                DamageTypeClass=Obj(cls_ref(DMG_KILL)))
    still, _ = normal.branch(bp.m("Not_PreBool", A=bp.pure(ACTOR, "IsDead", self=asp)))
    still.call(VICTORY, "KillTargetCharacterOrStructure", ActorToKill=asp, DamageCauser=bp.self_(), bTryDestroyActor=False)
    zok, _, asz = notdino.cast(ZOMBIE, nd2)
    zok.call(GS, "ApplyDamage", DamagedActor=asz, EventInstigator=ctrl, DamageCauser=bp.self_(),
             BaseDamage=1.0e6,   # zombie: health + 666 always exceeds its health; any larger value is identical
             DamageTypeClass=Obj(cls_ref(DMG_KILL)))
    return bp


# ------------------------------------------------------------------------------------------------
def start_chain(bp, flow, root, shooter):
    """L50-60: ignore the shot if this player's previous chain is still searching, or the root is already hit;
    else spawn the search. Runs in the projectile, so BP_TeslaKill never reads other instances of itself."""
    flow.set("Locked", False, BOOL)
    others = flow.call(GS, "GetAllActorsOfClass", ActorClass=Obj(cls_ref(KILL)))
    lb, oel, _ = flow.foreach(others.out("OutActors"))
    cok, _, och = lb.cast(KILL, oel)
    mine = bp.m("BooleanAND", A=bp.var_of(och, "SearchActive", KILL),
                B=bp.m("EqualEqual_ObjectObject", A=bp.var_of(och, "Shooter", KILL), B=shooter))
    marked = bp.arr("Array_Contains", TargetArray=bp.var_of(och, "HitList", KILL), ItemToFind=root)
    lk, _ = cok.branch(bp.m("BooleanOR", A=mine, B=marked))
    lk.set("Locked", True)
    _, free = flow.branch(bp.var("Locked"))
    s = free.spawn(KILL, xform(bp, loc(bp, bp.self_())))
    free.call(KILL, "StartChain", target=s.out("ReturnValue"), RootIn=root, ShooterIn=shooter)


def build_projectile():
    """Added to ProjWunderwaffe's event graph. Projectile defaults: direct + explosion damage 1 (weapon file)."""
    bp = BP(real_vars=set())
    b = bp.event("ReceiveBeginPlay", ACTOR)
    b.call(GS, "PlaySoundAttached", Sound=asset("SoundWave", "S_Waffe_ProjLoop"), AttachToComponent=bp.member("RootComponent"),
           bStopWhenAttachedToDestroyed=True)
    hit = bp.event("ReceiveHit", ACTOR)
    hit.node.out("Other").ptype = OBJ(ACTOR)
    hit.set("HitActor", hit.p("Other"), OBJ(ACTOR))
    d = bp.event("ReceiveDestroyed", ACTOR)
    other = bp.var("HitActor", OBJ(ACTOR))
    me = loc(bp, bp.self_())
    shooter = bp.var_of(bp.self_(), "Instigator", ACTOR)
    d.call(GS, "PlaySoundAtLocation", Sound=asset("SoundWave", "S_Waffe_Impact"), Location=me)
    dc, notc, asc = d.cast(CHAR, other)
    direct, indirect = dc.branch(is_creature(bp, asc, shooter))
    direct.set("RootC", asc, CHR)
    direct.callself("WaWStart")
    indirect.callself("WaWSplashRoot")
    notc.callself("WaWSplashRoot")
    # no creature hit directly: creatures in the 110 u splash with line of sight. The first one starts the chain;
    # the lock makes any later ones in the same frame ignore themselves (WaW: first damage callback wins).
    sp = bp.custom("WaWSplashRoot")
    ov = sp.call(KSL, "SphereOverlapActors_DEPRECATED", SpherePos=me, SphereRadius=110.0 * U,
                 Filter="AllObjects", ActorClassFilter=Obj(cls_ref(CHAR)))
    body, el, _ = sp.foreach(ov.out("OutActors"))
    eok, _, ase = body.cast(CHAR, el)
    cr, _ = eok.branch(is_creature(bp, ase, shooter))
    clear, _ = los_clear(bp, cr, me, loc(bp, ase), [ase])
    clear.set("RootC", ase)
    clear.callself("WaWStart")
    st = bp.custom("WaWStart")
    start_chain(bp, st, bp.var("RootC"), shooter)
    return bp


if __name__ == "__main__":
    out = "/Users/YOU/ark-mashup/.work/graphs"
    os.makedirs(out, exist_ok=True)
    built = [(name, fn()) for name, fn in [("BP_TeslaChain", build_task), ("BP_TeslaKill", build_search), ("ProjWunderwaffe", build_projectile)]]
    for name, b in built:
        open(f"{out}/{name}.txt", "w").write(b.text())
        print(f"{name}: {len(b.g.nodes)} nodes; vars: {b.vars}")
