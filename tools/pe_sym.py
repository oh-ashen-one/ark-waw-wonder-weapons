"""Map absolute crash addresses to the nearest preceding exported symbol of a PE DLL (assumes preferred ImageBase).
Usage: python3 -I pe_sym.py <dll> <addr> [addr...]"""
import struct, sys, bisect
def read_pe(path):
    b = open(path, 'rb').read()
    pe = struct.unpack_from('<I', b, 0x3c)[0]
    nsec = struct.unpack_from('<H', b, pe + 6)[0]; optsz = struct.unpack_from('<H', b, pe + 20)[0]
    opt = pe + 24; magic = struct.unpack_from('<H', b, opt)[0]; assert magic == 0x20b
    base = struct.unpack_from('<Q', b, opt + 24)[0]; size = struct.unpack_from('<I', b, opt + 56)[0]
    exp_rva, exp_sz = struct.unpack_from('<II', b, opt + 112)
    secs = []
    for i in range(nsec):
        s = pe + 24 + optsz + 40 * i
        va, vs, raw_sz, raw = struct.unpack_from('<IIII', b, s + 12)[:4][0], struct.unpack_from('<I', b, s + 8)[0], struct.unpack_from('<I', b, s + 16)[0], struct.unpack_from('<I', b, s + 20)[0]
        secs.append((struct.unpack_from('<I', b, s + 12)[0], struct.unpack_from('<I', b, s + 8)[0], raw))
    def off(rva):
        for va, vs, raw in secs:
            if va <= rva < va + max(vs, 1): return rva - va + raw
        raise ValueError(hex(rva))
    e = off(exp_rva)
    nfun, nnames, afun, aname, aord = struct.unpack_from('<IIIII', b, e + 20)
    funcs = [struct.unpack_from('<I', b, off(afun) + 4 * i)[0] for i in range(nfun)]
    syms = []
    for i in range(nnames):
        nrva = struct.unpack_from('<I', b, off(aname) + 4 * i)[0]; o = struct.unpack_from('<H', b, off(aord) + 2 * i)[0]
        n = b[off(nrva):b.index(b'\0', off(nrva))].decode('latin-1'); syms.append((funcs[o], n))
    syms.sort()
    return base, size, syms
dll = sys.argv[1]; base, size, syms = read_pe(dll)
if sys.argv[2].startswith('base='): base = int(sys.argv[2][5:], 16); sys.argv.pop(2); keys = [s[0] for s in syms]
print(f"{dll.split('/')[-1]} ImageBase={base:#x} SizeOfImage={size:#x} exports={len(syms)}")
for a in sys.argv[2:]:
    rva = int(a, 16) - base
    if not 0 <= rva < size: print(a, "outside preferred image (relocated?)"); continue
    i = bisect.bisect_right(keys, rva) - 1
    print(a, f"rva={rva:#x}", f"{syms[i][1]} +{rva - syms[i][0]:#x}" if i >= 0 else "?")
