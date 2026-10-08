
#### 追記（2026-10-04 07:02:58 +0900。W1-a5-2 の続き。監査役の実行上の注意により、副詞の門の 5 関数は消さず、呼ばない形で残す）

記録日時は `artifacts/w1-a5/r2/change_time_addendum.txt`。この追記の時点で、5 関数はまだ戻していない（順序: この追記 → データ・テストの凍結の確認 → 直す前の記録 → 5 関数を戻す → C1・C2・C5・決め打ちの流し直し）。上の 06:30:39 の記録の本文は書き換えない。

- **前**（06:30:39 の変更 1「消すもの」と H235）: 副詞の門の関数 `_w1a5_hira`・`_w1a5_adverb_class`・`_w1a5_after_adverb`・`_w1a5_np_boundary`・`_w1a5_adverb_gate` を消す。この追記の時点の木は、そのとおり 5 関数を消している（`artifacts/w1-a5/r2/pre_restore/semantic_reader.before_restore.py.txt`）。
- **後**: 5 関数を第 1 ラウンドの本文のまま（1 字も変えずに。`artifacts/w1-a5/r2/semantic_reader.r1.py.txt` の本文）区画に戻す。どこからも呼ばない（`_w1a5_reread`・`w1a5_wrap` から呼ばれない）。見出しのコメントは「K213 withdrawn (K218, round 2): the mark of an adverb is not made; the functions of its gates stay and are not called」の型（英語。例文・日本語の語を書かない）。呼び出し側（引き金 T4 の副詞・`exempt`・副詞の門の繰り返し・A6・`flags`）は変更 1 のとおり外したまま。登録の定数・表は残す（変更なし）。変更 1 の「消すもの」のうち「関数 … を消し」は「呼ばない形で残す」に読み替える。
- **理由**: 監査役の実行上の注意（「副詞の区画は呼び出しを外す。削除行 0 の制約は守る: 呼ばない形にして関数は残し、docs に撤回を書く」）。関数を消す形は中間職の指示書 `plan.md` §2.3 の 3 に従ったもので、監査役の注意が指示書より優先する（`review.r1.md` 必須 4）。基点 `df4f001` に対する `-` 行は、どちらの形でも 0。
- **出典**: 監査役の実行上の注意（W1-a5-2 第 2 ラウンドの起動時）、`.claude/vera-audit/review-impl/W1-a5-2/review.r1.md` 必須の修正 4、同 1〜3。
- **振る舞いの同値**: 5 関数は呼ばれないので、出力は変わらない。戻した後に、最小の変更の写し（`plan_evidence/sim_change.diff`）との出力のバイト比較と、戻す前の出力との比較（全入力）を `artifacts/w1-a5/r2/` に記録する（結果は K226 の「第 2 ラウンドの続き」）。
- 同じ追記を `artifacts/w1-a5/r2/CHANGE_K218_addendum.md` に写した（`CHANGE_K218.md` は書き換えない）。
