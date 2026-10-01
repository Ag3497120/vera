# 実測: 選択済み核の facet 被覆による棄権

主判定: **不採択**。
事前登録の閾値 1/20 を一度だけ測定した。結果を見た後の閾値変更・再測定は行っていない。
実装は実験ディレクトリの `adjudicate.py` と `run_specificity.py` にあり、本番への配線は行っていない。

## 実行の同定と凍結

| 項目 | 実測・保存値 |
| --- | --- |
| 実行コマンド | python3.11 experiments/specificity_abstention/run_specificity.py |
| 開始 UTC | 2026-09-05T07:07:12.647677+00:00 |
| 終了 UTC | 2026-09-05T07:08:13.229765+00:00 |
| 経過秒 | 60.582 |
| HEAD | 46e37f1b5faaefbf2cf4e92b8a0dcb246e6c79be |
| seed | 31415 |
| 抽出核数 | 300 |
| 評価問数 | 300 |
| 生成不能除外 | 0 |
| ja 核数 | 89273 |
| DB | /Users/motonishikoudai/Projects/vera-corpus/build/vera.db |
| DB SHA-256 前 | ba64b4eb2e7af603c9a93f94edc2e5d4250af79e2af7802dcda4dc480952bb5e |
| DB SHA-256 後 | ba64b4eb2e7af603c9a93f94edc2e5d4250af79e2af7802dcda4dc480952bb5e |
| PREREG SHA-256 | 02f8a5ca5f7e02774bacf9529475d713d04315a94207a16185182eb8daae289c |

seed は登録前に experiments と指定 memory の py/md/json を検索して未出現を確認した。
未使用 seed であることと、過去の標本との核の完全非重複とは区別する。後者は主張しない。
利用した verantyx 全 Python ソースと治具・裁定の SHA-256 は `results.json:source_sha256` に保存した。
測定後に照合した 192 ソースのハッシュと PREREG はすべて不変。照合結果は `source_integrity.json` に保存。

## 四腕の成績（数値は results.json の実測のみ）

| 腕 | 問数 | 正 | 誤 | 棄 | 到達 | junk先頭 | junk含有 | 空候補 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 300 | 14 | 236 | 50 | 284 | 57 | 142 | 1 |
| specificity | 300 | 10 | 5 | 285 | 284 | 57 | 142 | 1 |
| no_junk | 300 | 34 | 229 | 37 | 280 | 0 | 0 | 2 |
| no_junk_specificity | 300 | 32 | 11 | 257 | 280 | 0 | 0 | 2 |

baseline/specificity は現行候補、no_junk/no_junk_specificity は取得後に junk を除いた候補を使う。
補助腕は残枠を補充せず、store の全入口を塞いだ WIRE3 の再現とは扱わない。
全腕は同じ store の candidates_appended → score_facets → shell → run_consensus を通る。
同じ候補条件内では合意結果を一度だけ計算し、裁定の有無を比較する。
空候補を除外した過去の治具と異なり、今回は登録どおり空候補も UNKNOWN_NO_EVIDENCE として全腕の分母に残した。

## 事前登録の主判定線

| 条件 | 判定 | 実測比較・検査 |
| --- | --- | --- |
| WRONG_DOWN | PASS | 5 < 236 |
| REFUSAL_NOT_WORSE | PASS | 285 ≥ 50 |
| CORRECT_NOT_WORSE | FAIL | 10 ≥ 14 |
| PATH_MATCH | PASS | 対応する候補・配置同一、元合意不変、非ANSWER保持、DBハッシュ一致 |

JUNK_TOP1_ZERO は登録どおり採否に用いていない。
保存済みの 600 対を `verify_results.py` で独立に再検査し、Fraction による厳密な閾値比較・候補と配置の一致・非ANSWER保持はすべて PASS。探針の再実行ではない。
REFUSAL_NOT_WORSE は降格のみの規則では構造上満たせる。これだけで junk の棄権を肩代わりできたとは結論しない。

## 補助腕の同じ不等式（baseline 比、主判定に代用しない）

| 条件 | 参考判定 | 比較 |
| --- | --- | --- |
| WRONG_DOWN | PASS | 11 < 236 |
| REFUSAL_NOT_WORSE | PASS | 257 ≥ 50 |
| CORRECT_NOT_WORSE | PASS | 32 ≥ 14 |

## 判定型の全分布

| 腕 | verdict | 件数 |
| --- | --- | --- |
| baseline | AMBIGUOUS | 7 |
| baseline | ANSWER | 250 |
| baseline | UNKNOWN_INSUFFICIENT_EVIDENCE | 1 |
| baseline | UNKNOWN_NO_EVIDENCE | 42 |
| specificity | AMBIGUOUS | 7 |
| specificity | ANSWER | 15 |
| specificity | UNKNOWN_INSUFFICIENT_EVIDENCE | 236 |
| specificity | UNKNOWN_NO_EVIDENCE | 42 |
| no_junk | AMBIGUOUS | 14 |
| no_junk | ANSWER | 263 |
| no_junk | UNKNOWN_INSUFFICIENT_EVIDENCE | 1 |
| no_junk | UNKNOWN_NO_EVIDENCE | 22 |
| no_junk_specificity | AMBIGUOUS | 14 |
| no_junk_specificity | ANSWER | 43 |
| no_junk_specificity | UNKNOWN_INSUFFICIENT_EVIDENCE | 221 |
| no_junk_specificity | UNKNOWN_NO_EVIDENCE | 22 |

## 分類遷移の全分布

| 比較 | 遷移 | 件数 |
| --- | --- | --- |
| baseline -> specificity | correct -> correct | 10 |
| baseline -> specificity | correct -> refusal | 4 |
| baseline -> specificity | refusal -> refusal | 50 |
| baseline -> specificity | wrong -> refusal | 231 |
| baseline -> specificity | wrong -> wrong | 5 |
| baseline -> no_junk | correct -> correct | 12 |
| baseline -> no_junk | correct -> refusal | 1 |
| baseline -> no_junk | correct -> wrong | 1 |
| baseline -> no_junk | refusal -> correct | 8 |
| baseline -> no_junk | refusal -> refusal | 28 |
| baseline -> no_junk | refusal -> wrong | 14 |
| baseline -> no_junk | wrong -> correct | 14 |
| baseline -> no_junk | wrong -> refusal | 8 |
| baseline -> no_junk | wrong -> wrong | 214 |
| no_junk -> no_junk_specificity | correct -> correct | 32 |
| no_junk -> no_junk_specificity | correct -> refusal | 2 |
| no_junk -> no_junk_specificity | refusal -> refusal | 37 |
| no_junk -> no_junk_specificity | wrong -> refusal | 218 |
| no_junk -> no_junk_specificity | wrong -> wrong | 11 |
| baseline -> no_junk_specificity | correct -> correct | 10 |
| baseline -> no_junk_specificity | correct -> refusal | 4 |
| baseline -> no_junk_specificity | refusal -> correct | 8 |
| baseline -> no_junk_specificity | refusal -> refusal | 40 |
| baseline -> no_junk_specificity | refusal -> wrong | 2 |
| baseline -> no_junk_specificity | wrong -> correct | 14 |
| baseline -> no_junk_specificity | wrong -> refusal | 213 |
| baseline -> no_junk_specificity | wrong -> wrong | 9 |

## 正答を失った全件（両候補条件）

| id | 比較 | gold | 問い | 被覆 | 裁定後 |
| --- | --- | --- | --- | --- | --- |
| 54 | baseline → specificity | 言語学者 | ヤーコブソン ムカジョフスキー ヨセフ | 3/73; 覆った語=ムカジョフスキー,ヤーコブソン,ヨセフ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |
| 100 | baseline → specificity | 論 | 中核 傾向 代表 | 3/84; 覆った語=中核,代表,傾向 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |
| 138 | baseline → specificity | 数 | qubit octet rule | 3/723; 覆った語=octet,qubit,rule | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |
| 271 | baseline → specificity | 自民党 | 到底 先立 出演被害防止 | 3/83; 覆った語=先立,出演被害防止,到底 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |
| 54 | no_junk → no_junk_specificity | 言語学者 | ヤーコブソン ムカジョフスキー ヨセフ | 3/73; 覆った語=ムカジョフスキー,ヤーコブソン,ヨセフ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |
| 271 | no_junk → no_junk_specificity | 自民党 | 到底 先立 出演被害防止 | 3/83; 覆った語=先立,出演被害防止,到底 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — |

上表は 6 件の腕内遷移。複数腕に同じ問いが出る場合も省略しない。

## 誤答を棄権へ下げた全件（両候補条件）

| id | 比較 | gold | 問い | 棄権に下げた誤答核 | 被覆 |
| --- | --- | --- | --- | --- | --- |
| 2 | baseline → specificity | 温泉法第十六条 | 許可 法人 前条第一項 | 許可 | 0/164; 覆った語=∅ |
| 3 | baseline → specificity | ジアダ | シュタイナー シャーロック シャングリラ | ゴリー | 1/33; 覆った語=シャーロック |
| 4 | baseline → specificity | 職業安定法 | 昭和23年3月2日基発381号 広 排除 | 広 | 0/505; 覆った語=∅ |
| 5 | baseline → specificity | 第18条 | 任命 二級 夜勤手当 | 九 | 2/2860; 覆った語=任命,夜勤手当 |
| 7 | baseline → specificity | 先住部族 | 紀元前2千年紀後半 長方形頭 頭 | 頭 | 0/40; 覆った語=∅ |
| 8 | baseline → specificity | 金融商品取引法第六十条 | 第五十八条 規定 売買 | 四 | 3/6394; 覆った語=売買,第五十八条,規定 |
| 9 | baseline → specificity | 本居宣長 | 指摘 壬申 国学 | 指摘 | 0/47; 覆った語=∅ |
| 10 | baseline → specificity | 民事調停法第二十条 | 職権 管轄裁判所 調停 | 職権 | 0/36; 覆った語=∅ |
| 12 | baseline → specificity | 牧野法施行規則第十八条 | 書類 添附 届出 | 書類 | 0/33; 覆った語=∅ |
| 13 | baseline → specificity | 症例報告 | 哲学的思考実験 中 実証的 | 中 | 0/498; 覆った語=∅ |
| 14 | baseline → specificity | 次男 | 出 報告 圧 | 出 | 0/106; 覆った語=∅ |
| 15 | baseline → specificity | テンペレートファージ | 可能性 拡散 得 | 可能性 | 0/710; 覆った語=∅ |
| 16 | baseline → specificity | 鉱業法施行規則第十五条 | 期日 競願 準用 | 準用 | 0/61; 覆った語=∅ |
| 17 | baseline → specificity | 商法第六百八十五条 | 従物 書式 推定等 | 書式 | 0/50; 覆った語=∅ |
| 19 | baseline → specificity | 関連企業 | インド アイグループ software | インド | 0/203; 覆った語=∅ |
| 20 | baseline → specificity | 保安基準第二十二条 | 道路運送車両 着席 空間 | 空間 | 0/112; 覆った語=∅ |
| 21 | baseline → specificity | 文化財保護法第百三十五条 | 選定 重要文化的景観 解除 | 選定 | 0/12; 覆った語=∅ |
| 22 | baseline → specificity | p.w.atkins | 東京化学同人 元裕 物理化学 | 物理化学 | 0/19; 覆った語=∅ |
| 23 | baseline → specificity | 宮本隆司 | 撮影 建設過程 過程 | 当初 | 2/953; 覆った語=撮影,過程 |
| 24 | baseline → specificity | 第三回四分利付英貨公債発行規程第八条 | 日本国ノ 関スル 間ニ | 二 | 1/14025; 覆った語=関スル |
| 25 | baseline → specificity | 立方体 | 投影図 座標軸 単面投影 | 投影図 | 0/18; 覆った語=∅ |
| 26 | baseline → specificity | 鉱山保安法第二条 | 鉱業権者 法律 租鉱権者 | 法律 | 0/1374; 覆った語=∅ |
| 27 | baseline → specificity | 無尽業法施行細則第十四条 | 効力ヲ 認可ハ 其ノ | 二 | 2/14025; 覆った語=其ノ,効力ヲ |
| 30 | baseline → specificity | 浅田 | プロフィギュアスケーター バカ 日放送 | バラエティ | 2/806; 覆った語=バカ,日放送 |
| 32 | baseline → specificity | 外務公務員法施行令第一条 | 申出 規定 第八条第一項 | 十七 | 3/1460; 覆った語=申出,第八条第一項,規定 |
| 33 | baseline → specificity | 道路運送法施行規則附則第七条 | 経過措置 登録事項 規定 | 四 | 3/6394; 覆った語=登録事項,経過措置,規定 |
| 34 | baseline → specificity | 連帯債務 | 支払い 求償 d | 支払い | 0/21; 覆った語=∅ |
| 35 | baseline → specificity | 多倍数種 | 既知 植物属 約半数 | 既知 | 0/8; 覆った語=∅ |
| 37 | baseline → specificity | 商法第五百七十七条 | 種類 荷送人 運送 | 種類 | 0/300; 覆った語=∅ |
| 39 | baseline → specificity | 法的規制 | 軽 枠組 売 | 軽 | 0/13; 覆った語=∅ |
| 40 | baseline → specificity | 建築物な | 適用 局部等電位化 機器 | 基準 | 2/362; 覆った語=機器,適用 |
| 41 | baseline → specificity | 宝月誠 | 思想 社会的背景 初期シカゴ | 思想 | 0/264; 覆った語=∅ |
| 44 | baseline → specificity | 恩給法附則第百六十一条 | 処分庁 行政庁 施行日前 | 処分庁 | 1/87; 覆った語=行政庁 |
| 47 | baseline → specificity | 通説 | 1行 ドイツ 不可罰 | ドイツ | 0/550; 覆った語=∅ |
| 48 | baseline → specificity | 家畜保健衛生所法附則第百六十一条 | 行政庁 処分 経過措置 | 行政庁 | 1/249; 覆った語=処分 |
| 49 | baseline → specificity | 両親 | 以来 人工呼吸器 ドイツ | 以来 | 0/12; 覆った語=∅ |
| 50 | baseline → specificity | psycho-pass | 名前 タイトル sinners | 名前 | 1/405; 覆った語=タイトル |
| 51 | baseline → specificity | 医学教育 | 場 国 制度 | 場 | 0/223; 覆った語=∅ |
| 53 | baseline → specificity | 壁新聞 | ニュース 総合博物館 寄贈 | ニュース | 0/86; 覆った語=∅ |
| 55 | baseline → specificity | 海上運送法第二十九条 | 締結 変更 国土交通大臣 | 五十 | 3/158; 覆った語=国土交通大臣,変更,締結 |
| 56 | baseline → specificity | 京都府特殊物件処理委員会 | 応急利用等 措置 政府 | 政府 | 1/1156; 覆った語=措置 |
| 57 | baseline → specificity | 社会福祉法第四十一条 | 終了 定款 最終 | 八 | 3/3276; 覆った語=定款,最終,終了 |
| 58 | baseline → specificity | 土地家屋調査士法第十四条 | 調査士 登録 所属 | 登録 | 0/57; 覆った語=∅ |
| 59 | baseline → specificity | 液体ヘリウム | クエンチ t 不要 | クエンチ | 0/18; 覆った語=∅ |
| 60 | baseline → specificity | 人為 | 語 自然 加 | 語 | 1/1089; 覆った語=加 |
| 61 | baseline → specificity | 保安法第五十条 | 経過 政令 更新 | 経過 | 1/61; 覆った語=更新 |
| 64 | baseline → specificity | 無線局免許手続規則第二十七条 | 記録 別表第十号 許可記録 | 記録 | 0/261; 覆った語=∅ |
| 66 | baseline → specificity | 16組 | 放送 披露 本番 | 放送 | 0/543; 覆った語=∅ |
| 68 | baseline → specificity | 完了後 | ポルトガル 言語純化運動 教徒 | 単語 | 2/309; 覆った語=ポルトガル,教徒 |
| 69 | baseline → specificity | コーンフォード | 哲学史観 理性化 生 | 生 | 0/120; 覆った語=∅ |
| 74 | baseline → specificity | 首脳 | フランス 冬季大会 抗議 | フランス | 0/332; 覆った語=∅ |
| 75 | baseline → specificity | 理論生物学 | 行動 定量的 形質 | 行動 | 1/292; 覆った語=形質 |
| 76 | baseline → specificity | chemrxiv | 化学関連分野 投稿 未発表プレプリント | 投稿 | 0/37; 覆った語=∅ |
| 77 | baseline → specificity | 高橋 | 法律学小辞典 光男 小早川 | 小早川 | 0/38; 覆った語=∅ |
| 78 | baseline → specificity | 哲学的考察 | 問題 妊娠中絶 影響 | 問題 | 1/1270; 覆った語=影響 |
| 79 | baseline → specificity | 鉱業登録令第五十条 | 試掘権 登録 試掘権等 | 登録 | 0/57; 覆った語=∅ |
| 80 | baseline → specificity | 系譜 | 地名 成立 始 | 地名 | 0/134; 覆った語=∅ |
| 84 | baseline → specificity | 道路運送法第五条 | 記載 提出 許可 | 記載 | 1/207; 覆った語=提出 |
| 86 | baseline → specificity | 森林法第二条 | 法律 土地 立木竹 | 法律 | 1/1374; 覆った語=土地 |
| 87 | baseline → specificity | 昭和41年政令第376号 | 日 政令 記念 | 日 | 1/314; 覆った語=記念 |
| 88 | baseline → specificity | 保安法第二十一条 | 都道府県知事 高圧ガス 製造 | 都道府県知事 | 0/116; 覆った語=∅ |
| 89 | baseline → specificity | 岩田圭一 | 目的論 エンテレケイア pdf | アリストテレス | 2/428; 覆った語=エンテレケイア,目的論 |
| 91 | baseline → specificity | 会計令第百二十条 | 職員 収納 出納計算書 | 職員 | 0/196; 覆った語=∅ |
| 93 | baseline → specificity | 健康保険法施行規則第百六十七条 | 範囲 特定健康保険組合 策定 | 範囲 | 0/452; 覆った語=∅ |
| 94 | baseline → specificity | 農地法施行規則第七十三条 | 農業者 農林水産省令 規定 | 規定 | 0/1354; 覆った語=∅ |
| 95 | baseline → specificity | 聖蹟指定 | 本格化 目的 濃 | 目的 | 0/775; 覆った語=∅ |
| 96 | baseline → specificity | 鉱業法施行規則第二十三条 | 設定 様式第十四 租鉱権 | 設定 | 0/112; 覆った語=∅ |
| 97 | baseline → specificity | 抗議活動 | グーシャ 深夜 市内 | グーシャ | 0/17; 覆った語=∅ |
| 98 | baseline → specificity | 証明機関 | 無線機 実施 指定制 | 無線機 | 0/43; 覆った語=∅ |
| 99 | baseline → specificity | 古物営業法第四条 | 許可 該当 破産手続開始 | 許可 | 0/164; 覆った語=∅ |
| 102 | baseline → specificity | 肺法 | 昭和35年3月31日 寄与 塵肺 | 寄与 | 0/40; 覆った語=∅ |
| 103 | baseline → specificity | 瞬時電圧低下 | 概 多 多い | 基本的 | 3/168; 覆った語=多,多い,概 |
| 104 | baseline → specificity | 商法第六百十四条 | 返還請求 寄託者 質入 | 寄託者 | 1/65; 覆った語=返還請求 |
| 105 | baseline → specificity | スピグル | 拡張 バルト 具体的な | 拡張 | 0/31; 覆った語=∅ |
| 106 | baseline → specificity | 消費生活協同組合法施行規則第三十七条 | 同意 書面 四第六項 | 同意 | 0/36; 覆った語=∅ |
| 108 | baseline → specificity | 最高裁判所裁判官国民審査法施行令第三十条 | 前条 第二十二条 審査公報 | 第二十二条 | 0/29; 覆った語=∅ |
| 109 | baseline → specificity | 規範的責任論 | 立場 学派的対立 対立 | 立場 | 0/265; 覆った語=∅ |
| 110 | baseline → specificity | 家畜商法附則第七条 | 会社法 役員 資格 | 会社法 | 0/66; 覆った語=∅ |
| 112 | baseline → specificity | 落石 | 被害 発生 地震 | 被害 | 2/409; 覆った語=地震,発生 |
| 114 | baseline → specificity | 難民認定法第七十条 | 拘禁刑 各号 併科 | 拘禁刑 | 0/42; 覆った語=∅ |
| 115 | baseline → specificity | 航空法施行規則第百六十三条 | 組 機長 要件 | 組 | 0/43; 覆った語=∅ |
| 117 | baseline → specificity | 地方税法施行令第四十八条 | 給料 規定 第一号 | 二 | 3/14025; 覆った語=第一号,給料,規定 |
| 118 | baseline → specificity | 沖野眞已各裁判官 | 国家賠償 放置 棄却 | 国家賠償 | 0/9; 覆った語=∅ |
| 119 | baseline → specificity | 犯行 | 効果 初 密室状態 | 効果 | 0/501; 覆った語=∅ |
| 120 | baseline → specificity | 港則法施行規則第十八条 | 目的 規定 種類 | 目的 | 1/775; 覆った語=規定 |
| 121 | baseline → specificity | 地方税法附則第百四十三条 | 行為 附則 罰則 | 行為 | 0/794; 覆った語=∅ |
| 122 | baseline → specificity | イブ | 思想 持 傾き | 思想 | 1/264; 覆った語=持 |
| 123 | baseline → specificity | 明石家電視台 | 6月1日放送分 放送 プレバト | 放送 | 0/543; 覆った語=∅ |
| 124 | baseline → specificity | 法律第百十条 | 法令 業務 選任 | 法令 | 0/232; 覆った語=∅ |
| 125 | baseline → specificity | 文化財保護法第八十六条 | 管理団体 規定 調査 | 規定 | 0/1354; 覆った語=∅ |
| 126 | baseline → specificity | 中澤高志 | npo 困難性 地域経済学研究 | npo | 0/26; 覆った語=∅ |
| 127 | baseline → specificity | 執着 | 江戸 関西 真似 | 江戸 | 1/57; 覆った語=関西 |
| 129 | baseline → specificity | 明 | 危険 労働強度 内 | 内 | 0/96; 覆った語=∅ |
| 130 | baseline → specificity | 山下法務大臣 | 収監先 死刑執行命令書 署名 | 署名 | 0/39; 覆った語=∅ |
| 131 | baseline → specificity | 嫌 | 受 人 付 | 受 | 0/202; 覆った語=∅ |
| 132 | baseline → specificity | 高畠通敏 | 筑摩書房 言語 第299号 | 言語 | 0/755; 覆った語=∅ |
| 133 | baseline → specificity | 商法第五百二十五条 | 当事者 日時 解除 | 十二 | 3/2107; 覆った語=当事者,日時,解除 |
| 134 | baseline → specificity | 個人情報保護法 | 全面施行 積極的プライバシー 成立 | 成立 | 0/149; 覆った語=∅ |
| 135 | baseline → specificity | 船舶区画規程第七十八条 | 機能 管装置 当該水密区画 | 機能 | 0/486; 覆った語=∅ |
| 136 | baseline → specificity | 三機能 | 現代性 聖職者 形成 | 形成 | 0/59; 覆った語=∅ |
| 137 | baseline → specificity | 住宅 | 住家 使用 住宅着工件数 | 使用 | 0/633; 覆った語=∅ |
| 139 | baseline → specificity | 図書館法第二十六条 | 私立図書館 国 干渉 | 国 | 0/836; 覆った語=∅ |
| 140 | baseline → specificity | 放送法施行規則第百四十八条 | 番組送出設備 業務 電気通信設備 | 業務 | 0/100; 覆った語=∅ |
| 141 | baseline → specificity | 再審請求中 | 少年死刑囚 傾向 強 | 傾向 | 1/517; 覆った語=強 |
| 142 | baseline → specificity | 自動車用静穏装置 | 逆位相 発生 騒音 | 発生 | 0/196; 覆った語=∅ |
| 143 | baseline → specificity | 有機化合物 | 初期 分析手法 個別 | 初期 | 0/229; 覆った語=∅ |
| 144 | baseline → specificity | 臨床的意義 | 半規管機能低下 意思決定 影響 | 影響 | 0/578; 覆った語=∅ |
| 146 | baseline → specificity | 外国ニ | 外国 流通 取締り | 外国 | 0/82; 覆った語=∅ |
| 147 | baseline → specificity | アグロロジー | 一分野 助言 同義 | 人間 | 2/1073; 覆った語=一分野,同義 |
| 149 | baseline → specificity | 外国貿易法第二十三条 | 対外直接投資 政令 第四項各号 | 政令 | 0/42; 覆った語=∅ |
| 151 | baseline → specificity | 農産物検査法第十六条 | 農林水産大臣 事実 職員 | 三十八 | 3/369; 覆った語=事実,職員,農林水産大臣 |
| 152 | baseline → specificity | 保健師助産師看護師法施行規則第十三条 | 登録 法第十五条 第一号 | 十四 | 3/1772; 覆った語=法第十五条,登録,第一号 |
| 153 | baseline → specificity | 金丸康信 | 原田由起彦 山梨県 務 | 山梨県 | 0/16; 覆った語=∅ |
| 154 | baseline → specificity | 神奈川人権センター | 日本 申 抗議 | 日本 | 0/2493; 覆った語=∅ |
| 156 | baseline → specificity | 旅行業法第三十二条 | 手配業 旅行サービス 禁止 | 禁止 | 0/74; 覆った語=∅ |
| 157 | baseline → specificity | 砂防法第四十一条 | 義務ニ 此ノ 関シテハ | 第四条 | 2/489; 覆った語=此ノ,関シテハ |
| 158 | baseline → specificity | 三権 | 置 権力 立法 | 置 | 0/21; 覆った語=∅ |
| 161 | baseline → specificity | 鉱業登録令第十一条 | 経済産業大臣 滅失 期間 | 七 | 3/3731; 覆った語=期間,滅失,経済産業大臣 |
| 162 | baseline → specificity | 移入 | 太平洋側 混血 札幌市付近 | 混血 | 0/19; 覆った語=∅ |
| 163 | baseline → specificity | 地方税法第三百七十四条 | 滞納処分 執行 目的 | 目的 | 1/775; 覆った語=執行 |
| 164 | baseline → specificity | 掘立小屋 | 強盗殺人事件 男性 当時46歳 | 男性 | 0/385; 覆った語=∅ |
| 165 | baseline → specificity | 澤口実歩 | 同局アナウンサー 日 放送 | 放送開始 | 3/80; 覆った語=同局アナウンサー,放送,日 |
| 166 | baseline → specificity | 企業合理化促進法施行規則第四条 | 補助金交付 提出 申請書 | 提出 | 0/77; 覆った語=∅ |
| 167 | baseline → specificity | ボルノウ | 池川 大塚 人間 | 人間 | 0/1073; 覆った語=∅ |
| 168 | baseline → specificity | 道路運送車両法第十六条 | 自動車 申請 運行 | 自動車 | 0/181; 覆った語=∅ |
| 169 | baseline → specificity | 貸付信託法附則第百二十一条 | 施行前 規定 効力 | 規定 | 2/1354; 覆った語=効力,施行前 |
| 170 | baseline → specificity | 予防接種法第四十九条 | 費用 定期 支弁 | 費用 | 0/210; 覆った語=∅ |
| 171 | baseline → specificity | 検察審査会法第十五条 | 各群 規定 検察審査員 | 規定 | 0/1354; 覆った語=∅ |
| 172 | baseline → specificity | 東北6県 | 民放 関東地方 無料聴取 | 民放 | 0/5; 覆った語=∅ |
| 173 | baseline → specificity | 加入電話 | 警察電話 市内 消防署 | 警察電話 | 0/12; 覆った語=∅ |
| 175 | baseline → specificity | 陰イオン | mgso4 反応 化合物 | 反応 | 0/431; 覆った語=∅ |
| 176 | baseline → specificity | 車道 | 設置 多い 駅前 | 設置 | 1/124; 覆った語=多い |
| 177 | baseline → specificity | 海事代理士法第八条 | 地方運輸局長 運輸監理部長 第十二条 | 第十二条 | 0/129; 覆った語=∅ |
| 178 | baseline → specificity | 森林法施行法第九条 | 遅滞な 組織変更 第七条 | 第七条 | 0/329; 覆った語=∅ |
| 180 | baseline → specificity | 小坂誠 | 対横浜5回戦 代打 巨人 | 巨人 | 0/99; 覆った語=∅ |
| 181 | baseline → specificity | 難民認定法第四十八条 | 口頭審理 認定 異議 | 認定 | 0/37; 覆った語=∅ |
| 182 | baseline → specificity | 斜辺 | 共有 cd 合同 | 共有 | 0/50; 覆った語=∅ |
| 183 | baseline → specificity | 宗教法人法第三条 | 境内建物 目的 規定 | 目的 | 1/775; 覆った語=規定 |
| 184 | baseline → specificity | 戸籍法施行規則第六十条 | 漢字 常用漢字表 括弧書き | 漢字 | 0/190; 覆った語=∅ |
| 185 | baseline → specificity | 労働関係調整法第三十五条 | 当事者 双方 労働争議 | 当事者 | 0/212; 覆った語=∅ |
| 186 | baseline → specificity | 臨床血液学 | 扱 算定検査 血液学的検査 | 扱 | 0/66; 覆った語=∅ |
| 187 | baseline → specificity | 船員法第百四条 | 規定 基準 市町村 | 規定 | 1/1354; 覆った語=基準 |
| 188 | baseline → specificity | 認識論的問題 | 性質 法 見な | 性質 | 1/546; 覆った語=見な |
| 189 | baseline → specificity | 計算証明規則第十六条 | 歳入 競争契約 書類 | 歳入 | 0/15; 覆った語=∅ |
| 190 | baseline → specificity | 物価統制令第三十五条 | 規定ニ 第十二条 違反シタル | 第十二条 | 0/129; 覆った語=∅ |
| 191 | baseline → specificity | 理論的説明 | 知 高温超伝導 現象 | 知 | 0/54; 覆った語=∅ |
| 193 | baseline → specificity | 抵当権設定者 | 引 実現 効率的利用 | 引 | 0/17; 覆った語=∅ |
| 194 | baseline → specificity | 航空法施行規則第百九十四条 | 物件 輸送禁止 火薬類火薬 | 物件 | 0/7; 覆った語=∅ |
| 195 | baseline → specificity | 地方税法第三百一条 | 虚偽 規定 前条第一項 | 虚偽 | 0/5; 覆った語=∅ |
| 196 | baseline → specificity | ゲームエンジン | 作業 不在 主流 | 作業 | 0/266; 覆った語=∅ |
| 197 | baseline → specificity | 学校基本調査規則第四条 | 時期 学齢児童生徒 卒業者 | 時期 | 0/225; 覆った語=∅ |
| 198 | baseline → specificity | 合名会社等再建整備令第四条 | 適用 必要 整備計画 | 適用 | 0/258; 覆った語=∅ |
| 199 | baseline → specificity | 地方税法施行令第九条 | 適格合併等 規定 同項 | 規定 | 1/1354; 覆った語=同項 |
| 200 | baseline → specificity | 規制機関 | 実質的 控 国 | 実質的 | 0/6; 覆った語=∅ |
| 201 | baseline → specificity | 水産業協同組合法第百十六条 | 次条第一項 規定 六十一 | 規定 | 0/1354; 覆った語=∅ |
| 202 | baseline → specificity | ニュースゾーン | 広瀬麻知子 番組 4年間担当 | 番組 | 0/497; 覆った語=∅ |
| 203 | baseline → specificity | dominator | anniversary 追加生産 th | 音楽 | 2/764; 覆った語=anniversary,th |
| 204 | baseline → specificity | 桧垣良成 | 展開 カント 日本哲学会 | 展開 | 0/38; 覆った語=∅ |
| 205 | baseline → specificity | 民法第三百六十六条 | 質権者 金銭 質権 | 債権者 | 2/127; 覆った語=質権,金銭 |
| 206 | baseline → specificity | サンダル | 着用可能な 品物 ハイヒール | 品物 | 0/31; 覆った語=∅ |
| 207 | baseline → specificity | 坂倉 | 特 岡田 復帰 | 特 | 0/461; 覆った語=∅ |
| 208 | baseline → specificity | 気象業務法施行規則第二十九条 | 法第二十四条 記載 指定試験機関 | 記載 | 0/207; 覆った語=∅ |
| 209 | baseline → specificity | 冥王星 | 定義 system solar | 定義 | 0/853; 覆った語=∅ |
| 212 | baseline → specificity | 接地 | 広義 日本 必 | 広義 | 1/117; 覆った語=必 |
| 213 | baseline → specificity | 波長分布 | 照明下 太陽光線 異な | 異な | 0/97; 覆った語=∅ |
| 214 | baseline → specificity | 海面漁業生産統計調査規則第十条 | 集計結果 都道府県別 送付 | 送付 | 0/2; 覆った語=∅ |
| 215 | baseline → specificity | 道路運送車両法施行規則第三十六条 | 当該自動車 新規検査 申請 | 申請 | 0/131; 覆った語=∅ |
| 216 | baseline → specificity | 法律附則第四条 | 外務公務員 在外公館 名称 | 名称 | 0/427; 覆った語=∅ |
| 217 | baseline → specificity | 各番組 | 特別番組 呼 土曜朝改編 | 形 | 2/421; 覆った語=呼,特別番組 |
| 218 | baseline → specificity | 予防課 | 救急課 原子力規制庁原子力規制企画課火災対策室な 執行 | 執行 | 0/74; 覆った語=∅ |
| 219 | baseline → specificity | 薬事法距離制限違憲判決 | 最高裁判所 態様 弊害 | 最高裁判所 | 0/240; 覆った語=∅ |
| 221 | baseline → specificity | ヒルシステム | ヒル 数 他 | 他 | 0/1274; 覆った語=∅ |
| 222 | baseline → specificity | 班田収授 | 理由 大隅な 墾田 | 理由 | 0/559; 覆った語=∅ |
| 223 | baseline → specificity | 南満洲鉄道附属地煙草税令 | 廃止 満洲国ニ 勅令中改正等ノ | 廃止 | 0/94; 覆った語=∅ |
| 224 | baseline → specificity | psa | 言語全体 談話的 関係 | 関係 | 0/898; 覆った語=∅ |
| 225 | baseline → specificity | 言語学的な | 民族 人 理論 | 民族 | 1/92; 覆った語=人 |
| 226 | baseline → specificity | 貿易保険法第十条 | 職員 次条 法人 | 職員 | 0/196; 覆った語=∅ |
| 227 | baseline → specificity | 教科用図書検定調査審議会令附則第二条 | 政令 施行 教科用図書検定調査審議会 | 政令 | 0/42; 覆った語=∅ |
| 228 | baseline → specificity | 科学研究費助成事業 | 工学 再生 日本学術振興会 | 工学 | 0/160; 覆った語=∅ |
| 229 | baseline → specificity | 内航海運業法第十八条 | 登録 国土交通大臣 届出 | 登録 | 1/57; 覆った語=届出 |
| 230 | baseline → specificity | 口角 | 左右非対称 左右対称 協調運動 | 説明 | 1/355; 覆った語=左右対称 |
| 232 | baseline → specificity | 一般名 | 語 アルキル 続 | 語 | 1/1089; 覆った語=続 |
| 233 | baseline → specificity | r1 | 存在 住宅数 依然 | 存在 | 0/623; 覆った語=∅ |
| 234 | baseline → specificity | 火薬類取締法施行規則第八十三条 | 取扱者 制限 経済産業省令 | 制限 | 0/269; 覆った語=∅ |
| 235 | baseline → specificity | 農業工学技術者 | 土地改良技術者 研究機関な 商品 | 商品 | 0/71; 覆った語=∅ |
| 236 | baseline → specificity | ランベルト | 吸光度 存在量 求 | 等価幅 | 2/106; 覆った語=存在量,求 |
| 237 | baseline → specificity | 漁船法第二十七条 | 漁船用機械 試験 設計 | 設計 | 0/213; 覆った語=∅ |
| 238 | baseline → specificity | 現存社会 | マルクス 経済理論 社会科学 | マルクス | 0/80; 覆った語=∅ |
| 239 | baseline → specificity | 生活保護法第四十四条 | 都道府県知事 管理者 立入検査 | 都道府県知事 | 0/116; 覆った語=∅ |
| 241 | baseline → specificity | タミール | 発音 地名な 思 | 語 | 2/1089; 覆った語=思,発音 |
| 242 | baseline → specificity | 日本銀行政府有価証券取扱規程第三十四条 | 第二十八条ノ 於テ 日本銀行ニ | 二 | 1/14025; 覆った語=於テ |
| 243 | baseline → specificity | 条約第六条 | 担任スヘシ 左ノ 以テ | 第一条 | 2/736; 覆った語=以テ,左ノ |
| 245 | baseline → specificity | 速度分布 | 分布関数 温度 従い | 温度 | 0/249; 覆った語=∅ |
| 246 | baseline → specificity | バーク | 取 供 合い | 取 | 0/63; 覆った語=∅ |
| 250 | baseline → specificity | 警視庁 | 受 可能 対応 | 受 | 0/202; 覆った語=∅ |
| 251 | baseline → specificity | 貿易保険法第六十九条 | 該当 保険契約 海外投資 | 該当 | 0/42; 覆った語=∅ |
| 252 | baseline → specificity | 音楽関連 | 同県 沖縄県 決定 | 決定 | 0/204; 覆った語=∅ |
| 253 | baseline → specificity | 海上運送法第三十四条 | 船員確保基本方針 第一条 船舶法 | 第一条 | 0/736; 覆った語=∅ |
| 254 | baseline → specificity | 公職選挙法施行令第百四十四条 | 政令 国勢調査 公示 | 政令 | 0/42; 覆った語=∅ |
| 256 | baseline → specificity | 地方税法施行令附則第十八条 | 譲渡所得等 金額 特例 | 金額 | 0/115; 覆った語=∅ |
| 258 | baseline → specificity | 第五十九条 | 禁止 意見聴取 提出 | 禁止 | 0/74; 覆った語=∅ |
| 260 | baseline → specificity | 入場 | 含 会場 映画館 | 含 | 0/66; 覆った語=∅ |
| 261 | baseline → specificity | 引受先 | 答弁 検討 縦割 | 政府 | 2/1156; 覆った語=検討,答弁 |
| 262 | baseline → specificity | 金融機関再建整備法施行規則第二十三条 | 評価 記載 金融機関 | 評価 | 0/223; 覆った語=∅ |
| 263 | baseline → specificity | 母体 | 性感染症 含 ヒト | ヒト | 0/287; 覆った語=∅ |
| 264 | baseline → specificity | 地方税法第六百八十六条 | 更正 前条第二項 規定 | 六十六 | 3/119; 覆った語=前条第二項,更正,規定 |
| 265 | baseline → specificity | 船員職業安定法附則第二十八条 | 政令 罰則 法律 | 政令 | 1/42; 覆った語=法律 |
| 266 | baseline → specificity | 航空法第百十九条 | 六月以内 国土交通大臣 該当 | 六十三 | 3/150; 覆った語=六月以内,国土交通大臣,該当 |
| 268 | baseline → specificity | 劇性 | 強い 指定 法令 | 必要 | 3/1677; 覆った語=強い,指定,法令 |
| 269 | baseline → specificity | 土地改良法第四十三条 | 資格 承継 決済 | 資格 | 0/78; 覆った語=∅ |
| 270 | baseline → specificity | キリコ | 体 傭兵部隊 判明 | 体 | 0/152; 覆った語=∅ |
| 272 | baseline → specificity | 健康保険法施行規則第八十三条 | 給付 規定 記載 | 五十九 | 3/134; 覆った語=給付,規定,記載 |
| 273 | baseline → specificity | 的基礎 | 接点 多い 批判 | 接点 | 0/14; 覆った語=∅ |
| 274 | baseline → specificity | ピーク | 平成6年 動脈硬化 度 | 度 | 0/41; 覆った語=∅ |
| 277 | baseline → specificity | 法学者ウルピアヌス | 公法 西洋法学 利益 | 国家 | 2/345; 覆った語=公法,利益 |
| 278 | baseline → specificity | 改元前日 | 大型特番 枠 日スペシャル | 枠 | 0/144; 覆った語=∅ |
| 279 | baseline → specificity | iosアプリ | 配信 production 制作 | 配信 | 1/142; 覆った語=制作 |
| 281 | baseline → specificity | 公有水面埋立法第三条 | 其ノ 遅滞ナク 掲グル | 二 | 3/14025; 覆った語=其ノ,掲グル,遅滞ナク |
| 282 | baseline → specificity | テープ | 主 使 作成 | 主 | 1/464; 覆った語=使 |
| 283 | baseline → specificity | 在外公館等借入金返済実施規程第一条 | 法律 返済 規程 | 法律 | 0/1374; 覆った語=∅ |
| 284 | baseline → specificity | キノリニウムベタイン | 血赤色 負 青色 | 負 | 0/5; 覆った語=∅ |
| 285 | baseline → specificity | 国土調査法施行令第十六条 | 認証 請求 成果 | 認証 | 0/31; 覆った語=∅ |
| 286 | baseline → specificity | 気象業務法第四十六条 | 違反 該当 第九条 | 違反 | 0/100; 覆った語=∅ |
| 289 | baseline → specificity | 港湾法第四十一条 | 構築物 改築等 有害構築物 | 構築物 | 0/4; 覆った語=∅ |
| 292 | baseline → specificity | 元来 | 化学構造な 仏 動詞 | 動詞 | 0/191; 覆った語=∅ |
| 294 | baseline → specificity | 宗教法人法第五十二条 | 規則 認証書 交付 | 規則 | 0/183; 覆った語=∅ |
| 295 | baseline → specificity | 解決方法 | 利点 元 オブザーバブル | 利点 | 0/233; 覆った語=∅ |
| 296 | baseline → specificity | 同居 | 親族以外 適用除外 他人 | 他人 | 0/102; 覆った語=∅ |
| 297 | baseline → specificity | 武器等製造法附則第九条 | 罰則 行為 施行前 | 罰則 | 1/175; 覆った語=行為 |
| 298 | baseline → specificity | 離島航路整備法施行規則第二条 | 国土交通大臣 航路補助金 申請 | 国土交通大臣 | 0/61; 覆った語=∅ |
| 299 | baseline → specificity | 反三木派 | 椎名 批判 政権主流派 | 批判 | 0/347; 覆った語=∅ |
| 2 | no_junk → no_junk_specificity | 温泉法第十六条 | 許可 法人 前条第一項 | 許可 | 0/164; 覆った語=∅ |
| 3 | no_junk → no_junk_specificity | ジアダ | シュタイナー シャーロック シャングリラ | ゴリー | 1/33; 覆った語=シャーロック |
| 4 | no_junk → no_junk_specificity | 職業安定法 | 昭和23年3月2日基発381号 広 排除 | 排除 | 0/4; 覆った語=∅ |
| 8 | no_junk → no_junk_specificity | 金融商品取引法第六十条 | 第五十八条 規定 売買 | 十三 | 3/2011; 覆った語=売買,第五十八条,規定 |
| 9 | no_junk → no_junk_specificity | 本居宣長 | 指摘 壬申 国学 | 指摘 | 0/47; 覆った語=∅ |
| 10 | no_junk → no_junk_specificity | 民事調停法第二十条 | 職権 管轄裁判所 調停 | 職権 | 0/36; 覆った語=∅ |
| 12 | no_junk → no_junk_specificity | 牧野法施行規則第十八条 | 書類 添附 届出 | 書類 | 0/33; 覆った語=∅ |
| 15 | no_junk → no_junk_specificity | テンペレートファージ | 可能性 拡散 得 | 可能性 | 0/710; 覆った語=∅ |
| 16 | no_junk → no_junk_specificity | 鉱業法施行規則第十五条 | 期日 競願 準用 | 準用 | 0/61; 覆った語=∅ |
| 17 | no_junk → no_junk_specificity | 商法第六百八十五条 | 従物 書式 推定等 | 書式 | 0/50; 覆った語=∅ |
| 19 | no_junk → no_junk_specificity | 関連企業 | インド アイグループ software | インド | 0/203; 覆った語=∅ |
| 20 | no_junk → no_junk_specificity | 保安基準第二十二条 | 道路運送車両 着席 空間 | 空間 | 0/112; 覆った語=∅ |
| 21 | no_junk → no_junk_specificity | 文化財保護法第百三十五条 | 選定 重要文化的景観 解除 | 選定 | 0/12; 覆った語=∅ |
| 22 | no_junk → no_junk_specificity | p.w.atkins | 東京化学同人 元裕 物理化学 | 物理化学 | 0/19; 覆った語=∅ |
| 23 | no_junk → no_junk_specificity | 宮本隆司 | 撮影 建設過程 過程 | 当初 | 2/953; 覆った語=撮影,過程 |
| 24 | no_junk → no_junk_specificity | 第三回四分利付英貨公債発行規程第八条 | 日本国ノ 関スル 間ニ | 第七条 | 3/329; 覆った語=日本国ノ,間ニ,関スル |
| 25 | no_junk → no_junk_specificity | 立方体 | 投影図 座標軸 単面投影 | 投影図 | 0/18; 覆った語=∅ |
| 26 | no_junk → no_junk_specificity | 鉱山保安法第二条 | 鉱業権者 法律 租鉱権者 | 法律 | 0/1374; 覆った語=∅ |
| 30 | no_junk → no_junk_specificity | 浅田 | プロフィギュアスケーター バカ 日放送 | バラエティ | 2/806; 覆った語=バカ,日放送 |
| 31 | no_junk → no_junk_specificity | 都市ガス | 支障 店舗 復旧 | 支障 | 0/12; 覆った語=∅ |
| 32 | no_junk → no_junk_specificity | 外務公務員法施行令第一条 | 申出 規定 第八条第一項 | 十七 | 3/1460; 覆った語=申出,第八条第一項,規定 |
| 33 | no_junk → no_junk_specificity | 道路運送法施行規則附則第七条 | 経過措置 登録事項 規定 | 経過措置 | 0/32; 覆った語=∅ |
| 34 | no_junk → no_junk_specificity | 連帯債務 | 支払い 求償 d | 支払い | 0/21; 覆った語=∅ |
| 35 | no_junk → no_junk_specificity | 多倍数種 | 既知 植物属 約半数 | 既知 | 0/8; 覆った語=∅ |
| 37 | no_junk → no_junk_specificity | 商法第五百七十七条 | 種類 荷送人 運送 | 種類 | 0/300; 覆った語=∅ |
| 40 | no_junk → no_junk_specificity | 建築物な | 適用 局部等電位化 機器 | 基準 | 2/362; 覆った語=機器,適用 |
| 41 | no_junk → no_junk_specificity | 宝月誠 | 思想 社会的背景 初期シカゴ | 思想 | 0/264; 覆った語=∅ |
| 44 | no_junk → no_junk_specificity | 恩給法附則第百六十一条 | 処分庁 行政庁 施行日前 | 処分庁 | 1/87; 覆った語=行政庁 |
| 45 | no_junk → no_junk_specificity | 国土調査法第三十七条 | 実施 第二十三条 国土調査 | 第二十三条 | 0/31; 覆った語=∅ |
| 47 | no_junk → no_junk_specificity | 通説 | 1行 ドイツ 不可罰 | ドイツ | 0/550; 覆った語=∅ |
| 48 | no_junk → no_junk_specificity | 家畜保健衛生所法附則第百六十一条 | 行政庁 処分 経過措置 | 行政庁 | 1/249; 覆った語=処分 |
| 49 | no_junk → no_junk_specificity | 両親 | 以来 人工呼吸器 ドイツ | 以来 | 0/12; 覆った語=∅ |
| 50 | no_junk → no_junk_specificity | psycho-pass | 名前 タイトル sinners | 名前 | 1/405; 覆った語=タイトル |
| 51 | no_junk → no_junk_specificity | 医学教育 | 場 国 制度 | 国民 | 3/359; 覆った語=制度,国,場 |
| 52 | no_junk → no_junk_specificity | 地方税法第五百九十一条 | 虚偽 手段 特別土地保有税 | 虚偽 | 0/5; 覆った語=∅ |
| 53 | no_junk → no_junk_specificity | 壁新聞 | ニュース 総合博物館 寄贈 | ニュース | 0/86; 覆った語=∅ |
| 55 | no_junk → no_junk_specificity | 海上運送法第二十九条 | 締結 変更 国土交通大臣 | 五十 | 3/158; 覆った語=国土交通大臣,変更,締結 |
| 56 | no_junk → no_junk_specificity | 京都府特殊物件処理委員会 | 応急利用等 措置 政府 | 政府 | 1/1156; 覆った語=措置 |
| 58 | no_junk → no_junk_specificity | 土地家屋調査士法第十四条 | 調査士 登録 所属 | 登録 | 0/57; 覆った語=∅ |
| 59 | no_junk → no_junk_specificity | 液体ヘリウム | クエンチ t 不要 | クエンチ | 0/18; 覆った語=∅ |
| 60 | no_junk → no_junk_specificity | 人為 | 語 自然 加 | ランドスケープ | 3/202; 覆った語=加,自然,語 |
| 61 | no_junk → no_junk_specificity | 保安法第五十条 | 経過 政令 更新 | 経過 | 1/61; 覆った語=更新 |
| 64 | no_junk → no_junk_specificity | 無線局免許手続規則第二十七条 | 記録 別表第十号 許可記録 | 記録 | 0/261; 覆った語=∅ |
| 65 | no_junk → no_junk_specificity | 資産再評価法施行令第一条 | 減価償却資産 帳簿価額 取得価額 | 取得価額 | 0/4; 覆った語=∅ |
| 66 | no_junk → no_junk_specificity | 16組 | 放送 披露 本番 | 放送 | 0/543; 覆った語=∅ |
| 68 | no_junk → no_junk_specificity | 完了後 | ポルトガル 言語純化運動 教徒 | 単語 | 2/309; 覆った語=ポルトガル,教徒 |
| 74 | no_junk → no_junk_specificity | 首脳 | フランス 冬季大会 抗議 | フランス | 0/332; 覆った語=∅ |
| 75 | no_junk → no_junk_specificity | 理論生物学 | 行動 定量的 形質 | 行動 | 1/292; 覆った語=形質 |
| 76 | no_junk → no_junk_specificity | chemrxiv | 化学関連分野 投稿 未発表プレプリント | 投稿 | 0/37; 覆った語=∅ |
| 77 | no_junk → no_junk_specificity | 高橋 | 法律学小辞典 光男 小早川 | 小早川 | 0/38; 覆った語=∅ |
| 78 | no_junk → no_junk_specificity | 哲学的考察 | 問題 妊娠中絶 影響 | 問題 | 1/1270; 覆った語=影響 |
| 79 | no_junk → no_junk_specificity | 鉱業登録令第五十条 | 試掘権 登録 試掘権等 | 登録 | 0/57; 覆った語=∅ |
| 80 | no_junk → no_junk_specificity | 系譜 | 地名 成立 始 | 地名 | 0/134; 覆った語=∅ |
| 83 | no_junk → no_junk_specificity | 相続税法第二十七条 | 相続税 贈与 相続 | 相続税 | 0/8; 覆った語=∅ |
| 84 | no_junk → no_junk_specificity | 道路運送法第五条 | 記載 提出 許可 | 記載 | 1/207; 覆った語=提出 |
| 86 | no_junk → no_junk_specificity | 森林法第二条 | 法律 土地 立木竹 | 法律 | 1/1374; 覆った語=土地 |
| 88 | no_junk → no_junk_specificity | 保安法第二十一条 | 都道府県知事 高圧ガス 製造 | 都道府県知事 | 0/116; 覆った語=∅ |
| 89 | no_junk → no_junk_specificity | 岩田圭一 | 目的論 エンテレケイア pdf | アリストテレス | 2/428; 覆った語=エンテレケイア,目的論 |
| 91 | no_junk → no_junk_specificity | 会計令第百二十条 | 職員 収納 出納計算書 | 職員 | 0/196; 覆った語=∅ |
| 93 | no_junk → no_junk_specificity | 健康保険法施行規則第百六十七条 | 範囲 特定健康保険組合 策定 | 範囲 | 0/452; 覆った語=∅ |
| 94 | no_junk → no_junk_specificity | 農地法施行規則第七十三条 | 農業者 農林水産省令 規定 | 規定 | 0/1354; 覆った語=∅ |
| 95 | no_junk → no_junk_specificity | 聖蹟指定 | 本格化 目的 濃 | 目的 | 0/775; 覆った語=∅ |
| 96 | no_junk → no_junk_specificity | 鉱業法施行規則第二十三条 | 設定 様式第十四 租鉱権 | 設定 | 0/112; 覆った語=∅ |
| 97 | no_junk → no_junk_specificity | 抗議活動 | グーシャ 深夜 市内 | グーシャ | 0/17; 覆った語=∅ |
| 98 | no_junk → no_junk_specificity | 証明機関 | 無線機 実施 指定制 | 無線機 | 0/43; 覆った語=∅ |
| 99 | no_junk → no_junk_specificity | 古物営業法第四条 | 許可 該当 破産手続開始 | 許可 | 0/164; 覆った語=∅ |
| 100 | no_junk → no_junk_specificity | 論 | 中核 傾向 代表 | 方式 | 2/279; 覆った語=代表,傾向 |
| 102 | no_junk → no_junk_specificity | 肺法 | 昭和35年3月31日 寄与 塵肺 | 寄与 | 0/40; 覆った語=∅ |
| 103 | no_junk → no_junk_specificity | 瞬時電圧低下 | 概 多 多い | 基本的 | 3/168; 覆った語=多,多い,概 |
| 104 | no_junk → no_junk_specificity | 商法第六百十四条 | 返還請求 寄託者 質入 | 寄託者 | 1/65; 覆った語=返還請求 |
| 105 | no_junk → no_junk_specificity | スピグル | 拡張 バルト 具体的な | 拡張 | 0/31; 覆った語=∅ |
| 106 | no_junk → no_junk_specificity | 消費生活協同組合法施行規則第三十七条 | 同意 書面 四第六項 | 同意 | 0/36; 覆った語=∅ |
| 108 | no_junk → no_junk_specificity | 最高裁判所裁判官国民審査法施行令第三十条 | 前条 第二十二条 審査公報 | 第二十二条 | 0/29; 覆った語=∅ |
| 109 | no_junk → no_junk_specificity | 規範的責任論 | 立場 学派的対立 対立 | 立場 | 0/265; 覆った語=∅ |
| 110 | no_junk → no_junk_specificity | 家畜商法附則第七条 | 会社法 役員 資格 | 会社法 | 0/66; 覆った語=∅ |
| 112 | no_junk → no_junk_specificity | 落石 | 被害 発生 地震 | 被害 | 2/409; 覆った語=地震,発生 |
| 114 | no_junk → no_junk_specificity | 難民認定法第七十条 | 拘禁刑 各号 併科 | 拘禁刑 | 0/42; 覆った語=∅ |
| 118 | no_junk → no_junk_specificity | 沖野眞已各裁判官 | 国家賠償 放置 棄却 | 国家賠償 | 0/9; 覆った語=∅ |
| 119 | no_junk → no_junk_specificity | 犯行 | 効果 初 密室状態 | 効果 | 0/501; 覆った語=∅ |
| 120 | no_junk → no_junk_specificity | 港則法施行規則第十八条 | 目的 規定 種類 | 目的 | 1/775; 覆った語=規定 |
| 121 | no_junk → no_junk_specificity | 地方税法附則第百四十三条 | 行為 附則 罰則 | 行為 | 0/794; 覆った語=∅ |
| 122 | no_junk → no_junk_specificity | イブ | 思想 持 傾き | 思想 | 1/264; 覆った語=持 |
| 123 | no_junk → no_junk_specificity | 明石家電視台 | 6月1日放送分 放送 プレバト | 放送 | 0/543; 覆った語=∅ |
| 124 | no_junk → no_junk_specificity | 法律第百十条 | 法令 業務 選任 | 法令 | 0/232; 覆った語=∅ |
| 125 | no_junk → no_junk_specificity | 文化財保護法第八十六条 | 管理団体 規定 調査 | 規定 | 0/1354; 覆った語=∅ |
| 126 | no_junk → no_junk_specificity | 中澤高志 | npo 困難性 地域経済学研究 | npo | 0/26; 覆った語=∅ |
| 127 | no_junk → no_junk_specificity | 執着 | 江戸 関西 真似 | 江戸 | 1/57; 覆った語=関西 |
| 130 | no_junk → no_junk_specificity | 山下法務大臣 | 収監先 死刑執行命令書 署名 | 署名 | 0/39; 覆った語=∅ |
| 132 | no_junk → no_junk_specificity | 高畠通敏 | 筑摩書房 言語 第299号 | 言語 | 0/755; 覆った語=∅ |
| 133 | no_junk → no_junk_specificity | 商法第五百二十五条 | 当事者 日時 解除 | 十二 | 3/2107; 覆った語=当事者,日時,解除 |
| 134 | no_junk → no_junk_specificity | 個人情報保護法 | 全面施行 積極的プライバシー 成立 | 成立 | 0/149; 覆った語=∅ |
| 135 | no_junk → no_junk_specificity | 船舶区画規程第七十八条 | 機能 管装置 当該水密区画 | 機能 | 0/486; 覆った語=∅ |
| 136 | no_junk → no_junk_specificity | 三機能 | 現代性 聖職者 形成 | 形成 | 0/59; 覆った語=∅ |
| 137 | no_junk → no_junk_specificity | 住宅 | 住家 使用 住宅着工件数 | 使用 | 0/633; 覆った語=∅ |
| 139 | no_junk → no_junk_specificity | 図書館法第二十六条 | 私立図書館 国 干渉 | 干渉 | 0/40; 覆った語=∅ |
| 140 | no_junk → no_junk_specificity | 放送法施行規則第百四十八条 | 番組送出設備 業務 電気通信設備 | 業務 | 0/100; 覆った語=∅ |
| 141 | no_junk → no_junk_specificity | 再審請求中 | 少年死刑囚 傾向 強 | 傾向 | 1/517; 覆った語=強 |
| 142 | no_junk → no_junk_specificity | 自動車用静穏装置 | 逆位相 発生 騒音 | 発生 | 0/196; 覆った語=∅ |
| 143 | no_junk → no_junk_specificity | 有機化合物 | 初期 分析手法 個別 | 初期 | 0/229; 覆った語=∅ |
| 144 | no_junk → no_junk_specificity | 臨床的意義 | 半規管機能低下 意思決定 影響 | 影響 | 0/578; 覆った語=∅ |
| 146 | no_junk → no_junk_specificity | 外国ニ | 外国 流通 取締り | 外国 | 0/82; 覆った語=∅ |
| 147 | no_junk → no_junk_specificity | アグロロジー | 一分野 助言 同義 | 人間 | 2/1073; 覆った語=一分野,同義 |
| 149 | no_junk → no_junk_specificity | 外国貿易法第二十三条 | 対外直接投資 政令 第四項各号 | 政令 | 0/42; 覆った語=∅ |
| 151 | no_junk → no_junk_specificity | 農産物検査法第十六条 | 農林水産大臣 事実 職員 | 三十八 | 3/369; 覆った語=事実,職員,農林水産大臣 |
| 152 | no_junk → no_junk_specificity | 保健師助産師看護師法施行規則第十三条 | 登録 法第十五条 第一号 | 十四 | 3/1772; 覆った語=法第十五条,登録,第一号 |
| 153 | no_junk → no_junk_specificity | 金丸康信 | 原田由起彦 山梨県 務 | 山梨県 | 0/16; 覆った語=∅ |
| 154 | no_junk → no_junk_specificity | 神奈川人権センター | 日本 申 抗議 | 日本 | 0/2493; 覆った語=∅ |
| 156 | no_junk → no_junk_specificity | 旅行業法第三十二条 | 手配業 旅行サービス 禁止 | 禁止 | 0/74; 覆った語=∅ |
| 157 | no_junk → no_junk_specificity | 砂防法第四十一条 | 義務ニ 此ノ 関シテハ | 第四条 | 2/489; 覆った語=此ノ,関シテハ |
| 161 | no_junk → no_junk_specificity | 鉱業登録令第十一条 | 経済産業大臣 滅失 期間 | 経済産業大臣 | 0/45; 覆った語=∅ |
| 162 | no_junk → no_junk_specificity | 移入 | 太平洋側 混血 札幌市付近 | 混血 | 0/19; 覆った語=∅ |
| 163 | no_junk → no_junk_specificity | 地方税法第三百七十四条 | 滞納処分 執行 目的 | 目的 | 1/775; 覆った語=執行 |
| 164 | no_junk → no_junk_specificity | 掘立小屋 | 強盗殺人事件 男性 当時46歳 | 男性 | 0/385; 覆った語=∅ |
| 165 | no_junk → no_junk_specificity | 澤口実歩 | 同局アナウンサー 日 放送 | 放送開始 | 3/80; 覆った語=同局アナウンサー,放送,日 |
| 166 | no_junk → no_junk_specificity | 企業合理化促進法施行規則第四条 | 補助金交付 提出 申請書 | 提出 | 0/77; 覆った語=∅ |
| 167 | no_junk → no_junk_specificity | ボルノウ | 池川 大塚 人間 | 人間 | 0/1073; 覆った語=∅ |
| 168 | no_junk → no_junk_specificity | 道路運送車両法第十六条 | 自動車 申請 運行 | 自動車 | 0/181; 覆った語=∅ |
| 169 | no_junk → no_junk_specificity | 貸付信託法附則第百二十一条 | 施行前 規定 効力 | 規定 | 2/1354; 覆った語=効力,施行前 |
| 170 | no_junk → no_junk_specificity | 予防接種法第四十九条 | 費用 定期 支弁 | 費用 | 0/210; 覆った語=∅ |
| 171 | no_junk → no_junk_specificity | 検察審査会法第十五条 | 各群 規定 検察審査員 | 規定 | 0/1354; 覆った語=∅ |
| 172 | no_junk → no_junk_specificity | 東北6県 | 民放 関東地方 無料聴取 | 民放 | 0/5; 覆った語=∅ |
| 173 | no_junk → no_junk_specificity | 加入電話 | 警察電話 市内 消防署 | 警察電話 | 0/12; 覆った語=∅ |
| 174 | no_junk → no_junk_specificity | 健康保険法施行規則第百三十四条 | 第三十三条 第五十八条 第六十一条 | 第三十三条 | 0/15; 覆った語=∅ |
| 175 | no_junk → no_junk_specificity | 陰イオン | mgso4 反応 化合物 | 反応 | 0/431; 覆った語=∅ |
| 176 | no_junk → no_junk_specificity | 車道 | 設置 多い 駅前 | 設置 | 1/124; 覆った語=多い |
| 177 | no_junk → no_junk_specificity | 海事代理士法第八条 | 地方運輸局長 運輸監理部長 第十二条 | 第十二条 | 0/129; 覆った語=∅ |
| 178 | no_junk → no_junk_specificity | 森林法施行法第九条 | 遅滞な 組織変更 第七条 | 第七条 | 0/329; 覆った語=∅ |
| 180 | no_junk → no_junk_specificity | 小坂誠 | 対横浜5回戦 代打 巨人 | 巨人 | 0/99; 覆った語=∅ |
| 181 | no_junk → no_junk_specificity | 難民認定法第四十八条 | 口頭審理 認定 異議 | 認定 | 0/37; 覆った語=∅ |
| 182 | no_junk → no_junk_specificity | 斜辺 | 共有 cd 合同 | 共有 | 0/50; 覆った語=∅ |
| 183 | no_junk → no_junk_specificity | 宗教法人法第三条 | 境内建物 目的 規定 | 目的 | 1/775; 覆った語=規定 |
| 184 | no_junk → no_junk_specificity | 戸籍法施行規則第六十条 | 漢字 常用漢字表 括弧書き | 漢字 | 0/190; 覆った語=∅ |
| 185 | no_junk → no_junk_specificity | 労働関係調整法第三十五条 | 当事者 双方 労働争議 | 当事者 | 0/212; 覆った語=∅ |
| 187 | no_junk → no_junk_specificity | 船員法第百四条 | 規定 基準 市町村 | 規定 | 1/1354; 覆った語=基準 |
| 188 | no_junk → no_junk_specificity | 認識論的問題 | 性質 法 見な | 性質 | 1/546; 覆った語=見な |
| 189 | no_junk → no_junk_specificity | 計算証明規則第十六条 | 歳入 競争契約 書類 | 歳入 | 0/15; 覆った語=∅ |
| 190 | no_junk → no_junk_specificity | 物価統制令第三十五条 | 規定ニ 第十二条 違反シタル | 第十二条 | 0/129; 覆った語=∅ |
| 194 | no_junk → no_junk_specificity | 航空法施行規則第百九十四条 | 物件 輸送禁止 火薬類火薬 | 物件 | 0/7; 覆った語=∅ |
| 195 | no_junk → no_junk_specificity | 地方税法第三百一条 | 虚偽 規定 前条第一項 | 虚偽 | 0/5; 覆った語=∅ |
| 196 | no_junk → no_junk_specificity | ゲームエンジン | 作業 不在 主流 | 作業 | 0/266; 覆った語=∅ |
| 197 | no_junk → no_junk_specificity | 学校基本調査規則第四条 | 時期 学齢児童生徒 卒業者 | 時期 | 0/225; 覆った語=∅ |
| 198 | no_junk → no_junk_specificity | 合名会社等再建整備令第四条 | 適用 必要 整備計画 | 適用 | 0/258; 覆った語=∅ |
| 199 | no_junk → no_junk_specificity | 地方税法施行令第九条 | 適格合併等 規定 同項 | 規定 | 1/1354; 覆った語=同項 |
| 200 | no_junk → no_junk_specificity | 規制機関 | 実質的 控 国 | 実質的 | 0/6; 覆った語=∅ |
| 201 | no_junk → no_junk_specificity | 水産業協同組合法第百十六条 | 次条第一項 規定 六十一 | 規定 | 0/1354; 覆った語=∅ |
| 202 | no_junk → no_junk_specificity | ニュースゾーン | 広瀬麻知子 番組 4年間担当 | 番組 | 0/497; 覆った語=∅ |
| 203 | no_junk → no_junk_specificity | dominator | anniversary 追加生産 th | 音楽 | 2/764; 覆った語=anniversary,th |
| 204 | no_junk → no_junk_specificity | 桧垣良成 | 展開 カント 日本哲学会 | 展開 | 0/38; 覆った語=∅ |
| 205 | no_junk → no_junk_specificity | 民法第三百六十六条 | 質権者 金銭 質権 | 債権者 | 2/127; 覆った語=質権,金銭 |
| 206 | no_junk → no_junk_specificity | サンダル | 着用可能な 品物 ハイヒール | 品物 | 0/31; 覆った語=∅ |
| 208 | no_junk → no_junk_specificity | 気象業務法施行規則第二十九条 | 法第二十四条 記載 指定試験機関 | 記載 | 0/207; 覆った語=∅ |
| 209 | no_junk → no_junk_specificity | 冥王星 | 定義 system solar | 定義 | 0/853; 覆った語=∅ |
| 212 | no_junk → no_junk_specificity | 接地 | 広義 日本 必 | 広義 | 1/117; 覆った語=必 |
| 213 | no_junk → no_junk_specificity | 波長分布 | 照明下 太陽光線 異な | 異な | 0/97; 覆った語=∅ |
| 214 | no_junk → no_junk_specificity | 海面漁業生産統計調査規則第十条 | 集計結果 都道府県別 送付 | 送付 | 0/2; 覆った語=∅ |
| 215 | no_junk → no_junk_specificity | 道路運送車両法施行規則第三十六条 | 当該自動車 新規検査 申請 | 申請 | 0/131; 覆った語=∅ |
| 216 | no_junk → no_junk_specificity | 法律附則第四条 | 外務公務員 在外公館 名称 | 名称 | 0/427; 覆った語=∅ |
| 218 | no_junk → no_junk_specificity | 予防課 | 救急課 原子力規制庁原子力規制企画課火災対策室な 執行 | 執行 | 0/74; 覆った語=∅ |
| 219 | no_junk → no_junk_specificity | 薬事法距離制限違憲判決 | 最高裁判所 態様 弊害 | 最高裁判所 | 0/240; 覆った語=∅ |
| 222 | no_junk → no_junk_specificity | 班田収授 | 理由 大隅な 墾田 | 理由 | 0/559; 覆った語=∅ |
| 223 | no_junk → no_junk_specificity | 南満洲鉄道附属地煙草税令 | 廃止 満洲国ニ 勅令中改正等ノ | 廃止 | 0/94; 覆った語=∅ |
| 224 | no_junk → no_junk_specificity | psa | 言語全体 談話的 関係 | 関係 | 0/898; 覆った語=∅ |
| 225 | no_junk → no_junk_specificity | 言語学的な | 民族 人 理論 | 民族 | 1/92; 覆った語=人 |
| 226 | no_junk → no_junk_specificity | 貿易保険法第十条 | 職員 次条 法人 | 職員 | 0/196; 覆った語=∅ |
| 227 | no_junk → no_junk_specificity | 教科用図書検定調査審議会令附則第二条 | 政令 施行 教科用図書検定調査審議会 | 政令 | 0/42; 覆った語=∅ |
| 228 | no_junk → no_junk_specificity | 科学研究費助成事業 | 工学 再生 日本学術振興会 | 工学 | 0/160; 覆った語=∅ |
| 229 | no_junk → no_junk_specificity | 内航海運業法第十八条 | 登録 国土交通大臣 届出 | 登録 | 1/57; 覆った語=届出 |
| 230 | no_junk → no_junk_specificity | 口角 | 左右非対称 左右対称 協調運動 | 説明 | 1/355; 覆った語=左右対称 |
| 232 | no_junk → no_junk_specificity | 一般名 | 語 アルキル 続 | 反復 | 2/47; 覆った語=続,語 |
| 233 | no_junk → no_junk_specificity | r1 | 存在 住宅数 依然 | 存在 | 0/623; 覆った語=∅ |
| 234 | no_junk → no_junk_specificity | 火薬類取締法施行規則第八十三条 | 取扱者 制限 経済産業省令 | 制限 | 0/269; 覆った語=∅ |
| 235 | no_junk → no_junk_specificity | 農業工学技術者 | 土地改良技術者 研究機関な 商品 | 商品 | 0/71; 覆った語=∅ |
| 236 | no_junk → no_junk_specificity | ランベルト | 吸光度 存在量 求 | 等価幅 | 2/106; 覆った語=存在量,求 |
| 237 | no_junk → no_junk_specificity | 漁船法第二十七条 | 漁船用機械 試験 設計 | 設計 | 0/213; 覆った語=∅ |
| 238 | no_junk → no_junk_specificity | 現存社会 | マルクス 経済理論 社会科学 | マルクス | 0/80; 覆った語=∅ |
| 239 | no_junk → no_junk_specificity | 生活保護法第四十四条 | 都道府県知事 管理者 立入検査 | 都道府県知事 | 0/116; 覆った語=∅ |
| 241 | no_junk → no_junk_specificity | タミール | 発音 地名な 思 | 発音 | 0/133; 覆った語=∅ |
| 242 | no_junk → no_junk_specificity | 日本銀行政府有価証券取扱規程第三十四条 | 第二十八条ノ 於テ 日本銀行ニ | 第五条 | 2/393; 覆った語=於テ,日本銀行ニ |
| 243 | no_junk → no_junk_specificity | 条約第六条 | 担任スヘシ 左ノ 以テ | 第一条 | 2/736; 覆った語=以テ,左ノ |
| 245 | no_junk → no_junk_specificity | 速度分布 | 分布関数 温度 従い | 温度 | 0/249; 覆った語=∅ |
| 251 | no_junk → no_junk_specificity | 貿易保険法第六十九条 | 該当 保険契約 海外投資 | 該当 | 0/42; 覆った語=∅ |
| 252 | no_junk → no_junk_specificity | 音楽関連 | 同県 沖縄県 決定 | 決定 | 0/204; 覆った語=∅ |
| 253 | no_junk → no_junk_specificity | 海上運送法第三十四条 | 船員確保基本方針 第一条 船舶法 | 第一条 | 0/736; 覆った語=∅ |
| 254 | no_junk → no_junk_specificity | 公職選挙法施行令第百四十四条 | 政令 国勢調査 公示 | 政令 | 0/42; 覆った語=∅ |
| 256 | no_junk → no_junk_specificity | 地方税法施行令附則第十八条 | 譲渡所得等 金額 特例 | 金額 | 0/115; 覆った語=∅ |
| 258 | no_junk → no_junk_specificity | 第五十九条 | 禁止 意見聴取 提出 | 禁止 | 0/74; 覆った語=∅ |
| 259 | no_junk → no_junk_specificity | 健康保険法施行令第四十三条 | 支給 薬局 保険医療機関 | 支給 | 0/17; 覆った語=∅ |
| 261 | no_junk → no_junk_specificity | 引受先 | 答弁 検討 縦割 | 政府 | 2/1156; 覆った語=検討,答弁 |
| 262 | no_junk → no_junk_specificity | 金融機関再建整備法施行規則第二十三条 | 評価 記載 金融機関 | 評価 | 0/223; 覆った語=∅ |
| 263 | no_junk → no_junk_specificity | 母体 | 性感染症 含 ヒト | ヒト | 0/287; 覆った語=∅ |
| 264 | no_junk → no_junk_specificity | 地方税法第六百八十六条 | 更正 前条第二項 規定 | 六十六 | 3/119; 覆った語=前条第二項,更正,規定 |
| 265 | no_junk → no_junk_specificity | 船員職業安定法附則第二十八条 | 政令 罰則 法律 | 政令 | 1/42; 覆った語=法律 |
| 266 | no_junk → no_junk_specificity | 航空法第百十九条 | 六月以内 国土交通大臣 該当 | 六十三 | 3/150; 覆った語=六月以内,国土交通大臣,該当 |
| 268 | no_junk → no_junk_specificity | 劇性 | 強い 指定 法令 | 必要 | 3/1677; 覆った語=強い,指定,法令 |
| 269 | no_junk → no_junk_specificity | 土地改良法第四十三条 | 資格 承継 決済 | 資格 | 0/78; 覆った語=∅ |
| 272 | no_junk → no_junk_specificity | 健康保険法施行規則第八十三条 | 給付 規定 記載 | 五十九 | 3/134; 覆った語=給付,規定,記載 |
| 273 | no_junk → no_junk_specificity | 的基礎 | 接点 多い 批判 | 接点 | 0/14; 覆った語=∅ |
| 276 | no_junk → no_junk_specificity | 皇后 | 巡幸中 散策 庭 | 散策 | 0/7; 覆った語=∅ |
| 277 | no_junk → no_junk_specificity | 法学者ウルピアヌス | 公法 西洋法学 利益 | 国家 | 2/345; 覆った語=公法,利益 |
| 279 | no_junk → no_junk_specificity | iosアプリ | 配信 production 制作 | 配信 | 1/142; 覆った語=制作 |
| 281 | no_junk → no_junk_specificity | 公有水面埋立法第三条 | 其ノ 遅滞ナク 掲グル | 第三条 | 3/669; 覆った語=其ノ,掲グル,遅滞ナク |
| 282 | no_junk → no_junk_specificity | テープ | 主 使 作成 | キャッチコピー | 3/97; 覆った語=主,作成,使 |
| 283 | no_junk → no_junk_specificity | 在外公館等借入金返済実施規程第一条 | 法律 返済 規程 | 法律 | 0/1374; 覆った語=∅ |
| 284 | no_junk → no_junk_specificity | キノリニウムベタイン | 血赤色 負 青色 | 青色 | 0/633; 覆った語=∅ |
| 285 | no_junk → no_junk_specificity | 国土調査法施行令第十六条 | 認証 請求 成果 | 認証 | 0/31; 覆った語=∅ |
| 286 | no_junk → no_junk_specificity | 気象業務法第四十六条 | 違反 該当 第九条 | 違反 | 0/100; 覆った語=∅ |
| 288 | no_junk → no_junk_specificity | 301条提訴 | 件数 判断 交渉 | 件数 | 0/44; 覆った語=∅ |
| 289 | no_junk → no_junk_specificity | 港湾法第四十一条 | 構築物 改築等 有害構築物 | 構築物 | 0/4; 覆った語=∅ |
| 290 | no_junk → no_junk_specificity | 生活保護法施行令第三条 | 教育扶助 特例 親権者 | 特例 | 0/38; 覆った語=∅ |
| 291 | no_junk → no_junk_specificity | 公職選挙法第五十五条 | 開票管理者 送致 投票立会人 | 法律第十四条 | 2/282; 覆った語=投票立会人,開票管理者 |
| 292 | no_junk → no_junk_specificity | 元来 | 化学構造な 仏 動詞 | 動詞 | 0/191; 覆った語=∅ |
| 293 | no_junk → no_junk_specificity | メンタルケア | 理想的な 最適 社会 | 理想的な | 0/4; 覆った語=∅ |
| 294 | no_junk → no_junk_specificity | 宗教法人法第五十二条 | 規則 認証書 交付 | 規則 | 0/183; 覆った語=∅ |
| 295 | no_junk → no_junk_specificity | 解決方法 | 利点 元 オブザーバブル | 利点 | 0/233; 覆った語=∅ |
| 296 | no_junk → no_junk_specificity | 同居 | 親族以外 適用除外 他人 | 他人 | 0/102; 覆った語=∅ |
| 297 | no_junk → no_junk_specificity | 武器等製造法附則第九条 | 罰則 行為 施行前 | 罰則 | 1/175; 覆った語=行為 |
| 298 | no_junk → no_junk_specificity | 離島航路整備法施行規則第二条 | 国土交通大臣 航路補助金 申請 | 国土交通大臣 | 0/61; 覆った語=∅ |
| 299 | no_junk → no_junk_specificity | 反三木派 | 椎名 批判 政権主流派 | 批判 | 0/347; 覆った語=∅ |

## junk 除去で棄権から誤答に変わった問いの全件追跡

該当 14 件、同じ裁定で棄権に戻った 12 件、誤答のまま 2 件。

| id | gold | 問い | 現行 | junk除去 | junk除去＋裁定 | 被覆 |
| --- | --- | --- | --- | --- | --- | --- |
| 18 | 農業保険法第二十八条 | 選任等 農業共済組合 設立準備会 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 中小漁業融資保証法第四十七条 | wrong / ANSWER / 中小漁業融資保証法第四十七条 | 2/10; 覆った語=設立準備会,選任等 |
| 29 | 私立学校法第六十五条 | 欠員 辞任 満了 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 社会福祉法第四十二条 | wrong / ANSWER / 社会福祉法第四十二条 | 3/10; 覆った語=欠員,満了,辞任 |
| 31 | 都市ガス | 支障 店舗 復旧 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 支障 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ |
| 45 | 国土調査法第三十七条 | 実施 第二十三条 国土調査 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 第二十三条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ |
| 52 | 地方税法第五百九十一条 | 虚偽 手段 特別土地保有税 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 虚偽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ |
| 65 | 資産再評価法施行令第一条 | 減価償却資産 帳簿価額 取得価額 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 取得価額 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |
| 83 | 相続税法第二十七条 | 相続税 贈与 相続 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 相続税 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/8; 覆った語=∅ |
| 174 | 健康保険法施行規則第百三十四条 | 第三十三条 第五十八条 第六十一条 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 第三十三条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/15; 覆った語=∅ |
| 259 | 健康保険法施行令第四十三条 | 支給 薬局 保険医療機関 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 支給 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/17; 覆った語=∅ |
| 276 | 皇后 | 巡幸中 散策 庭 | refusal / AMBIGUOUS / — | wrong / ANSWER / 散策 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/7; 覆った語=∅ |
| 288 | 301条提訴 | 件数 判断 交渉 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 件数 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/44; 覆った語=∅ |
| 290 | 生活保護法施行令第三条 | 教育扶助 特例 親権者 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 特例 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ |
| 291 | 公職選挙法第五十五条 | 開票管理者 送致 投票立会人 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 法律第十四条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/282; 覆った語=投票立会人,開票管理者 |
| 293 | メンタルケア | 理想的な 最適 社会 | refusal / UNKNOWN_NO_EVIDENCE / — | wrong / ANSWER / 理想的な | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |

## 全探針（棄権・無変化も省略しない）

| id | gold | 問い | baseline | specificity | 現行核の被覆 | no_junk | no_junk_specificity | 除去後核の被覆 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 西浦泰介 | 崩壊挙動 崩壊過程 被覆ブロック | correct / ANSWER / 西浦泰介 | correct / ANSWER / 西浦泰介 | 3/18; 覆った語=崩壊挙動,崩壊過程,被覆ブロック | correct / ANSWER / 西浦泰介 | correct / ANSWER / 西浦泰介 | 3/18; 覆った語=崩壊挙動,崩壊過程,被覆ブロック |
| 1 | 専用 | 施工機 回転 深 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 2 | 温泉法第十六条 | 許可 法人 前条第一項 | wrong / ANSWER / 許可 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/164; 覆った語=∅ | wrong / ANSWER / 許可 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/164; 覆った語=∅ |
| 3 | ジアダ | シュタイナー シャーロック シャングリラ | wrong / ANSWER / ゴリー | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/33; 覆った語=シャーロック | wrong / ANSWER / ゴリー | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/33; 覆った語=シャーロック |
| 4 | 職業安定法 | 昭和23年3月2日基発381号 広 排除 | wrong / ANSWER / 広 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/505; 覆った語=∅ | wrong / ANSWER / 排除 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |
| 5 | 第18条 | 任命 二級 夜勤手当 | wrong / ANSWER / 九 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/2860; 覆った語=任命,夜勤手当 | correct / ANSWER / 第18条 | correct / ANSWER / 第18条 | 3/23; 覆った語=二級,任命,夜勤手当 |
| 6 | 水防法第三十八条 | 消防機関 業務 水防団等 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 7 | 先住部族 | 紀元前2千年紀後半 長方形頭 頭 | wrong / ANSWER / 頭 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/40; 覆った語=∅ | correct / ANSWER / 先住部族 | correct / ANSWER / 先住部族 | 2/12; 覆った語=長方形頭,頭 |
| 8 | 金融商品取引法第六十条 | 第五十八条 規定 売買 | wrong / ANSWER / 四 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/6394; 覆った語=売買,第五十八条,規定 | wrong / ANSWER / 十三 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/2011; 覆った語=売買,第五十八条,規定 |
| 9 | 本居宣長 | 指摘 壬申 国学 | wrong / ANSWER / 指摘 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/47; 覆った語=∅ | wrong / ANSWER / 指摘 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/47; 覆った語=∅ |
| 10 | 民事調停法第二十条 | 職権 管轄裁判所 調停 | wrong / ANSWER / 職権 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/36; 覆った語=∅ | wrong / ANSWER / 職権 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/36; 覆った語=∅ |
| 11 | 勲章褫奪令施行細則第五条 | 褒章ノ 準用ス 記章 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 勲章褫奪令施行細則第五条 | correct / ANSWER / 勲章褫奪令施行細則第五条 | 3/8; 覆った語=準用ス,褒章ノ,記章 |
| 12 | 牧野法施行規則第十八条 | 書類 添附 届出 | wrong / ANSWER / 書類 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/33; 覆った語=∅ | wrong / ANSWER / 書類 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/33; 覆った語=∅ |
| 13 | 症例報告 | 哲学的思考実験 中 実証的 | wrong / ANSWER / 中 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/498; 覆った語=∅ | correct / ANSWER / 症例報告 | correct / ANSWER / 症例報告 | 3/29; 覆った語=中,哲学的思考実験,実証的 |
| 14 | 次男 | 出 報告 圧 | wrong / ANSWER / 出 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/106; 覆った語=∅ | wrong / ANSWER / 食品 | wrong / ANSWER / 食品 | 2/11; 覆った語=出,報告 |
| 15 | テンペレートファージ | 可能性 拡散 得 | wrong / ANSWER / 可能性 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/710; 覆った語=∅ | wrong / ANSWER / 可能性 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/710; 覆った語=∅ |
| 16 | 鉱業法施行規則第十五条 | 期日 競願 準用 | wrong / ANSWER / 準用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/61; 覆った語=∅ | wrong / ANSWER / 準用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/61; 覆った語=∅ |
| 17 | 商法第六百八十五条 | 従物 書式 推定等 | wrong / ANSWER / 書式 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/50; 覆った語=∅ | wrong / ANSWER / 書式 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/50; 覆った語=∅ |
| 18 | 農業保険法第二十八条 | 選任等 農業共済組合 設立準備会 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 中小漁業融資保証法第四十七条 | wrong / ANSWER / 中小漁業融資保証法第四十七条 | 2/10; 覆った語=設立準備会,選任等 |
| 19 | 関連企業 | インド アイグループ software | wrong / ANSWER / インド | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/203; 覆った語=∅ | wrong / ANSWER / インド | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/203; 覆った語=∅ |
| 20 | 保安基準第二十二条 | 道路運送車両 着席 空間 | wrong / ANSWER / 空間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/112; 覆った語=∅ | wrong / ANSWER / 空間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/112; 覆った語=∅ |
| 21 | 文化財保護法第百三十五条 | 選定 重要文化的景観 解除 | wrong / ANSWER / 選定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ | wrong / ANSWER / 選定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ |
| 22 | p.w.atkins | 東京化学同人 元裕 物理化学 | wrong / ANSWER / 物理化学 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/19; 覆った語=∅ | wrong / ANSWER / 物理化学 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/19; 覆った語=∅ |
| 23 | 宮本隆司 | 撮影 建設過程 過程 | wrong / ANSWER / 当初 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/953; 覆った語=撮影,過程 | wrong / ANSWER / 当初 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/953; 覆った語=撮影,過程 |
| 24 | 第三回四分利付英貨公債発行規程第八条 | 日本国ノ 関スル 間ニ | wrong / ANSWER / 二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/14025; 覆った語=関スル | wrong / ANSWER / 第七条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/329; 覆った語=日本国ノ,間ニ,関スル |
| 25 | 立方体 | 投影図 座標軸 単面投影 | wrong / ANSWER / 投影図 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/18; 覆った語=∅ | wrong / ANSWER / 投影図 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/18; 覆った語=∅ |
| 26 | 鉱山保安法第二条 | 鉱業権者 法律 租鉱権者 | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1374; 覆った語=∅ | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1374; 覆った語=∅ |
| 27 | 無尽業法施行細則第十四条 | 効力ヲ 認可ハ 其ノ | wrong / ANSWER / 二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/14025; 覆った語=其ノ,効力ヲ | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 28 | 地方自治法施行規則第十二条 | 監査委員 特別区 選挙管理委員 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 29 | 私立学校法第六十五条 | 欠員 辞任 満了 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 社会福祉法第四十二条 | wrong / ANSWER / 社会福祉法第四十二条 | 3/10; 覆った語=欠員,満了,辞任 |
| 30 | 浅田 | プロフィギュアスケーター バカ 日放送 | wrong / ANSWER / バラエティ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/806; 覆った語=バカ,日放送 | wrong / ANSWER / バラエティ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/806; 覆った語=バカ,日放送 |
| 31 | 都市ガス | 支障 店舗 復旧 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 支障 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ |
| 32 | 外務公務員法施行令第一条 | 申出 規定 第八条第一項 | wrong / ANSWER / 十七 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1460; 覆った語=申出,第八条第一項,規定 | wrong / ANSWER / 十七 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1460; 覆った語=申出,第八条第一項,規定 |
| 33 | 道路運送法施行規則附則第七条 | 経過措置 登録事項 規定 | wrong / ANSWER / 四 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/6394; 覆った語=登録事項,経過措置,規定 | wrong / ANSWER / 経過措置 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/32; 覆った語=∅ |
| 34 | 連帯債務 | 支払い 求償 d | wrong / ANSWER / 支払い | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/21; 覆った語=∅ | wrong / ANSWER / 支払い | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/21; 覆った語=∅ |
| 35 | 多倍数種 | 既知 植物属 約半数 | wrong / ANSWER / 既知 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/8; 覆った語=∅ | wrong / ANSWER / 既知 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/8; 覆った語=∅ |
| 36 | 欧米 | information 近代刑法 テレホンカード | correct / ANSWER / 欧米 | correct / ANSWER / 欧米 | 3/41; 覆った語=information,テレホンカード,近代刑法 | correct / ANSWER / 欧米 | correct / ANSWER / 欧米 | 3/41; 覆った語=information,テレホンカード,近代刑法 |
| 37 | 商法第五百七十七条 | 種類 荷送人 運送 | wrong / ANSWER / 種類 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/300; 覆った語=∅ | wrong / ANSWER / 種類 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/300; 覆った語=∅ |
| 38 | 情報産業 | 合 更 構築サービスな | wrong / ANSWER / 超銀河団 | wrong / ANSWER / 超銀河団 | 2/28; 覆った語=合,更 | wrong / ANSWER / 超銀河団 | wrong / ANSWER / 超銀河団 | 2/28; 覆った語=合,更 |
| 39 | 法的規制 | 軽 枠組 売 | wrong / ANSWER / 軽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/13; 覆った語=∅ | correct / ANSWER / 法的規制 | correct / ANSWER / 法的規制 | 3/12; 覆った語=売,枠組,軽 |
| 40 | 建築物な | 適用 局部等電位化 機器 | wrong / ANSWER / 基準 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/362; 覆った語=機器,適用 | wrong / ANSWER / 基準 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/362; 覆った語=機器,適用 |
| 41 | 宝月誠 | 思想 社会的背景 初期シカゴ | wrong / ANSWER / 思想 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/264; 覆った語=∅ | wrong / ANSWER / 思想 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/264; 覆った語=∅ |
| 42 | ヘロン | mechanica company e | correct / ANSWER / ヘロン | correct / ANSWER / ヘロン | 3/50; 覆った語=company,e,mechanica | correct / ANSWER / ヘロン | correct / ANSWER / ヘロン | 3/50; 覆った語=company,e,mechanica |
| 43 | 計算証明規則第七十条 | 通則法 証明責任者 第二条第一項 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 44 | 恩給法附則第百六十一条 | 処分庁 行政庁 施行日前 | wrong / ANSWER / 処分庁 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/87; 覆った語=行政庁 | wrong / ANSWER / 処分庁 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/87; 覆った語=行政庁 |
| 45 | 国土調査法第三十七条 | 実施 第二十三条 国土調査 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 第二十三条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ |
| 46 | 石材 | 3トン 34メートル 5トン | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 47 | 通説 | 1行 ドイツ 不可罰 | wrong / ANSWER / ドイツ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/550; 覆った語=∅ | wrong / ANSWER / ドイツ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/550; 覆った語=∅ |
| 48 | 家畜保健衛生所法附則第百六十一条 | 行政庁 処分 経過措置 | wrong / ANSWER / 行政庁 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/249; 覆った語=処分 | wrong / ANSWER / 行政庁 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/249; 覆った語=処分 |
| 49 | 両親 | 以来 人工呼吸器 ドイツ | wrong / ANSWER / 以来 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ | wrong / ANSWER / 以来 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ |
| 50 | psycho-pass | 名前 タイトル sinners | wrong / ANSWER / 名前 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/405; 覆った語=タイトル | wrong / ANSWER / 名前 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/405; 覆った語=タイトル |
| 51 | 医学教育 | 場 国 制度 | wrong / ANSWER / 場 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/223; 覆った語=∅ | wrong / ANSWER / 国民 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/359; 覆った語=制度,国,場 |
| 52 | 地方税法第五百九十一条 | 虚偽 手段 特別土地保有税 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 虚偽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ |
| 53 | 壁新聞 | ニュース 総合博物館 寄贈 | wrong / ANSWER / ニュース | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/86; 覆った語=∅ | wrong / ANSWER / ニュース | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/86; 覆った語=∅ |
| 54 | 言語学者 | ヤーコブソン ムカジョフスキー ヨセフ | correct / ANSWER / 言語学者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/73; 覆った語=ムカジョフスキー,ヤーコブソン,ヨセフ | correct / ANSWER / 言語学者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/73; 覆った語=ムカジョフスキー,ヤーコブソン,ヨセフ |
| 55 | 海上運送法第二十九条 | 締結 変更 国土交通大臣 | wrong / ANSWER / 五十 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/158; 覆った語=国土交通大臣,変更,締結 | wrong / ANSWER / 五十 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/158; 覆った語=国土交通大臣,変更,締結 |
| 56 | 京都府特殊物件処理委員会 | 応急利用等 措置 政府 | wrong / ANSWER / 政府 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1156; 覆った語=措置 | wrong / ANSWER / 政府 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1156; 覆った語=措置 |
| 57 | 社会福祉法第四十一条 | 終了 定款 最終 | wrong / ANSWER / 八 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/3276; 覆った語=定款,最終,終了 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 58 | 土地家屋調査士法第十四条 | 調査士 登録 所属 | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/57; 覆った語=∅ | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/57; 覆った語=∅ |
| 59 | 液体ヘリウム | クエンチ t 不要 | wrong / ANSWER / クエンチ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/18; 覆った語=∅ | wrong / ANSWER / クエンチ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/18; 覆った語=∅ |
| 60 | 人為 | 語 自然 加 | wrong / ANSWER / 語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1089; 覆った語=加 | wrong / ANSWER / ランドスケープ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/202; 覆った語=加,自然,語 |
| 61 | 保安法第五十条 | 経過 政令 更新 | wrong / ANSWER / 経過 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/61; 覆った語=更新 | wrong / ANSWER / 経過 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/61; 覆った語=更新 |
| 62 | 近畿大学 | 理学科 約1億38万円 退職者約563人 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 63 | 傷病者 | 屋外階段 回復 徴候 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 傷病者 | correct / ANSWER / 傷病者 | 3/34; 覆った語=回復,屋外階段,徴候 |
| 64 | 無線局免許手続規則第二十七条 | 記録 別表第十号 許可記録 | wrong / ANSWER / 記録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/261; 覆った語=∅ | wrong / ANSWER / 記録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/261; 覆った語=∅ |
| 65 | 資産再評価法施行令第一条 | 減価償却資産 帳簿価額 取得価額 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 取得価額 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |
| 66 | 16組 | 放送 披露 本番 | wrong / ANSWER / 放送 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/543; 覆った語=∅ | wrong / ANSWER / 放送 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/543; 覆った語=∅ |
| 67 | 放送法施行規則第百十条 | 送信空中線 近接 起因 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 放送法施行規則第百十条 | correct / ANSWER / 放送法施行規則第百十条 | 3/10; 覆った語=起因,近接,送信空中線 |
| 68 | 完了後 | ポルトガル 言語純化運動 教徒 | wrong / ANSWER / 単語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/309; 覆った語=ポルトガル,教徒 | wrong / ANSWER / 単語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/309; 覆った語=ポルトガル,教徒 |
| 69 | コーンフォード | 哲学史観 理性化 生 | wrong / ANSWER / 生 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/120; 覆った語=∅ | correct / ANSWER / コーンフォード | correct / ANSWER / コーンフォード | 3/14; 覆った語=哲学史観,理性化,生 |
| 70 | 接近欲求 | 発言内容 無意識 隷属 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 71 | 漁船損害等補償法第四十条 | 連署 組合員 総組合員 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 72 | 運河法第四条 | 否ニ 妨アリヤ 運河ノ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 運河法第四条 | correct / ANSWER / 運河法第四条 | 3/8; 覆った語=否ニ,妨アリヤ,運河ノ |
| 73 | 4号機 | 大幅続落 605円15銭 放射能汚染 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 74 | 首脳 | フランス 冬季大会 抗議 | wrong / ANSWER / フランス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/332; 覆った語=∅ | wrong / ANSWER / フランス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/332; 覆った語=∅ |
| 75 | 理論生物学 | 行動 定量的 形質 | wrong / ANSWER / 行動 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/292; 覆った語=形質 | wrong / ANSWER / 行動 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/292; 覆った語=形質 |
| 76 | chemrxiv | 化学関連分野 投稿 未発表プレプリント | wrong / ANSWER / 投稿 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/37; 覆った語=∅ | wrong / ANSWER / 投稿 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/37; 覆った語=∅ |
| 77 | 高橋 | 法律学小辞典 光男 小早川 | wrong / ANSWER / 小早川 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ | wrong / ANSWER / 小早川 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ |
| 78 | 哲学的考察 | 問題 妊娠中絶 影響 | wrong / ANSWER / 問題 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1270; 覆った語=影響 | wrong / ANSWER / 問題 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1270; 覆った語=影響 |
| 79 | 鉱業登録令第五十条 | 試掘権 登録 試掘権等 | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/57; 覆った語=∅ | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/57; 覆った語=∅ |
| 80 | 系譜 | 地名 成立 始 | wrong / ANSWER / 地名 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/134; 覆った語=∅ | wrong / ANSWER / 地名 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/134; 覆った語=∅ |
| 81 | スコットランド | マリウス 国際博物館設計競技 常識学派 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 82 | 船用品試験機試験規程第二十条 | 精度ノ 適当ニ 試験ハ | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 83 | 相続税法第二十七条 | 相続税 贈与 相続 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 相続税 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/8; 覆った語=∅ |
| 84 | 道路運送法第五条 | 記載 提出 許可 | wrong / ANSWER / 記載 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/207; 覆った語=提出 | wrong / ANSWER / 記載 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/207; 覆った語=提出 |
| 85 | 鉱業登録令第二十四条 | 租鉱区 申請書 鉱区 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 86 | 森林法第二条 | 法律 土地 立木竹 | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1374; 覆った語=土地 | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1374; 覆った語=土地 |
| 87 | 昭和41年政令第376号 | 日 政令 記念 | wrong / ANSWER / 日 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/314; 覆った語=記念 | wrong / ANSWER / 金田一春彦 | wrong / ANSWER / 金田一春彦 | 2/29; 覆った語=日,記念 |
| 88 | 保安法第二十一条 | 都道府県知事 高圧ガス 製造 | wrong / ANSWER / 都道府県知事 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/116; 覆った語=∅ | wrong / ANSWER / 都道府県知事 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/116; 覆った語=∅ |
| 89 | 岩田圭一 | 目的論 エンテレケイア pdf | wrong / ANSWER / アリストテレス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/428; 覆った語=エンテレケイア,目的論 | wrong / ANSWER / アリストテレス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/428; 覆った語=エンテレケイア,目的論 |
| 90 | 覚醒剤取締法第三十三条 | 第三十条 覚醒剤監視員 廃棄 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 91 | 会計令第百二十条 | 職員 収納 出納計算書 | wrong / ANSWER / 職員 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ | wrong / ANSWER / 職員 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ |
| 92 | リニューアル | 150円 19時枠 ストロー | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 93 | 健康保険法施行規則第百六十七条 | 範囲 特定健康保険組合 策定 | wrong / ANSWER / 範囲 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/452; 覆った語=∅ | wrong / ANSWER / 範囲 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/452; 覆った語=∅ |
| 94 | 農地法施行規則第七十三条 | 農業者 農林水産省令 規定 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ |
| 95 | 聖蹟指定 | 本格化 目的 濃 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/775; 覆った語=∅ | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/775; 覆った語=∅ |
| 96 | 鉱業法施行規則第二十三条 | 設定 様式第十四 租鉱権 | wrong / ANSWER / 設定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/112; 覆った語=∅ | wrong / ANSWER / 設定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/112; 覆った語=∅ |
| 97 | 抗議活動 | グーシャ 深夜 市内 | wrong / ANSWER / グーシャ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/17; 覆った語=∅ | wrong / ANSWER / グーシャ | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/17; 覆った語=∅ |
| 98 | 証明機関 | 無線機 実施 指定制 | wrong / ANSWER / 無線機 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/43; 覆った語=∅ | wrong / ANSWER / 無線機 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/43; 覆った語=∅ |
| 99 | 古物営業法第四条 | 許可 該当 破産手続開始 | wrong / ANSWER / 許可 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/164; 覆った語=∅ | wrong / ANSWER / 許可 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/164; 覆った語=∅ |
| 100 | 論 | 中核 傾向 代表 | correct / ANSWER / 論 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/84; 覆った語=中核,代表,傾向 | wrong / ANSWER / 方式 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/279; 覆った語=代表,傾向 |
| 101 | 松波仁一郎 | 信山社 梅謙次郎校閲 穂積陳重 | correct / ANSWER / 松波仁一郎 | correct / ANSWER / 松波仁一郎 | 3/9; 覆った語=信山社,梅謙次郎校閲,穂積陳重 | correct / ANSWER / 松波仁一郎 | correct / ANSWER / 松波仁一郎 | 3/9; 覆った語=信山社,梅謙次郎校閲,穂積陳重 |
| 102 | 肺法 | 昭和35年3月31日 寄与 塵肺 | wrong / ANSWER / 寄与 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/40; 覆った語=∅ | wrong / ANSWER / 寄与 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/40; 覆った語=∅ |
| 103 | 瞬時電圧低下 | 概 多 多い | wrong / ANSWER / 基本的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/168; 覆った語=多,多い,概 | wrong / ANSWER / 基本的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/168; 覆った語=多,多い,概 |
| 104 | 商法第六百十四条 | 返還請求 寄託者 質入 | wrong / ANSWER / 寄託者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/65; 覆った語=返還請求 | wrong / ANSWER / 寄託者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/65; 覆った語=返還請求 |
| 105 | スピグル | 拡張 バルト 具体的な | wrong / ANSWER / 拡張 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ | wrong / ANSWER / 拡張 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ |
| 106 | 消費生活協同組合法施行規則第三十七条 | 同意 書面 四第六項 | wrong / ANSWER / 同意 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/36; 覆った語=∅ | wrong / ANSWER / 同意 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/36; 覆った語=∅ |
| 107 | 船舶安全法第十八条 | 拘禁刑又ハ 罰金ニ 各号ノ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 108 | 最高裁判所裁判官国民審査法施行令第三十条 | 前条 第二十二条 審査公報 | wrong / ANSWER / 第二十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/29; 覆った語=∅ | wrong / ANSWER / 第二十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/29; 覆った語=∅ |
| 109 | 規範的責任論 | 立場 学派的対立 対立 | wrong / ANSWER / 立場 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/265; 覆った語=∅ | wrong / ANSWER / 立場 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/265; 覆った語=∅ |
| 110 | 家畜商法附則第七条 | 会社法 役員 資格 | wrong / ANSWER / 会社法 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/66; 覆った語=∅ | wrong / ANSWER / 会社法 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/66; 覆った語=∅ |
| 111 | 健康保険法第百三十七条 | 通算 前四月間 出産育児一時金 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 112 | 落石 | 被害 発生 地震 | wrong / ANSWER / 被害 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/409; 覆った語=地震,発生 | wrong / ANSWER / 被害 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/409; 覆った語=地震,発生 |
| 113 | 工場抵当法第九条 | 為ス 為スニ 登記ヲ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 114 | 難民認定法第七十条 | 拘禁刑 各号 併科 | wrong / ANSWER / 拘禁刑 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ | wrong / ANSWER / 拘禁刑 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ |
| 115 | 航空法施行規則第百六十三条 | 組 機長 要件 | wrong / ANSWER / 組 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/43; 覆った語=∅ | wrong / ANSWER / 航空法第七十二条 | wrong / ANSWER / 航空法第七十二条 | 3/9; 覆った語=機長,組,要件 |
| 116 | アクチンフィラメント | 連結 参照 項 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 117 | 地方税法施行令第四十八条 | 給料 規定 第一号 | wrong / ANSWER / 二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/14025; 覆った語=第一号,給料,規定 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 118 | 沖野眞已各裁判官 | 国家賠償 放置 棄却 | wrong / ANSWER / 国家賠償 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/9; 覆った語=∅ | wrong / ANSWER / 国家賠償 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/9; 覆った語=∅ |
| 119 | 犯行 | 効果 初 密室状態 | wrong / ANSWER / 効果 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/501; 覆った語=∅ | wrong / ANSWER / 効果 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/501; 覆った語=∅ |
| 120 | 港則法施行規則第十八条 | 目的 規定 種類 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=規定 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=規定 |
| 121 | 地方税法附則第百四十三条 | 行為 附則 罰則 | wrong / ANSWER / 行為 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/794; 覆った語=∅ | wrong / ANSWER / 行為 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/794; 覆った語=∅ |
| 122 | イブ | 思想 持 傾き | wrong / ANSWER / 思想 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/264; 覆った語=持 | wrong / ANSWER / 思想 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/264; 覆った語=持 |
| 123 | 明石家電視台 | 6月1日放送分 放送 プレバト | wrong / ANSWER / 放送 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/543; 覆った語=∅ | wrong / ANSWER / 放送 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/543; 覆った語=∅ |
| 124 | 法律第百十条 | 法令 業務 選任 | wrong / ANSWER / 法令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/232; 覆った語=∅ | wrong / ANSWER / 法令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/232; 覆った語=∅ |
| 125 | 文化財保護法第八十六条 | 管理団体 規定 調査 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ |
| 126 | 中澤高志 | npo 困難性 地域経済学研究 | wrong / ANSWER / npo | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/26; 覆った語=∅ | wrong / ANSWER / npo | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/26; 覆った語=∅ |
| 127 | 執着 | 江戸 関西 真似 | wrong / ANSWER / 江戸 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/57; 覆った語=関西 | wrong / ANSWER / 江戸 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/57; 覆った語=関西 |
| 128 | 商法施行法第四十二条 | 従ヒテ 規定ニ 商法施行前ニ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 129 | 明 | 危険 労働強度 内 | wrong / ANSWER / 内 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/96; 覆った語=∅ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 130 | 山下法務大臣 | 収監先 死刑執行命令書 署名 | wrong / ANSWER / 署名 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/39; 覆った語=∅ | wrong / ANSWER / 署名 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/39; 覆った語=∅ |
| 131 | 嫌 | 受 人 付 | wrong / ANSWER / 受 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/202; 覆った語=∅ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 132 | 高畠通敏 | 筑摩書房 言語 第299号 | wrong / ANSWER / 言語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/755; 覆った語=∅ | wrong / ANSWER / 言語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/755; 覆った語=∅ |
| 133 | 商法第五百二十五条 | 当事者 日時 解除 | wrong / ANSWER / 十二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/2107; 覆った語=当事者,日時,解除 | wrong / ANSWER / 十二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/2107; 覆った語=当事者,日時,解除 |
| 134 | 個人情報保護法 | 全面施行 積極的プライバシー 成立 | wrong / ANSWER / 成立 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/149; 覆った語=∅ | wrong / ANSWER / 成立 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/149; 覆った語=∅ |
| 135 | 船舶区画規程第七十八条 | 機能 管装置 当該水密区画 | wrong / ANSWER / 機能 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/486; 覆った語=∅ | wrong / ANSWER / 機能 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/486; 覆った語=∅ |
| 136 | 三機能 | 現代性 聖職者 形成 | wrong / ANSWER / 形成 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/59; 覆った語=∅ | wrong / ANSWER / 形成 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/59; 覆った語=∅ |
| 137 | 住宅 | 住家 使用 住宅着工件数 | wrong / ANSWER / 使用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/633; 覆った語=∅ | wrong / ANSWER / 使用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/633; 覆った語=∅ |
| 138 | 数 | qubit octet rule | correct / ANSWER / 数 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/723; 覆った語=octet,qubit,rule | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 139 | 図書館法第二十六条 | 私立図書館 国 干渉 | wrong / ANSWER / 国 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/836; 覆った語=∅ | wrong / ANSWER / 干渉 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/40; 覆った語=∅ |
| 140 | 放送法施行規則第百四十八条 | 番組送出設備 業務 電気通信設備 | wrong / ANSWER / 業務 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/100; 覆った語=∅ | wrong / ANSWER / 業務 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/100; 覆った語=∅ |
| 141 | 再審請求中 | 少年死刑囚 傾向 強 | wrong / ANSWER / 傾向 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/517; 覆った語=強 | wrong / ANSWER / 傾向 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/517; 覆った語=強 |
| 142 | 自動車用静穏装置 | 逆位相 発生 騒音 | wrong / ANSWER / 発生 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ | wrong / ANSWER / 発生 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ |
| 143 | 有機化合物 | 初期 分析手法 個別 | wrong / ANSWER / 初期 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/229; 覆った語=∅ | wrong / ANSWER / 初期 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/229; 覆った語=∅ |
| 144 | 臨床的意義 | 半規管機能低下 意思決定 影響 | wrong / ANSWER / 影響 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/578; 覆った語=∅ | wrong / ANSWER / 影響 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/578; 覆った語=∅ |
| 145 | 文章 | 前ページ 力添 取 | correct / ANSWER / 文章 | correct / ANSWER / 文章 | 3/52; 覆った語=前ページ,力添,取 | correct / ANSWER / 文章 | correct / ANSWER / 文章 | 3/52; 覆った語=前ページ,力添,取 |
| 146 | 外国ニ | 外国 流通 取締り | wrong / ANSWER / 外国 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/82; 覆った語=∅ | wrong / ANSWER / 外国 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/82; 覆った語=∅ |
| 147 | アグロロジー | 一分野 助言 同義 | wrong / ANSWER / 人間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1073; 覆った語=一分野,同義 | wrong / ANSWER / 人間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1073; 覆った語=一分野,同義 |
| 148 | 牛山 | 東海大学出版会 光学 草川 | wrong / ANSWER / max | wrong / ANSWER / max | 3/15; 覆った語=光学,東海大学出版会,草川 | wrong / ANSWER / max | wrong / ANSWER / max | 3/15; 覆った語=光学,東海大学出版会,草川 |
| 149 | 外国貿易法第二十三条 | 対外直接投資 政令 第四項各号 | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ |
| 150 | 全図 | イリヤス 人体構造上 マンスール | correct / ANSWER / 全図 | correct / ANSWER / 全図 | 3/10; 覆った語=イリヤス,マンスール,人体構造上 | correct / ANSWER / 全図 | correct / ANSWER / 全図 | 3/10; 覆った語=イリヤス,マンスール,人体構造上 |
| 151 | 農産物検査法第十六条 | 農林水産大臣 事実 職員 | wrong / ANSWER / 三十八 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/369; 覆った語=事実,職員,農林水産大臣 | wrong / ANSWER / 三十八 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/369; 覆った語=事実,職員,農林水産大臣 |
| 152 | 保健師助産師看護師法施行規則第十三条 | 登録 法第十五条 第一号 | wrong / ANSWER / 十四 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1772; 覆った語=法第十五条,登録,第一号 | wrong / ANSWER / 十四 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1772; 覆った語=法第十五条,登録,第一号 |
| 153 | 金丸康信 | 原田由起彦 山梨県 務 | wrong / ANSWER / 山梨県 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/16; 覆った語=∅ | wrong / ANSWER / 山梨県 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/16; 覆った語=∅ |
| 154 | 神奈川人権センター | 日本 申 抗議 | wrong / ANSWER / 日本 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/2493; 覆った語=∅ | wrong / ANSWER / 日本 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/2493; 覆った語=∅ |
| 155 | 鉄道運輸規程第四十七条 | 託送スルニ 許諾ヲ 迄自己ノ | correct / ANSWER / 鉄道運輸規程第四十七条 | correct / ANSWER / 鉄道運輸規程第四十七条 | 3/8; 覆った語=託送スルニ,許諾ヲ,迄自己ノ | correct / ANSWER / 鉄道運輸規程第四十七条 | correct / ANSWER / 鉄道運輸規程第四十七条 | 3/8; 覆った語=託送スルニ,許諾ヲ,迄自己ノ |
| 156 | 旅行業法第三十二条 | 手配業 旅行サービス 禁止 | wrong / ANSWER / 禁止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ | wrong / ANSWER / 禁止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ |
| 157 | 砂防法第四十一条 | 義務ニ 此ノ 関シテハ | wrong / ANSWER / 第四条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/489; 覆った語=此ノ,関シテハ | wrong / ANSWER / 第四条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/489; 覆った語=此ノ,関シテハ |
| 158 | 三権 | 置 権力 立法 | wrong / ANSWER / 置 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/21; 覆った語=∅ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 159 | 民法第七百三十六条 | 養子 養親 間 | wrong / ANSWER / 養子 | wrong / ANSWER / 養子 | 2/33; 覆った語=間,養親 | wrong / ANSWER / 養子 | wrong / ANSWER / 養子 | 2/33; 覆った語=間,養親 |
| 160 | アスラ | 輝 冥界 支配神 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / アスラ | correct / ANSWER / アスラ | 3/10; 覆った語=冥界,支配神,輝 |
| 161 | 鉱業登録令第十一条 | 経済産業大臣 滅失 期間 | wrong / ANSWER / 七 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/3731; 覆った語=期間,滅失,経済産業大臣 | wrong / ANSWER / 経済産業大臣 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/45; 覆った語=∅ |
| 162 | 移入 | 太平洋側 混血 札幌市付近 | wrong / ANSWER / 混血 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/19; 覆った語=∅ | wrong / ANSWER / 混血 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/19; 覆った語=∅ |
| 163 | 地方税法第三百七十四条 | 滞納処分 執行 目的 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=執行 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=執行 |
| 164 | 掘立小屋 | 強盗殺人事件 男性 当時46歳 | wrong / ANSWER / 男性 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/385; 覆った語=∅ | wrong / ANSWER / 男性 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/385; 覆った語=∅ |
| 165 | 澤口実歩 | 同局アナウンサー 日 放送 | wrong / ANSWER / 放送開始 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/80; 覆った語=同局アナウンサー,放送,日 | wrong / ANSWER / 放送開始 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/80; 覆った語=同局アナウンサー,放送,日 |
| 166 | 企業合理化促進法施行規則第四条 | 補助金交付 提出 申請書 | wrong / ANSWER / 提出 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/77; 覆った語=∅ | wrong / ANSWER / 提出 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/77; 覆った語=∅ |
| 167 | ボルノウ | 池川 大塚 人間 | wrong / ANSWER / 人間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1073; 覆った語=∅ | wrong / ANSWER / 人間 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1073; 覆った語=∅ |
| 168 | 道路運送車両法第十六条 | 自動車 申請 運行 | wrong / ANSWER / 自動車 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/181; 覆った語=∅ | wrong / ANSWER / 自動車 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/181; 覆った語=∅ |
| 169 | 貸付信託法附則第百二十一条 | 施行前 規定 効力 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1354; 覆った語=効力,施行前 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1354; 覆った語=効力,施行前 |
| 170 | 予防接種法第四十九条 | 費用 定期 支弁 | wrong / ANSWER / 費用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/210; 覆った語=∅ | wrong / ANSWER / 費用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/210; 覆った語=∅ |
| 171 | 検察審査会法第十五条 | 各群 規定 検察審査員 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ |
| 172 | 東北6県 | 民放 関東地方 無料聴取 | wrong / ANSWER / 民放 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ | wrong / ANSWER / 民放 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ |
| 173 | 加入電話 | 警察電話 市内 消防署 | wrong / ANSWER / 警察電話 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ | wrong / ANSWER / 警察電話 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/12; 覆った語=∅ |
| 174 | 健康保険法施行規則第百三十四条 | 第三十三条 第五十八条 第六十一条 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 第三十三条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/15; 覆った語=∅ |
| 175 | 陰イオン | mgso4 反応 化合物 | wrong / ANSWER / 反応 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/431; 覆った語=∅ | wrong / ANSWER / 反応 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/431; 覆った語=∅ |
| 176 | 車道 | 設置 多い 駅前 | wrong / ANSWER / 設置 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/124; 覆った語=多い | wrong / ANSWER / 設置 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/124; 覆った語=多い |
| 177 | 海事代理士法第八条 | 地方運輸局長 運輸監理部長 第十二条 | wrong / ANSWER / 第十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/129; 覆った語=∅ | wrong / ANSWER / 第十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/129; 覆った語=∅ |
| 178 | 森林法施行法第九条 | 遅滞な 組織変更 第七条 | wrong / ANSWER / 第七条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/329; 覆った語=∅ | wrong / ANSWER / 第七条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/329; 覆った語=∅ |
| 179 | 刑事訴訟法第四条 | 関連事件 数個 必要 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 対象外（元が非ANSWER） |
| 180 | 小坂誠 | 対横浜5回戦 代打 巨人 | wrong / ANSWER / 巨人 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/99; 覆った語=∅ | wrong / ANSWER / 巨人 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/99; 覆った語=∅ |
| 181 | 難民認定法第四十八条 | 口頭審理 認定 異議 | wrong / ANSWER / 認定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/37; 覆った語=∅ | wrong / ANSWER / 認定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/37; 覆った語=∅ |
| 182 | 斜辺 | 共有 cd 合同 | wrong / ANSWER / 共有 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/50; 覆った語=∅ | wrong / ANSWER / 共有 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/50; 覆った語=∅ |
| 183 | 宗教法人法第三条 | 境内建物 目的 規定 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=規定 | wrong / ANSWER / 目的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/775; 覆った語=規定 |
| 184 | 戸籍法施行規則第六十条 | 漢字 常用漢字表 括弧書き | wrong / ANSWER / 漢字 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/190; 覆った語=∅ | wrong / ANSWER / 漢字 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/190; 覆った語=∅ |
| 185 | 労働関係調整法第三十五条 | 当事者 双方 労働争議 | wrong / ANSWER / 当事者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/212; 覆った語=∅ | wrong / ANSWER / 当事者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/212; 覆った語=∅ |
| 186 | 臨床血液学 | 扱 算定検査 血液学的検査 | wrong / ANSWER / 扱 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/66; 覆った語=∅ | correct / ANSWER / 臨床血液学 | correct / ANSWER / 臨床血液学 | 3/13; 覆った語=扱,算定検査,血液学的検査 |
| 187 | 船員法第百四条 | 規定 基準 市町村 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1354; 覆った語=基準 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1354; 覆った語=基準 |
| 188 | 認識論的問題 | 性質 法 見な | wrong / ANSWER / 性質 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/546; 覆った語=見な | wrong / ANSWER / 性質 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/546; 覆った語=見な |
| 189 | 計算証明規則第十六条 | 歳入 競争契約 書類 | wrong / ANSWER / 歳入 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/15; 覆った語=∅ | wrong / ANSWER / 歳入 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/15; 覆った語=∅ |
| 190 | 物価統制令第三十五条 | 規定ニ 第十二条 違反シタル | wrong / ANSWER / 第十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/129; 覆った語=∅ | wrong / ANSWER / 第十二条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/129; 覆った語=∅ |
| 191 | 理論的説明 | 知 高温超伝導 現象 | wrong / ANSWER / 知 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/54; 覆った語=∅ | correct / ANSWER / 理論的説明 | correct / ANSWER / 理論的説明 | 3/10; 覆った語=現象,知,高温超伝導 |
| 192 | 手形法第四条 | 在ルト 為替手形ハ 支払人ノ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 193 | 抵当権設定者 | 引 実現 効率的利用 | wrong / ANSWER / 引 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/17; 覆った語=∅ | correct / ANSWER / 抵当権設定者 | correct / ANSWER / 抵当権設定者 | 3/26; 覆った語=効率的利用,実現,引 |
| 194 | 航空法施行規則第百九十四条 | 物件 輸送禁止 火薬類火薬 | wrong / ANSWER / 物件 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/7; 覆った語=∅ | wrong / ANSWER / 物件 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/7; 覆った語=∅ |
| 195 | 地方税法第三百一条 | 虚偽 規定 前条第一項 | wrong / ANSWER / 虚偽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ | wrong / ANSWER / 虚偽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ |
| 196 | ゲームエンジン | 作業 不在 主流 | wrong / ANSWER / 作業 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/266; 覆った語=∅ | wrong / ANSWER / 作業 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/266; 覆った語=∅ |
| 197 | 学校基本調査規則第四条 | 時期 学齢児童生徒 卒業者 | wrong / ANSWER / 時期 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/225; 覆った語=∅ | wrong / ANSWER / 時期 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/225; 覆った語=∅ |
| 198 | 合名会社等再建整備令第四条 | 適用 必要 整備計画 | wrong / ANSWER / 適用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/258; 覆った語=∅ | wrong / ANSWER / 適用 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/258; 覆った語=∅ |
| 199 | 地方税法施行令第九条 | 適格合併等 規定 同項 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1354; 覆った語=同項 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1354; 覆った語=同項 |
| 200 | 規制機関 | 実質的 控 国 | wrong / ANSWER / 実質的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/6; 覆った語=∅ | wrong / ANSWER / 実質的 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/6; 覆った語=∅ |
| 201 | 水産業協同組合法第百十六条 | 次条第一項 規定 六十一 | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ | wrong / ANSWER / 規定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1354; 覆った語=∅ |
| 202 | ニュースゾーン | 広瀬麻知子 番組 4年間担当 | wrong / ANSWER / 番組 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/497; 覆った語=∅ | wrong / ANSWER / 番組 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/497; 覆った語=∅ |
| 203 | dominator | anniversary 追加生産 th | wrong / ANSWER / 音楽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/764; 覆った語=anniversary,th | wrong / ANSWER / 音楽 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/764; 覆った語=anniversary,th |
| 204 | 桧垣良成 | 展開 カント 日本哲学会 | wrong / ANSWER / 展開 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ | wrong / ANSWER / 展開 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ |
| 205 | 民法第三百六十六条 | 質権者 金銭 質権 | wrong / ANSWER / 債権者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/127; 覆った語=質権,金銭 | wrong / ANSWER / 債権者 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/127; 覆った語=質権,金銭 |
| 206 | サンダル | 着用可能な 品物 ハイヒール | wrong / ANSWER / 品物 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ | wrong / ANSWER / 品物 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ |
| 207 | 坂倉 | 特 岡田 復帰 | wrong / ANSWER / 特 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/461; 覆った語=∅ | correct / ANSWER / 坂倉 | correct / ANSWER / 坂倉 | 3/16; 覆った語=岡田,復帰,特 |
| 208 | 気象業務法施行規則第二十九条 | 法第二十四条 記載 指定試験機関 | wrong / ANSWER / 記載 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/207; 覆った語=∅ | wrong / ANSWER / 記載 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/207; 覆った語=∅ |
| 209 | 冥王星 | 定義 system solar | wrong / ANSWER / 定義 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/853; 覆った語=∅ | wrong / ANSWER / 定義 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/853; 覆った語=∅ |
| 210 | 織田信長篇 | 安土城 i 5巻 | wrong / ANSWER / 天正4年 | wrong / ANSWER / 天正4年 | 1/4; 覆った語=安土城 | wrong / ANSWER / 天正4年 | wrong / ANSWER / 天正4年 | 1/4; 覆った語=安土城 |
| 211 | 行旅病人及行旅死亡人取扱法第十七条 | 同伴者並其ノ 外国人タル 規定ヲ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 212 | 接地 | 広義 日本 必 | wrong / ANSWER / 広義 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/117; 覆った語=必 | wrong / ANSWER / 広義 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/117; 覆った語=必 |
| 213 | 波長分布 | 照明下 太陽光線 異な | wrong / ANSWER / 異な | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/97; 覆った語=∅ | wrong / ANSWER / 異な | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/97; 覆った語=∅ |
| 214 | 海面漁業生産統計調査規則第十条 | 集計結果 都道府県別 送付 | wrong / ANSWER / 送付 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/2; 覆った語=∅ | wrong / ANSWER / 送付 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/2; 覆った語=∅ |
| 215 | 道路運送車両法施行規則第三十六条 | 当該自動車 新規検査 申請 | wrong / ANSWER / 申請 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/131; 覆った語=∅ | wrong / ANSWER / 申請 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/131; 覆った語=∅ |
| 216 | 法律附則第四条 | 外務公務員 在外公館 名称 | wrong / ANSWER / 名称 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/427; 覆った語=∅ | wrong / ANSWER / 名称 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/427; 覆った語=∅ |
| 217 | 各番組 | 特別番組 呼 土曜朝改編 | wrong / ANSWER / 形 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/421; 覆った語=呼,特別番組 | correct / ANSWER / 各番組 | correct / ANSWER / 各番組 | 3/21; 覆った語=呼,土曜朝改編,特別番組 |
| 218 | 予防課 | 救急課 原子力規制庁原子力規制企画課火災対策室な 執行 | wrong / ANSWER / 執行 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ | wrong / ANSWER / 執行 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ |
| 219 | 薬事法距離制限違憲判決 | 最高裁判所 態様 弊害 | wrong / ANSWER / 最高裁判所 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/240; 覆った語=∅ | wrong / ANSWER / 最高裁判所 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/240; 覆った語=∅ |
| 220 | 船員職業安定法第四十九条 | 求人 船員 求職者 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 221 | ヒルシステム | ヒル 数 他 | wrong / ANSWER / 他 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1274; 覆った語=∅ | correct / ANSWER / ヒルシステム | correct / ANSWER / ヒルシステム | 3/24; 覆った語=ヒル,他,数 |
| 222 | 班田収授 | 理由 大隅な 墾田 | wrong / ANSWER / 理由 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/559; 覆った語=∅ | wrong / ANSWER / 理由 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/559; 覆った語=∅ |
| 223 | 南満洲鉄道附属地煙草税令 | 廃止 満洲国ニ 勅令中改正等ノ | wrong / ANSWER / 廃止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/94; 覆った語=∅ | wrong / ANSWER / 廃止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/94; 覆った語=∅ |
| 224 | psa | 言語全体 談話的 関係 | wrong / ANSWER / 関係 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/898; 覆った語=∅ | wrong / ANSWER / 関係 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/898; 覆った語=∅ |
| 225 | 言語学的な | 民族 人 理論 | wrong / ANSWER / 民族 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/92; 覆った語=人 | wrong / ANSWER / 民族 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/92; 覆った語=人 |
| 226 | 貿易保険法第十条 | 職員 次条 法人 | wrong / ANSWER / 職員 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ | wrong / ANSWER / 職員 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/196; 覆った語=∅ |
| 227 | 教科用図書検定調査審議会令附則第二条 | 政令 施行 教科用図書検定調査審議会 | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ |
| 228 | 科学研究費助成事業 | 工学 再生 日本学術振興会 | wrong / ANSWER / 工学 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/160; 覆った語=∅ | wrong / ANSWER / 工学 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/160; 覆った語=∅ |
| 229 | 内航海運業法第十八条 | 登録 国土交通大臣 届出 | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/57; 覆った語=届出 | wrong / ANSWER / 登録 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/57; 覆った語=届出 |
| 230 | 口角 | 左右非対称 左右対称 協調運動 | wrong / ANSWER / 説明 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/355; 覆った語=左右対称 | wrong / ANSWER / 説明 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/355; 覆った語=左右対称 |
| 231 | 文化功労者年金法施行規則第四条 | 返還 年金証書 死亡 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 232 | 一般名 | 語 アルキル 続 | wrong / ANSWER / 語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/1089; 覆った語=続 | wrong / ANSWER / 反復 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/47; 覆った語=続,語 |
| 233 | r1 | 存在 住宅数 依然 | wrong / ANSWER / 存在 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/623; 覆った語=∅ | wrong / ANSWER / 存在 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/623; 覆った語=∅ |
| 234 | 火薬類取締法施行規則第八十三条 | 取扱者 制限 経済産業省令 | wrong / ANSWER / 制限 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/269; 覆った語=∅ | wrong / ANSWER / 制限 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/269; 覆った語=∅ |
| 235 | 農業工学技術者 | 土地改良技術者 研究機関な 商品 | wrong / ANSWER / 商品 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/71; 覆った語=∅ | wrong / ANSWER / 商品 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/71; 覆った語=∅ |
| 236 | ランベルト | 吸光度 存在量 求 | wrong / ANSWER / 等価幅 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/106; 覆った語=存在量,求 | wrong / ANSWER / 等価幅 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/106; 覆った語=存在量,求 |
| 237 | 漁船法第二十七条 | 漁船用機械 試験 設計 | wrong / ANSWER / 設計 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/213; 覆った語=∅ | wrong / ANSWER / 設計 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/213; 覆った語=∅ |
| 238 | 現存社会 | マルクス 経済理論 社会科学 | wrong / ANSWER / マルクス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/80; 覆った語=∅ | wrong / ANSWER / マルクス | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/80; 覆った語=∅ |
| 239 | 生活保護法第四十四条 | 都道府県知事 管理者 立入検査 | wrong / ANSWER / 都道府県知事 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/116; 覆った語=∅ | wrong / ANSWER / 都道府県知事 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/116; 覆った語=∅ |
| 240 | 日本銀行国債事務取扱規程第四十五条 | 閲覧ノ 日本銀行ハ 請求ヲ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 241 | タミール | 発音 地名な 思 | wrong / ANSWER / 語 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1089; 覆った語=思,発音 | wrong / ANSWER / 発音 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/133; 覆った語=∅ |
| 242 | 日本銀行政府有価証券取扱規程第三十四条 | 第二十八条ノ 於テ 日本銀行ニ | wrong / ANSWER / 二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/14025; 覆った語=於テ | wrong / ANSWER / 第五条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/393; 覆った語=於テ,日本銀行ニ |
| 243 | 条約第六条 | 担任スヘシ 左ノ 以テ | wrong / ANSWER / 第一条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/736; 覆った語=以テ,左ノ | wrong / ANSWER / 第一条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/736; 覆った語=以テ,左ノ |
| 244 | 業法施行規則第六条 | 免許証 個人番号 再交付 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 業法施行規則第六条 | correct / ANSWER / 業法施行規則第六条 | 3/9; 覆った語=個人番号,免許証,再交付 |
| 245 | 速度分布 | 分布関数 温度 従い | wrong / ANSWER / 温度 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/249; 覆った語=∅ | wrong / ANSWER / 温度 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/249; 覆った語=∅ |
| 246 | バーク | 取 供 合い | wrong / ANSWER / 取 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/63; 覆った語=∅ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 247 | 成田得平 | 単一民族国家 国政選挙 北海道議会 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 248 | 船員法第四十五条 | 船員 船舶所有者 規定 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） |
| 249 | 身体障害者福祉法施行規則第四条 | 氏名 生年月日 厚生労働省令 | wrong / ANSWER / 補助者 | wrong / ANSWER / 補助者 | 3/21; 覆った語=厚生労働省令,氏名,生年月日 | wrong / ANSWER / 補助者 | wrong / ANSWER / 補助者 | 3/21; 覆った語=厚生労働省令,氏名,生年月日 |
| 250 | 警視庁 | 受 可能 対応 | wrong / ANSWER / 受 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/202; 覆った語=∅ | wrong / ANSWER / 相談 | wrong / ANSWER / 相談 | 3/18; 覆った語=受,可能,対応 |
| 251 | 貿易保険法第六十九条 | 該当 保険契約 海外投資 | wrong / ANSWER / 該当 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ | wrong / ANSWER / 該当 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ |
| 252 | 音楽関連 | 同県 沖縄県 決定 | wrong / ANSWER / 決定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/204; 覆った語=∅ | wrong / ANSWER / 決定 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/204; 覆った語=∅ |
| 253 | 海上運送法第三十四条 | 船員確保基本方針 第一条 船舶法 | wrong / ANSWER / 第一条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/736; 覆った語=∅ | wrong / ANSWER / 第一条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/736; 覆った語=∅ |
| 254 | 公職選挙法施行令第百四十四条 | 政令 国勢調査 公示 | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/42; 覆った語=∅ |
| 255 | 日本銀行国債事務取扱規程第五十七条 | 前項ノ 公債償還資金 国債元利金ヲ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 256 | 地方税法施行令附則第十八条 | 譲渡所得等 金額 特例 | wrong / ANSWER / 金額 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/115; 覆った語=∅ | wrong / ANSWER / 金額 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/115; 覆った語=∅ |
| 257 | イグナトフ | 慎導灼 特 刑事課一係 | correct / ANSWER / イグナトフ | correct / ANSWER / イグナトフ | 3/13; 覆った語=刑事課一係,慎導灼,特 | correct / ANSWER / イグナトフ | correct / ANSWER / イグナトフ | 3/13; 覆った語=刑事課一係,慎導灼,特 |
| 258 | 第五十九条 | 禁止 意見聴取 提出 | wrong / ANSWER / 禁止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ | wrong / ANSWER / 禁止 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/74; 覆った語=∅ |
| 259 | 健康保険法施行令第四十三条 | 支給 薬局 保険医療機関 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 支給 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/17; 覆った語=∅ |
| 260 | 入場 | 含 会場 映画館 | wrong / ANSWER / 含 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/66; 覆った語=∅ | correct / ANSWER / 入場 | correct / ANSWER / 入場 | 3/17; 覆った語=会場,含,映画館 |
| 261 | 引受先 | 答弁 検討 縦割 | wrong / ANSWER / 政府 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1156; 覆った語=検討,答弁 | wrong / ANSWER / 政府 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/1156; 覆った語=検討,答弁 |
| 262 | 金融機関再建整備法施行規則第二十三条 | 評価 記載 金融機関 | wrong / ANSWER / 評価 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/223; 覆った語=∅ | wrong / ANSWER / 評価 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/223; 覆った語=∅ |
| 263 | 母体 | 性感染症 含 ヒト | wrong / ANSWER / ヒト | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/287; 覆った語=∅ | wrong / ANSWER / ヒト | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/287; 覆った語=∅ |
| 264 | 地方税法第六百八十六条 | 更正 前条第二項 規定 | wrong / ANSWER / 六十六 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/119; 覆った語=前条第二項,更正,規定 | wrong / ANSWER / 六十六 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/119; 覆った語=前条第二項,更正,規定 |
| 265 | 船員職業安定法附則第二十八条 | 政令 罰則 法律 | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/42; 覆った語=法律 | wrong / ANSWER / 政令 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/42; 覆った語=法律 |
| 266 | 航空法第百十九条 | 六月以内 国土交通大臣 該当 | wrong / ANSWER / 六十三 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/150; 覆った語=六月以内,国土交通大臣,該当 | wrong / ANSWER / 六十三 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/150; 覆った語=六月以内,国土交通大臣,該当 |
| 267 | 漁業法第百六十五条 | 海草乾場 漁業協同組合 漁業者 | correct / ANSWER / 漁業法第百六十五条 | correct / ANSWER / 漁業法第百六十五条 | 3/8; 覆った語=海草乾場,漁業協同組合,漁業者 | correct / ANSWER / 漁業法第百六十五条 | correct / ANSWER / 漁業法第百六十五条 | 3/8; 覆った語=海草乾場,漁業協同組合,漁業者 |
| 268 | 劇性 | 強い 指定 法令 | wrong / ANSWER / 必要 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1677; 覆った語=強い,指定,法令 | wrong / ANSWER / 必要 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/1677; 覆った語=強い,指定,法令 |
| 269 | 土地改良法第四十三条 | 資格 承継 決済 | wrong / ANSWER / 資格 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/78; 覆った語=∅ | wrong / ANSWER / 資格 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/78; 覆った語=∅ |
| 270 | キリコ | 体 傭兵部隊 判明 | wrong / ANSWER / 体 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/152; 覆った語=∅ | correct / ANSWER / キリコ | correct / ANSWER / キリコ | 3/53; 覆った語=体,傭兵部隊,判明 |
| 271 | 自民党 | 到底 先立 出演被害防止 | correct / ANSWER / 自民党 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/83; 覆った語=先立,出演被害防止,到底 | correct / ANSWER / 自民党 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/83; 覆った語=先立,出演被害防止,到底 |
| 272 | 健康保険法施行規則第八十三条 | 給付 規定 記載 | wrong / ANSWER / 五十九 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/134; 覆った語=給付,規定,記載 | wrong / ANSWER / 五十九 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/134; 覆った語=給付,規定,記載 |
| 273 | 的基礎 | 接点 多い 批判 | wrong / ANSWER / 接点 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/14; 覆った語=∅ | wrong / ANSWER / 接点 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/14; 覆った語=∅ |
| 274 | ピーク | 平成6年 動脈硬化 度 | wrong / ANSWER / 度 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/41; 覆った語=∅ | correct / ANSWER / ピーク | correct / ANSWER / ピーク | 2/9; 覆った語=動脈硬化,度 |
| 275 | 整備法第五十三条 | 第七条第一項 第三項 国際観光ホテル | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 整備法第五十三条 | correct / ANSWER / 整備法第五十三条 | 3/9; 覆った語=国際観光ホテル,第七条第一項,第三項 |
| 276 | 皇后 | 巡幸中 散策 庭 | refusal / AMBIGUOUS / — | refusal / AMBIGUOUS / — | 対象外（元が非ANSWER） | wrong / ANSWER / 散策 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/7; 覆った語=∅ |
| 277 | 法学者ウルピアヌス | 公法 西洋法学 利益 | wrong / ANSWER / 国家 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/345; 覆った語=公法,利益 | wrong / ANSWER / 国家 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/345; 覆った語=公法,利益 |
| 278 | 改元前日 | 大型特番 枠 日スペシャル | wrong / ANSWER / 枠 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/144; 覆った語=∅ | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） |
| 279 | iosアプリ | 配信 production 制作 | wrong / ANSWER / 配信 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/142; 覆った語=制作 | wrong / ANSWER / 配信 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/142; 覆った語=制作 |
| 280 | 公有水面埋立法第八条 | 埋立ノ 第六条ノ 受ケタル | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | correct / ANSWER / 公有水面埋立法第八条 | correct / ANSWER / 公有水面埋立法第八条 | 3/8; 覆った語=受ケタル,埋立ノ,第六条ノ |
| 281 | 公有水面埋立法第三条 | 其ノ 遅滞ナク 掲グル | wrong / ANSWER / 二 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/14025; 覆った語=其ノ,掲グル,遅滞ナク | wrong / ANSWER / 第三条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/669; 覆った語=其ノ,掲グル,遅滞ナク |
| 282 | テープ | 主 使 作成 | wrong / ANSWER / 主 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/464; 覆った語=使 | wrong / ANSWER / キャッチコピー | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 3/97; 覆った語=主,作成,使 |
| 283 | 在外公館等借入金返済実施規程第一条 | 法律 返済 規程 | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1374; 覆った語=∅ | wrong / ANSWER / 法律 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/1374; 覆った語=∅ |
| 284 | キノリニウムベタイン | 血赤色 負 青色 | wrong / ANSWER / 負 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/5; 覆った語=∅ | wrong / ANSWER / 青色 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/633; 覆った語=∅ |
| 285 | 国土調査法施行令第十六条 | 認証 請求 成果 | wrong / ANSWER / 認証 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ | wrong / ANSWER / 認証 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/31; 覆った語=∅ |
| 286 | 気象業務法第四十六条 | 違反 該当 第九条 | wrong / ANSWER / 違反 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/100; 覆った語=∅ | wrong / ANSWER / 違反 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/100; 覆った語=∅ |
| 287 | 血統 | 共同 傍系親 男子 | correct / ANSWER / 血統 | correct / ANSWER / 血統 | 3/23; 覆った語=傍系親,共同,男子 | correct / ANSWER / 血統 | correct / ANSWER / 血統 | 3/23; 覆った語=傍系親,共同,男子 |
| 288 | 301条提訴 | 件数 判断 交渉 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 件数 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/44; 覆った語=∅ |
| 289 | 港湾法第四十一条 | 構築物 改築等 有害構築物 | wrong / ANSWER / 構築物 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ | wrong / ANSWER / 構築物 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |
| 290 | 生活保護法施行令第三条 | 教育扶助 特例 親権者 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 特例 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/38; 覆った語=∅ |
| 291 | 公職選挙法第五十五条 | 開票管理者 送致 投票立会人 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 法律第十四条 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 2/282; 覆った語=投票立会人,開票管理者 |
| 292 | 元来 | 化学構造な 仏 動詞 | wrong / ANSWER / 動詞 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/191; 覆った語=∅ | wrong / ANSWER / 動詞 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/191; 覆った語=∅ |
| 293 | メンタルケア | 理想的な 最適 社会 | refusal / UNKNOWN_NO_EVIDENCE / — | refusal / UNKNOWN_NO_EVIDENCE / — | 対象外（元が非ANSWER） | wrong / ANSWER / 理想的な | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/4; 覆った語=∅ |
| 294 | 宗教法人法第五十二条 | 規則 認証書 交付 | wrong / ANSWER / 規則 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/183; 覆った語=∅ | wrong / ANSWER / 規則 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/183; 覆った語=∅ |
| 295 | 解決方法 | 利点 元 オブザーバブル | wrong / ANSWER / 利点 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/233; 覆った語=∅ | wrong / ANSWER / 利点 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/233; 覆った語=∅ |
| 296 | 同居 | 親族以外 適用除外 他人 | wrong / ANSWER / 他人 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/102; 覆った語=∅ | wrong / ANSWER / 他人 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/102; 覆った語=∅ |
| 297 | 武器等製造法附則第九条 | 罰則 行為 施行前 | wrong / ANSWER / 罰則 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/175; 覆った語=行為 | wrong / ANSWER / 罰則 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 1/175; 覆った語=行為 |
| 298 | 離島航路整備法施行規則第二条 | 国土交通大臣 航路補助金 申請 | wrong / ANSWER / 国土交通大臣 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/61; 覆った語=∅ | wrong / ANSWER / 国土交通大臣 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/61; 覆った語=∅ |
| 299 | 反三木派 | 椎名 批判 政権主流派 | wrong / ANSWER / 批判 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/347; 覆った語=∅ | wrong / ANSWER / 批判 | refusal / UNKNOWN_INSUFFICIENT_EVIDENCE / — | 0/347; 覆った語=∅ |

候補列・殻の全配置・content tokens・全探索 trace は [results.json](results.json) に腕ごとに保存した。
この表の被覆は選択核の全 facet 分母と覆った語であり、配置された面数ではない。

## 回帰検査（本番変更なしでの健康確認）

`python3.11 -m verantyx.cli lab`: 178/178、skipped 0。
`python3.11 experiments/guard/verify_all.py`: forks 89/89 / 測定 48/50。
終了コードは lab=0、guard=1。guard の失敗は V5 の凍結バイナリ不在と、その結果を集約した V24 で、背景に記載された既知の環境依存と同じ組である。

| guard 実行ファイル | 結果 |
| --- | --- |
| run_confirm.py | 6/7 |
| run_confirm2.py | 5/5 |
| run_confirm3.py | 5/5 |
| run_confirm_lang.py | 3/3 |
| run_confirm4.py | 5/6 |
| run_confirm5.py | 3/3 |
| run_confirm6.py | 3/3 |
| run_confirm7.py | 4/4 |
| run_confirm8.py | 4/4 |
| run_confirm9.py | 6/6 |
| run_confirm10.py | 4/4 |

- run_confirm.py: V5_guard_cli_speed: {'error': 'frozen binary not found: /Users/motonishik
- run_confirm4.py: V24_regression_all_green: {'scripts': {'run_confirm.py': '6/7', 'run_conf

失敗した測定の詳細（実行結果の原文）:
`results_confirm.json: V5_guard_cli_speed`
```json
{
  "pass": false,
  "detail": {
    "error": "frozen binary not found: /Users/motonishikoudai/Projects/Verantyx/cli/VerantyxIDE/Vendor/vera-memory"
  }
}
```
`results_confirm4.json: V24_regression_all_green`
```json
{
  "pass": false,
  "detail": {
    "scripts": {
      "run_confirm.py": "6/7",
      "run_confirm2.py": "5/5",
      "run_confirm3.py": "5/5",
      "run_confirm_lang.py": "3/3"
    },
    "expected": {
      "run_confirm.py": "7/7",
      "run_confirm2.py": "5/5",
      "run_confirm3.py": "5/5",
      "run_confirm_lang.py": "3/3"
    },
    "forks": "89/89",
    "failed_forks": []
  }
}
```
lab の stderr には WikiText cache 不在による synthetic_en fallback の RuntimeWarning が出た。skipped に算入されたものはない。
lab の全 fork 判定は [lab.log](lab.log)、guard のログは [guard.log](guard.log)、
構造化結果は [guard_result.json](guard_result.json)、各測定詳細は `checks_after/` に保存。
本番 verantyx/*.py は今回変更していないため、git checkout による撤回対象はない。
健康確認が更新した既存 JSON 等は実行後の証拠を別保存し、実行前のバイト列に復元した。利用者の既存変更を維持した。

## この登録で言えること・言えないこと

落ちた主判定は CORRECT_NOT_WORSE。登録した採択条件を満たさず、本番採用しない。
この実装は低い facet 被覆を型付き棄権に変える。上の正答喪失・誤答抑制・junk 除去後の個別遷移を、同じ固定閾値で観測した。
被覆率の閾値と、問いが唯一の核を指定できることは同一ではない。高被覆の誤答や、正しいが facet の多い核の棄権を、この比率だけでは排除できない。
既存 direction_band/REVERSE_SPECIFIC の帯唯一性・次点比の判定は今回改変せず、順方向の選択核だけを裁定した。
具体的には、現行で正答だった言語学者 (3/73)、論 (3/84)、数 (3/723)、自民党 (3/83) は、問いの内容語をすべて覆っていても全 facet を分母にしたため落ちた。一文字核を gold から外すなどの事後的な評価変更はしていない。
一方、junk 除去で初めて誤答になり裁定後も残った id 18 は 2/10、id 29 は 3/10 と高被覆だった。一般語を共有する別条文を、この絶対被覆率では識別できなかった。これらは今回保存した実測例であり、未実行の閾値による改善予想ではない。
補助腕の結果は候補取得後の junk 除去という条件に限定する。junk の3入口すべてへの配線や、本番 ja_consensus_ask の改善を実測したとは主張しない。
不採択を別の閾値の結果で上書きせず、凍結登録・実装・全件の証拠を残す。
