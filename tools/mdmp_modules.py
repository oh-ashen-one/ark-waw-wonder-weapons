"""List module base/size/name from a Windows minidump. Usage: python3 -I mdmp_modules.py <dmp> [name-filter]"""
import struct, sys
b = open(sys.argv[1], 'rb').read(); flt = sys.argv[2].lower() if len(sys.argv) > 2 else ''
assert b[:4] == b'MDMP'
nstreams, rva_dir = struct.unpack_from('<II', b, 8)
for i in range(nstreams):
    stype, size, rva = struct.unpack_from('<III', b, rva_dir + 12 * i)
    if stype == 4:  # ModuleListStream
        n = struct.unpack_from('<I', b, rva)[0]
        for j in range(n):
            m = rva + 4 + 108 * j
            base, msize = struct.unpack_from('<QI', b, m)
            name_rva = struct.unpack_from('<I', b, m + 20)[0]
            ln = struct.unpack_from('<I', b, name_rva)[0]
            name = b[name_rva + 4:name_rva + 4 + ln].decode('utf-16-le')
            if flt in name.lower(): print(f"{base:#x} {msize:#x} {name}")
