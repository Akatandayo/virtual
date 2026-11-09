"""Minimal little-endian NBT reader/writer for Bedrock level.dat / mcstructure."""
import struct, io, json

TAG_END, TAG_BYTE, TAG_SHORT, TAG_INT, TAG_LONG, TAG_FLOAT, TAG_DOUBLE, TAG_BYTE_ARRAY, TAG_STRING, TAG_LIST, TAG_COMPOUND, TAG_INT_ARRAY, TAG_LONG_ARRAY = range(13)

class Tag:
    __slots__ = ("t", "v", "lt")
    def __init__(self, t, v, lt=None):
        self.t = t; self.v = v; self.lt = lt  # lt: list element type
    def __repr__(self):
        return f"Tag({self.t},{self.v!r})"

def _rs(f):
    n = struct.unpack('<H', f.read(2))[0]
    return f.read(n).decode('utf-8', 'replace')

def _read_payload(f, t):
    if t == TAG_BYTE: return Tag(t, struct.unpack('<b', f.read(1))[0])
    if t == TAG_SHORT: return Tag(t, struct.unpack('<h', f.read(2))[0])
    if t == TAG_INT: return Tag(t, struct.unpack('<i', f.read(4))[0])
    if t == TAG_LONG: return Tag(t, struct.unpack('<q', f.read(8))[0])
    if t == TAG_FLOAT: return Tag(t, struct.unpack('<f', f.read(4))[0])
    if t == TAG_DOUBLE: return Tag(t, struct.unpack('<d', f.read(8))[0])
    if t == TAG_BYTE_ARRAY:
        n = struct.unpack('<i', f.read(4))[0]; return Tag(t, f.read(n))
    if t == TAG_STRING: return Tag(t, _rs(f))
    if t == TAG_LIST:
        lt = f.read(1)[0]; n = struct.unpack('<i', f.read(4))[0]
        return Tag(t, [_read_payload(f, lt) for _ in range(n)], lt)
    if t == TAG_COMPOUND:
        d = {}
        while True:
            ct = f.read(1)[0]
            if ct == TAG_END: break
            name = _rs(f)
            d[name] = _read_payload(f, ct)
        return Tag(t, d)
    if t == TAG_INT_ARRAY:
        n = struct.unpack('<i', f.read(4))[0]; return Tag(t, list(struct.unpack(f'<{n}i', f.read(4*n))))
    if t == TAG_LONG_ARRAY:
        n = struct.unpack('<i', f.read(4))[0]; return Tag(t, list(struct.unpack(f'<{n}q', f.read(8*n))))
    raise ValueError(f"bad tag {t}")

def read_root(data):
    f = io.BytesIO(data)
    t = f.read(1)[0]
    name = _rs(f)
    return name, _read_payload(f, t)

def _ws(f, s):
    b = s.encode('utf-8'); f.write(struct.pack('<H', len(b))); f.write(b)

def _write_payload(f, tag):
    t, v = tag.t, tag.v
    if t == TAG_BYTE: f.write(struct.pack('<b', v))
    elif t == TAG_SHORT: f.write(struct.pack('<h', v))
    elif t == TAG_INT: f.write(struct.pack('<i', v))
    elif t == TAG_LONG: f.write(struct.pack('<q', v))
    elif t == TAG_FLOAT: f.write(struct.pack('<f', v))
    elif t == TAG_DOUBLE: f.write(struct.pack('<d', v))
    elif t == TAG_BYTE_ARRAY: f.write(struct.pack('<i', len(v))); f.write(v)
    elif t == TAG_STRING: _ws(f, v)
    elif t == TAG_LIST:
        lt = tag.lt if tag.lt is not None else (v[0].t if v else TAG_END)
        f.write(bytes([lt])); f.write(struct.pack('<i', len(v)))
        for e in v: _write_payload(f, e)
    elif t == TAG_COMPOUND:
        for k, e in v.items():
            f.write(bytes([e.t])); _ws(f, k); _write_payload(f, e)
        f.write(bytes([TAG_END]))
    elif t == TAG_INT_ARRAY: f.write(struct.pack('<i', len(v))); f.write(struct.pack(f'<{len(v)}i', *v))
    elif t == TAG_LONG_ARRAY: f.write(struct.pack('<i', len(v))); f.write(struct.pack(f'<{len(v)}q', *v))
    else: raise ValueError(t)

def write_root(tag, name=""):
    f = io.BytesIO()
    f.write(bytes([tag.t])); _ws(f, name); _write_payload(f, tag)
    return f.getvalue()

def read_level_dat(path):
    d = open(path, 'rb').read()
    ver, ln = struct.unpack('<ii', d[:8])
    name, root = read_root(d[8:8+ln])
    return ver, root

def write_level_dat(path, ver, root):
    body = write_root(root)
    open(path, 'wb').write(struct.pack('<ii', ver, len(body)) + body)

def to_py(tag):
    if tag.t == TAG_COMPOUND: return {k: to_py(v) for k, v in tag.v.items()}
    if tag.t == TAG_LIST: return [to_py(v) for v in tag.v]
    if tag.t == TAG_BYTE_ARRAY: return tag.v.hex()
    return tag.v

if __name__ == '__main__':
    import sys
    ver, root = read_level_dat(sys.argv[1])
    print('storage version', ver)
    for k, v in sorted(root.v.items()):
        val = to_py(v)
        s = json.dumps(val, ensure_ascii=False)
        print(f"{k} [{v.t}] = {s[:300]}")
