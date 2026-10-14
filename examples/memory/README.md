# memory: 作業ログの記憶 / a memory for a working log

事実を **1 回に 1 つ、1 文で** 渡し、あとで問う。答えは覚えた文の一字一句の引用か「分かりません」だけ。
同じ席に別の値を 2 回言うと、どちらかを選ばず **食い違い（contested）** として黙る。

Tell it facts **one per message, one sentence each**, ask later. An answer is a verbatim quote of a remembered sentence, or 「分かりません」.
Two different values told for the same seat are reported as **contested**, never picked.

```
sh examples/memory/run.sh            # or: vera mem --store ./memory-store --say "広報の担当は山本" ...
```

期待する出力の形（モデルが 1 事実 1 書き込みで書いた場合）:

```
記憶: 3 件を session 1 に渡しました（保存）
分かりません（理由: contested、記録の中で答えが食い違っています： 「山本」 / 「田中」）
答え: 「東京」
根拠: 会議の場所は東京
store: ./memory-store
OK mem_store
```

* 「広報の担当」は 2 つの値が言われたので contested。直すには「広報の担当は田中に変更」のように **変更として** 言う（UPDATE）。
* 答えられるのは「X の Y は A」の形の 1 文。「会議は東京で開く」のような出来事の文は、問いは読めても値を引用として出さず「分かりません」になる。同義語（場所 / 開催地）も読めない。黙るのが正しい挙動で、限界でもある。
* `vera run --store ./memory-store` の画面の「記憶」タブで、注記（SAME_SEAT / UPDATE / REVERSAL_X）と、問いの位置の十字・巣が見える。
* 台帳: `vera verify ./memory-store`（連鎖と再生）。
