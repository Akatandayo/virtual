;===========================================================================
; specials.st -- 必殺技 / 超必殺技
;
; 代償 (cost) summary
;   Glitch Warp      : own life -20  (free during OVERFLOW)
;   Data Lash        : own life -30
;   Self Corrupt     : own life -80, power +600, OVERFLOW for 10 seconds
;   FATAL ERROR      : power 1000, own life -50
;   SYSTEM CRASH     : power 3000, own life -150
; Self-damage can never KO Doku (LifeAdd kill = 0 leaves at least 1 life).
;===========================================================================

;===========================================================================
; Bug Shot  (↓↘→ + P)  -- throws a cube of corrupted data
;===========================================================================
[Statedef 1000]
type = S
movetype = A
physics = S
juggle = 4
poweradd = 40
velset = 0, 0
ctrl = 0
anim = 1000
sprpriority = 2

[State 1000, strength]
type = VarSet
trigger1 = Time = 0
v = 1
value = ifelse(AILevel > 0, Random % 3, ifelse(command = "shot_z", 2, ifelse(command = "shot_y", 1, 0)))

[State 1000, sfx]
type = PlaySnd
trigger1 = AnimElem = 2
value = S1, 0

[State 1000, shot]
type = Projectile
trigger1 = AnimElem = 2
projid = 1000
projanim = 6000
projhitanim = 6001
projremanim = 6001
projcancelanim = 6001
projremove = 1
projremovetime = -1
projpriority = 1
projsprpriority = 3
offset = 110, -140
velocity = 7 + var(1) * 2, 0
attr = S, SP
damage = 50, 8
animtype = Medium
guardflag = MA
hitflag = MAF
pausetime = 0, 10
sparkno = S6020
guard.sparkno = S6025
sparkxy = 0, 0
hitsound = S5, 1
guardsound = S6, 0
ground.type = High
ground.slidetime = 12
ground.hittime = 16
ground.velocity = -9
air.velocity = -5, -7
air.hittime = 16

; OVERFLOW: two extra cubes spread up and down
[State 1000, overflow shot up]
type = Projectile
trigger1 = AnimElem = 2
trigger1 = var(10) > 0
projid = 1001
projanim = 6000
projhitanim = 6001
projremanim = 6001
projcancelanim = 6001
projpriority = 1
projsprpriority = 3
offset = 100, -180
velocity = 7 + var(1) * 2, -0.9
attr = S, SP
damage = 30, 5
animtype = Light
guardflag = MA
hitflag = MAF
pausetime = 0, 8
sparkno = S6020
guard.sparkno = S6025
hitsound = S5, 0
guardsound = S6, 0
ground.type = High
ground.slidetime = 10
ground.hittime = 14
ground.velocity = -7
air.velocity = -4, -6

[State 1000, overflow shot down]
type = Projectile
trigger1 = AnimElem = 2
trigger1 = var(10) > 0
projid = 1001
projanim = 6000
projhitanim = 6001
projremanim = 6001
projcancelanim = 6001
projpriority = 1
projsprpriority = 3
offset = 100, -100
velocity = 7 + var(1) * 2, 0.5
attr = S, SP
damage = 30, 5
animtype = Light
guardflag = MA
hitflag = MAF
pausetime = 0, 8
sparkno = S6020
guard.sparkno = S6025
hitsound = S5, 0
guardsound = S6, 0
ground.type = Low
ground.slidetime = 10
ground.hittime = 14
ground.velocity = -7
air.velocity = -4, -6

[State 1000, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;===========================================================================
; Glitch Warp  (↓↙← + K)  a: forward / b: behind the opponent / c: retreat
;===========================================================================
[Statedef 1100]
type = S
movetype = I
physics = S
velset = 0, 0
ctrl = 0
anim = 1100
sprpriority = 2

[State 1100, strength]
type = VarSet
trigger1 = Time = 0
v = 1
value = ifelse(AILevel > 0, 1, ifelse(command = "warp_c", 2, ifelse(command = "warp_b", 1, 0)))

[State 1100, cost]
type = LifeAdd
trigger1 = Time = 0
trigger1 = var(10) <= 0
value = -20
kill = 0
absolute = 1

[State 1100, sfx]
type = PlaySnd
trigger1 = Time = 0
value = S1, 2

[State 1100, invul]
type = NotHitBy
trigger1 = 1
value = SCA
time = 2

[State 1100, burst]
type = Explod
trigger1 = Time = 4
anim = 6050
pos = 0, 0
postype = p1
removetime = 15
sprpriority = 3
ownpal = 1

[State 1100, vanish]
type = ChangeState
trigger1 = AnimTime = 0
value = 1101

;---------------------------------------------------------------------------
[Statedef 1101]
type = S
movetype = I
physics = N
velset = 0, 0
ctrl = 0
anim = 1102

[State 1101, invisible]
type = AssertSpecial
trigger1 = 1
flag = Invisible

[State 1101, invul]
type = NotHitBy
trigger1 = 1
value = SCA
time = 2

[State 1101, move a]
type = PosAdd
trigger1 = Time = 4
trigger1 = var(1) = 0
x = 170

[State 1101, move b: behind the opponent]
type = PosAdd
trigger1 = Time = 4
trigger1 = var(1) = 1
x = P2Dist X + 80

[State 1101, move c]
type = PosAdd
trigger1 = Time = 4
trigger1 = var(1) = 2
x = -220

[State 1101, face]
type = Turn
trigger1 = Time = 5
trigger1 = P2Dist X < 0

[State 1101, appear]
type = ChangeState
trigger1 = Time >= 7
value = 1102

;---------------------------------------------------------------------------
[Statedef 1102]
type = S
movetype = I
physics = S
velset = 0, 0
ctrl = 0
anim = 1101

[State 1102, sfx]
type = PlaySnd
trigger1 = Time = 0
value = S1, 0

[State 1102, burst]
type = Explod
trigger1 = Time = 0
anim = 6050
pos = 0, 0
postype = p1
removetime = 15
sprpriority = 3
ownpal = 1

[State 1102, invul]
type = NotHitBy
trigger1 = Time < 6
value = SCA
time = 1

[State 1102, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;===========================================================================
; Data Lash  (→↓↘ + P)  -- rising scarf spiral, invincible start
;===========================================================================
[Statedef 1200]
type = A
movetype = A
physics = N
juggle = 4
poweradd = 60
ctrl = 0
anim = 1200
sprpriority = 2

[State 1200, strength]
type = VarSet
trigger1 = Time = 0
v = 1
value = ifelse(AILevel > 0, 2, ifelse(command = "lash_z", 2, ifelse(command = "lash_y", 1, 0)))

[State 1200, cost]
type = LifeAdd
trigger1 = Time = 0
value = -30
kill = 0
absolute = 1

[State 1200, invincible start]
type = NotHitBy
trigger1 = Time = 0
value = SCA
time = 6 + var(1) * 2

[State 1200, sfx]
type = PlaySnd
trigger1 = Time = 0
value = S1, 1

[State 1200, rise]
type = VelSet
trigger1 = Time = 2
x = 2 + var(1) * 1.2
y = -11 - var(1) * 1.5

[State 1200, gravity]
type = VelAdd
trigger1 = Time >= 3
y = 0.62

[State 1200, afterimage]
type = AfterImage
trigger1 = Time = 0
time = 20
length = 5
timegap = 2
framegap = 2
trans = add
paladd = 30, 0, 50
palmul = 0.6, 0.4, 0.9

[State 1200, hit 1-2]
type = HitDef
trigger1 = AnimElem = 1
trigger2 = AnimElem = 3
attr = A, SA
damage = 28, 4
animtype = Medium
guardflag = MA
hitflag = MAF
priority = 5, Hit
pausetime = 6, 6
sparkno = S6020
guard.sparkno = S6025
sparkxy = -10, -160
hitsound = S5, 1
guardsound = S6, 0
ground.type = High
ground.hittime = 20
ground.velocity = -2, -9
air.velocity = -2, -9
air.hittime = 20
fall = 1
fall.recover = 0

[State 1200, final hit]
type = HitDef
trigger1 = AnimElem = 5
attr = A, SA
damage = 46, 6
animtype = Up
guardflag = MA
hitflag = MAF
priority = 5, Hit
pausetime = 12, 12
sparkno = S6020
guard.sparkno = S6025
sparkxy = -10, -200
hitsound = S5, 2
guardsound = S6, 0
ground.type = High
ground.velocity = -6, -12
air.velocity = -6, -12
fall = 1

[State 1200, fall anim]
type = ChangeAnim
trigger1 = AnimTime = 0
trigger1 = Anim = 1200
value = 1201

[State 1200, land]
type = ChangeState
trigger1 = Vel Y > 0
trigger1 = Pos Y >= 0
value = 52

;===========================================================================
; Self Corrupt  (↓↓ + P)  -- 自傷バグ
; Tear own data apart: life -80, power +600, OVERFLOW for 10 seconds.
; During OVERFLOW: attack x1.15, Bug Shot fires 3 cubes, Glitch Warp is free.
;===========================================================================
[Statedef 1300]
type = S
movetype = I
physics = S
velset = 0, 0
ctrl = 0
anim = 1300
sprpriority = 2

[State 1300, warning]
type = PlaySnd
trigger1 = Time = 0
value = S1, 6

[State 1300, crunch]
type = PlaySnd
trigger1 = AnimElem = 2
value = S1, 3

[State 1300, cost]
type = LifeAdd
trigger1 = AnimElem = 2
value = -80
kill = 0
absolute = 1

[State 1300, power]
type = PowerAdd
trigger1 = AnimElem = 2
value = 600

[State 1300, overflow on]
type = VarSet
trigger1 = AnimElem = 2
v = 10
value = 600

[State 1300, flash]
type = PalFX
trigger1 = AnimElem = 2
time = 20
add = 160, -40, -40
sinadd = 60, 0, 0, 4

[State 1300, shake]
type = EnvShake
trigger1 = AnimElem = 2
time = 14
ampl = 5

[State 1300, burst]
type = Explod
trigger1 = AnimElem = 2
anim = 6080
pos = 0, -120
postype = p1
removetime = 15
sprpriority = 4
ownpal = 1

[State 1300, window]
type = Explod
trigger1 = AnimElem = 2
anim = 6041
pos = -90, -300
postype = p1
removetime = 70
sprpriority = 5
ownpal = 1

[State 1300, old aura off]
type = RemoveExplod
trigger1 = AnimElem = 2
id = 6090

[State 1300, aura]
type = Explod
trigger1 = AnimElem = 2
id = 6090
anim = 6090
pos = 0, 0
postype = p1
bindtime = -1
removetime = -1
sprpriority = -1
trans = add
ownpal = 1
removeongethit = 0

[State 1300, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;===========================================================================
; 超必殺技 1  FATAL ERROR  (↓↘→↓↘→ + P, 1 gauge)
; Cost: own life -50.  A glitch beam that crosses the whole screen.
;===========================================================================
[Statedef 3000]
type = S
movetype = A
physics = S
juggle = 0
velset = 0, 0
ctrl = 0
anim = 3000
sprpriority = 3

[State 3000, pay power]
type = PowerAdd
trigger1 = Time = 0
value = -1000

[State 3000, pay life]
type = LifeAdd
trigger1 = Time = 0
value = -50
kill = 0
absolute = 1

[State 3000, superpause]
type = SuperPause
trigger1 = Time = 0
time = 40
anim = -1
sound = S3, 0
pos = 0, -120
darken = 1
p2defmul = 1
poweradd = 0
unhittable = 1

[State 3000, banner]
type = Explod
trigger1 = Time = 0
anim = 6060
postype = left
pos = 320, 110
removetime = 80
supermovetime = 40
sprpriority = 10
ontop = 1
ownpal = 1

[State 3000, self burst]
type = Explod
trigger1 = Time = 0
anim = 6080
pos = 0, -120
postype = p1
removetime = 15
supermovetime = 15
sprpriority = 4
ownpal = 1

[State 3000, invul during startup]
type = NotHitBy
trigger1 = Time < 26
value = SCA
time = 1

[State 3000, beam]
type = Explod
trigger1 = Time = 24
anim = 6070
pos = 90, -130
postype = p1
removetime = 60
sprpriority = 4
trans = add
ownpal = 1

[State 3000, beam sfx]
type = PlaySnd
trigger1 = Time = 24
trigger2 = Time = 54
value = S1, 4

[State 3000, beam shake]
type = EnvShake
trigger1 = Time = 24
time = 60
ampl = 3
freq = 120

; multi-hit: one hit every 4 ticks
[State 3000, beam hit]
type = HitDef
trigger1 = Time >= 24
trigger1 = Time < 80
trigger1 = ((Time - 24) % 4) = 0
attr = S, HP
damage = 18, 3
animtype = Light
guardflag = MA
hitflag = MAF
priority = 6, Hit
pausetime = 0, 3
sparkno = S6020
guard.sparkno = S6025
sparkxy = -10, -130
hitsound = S5, 1
guardsound = S6, 0
ground.type = High
ground.hittime = 10
ground.slidetime = 4
ground.velocity = -1
air.velocity = -1, -1
air.hittime = 10
air.juggle = 0
getpower = 0, 0

[State 3000, beam final]
type = HitDef
trigger1 = Time = 80
attr = S, HP
damage = 80, 10
animtype = Hard
guardflag = MA
hitflag = MAF
priority = 7, Hit
pausetime = 16, 16
sparkno = S6020
guard.sparkno = S6025
sparkxy = -10, -130
hitsound = S5, 3
guardsound = S6, 0
ground.type = High
ground.velocity = -10, -9
air.velocity = -10, -9
fall = 1
air.juggle = 0
getpower = 0, 0

[State 3000, end]
type = ChangeState
trigger1 = Time >= 86
value = 3001

;---------------------------------------------------------------------------
[Statedef 3001]
type = S
movetype = I
physics = S
velset = 0, 0
ctrl = 0
anim = 3001

[State 3001, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;===========================================================================
; 超必殺技 2  SYSTEM CRASH  (↓↘→↓↘→ + K, 3 gauges)
; Cost: own life -150.  Unblockable glitch lunge; on hit the opponent's
; data is corrupted and the screen crashes.
;===========================================================================
[Statedef 3100]
type = S
movetype = A
physics = N
juggle = 0
velset = 0, 0
ctrl = 0
anim = 3100
sprpriority = 3

[State 3100, pay power]
type = PowerAdd
trigger1 = Time = 0
value = -3000

[State 3100, pay life]
type = LifeAdd
trigger1 = Time = 0
value = -150
kill = 0
absolute = 1

[State 3100, superpause]
type = SuperPause
trigger1 = Time = 0
time = 50
anim = -1
sound = S3, 0
pos = 0, -120
darken = 1
poweradd = 0
unhittable = 1

[State 3100, self burst]
type = Explod
trigger1 = Time = 0
anim = 6080
pos = 0, -120
postype = p1
removetime = 15
supermovetime = 15
sprpriority = 4
ownpal = 1

[State 3100, warning]
type = Explod
trigger1 = Time = 0
anim = 6043
postype = left
pos = 320, 140
removetime = 50
supermovetime = 50
sprpriority = 10
ontop = 1
ownpal = 1

[State 3100, invul]
type = NotHitBy
trigger1 = Time < 30
value = SCA
time = 1

[State 3100, dash]
type = VelSet
trigger1 = Time = 4
x = 15

[State 3100, afterimage]
type = AfterImage
trigger1 = Time = 4
time = 26
length = 8
timegap = 1
framegap = 2
trans = add
paladd = 0, 60, 90
palmul = 0.3, 0.7, 1

[State 3100, grab]
type = HitDef
trigger1 = Time = 4
attr = S, HA
damage = 0, 0
animtype = Hard
hitflag = MAF
priority = 7, Hit
pausetime = 0, 0
sparkno = -1
hitsound = S1, 1
p1stateno = 3110
p2stateno = 3150
p2getp1state = 1
p1facing = 1
p2facing = 1
ground.type = High
getpower = 0, 0

[State 3100, stop]
type = VelSet
trigger1 = Time = 26
x = 0

[State 3100, whiff]
type = ChangeState
trigger1 = Time >= 34
value = 3111

;---------------------------------------------------------------------------
[Statedef 3110]
type = S
movetype = A
physics = N
velset = 0, 0
ctrl = 0
anim = 3110
sprpriority = 3

[State 3110, invul]
type = NotHitBy
trigger1 = 1
value = SCA
time = 1

[State 3110, hold]
type = TargetBind
trigger1 = Time < 140
pos = 120, 0

[State 3110, corruption]
type = Explod
trigger1 = Time = 0
anim = 6120
pos = 120, -110
postype = p1
removetime = 60
sprpriority = 4
ownpal = 1

[State 3110, beam sfx]
type = PlaySnd
trigger1 = Time = 0
value = S1, 4

[State 3110, chip]
type = TargetLifeAdd
trigger1 = Time > 0
trigger1 = Time <= 60
trigger1 = (Time % 6) = 0
value = -floor(22 * fvar(1))

[State 3110, chip spark]
type = Explod
trigger1 = Time > 0
trigger1 = Time <= 60
trigger1 = (Time % 6) = 0
anim = 6020
pos = 100 + (Random % 50), -60 - (Random % 120)
postype = p1
removetime = 10
sprpriority = 5
ownpal = 1

[State 3110, chip sfx]
type = PlaySnd
trigger1 = Time > 0
trigger1 = Time <= 60
trigger1 = (Time % 12) = 0
value = S5, 0

[State 3110, crash screen]
type = Explod
trigger1 = Time = 64
anim = 6110
postype = left
pos = 320, 240
removetime = 70
sprpriority = 20
ontop = 1
ownpal = 1

[State 3110, crash sfx]
type = PlaySnd
trigger1 = Time = 64
value = S1, 1

[State 3110, crash sfx 2]
type = PlaySnd
trigger1 = Time = 100
value = S1, 5

[State 3110, crash shake]
type = EnvShake
trigger1 = Time = 64
time = 20
ampl = 6

[State 3110, final damage]
type = TargetLifeAdd
trigger1 = Time = 134
value = -floor(160 * fvar(1))

[State 3110, final sfx]
type = PlaySnd
trigger1 = Time = 134
value = S5, 3

[State 3110, final spark]
type = Explod
trigger1 = Time = 134
anim = 6080
pos = 120, -110
postype = p1
removetime = 15
sprpriority = 5
ownpal = 1

[State 3110, launch]
type = TargetVelSet
trigger1 = Time = 134
x = -10
y = -10

[State 3110, release]
type = TargetState
trigger1 = Time = 134
value = 3151

[State 3110, end]
type = ChangeState
trigger1 = Time >= 140
value = 3111

;---------------------------------------------------------------------------
[Statedef 3111]
type = S
movetype = I
physics = S
velset = 0, 0
ctrl = 0
anim = 3111

[State 3111, end]
type = ChangeState
trigger1 = AnimTime = 0
value = 0
ctrl = 1

;---------------------------------------------------------------------------
; P2: being corrupted (P2's own sprites)
[Statedef 3150]
type = S
movetype = H
physics = N
velset = 0, 0

[State 3150, anim]
type = ChangeAnim2
trigger1 = Time = 0
value = 820

[State 3150, glitch]
type = PalFX
trigger1 = (Time % 8) = 0
time = 4
add = 0, 80, 120
invertall = 1

[State 3150, safety]
type = SelfState
trigger1 = Time > 1
trigger1 = !GetHitVar(isbound)
value = 5050

;---------------------------------------------------------------------------
; P2: launched after the crash
[Statedef 3151]
type = A
movetype = H
physics = N

[State 3151, anim]
type = ChangeAnim2
trigger1 = Time = 0
value = 821

[State 3151, gravity]
type = VelAdd
trigger1 = 1
y = 0.8

[State 3151, land]
type = SelfState
trigger1 = Vel Y > 0
trigger1 = Pos Y >= 0
value = 5100
