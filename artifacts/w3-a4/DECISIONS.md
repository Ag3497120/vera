# W3-a4 判断記録（実装役 Claude Sonnet 5.5）

作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S`（HEAD = `c334fe6`）。指示書: `.claude/vera-audit/review-impl/W3-a4/plan.md`。

## 0. 写したもの
- 中間職の試作 `proto_evidence/`（`p1_probe.py`・`p3_variants.py`・`reader_probe.py`）を **読み**、考え方を写した（コードは書き直した: `scripts/p1_r7_bytes.py`・`scripts/p3_cover.py`・`scripts/reader_probe.py`）。`est_sahen.py` は使っていない。
- `artifacts/w5-d/scripts/run_build_w5d.sh` → `scripts/run_build_w3a4.sh`、`artifacts/w3-a3/measure_w3a3.py` → `scripts/measure_w3a4.py`（パスだけ）。

## 1. 指示書の初期状態の確認
- 作業ツリーは `git status --porcelain` が空（手順 0 の前）。途中までの未コミットの作業は無かった。

## 2. 指示書の C1〜C7 の決め方（指示書どおり）
- C1: `pos3` は読まない。「普通名詞（pos2）の直後に する の動詞が続く」で決めた。定数 `SAHEN_NOUN_POS2` とヘルパ `_sahen_verb`。禁止語を避ける細工はしていない。
- C2: サ変の項は `acc["chain_sahen"]`。`acc["chain"]` には入れず、`chain_skips["sahen"]` は今までどおり数える。内訳 `acc["sahen_chain_skips"]`。出所ごとの不変条件（和 = `chain_skips["sahen"]`）は試験と `r8_base_checks.txt` で確認（全出所 OK）。
- C3: 古い cache の停止は既存の検査の後ろに 2 つ目（`SAHEN_CACHE_KEYS`）。同じ `STAGE_CACHE_STALE`・終了コード 4。
- C4: `frame_cover_rule` の既定は `"all9"`。`DEFAULT_CONFIG` に 1 行足した（「`_apply_gen_frame` の包含だけ」の外。宣言する）。r8 の設定ファイルだけが `k62_he_by_ni_place`。
- C5: `coarse_place.py` は 1 文字も変えていない。覆った へ は `frame_unconfirmed` に出ない。manifest の `cover_he_by_ni_place` に数だけ出す。
- C6: 名詞＋できる は今までどおり。受身・使役は `voice`。
- C7: P5 が基準を満たした（57/70 = 0.8143）ので `sahen_upgrade`（D9）は入れていない。

## 3. 手順 4・11 で選んだ値と理由
- 手順 4: `frame_cover_rule` = `k62_he_by_ni_place`。p3 の目視で明らかな誤りは 0/12（`he_by_ni_place` は 0/11）。事前登録の「既定のまま、2 割を超えたら狭める」に従った。疑わしい 4 語（`よぶ`・`嫁ぐ`・`向かえる`・`送り返す`）は記録し、判定には使っていない。
- 手順 11: P5 = 57/70 = 0.8143。基準 0.8 を満たしたので D9 は入れない。ただし余裕は小さい（疑わしい 12 語を正しいとも誤りとも数えていない）。`意味する` を明らかな誤りとしたのは、「〜を意味する」が相手へ伝える行為でなく意味の関係だと読んだため（私の読みで、正解データではない）。

## 4. 指示書からの逸脱・指示書に無い判断（隠さない）
1. **D7 の重なりの検査**: 指示書は「`read_generated_frames` で読んだ結果の語」とした。私は **2 本の生のファイルの語（棄権の行を含む）** で検査し、**抽出より前**（引数と除外語の読み込みの直後）に行う（何も書かずに止めるため。抽出 cache の書き込みも起きない）。`--generated-frames-add` だけで `--generated-frames` が無い、または `--generated-frames-add-ledger` だけ、のときは型つきで終了コード 2（`UNKNOWN_GENERATED_FRAMES_ADD_ARGS`）。
2. **D6 の `needs`**: `--exclude-frames` だけを `--sahen-min-uses` なしで渡したときは黙って無視せず、型つきで終了コード 2（`UNKNOWN_EXCLUDE_FRAMES_WITHOUT_SAHEN_MIN_USES`）。`--sahen-min-uses` に `--kind pred` と `--stage-cache` が無い、cache に `sahen_verb` が無いときも終了コード 2。
3. **D5 の `cover.ignored`**: 無視した助詞のうち **生成の枠に実際に無かったものだけ** を書く（枠にあれば覆われているので「無視した」には当たらない）。`manifest.generated_frames.outcomes.cover_ignored_non_k62` はこの語の数（1: `よぶ` の と）。`cover_he_by_ni_place` は へ を覆った語の数（r8 で 15）。
4. **D8 の `compare_to`**: `n_seen` だけの違いは「判定が変わった」に数えない。`ns` ごとの集計は **新しい ns** で数える。`changed_P_words` の「P」は ns に P を含む（P と NP）、「N」は N を含む。manifest の `duration_sec` と `build_finished_at_utc` は `compare_to` の時間を含めて更新した。
5. **P1 の語**: 15,102 語（`gen_frame`・`role_distribution` の行を持つ語 5,097 + 無作為 10,000 + 名詞 5）。見出し語 1.76M の全数ではない。r7 の sqlite が不変（`readonly_after.txt`）であること、判定関数の変更が `_apply_gen_frame` の包含だけで既定が旧規則であることと合わせて P1 を主張する。
6. **`test_coarse_place_w3a4_r7_unchanged.py`**: r7 のディレクトリが無いと失敗する（skip しない指示）。データ `data/w3a4_r7_answer_sha.tsv` は `p1/r7_before.tsv`（基点のコードで取った）から `scripts/make_r7_answer_sha.py` で作った（行 73: 12 + 13 + 48）。
7. **`p5_pre.py`**: r8/base の `meta.config` が `DEFAULT_CONFIG` + `config_w3a4.json` と一致することを assert している（一致した）。
8. 試験の追加は `tests/coarse_place/` の新しいファイル 7 本とデータ 1 本だけ（既存の試験の行の削除 0）。
9. 構築の時間: r8/base 635.9 秒はチケット・指示書の見込み（約 9 分）より長い。他の作業で負荷が高かった（`uptime` 3〜13）。

## 5. 写した中間職のスクリプト
- 写した（読んで書き直した）: `proto_evidence/p1_probe.py`・`p3_variants.py`・`reader_probe.py` の考え方。そのままコピーしたファイルは無い。

## 6. 第 2 ラウンド（レビュー r1 の M1）
- `verantyx/coarse_types.py` の `slot_min` の行の空白を基点と同じ 1 バイトに戻した（他の行は触っていない）。差分の `+`/`-` の行に `slot_min` は無い。
- r8/run1 は消さず、同じ引数で r8/run2 を作った（`coarse_types_sha256` を直したコードに合わせるため）。run1 は空白 1 字の違うコードで作った・run2 は直したコードで作り、内容は同じ（`content_sha256` `89bd07e6…82a5`、`placement.sqlite` の sha256 も同じ）。P6 の配置はどちらでもよい。
- 負荷: 構築の前に `uptime` が 8.43 だったので 2 回（約 10 分）待ち、7.95 になってから流した。
- 任意の改善 1（`frame_cover_rule` の値の検査を設定の読み込みで行う）は **しない**: `build_coarse_placement.py` を変えると `builder_sha256` が変わり、run2 の出所の確認（`builder_sha256` が `21f94de6…e7c3` のまま）が成り立たなくなるため。任意 2・3（事前登録の時刻の書き方・目視の理由の文）も今回は触らない（製品・測定に影響しない）。
- 試験: 関係する分（`tests/coarse_place` ほか）を流した 1 回目に `test_the_stop_signal_ends_the_run_with_an_interrupted_record` が失敗した（`subprocess.TimeoutExpired`、20 秒）。直後の単独実行も 1 回失敗したが、その後の単独実行は 基点の写し・変更後ともに 6 回ずつ全部通り（約 0.46 秒）、関係する分の全体は 296 passed（`pytest_related_r2.txt`）。差分は `run` の信号の扱いに及ばない（基点の写しと同じ試験も通る）ので、負荷由来の不安定と判断する（第 1 ラウンドの既知の穴 8 と同じ）。
- 再確認（run2、内容は run1 と同じなので測定は増やしていない）: P1 の 15,102 語の答えの sha256 が基点のコードの出力と `cmp` 一致（`p1/p1_cmp_r2.txt`）、P2（`p2_words_run2.txt`）・§12.10 の不変条件（`frame_invariants_r8_run2.txt`、run1 と diff 空）は run1 と同じ、読み込まれた verantyx*/tools* はすべてツリー配下（`check_modules_r2.txt`）。

## 7. 第 3 ラウンド（レビュー r2 の M1）
- docs §12.17 の sha256 の省略形 2 つを出典の全長の値に合わせて直した: 「生成」の段落の `1509fd30…68d2` → `1509fd30…68e2`（`prompt_sha.txt`・`gen_sahen_summary.json` の `prompt_template_sha256` = `1509fd3014397232d48dfd00b0ae9d8df078b5f2fb3d54e9f53c2b17a76d68e2`）、第 2 ラウンドの段落の `e20bbbc7…b5fe` → `e20bbbc7…e5b7`（`code_sha_base.txt`・`manifest_r8_run1.json` の `coarse_types_sha256` = `e20bbbc780af038a1916e255058ba6e3d66fb8c2ced642982e691f551fbfe5b7`）。`impl.r2.md` にも同じ誤りがあったが、報告は更新しない（`impl.r3.md` に正しい値を書く）。
- §12.17 の追記にある省略形の sha256 8 種（`106d892e…ec4`・`1509fd30…68e2`・`21f94de6…e7c3`・`68551a6a…d882`・`73f9381e…3279`・`cb7e44f9…bb91`・`e20bbbc7…e5b7`・`ff9ddf02…fe50`）を、artifacts の全長の値（および `106d892e…ec4` は r8/run2 の `placement.sqlite` の `shasum -a 256`）と照合した。全部一致。
- 製品コード・試験・配置・r8 は変えていない（r8 の作り直しなし）。
