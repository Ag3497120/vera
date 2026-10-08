## T6aa results (S300 RUN; T6z defaults + common answer of a list; 90 fixed questions; search budget 64/8; level mid)

- legacy check: common=None answer_obj equals the stored T6z answer object (sha256 of the sorted-key JSON) for 45 of 45 read-outs; mismatches: none
- trace check (incl. common answers): 45 / 45 read-outs 100% (failures 0)

(1) rule B official (answerable a01..a60; unanswerable = fict + attr)

| system | correct/wrong/abstain | unanswerable answered (fict+attr) |
|---|---|---|
| T0 legacy a1 | 45/7/8 | 3+8 = 11 |
| T6z rule B (list = abstention) | 18/3/39 | 2+2 = 4 |
| **T6aa rule B (list answered by common words)** | 18/4/38 | 3+3 = 6 |

verdicts: {'ANSWER': 25, 'CHOICE': 20, 'None': 45}

(2) lists

- lists (CHOICE): 20; with a non-empty common answer: 3; with an empty common answer (stay a list = abstention): 17
- common answers of answerable questions: 1, containing gold: 0; of unanswerable (fict/attr): 2 (answered = wrong)
- lists with empty common answer: intersection empty 10; intersection only query units/centres 7

| id | gold | entries | intersection | query units | centres (n) | common answer | gold in it |
|---|---|---|---|---|---|---|---|
| a05 | 創世記|旧約聖書 | 19 | 0 | オナン、書物、登場 | 2 | (empty) | N |
| a06 | イクスピアリ | 45 | 1 | ムーン、工房ハーヴェスト、経営、舞浜地ビール | 1 | (empty) | N |
| a11 | ウガンダ | 89 | 0 | テレゴ、国、県 | 6 | (empty) | N |
| a16 | 大邱広域市|大韓民国 | 34 | 1 | FC、大邱、本拠地 | 1 | (empty) | N |
| a19 | イタリア共和国|カラブリア州 | 22 | 1 | ジェラーチェ、国 | 1 | (empty) | N |
| a24 | 医療行為|代替医療 | 65 | 1 | 温熱療法 | 1 | (empty) | N |
| a27 | 断熱層|構造|工法 | 42 | 0 | 外断熱 | 3 | (empty) | N |
| a32 | 小野拓実 | 26 | 0 | らない、作者、叱、母親 | 9 | (empty) | N |
| a33 | グラフ|頂点 | 11 | 0 | 連結グラフ | 6 | (empty) | N |
| a37 | 松本零士 | 18 | 0 | トチロー、作品、登場 | 2 | (empty) | N |
| a43 | 直線|線分 | 18 | 0 | 二等分線 | 6 | (empty) | N |
| a47 | 群馬県|新潟県|三国山脈 | 7 | 1 | 万太郎山 | 1 | (empty) | N |
| a48 | 大阪府|大阪市|大川 | 25 | 1 | 天満橋 | 1 | (empty) | N |
| a55 | 滋賀県|日野町 | 30 | 1 | 日野事件、発生 | 1 | (empty) | N |
| a59 | 職人|浮世絵版画|板木 | 6 | 2 | 彫師 | 1 | 起 | N |
| u03 |  | 85 | 0 | ヴァルケンシュタット、駅 | 3 | (empty) | - |
| u04 |  | 2 | 2 | 建設、紫苑川ダム | 1 | ダム | - |
| u19 |  | 88 | 0 | ポルタヴィーノ、国、県 | 6 | (empty) | - |
| u26 |  | 6 | 3 | 何メートル、天満橋、長 | 2 | 政府 | - |
| u30 |  | 42 | 0 | 英語名、鉱工業 | 2 | (empty) | - |

(3) per-question grade changes vs T6z
- a59: abstain -> wrong
- u04: abstain -> wrong
- u26: abstain -> wrong
