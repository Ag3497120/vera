# 公開パッケージの組み立て (W1-b)

開発ツリー（`verantyx/` が直下にあるレイアウト）から、公開リポジトリ `origin/src/public` と同じレイアウト（`vera_base/verantyx/...` ＋ wrapper ＋ `example.py` ＋ `tests/` ＋ `tools/` ＋ `docs/`）を**規則で**組み立て、組み立てた出力が単独で起動することを機械的に確かめる。
このページの数値と一覧はすべて `artifacts/w1-b/` の出力（`manifest.json`、`check_venv311.json`、`check_system313.json`、`determinism.jsonl`、`bundled_tests_*.txt`、`pytest_test_build_public.txt`）から取っている。GitHub への push・公開はしていない（提案は末尾）。

記号: `<W>` = 開発ツリーの根、`$VPY` = fugashi 入りの Python 3.11（venv）、`$SPY` = fugashi 無しのシステム Python 3.13（`command -v python3` の絶対パスで指定する。`env -i` の下の素の `python3` は別物になる）、`<T>` = 一時ディレクトリ。

## 1. 使い方

```bash
T=$(mktemp -d)
env -i $VPY -B <W>/tools/build_public.py --out $T/out1            # 組み立て。--out は存在しないか空であること
env -i $VPY -B <W>/tools/build_public.py --out $T/out2            # 2 回目（出力が同一であることを確かめる）
diff -r $T/out1 $T/out2 && echo IDENTICAL
env -i $VPY -B <W>/tools/check_public.py --digest-only $T/out1 --label run1
git -C <W> archive origin/src/public | tar -x -C $T/pub            # 比較用（先に mkdir $T/pub）
env -i $VPY -B <W>/tools/check_public.py $T/out1 --label venv311   --against $T/pub --json check_venv311.json
env -i $SPY -B <W>/tools/check_public.py $T/out1 --label system313 --against $T/pub --json check_system313.json
env PYTHONPATH=<W> PYTHONDONTWRITEBYTECODE=1 $VPY -B -m pytest -p no:cacheprovider -q tests/test_build_public.py
```

- `build_public.py` の終了コード: 0 成功 / 2 型付きエラー（stderr に JSON 1 行。`OUT_NOT_EMPTY`・`OUT_INSIDE_SRC`・`SRC_MISSING`・`OVERLAY_MISSING`・`PYPROJECT_MISSING`・`PATH_COLLISION`・`EXCLUDED_MODULE_IMPORTED`）。一時ディレクトリで組み、成功したときだけ `--out` へ移すので、失敗しても中途半端な出力は残らない。
- `check_public.py` の終了コード: 0 選んだ検査がすべて PASS（かつ出力が検査中に変わっていない）/ 1 それ以外 / 2 使い方の誤り。結果の種類は `PASS` / `FAIL` / `UNKNOWN_<理由>`（道具が無い・時間切れ）で、`UNKNOWN_*` は合格に数えない。
- 子プロセスは `-B -I`、`env={HOME: 一時dir}`、`cwd=一時dir`。`-I` は `PYTHON*` 環境変数を無視するので、バイトコードのキャッシュを出力に作らないよう必ず `-B` も付ける。

## 2. 規則

### 含めるもの（`manifest.json` の `rules.include`）
- `package_tree`: every file found by walking verantyx/ is copied to vera_base/verantyx/<same relative path>; there is no file list
- `overlay_tree`: every file found by walking the overlay directory is copied to <same relative path>
- `package_data`: pyproject.toml's [tool.setuptools.package-data] table is regenerated from the non-.py files found under vera_base/ (nearest ancestor with __init__.py = the package)

手書きのファイル一覧・サブパッケージ名の一覧は持たない。`verantyx/` 配下をファイルシステムで再帰探索するので、新しいサブパッケージやデータファイルを足せば道具を変えずに出力に入る（`tests/test_build_public.py` の P3 テストで確認）。

### 除くもの（`rules.exclude`。上から順に最初に当たった規則で記録・計数する）

| id | 理由 | 判定 |
|---|---|---|
| `vcs` | version-control data | a path component is .git |
| `cache` | interpreter / tool caches | a path component is __pycache__, .pytest_cache, .mypy_cache or .ruff_cache; or the extension is .pyc/.pyo; or the name is .DS_Store |
| `store_data` | real data of a Vera store (personal / environment data) | the file name starts with vera_store. |
| `measurement` | measurement outputs and run logs (not part of the product) | the extension is .log; or a path component is experiments, results or artifacts |
| `personal_path` | contains an absolute path under a Users directory (personal environment) | the file bytes contain the marker whose hex is 2f55736572732f; only line numbers are recorded |
| `vcs_ignored` | ignored by version control: a local-only file that the author's own ignore rules name | git lists the file as untracked AND ignored (git ls-files --others --ignored --exclude-standard); a tracked file is never excluded by this rule |

- 衝突: if the package layer and the overlay produce the same output path, the build stops with PATH_COLLISION (no layer wins)
- 除外モジュールの import: if a bundled .py imports a module whose file was excluded, the build stops with EXCLUDED_MODULE_IMPORTED
- 版管理の調査（`vcs_survey`）: `--src` が git の作業ツリーの根なら、git に「無視されている（`.gitignore` 等）」ファイルを `vcs_ignored` で除き、「未追跡だが無視されていない」ファイルは含めたうえで `manifest.json` の `vcs.untracked_included` に並べる（パッケージ層だけ。理由は判断 D12）。git が無い・作業ツリーの根でない・git が失敗したときは、除外せず、`vcs.state` に `UNKNOWN_GIT_MISSING` / `UNKNOWN_NOT_A_GIT_TREE` / `UNKNOWN_GIT_ERROR` を型で記録する（「無視されたものは無い」とは読ませない）。読む無視規則は、複製（クローン）と一緒にあるものだけ: ツリー内の `.gitignore`（入れ子のものを含む）と `.git/info/exclude`（クローンごとの手元の規則ファイルなので、同じコミットでもクローンによって除外が変わりうる）。利用者のグローバル設定（`~/.gitconfig`）、既定のグローバル ignore ファイル（`$XDG_CONFIG_HOME/git/ignore` / `$HOME/.config/git/ignore`）、システム設定は読まない（`git -c core.excludesFile=/dev/null` と `GIT_CONFIG_GLOBAL`・`GIT_CONFIG_NOSYSTEM` で無効にしている。効くことは `tests/test_build_public.py::test_users_global_ignore_files_do_not_change_the_output` で確かめている）。
- 個人パスの判定パターンは 16 進（`2f55736572732f`）で持つ。`manifest.json` にもこのページにも個人環境の絶対パスの文字列は入らない。

### 公開側にしか無いファイル（`public_overlay/`）

`public_overlay/` は `origin/src/public` の `vera_base/verantyx/` 以外のファイル 138 個に、次の 2 点だけ手を加えたもの（`tests/conftest.py` の追加で 139 ファイル。出力では pyproject.toml を生成物に回すので、`manifest.json` の `counts.files_by_origin.overlay` は 138）。
- 新規 `tests/conftest.py`: `<root>/vera_base` を `sys.path` の先頭に入れるだけ（公開版の文書が求める `PYTHONPATH=vera_base` を環境変数なしで成り立たせる）。
- 変更 `vera_base/__init__.py`: 任意依存（fugashi・unidic_lite）の欠落ガード（後述の判断 D6）。

開発ツリーの同じパスと比べた結果は `manifest.json` の各 overlay ファイルの `dev_counterpart` に出る。開発側と違う・開発側に無いもの:

| path | dev_counterpart |
|---|---|
| `.gitignore` | differs |
| `EVAL.md` | absent |
| `KNOWN_ISSUES.md` | absent |
| `README.md` | differs |
| `docs/CONSTRUCTIONS_2026-10-02.md` | differs |
| `docs/ROUTE_FOLLOW_2026-10-02.md` | differs |
| `example.py` | absent |
| `pyproject.toml` | differs |
| `release/DATA_CARD.md` | absent |
| `requirements.txt` | absent |
| `tests/conftest.py` | absent |
| `tests/test_memory_revalidate.py` | differs |
| `tests/test_semantic_measure.py` | differs |
| `tests/test_verifier_agents.py` | differs |
| `tools/cov_comparison.py` | differs |
| `tools/cov_giving.py` | differs |
| `tools/cov_negation.py` | differs |
| `tools/cov_np_internal.py` | differs |
| `tools/gold_probe.py` | absent |
| `tools/realize_measure.py` | differs |
| `vera_base/__init__.py` | absent |
| `vera_base/cli.py` | absent |
| `vera_base/corpus.py` | absent |
| `vera_base/data/chat_pack.json` | absent |
| `vera_base/data/pun_lexicon.json` | absent |
| `vera_base/server.py` | absent |

同一（`same`）は 113 ファイル。

## 3. 件数（`artifacts/w1-b/manifest.json` の `counts`）

| 層 | 件数 |
|---|---:|
| package（`verantyx/` を探索） | 315 |
| overlay（公開側にしか無いもの） | 138 |
| generated（`pyproject.toml`。種別 `CONSTRUCTED`） | 1 |
| 合計（`manifest.json` 自身を除く） | 454 |

`manifest.json` は自分のハッシュを書けないので `files` にも件数にも入れない。出力ツリーのファイル数は `check_venv311.json` の `out_file_count`（455）で、manifest を含む。

| 除外の規則 | 件数 |
|---|---:|
| `cache` | 0 |
| `measurement` | 0 |
| `personal_path` | 1 |
| `store_data` | 0 |
| `vcs` | 0 |
| `vcs_ignored` | 0 |
| 合計 | 1 |

除外された全件（`manifest.json` の `excluded`）:

| source_path | layer | rule | 行番号 |
|---|---|---|---|
| `verantyx/build_failure_eval.py` | package | `personal_path` | 22, 23, 47 |

版管理の調査の結果（`manifest.json` の `vcs`）: `state` = `GIT_WORK_TREE`、`untracked_included` = 0 件（`counts.untracked_included_total`）、`layers_not_checked` = 空。実ツリーでは `vcs_ignored` に当たるファイルは 0 件だった（`.gitignore` が名指しする `verantyx/dialogue_context.py` などは作業ツリーに存在しない）。この規則の効きは合成ツリーのテストで確かめている（`tests/test_build_public.py::test_vcs_ignored_files_are_excluded_and_untracked_are_listed`）。`vcs` の節は開発ツリーの git の状態に依存するので、overlay を未追跡のまま組んだ今回の `manifest.json` と、コミット後に組み直した `manifest.json` は `vcs` 以外が同じでも一致するとは限らない（overlay は未追跡を報告しないので、現時点では差は出ない見込みだが、コミット後の再実行では未確認）。

`verantyx/build_failure_eval.py` は実ログ断片の治具で、個人環境の絶対パスを含む。これを import している同梱モジュールは無い（あれば `EXCLUDED_MODULE_IMPORTED` でビルドが止まる）。

出力のパッケージ（`manifest.json` の `packages`、`__init__.py` を持つディレクトリ）: `vera_base`、`vera_base.verantyx`、`vera_base.verantyx.constructions`、`vera_base.verantyx.domains`。

決定性（P1）: 同じ入力から 2 回組んだ出力は `diff -r` で一致し、ダイジェストは次のとおり（`determinism.jsonl`）。

| 実行 | ファイル数 | ダイジェスト |
|---|---:|---|
| run1 | 455 | `dc1243a432c76ec23cf481bae23c5a3add98b1f9215ef504398d2809ca556826` |
| run2 | 455 | `dc1243a432c76ec23cf481bae23c5a3add98b1f9215ef504398d2809ca556826` |

## 4. `origin/src/public` との差

比較は `check_public.py --against`（相対パスごとのバイト比較）。出力ツリー（manifest を含む）を基準に、公開版（`git archive origin/src/public`）との差を出している（`check_venv311.json` の `public_diff`）。

| 区分 | 件数 |
|---|---:|
| 追加（出力にあって公開版に無い） | 123 |
| 変更 | 4 |
| 削除（公開版にあって出力に無い） | 0 |
| 同一 | 328 |

### 変更（全件）

- `pyproject.toml` — 生成。`[tool.setuptools.package-data]` を探索結果から作り直した（公開版の表には `failure_packs`・`field_app.html` が無い）
- `vera_base/__init__.py` — overlay の変更。`Chat` の任意依存欠落ガード
- `vera_base/verantyx/semantic_unknown_choice.py` — 開発ツリー（wave3）のほうが公開版より古い（後述の既知の穴）
- `vera_base/verantyx/verifier_agents.py` — 開発ツリー（wave3）のほうが公開版より古い（後述の既知の穴）

### 削除（全件）

なし。

### 追加（ディレクトリごとの件数と全件）

| ディレクトリ | 件数 |
|---|---:|
| `.` | 1 |
| `tests` | 1 |
| `vera_base/verantyx` | 103 |
| `vera_base/verantyx/constructions` | 1 |
| `vera_base/verantyx/domains` | 1 |
| `vera_base/verantyx/failure_packs` | 15 |
| `vera_base/verantyx/lang_data` | 1 |
| 合計 | 123 |

追加の理由: `manifest.json` は組み立て結果の目録、`tests/conftest.py` は overlay の追加、その他は開発ツリーにあって公開版に取りこぼされていたもの。`vera_base/verantyx/domains/`・`failure_packs/`・`lang_data/`・`constructions/` の追加分は、チケット背景が指摘する「公開版に入っていなかった」ものに当たる。

全件:

- `manifest.json`
- `tests/conftest.py`
<details><summary>`vera_base/verantyx` (103 件)</summary>

- `vera_base/verantyx/agent.py`
- `vera_base/verantyx/agent_forks.py`
- `vera_base/verantyx/agent_tools.py`
- `vera_base/verantyx/ai_ingest.py`
- `vera_base/verantyx/ai_ingest_forks.py`
- `vera_base/verantyx/arc_env_adapter.py`
- `vera_base/verantyx/assembled.py`
- `vera_base/verantyx/attest_llm.py`
- `vera_base/verantyx/audit_app.py`
- `vera_base/verantyx/axis_summary.py`
- `vera_base/verantyx/boundary_eval.py`
- `vera_base/verantyx/build_en.py`
- `vera_base/verantyx/build_failure.py`
- `vera_base/verantyx/capacity_calibration.py`
- `vera_base/verantyx/capacity_ingest.py`
- `vera_base/verantyx/card_numbers.py`
- `vera_base/verantyx/cli.py`
- `vera_base/verantyx/cognitive_interventions.py`
- `vera_base/verantyx/compose.py`
- `vera_base/verantyx/consensus_ab_eval.py`
- `vera_base/verantyx/consensus_forks.py`
- `vera_base/verantyx/constellation.py`
- `vera_base/verantyx/conversation.py`
- `vera_base/verantyx/corpus_aozora.py`
- `vera_base/verantyx/corpus_audit.py`
- `vera_base/verantyx/corpus_fetch.py`
- `vera_base/verantyx/cross_geometry_forks.py`
- `vera_base/verantyx/defect_gaps.py`
- `vera_base/verantyx/doctor.py`
- `vera_base/verantyx/domain_ingest.py`
- `vera_base/verantyx/drift.py`
- `vera_base/verantyx/experience.py`
- `vera_base/verantyx/experience_cross.py`
- `vera_base/verantyx/export_view3d.py`
- `vera_base/verantyx/failure_domains.py`
- `vera_base/verantyx/failure_domains_eval.py`
- `vera_base/verantyx/field_app.html`
- `vera_base/verantyx/field_app.py`
- `vera_base/verantyx/field_reports.py`
- `vera_base/verantyx/field_reports_eval.py`
- `vera_base/verantyx/field_session.py`
- `vera_base/verantyx/gapnode.py`
- `vera_base/verantyx/generalization_eval.py`
- `vera_base/verantyx/hf_store.py`
- `vera_base/verantyx/index.py`
- `vera_base/verantyx/ingest_coherence.py`
- `vera_base/verantyx/intent_chain.py`
- `vera_base/verantyx/jgen_lexicon.py`
- `vera_base/verantyx/kripke_rewrite_forks.py`
- `vera_base/verantyx/lang_router_forks.py`
- `vera_base/verantyx/layer_stack.py`
- `vera_base/verantyx/lean_witness.py`
- `vera_base/verantyx/lean_witness_forks.py`
- `vera_base/verantyx/llm_local.py`
- `vera_base/verantyx/math_sim_forks.py`
- `vera_base/verantyx/mcp_server.py`
- `vera_base/verantyx/module_forge.py`
- `vera_base/verantyx/module_ingest.py`
- `vera_base/verantyx/module_verify.py`
- `vera_base/verantyx/multilingual_eval.py`
- `vera_base/verantyx/obfuscate_forks.py`
- `vera_base/verantyx/observation.py`
- `vera_base/verantyx/own_ai_guide.py`
- `vera_base/verantyx/pack_authoring.py`
- `vera_base/verantyx/pack_ingest.py`
- `vera_base/verantyx/phase2_forks.py`
- `vera_base/verantyx/placement_explain.py`
- `vera_base/verantyx/pour_forks.py`
- `vera_base/verantyx/preregistration.py`
- `vera_base/verantyx/procedure.py`
- `vera_base/verantyx/procedure_exec.py`
- `vera_base/verantyx/procedure_ingest.py`
- `vera_base/verantyx/procedure_vary.py`
- `vera_base/verantyx/proof_ledger.py`
- `vera_base/verantyx/proposal.py`
- `vera_base/verantyx/proposal_verify.py`
- `vera_base/verantyx/prover.py`
- `vera_base/verantyx/release.py`
- `vera_base/verantyx/rewrite_eval.py`
- `vera_base/verantyx/rewrite_math.py`
- `vera_base/verantyx/rotation_signature.py`
- `vera_base/verantyx/rule_synthesis.py`
- `vera_base/verantyx/self_audit.py`
- `vera_base/verantyx/self_evolve.py`
- `vera_base/verantyx/self_harness.py`
- `vera_base/verantyx/serve_view3d.py`
- `vera_base/verantyx/settings_guide.py`
- `vera_base/verantyx/settings_registry.py`
- `vera_base/verantyx/settings_registry_eval.py`
- `vera_base/verantyx/structural_similarity.py`
- `vera_base/verantyx/structure_forks.py`
- `vera_base/verantyx/summarize.py`
- `vera_base/verantyx/task_bootstrap.py`
- `vera_base/verantyx/task_recipes.py`
- `vera_base/verantyx/tool_call_quarantine.py`
- `vera_base/verantyx/transfer_outcomes.py`
- `vera_base/verantyx/transfer_reading.py`
- `vera_base/verantyx/tree_witness.py`
- `vera_base/verantyx/ui_transition.py`
- `vera_base/verantyx/vera_server.py`
- `vera_base/verantyx/vocab_growth.py`
- `vera_base/verantyx/watermark.py`
- `vera_base/verantyx/watermark_forks.py`

</details>

- `vera_base/verantyx/constructions/modality.py`
- `vera_base/verantyx/domains/__init__.py`
- `vera_base/verantyx/failure_packs/data_pipeline.json`
- `vera_base/verantyx/failure_packs/decision_explain.json`
- `vera_base/verantyx/failure_packs/disaster_info.json`
- `vera_base/verantyx/failure_packs/education_assess.json`
- `vera_base/verantyx/failure_packs/game_qa.json`
- `vera_base/verantyx/failure_packs/lab_automation.json`
- `vera_base/verantyx/failure_packs/manufacturing_qa.json`
- `vera_base/verantyx/failure_packs/medical_evidence.json`
- `vera_base/verantyx/failure_packs/research_experiment.json`
- `vera_base/verantyx/failure_packs/robot_grasp.json`
- `vera_base/verantyx/failure_packs/search_zero.json`
- `vera_base/verantyx/failure_packs/soc_telemetry.json`
- `vera_base/verantyx/failure_packs/support_kb.json`
- `vera_base/verantyx/failure_packs/translation_l10n.json`
- `vera_base/verantyx/failure_packs/web_agent.json`
- `vera_base/verantyx/lang_data/ja_domain_disaster.json`

## 5. 検査結果

(a)〜(f)・p4 は `check_public.py` の検査。scan は情報であり合否に入れない。

| 検査 | 内容 | venv311 | system313 |
|---|---|---|---|
| a | `import vera_base` | PASS | PASS |
| b | 読み込まれた verantyx*/vera_base* がすべて出力配下 | PASS | PASS |
| c | pyproject の packages 宣言＝実ディレクトリ、package-data、wheel の中身＝出力 | PASS | PASS |
| d | `example.py` が最後まで動く | PASS | PASS |
| e | 未知入力への応答（返ること） | PASS | PASS |
| f | 同梱テストの収集エラー 0 | PASS | PASS |
| p4 | 個人パス・ストア実データ・.git・キャッシュ・測定物が無い | PASS | PASS |
| scan | 全モジュール import（情報） | DONE | DONE |

- venv311: Python 3.11.14、任意依存 {'fugashi': True, 'unidic_lite': True}、外部の `verantyx` に届く環境か = True、`all_pass` = True、`out_unchanged` = True。
- system313: Python 3.13.5、任意依存 {'fugashi': False, 'unidic_lite': False}、外部の `verantyx` に届く環境か = False、`all_pass` = True、`out_unchanged` = True。

(b) の詳細（子プロセスごとに読み込まれたモジュール数と、出力の外から読まれた数）:

| 環境 | 子プロセス | 出力配下 | 出力の外 |
|---|---|---:|---:|
| venv311 | a | 33 | 0 |
| venv311 | d | 61 | 0 |
| venv311 | e | 63 | 0 |
| venv311 | f | 107 | 0 |
| venv311 | scan | 294 | 0 |
| system313 | a | 33 | 0 |
| system313 | d | 33 | 0 |
| system313 | e | 44 | 0 |
| system313 | f | 107 | 0 |
| system313 | scan | 292 | 0 |

venv311 は出力をパスに入れないと外部の別物 `verantyx` に届く環境（`external_verantyx_reachable` = True）だが、出力を先頭に置いた子プロセスでは外へ出たモジュールが 0 件だった。

(c) の詳細:

- venv311: 宣言したパッケージ 4 / 実在 4。wheel の `vera_base/` 以下 321 ファイル、出力の `vera_base/` 以下 321 ファイル、片方にだけあるもの 0 / 0。
- system313: 宣言したパッケージ 4 / 実在 4。wheel の `vera_base/` 以下 321 ファイル、出力の `vera_base/` 以下 321 ファイル、片方にだけあるもの 0 / 0。

(d): `example.py` の標準出力は空でない行が次の数。

- venv311: 6 行、終了コード 0、`degraded`（任意依存が欠けていたか）= False。
- system313: 6 行、終了コード 0、`degraded`（任意依存が欠けていたか）= True。

(e): 未知入力 14 件を、`vera_base.Chat([])` と `vera_base.Chat([構成した文書 1 件], tree=True)` の 2 通りで `reply` に渡した（入力は `tools/check_public.py` の定数で、結果に合わせて変えていない。構成した文書は `kind: CONSTRUCTED` と申告している）。これは起動して返ることの検査であり、返答の内容の正しさではない。

| 環境 | 構成 | 呼び出し | 例外 | `kind` ごとの件数 | `UNKNOWN_NO_PARSER` |
|---|---|---:|---:|---|---:|
| venv311 | empty | 14 | 0 | ack: 1, unknown: 3, unreadable: 10 | 0 |
| venv311 | with_constructed_document | 14 | 0 | ack: 1, unknown: 3, unreadable: 10 | 0 |
| system313 | empty | 14 | 0 | UNKNOWN_NO_PARSER: 14 | 14 |
| system313 | with_constructed_document | 14 | 0 | UNKNOWN_NO_PARSER: 14 | 14 |

`UNKNOWN_NO_PARSER` 以外の応答（検査 JSON の項目名は `responses_other_than_unknown_no_parser_total`）は、fugashi 無しの環境（system313）で 0 件 / 28 件、fugashi 有りの環境（venv311）で 28 件 / 28 件。この項目は「中身がある」ことを意味しない: venv311 の 28 件の内訳は `ack` 2・`unknown` 6・`unreadable` 20（`kind` ごとの件数の表のとおり）で、大半は型付きの「分からない」「読めない」という棄権である。内容の正しさは (e) の範囲外で、判定していない。system313 では全件が「日本語を読めない」という型付きの返答（`UNKNOWN_NO_PARSER`）であり、起動して返ることの確認にとどまる。

(f): 同梱テストの収集は 2 環境とも収集 1693 件・収集エラー 0 件（system313 は 1693 件・0 件）。収集であり、テストの合否ではない。

(p4): 個人パス・`vera_store.*`・`.git`・キャッシュ・測定物の件数は両環境とも {'cache': 0, 'measurement': 0, 'personal_path': 0, 'store_data': 0, 'vcs': 0}。

(scan): `pkgutil.walk_packages` で見つけた全モジュールを import した結果。

| 環境 | 見つけた | import できた | `ModuleNotFoundError` | その他の例外 |
|---|---:|---:|---|---|
| venv311 | 292 | 292 | なし | なし |
| system313 | 292 | 290 | `verantyx.constructions.connective_rel` (欠落 `fugashi`), `verantyx.constructions.te_chain` (欠落 `fugashi`) | なし |

### 同梱テストを実際に走らせた結果（情報。受入基準ではない）

- 組み立てた出力（venv311、出力の根で `python -B -m pytest -p no:cacheprovider -q -rf tests`）: 28 failed, 1655 passed, 10 skipped, 37 subtests passed in 12.74s（`bundled_tests_venv311.txt`）。
- 比較用に、公開版そのもの（`origin/src/public` を展開し `PYTHONPATH=<公開版>/vera_base`）を同じ環境で走らせた結果: 32 failed, 1651 passed, 10 skipped, 37 subtests passed in 13.11s（`bundled_tests_public_baseline_venv311.txt`）。
- 失敗の差: 出力だけで失敗 2 件、公開版だけで失敗 6 件（一覧は両ファイルの差）。出力だけで失敗するのは `tests/test_semantic_unknown_choice.py` と `tests/test_verifier_agents.py` の各 1 件で、開発ツリー（wave3）の 2 ファイルが公開版より古いことに対応している可能性が高いが、wave5 で組み直して確かめてはいない（未検証）。公開版だけで失敗する 6 件（`test_one_chat_round5.py`・`test_one_request_goal_route.py`）が出力で通る理由は調べていない（未検証）。
- 実行の仕方（作業ディレクトリと、パスを相対で渡すか絶対で渡すか）で失敗数が変わることがあった。上の数は出力の根で相対の `tests` を渡した実行のもの。この違いの原因は調べておらず、artifacts にも残していない。製品の合否の主張には使わない。

## 6. 既知の穴（直していないもの）

1. **任意依存が欠けると import が落ちるモジュール**（`verantyx/` は変更禁止のため直していない）: system313（fugashi 無し）の scan で `verantyx.constructions.connective_rel` と `verantyx.constructions.te_chain` が `ModuleNotFoundError: fugashi`。venv311 では全モジュール import できる。
2. **CI の「Import every module」は最上位しか見ていない**: `.github/workflows/verify.yml` は `pkgutil.iter_modules(verantyx.__path__)` を使うので、サブパッケージ内（上の 2 件）は見つからない。しかもその step は「標準ライブラリだけで動く」ことを守るために pip install の前に走るが、実際には fugashi を必要とするモジュールがある。
3. **開発ツリー（wave3）は公開版より 2 ファイル古い**: `verantyx/semantic_unknown_choice.py`（公開版に `_JSONOptionResolver` がある）と `verantyx/verifier_agents.py`（公開版に `checks.sort(...)` がある）。どちらも `origin/src/wave5` には在り、`dev`（wave3）には無い。W0-1 の wave5 取り込み後に解消する差で、それまでは dev から組むとこの 2 点で公開版より古くなる（`public_diff.modified` の 2 件）。
4. **公開の `pyproject.toml` は fugashi と unidic-lite を必須依存にしている**（`dependencies = ["fugashi>=1.3", "unidic-lite>=1.0.8"]`）。変えていない（既存の挙動の変更になるため、提案にとどめる）。pip で入れる限りは入るが、`PYTHONPATH` だけで使う場合（公開版 README の使い方）は欠落しうる。
5. **fugashi はあるが辞書（unidic_lite）が壊れている・無い場合は未検証**: ガードは `ModuleNotFoundError` の `name` が `fugashi` / `unidic_lite` のときだけを捕まえる。辞書が読めないときの `RuntimeError` などは捕まえず、試せる環境も無かった。
6. **ガードは `Chat` だけ**: `Bot`・`judge`・`crossverify`・`two_stage`・`Base` は対象外。fugashi が無い環境（system313）で実測した範囲: `two_stage(...)`・`read_records(...)`・`Base().add(...).build()` はガード無しの元の例外（`ModuleNotFoundError: fugashi`）になる。`Bot()` の構築は通る（`Bot` の他のメソッドは試していない）。`judge`・`crossverify` は呼んでいない（未検証）。`import vera_base` 自体は通る（検査 a）。
7. **開発ツリーの根で引数なしの `pytest` を走らせると `public_overlay/tests` も集めてしまう**: 同名のテストファイルがあるので衝突する（実測: `pytest --collect-only -q tests public_overlay/tests` は収集エラーで中断する。件数は artifacts に残していない）。`pytest tests/...` と範囲を指定すること。
8. **同梱テストには落ちるものがある**（5 節）。この道具はテストの合否を保証しない。収集できること（収集エラー 0）だけを検査している。
9. 検査 (e) は「起動して返ること」だけを見ており、内容の正しさは見ない。fugashi 無しでは全件が `UNKNOWN_NO_PARSER` になる。
10. **D4 は静的な import だけを見る**: `__import__("verantyx.x")` や `importlib.import_module(...)` で除外モジュールを文字列から読む箇所は検出できない（合成ツリーで `__import__("verantyx.leak")` を書いたところ、ビルドは終了コード 0 で通ることを実測した）。現在の実ツリーで除外された 1 件（`build_failure_eval`）を文字列で読む箇所は無い。
11. **git の無視規則は `--src` が git 作業ツリーの根のときだけ働く**: 合成ツリーや git の無い環境では `vcs_ignored` は効かず、`vcs.state` に型で記録されるだけ（上記）。overlay の未追跡ファイルは報告しない（判断 D12）。
12. **(b) は、a・d・e・f のどれかの子プロセスが読み込みモジュール一覧を返さなかった場合に `UNKNOWN_NO_CHILD_RESULT`（欠けた子の名前つき）を返す**ようにした（以前は黙って飛ばしていた）。関数を直接呼ぶ確認（空の結果で `UNKNOWN_NO_CHILD_RESULT`、一部だけで欠けた子の名前つき）は行ったが、子プロセスを実際に失敗させる回帰テストは書いていない（未検証）。
13. wheel の検査は `setuptools.build_meta.build_wheel` を直接呼ぶ。PEP 517 の隔離ビルド（`python -m build`、ネットワーク必須）や、wheel を新しい venv に入れて動かすことまでは確かめていない。
14. **入れ子の git リポジトリの無視規則は効かない**: `verantyx/` の下に別の git リポジトリ（`.git` を持つサブディレクトリ）があると、外側の git はそれを 1 つのディレクトリとしてしか返さず、入れ子側の `.gitignore` が名指しするファイルも出力に入る（合成ツリーで実測: 入れ子側の `.gitignore` が `secret.json` を名指ししても `secret.json` は出力に入った。`.git` 自体は規則 `vcs` で除かれた）。`NESTED_REPOSITORY` のような型付きの停止はまだ無い。実ツリーの `verantyx/`・`public_overlay/` に入れ子の `.git` が無いことはレビューで確かめられている。
15. **`.git/info/exclude` は読む**（クローンごとの手元の規則）。同じコミットでも、組むクローンの `.git/info/exclude` が違えば `vcs_ignored` の対象が変わりうる。利用者のグローバル ignore は読まない（判断 D11）。

## 7. 判断記録

| # | 決定 | 理由 |
|---|---|---|
| D1 | パッケージ本体は dev の `verantyx/` をファイルシステムで再帰探索して全部取り、除外は規則だけで行う。出力先は `vera_base/verantyx/`。ファイル名の手書き一覧は持たず、コード中に `domains` などの名前を書かない。 | チケット「規則で」・P3。 |
| D2 | `public_overlay/` は公開版の `vera_base/verantyx/` 以外のファイルをそのまま写したものとし、必要な変更（D5, D6）だけを加える。 | 公開版の tests/tools/docs の選び方は人が選んだもので開発ツリーから規則で導けない。しかも一部は公開版のほうが新しく、開発版の `tests/test_semantic_measure.py` には個人パスが入る。開発側との食い違いは manifest の `dev_counterpart` に毎回出る。 |
| D3 | overlay とパッケージが同じ出力パスを持ったら、どちらも勝たせずビルドを失敗させる（終了コード 2、`PATH_COLLISION`）。 | 同点は棄権。 |
| D4 | 個人環境の絶対パスを含むファイルは中身の規則で除外する。除外したモジュールを同梱モジュールが import していたらビルドを失敗させる（`EXCLUDED_MODULE_IMPORTED`）。 | P4。壊れた出力を黙って作らない。 |
| D5 | overlay に `tests/conftest.py` を足す（`<root>/vera_base` を `sys.path` の先頭へ）。 | 公開版の文書が求める `PYTHONPATH=vera_base` を環境変数なしで成り立たせる。外部の別物 `verantyx` を黙って読む事故を防ぐ。 |
| D6 | overlay の `vera_base/__init__.py` に任意依存の欠落ガードを入れる。依存があるときは `vera_base.Chat is verantyx.chat.Chat`（同じオブジェクト）で挙動は変わらない。無いときだけ、`ModuleNotFoundError` の `name` が任意依存名のときに限り、型付きの応答 `kind="UNKNOWN_NO_PARSER"`（何が無いか・入れ方つき）を返す。広い `except` は使わない。 | 「黙って落ちず、何が無いので出来ないかを返す」。`verantyx/` は触れないので公開の入口で行う。型名は既存の `verantyx/document_loaders.py` の `UNKNOWN_NO_PARSER` に揃えた。 |
| D7 | `pyproject.toml` は overlay の公開版を使い、`[tool.setuptools.package-data]` 表だけを探索結果から生成し直す。manifest で `CONSTRUCTED` と申告する。`dependencies` は変えない。 | 手で直すと手書き一覧になる。依存宣言の変更は既存の挙動の変更なので提案にとどめる。 |
| D8 | 検査の子プロセスはすべて `-B -I`、`env={HOME: 一時dir}`、`cwd=一時dir`、出力を `sys.path[0]` に明示して動かす。 | 余計なパス・HOME 配下のコーパスを読ませない。出力にキャッシュを作らない。 |
| D9 | 結果は `PASS` / `FAIL` / `UNKNOWN_<理由>` の 3 種。道具が無いとき（pytest・setuptools 無し、時間切れ）は `UNKNOWN_*` とし、合格に数えない。 | 分からないことと偽を混ぜない。 |
| D10 | 出力物（`manifest.json`・検査 JSON・artifacts・このページ）には絶対パスを書かない。インタプリタは `--label` と `sys.version` で表す。 | P4。出力先のパスを入れると決定性（P1）も崩れる。 |
| D11 | `--src` が git の作業ツリーの根なら、git が「無視している（untracked かつ ignored）」ファイルを規則 `vcs_ignored` で除く。追跡されているファイルは、無視規則に当たっていても除かない（作者が `git add -f` した意思を尊重）。git が使えないとき・作業ツリーの根でないときは、除外せず `vcs.state` に型（`UNKNOWN_GIT_MISSING` / `UNKNOWN_NOT_A_GIT_TREE` / `UNKNOWN_GIT_ERROR`）で記録する。 | 開発ツリー自身の `.gitignore` が名指しする手元だけのファイル（壊れたスクラッチ、`*.local.json`）が、作者の作業コピーで組むと公開物に入る穴をふさぐ（レビュー第 1 回の必須 1）。「分からない」を「無視されたものは無い」と混ぜない。 読む無視規則はクローンと一緒にあるもの（ツリー内の `.gitignore`・`.git/info/exclude`）だけで、利用者のグローバル設定・既定のグローバル ignore ファイル・システム設定は読まない（組む人ごとに出力が変わらないように。レビュー第 2 回の必須 1）。 |
| D12 | 未追跡だが無視されていないパッケージ層のファイルは含め、`vcs.untracked_included` に全件並べて見えるようにする。overlay 層は未追跡を報告しない（無視されたものだけ除く）。 | 含めるか止めるかのどちらでもよいとされた箇所。止めると新規ファイルを追加した直後に組めなくなるので、含めて見えるようにした。overlay は今回まるごと未追跡（コミット前）なので、報告すると全件が並び、コミット後に manifest が変わってしまう。製品コードの層だけ見えれば、公開物に未コミットの製品コードが入ることは検知できる。 |
| D13 | 検査 (e) の項目名を `responses_other_than_unknown_no_parser_total` に改めた。「中身があるか」の判定は作っていない。 | 旧名は、型付きの棄権（`unknown`・`unreadable`）まで含めた数に実質的な応答という含みを持たせる名前だった（レビュー第 1 回の必須 2）。 |

第 2 ラウンドの追加: (b) が子プロセスの結果欠落を `UNKNOWN_NO_CHILD_RESULT` にする、`build_public.py` が製品コードを `ast.parse` するときの `SyntaxWarning` を表示しない（製品側の警告は道具の stderr に出さない）。

実装時の追加判断: ① `--out` が開発ツリーの中なら `OUT_INSIDE_SRC` で拒否する（出力が `.gitignore` や未追跡物に紛れるのを防ぐ）。② `check_public.py` 自身は `verantyx` も `vera_base` も import しない（動的な検査はすべて子プロセス）。③ 公開版との比較用に `bundled_tests_public_baseline_venv311.txt` を追加で置いた（指示書の一覧に無いが、数を書くときの比較対象として必要だった）。

## 8. 公開の提案（push・公開はしていない）

以下は提案であり、実行していない。

1. W0-1（wave4 / wave5 の取り込み）が済んだ開発ツリーで `build_public.py` を再実行し、「変更」の 2 ファイル（上の既知の穴 3）が解消したことを `public_diff` で確かめる。
2. 組み立てた出力に対し、2 つのインタプリタで `check_public.py` を走らせ、(a)〜(f)・p4 がすべて PASS であることを確認する。fugashi 無しの環境では (e) が全件 `UNKNOWN_NO_PARSER` になることを承知しておく。
3. 公開リポジトリのブランチ（`origin/src/public` とは別の作業ブランチ）へ出力を反映し、追加・変更の一覧（4 節）をレビューしてから公開側へ取り込む。公開は人が決める。
4. 任意依存の欠落時の扱い（公開 `pyproject.toml` の必須依存の見直し、`Bot` などへのガードの拡張、`connective_rel` / `te_chain` の遅延 import 化）は `verantyx/` の変更を伴うので、別チケットで扱う。
5. CI に、サブパッケージを含めた全モジュール import（`pkgutil.walk_packages`）と、公開レイアウトの組み立て＋ `check_public.py` を足すことを検討する。

## 9. W16-t10 配布 smoke と実測ファイル表（事前登録、2026-10-06 00:00 Asia/Tokyo）

この節と `artifacts/w16-t10/preregistration.md` は smoke fixture を用いた基線再測定と wheel 実行の前に登録した。期待契約は同ファイルの SHA-256 で凍結する。測定値は run 別 artifacts に残す。最初の草稿（22:58）は英語で、`read` の現行 parser 構文も反映していなかったため `preregistration.r0.md` に保存した。23:05・23:11・23:54 の訂正版は `preregistration.r1.md`〜`r3.md` に保存した。00:00 に ask document を既存 semantic reader テストの fixture に変更し、これを有効な登録とした。先行 run が欠落 package を迂回し得る環境だったと判明したため、実装着手後の登録訂正と測定のやり直しを作業報告に記録する。

### 9.1 固定する確認と期待形

| 確認 | 固定した入力 | 合格条件 |
|---|---|---|
| wheel 構築・導入 | この開発ツリーから作る wheel、新規 venv、作業ツリー外の空 cwd | build と install が終了コード 0。起動した `vera` が新規 venv の `site-packages` 配下から `verantyx` を読み込む |
| `vera --help` | 引数なし | 終了コード 0、標準出力に `usage: vera` を含む |
| `vera read --text` | `ハルはミナに本を渡した。` | 終了コード 0、標準出力が JSON object で `schema=verantyx.semantic_read/1`、`lang=ja`、`readable` が bool、`clauses` が list |
| `vera ask` | `誰が肥料を運んだ？`、既存 `tests/test_semantic_reader.py` の `test_condition_source_and_unresolved_exception_retained` fixture を `--document` に指定、`--mode round5` | 終了コード 0、標準出力が JSON object で `verdict` が文字列。fixture は `constructed` であり、値の意味や答えの正しさはこの smoke で採点しない |
| `vera serve --no-llm` | 隔離した store、loopback の空き port | 子プロセスが起動した状態で GET `/v1/models` が HTTP 200 の JSON object を返し、`data` が list、その先頭の `id` が `vera-no-llm`。子プロセスは終了コード 0 で停止 |
| wheel 内容 | 上記 smoke で作成した wheel | zip member に `verantyx/constructions/` と `verantyx/data/` がある |
| 読込ファイルの照合 | smoke の全 CLI 子プロセスで計測した読み込み path | `site-packages/verantyx/` 配下の読み込みファイルを wheel member と相対 path で照合し、未収録件数 0。外部文書・隔離 store・ログ・venv 内の Python 標準ライブラリは package-data の照合対象外として別記録 |
| 配置資産往復 | `pack_placement.sh` の出力 tar と sha256 を `file://` で `placement fetch` に渡す | sha256 一致、tar 展開成功、出力に設定先 `VERA_PLACEMENT=<dir>` を含む。配置ありの `vera read` の比較は、利用可能な配置資産で別に記録し、未実行なら未達とする |

### 9.2 実測表の作り方

各 smoke 子プロセスで Python の `builtins.open`、`io.open`、read-capable `os.open`、`sqlite3.connect` を計測し、成否と path を JSONL に記録する。package-data 判定表は成功した package 配下の読み込みと失敗した package-data 候補を相対化して作る。存在確認だけの `stat`、書き込み、ユーザー入力文書、隔離 store、外部資産、Python module import は「runtime data open」表へ混ぜない。wheel member との比較はパスの完全一致で行い、大小文字・名前・ハッシュで代替一致させない。

実測表の各行は `source_path | wheel_relative_path | wheel_member_present` とし、観測されなかったファイルを推測で足さない。トレースで捕捉できない OS/native library 内部の読み込みはこの表の対象外で、限界として報告する。wheel と smoke の出力は `artifacts/w16-t10/` に残す。

### 9.3 凍結した期待

以下は実測結果ではなく、このチケットの受入契約である。事前登録ファイルのハッシュが対応する固定期待を示す。

- P1: 全 smoke 項目の終了コード 0 と上記出力形。
- P2: `constructions` と `data` が wheel にあり、実測 package runtime data open の未収録数 0。
- P3: pack/fetch の SHA-256 が一致し、配置を与えた read が配置ありの結果を返す。
- P4: 基線の全体比較は監査役の責務。本実装役は全体テストを実行しない。

### 9.4 直す前の基線測定

基点コミット `3a1677c` のソースを `git archive` から scratch に展開し、配布設定の修正前に煙試験した。採用する基線測定は `artifacts/w16-t10/baseline-20261006T000253-65711/`。通常の新規 venv に wheel を入れ、smoke 用の `fugashi` と `unidic_lite` だけを個別に symlink した。P1 は `help`・`read`・`serve` が通り、非空文書を使った `ask` が終了コード 1 で失敗した。`ask.stderr` は `semantic_reader.py:1212` の `ModuleNotFoundError: No module named 'verantyx.constructions'` を記録している。P2 は `constructions_present=false` と `data_present=false` で不合格。`package-open-paths.txt` に記録された package path はすべて基線 wheel に存在し、`p2-verification.json` の未収録 open 数は 0 だった。欠けていた constructions は Python import であり、open tracer の data file 数だけでは見つからない。

| source path | wheel-relative path | wheel member |
|---|---|---|
| installed package code | `verantyx/cli.py` | present |
| installed package code | `verantyx/one.py` | present |
| installed package code | `verantyx/semantic_reader.py` | present |
| installed package data | `verantyx/lang_data/ja_grammar.json` | present |
| installed package data | `verantyx/lang_data/roles_learned.json` | present |
| installed package data | `verantyx/lang_data/transitivity.json` | present |

`verantyx/data/` 内の JSON はこの smoke で開かなかった。wheel に含めるのは受入基準の明示要件であり、open 実測の発見とは分けて扱う。23:31 run は検査器自身の open が混ざり、23:49 run は system site-packages を通じて別の editable package を参照し得たため、どちらも根拠に使わない。23:57 run は空でない基本文を渡したものの construction reader を通った証拠がなく、P1 根拠から外す。これらのログは監査可能性のため残す。

### 9.5 修正版 wheel smoke の測定

修正版の全 smoke 結果は `artifacts/w16-t10/release-20261006T000833-67881/` に保存した。`p1-verification.json` の全コマンドが終了コード 0 で出力形を満たす。wheel には `constructions` と `data` があり、`p2-verification.json` は成功した package open 5 件、未収録 0 件を記録する。open された package data は次のとおり。`wheel-members.txt` が wheel 全 member、`package-open-paths.txt` と `package-missing-members.txt` が実測との照合。

| source path | wheel-relative path | wheel member |
|---|---|---|
| installed package data | `verantyx/data/case_frames.json` | present |
| installed package data | `verantyx/data/realize_forms_ja.json` | present |
| installed package data | `verantyx/lang_data/ja_grammar.json` | present |
| installed package data | `verantyx/lang_data/roles_learned.json` | present |
| installed package data | `verantyx/lang_data/transitivity.json` | present |

`verantyx/data/realize_variants.json` は smoke 中に観測されていないが、明示要件の `data/*.json` として wheel に含まれる。Python import のうち tracer が捕捉しなかった経路は完全な実測と称さず、既知の限界に記録する。

### 9.6 構成 fixture を使った pack/fetch の転送確認

配置そのものは変更せず、in-tree schema から空の SQLite と table count 0 の manifest を scratch に構成して transport のみを確認した。入力の SHA-256 は `artifacts/w16-t10/constructed-placement-inputs.sha256` に pack より前に固定した。

最初の `pack_placement.sh` 出力では macOS `tar` が `._manifest.json` と `._placement.sqlite` も格納し、fetch は `UNKNOWN_UNSAFE_ARCHIVE` を返した（member 一覧: `constructed-placement-initial-members.txt`、応答: `constructed-fetch.json`）。梱包時に `COPYFILE_DISABLE=1` を指定して再生成した tar は manifest と SQLite だけを含み、`constructed-placement-fixed-members.txt` に記録した。`file://` fetch は `PLACEMENT_FETCHED` と tar SHA-256 `c1f86423745c7f732abcdf5145b79f498e3d0a967b5c3cbfcc2aba74f8629c6f` を返し、`constructed-placement-inputs.sha256` と `constructed-placement-fetch-hashes.sha256` の diff は差分なしだった。tar、sidecar、CLI 応答、展開後の hash は `artifacts/w16-t10/` に保存した。

これは `constructed` な空 fixture の転送確認に限られる。r9 配置に対する `vera read` は実行しておらず、P3 は未達。r9 の実体がある別の `wt/` クローンは共通指示により開いていない。
