// 承太郎ボットの設定。変更したらサーバーを再起動する。
export const CONFIG = {
  // ゲーム内でのプレイヤー名
  botName: "空条承太郎",
  // 頭脳プログラム(brain)の待ち受けアドレス。brain/.env の PORT と合わせる
  brainUrl: "http://127.0.0.1:3920",
  // 頭脳と通信する間隔(ティック。20で1秒)
  pollTicks: 10,
  // 出現時にスタープラチナのスタンドディスクを持たせる
  giveStand: true,
  // 承太郎スキンを表示するための帽子アイテム(頭装備枠)を着ける
  wearSkin: true,
  // 人間のプレイヤーが誰もいなくなったら退出する(APIの無駄遣い防止)
  despawnWhenEmpty: true,
  // モブに殴られたとき、指示待ちなら自動で反撃する
  autoDefend: true,
};
