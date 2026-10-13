"""Probe UFUNCTION signatures in the open Blueprint graph (ARK DevKit editor under Wine).

Pastes one call node per "Class:Function", selects all, copies back and prints each node's resolved pins.
The graph must be a scratch graph: everything in it is deleted afterwards.
Usage: python3 tools/bp_probe.py /Script/ShooterGame.PrimalCharacter:GetHealth ...
"""
import re
import subprocess
import sys
import time

sys.path.insert(0, "/Users/YOU/ark-mashup/tools")
from bpgen import Graph  # noqa: E402

INP = "/Users/YOU/ark-mashup/.work/inp"


def inp(*a):
    subprocess.run([INP, *a], check=False)


def wait_idle(timeout=180):
    """Wait while an editor progress window (about 510x110, e.g. 'Rebuilding Class Hierarchy') is up."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        out = subprocess.run(["/Users/YOU/ark-mashup/.work/winid", "UE4Editor.exe"], capture_output=True, text=True).stdout
        busy = any(len(l.split()) >= 5 and l.split()[3] == "510" and l.split()[4] == "110" and l.split()[1] != "12"
                   for l in out.splitlines())
        if not busy:
            return
        time.sleep(2)


def probe(specs, gx=700, gy=700):
    g = Graph(0, 0)
    for i, s in enumerate(specs):
        cls, fn = s.rsplit(":", 1)
        g.call(cls, fn, x=(i % 6) * 350, y=(i // 6) * 300)
    inp("click", str(gx), str(gy)); time.sleep(0.3)
    inp("key", "a", "ctrl"); inp("key", "forwarddelete"); time.sleep(2)
    g.to_clipboard(); time.sleep(4); inp("click", "700", "140"); time.sleep(1)
    inp("click", str(gx), str(gy)); inp("key", "v", "ctrl"); time.sleep(3); wait_idle(); time.sleep(1)
    subprocess.run("pbcopy < /dev/null", shell=True)
    inp("click", str(gx), str(gy)); time.sleep(0.2)
    inp("key", "a", "ctrl"); time.sleep(0.3); inp("key", "c", "ctrl"); time.sleep(3); wait_idle()
    txt = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    inp("key", "forwarddelete")
    out = []
    for blk in re.split(r"(?m)^Begin Object Class=K2Node", txt)[1:]:
        fr = re.search(r'MemberName="([^"]+)"', blk)
        pins = []
        for m in re.finditer(r'PinName="([^"]+)"(.*?)End Object', blk, re.S):
            body = m.group(2)
            d = "out" if "EGPD_Output" in body else "in"
            cat = re.search(r'PinCategory="([^"]*)"', body)
            sub = re.search(r"PinSubCategoryObject=([^,)]+)", body)
            arr = " []" if "bIsArray=True" in body else ""
            ref = " &" if "bIsReference=True" in body else ""
            hid = " (hidden)" if "bHidden=True" in body else ""
            pins.append(f"{d}:{m.group(1)}:{cat.group(1) if cat else '?'}{('/' + sub.group(1).split('.')[-1]) if sub else ''}{arr}{ref}{hid}")
        out.append((fr.group(1) if fr else "?", pins))
    return out, txt


if __name__ == "__main__":
    import json, os
    res, raw = probe(sys.argv[1:])
    pj = "/Users/YOU/ark-mashup/.work/refl/pins.json"
    db = json.load(open(pj)) if os.path.exists(pj) else {}
    want = {a.rsplit(":", 1)[1] for a in sys.argv[1:]}
    for name, pins in res:
        if name in want and pins:
            db[name] = pins
    json.dump(db, open(pj, "w"), indent=1)
    for name, pins in res:
        print(name, "->", ", ".join(pins) if pins else "(NO PINS: unresolved)")
