"""Generate attacks.st (normal moves + throw) for DenshiDoku.

The normals share one template, so they are described by the table below.
Edit the table and re-run:  python3 build_states.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'DenshiDoku', 'attacks.st')

# state, kind(S/C/A), name, damage, animtype, guardflag, ground.type, level(0-2), sparky, extra
N = [
    (200, 'S', '立ち弱P  scarf jab',        22, 'Light',  'MA', 'High', 0, -150, ''),
    (210, 'S', '立ち中P  scarf slash',      45, 'Medium', 'MA', 'High', 1, -140, ''),
    (220, 'S', '立ち強P  overhead swing',   75, 'Hard',   'MA', 'High', 2, -150, ''),
    (230, 'S', '立ち弱K  light kick',       25, 'Light',  'MA', 'Low',  0, -70, ''),
    (240, 'S', '立ち中K  kick',             50, 'Medium', 'MA', 'Low',  1, -80, ''),
    (250, 'S', '立ち強K  glitch pillar (launcher)', 70, 'Hard', 'MA', 'High', 2, -120, 'launch'),
    (400, 'C', 'しゃがみ弱P',               20, 'Light',  'MA', 'Low',  0, -90, ''),
    (410, 'C', 'しゃがみ中P',               40, 'Medium', 'L',  'Low',  1, -80, ''),
    (420, 'C', 'しゃがみ強P  anti-air',     70, 'Hard',   'MA', 'High', 2, -200, 'antiair'),
    (430, 'C', 'しゃがみ弱K',               22, 'Light',  'L',  'Low',  0, -40, ''),
    (440, 'C', 'しゃがみ中K',               45, 'Medium', 'L',  'Low',  1, -40, ''),
    (450, 'C', 'しゃがみ強K  sweep',         65, 'Hard',   'L',  'Trip', 2, -30, 'trip'),
    (600, 'A', 'ジャンプ弱P',               24, 'Light',  'HA', 'High', 0, -150, ''),
    (610, 'A', 'ジャンプ中P',               44, 'Medium', 'HA', 'High', 1, -120, ''),
    (620, 'A', 'ジャンプ強P',               70, 'Hard',   'HA', 'High', 2, -110, ''),
    (630, 'A', 'ジャンプ弱K',               24, 'Light',  'HA', 'High', 0, -60, ''),
    (640, 'A', 'ジャンプ中K',               48, 'Medium', 'HA', 'High', 1, -50, ''),
    (650, 'A', 'ジャンプ強K  glitch burst',  66, 'Hard',   'MA', 'High', 2, -120, 'burst'),
]

PAUSE = (8, 10, 12)
HITTIME = (12, 15, 18)
SLIDE = (10, 12, 14)
GVEL = (-8, -10, -12)
AVEL = ('-5, -6', '-6, -7', '-7, -8')
POWER = (20, 35, 55)


def normal(st, kind, name, dmg, animtype, gflag, gtype, lv, sparky, extra):
    physics = {'S': 'S', 'C': 'C', 'A': 'A'}[kind]
    attr = {'S': 'S', 'C': 'C', 'A': 'A'}[kind]
    vel = '' if kind == 'A' else 'velset = 0, 0\n'
    end_state, end_ctrl = {'S': (0, 1), 'C': (11, 1), 'A': (50, 0)}[kind]
    hitflag = 'MAF' if kind != 'A' else 'MAF'
    gv = GVEL[lv]
    av = AVEL[lv]
    fall = ''
    if extra == 'launch':
        gv = '-3, -15'
        av = '-3, -15'
        fall = 'fall = 1\nfall.recover = 0\n'
    elif extra == 'antiair':
        av = '-4, -11'
        fall = 'air.fall = 1\n'
    elif extra == 'trip':
        gv = '-6, -6'
        fall = 'fall = 1\nfall.recover = 0\n'
    elif extra == 'burst':
        av = '-6, -10'
        fall = 'air.fall = 1\n'
    s = f''';---------------------------------------------------------------------------
; {name}
[Statedef {st}]
type = {kind}
movetype = A
physics = {physics}
juggle = {2 + lv}
poweradd = {POWER[lv]}
ctrl = 0
{vel}anim = {st}
sprpriority = 2

[State {st}, swing]
type = PlaySnd
trigger1 = Time = 1
value = S0, {lv}

[State {st}, hitdef]
type = HitDef
trigger1 = Time = 0
attr = {attr}, {('NA', 'NA', 'HA')[lv]}
damage = {dmg}, {dmg // 8}
animtype = {animtype}
guardflag = {gflag}
hitflag = {hitflag}
priority = {3 + lv}, Hit
pausetime = {PAUSE[lv]}, {PAUSE[lv]}
sparkno = S6020
guard.sparkno = S6025
sparkxy = -10, {sparky}
hitsound = S5, {lv}
guardsound = S6, 0
ground.type = {gtype}
ground.slidetime = {SLIDE[lv]}
ground.hittime = {HITTIME[lv]}
ground.velocity = {gv}
air.velocity = {av}
air.hittime = {HITTIME[lv]}
guard.velocity = {GVEL[lv] + 2}
{fall}'''
    if extra == 'launch':
        s += f'''
[State {st}, pillar]
type = Explod
trigger1 = AnimElem = 2
anim = 6030
pos = 100, 0
postype = p1
sprpriority = 3
removetime = 18
ownpal = 1

[State {st}, pillar sfx]
type = PlaySnd
trigger1 = AnimElem = 2
value = S1, 0
'''
    if extra == 'burst':
        s += f'''
[State {st}, burst sfx]
type = PlaySnd
trigger1 = AnimElem = 2
value = S1, 1
'''
    if kind == 'A':
        s += f'''
[State {st}, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 50
ctrl = 0
anim = 44
'''
    else:
        s += f'''
[State {st}, end]
type = ChangeState
trigger1 = AnimTime = 0
value = {end_state}
ctrl = {end_ctrl}
'''
    return s


THROW = r''';===========================================================================
; 投げ  Scarf Bind (近距離で 前/後 + y)
;===========================================================================
[Statedef 800]
type = S
movetype = A
physics = S
juggle = 0
velset = 0, 0
ctrl = 0
anim = 800
sprpriority = 2

[State 800, swing]
type = PlaySnd
trigger1 = Time = 1
value = S0, 1

[State 800, throw]
type = HitDef
trigger1 = Time = 0
attr = S, NT
hitflag = M-
priority = 2, Miss
sparkno = -1
p1sprpriority = 2
p2sprpriority = 1
p1facing = 1
p2facing = 1
p1stateno = 810
p2stateno = 820
guard.dist = 0
fall = 1

[State 800, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;---------------------------------------------------------------------------
[Statedef 810]
type = S
movetype = A
physics = N
anim = 810
poweradd = 60
velset = 0, 0
ctrl = 0

[State 810, flip if back throw]
type = Turn
trigger1 = Time = 0
trigger1 = command = "holdback"

[State 810, hold up]
type = TargetBind
trigger1 = AnimElem = 1, >= 0
trigger1 = AnimElem = 3, < 0
pos = 110, -90

[State 810, glitch sfx]
type = PlaySnd
trigger1 = AnimElem = 2
value = S1, 1

[State 810, shake]
type = EnvShake
trigger1 = AnimElem = 2
time = 10
ampl = 4

[State 810, slam bind]
type = TargetBind
trigger1 = AnimElem = 3, >= 0
trigger1 = AnimElem = 3, < 4
pos = 150, -20

[State 810, damage]
type = TargetLifeAdd
trigger1 = AnimElem = 3, = 4
value = -floor(110 * fvar(1))

[State 810, hit sfx]
type = PlaySnd
trigger1 = AnimElem = 3, = 4
value = S5, 2

[State 810, spark]
type = Explod
trigger1 = AnimElem = 3, = 4
anim = 6020
pos = 150, -40
postype = p1
sprpriority = 4
removetime = 10
ownpal = 1

[State 810, throw away]
type = TargetVelSet
trigger1 = AnimElem = 3, = 4
x = -9
y = -7

[State 810, release]
type = TargetState
trigger1 = AnimElem = 3, = 4
value = 821

[State 810, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;---------------------------------------------------------------------------
; P2: held by the scarf (runs with P2's sprites)
[Statedef 820]
type = A
movetype = H
physics = N
velset = 0, 0

[State 820, anim]
type = ChangeAnim2
trigger1 = Time = 0
value = 820

[State 820, safety]
type = SelfState
trigger1 = !GetHitVar(isbound)
trigger1 = Time > 1
value = 5050

;---------------------------------------------------------------------------
; P2: thrown
[Statedef 821]
type = A
movetype = H
physics = N

[State 821, anim]
type = ChangeAnim2
trigger1 = Time = 0
value = 821

[State 821, gravity]
type = VelAdd
trigger1 = 1
y = 0.8

[State 821, land]
type = SelfState
trigger1 = Vel Y > 0
trigger1 = Pos Y >= 0
value = 5100
'''


def main():
    parts = [''';===========================================================================
; attacks.st -- 通常技 / 投げ  (generated by mugen/tools/build_states.py)
; 弱/中/強 = x,y,z (パンチ=マフラー)  a,b,c (キック)
;===========================================================================
''']
    for row in N:
        parts.append(normal(*row))
    parts.append(THROW)
    with open(OUT, 'w', newline='\r\n') as f:
        f.write('\n'.join(parts))
    print('attacks.st written')


if __name__ == '__main__':
    main()
