## tok (18): I2-001, I2-007, I2-008, I2-015, I2-016, I2-018, I2-019, I2-026, I2-038, I2-040, I2-041, I2-046, I2-047, I2-050, R2-I008, R2-I009, R2-I011, R2-I014
- **I2-001** ハッシュテーブルの別名は何ですか | gold `ハッシュ表` | gold sentence: ハッシュ表ともいう。
  - RUN units of gold sentence: ハッシュ/表/ともいう; gold one RUN unit: no (spans 2); question RUN units ['ハッシュテーブル', '別名'], shared with gold sentence []
  - verdicts R/W/C: CHOICE/UNKNOWN_RATIO_DISAGREEMENT/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['ハッシュテーブル', '効率的な', '実装', '連想配列', '集合'] (of 5 holding a question unit); gold units in tier: []
  - ssp listed 22 entries; first: [RUN] 1つ/のうち/ハッシュテーブル ; [RUN] 1つ/のうち/ハッシュテーブル/効率的な/実装 ; [RUN] 1つ/のうち/ハッシュテーブル/効率的な/連想配列
- **I2-007** 沢辺駅が廃駅となったのは何に伴うものですか | gold `路線の廃止` | gold sentence: 2007年（平成19年）、路線の廃止に伴い廃駅となった。
  - RUN units of gold sentence: 2007年/平成19年/路線/廃止/伴い/廃駅; gold one RUN unit: no (spans None); question RUN units ['沢辺駅', '廃駅', '伴', 'うものですか'], shared with gold sentence ['廃駅']
  - verdicts R/W/C: CHOICE/ANSWER/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['廃駅', '伴', '沢辺駅', '駅', '伴い', '国鉄', '日本国有鉄道', '縄文時代'] (of 33 holding a question unit); gold units in tier: []
  - ssp listed 21 entries; first: [RUN] おおぐるわかいづか/主体/大曲輪貝塚/環状集落/縄文時代 ; [RUN] おおぐるわかいづか/主体/愛知県名古屋市瑞穂区/環状集落/縄文時代 ; [RUN] おおぐるわかいづか/主体/環状集落/縄文時代/貝塚
- **I2-008** 唯物史観を唱えた人物は誰ですか | gold `カール・マルクス` | gold sentence: 19世紀にカール・マルクスが唱えた歴史観である。
  - RUN units of gold sentence: 19世紀/カール/マルクス/唱/えた/歴史観; gold one RUN unit: no (spans 2); question RUN units ['唯物史観', '唱', 'えた', '人物'], shared with gold sentence ['唱', 'えた']
  - verdicts R/W/C: CHOICE/CHOICE/ANSWER; read RUN crosses ['えた', '人物', '唱', '唯物史観', '登場', '備'] (of 24 holding a question unit); gold units in tier: []
  - ssp listed 41 entries; first: [RUN] 19世紀/えた/カール/マルクス/唱/歴史観 ; [RUN] 人物/旧約聖書/登場 ; [WORD] イム/オナン/マハナ/人物/創世/登場/記
- **I2-015** 七里村の地域は現在、どの市のどの区の一部にあたりますか | gold `さいたま市見沼区` | gold sentence: 現在のさいたま市見沼区の一部にあたる。
  - RUN units of gold sentence: 現在のさいたま/市見沼区/の一部にあたる; gold one RUN unit: no (spans 2); question RUN units ['七里村', '地域', 'は現在', '市', 'のどの', '区', 'の一部にあたりますか'], shared with gold sentence []
  - verdicts R/W/C: CHOICE/CHOICE/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['市', '地域', 'のどの', '七里村', 'アメリカ', 'ニューヨーク', '文化', 'くは'] (of 22 holding a question unit); gold units in tier: []
  - ssp listed 51 entries; first: [RUN] くは/アメリカ/ニューヨーク/ハガチー/多/始/市 ; [RUN] くは/アメリカ/ニューヨーク/古/多/始/市 ; [RUN] くは/アメリカ/ニューヨーク/始/市

## noquery (20): I2-010, I2-011, I2-017, I2-020, I2-023, I2-032, I2-035, I2-039, I2-043, I2-044, R2-I002, R2-I003, R2-I004, R2-I006, R2-I007, R2-I010, R2-I012, R2-I015, R2-I017, R2-I019
- **I2-010** ブリティッシュ・エアウェイズはヨーロッパで何位の規模ですか | gold `3位` | gold sentence: ヨーロッパでは3位、世界では9位の規模を誇る大手航空会社であり、イギリスのフラッグ・キャリアである。
  - RUN units of gold sentence: ヨーロッパ/3位/世界/9位/規模/誇/大手航空会社/であり/イギリス/フラッグ/キャリア; gold one RUN unit: ['3位']; question RUN units ['ブリティッシュ', 'エアウェイズ', 'ヨーロッパ', '規模'], shared with gold sentence ['ヨーロッパ', '規模']
  - verdicts R/W/C: UNKNOWN_SECTION_DISAGREEMENT/CHOICE/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['エアウェイズ', 'ブリティッシュ', 'ヨーロッパ', '規模'] (of 4 holding a question unit); gold units in tier: ['3位']
  - ssp listed 25 entries; first: [WORD] Google/LaMDA/ファミリー/モデル/ラムダ/型/言語 ; [WORD] Google/LaMDA/ファミリー/ラムダ/型 ; [WORD] Google/LaMDA/ファミリー/ラムダ/言語
- **I2-011** 「改名」と同じ意味の語は何ですか | gold `改称` | gold sentence: 改称（かいしょう）も同義。
  - RUN units of gold sentence: 改称/かいしょう/同義; gold one RUN unit: ['改称']; question RUN units ['改名', '同', 'じ', '意味', '語'], shared with gold sentence []
  - verdicts R/W/C: ANSWER/ANSWER/ANSWER; read RUN crosses ['意味', '語', 'じ', '同', '改名', 'という'] (of 49 holding a question unit); gold units in tier: ['改称']
  - ssp listed 8 entries; first: [RUN] という/意味/語 ; [WORD] 中央/名/地域/語 ; [CHAR] 2/a/l/n/o/ト/フ/ブ/..(13)
- **I2-017** IEEE 488の通称は何ですか | gold `GPIB` | gold sentence: 通称GPIB（General Purpose Interface Bus）とも呼ばれ、最大15台の機器をデイジーチェーン（順次接続する方式）で接続でき、計測器の制御やデータ収集に広く用いられる。
  - RUN units of gold sentence: 通称/GPIB/General/Purpose/Interface/Bus/とも/呼/ばれ/最大15台/機器/デイジーチェーン/順次接続/方式/接続/計測器/制御/や/データ/収集; gold one RUN unit: ['GPIB']; question RUN units ['IEEE', '488の', '通称'], shared with gold sentence ['通称']
  - verdicts R/W/C: UNKNOWN_NO_FIXED_POINT/CHOICE/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['通称', 'IEEE', 'とも', 'PSE', 'ふかがわはちまんぐう', 'エス', '深川八幡宮'] (of 7 holding a question unit); gold units in tier: ['GPIB']
  - ssp listed 15 entries; first: [WORD] がわ/はち/ふか/八幡/称さ ; [WORD] がわ/はち/ふか/宮/称さ ; [WORD] がわ/はち/八幡/深川/称さ
- **I2-020** 善五郎の当代は何代目ですか | gold `17代目` | gold sentence: 現在は17代目。
  - RUN units of gold sentence: 現在は/17代目; gold one RUN unit: ['17代目']; question RUN units ['善五郎', '当代', '何代目'], shared with gold sentence []
  - verdicts R/W/C: UNKNOWN_NO_EVIDENCE/CHOICE/CHOICE; read RUN crosses ['善五郎', 'ぜんごろう', '京焼', '家元'] (of 4 holding a question unit); gold units in tier: ['17代目']
  - ssp listed 29 entries; first: [WORD] 17/2005/FIFA/かけ/カップ/ワールド/日/月/..(10) ; [WORD] 2/2022/4/6/令和/年/目/第/..(10) ; [WORD] 2022/6/令和/年/目/第/行わ

## budget (6): I2-012, I2-025, I2-028, I2-033, I2-045, R2-I013
- **I2-012** 富岡八幡宮は通称で何と呼ばれますか | gold `深川八幡宮` | gold sentence: 通称で深川八幡宮（ふかがわはちまんぐう）とも称される。
  - RUN units of gold sentence: 通称/深川八幡宮/ふかがわはちまんぐう/とも/称; gold one RUN unit: ['深川八幡宮']; question RUN units ['富岡八幡宮', '通称', '呼', 'ばれますか'], shared with gold sentence ['通称']
  - verdicts R/W/C: ANSWER/ANSWER/ANSWER; read RUN crosses ['呼', '通称', '富岡八幡宮', 'とも', 'ばれる', 'ぶ', '用い', 'ばれ', '英語', 'データ'] (of 45 holding a question unit); gold units in tier: ['深川八幡宮']
  - ssp listed 17 entries; first: [RUN] とも/言/訳 ; [WORD] カウンタ/列車/用い/装置/車軸 ; [CHAR] 八/在/安/定/宮/川/幡/当/..(13)
- **I2-025** レッド計画ではアメリカを何色としていましたか | gold `青` | gold sentence: イギリスを「赤」、アメリカを「青」と色分けし、万一米英間に戦争が起こった場合の作戦について軍部に研究させていた。
  - RUN units of gold sentence: イギリス/赤/アメリカ/青/色分/けし/万一米英間/戦争/起/こった場合の/作戦/軍部/研究; gold one RUN unit: ['青']; question RUN units ['レッド', '計画', 'アメリカ', '何色'], shared with gold sentence ['アメリカ']
  - verdicts R/W/C: ANSWER/ANSWER/CHOICE; read RUN crosses ['アメリカ', '計画', 'レッド', '合衆国', 'イギリス', 'ニューヨーク', '大学', '市', '20世紀初頭', '戦争'] (of 14 holding a question unit); gold units in tier: ['東京都青梅市柚木町', '青', '青ヶ', '青海町']
  - ssp listed 28 entries; first: [RUN] アメリカ/ニューヨーク/合衆国/市/戦争 ; [WORD] えき/区/大字/市/町/県/鉄道 ; [CHAR] 2/I/イ/ス/タ/ド/ル/ン/..(11)
- **I2-028** 大曲輪貝塚は別名で何と呼ばれますか | gold `大曲輪遺跡` | gold sentence: 貝塚以外の遺構も見つかっていることから、大曲輪遺跡（おおぐるわいせき）とも呼ばれる。
  - RUN units of gold sentence: 貝塚以外/遺構/つかっていることから/大曲輪遺跡/おおぐるわいせき/とも/呼/ばれる; gold one RUN unit: ['大曲輪遺跡']; question RUN units ['大曲輪貝塚', '別名', '呼', 'ばれますか'], shared with gold sentence ['呼']
  - verdicts R/W/C: ANSWER/ANSWER/ANSWER; read RUN crosses ['呼', '大曲輪貝塚', 'とも', 'ばれる', 'ぶ', '用い', 'ばれ', '英語', 'データ', '噴火'] (of 41 holding a question unit); gold units in tier: ['大曲輪遺跡']
  - ssp listed 23 entries; first: [RUN] とも/言/訳 ; [WORD] カウンタ/列車/用い/装置/車軸 ; [CHAR] 1/3/9/ア/イ/ス/タ/ッ/..(19)
- **I2-033** ニュクティーモスの父である王は誰ですか | gold `リュカーオーン` | gold sentence: アルカディアー地方の王リュカーオーンの50人の子供の末子。
  - RUN units of gold sentence: アルカディアー/地方/王リュカーオーン/50人/子供/末子; gold one RUN unit: ['王リュカーオーン']; question RUN units ['ニュクティーモス', '父', '王'], shared with gold sentence []
  - verdicts R/W/C: UNKNOWN_NO_EVIDENCE/UNKNOWN_RATIO_DISAGREEMENT/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['ニュクティーモス', '父'] (of 13 holding a question unit); gold units in tier: ['王リュカーオーン']
  - ssp listed 11 entries; first: [CHAR/L1] 0/1/2/3/4/5/6/7/..(145) ; [CHAR/L1] 0/1/2/3/4/5/6/7/..(148) ; [CHAR/L2] ィ/イ/ク/ス/テ/ニ/モ/ュ/..(13)

## nofix (1): I2-036
- **I2-036** NGC 36を発見したのはいつですか | gold `1785年10月25日` | gold sentence: 1785年10月25日にウィリアム・ハーシェルによって発見された。
  - RUN units of gold sentence: 1785年10月25日に/ウィリアム/ハーシェル/発見; gold one RUN unit: ['1785年10月25日に']; question RUN units ['NGC', '36を', '発見'], shared with gold sentence ['発見']
  - verdicts R/W/C: ANSWER/CHOICE/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['発見', 'NGC', '1785年10月25日に', '36は', 'うお', 'ウィリアム', 'ハーシェル', '座', '方角', '渦巻銀河'] (of 10 holding a question unit); gold units in tier: ['1785年10月25日に']
  - ssp listed 16 entries; first: [RUN] 36は/NGC/うお/座/方角/渦巻銀河 ; [WORD] 10/1785/25/ウィリアム/ハーシェル/月/発見 ; [WORD] 10/1785/25/ウィリアム/日/月/発見

## noagree (7): I2-003, I2-005, I2-006, I2-013, I2-021, I2-030, I2-031
- **I2-003** 川原石駅の駅番号は何ですか | gold `JR-Y13` | gold sentence: 駅番号はJR-Y13。
  - RUN units of gold sentence: 駅番号/JR-Y13; gold one RUN unit: ['JR-Y13']; question RUN units ['川原石駅', '駅番号'], shared with gold sentence ['駅番号']
  - verdicts R/W/C: AMBIGUOUS/CHOICE/ANSWER; read RUN crosses ['駅番号', '川原石駅'] (of 11 holding a question unit); gold units in tier: ['JR-Y13']
  - ssp listed 16 entries; first: [WORD] えき/き/位置/共和/区/国/大字/市/..(13) ; [WORD] ドイツ/上/以下/便宜/共和/国/市/町/..(11) ; [CHAR] 2/ン/ー/原/地/大/字/川/..(13)
- **I2-005** 海老津駅の駅番号は何ですか | gold `JA16` | gold sentence: 駅番号はJA16。
  - RUN units of gold sentence: 駅番号/JA16; gold one RUN unit: ['JA16']; question RUN units ['海老津駅', '駅番号'], shared with gold sentence ['駅番号']
  - verdicts R/W/C: AMBIGUOUS/CHOICE/ANSWER; read RUN crosses ['駅番号', '海老津駅'] (of 11 holding a question unit); gold units in tier: ['JA16']
  - ssp listed 11 entries; first: [WORD] えき/き/位置/共和/区/国/大字/市/..(13) ; [WORD] ドイツ/上/以下/便宜/共和/国/市/町/..(11) ; [CHAR] 会/南/大/島/川/建/本/津/..(13)
- **I2-006** 海浦駅の駅番号は何ですか | gold `OR08` | gold sentence: 駅番号はOR08。
  - RUN units of gold sentence: 駅番号/OR08; gold one RUN unit: ['OR08']; question RUN units ['海浦駅', '駅番号'], shared with gold sentence ['駅番号']
  - verdicts R/W/C: UNKNOWN_NO_EVIDENCE/CHOICE/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['駅番号', '海浦駅'] (of 11 holding a question unit); gold units in tier: ['OR08']
  - ssp listed 10 entries; first: [WORD] えき/き/位置/共和/区/国/大字/市/..(13) ; [WORD] ドイツ/上/以下/便宜/共和/国/市/町/..(11) ; [CHAR/L1] 0/1/2/3/4/5/6/7/..(153)
- **I2-013** 千葉神社の旧社格は何ですか | gold `県社` | gold sentence: 旧社格は県社。
  - RUN units of gold sentence: 旧社格/県社; gold one RUN unit: ['県社']; question RUN units ['千葉神社', '旧社格'], shared with gold sentence ['旧社格']
  - verdicts R/W/C: UNKNOWN_NO_FIXED_POINT/ANSWER/CHOICE; read RUN crosses ['旧社格', '千葉神社', '県社', 'ちばじんじゃ', '別表神社', '千葉県千葉市中央区', '神社本庁'] (of 7 holding a question unit); gold units in tier: ['県社']
  - ssp listed 16 entries; first: [WORD] むら/区/大字/存在/市/村/田村/町/..(10) ; [CHAR] イ/ス/ブ/ラ/ン/ー/京/制/..(16) ; [CHAR] イ/ス/ブ/ラ/ン/ー/京/千/..(16)

## select (1): R2-I018
- **R2-I018** 2014年国勢調査でのテレゴ県の住民数は何人でしたか | gold `20万人` | gold sentence: 面積は1,102平方キロメートル、人口は20万人（2014年国勢調査）、23万人（2020年投影人口。
  - RUN units of gold sentence: 面積/は1/102平方キロメートル/人口/20万人/2014年国勢調査/23万人/2020年投影人口; gold one RUN unit: ['20万人']; question RUN units ['2014年国勢調査', 'テレゴ', '県', '住民数', '何人'], shared with gold sentence ['2014年国勢調査']
  - verdicts R/W/C: CHOICE/ANSWER/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['県', 'テレゴ', '2014年国勢調査', '位置', 'イタリア', '基礎自治体', 'けん', 'コムーネ', '北部'] (of 71 holding a question unit); gold units in tier: ['20万人']
  - ssp listed 19 entries; first: [RUN] 6つ/ウガンダ/テレゴ/副郡/北部地域 ; [RUN] 6つ/ウガンダ/テレゴ/副郡/西ナイル ; [RUN] 6つ/テレゴ/副郡/北部地域/西ナイル

## hit (16): I2-002, I2-004, I2-009, I2-014, I2-022, I2-024, I2-027, I2-029, I2-034, I2-037, I2-042, I2-048, R2-I001, R2-I005, R2-I016, R2-I020
- **I2-002** 連結グラフで、極大で連結な部分グラフは何と呼ばれますか | gold `連結成分` | gold sentence: 極大で連結な部分グラフは、連結成分（connected component）という。
  - RUN units of gold sentence: 極大/連結な/部分グラフ/連結成分/connected/component/という; gold one RUN unit: ['連結成分']; question RUN units ['連結グラフ', '極大', '連結な', '部分グラフ', '呼', 'ばれますか'], shared with gold sentence ['極大', '連結な', '部分グラフ']
  - verdicts R/W/C: ANSWER/CHOICE/ANSWER; read RUN crosses ['呼', '極大', '連結な', '部分グラフ', '連結グラフ', 'とも', 'ばれる', 'ぶ', '用い'] (of 45 holding a question unit); gold units in tier: ['連結成分']
  - ssp listed 19 entries; first: [RUN] とも/言/訳 ; [WORD] component/connected/グラフ/連結/部分 ; [WORD] component/グラフ/成分/連結/部分
- **I2-004** 花園町駅の駅番号は何ですか | gold `Y17` | gold sentence: 駅番号はY17。
  - RUN units of gold sentence: 駅番号/Y17; gold one RUN unit: ['Y17']; question RUN units ['花園町駅', '駅番号'], shared with gold sentence ['駅番号']
  - verdicts R/W/C: AMBIGUOUS/CHOICE/CHOICE; read RUN crosses ['駅番号', '花園町駅', 'JA16', 'JR-Y13', 'Metro', 'OR08', 'Y17', '四', '橋線'] (of 9 holding a question unit); gold units in tier: ['Y17']
  - ssp listed 12 entries; first: [WORD] えき/き/位置/共和/区/国/大字/市/..(13) ; [WORD] ドイツ/上/以下/便宜/共和/国/市/町/..(11) ; [CHAR] 公/区/園/大/市/成/線/道/..(9)
- **I2-009** ビー・ジーズのメンバー全員が共通して担当する役割は何ですか | gold `ボーカル` | gold sentence: 全員共通してボーカルを担当。
  - RUN units of gold sentence: 全員共通/ボーカル/担当; gold one RUN unit: ['ボーカル']; question RUN units ['ジーズ', 'メンバー', '全員', '共通', '担当', '役割'], shared with gold sentence ['担当']
  - verdicts R/W/C: UNKNOWN_NO_FIXED_POINT/ANSWER/UNKNOWN_NO_FIXED_POINT; read RUN crosses ['メンバー', '担当', 'ジーズ', 'dropz', 'ワーキングホリデー', '全員共通', '日本人', '星野英彦ソロプロジェクト', '滞在'] (of 9 holding a question unit); gold units in tier: ['ボーカル']
  - ssp listed 15 entries; first: [WORD] dropz/ソロ/プロジェクト/メンバー/参加/星野/英彦 ; [CHAR/L1] 0/1/2/3/4/5/6/7/..(158) ; [CHAR/L2] イ/ジ/ス/ズ/ト/バ/ビ/メ/..(13)
- **I2-014** 千葉神社の社紋は何ですか | gold `九曜紋` | gold sentence: 神紋は三光紋（月星）、社紋は九曜紋。
  - RUN units of gold sentence: 神紋/三光紋/月星/社紋/九曜紋; gold one RUN unit: ['九曜紋']; question RUN units ['千葉神社', '社紋'], shared with gold sentence ['社紋']
  - verdicts R/W/C: ANSWER/ANSWER/CHOICE; read RUN crosses ['千葉神社', '社紋', 'ちばじんじゃ', '三光紋', '九曜紋', '千葉県千葉市中央区', '月星', '神紋'] (of 8 holding a question unit); gold units in tier: ['九曜紋']
  - ssp listed 22 entries; first: [RUN] 三光紋/九曜紋/月星/社紋/神紋 ; [WORD] 企業/出版/社 ; [CHAR] イ/ス/ブ/ラ/ン/ー/京/制/..(16)

