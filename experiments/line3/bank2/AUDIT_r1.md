# Audit of bank2.tsv

Auditor: Claude (Opus 5.5), 2026-10-08. Inputs: `bank2.tsv`, `../S300_fulllead.jsonl`, `../S3000.jsonl`, `../PROMPT.md`, author's `check.py`.

Outputs: `bank2_audited.tsv` (valid + fixed rows, extra column `audit`), `check_audited.py` / `check_audited.txt`, `baselines.py` / `baselines.txt`.

## Counts

| kind | before | valid | fixed | dropped | after |
|---|---|---|---|---|---|
| intra2 | 50 | 32 | 17 | 1 | 49 |
| cross2 | 30 | 0 | 8 | 22 | 8 |
| unans | 40 | 35 | 5 | 0 | 40 |
| total | 120 | 67 | 30 | 23 | 97 |

unans after: 20 fulllead + 20 s3000 (unchanged split).

## Main problems found

1. **cross2 did not test bridging at all.** All 30 original cross2 questions literally name the bridge entity B
   (e.g. 「城站駅が位置する**杭州市**は…」), so each is a one-hop lookup of B's sentence; keyword lookup B1 already found
   the gold in 15-16/30. In addition 15 were definitional/dictionary questions with long clause golds
   (選挙区, 丸木舟, ミドルウェア, 核兵器, 形態素, アカデミー, 世界地図, 文化圏, 図書館員, ...), two had A's title containing B
   (レバノン選手団, ノーフォーク伯爵: cannot be asked without naming B), and B was reused (豊橋市 x3, 杭州市/選挙区/スキー/テニス/栃木県 x2).
   Kept only pairs where the question can be rephrased as "the X where A is" without naming B and the gold is short: 8 items.
   **cross2 is now too small (8) to report a rate; it needs ~20 newly authored items** (rule for the author: the question must not
   contain B's title, and A's title must not contain B's title).
2. **intra2 is real but shallow.** All 49 kept golds sit in a sentence without the title, but 34/49 evidence sentences are the
   sentence immediately after a title-bearing sentence (31 are sentence #1), and many evidence sentences repeat the question's
   own key word (駅番号, 旧社格, 社紋, 通称, 別名 forms). 4 items (I2-003..006) are one template (駅番号は…).
3. **Guessable / in-question golds:** I2-049 (アジア in question, dropped), I2-025 (赤 from レッド), I2-032 (千里馬運動 from 千里馬区域),
   I2-033 (ニュクティモス = title minus ー), I2-035 (黒い in question → 黒パン), I2-034 (35 = サンゴー). Fixed by asking a different fact.
4. **Questions without the subject** (pure lookup of the evidence wording, or ambiguous): I2-002, I2-041, I2-044, I2-047; unans US-002, US-008, US-010, US-019.
5. **Gold form/alternatives:** 永樂（えいらく）姓 (reading inside gold), 西村姓 without 西村, USB without イーサネット/LXI, I2-045 with two correct aliases in two sentences.
6. **unans are sound:** for all 40 the subject is mentioned in no other article of its corpus file, and keyword greps for the asked
   attribute (開業, 声優, 優勝, 標高, 列車番号, ...) find nothing relevant; s3000 unans answers are also absent from the subjects' full leads.
   Minor tell: 10/40 unans use 最初/初めて ("first ...") phrasing; no answerable item asks a "first X" question (only I2-048 初優勝).

## Re-check

`check_audited.py` = author's checker adapted to `bank2_audited.tsv` (expects 49/8/40, validates `audit` column, and additionally fails if
any gold occurs in the question). Result: 97 questions, 97/97 unique ids, **0 constraint errors** (see `check_audited.txt`).

## Baselines (from `baselines.txt`; gold-in-candidate, ties kept)

| kind | n | B1 MeCab | B2 MeCab | B1 bigram | B2 bigram |
|---|---|---|---|---|---|
| intra2 | 49 | 32 (65%) | 42 (86%) | 26 (53%) | 41 (84%) |
| cross2 | 8 | 1 (12%) | 7 (88%) | 1 (12%) | 8 (100%) |
| unans | 40 | returns a candidate 40/40 | 40/40 | 40/40 | 40/40 |

Original bank2.tsv for comparison: cross2 B1 50-53%, B2 97-100%; intra2 B1 64-68%, B2 86-88%.

Reading: the audited bank separates *one-sentence* keyword lookup from anything that crosses a sentence (cross2 12%, intra2 53-65%
vs 56-58/60 on the old bank), but a *trivial* two-hop heuristic (top sentence + next sentence / + article whose title appears in it)
recovers 84-100%. So the bank can show that a system goes beyond B1, but it cannot by itself show that a structure does more than B2.
Hard core (missed by B2 with both tokenizers): 6 intra2 items whose evidence is not the sentence right after the best-matching sentence (e.g. I2-011, I2-014, I2-029, I2-039).
To discriminate structure from B2 the next bank needs intra2 evidence that is not adjacent to the title sentence and cross2 bridges
where A's sentence contains several titled entities (so "follow every title" is noisy) and the question does not name B.

## Per-item decisions

Format: id — decision — reason; for fixes the changed fields are shown (old → new).

- **I2-001** (intra2) — valid — ok
- **I2-002** (intra2) — fix — question did not name the subject at all (pure keyword lookup of sentence 2 wording); subject added
    - question: `極大で連結な部分グラフは何と呼ばれますか` → `連結グラフで、極大で連結な部分グラフは何と呼ばれますか`
- **I2-003** (intra2) — valid — ok (one of 4 near-identical 駅番号 template items 003-006; kept, but they are a single question pattern)
- **I2-004** (intra2) — valid — ok
- **I2-005** (intra2) — valid — ok
- **I2-006** (intra2) — valid — ok
- **I2-007** (intra2) — valid — ok
- **I2-008** (intra2) — valid — ok
- **I2-009** (intra2) — valid — ok
- **I2-010** (intra2) — valid — ok
- **I2-011** (intra2) — valid — ok
- **I2-012** (intra2) — valid — ok
- **I2-013** (intra2) — valid — ok
- **I2-014** (intra2) — valid — ok
- **I2-015** (intra2) — valid — ok
- **I2-016** (intra2) — valid — ok; alternative 地上 rejected because 地上 also occurs in the title sentence (地上絵)
- **I2-017** (intra2) — valid — ok
- **I2-018** (intra2) — valid — ok
- **I2-019** (intra2) — valid — ok
- **I2-020** (intra2) — valid — ok
- **I2-021** (intra2) — fix — gold alternative added (西村 is an equally correct answer)
    - gold: `西村姓` → `西村姓|西村`
- **I2-022** (intra2) — fix — gold 「永樂（えいらく）姓」 contained the reading in parentheses; a reader answering 永樂 would be marked wrong
    - gold: `永樂（えいらく）姓` → `永樂`
- **I2-023** (intra2) — fix — gold repeated the question word 時代風潮; gold reduced to the informative part
    - gold: `富国強兵の時代風潮` → `富国強兵`
- **I2-024** (intra2) — valid — ok
- **I2-025** (intra2) — fix — gold 赤 is guessable from the subject name レッド計画 (red); asked for the other colour instead
    - question: `レッド計画ではイギリスを何色に分類しましたか` → `レッド計画ではアメリカを何色としていましたか`
    - gold: `赤` → `青`
- **I2-026** (intra2) — valid — ok
- **I2-027** (intra2) — fix — question unnatural (asked the subject term back as "フットチョークと呼ばれる技の名称"); rephrased
    - question: `ブラジリアン柔術でフットチョークと呼ばれる技の名称は何ですか` → `フットチョークはブラジリアン柔術では何と呼ばれますか`
- **I2-028** (intra2) — valid — ok
- **I2-029** (intra2) — valid — ok
- **I2-030** (intra2) — valid — ok
- **I2-031** (intra2) — fix — question unnatural and gold incomplete (イーサネット and LXI are equally correct)
    - question: `IEEE 488の後継規格への移行に使われている通信方式の一つは何ですか` → `IEEE 488の後継規格にはどのような通信方式が使われていますか`
    - gold: `USB` → `USB|イーサネット|LXI`
- **I2-032** (intra2) — fix — gold 千里馬運動 guessable from subject 千里馬区域 + question word 運動; asked for the facility instead
    - question: `千里馬区域の名称の由来として挙げられる運動は何ですか` → `千里馬区域で千里馬運動の発祥の地とされた施設は何ですか`
    - gold: `千里馬運動` → `製鋼所`
- **I2-033** (intra2) — fix — gold ニュクティモス is the title minus 「ー」 (guessable); asked for the father (sentence 2, no title)
    - question: `ニュクティーモスは長母音を省略するとどう表記されますか` → `ニュクティーモスの父である王は誰ですか`
    - gold: `ニュクティモス` → `リュカーオーン`
    - evidence: `ニュクティーモス#1` → `ニュクティーモス#2`
- **I2-034** (intra2) — fix — gold 35（SUNGO）カメラ largely guessable from サンゴー=35 and an odd string to expect; asked for founding year (sentence 1, no title)
    - question: `サンゴーカメラの別表記は何ですか` → `サンゴーカメラは何年に設立されましたか`
    - gold: `35（SUNGO）カメラ` → `1981年`
    - evidence: `サンゴーカメラ#2` → `サンゴーカメラ#1`
- **I2-035** (intra2) — fix — question contained the reason (黒い) making 黒パン guessable; neutral question, both aliases accepted
    - question: `通常の小麦パンより黒いことから、ライ麦パンは何とも呼ばれますか` → `ライ麦パンの別名は何ですか`
    - gold: `黒パン` → `黒パン|ライパン`
- **I2-036** (intra2) — valid — ok
- **I2-037** (intra2) — valid — ok
- **I2-038** (intra2) — valid — ok
- **I2-039** (intra2) — valid — ok
- **I2-040** (intra2) — valid — ok
- **I2-041** (intra2) — fix — question quoted the evidence sentence’s own key string (Sol Cubano) and never named the subject; rephrased via subject
    - question: `「Sol Cubano」はどのような意味ですか` → `ソル・クバーノというカクテル名はどういう意味ですか`
- **I2-042** (intra2) — valid — ok
- **I2-043** (intra2) — fix — question unnatural (「どの町などにあたりますか」)
    - question: `宮床村は現在のどの町などにあたりますか` → `宮床村は現在のどの町にあたりますか`
- **I2-044** (intra2) — fix — question did not name the subject and gold was a long clause; subject named, short golds
    - question: `近松門左衛門が活躍する以前の人形芝居には、どのような特徴がありますか` → `古浄瑠璃の人形芝居の特徴は何ですか`
    - gold: `素朴な力強さや宗教色が強い` → `素朴な力強さ|宗教色`
- **I2-045** (intra2) — fix — ambiguous: 「別の呼び方」 has two correct answers in different sentences (トランスジェンダー女性 #1, MtF #2) and トランスジェンダー女性 is near-guessable from the title; asked for the unique abbreviation instead
    - question: `トランス女性は別の呼び方で何と呼ばれますか` → `トランス女性は英語の略称で何と表現されますか`
    - gold: `トランスジェンダー女性` → `MtF`
    - evidence: `トランス女性#1` → `トランス女性#2`
- **I2-046** (intra2) — valid — ok
- **I2-047** (intra2) — fix — question omitted the subject entirely (ambiguous: which competition?)
    - question: `男子競技には何か国の選手が参加しましたか` → `2022年アジア競技大会のビーチバレーボール競技では、男子競技に何か国の選手が参加しましたか`
- **I2-048** (intra2) — valid — ok
- **I2-049** (intra2) — drop — gold アジア occurs in the question; the article has no other non-title fact to ask (sentence 1 is the only one), so not fixable
- **I2-050** (intra2) — fix — question convoluted; rephrased naturally
    - question: `LaMDAを巡る主張がきっかけで有効性の議論につながった試験は何ですか` → `LaMDAが意識を持ったという主張は、何の有効性についての議論につながりましたか`
- **C2-001** (cross2) — drop — definitional long gold; question names B (選挙区) so it is a one-hop lookup of B; unnatural
- **C2-002** (cross2) — drop — same B and gold as C2-001; definitional; names B
- **C2-003** (cross2) — drop — long definitional gold; question names B (丸木舟); unnatural
- **C2-004** (cross2) — drop — names B (センチメートル); asks a dictionary fact ("長さの単位") that is general knowledge
- **C2-005** (cross2) — drop — artificial ("説明に出てくる工学科"); names B; generic gold
- **C2-006** (cross2) — fix — question named B (杭州市) → one-hop; bridge restored by asking about "the city where the station is"
    - question: `城站駅が位置する杭州市は、浙江省でどのような都市ですか` → `城站駅がある市は、浙江省でどのような位置づけの都市ですか`
- **C2-007** (cross2) — drop — duplicate of C2-006 (same B 杭州市, same gold 省都)
- **C2-008** (cross2) — drop — A’s title contains B (レバノン), so the question necessarily names B → one-hop; long gold
- **C2-009** (cross2) — drop — long definitional gold; names B (ミドルウェア); artificial
- **C2-010** (cross2) — drop — artificial ("競技名に含まれるスキー"), long gold, names B
- **C2-011** (cross2) — drop — artificial (name-part etymology), long gold, names B; flagged by owner
- **C2-012** (cross2) — drop — definitional long gold; names B (核兵器)
- **C2-013** (cross2) — drop — definitional; names B (形態素)
- **C2-014** (cross2) — drop — A’s title contains B (ノーフォーク) → one-hop; artificial
- **C2-015** (cross2) — drop — artificial ("名称にある「アカデミー」"); names B
- **C2-016** (cross2) — drop — definitional long gold; names B (世界地図)
- **C2-017** (cross2) — drop — artificial, definitional gold 一定の文化様式; flagged by owner
- **C2-018** (cross2) — fix — question omitted the subject and named B (5月19日) → one-hop; bridge restored; gold shortened to the non-leap answer (2005 is not a leap year)
    - question: `大会初日の5月19日は、グレゴリオ暦で年始から何日目ですか` → `2005年アジア野球選手権大会の開幕日は、年始から何日目にあたりますか`
    - gold: `139日目（閏年では140日目）` → `139日目`
- **C2-019** (cross2) — drop — definitional; names B (図書館員); generic gold
- **C2-020** (cross2) — fix — question named B (碑林区) → one-hop; bridge restored
    - question: `臥竜寺がある碑林区は、中国の行政区分で何ですか` → `臥竜寺がある区は、行政区分上どのような区ですか`
- **C2-021** (cross2) — fix — gold contained タカラトミー which is in A’s sentence (and long); question named B; asked for the product type only
    - question: `オーガノイドシステムの設定に登場するゾイドシリーズは、何の会社が展開する何のシリーズですか` → `オーガノイドシステムが登場するシリーズは、どんな種類の商品ですか`
    - gold: `タカラトミー（旧・トミー）が展開する玩具シリーズ` → `玩具シリーズ|玩具`
- **C2-022** (cross2) — fix — long gold; asked naturally without naming テニス explicitly as B (still in subject string)
    - question: `タッチテニスの元になったテニスは、何人または何組のプレイヤーが行う球技ですか` → `タッチテニスの元になった競技は、何人で行う球技ですか`
    - gold: `二人または二組のプレイヤー` → `二人または二組|二人`
- **C2-023** (cross2) — drop — duplicate of C2-010 (same B スキー, same gold); flagged by owner
- **C2-024** (cross2) — fix — question named B (プティーウリ) and gold was a long address; asked for the country
    - question: `プチヴリ公国の首都として挙げられるプティーウリは、どの国・州・地区にある市ですか` → `プチヴリ公国の首都は、現在どの国にありますか`
    - gold: `ウクライナ・スームィ州プティーウリ地区` → `ウクライナ`
- **C2-025** (cross2) — drop — duplicate B テニス of C2-022; artificial; long gold
- **C2-026** (cross2) — fix — question named B (豊橋市) → one-hop; bridge restored
    - question: `石巻神社がある豊橋市は、愛知県のどの地域に位置しますか` → `石巻神社がある市は、愛知県のどの地域にありますか`
- **C2-027** (cross2) — drop — duplicate of C2-026 (same B 豊橋市, same gold 東三河)
- **C2-028** (cross2) — drop — duplicate of C2-026 (same B 豊橋市, same gold 東三河)
- **C2-029** (cross2) — fix — question named B (栃木県) → one-hop; bridge restored; alt gold 関東
    - question: `古賀志町がある栃木県は、日本の何地方に位置しますか` → `古賀志町がある県は、日本の何地方にありますか`
    - gold: `関東地方` → `関東地方|関東`
- **C2-030** (cross2) — drop — duplicate of C2-029 (same B 栃木県, same gold)
- **UF-001** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-002** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-003** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-004** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-005** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-006** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-007** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-008** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-009** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-010** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-011** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-012** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-013** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-014** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-015** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-016** (unans) — fix — question unnatural (etymology of a music unit’s name); same-form factual question, still unanswerable
    - question: `「イクシード」という語の語源となった言語は何ですか` → `イクシードは何年に結成されましたか`
- **UF-017** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-018** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-019** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **UF-020** (unans) — valid — ok; answer absent from the whole S300_fulllead file (subject not mentioned in any other article)
- **US-001** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-002** (unans) — fix — question omitted the subject
    - question: `有罪判決を受けた日本人観光客の氏名は何ですか` → `メルボルン事件で有罪判決を受けた日本人の氏名は何ですか`
- **US-003** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-004** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-005** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-006** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-007** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-008** (unans) — fix — question omitted the subject (2005年大会 of what?)
    - question: `2005年大会で優勝した国はどこですか` → `2005年アジア野球選手権大会で優勝した国はどこですか`
- **US-009** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-010** (unans) — fix — question used 「この製品群」 with no subject
    - question: `この製品群が最初に発売された年はいつですか` → `Visual Studio Application Lifecycle Managementが最初に発売されたのはいつですか`
- **US-011** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-012** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-013** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-014** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-015** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-016** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-017** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-018** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
- **US-019** (unans) — fix — question omitted the subject
    - question: `事故の発生地点の標高は何メートルですか` → `富士山ライブ配信滑落死事故が起きた地点の標高は何メートルですか`
- **US-020** (unans) — valid — ok; answer absent from the whole S3000 file (subject not mentioned elsewhere; also absent from its full lead)
