# PUB-M6b (4) — bank_ls dev の言い換えの問いが外れる理由（offline、dev 2 本）

言い換え 58 問のうち到達 0。同じ言い方 6 問のうち到達 6。存在しない問い 16 のうち答えを出した 0。

## 最初に落ちる段（言い換え 58 問）

- Q1 question not read: 40
- Q2 question read as an event (F3), memory holds an attribute: 7
- Q2 question read as an event (F4), memory holds an attribute: 1
- Q2b question read as an event, memory holds an event: 1
- Q3 attribute question, no position with its slot noun: 9

問いが読めない内訳: {'Q1 question not read (frame_not_read:case_before_topic)': 9, 'Q1 question not read (frame_not_read:gap_is_not_a_particle)': 24, 'Q1 question not read (frame_not_read:no_predicate)': 1, 'Q1 question not read (no_question_word)': 5, 'Q1 question not read (several_clauses)': 1}

ほかの妨げ（重なることがある）: {'fact stored as an event (F3)': 16, 'stored sentence F0 (all)': 6, 'stored sentence F0 (one of two)': 7}

## 単位の重なりの経路のシミュレーション（コードには入れていない）

位置（F1 / F2）のうち、問いの内容語の単位との共有が N 以上、値の型が問い語に合い、最高点が一意のもの。言い換え: {'1': {'gold': 24, 'none': 15, 'tie': 8, 'wrong': 11}, '2': {'gold': 20, 'none': 34, 'wrong': 3, 'tie': 1}, '3': {'none': 46, 'gold': 10, 'wrong': 1, 'tie': 1}}。存在しない問い: {'1': {'none': 9, 'admitted': 5, 'tie': 2}, '2': {'none': 16}, '3': {'none': 16}}。

## 全問

| 物語 | 種類 | 問い | 金の値 | 保存された文 | 保存の席 / 問いの席 | 読み | 最初に落ちる段 | ほかの妨げ | 重なり N=2 |
|---|---|---|---|---|---|---|---|---|---|
| D01 | plai/same | 認証端末の検収日はいつですか？ | 2032年10月3日 | 認証端末の検収日は2032年10月3日。 | 認証端末の検収日 / 認証端末の検収日 | F1 検収日 [['の', '認証端末']] | Q0 reached | - | gold |
| D01 | cont/reph | 新館を開ける日はいつですか？ | 矛盾: 2032年11月7日 と 2032年11月8日 | 新館開館日は2032年11月7日。 // 新館開館日は2032年11月8日。 | 新館開館日 / 新館を開ける日 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | gold |
| D01 | upda/reph | 棚ラベルの確認作業はいつまでですか？ | 2032年9月24日 | 棚ラベル照合の締切は2032年9月22日から2032年9月24日に変更になった。 | 棚ラベル照合の締切 / 確認作業はいつまで | F1 確認作業 [['の', '棚ラベル']] | Q3 attribute question, no position with its slot noun | - | gold |
| D01 | plai/reph | 北側搬入口の鍵は何時に開けますか？ | 6時40分 | 北側搬入口の解錠時刻は6時40分。 | 北側搬入口の解錠時刻 / 鍵は何時に開けます | F3 開ける [] | Q2 question read as an event (F3), memory holds an attribute | - | gold |
| D01 | cont/reph | 最初の蔵書の搬出日はいつですか？ | 矛盾: 2032年10月15日 と 2032年10月16日 | 蔵書の第一陣移送日は2032年10月15日。 // 蔵書の第一陣移送日は2032年10月16日。 | 蔵書の第一陣移送日 / 蔵書の搬出日はいつ | F1 搬出日 [['の', '蔵書'], ['の', '最初']] | Q3 attribute question, no position with its slot noun | - | gold |
| D01 | upda/same | 認証端末の設置日は何日ですか？ | 2032年10月4日 | 認証端末の設置日は2032年10月2日から2032年10月4日に変更になった。 | 認証端末の設置日 / 認証端末の設置日 | F1 設置日 [['の', '認証端末']] | Q0 reached | - | gold |
| D01 | plai/reph | 職員休憩室へつなぐ内線は何番ですか？ | 413 | 職員休憩室の内線番号は413。 | 職員休憩室の内線番号 / つなぐ内線は何番 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | none |
| D01 | cont/reph | 大閲覧室でイベントを受け入れる人数は何人ですか？ | 矛盾: 120人 と 96人 | 大閲覧室のイベント定員は120人。 // 大閲覧室のイベント定員は96人。 | 大閲覧室のイベント定員 / イベントを受け入れる人数 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | gold |
| D01 | plai/reph | 一般書の移送箱は何箱ですか？ | 340箱 | 一般書の箱数は340箱。 | 一般書の箱数 / 移送箱は何箱 | F1 移送箱 [['の', '一般書']] | Q3 attribute question, no position with its slot noun | - | gold |
| D01 | cont/reph | 珪戸分室を閉じるのは何日ですか？ | 矛盾: 2032年10月31日 と 2032年11月1日 | 珪戸分室の閉室日は2032年10月31日。 // 珪戸分室の閉室日は2032年11月1日。 | 珪戸分室の閉室日 / 分室を閉じるのは何日 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (all) | none |
| D01 | upda/reph | 本の庭開きの会場準備は何日ですか？ | 2032年10月30日 | イベント設営日は2032年10月29日から2032年10月30日に変更になった。 | イベント設営日 / 会場準備は何日 | F1 会場準備 [['の', '庭開き'], ['の', '本']] | Q3 attribute question, no position with its slot noun | - | none |
| D01 | plai/same | イベント午後枠の定員は何人ですか？ | 24名 | イベント午後枠の定員は24名。 | イベント午後枠の定員 / イベント午後枠の定員 | F1 定員 [['の', 'イベント午後枠']] | Q0 reached | - | gold |
| D01 | cont/reph | 台車調達にいくら計上していますか？ | 矛盾: 486,000円 と 512,000円 | 搬送台車の購入費は486,000円。 // 搬送台車の購入費は512,000円。 | 搬送台車の購入費 / 台車調達にいくら | F4 計上 [] | Q2 question read as an event (F4), memory holds an attribute | - | none |
| D01 | upda/reph | 参加希望を送る期限は何日ですか？ | 2032年10月22日 | イベント受付締切は2032年10月20日から2032年10月22日に変更になった。 | イベント受付締切 / 参加希望を送る期限 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | none |
| D01 | plai/reph | 連絡カードは何枚配布しますか？ | 26枚 | 災害連絡カードの配布枚数は26枚。 | 災害連絡カードの配布枚数 / 連絡カードは何枚配布 | F3 配布 [] | Q2 question read as an event (F3), memory holds an attribute | - | gold |
| D01 | cont/same | 早番の出勤時刻は何時ですか？ | 矛盾: 8時15分 と 8時30分 | 早番の出勤時刻は8時15分。 // 早番の出勤時刻は8時30分。 | 早番の出勤時刻 / 早番の出勤時刻 | F1 出勤時刻 [['の', '早番']] | Q0 reached | - | gold |
| D01 | plai/reph | 児童コーナーの書架は何段ですか？ | 5段 | 児童書架の棚段数は5段。 | 児童書架の棚段数 / 児童コーナーの書架は何段 | F1 書架 [['の', '児童コーナー']] | Q3 attribute question, no position with its slot noun | - | gold |
| D01 | cont/reph | 西側看板の取り付けは何日に予定されていますか？ | 矛盾: 2032年10月26日 と 2032年10月24日 | 西面サインの設置日は2032年10月26日。 // 西面サインの設置日は2032年10月24日。 | 西面サインの設置日 / 西側看板の取り付け | F3 予定 [] | Q2 question read as an event (F3), memory holds an attribute | - | none |
| D01 | upda/reph | 新任向け研修は何分で組みますか？ | 120分 | 職員研修時間は90分から120分に変更になった。 | 職員研修時間 / 新任向け研修は何分 | F3 組む [] | Q2 question read as an event (F3), memory holds an attribute | - | none |
| D01 | plai/same | 広報チラシの印刷部数はいくつですか？ | 1,400部 | 広報チラシの印刷部数は1,400部。 | 広報チラシの印刷部数 / 広報チラシの印刷部数 | F1 印刷部数 [['の', '広報チラシ']] | Q0 reached | - | gold |
| D01 | cont/reph | 貸出系を止めるのは何時ですか？ | 矛盾: 19時00分 と 20時00分 | 貸出系停止の開始時刻は19時00分。 // 貸出系停止の開始時刻は20時00分。 | 貸出系停止の開始時刻 / 貸出系を止めるのは何時 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D01 | upda/reph | 展示写真の許可確認を終える日を教えてください？ | 2032年10月19日 | 写真掲示承認の締切は2032年10月18日から2032年10月19日に変更になった。 | 写真掲示承認の締切 / 展示写真の許可確認を終える日 | no_question_word | Q1 question not read (no_question_word) | - | none |
| D01 | plai/reph | 停電用に予備する蓄電池はいくつありますか？ | 3台 | 予備蓄電池の台数は3台。 | 予備蓄電池の台数 / 停電用に予備する蓄電池 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D01 | cont/reph | ボランティア説明会はどの部屋で開きますか？ | 矛盾: 研修室藍 と 会議室C | ボランティア説明会の会場は研修室藍。 // ボランティア説明会の会場は会議室C。 | ボランティア説明会の会場 / 説明会はどの部屋 | no_question_word | Q1 question not read (no_question_word) | - | gold |
| D01 | plai/reph | 蔵書検索画面の切替は何時に始まりますか？ | 18時40分 | OPAC切替開始時刻は18時40分。 | OPAC切替開始時刻 / 蔵書検索画面の切替 | F3 始まる [] | Q2 question read as an event (F3), memory holds an attribute | - | none |
| D01 | cont/reph | 郷土資料箱に保つ湿度の上限を教えてください？ | 矛盾: 45% と 48% | 郷土資料箱の保管湿度上限は45%。 // 郷土資料箱の保管湿度上限は48%。 | 郷土資料箱の保管湿度上限 / 箱に保つ湿度の上限 | no_question_word | Q1 question not read (no_question_word) | - | wrong |
| D01 | upda/reph | 増便分として用意する台車は何台ですか？ | 22台 | 追加台車数は18台から22台に変更になった。 | 追加台車数 / 増便分として用意する台車 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | none |
| D01 | plai/same | 新館カードの有効期間は何年ですか？ | 3年 | 新館カードの有効期間は3年。 | 新館カードの有効期間 / 新館カードの有効期間 | F1 有効期間 [['の', '新館カード']] | Q0 reached | - | gold |
| D01 | cont/reph | 書架を運ぶ便の出発予定は何時ですか？ | 矛盾: 7時20分 と 7時35分 | 書架便の第一便出発時刻は7時20分。 // 書架便の第一便出発時刻は7時35分。 | 書架便の第一便出発時刻 / 書架を運ぶ便の出発予定 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | gold |
| D01 | upda/reph | 玄関照明の動作確認は何時に行いますか？ | 17時50分 | 玄関灯点検時刻は17時30分から17時50分に変更になった。 | 玄関灯点検時刻 / 玄関照明の動作確認 | F3 行う [] | Q2 question read as an event (F3), memory holds an attribute | - | none |
| D01 | plai/reph | 優先席を示す色は何ですか？ | 若草色 | 車いす優先席の表示色は若草色。 | 車いす優先席の表示色 / 優先席を示す色 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | gold |
| D01 | cont/reph | 開館式でリボンを切る時刻は何時ですか？ | 矛盾: 9時40分 と 10時00分 | 開館式のテープカット時刻は9時40分。 // 開館式のテープカット時刻は10時00分。 | 開館式のテープカット時刻 / リボンを切る時刻 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D02 | cont/reph | 替えブラシを試験用に手配する本数はいくつですか？ | 矛盾: 420本 と 460本 | 仮発注の交換ブラシは420本で枠を押さえた。 // 仮の購買票では交換ブラシを460本と記した。 | 仮発注の交換ブラシ / 試験用に手配する本数 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two); fact stored as an event (F3) | none |
| D02 | plai/reph | 認証審査へ資料を出す日はいつですか？ | 11月6日 | 認証資料の提出締切は11月6日と台帳に載せた。 | 認証資料の提出締切 / 資料を出す日 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | fact stored as an event (F3) | none |
| D02 | upda/reph | 静音設定で連続運転できる長さはどれくらいですか？ | 46分 | 静音運転の連続時間は42分から46分に変更になった。 | 静音運転の連続時間 / 連続運転できる長さ | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D02 | plai/reph | 駆動部品の保証期間はどれくらいですか？ | 20か月 | モーター保証期間は20か月で見積もっている。 | モーター保証期間 / 駆動部品の保証期間 | F1 保証期間 [['の', '駆動部品']] | Q3 attribute question, no position with its slot noun | fact stored as an event (F3) | none |
| D02 | cont/reph | 朝一番に組立作業をする場所の温度表示は何度ですか？ | 矛盾: 19.5度 と 21度 | 組立室の朝の室温は19.5度だった。 // 組立室の朝は温度表示が21度だった。 | 組立室の朝の室温 / 場所の温度表示 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two) | wrong |
| D02 | upda/reph | 先行機が工房を出る日程はいつですか？ | 11月5日 | 先行試作の工房出荷日は11月3日から11月5日に変更になった。 | 先行試作の工房出荷日 / 工房を出る日程 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | gold |
| D02 | plai/reph | 洗ったごみ容器が乾くまでの目安は何分ですか？ | 17分 | ケースを水洗いした後の乾燥時間は17分だった。 | ケースを水洗いした後の乾燥時間 / ごみ容器が乾くまでの目安 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (all) | none |
| D02 | cont/reph | 床材を再現する粉の混ぜ方はどう記録されていますか？ | 矛盾: 8対2 と 7対3 | 模擬砂の配合比は8対2で試験票を作った。 // 模擬砂の比率は7対3と試験帳に残っていた。 | 模擬砂の配合比 / 粉の混ぜ方 | no_question_word | Q1 question not read (no_question_word) | fact stored as an event (F3) | none |
| D02 | plai/reph | 購入検討者向けの説明会場はどこですか？ | 繭輪市の殻間広場 | 販売説明会の開催地は繭輪市の殻間広場に決まった。 | 販売説明会の開催地 / 購入検討者向けの説明会場 | F1 説明会場 [['の', '購入検討者向け']] | Q3 attribute question, no position with its slot noun | fact stored as an event (F3) | none |
| D02 | cont/reph | 試験後の箱を運送会社が回収する日はいつですか？ | 矛盾: 11月17日 と 11月19日 | 返却用箱の集荷日は11月17日で輸送票に書いた。 // 返却用箱の集荷日は11月19日と輸送表にある。 | 返却用箱の集荷日 / 試験後の箱を運送会社が回収する日 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two); fact stored as an event (F3) | none |
| D02 | upda/reph | 組付け確認の集まりは何日に開かれますか？ | 11月14日 | 組付け確認会は11月12日から11月14日に変更になった。 | 組付け確認会 / 組付け確認の集まり | F3 開く [] | Q2 question read as an event (F3), memory holds an attribute | - | gold |
| D02 | plai/reph | 持ち手の試作品にはどの樹脂を使いましたか？ | 再生ABS樹脂 | 天面取っ手の試作品素材は再生ABS樹脂だった。 | 天面取っ手の試作品素材 / 持ち手の試作品 | no_question_word | Q1 question not read (no_question_word) | - | gold |
| D02 | cont/reph | 展示に使う試作機は何台と数えられていますか？ | 矛盾: 2台 と 3台 | 展示向けの試作機台数は2台で組んである。 // 展示向け試作機は3台と資材控えに載っていた。 | 展示向けの試作機台数 / 展示に使う試作機 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | fact stored as an event (F3) | none |
| D02 | upda/reph | 売り場で評価してもらう機体はいくつですか？ | 10台 | 店頭評価機の割当数は12台から10台に変更になった。 | 店頭評価機の割当数 / 売り場で評価してもらう機体 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | none |
| D02 | plai/reph | 二号機を床から測った高さは何センチですか？ | 9.4センチ | 二号機の全高は9.4センチに収まった。 | 二号機の全高 / 床から測った高さ | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | fact stored as an event (F3) | none |
| D02 | cont/reph | 予備の蓄電池は何日に届く見込みですか？ | 矛盾: 18日 と 24日 | 予備電池の納入見込みは18日と問屋から返ってきた。 // 予備電池は問屋の予定表で24日着になっていた。 | 予備電池の納入見込み / 予備の蓄電池 | frame_not_read:no_predicate | Q1 question not read (frame_not_read:no_predicate) | stored sentence F0 (all) | none |
| D02 | cont/reph | 音を測る際、掃除機からマイクまで何メートル離しますか？ | 矛盾: 1.0メートル と 1.2メートル | 吸引音の評価距離は1.0メートルに固定した。 // 吸引音の評価距離は1.2メートルと試験帳の別紙に書いてあった。 | 吸引音の評価距離 / 掃除機からマイクまで | several_clauses | Q1 question not read (several_clauses) | fact stored as an event (F3) | none |
| D02 | plai/reph | 蓄電池の経時確認はいつ始める予定ですか？ | 11月18日 | 蓄電池の経時試験開始日は11月18日に仮置きした。 | 蓄電池の経時試験開始日 / 蓄電池の経時確認 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (all) | none |
| D02 | upda/reph | 充電耐久で許容する上限回数はいくつですか？ | 60サイクル | 充電耐久上限は48サイクルから60サイクルに変更になった。 | 充電耐久上限 / 充電耐久で許容する上限回数 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | tie |
| D02 | plai/reph | 二号機を持ち上げた時の重さはいくらですか？ | 3.1キロ | 二号機の重量は3.1キロで台帳に残した。 | 二号機の重量 / 二号機を持ち上げた時の重さ | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | fact stored as an event (F3) | none |
| D02 | cont/reph | 最初の量産分に用意する梱包箱はいくつですか？ | 矛盾: 720箱 と 760箱 | 初回量産用の箱は720箱で資材票に置いた。 // 初回量産用の箱は760箱で資材表に記入されていた。 | 初回量産用の箱 / 最初の量産分に用意する梱包箱 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two); fact stored as an event (F3) | none |
| D02 | upda/reph | 説明書の校正原稿はいつまでに戻しますか？ | 11月22日 | 取扱説明書の校正返却日は11月20日から11月22日に変更になった。 | 説明書の校正返却日 / 校正原稿 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D02 | plai/reph | 交換用の駆動輪について問屋が示した合計はいくらですか？ | 143,000円 | 部品交換の見積総額は143,000円で問屋に届いている。 | 部品交換の見積総額 / 問屋が示した合計 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | fact stored as an event (F3) | none |
| D02 | cont/reph | 基板の試作品を受け取るのは何日ですか？ | 矛盾: 11月2日 と 11月4日 | 基板の試作受取日は11月2日で便を頼んだ。 // 基板の試作受取日は11月4日だと便名に書き込まれている。 | 基板の試作受取日 / 基板の試作品を受け取る | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two); fact stored as an event (F3) | none |
| D02 | plai/reph | 取材向けの資料一式はいつから閲覧できますか？ | 12月18日 | 報道資料セットの閲覧開始日は12月18日にした。 | 報道資料セットの閲覧開始日 / 取材向けの資料一式 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | - | gold |
| D02 | cont/reph | 売り場用の見本機を何台配る計画ですか？ | 矛盾: 36台 と 40台 | 店頭見本の配布台数は36台で案内票を作った。 // 営業用見本機の準備数は40台と手配表に載った。 | 店頭見本の配布台数 / 売り場用の見本機を何台配る | F4 計画 [] | Q2b question read as an event, memory holds an event | fact stored as an event (F3) | none |
| D02 | upda/reph | 新型機の販売開始日はいつですか？ | 1月22日 | 発売日は1月15日から1月22日に変更になった。 | 発売日 / 新型機の販売開始日 | F1 販売開始日 [['の', '新型機']] | Q3 attribute question, no position with its slot noun | - | wrong |
| D02 | plai/reph | 販売の場で示す金額はいくらですか？ | 48,600円 | 店頭想定価格は48,600円に置いた。 | 店頭想定価格 / 販売の場で示す金額 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | - | none |
| D02 | cont/reph | 発売後の安全相談窓口へかける内線番号はいくつですか？ | 矛盾: 4316 と 4318 | 発売時の安全窓口内線は4316で申請票に入れた。 // 発売時の安全窓口内線は4318だと運用表の控えにある。 | 発売時の安全窓口内線 / 安全相談窓口へかける内線番号 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (one of two); fact stored as an event (F3) | none |
| D02 | upda/reph | 販売店への先行分は何日に納めますか？ | 1月11日 | 販売拠点への先行納入日は1月8日から1月11日に変更になった。 | 販売拠点への先行納入日 / 販売店への先行分 | frame_not_read:gap_is_not_a_particle | Q1 question not read (frame_not_read:gap_is_not_a_particle) | stored sentence F0 (all) | none |
| D02 | plai/reph | 操作ガイドの初版で選べる言語は何ですか？ | 日本語と英語 | 操作ガイドの初版対応言語は日本語と英語にした。 | 操作ガイドの初版対応言語 / 初版で選べる言語 | frame_not_read:case_before_topic | Q1 question not read (frame_not_read:case_before_topic) | stored sentence F0 (all) | none |
| D02 | cont/reph | 販促映像の再生時間は何秒ですか？ | 矛盾: 74秒 と 82秒 | 販促用の短い動画は74秒で編集卓に入っていた。 // 販促用の短い動画は82秒だと編集控えに残っていた。 | 販促用の短い動画 / 販促映像の再生時間 | F1 再生時間 [['の', '販促映像']] | Q3 attribute question, no position with its slot noun | stored sentence F0 (one of two); fact stored as an event (F3) | none |
