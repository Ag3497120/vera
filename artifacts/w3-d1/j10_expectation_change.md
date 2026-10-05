# J10 を閉じたことによる期待の変化（監査役の判断待ち）

`tests/test_w10f04_fill.py` は許可パスの外なので **編集していない**（skip/xfail にもしていない）。J10（実現器が型つきの十字を拒む）を閉じると、次の 1 件が落ちる。期待の変更は監査役が許可して統合時に行う。

## 旧い期待（テスト関数の全文。基点 6bc410d、194 行目から）
```python
def test_realize_is_recorded_and_can_be_required(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=r8)            # r3: the gate itself, on a one-hole sentence (the realizer step exists only there)
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}) == (None, 'REFUSED')         # J10: the realizer cannot read back a typed goal cross
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}, True) == ('GATE_B_REALIZE_REFUSED', 'REFUSED')
    d, _ = decide('ウサギが図書館へ走った。', [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], r8, HOLE2)
    assert d.status == 'ADOPTED' and d.gate_log[0]['realize'] == 'SKIPPED_OTHER_HOLES'                       # in a two-hole sentence the step is skipped, and the record says so
```

## 新しい期待（同じ呼び出し。`tests/test_w3d1_gate_b.py::test_the_j10_sentence_of_test_w10f04_fill_is_now_realized` に書いた全文）
```python
def test_the_j10_sentence_of_test_w10f04_fill_is_now_realized(r8):
    q = S._placement_query(R8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=R8)
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, R8, {}) == (None, 'REALIZED')
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, R8, {}, True) == (None, 'REALIZED')
```

統合時に `test_w10f04_fill.py` の 197・198 行を次のように変えることを提案する（2 行目の関数名・他の行は変えない）:
```python
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}) == (None, 'REALIZED')         # J10 closed (W3-d1)
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}, True) == (None, 'REALIZED')
```

## 変わる理由
J10 の原因は (i) 実現器が文の再読を配置なしで行う、(ii) 主題を は で書く、の 2 つだった。W3-d1 で、実現器は渡された配置で再読し（K312）、主題の助詞を表の順（は、が）に試して **出す文そのもの** が再読一致を通った最初の候補を出す（K315）。`母が駅へ歩いた。` は配置つきでは は の文が ABSTAINED になり、が の文が元の十字に戻るので、`母が駅へ歩いた。` が出る。

## 実測（`tests/test_w10f04_fill.py -k test_realize_is_recorded` の失敗と、同じ呼び出しの出力）
```
tests/test_w10f04_fill.py:197: AssertionError
=========================== short test summary info ============================
FAILED tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required
1 failed, 54 deselected in 0.53s
```
```
F._gate_b(..., R8, {})       = (None, 'REALIZED')
F._gate_b(..., R8, {}, True) = (None, 'REALIZED')
```

このテスト関数の残りの行（`ADOPTED`・`SKIPPED_OTHER_HOLES`）は落ちる前の 197 行で止まるため未実行。別途（ファイルを編集せずに）同じ内容を実行して通ることを確かめた（下記）。

残りの 2 行に当たる呼び出し（`T.decide('ウサギが図書館へ走った。', [op2(['犬']), pick, pick], R8, HOLE2)`、`tests.test_w10f04_fill` の関数を import して実行）の出力: `ADOPTED SKIPPED_OTHER_HOLES`（旧い期待どおり）。
