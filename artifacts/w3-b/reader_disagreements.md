# 読解器との食い違い（クラス (c)）: 読解器が読み、手で書いた期待と違った文

検査データ 204 文（日 103・英 101）のうち 5 件。凍結した一覧は `tests/event_cross/data/reader_disagreements.json`。
どの件も期待を直していない・文を消していない。十字の層は読解器の節を忠実に写すだけで、直していない（`tests/test_event_cross_data.py` は
この 5 件を「節の忠実な写し」として確かめる）。
機械の観測は `artifacts/w3-b/reader_obs.jsonl`、分類は `artifacts/w3-b/e2_classes.json`、下書き（機械の抜き出し）は `reader_disagreements.draft.md`。

| id | 文 | 期待（手で書いた） | 読解器の出力 | 規約の該当 | 読み |
|---|---|---|---|---|---|
| ja-032 | 姉は妹より足が速い。 | entity 姉 / standard 妹 / attribute 足 | entity 姉 / standard 妹（`attribute` が無い） | §2「A は B が 形容詞 の B（側面）は attribute」・§10 | 読解器が `足` を黙って落とす（役割を 1 つ欠く不完全）。計画書 §1.2 が先に実測していたのと同じ型 |
| ja-034 | 東の畑は西の畑より水が多い。 | entity 東の畑 / standard 西の畑 / attribute 水 | entity 東の畑 / standard 西の畑 | 同上 | 同上 |
| ja-037 | 夏は冬より日が長い。 | entity 夏 / standard 冬 / attribute 日 | entity 夏 / standard 冬 | 同上 | 同上 |
| ja-094 | この橋はあの橋より長い。 | entity 橋 / standard 橋 | entity 橋 / standard あの橋 | §3「指示詞の連体詞は外す」 | 読解器は `この橋` の このは外したが `あの橋` の あのは外していない（値の正規化の漏れ。規約の言う正しい値は 橋）。読解器の誤り |
| ja-080 | 先生が地図をぬめった。 | readable: false（§7-5 主節の述語が造語） | readable: true、述語 ぬめる、agent 先生 / patient 地図 | §7-5・§7 の「読めない」に当たるか | **期待の側の怪しさあり**: 書いたとき ぬめる を造語のつもりで書いたが、ぬめる は辞書にある語（滑る）。ただし 地図を ぬめる は他動詞の使い方として不自然。規約の 5 は「辞書に無い語」が条件なので、この文は §7-5 に当たらない可能性が高い（= 期待の書き誤りの疑い）。読解器を調べてから期待を直すのは写しになるので直さず、中間職の判断に回す。直す場合は `docs/EVENT_CROSS.md` の変更記録に書き、`FROZEN.json` に新しい sha を追記する |

## 件数の意味

- 日本語 5 件のうち、読解器の誤りの疑いが強いのは ja-094（指示詞の外し漏れ）と 比較の attribute 欠落 3 件（ja-032・034・037）。
- ja-080 は期待の書き誤りの疑い（上記）。
- 英語は 0 件。
- 触らないと決めたもの: `verantyx/semantic_reader.py`・`semantic_read.py` の役割と値の規則（このチケットの許可パスの外）。
  比較の `attribute` 欠落（ja-032・034・037）については、入口が `dimension` を落とす 1 か所を直す差分を `artifacts/w3-b/proposed_reader_dimension_attribute.patch` に残した（作業ツリーには**適用していない**）。
  コピーに当てて読解器を呼ぶと、3 文と 弟は兄より背が高い。 で `attribute` が `足`・`水`・`日`・`背` と出ることだけを確かめた（読解の健全性のテスト・採点器は流していない。適用するかの判断と全体の確認は読解側の別チケット）。
  ja-094 の あの の外し漏れは差分を作っていない（原因の場所を調べていない）。
