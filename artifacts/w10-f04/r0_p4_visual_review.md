# P4 目視の記録（目視であり正解データではない）

採用された候補: 0 件（誤採用 0 は「採用が無い」ことによる自明な 0。門の通過率の証拠ではない）。以下は不採用 32 穴の一覧（機械で `p4_real.jsonl` から生成）。

| 文 | 穴 | 申告の型 | 近い語（門の結果） | 不採用の理由 |
|---|---|---|---|---|
| 母が図書館へ歩いた。 | へ:図書館 | PLACE | 図書館[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が図書館へ走った。 | へ:図書館 | PLACE | 図書館[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 姉が家へ歩いた。 | へ:家 | PLACE | 家[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母が谷へ歩いた。 | へ:谷 | PLACE | 谷[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 弟が役所へ走った。 | へ:役所 | PLACE | 役所[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 妹が本部へ歩いた。 | へ:本部 | PLACE | 本所[a1]; 本社[a1]; 本部[a1] | NO_CANDIDATE_PASSED |
| 兄が窓口で名乗った。 | で:窓口 | PLACE | 窓口[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母がホールで断った。 | で:ホール | NATURAL_PHENOMENON | ホール[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 弟が交番で走った。 | で:交番 | PLACE | 交番[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が土間で歩いた。 | で:土間 | PLACE | 廊下[b]; 部屋[passed]; 家[a1]; 庭[passed]; 屋外[passed] | GATE_D_TIE |
| 母が広間で名乗った。 | で:広間 | PLACE | 広間[a1]; 部屋[passed]; 空間[b]; 場所[passed]; 室内[passed] | GATE_D_TIE |
| 手紙が駅へ飛んだ。 | が:手紙 | ANIMAL | 犬[passed]; 猫[passed]; 鳥[passed]; 魚[passed]; 昆虫[passed] | GATE_D_TIE |
| 夫婦がホテルで名乗った。 | が:夫婦 | PERSON | 家族[a1]; 親族[a1]; 仲間[passed]; 同僚[passed]; 友人[a1] | GATE_D_TIE |
| 友人が庭へ走った。 | が:友人 | PERSON | 友達[passed]; 仲間[passed]; 同僚[passed]; 親友[passed]; 友人[a1] | GATE_D_TIE |
| 夫婦が森へ歩いた。 | が:夫婦 | PERSON | 家族[a1]; 恋人[a1]; 仲間[passed]; 親戚[passed]; 友人[a1] | GATE_D_TIE |
| 住民が村へ歩いた。 | が:住民 | PERSON | 人[passed]; 市民[passed]; 国民[a1]; 住民[a1] | GATE_D_TIE |
| 隊員が港へ走った。 | が:隊員 | PERSON | 兵士[passed]; 将校[a1]; 士官[a1]; 警備員[passed]; 巡査[a1] | GATE_D_TIE |
| 先生が校舎で挨拶を断った。 | を:挨拶 | EVENT_ACT | 挨拶[a1]; 手紙[a1]; 電話[a1]; メール[a1]; 連絡[a1] | NO_CANDIDATE_PASSED |
| 母がホテルで勝利を願った。 | を:勝利 | EVENT_ACT | 達成[passed]; 成功[a1]; 実現[passed]; 得る[a1]; 獲物[a2] | GATE_D_TIE |
| 姉が神社で日程を断った。 | を:日程 | ABSTRACT | 予定[a1]; 計画[a1]; スケジュール[a1]; 日付[a1]; 時間[a1] | NO_CANDIDATE_PASSED |
| 兄がアパートで地図を断った。 | を:地図 | ABSTRACT | 地図[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 姉が机を中から広場へ引いた。 | を:机 | ARTIFACT | 机[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 母が荷物を港へ押した。 | を:荷物 | ARTIFACT | 荷物[a1] | GATE_A_NOT_PLACED:PLACEMENT_UNPLACED |
| 姉が机を工場から広場へ引いた。 | を:机 | ARTIFACT | 机[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |
| 兄が山田に催促した。 | に:山田 | TIME | 先週[a1]; 昨日[a1]; 今月[a1]; 直近[b]; 近日[a1] | NO_CANDIDATE_PASSED |
| 姉が本社に請求した。 | に:本社 | TIME | 昨日[a1]; 先月[a1]; 今週[a1]; 直近[b]; 過去[a1] | NO_CANDIDATE_PASSED |
| 妹が山田に申告した。 | に:山田 | TIME | 昨日[a1]; 先週[a1]; 今月[a1]; 去年[a1]; 今朝[a1] | NO_CANDIDATE_PASSED |
| 家族が図書館へ走った。 | が:家族 | PERSON | 親戚[passed]; 族[a1]; 家系[a1]; 一族[a2]; 血縁[a1] | GATE_D_CHOICE_ABSTAINED:NONE_SELECTED |
| 家族が図書館へ走った。 | へ:図書館 | PLACE | 駅[passed]; 公園[passed]; 学校[a1]; 病院[passed]; 家[a1] | GATE_D_TIE |
| 警察が家へ歩いた。 | が:警察 | PERSON | 警官[passed]; 警部[a1]; 巡査[a1]; 署員[a1]; 警察官[passed] | GATE_D_TIE |
| 警察が家へ歩いた。 | へ:家 | PLACE | 家[a1]; 駅[passed]; 学校[a1]; 病院[passed]; 公園[passed] | GATE_D_TIE |
| 妹が東京に旅行した。 | に:東京 | TIME | 東京[a1] | GATE_A_NOT_PLACED:PLACEMENT_MULTIPLE |

タイ（GATE_D_TIE）の行は、複数の語が全ての門を通ったために棄権したもの。通った語が妥当かどうかは目視で見ていない（採用していないので誤採用にならない）。
