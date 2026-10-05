# Round5-A 公開開発素材 — 回答取得前の独立監査

2026-09-30。正式事前登録`PREREGISTERED_2026-09-30_round5a_semantic_plan.md`に基づく開発素材。**封印評価でも、Veraの能力測定結果でもない。**

gpt-6-luna / low / fast担当が、実装コード・封印・heldoutを読まずに日本語の資料と質問80件を作成した。24件は12組の構造対。作成時のJSON・件数・型・出典参照検査に加え、rootと、runtimeやVeraの回答を閲覧しない独立担当が資料→質問→参照の論理を照合した。

初版には、入室許可から実際の入室や義務を導くこと、十分条件を必要条件へ読み替えること、書かれていないボタンを手順名から補うこと、文書順を時間順の根拠にすること等の問題があった。また、2段結合を意図したのに後半資料だけで答えられるもの、問いが意図した情報不足を特定しないものがあった。

回答取得をHOLDにし、元の版を保存して19行を訂正した。計算の初期量・同日・増減範囲・隙間なしといった前提の明示化も含む。80件を維持し、難問の除外やruntimeの成績による正解変更は行っていない。独立担当が修正後の全80件を再読し、残る必須不整合0と判断した後、manifestをAPPROVEDへ更新した。

| 最終素材の区分 | 件数 |
|---|---:|
| ANSWER | 63 |
| UNKNOWN | 10 |
| CONFLICT | 4 |
| AMBIGUOUS | 3 |
| 合計 | 80 |

これらは期待結果の内訳であり、Veraの正答数ではない。全80一意ID、12組24件の対、全出典参照、manifestとの件数・hash一致を確認済み。

```text
初版 fixtures.jsonl SHA-256:
47e0a765c10dff53a4c53db1fa449be5fd3f553ce907202d303a9e5856b3126b

最終 fixtures.jsonl SHA-256:
a765402a5fc88176dd17833730780c3b8c917f7c3d80a7748277c61845c1c693
```

監査元・再現資産:

- 素材とmanifest: `/Users/motonishikoudai/Projects/vera-round5-dev/`
- 全件独立監査: `/Users/motonishikoudai/Projects/vera-round5-run/fixture_audit_notes.md`
- 変更前後と理由: `/Users/motonishikoudai/Projects/vera-round5-run/fixture_corrections.json`
- 元版および中間版: `/Users/motonishikoudai/Projects/vera-round5-run/fixture_versions/`

今後はこのhashを使って開発検証を行う。素材の参照誤りが新たに見つかった場合は理由・版・測定への影響を残し、結果を黙って置き換えない。監査は自然言語資料の品質確認であり、形式意味論の完全性証明ではない。開発素材の成績を未見一般化や最終目標達成の証拠にしない。
