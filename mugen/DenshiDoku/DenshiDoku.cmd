; 電子 独 (Denshi Doku) -- command file
; x,y,z = パンチ (マフラー)   a,b,c = キック   s = 挑発

[Remap]
x = x
y = y
z = z
a = a
b = b
c = c
s = s

[Defaults]
command.time = 15
command.buffer.time = 1

;-| 超必殺技 |----------------------------------------------------------------
[Command]
name = "fatal"
command = ~D, DF, F, D, DF, F, x
time = 30
[Command]
name = "fatal"
command = ~D, DF, F, D, DF, F, y
time = 30
[Command]
name = "fatal"
command = ~D, DF, F, D, DF, F, z
time = 30

[Command]
name = "crash"
command = ~D, DF, F, D, DF, F, a
time = 30
[Command]
name = "crash"
command = ~D, DF, F, D, DF, F, b
time = 30
[Command]
name = "crash"
command = ~D, DF, F, D, DF, F, c
time = 30

;-| 必殺技 |------------------------------------------------------------------
[Command]
name = "lash_x"
command = ~F, D, DF, x
[Command]
name = "lash_y"
command = ~F, D, DF, y
[Command]
name = "lash_z"
command = ~F, D, DF, z

[Command]
name = "shot_x"
command = ~D, DF, F, x
[Command]
name = "shot_y"
command = ~D, DF, F, y
[Command]
name = "shot_z"
command = ~D, DF, F, z

[Command]
name = "warp_a"
command = ~D, DB, B, a
[Command]
name = "warp_b"
command = ~D, DB, B, b
[Command]
name = "warp_c"
command = ~D, DB, B, c

[Command]
name = "corrupt"
command = ~D, D, x
[Command]
name = "corrupt"
command = ~D, D, y
[Command]
name = "corrupt"
command = ~D, D, z

;-| 移動 |--------------------------------------------------------------------
[Command]
name = "FF"
command = F, F
time = 10

[Command]
name = "BB"
command = B, B
time = 10

[Command]
name = "recovery"
command = x+y
time = 1
[Command]
name = "recovery"
command = a+b
time = 1

;-| 投げ |--------------------------------------------------------------------
[Command]
name = "fwd_y"
command = /F, y
time = 1
[Command]
name = "back_y"
command = /B, y
time = 1

;-| ボタン単体 |--------------------------------------------------------------
[Command]
name = "x"
command = x
time = 1
[Command]
name = "y"
command = y
time = 1
[Command]
name = "z"
command = z
time = 1
[Command]
name = "a"
command = a
time = 1
[Command]
name = "b"
command = b
time = 1
[Command]
name = "c"
command = c
time = 1
[Command]
name = "s"
command = s
time = 1

;-| 押しっぱなし |------------------------------------------------------------
[Command]
name = "holdfwd"
command = /$F
time = 1
[Command]
name = "holdback"
command = /$B
time = 1
[Command]
name = "holdup"
command = /$U
time = 1
[Command]
name = "holddown"
command = /$D
time = 1

;=============================================================================
[Statedef -1]
;=============================================================================

;=============================================================================
; CPU (AILevel > 0) -- simple AI. Probabilities scale with the AI level.
;=============================================================================
[State -1, AI: SYSTEM CRASH]
type = ChangeState
value = 3100
triggerall = AILevel > 0
triggerall = power >= 3000 && statetype != A
triggerall = P2BodyDist X < 220 && P2StateType != L
trigger1 = ctrl && Random < AILevel * 8
trigger2 = (stateno = [200, 499]) && MoveHit

[State -1, AI: FATAL ERROR]
type = ChangeState
value = 3000
triggerall = AILevel > 0
triggerall = power >= 1000 && statetype != A
triggerall = P2StateType != L
trigger1 = ctrl && Random < AILevel * 4
trigger2 = (stateno = [200, 499]) && MoveHit && Random < 500

[State -1, AI: self corrupt]
type = ChangeState
value = 1300
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
triggerall = var(10) = 0
triggerall = life > 300
trigger1 = P2BodyDist X > 300 && Random < AILevel * 2

[State -1, AI: anti-air]
type = ChangeState
value = ifelse(Random < 500, 1200, 420)
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
trigger1 = P2StateType = A && P2MoveType != H
trigger1 = P2BodyDist X < 150 && P2Dist Y < -40
trigger1 = Random < AILevel * 60

[State -1, AI: combo into special]
type = ChangeState
value = ifelse(Random < 600, 1000, 1200)
triggerall = AILevel > 0
triggerall = statetype != A
trigger1 = (stateno = [210, 249]) || (stateno = [410, 449])
trigger1 = MoveHit && Random < AILevel * 90

[State -1, AI: chain medium]
type = ChangeState
value = ifelse(statetype = C, 410, 210)
triggerall = AILevel > 0
trigger1 = stateno = 200 || stateno = 230 || stateno = 400 || stateno = 430
trigger1 = MoveContact && Random < AILevel * 100

[State -1, AI: bug shot]
type = ChangeState
value = 1000
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
triggerall = NumProjID(1000) = 0
trigger1 = P2BodyDist X > 250 && Random < AILevel * 6

[State -1, AI: warp behind]
type = ChangeState
value = 1100
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
trigger1 = P2BodyDist X = [120, 400]
trigger1 = Random < AILevel * 2

[State -1, AI: dash in]
type = ChangeState
value = 100
triggerall = AILevel > 0
triggerall = ctrl && statetype = S
trigger1 = P2BodyDist X > 280 && Random < AILevel * 4

[State -1, AI: throw]
type = ChangeState
value = 800
triggerall = AILevel > 0
triggerall = ctrl && statetype = S
triggerall = P2StateType != A && P2MoveType != H
trigger1 = P2BodyDist X < 30 && Random < AILevel * 20

[State -1, AI: close normals]
type = ChangeState
value = ifelse(Random < 400, 200, ifelse(Random < 500, 430, 240))
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
trigger1 = P2BodyDist X < 90 && P2StateType != L
trigger1 = Random < AILevel * 25

[State -1, AI: mid pokes]
type = ChangeState
value = ifelse(Random < 500, 220, 450)
triggerall = AILevel > 0
triggerall = ctrl && statetype != A
trigger1 = P2BodyDist X = [90, 170] && P2StateType != L
trigger1 = Random < AILevel * 10

[State -1, AI: air attack]
type = ChangeState
value = ifelse(Random < 500, 640, 620)
triggerall = AILevel > 0
triggerall = ctrl && statetype = A
trigger1 = P2BodyDist X < 120 && Random < AILevel * 40

;=============================================================================
; Player
;=============================================================================

;---------------------------------------------------------------------------
; 超必殺技
[State -1, SYSTEM CRASH]
type = ChangeState
value = 3100
triggerall = !AILevel
triggerall = command = "crash"
triggerall = power >= 3000
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact
trigger3 = (stateno = [1000, 1299]) && MoveContact

[State -1, FATAL ERROR]
type = ChangeState
value = 3000
triggerall = !AILevel
triggerall = command = "fatal"
triggerall = power >= 1000
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact
trigger3 = (stateno = [1000, 1299]) && MoveContact
trigger4 = stateno = 1000 && AnimElemNo(0) >= 2

;---------------------------------------------------------------------------
; 必殺技
[State -1, Self Corrupt]
type = ChangeState
value = 1300
triggerall = !AILevel
triggerall = command = "corrupt"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact

[State -1, Data Lash]
type = ChangeState
value = 1200
triggerall = !AILevel
triggerall = command = "lash_x" || command = "lash_y" || command = "lash_z"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact

[State -1, Bug Shot]
type = ChangeState
value = 1000
triggerall = !AILevel
triggerall = command = "shot_x" || command = "shot_y" || command = "shot_z"
triggerall = statetype != A
triggerall = NumProjID(1000) = 0
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact

[State -1, Glitch Warp]
type = ChangeState
value = 1100
triggerall = !AILevel
triggerall = command = "warp_a" || command = "warp_b" || command = "warp_c"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 499]) && MoveContact

;---------------------------------------------------------------------------
; 投げ
[State -1, Throw]
type = ChangeState
value = 800
triggerall = !AILevel
triggerall = command = "fwd_y" || command = "back_y"
triggerall = statetype = S
triggerall = ctrl
trigger1 = P2BodyDist X < 30
trigger1 = P2StateType != A
trigger1 = P2MoveType != H

;---------------------------------------------------------------------------
; ダッシュ / バックステップ
[State -1, Dash]
type = ChangeState
value = 100
triggerall = !AILevel
trigger1 = command = "FF"
trigger1 = statetype = S
trigger1 = ctrl

[State -1, Back step]
type = ChangeState
value = 105
triggerall = !AILevel
trigger1 = command = "BB"
trigger1 = statetype = S
trigger1 = ctrl

;---------------------------------------------------------------------------
; 立ち通常技 (弱→中→強 のチェーン可)
[State -1, Stand z]
type = ChangeState
value = 220
triggerall = !AILevel
triggerall = command = "z" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = [200, 249] || stateno = [400, 449]) && stateno != 220 && MoveContact

[State -1, Stand c]
type = ChangeState
value = 250
triggerall = !AILevel
triggerall = command = "c" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = [200, 249] || stateno = [400, 449]) && MoveContact

[State -1, Stand y]
type = ChangeState
value = 210
triggerall = !AILevel
triggerall = command = "y" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230 || stateno = 400 || stateno = 430) && MoveContact

[State -1, Stand b]
type = ChangeState
value = 240
triggerall = !AILevel
triggerall = command = "b" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230 || stateno = 400 || stateno = 430) && MoveContact

[State -1, Stand x]
type = ChangeState
value = 200
triggerall = !AILevel
triggerall = command = "x" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230) && MoveContact && AnimElemNo(0) >= 3

[State -1, Stand a]
type = ChangeState
value = 230
triggerall = !AILevel
triggerall = command = "a" && command != "holddown"
triggerall = statetype = S
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230) && MoveContact && AnimElemNo(0) >= 3

;---------------------------------------------------------------------------
; しゃがみ通常技
[State -1, Crouch z]
type = ChangeState
value = 420
triggerall = !AILevel
triggerall = command = "z" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 249] || stateno = [400, 449]) && stateno != 420 && MoveContact

[State -1, Crouch c]
type = ChangeState
value = 450
triggerall = !AILevel
triggerall = command = "c" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = [200, 249] || stateno = [400, 449]) && MoveContact

[State -1, Crouch y]
type = ChangeState
value = 410
triggerall = !AILevel
triggerall = command = "y" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230 || stateno = 400 || stateno = 430) && MoveContact

[State -1, Crouch b]
type = ChangeState
value = 440
triggerall = !AILevel
triggerall = command = "b" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = 200 || stateno = 230 || stateno = 400 || stateno = 430) && MoveContact

[State -1, Crouch x]
type = ChangeState
value = 400
triggerall = !AILevel
triggerall = command = "x" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = 400 || stateno = 430) && MoveContact && AnimElemNo(0) >= 3

[State -1, Crouch a]
type = ChangeState
value = 430
triggerall = !AILevel
triggerall = command = "a" && command = "holddown"
triggerall = statetype != A
trigger1 = ctrl
trigger2 = (stateno = 400 || stateno = 430) && MoveContact && AnimElemNo(0) >= 3

;---------------------------------------------------------------------------
; 空中通常技
[State -1, Air x]
type = ChangeState
value = 600
triggerall = !AILevel
triggerall = command = "x"
triggerall = statetype = A
trigger1 = ctrl

[State -1, Air y]
type = ChangeState
value = 610
triggerall = !AILevel
triggerall = command = "y"
triggerall = statetype = A
trigger1 = ctrl
trigger2 = (stateno = 600 || stateno = 630) && MoveContact

[State -1, Air z]
type = ChangeState
value = 620
triggerall = !AILevel
triggerall = command = "z"
triggerall = statetype = A
trigger1 = ctrl
trigger2 = (stateno = [600, 649]) && stateno != 620 && MoveContact

[State -1, Air a]
type = ChangeState
value = 630
triggerall = !AILevel
triggerall = command = "a"
triggerall = statetype = A
trigger1 = ctrl

[State -1, Air b]
type = ChangeState
value = 640
triggerall = !AILevel
triggerall = command = "b"
triggerall = statetype = A
trigger1 = ctrl
trigger2 = (stateno = 600 || stateno = 630) && MoveContact

[State -1, Air c]
type = ChangeState
value = 650
triggerall = !AILevel
triggerall = command = "c"
triggerall = statetype = A
trigger1 = ctrl
trigger2 = (stateno = [600, 649]) && MoveContact

;---------------------------------------------------------------------------
; 挑発
[State -1, Taunt]
type = ChangeState
value = 195
triggerall = !AILevel
triggerall = command = "s"
trigger1 = statetype = S
trigger1 = ctrl
