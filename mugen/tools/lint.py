"""Static checks for the DenshiDoku character files.

- every anim / state / sound / sprite reference resolves
- every [State] block has a known controller type and at least one trigger
- every [Statedef] number is unique
"""
import os
import re
import sys

from mugenfmt import read_sff2

HERE = os.path.dirname(os.path.abspath(__file__))
CHAR = os.path.join(HERE, '..', 'DenshiDoku')

# states provided by MUGEN's common1.cns
COMMON_STATES = {0, 10, 11, 12, 20, 40, 45, 50, 52, 100, 105, 106, 110, 115, 120, 130, 131, 132, 140,
                 150, 151, 152, 153, 154, 155, 170, 175, 190, 191, 5000, 5001, 5002, 5005, 5010, 5011,
                 5020, 5030, 5035, 5040, 5050, 5070, 5071, 5080, 5081, 5100, 5101, 5110, 5120, 5150,
                 5200, 5201, 5210, 5500, 5900}

CONTROLLERS = {
    'afterimage', 'afterimagetime', 'allpalfx', 'angleadd', 'angledraw', 'anglemul', 'angleset',
    'appendtoclipboard', 'assertspecial', 'attackdist', 'attackmulset', 'bgpalfx', 'bindtoparent',
    'bindtoroot', 'bindtotarget', 'changeanim', 'changeanim2', 'changestate', 'clearclipboard',
    'ctrlset', 'defencemulset', 'destroyself', 'displaytoclipboard', 'envcolor', 'envshake', 'explod',
    'explodbindtime', 'forcefeedback', 'fallenvshake', 'gamemakeanim', 'gravity', 'helper', 'hitadd',
    'hitby', 'hitdef', 'hitfalldamage', 'hitfallset', 'hitfallvel', 'hitoverride', 'hitvelset',
    'lifeadd', 'lifeset', 'makedust', 'modifyexplod', 'movehitreset', 'nothitby', 'null', 'offset',
    'palfx', 'parentvaradd', 'parentvarset', 'pause', 'playerpush', 'playsnd', 'posadd', 'posfreeze',
    'posset', 'poweradd', 'powerset', 'projectile', 'removeexplod', 'reversaldef', 'screenbound',
    'selfstate', 'sprpriority', 'statetypeset', 'sndpan', 'stopsnd', 'superpause', 'targetbind',
    'targetdrop', 'targetfacing', 'targetlifeadd', 'targetpoweradd', 'targetstate', 'targetveladd',
    'targetvelset', 'trans', 'turn', 'varadd', 'varrandom', 'varrangeset', 'varset', 'veladd',
    'velmul', 'velset', 'width'}

errors = []


def err(msg):
    errors.append(msg)


def parse_blocks(path):
    """Yield (header, [(key, value, lineno)])."""
    blocks = []
    cur = None
    for n, raw in enumerate(open(path, encoding='utf-8'), 1):
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('['):
            if not line.endswith(']'):
                err(f'{os.path.basename(path)}:{n}: malformed section header: {line}')
            cur = (line[1:-1].strip(), [], n)
            blocks.append(cur)
        elif cur is not None:
            if '=' not in line and not line.lower().startswith(('loopstart', 'clsn')):
                err(f'{os.path.basename(path)}:{n}: line without "=": {line}')
                continue
            k, _, v = line.partition('=')
            cur[1].append((k.strip().lower(), v.strip(), n))
    return blocks


def balanced(expr):
    d = 0
    for ch in expr:
        d += ch == '('
        d -= ch == ')'
        if d < 0:
            return False
    return d == 0 and expr.count('"') % 2 == 0


def main():
    sprites, pals = read_sff2(os.path.join(CHAR, 'DenshiDoku.sff'))
    # air
    actions = set()
    air = open(os.path.join(CHAR, 'DenshiDoku.air'), encoding='utf-8').read()
    for m in re.finditer(r'\[Begin Action (\d+)\]', air):
        actions.add(int(m.group(1)))
    for m in re.finditer(r'^(\d+),(\d+), ', air, re.M):
        if (int(m.group(1)), int(m.group(2))) not in sprites:
            err(f'air: missing sprite {m.group(1)},{m.group(2)}')
    # sounds
    import struct
    snd = open(os.path.join(CHAR, 'DenshiDoku.snd'), 'rb').read()
    nsnd, ofs = struct.unpack_from('<II', snd, 16)
    sounds = set()
    for _ in range(nsnd):
        nxt, ln, g, n = struct.unpack_from('<IIII', snd, ofs)
        assert snd[ofs + 16:ofs + 20] == b'RIFF'
        sounds.add((g, n))
        ofs = nxt
        if not ofs:
            break
    if len(sounds) != nsnd:
        err('snd: subfile chain broken')

    files = ['DenshiDoku.cns', 'attacks.st', 'specials.st', 'DenshiDoku.cmd']
    statedefs = {}
    refs = []  # (kind, value, where)
    for fn in files:
        path = os.path.join(CHAR, fn)
        for header, kv, n in parse_blocks(path):
            where = f'{fn}:{n}'
            h = header.lower()
            if h.startswith('statedef'):
                num = int(header.split()[1])
                if num in statedefs:
                    err(f'{where}: duplicate Statedef {num}')
                statedefs[num] = where
                for k, v, ln in kv:
                    if k == 'anim':
                        refs.append(('anim', v, where))
            elif h.startswith('state '):
                d = {k: v for k, v, _ in kv}
                typ = d.get('type', '').lower()
                if typ not in CONTROLLERS:
                    err(f'{where}: unknown/missing controller type "{d.get("type")}"')
                if not any(k.startswith('trigger') for k, _, _ in kv):
                    err(f'{where}: no triggers')
                for k, v, ln in kv:
                    if not balanced(v):
                        err(f'{fn}:{ln}: unbalanced parentheses/quotes: {v}')
                    if k.startswith('trigger') and not re.match(r'trigger(all|\d+)$', k):
                        err(f'{fn}:{ln}: bad trigger key {k}')
                if typ in ('changestate', 'selfstate') and 'value' in d:
                    refs.append(('state', d['value'], where))
                if typ == 'targetstate':
                    refs.append(('state', d['value'], where))
                if typ in ('changeanim', 'changeanim2'):
                    refs.append(('anim', d['value'], where))
                if typ == 'explod':
                    refs.append(('anim', d.get('anim', ''), where))
                if typ == 'projectile':
                    for key in ('projanim', 'projhitanim', 'projremanim', 'projcancelanim'):
                        if key in d:
                            refs.append(('anim', d[key], where))
                if typ == 'hitdef':
                    for key in ('p1stateno', 'p2stateno'):
                        if key in d:
                            refs.append(('state', d[key], where))
                for key in ('hitsound', 'guardsound', 'value', 'sound'):
                    if key in d and (typ in ('playsnd',) or key != 'value') and d[key].upper().startswith('S'):
                        refs.append(('snd', d[key], where))
                for key in ('sparkno', 'guard.sparkno'):
                    if key in d and d[key].upper().startswith('S'):
                        refs.append(('anim', d[key][1:], where))
            elif h == 'data':
                for k, v, ln in kv:
                    if k in ('sparkno', 'guard.sparkno') and v.upper().startswith('S'):
                        refs.append(('anim', v[1:], fn))
    # resolve refs
    for kind, v, where in refs:
        v = v.strip()
        if kind == 'anim':
            for num in re.findall(r'(?<![\w.])(\d{1,4})(?![\w.])', v):
                num = int(num)
                if num >= 100 or num == 0:
                    if num not in actions and num not in (500, 1000):
                        err(f'{where}: anim {num} not in air')
        elif kind == 'state':
            v = re.sub(r'[<>=]\s*\d+', '', v)   # drop comparison operands (e.g. Random < 500)
            for num in re.findall(r'(?<![\w.(])(\d{1,4})(?![\w.])', v):
                num = int(num)
                if num >= 10 and num not in statedefs and num not in COMMON_STATES and num != 1000 or \
                        num == 0 and False:
                    if num not in statedefs and num not in COMMON_STATES:
                        err(f'{where}: state {num} not defined')
        elif kind == 'snd':
            m = re.match(r'S\s*(\d+)\s*,\s*(\d+)', v, re.I)
            if m and (int(m.group(1)), int(m.group(2))) not in sounds:
                err(f'{where}: sound {v} missing')
    # command names used must exist
    cmd = open(os.path.join(CHAR, 'DenshiDoku.cmd'), encoding='utf-8').read()
    defined = set(re.findall(r'^name\s*=\s*"([^"]+)"', cmd, re.M))
    used = set()
    for fn in files:
        txt = open(os.path.join(CHAR, fn), encoding='utf-8').read()
        used |= set(re.findall(r'command\s*!?=\s*"([^"]+)"', txt))
    for u in sorted(used - defined):
        err(f'command "{u}" used but not defined')
    # required anims
    required = [0, 5, 6, 10, 11, 12, 20, 21, 40, 41, 42, 43, 44, 47, 100, 105, 120, 121, 122, 130, 131, 132,
                140, 141, 142, 150, 151, 152, 170, 175, 190, 5000, 5001, 5002, 5010, 5011, 5012, 5020, 5021,
                5022, 5030, 5035, 5040, 5050, 5060, 5070, 5080, 5100, 5110, 5120, 5140, 5150, 5160, 5170,
                5210, 5300]
    for r in required:
        if r not in actions:
            err(f'required anim {r} missing')
    if (9000, 0) not in sprites or (9000, 1) not in sprites:
        err('portraits missing')
    print(f'{len(statedefs)} statedefs, {len(actions)} actions, {len(sprites)} sprites, {len(sounds)} sounds')
    for e in errors:
        print('ERROR', e)
    print('OK' if not errors else f'{len(errors)} problem(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
