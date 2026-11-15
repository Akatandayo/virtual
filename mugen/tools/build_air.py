"""Generate DenshiDoku.air. Collision boxes come from the generated frames."""
import os

# element: (group, index, ticks[, flags])  flags: 'H' = attack box active, 'N' = no hurt box
#          x/y offsets via ('off', dx, dy) tuple appended in flags dict form
A = {}


def act(no, elems, loop=None, comment=''):
    A[no] = (elems, loop, comment)


def seq(group, idxs, t, flags=''):
    return [(group, i, t, flags) for i in idxs]


# ---------------------------------------------------------------- basic
act(0, seq(0, range(8), 6), comment='stand (floating)')
act(5, seq(5, (0, 1), 3), comment='turn')
act(6, seq(5, (0, 1), 3), comment='crouch turn')
act(10, [(10, 0, 3, '')], comment='stand -> crouch')
act(11, seq(11, range(8), 6), comment='crouching')
act(12, [(10, 0, 3, '')], comment='crouch -> stand')
act(20, seq(20, range(8), 5), comment='walk forward')
act(21, seq(21, range(8), 6), comment='walk back')
act(40, [(40, 0, 3, '')], comment='jump start')
for n in (41, 42, 43):
    act(n, seq(41, range(4), 5), comment='jump up')
for n in (44, 45, 46):
    act(n, seq(44, range(4), 5), comment='jump down')
act(47, [(47, 0, 4, '')], comment='landing')
act(100, seq(100, range(4), 3), comment='run (glitch dash)')
act(105, seq(105, (0, 1), 4) + [(105, 2, -1, '')], comment='hop back')
act(120, [(120, 0, 2, '')], comment='start guard (stand)')
act(121, [(131, 0, 2, '')], comment='start guard (crouch)')
act(122, [(132, 0, 2, '')], comment='start guard (air)')
act(130, [(130, 0, -1, '')], comment='guarding (stand)')
act(131, [(131, 0, -1, '')], comment='guarding (crouch)')
act(132, [(132, 0, -1, '')], comment='guarding (air)')
act(140, [(120, 0, 2, '')], comment='stop guard (stand)')
act(141, [(131, 0, 2, '')], comment='stop guard (crouch)')
act(142, [(132, 0, 2, '')], comment='stop guard (air)')
act(150, [(130, 1, -1, '')], comment='guard hit (stand)')
act(151, [(131, 1, -1, '')], comment='guard hit (crouch)')
act(152, [(132, 1, -1, '')], comment='guard hit (air)')
act(170, [(170, 0, 12, ''), (170, 1, -1, '')], comment='lose (time over)')
act(175, [(170, 0, 12, ''), (170, 1, -1, '')], comment='draw game')
act(180, seq(0, range(8), 6), comment='win 1 (error window explod)')
act(181, seq(181, range(4), 6), comment='win 2')
act(190, seq(190, range(8), 4) + [(0, 0, 6, '')], comment='intro (materialize)')
act(195, seq(195, range(6), 4) + [(0, 0, 4, '')], comment='taunt')

# ---------------------------------------------------------------- get hit
for base, g in ((5000, 5000), (5010, 5010), (5020, 5020)):
    for k in range(3):
        act(base + k, [(g, k, -1, '')], comment='get hit')
    act(base + 5, [(g, 0, 6, ''), (0 if base < 5020 else 11, 0, 4, '')], comment='get hit recover')
act(5030, [(5030, 0, 3, ''), (5030, 1, -1, '')], comment='air get hit')
act(5035, [(5030, 1, 4, '')], comment='air get hit transition')
act(5040, [(5040, 0, -1, '')], comment='air recover')
act(5050, [(5050, 0, 4, ''), (5050, 1, 4, ''), (5050, 2, -1, '')], comment='falling')
act(5060, [(5060, 0, -1, '')], comment='falling (coming down)')
act(5070, [(5070, 0, -1, '')], comment='tripped')
act(5080, [(5080, 0, -1, '')], comment='lying hit')
act(5100, [(5100, 0, -1, '')], comment='bounce off floor')
act(5101, [(5050, 2, -1, '')], comment='bounce into air')
act(5110, [(5110, 0, 40, ''), (5110, 1, 3, ''), (5110, 0, 30, ''), (5110, 1, 3, '')], loop=0, comment='lying down')
act(5120, seq(5120, range(3), 6) + [(0, 0, 3, '')], comment='get up')
for n in (5140, 5150, 5160, 5170):
    act(n, [(5110, 0, -1, '')], comment='lie dead')
act(5200, [(5050, 0, -1, '')], comment='air fall recovery')
act(5210, seq(44, range(4), 3), comment='air recovery')
act(5300, seq(5300, range(4), 5), comment='dizzy')

# ---------------------------------------------------------------- normals
act(200, [(200, 0, 3, ''), (200, 1, 3, 'H'), (200, 2, 4, ''), (200, 0, 3, '')], comment='stand x: scarf jab')
act(210, [(210, 0, 5, ''), (210, 1, 3, 'H'), (210, 2, 3, 'H'), (210, 3, 7, ''), (0, 0, 4, '')],
    comment='stand y: scarf slash')
act(220, [(220, 0, 9, ''), (220, 1, 3, 'H'), (220, 2, 4, 'H'), (220, 3, 3, 'H'), (220, 4, 10, ''), (0, 0, 5, '')],
    comment='stand z: overhead swing')
act(230, [(230, 0, 3, ''), (230, 1, 4, 'H'), (230, 2, 5, ''), (0, 0, 2, '')], comment='stand a: light kick')
act(240, [(240, 0, 5, ''), (240, 1, 3, 'H'), (240, 2, 3, 'H'), (240, 3, 8, ''), (0, 0, 3, '')],
    comment='stand b: kick')
act(250, [(250, 0, 10, ''), (250, 1, 6, 'H'), (250, 2, 14, 'H'), (0, 0, 4, '')], comment='stand c: glitch pillar')
act(400, [(400, 0, 2, ''), (400, 1, 3, 'H'), (400, 0, 4, '')], comment='crouch x')
act(410, [(410, 0, 4, ''), (410, 1, 3, 'H'), (410, 2, 4, 'H'), (11, 0, 5, '')], comment='crouch y')
act(420, [(420, 0, 6, ''), (420, 1, 3, 'H'), (420, 2, 4, 'H'), (420, 3, 10, ''), (11, 0, 4, '')],
    comment='crouch z: anti-air')
act(430, [(430, 0, 3, ''), (430, 1, 3, 'H'), (430, 0, 4, '')], comment='crouch a')
act(440, [(440, 0, 5, ''), (440, 1, 3, 'H'), (440, 2, 3, 'H'), (440, 0, 6, '')], comment='crouch b')
act(450, [(450, 0, 7, ''), (450, 1, 4, 'H'), (450, 2, 4, 'H'), (11, 0, 12, '')], comment='crouch c: sweep')
act(600, [(600, 0, 2, ''), (600, 1, 6, 'H'), (600, 0, 4, '')], comment='air x')
act(610, [(610, 0, 4, ''), (610, 1, 4, 'H'), (610, 2, 5, 'H'), (44, 0, 5, '')], comment='air y')
act(620, [(620, 0, 6, ''), (620, 1, 4, 'H'), (620, 2, 6, 'H'), (44, 0, 6, '')], comment='air z')
act(630, [(630, 0, 3, ''), (630, 1, 8, 'H'), (630, 0, 4, '')], comment='air a')
act(640, [(640, 0, 4, ''), (640, 1, 10, 'H'), (44, 0, 5, '')], comment='air b')
act(650, [(650, 0, 6, ''), (650, 1, 8, 'H'), (650, 0, 5, ''), (44, 0, 4, '')], comment='air c: glitch burst')
act(800, [(800, 0, 3, ''), (800, 1, 4, 'H'), (800, 0, 6, '')], comment='throw attempt')
act(810, [(810, 0, 10, ''), (810, 1, 14, ''), (810, 2, 16, ''), (0, 0, 6, '')], comment='throw')

# ---------------------------------------------------------------- specials
act(1000, [(1000, 0, 8, ''), (1000, 1, 6, ''), (1000, 2, 14, ''), (0, 0, 2, '')], comment='bug shot')
act(1100, seq(1100, range(5), 3, ''), comment='warp out')
act(1101, seq(1100, (4, 3, 2, 1, 0), 3, ''), comment='warp in')
act(1102, [(1100, 4, -1, 'N')], comment='warp: hidden')
act(1200, [(1200, 0, 3, 'H'), (1200, 1, 3, 'H'), (1200, 2, 3, 'H'), (1200, 3, 3, 'H'), (1200, 0, 3, 'H'),
           (1200, 1, 3, 'H'), (1200, 2, 3, 'H')], comment='data lash (rising)')
act(1201, [(1200, 4, -1, '')], comment='data lash fall')
act(1300, [(1300, 0, 6, ''), (1300, 1, 4, ''), (1300, 2, 4, ''), (1300, 3, 4, ''), (1300, 4, 4, ''),
           (1300, 1, 4, ''), (1300, 2, 4, ''), (1300, 5, 10, ''), (0, 0, 2, '')], comment='self corrupt')
act(3000, [(3000, 0, 24, ''), (3000, 1, 3, 'B'), (3000, 2, 3, 'B')], loop=1, comment='FATAL ERROR')
act(3001, [(3000, 2, 10, ''), (3000, 0, 8, ''), (0, 0, 4, '')], comment='FATAL ERROR end')
act(3100, [(3100, 0, -1, 'H')], comment='SYSTEM CRASH lunge')
act(3110, [(3100, 1, 6, ''), (3100, 2, 3, ''), (3100, 1, 3, '')], loop=1, comment='SYSTEM CRASH cinematic')
act(3111, [(3100, 0, 10, ''), (0, 0, 4, '')], comment='SYSTEM CRASH end')

# P2 throw / crash anims (use P2's own sprites via ChangeAnim2)
act(820, [(5000, 0, -1, '')], comment='P2 held (own sprites)')
act(821, [(5030, 0, -1, '')], comment='P2 thrown (own sprites)')

# ---------------------------------------------------------------- effects
act(6000, seq(6000, range(4), 3), comment='bug projectile')
act(6001, seq(6010, range(5), 3), comment='bug projectile hit')
act(6020, seq(6020, range(5), 2), comment='hitspark')
act(6025, seq(6025, range(4), 2), comment='guardspark')
act(6030, seq(6030, range(6), 3), comment='glitch pillar')
for k in range(4):
    act(6040 + k, [(6040, k, -1, '')], comment='error window')
act(6050, seq(6050, range(5), 3), comment='teleport burst')
act(6060, [(6060, 0, 6, ''), (6060, 1, 2, '')], loop=0, comment='FATAL ERROR banner')
act(6070, seq(6070, range(4), 2), comment='beam')
act(6080, seq(6080, range(5), 3), comment='self damage burst')
act(6090, seq(6090, range(4), 4), comment='overflow aura')
act(6100, [(6100, 0, -1, '')], comment='scanlines')
act(6110, [(6110, 0, 24, ''), (6110, 1, 3, '')], loop=0, comment='system crash screen')
act(6120, seq(6120, range(4), 3), comment='corruption particles')


def _box(b):
    x0, y0, x1, y1 = b
    return f'{min(x0, x1)}, {min(y0, y1)}, {max(x0, x1)}, {max(y0, y1)}'


PROJ_BOX = (-20, -20, 20, 20)
BEAM_BOX = (80, -170, 760, -90)   # FATAL ERROR beam (explod 6070 at 90,-130)


def write(frames, sprites, outdir):
    have = {(s.group, s.number) for s in sprites}
    lines = ['; DenshiDoku.air -- generated by mugen/tools/build_air.py', '']
    for no in sorted(A):
        elems, loop, comment = A[no]
        lines.append(f'; {comment}')
        lines.append(f'[Begin Action {no}]')
        for k, (g, i, t, flags) in enumerate(elems):
            assert (g, i) in have, f'action {no}: missing sprite {g},{i}'
            if loop is not None and k == loop:
                lines.append('Loopstart')
            f = frames.get((g, i))
            if no in (6000,):
                lines.append('Clsn2: 1')
                lines.append(f'  Clsn2[0] = {_box(PROJ_BOX)}')
                lines.append('Clsn1: 1')
                lines.append(f'  Clsn1[0] = {_box(PROJ_BOX)}')
            elif f is not None and no < 6000 and no not in (820, 821):
                if f.hurt and 'N' not in flags:
                    lines.append('Clsn2: 1')
                    lines.append(f'  Clsn2[0] = {_box(f.hurt)}')
                if 'B' in flags:
                    lines.append('Clsn1: 1')
                    lines.append(f'  Clsn1[0] = {_box(BEAM_BOX)}')
                if 'H' in flags:
                    assert f.hit, f'action {no}: frame {g},{i} has no attack box'
                    lines.append('Clsn1: 1')
                    lines.append(f'  Clsn1[0] = {_box(f.hit)}')
            lines.append(f'{g},{i}, 0,0, {t}')
        lines.append('')
    with open(os.path.join(outdir, 'DenshiDoku.air'), 'w', newline='\r\n') as fh:
        fh.write('\n'.join(lines))
    print(f'{len(A)} actions written')
