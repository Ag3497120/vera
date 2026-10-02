# 意味読解の健全性(W1-a): 誤読を「対応済み」として返さない

作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S`(基点 `dev` = `075d486`、未コミット)。第 3 ラウンド(中間職のレビュー `review.r2.md` の M1〜M4 への対応)を反映した版。
数値はすべて `artifacts/w1-a/` の出力から出る。§6 の表は `tests/reading_soundness/recompute.py` の出力(`artifacts/w1-a/recompute.md`)をそのまま貼ってある。
各コマンドと出力ファイルの対応は `artifacts/w1-a/COMMANDS.md`。

## 1. 目的

読解器(`verantyx/semantic_reader.py` と `verantyx/constructions/`)と検査(`verantyx/semantic_verify.py`)が、誤った構造を「対応済み(unsupported なし)・検証済み」として返すのをやめる。
手段は 2 つで、この順に優先した。(1) 誤読の型ごとに、誤った役割を作る段の規則を直して正しく読む。(2) 正しく読めないものは、節を消さずに型付きの unsupported 理由を足して返し、検査が通さない。
分かることと偽であることを混ぜない: 「読めない」は偽の構造でなく、型付きの理由(§4.2 の表)で返す。
第 1 ラウンドの反省: 規則が評価バンクの語彙(場所の接尾辞の一覧、数字＋時の形、副詞可能 の語)に合っていて「型としては直っていない」と指摘された。第 2 ラウンドは、型を **肯定側の基準**(時を表す形態素、動作主になれること、受け手であること)で定義し直し、バンクに無い下位形を新しいバンクで測った。

## 2. 型の定義と評価バンク(自作・評価バンクは見ていない)

置き場所 `tests/reading_soundness/`(JSON Lines)。正解は読解器に通す前に書いて凍結した(第 1 ラウンド: `artifacts/w1-a/bank_freeze.sha256`、第 2 ラウンド: `bank_freeze_r2.sha256`、第 3 ラウンド: `bank_freeze_r3.sha256`)。いまのファイルの sha256 は §6 の表(すべて凍結時と一致)。

| 型 | 中身 | 文数 | ファイル |
|---|---|---|---|
| J1 | 時間・場所表現の役割(受身＋時間に／能動＋時間に／受身＋場所に／主題の時間名詞) | 17 | ja.jsonl |
| J2 | 受身の動作主(あり／なし／間接受身) | 18 | ja.jsonl |
| J3 | 時間副詞句と主語(読点あり／なし／時間以外の副詞句) | 15 | ja.jsonl |
| J4 | 変換先・結果／真の受け手 | 15 | ja.jsonl |
| J5 | 比較 | 17 | ja.jsonl |
| J6 | 指示語 | 16 | ja.jsonl |
| J7 | 使役 | 16 | ja.jsonl |
| J8 | 二重否定 | 17 | ja.jsonl |
| J9 | 挨拶・感動詞・断片・無意味 | 18 | ja.jsonl |
| T7 | 指示書表の 7 文(正解付き) | 7 | table7.jsonl |
| **K1** | 数字の時刻・期間の変種(半・過ぎ・時間後・頃・日後・上旬・年代) | 10 | ja_r2.jsonl |
| **K2** | 時間でない 副詞可能 の語＋読点(結局・実際・以上・普通・基本的に・全部・通常)。正解は副詞を除いた主節の構造 | 7 | ja_r2.jsonl |
| **K3** | 受身＋に＋(場所語の一覧に無い)場所の名詞(窓辺・玄関先・屋根裏・駐車場の隅・棚の上 …) | 8 | ja_r2.jsonl |
| **K4** | 変化・日程変更の述語＋時間の に(変更・延期・変える・延長・繰り下げ・前倒し) | 6 | ja_r2.jsonl |
| **K5** | を の目的語＋色・状態の に(動詞は類の外: 塗る・張り替える・塗り直す。gold_scramble の経路を狙った) | 5 | ja_r2.jsonl |
| **K6** | 挨拶の定型(お世話になっております・失礼いたします・お待たせいたしました …) | 7 | ja_r2.jsonl |
| **L1** | 受身＋に＋(場所・部位・催し・組織にも見える語: 境内・礼拝堂・下部・展示会場・内部・町内会館・校舎裏)7、本当に組織が動作主(警察・委員会・探検隊・政府・劇団)5、部・課(野球部・経理課)2。正解は 非動作主は patient＋place|location、組織は agent＋patient | 14 | ja_r3.jsonl |
| **L2** | 変化の動詞＋人の に 句: 受益者・分配先(人)8(恩恵の補助動詞あり 4、なし 2、分ける 2)、目的語が人で に が地位(任命・選出・抜擢・登用)4 | 12 | ja_r3.jsonl |
| **L3** | `Nのより Adj`(より がタガーで副詞になる比較。standard は準体の の を含む句) | 6 | ja_r3.jsonl |
| E0 | 英語の統制(読めて正しい単純文) | 8 | en.jsonl |
| E1〜E6 | 否定／量化／関係節／使役／比較／従属節 | 8, 9, 8, 8, 8, 8 | en.jsonl |
| **F0** | 英語の統制(読めて正しい文) | 6 | en_r2.jsonl |
| **F1〜F6** | 縮約関係節／分詞の後置修飾／that なし補文／従属節 as・so that など／数と焦点の量化／補文動詞(keep/see/hear＋目的語＋-ing など) | 5, 5, 5, 5, 6, 6 | en_r2.jsonl |
| A3 | 受身で動作主なしの「誰が」質問(時間 4・場所 4) | 8 | a3.jsonl |
| **A3R2** | 同(受身＋に の場所 4・時刻の変種 3) | 7 | a3_r2.jsonl |
| **A3R3** | 同(受身＋に＋場所・催し・部位・組織にも見える語 6) | 6 | a3_r3.jsonl |

正解の書き方と照合規則は `tests/reading_soundness/harness.py` の docstring が正本。要点: `kind=clauses`(alternatives のどれかと対象節が全部一致)、`none`(構造化しない)、`unsupported`(Frame・読解器が表せない。棄権が正)、`frame`(英語)。節の一致は述語・極性・役割の過不足なしの完全一致。英語は時間の副詞を Frame が持たないので、落としても誤読としない。
第 2 ラウンドの日本語バンク(K1〜K6)の正解は「unsupported」ではなく**正しい構造**で書いた(読めずに未対応になるのは構わないが、それは未対応であって正読ではない)。
O1(レビューの任意改善)を実装: 対象節の一部だけが別々の alternative に一致する場合の `false_pass` は、いちばん多くの節を説明する alternative に照らして数える。

**凍結後の変更**: 第 1 ラウンドで J1-17 の正解を 1 行甘くしたが、第 2 ラウンドで**凍結時の正解に戻した**(R9)。`ja.jsonl` の sha256 は凍結時の `d4bff65f…` に一致する。経緯の記録は `bank_gold_amendment.txt`・`bank_after_amendment.sha256`・`soundness_after_pre_gold_amendment.{json,txt}`(読み取り用に残した)。

## 3. 原因表(誤った役割が付く段)

自作文の dev 結果(`artifacts/w1-a/soundness_dev.json`)と手元の probe で確かめた。`frames.py` は共有部品で許可パス外なので変更していない。「第 2 ラウンドで足した原因」は、レビューの再現文(`review_r1_examples_ja_dev.txt`)で確かめた。

| 型 | 再現(バンク id) | 誤った役割が付く段(ファイル:関数) | 確かめた事実 |
|---|---|---|---|
| 時間表現が参与者(受身の agent、能動の recipient/goal) | T7-01, J1-01〜J1-11, **K1-01〜K1-10** | `frames.py:_frame` が最初の に 句を受身なら agent、能動なら recipient に入れる(時間除外は 副詞可能 の語だけ)。`semantic_reader.py:_piece` の frame 分岐がそれを型を見ずに Role にした。`semantic_verify.py:license_clause` の frame 分岐も `frames.read_all` と同じ割当を要求していた。**第 2 ラウンドで足した原因**: 時間型の判定自体が「数詞を含む句は時間でない(`_is_time_phrase`)」「数字＋時の形(`_TIME_PHRASE_NUMERIC`)」に限られ、`6時半`・`3時過ぎ`・`2時間後` を取りこぼしていた(検査側 `_VT_CLOCK`・`_vt_is_time` も同じ穴) | dev の K1: 10 文中 3 が誤読(soundness_dev.json)。レビュー再現文 `6時半に姉が家を出た。` は dev で recipient=6時半 |
| 副詞可能 を時間の基準にした誤り(**指示書手順 6 の誤りの訂正**) | **K2-01〜K2-07**、レビュー再現文(結局・実際・一部・以上) | `semantic_reader.py:_is_time_phrase`/`_time_word_adverbial`・`semantic_verify.py:_vt_is_time` が `副詞可能` だけで時間とみなし、結局・実際・一部・以上・全部 を `time` にした | dev の K2: 7 文中 2 が誤読。レビュー再現文は dev で `time=結局` など |
| 主題の時間名詞が参与者 | J1-15〜J1-17 | 同上(は 主題が空いた agent/patient に入る) | dev で 戦後 が agent/patient |
| 時間副詞句と主語の結合 | T7-02, J3-01〜J3-12 | `constructions/np_internal.py:_parse`(読点 `、` を並列と読んで `今朝、妹` を 1 つの名詞句にする)、`constructions/time_expr.py:_role_chain`(`兄が公園` を 1 つの役割句にする)、`semantic_reader.py:_time_adverbial` | dev の J3: 誤読 8 |
| 受身の に 句の動作主(**場所の否定一覧が原因**) | J1-12〜J1-14、**K3-01〜K3-08**、A3R2-01〜04 | 第 1 ラウンドの `_role_claim`・`_type_gate` は「場所語の一覧に入るなら agent にしない」(否定の一覧)で、一覧に無い場所の語(花壇・屋上・窓辺 …)はすべて agent として残った。diathesis 経由の節(机の上)にも同じ穴。検査側も一覧が違っていた | dev の K3: 8 文中 8 が誤読(`soundness_dev.txt`)。`花壇に花が植えられた。` は dev で agent=花壇 |
| **受身の に 句の動作主(第 3 ラウンド M1: 末尾の文字で組織と判定した)** | **L1-01〜L1-07, L1-13, L1-14**、A3R3-01〜06、レビュー再現文(神社・教会・外部・胸部・棚の一部・高校・茶会・大会・本社・商社) | `semantic_reader.py:_is_person_phrase` が `head.endswith(_PERSON_SUFFIXES)`(社・会・部・校 …)で人・組織とした。神社・教会・茶会・大会・外部・胸部・一部・高校・山間部・出力部 は末尾の文字が組織の接尾辞と同じだけで、組織ではない(場所・催し・部位・領域・機械の部分)。場所の除外(`_is_place_phrase`)も閉じた接尾辞の一覧なので外れない。検査側 `_vt_is_addressee`(`_VT_ORGANISATION_ENDINGS`)が同じ一覧を写して同時にすり抜けた。**`太郎の鞄に` も、タガーの固有名詞を句全体から探していたため agent になった** | dev の L1: 14 文中誤読 7。第 2 ラウンドの修正後の木でも同じ形で出た(レビュー) |
| **変化の動詞の に が人(第 3 ラウンド M2: 新たな誤読)** | **L2-05, L2-06**、レビュー再現文(仕立てる・直す・選ぶ・整理する) | `semantic_reader.py:_case_role` の に 分岐が、変化の動詞(`_CHANGE_PREDICATES`)で場所・関係名詞でない に 句をすべて `result` にした(第 2 ラウンドで `_recipient_claim` が人でも `drop` にしたため、受益者の人が `result` に変わった)。検査の frame 分岐も `result` を句の型を見ずに許可した | **L2-05・L2-06(恩恵の補助動詞なし)は、dev では `recipient=<人>`(受益者。正解と一致)→ 第 2 ラウンドの木では `result=<人>`(誤読)→ 第 3 ラウンドでは未対応**。dev の L2 は 12 文中誤読 4(L2-09〜12: 地位を `recipient` にした) |
| **比較の より がタガーで副詞(第 3 ラウンド M3)** | **L3-01〜L3-06**、レビュー再現文(前のより・君のより・彼のより) | `_predicate_phrase_value` と検査の copula 分岐が、比較の より を `pos1=='助詞'` のときだけ見つけた。`の` の直後の より はタガーが 副詞 とするので、値に比較が無いとされ名詞文(identity/property)として通った | dev の L3: 6 文中誤読 5 |
| 変化・日程変更の述語の に 時間 | レビュー再現文(変更・変える・延期)、**K4-01〜K4-06** | `_case_role` の に 分岐が時間型の判定を変化の述語の判定より先に行い、変更先の時刻を出来事の時刻 `time` にした | dev の K4: 6 文中 1 が誤読 |
| 変換先を受け手にする | T7-03, J4-01〜J4-11、**K5-01〜K5-05** | `frames.py:_frame`(に→recipient)＋`_piece` の frame 分岐。**gold_scramble が frame の recipient を写す経路は再現した**(第 1 ラウンドの文書は「未再現」と書いたが誤り): `彼が部屋を青に塗った。` は frame が unsupported でも `gold_scramble` が `recipient=青` を supported で出す(`review_r1_examples_ja_dev.txt`)。門が frame の節にしか recipient の型を掛けていなかった | dev の K5: 5 文中 5 が誤読 |
| 指示語・比較の崩し | T7-04, J5-01〜J5-14, J6-01〜J6-06 | `semantic_reader.py:_piece` の copula 分岐(`lhs.split('の')` が文字で連体詞 この の「の」を切る。値に より＋形容詞 があっても名詞文とみなす)。検査の copula 分岐も同じ正規表現で同じ誤りを通した。**第 2 ラウンドの追加**: 比較構文 `comparison._dimension_bounds` が `ずっと` など程度副詞を dimension にした。等位の `AはBと同じくらい広い` は値に格助詞 と があっても述語句と見なされず identity になった | dev の J5: 誤読 14、J6: 誤読 5 |
| 挨拶・感動詞・定型句 | T7-07, J9-03, J9-06、**K6-01〜K6-07** | 同じ copula の文字走査が 感動詞トークン ありがとう の中の「が」で切る。役割 0 の frame が supported のまま。**第 2 ラウンドの追加**: `お世話になっております` は `frames.py` が `お＋名詞＋になる` から合成語 `世話る` を作り、`お世話` をその受け手にして supported にした | dev の K6: 7 文中 1 が誤読(`世話る`)、J9: 誤読 2 |
| 使役の被使役者を受け手にする | T7-05, J7-01〜J7-16 | `frames.py:_frame`(`書かせる` を 1 述語にし に 句を recipient にする)。`semantic_reader.py:_piece` は frame が unsupported なしなので構文を走らせない。`constructions/diathesis.py:_aligned_roles` は自動詞の使役の に 句を被使役者にする | dev の J7: 誤読 16 |
| 二重否定を名詞文にする | T7-06, J8-15〜J8-17 | `semantic_reader.py:_DOUBLE_NEGATION` が `なかったわけ` を拾わない。`constructions/negation.py:_copula_scope` が `報告書を送らないわけ` を名詞述語として identity にする | dev の J8: 誤読 3 |
| 主題の を空いた patient への取り込み(**第 2 ラウンドで見つけた**) | 手元の probe(`実は、弟が駅で友人に会った。`→ patient=実) | `frames.py:_frame` が は 主題を、空いた patient に入れる。会う・着く・住む のような自動詞の patient になる | 評価バンクには無かった。型の門(§4.2 の 12)で止めた |
| 英語 | E1〜E6、**F1〜F6** | `en_frames.py:read`(否定の決定詞・量化・関係節・使役・比較・従属節の印を見ず、残りの語を役割に詰める)。**第 2 ラウンドの追加**: 印の一覧(否定側)だけに頼っており、読めた Frame の正しさを検めていなかった(縮約関係節・分詞の後置修飾・that なし補文・as 節・数と焦点の量化・補文動詞・助動詞 might を読んで誤った Frame を返した) | dev の英語: E1〜E6 で誤読 5, 9, 8, 8, 8, 8、F1〜F6 で 5, 5, 5, 5, 6, 6(`soundness_dev.txt`) |

## 4. 直した規則

### 4.1 読解(正しく読む)
- **時間型の基準(肯定側)**(`semantic_reader.py:_is_time_phrase`/`_time_segment`/`_time_text`/`_time_fused`、検査側は `semantic_verify.py:_vt_counted_prefix`/`_vt_lexical_time`/`_vt_is_time`/`_vt_time_fused` を**別実装**で持つ)。時間とみなすのは次のどれかだけ。
  1. 数＋時間の助数詞(年・月・日・時・分・秒・世紀・週・時間・日間・年間・か月・曜日・年代・年度)の並びに、時間の接尾(半・過ぎ・前・後・頃・以降・以内・末・上旬 など)が付いたもの。午前・夜 などの前置、約、元号、同・翌・昨・来・今・毎 の接頭も可(`6時半`、`3時過ぎ`、`2時間後`、`数日後`、`2020年代`、`令和三年`)。元号名は既存の `_TIME_DATE` から取り出す(語を再掲しない)。
  2. 時を表す形態素(朝昼晩夜夕午週月年日曜期代世季春夏秋冬頃旬暮宵刻前後今昔現将初末)を含む名詞で、かつタガーが 副詞可能 と付けたもの。閉じた直示語(最近・当時・今後・以降・次 …)と暦の語(元日・大晦日・休日・誕生日・夏休み …)は 副詞可能 でなくてもよい。`<時間形態素>+明け/末/初め`(年明け・期末・月末)、`年度・学期・世紀・時代`、`<名詞>日`(給料日)も可。
  3. `<出来事名詞>の前/後`・`<出来事名詞>前/後/中/間際`(試合の後・食事中・閉館間際・退局後)。場所＋前(駅前・校舎前・駅の前)、空間語だけの句(前・上・中・時 単独)は時間でない。
  4. `の` で連なる句は主辞が時間ならよい(先週の金曜日、去年の夏)。固有名詞(…朝)・格助詞を含む句は時間でない。
  **副詞可能 だけでは時間にしない**(結局・実際・一部・以上・全部 は時間でない)。基準は `semantic_reader.py` の `_TIME_*` の docstring/コメントにある。
- **frame の参与者を型で検める**(`_role_claim`): 時間句(に/は)は参与者にしない(`time` 役割として付ける)。受身の に 句は、**動作主になれる型**のときだけ agent(`_can_be_passive_agent`: 人・人名・代名詞・役職・組織・動物で、場所でもあるもの〈学校・会社〉は除く。包含の動詞〈囲まれる〉は例外。伝達・授受の動詞は主語が人のときと、を の目的語があるとき(間接受身)だけ)。から 句は、時間・場所だけの語は agent にせず `source` として読む(`_is_origin_not_agent`)。recipient の に 句の型は `_recipient_claim` に 1 か所にまとめた(受け手の動詞・恩恵・人 → recipient、変化・日程変更の動詞 → `result`、移動・設置・場所の動詞の終点は従来どおり recipient、そのほかで を の目的語があり人でも場所でもないものは claim せず曖昧にして unsupported)。主題 は の patient は、自動詞(`frames.transitivity` が `intrans`)なら claim しない。
- **変化・日程変更の述語**(`_CHANGE_PREDICATES`): 基準は「目的語の値を変える/決め直す」動詞(変形・変換・分割・状態変化・昇進・任命・色の変更・日程の延期/前倒し)。に 句が時間型でも、を の目的語**の後ろ**にあれば `result`(新しい値)、前にあれば出来事の時刻かもしれないので `ambiguous`(unsupported)。`time` にはしない(`_case_role` の `after_object`)。`_PLACEMENT_PREDICATES` から 塗る を外した(塗る は面にも色にも使い、置く類ではない)。分け合う動詞(`_SHARING_PREDICATES`)だけが人の受け手を取り、数を表す句(二つのグループ)は受け手にしない。
- **topic の時間**(`_time_topic`)、**読点の時間副詞**(`_time_word_adverbial`)、**copula の token 分割**(`_copula_split`)、**attribute の分割**(`_split_attribute`)、**値が述語句**(`_predicate_phrase_value`: 最後の内容語が形容詞・形状詞・動詞で、より・が・を・に・で・へ・から・まで・と のいずれかを含む。括弧の中と末尾の 〜である/〜であった は数えない)は unsupported。**感動詞**で始まる挨拶は `Unread('interjection is not a proposition')`。
- **述語そのものを参与者にしない**(`_repeats_predicate`): 参与者の語幹(お・ご を除く、2 文字以上)が述語の語頭と一致するとき(`世話る` と `お世話`)。1 文字の同族目的語(歌を歌う)は止めない。
- **役割 0 の節**: 参与者が全く無い節は、文に内容語が残っているか否かによらず supported にしない(`event without participant or content word`)。modality などの構文が、参与者を黙って落とした空の節を supported にするのを止める。
- **構文**: `np_internal` は、時間・関係の語(副詞可能・形状詞可能・連体詞＋副詞可能)＋読点を並列にしない。読点だけの 2 項の対で、片方が人でもう片方が人でないもの(普通、母)も並列にしない(実在の並列の `本科5学科、専攻科2専攻` や 人と人の対は残す)。`time_expr` は が/は をまたぐ役割句を作らない。`diathesis` は使役の被使役者を native frame が recipient とした句に限り、自動詞の使役(を＋に)は `frames.transitivity` が他動詞でなければ棄権、基底の動詞を語幹で一意化する。`negation` は 名詞述語 が節のとき名詞文にしない。`comparison` は dimension が名詞でなければ(程度副詞・副詞形)形容詞自身を dimension にする。`adnominal` は location 役割を setting の元として受ける。`gold_caus_pass` と `diathesis` の安全理由に使役の理由を名指しで足した。
- **人・組織の判定を正の証拠にする(第 3 ラウンド M1)**(`semantic_reader.py:_is_person_phrase`、検査側 `semantic_verify.py:_vt_is_addressee` は別実装): 語の末尾の文字(社・会・部・校・所 …)では判定しない。人・組織とするのは、句の主辞(最後の の より後ろ)が次のどれかのときだけ。(a) 閉じた人・集合行為者の名詞(`_PERSON_NOUNS`: 警察・企業・政府・協会・機関・組合・劇団・財団・役所・国会・政党・部隊・陸軍・刑事・山賊・取締役会 …、親族・役職を含む。語義が組織に偏る語だけ。学会・大会のような催しとも読める語、会社・大学のような場所でもある語は入れない)または `frames.ROLES`・学習済み役職、(b) 代名詞、(c) 主辞が人名・組織名・一般の固有名詞(名前そのもの。**固有名詞が主辞の前にあるだけの句は人としない**: 太郎の鞄、山田橋、伏見稲荷神社)、(d) 名詞の後ろにタガーが 接尾辞 とした さん・氏・君・様・殿・達・たち・ども・ちゃん・団・隊(消防団・探検隊・子供達)、名詞の後ろの 軍・チーム(連合軍・開発チーム)、(e) 人の役職名詞＋会(委員会)、(f) `frames.is_role` の末尾の人接尾(整備士・研修生・部長)で、サ変可能(動作名詞: 成長・関係・配達)でないもの。いずれにも当たらない受身の に 句は agent にせず、既存の `_NONAGENT_REASON` で unsupported にする。部・課・会・社 で終わる語は、名前(固有名詞が主辞)か役職名詞＋会でなければ組織とみなさない(野球部・経理課・出力部・山間部 は区別できないので未対応)。
- **変化の動詞の に 句(第 3 ラウンド M2)**(`_case_role`): (1) に 句が目的語**より前**(BにAを直す)なら `result` にしない(`ambiguous`)。語順は語彙を要さない根拠。(2) 人の に 句は、目的語(受身なら主語)も人のとき(`彼を部長に任命`)に限り `result`(状態・地位)。目的語が物のとき(`娘に着物を仕立てた`)は受益者で、`result` ではなく `ambiguous`(恩恵の補助動詞があれば recipient)。(3) 地位を授ける動詞(`_APPOINTMENT_PREDICATES`: 任命・登用・起用・抜擢・選任・選出・指名・認定・昇進・昇格・降格)は、目的語が人であることを動詞自身が選択するので、目的語の判定を問わず に 句を `result`。検査側は自前の `_VT_APPOINTMENT_VERBS` と語順・人の判定で、同じ型の `result` を拒否する。
- **比較の より(第 3 ラウンド M3)**: `より` が名詞・代名詞・数・`の` の直後にあれば、品詞タグ(助詞/副詞)によらず比較の印とみなし、copula の値を述語句(unsupported)にする(`前のより軽い`)。値の先頭の副詞 より(`より良い社会`)は比較の印としない。比較構文が読めれば読み(standard は準体の の を含む句 `前の`)、読めなければ未対応。`ほど` の比較は、`ほど…ない` を比較構文が既存のまま読む(copula の値には入らないので変更していない)。
- **英語**(`en_frames.py:read_typed`): 否定側の印(否定の決定詞・量化・関係節・使役・不定詞補文・比較・従属節・等位・助動詞・焦点語・文頭の否定・as)に加えて、**読めた Frame の肯定側の検め**を足した。(a) 主動詞のトークンが動詞か(`_verb_token_problem`: be の後は分詞だけ。限定詞・前置詞・形容詞を動詞にしない)。(b) 各役割が名詞句か(`_np_problem`: 数詞・焦点語・接続詞・助動詞を含まない。小文字名詞の後の代名詞・固有名詞〈縮約関係節〉、末尾の分詞、知覚・保持動詞の後の -ing を含まない)。(c) 文の内容語がすべて述語か役割に覆われているか(`_frame_problems`: 黙って落とした語があれば `(None, 理由)`)。(d) 小節(painted the room blue)、変化の動詞の to/into(convert X to Y: 結果であって受け手でない)、動詞の後の節(thinks the report is late)。`read` は `read_typed` の Frame を返す。比較の形容詞の語幹一覧は、評価文でなく一般の語彙(1〜2 音節の変化する形容詞)から作り直し、条件の 2 語組と評価文由来の語(crowded, red)を削除した(R8)。`regression()['all_pass']` は True。

### 4.2 門(読めないと言う)と検査

`semantic_reader._type_gate`(すべての規則の節に掛かる)は節を消さず、次の型付き理由を足す。検査は `semantic_verify._vt_check_roles`(`license_clause` の汎用部で全規則に掛かる)と frame 分岐の `_vt_participant_excluded` が、読解を import せず自前のトークン化・自前の定義で同じ型を検める。**各門に、止める正例 3 件以上と残す負例 3 件以上**を `tests/reading_soundness/test_gates_round2.py`・`test_gates_round3.py`(第 2 ラウンド)と `test_reading_soundness.py`(第 1 ラウンド)に置いた。

| 理由(typed) | 条件 | 止める正例(テスト, 文数) | 残す負例(テスト, 文数) |
|---|---|---|---|
| `ill-typed role: time phrase as event participant` | 事象の参与者が時間型で に/は に続く(数字の時刻・期間の変種を含む) | `test_gate_counted_time_is_read_as_time`(5)、`…not_dropped_to_nothing`(3)、`test_gate_time_phrase_is_never_an_event_participant`(5) | `test_gate_ordinary_verb_keeps_its_time`(3)、`test_gate_time_phrase_keeps_real_passive_agents`(3) |
| `ill-typed role: time phrase fused with participant` | 時間語が参与者の名詞と助詞なしで連なる | `test_gate_time_word_fused_with_subject_is_not_read`(3) | `test_gate_time_adverbial_before_a_comma_is_kept_as_time`(4) |
| (時間でない 副詞可能 を time にしない) | 時を表す形態素・直示語・暦の語のどれも持たない 副詞可能 は時間でない | `test_gate_non_time_adverbial_noun_is_not_a_time`(4)、`test_non_time_phrases_are_not_time`(61 句) | `test_time_phrases_are_time`(72 句) |
| `ill-typed role: a phrase that cannot act (not a person/organisation) as agent` | agent に続く が に・へ・から の句が、人・組織・動物でない(場所でもある語、伝達の動詞の直接受身の受け取り手、場所だけ・時間だけの から 句を含む) | `test_gate_non_agent_ni_phrase_is_not_the_agent_of_a_passive`(6)、`test_gate_place_with_kara_is_the_source_not_the_agent_of_a_passive`(4)、`test_gate_time_with_kara_is_never_an_agent`(3)、`test_gate_direct_passive_of_a_transfer_verb_has_a_recipient_not_an_agent`(3) | `test_gate_person_ni_phrase_keeps_the_agent_of_a_passive`(5)、`test_gate_person_or_organisation_with_kara_keeps_the_agent_of_a_passive`(4)、`test_gate_an_animal_can_be_the_agent_of_a_passive`(3)、`test_gate_indirect_passive_of_a_transfer_verb_keeps_its_agent`(3) |
| `ill-typed role: a phrase that cannot act (not a person/organisation) as agent`(**第 3 ラウンド: 判定を正の証拠に変更**) | 受身の に 句の主辞が、上の (a)〜(f) のどれでもない(末尾が 社・会・部・校 の語、固有名詞が主辞の前だけにある句を含む) | `test_m1_a_word_that_only_ends_like_an_organisation_is_not_the_agent`(9)、`test_m1_checker_refuses_the_same_clause_with_the_unsupported_mark_removed`(3)、`test_m1_reader_and_checker_both_say_no_person`(17 句) | `test_m1_a_person_or_an_organisation_by_positive_evidence_is_still_the_agent`(13)、`test_m1_reader_and_checker_both_say_person`(19 句) |
| `ill-typed role: a person as the result of a verb of change on a thing` / `…a に-phrase before the object of a verb of change is not its result` | 変化の動詞(地位を授ける動詞を除く)の `result` が、人(目的語は物)、または目的語より前の に 句 | `test_m2_a_person_after_the_object_of_a_verb_of_change_is_not_a_result`(5)、`test_m2_a_に_phrase_before_the_object_is_never_the_result_whoever_it_names`(5。人の語彙に無い語)、`test_m2_checker_refuses_the_person_result_with_the_unsupported_mark_removed`(3)、`test_m2_checker_refuses_a_result_that_precedes_its_object`(3) | `test_m2_a_status_for_a_person_object_and_a_thing_result_are_still_results`(6)、`test_m2_a_result_after_its_object_is_still_read`(3)、`test_m2_a_beneficiary_with_a_benefactive_is_still_the_recipient`(3) |
| `copula value is a predicate phrase`(**第 3 ラウンド: 副詞の より**) | より が の・名詞・代名詞・数の直後 | `test_m3_a_comparison_with_a_nominalised_standard_is_not_an_identity_or_property`(4)、`test_m3_checker_refuses_the_copula_clause_with_the_unsupported_mark_removed`(3) | `test_m3_a_noun_sentence_without_a_comparison_is_still_read`(4) |
| `ill-typed role: recipient is not an addressee` | recipient に続く に の句が、受け手の動詞・恩恵・人・終点の動詞のどれでもなく、を の目的語がある(**すべての規則の節**: gold_scramble を含む) | `test_gate_result_colour_is_never_a_recipient_whichever_rule_reads_it`(4) | `test_gate_real_recipients_are_kept_after_the_gate_moved`(4)、`test_gate_real_recipients_are_kept`(3) |
| `ill-typed role: time phrase as place/goal/direction/result` | goal・location・direction・place が時間型、または変化の動詞でない述語の result が時間型 | `test_checker_rejects_a_counted_time_renamed_to_a_participant_or_adjunct`(7) | `test_gate_rescheduling_time_is_the_result`(4) |
| `ill-typed role: time phrase of a verb of change is its new value, not when it happened` | 変化・日程変更の述語で、を の目的語があり、`time` 役割が に に続く | `test_gate_rescheduling_time_is_the_result`(4。`time` が出ない) | `test_gate_ordinary_verb_keeps_its_time`(3) |
| `ill-typed role: participant repeats the predicate itself` | 参与者の語幹(2 文字以上)が述語の語頭と一致 | `test_gate_participant_repeating_the_predicate_is_not_read`(3) | `test_gate_cognate_object_is_kept`(3) |
| `ill-typed role: a は-topic as the patient of an intransitive verb` | patient に続く が は で、述語が自動詞(受身を除く) | `test_gate_topic_is_not_the_patient_of_an_intransitive_verb`(4) | `test_gate_topic_patient_of_a_transitive_verb_is_kept`(4) |
| `ill-typed role: phrase spans a case particle` / `span cuts a token` | 名詞役割が が・を・は・より を括弧の外でまたぐ(節の名詞化は除く)/ 役割境界が語の途中 | `test_checker_rejects_an_entity_cut_inside_a_word` ほか | `test_gate_demonstrative_is_one_entity`(3) |
| `event without participant or content word` | 参与者が無い節(すみません、断片、役割を落とした空の modality) | `test_gate_greetings_are_not_propositions`(3) | `test_gate_short_clauses_with_a_participant_are_kept`(3) |
| `causative frame: causer/causee unresolved` | 使役の frame に recipient(被使役者)が残る | `test_gate_causative_roles_are_causer_causee_patient`(3)、`test_gate_intransitive_causative_is_not_read_as_causee_destination`(3) | 同上(知らせる・を のみの使役は止めない) |
| `copula value is a predicate phrase` | 値が述語句、または より を含む。等位の と も含む | `test_gate_comparison_is_not_an_attribute_sentence`(3)、`test_gate_equative_is_not_a_copula_identity`(3) | `test_gate_demonstrative_is_one_entity`(3) |
| (comparison の dimension) | dimension は名詞だけ | `test_gate_degree_adverb_is_not_the_comparison_dimension`(3) | `test_gate_noun_dimension_is_kept`(3) |
| 英語の `(None, 理由)` | 助動詞・縮約関係節・分詞の後置修飾・小節/知覚補文・変化の動詞の to・埋め込み節/コピュラ | `test_en_*`(4+3+3+4+3+4) | `test_en_plain_sentences_are_still_read`(4)、`test_english_controls_are_still_read`(F0 6 文) |

読解と検査は述語類・時間語の一覧を別々に持つので、`test_reader_and_checker_class_lists_agree` と `test_round2_class_lists_agree` が一覧の一致を、`test_reader_and_checker_agree_on_what_a_time_is`(133 句)が時間型の判定の一致を検める(独立性を保ったまま食い違いによる INVALID_PROOF を防ぐ)。
**検査の変異テスト**(`test_checker_*`、第 1 ラウンド 8 件＋第 2 ラウンド 12 件): 時間句を agent/recipient/patient/goal/place/location/direction に戻す、agent と patient を入れ替える、result を recipient/time に戻す、日程変更の結果を goal に戻す、比較の direction を反転する・dimension を替える、entity を語の途中で切る、causee と patient を入れ替える。すべて検査が拒否する(`pytest_reading_soundness.txt`)。

### 型付き理由(`coverage_after.json` の理由集計に現れる)
出典: `coverage_after.json` の `unsupported_reasons_pct_of_only_unsupported`(「unsupported だけの文」に対する割合)と `unread_reasons`。第 2 ラウンドで足した理由(`ill-typed role: …`)の集計は `coverage_clauses_after.jsonl`(全節の理由)で数えられる。感動詞の Unread は `unread_reasons` の `unsupported clause grammar` に含まれる。

## 5. 測定条件

- 修正前: `dev` の `git archive 075d486` を作業用ディレクトリ(`COMMANDS.md` の DEV。W の外)に展開。修正後: W(HEAD `075d486`、未コミットの差分)。どちらも `env -i … PYTHONPATH=<木>`、harness の隔離検査が「読み込まれた verantyx* が全部その木の配下」を確認(`soundness_dev.txt`, `soundness_after.txt` の `foreign_modules=[]`、`A0_final.txt` の `outside: []`)。
- カバレッジの入力 `jawiki_leads.full.jsonl`: 720,529,154 バイト、sha256 `7585034b6149bf3b9f684cc0c354dbfb203ceed928e15955a399d1cbbdf045ae`(`leads.sha256`)。`tools/read_coverage.py` は無改変、`VERA_LEADS` を渡し `--n 1500 --stride 200`。
- 評価バンクの凍結: §2。第 2 ラウンドのバンクは、読解器に通す前に `bank_freeze_r2.sha256` で凍結し、**最初の実行で誤読 2 件(K2-04 `普通、母が…`、F5-06 `Nearly fifty guests …`)が見つかった**(`soundness_after_r2_first_run_before_np_en_fix.json`: 誤読 3 = この 2 件＋ J1-17)。正解は直さず、規則(np_internal の人と非人の対、英語の数詞・近似語)を直した。

- 第 3 ラウンドのバンク(`ja_r3.jsonl` 32 文・`a3_r3.jsonl` 6 文)は、読解器(harness)に通す前に `bank_freeze_r3.sha256` で凍結した。**凍結前に、似た形の文を手元の probe(`show_clauses.py`)に通している**(レビュー指摘の文と、野球部・消防団・委員会・運動会・山間部・出力部 など M1〜M3 の下位形を探すための文。バンクの文そのものは凍結前に一度も通していないが、同じ語彙の文を見て規則を作ったので、バンクは未知入力ではなく「同じ型の確認」である)。凍結後の最初の harness 実行で `ja_r3` は誤読 0・検査誤通過 0(正読 L1 5/14、L2 10/12、L3 6/6)。正解は直していない。
- 第 3 ラウンドの規則修正は、レビューの文と手元の追加 probe(重複を除いた 141 文: 場所・催し・部位・組織の語の受身、変化の動詞＋人、Nのより Adj。入力 `r3_probe_ja.txt`、dev での読み `r3_probe_ja_dev.txt`、修正後 `r3_probe_ja_after.txt`)に対して行った。probe で見つけた同型の穴(`太郎の鞄に`・`伏見稲荷神社に`・`運動会に`・`山間部に`・`出力部に`・`配達に`、`先生が児童に絵本を編集した`)は、型の条件(正の証拠・語順)で直した。残った穴は §8 K13〜。

## 6. 結果

(`recompute.py` の出力。出典 `soundness_dev.json`, `soundness_after.json`, `coverage_*.json`, `dropped.tsv`, `gained.tsv`, `changed.tsv`, `*_classified.tsv`, `before/after_pytest.txt`, `bank_freeze*.sha256`)

#### 型ごとの結果(出典: soundness_dev.json / soundness_after.json)

| 型 | 文数 | dev 正読 | dev 誤読 | dev 未対応 | dev 検査誤通過 | 修正後 正読 | 修正後 誤読 | うち上申済み | 修正後 未対応 | 修正後 棄権が正解 | 修正後 正読かつ全節検査PASS | 修正後 検査誤通過 | 正読が半数以上 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E0 | 8 | 8 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| E1 | 8 | 3 | 5 | 0 | 0 | 3 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| E2 | 9 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 9 | 9 | 0 | 0 | False |
| E3 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E4 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E5 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| E6 | 8 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 8 | 8 | 0 | 0 | False |
| F0 | 6 | 6 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| F1 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F2 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F3 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F4 | 5 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 5 | 5 | 0 | 0 | False |
| F5 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | False |
| F6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 6 | 6 | 0 | 0 | False |
| J1 | 17 | 0 | 16 | 1 | 15 | 13 | 1 | 1 | 3 | 0 | 13 | 1 | True |
| J2 | 18 | 17 | 1 | 0 | 1 | 17 | 0 | 0 | 1 | 0 | 17 | 0 | True |
| J3 | 15 | 1 | 8 | 6 | 9 | 9 | 0 | 0 | 6 | 6 | 9 | 0 | True |
| J4 | 15 | 4 | 11 | 0 | 11 | 13 | 0 | 0 | 2 | 0 | 13 | 0 | True |
| J5 | 17 | 1 | 14 | 2 | 14 | 11 | 0 | 0 | 6 | 0 | 11 | 0 | True |
| J6 | 16 | 10 | 5 | 1 | 5 | 15 | 0 | 0 | 1 | 0 | 15 | 0 | True |
| J7 | 16 | 0 | 16 | 0 | 16 | 9 | 0 | 0 | 7 | 0 | 9 | 0 | True |
| J8 | 17 | 14 | 3 | 0 | 0 | 14 | 0 | 0 | 3 | 0 | 14 | 0 | True |
| J9 | 18 | 16 | 2 | 0 | 2 | 18 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| K1 | 10 | 0 | 3 | 7 | 2 | 8 | 0 | 0 | 2 | 0 | 8 | 0 | True |
| K2 | 7 | 0 | 2 | 5 | 2 | 0 | 0 | 0 | 7 | 0 | 0 | 0 | False |
| K3 | 8 | 0 | 8 | 0 | 7 | 0 | 0 | 0 | 8 | 0 | 0 | 0 | False |
| K4 | 6 | 0 | 1 | 5 | 1 | 5 | 0 | 0 | 1 | 0 | 5 | 0 | True |
| K5 | 5 | 0 | 5 | 0 | 5 | 1 | 0 | 0 | 4 | 0 | 1 | 0 | False |
| K6 | 7 | 6 | 1 | 0 | 1 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | True |
| L1 | 14 | 7 | 7 | 0 | 7 | 5 | 0 | 0 | 9 | 0 | 5 | 0 | False |
| L2 | 12 | 8 | 4 | 0 | 4 | 10 | 0 | 0 | 2 | 0 | 10 | 0 | True |
| L3 | 6 | 1 | 5 | 0 | 5 | 6 | 0 | 0 | 0 | 0 | 6 | 0 | True |
| T7 | 7 | 0 | 7 | 0 | 6 | 6 | 0 | 0 | 1 | 0 | 5 | 0 | True |
| 合計 | 326 | 102 | 197 | 27 | 113 | 184 | 1 | 1 | 141 | 84 | 141 | 1 | - |

harness 実行の木: dev = `/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/r3/dev` (not a git tree (archive of 075d486 expected for DEVTREE)), 修正後 = `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S` (075d486105caa1c490e5a2a4f61b256921b111d3)
評価文の件数(ファイル別): {'table7.jsonl': 7, 'ja.jsonl': 149, 'ja_r2.jsonl': 43, 'ja_r3.jsonl': 32, 'en.jsonl': 57, 'en_r2.jsonl': 38}

#### カバレッジ(出典: coverage_before.json / coverage_after.json / dropped.tsv / gained.tsv / changed.tsv)

| 指標 | 修正前(dev) | 修正後 |
|---|---|---|
| documents | 1500 | 1500 |
| sentences_approx | 3575 | 3575 |
| supported_sentences | 1365 | 1355 |
| supported_pct | 38.2 | 37.9 |
| only_unsupported_sentences | 1439 | 1431 |
| unread_spans | 772 | 790 |

- supported から外れた文(dropped.tsv): 49 件。分類(coverage_dropped_classified.tsv): {'WAS_WRONG': 49}
- dropped の分類理由欄の語から機械的に分けた内訳(recompute.py の `_kind`。目安であり、分類の正本は各行の理由): {'時間・場所・方角・結果・対象を参与者にした': 8, '先行する語を黙って落とした': 2, '語の途中・括弧・助詞をまたぐ役割句': 19, '役割 0 の空の節': 19, 'そのほか': 1}
- 新たに supported になった文(gained.tsv): 39 件。分類(coverage_gained_classified.tsv): {'CORRECT': 39}
- どちらも supported だが supported 節の構造が変わった文(changed.tsv): 78 件
- 検算: 修正前 1365 - 49 + 39 = 1355 (修正後 1355)

#### 全テスト(出典: before_pytest.txt / after_pytest.txt)

- 作業前: `124 failed, 3684 passed, 28 skipped, 82 xfailed, 68 xpassed, 37 subtests passed in 28.70s`
- 作業後: `123 failed, 4598 passed, 28 skipped, 78 xfailed, 72 xpassed, 37 subtests passed in 25.35s`

#### 凍結ハッシュ(出典: bank_freeze.sha256 = 第 1 ラウンドの 4 ファイル、bank_freeze_r2.sha256 = 第 2 ラウンドの 3 ファイル、bank_freeze_r3.sha256 = 第 3 ラウンドの 2 ファイル)と、いまの評価ファイルの sha256

| ファイル | 凍結時の sha256 | いまの sha256 | 一致 |
|---|---|---|---|
| a3.jsonl | `4e2d728ac017813d8f6f4ef26505d8394e7a7d8f0ad131487e02a3e67c559e58` | `4e2d728ac017813d8f6f4ef26505d8394e7a7d8f0ad131487e02a3e67c559e58` | 一致 |
| a3_r2.jsonl | `2672d566bd650b181617e89b77ce10ce44d3226169ec58589b10f8bb9d070394` | `2672d566bd650b181617e89b77ce10ce44d3226169ec58589b10f8bb9d070394` | 一致 |
| a3_r3.jsonl | `48e86f0a3d9a3b9c8597dd266a992999bc5580cf8cb625e7dad31d44beb29305` | `48e86f0a3d9a3b9c8597dd266a992999bc5580cf8cb625e7dad31d44beb29305` | 一致 |
| en.jsonl | `88fb349633b7d659db156afbf60ca48d4478692b0ad9c5f63f0506bb5bb76049` | `88fb349633b7d659db156afbf60ca48d4478692b0ad9c5f63f0506bb5bb76049` | 一致 |
| en_r2.jsonl | `a3f77278f73f2cc3d8502876baa5392d6e6febdace5ecfcd26c4bc1ae22cd8c8` | `a3f77278f73f2cc3d8502876baa5392d6e6febdace5ecfcd26c4bc1ae22cd8c8` | 一致 |
| ja.jsonl | `d4bff65f30857cee01ffa30a4c402fbcd87725085a213075b2178a51a3065c0e` | `d4bff65f30857cee01ffa30a4c402fbcd87725085a213075b2178a51a3065c0e` | 一致 |
| ja_r2.jsonl | `9df414efd8aa16a94af03cbe15e7e28037771543c4aed2969af7027bf105fea4` | `9df414efd8aa16a94af03cbe15e7e28037771543c4aed2969af7027bf105fea4` | 一致 |
| ja_r3.jsonl | `af6bb55eecf295a921d6e02b54e17e24f91a85eb8f1b60624f9a14cfa2b23f88` | `af6bb55eecf295a921d6e02b54e17e24f91a85eb8f1b60624f9a14cfa2b23f88` | 一致 |
| table7.jsonl | `4f8daab2c15ef1491610ae09326ece5d48d9e7dc18a5be89a39dfe3dbab1fa7f` | `4f8daab2c15ef1491610ae09326ece5d48d9e7dc18a5be89a39dfe3dbab1fa7f` | 一致 |

上申済みの既知の例外(harness.py の ESCALATED、id で列挙): J1-17 (end point of へ is read as recipient by a convention fixed in an existing test; escalated (docs/READING_SOUNDNESS.md))

### A1 誤読 0
修正後は表 7 文・J1〜J9・K1〜K6・L1〜L3・E0〜E6・F0〜F6 の全 326 文で、**上申済みの 1 件(J1-17)を除く誤読が 0、検査誤通過が 0**(`soundness_after.txt`: `TOTAL misread=1 false_pass=1`、`ESCALATED … misread=1 false_pass=1`、`UNESCALATED misread=0 false_pass=0`)。dev は誤読 197(うち上申済みの 1 を除くと 196)・検査誤通過 113(`soundness_dev.txt`: `TOTAL misread=197 false_pass=113`)。第 3 ラウンドの L1〜L3 だけでは、dev の誤読は L1 7/14、L2 4/12、L3 5/6、修正後は 0(第 2 ラウンドの木では、レビューの未公開文で 10 件の誤読が出ていた: `review.r2.md`)。
J1-17(`戦後は若者が都会へ移った。`)は、凍結した正解では誤読になる(正解 `direction=都会`、読解器は `recipient=都会`)。原因は「へ の終点を recipient と呼ぶ」規約を既存テスト `tests/test_semantic_realize.py::test_reader_case_roles_are_preserved`(`マキは研究室へ行った。`→ recipient)が固定していること。チケットが誤読とする「着点を受け手にする」と衝突し、既存テストは変えられない(許可パスの規則)ので、**上申として扱う**: `harness.py` の `ESCALATED` と pytest(`test_the_only_misread_is_the_escalated_exception`)は、この 1 件を id で列挙して例外とし、ほかの誤読は 0 を要求する。判断記録 H1・既知の穴 K1。
レビューの再現文(日本語 20・英語 10。`review_r1_examples_{ja,en}.txt`)を dev と修正後で流した結果: 日本語は supported の節が dev で 17 件、修正後で 8 件(`review_r1_examples_ja_dev.txt` / `_after.txt`)。残り 8 は時刻が `time` になった 4 文、日程変更の結果が `result` になった 3 文、`一部、…` が既存の量化構文(`quantifier`: 一部 を事象の部分量化として読む設計、述語名 `…__quant_partial`)で読まれた 1 文で、どれも誤読ではない(後者は H18)。英語は dev で 10 文すべてが Frame を返し、修正後は 0(`review_r1_examples_en_*.txt`)。

`pytest tests/reading_soundness`(`pytest_reading_soundness.txt`): `913 passed`(評価 326 文×型、門の単体 正例・負例、第 3 ラウンドの `test_gates_round3.py`、検査の変異、凍結ハッシュ、読解器と検査の類一覧の一致)。

### A2 半数以上を正読
J1〜J9 のすべてで 2×正読 ≥ 文数(表の最右列)。第 2 ラウンドの下位形: K1 8/10、K4 5/6、K6 7/7 は半数以上。第 3 ラウンドの下位形: L2 10/12、L3 6/6 は半数以上。**半数に届かない下位形と理由**:
- L1 5/14(受身＋に＋場所・部位・催し・組織にも見える語): 正読は本当に組織が動作主の 5 文(警察・委員会・探検隊・政府・劇団)。非動作主の 7 文(境内・礼拝堂・下部・展示会場・内部・町内会館・校舎裏)は、正解は patient＋place|location だが、場所として読む規則が無いので未対応(K3 と同じ理由、H4)で、誤読ではない(agent の supported 節は 0)。部・課 の 2 文(野球部・経理課)は、組織の証拠が無い(出力部・山間部 と区別できない)ので未対応(H25)。
- K2 0/7(時間でない 副詞可能 の語＋読点): 文頭の談話副詞(結局・実際・以上・普通・基本的に・全部・通常)は役割を持たず、原文の内容語が役割に載らない節になる。副詞を捨てた主節だけを supported にするのは「読み飛ばしを数える」原則に反するので、型付きの `unrepresented source content` で棄権する(誤読ではなく未対応)。
- K3 0/8(受身＋に＋未知の場所名詞): agent にしないことは実装したが、`花壇` のような場所語を `place`/`location` として読む規則は実装していない(場所の判定は閉じた接尾辞・語彙で、未知の場所名は棄権)。検査側の `location` の許可条件(住む・位置する 等)を広げると、quantifier・te_chain・adnominal が recipient/location に依存している既存の読みが動くので、このチケットでは広げなかった(H4)。
- K5 1/5(色・状態の に、動詞が類の外): 塗る・張り替える・塗り直す が「面に塗る」(場所)か「色に塗る」(結果)かは に の語の型で決まり、色語の辞書を持たないので棄権。
英語は A2 を課さない(統制 E0 8/8、F0 6/6 は読む)。

### A3 受身で動作主なしの「誰が」に時間・場所を返さない
`a3_check.py`(`mode="semantic"`): 修正後は 21 文(`a3.jsonl` 8 ＋ `a3_r2.jsonl` 7 ＋ `a3_r3.jsonl` 6。時間 7・場所・催し・部位 14)すべてで `ANSWER` を返さず(`UNKNOWN_NO_EVIDENCE` 12、`UNKNOWN_UNSUPPORTED_EVIDENCE` 9)、禁止語を返したものは 0(`a3_after.txt`, `rows=21 failed=0`, `exit=0`)。dev は 21 文中 13 文(A3-02, A3-03, A3-08, A3R2-01, 02, 03, 05, A3R3-01〜06)で時間語・場所語を `ANSWER`(`a3_dev.txt`, `rows=21 failed=13`, `exit=1`)。第 3 ラウンドの 6 文(`a3_r3.jsonl`)は、末尾が 社・会・部・所 の語(総会・展覧会・製作所・内部)や場所(境内・礼拝堂)が受身の に 句にあるもので、第 2 ラウンドの木で A3 型の誤答(`神社`・`教会`・`外部` を `ANSWER`)が出たのに対応する。第 1 ラウンドの場所の文 4 つは「で」の場所で dev でも失敗しておらず、受身の に の場所を測っていなかった。第 2 ラウンドで受身＋に の場所 4 文を足した(A3R2-01〜04)。

### A4 既存テストの新しい失敗 0
基線(作業前の W): `124 failed, 3684 passed, …`(`before_pytest.txt`)。失敗一覧は `/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_075d486_failures.txt` と一致(`before_vs_w0-1.txt`)。修正後: `123 failed, 4598 passed, 28 skipped, 78 xfailed, 72 xpassed`(`after_pytest.txt`。passed の増分は `tests/reading_soundness` の新規テスト)。失敗 123 件は全部基線の失敗一覧に含まれる(`comm -23` の出力は空)。`tools/w0_1_compare_runs.py`: `G3 NEW_FAIL=0`、FIXED 1(`test_semantic_measure::test_role_only_questions_generalize[…駅B…]`)、`exit=0`(`compare.txt`)。xfail の印は外していない(作業前 82 xfailed / 68 xpassed、修正後 78 / 72)。既存テストの差分は 0(`A0_final.txt`)。

### A5 カバレッジ
supported 文 1365 → 1355(表。`coverage_diff_output.txt`)。supported から外れた 49 文は全件を `coverage_dropped_classified.tsv` に分類した: **`WAS_WRONG` 49、`DROPPED_CORRECT` 0**(`exit=0`)。内訳(理由欄の語から機械的に分けた目安、§6 の表): 役割 0 の空の節 19(うち modality 10)、語の途中・括弧・助詞をまたぐ役割句 19、時間・場所・方角・結果・対象を参与者にした 8、先行する語を黙って落とした 2、ほか 1。新たに supported になった 39 文は `coverage_gained_classified.tsv` で `CORRECT` 39、`MISREAD` 0(`名前（読み、生没年）は、〜` の定義文 37、位置する 1、quote 1)。同じ supported のまま構造が変わった 78 文は `changed.tsv`(未分類。目視した範囲は、括弧内の切断が名前全体になった copula、時間表現が agent/recipient から time になったものが多い)。
第 1 ラウンドから変わった dropped: 新たに落ちた 16 文の内訳は、modality の空の節 10、時間・場所・対象を動作主・受け手にしていた 6(`w1089:108`, `w11:0`, `w209:0`, `w234:76`, `w665:53`, `w709:86`)。第 1 ラウンドで落ちていた `w425:14`(`結成当初は…ユニットであった`)と `w859:0`(`X(…)は、…であった`)は、値の判定が括弧と末尾の「である/であった」を数えなくなったので落ちなくなった(正しく読めていたものを落としていた誤検出を、この修正で解消した)。
分類は自分で原文と前後の節を読んで付けた。判断が割れうるのは、以前の節が文の一部だけを正しく読み、残りを黙って落としていたもの(`w1163:48`, `w855:185`, `w868:69`, `w988:68`, `w623:10`, `w40:0`)と、役割 0 の modality 節 10 文(情報の乏しい断言だったが「正しい構造」ではない、と判断した)。落とした内容が原文にあったので `WAS_WRONG` とした(原則「自動で読み飛ばしたものも数える」)。
第 1 ラウンドの `np_internal` の「読点だけの 2 項は全部棄権」案は、`本科5学科、専攻科2専攻を擁する`(w157)と `…嶋中行雄、エコノミストの嶋中雄二がいる`(w846)を落とした(`DROPPED_CORRECT` になる)ので採らず、人と非人の組み(異種)のときだけ並列にしない規則にした(H21)。

第 3 ラウンドの変更後も、supported 文の集合は 1365 → 1355、dropped 49・gained 39 のまま(第 2 ラウンドの分類ファイルが全件に当たり、`missing=0`、`WAS_WRONG` 49・`DROPPED_CORRECT` 0・gained `CORRECT` 39)。supported 文の集合の差(dropped・gained)は第 2 ラウンドの 49・39 と件数が同じで、分類ファイルは全件に当たった(上の `missing=0`)。supported でない節の理由・役割名が変わった文があるかは数えていない。

### A6 決め打ちでない
`check_hardcode.py`(`a6_hardcode.txt`, `exit=0`): 全評価文(table7・ja・ja_r2・ja_r3・en・en_r2・a3・a3_r2・a3_r3)の固有名詞・数字・英字を含む語、英語の文頭以外の大文字語が追加行に現れない(0 件)。**英語は全内容語(3 文字以上の小文字語)を照合して一覧に出す**ようにした(R8。一覧は同ファイル。各語がどの追加行に出たかを併記)。出た語の説明: 助動詞・量化詞・焦点語・接続詞・数詞・時間語など**閉じた機能語類の定義**(`_MODALS`, `_QUANT`, `_FOCUS`, `_SUBORD`, `_NUMBER_WORDS`, `_TIME`)に含まれるもの、比較の形容詞語幹の一般語彙(`_ADJ_STEMS`。fast/long/new/old/early/late など。基準は直前のコメント: 1〜2 音節で比較変化する一般の形容詞)、補文・小節・変化の動詞の類(`_COMPLEMENT_MATRIX`, `_SMALL_CLAUSE_MATRIX`, `_RESULT_CHANGE_VERBS`)、そのほかはコメントと docstring の説明語(book, report, engineer, arrived …。説明用の語で、条件には使っていない)。評価文の固有の語(人名・日付・製品名)は条件に現れない。`git diff 075d486 -- verantyx/ | grep '^+' | grep -n -w -E 'crowded|quickly|red'` は 0 行、表 7 文の語の grep も 0 行(`a6_grep.txt`)。日本語の普通名詞・動詞の一致一覧も同ファイル: 述語・名詞の「類」を基準で定義した一覧(受け手の動詞、結果を取る変化・日程変更の動詞、移動・設置の動詞、包含の動詞、人・動物を表す名詞、場所の接尾辞、時間の形態素・直示語・暦の語、助数詞)で、評価文から作っていない。バンクの J4 には類の外の動詞(起こす・編み上げる・仕上げる)を 3 つ入れており、K5 は類の外の動詞(塗る・張り替える)を使う。

### A7 文書の数値の再計算
`recompute.py` が `artifacts/w1-a/` から §6 の表を出す(`recompute.md`)。文書のその他の数値はファイル名つきで出典を示した。

## 7. 判断記録

- **H1 J1-17 の正解を凍結時に戻し、上申とした(第 2 ラウンド、R9)**: 第 1 ラウンドは、凍結後に `戦後は若者が都会へ移った。` の正解へ alternative(`recipient=都会`)を足し、誤読 0 にしていた。これは「判定を甘くする alternatives を後から足さない」に反するので取り消し、凍結時のハッシュに戻した。既存テストの規約と衝突する 1 件は、ハーネスと pytest で id 指定の既知の例外にし、ほかは誤読 0 を要求する。**監督に上申**: 「へ・に の終点を recipient と呼ぶ」規約(K1)を、このチケットの誤読基準とどう折り合わせるか。
- **H2 frames.py を触らない(D1)**: 時間句・受け手・動作主の型は読解側で検め、検査側は自前で検める。
- **H3 recipient は「どれでも落とす」ではなく類で決める**: 受け手の動詞・人名以外の に 句をすべて曖昧にすると、実在の文(置く・分ける・恩恵の あげる・人を表す語)で正しい答えが落ちた。そこで類を足し、を の目的語があるものに限って落とすようにした。第 2 ラウンドで、この条件を frame 分岐から **すべての規則の節に掛かる門と検査の汎用部**へ移した(R5)。移したところ `塗る` が `_PLACEMENT_PREDICATES`(置く類の終点は recipient のまま残す規約)に入っていて `彼が部屋を青に塗った。` の `recipient=青` を通したので、`塗る` を置く類から外した。
- **H4 locative に(住む・位置する・ある・属する)と placement の終点は recipient のまま**: 試作で location に直したところ、quantifier・te_chain・adnominal が recipient を前提にしていて、「…にある」型の文が大量に落ちた。直さず、既存の読みを保った(K1)。受身＋に の場所を location として読む規則も、同じ理由で入れていない(K3)。
- **H5 diathesis の使役は frame が recipient を残したときだけ受ける**(K2 の原因)。
- **H6 np_internal の読点並列**: 時間・関係の語(副詞可能)が読点の前に立つと並列にしない。読点だけの 2 項の対を全部棄権にする案は、実在の並列(本科…、専攻科…／嶋中行雄、嶋中雄二)を落とした(A5 の `DROPPED_CORRECT` になった)ので採らず、片方が人でもう片方が人でない対だけを並列にしない(H21)。
- **H7 diathesis の先行語**・**H8 coordinated 伝播**・**H10 gold_double_neg は変更しない**・**H12 指示語(D7)**: 第 1 ラウンドのとおり。
- **H9 modality**: 第 1 ラウンドは変更しないとしたが、第 2 ラウンドで「役割 0 の節は supported にしない」(型の門)を足したので、modality が参与者を黙って落とした空の節 10 文は未対応になった(A5)。
- **H11 比較**: copula が値に より または 述語句の格助詞(と を含む)を持つと unsupported にし、比較構文が読む。`comparison._dimension_bounds` は dimension が名詞でないとき形容詞自身を dimension にする(`ずっと長い` の `ずっと` を dimension にしていた)。
- **H13 英語(第 2 ラウンドで改訂)**: 否定側の印の一覧だけでなく、**読めた Frame の肯定側の検め**を足した。その代わり、前置詞句の付加語(`at noon` `in the park`)など Frame が持たない語が文に残る文は棄権になる(以前は付加語を黙って落として読んでいた)。未知の動詞活用(`broke` のように不規則動詞の表にない語)も棄権になる(動詞として確かめられない語は読まない)。
- **H14 index search**: `artifacts/w1-a/index_search.txt`(第 1 ラウンド)。既存物を作り直していない。
- **H15 補助測定: 単位受入デモ**(受入基準ではない。`unit_demos.txt` に dev と修正後の末尾 12 行): `gold_caus_pass`・`gold_double_neg`・`gold_comparison` は dev・修正後とも `DEMO OK`。**`gold_passive` は修正後に `DEMO FAIL`**(`assert on["correct"] > off["correct"]`: seed 7 で on 6 / off 6。dev は 8 / 7)。原因: `ジャガイモの畝は、土寄せの時期に農家によって整えられた。` は dev では frame が `土寄せの時期に` を曖昧にして unsupported になり、gold_passive が修飾語(ジャガイモの)と patient(畝)に分けて読んでいた。修正後は `…の時期` を時間と読めるので frame が自力で supported になり(`patient=ジャガイモの畝`, `time=土寄せの時期`)、構文が走らず、質問側の「畝」と patient の語が一致せず棄権になる。読みは正しいが、構文が与えていた細かい分け方が無くなった。`gold_scramble` は dev で `DEMO OK`(wrong_overlap は on 5 / off 5)、修正後は `DEMO FAIL: wrong_overlap rose on seed 101`(on 8 / off 6。第 1 ラウンドは 7 / 5)。`gold_probe.py wdw --phenomenon 語順 --seed 101` の on と off の差を見ると、増えた例は `古い路線図を、駅の案内係が…取り替えた。`(答え `古い路線図`、gold は `古い路線図を。`)のような gold の書式(助詞つき)との部分一致で、確認できた範囲では答えの語は合っている(差のうち 1 件だけを確認した。残りは未確認)。デモの判定は変えていない。統合時に確認が要る。
- **H16 質問応答への影響(補助測定)**: `qa_probe_summary.txt`。使役を問う質問が答えなくなる(K2)のほか、時間・受け手・動作主の門で棄権が増えた。correct でなくなった問は seed 7 で 17、seed 101 で 13(うち使役系 13 と 7)。correct の件数は seed 7 で 121→108、seed 101 で 90→79。いくつかは、読解が正しくなった結果、構文(gold_passive など)が走らなくなって質問側が期待する構造(`ジャガイモの畝` を `畝` と修飾語に分ける形)が変わったもの。質問側(`semantic_wh.py`)は許可パス外なので変更していない。
- **H17 時間型の基準(R2、指示書手順 6 の訂正)**: 副詞可能 を基準にするのをやめ、時を表す形態素・閉じた直示語・暦の語・出来事名詞＋前/後/中、数字の時刻・期間(R1)を、読解と検査で別々に実装した。許容する語は基準(§4.1)で決め、評価文の語を足していない。
- **H18 一部、(R2 の再現文)**: `一部、兄が駅で傘を買った。` は、既存の量化構文(`quantifier`)が 一部 を「事象の部分量化」(述語名 `買う__quant_partial`、役割 `quantifier_partial__event=一部`)として読み、supported になる。`time=一部` の節は出ない(受入の確かめ方のとおり)。構文の設計(wave4 の単位)であり、時間でない語を時間にした誤読ではないと判断して変更していない。ただし「一部、」を文頭の副詞(「一部の例外を除き」ではなく「部分的に」)と読むかは設計判断で、判断が割れうる。
- **H19 受身の動作主(R3)**: 肯定側の型(動作主になれる)に切り替えた。人・組織・動物の語彙は閉じた類で、未登録の語・場所でもある語(学校・会社・役所)は棄権になる。**場所の判定が閉じた接尾辞で、タガーが地名ではない語を 固有名詞-人名 と付ける場合**(壇上 を人名と付ける)は agent として残る。
- **H20 から の受身の動作主**: 時間だけ・場所だけの語は agent にせず `source` と読む。人・組織・場所でもある語(役所・研究所・図書館)は従来どおり agent。
- **H21 np_internal の異種の対**: `_is_person_item` は `frames.is_role`・人名の接尾辞・代名詞・人名の固有名詞で人を判定する(読解と検査が同じ判定を共有する。独立の別実装ではない)。
- **H22 英語の比較の形容詞語幹**: 評価文由来の語(crowded, red)と 2 語組の条件を削除し、一般の語彙(1〜2 音節で比較変化する形容詞)から作り直した(R8)。語幹の一覧に評価文の語(fast, tall, new, old, large …)が含まれるのは、一般の語彙だから。
- **H23 バンクの最初の実行で見つかった誤読 2 件**: 新しいバンク(ja_r2・en_r2)を凍結後に最初に流した結果、K2-04(`普通、母が…`)と F5-06(`Nearly fifty guests …`)が誤読だった(`soundness_after_r2_first_run_before_np_en_fix.json`)。正解は直さず、規則を直した(np_internal: 形状詞可能と人／非人の対、英語: 数詞 thirty〜ninety・近似語)。
- **H24 O1〜O4**: O1 は実装(harness)。O2 は `np_internal._license_adverbial` のタガー生成を共有のタガーに変更。O3(J3-10〜12 の正解を構造にする)は凍結のため変更していない(見送り)。O4(changed.tsv の分類)は実施していない(78 件)。

- **H25 人・組織の判定を末尾の文字から正の証拠へ(第 3 ラウンド M1)**: `_PERSON_SUFFIXES`(社・会・部・校・院・館・園・所・局・署・省・庁・団・隊 …)の `endswith` をやめ、§4.1 の (a)〜(f) の正の証拠だけを人・組織とした。理由: 末尾が同じ語が組織・催し・場所・部位・領域・機械の部分を区別なく含み(神社・教会・茶会・大会・外部・胸部・一部・高校・山間部・出力部)、同じ一覧を読解と検査が写していたので両方を同時にすり抜けた。**代償**: 野球部・営業部・経理課 のような実在の組織も、固有名詞が主辞でなければ組織とみなさず未対応になる(`新入生が野球部に勧誘された。` は dev では正読、いまは未対応)。出力部(機械の部分)・山間部(領域)と区別する根拠がタガーに無い。A5 では、この代償で落ちたコーパスの文は 0(`coverage_dropped_classified.tsv` は変わらず 49 件が `WAS_WRONG`、`DROPPED_CORRECT` 0)。一方、評価の外の実在の文では落ちうる(K13)。集合行為者の語(政府・軍・協会・機関・組合・劇団・財団・役所・役場)は閉じた語彙として `_PERSON_NOUNS` に足した(`役所` は第 2 ラウンドのテスト `test_gate_person_or_organisation_with_kara_keeps_the_agent_of_a_passive` が agent を要求していた。テストは変えていない)。主辞の前にある固有名詞では人としない(`太郎の鞄`・`伏見稲荷神社`・`山田橋`)ことも、同じ変更で入れた(以前は句全体から固有名詞を探していた)。サ変可能(動作名詞)の末尾の長・係・達・手 は人としない(成長・関係・配達)。
- **H26 変化の動詞の人の に 句(第 3 ラウンド M2)**: レビューの合格条件(人は result にしない。受け手の根拠が無ければ unsupported)に従い、受益者を `recipient` と読む案は、恩恵の補助動詞がある場合(あげる・やる)だけにした。plain の `母が息子に作文を直した。` は dev では `recipient=息子`(正解と一致)で正読だったが、いまは未対応(L2-05・L2-06)。語順(に 句が目的語より前)を語彙に頼らない根拠として足したので、`先生が児童に絵本を編集した。`(児童 は人の語彙に無い)も `result` にならない。目的語が人(彼を部長に)のとき、および地位を授ける動詞(`_APPOINTMENT_PREDICATES`。目的語が人であることを動詞が選択するので、`候補を議長に選出` のように目的語の語が人の語彙に無くても通る)では `result`。受身(`彼が部長に選ばれた`)は主語を目的語の代わりに使う。検査側は自前の `_VT_APPOINTMENT_VERBS` と語順・人の判定で同じ型を拒否する(`test_m2_class_lists_agree` が一覧の一致を検める)。
- **H27 比較の より(第 3 ラウンド M3)**: 『前のより軽い』のように standard が準体の の で終わる句(`前の`)になる。これは比較構文の既存の読みで、評価バンクの正解(L3)も `standard=前の` と書いた(の を含む句が省略された名詞句の全体だと判断。判断が割れうる)。`ほど` の比較は、copula の値に入る形(`昨日のほど辛くない`)でも、比較構文の既存の読み(`ほど…ない`)に任せ、変更していない。
- **H28 検査の独立性(レビューの申し送り 1)**: 検査(`_vt_is_addressee`・`_VT_APPOINTMENT_VERBS`・`_vt_check_roles` の result 分岐)は読解を import せず、自前のトークン化と自前の関数で書いたが、**判定の基準(正の証拠の一覧、サ変可能の除外)は同じ内容を二重に書いている**。「別の関数」であって「別の根拠」ではない。違いは、検査が読解の出力(`unsupported` の印)を信用せず、役割の語の型を原文から再判定する点と、語順(`result` が目的語より前)のように、人の語彙に頼らない根拠を検査側にも置いた点。`test_m1_checker_refuses_the_same_clause_with_the_unsupported_mark_removed` などの変異テストは、読解が止めた節の印を外しても検査が拒否することを示す。人の語彙そのものが欠ける(児童・園児・見習い など)穴は、読解も検査も同じように通す(K13)。
- **H29 凍結バンクの新規 3 型(M4)**: `ja_r3.jsonl`(L1 14・L2 12・L3 6)・`a3_r3.jsonl`(6)。レビューの要求(場所・催し・部位・組織にも見える語の受身 8 以上のうち 3 以上は本当に組織が動作主、変化の動詞＋人 6 以上と役職の対照 3 以上、Nのより Adj 5 以上、A3 4 以上)を満たす件数(`test_bank_is_large_enough`)。正解は正しい構造で書き、unsupported を正解にしていない。正読が半数に届かない下位形(L1)の理由は §6 A2。
- **H30 検査の変異テスト(レビューの確認点 6)**: 第 3 ラウンドの追加分は `test_gates_round3.py`: (1) 読解が止めた節の unsupported を外した節を検査が拒否する(M1: 古寺・西部・音楽会、M3: 兄のより・隣町のより・君のより)、(2) 受益者・人の に 句を `result` に改名した節を検査が拒否する(M2)、(3) 目的語より前の に 句を `result` に改名した節を検査が拒否する(M2 の語順)。
- **H31 補助測定を再実行していない**: 単位受入デモ(`unit_demos.txt`)と質問応答への影響(`qa_probe_*`)は第 2 ラウンドの測定のまま。第 3 ラウンドの変更後は測り直していない(受入基準ではない)。H15・H16 の数値は第 2 ラウンドの木のもの。

## 8. 既知の穴(隠さない)

- **K1 項目の呼び名(上申)**: 「移動・設置・場所の動詞の終点」(へ・に)を recipient と呼ぶ規約。住む・位置する・ある・属する・出場する(を の目的語の無い動詞の に 補語)や、へ の終点、置く類の終点も recipient のまま。J1-17 が凍結した正解で誤読になる(§6 A1)。既存テスト(`test_reader_case_roles_are_preserved`)と構文(quantifier・adnominal・te_chain)がその呼び名に依存しており、このチケットでは変えていない。
- **K2 使役を問う質問が答えなくなった**: 文書側が diathesis の `causer/causee/patient` になり、質問側(`semantic_wh.py` など許可パス外)が使役を知らず棄権する(`qa_probe_summary.txt`: 使役系 13 問・7 問)。直すには質問側が causer/causee を読む必要がある(別チケット)。
- **K3 「人」「動作主」の判定は閉じた類**: 人・組織・動物は語彙・接尾辞・親族語で判定する。未登録の語(例: タガーが固有名詞・普通名詞と付けた新しい役職名)や、場所でもある語(学校・会社)は受身の agent にならず、棄権になる(誤読ではなく未対応)。タガーの誤タグ(壇上 を人名)は拾えない。
- **K4 受身＋に の場所**: agent にはしないが、場所として読む規則が無いので未対応になる(K3 バンク 0/8)。
- **K5 色・状態の に**: 変化の類の外の動詞(塗る・張り替える)で に の語が色・状態でも、読めず棄権(K5 バンク 1/5)。
- **K6 読み飛ばし**: diathesis が文頭の「名詞だけ＋の」を読み飛ばす既存の設計は型付きの理由を足していない。modality の空の節は未対応にした(H9)。`一方、`・`また、` など接続の語を黙って落とした節は supported のまま。
- **K7 英語**: 未知の動詞活用・前置詞句の付加語・副詞の吸収などは棄権になる(H13)。量化詞・使役・比較・従属節・補文動詞の判定は閉じた語彙と語形の近似で、未知の言い回しは読んでしまうことがある。
- **K8 比較と二重否定の正読の範囲**: 比較の正読は比較構文の閉じた形容詞語彙に限る。過去形の二重否定は未対応。
- **K9 値の先頭の読点**: `X（読み）は、Y` の定義文は value が `、Y` で始まる(既存の表現)。
- **K10 一部(H18)**: `一部、…` を量化構文が supported にする。
- **K11 コミット・統合**: 差分は未コミット。`np_internal.py`・`time_expr.py`・`diathesis.py`・`comparison.py` は他チケットが触る可能性がある(統合時に確認)。
- **K12 changed.tsv の 78 件は未分類**(O4)。目視した範囲では、修正後も誤った節が残る例(`四六のガマ（しろくのガマ）とは…` の property の entity/attribute の分け方、`日本の農道一覧（…）は…` の entity=日本)がある。
- **K13 人の語彙の穴(第 3 ラウンド)**: 人・組織の判定は正の証拠の一覧(閉じた語彙・親族語・役職・人名・接尾辞)。一覧に無い人を表す語(児童・園児・見習い・新入り・末っ子)は人と判定されない。受身の に 句では agent にならず(未対応で安全)、変化の動詞の に 句では語順(目的語より後)と人の語彙のどちらかの証拠が要るので、`先生が絵本を児童に編集した。`(目的語の後ろ)のように語彙に無い人が目的語の後ろにあるときは `result` になりうる。逆に、実在の組織で固有名詞が主辞でないもの(野球部・営業部・経理課・自治会・商社)は agent にならず未対応(§H25)。
- **K14 末尾の文字が人の接尾辞と同じ語(第 3 ラウンド)**: `frames.is_role`(許可パス外)の末尾の人接尾(長・手・人・生 …)に当たる語は、サ変可能でなければ人とみなす。`身長`・`全長`(長)、`個人`(人)が agent として残る(`全長に印が付けられた。`→ agent=全長、`個人に責任が負わされた。`→ agent=個人。後者は 負わす の類=課す・負わす が伝達・授受の動詞に入っていないことも原因)。`r3_probe_ja_after.txt` に 3 件が残っている(誤読で、未修正)。
- **K15 受身の に が組織の 選ぶ(第 3 ラウンド)**: `自治会に新しい役員が選ばれた。` は `result=自治会`(supported)。「…として選ばれた」か「…に選ばれた(動作主)」か原文で決まらない曖昧な文で、地位を表す に が `result` になる読みを許した。未修正。
