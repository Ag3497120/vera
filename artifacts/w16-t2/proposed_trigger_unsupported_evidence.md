# 提案（適用していない）: 後段の引き金に `UNKNOWN_UNSUPPORTED_EVIDENCE` を足す

## 何が起きているか（実測）
統合した経路は、旧 serve が「後段（`_qc_run`）を本読みの結果に関係なく直接呼んでいた」ことをやめ、ask と同じく「本読みが `UNKNOWN_UNREAD` / `UNKNOWN_NO_EVIDENCE` で止まったときだけ後段」にそろえた。
そのため W3-c4 の検査データ（`tests/observe/question_ask`）の次の 2 行は、旧 serve が正答（後段が答えた）だったのに、新では ask・serve・chat のすべてが棄権になった（正答→棄権 2 行）:
- AQ021 `誰が市場で馬を売った？`（正: 農夫）: 本読みの verdict は `UNKNOWN_UNSUPPORTED_EVIDENCE`（引き金の外）。
- AQ022 `誰が港から魚を送った？`（正: 漁師）: 同じ。
(`artifacts/w16-t2/t2_compare.txt` の w3c4 の節、「changed rows」。)

## 実験（引き金に足した場合。製品の既定ではない）
`run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE`（子プロセスの中で `doc_answer.QC_TRIGGER` に足すだけ）で U4・own60・W3-c4・b2like を流した: `exp_trigger_compare.txt`。
正答→棄権は 0、誤答は足さない前と同じ（own60 の O38 と b2like の BQ002 の 2 行。どちらも基点の ask が既に誤答）。入口間の AnswerResult の不一致は 0。

## 適用に必要なこと（監査役の許可）
`doc_answer.QC_TRIGGER` に型を足すと、次の既存テストが落ちる（引き金の外では同じオブジェクトが返ることを固定している）。
- `tests/test_ask_question_cross.py:81`（`cli._QC_TRIGGER == (...)`）・`:86`（`UNKNOWN_UNSUPPORTED_EVIDENCE` を引き金の外の例にしている）・`:236`
- `tests/attack/test_attack_w3c4.py:241`・`:249-255`（`UNKNOWN_UNSUPPORTED_EVIDENCE` の stub が基点と同じ出力）
事前登録（W3-c4）の「閉じた 2 つ」の変更になるので、実装役は変えなかった。
