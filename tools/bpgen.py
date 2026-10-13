"""Generate UE4.5 (ARK DevKit) Blueprint graph text for clipboard paste (Ctrl+V in a graph).

Format learned by round-tripping nodes through the editor (2026-10-08): nodes are K2Node_* objects with
EdGraphPin subobjects; links are `LinkedTo(i)=EdGraphPin'<Node>.<Pin>'`. On paste the editor reconstructs
every node, so only pins that carry a link or a default need to be written.

    g = Graph()
    ev = g.event("ReceiveBeginPlay", "/Script/Engine.Actor")
    pr = g.call("/Script/Engine.KismetSystemLibrary", "PrintString", InString="hi")
    g.link(ev["then"], pr["execute"])
    print(g.text())
"""
import itertools
import subprocess

import random as _rnd
_pid = itertools.count(_rnd.randrange(10_000_000, 90_000_000) * 10)
STD_MACROS = "/Engine/EditorBlueprintResources/StandardMacros.StandardMacros"
MACRO_GUIDS = {"ForEachLoop": "99DBFD5540A796041F72A5A9DA655026"}


class Pin:
    def __init__(self, node, name, out, cat=None, sub=None, default=None):
        self.node, self.name, self.out, self.cat, self.sub, self.default = node, name, out, cat, sub, default
        self.obj = f"EdGraphPin_{next(_pid)}"
        self.links = []
        self.default_obj = None
        self.ptype = None   # explicit PinType literal, e.g. (PinCategory="int")


class Node:
    def __init__(self, g, cls, props, x, y):
        self.g, self.cls, self.props, self.x, self.y = g, cls, props, x, y
        self.name = f"{cls}_{next(g._nid)}"
        self.pins = {}

    def pin(self, name, out=None, cat=None, sub=None, default=None):
        if name not in self.pins:
            if out is None:
                out = name in OUT_PIN_NAMES or name.startswith("then") or name.startswith("As ")
            self.pins[name] = Pin(self, name, out, cat, sub, default)
        p = self.pins[name]
        if default is not None:
            p.default = default
        if cat is not None:
            p.cat = cat
        return p

    def __getitem__(self, name):
        return self.pin(name)

    def out(self, name, cat=None, sub=None):
        return self.pin(name, out=True, cat=cat, sub=sub)

    def inp(self, name, cat=None, sub=None, default=None):
        return self.pin(name, out=False, cat=cat, sub=sub, default=default)

    def text(self):
        fn = next((v.split('MemberName="')[1].split('"')[0] for k, v in self.props if k == "FunctionReference"), None)
        if fn:
            for p in self.pins.values():
                if not p.ptype and not p.cat:
                    p.ptype = sig_ptype(fn, p.name)
        L = [f'Begin Object Class={self.cls} Name="{self.name}"']
        pins = list(self.pins.values())
        for p in pins:
            L += [f'   Begin Object Class=EdGraphPin Name="{p.obj}"', "   End Object"]
        for p in pins:
            L.append(f'   Begin Object Name="{p.obj}"')
            L.append(f'      PinName="{p.name}"')
            if p.out:
                L.append("      Direction=EGPD_Output")
            cat = p.cat or ("exec" if p.name in EXEC_PIN_NAMES or p.name.startswith("then") else "")
            if p.ptype:
                L.append(f"      PinType={p.ptype}")
            elif cat:
                t = f'PinCategory="{cat}"'
                if p.sub:
                    t += f",PinSubCategoryObject={p.sub}"
                L.append(f"      PinType=({t})")
            if p.default is not None:
                L.append(f'      DefaultValue="{p.default}"')
            if p.default_obj is not None:
                L.append(f"      DefaultObject={p.default_obj}")
            for i, q in enumerate(p.links):
                L.append(f"      LinkedTo({i})=EdGraphPin'{q.node.name}.{q.obj}'")
            L.append("   End Object")
        for k, v in self.props:
            L.append(f"   {k} {v}" if k.startswith("CustomProperties") else f"   {k}={v}")
        for i, p in enumerate(pins):
            L.append(f"   Pins({i})=EdGraphPin'{p.obj}'")
        L += [f"   NodePosX={self.x}", f"   NodePosY={self.y}", "End Object"]
        return "\n".join(L)


EXEC_PIN_NAMES = {"execute", "then", "else", "exec", "Exec", "LoopBody", "Completed", "CastFailed", "Then"}
OUT_PIN_NAMES = {"then", "else", "ReturnValue", "LoopBody", "Completed", "Array Element", "Array Index",
                 "CastFailed", "Output_Get", "Then"}


import json as _json, os as _os
_SIG = {}
_sp = "/Users/YOU/ark-mashup/.work/refl/pins.json"
if _os.path.exists(_sp):
    _SIG = _json.load(open(_sp))
_STRUCTS = {"Object:Vector": "ScriptStruct'/Script/CoreUObject.Object:Vector'",
            "Object:Rotator": "ScriptStruct'/Script/CoreUObject.Object:Rotator'",
            "Object:Transform": "ScriptStruct'/Script/CoreUObject.Object:Transform'",
            "EngineTypes:HitResult": "ScriptStruct'/Script/Engine.EngineTypes:HitResult'",
            "Object:LinearColor": "ScriptStruct'/Script/CoreUObject.Object:LinearColor'"}


def sig_ptype(func, pin):
    """PinType literal for a function pin, from the editor-probed signatures (simple types only)."""
    for e in _SIG.get(func, []):
        d, name, rest = e.split(":", 2)
        if name != pin:
            continue
        cat = rest.split("/")[0].split(" ")[0]
        if cat in ("int", "float", "bool", "string", "name", "text", "byte"):
            return f'(PinCategory="{cat}")'
        if cat in ("object", "class") and "/" in rest:
            short = rest.split("/", 1)[1].split("'")[0]
            mod = ("CoreUObject" if short in ("Object", "Class") else
                   "AIModule" if short in ("AIController",) else
                   "ShooterGame" if short in ("PrimalCharacter", "ShooterWeapon", "VictoryCore", "ShooterCharacter",
                                              "PrimalDinoCharacter", "ShooterProjectile") else "Engine")
            arr = ",bIsArray=True" if "[]" in rest else ""
            return f'(PinCategory="{cat}",PinSubCategoryObject=Class\'/Script/{mod}.{short}\'{arr})'
        if cat == "struct":
            key = rest.split("/", 1)[1].split("'")[0]
            if key in _STRUCTS:
                return f'(PinCategory="struct",PinSubCategoryObject={_STRUCTS[key]})'
    return None


EVENT_SIGS = {}   # custom event name -> {param: PinType literal} (filled by bpc.BP.custom)


class Graph:
    def __init__(self, x0=0, y0=0):
        self.nodes = []
        self._nid = itertools.count(_rnd.randrange(100_000, 900_000) * 1000)
        self.cx, self.cy = x0, y0

    def _pos(self, x, y):
        if x is None:
            x, self.cx = self.cx, self.cx + 320
        return x, (self.cy if y is None else y)

    def node(self, cls, props=(), x=None, y=None):
        x, y = self._pos(x, y)
        n = Node(self, cls, list(props), x, y)
        self.nodes.append(n)
        return n

    def link(self, a, b):
        if not a.out and b.out:
            a, b = b, a
        a.links.append(b)
        b.links.append(a)

    def chain(self, *pairs):
        """chain(nodeA, nodeB, ...) links then->execute in order."""
        for a, b in zip(pairs, pairs[1:]):
            self.link(a.out("then"), b.inp("execute"))

    # ---- node helpers -------------------------------------------------------------------------
    def call(self, parent, func, x=None, y=None, pure=False, **defaults):
        ref = f"(MemberParentClass=Class'{parent}',MemberName=\"{func}\")" if parent else \
              f"(MemberName=\"{func}\",bSelfContext=True)"
        n = self.node("K2Node_CallFunction", [("FunctionReference", ref)], x, y)
        for k, v in defaults.items():
            n.inp(k, default=v)
        return n

    def event(self, func, parent, x=None, y=None):
        return self.node("K2Node_Event", [
            ("EventSignatureName", f'"{func}"'), ("EventSignatureClass", f"Class'{parent}'"),
            ("EventReference", f"(MemberParentClass=Class'{parent}',MemberName=\"{func}\")"),
            ("bOverrideFunction", "True")], x, y)

    def custom_event(self, name, x=None, y=None):
        return self.node("K2Node_CustomEvent", [("CustomFunctionName", f'"{name}"')], x, y)

    def branch(self, x=None, y=None):
        return self.node("K2Node_IfThenElse", [], x, y)

    def seq(self, x=None, y=None):
        return self.node("K2Node_ExecutionSequence", [], x, y)

    def get(self, var, x=None, y=None, cls=None):
        ref = f"(MemberParentClass=Class'{cls}',MemberName=\"{var}\")" if cls else \
              f"(MemberName=\"{var}\",bSelfContext=True)"
        return self.node("K2Node_VariableGet", [("VariableReference", ref)], x, y)

    def set(self, var, x=None, y=None, cls=None):
        ref = f"(MemberParentClass=Class'{cls}',MemberName=\"{var}\")" if cls else \
              f"(MemberName=\"{var}\",bSelfContext=True)"
        return self.node("K2Node_VariableSet", [("VariableReference", ref)], x, y)

    def macro(self, name, x=None, y=None):
        guid = MACRO_GUIDS.get(name)
        g = f",GraphGuid={guid}" if guid else ""
        return self.node("K2Node_MacroInstance", [("MacroGraphReference",
            f"(MacroGraph=EdGraph'{STD_MACROS}:{name}',GraphBlueprint=Blueprint'{STD_MACROS}'{g})")], x, y)

    def cast(self, target_class, x=None, y=None):
        return self.node("K2Node_DynamicCast", [("TargetType", f"Class'{target_class}'")], x, y)

    def self_ref(self, x=None, y=None):
        return self.node("K2Node_Self", [], x, y)

    def propagate_types(self):
        """Give every data pin an explicit PinType: known node pins first, then copy types across links."""
        for n in self.nodes:
            for p in n.pins.values():
                if p.ptype or p.cat:
                    continue
                if n.cls == "K2Node_Self" and p.name == "self":
                    p.ptype = '(PinCategory="object",PinSubCategory="self")'
                elif n.cls == "K2Node_IfThenElse" and p.name == "Condition":
                    p.ptype = '(PinCategory="bool")'
                elif n.cls == "K2Node_DynamicCast" and p.name == "Object":
                    p.ptype = "(PinCategory=\"object\",PinSubCategoryObject=Class'/Script/CoreUObject.Object')"
                elif n.cls == "K2Node_MacroInstance" and p.name == "Array Index":
                    p.ptype = '(PinCategory="int")'
                elif n.cls == "K2Node_MacroInstance" and p.name == "Condition":
                    p.ptype = '(PinCategory="bool")'
        for n in self.nodes:   # function-signature types
            fn = next((v.split('MemberName="')[1].split('"')[0] for k, v in n.props if k == "FunctionReference"), None)
            if fn:
                for p in n.pins.values():
                    if not p.ptype and not p.cat:
                        p.ptype = sig_ptype(fn, p.name) or EVENT_SIGS.get(fn, {}).get(p.name)
        changed = True
        while changed:
            changed = False
            for n in self.nodes:
                for p in n.pins.values():
                    if p.ptype or p.cat in ("exec",) or p.name in ("execute", "then", "else") or p.name.startswith("then"):
                        continue
                    for q in p.links:
                        if q.ptype and '"self"' not in q.ptype:
                            p.ptype = q.ptype.replace(",bIsReference=True", "")
                            changed = True
                            break

    def check_impure(self):
        """A function whose probed signature has an exec pin must be wired into the exec chain."""
        bad = []
        for n in self.nodes:
            fn = next((v.split('MemberName="')[1].split('"')[0] for k, v in n.props if k == "FunctionReference"), None)
            if fn and any(e.startswith("in:execute:exec") for e in _SIG.get(fn, [])):
                ex = n.pins.get("execute")
                if not ex or not ex.links:
                    bad.append(fn)
        if bad:
            raise ValueError(f"impure functions used as pure (no exec link): {sorted(set(bad))}")

    def text(self):
        self.check_impure()
        self.propagate_types()
        return "\n".join(n.text() for n in self.nodes)

    def to_clipboard(self):
        subprocess.run(["pbcopy"], input=self.text().replace("\n", "\r\n").encode(), check=True)
