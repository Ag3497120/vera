# 事前登録: 選択済み核の facet 被覆による棄権

登録日: 2026-09-05。測定・実装の前にこの文書を確定し、SHA-256 を
PREREG.sha256 に保存する。実行器は一致を検査する。この登録は追記も含め
測定後に変更しない。結果・制約・不採択は RESULTS.md に記録する。

## 参照したものと今回の差分

- `python3.11 -m verantyx.cli index search "特定性 帯 REVERSE_SPECIFIC 直接候補"`
  は UNKNOWN_NOT_FOUND。語を分けた `index search REVERSE_SPECIFIC` と
  `index search direction_band` で既存実装・登録を引き、そのソースを読んだ。
- `experiments/source_group_mass/RESULTS_WIRE.md` (WIRE1–3)、`RESULTS_A2.md`、
  `~/.claude/projects/-Users-motonishikoudai-Projects-Vera/memory/vera-junk-cores-carry-abstention.md`。
- 同 memory の `vera-reverse-specific.md`、`vera-a-only-directive.md`、
  ルート `CLAUDE.md`、`experiments/forward_win_mechanism/PREREG2.md`。
- `consensus_store.direction_band` は内容語の最大被覆帯を既に求める。
  `REVERSE_SPECIFIC` は順方向非 ANSWER の帯割れを被覆語数/面数の
  次点比で裁定する。順方向 ANSWER を棄権させる今回の役割とは異なる。
  帯計算・逆方向回答・候補順位・合意エネルギーは作り直さない。
- `candidates_for_query` の末尾追記で既に用いる facet の
  `overlap / max(1, len(cross))` を、独立した棄権条件として読む。
  REVERSE_SPECIFIC の名前語込みの分子や次点比とは混ぜない。

## 固定する規則

`Q = query_content(query)[0]`、選択済み核を `c`、その store の全 facet キー集合を
`F(c)` とする。特定性 `S(c,Q) = |Q ∩ F(c)| / max(1, |F(c)|)`。
一致は既存候補追記と同じ文字列の完全一致。語の意味推測・新トークナイザ・
LLM・ニューラル判定は使わない。出現回数・mass は分母にも分子にも入れない。
核名は面ではないので加算しない。直接名前ヒットも免除しない。
配置された面だけを分母にせず、情報量を配置から捏造しない。

固定閾値 **τ = 1/20 (0.05)**。これは「全 facet の少なくとも二十分の一を
問いが直接覆う」という検証対象の設計条件であり、実測から校正した値でも、
既存 REVERSE_SPECIFIC の margin 5.0 を変換した値でもない。
閾値の最適化・探索は行わない。

`run_consensus` の返り値が ANSWER で `20 * |Q ∩ F(c)| < max(1, |F(c)|)`
なら `UNKNOWN_INSUFFICIENT_EVIDENCE` に下げ、公開する core/text/tokens を
None/空文字/空列にする。元の核・覆った語・分母・比率・元判定は監査記録に残す。
閾値と等しい場合は通す（候補間の同点とは別）。元の非 ANSWER は型ごと保持。
他候補への置換・再選択・同点崩し・棄権からの昇格はしない。
この裁定は junk 判定を参照せず、候補中の junk の有無に関係なく同じ計算をする。
低被覆であることは棄権条件であり、高被覆なら正解と保証する規則ではない。

## 実装範囲と同一路の治具

今回の実装は `experiments/specificity_abstention/` に置く独立した裁定関数と
実行器とする。既存の `ConsensusResult` をコピーして下げ、探索層の規則は変えない。
本番への自動配線は今回行わない。採択可否をまず測る。

全腕が `experiments/retrieval_reach/run_reach.py` の
`candidates_appended → shell → run_consensus` を通る。同じ関数を import する。
shell は同ファイルの AXES / FACET_FACES / score_facets(weight=0.0) の手順で作る。
質量は `_MassView`、df と demand の生成も同ファイルの関数を使う。
裁定はこの run_consensus の後段で実行し、候補取得・面配置・合意探索には加点しない。
store の内容・core_count・has・索引を編集/差し替えない。DB は読み取り専用。
既存関数が構築する転置索引キャッシュは通常の動作として許す。

4 腕:

1. `baseline`: 現行候補、裁定なし。
2. `specificity`: 現行候補、裁定あり。**主判定対象**。
3. `no_junk`: candidates_appended の返した候補列から既存 is_junk_core によって
   junk を除き、その列で shell → run_consensus。残枠の再充填はしない。
4. `no_junk_specificity`: 3 と同じ候補列・経路の後段で同じ裁定。

3/4 は補助観測。store 複製や3入口の門の効果を測るものではなく、
「取得後に除く」という操作を明記した対照である。3/4 の結果を
WIRE3 の配線予測に代用しない。1/2 と3/4はそれぞれ同一の候補と配置を使い、
裁定だけの差を比較する。空候補も run_consensus に渡し、棄権として分母に残す。

## 未見の探針・記録

DB は run_reach.DB の vera.db、ja store。`rich=sorted(c for c,f in crosses.items()
if len(f)>=8)`。population は `random.Random(31415).sample(rich, min(300,len(rich)))`。
seed 31415 は登録前に experiments および上記 memory の py/md/json を rg で検索して
出現しなかった。今回未使用の seed とする（過去の全実行履歴の不存在までは証明しない）。
過去 seed の再測定で線を決めない。人口 seed の相違は核の完全非重複を保証しない。

生成は WIRE2/3 と同じ seed オフセットを固定:
train は mid_facets(seed=31415+58+r), r in range(3)、問いは
mid_facets(seed=31415+957)。gold と問いは無変更 store から作り全腕共通。
生成不能は明示して除外し、その件数と理由を記録する。候補なしは除外しない。
全評価問について gold/query/Q/候補列/配置/元判定/裁定後判定/被覆語/全 facet 数を保存。
正答は verdict=ANSWER かつ core=gold、誤答は ANSWER かつ core≠gold、
それ以外は棄権。AMBIGUOUS も棄権。3分類の和と asked の一致を検査する。

保存: PREREG と実装と入力 DB と利用ソースの SHA-256、HEAD、実行時刻、
全件 JSON、分類遷移、verdict 分布、全正答喪失、全誤答抑制、
baseline 棄権→no_junk 誤答を no_junk_specificity が救った/救えなかった全件。
RESULTS.md に判定線の結果と全件の表を記録し、集計だけで済ませない。

## 凍結した主判定線

- WRONG_DOWN: specificity.wrong < baseline.wrong。
- REFUSAL_NOT_WORSE: specificity.refusal ≥ baseline.refusal。
- CORRECT_NOT_WORSE: specificity.correct ≥ baseline.correct。
- JUNK_TOP1_ZERO は判定しない。junk先頭件数は文脈としてのみ記録。
- PATH_MATCH: 対応する腕で候補・配置・元合意が同一、裁定は非 ANSWER を保持し、
  通過 ANSWER の核・text/tokens を保持する。原 DB のハッシュは実行前後で同一。

主判定をすべて満たした場合のみこの実験条件で支持。どれか落ちたら不採択、
理由・全遷移を残し閾値を変えて再実行しない。補助腕の良い数値で主判定を救済しない。
補助腕の WRONG_DOWN / REFUSAL_NOT_WORSE / CORRECT_NOT_WORSE も baseline 比で
同じ不等式を参考表示し、junk 除去で失った棄権の回復は個別遷移で確認する。

## 回帰と停止

本番 verantyx/*.py を編集した場合は変更後に必ず
`python3.11 -m verantyx.cli lab` (178/178, skipped 0) と
`python3.11 experiments/guard/verify_all.py` (forks 89/89) を実行する。
測定 48/50 の既知環境依存は失敗名と理由を記録する。
この条件が崩れたら今回変更した本番ファイルだけを git checkout で戻し記録する。
作業前からある verantyx/paths.py と他の利用者変更は戻さない。
実験だけの変更でも今回は両コマンドを健康確認として実行しログを保存する。
予想成績は書かない。未達でも削除せず登録と実装・実測を残す。
