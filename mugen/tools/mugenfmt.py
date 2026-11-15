"""MUGEN file writers: SFF v2 (RLE8, 8-bit indexed) and SND v1.

Also contains a minimal SFF v2 reader used to verify the output round-trips.
"""
import struct


# ---------------------------------------------------------------- SFF v2 ---

def rle8_encode(pixels: bytes) -> bytes:
    """SFF v2 RLE8: a byte with top bits 01 (0x40-0x7F) is a run header
    (length = low 6 bits) followed by the color; any other byte is a literal."""
    out = bytearray()
    i, n = 0, len(pixels)
    while i < n:
        c = pixels[i]
        run = 1
        while i + run < n and pixels[i + run] == c and run < 63:
            run += 1
        if run > 1 or (c & 0xC0) == 0x40:
            out.append(0x40 | run)
            out.append(c)
        else:
            out.append(c)
        i += run
    return bytes(out)


def rle8_decode(data: bytes, size: int) -> bytes:
    out = bytearray()
    i = 0
    while len(out) < size and i < len(data):
        d = data[i]
        i += 1
        if d & 0xC0 == 0x40:
            out.extend([data[i]] * (d & 0x3F))
            i += 1
        else:
            out.append(d)
    return bytes(out[:size])


class Sprite:
    def __init__(self, group, number, width, height, axisx, axisy, pixels, palidx=0):
        self.group, self.number = group, number
        self.width, self.height = width, height
        self.axisx, self.axisy = axisx, axisy
        self.pixels = pixels  # bytes, width*height palette indices
        self.palidx = palidx


def write_sff2(path, sprites, palettes):
    """palettes: list of ((group, number), [(r,g,b)*256])."""
    HEADER = 512
    pal_nodes = bytearray()
    ldata = bytearray()
    for i, ((g, n), cols) in enumerate(palettes):
        ofs = len(ldata)
        for (r, gg, b) in cols:
            ldata += bytes((r, gg, b, 0))
        pal_nodes += struct.pack('<HHHHII', g, n, len(cols), 0, ofs, len(cols) * 4)

    spr_nodes = bytearray()
    seen = {}
    for idx, s in enumerate(sprites):
        key = (s.group, s.number)
        if key in seen:
            raise ValueError(f'duplicate sprite {key}')
        seen[key] = idx
        assert len(s.pixels) == s.width * s.height, key
        comp = rle8_encode(s.pixels)
        blob = struct.pack('<I', len(s.pixels)) + comp
        ofs = len(ldata)
        ldata += blob
        spr_nodes += struct.pack('<HHHHhhHBBIIHH', s.group, s.number, s.width, s.height,
                                 s.axisx, s.axisy, 0, 2, 8, ofs, len(blob), s.palidx, 0)

    spr_ofs = HEADER
    pal_ofs = spr_ofs + len(spr_nodes)
    ldata_ofs = pal_ofs + len(pal_nodes)
    tdata_ofs = ldata_ofs + len(ldata)
    hdr = bytearray(b'ElecbyteSpr\x00')
    hdr += bytes((0, 1, 0, 2))           # version 2.01 (verlo3, verlo2, verlo1, verhi)
    hdr += struct.pack('<I', 0)
    hdr += struct.pack('<IIII', 0, 0, 0, 0)  # reserved / compat version
    hdr += struct.pack('<IIII', spr_ofs, len(sprites), pal_ofs, len(palettes))
    hdr += struct.pack('<IIII', ldata_ofs, len(ldata), tdata_ofs, 0)
    hdr += b'\x00' * (HEADER - len(hdr))
    with open(path, 'wb') as f:
        f.write(hdr + spr_nodes + pal_nodes + ldata)


def read_sff2(path):
    """Return ({(g,n): Sprite}, [palettes]) for verification."""
    d = open(path, 'rb').read()
    assert d[:12] == b'ElecbyteSpr\x00'
    assert d[15] == 2
    spr_ofs, nspr, pal_ofs, npal, lofs, llen, tofs, tlen = struct.unpack_from('<IIIIIIII', d, 36)
    pals = []
    for i in range(npal):
        g, n, ncol, link, ofs, ln = struct.unpack_from('<HHHHII', d, pal_ofs + i * 16)
        raw = d[lofs + ofs: lofs + ofs + ln]
        pals.append(((g, n), [tuple(raw[j * 4:j * 4 + 3]) for j in range(ncol)]))
    sprites = {}
    for i in range(nspr):
        (g, n, w, h, ax, ay, link, fmt, depth, ofs, ln, palidx, flags) = \
            struct.unpack_from('<HHHHhhHBBIIHH', d, spr_ofs + i * 28)
        assert fmt == 2 and depth == 8
        base = (tofs if flags & 1 else lofs) + ofs
        usize = struct.unpack_from('<I', d, base)[0]
        px = rle8_decode(d[base + 4: base + ln], w * h)
        assert usize == w * h and len(px) == w * h, (g, n)
        sprites[(g, n)] = Sprite(g, n, w, h, ax, ay, px, palidx)
    return sprites, pals


# ------------------------------------------------------------------ SND ---

def wav_bytes(samples, rate=22050):
    """samples: list/array of ints in -32768..32767 (16-bit mono PCM)."""
    data = struct.pack('<%dh' % len(samples), *samples)
    fmt = struct.pack('<HHIIHH', 1, 1, rate, rate * 2, 2, 16)
    body = b'WAVE' + b'fmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(data)) + data
    return b'RIFF' + struct.pack('<I', len(body)) + body


def write_snd(path, sounds):
    """sounds: list of ((group, number), wav_bytes)."""
    HEADER = 512
    out = bytearray(b'ElecbyteSnd\x00')
    out += bytes((0, 0, 0, 1))
    out += struct.pack('<II', len(sounds), HEADER)
    out += b'\x00' * (HEADER - len(out))
    pos = HEADER
    for i, ((g, n), wav) in enumerate(sounds):
        nxt = pos + 16 + len(wav)
        if i == len(sounds) - 1:
            nxt = 0
        out += struct.pack('<IIII', nxt, len(wav), g, n) + wav
        pos += 16 + len(wav)
    with open(path, 'wb') as f:
        f.write(out)
