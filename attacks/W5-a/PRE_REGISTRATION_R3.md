# W5-a K64 過剰棄権の追試 事前登録

登録日時: 2026-10-03 09:52 UTC

## 対象

`docs/READING_SOUNDNESS.md` §10A K64 の新条件（受身でない `を` 節について、`_is_person_phrase` による正の動作主証拠が無く、述語が読解器の閉じた目的語類に無ければ `AGENT_EVIDENCE_MISSING` で棄権）を調べる。報告対象は、普通の日本語として人・人の集団・組織の動作主が明らかで、基点コミットでは agent/patient と読めたが、W5-a 統合後は同理由で棄権する文に限る。単に現行器が読めない文は命中にしない。

## 固定する評価内容

次の 5 文の gold は、実行前に `agent/patient` と凍結する。

1. `尼僧が古い箱を閉めた。` — person actor, `閉める`, patient `古い箱`.
2. `複数の人物が回答書を発行した。` — person group, `発行する`, patient `回答書`.
3. `尼僧が寺の案内図を描いた。` — person actor, `描く`, patient `寺の案内図`.
4. `会社が試作品を公開した。` — organization actor, `公開する`, patient `試作品`.
5. `複数の人物が別々の名を名乗った。` — person group, `名乗る`, patient `別々の名`.

命中は、(a) 基点 `2732274^` の checked-in `semantic_read.py` を実行して gold roles を得て、(b) 現行入口の結果が unreadable となり、reason が `AGENT_EVIDENCE_MISSING:<主語>` と完全一致し、(c) 人手で見た主語の意味が動作主を肯定する場合。その他の結果はこの過剰棄権攻撃の外れとして報告する。基点と現行の比較は同じ import 環境で行い、基点ソースは git のこのクローンからメモリに読み込む。

入力と gold を持つ追試ファイルの SHA-256 を、実装比較前に `FIXTURE_R3.sha256` に保存する。

事前登録訂正 (2026-10-03 09:54 UTC): 第 1 文を `寺の戸` から `古い箱` に変更した。語句 `戸` は場所と誤解釈される可能性があり、K64 の `AGENT_EVIDENCE_MISSING` と「`を` 句が場所のときの曖昧性棄権」を混同しないため。入力 fixture を作る前の訂正で、検査結果は見ていない。
