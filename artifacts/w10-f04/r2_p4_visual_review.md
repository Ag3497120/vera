# P4 目視の記録（目視であり正解データではない。第 2 ラウンド）

採用された候補: 1 件（下の「採用の目視」）。誤採用（目視）の件数は下に書いた。以下は全 32 穴の一覧（`p4_real.jsonl` から機械で生成）。「申告の型が穴の語の型か」= 申告の型が、配置が穴の語に与える型（`hole_word_types`）に入るか（—: 配置が穴の語に型を与えない、または申告が無い）。

| 文 | 穴 | 申告の型 | 穴の語の配置の型 | 申告の型が穴の語の型か | 近い語[最初に落ちた門] | 理由 |
|---|---|---|---|---|---|---|
| 母が図書館へ歩いた。 | へ:図書館 | GROUP_ORG | GROUP_ORG,PLACE | はい | 図書館[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が図書館へ走った。 | へ:図書館 | GROUP_ORG | GROUP_ORG,PLACE | はい | （語なし） | NO_CANDIDATE_WORDS |
| 姉が家へ歩いた。 | へ:家 | NATURAL_PHENOMENON | PLACE,STATE_PROPERTY | いいえ | 家[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母が谷へ歩いた。 | へ:谷 | NATURAL_PHENOMENON | PLACE,STATE_PROPERTY | いいえ | 谷[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 弟が役所へ走った。 | へ:役所 | GROUP_ORG | GROUP_ORG,PLACE | はい | 役所[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 妹が本部へ歩いた。 | へ:本部 | GROUP_ORG | GROUP_ORG,PLACE | はい | 本部[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が窓口で名乗った。 | で:窓口 | ABSTRACT | ABSTRACT,PLACE | はい | 窓口[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母がホールで断った。 | で:ホール | NATURAL_PHENOMENON | EVENT_ACT,PLACE | いいえ | ホール[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 弟が交番で走った。 | で:交番 | NATURAL_PHENOMENON | PERSON,PLACE | いいえ | 交番[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が土間で歩いた。 | で:土間 | PLACE | — | — | （語なし） | NO_CANDIDATE_WORDS |
| 母が広間で名乗った。 | で:広間 | PLACE | — | — | （語なし） | NO_CANDIDATE_WORDS |
| 手紙が駅へ飛んだ。 | が:手紙 | ABSTRACT | ABSTRACT,IDENTIFIER,INFO_LANGUAGE,WORK | はい | （語なし） | NO_CANDIDATE_WORDS |
| 夫婦がホテルで名乗った。 | が:夫婦 | PERSON | NATURAL_PHENOMENON,PERSON | はい | 夫婦[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 友人が庭へ走った。 | が:友人 | PERSON | ABSTRACT,PERSON | はい | （語なし） | NO_CANDIDATE_WORDS |
| 夫婦が森へ歩いた。 | が:夫婦 | PERSON | NATURAL_PHENOMENON,PERSON | はい | 夫婦[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 住民が村へ歩いた。 | が:住民 | PERSON | GROUP_ORG,PERSON,TIME | はい | 住民[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 隊員が港へ走った。 | が:隊員 | PERSON | PERSON,QUANTITY | はい | 兵士[passed] | ADOPTED |
| 先生が校舎で挨拶を断った。 | を:挨拶 | EVENT_ACT | EVENT_ACT,INFO_LANGUAGE,TIME | はい | 断る[a1] | GATE_A_TYPE_NOT_EXPECTED |
| 母がホテルで勝利を願った。 | を:勝利 | EVENT_ACT | EVENT_ACT,PLACE,TIME | はい | 願う[a1] | GATE_A_TYPE_NOT_EXPECTED |
| 姉が神社で日程を断った。 | を:日程 | EVENT_ACT | PLACE,TIME | いいえ | 日程[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄がアパートで地図を断った。 | を:地図 | ARTIFACT | INFO_LANGUAGE,PLACE | いいえ | MAP[a1] | GATE_A_NOT_PLACED:PLACEMENT_UNPLACED |
| 姉が机を中から広場へ引いた。 | を:机 | ARTIFACT | ARTIFACT,PLACE | はい | PLACE[a1] | GATE_A_NOT_PLACED:PLACEMENT_UNPLACED |
| 母が荷物を港へ押した。 | を:荷物 | ARTIFACT | — | — | 押す[a1] | GATE_A_TYPE_NOT_EXPECTED |
| 姉が机を工場から広場へ引いた。 | を:机 | ARTIFACT | ARTIFACT,PLACE | はい | PLACE[a1] | GATE_A_NOT_PLACED:PLACEMENT_UNPLACED |
| 兄が山田に催促した。 | に:山田 | PERSON | PERSON,PLACE | はい | （語なし） | NO_CANDIDATE_WORDS |
| 姉が本社に請求した。 | に:本社 | GROUP_ORG | GROUP_ORG,PLACE | はい | （語なし） | NO_CANDIDATE_WORDS |
| 妹が山田に申告した。 | に:山田 | PERSON | PERSON,PLACE | はい | （語なし） | NO_CANDIDATE_WORDS |
| 家族が図書館へ走った。 | が:家族 | PERSON | GROUP_ORG,PERSON | はい | 図書館[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 家族が図書館へ走った。 | へ:図書館 | PLACE | GROUP_ORG,PLACE | はい | 家族[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 警察が家へ歩いた。 | が:警察 | PERSON | GROUP_ORG,PERSON | はい | 警察[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 警察が家へ歩いた。 | へ:家 | NATURAL_PHENOMENON | PLACE,STATE_PROPERTY | いいえ | 警察[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 妹が東京に旅行した。 | に:東京 | PLACE | PLACE,TIME | はい | （語なし） | NO_CANDIDATE_WORDS |

## 採用の目視（人が見た判定。正解データではない）

- 「隊員が港へ走った。」 穴 が:隊員 → 候補 `兵士`、申告の型 PERSON（穴の語の配置の型 PERSON,QUANTITY）。
  - 目視の判定（実装役。正解データではない）: 妥当。人を指す語の穴に人を指す語（申告の型は穴の語の型に入る）。置換した文『兵士が港へ走った。』は自然で、足した意味は隊員 → 兵士（近い語であって同義ではない）。誤採用（目視）は 0 件。ただし採用が 1 件だけなので、門の判別力の証拠にはならない。

`GATE_D_TIE` の行は複数の語がすべての門を通ったために棄権した行（同点は棄権）。`NO_CANDIDATE_WORDS` は後段が近い語を 1 つも返さなかった行（後段の失敗ではない。型つきの不採用）。

## 数えたもの（`p4_real.jsonl` から）
- 誤採用（目視）: 0 / 採用 1。
- 申告の型が穴の語の型でなかった行（表の「いいえ」）: 7 件。7 件とも、後段が穴の語自身または表の外の語（`PLACE`・`MAP` など）を近い語に返したため門 (a1) で先に落ちた。**(a3) まで届いた行は P4 には 0**（本物の後段で (a3) が働いた実測は無い。働くことの確認は fake 台本 `F-A3-01〜12` とテスト）。P4 r1 と違い、人・会社・地名の穴（R-25〜R-27）への申告は PERSON／GROUP_ORG（穴の語の型）になり、近い語は空だった（`NO_CANDIDATE_WORDS`）。
- 残るリスク（数える）: 配置が位置の型を穴の語の候補に持つ穴（`東京` = PLACE,TIME。R-30）は、後段が TIME を申告すれば (a3) を通る。今回の実測では R-30 は PLACE を申告し近い語は空。
