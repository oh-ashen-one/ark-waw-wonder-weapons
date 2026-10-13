"""Small flow DSL on top of bpgen: write Blueprint logic as Python, emit paste-ready UE4.5 graph text.

    bp = BP()
    f = bp.event("ReceiveBeginPlay", ACTOR)          # Flow starting at the event's exec output
    loc = bp.pure(ACTOR, "K2_GetActorLocation")       # pure call -> its ReturnValue pin
    f.call(KSL, "PrintString", InString="hi")
    yes, no = f.branch(bp.pure(MATH, "Greater_FloatFloat", A=1.0, B=0.5))
    open("out.txt", "w").write(bp.text())

Values passed as inputs: a Pin (linked), an Obj("Class'..'") (object/class default), or a literal (DefaultValue).
Member variables must exist in the target Blueprint (create them in the editor first; see bp.vars).
"""
import sys

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpgen import Graph, Pin, EVENT_SIGS  # noqa: E402

KSL = "/Script/Engine.KismetSystemLibrary"
MATH = "/Script/Engine.KismetMathLibrary"
GS = "/Script/Engine.GameplayStatics"
ARR = "/Script/Engine.KismetArrayLibrary"
ACTOR = "/Script/Engine.Actor"
PAWN = "/Script/Engine.Pawn"
CHAR = "/Script/Engine.Character"
SKM = "/Script/Engine.SkeletalMeshComponent"
CMC = "/Script/Engine.CharacterMovementComponent"
PRIMAL = "/Script/ShooterGame.PrimalCharacter"
DINO = "/Script/ShooterGame.PrimalDinoCharacter"
VICTORY = "/Script/ShooterGame.VictoryCore"
MOD = "/Game/Mods/ArkMashup"


def bpclass(name):
    return f"{MOD}/{name}.{name}_C"


def cls_ref(path):
    """Object reference literal for a class path (native or Blueprint)."""
    return f"BlueprintGeneratedClass'{path}'" if path.startswith("/Game/") else f"Class'{path}'"


GLOBAL_TYPES = {}
ENUM_PREFIX = {"ECC_": "ECollisionChannel", "ECR_": "ECollisionResponse"}
MEMBER_TYPES = {"Mesh": "/Script/Engine.SkeletalMeshComponent", "CharacterMovement": "/Script/Engine.CharacterMovementComponent",
                "CapsuleComponent": "/Script/Engine.CapsuleComponent", "Controller": "/Script/Engine.Controller",
                "RootComponent": "/Script/Engine.SceneComponent", "Instigator": "/Script/Engine.Pawn"}   # member var name -> PinType literal (for reads of other Blueprints' vars)


def elem_of(t):
    return t.replace(",bIsArray=True", "") if t else None


def arr_of(t):
    return t[:-1] + ",bIsArray=True)" if t and "bIsArray" not in t else t


def type_of_value(v):
    if isinstance(v, Pin):
        return v.ptype
    if isinstance(v, Obj):
        kind = v.ref.split("'")[0]
        return OBJ("/Script/Engine." + kind) if kind not in ("Class", "BlueprintGeneratedClass") else None
    if isinstance(v, bool):
        return T("bool")
    if isinstance(v, int):
        return T("int")
    if isinstance(v, float):
        return T("float")
    return None


def asset(kind, name):
    return Obj(f"{kind}'{MOD}/{name}.{name}'")


class Obj:
    def __init__(me, ref):
        me.ref = ref


def lit(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.6f}"
    return str(v)


class BP:
    def __init__(me, real_vars=None):
        me.g = Graph(0, 0)
        me.vars = {}          # name -> type description (for the editor checklist)
        # Store mode: variables not in real_vars live in a "Set_<Name>" custom event's persistent parameter
        # (pasteable, no editor UI needed). real_vars=None -> every variable is a real member variable.
        me.real_vars = real_vars
        me._stores = {}
        me._x, me._y = 0, 0
        me._row = 0

    # --- layout: exec nodes advance x on a row, pure nodes stack below them -------------------
    def _xy(me, pure=False):
        if pure:
            me._py = getattr(me, "_py", 0) + 120
            return me._x, me._row * 900 + 250 + (me._py % 600)
        me._x += 340
        return me._x, me._row * 900

    def newrow(me):
        me._row += 1
        me._x = 0

    def _apply(me, node, ins):
        for k, v in ins.items():
            if v is None:
                continue
            if isinstance(v, Pin):
                me.g.link(v, node.inp(k))
            elif isinstance(v, Obj):
                p = node.inp(k)
                node.props_pin_obj = getattr(node, "props_pin_obj", {})
                p.default_obj = v.ref
            else:
                node.inp(k, default=lit(v))
                # enum defaults only survive a paste when the pin carries its exact enum type (2026-10-10:
                # untyped "ECR_Block"/"Visibility" pasted back as the enum's first value)
                if isinstance(v, str) and v[:4] in ENUM_PREFIX:
                    node.inp(k).ptype = T("byte", f"Enum'/Script/Engine.EngineTypes:{ENUM_PREFIX[v[:4]]}'")
        return node

    # --- pure helpers -----------------------------------------------------------------------
    def pure(me, cls, fn, out="ReturnValue", **ins):
        x, y = me._xy(True)
        n = me.g.call(cls, fn, x=x, y=y)
        me._apply(n, ins)
        return n.out(out) if out else n

    def purenode(me, cls, fn, **ins):
        return me.pure(cls, fn, out=None, **ins)

    def is_store(me, name, cls=None):
        return me.real_vars is not None and cls is None and name not in me.real_vars

    def store(me, name):
        if name not in me._stores:
            typ = me.vars.get(name)
            if typ is None:
                raise KeyError(f"type of store variable {name} unknown: pass typ= on first use")
            row, x = me._row, me._x
            me._row, me._x = 99 + len(me._stores), 0
            fl = me.custom(f"Set_{name}", [(name, typ)])
            me._row, me._x = row, x
            me._stores[name] = fl.node
        return me._stores[name]

    def var(me, name, typ=None, cls=None):
        if typ and not cls:
            me.vars.setdefault(name, typ)
        if me.is_store(name, cls):
            pin = me.store(name).out(name)
            pin.ptype = me.vars.get(name)
            return pin
        x, y = me._xy(True)
        n = me.g.get(name, x=x, y=y, cls=cls)
        if cls:
            n.inp("self")
        o = n.out(name)
        o.ptype = me.vars.get(name) or GLOBAL_TYPES.get(name)
        return o

    def member(me, name, typ=None):
        """Inherited/own member (component or native property) on self, e.g. Mesh, CharacterMovement."""
        x, y = me._xy(True)
        n = me.g.get(name, x=x, y=y)
        o = n.out(name)
        o.ptype = typ or (OBJ(MEMBER_TYPES[name]) if name in MEMBER_TYPES else None)
        return o

    def var_of(me, target, name, cls):
        x, y = me._xy(True)
        n = me.g.get(name, x=x, y=y, cls=cls)
        me.g.link(target, n.inp("self"))
        n.inp("self").ptype = OBJ(cls)
        o = n.out(name)
        o.ptype = GLOBAL_TYPES.get(name) or (OBJ(MEMBER_TYPES[name]) if name in MEMBER_TYPES else None)
        return o

    def self_(me):
        x, y = me._xy(True)
        return me.g.self_ref(x, y).out("self")

    def make_array(me, items, elem=None):
        x, y = me._xy(True)
        n = me.g.node("K2Node_MakeArray", [("NumInputs", str(len(items)))], x, y)
        elem = elem or next((t for t in map(type_of_value, items) if t), None)
        me._apply(n, {f"[{i}]": v for i, v in enumerate(items)})
        for i in range(len(items)):
            n.inp(f"[{i}]").ptype = elem
        o = n.out("Array")
        o.ptype = arr_of(elem)
        return o

    def arr(me, fn, out="ReturnValue", **ins):
        x, y = me._xy(True)
        n = me.g.node("K2Node_CallArrayFunction",
                        [("FunctionReference", f"(MemberParentClass=Class'{ARR}',MemberName=\"{fn}\")")], x, y)
        me._apply(n, ins)
        type_array_node(n, ins)
        return n.out(out) if out else n

    # math sugar
    def m(me, fn, **ins):
        return me.pure(MATH, fn, **ins)

    # --- entry points -----------------------------------------------------------------------
    def event(me, fn, cls):
        me.newrow()
        x, y = me._xy()
        n = me.g.event(fn, cls, x, y)
        return Flow(me, n.out("then"), n)

    def custom(me, name, params=()):
        """params: [(name, PinType-literal)], e.g. ("Target", OBJ(ACTOR))."""
        me.newrow()
        x, y = me._xy()
        props = [("CustomFunctionName", f'"{name}"')]
        EVENT_SIGS[name] = dict(params)
        for i, (pn, pt) in enumerate(params):
            props.append(("CustomProperties UserDefinedPin", user_pin(pn, pt)))
        n = me.g.node("K2Node_CustomEvent", props, x, y)
        for pn, pt in params:
            n.out(pn).ptype = pt
        return Flow(me, n.out("then"), n)

    def text(me):
        return me.g.text()


def T(cat, sub=None, array=False):
    s = f'PinCategory="{cat}"'
    if sub:
        s += f",PinSubCategoryObject={sub}"
    if array:
        s += ",bIsArray=True"
    return f"({s})"


def OBJ(cls, array=False):
    return T("object", cls_ref(cls), array)


FLOAT, INT, BOOL = T("float"), T("int"), T("bool")
VEC = T("struct", "ScriptStruct'/Script/CoreUObject.Object:Vector'")


class Flow:
    """An exec cursor."""

    def __init__(me, bp, pin, node=None):
        me.bp, me.pin, me.node = bp, pin, node

    def p(me, name):
        """Output data pin of the node this flow started from (event params)."""
        return me.node.out(name)

    def _exec(me, node, inpin="execute", outpin="then"):
        if me.pin is not None:
            me.bp.g.link(me.pin, node.inp(inpin))
        me.pin = node.out(outpin)
        return node

    def call(me, cls, fn, target=None, **ins):
        x, y = me.bp._xy()
        n = me.bp.g.call(cls, fn, x=x, y=y)
        if fn in ("GetAllActorsOfClass", "SphereOverlapActors_DEPRECATED"):
            n.out("OutActors").ptype = OBJ(ACTOR, True)
        if target is not None:
            me.bp.g.link(target, n.inp("self"))
        me.bp._apply(n, ins)
        return me._exec(n)

    def callself(me, fn, **ins):
        x, y = me.bp._xy()
        n = me.bp.g.call(None, fn, x=x, y=y)
        me.bp._apply(n, ins)
        return me._exec(n)

    def arr(me, fn, **ins):
        x, y = me.bp._xy()
        n = me.bp.g.node("K2Node_CallArrayFunction",
                           [("FunctionReference", f"(MemberParentClass=Class'{ARR}',MemberName=\"{fn}\")")], x, y)
        me.bp._apply(n, ins)
        type_array_node(n, ins)
        return me._exec(n)

    def set(me, name, value, typ=None, cls=None, target=None):
        if typ and not cls:
            me.bp.vars.setdefault(name, typ)
        if target is None and me.bp.is_store(name, cls):
            me.bp.store(name)
            return me.callself(f"Set_{name}", **{name: value})
        x, y = me.bp._xy()
        n = me.bp.g.set(name, x=x, y=y, cls=cls)
        if target is not None:
            me.bp.g.link(target, n.inp("self"))
        me.bp._apply(n, {name: value})
        n.inp(name).ptype = n.inp(name).ptype or typ or GLOBAL_TYPES.get(name) or me.bp.vars.get(name)
        if target is not None and cls:
            n.inp("self").ptype = OBJ(cls)
        return me._exec(n)

    def delay(me, seconds):
        return me.call(KSL, "Delay", Duration=seconds)

    def branch(me, cond):
        x, y = me.bp._xy()
        n = me.bp.g.branch(x, y)
        me.bp._apply(n, {"Condition": cond})
        me._exec(n, outpin="then")
        t = Flow(me.bp, n.out("then"))
        e = Flow(me.bp, n.out("else"))
        me.pin = None
        return t, e

    def seq(me, n_out=2):
        x, y = me.bp._xy()
        n = me.bp.g.seq(x, y)
        me._exec(n, outpin="then_0")
        outs = [Flow(me.bp, n.out(f"then_{i}")) for i in range(n_out)]
        me.pin = None
        return outs

    def foreach(me, array_pin, elem=None):
        x, y = me.bp._xy()
        n = me.bp.g.macro("ForEachLoop", x, y)
        me.bp.g.link(array_pin, n.inp("Array"))
        at = arr_of(elem) if elem else (array_pin.ptype or OBJ(ACTOR, True))
        n.inp("Array").ptype = at
        n.out("Array Element").ptype = elem_of(at)
        n.props.append(("ResolvedWildcardType", elem_of(at)))
        me._exec(n, inpin="Exec", outpin="Completed")
        body = Flow(me.bp, n.out("LoopBody"))
        return body, n.out("Array Element"), n.out("Array Index")

    def whileloop(me, cond):
        x, y = me.bp._xy()
        n = me.bp.g.macro("WhileLoop", x, y)
        me.bp._apply(n, {"Condition": cond})
        me._exec(n, inpin="execute", outpin="Completed")
        return Flow(me.bp, n.out("LoopBody"))

    def spawn(me, cls_path, transform_pin, **ins):
        """SpawnActorFromClass. Returns the node (ReturnValue = the spawned actor)."""
        x, y = me.bp._xy()
        n = me.bp.g.node("K2Node_SpawnActorFromClass", [], x, y)
        n.inp("Class").default_obj = cls_ref(cls_path)
        n.inp("Class").ptype = T("class", cls_ref(ACTOR))
        n.inp("SpawnTransform").ptype = T("struct", "ScriptStruct'/Script/CoreUObject.Object:Transform'")
        if hasattr(transform_pin, "ptype"):
            transform_pin.ptype = n.inp("SpawnTransform").ptype
        n.out("ReturnValue").ptype = OBJ(cls_path)
        if "bNoCollisionFail" in ins:
            ins["SpawnEvenIfColliding"] = ins.pop("bNoCollisionFail")
        me.bp.g.link(transform_pin, n.inp("SpawnTransform"))
        me.bp._apply(n, ins)
        return me._exec(n)

    def cast(me, cls, obj_pin):
        """Dynamic cast (exec node in 4.5). Returns (ok_flow, fail_flow, as_pin)."""
        x, y = me.bp._xy()
        n = me.bp.g.cast(cls, x, y)
        me.bp.g.link(obj_pin, n.inp("Object"))
        me._exec(n)
        ok = Flow(me.bp, n.out("then"))
        bad = Flow(me.bp, n.out("CastFailed"))
        me.pin = None
        o = n.out(cast_pin_name(cls))
        o.ptype = OBJ(cls)
        return ok, bad, o

    def end(me):
        me.pin = None


# Output pin name of K2Node_DynamicCast. UE4.5: "As" + the class display name. Verified names go here.
CAST_PIN_OVERRIDES = {}


def cast_pin_name(cls):
    if cls in CAST_PIN_OVERRIDES:
        return CAST_PIN_OVERRIDES[cls]
    return "As" + cls.split(".")[-1]     # verified 2026-10-09: AsCharacter, AsBP_WaWZombie_C


def type_array_node(n, ins):
    """Resolve KismetArrayLibrary wildcard pins from the TargetArray link (pins don't propagate on paste)."""
    ta = ins.get("TargetArray")
    at = ta.ptype if isinstance(ta, Pin) else None
    if not at:
        return
    n.inp("TargetArray").ptype = at
    et = elem_of(at)
    for nm in ("NewItem", "Item", "ItemToFind"):
        if nm in n.pins:
            n.pins[nm].ptype = et
            if et and '"object"' in et and n.pins[nm].default is None:
                n.pins[nm].default = ""     # clear the int placeholder's autogenerated "0"
    if n.props and "Array_Get" in n.props[0][1]:
        n.out("Item").ptype = et


def user_pin(name, ptype):
    """UE4.5 K2Node_EditablePinBase custom export: Name=.. IsArray=.. IsReference=.. Category=.. [SubCategoryObject=..]"""
    import re
    cat = re.search(r'PinCategory="([^"]*)"', ptype).group(1)
    sub = re.search(r"PinSubCategoryObject=([^,)]+'[^']*')", ptype)
    arr = 1 if "bIsArray=True" in ptype else 0
    out = f"Name={name} IsArray={arr} IsReference=0 Category={cat}"
    if sub:
        out += " SubCategoryObject=" + sub.group(1).split("'")[1]
    return out
