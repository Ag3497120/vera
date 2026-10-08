# P4 目視の記録（目視であり正解データではない。第 3 ラウンド。裁定 A・B の後）

採用された候補: 0 件（下の「採用の目視」）。誤採用（目視）の件数は下に書いた。以下は全 32 穴の一覧（`p4_real.jsonl` から機械で生成）。「申告の型が穴の語の型か」= 申告の型が、配置が穴の語に与える型（`hole_word_types`）に入るか（—: 配置が穴の語に型を与えない、または申告が無い）。

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
| 隊員が港へ走った。 | が:隊員 | PERSON | PERSON,QUANTITY | はい | 兵士[a4] | GATE_A_ROLE_SPLIT |
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

- 採用 0 件: 目視の対象は無い。誤採用（目視）= 0 件（採用が無いので 0。正解データによる確認ではない）。

## 門 (a4) で止まった語（r2 では (a1)〜(a3) を通り、後の門に任された語）

- 「隊員が港へ走った。」 穴 が:隊員 → 候補 `兵士`、申告の型 PERSON、穴の語の配置の型 PERSON,QUANTITY、型ごとの役割 {"PERSON": "agent", "QUANTITY": null}、理由 GATE_A_ROLE_SPLIT (TYPE_NOT_READ)

`GATE_D_TIE` の行は複数の語がすべての門を通ったために棄権した行（同点は棄権）。`NO_CANDIDATE_WORDS` は後段が近い語を 1 つも返さなかった行（後段の失敗ではない。型つきの不採用）。
