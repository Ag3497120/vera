# K62 の表の出所（W3-a3）

- 出所: `origin/integ-w3b1` の `docs/READING_SOUNDNESS.md` の §10（W3-b1）の「K62 型の表と証拠の門」。§10A の K62 ではない。
- コミット `5d863ddb04a52549dfdcb3172e76ace412d825ad`（`5d863dd`）、blob `0d6233b20c6a1cd717f9a16bb6d96476422864ab`。
- 取得: `git show origin/integ-w3b1:docs/READING_SOUNDNESS.md`。下は、表 `w3b1_frames` の BEGIN の印から END の印まで（印を含む）をそのまま貼ったもの（編集していない）。
- `coarse_types.K62_FRAMES` はこの表の写し（型 id・助詞・名詞の型 id だけ）で、`tests/coarse_place/test_coarse_place_w3a3_k62.py` がこのファイルと機械で照合する。

<!-- BEGIN table:w3b1_frames -->
| 述語の型 | 役割 | 助詞 | 期待する型 | 種類 |
|---|---|---|---|---|
| `P_MOVE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_MOVE` | goal | へ | PLACE | 項 |
| `P_MOVE` | source | から | PLACE | 項 |
| `P_MOVE` | place | で | PLACE | 付加 |
| `P_MOVE` | time | に | TIME | 付加 |
| `P_COMMUNICATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_COMMUNICATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
| `P_COMMUNICATE` | place | で | PLACE | 付加 |
| `P_COMMUNICATE` | time | に | TIME | 付加 |
<!-- END table:w3b1_frames -->
