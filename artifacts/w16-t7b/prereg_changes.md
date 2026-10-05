# W16-t7b 凍結後の試験の変更（第 2 ラウンド）

- 変更前の試験ファイルの sha256: 62c32779be15cf02c1e79fa5223cdd03a00c8b0559ab242760ad0bf295fe44ea（prereg_sha256.txt の値）。既存 19 本の期待は変えていない。
- 追加（レビュー M1 への対応。末尾に追記、既存の関数は一字も変えていない）: test_m1a_python_and_code_root_together、test_m1b_vera_cmd_exclusive_with_python_and_code_root（6 パラメータ）、test_m1c_frozen_requires_both。
- 理由: --python と --code-root の同時指定を認め、--vera-cmd とは排他（終了 2）にし、凍結物は両方必須にしたため。
- 追加後の sha256 は prereg_sha256.txt の 2 行目に追記。
