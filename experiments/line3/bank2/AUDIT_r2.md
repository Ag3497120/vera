# Audit of round 2 (bank2_r2.tsv)

Auditor: Claude (Opus 5.5), 2026-10-08. Inputs: `bank2-author/out/bank2_r2.tsv` (44 new items R2-*, authored by codex gpt-6-luna
from `PROMPT2.md`), the two corpora, the author's `check_r2.py` / `README_r2.md`. Standards: exactly those of round 1
(`AUDIT_r1.md`): gold verbatim in evidence; gold not in the question and not guessable from question/title; intra2 gold in no
sentence containing the title; cross2 needs two articles, B's title absent from the question, A's title does not contain B's,
short natural gold, no dictionary-definition golds, no B reuse; unans answer absent from the whole corpus file, same question forms
as answerable items. Output: `bank2_r2_audited.tsv` (in `bank2-author/out/`), merged into `bank2.tsv`.

## Counts

| kind | authored | valid | fixed | dropped | kept |
|---|---|---|---|---|---|
| intra2 (fulllead) | 20 | 12 | 8 | 0 | 20 |
| cross2 (s3000) | 14 (target was 25) | 1 | 0 | 13 | 1 |
| unans | 10 (5 fulllead + 5 s3000) | 10 | 0 | 0 | 10 |
| total | 44 | 23 | 8 | 13 | 31 |

## Main findings

1. **cross2 failed again (1/14 kept).** The author obeyed the mechanical rules (B's title is not in the question, A's title does
   not contain B), but satisfied them by choosing B articles that are *generic concepts* (王国, 製作, 蔵米, スキー, 規則, 選挙区, 核兵器,
   アカデミー, センチメートル, ミドルウェア, 図書館員, 丸木舟) and asking for their dictionary definition. Eight of the 14 reuse exactly the
   B articles dropped in round 1 as definitional (選挙区, 丸木舟, センチメートル, ミドルウェア, 核兵器, アカデミー, 図書館員, スキー).
   Several golds are guessable without B (国王 for Thailand, 藩 next to 幕府, テレビ番組 next to ドラマ, 図書館 already in A,
   一本の木 from 丸木). R2-C014 is a homonym link (ふじさん matches only A's reading gloss). Only R2-C006 (共在説 → 聖餐 → 最後の晩餐)
   is kept, and it is borderline-definitional. The "A sentence with several titled entities" goal was met by 1/14 (C014, dropped).
   The author itself reported that the S3000 title scan yields mostly homonyms/generic words: **with first sentences only, S3000
   has few natural entity-to-entity bridges; cross2 cannot be grown by more authoring rounds on this corpus.**
2. **intra2 is sound** (20/20 kept). Every evidence index is >= 2 and no gold is in a title sentence. Fixes: subject missing from
   the question (I001), questions copying the evidence key words (I007 気象条件, I017 ヴェイユ予想/定義/導入), a factually off
   question (I011: the 1901 book describes a different motion, it does not record the ちょん掛け motion under another name), a
   question contrived to point at sentence 3 when sentence 2 already answers it (I015), and gold formatting (I006 "120 m" with a
   space, I019 "15台程度", I020 phrase gold). Remaining weakness: in most items the question still shares a non-title keyword with
   the evidence sentence (年号 2004年/2007年/2014年, ベリー, マウンテンバイク, 京成バス千葉イースト), so B1 finds the gold in 60-75% —
   "not adjacent to the title" did not make these items harder for keyword lookup, only for "title sentence + next sentence".
3. **unans are sound** (10/10). Each subject is mentioned in no other article of its corpus file (レバノン occurs inside the title
   of 「2020年東京オリンピックのレバノン選手団」, whose sentence says nothing about currency); the asked attributes (人口, 廃止年,
   貯水容量, 例祭, 創業, レーベル, 運行本数, 身長, ネットの高さ, 通貨) are absent; s3000 subjects' full leads (HONEY BADGER,
   プラガティ急行) do not contain them either. Forms match answerable items (何人, 何年, 何メートル, どこ, 何) and none uses 最初/初めて
   (bank-wide 10/50 unans still do). Tell: **all 10 reuse subjects already in the bank** — the 5 fulllead ones are the subjects of
   R2 intra2 items (市川町, 内浦町, 赤尾ダム, 中之嶽神社, 岡崎建設) and the 5 s3000 ones are subjects of round-1 unans
   (US-011, 013, 014, 015, 020). Same-subject answerable/unanswerable pairs are a useful contrast, but a subject that is
   "known unanswerable" in round 1 now carries two unans questions.

## Baselines on the kept round-2 items (`baselines.txt`, gold-in-candidate, ties kept)

| kind | n | B1 MeCab | B2 MeCab | B1 bigram | B2 bigram |
|---|---|---|---|---|---|
| intra2 | 20 | 15 (75%) | 15 (75%) | 12 (60%) | 13 (65%) |
| cross2 | 1 | 1 | 1 | 0 | 1 |

B2 adds almost nothing over B1 for R2 intra2 (non-adjacency worked), but B1 alone is already high. Missed by B2 with both
tokenizers: R2-I003, R2-I006, R2-I013.

## Per-item decisions

Format: id — decision — reason; for fixes the changed fields are shown (old → new).

- **R2-I001** (intra2) — fix — question did not name the subject (pure lookup of the evidence wording ベリー/脱退); subject added
    - question: `ベリーの脱退後、誰が新たにメンバーとなりましたか` → `ビースティ・ボーイズでベリーが抜けた後、新たにメンバーとなったのは誰ですか`
- **R2-I002** (intra2) — valid — ok
- **R2-I003** (intra2) — valid — ok
- **R2-I004** (intra2) — valid — ok
- **R2-I005** (intra2) — valid — ok (和歌山線 is mildly predictable from the route in sentence 0, but not from question/title)
- **R2-I006** (intra2) — fix — gold 「120 m」 contains a half-width space; a reader answering 120m / 120メートル would be marked wrong; bare number added
    - gold: `120 m` → `120 m|120`
- **R2-I007** (intra2) — fix — question repeated the evidence key noun 気象条件 verbatim; paraphrased; short alternative added
    - question: `数河高原の気象条件は、どの地域型に分類されますか` → `数河高原はどの気候区分に属しますか`
    - gold: `日本海側気候` → `日本海側気候|日本海側`
- **R2-I008** (intra2) — valid — ok (question repeats 正式な学術用語; kept because it disambiguates from the alternative name カルデラ噴火 in the same sentence)
- **R2-I009** (intra2) — valid — ok (numeric gold verbatim; scorer must normalise 3万2,500 / 32,500)
- **R2-I010** (intra2) — valid — ok
- **R2-I011** (intra2) — fix — question was factually off: the 1901 book describes a different motion (片手でまわし・胸を突く), it does not record the ちょん掛け motion under another name; asked for the spelling under which the technique appears
    - question: `1901年の相撲書では、ちょん掛けの動作をどの技名で記していますか` → `ちょん掛けは、1901年の相撲書ではどのような表記の技名で載っていますか`
- **R2-I012** (intra2) — valid — ok
- **R2-I013** (intra2) — valid — ok
- **R2-I014** (intra2) — valid — ok
- **R2-I015** (intra2) — fix — question was contrived to point at sentence 3 (U-20大会も制した); the winner is already stated in sentence 2 (no title, not adjacent to a title sentence); simplified
    - question: `2017 FIFA U-17ワールドカップで優勝し、同年のU-20大会も制した国はどこですか` → `2017 FIFA U-17ワールドカップで優勝した国はどこですか`
    - evidence: `2017 FIFA U-17ワールドカップ#3` → `2017 FIFA U-17ワールドカップ#2`
- **R2-I016** (intra2) — valid — ok
- **R2-I017** (intra2) — fix — question copied three evidence words (ヴェイユ予想/定義/導入); paraphrased to keep only the subject
    - question: `グロタンディーク位相は、ヴェイユ予想の解決に向け何を定義する際に導入されましたか` → `グロタンディーク位相は、もともと何を定義するために導入されましたか`
- **R2-I018** (intra2) — valid — ok
- **R2-I019** (intra2) — fix — gold contained the hedge 程度 (cf. round-1 I2-023); short alternative added
    - gold: `15台程度` → `15台程度|15台`
- **R2-I020** (intra2) — fix — question unnatural (「どのような情報の流れ」) and gold a phrase; rephrased, short alternative added (still partly guessable from the Web 2.0 vs 1.0 contrast)
    - question: `Porn 2.0で対比される旧来型サイトは、利用者にどのような情報の流れを提供していましたか` → `Porn 2.0と対照的とされる従来のポルノサイトは、どのようなコンテンツを提供していましたか`
    - gold: `一方向のコンテンツ` → `一方向のコンテンツ|一方向`
- **R2-C001** (cross2) — drop — dictionary-definition gold (王国 = state whose head is a 国王); 国王 is guessable from general knowledge of Thailand without reading B
- **R2-C002** (cross2) — drop — definitional/artificial (製作 dictionary sense); テレビ番組 is guessable from ドラマ; unnatural question
- **R2-C003** (cross2) — drop — definitional (蔵米 dictionary sense); one-character gold 藩 is the obvious pair of 幕府 (guessable); contrived question
- **R2-C004** (cross2) — drop — dictionary gold (スキー definition, 2枚もしくは1枚); same B and gold as round-1 dropped C2-010/C2-023
- **R2-C005** (cross2) — drop — definitional (規則 dictionary sense), generic gold 文章, artificial question
- **R2-C006** (cross2) — valid — ok; borderline: 聖餐 is a concept and 最後の晩餐 comes from its definition, but the gold is a short named event, B is not in the question, A’s title does not contain B
- **R2-C007** (cross2) — drop — definitional clause gold (選挙区 definition); same B as round-1 dropped C2-001/C2-002
- **R2-C008** (cross2) — drop — definitional gold (核兵器 definition); same B as round-1 dropped C2-012; unnatural question
- **R2-C009** (cross2) — drop — artificial name-etymology question (as round-1 C2-015, same B アカデミー); the link is the word アカデミー inside アカデミー賞, not the award
- **R2-C010** (cross2) — drop — dictionary unit conversion (センチメートル = 1/100メートル); same B as round-1 dropped C2-004
- **R2-C011** (cross2) — drop — definitional gold (ミドルウェア definition); same B as round-1 dropped C2-009
- **R2-C012** (cross2) — drop — definitional gold (図書館員 = 図書館において業務に従事する者); 図書館 occurs in A’s sentence several times, so gold is guessable from A alone
- **R2-C013** (cross2) — drop — definitional gold (丸木舟 definition), guessable from 丸木; same B as round-1 dropped C2-003
- **R2-C014** (cross2) — drop — artificial homonym link (B ふじさん matches only the reading gloss of 富士山 in A); no user would ask for a train named like the mountain
- **R2-U001** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent
- **R2-U002** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent
- **R2-U003** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent
- **R2-U004** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent
- **R2-U005** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent
- **R2-U006** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent (also absent from the subject’s full lead where present)
- **R2-U007** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent (also absent from the subject’s full lead where present)
- **R2-U008** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent (also absent from the subject’s full lead where present)
- **R2-U009** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent (also absent from the subject’s full lead where present)
- **R2-U010** (unans) — valid — ok; subject not mentioned in any other article of its corpus file and the asked attribute is absent (also absent from the subject’s full lead where present)
