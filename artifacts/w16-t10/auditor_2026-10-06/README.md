# 監査役の検証（2026-10-06、sandbox の外）

- P1/P2: `VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python VERA_SMOKE_SCRATCH_ROOT=<scratch> bash tools/release/smoke_wheel.sh <out>` → `p1-verification.json`（PASS。serve の `/v1/models` の応答は `serve-response.json`）、`p2-verification.json`（PASS）。
- P3: r9/run2（`wt/W3-a6-S/build/coarse-W3a/full/r9/run2`、`r9_inputs.sha256`）を `tools/release/pack_placement.sh` で梱包（`pack.out`、`r9-run2.tar.sha256`）→ wheel の `vera placement fetch --from file://… --dest …`（`fetch.json`）→ 展開後の sha（`fetched.sha256`）は元と一致。
- 読解: 公開の入口文（`artifacts/w3-b1/entry_inputs.txt` の先頭 600 文）のうち、配置で出力が変わる 50 文（すべて棄権→棄権で、理由だけが変わる）から先頭 10 文（`sentences3.txt`）。wheel の `vera read --strict-read` を配置なし・元の r9・取得した r9 で流した出力が `read3/`、比較が `read_compare.tsv`: 取得 = 元 10/10、配置なしと違う 10/10。
- 単純な他動詞文 18 文（配置なしでも読める）では、配置の有無で出力は同じだった（この表には入れていない）。
