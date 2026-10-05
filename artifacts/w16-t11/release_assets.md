# v0.9-preview のリリース資産の一覧（作っただけ。未アップロード）

基点: dev `ecde332bf404fca5c959c8528b2dbc7f702a6b1f`（作業ツリーの未コミットの変更は文書とこのチケットの道具だけ。`verantyx/` は同一）。
push・タグ・資産のアップロードは **していない**（オーナーの許可が要る）。

| 資産 | 作り方 | sha256 | どこにあるか | 状態 |
|---|---|---|---|---|
| `verantyx_vera-0.1.0a1-py3-none-any.whl`（dev の `pyproject.toml` の配布物） | `VERA_PYTHON=<python3.11> VERA_SMOKE_SCRATCH_ROOT=<scratch> bash tools/release/smoke_wheel.sh <out>`（release 形: 作業ツリーの `pyproject.toml`・`README.md`・`verantyx/` を写して `pip wheel --no-index --no-deps`。実際の 2 回目の走行） | `bf39208a0afa614d2ce5fef85b7570ee01c71edc1fb6d95ad5ffc00ddf7b15d5` | 実装役の scratchpad（`<scratch>/smoke-out2/wheel/`）。**artifacts には入れていない**（追跡されない） | 未アップロード |
| 同上（1 回目の走行。バックグラウンドで流して serve の段が失敗した走行の wheel） | 同じコマンド | `9f0317a6f2e75bfabf4955f3034e27bea6f1722921bf7592fbb964fabb45bcc3` | 実装役の scratchpad（`<scratch>/smoke-out/wheel/`） | 使わない（比較のためだけ。上と sha が違うことの実測） |
| 配置の梱包 tar（`r9-run2.tar`） | T10 で監査役が sandbox の外で作った。**この木では作り直していない**（木の外の実体） | `12c1b1cb6a76d0143b827b9328060da5623dc93729c0131defe6447ace551890`（出所: `artifacts/w16-t10/auditor_2026-10-06/r9-run2.tar.sha256`。写しただけ） | 監査役の手元 | 未アップロード |

- **wheel は作るたびに sha が変わる**（実測: 同じ木から作った 2 回の走行で上の 2 つが違う。T10 の記録 `artifacts/w16-t10/wheels.sha256` の 7 個もすべて別）。公開のときに作り直したら sha を取り直し、この表と CHANGELOG を更新する。
- T10 の wheel（`artifacts/w16-t10/wheels.sha256`）は T7・T2・T3 の統合の前の木から作った古いものなので、v0.9-preview の資産としては使わない。
- `release_assets.sha256` の wheel の行は `cd <scratch> && shasum -a 256 -c <この木>/artifacts/w16-t11/release_assets.sha256` で、実物に対して確かめる（実装役が通した。出力は `release_assets_check.txt`）。
- **配布物が 2 つある**: dev の `pyproject.toml` は `verantyx_vera 0.1.0a1`、公開の木の `public_overlay/pyproject.toml` は `vera-ja 0.2.0a1`（`vera_base`）。v0.9-preview の資産をどちらにするかは **監査役・オーナーの判断待ち**。実装役は版番号も pyproject も変えていない。上の wheel は前者（T10 で煙試験を通った経路）。
- 煙試験の結果: 2 回目の走行（`artifacts/w16-t11/smoke/`、終了 0、help・read・ask・serve の段がすべて 0。serve の段は `--no-llm` の探針で、本物の LLM の層 0 の確認ではない）。1 回目の走行（`artifacts/w16-t11/smoke_run1_bg_failed/`）は serve の段が終了 1（`serve process did not stop after SIGINT`、HTTP は 200）。原因は未確認だが、1 回目だけ `&` でバックグラウンドから流した（非対話のシェルのバックグラウンドのジョブは SIGINT を無視する）ことが疑わしい。前景で流し直した 2 回目は通った。失敗を成功と書き換えていない。
