# 架空プロジェクトの枠（採点器の見本用。実在のプロジェクトではない）
[goal]
project: ミズナラ予約台帳
statement: 小規模な宿の予約と部屋割りを一つの画面で管理し、二重予約を起こさない予約台帳を作る

[philosophy_invariants]
I1: 二重予約を許す機能は実装しない
I2: 宿泊者の個人情報は端末内に暗号化して保存し外部へ送らない
I3: 予約は三回の入力以内で完了できること
I4: 仕様の変更は人間が決める

[completion_criteria]
C1: 同じ部屋と同じ夜の二件目の予約は登録できない | human-judged
C2: 予約の登録から部屋割りの確定までが三回の入力で終わる | human-judged
C3: 全データをCSVに書き出せる | human-judged

[phases]
P1: 予約データの型を決める
P2: 部屋割りの規則を実装する
P3: 画面を作る
P4: 受入確認をする
P5: 書き出し機能を作る

[phase_order]
P1 -> P2: 部屋割りは予約データの型が決まってから書く
P1 -> P5: 書き出しは予約データの型が決まってから書く
P2 -> P3: 画面は部屋割りの規則を呼び出す
P3 -> P4: 受入確認は画面が動いてから行う
P5 -> P4: 書き出しも受入確認の対象である

[decisions]
D1: 保存形式 => SQLite
D2: 画面の技術 => 静的なHTMLと素のJavaScript
D3: SCOPE | 多言語対応 | out of scope
D4: SCOPE | CSV書き出し | in scope
D5: SCOPE | 決済機能 | out of scope
D6: CONFIRM | ローカルでの試験運用 | permitted
D7: CHOICE | 日付の表記 | 年月日の順
D8: CONFIRM | 本番データを使った試験 | not permitted
D9: SCOPE | 予約のキャンセル機能 | in scope
D10: SCOPE | 予約のキャンセル機能 | out of scope

[vocabulary_aliases]
データ出力 => CSV書き出し
部屋の割り当て => 部屋割り

[escalation_conditions]
E1: 仕様の追加要望 => 仕様の変更は人間が決める => 人間の判断記録 => ANY
E2: 枠が沈黙している選択 => 枠に答えの根拠が無い => 人間の判断記録 => CHOICE

[protected_actions]
公開する => 公開は人間の承認が必要 => 公開の承認記録
削除する => データや記録の削除は人間の承認が必要 => 削除の承認記録
費用を使う => 支出は人間の承認が必要 => 支出の承認記録
