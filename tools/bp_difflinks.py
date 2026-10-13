"""bp_difflinks.py <generated.txt> [live.txt] : list pins whose links were dropped by the editor on paste."""
import re, sys
def parse(path):
    t = open(path).read(); nodes = {}
    for b in re.split(r'(?m)^Begin Object Class=', t)[1:]:
        name = b.split('"')[1]
        fn = re.search(r'MemberName="([^"]+)"', b) or re.search(r'CustomFunctionName="([^"]+)"', b)
        fn = fn.group(1) if fn else b.split(' ')[0]
        nodes[name] = (fn, {m.group(1): (len(re.findall('LinkedTo', m.group(2))), re.search(r'PinType=\(([^)]*)\)', m.group(2)))
                            for m in re.finditer(r'PinName="([^"]+)"(.*?)End Object', b, re.S)})
    return nodes
g = parse(sys.argv[1]); l = parse(sys.argv[2] if len(sys.argv) > 2 else "/Users/YOU/ark-mashup/.work/refl/live.txt")
for n, (fn, pins) in g.items():
    for p, (c, gt) in pins.items():
        lc = l.get(n, (0, {}))[1].get(p, (None, None))
        if lc[0] is None or lc[0] < c:
            print(fn, p, c, lc[0], "gen:", gt.group(1)[:90] if gt else None, "| live:", lc[1].group(1)[:90] if lc[1] else None)
