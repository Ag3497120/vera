# P4 目視の記録（目視であり正解データではない）

採用された候補: 0 件。誤採用（目視）は採用が無いので 0 だが、これは「採用が無い」ことによる自明な 0 で、門の判別力の証拠ではない。以下は全 32 穴の一覧（`p4_real.jsonl` から機械で生成）。

| 文 | 穴 | 申告の型 | 近い語[最初に落ちた門] | 理由 |
|---|---|---|---|---|
| 母が図書館へ歩いた。 | へ:図書館 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 建物[passed] | GATE_D_TIE |
| 兄が図書館へ走った。 | へ:図書館 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 地域[passed] | GATE_D_TIE |
| 姉が家へ歩いた。 | へ:家 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 場[a1] | GATE_D_TIE |
| 母が谷へ歩いた。 | へ:谷 | PLACE | 山[passed]; 川[passed]; 海[passed]; 坂[passed]; 道[passed] | GATE_D_TIE |
| 弟が役所へ走った。 | へ:役所 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 場[a1] | GATE_D_TIE |
| 妹が本部へ歩いた。 | へ:本部 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 点[passed] | GATE_D_TIE |
| 兄が窓口で名乗った。 | で:窓口 | PLACE | 窓口[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母がホールで断った。 | で:ホール | NATURAL_PHENOMENON | 部屋[a2]; 場所[a2]; 空間[a2]; 室[a1]; エリア[a2] | NO_CANDIDATE_PASSED |
| 弟が交番で走った。 | で:交番 | PLACE | 駅[passed]; 郵便局[a1]; 警察署[passed]; 病院[passed]; 学校[a1] | GATE_D_TIE |
| 兄が土間で歩いた。 | で:土間 | PLACE | 廊下[b]; 部屋[passed]; 家[a1]; 場所[passed]; 空間[b] | GATE_D_TIE |
| 母が広間で名乗った。 | で:広間 | PLACE | 部屋[passed]; 空間[b]; 場所[passed]; 室[a1]; エリア[b] | GATE_D_TIE |
| 手紙が駅へ飛んだ。 | が:手紙 | ANIMAL | 犬[passed]; 猫[passed]; 鳥[passed]; 魚[passed]; 馬[passed] | GATE_D_TIE |
| 夫婦がホテルで名乗った。 | が:夫婦 | PERSON | 家族[a1]; 親族[a1]; 仲間[passed]; 同僚[passed]; 友人[a1] | GATE_D_TIE |
| 友人が庭へ走った。 | が:友人 | PERSON | 友達[passed]; 仲間[passed]; 同僚[passed]; 親友[passed]; 友人[a1] | GATE_D_TIE |
| 夫婦が森へ歩いた。 | が:夫婦 | PERSON | 家族[a1]; 恋人[a1]; 仲間[passed]; 親戚[passed]; 友人[a1] | GATE_D_TIE |
| 住民が村へ歩いた。 | が:住民 | PERSON | 人[passed]; 市民[passed]; 国民[a1]; 家族[a1] | GATE_D_TIE |
| 隊員が港へ走った。 | が:隊員 | PERSON | 兵士[passed]; 将校[a1]; 士官[a1]; 警備員[passed]; 巡査[a1] | GATE_D_TIE |
| 先生が校舎で挨拶を断った。 | を:挨拶 | EVENT_ACT | 挨拶[a1]; 手紙[a1]; 言葉[a2]; 文句[a1]; お礼[a1] | NO_CANDIDATE_PASSED |
| 母がホテルで勝利を願った。 | を:勝利 | EVENT_ACT | 成功[a1]; 達成[passed]; 実現[passed]; 優勝[a1]; 得点[passed] | GATE_D_TIE |
| 姉が神社で日程を断った。 | を:日程 | EVENT_ACT | 予定[a1]; 計画[a1]; スケジュール[a1]; 行事[passed]; 会議[passed] | GATE_D_TIE |
| 兄がアパートで地図を断った。 | を:地図 | ARTIFACT | 図面[a1]; 図式[a1]; 図解[a1]; 図版[a1]; 図表[a1] | NO_CANDIDATE_PASSED |
| 姉が机を中から広場へ引いた。 | を:机 | ARTIFACT | 椅子[a1]; テーブル[a1]; 机[a1]; 棚[a1]; 箱[passed] | GATE_D_CHOICE_ABSTAINED:NONE_SELECTED |
| 母が荷物を港へ押した。 | を:荷物 | ARTIFACT | 箱[passed]; 荷[a1]; 品[a1]; 物[a1]; 袋[a1] | GATE_D_CHOICE_ABSTAINED:NONE_SELECTED |
| 姉が机を工場から広場へ引いた。 | を:机 | ARTIFACT | 椅子[a1]; テーブル[a1]; 机[a1]; 棚[a1]; 箱[passed] | GATE_D_CHOICE_ABSTAINED:NONE_SELECTED |
| 兄が山田に催促した。 | に:山田 | TIME | 昨日[a1]; 先週[a1]; 今月[a1]; 今朝[a1]; 明日[a1] | NO_CANDIDATE_PASSED |
| 姉が本社に請求した。 | に:本社 | TIME | 昨日[a1]; 先月[a1]; 今週[a1]; 直近[b]; 過去[a1] | NO_CANDIDATE_PASSED |
| 妹が山田に申告した。 | に:山田 | TIME | 昨日[a1]; 先週[a1]; 今月[a1]; 去年[a1]; 今朝[a1] | NO_CANDIDATE_PASSED |
| 家族が図書館へ走った。 | が:家族 | PERSON | 親戚[passed]; 族[a1]; 家[a1] | GATE_D_CHOICE_ABSTAINED:NONE_SELECTED |
| 家族が図書館へ走った。 | へ:図書館 | PLACE | 駅[passed]; 公園[passed]; 学校[a1]; 病院[passed]; 家[a1] | GATE_D_TIE |
| 警察が家へ歩いた。 | が:警察 | PERSON | 警官[passed]; 署員[a1]; 巡査[a1]; 警部[a1]; 警察官[passed] | GATE_D_TIE |
| 警察が家へ歩いた。 | へ:家 | PLACE | 駅[passed]; 場所[passed]; 地[passed]; 所[passed]; 辺[a1] | GATE_D_TIE |
| 妹が東京に旅行した。 | に:東京 | TIME | 来週[a1]; 明日[a1]; 先月[a1]; 去年[a1]; 今夏[a1] | NO_CANDIDATE_PASSED |

`GATE_D_TIE` の行は複数の語がすべての門を通ったために棄権した行（同点は棄権）。通った語が妥当かは見ていない（採用していない）。
