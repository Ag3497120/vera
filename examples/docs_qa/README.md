# docs_qa: 文書に問う / asking documents

```
vera ask --docs examples/docs_qa/manuals "保守契約の窓口は何ですか"
vera ask --docs examples/docs_qa/manuals --backend openai --model llama3.1 --base-url http://127.0.0.1:11434/v1 "経費精算システムの旧称は何ですか"
vera run --docs examples/docs_qa/manuals          # the same, in the browser: http://127.0.0.1:3090/
```

出力の形（答えは引用と、その引用元の文。それ以外のモデルの文は出ません）:

```
答え: 「総務部」
根拠: 保守契約の窓口は総務部である。（保守契約#1）
run: runs/ask-20261014-…
```

文書に答えがない問い、または門が通さない引用のときは:

```
分かりません（理由: no_record、文書にその答えが書かれていません）
```

* `manuals/` は 2 つの短い文書。「保守契約の窓口は何ですか」「経費精算システムの旧称は何ですか」は引用で答えられる。
* 「夜間の障害受付の窓口は何ですか」は、文書に「夜間の障害受付は別契約である。」しかないので、モデルが「別契約」を答えにしようとしても門が `no_evidence/no_slot_head`（その文は窓口を述べていない）で拒否する。
* `vera verify runs/ask-…` で連鎖と再生を確かめる。
* 試験: `tests/harness/test_examples.py` が、偽のモデルでこの文書に対する上の 3 つの挙動（答える・答える・門が拒否する）を実際の門で確かめている。

The two documents in `manuals/` are tiny. Two questions are answerable by quotation; for the third, the gate refuses a quote whose sentence does not state the asked item.
