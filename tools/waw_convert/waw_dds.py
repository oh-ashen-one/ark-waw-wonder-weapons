#!/usr/bin/env python3
"""Minimal DDS (DXT1 / DXT3 / DXT5) top-mip decoder + PNG writer.  numpy + stdlib only.
WaW weapon textures are all DXT1 or DXT5.  No game data in this file.
  python3 waw_dds.py in.dds out.png
"""
import struct
import sys
import zlib

import numpy as np


def _rgb565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, g, b], axis=-1).astype(np.int32)


def _color_block(blk, dxt1):
    """blk: (n, 8) uint8 -> (n, 16, 4) uint8 RGBA (alpha=255 except DXT1 transparent)."""
    c0 = blk[:, 0].astype(np.int32) | (blk[:, 1].astype(np.int32) << 8)
    c1 = blk[:, 2].astype(np.int32) | (blk[:, 3].astype(np.int32) << 8)
    p0, p1 = _rgb565(c0), _rgb565(c1)
    pal = np.zeros((len(blk), 4, 4), dtype=np.int32)
    pal[:, 0, :3], pal[:, 1, :3] = p0, p1
    four = (c0 > c1) if dxt1 else np.ones(len(blk), dtype=bool)
    pal[:, 2, :3] = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    pal[:, 3, :3] = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    pal[:, :, 3] = 255
    if dxt1:
        pal[:, 3, 3] = np.where(four, 255, 0)
    bits = (blk[:, 4].astype(np.uint32) | (blk[:, 5].astype(np.uint32) << 8) |
            (blk[:, 6].astype(np.uint32) << 16) | (blk[:, 7].astype(np.uint32) << 24))
    idx = np.stack([(bits >> (2 * i)) & 3 for i in range(16)], axis=1).astype(np.int64)
    return np.take_along_axis(pal, idx[:, :, None].repeat(4, axis=2), axis=1)


def _alpha_block5(blk):
    a0 = blk[:, 0].astype(np.int32)
    a1 = blk[:, 1].astype(np.int32)
    pal = np.zeros((len(blk), 8), dtype=np.int32)
    pal[:, 0], pal[:, 1] = a0, a1
    gt = a0 > a1
    for i in range(1, 7):
        pal[:, i + 1] = np.where(gt, ((7 - i) * a0 + i * a1) // 7,
                                 np.where(i <= 4, ((5 - i) * a0 + i * a1) // 5, 0))
    pal[:, 6] = np.where(gt, pal[:, 6], 0)
    pal[:, 7] = np.where(gt, pal[:, 7], 255)
    bits = np.zeros(len(blk), dtype=np.uint64)
    for i in range(6):
        bits |= blk[:, 2 + i].astype(np.uint64) << np.uint64(8 * i)
    idx = np.stack([((bits >> np.uint64(3 * i)) & np.uint64(7)) for i in range(16)], axis=1).astype(np.int64)
    return np.take_along_axis(pal, idx, axis=1)


def _alpha_block3(blk):
    out = np.zeros((len(blk), 16), dtype=np.int32)
    for i in range(16):
        byte = blk[:, i // 2].astype(np.int32)
        v = (byte >> (4 * (i % 2))) & 15
        out[:, i] = v * 17
    return out


def decode_dds(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'DDS ', 'not a DDS'
    h, w = struct.unpack_from('<II', b, 12)
    fourcc = b[84:88]
    data = np.frombuffer(b, dtype=np.uint8, offset=128)
    bw, bh = (w + 3) // 4, (h + 3) // 4
    if fourcc == b'DXT1':
        blk = data[:bw * bh * 8].reshape(-1, 8)
        px = _color_block(blk, True)
    elif fourcc in (b'DXT3', b'DXT5'):
        blk = data[:bw * bh * 16].reshape(-1, 16)
        px = _color_block(blk[:, 8:], False)
        px[:, :, 3] = _alpha_block5(blk[:, :8]) if fourcc == b'DXT5' else _alpha_block3(blk[:, :8])
    else:
        raise ValueError('unsupported DDS fourcc %r' % fourcc)
    px = px.reshape(bh, bw, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)
    return np.clip(px[:h, :w], 0, 255).astype(np.uint8)


def write_png(path, rgba):
    h, w, c = rgba.shape
    raw = b''.join(b'\x00' + rgba[y].tobytes() for y in range(h))

    def chunk(t, d):
        c_ = struct.pack('>I', len(d)) + t + d
        return c_ + struct.pack('>I', zlib.crc32(t + d) & 0xFFFFFFFF)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + \
        chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
    open(path, 'wb').write(png)


if __name__ == '__main__':
    write_png(sys.argv[2], decode_dds(sys.argv[1]))
