# PUB-M2/M3/M4 measurement (offline, no model)

shape table shape.v2 (sha 7c4e3d08d76e59fab592339bdf20ccfaad556a61b2492a47726251a3dd69f9fc), cross serialisation cross.v1.  Script: `experiments/line3/pub/m2/measure.py`; numbers: `results.json`.

## (a) bank5: 6 stories, each message text one write

writes 159: accepted 129 (81.1 %), F0 refused 30 (18.9 %), other refusals {}; accepted but weave_span refused 78 (60.5 % of accepted); topics declared 18.
F0 reasons (clauses): {'gap_is_not_a_particle': 29, 'no_predicate': 1, 'no_relation': 3}.  weave refusals: {'span_inexpressible:gap_is_not_a_particle': 78}.  Accepted clauses by shape: {'F1': 56, 'F2': 165, 'F3': 7}.  Completed by a nest: 0.  Change clauses: 15.

| tank | crosses | seats | max ring L |
|---|---|---|---|
| F1 | 34 | 112 | 6 |
| F2 | 137 | 165 | 1 |
| F3 | 7 | 14 | 2 |
| F4 | 0 | 0 | 0 |

F0 tank sentences 0; nests 6 (members 0, of which completed 0; written under a nest and not members 228); positions 183; history entries: update 0, other 38.

## (b2) the 36 meter v1 stores: the model's raw write calls replayed

writes 2337: accepted 2245 (96.1 %), F0 refused 92 (3.9 %), other refusals {}; accepted but weave_span refused 72 (3.2 % of accepted); topics declared 110.
F0 reasons (clauses): {'case_before_topic': 1, 'gap_is_not_a_particle': 64, 'no_predicate': 10, 'no_relation': 17}.  weave refusals: {'span_inexpressible:gap_is_not_a_particle': 7, 'span_inexpressible:nested_particle_chain': 65}.  Accepted clauses by shape: {'F1': 1682, 'F2': 560, 'F3': 2, 'F4': 1}.  Completed by a nest: 1.  Change clauses: 23.

| tank | crosses | seats | max ring L |
|---|---|---|---|
| F1 | 904 | 3814 | 13 |
| F2 | 428 | 560 | 1 |
| F3 | 3 | 8 | 2 |
| F4 | 0 | 0 | 0 |

F0 tank sentences 0; nests 41 (members 400, of which completed 1; written under a nest and not members 1855); positions 1882; history entries: update 12, other 348.

## (b1) the 36 meter v1 stores' stored sentences (1610 sentences) through build_index

clauses by shape: {'F0': 26, 'F1': 1582, 'F2': 1, 'F4': 1}.

| tank | crosses | seats | max ring L |
|---|---|---|---|
| F1 | 861 | 4477 | 13 |
| F2 | 1 | 1 | 1 |
| F3 | 0 | 0 | 0 |
| F4 | 1 | 2 | 2 |

## 10 sample crosses

```
# meter_v1/MEM-T02/blind/r03
[F1] 所要時間  (L=7, written 6 times)
  の: 登壇者説明(s22){の:運営準備(s22){の:町なか映画祭(s22)}} | 舞台音響チェック(s23){の:運営準備(s23){の:町なか映画祭(s23)}} | 道案内確認(s25){の:運営準備(s25){の:町なか映画祭(s25)}} | 舞台音響チェック(s20){の:運営準備(s20){の:町なか映画祭(s20)}} | 記者説明(s21){の:運営準備(s21){の:町なか映画祭(s21)}} | 確認(s24){の:道案内(s24){の:運営準備(s24){の:町なか映画祭(s24)}}}
  は: 45分(s25) | 45分(s24) | 60分(s23) | 60分(s22) | 30分(s21) | 45分(s20)
```
```
# meter_v1/MEM-T01/blind/r02
[F1] 担当  (L=13, written 12 times)
  の: 文言確認(s9) | 認証モジュール(s2) | リリース窓口(s6) | 手順書確認(s7) | 試験用API監視(s32) | 認証モジュール(s0) | 監視当番(s1) | 決済レビュー(s3) | リリース窓口(s4) | 翻訳確認(s5) | 端末テスト責任者(s8) | スクリーンショット撮影(s18)
  は: 森(s18) | 小林(s7) | 渡辺(s6) | 田中(s3) | 佐藤(s2) | 井上(s32) | 高橋(s9) | 森(s8) | 渡辺(s5) | 小林(s4) | 佐藤(s1) | 田中(s0)
```
```
# meter_v1/MEM-T06/blind/r02
[F1] 担当  (L=11, written 10 times)
  の: 撮影年確認(s7) | 権利確認(s6) | スキャン卓A(s14) | 画像確認係(s15) | チェックサム(s91) | 権利確認(s0){の:メタデータ表(s0)} | 台帳照合(s1){の:メタデータ表(s1)} | スキャン卓A(s8) | 記録係(s13) | 保存形式(s18)
  は: 保存担当(s18) | 前田(s7) | 大谷(s6) | 長谷川(s15) | 三浦(s14) | 河合(s91) | 三浦(s13) | 長谷川(s8) | 大谷(s1) | 前田(s0)
```
```
# meter_v1/MEM-T06/blind/r03
[F2] 原本フォルダ  (L=1, written 5 times)
  は: archive/raw/1950s(s98) | archive/raw/1950s(s74) | archive/raw/1950s(s71) | archive/raw/1950s(s29) | archive/raw/1950s(s27)
```
```
# meter_v1/MEM-T06/notes/r01
[F2] マスター画像形式  (L=1, written 4 times)
  は: PNG(s48) | PNG(s46) | PNG(s42) | TIFF(s22)
```
```
# meter_v1/MEM-T04/notes/r02
[F3] 設定  (L=2, written 1 times)
  に: 7万円(s53)
  を: 端末試験用予算(s53)
  が: リリース(s53){の:倉庫在庫アプリ3.2(s53)[via nest]}[via nest]
```
```
# bank5/MEM-T01
[F3] 行う  (L=2, written 1 times)
  で: 大阪(s9)
  が: 障害訓練(s9)
```
```
# bank5/MEM-T02
[F3] 印刷  (L=2, written 1 times)
  が: プログラム(s12)
  quantity: 450部(s12)
```
```
# meter_v1/MEM-T04/blind/r02
[F1] 担当  (L=11, written 10 times)
  の: 認証運用(s10) | 認証運用(s7) | 認証運用(s6) | 認証運用(s4) | ストア申請(s15) | ログダッシュボード(s74) | ストア申請(s11) | FAQ確認(s12) | 翻訳レビュー(s14) | ログダッシュボード(s63)
  は: 出荷照合平井(s10) | トークン更新松本(s7) | 監査ログ松本(s6) | トークン更新平井(s4) | 西田(s74) | 安藤(s15) | 石田(s14) | 西田(s63) | 安藤(s12) | 石田(s11)
```
```
# meter_v1/MEM-T06/notes/r03
[F1] 記録係  (L=11, written 10 times)
  の: B(s21) | スキャン卓B(s20) | 卓B(s19) | スキャン卓B(s18) | スキャン卓B(s17) | B(s16) | スキャン卓B(s15) | 卓B(s13) | スキャン卓B(s12) | スキャン卓B(s11)
  は: 三浦(s21) | 三浦(s20) | 三浦(s19) | 三浦(s18) | 三浦(s17) | 三浦(s16) | 三浦(s15) | 三浦(s13) | 三浦(s12) | 三浦(s11)
```
