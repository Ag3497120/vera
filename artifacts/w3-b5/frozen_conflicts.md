# 凍結したテストとの避けられない衝突（W3-b5。3 件）

既存のテストは変えていない。基点（`7494ba2`）で全部通り、今 3 件が落ちる（関係するテスト 5,666 件のうち。`pytest_related_after.txt`・`pytest_related_base.txt`・`pytest_related_new.txt`）。3 件とも、チケットが指定した変更の定義上の結果で、実装の誤りではない。監査役が統合のとき差し替える（提案は下）。
`FAILED` 行の名前は変えない。

## 1. `tests/test_semantic_read_w3b4.py::test_the_plan_of_w3b4_is_the_plan_of_w3b2_with_the_two_references_to_the_table_replaced`

- 固定しているもの: `typed_plan_u_w3b4_ja` の本文（docstring を除く文を `ast.unparse` したもの）が、W3-b2 の `typed_plan_u_w3b2_ja` の本文と、表の参照 2 か所を置き換えた以外 **同じ** であること。
- 落ちる理由: チケットが「役割決定の関数の中」の変更を指定し、`typed_plan_u_w3b4_ja` に 挿入のみ（既存の行は 1 行も消さない・変えない）で行を足したので、本文が基点と違う（`git diff 7494ba2 -- verantyx | grep -c '^-[^-]'` は 0）。
- 提案する差し替え（名前は変えない。比較を「古い本文の文がすべて新しい本文に順序どおり残っている」に変える）:

```python
def test_the_plan_of_w3b4_is_the_plan_of_w3b2_with_the_two_references_to_the_table_replaced():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    old, old_args = _plan_text(src, 'typed_plan_u_w3b2_ja', (('TYPED_FRAMES_NOT_READ', 'TYPED_FRAMES_NOT_READ_W3B4'), ('TYPED_FRAMES.get(ptype)', 'typed_frames_v2().get(ptype)')))
    new, new_args = _plan_text(src, 'typed_plan_u_w3b4_ja')
    assert old_args == new_args
    # W3-b5 (docs 10F K200): the plan only GAINS lines (the rows of the kind frame_required); every statement of the plan of W3-b2 is still there, in the same order
    import difflib
    assert [l for l in difflib.ndiff(old.splitlines(), new.splitlines()) if l.startswith('- ')] == []
    assert 'TYPED_FRAMES_NOT_READ_W3B4' in new and 'typed_frames_v2()' in new
```

- 同じ性質を `tests/test_semantic_read_w3b5.py::test_the_plan_of_w3b4_only_gains_lines_and_the_end_of_the_reader_file_is_the_one_of_the_base_commit` が基点（`7494ba2`）の本文との `ndiff` で確かめている（`-` の行 0）。

## 2. `tests/coarse_place/test_coarse_place_w3a4_r7_unchanged.py::test_the_answers_of_r7_are_byte_identical_to_the_frozen_hashes`

- 固定しているもの: r7 の 73 語の答えの `json.dumps(answer, ensure_ascii=False)` の sha256（`data/w3a4_r7_answer_sha.tsv`）。
- 落ちる理由: 答えに鍵 `frame_generated` が増える（チケットの目的 (1)）ので、`json.dumps` した文字列は定義上すべて変わる。`frame_generated` を除いた答えは基点と byte 一致で、r7 の 4,788 語 + 207 語、r8 の 8,030 語 + 207 語の全部で確かめた（`query_unchanged_r7.txt`・`query_unchanged_r8.txt`: 不一致 0）。`frame_status` の比較は通っている。
- 提案する差し替え（名前は変えない。`frame_generated` を除いてから hash を取る）:

```python
def test_the_answers_of_r7_are_byte_identical_to_the_frozen_hashes():
    rs = rows()
    assert len(rs) == 73 and {r[0] for r in rs} == {"twelve", "not_confirmed", "direct"}
    bad = []
    for kind, w, sha, fs in rs:
        ans = cp.query(w, placement=R7)
        ans = {k: v for k, v in ans.items() if k != "frame_generated"}       # W3-b5: one key more (docs/COARSE_PLACEMENT.md 11.6); the rest of the answer is what it was
        h = hashlib.sha256(json.dumps(ans, ensure_ascii=False).encode("utf-8")).hexdigest()
        if h != sha or ans.get("frame_status") != fs:
            bad.append((kind, w))
    assert not bad, bad
```

## 3. `tests/coarse_place/test_coarse_place_w5b.py::test_a_spelling_that_has_an_answer_of_its_own_keeps_it_exactly_as_the_answer_function_gives_it`

- 固定しているもの: `query` の答え（`spelling`・`term` を除く）が、同じ語を `cp._answer(...)` に直接かけた答え（`term` を除く）と **等しい**こと。
- 落ちる理由: 鍵 `frame_generated` は `query` が足す（チケットが許す変更は `query` の `frame_generated` の追加だけ。`_answer`・`_direct`・`_set_frame` は許可の外）ので、`_answer` の答えには無い。
- 提案する差し替え（名前は変えない。`query` が足した鍵を比べる前に除く）:

```python
        without = {k: v for k, v in r.items() if k not in ("spelling", "term", "frame_generated")}      # W3-b5: `query` adds frame_generated; `_answer` does not
```

## 本体の同一性・hash のほかに衝突した可能性があったもの（確かめたが衝突しなかった）

- 答えの末尾の鍵を固定する 5 本（`tests/coarse_place/test_coarse_place_w3a3_query.py:90`・`test_coarse_place_w5e_frame_backing.py:165`・`test_coarse_place_w5d_frame_types.py:56,68`・`tests/attack/w3a3/test_w5d_r7_frame_types.py:72`）: `frame_generated` を W3-a3 の末尾の最初の鍵の直前に置いたので、通る。
- `tests/test_semantic_read_w3b1.py::test_only_the_gate_and_the_query_adapter_read_the_fields_of_an_answer`: 新しい読み手 `predicate_frame_generated` は答えの `state`・`origin`・`top`・`decided_by`・`estimate_basis` を添字・`.get` で読まない（`frame_generated` の値の中の `origin` は、答えの欄でなく値の欄なので、辞書の部分集合の比較で読む）。通る。
- W3-b4 の「表の値を固定する」3 本・`test_the_name_the_entry_calls_is_the_plan_of_w3b4_…`（名前の差し替えと末尾 3 文）・W3-b2 の `test_the_reader_file_only_gains_lines`: `frame_required` の行を別の辞書に置き、末尾に何も足さず、名前を差し替えなかったので、通る。

## 環境由来の 1 件（衝突ではない）

- `tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches` が全体テストで落ちる（基線の失敗一覧には無い）。落ちる行は `assert meta["child_env"]["HOME"] == "<WORK>/home" and meta["verantyx_untouched"] is True` の後半で、`verantyx_untouched` が False（作業ツリーの `verantyx/` に未コミットの変更がある間だけ起きる。指示書・チケットが「`test_s6_…`（未コミットの間だけ）は環境由来」と書いたもの）。コミット後は通る見込みで、この変更の誤りではない。
