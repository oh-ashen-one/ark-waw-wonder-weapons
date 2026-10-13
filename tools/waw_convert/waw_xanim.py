#!/usr/bin/env python3
"""Parser for OpenAssetTools "compiled xanim" files (CoD4/IW3 + CoD:WaW/T4 raw
XAnim binary, version 17), as written by OAT's Unlinker (CompiledXAnimWriter.cpp).

Layout (little endian), mirrors OAT ObjLoading/XAnim/CompiledXAnimLoader.cpp:
  u16 version(=17) | u16 numFramesField | u16 boneCount | u8 flags | u8 assetType | u16 fps
  [delta track if flags&2]
  flipQuat bitmask (ceil(boneCount/8) bytes) | halfQuat bitmask (same size)
  boneCount x cstring bone name
  per bone: quat track, trans track
  u8 notifyCount ; per notify: cstring name, u16 frame

No game data lives in this file; it only decodes the container.

Provenance / licence note: the byte layout, the 0x3FFF0001 quaternion normaliser and the
trans-size scale constants were taken from reading OpenAssetTools' CompiledXAnimLoader.cpp
(https://github.com/Laupetin/OpenAssetTools, tag v0.33.0, GPL-3.0).  This is an independent
Python re-implementation of that file format (no code copied), but it follows the loader step by
step; treat it as GPL-3.0-compatible when deciding where to publish it.
Pure python 3 (stdlib only).  Public API: parse_xanim(path_or_bytes) -> Xanim
"""
import math
import struct

Q_SCALE = 32767.0                       # 0x3FFF0001 == 32767**2
HALF_TRANS_SIZE_SCALE = 0.003921568859368563    # ~1/255   (u8 trans)
FULL_TRANS_SIZE_SCALE = 0.00001525902189314365  # ~1/65535 (u16 trans)

FLAG_LOOPED = 0x1
FLAG_DELTA = 0x2


class Reader:
    def __init__(self, b):
        self.b = b
        self.o = 0

    def u8(self):
        v = self.b[self.o]
        self.o += 1
        return v

    def u16(self):
        v = struct.unpack_from('<H', self.b, self.o)[0]
        self.o += 2
        return v

    def i16(self):
        v = struct.unpack_from('<h', self.b, self.o)[0]
        self.o += 2
        return v

    def f32(self):
        v = struct.unpack_from('<f', self.b, self.o)[0]
        self.o += 4
        return v

    def cstr(self):
        e = self.b.index(b'\0', self.o)
        s = self.b[self.o:e].decode('ascii', 'replace')
        self.o = e + 1
        return s

    def raw(self, n):
        v = self.b[self.o:self.o + n]
        self.o += n
        return v


def _w_from_xyz(x, y, z):
    t = 0x3FFF0001 - (x * x + y * y + z * z)
    if t <= 0:
        t = 0
    else:
        t = int(math.floor(math.sqrt(float(t)) + 0.5))
    return t


def _consume_quat(r):
    x, y, z = r.i16(), r.i16(), r.i16()
    return [x, y, z, _w_from_xyz(x, y, z)]


def _consume_quat2(r):
    z = r.i16()
    t = 0x3FFF0001 - z * z
    w = 0 if t <= 0 else int(math.floor(math.sqrt(float(t)) + 0.5))
    return [0, 0, z, w]          # half quat == rotation about Z only (x=y=0)


def _flip(q):
    return [-c for c in q]


def _dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def _indices(r, n, use_byte, num_loop_frames):
    if n >= num_loop_frames:
        return list(range(n))
    if use_byte:
        return [r.u8() for _ in range(n)]
    return [r.u16() for _ in range(n)]


def _read_quat_track(r, nlf, use_byte, flip, half):
    n = r.u16()
    if n == 0:
        return None                       # NO_QUAT
    if n == 1:
        q = _consume_quat2(r) if half else _consume_quat(r)
        if flip:
            q = _flip(q)
        return {'idx': [0], 'q': [q]}
    idx = _indices(r, n, use_byte, nlf)
    out = []
    for i in range(n):
        q = _consume_quat2(r) if half else _consume_quat(r)
        if i > 0:
            if _dot(out[i - 1], q) < 0:
                q = _flip(q)
        elif flip:
            q = _flip(q)
        out.append(q)
    return {'idx': idx, 'q': out}


def _read_trans_track(r, nlf, use_byte):
    n = r.u16()
    if n == 0:
        return None                       # NO_TRANS
    if n == 1:
        return {'idx': [0], 't': [[r.f32(), r.f32(), r.f32()]]}
    idx = _indices(r, n, use_byte, nlf)
    small = r.u8() != 0
    mins = [r.f32() for _ in range(3)]
    sc = HALF_TRANS_SIZE_SCALE if small else FULL_TRANS_SIZE_SCALE
    size = [r.f32() * sc for _ in range(3)]
    t = []
    for _ in range(n):
        if small:
            v = [r.u8(), r.u8(), r.u8()]
        else:
            v = [r.u16(), r.u16(), r.u16()]
        t.append([mins[k] + size[k] * v[k] for k in range(3)])
    return {'idx': idx, 't': t}


class Xanim:
    pass


def parse_xanim(src):
    b = open(src, 'rb').read() if isinstance(src, str) else bytes(src)
    r = Reader(b)
    a = Xanim()
    a.version = r.u16()
    if a.version != 17:
        raise ValueError('unsupported xanim version %d (expected 17: IW3/T4)' % a.version)
    stored = r.u16()
    bone_count = r.u16()
    a.flags = r.u8()
    a.asset_type = r.u8()
    a.fps = r.u16()
    a.looped = bool(a.flags & FLAG_LOOPED)
    a.has_delta = bool(a.flags & FLAG_DELTA)
    nlf = stored + 1 if a.looped else stored          # number of keyable frames (0..num_frames)
    a.num_frames = nlf - 1                              # duration = num_frames / fps
    use_byte = a.num_frames < 256
    a.delta = None
    if a.has_delta:
        # IW3/T4 delta: 2D (yaw-only) quat track + trans track (root motion).
        dq = None
        n = r.u16()
        if n == 1:
            dq = {'idx': [0], 'q': [_consume_quat2(r)]}
        elif n > 1:
            idx = _indices(r, n, use_byte, nlf)
            qs = []
            for i in range(n):
                q = _consume_quat2(r)
                if i > 0 and _dot(qs[i - 1], q) < 0:
                    q = _flip(q)
                qs.append(q)
            dq = {'idx': idx, 'q': qs}
        dt = _read_trans_track(r, nlf, use_byte)
        a.delta = {'quat': dq, 'trans': dt}
    a.bones = []
    if bone_count:
        bm = (bone_count + 7) // 8
        flip = r.raw(bm)
        half = r.raw(bm)
        names = [r.cstr() for _ in range(bone_count)]
        for i, nm in enumerate(names):
            f = bool(flip[i // 8] & (1 << (i % 8)))
            h = bool(half[i // 8] & (1 << (i % 8)))
            q = _read_quat_track(r, nlf, use_byte, f, h)
            t = _read_trans_track(r, nlf, use_byte)
            a.bones.append({'name': nm, 'quat': q, 'trans': t, 'half': h})
    ncount = r.u8()
    a.notes = []
    for _ in range(ncount):
        nm = r.cstr()
        fr = r.u16()
        a.notes.append({'name': nm, 'frame': fr,
                        'time': (fr / a.num_frames) if a.num_frames else 0.0})
    a.trailing = len(b) - r.o
    return a


def _normalize(q):
    n = math.sqrt(sum(c * c for c in q)) or 1.0
    return [c / n for c in q]


def _slerp(a, b, t):
    d = _dot(a, b)
    if d < 0:
        b = _flip(b)
        d = -d
    if d > 0.9995:
        return _normalize([a[i] + (b[i] - a[i]) * t for i in range(4)])
    th = math.acos(max(-1.0, min(1.0, d)))
    s = math.sin(th)
    wa = math.sin((1 - t) * th) / s
    wb = math.sin(t * th) / s
    return _normalize([a[i] * wa + b[i] * wb for i in range(4)])


def sample_track(idx, vals, frame, kind):
    """Sample a keyed track at integer/float frame. kind: 'q' or 't'."""
    if frame <= idx[0]:
        return vals[0]
    if frame >= idx[-1]:
        return vals[-1]
    # idx is ascending
    lo, hi = 0, len(idx) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if idx[mid] <= frame:
            lo = mid
        else:
            hi = mid
    f0, f1 = idx[lo], idx[hi]
    t = (frame - f0) / float(f1 - f0)
    if kind == 'q':
        return _slerp(_normalize(vals[lo]), _normalize(vals[hi]), t)
    return [vals[lo][k] + (vals[hi][k] - vals[lo][k]) * t for k in range(3)]


def bake(anim):
    """Return per-bone dense sample lists for frames 0..num_frames.
    -> {name: {'q': [[x,y,z,w]*N] or None, 't': [[x,y,z]*N] or None}}
    Quaternion order is (x, y, z, w), unit length, WaW (right-handed, Z-up) space.
    A None track means the bone is not keyed for that channel (use bind pose)."""
    out = {}
    n = anim.num_frames + 1
    for b in anim.bones:
        q = t = None
        if b['quat'] is not None:
            tr = b['quat']
            q = [_normalize(sample_track(tr['idx'], tr['q'], f, 'q')) for f in range(n)]
            # make the sequence sign-continuous
            for i in range(1, n):
                if _dot(q[i - 1], q[i]) < 0:
                    q[i] = _flip(q[i])
        if b['trans'] is not None:
            tr = b['trans']
            t = [sample_track(tr['idx'], tr['t'], f, 't') for f in range(n)]
        out[b['name']] = {'q': q, 't': t}
    return out


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        a = parse_xanim(p)
        print('%s: v%d frames=%d fps=%d looped=%s delta=%s bones=%d notes=%s trailing=%d' % (
            p, a.version, a.num_frames, a.fps, a.looped, a.has_delta, len(a.bones),
            [(n['name'], n['frame']) for n in a.notes], a.trailing))
