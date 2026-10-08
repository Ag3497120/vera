# W5-b 第2波・攻撃ケース事前登録

登録時刻: 2026-10-03 13:05:16 UTC

製品コードは変更しない。偽の mapper は許すが、本物の LLM/provider は起動しない。各ケースはこの表の入力と期待を変えずに実行し、期待を満たさない実出力だけを命中として報告する。安全側の棄権を成功とするケースは、回答が出た場合に限り命中。

| ID | 対象・入力 | 期待する出力 |
|---|---|---|
| M1 | `tests/test_conduct_map_w5b.py` と同じ小さな scripted mapping 台帳を作り、台帳 JSONL の行順だけを逆転。manifest はそのまま。 | replay/回答をせず `LEDGER_INTEGRITY`。 |
| M2 | 新規の scripted mapping 台帳で、最後の `map_*` 行を重複追記し manifest はそのまま。 | replay/回答をせず `LEDGER_INTEGRITY`。 |
| M3 | 新規の scripted mapping 台帳で、manifest に記録された最後の `map_*` 行を台帳末尾から切り詰める。 | replay/回答をせず `LEDGER_INTEGRITY`。 |
| K1 | `ヒナタ丸` を `ARTIFACT`、`ひなた丸` を `GROUP_ORG` とする二つの direct DECIDED placement。 | 各綴りは自身の direct 型を返し、差を明示。相手の型を借りた estimated 判定や勝者選択をしない。 |
| S1 | 3候補がある sovereign に対し、2プロセスの promote と1プロセスの release を同時開始。 | 終了後 status は RELEASED、active promotions は0、promotion id の二重登録は0。 |
| O1 | 複数経路で観測された要素から座標を1つ落として reobserve。 | `MISMATCH/COORDS_INCOMPLETE`。 |
| R1 | 配置なしで日本語の普通名詞「チーム」を主語にした「チームがテストを書く。」 | 「チーム」を agent 名として route しない。安全側の未決定を返す。 |
| R2 | 既存の割当文の後に `追記：やっぱりそのまま、実装はルナに任せる。` を置く。 | 「そのまま」は置換ではないので既存関係を supersede しない。 |
| A1 | `What’s the language of the invoice archive?` と `Which language for the invoice archive?`。枠の記録は invoice の形式のみ。 | 記録に無い language 属性から回答しない。属性の取り方がどちらも読めない場合も棄権する。 |
| A2 | `Which billing-language should we use for the invoice archive?`。記録に billing-language は無い。 | compound 属性を別の既知語へ縮めて回答せず棄権する。 |
| Q1 | 保護操作の否定依頼 `ログを削除しないでください。`。 | 肯定の削除許可として回答しない。 |
| Q2 | 条件を前置した依頼 `もし可能なら、ログを削除してください。`。 | `HUMAN_APPROVAL_REQUIRED` に上げ、回答しない。 |

期待の根拠: `docs/CONDUCT_ASK.md` §16.1, §16.2, §16.4–16.6; `docs/ROUTING_FROM_TEXT.md` D17, D20; `docs/OBSERVATION.md` §5; `tests/test_coarse_place/test_coarse_place_w5b.py` (実在パスは `tests/coarse_place/test_coarse_place_w5b.py`) と `docs/COARSE_PLACEMENT.md` §11.9。
