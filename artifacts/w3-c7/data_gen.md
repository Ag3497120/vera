# W3-c7 検査データの作り方
- 生成: `cd <ツリー> && python3 artifacts/w3-c7/tools/mk_data.py --seed 300701`（`random.Random(300701)`）。出力は `tests/reading_soundness/w3c7_{multi,te,quote,sharing,anaphora}.jsonl`。
- 期待はテンプレート（節の表・接続語の表・K300〜K307・H300〜H308）から書いた。読解器・段 C7 は呼んでいない（段 C7 はまだ存在しない）。`source: generated seed` が機械で並べた行、`source: hand` が手で書いた行。
- 凍結前に行ったのは、トークンの品詞・切れ目の検出が想定どおりかの確認だけ（W3-b3 の純関数 `w3b3_groups`・`w3b3_cuts`・`w3b3_unlisted` と品詞。出力は `artifacts/w3-c7/tools` の外の作業用脚本）。単独の節を基点の入口で読んで、語（述語・名詞）が読める語であることを確かめた（期待の十字は基点の入口の単独の読みと同じ形で書いた）。
- `w3c7_placement_r9.jsonl`（配置の答えの記録）は段 C7 を実装した後に、実物の r9 の答えをそのまま記録して作る（凍結の対象外。別に sha256 を残す）。
