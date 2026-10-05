# Coarse placement: a rough type for (almost) every content word, and "the nearest thing" for an unplaced one (W3-a)

Status: implemented and measured; the criteria that are not met are marked FAIL in the results table (section 7), not hidden.  **Every number in this file sits in a table that is
rendered from `artifacts/w3-a/` by `artifacts/w3-a/render_docs_numbers.py`** (`--check`
re-renders and compares).  Prose below states how the system works, never a measured
value; whether a criterion is met is the PASS/FAIL column of the results table.

**W3-a2（第 11 節、日本語）**: 上位語の連鎖の誤り（F1）・数量の単位（F2）・画像説明の残り（F3）を直し、証拠の足りない語に対して codex（gpt-6-luna、effort low）で定義文を
並列に生成して「推定（生成）」として配置に入れた。問い合わせの契約（読解器のため）は第 11.7 節。

This module does **not** change the reader.  It supplies the rough types the next ticket
will connect to the reader (a role is assigned when the predicate's wanted type fits the
word's type; that needs a rough type for nearly every content word).  At run time it
uses no weight, no trained model, no external dictionary and no LLM: counted evidence
and structure only.

**日本語の要約**（数値は書かない。結果は第 7 節の表）: 内容語（名詞・動詞・形容詞・固有名）に粗い型（名詞 17・述語 13）を、数えた証拠だけで広く付け、配置に無い語には
「語の形」と「その場の役割の位置」の近さから型の候補を **推定（構成）** として返す。重み・学習済みモデル・辞書データ・LLM は使わない。証拠は種類（定義の上位語・別名・括弧別表記・
役割の分布・サ変・述語の枠組み・語の形）ごとの別の腕で、出所（Wikipedia と codex 生成コーパスの 8 系列）ごとに別に数え、足し合わせない。腕どうしは重ねるだけで、
一致すれば `DECIDED`、割れれば `MULTIPLE`、同点は並べて棄権し、証拠が弱ければ `UNPLACED`／`UNKNOWN` のままにする。判定規則は 1 か所（`coarse_types.decide_word`）にあり、
答えの `axes.<腕>.met` は「その腕が決定に加わったか」を表す。配置が無い状態は `NO_PLACEMENT`（0 件と区別）。入口は
`python -m verantyx.coarse_place --term <語> [--context-role <助詞>] [--context-predicate <述語>] [--placement <dir>]`。この配置を読解器につなぐのは次のチケット。

## 1. The type system (`verantyx/coarse_types.py`)

Seventeen noun types and thirteen predicate types.  The ids are ASCII and fixed; the
inventory only grows (the test `test_inventory_only_grows` fails on a removal or rename).

| id | meaning | | id | meaning |
|---|---|---|---|---|
| `PERSON` | person | | `P_GIVE` | giving / receiving |
| `GROUP_ORG` | group, organisation | | `P_MOVE` | movement |
| `ANIMAL` | animal | | `P_CHANGE` | change |
| `PLANT` | plant, fungus | | `P_CREATE` | creation |
| `ARTIFACT` | artefact, tool, vehicle | | `P_COMMUNICATE` | communication |
| `SUBSTANCE_FOOD` | substance, food, drink | | `P_PERCEIVE` | perception |
| `PLACE` | place, facility, landform, building | | `P_EXIST` | existence |
| `TIME` | time, point, period | | `P_POSSESS` | possession |
| `QUANTITY` | quantity, unit | | `P_STATE` | state (adjectives included) |
| `EVENT_ACT` | event, act | | `P_COGNITION` | thought, recognition |
| `STATE_PROPERTY` | state, property (illness, symptom) | | `P_EMOTION` | emotion |
| `ABSTRACT` | abstract concept (field, system, method) | | `P_CONSUME` | eating, drinking, consuming |
| `INFO_LANGUAGE` | information, document, word, language, sign | | `P_ACT` | other act |
| `BODY_PART` | body part, organ | | | |
| `NATURAL_PHENOMENON` | natural phenomenon | | | |
| `WORK` | work (title of a book, film, song, programme, game) | | | |
| `IDENTIFIER` | identifier (URL, model number, alphanumeric code) | | | |

### Boundary rules (written before the answer keys)

- Building, station, landform, park, shrine, castle: `PLACE`.  Vehicle, tool, machine, garment, instrument: `ARTIFACT`.
- Company, school, party, team, army (as an organisation): `GROUP_ORG`; as a building the word is polysemous and also gets `PLACE`.
- Country, city, region: `PLACE`; only a clearly organisational use adds `GROUP_ORG`.
- Dish, drink, ingredient, medicine, metal, compound: `SUBSTANCE_FOOD`.
- Illness, symptom, property, a feeling noun, colour: `STATE_PROPERTY`.
- Academic field, system, doctrine, method, theory, religion, law: `ABSTRACT`.
- Language name, script, sign, document, word, standard: `INFO_LANGUAGE`.
- Title of a book / film / song / programme / game / painting: `WORK`.
- "N years", "N o'clock", a date: `TIME`.  "N pieces", "N kilograms", a number: `QUANTITY`.
- URL, e-mail address, model number, alphanumeric code: `IDENTIFIER`.
- Celestial body, weather, earthquake, tsunami, wave, light: `NATURAL_PHENOMENON`.
- Hand, eye, organ, bone, muscle: `BODY_PART`.
- War, accident, meeting, tournament, festival, a verbal noun for an action: `EVENT_ACT`.
- An occupation or role name: `PERSON`; the group of people itself: `GROUP_ORG`.
- Verbs, adjectives and adjectival nouns get a predicate type (`P_` prefix); adjectives and adjectival nouns are `P_STATE`.

### Seeds

The only hand-written knowledge is a short list of GENERAL anchors a definition's hypernym
chain can end in (person, tool, building, time, unit, event, property, concept, document,
language, phenomenon, work, organisation ...), at most 30 per noun type and 25 per predicate
type, and a list of hypernyms that talk about the word instead of the thing ("term",
"name", ...) which are skipped when typing a hypernym.  The predicate seeds are
verbs from the head of the material's own frequency list (`artifacts/w3-a/pred_verb_freq.tsv`,
made by `pred_seed_freq.py` from the extraction counts; the range and the check that every
seed lies inside it are in `pred_seed_freq_summary.json` and a test), typed by hand; none of them
is a word of the frozen predicate check beyond the ten the frozen file marked as overlapping
before it was frozen (in fact none).  A type with few frequent members (emotion, eating)
therefore has few seeds.  The words the ticket names as end-of-word traps are not seeds
(a test checks it).  The lists are in `coarse_types.py` and counted in the build manifest.

## 2. Correspondence to the three-dimensional cross

```
                evidence arm: definition (hypernym of the title's first sentence)
                evidence arm: alias (redirect -> target's type)
                evidence arm: paren_alias ("X (Y, ...)": Y is another spelling of X; counted apart from alias)
                         |
 role@jawiki  ---  [ core: a headword ]  ---  role@codex:<family> (eight families, one arm each)
                         |
                evidence arm: notation (spelling), sahen (verbal-noun use), hearst (A, B などの Y),
                              pos_class / frame (predicates), morphology (shared units, query time)
                face of each arm: types with COUNTS
```

The core is the headword.  Each arm is one kind of evidence; the face of an arm is the
counts per type.  Sources (the encyclopedia and each of the eight generated-corpus
families) are separate arms and are never pooled; counts of different arms are never
added.  Codex-derived evidence is marked `generated`.

## 3. How a word is placed

1. **Spelling (`notation`)**: digits + a time unit, date, clock time -> `TIME`; digits + a
   counter learned from the material (a unit that follows numbers often enough), digits
   alone -> `QUANTITY`; URL, e-mail, letter+digit code, version string -> `IDENTIFIER`.
2. **Seed**: a hand anchor decides.
3. **Definition**: the hypernym phrase of a title's first sentence ("X is a Y", "X is a
   kind of Y", copula omitted, "X, also called Y", coordinated hypernyms); the type of Y
   is X's.  Y's own type is found by chain (seeds first, then the plain-title headwords
   the previous round decided), falling back to the longest right-hand unit of at least
   two characters that is a donor.  Articles titled "X (qualifier)" describe another sense
   of X: they never feed the chain (their qualifier is a separate, weaker arm).
4. **Alias**: a redirect title takes the type of its target (when the target is decided).
   **Paren alias** (an arm of its own, never added to alias): in a lead "X (Y, ...)" the first
   bracket element Y, when it is a plain Japanese-character string (no space, colon, digit,
   Latin letter), takes the type of X.
   A lead whose first sentence was cut by an image caption has `]]` in it: of the `]]`-separated
   parts, the first that starts with the topic marker or with the title is read (otherwise the
   last part, as before); how many leads are read differently is counted in the manifest.
   A hypernym phrase made of a taxonomic rank ("... the genus-level taxon X ...") takes the
   type of the last taxon before the rank word.
5. **Hypernym pairs from running text** (`hearst`): "A and B and other Y".
6. **Role**: where the word stands (particle + the first verb after it).  A context counts
   for a type only if the type leads the context's typed words, with a clear majority and
   clearly more than its base rate (the lift test), leaving the word's own uses out.  Each
   source is its own arm.  `sahen`: how often the word is directly followed by "do".
7. **Predicates**: seeds; adjectives and adjectival nouns are `P_STATE` by word class
   (`pos_class`); verbs by a small structure table over which noun types stand in which
   particle slot before the verb (`frame`).
8. **Overlay** (never a sum): the arms that met their thresholds are laid over each
   other.  The rule lives in ONE function, `coarse_types.decide_word`, used by the builder and by
   the query, so the `met` of an arm in the answer is what really decided.  All arms agree on one type: `DECIDED`.  They split, or a tie occurs inside one
   arm: `MULTIPLE` with all the tied types side by side.  The display order of a list of
   types is alphabetical and is **not** a ranking; no winner is ever chosen by order.
   Whether definition-like arms outrank role arms is a registered setting, and the weakest
   arm (role) never decides alone: a configured number of role sources must each MEET their
   own threshold (a source that merely has a vote does not count) and agree (see the
   configuration table).  An arm that reached its own threshold but was set aside says why
   (`ROLE_SINGLE_SOURCE`, `SEEDED`, `OUTRANKED`).
   **Namespace** (noun or predicate): every source votes on its own counts of noun uses and
   verb / adjective uses (a tie abstains); the sources are not pooled.  When they disagree (or all
   tie) both sets of arms are evaluated and overlaid, so a split shows up as `MULTIPLE` or the
   word stays unplaced (`namespace` `NP` until the decision names one).
   **Counters** (the unit after Arabic numerals that makes "number + unit" a quantity): a unit
   qualifies only when it clears the threshold in a configured number of sources, each
   counted alone.
9. **Not enough evidence**: the word stays `UNPLACED` (it occurs in the material) or is
   `UNKNOWN` (it does not).  Nothing is forced.

A word's shape (units shared with placed words) is **never** a direct placement; it is
used only at query time as an estimate (next section).

## 4. Asking (`python -m verantyx.coarse_place`, `verantyx.coarse_place.query`)

```
python -m verantyx.coarse_place --term <word> [--context-role <particle>]
        [--context-predicate <verb>] [--placement <dir>]
```

`--context-role` is one of the twelve particles `が を に で へ と から まで より の は も`
(anything else: exit 64 with a JSON reason).  The placement directory comes from
`--placement` or the environment variable `VERA_COARSE_PLACEMENT`; nothing else is searched.
Exit code: 0 a typed answer, 2 `NO_PLACEMENT`, 64 bad arguments.

The answer is one JSON object: `term`, `namespace` (`N`/`P`, null when nothing is known),
`state` (`DECIDED` / `MULTIPLE` / `UNPLACED` / `UNKNOWN` / `NO_PLACEMENT`),
`origin` (`direct` / `estimated` / null), `estimate_basis` (null for a direct answer; `proximity` or `generated` for an estimate, W3-a2), `constructed` (true only for an estimate),
`top` (an unordered set of type ids), `candidates` (each type with its per-arm counts),
`axes` (per arm: counts, the arm's top types, `met` = the arm reached its threshold AND took
part in the decision, `threshold_met` = its own threshold only, `why` = the reason an arm that
reached its threshold was set aside, whether the source is generated), `neighbors` (what an estimate was built on: the placed word,
the units' family words, or the context slot, each with a `via`), `seen_in_material`,
`context`, `placement` (path, content sha256, and for `NO_PLACEMENT` the reason: `UNSET`,
`MISSING`, `UNREADABLE`, `MANIFEST_MISMATCH`).  `decided_by` and `generated` are added for
direct answers.

Invariants (tested): `DECIDED` iff one type; `MULTIPLE` iff two or more; `UNPLACED`,
`UNKNOWN`, `NO_PLACEMENT` iff none; `origin == estimated` iff `constructed` iff `estimate_basis` is `proximity` or `generated`;
an estimate always lists its neighbours; a direct answer has `estimate_basis` null.  A placement that exists but holds no words answers `UNKNOWN`, never
`NO_PLACEMENT` (zero hits and "no placement" are different).

### Estimating an unplaced word (a construction, always marked)

- **head**: the longest right-hand part (at least two characters) that is itself decided,
  when the left part is an attested word or a single known character (the lattice rule:
  both sides of a split are nodes).  A single-character suffix never decides.
  The left part may itself be made of words: it is split again (cuts as in the lattice, both
  parts at least two characters) until every piece is a real word or an atom.
- **kin**: the longest right-hand unit whose family of placed words leans one way.
- **kin_left** (a last tier, only when nothing above fired; **off by default**, see the configuration
  table): the term as the LEFT unit of a large, almost uniform family of placed words (a fragment the
  tokeniser cut off a longer word).  It is kept as an option because it raises the coverage a little,
  but on the dev data it also added an estimated error, and a coverage rule must not add errors.
- **context**: the role slot the caller passes; sources are consulted separately and
  must agree (the answer shows each source's own counts, never their sum).
- The stages are overlaid, not summed.  When they disagree the configured conflict
  policy applies (see configuration).  If nothing gathers: `UNPLACED` / `UNKNOWN`.

## 5. Building (`tools/build_coarse_placement.py`)

```
holdout   draw the held-out sentences (a fixed seed)
build     build a placement directory (placement.sqlite + manifest.json)
verify    recompute table counts and content_sha256 and compare with the manifest
```

The placement is built outside the tree, in
`/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/{sample,full,dev}/...`
(a path is always an argument).  A build is deterministic: `content_sha256` is a hash of
every table in a fixed order (the sqlite file bytes are not compared).  It stops with
exit 2 when no output directory is given (`UNKNOWN_OUT_UNSET`) and with exit 3 when the
frozen test data do not match `FROZEN.json` (`FROZEN_MISMATCH`).  The material actually
used, per-input counts, hashes and the number of rows skipped per reason are in the
manifest; the held-out sentences and the excluded unknown words are removed from the
material and counted.

<!-- BEGIN table:build_summary -->
| item | value |
|---|---|
| build started / finished (UTC) | 2026-10-03T03:35:43Z / 2026-10-03T03:45:41Z |
| duration (s) | 598.1 |
| stage seconds | aliases_sec=22.0, codex_sec=245.1, ctx_sec=24.6, decide_sec=84.5, definitions_sec=18.2, extraction_sec=378.1, hearst_sec=32.6, jawiki_sec=133.0, resolve_sec=200.9, stage_a_sec=100.1, stage_b_sec=99.7, units_sec=97.7, votes_sec=32.6, write_sec=15.5 |
| placement bytes | 273,076,224 |
| content_sha256 | ecd3f8e38e186a902398ee41b3cc8d06c9faaedd6bd2d3f4b86fb80166e8e995 |
| config sha256 | a1c0c2047533dddb20deaae1f8df799e98a80a38a0cfe98df8fa51216bbc761c |
| coarse_types.py sha256 | a715129f8a96f47afd39f5007316ce3266ac008e5386e6dcfbc56582ae0f79d4 |
| tables (rows) | atoms=7,403, counters=140, ctx=166,701, evidence=1,522,401, generated=52,270, headwords=1,758,846, meta=4, unit_kin=618,996, unit_sample=295,893 |
| rows by state / namespace | DECIDED/N=999998, DECIDED/P=2934, MULTIPLE/N=5713, MULTIPLE/NP=8, MULTIPLE/P=71, UNPLACED/N=741994, UNPLACED/NP=162, UNPLACED/P=7966 |
| evidence rows by arm | alias=303605, definition=568905, definition_recovered=8273, frame=1090, gen_definition=19526, hearst=16818, ns_vote=1136, paren_alias=98078, pos_class=8125, role=401243, sahen=56890, seed=656, title_qualifier=38056 |
| hypernym chain rounds | round 0: donors 375, decided 418429; round 1: donors 418804, decided 544051; round 2: donors 544426, decided 556599; round 3: donors 556974, decided 559734; round 4: donors 560109, decided 560044 |
| alias rows | paren_resolved=100142, paren_unresolved_target=158410, resolved=303609, unresolved_target=646942 |
| seed counts | noun=375, pred=281 |
<!-- END table:build_summary -->

<!-- BEGIN table:build_inputs -->
| input | bytes | lines / rows | sha256 (prefix) |
|---|---|---|---|
| jawiki_leads | 720,529,154 | 2455473 | 7585034b6149 |
| codex:code | 1,443,852,288 | 1405189 | 60d896ef7e63 |
| codex:code_qa | 861,270,016 | 324639 | 4cf816fd16c8 |
| codex:conversation | 1,606,750,208 | 2242864 | ab3736b20f10 |
| codex:figurative_commonsense | 231,194,624 | 238905 | ac36ce8e8a8d |
| codex:general_qa | 507,125,760 | 317423 | 80234f7534a5 |
| codex:narrative | 181,018,624 | 146598 | 81d29e62ed3c |
| codex:paraphrase_entail | 340,123,648 | 379574 | 60c942cd7c37 |
| codex:pro | 812,023,808 | 1366290 | 910f1e77afb8 |
<!-- END table:build_inputs -->

<!-- BEGIN table:build_skips -->
| source | rows skipped, by reason |
|---|---|
| codex:code | excluded_term=224, holdout=274 |
| codex:code_qa | excluded_term=58, holdout=81 |
| codex:conversation | excluded_term=338, holdout=613, no_japanese=27 |
| codex:figurative_commonsense | excluded_term=134, holdout=59 |
| codex:general_qa | excluded_term=422, holdout=77 |
| codex:narrative | excluded_term=44, holdout=28 |
| codex:paraphrase_entail | excluded_term=212, holdout=104 |
| codex:pro | excluded_term=49, holdout=330 |
| jawiki | bracket_rule_changed=1611, bracket_text_last=15425, bracket_text_part=22162, bracket_text_part_first=1501, bracket_text_part_middle=110, caption_fragment=87, caption_only=11418, def_empty=3319, def_ends_代名詞=77, def_ends_代名詞_recovered=2, def_ends_副詞=228, def_ends_副詞_recovered=10, def_ends_助動詞=8420, def_ends_助動詞_recovered=4767, def_ends_助詞=3517, def_ends_助詞_recovered=245, def_ends_動詞=40190, def_ends_動詞_recovered=20610, def_ends_形容詞=587, def_ends_形容詞_recovered=338, def_ends_形状詞=458, def_ends_形状詞_recovered=149, def_ends_感動詞=91, def_ends_感動詞_recovered=5, def_ends_接尾辞=72, def_ends_接尾辞_recovered=26, def_ends_接続詞=18, def_ends_接続詞_recovered=3, def_ends_接頭辞=27, def_ends_接頭辞_recovered=1, def_ends_空白=4, def_ends_空白_recovered=1, def_ends_記号=1569, def_ends_記号_recovered=109, def_ends_連体詞=22, def_ends_連体詞_recovered=1, def_no_noun_phrase=9590, def_no_noun_phrase_recovered=3345, disambiguation=11851, excluded_term=9248, holdout=1500, list_article=10589, meta_title=3327, notation_title=13674, title_too_long=199463 |
<!-- END table:build_skips -->

<!-- BEGIN table:build_excluded -->
| item | value |
|---|---|
| unknown words excluded (terms) | 299 |
| rows/titles dropped for containing one | 10736 |
| held-out rows removed | [{"codex_rows": 1000, "jawiki_lines": 1000, "path": "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S/artifacts/w3-a/holdout_2000.jsonl", "sha256": "c9772c535ee284b2cf10adcea45be63704b7f8494fe00778655c4f4ff1c30323"}, {"codex_rows": 500, "jawiki_lines": 500, "path": "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S/artifacts/w3-a/dev_l1_1000.jsonl", "sha256": "bf33fe42792a129e5e7e62b8d0b06108f835b6d55851056514c5d05cea20f86f"}] |
<!-- END table:build_excluded -->

<!-- BEGIN table:build_materials -->
| material | use |
|---|---|
| jawiki lead sentences | definition / alias / role / pos material |
| codex generated corpus index (train) | role / pos material per family (origin: generated) |
| hand-written seeds | verantyx/coarse_types.py (SEEDS_NOUN, SEEDS_PRED) |
| notation rules | verantyx/coarse_types.py (notation_type) |
| predicate frame rule table | verantyx/coarse_types.py (PRED_FRAME_RULES) |
| stop-word lists (they give no type) | verantyx/coarse_types.py (GENERIC_HEADS, META_HEADS, RANK_WORDS) |
| paren alias (the first bracket element after a title) | derived from the jawiki leads above (an arm of its own) |
| generated definition sentences (a model wrote them; not a testimony) | arm gen_definition: places only a word nothing else decided, as an estimate (generated); never settles a tie; never a donor |
| unidic-lite via fugashi | word segmentation, the coarse word class (pos1, pos2) and orthBase ONLY; no finer dictionary sense labels |
<!-- END table:build_materials -->

## 6. Pre-registered definitions and the configuration

`artifacts/w3-a/PREREG.md` (frozen) fixes the scoring: **correct** = the top set is
non-empty, meets the gold, and is no larger than max(1, |gold|); **wrong decision** = a
single type outside the gold; everything else is "other".  Thresholds and rules were
chosen on the dev vocabulary and dev unknown words only (`dev_runs`); the frozen test
data were measured only after the configuration was fixed (`config_final.json`), and
every measurement is kept (`eval_runs`).

<!-- BEGIN table:config -->
| setting | value |
|---|---|
| alias_min | 1 |
| conflict_policy | unknown |
| counter_latin_numerals_min | 6 |
| counter_latin_share_pct | 10 |
| counter_max_chars | 3 |
| counter_max_chars_single | 6 |
| counter_min | 80 |
| counter_min_sources | 2 |
| ctx_min_lift_pct | 300 |
| ctx_min_share_pct | 70 |
| ctx_min_total | 20 |
| ctx_store_min | 20 |
| def_min | 1 |
| definition_outranks_role | False |
| donor_contra_min | 5 |
| donor_stage_b | True |
| est_ctx_min_lift_pct | 300 |
| est_ctx_min_share_pct | 70 |
| est_ctx_min_sources | 2 |
| est_ctx_min_total | 20 |
| frame_min_total | 30 |
| gen_upgrade_on_agreement | True |
| head_min_chars | 2 |
| hearst_min | 2 |
| hearst_min_share_pct | 70 |
| kin_left | False |
| kin_left_min_count | 10 |
| kin_left_min_share_pct | 90 |
| kin_min_count | 3 |
| kin_min_share_pct | 70 |
| kin_min_unit_chars | 2 |
| kin_store_min | 3 |
| left_attested | True |
| left_recursive | True |
| max_chain_depth | 4 |
| max_word_chars | 12 |
| min_seen | 3 |
| min_suffix_chars | 2 |
| paren_alias_min | 1 |
| pos_min | 3 |
| qual_min | 999 |
| recovered_decides | True |
| role_min | 5 |
| role_min_share_pct | 70 |
| role_min_sources | 2 |
| sahen_min | 3 |
| sahen_min_share_pct | 30 |
<!-- END table:config -->

## 7. Results (frozen test data)

<!-- BEGIN table:results -->
| Criterion | Measure | Target | Measured | Result |
|---|---|---|---|---|
| L1 | placed content words (direct, top non-empty) | >= 100,000 | 993,027 | PASS |
| L1 | token cover on the 2,000 held-out sentences (direct + estimated) | >= 90% | 79.1% (17217 of 21774 tokens) | FAIL |
| L1 | distinct-word cover (reference) | - | 64.1% (5383 of 8391) | - |
| L2 | direct and correct / all (n=1072) | >= 85% | 52.9% | FAIL |
| L2 | direct and wrongly decided as ONE type / all | <= 8% | 4.4% | PASS |
| L2 | suffix-trap words (n=154): wrongly decided / all | <= 5% | 4.5% | PASS |
| L3 | typed unknown words (n=174): correct | >= 65% | 49.4% | FAIL |
| L3 | typed unknown words: wrong | <= 15% | 5.2% | PASS |
| L3 | gold-unknown words (n=60): a type was returned | <= 20% | 15.0% | PASS |
| L3 | unknown words returned DIRECT other than by spelling rule | 0 | 0 | PASS |
| L4 | estimates without the construction mark | 0 | 0 | PASS |
| L5 | query time, mean / p95 / max (ms), 23083 queries | mean, p95 <= 50 | 0.093 / 0.202 / 2.903 | PASS |
| L5 | one command-line call incl. load (ms) / import only (ms) | - | 199.3 / 108.0 | - |
| L5 | placement size (bytes) | - | 273,076,224 | - |
| L5 | build duration (s), full material | - | 598.1 | - |
| L5 | content_sha256 of this placement | - | ecd3f8e38e18... | - |
<!-- END table:results -->

### L1: breadth

<!-- BEGIN table:funnel -->
| step (distinct words) | count |
|---|---|
| words in the tokenised material (any count) | 3,853,102 |
| words in the material seen at least min_seen times | 795,818 |
| titles whose first sentence gave a hypernym phrase | 565,190 |
| titles with a qualifier phrase (other senses) | 49,918 |
| alias titles whose target had a type | 303,609 |
| paren-alias words whose head had a type | 97,617 |
| words whose sources disagree on noun / verb (or tie): both arm sets evaluated | 230 |
| rows in the headword table | 1,758,846 |
| rows with any evidence row | 1,223,413 |
| rows placed directly (DECIDED or MULTIPLE) | 993,027 |
<!-- END table:funnel -->

<!-- BEGIN table:l1_breadth -->
| breakdown of placed headwords | counts |
|---|---|
| by state | DECIDED=1002932, MULTIPLE=5792, UNPLACED=750122 |
| placed (direct) by namespace | N=990014, NP=8, P=3005 |
| placed (direct) by origin of the headword | paren_alias=94682, seed=656, title=878689, token=19000 |
| placed (direct) by decisive arm | alias=303576, definition=565083, definition_recovered=8222, frame@codex:code=33, frame@codex:code_qa=17, frame@codex:conversation=72, frame@codex:figurative_commonsense=101, frame@codex:general_qa=113, frame@codex:narrative=76, frame@codex:paraphrase_entail=121, frame@codex:pro=152, frame@jawiki=46, gen_definition=2557, hearst@codex:code=343, hearst@codex:code_qa=63, hearst@codex:conversation=13, hearst@codex:figurative_commonsense=14, hearst@codex:general_qa=624, hearst@codex:paraphrase_entail=1, hearst@jawiki=849, paren_alias=97609, pos_class@codex:code=257, pos_class@codex:code_qa=232, pos_class@codex:conversation=720, pos_class@codex:figurative_commonsense=919, pos_class@codex:general_qa=915, pos_class@codex:narrative=491, pos_class@codex:paraphrase_entail=345, pos_class@codex:pro=598, pos_class@jawiki=1986, role@codex:code=945, role@codex:code_qa=712, role@codex:conversation=1730, role@codex:figurative_commonsense=1702, role@codex:general_qa=2540, role@codex:narrative=1931, role@codex:paraphrase_entail=2911, role@codex:pro=1659, role@jawiki=2741, sahen@codex:code=2649, sahen@codex:code_qa=1191, sahen@codex:conversation=1753, sahen@codex:figurative_commonsense=1077, sahen@codex:general_qa=2027, sahen@codex:narrative=590, sahen@codex:paraphrase_entail=1600, sahen@codex:pro=709, sahen@jawiki=4978, seed=656 |
| all rows in the headword table | 1,758,846 |
<!-- END table:l1_breadth -->

<!-- BEGIN table:l1_by_pos -->
| word class | tokens | covered | rate |
|---|---|---|---|
| 動詞 | 2503 | 2089 | 83.5% |
| 名詞 | 18778 | 14635 | 77.9% |
| 形容詞 | 339 | 339 | 100.0% |
| 形状詞 | 154 | 154 | 100.0% |
<!-- END table:l1_by_pos -->

<!-- BEGIN table:l1_by_source -->
| source of the sentence | tokens | covered | rate |
|---|---|---|---|
| codex:code | 2010 | 1470 | 73.1% |
| codex:code_qa | 522 | 412 | 78.9% |
| codex:conversation | 1046 | 936 | 89.5% |
| codex:figurative_commonsense | 187 | 164 | 87.7% |
| codex:general_qa | 261 | 231 | 88.5% |
| codex:narrative | 43 | 34 | 79.1% |
| codex:paraphrase_entail | 432 | 366 | 84.7% |
| codex:pro | 1829 | 1526 | 83.4% |
| jawiki | 15444 | 12078 | 78.2% |
<!-- END table:l1_by_source -->

<!-- BEGIN table:l1_tokens_by_result -->
| kind | counts |
|---|---|
| origin of the answer | direct=14832, estimated=2385, none=4557 |
| state of the answer | DECIDED=14705, MULTIPLE=2512, UNKNOWN=357, UNPLACED=4200 |
<!-- END table:l1_tokens_by_result -->

The most frequent uncovered tokens (a material for the next improvement):

<!-- BEGIN table:l1_top_misses -->
| word | class | uncovered tokens |
|---|---|---|
| 出身 | 名詞 | 46 |
| 合衆 | 名詞 | 41 |
| 名 | 名詞 | 24 |
| 愛知 | 名詞 | 22 |
| 会 | 名詞 | 22 |
| 共和 | 名詞 | 21 |
| of | 名詞 | 16 |
| 図書 | 名詞 | 15 |
| 国際 | 名詞 | 14 |
| もの | 名詞 | 14 |
| 博物 | 名詞 | 13 |
| 読む | 動詞 | 12 |
| error | 名詞 | 12 |
| The | 名詞 | 11 |
| 美術 | 名詞 | 11 |
| レビュー | 名詞 | 11 |
| 人民 | 名詞 | 10 |
| 姓 | 名詞 | 10 |
| 指す | 動詞 | 10 |
| 示す | 動詞 | 10 |
| シングル | 名詞 | 10 |
| 官僚 | 名詞 | 9 |
| もり | 名詞 | 9 |
| BS | 名詞 | 9 |
| 南宋 | 名詞 | 9 |
| ぶん | 名詞 | 9 |
| 例 | 名詞 | 9 |
| コマンド | 名詞 | 9 |
| to | 名詞 | 9 |
| git | 名詞 | 9 |
| ごう | 名詞 | 8 |
| for | 名詞 | 8 |
| 民国 | 名詞 | 8 |
| 系列 | 名詞 | 8 |
| グラフ | 名詞 | 8 |
| value | 名詞 | 8 |
| 式 | 名詞 | 8 |
| 朝 | 名詞 | 8 |
| 何 | 名詞 | 8 |
| 配列 | 名詞 | 8 |
<!-- END table:l1_top_misses -->

### L2: direct placement

<!-- BEGIN table:l2_summary -->
| measure | value |
|---|---|
| words scored (seed words removed) | 1072 |
| direct | 739 |
| non-direct (reference) | None/other=162, estimated/correct=145, estimated/wrong_single=26 |
| by state | DECIDED=773, MULTIPLE=137, UNKNOWN=11, UNPLACED=151 |
| size of top (number of types listed -> words) | 0->162, 1->773, 2->111, 3->20, 4->5, 5->1 |
<!-- END table:l2_summary -->

By gold type (outcomes: `correct`, `wrong_single`, `other`; `(non-direct)` marks answers that were estimates):

<!-- BEGIN table:l2_by_type -->
| gold type | outcomes |
|---|---|
| ABSTRACT | correct=17, correct(non-direct)=10, other=10, other(non-direct)=9, wrong_single=5, wrong_single(non-direct)=2 |
| ABSTRACT,STATE_PROPERTY | other(non-direct)=1 |
| ANIMAL | correct=14, correct(non-direct)=19, other=10, other(non-direct)=3 |
| ARTIFACT | correct=36, correct(non-direct)=8, other=17, other(non-direct)=23, wrong_single=6, wrong_single(non-direct)=2 |
| BODY_PART | correct=9, correct(non-direct)=6, other=5, other(non-direct)=16, wrong_single=7, wrong_single(non-direct)=1 |
| BODY_PART,PLACE | correct=1 |
| EVENT_ACT | correct=34, correct(non-direct)=6, other=12, other(non-direct)=8, wrong_single=2, wrong_single(non-direct)=2 |
| EVENT_ACT,ABSTRACT | correct=2 |
| EVENT_ACT,INFO_LANGUAGE | correct=3, other=1, other(non-direct)=1 |
| EVENT_ACT,SUBSTANCE_FOOD | correct(non-direct)=1 |
| GROUP_ORG | correct=27, correct(non-direct)=22, other=5, other(non-direct)=3, wrong_single=1, wrong_single(non-direct)=3 |
| GROUP_ORG,EVENT_ACT | correct(non-direct)=2 |
| GROUP_ORG,PLACE | correct=4 |
| IDENTIFIER | correct=15 |
| INFO_LANGUAGE | correct=18, correct(non-direct)=2, other=10, other(non-direct)=7, wrong_single=2, wrong_single(non-direct)=1 |
| INFO_LANGUAGE,ABSTRACT | other(non-direct)=1 |
| INFO_LANGUAGE,WORK | correct=2, correct(non-direct)=1, other(non-direct)=1, wrong_single=2 |
| NATURAL_PHENOMENON | correct=11, correct(non-direct)=10, other=5, other(non-direct)=4, wrong_single=3, wrong_single(non-direct)=1 |
| NATURAL_PHENOMENON,PLACE | correct=2 |
| PERSON | correct=48, correct(non-direct)=9, other=3, other(non-direct)=17, wrong_single=1, wrong_single(non-direct)=4 |
| PLACE | correct=70, correct(non-direct)=3, other=7, other(non-direct)=15, wrong_single(non-direct)=2 |
| PLACE,ABSTRACT | correct=2 |
| PLACE,GROUP_ORG | correct=15, correct(non-direct)=2 |
| PLANT | correct=19, correct(non-direct)=8, other=4, other(non-direct)=3, wrong_single=3 |
| PLANT,SUBSTANCE_FOOD | correct=16, correct(non-direct)=2 |
| QUANTITY | correct=65, correct(non-direct)=3, other=11, other(non-direct)=15, wrong_single=8, wrong_single(non-direct)=1 |
| STATE_PROPERTY | correct=15, correct(non-direct)=13, other=7, other(non-direct)=8, wrong_single=4 |
| SUBSTANCE_FOOD | correct=33, correct(non-direct)=7, other=13, other(non-direct)=9, wrong_single=1, wrong_single(non-direct)=4 |
| SUBSTANCE_FOOD,ARTIFACT | other(non-direct)=3 |
| TIME | correct=75, correct(non-direct)=7, other=5, other(non-direct)=9, wrong_single=1, wrong_single(non-direct)=1 |
| TIME,EVENT_ACT | correct=3 |
| WORK | correct=11, correct(non-direct)=4, other(non-direct)=6, wrong_single=1, wrong_single(non-direct)=2 |
<!-- END table:l2_by_type -->

By category:

<!-- BEGIN table:l2_by_category -->
| category | outcomes |
|---|---|
| daily | correct=200, correct(non-direct)=66, other=99, other(non-direct)=77, wrong_single=30, wrong_single(non-direct)=7 |
| polysemous | correct=50, correct(non-direct)=8, other=1, other(non-direct)=7, wrong_single=2 |
| proper | correct=75, correct(non-direct)=34, other=6, other(non-direct)=32, wrong_single=3, wrong_single(non-direct)=13 |
| technical | correct=154, correct(non-direct)=36, other=18, other(non-direct)=40, wrong_single=12, wrong_single(non-direct)=6 |
| time_quantity | correct=88, correct(non-direct)=1, other=1, other(non-direct)=6 |
<!-- END table:l2_by_category -->

By the arm that decided:

<!-- BEGIN table:l2_by_arm -->
| decisive arm | outcomes |
|---|---|
| - | other(non-direct)=162 |
| alias | correct=16, wrong_single=7 |
| alias+hearst | correct=2, other=1 |
| alias+hearst+role | correct=1 |
| alias+hearst+role+sahen | other=1 |
| alias+paren_alias | correct=4, other=1 |
| alias+paren_alias+role | other=1 |
| alias+role | correct=3, other=2 |
| definition | correct=134, wrong_single=12 |
| definition+hearst | correct=22, other=7 |
| definition+hearst+paren_alias+role | other=1 |
| definition+hearst+role | correct=21, other=9 |
| definition+hearst+role+sahen | other=1 |
| definition+hearst+sahen | other=1 |
| definition+paren_alias+role | correct=1 |
| definition+role | correct=27, other=14, wrong_single=1 |
| definition+role+sahen | other=1 |
| definition+sahen | correct=1, other=2 |
| definition_recovered | correct=8, wrong_single=2 |
| definition_recovered+hearst | correct=3, other=3 |
| definition_recovered+hearst+role | correct=1, other=1 |
| definition_recovered+role | correct=8, other=2 |
| definition_recovered+sahen | other=1 |
| est:morphology:head | correct(non-direct)=5, wrong_single(non-direct)=8 |
| est:morphology:head+morphology:kin | correct(non-direct)=8 |
| est:morphology:kin | correct(non-direct)=25, wrong_single(non-direct)=5 |
| gen_definition | correct(non-direct)=107, wrong_single(non-direct)=13 |
| gen_definition+role | correct=27 |
| hearst | correct=27, other=3, wrong_single=10 |
| hearst+paren_alias+role | correct=1 |
| hearst+role | correct=11, other=15 |
| hearst+sahen | other=1 |
| notation | correct=92 |
| paren_alias | correct=3 |
| paren_alias+role | correct=1, other=3 |
| pos_class | wrong_single=1 |
| role | correct=123, other=49, wrong_single=11 |
| role+sahen | correct=4, other=5 |
| sahen | correct=26, wrong_single=3 |
<!-- END table:l2_by_arm -->

End-of-word traps, by the type the word ending suggests:

<!-- BEGIN table:l2_traps -->
| end-of-word unit suggests | outcomes |
|---|---|
| ANIMAL | correct=5, correct(non-direct)=1, other=1, other(non-direct)=5, wrong_single=2 |
| ARTIFACT | correct=1, correct(non-direct)=1, other=1, other(non-direct)=2, wrong_single=1 |
| BODY_PART | correct=5, correct(non-direct)=2, other=2, other(non-direct)=3, wrong_single=1, wrong_single(non-direct)=1 |
| EVENT_ACT | correct=2, correct(non-direct)=2 |
| GROUP_ORG | correct=7, correct(non-direct)=2, other=2, other(non-direct)=2 |
| NATURAL_PHENOMENON | correct=8, correct(non-direct)=1, other=1, other(non-direct)=2, wrong_single(non-direct)=1 |
| PERSON | correct=10, correct(non-direct)=5, other=5, other(non-direct)=7, wrong_single=1, wrong_single(non-direct)=1 |
| PLACE | correct=14, correct(non-direct)=1, other=4, other(non-direct)=6, wrong_single(non-direct)=1 |
| PLANT | correct=4, other=1, other(non-direct)=3, wrong_single(non-direct)=1 |
| QUANTITY | other(non-direct)=1 |
| SUBSTANCE_FOOD | correct=7, correct(non-direct)=1, other=1, other(non-direct)=5 |
| TIME | correct=2, other=2, other(non-direct)=5, wrong_single=2 |
<!-- END table:l2_traps -->

Proposed corrections of the answer key (the frozen key is never changed; the proposals are
in `artifacts/w3-a/gold_errata_proposed.jsonl`, and the reference rescoring below is for the
reviewer's decision only):

<!-- BEGIN table:errata_ref -->
| scoring | n | correct | wrong decision | trap wrong decision |
|---|---|---|---|---|
| frozen key (official) | 1072 | 52.9% | 4.4% | 4.5% |
| with the proposed errata (reference only; the reviewer decides): V0478, V0683, V0684, V0685, V0724, V0729, V0732, V0948, V0949, V0950, V1069, V1073 | 1072 | 53.4% | 4.0% | 3.9% |
<!-- END table:errata_ref -->

### L3: estimation from nearness

<!-- BEGIN table:l3_by_kind -->
| kind | outcomes |
|---|---|
| coinage | correct=10, unknown=8 |
| compound | correct=64, unknown=62, wrong=9 |
| neologism | unknown=3 |
| proper | correct=12, unknown=6 |
<!-- END table:l3_by_kind -->

<!-- BEGIN table:l3_by_type -->
| gold type | outcomes |
|---|---|
| ABSTRACT | correct=2, unknown=8 |
| ANIMAL | correct=4, unknown=6 |
| ARTIFACT | correct=2, unknown=5, wrong=3 |
| BODY_PART | correct=10 |
| EVENT_ACT | correct=5, unknown=4 |
| EVENT_ACT,GROUP_ORG | correct=1 |
| GROUP_ORG | correct=5, unknown=2, wrong=3 |
| IDENTIFIER | correct=5 |
| INFO_LANGUAGE | correct=1, unknown=7, wrong=1 |
| INFO_LANGUAGE,WORK | correct=1 |
| NATURAL_PHENOMENON | unknown=10 |
| PERSON | correct=9, unknown=7 |
| PLACE | correct=7, unknown=5 |
| PLACE,GROUP_ORG | correct=1 |
| PLANT | correct=6, unknown=4 |
| QUANTITY | correct=5, unknown=5 |
| STATE_PROPERTY | correct=3, unknown=7 |
| SUBSTANCE_FOOD | correct=10 |
| TIME | correct=2, unknown=6, wrong=2 |
| WORK | correct=7, unknown=3 |
<!-- END table:l3_by_type -->

<!-- BEGIN table:l3_by_stage -->
| deciding stage | outcomes |
|---|---|
| - | unknown=79 |
| est:context | correct=25, wrong=2 |
| est:context+morphology:head | correct=8 |
| est:context+morphology:head+morphology:kin | correct=3 |
| est:context+morphology:kin | correct=8, wrong=1 |
| est:morphology:head | correct=18, wrong=5 |
| est:morphology:head+morphology:kin | correct=11 |
| est:morphology:kin | correct=8, wrong=1 |
| notation | correct=5 |
<!-- END table:l3_by_stage -->

### L5: speed

<!-- BEGIN table:speed -->
| measure | value |
|---|---|
| queries | 23083 |
| mean ms | 0.093 |
| median ms | 0.078 |
| p95 ms | 0.202 |
| max ms | 2.903 |
| command-line call incl. load (ms) | 199.3 |
| interpreter + import only (ms) | 108.0 |
<!-- END table:speed -->

### Predicates (report only, not an acceptance criterion)

<!-- BEGIN table:pred -->
| subset | n | correct | wrong (one type) | returned any type |
|---|---|---|---|---|
| all | 119 | 15 | 25 | 45 |
| not a seed of this build (the official figure) | 119 | 15 | 25 | 45 |
| P_ACT | 10 | 0 | 1 | 1 |
| P_CHANGE | 10 | 2 | 2 | 4 |
| P_COGNITION | 8 | 0 | 2 | 2 |
| P_COMMUNICATE | 8 | 0 | 2 | 2 |
| P_CONSUME | 9 | 0 | 2 | 5 |
| P_CREATE | 8 | 0 | 1 | 1 |
| P_EMOTION | 10 | 0 | 2 | 2 |
| P_EXIST | 10 | 1 | 2 | 3 |
| P_GIVE | 8 | 2 | 4 | 7 |
| P_MOVE | 10 | 0 | 3 | 3 |
| P_PERCEIVE | 9 | 0 | 1 | 2 |
| P_POSSESS | 9 | 0 | 3 | 3 |
| P_STATE | 10 | 10 | 0 | 10 |
<!-- END table:pred -->

<!-- BEGIN table:pred_by_arm -->
| decisive arm | n | correct | wrong (one type) | returned any |
|---|---|---|---|---|
| - | 74 | 0 | 0 | 0 |
| alias | 2 | 0 | 2 | 2 |
| definition | 1 | 0 | 1 | 1 |
| est:morphology:head | 12 | 3 | 9 | 12 |
| est:morphology:kin | 2 | 0 | 2 | 2 |
| frame | 18 | 2 | 11 | 18 |
| pos_class | 10 | 10 | 0 | 10 |
<!-- END table:pred_by_arm -->

### Decision-rule audit (review round 1, M1 and M2)

Every direct headword of the final placement is re-decided from its stored evidence by the
shared function; the table must show zero in every check row.

<!-- BEGIN table:met_audit -->
| check (every decided headword of the final full placement) | count |
|---|---|
| direct headwords | 993,027 |
| estimated (generated) headwords | 15,697 |
| re-decided by coarse_types.decide_word from the stored evidence (direct + estimated) | 1,008,724 |
| stored origin differs from the recomputed one (W3-a2) | 0 |
| stored decision differs from the recomputed one | 0 |
| set of met arms differs from decided_by (M2) | 0 |
| decided by exactly one role source and no other arm (M1) | 0 |
| a role source among the deciding arms but fewer than role_min_sources | 0 |
| seed-decided word with another arm still marked met | 0 |
| direct by one role source below role_min_sources + an agreeing generated definition (by design, W3-a2) | 2557 |
| deciding arms (word counts) | alias=303576, definition=565083, definition_recovered=8222, frame=731, gen_definition=18254, hearst=1907, paren_alias=97609, pos_class=6463, role=16871, sahen=16574, seed=656 |
<!-- END table:met_audit -->

### The wrong words

The full list of words that were not directly and correctly placed (typed vocabulary)
and of unknown words that were wrong, returned a type when none was due, or got none
is `artifacts/w3-a/errors_final.md` (regenerated by the render script).

## 8. All measurements

Frozen test data (every run is kept):

<!-- BEGIN table:eval_history -->
| run | command | time (UTC) | placement sha | config sha | result |
|---|---|---|---|---|---|
| 001 | l2 | 2026-10-02T21:36:27Z | 317b1949dac3 | 2b77e9157b8b | correct 54.1%, wrong 9.5%, trap wrong 13.0% |
| 002 | l3 | 2026-10-02T21:36:28Z | 317b1949dac3 | 2b77e9157b8b | correct 44.8%, wrong 4.0%, returned-type 18.3% |
| 003 | l1 | 2026-10-02T21:36:31Z | 317b1949dac3 | 2b77e9157b8b | token cover 76.1%, placed 1,018,478 |
| 004 | pred | 2026-10-02T21:36:31Z | 317b1949dac3 | 2b77e9157b8b | non-seed correct 24 of 109 |
| 005 | l2 | 2026-10-02T22:01:10Z | e07d46485ef2 | e48fcb83e230 | correct 53.5%, wrong 8.6%, trap wrong 12.3% |
| 006 | l3 | 2026-10-02T22:01:10Z | e07d46485ef2 | e48fcb83e230 | correct 45.4%, wrong 4.0%, returned-type 18.3% |
| 007 | l1 | 2026-10-02T22:01:11Z | e07d46485ef2 | e48fcb83e230 | token cover 74.0%, placed 1,009,027 |
| 008 | pred | 2026-10-02T22:01:11Z | e07d46485ef2 | e48fcb83e230 | non-seed correct 24 of 109 |
| 009 | l5 | 2026-10-02T22:01:14Z | e07d46485ef2 | e48fcb83e230 | mean 0.071 ms, p95 0.154 ms |
| 010 | l2 | 2026-10-02T22:54:04Z | ad3879476719 | 19c2da226ee4 | correct 50.1%, wrong 5.5%, trap wrong 5.8% |
| 011 | l3 | 2026-10-02T22:54:04Z | ad3879476719 | 19c2da226ee4 | correct 51.1%, wrong 5.2%, returned-type 18.3% |
| 012 | l1 | 2026-10-02T22:54:06Z | ad3879476719 | 19c2da226ee4 | token cover 71.6%, placed 1,108,448 |
| 013 | pred | 2026-10-02T22:54:06Z | ad3879476719 | 19c2da226ee4 | non-seed correct 17 of 109 |
| 014 | pred | 2026-10-02T22:54:26Z | ad3879476719 | 19c2da226ee4 | non-seed correct 17 of 119 |
| 015 | l5 | 2026-10-02T22:54:29Z | ad3879476719 | 19c2da226ee4 | mean 0.084 ms, p95 0.196 ms |
| 016 | l2 | 2026-10-02T23:14:55Z | 5b649f8f4ac4 | 1b2878a09db6 | correct 50.1%, wrong 5.5%, trap wrong 5.8% |
| 017 | l3 | 2026-10-02T23:14:56Z | 5b649f8f4ac4 | 1b2878a09db6 | correct 51.1%, wrong 5.2%, returned-type 18.3% |
| 018 | l1 | 2026-10-02T23:14:57Z | 5b649f8f4ac4 | 1b2878a09db6 | token cover 71.2%, placed 1,108,448 |
| 019 | pred | 2026-10-02T23:14:57Z | 5b649f8f4ac4 | 1b2878a09db6 | non-seed correct 17 of 119 |
| 020 | l5 | 2026-10-02T23:15:00Z | 5b649f8f4ac4 | 1b2878a09db6 | mean 0.082 ms, p95 0.194 ms |
| 021 | l2 | 2026-10-03T00:28:21Z | eaee8a6361f6 | 6783f0528cc3 | correct 50.0%, wrong 4.4%, trap wrong 4.5% |
| 022 | l3 | 2026-10-03T00:28:21Z | eaee8a6361f6 | 6783f0528cc3 | correct 49.4%, wrong 5.2%, returned-type 15.0% |
| 023 | l1 | 2026-10-03T00:28:23Z | eaee8a6361f6 | 6783f0528cc3 | token cover 70.9%, placed 990,470 |
| 024 | pred | 2026-10-03T00:28:23Z | eaee8a6361f6 | 6783f0528cc3 | non-seed correct 15 of 119 |
| 025 | l5 | 2026-10-03T00:28:26Z | eaee8a6361f6 | 6783f0528cc3 | mean 0.087 ms, p95 0.196 ms |
| 026 | l2 | 2026-10-03T00:58:20Z | 44b9e08de935 | da1ad2b335d7 | correct 50.4%, wrong 4.4%, trap wrong 4.5% |
| 027 | l3 | 2026-10-03T00:58:21Z | 44b9e08de935 | da1ad2b335d7 | correct 49.4%, wrong 5.2%, returned-type 15.0% |
| 028 | l1 | 2026-10-03T00:58:22Z | 44b9e08de935 | da1ad2b335d7 | token cover 70.9%, placed 990,470 |
| 029 | pred | 2026-10-03T00:58:23Z | 44b9e08de935 | da1ad2b335d7 | non-seed correct 15 of 119 |
| 030 | l5 | 2026-10-03T00:58:25Z | 44b9e08de935 | da1ad2b335d7 | mean 0.086 ms, p95 0.191 ms |
| 031 | l2 | 2026-10-03T01:17:29Z | ce65b9c2081e | da1ad2b335d7 | correct 50.4%, wrong 4.4%, trap wrong 4.5% |
| 032 | l3 | 2026-10-03T01:17:29Z | ce65b9c2081e | da1ad2b335d7 | correct 49.4%, wrong 5.2%, returned-type 15.0% |
| 033 | l1 | 2026-10-03T01:17:31Z | ce65b9c2081e | da1ad2b335d7 | token cover 70.9%, placed 990,470 |
| 034 | pred | 2026-10-03T01:17:31Z | ce65b9c2081e | da1ad2b335d7 | non-seed correct 15 of 119 |
| 035 | l5 | 2026-10-03T01:17:34Z | ce65b9c2081e | da1ad2b335d7 | mean 0.09 ms, p95 0.199 ms |
| 036 | l2 | 2026-10-03T02:55:25Z | 7ca68ffe5546 | da1ad2b335d7 | correct 52.9%, wrong 4.4%, trap wrong 4.5% |
| 037 | l3 | 2026-10-03T02:55:25Z | 7ca68ffe5546 | da1ad2b335d7 | correct 50.6%, wrong 4.6%, returned-type 15.0% |
| 038 | l1 | 2026-10-03T02:55:26Z | 7ca68ffe5546 | da1ad2b335d7 | token cover 79.1%, placed 993,027 |
| 039 | pred | 2026-10-03T02:55:27Z | 7ca68ffe5546 | da1ad2b335d7 | non-seed correct 15 of 119 |
| 040 | l5 | 2026-10-03T02:55:29Z | 7ca68ffe5546 | da1ad2b335d7 | mean 0.087 ms, p95 0.191 ms |
| 041 | l2 | 2026-10-03T03:46:17Z | ecd3f8e38e18 | a1c0c2047533 | correct 52.9%, wrong 4.4%, trap wrong 4.5% |
| 042 | l3 | 2026-10-03T03:46:17Z | ecd3f8e38e18 | a1c0c2047533 | correct 49.4%, wrong 5.2%, returned-type 15.0% |
| 043 | l1 | 2026-10-03T03:46:19Z | ecd3f8e38e18 | a1c0c2047533 | token cover 79.1%, placed 993,027 |
| 044 | pred | 2026-10-03T03:46:19Z | ecd3f8e38e18 | a1c0c2047533 | non-seed correct 15 of 119 |
| 045 | l5 | 2026-10-03T03:46:22Z | ecd3f8e38e18 | a1c0c2047533 | mean 0.093 ms, p95 0.202 ms |
<!-- END table:eval_history -->

Dev data (used to choose the configuration; none of these touches the frozen test data):

<!-- BEGIN table:dev_history -->
| run | command | placement | config sha | dev result |
|---|---|---|---|---|
| 001 | l2 | sample/run1 | f7b47d37f4f0 | correct 9.3%, wrong 0.7%, trap wrong 0.0% |
| 002 | l3 | sample/run1 | f7b47d37f4f0 | correct 10.0%, wrong 6.0%, returned-type 0.0% |
| 003 | l2 | dev/full1 | f7b47d37f4f0 | correct 36.7%, wrong 24.8%, trap wrong 29.7% |
| 004 | l3 | dev/full1 | f7b47d37f4f0 | correct 32.0%, wrong 26.0%, returned-type 6.7% |
| 005 | l1 | dev/full1 | f7b47d37f4f0 | dev token cover 80.2% |
| 006 | l2 | dev/full2 | 6f93fc7c83c0 | correct 50.0%, wrong 11.2%, trap wrong 16.2% |
| 007 | l3 | dev/full2 | 6f93fc7c83c0 | correct 46.0%, wrong 8.0%, returned-type 13.3% |
| 008 | l1 | dev/full2 | 6f93fc7c83c0 | dev token cover 73.6% |
| 009 | l2 | dev/v1 | 70768e1f7066 | correct 51.2%, wrong 9.7%, trap wrong 16.2% |
| 010 | l3 | dev/v1 | 70768e1f7066 | correct 46.0%, wrong 8.0%, returned-type 13.3% |
| 011 | l2 | dev/v2 | b7609bb79b2a | correct 49.8%, wrong 8.1%, trap wrong 8.1% |
| 012 | l3 | dev/v2 | b7609bb79b2a | correct 46.0%, wrong 8.0%, returned-type 13.3% |
| 013 | l1 | dev/v1 | 70768e1f7066 | dev token cover 73.0% |
| 014 | l1 | dev/v2 | b7609bb79b2a | dev token cover 72.9% |
| 015 | l2 | dev/v3 | 55025227e29d | correct 52.4%, wrong 11.7%, trap wrong 21.6% |
| 016 | l3 | dev/v3 | 55025227e29d | correct 48.0%, wrong 8.0%, returned-type 13.3% |
| 017 | l1 | dev/v3 | 55025227e29d | dev token cover 79.5% |
| 018 | l2 | dev/h1 | bdc2c456a04d | correct 51.0%, wrong 6.9%, trap wrong 10.8% |
| 019 | l3 | dev/h1 | bdc2c456a04d | correct 46.0%, wrong 8.0%, returned-type 13.3% |
| 020 | l1 | dev/h1 | bdc2c456a04d | dev token cover 73.6% |
| 021 | l2 | dev/h2a | bdc2c456a04d | correct 51.0%, wrong 6.9%, trap wrong 10.8% |
| 022 | l2 | dev/h2b | 056230049117 | correct 51.0%, wrong 6.9%, trap wrong 10.8% |
| 023 | l3 | dev/h2a | bdc2c456a04d | correct 46.0%, wrong 8.0%, returned-type 13.3% |
| 024 | l3 | dev/h2b | 056230049117 | correct 60.0%, wrong 10.0%, returned-type 20.0% |
| 025 | l1 | dev/h2b | 056230049117 | dev token cover 76.1% |
| 026 | l1 | dev/h2a | bdc2c456a04d | dev token cover 75.5% |
| 027 | l2 | dev/h2d | 65b1448c8042 | correct 50.2%, wrong 8.5%, trap wrong 10.8% |
| 028 | l3 | dev/h2d | 65b1448c8042 | correct 72.0%, wrong 12.0%, returned-type 20.0% |
| 029 | l2 | dev/h2c | 746a640b0897 | correct 50.2%, wrong 8.5%, trap wrong 10.8% |
| 030 | l3 | dev/h2c | 746a640b0897 | correct 48.0%, wrong 8.0%, returned-type 13.3% |
| 031 | l1 | dev/h2d | 65b1448c8042 | dev token cover 82.7% |
| 032 | l1 | dev/h2c | 746a640b0897 | dev token cover 81.4% |
| 033 | l5 | dev/h2d | 65b1448c8042 | mean 0.073 ms |
| 034 | l2 | dev/h3e | daa213d261e0 | correct 51.9%, wrong 7.6%, trap wrong 13.5% |
| 035 | l3 | dev/h3e | daa213d261e0 | correct 72.0%, wrong 18.0%, returned-type 26.7% |
| 036 | l1 | dev/h3e | daa213d261e0 | dev token cover 78.2% |
| 037 | l2 | dev/h3g | 2b77e9157b8b | correct 51.9%, wrong 7.6%, trap wrong 13.5% |
| 038 | l2 | dev/h3h | 99d1df21a158 | correct 51.9%, wrong 7.6%, trap wrong 13.5% |
| 039 | l2 | dev/h3f | 688af64b7bd0 | correct 51.9%, wrong 7.6%, trap wrong 13.5% |
| 040 | l3 | dev/h3h | 99d1df21a158 | correct 60.0%, wrong 18.0%, returned-type 13.3% |
| 041 | l3 | dev/h3f | 688af64b7bd0 | correct 52.0%, wrong 12.0%, returned-type 13.3% |
| 042 | l1 | dev/h3g | 2b77e9157b8b | dev token cover 77.0% |
| 043 | l1 | dev/h3h | 99d1df21a158 | dev token cover 77.5% |
| 044 | l1 | dev/h3f | 688af64b7bd0 | dev token cover 77.3% |
| 045 | l3 | dev/h3g | 2b77e9157b8b | correct 52.0%, wrong 10.0%, returned-type 13.3% |
| 046 | l2 | dev/h4r1 | d89a52e139bb | correct 51.7%, wrong 7.6%, trap wrong 13.5% |
| 047 | l3 | dev/h4r1 | d89a52e139bb | correct 52.0%, wrong 10.0%, returned-type 13.3% |
| 048 | l1 | dev/h4r1 | d89a52e139bb | dev token cover 76.8% |
| 049 | l2 | dev/h4r2 | e48fcb83e230 | correct 50.3%, wrong 7.1%, trap wrong 10.8% |
| 050 | l2 | dev/h4r3 | ff1cbfb7ce80 | correct 48.4%, wrong 7.1%, trap wrong 13.5% |
| 051 | l3 | dev/h4r2 | e48fcb83e230 | correct 52.0%, wrong 10.0%, returned-type 13.3% |
| 052 | l3 | dev/h4r3 | ff1cbfb7ce80 | correct 54.0%, wrong 10.0%, returned-type 13.3% |
| 053 | l1 | dev/h4r2 | e48fcb83e230 | dev token cover 74.4% |
| 054 | l1 | dev/h4r3 | ff1cbfb7ce80 | dev token cover 71.4% |
| 055 | l3 | dev/r2a | 35822b0c60bf | correct 56.0%, wrong 4.0%, returned-type 20.0% |
| 056 | l2 | dev/r2a | 35822b0c60bf | correct 46.9%, wrong 6.7%, trap wrong 13.5% |
| 057 | l1 | dev/r2a | 35822b0c60bf | dev token cover 74.4% |
| 058 | l2 | dev/r2b | 19c2da226ee4 | correct 47.1%, wrong 6.0%, trap wrong 13.5% |
| 059 | l3 | dev/r2b | 19c2da226ee4 | correct 56.0%, wrong 4.0%, returned-type 20.0% |
| 060 | l1 | dev/r2b | 19c2da226ee4 | dev token cover 72.0% |
| 061 | l2 | dev/r2c | 32dedb632284 | correct 47.1%, wrong 6.0%, trap wrong 13.5% |
| 062 | l3 | dev/r2c | 32dedb632284 | correct 56.0%, wrong 4.0%, returned-type 20.0% |
| 063 | l1 | dev/r2c | 32dedb632284 | dev token cover 72.0% |
| 064 | l2 | dev/r2d | bb1826818e04 | correct 47.1%, wrong 6.0%, trap wrong 13.5% |
| 065 | l3 | dev/r2d | bb1826818e04 | correct 56.0%, wrong 4.0%, returned-type 20.0% |
| 066 | l1 | dev/r2d | bb1826818e04 | dev token cover 72.0% |
| 067 | l2 | dev/r2e | dc1f71d01cd9 | correct 47.2%, wrong 6.0%, trap wrong 16.2% |
| 068 | l3 | dev/r2e | dc1f71d01cd9 | correct 58.0%, wrong 6.0%, returned-type 13.3% |
| 069 | l1 | dev/r2e | dc1f71d01cd9 | dev token cover 68.5% |
| 070 | l2 | dev/r2f | 1b2878a09db6 | correct 47.1%, wrong 6.0%, trap wrong 13.5% |
| 071 | l3 | dev/r2f | 1b2878a09db6 | correct 56.0%, wrong 4.0%, returned-type 20.0% |
| 072 | l1 | dev/r2f | 1b2878a09db6 | dev token cover 71.5% |
| 073 | l2 | dev/r3a | 054354cf05f9 | correct 45.3%, wrong 4.5%, trap wrong 10.8% |
| 074 | l3 | dev/r3a | 054354cf05f9 | correct 52.0%, wrong 2.0%, returned-type 13.3% |
| 075 | l1 | dev/r3a | 054354cf05f9 | dev token cover 70.6% |
| 076 | l2 | dev/r3base | d925a542184c | correct 46.2%, wrong 5.2%, trap wrong 13.5% |
| 077 | l3 | dev/r3base | d925a542184c | correct 58.0%, wrong 4.0%, returned-type 13.3% |
| 078 | l1 | dev/r3base | d925a542184c | dev token cover 70.9% |
| 079 | l2 | dev/r3c2 | a2dde7251f5c | correct 44.1%, wrong 4.1%, trap wrong 10.8% |
| 080 | l3 | dev/r3c2 | a2dde7251f5c | correct 52.0%, wrong 2.0%, returned-type 13.3% |
| 081 | l1 | dev/r3c2 | a2dde7251f5c | dev token cover 70.5% |
| 082 | l2 | dev/r3c3 | 1773de540359 | correct 45.3%, wrong 4.5%, trap wrong 10.8% |
| 083 | l3 | dev/r3c3 | 1773de540359 | correct 52.0%, wrong 2.0%, returned-type 13.3% |
| 084 | l1 | dev/r3c3 | 1773de540359 | dev token cover 70.6% |
| 085 | l2 | dev/r3c5 | 6783f0528cc3 | correct 46.6%, wrong 4.1%, trap wrong 10.8% |
| 086 | l3 | dev/r3c5 | 6783f0528cc3 | correct 52.0%, wrong 0.0%, returned-type 6.7% |
| 087 | l1 | dev/r3c5 | 6783f0528cc3 | dev token cover 71.1% |
| 088 | l2 | dev/r4a | da1ad2b335d7 | correct 51.4%, wrong 4.1%, trap wrong 10.8% |
| 089 | l3 | dev/r4a | da1ad2b335d7 | correct 54.0%, wrong 0.0%, returned-type 6.7% |
| 090 | l1 | dev/r4a | da1ad2b335d7 | dev token cover 79.0% |
| 091 | l2 | dev/r4b | 57282a2bbd9f | correct 46.9%, wrong 4.1%, trap wrong 10.8% |
| 092 | l3 | dev/r4b | 57282a2bbd9f | correct 52.0%, wrong 0.0%, returned-type 6.7% |
| 093 | l1 | dev/r4b | 57282a2bbd9f | dev token cover 79.0% |
| 094 | l2 | dev/r5a | a1c0c2047533 | correct 51.4%, wrong 4.1%, trap wrong 10.8% |
| 095 | l3 | dev/r5a | a1c0c2047533 | correct 52.0%, wrong 0.0%, returned-type 6.7% |
| 096 | l1 | dev/r5a | a1c0c2047533 | dev token cover 79.0% |
<!-- END table:dev_history -->

## 9. Limits (what sets the ceiling)

- **Evidence is thin for common words.**  Many everyday words have no article of their own
  or only a one-line article without a hypernym; for them the arms of running text (role,
  hypernym pairs) must carry the decision, and a role slot is only weakly typed (the same
  particle + verb takes places, times and things alike).  The funnel table shows how many
  words reach each step.
- **A title is often another sense.**  Common words are also titles of works; such
  "X (qualifier)" articles are kept as a separate, weaker arm and only split a decision
  into `MULTIPLE`.
- **Hypernym phrases.**  A first sentence that does not end in a noun phrase, or that
  nominalises a verb phrase, gives no hypernym; the type of a hypernym that is itself
  ambiguous or mis-typed propagates one step down the chain (the chain depth is a
  configured value).
- **Constituents.**  The tokenizer cuts words into short units; a unit that occurs only
  inside compounds (a modifier, a reading in kana) has no standalone evidence and stays
  unplaced unless the word is estimated.
- **What bounds the direct accuracy.**  The only precise arm is the definition arm and it
  covers only words whose own article gives a typed hypernym; redirect aliases often point at a
  broader topic, a plain title is sometimes another sense (a band, a programme) of a common word,
  and a hypernym that is mis-typed propagates down the chain.  Role evidence is the weakest
  arm; since it can no longer decide on one source, many everyday words that earlier got a
  (partly wrong) role-only type are now left unplaced.  The wrong-word list shows these cases.
- **What bounds the coverage.**  Of the content tokens with no type, most are short kanji
  words and suffix-like units (a unit the tokeniser cut off a compound), Latin-script words in
  code, loanwords without an article, and kana-spelled words.  Giving them a default type would
  raise the coverage number without evidence and is not done; the optional last tier `kin_left`
  (off by default) would cover a cut-off fragment only when a large, almost uniform family of placed
  words starts with it.
- **Foreign-script tokens** (identifiers and English words in code) are not typed beyond
  the spelling rules.
- **Verbs** are placed by seeds, word class and a small structure table; the quality of
  the structure table is only reported (predicate table above).
- **Gold ambiguity.**  The boundary rules leave genuinely arguable words (a physical
  process is an event or a phenomenon; a hypernym such as "activity" says `EVENT_ACT`
  where the key says `ABSTRACT`); these appear in the wrong-word list.

## 10. Reproduction

```
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S ; PY=$W/artifacts/w3-a/py.sh
$PY $W/tools/build_coarse_placement.py build --jawiki <jawiki_leads.jsonl> --codex-dir <p4-W1c> \
    --out <dir> --exclude-terms tests/coarse_place/data/unknown_words.jsonl \
    --exclude-terms tests/coarse_place/data/dev_unknown.jsonl \
    --holdout artifacts/w3-a/holdout_2000.jsonl --holdout artifacts/w3-a/dev_l1_1000.jsonl \
    --frozen artifacts/w3-a/FROZEN.json --config artifacts/w3-a/config_final.json
$PY $W/tools/build_coarse_placement.py verify --placement <dir>
$PY $W/artifacts/w3-a/measure_w3a.py l1|l2|l3|l5|pred --placement <dir>
$PY $W/artifacts/w3-a/render_docs_numbers.py --check
$PY -m verantyx.coarse_place --term <word> --placement <dir>
```


## 11. W3-a2: 連鎖の誤りを止める・足りない証拠を生成して埋める（日本語）

この節の数値はすべて、`artifacts/w3-a/` の測定出力から `render_docs_numbers.py` が表に書き出したもの（表の外の本文には測っていない数値を書かない）。

### 11.1 何を直したか

- **F1（連鎖の誤り）**: 1 つの誤った上位語の型が、その語を上位語に持つ数千の記事に広がっていた。次の 3 つで止める。(a) 並列の上位語を全部取る（「者、もしくはグループ」の両方。型が割れれば腕の中の同点で、決めない）。(b) 代わりの取り方（`first_clause_phrases`）は、格助詞（から・まで・より・に・で・へ・と・を・が）の直後で読点の前の名詞の連続（「平安から鎌倉時代、」）を上位語にしない。代わりの取り方で取った定義は腕 `definition_recovered` として区別して evidence に残す。(c) **donor（連鎖で型を渡す語）を 2 段で決める**: 段 A（今までどおり）で全部解き、その最終の判定が DECIDED（連鎖が渡す型と同じ）で、かつ別の種類の腕（役割の票・hearst・別名・括弧別表記・表題の限定語。出所ごと・腕ごとに 1 つずつ、足さない）に違う 1 つの型が最上位で `donor_contra_min` 票以上ある腕が無い語だけを donor にして、連鎖・文脈の表・役割の票・hearst を段 B でやり直し、これを最終にする（段 B の結果で donor を作り直さない）。設定と dev での決め方は `artifacts/w3-a/DECISIONS.md` §5-2・§5-3。
- **F2（数量の単位）**: 助数詞の表は、1 形態素の単位を 6 文字まで、2 形態素をつないだ単位を 3 文字までにした。英数字の識別子の規則では単位を除外せず（時刻の単位だけ除く）、`notation_type` は学んだ単位を英数字の識別子の規則より先に見る（文字で始まるコードは識別子のまま）。**欧文の単位は構造の規則で絞る**（第 2 ラウンド、第 11.8 節）: 1 形態素の表だけから採り、その出所で「算用数字の直後に出た回数」が「名詞として出た回数」の `counter_latin_share_pct`% 以上、かつ直前の数字が `counter_latin_numerals_min` 種類以上のときだけ 1 票にする。`of`・`and`・`for` のような語と `4xx`・`5xx` の `xx` は、この規則で表に入らない。
- **F3（画像説明の残り）**: 定義に使う部分が「の」で始まり、主題（は）を含まないものは定義にしない（manifest の理由別に `caption_fragment`）。
- **F4**: `tests/coarse_place/test_coarse_place_review2.py` の無意味な `or` の assert を強めた。**F5**: 前の報告の直接配置の数値の誤りは `impl.r1.md`（W3-a2）で訂正した。**F6**: `__pycache__` を消した。

<!-- BEGIN table:hub_spread -->
| placement | hub (a lead ending in 'の<hub>。') | articles | wrongly typed and DECIDED (the type it was wrongly given) | state/top of the article's title (top 5) |
|---|---|---|---|---|
| r2b (W3-a, before the fix) | 小説家 | 2212 | 2070 (GROUP_ORG) | DECIDED/GROUP_ORG=2070, NONE/-=140, MULTIPLE/GROUP_ORG,PLANT=1, MULTIPLE/GROUP_ORG,PERSON=1 |
| r2b (W3-a, before the fix) | 僧 | 826 | 768 (GROUP_ORG) | DECIDED/GROUP_ORG=768, NONE/-=57, MULTIPLE/GROUP_ORG,INFO_LANGUAGE,PERSON,QUANTITY=1 |
| r2b (W3-a, before the fix) | 大名 | 1566 | 1496 (TIME) | DECIDED/TIME=1496, NONE/-=70 |
| r2b (W3-a, before the fix) | 武将 | 6917 |  | NONE/-=5908, UNPLACED/-=1007, MULTIPLE/EVENT_ACT,PLACE=1, DECIDED/P_STATE=1 |
| r2b (W3-a, before the fix) | 僧侶 | 439 |  | NONE/-=380, UNPLACED/-=58, DECIDED/P_STATE=1 |
| r2b (W3-a, before the fix) | 網膜 | 0 |  |  |
| r3c (F1-F6 only) | 小説家 | 2212 | 0 (GROUP_ORG) | NONE/-=1838, UNPLACED/-=371, DECIDED/PERSON=2, DECIDED/PLANT=1 |
| r3c (F1-F6 only) | 僧 | 826 | 0 (GROUP_ORG) | NONE/-=640, UNPLACED/-=185, MULTIPLE/IDENTIFIER,PERSON=1 |
| r3c (F1-F6 only) | 大名 | 1566 | 0 (TIME) | NONE/-=1398, UNPLACED/-=168 |
| r3c (F1-F6 only) | 武将 | 6917 |  | NONE/-=5916, UNPLACED/-=1000, DECIDED/P_STATE=1 |
| r3c (F1-F6 only) | 僧侶 | 439 |  | NONE/-=380, UNPLACED/-=58, DECIDED/P_STATE=1 |
| r3c (F1-F6 only) | 網膜 | 0 |  |  |
| r4 (round 1) | 小説家 | 2212 | 0 (GROUP_ORG) | NONE/-=1838, UNPLACED/-=369, DECIDED/PERSON=4, DECIDED/PLANT=1 |
| r4 (round 1) | 僧 | 826 | 0 (GROUP_ORG) | NONE/-=640, UNPLACED/-=184, MULTIPLE/IDENTIFIER,PERSON=1, DECIDED/INFO_LANGUAGE=1 |
| r4 (round 1) | 大名 | 1566 | 0 (TIME) | NONE/-=1398, UNPLACED/-=168 |
| r4 (round 1) | 武将 | 6917 |  | NONE/-=5916, UNPLACED/-=1000, DECIDED/P_STATE=1 |
| r4 (round 1) | 僧侶 | 439 |  | NONE/-=380, UNPLACED/-=57, DECIDED/PERSON=1, DECIDED/P_STATE=1 |
| r4 (round 1) | 網膜 | 0 |  |  |
| r5 (final) | 小説家 | 2212 | 0 (GROUP_ORG) | NONE/-=1838, UNPLACED/-=369, DECIDED/PERSON=4, DECIDED/PLANT=1 |
| r5 (final) | 僧 | 826 | 0 (GROUP_ORG) | NONE/-=640, UNPLACED/-=184, MULTIPLE/IDENTIFIER,PERSON=1, DECIDED/INFO_LANGUAGE=1 |
| r5 (final) | 大名 | 1566 | 0 (TIME) | NONE/-=1398, UNPLACED/-=168 |
| r5 (final) | 武将 | 6917 |  | NONE/-=5916, UNPLACED/-=1000, DECIDED/P_STATE=1 |
| r5 (final) | 僧侶 | 439 |  | NONE/-=380, UNPLACED/-=57, DECIDED/PERSON=1, DECIDED/P_STATE=1 |
| r5 (final) | 網膜 | 0 |  |  |
<!-- END table:hub_spread -->

段 B の donor が、段 A から「外した理由別」の合計より多く減るのは、外した donor を上位語に持っていた語が連鎖の中で型を渡されなくなり、その語がさらに別の語の donor ではなくなるため（連鎖の波及）。

<!-- BEGIN table:donor_stats -->
| placement | stage A donors (with seeds) | stage A non-seed | stage B donors | stage B non-seed | dropped: not DECIDED | dropped: contrary arm | donor_contra_min | stage seconds |
|---|---|---|---|---|---|---|---|---|
| r3c | 592435 | 592060 | 560419 | 560044 | 714 | 658 | 5 | stage_a_sec=99.8, stage_b_sec=97.3 |
| r4 | 592435 | 592060 | 560419 | 560044 | 714 | 658 | 5 | stage_a_sec=103.7, stage_b_sec=102.2 |
| r5 | 592435 | 592060 | 560419 | 560044 | 714 | 658 | 5 | stage_a_sec=100.1, stage_b_sec=99.7 |
<!-- END table:donor_stats -->

<!-- BEGIN table:donor_top -->
| donor (final placement r5) | type | heads typed through it | of those, heads with another met arm pointing elsewhere |
|---|---|---|---|
| 選手 | PERSON | 45728 | 0 |
| 学校 | GROUP_ORG | 27693 | 2 |
| 政治家 | PERSON | 23471 | 2 |
| 俳優 | PERSON | 16483 | 1 |
| 番組 | WORK | 14424 | 0 |
| 学者 | PERSON | 14412 | 1 |
| 駅 | PLACE | 14345 | 0 |
| 実業家 | PERSON | 14343 | 1 |
| 女優 | PERSON | 13296 | 0 |
| 映画 | WORK | 11997 | 21 |
| 作品 | WORK | 10440 | 4 |
| アルバム | WORK | 9646 | 8 |
| 作家 | PERSON | 8549 | 3 |
| 歌手 | PERSON | 8457 | 0 |
| 声優 | PERSON | 8131 | 0 |
<!-- END table:donor_top -->

### 11.2 証拠の足りない語の一覧

材料の見出し語のうち、状態が `UNPLACED` か `MULTIPLE` の語を、頻度 `n_seen`（jawiki と codex 8 系列で内容語として現れた回数の合計。順位を付けるためだけの合計で、型の票ではない）の降順に並べ、上位 60,000 語と同じ頻度の語は全部入れる（順序で切らない）。凍結した検査データは読まず、特別扱いもしない。重なりは選んだあとで数える（下の表）。

<!-- BEGIN table:needs_summary -->
| item | value |
|---|---|
| placement the list was taken from | /Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r3c/run1 (content_sha256 ce65b9c2081e...) |
| words listed (all words whose frequency is at least the boundary's) | 60,382 |
| requested n | 60,000 |
| boundary frequency (n_seen of the n-th word) | 68 |
| words at exactly the boundary frequency (all kept) | 663 |
| last frequency in the list | 68 |
| by state | MULTIPLE=2332, UNPLACED=58050 |
| by namespace | N=57587, NP=41, P=2754 |
| by evidence status | BELOW_THRESHOLD=35900, NO_EVIDENCE=22150, SPLIT=2332 |
| by origin of the headword | paren_alias=106, title=6721, token=53555 |
| file sha256 | a5fe23b9aef9f46449f0b16c4bbb0ce49d80b50afe38978d2bf99930071610af |
<!-- END table:needs_summary -->

<!-- BEGIN table:needs_overlap -->
| test file (counted AFTER the list was made) | terms in the file | words also in the list |
|---|---|---|
| dev_unknown | 65 | 0 |
| dev_vocab | 583 | 193 |
| predicate_check | 119 | 72 |
| typed_vocab | 1075 | 436 |
| unknown_words | 234 | 0 |
<!-- END table:needs_overlap -->

### 11.3 定義文の生成（`tools/gen_coarse_evidence.py`）

一覧を束（既定 40 語）にして `codex exec` に渡し、語ごとに定義文 1 文と上位語を JSON で返させる。台帳（追記専用）・再開・失敗の束の再試行（上限）・総呼び出し数の上限・並列スロット数（上限 12）を持ち、子プロセスの stdin は閉じる。`--codex-bin` は必須（既定値は持たない。テストが本物を呼ばないため）。**生成した文は、モデルが書いた文であって、材料の証言ではない**。出所（`generated`・モデル・effort・束の id・試行・出力ファイルの sha256）が全行に付く。

プロンプトの全文（検査データの語を例に使わない。例は置き場所だけ）:

<!-- BEGIN table:gen_prompt -->
```
あなたは日本語の辞書の編集者です。下の WORDS_JSON の各語について、辞書の見出しのような短い定義文を 1 文と、その語が何の一種かを表す上位語を 1 つ答えてください。

規則:
- definition は「<語>は<上位語>である。」または「<語>は<…>の一種である。」の形の 1 文にする。
- hypernym は名詞 1 つ（その語が何の一種か）。
- 語に複数の意味があるときは、いちばん一般的な意味を 1 つだけ選ぶ。
- 語として意味が分からない、断片で語にならない、綴りから何も判断できないものは、definition と hypernym の両方を null にする。無理に作らない。
- ファイルを読まない。コマンドを実行しない。ネットワークを使わない。道具を使わず、あなたの知識だけで答える。
- items は入力の語と同じ順で、語ごとに 1 件ずつ。word には入力の語をそのまま入れる。

WORDS_JSON: ["<語>", ...]
```

template sha256 (the fixed part): `ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65`
<!-- END table:gen_prompt -->

呼び出しの形:

<!-- BEGIN table:gen_argv -->
```
<codex> exec -m gpt-6-luna -c model_reasoning_effort="low" -c service_tier="priority" -s read-only --skip-git-repo-check --ephemeral --disable browser_use --disable computer_use --disable apps [-c <extra config> ...] -C <G>/work/empty --output-schema <G>/schema.json --json -o <G>/raw/<batch>.a<k>.last.json <prompt>
```
<!-- END table:gen_argv -->

実行の結果（`artifacts/w3-a/gen_summary.json`。台帳から数えた値）:

<!-- BEGIN table:gen_summary -->
| item | value |
|---|---|
| batch_size | 40 |
| batches_failed | 0 |
| batches_ok | 1510 |
| batches_total | 1510 |
| calls | 1510 |
| calls_per_word_answered | 0.02501 |
| calls_per_word_requested | 0.02501 |
| effort | low |
| end_status | {"ok": 1510} |
| failure_reasons | {} |
| ledger_sha256 | 42de32b510ae3bf1a4fe09f0756aac70f126f1480c45413a2064bdc321ab7910 |
| max_calls | 2000 |
| max_retries | 2 |
| model | gpt-6-luna |
| not_run_cap | 0 |
| not_run_other | 0 |
| ok_rate | 1.0 |
| prompt_template_sha256 | ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65 |
| slots | 12 |
| sum_call_sec | 47145.6 |
| wall_sec | 3995.4 |
| words_abstained | 5371 |
| words_answered | 60382 |
| words_dup_dropped | 0 |
| words_foreign_dropped | 0 |
| words_missing | 0 |
| words_requested | 60382 |
<!-- END table:gen_summary -->

### 11.4 生成した証拠の配置での扱い

- 生成した定義文は、Wikipedia のリードと同じ規則（`hypernym_phrases`、取れなければ `first_clause_phrases`）で読み、取れた句と生成の `hypernym` の欄の句を、段 B の donor の表で型に通す（異なる句ごとに 1 件）。これは新しい腕 `gen_definition`（出所 `generated:<モデル>:<effort>`）で、既存の `definition` の腕とは別に数える。
- **決め方**（`coarse_types.decide_word` の 1 か所）: (1) 生成の腕を除いて判定する。(2) それが DECIDED／MULTIPLE ならそれが最終（直接）。生成の腕は証拠として見せるだけ（`why=GENERATED_NOT_DECIDING`）。**生成は同点・複数候補を解消しない**。(3) UNPLACED で、生成の腕の最上位が 1 つの型 T のとき: 生成でない腕のうち自分の閾値を満たした（`ROLE_SINGLE_SOURCE` で外された役割の腕を含む）腕の最上位がちょうど [T] のものがあれば、**直接へ格上げ**（`gen_upgrade_on_agreement`。dev の根拠は DECISIONS §5-7・§5-9）。なければ **推定（生成）**: `origin=estimated`・`estimate_basis=generated`・`constructed=true`・`neighbors` に `via=generated:<束の id>`。(4) 生成の腕で型が割れたら決めない（`why=GENERATED_SPLIT`）。名詞の名前空間でない語（述語・NP）には生成の名詞の型を付けない。
- **生成の影響を推定（近さ）に持ち込まない**: 生成の腕が決め手に入った語は、**推定（生成）も、直接へ格上げした語も**、連鎖の donor・文脈の表の donor・単位の族（`unit_kin`・`unit_sample`）・問い合わせ時の主要部の継承（`_estimate` の head の段）に使わない。head の段は `origin=direct` で、かつ `decided_by` に `gen_definition` が無い語だけを見る。単位の族は、決め手に `gen_definition` を含まない直接の語だけから作る（第 1 ラウンドは格上げした語を入れており、レビューの指摘 M1 で直した。DECISIONS §6-0）。
- 除外語（`--exclude-terms`）を語か定義文に含む生成の行は捨て、件数を manifest に出す。配置の表 `generated`（語・モデル・effort・束の id・試行・定義文・上位語・読んだ句と型）に出所が残り、`content_sha256` と `verify` に入る。

<!-- BEGIN table:build_generated -->
| item | value |
|---|---|
| batches_failed | 0 |
| batches_ok | 1510 |
| calls | 1510 |
| dropped_by_reason | {"abstained": 5371, "dup_word": 0, "excluded_term": 0, "no_type": 32833, "not_in_material": 0, "ns_not_noun": 2741} |
| effort | low |
| ledger_path | /Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/generated/ledger.jsonl |
| ledger_sha256 | 42de32b510ae3bf1a4fe09f0756aac70f126f1480c45413a2064bdc321ab7910 |
| lines | 60382 |
| model | gpt-6-luna |
| models | ["gpt-6-luna:low"] |
| outcomes | {"base_decided_generated_ignored": 1111, "decided_direct_upgrade": 2557, "decided_estimated_generated": 15697, "tie": 72} |
| path | /Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/generated/definitions.jsonl |
| read_sec | 2.8 |
| rows_read | 55011 |
| sha256 | 248ca1a4b03f6ffd514458cba3975cbbc3392559aca3434be2fdd0e7ea0a8729 |
| used | 19437 |
<!-- END table:build_generated -->

### 11.5 W3-a と並べた結果

凍結した検査データ・同じ手順で測り直した。上がった項目も下がった項目も全部載せる。「承認の条件」の列は、誤決定率などが W3-a の件数より悪化していないこと。目標（85% など）に届かない項目は未達のままで、承認の条件ではない。

<!-- BEGIN table:p5_compare -->
| item | target | W3-a (r2b) | W3-a2 F1-F6 only (r3c) | W3-a2 final (r5) | W3-a2 round 1 (r4, before the review) | not worse than W3-a (approval condition) |
|---|---|---|---|---|---|---|
| L1 coverage (tokens) | at least 90.0% | 15498 / 21774 = 71.2% | 15445 / 21774 = 70.9% (-53, worse) | 17217 / 21774 = 79.1% (+1719, better) | 17223 / 21774 = 79.1% (+1725, better) | - |
| L2 correct (direct) | at least 85.0% | 537 / 1072 = 50.1% | 540 / 1072 = 50.4% (+3, better) | 567 / 1072 = 52.9% (+30, better) | 567 / 1072 = 52.9% (+30, better) | - |
| L2 wrong (direct) | at most 8.0% | 59 / 1072 = 5.5% | 47 / 1072 = 4.4% (-12, better) | 47 / 1072 = 4.4% (-12, better) | 47 / 1072 = 4.4% (-12, better) | PASS |
| L2 trap wrong (direct) | at most 5.0% | 9 / 154 = 5.8% | 7 / 154 = 4.5% (-2, better) | 7 / 154 = 4.5% (-2, better) | 7 / 154 = 4.5% (-2, better) | PASS |
| L3 correct | at least 65.0% | 89 / 174 = 51.1% | 86 / 174 = 49.4% (-3, worse) | 86 / 174 = 49.4% (-3, worse) | 88 / 174 = 50.6% (-1, worse) | - |
| L3 wrong | at most 15.0% | 9 / 174 = 5.2% | 9 / 174 = 5.2% (+0, same) | 9 / 174 = 5.2% (+0, same) | 8 / 174 = 4.6% (-1, better) | PASS |
| L3 returns a type for an unknown word | at most 20.0% | 11 / 60 = 18.3% | 9 / 60 = 15.0% (-2, better) | 9 / 60 = 15.0% (-2, better) | 9 / 60 = 15.0% (-2, better) | PASS |
<!-- END table:p5_compare -->

非直接の答えの内訳（推定（生成）と推定（近さ）を分けた）:

<!-- BEGIN table:l2_by_basis -->
| non-direct answers of the frozen typed vocabulary: estimate basis / outcome | words |
|---|---|
| generated/correct | 107 |
| generated/wrong_single | 13 |
| proximity/correct | 38 |
| proximity/wrong_single | 13 |
| (none / other: no type returned or several types) | 162 |
<!-- END table:l2_by_basis -->

<!-- BEGIN table:l1_by_basis -->
| how the token was answered (basis; direct = a testimony of the material) | tokens | of which a type was returned |
|---|---|---|
| direct | 14832 | 14832 |
| generated | 1644 | 1644 |
| none | 4557 | 0 |
| proximity | 741 | 741 |
<!-- END table:l1_by_basis -->

正解の型が証拠の表のどこかに現れる語の割合（上限。報告用）:

<!-- BEGIN table:upper_bound -->
| measure (report only) | words of 1072 | rate |
|---|---|---|
| gold type appears somewhere in the evidence table, generated arm included | 870 | 81.2% |
| same, generated arm not counted | 836 | 78.0% |
<!-- END table:upper_bound -->

### 11.6 問い合わせの契約（読解器のため）

`python -m verantyx.coarse_place --term <語> [--context-role <助詞>] [--context-predicate <述語>] [--placement <dir>]`、または `verantyx.coarse_place.query(term, context_role=…, context_predicate=…, placement=…)`。答えは 1 つの JSON で、読解器が見るのは次のキー。

| キー | 値 | 意味 |
|---|---|---|
| `state` | `DECIDED` | 型がちょうど 1 つ（`top` の長さが 1） |
| | `MULTIPLE` | 証拠が割れた。型の集合を並べて返す（順序は表示のための辞書順で、優劣ではない）。同点は棄権 |
| | `UNPLACED` | 材料に出てくる語だが、決める証拠が足りない（`top` は空）。「材料にある」ことは分かる |
| | `UNKNOWN` | 材料に無く、近さからも何も作れない（`top` は空）。「分からない」であって「偽」でも「無い」でもない |
| | `NO_PLACEMENT` | 配置が使えない。`placement.reason` が `UNSET`／`MISSING`／`UNREADABLE`／`MANIFEST_MISMATCH` の 4 種。0 件の配置は `UNKNOWN` を返す（`NO_PLACEMENT` ではない） |
| `top` | 型 id の集合 | 返す型の候補（名詞 17・述語 13 の id） |
| `candidates` | 型ごとの配列 | 候補の型と、それを支えた腕ごとの件数（`axes` の `counts`） |
| `axes.<腕>` | `counts`・`top`・`met`・`threshold_met`・`why`・`generated` | 証拠の腕ごとの件数（足し合わせない）。`met` = 決定に加わった腕。`generated` = codex コーパス由来の腕（役割の分布など。**直接の証拠**）。生成した定義文の腕は `axes["gen_definition"]` で、`provenance`（モデル・effort・束の id）が付く |
| `origin` | `direct` | **直接**: 語そのものの証拠（種・表記・定義・別名・役割の分布…。Wikipedia の定義や役割の分布と、一致した生成の定義を含む）。`estimate_basis` は null |
| | `estimated` | **推定（構成）**: 証言ではなく構成物。`constructed=true`、`neighbors` が空でない |
| `estimate_basis` | `null` / `proximity` / `generated` | 推定の種類。`proximity` = **推定（近さ）**（語の形の主要部・単位の族・その場の役割の位置）。`generated` = **推定（生成）**（モデルが書いた定義文だけで決まった） |
| `neighbors` | `[{word, type, via}]` | 推定が何に基づくか。`via` は `head:…`／`kin:…`／`context:…`／`generated:<束の id>` |
| `decided_by` | 腕の名前の配列 | 直接の答えで、決定に加わった腕 |

「生成」は 2 つあり、混ぜない: (1) **codex コーパス由来の腕**（`axes[*].generated=true`。生成コーパスの役割の分布など）は従来どおり **直接の証拠**。(2) **生成した定義文**（`gen_definition`）だけで決まったものが **推定（生成）**。生成した定義文が、Wikipedia の定義や、自分の閾値を満たした別の種類の腕と一致したときだけ「直接」に格上げされる（そのとき `decided_by` に両方が入る）。**格上げした直接の語（`decided_by` に `gen_definition` を含む `origin=direct`）は、この配置の中では推定（近さ）の材料（主要部・単位の族）に使われない**。読解器側でも、`decided_by` に `gen_definition` を含む直接の語は、含まない直接の語（Wikipedia の定義・役割の分布だけで決まった語）と分けて扱う余地がある（提案）。

不変条件（テストで確かめている）: `state==DECIDED` ⇔ `len(top)==1`、`MULTIPLE` ⇔ 2 以上、`UNPLACED`／`UNKNOWN`／`NO_PLACEMENT` ⇔ 空。`origin==estimated` ⇔ `constructed` ⇔ `estimate_basis` が `proximity` か `generated`。`origin==estimated` なら `neighbors` は空でない。`origin==direct` なら `estimate_basis` は null。

**読解器への提案**（読解器側は別チケット。ここでは線を提案するだけ）: 読解器は **`origin==direct` かつ `state==DECIDED` の型だけ** を役割の決定に使う。**推定（近さ）・推定（生成）は、同点の解消には使わない**（表示と候補の提示だけに使う）。`MULTIPLE`・`UNPLACED`・`UNKNOWN`・`NO_PLACEMENT` は、それぞれ別の型のまま棄権として扱い、「型が無い」を「型が合わない」と混ぜない。

（W5-b で追記）**表記の契約**: 問い合わせは NFKC だけ正規化し（全角／半角・互換文字は同じ語）、表記の判定・見出し語・証拠・推定のすべての検索にその 1 つの形を使う（出力の `term` は呼び手の文字列を strip したもの）。**ひらがなとカタカナは別の語**（読みの正規化はしない）で、`state` `top` `candidates` は問い合わせた表記の証拠だけで決まる。答えに鍵 `spelling` を足した（既存の鍵は変えていない）:
`{"query": <strip 後の入力>, "normalized": <NFKC 形>, "normalization": "NFKC", "kana": "DISTINCT", "kana_variant": null | {"term", "state", "top", "origin"}, "why": null | "KANA_VARIANT_DIFFERS"}`。
`kana_variant` は、ひらがなとカタカナを入れ替えた表記（コードポイントの差 0x60）の **見出し語の行だけ**（推定はしない。行が無ければ null）。`why` は、その行が `DECIDED`／`MULTIPLE` で `(state, top)` が答えと違うときだけ `KANA_VARIANT_DIFFERS`。**`spelling` は `state` `top` `candidates` に一切影響しない**（`NO_PLACEMENT` の答えにも付く）。詳細と測定は §11.9。

（W5-b 第 4 ラウンドで一部撤回: §11.9.3、監査役の裁定 C1。上の「`spelling` は `state` `top` `candidates` に一切影響しない」「推定はしない」「不変条件の `estimate_basis` は `proximity` か `generated`」は、**問うた表記が `UNPLACED`／`UNKNOWN` で、仮名が 1 つの文字体系だけで、もう一方の表記が `DECIDED` かつ `direct` のときに限り** 変わった。そのとき答えは `origin: estimated`・`estimate_basis: kana_variant`・`constructed: true` で、`spelling.why` は `ESTIMATED_FROM_KANA_VARIANT:<もう一方の表記>`。それ以外（自分の答えを持つ表記・`MULTIPLE` や `estimated` の変種・仮名が混ざった表記・`NO_PLACEMENT`）は上の記述のまま。）

**W3-a3 の追記（述語の `frame`・`frame_status`・`generated_frame`）**: すべての答えの最後に `frame_status`（閉じた 7 値）と `frame`（助詞 → 名詞の型。確認できた述語だけ、ほかは null）が付く。直接の答えには `generated_frame`、確認済みの枠には `frame_unconfirmed` も付く。意味・不変条件・閉じた一覧・述語の型が `direct` になる条件は **§12（特に §12.10）を見よ**。既存のキーの値と順は変えていない。

（W3-b5 追記 2026-10-04 06:10:50 +0900）**問い合わせの新しい鍵 `frame_generated`**（常に出す。`frame` とは独立）: 値は `null` か `{"origin": "generated", "constructed": true, "ptype": <生成の枠の表の ptype>, "frame": <生成の枠の表の frame をそのまま。{助詞: [型…]}>, "provenance": {"model", "effort", "batch_id", "attempt"}}`。引く語は答えの `spelling.normalized`（配置を引いた NFKC の形）。`null` になるのは、配置が開けない（`NO_PLACEMENT`）・配置に `generated_frames` 表が無い・表にその語の行が無いとき。置き場所は W3-a3 の末尾の鍵（`generated_frame`・`frame_status`・`frame`・`frame_unconfirmed`・`frame_disagreement` のうち答えにあるもの）の最初の鍵の直前（`spelling` の後ろ）。既存の鍵の値と順は変わらない（`frame_generated` を除いた答えは基点と byte 一致。r7・r8 の全語でテストする）。`frame`（CONFIRMED のときだけ）・`frame_status`・`frame_unconfirmed` の意味と値は変わらない。不変条件: `frame_generated` が null でないなら `origin == "generated"`・`constructed == true`・`frame` の鍵は格助詞 9 種・値は 17 型の文字列の並び。生成の枠は構成物であって証拠でない。読解器はこれを `frame_required` の行の許可（読んでよいか）にだけ使い、型の決定や同点の解消には使わない（docs/READING_SOUNDNESS.md §10F K200〜K203）。（W3-b5 追記 2026-10-04 07:39:33 +0900: 第 2 ラウンドの表の変更 2 の後、`frame_required` の行は 0 行で、読解器はこの鍵を使って読む文を 1 文も持たない。鍵は契約として残る。）

### 11.7 既知の穴

- 生成した定義文の精度は、凍結した検査データでは「推定（生成）」の語の正答・誤決定の件数（第 11.5 節の表）でしか分からない。検査データに無い語の精度は測っていない。
- 一覧は頻度だけで選ぶため、機能語に近い名詞（こと・ため など）や述語も含む。モデルが `null` で答えた語は棄権として数える。
- F1 の止め方は、連鎖から正しい型を渡せていた語（定義が割れた語を上位語に持つ記事など）も未配置にする。その代わりに誤った型の広がりは止まる（第 11.1 節の表）。
- `definition_recovered` を決め手にする判断は dev の小さい標本（決め手がこの腕だけの語）に基づく。
- 標本の外の設定（`donor_contra_min` など）は dev の 1 つの配置で選んだ。
- 欧文の単位の規則（第 11.8 節）は、dev ではなく抽出段の表の中身（私とレビューが挙げた実在の単位と非単位の小さい集合）で選んだ。`mm`（出所 `codex:code_qa` では日付の書式としても出る）と `em` は表に残らない。事前に書いた候補の格子に後から `K=6` を足した（DECISIONS §6-2）。
- 時の単位を頭に持つ 2 形態素の単位（`年後`・`日前`・`世紀末` など）が表に入り、`3年後` が数量になる（W3-a から続く既存の問題で、今回は直していない）。
  **（W5-b で直した: §11.9。`3年後` は `TIME`。この項目は直す前の記録として残す。）**
- 「正解の型が証拠の表のどこかに現れる語の割合」は、`evidence` 表の `ns_vote` 以外の全行（閾値に届かない票・役割の腕を含む）を数えたもの。中間職の数え方（W3-a のレビューの集計）とは違い、同じ数字にはならない。

### 11.8 第 2 ラウンド（レビュー r1 の必須の修正 M1・M2）

どちらも見出し語の状態（`headwords`）を変えないので、一覧と生成物（`definitions.jsonl`・台帳）は作り直さず、codex の追加呼び出しは 0 回。配置は `full/r5/run1`・`run2`（cache なし。生成あり）。第 1 ラウンドの `full/r4` は比較のために残してある。

**M1（格上げした語が推定（近さ）の材料に入っていた）**: 決め手に `gen_definition` を含む語は、直接でも、問い合わせの head の段と単位の族に使わない（第 11.4 節）。合成の配置のテスト（`test_coarse_place_generated.py` の `upgraded`）が、修正を外すと落ちることを確かめた（`artifacts/w3-a/m1_test_without_fix.txt`）。最終の配置での確認:

<!-- BEGIN table:m1_m2_check -->
| check on the final placement (m1_m2_check.py) | value |
|---|---|
| unit_sample rows | 295,893 |
| ... of which list a word decided with gen_definition (M1, must be 0) | 0 |
| words decided with gen_definition | 18,254 |
| ... of which upgraded to direct | 2,557 |
| compounds '<prefix><generated word>' whose estimate used the head stage on that word (M1, must be 0) | 0 |
| control: plain direct words (a sample) whose compound used the head stage on that word | 2907 of 3000 |
| Latin-script units in the counters table (M2) | 5: GHz, MiB, kg, km, ms |
| all counter units | 140 |
| unknown-word file (234 words): answers (top, origin) that differ from the F1-F6-only placement r3c | 0 |
<!-- END table:m1_m2_check -->

**M2（欧文の非単位が助数詞の表に入り、`4xx`・`5xx` が数量になった）**: 欧文の単位（全文字が ASCII）に **構造の規則** を足した。語の一覧は書かない。
1. 1 形態素の表だけから採る（2 形態素の表の欧文は採らない）。
2. その出所で、算用数字の直後に出た回数が、名詞として出た回数（大文字小文字を区別せず足す）の `counter_latin_share_pct`% 以上（`of`・`and`・`for`・`in`・`is` のように、数字の後は一部でしかない語を外す）。
3. その出所で、直前の数字が `counter_latin_numerals_min` 種類以上（`4xx`・`5xx` のように、ごく少数の数字にしか付かない語を外す）。抽出段に欧文の単位ごとの数字の集合 `counter_nums`（32 で打ち切り）を足した。
4. 出所ごとに 1 票で、出所をまたいで足さない（`counter_min`・`counter_min_sources` は今までどおり）。数字の集合が測られていない抽出段（古い cache・合成の `ex`）には適用しない（「測っていない」を「偽」にしない）。

設定（`counter_latin_share_pct`・`counter_latin_numerals_min`）は、dev を測る前に書いた規則（DECISIONS §6-1）で、抽出段の表だけを見て格子から選んだ。**規則からの逸脱**: 9 通りの格子（`artifacts/w3-a/latin_units_grid_prereg9.txt`）の結果は、実在の単位 `GHz` を失う `K=12` だった。表を見たあとに `K=6` を格子に足して同じ選び方で選び直した（DECISIONS §6-2。凍結データには欧文の単位の数量の語が無い）。全格子と per-source の値:

<!-- BEGIN table:latin_units_grid -->
| rule (per source; DECISIONS 6-1/6-2) | score (Q kept - N kept) | Latin units | the units | Q (real units) kept | N (non-units) kept |
|---|---|---|---|---|---|
| no rule (round 1) | - | 18 | AND, GHz, MiB, URL, and, app, em, for, has, in, is, kg, km, mm, ms, of, sum, xx | - | - |
| share >= 10%, numerals >= 5 | 4 | 6 | GHz, MiB, kg, km, ms, xx | km, kg, GHz, ms, MiB | xx |
| share >= 10%, numerals >= 6 | 5 | 5 | GHz, MiB, kg, km, ms | km, kg, GHz, ms, MiB | - |
| share >= 10%, numerals >= 8 | 4 | 4 | MiB, kg, km, ms | km, kg, ms, MiB | - |
| share >= 10%, numerals >= 12 | 4 | 4 | MiB, kg, km, ms | km, kg, ms, MiB | - |
| share >= 20%, numerals >= 5 | 3 | 5 | GHz, MiB, kg, km, xx | km, kg, GHz, MiB | xx |
| share >= 20%, numerals >= 6 | 4 | 4 | GHz, MiB, kg, km | km, kg, GHz, MiB | - |
| share >= 20%, numerals >= 8 | 3 | 3 | MiB, kg, km | km, kg, MiB | - |
| share >= 20%, numerals >= 12 | 3 | 3 | MiB, kg, km | km, kg, MiB | - |
| share >= 33%, numerals >= 5 | 3 | 5 | GHz, MiB, kg, km, xx | km, kg, GHz, MiB | xx |
| share >= 33%, numerals >= 6 | 4 | 4 | GHz, MiB, kg, km | km, kg, GHz, MiB | - |
| share >= 33%, numerals >= 8 | 3 | 3 | MiB, kg, km | km, kg, MiB | - |
| share >= 33%, numerals >= 12 | 3 | 3 | MiB, kg, km | km, kg, MiB | - |
<!-- END table:latin_units_grid -->

<!-- BEGIN table:latin_units_per_source -->
| unit | per source (counter_min=80 passed): after-numeral count / noun occurrences (no case) / distinct numerals (capped at 32) |
|---|---|
| AND | codex:code: 132 after a numeral / 4720 as a noun / 28 numerals; codex:code_qa: 130 after a numeral / 2260 as a noun / 23 numerals |
| GHz | codex:general_qa: 270 after a numeral / 5 as a noun / 6 numerals; jawiki: 80 after a numeral / 14 as a noun / 24 numerals |
| MiB | codex:code: 170 after a numeral / 104 as a noun / 21 numerals; codex:code_qa: 424 after a numeral / 156 as a noun / 12 numerals |
| URL | codex:code: 83 after a numeral / 17660 as a noun / 13 numerals; codex:code_qa: 131 after a numeral / 34018 as a noun / 7 numerals |
| and | codex:code: 181 after a numeral / 4720 as a noun / 15 numerals; codex:code_qa: 112 after a numeral / 2260 as a noun / 19 numerals |
| app | codex:code: 1633 after a numeral / 12760 as a noun / 32 numerals; codex:code_qa: 458 after a numeral / 9639 as a noun / 13 numerals |
| em | codex:code: 638 after a numeral / 641 as a noun / 1 numerals; jawiki: 531 after a numeral / 101 as a noun / 10 numerals |
| for | codex:code: 132 after a numeral / 20199 as a noun / 16 numerals; codex:code_qa: 120 after a numeral / 12075 as a noun / 14 numerals |
| has | codex:code: 350 after a numeral / 6058 as a noun / 10 numerals; codex:code_qa: 150 after a numeral / 3315 as a noun / 6 numerals |
| in | codex:code: 100 after a numeral / 20366 as a noun / 32 numerals; jawiki: 162 after a numeral / 5084 as a noun / 32 numerals |
| is | codex:code: 407 after a numeral / 29694 as a noun / 32 numerals; codex:code_qa: 88 after a numeral / 15923 as a noun / 11 numerals |
| kg | codex:code_qa: 105 after a numeral / 100 as a noun / 30 numerals; jawiki: 8238 after a numeral / 4579 as a noun / 32 numerals |
| km | codex:code_qa: 211 after a numeral / 289 as a noun / 32 numerals; jawiki: 12742 after a numeral / 5649 as a noun / 32 numerals |
| mm | codex:code_qa: 81 after a numeral / 7037 as a noun / 32 numerals; jawiki: 2402 after a numeral / 725 as a noun / 32 numerals |
| ms | codex:code: 111 after a numeral / 1075 as a noun / 22 numerals; codex:code_qa: 295 after a numeral / 740 as a noun / 32 numerals |
| of | codex:code: 607 after a numeral / 32306 as a noun / 14 numerals; codex:code_qa: 118 after a numeral / 11328 as a noun / 8 numerals |
| sum | codex:code: 168 after a numeral / 2891 as a noun / 1 numerals; codex:code_qa: 106 after a numeral / 11834 as a noun / 5 numerals |
| xx | codex:code: 840 after a numeral / 78 as a noun / 5 numerals; codex:code_qa: 966 after a numeral / 100 as a noun / 9 numerals |
<!-- END table:latin_units_per_source -->

最終の配置での問い合わせ（レビューの確かめの語。`2in` は報告だけ）:

<!-- BEGIN table:m2_queries -->
| query | state | top | rule | expected |
|---|---|---|---|---|
| 10ms | DECIDED | QUANTITY | number+counter | QUANTITY |
| 10メートル | DECIDED | QUANTITY | number+counter | QUANTITY |
| 128MiB | DECIDED | QUANTITY | number+counter | QUANTITY |
| 1of | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
| 2in | DECIDED | IDENTIFIER | alnum_code | (only reported) |
| 2km | DECIDED | QUANTITY | number+counter | QUANTITY |
| 30パーセント | DECIDED | QUANTITY | number+counter | QUANTITY |
| 3AND | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
| 3kg | DECIDED | QUANTITY | number+counter | QUANTITY |
| 40キロメートル | DECIDED | QUANTITY | number+counter | QUANTITY |
| 4xx | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
| 5GHz | DECIDED | QUANTITY | number+counter | QUANTITY |
| 5xx | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
| A1-23 | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
| ABC-123 | DECIDED | IDENTIFIER | alnum_code | IDENTIFIER |
<!-- END table:m2_queries -->

### 11.9 W5-b: 攻撃の第 2 波（W3-a2 の A1・A2・B1）

攻撃役の反例（`tests/attack/test_attack_w3a2_contract.py`。原本の写しで中身は変えていない）と、それへの直し。配置の実体は作り直していない（`tools/build_coarse_placement.py` は変えていない。配置は `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1`）。

#### 11.9.1 契約（§11.6 の追記と同じ。実装と一致させた）

- **A1（全角／半角）**: 以前は生の表記を先に引き、無いときだけ NFKC 形を引いた。生の表記の見出し語が「未配置」で NFKC 形が「決定」のとき、前者が後者を遮った（`ＮＰＯ` は `UNPLACED`、`NPO` は `DECIDED`）。今は NFKC 形だけを引く。
- **A2（かな）**: **ひらがなとカタカナは別の語**と決めた（監査役の推奨）。両表記を束ねる案は、凍結の L2 で誤った単一の型を増やすことを実測したので採らない: 非直接の 8 語のうち、別のかな表記の型を借りると `ロケット→WORK`・`モネ→WORK`（正解は `ARTIFACT`・`PERSON`）、`トキ`（今は正解の `ANIMAL`）は別表記 `とき` が 3 型（中間職の測定 `kana_variant_effect.txt`）。そこで `state` は問い合わせた表記の証拠だけで決め、もう一方の表記の見出し語の行を `spelling.kana_variant` で **見せるだけ**にした。
  攻撃テスト `test_hiragana_katakana_variant_keeps_same_state`（`あざみ` と `アザミ` の `state` が等しいことを要求する）は、この契約のもとで **通らない**（`あざみ` は `UNPLACED`、`アザミ` は `DECIDED ['PLANT']` のまま）。**宣言（衝突 C1）**: チケットの「攻撃テストが通る」とチケットの推奨「かな違いは別語」は両立しない。テストには触れていない。契約を固定する試験は `tests/coarse_place/test_coarse_place_w5b.py` の `test_contract_kana_distinct_*`。
  `あざみ` の `spelling.why` は `KANA_VARIANT_DIFFERS`（`アザミ` の行が `DECIDED ['PLANT']` で、答えの `UNPLACED` と違う）。
- **B1（`3年後`）**: `coarse_types.notation_type` の、学習した助数詞の分岐（算用数字で始まる数＋`counters` にある単位）で、単位が `TIME_UNITS` のどれかで **始まり**、それより長いとき（最長一致）は `QUANTITY` でなく `("TIME", "number+time_unit_head")`。構造の規則で、語の一覧は足していない（`TIME_UNITS` と学習した `counters` だけ）。
  **学習した助数詞でない単位には広げない**（`3分の1` は配置の直接の答え `QUANTITY` のまま）。**漢数字には広げない**（今の助数詞の分岐と同じ制限。`千日前`（地名）を `TIME` にしないため）。この規則に当たる単位は r5 の配置の `counters` 表（140 個）のうち 21 個（`artifacts/w5-b/time_head_counters.txt` が表から機械で数えた出力）。

#### 11.9.2 測定（出典: `artifacts/w5-b/`）

- 凍結の配置のデータ L1・L2・L3 の `items.jsonl` は、変更の前後で **バイト単位で同じ**（`coarse_items_cmp.txt`: 3 行とも `same`）。要約も同じ: L1 `token_cover_rate 0.7907`、L2 `correct_rate 0.5289 / wrong_single_rate 0.0438 / trap 0.0455`、L3 `correct_rate 0.4943 / wrong_rate 0.0517 / returned_type_rate 0.15`（`coarse_before_l*.txt` と `coarse_after_l*.txt`）。
- 問い合わせの前後（`coarse_probe_before.txt` と `coarse_probe_after.txt`、道具 `scripts/coarse_probe_queries.py`）: `3年後` `5日前` `21世紀末` `３年後` `10分後` `2週間後` `3か月後` `10秒ごと` `7日目` `3日分` は `QUANTITY` → `TIME`（規則 `number+time_unit_head`）。`ＮＰＯ` は `UNPLACED` → `DECIDED ['GROUP_ORG']`（`NPO` と同じ）。`千日前` は `UNPLACED` のまま、`3分の1` `10メートル` `10ms` は `QUANTITY` のまま。
- **残る穴**: `三年後`（漢数字）は今も推定（近さ）で `WORK` になる（`coarse_probe_after.txt`）。このチケットでは直していない（漢数字に広げると `千日前` のような地名を巻き込む）。`2年生` も、`年生` が学習した助数詞でないので推定（近さ）で `WORK`。
- 試験: `tests/coarse_place/test_coarse_place_w5b.py`（28 本）。
- （第 2 ラウンドで追記）**規則の当たる 21 単位（`time_head_counters.txt`）のうち、`日分`・`年ごと`・`時間制` は「時点」より「量・頻度・制度」に近い意味を持つ**。規則は構造（1 形態素目が時の単位で、学習した助数詞である）だけを見るので、これらも `TIME` を返す。型の規則として一貫しているが、意味の細かい区別（時点・期間・頻度）はこの層の型（`TIME`）では表さない。区別が要る使い手は、返った単位の語から自分で判断する（この層は区別を作らない）。

#### 11.9.3 第 4 ラウンド（監査役の裁定 C1、2026-10-03）: かな違いは別語のまま、変種の型は **推定（`kana_variant`）** として返す

**裁定の要約**: かな違いは別語のまま（§11.9.1 A2 の決定を維持）。ただし問い合わせた表記が `UNPLACED`／`UNKNOWN` で、ひらがな⇄カタカナの変種が `DECIDED` かつ `direct` なら、その型を直接ではなく **`origin: estimated`・`estimate_basis: kana_variant`** として返し、`why` に変種の表記を出す。攻撃テスト `test_hiragana_katakana_variant_keeps_same_state` は「同じ state」ではなく「変種の型が推定（kana_variant）として得られる」を assert する形に **改訂**する（攻撃役の期待は文書の読みの一つで、契約はこちら）。

**規則**（`coarse_place.query` の最後、`_answer` の後、`spelling` を作る前。`_borrow_kana_variant`）:
- 問うた表記の答えの `state` が `UNPLACED` か `UNKNOWN` のときだけ。`DECIDED`／`MULTIPLE`（直接・近さの推定・生成の推定のどれでも）は自分の答えを持つので借りない。`NO_PLACEMENT` も借りない。
- 仮名が 1 つの文字体系だけ（ひらがなだけ、またはカタカナだけ。`ー`・漢字・数字・英字は問わない）の表記だけ。ひらがなとカタカナが混ざった表記を入れ替えても同じ語の別表記にならないので借りない（指示書 D-r4-2。裁定より狭い側）。
- 変種の見出し語の行が `DECIDED` かつ `direct` のときだけ。`MULTIPLE` の変種・`estimated` の変種は借りない。
- 借りた答え: `state DECIDED`、`origin estimated`、`estimate_basis kana_variant`、`constructed true`、`top` は変種の型、`namespace` は変種の行のもの、`candidates [{"type": t, "axes": {"kana_variant": 1}}]`、`axes` に `kana_variant: {term, state, top, origin}` を足す、`neighbors [{"word": 変種, "type": t, "via": "kana_variant:<変種>"}]`、`seen_in_material` は問うた表記のもの。`decided_by` は付けない（ほかの推定の答えと同じ）。`spelling.why` は `ESTIMATED_FROM_KANA_VARIANT:<変種>`（借りないときは今までどおり `KANA_VARIANT_DIFFERS` か null）。
- 語の一覧は足していない（変種は問い合わせた表記から機械的に決まる）。配置の実体は作り直していない。

**攻撃テストの改訂（変更前と変更後の関数の全文）**。変更前（攻撃役の原本 `attacks/W3-a2/test_attack_contract.py`）:

```python
def test_hiragana_katakana_variant_keeps_same_state():
    hiragana = ask("あざみ")
    katakana = ask("アザミ")
    assert hiragana["state"] == katakana["state"], (
        f"kana spelling variants changed state: あざみ={hiragana['state']} "
        f"{hiragana['top']}, アザミ={katakana['state']} {katakana['top']}"
    )
```

変更後（`tests/attack/test_attack_w3a2_contract.py`。先頭の出典コメントも 1 行書き換えた。ほかの 2 本は 1 バイトも変えていない）:

```python
def test_hiragana_katakana_variant_keeps_same_state():
    hiragana = ask("あざみ")
    katakana = ask("アザミ")
    # W5-b round 4 (auditor ruling C1, 2026-10-03): the two kana spellings stay two words; an UNPLACED / UNKNOWN spelling whose other
    # kana spelling is DECIDED and direct gets that type as an ESTIMATE (estimate_basis kana_variant), never as a direct answer.
    assert (katakana["state"], katakana["origin"]) == ("DECIDED", "direct"), katakana
    assert (hiragana["state"], hiragana["top"]) == (katakana["state"], katakana["top"]), (hiragana["state"], hiragana["top"])
    assert (hiragana["origin"], hiragana["estimate_basis"], hiragana["constructed"]) == ("estimated", "kana_variant", True)
    assert hiragana["spelling"]["why"] == "ESTIMATED_FROM_KANA_VARIANT:アザミ"
```

**測定の前後**（凍結データの L1・L2・L3。コマンド `scripts/measure_coarse_w5b.py <木> artifacts/w5-b/coarse_after_r4 l1|l2|l3 --placement <r5 run1>`。出力 `artifacts/w5-b/coarse_after_r4_l1.txt` `_l2.txt` `_l3.txt` と `coarse_after_r4/`、第 3 ラウンドとの行ごとの差 `coarse_items_r3_vs_r4.txt`）:
- **L2（型つきの語彙 1,072 語）**: 事前登録の主指標は不変（`correct_rate 0.5289`・`wrong_single_rate 0.0438`・`trap_wrong_single_rate 0.0455`）。非直接の内訳は `estimated/wrong_single 26 → 28`・`None/other 162 → 160`・`estimated/correct 145 → 145`。変わった行はちょうど 2 つ: `ロケット`（V0405、正解 `ARTIFACT`、`UNPLACED` → `DECIDED`・`estimated`・`kana_variant`・`WORK`。`ろけっと` の型を借りた）と `モネ`（V0627、正解 `PERSON`、`UNPLACED` → `WORK`。`もね` の型を借りた）。どちらも印は付いている（`origin estimated`・`estimate_basis kana_variant`・`neighbors kana_variant:…`）が、型は **誤り**（推定の誤りに移った）。第 1 ラウンドの D1 で「束ねると誤る」と測った 2 語そのもの。裁定の帰結として受け入れた。
- **L3（未知語 234）**: `items.jsonl` はバイト単位で第 3 ラウンドと同じ（変わった行 0。`correct_rate 0.4943`・`wrong_rate 0.0517`・`returned_type_rate 0.15`・`leaks_direct_not_notation []`）。
- **L1（被覆）**: `token_cover_rate 0.7907 → 0.7957`、`distinct_cover_rate 0.6415 → 0.6483`、名詞 `0.7794 → 0.7842`、動詞 `0.8346 → 0.8422`。被覆できなかった語の一覧（`items.jsonl`）から 58 行（語と品詞の組）が消えた（被覆の側に移った。例: `ザ`・`デ` のような 1 文字のカタカナ、`もの`・`ごう`）。被覆は正誤を測らない指標なので、この 58 行の型が正しいかは測っていない。
- 配置をつないだ経路づけ（`scripts/routing_with_placement.py <r5 run1>`、`routing_with_placement_r3_vs_r4.diff`）: 第 3 ラウンドの出力と **差 0 行**（`agent changed: 0`、`misroutes … with placement 0`）。

**`event_cross` との接点（製品コードは変えていない。監査役への申し送り）**: `verantyx/event_cross.py` の `ESTIMATE_BASES = ('proximity', 'generated')` は `kana_variant` を知らない。`PlaceResult.from_coarse_query` で包んだ借りた答えは `invariant_problems()` に `ESTIMATE_BASIS_UNKNOWN:kana_variant` が出る（`artifacts/w5-b/kana_variant_event_cross.txt`: `DECIDED estimated kana_variant ['ESTIMATE_BASIS_UNKNOWN:kana_variant']`）。十字ではこれが `INVALID`（`LOOKUP_RESULT_INVALID`）として型つきで止まる（誤答にはならない）。`event_cross.py` は W3-b1 が変更中で触れない。`ESTIMATE_BASES` に足すかどうかは W3-b1 側の判断。同様に `tests/coarse_place/test_coarse_place_build.py` の `check_invariants`（W3-a のもの。このチケットでは変えない）も `estimate_basis` を `proximity`／`generated` に限っているので、借りた答えにそのヘルパーを当てると落ちる（新しい試験は当てていない）。

**残る穴**: (1) 借りた型が誤ることがある（`ロケット`・`モネ` の 2 例。かな違いで別の語義になる語）。印（`estimated`／`kana_variant`）が付くので、同点の解消には使わないという §11.6 の提案（推定は決めに使わない）に従う側が止められる。(2) 変種を持たない表記は従来どおり `UNPLACED`／`UNKNOWN` のまま（借りない）。

## 12. W3-a3: 述語の枠と高頻度語の「直接」の型 — 生成と分布の一致で埋める（日本語）

<!-- w3a3-prereg:begin -->
登録日時: 2026-10-03 18:49:53 +0900 から 2026-10-03 18:51:03 +0900 の間（`date '+%F %T %z'` の出力。`artifacts/w3-a3/prereg_time.txt` の `before` と `after`。この節はその間に書いた）
この時点で `tests/coarse_place/data/dev_verbs.jsonl`・`verb_check_300.jsonl`・`artifacts/w3-a3/FROZEN.json`・`tests/coarse_place/test_coarse_place_w3a3_*.py`・`tests/test_gen_coarse_evidence_pred.py` は存在しない。製品コード（`verantyx/coarse_*.py`・`tools/*.py`）の差分は 0。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-a3/plan.md`（チケット W3-a3）。この節に **語の一覧は無い**（型の id・助詞・設定の名前と格子だけ）。

### 12.1 目的と、規則の形（変えるなら下の「変更記録」に日時つきで書く）
述語（動詞）の「型 ＋ 格の枠（助詞 → 期待する充填物の型）」と、時・場所・数量の語の直接の型を、**生成（モデルが書いたもの）と分布（材料の数え）の一致** で `direct` にする。生成だけで決まったものは `estimated(generated)` に留める。配置は情報を増やさない: 分布の腕と `slot` の腕は **単独では決めない**（`AGREEMENT_ONLY`）。読解器には触れない（契約と欄だけ。読解器は W3-b2）。

### 12.2 K62 の写し（`coarse_types.K62_FRAMES`）
出典は W3-b1 の `docs/READING_SOUNDNESS.md` §10 の K62 の表（`origin/integ-w3b1`、コミット `5d863dd`、blob `0d6233b20c6a1cd717f9a16bb6d96476422864ab`。§10A の K62 ではない）。表は 2 型 9 行。写しは型 id・助詞・名詞の型 id だけで、`artifacts/w3-a3/k62_source.md` に表をそのまま貼って機械で照合する。**表を広げない**。残り 11 型は枠が無い（「読まない型」）。
**区別の行**: 型 T の行の (助詞, 名詞の型) の組のうち、もう一方の型のどの行にも無い組。表から機械的に導く関数で求め、手で選ばない。
（W3-b4 追記 2026-10-04 01:10 +0900）読解器は v2（`docs/READING_SOUNDNESS.md` §10D の `w3b4_frames`、`semantic_reader.typed_frames_v2()`）で読む。配置の逆引き・格上げは v1（この節の `K62_FRAMES`）のまま。v1 ⊂ v2（行単位）は `tests/coarse_place/test_k62_v1_subset_v2.py` が確かめる。逆引きを v2 に移すかは W3-a4（r7 の 48 語がどう動くかを測ってから）。

### 12.3 抽出段の新しい数え（`analyze`。読解器は使わない）
「項の連なり」の規則（隣接だけ。長距離は数えない）:
- 印 m は、名詞の連続（今の `analyze` の run と同じ切り方）の直後の格助詞 9 種（が を に で へ と から まで より）か、読点「、」（∅）。は・も・の は印にしない。
- 印の直後から右へ、次のどれかが来るまで見る。(1) 名詞の連続＋格助詞 9 種の組（ほかの項）。最大 3 組。4 組目が来たら数えない（`too_many_args`）。(2) 動詞（`pos1 == 動詞`）が来たらそれがこの項の述語。(3) 文末・句点に至っても動詞が無い（`no_verb`）、それ以外（読点・副詞・形容詞・連体詞・接続助詞・係助詞・の・名詞の連続のあとに助詞が無い・代名詞 等）が来たら数えない（`chain_broken`）。
- 述語は `orthBase`（無ければ表層）。直前が名詞の「する」は数えない（`sahen`）。動詞の直後に連続する助動詞の原形に れる・られる・せる・させる があれば数えない（`voice`。態を変えると助詞と役割の対応が変わるため。閉じた文法の類で、語の一覧ではない）。連続する助動詞の原形に た があれば「過去」の印を付ける。
- 充填物は `(連続全体の語, 最後の名詞の原形)`。数詞で始まる連続は数えない（`numeral_start`。数量は表記の規則と既存の counters で扱う）。
- 出所ごとに `acc["chain"]: Counter[(filler_run, filler_head, m, verb, past)]` に数える。出所をまたいで足さない。抽出段の cache に新しいキー `chain` が無いときは、型つきで止まる（`STAGE_CACHE_STALE`、終了コード 4）。理由別の数（`chain_broken`・`too_many_args`・`no_verb`・`sahen`・`voice`・`numeral_start`・数えた数）は manifest に出す。

### 12.4 述語の分布の腕 `role_distribution`（出所ごと。`ARMS_BY_SOURCE`）
決定は 2 段（循環を避ける）。**段 1** = 今の判定（新しい腕なし）を全語に行う。段 1 で `DECIDED`・`origin=direct`・名詞の型 1 つ・`decided_by` に生成の腕（`gen_definition`・`gen_frame`）を含まない語だけを「型の分かった充填物」とする。**段 2** で、新しい腕の行を足して、新しい行を持つ語だけを決め直す。新しい腕は単独では決めないので、段 2 で段 1 の型の源は変わらない。
- 充填物の型: 連続全体の語が段 1 で型を持てばそれ、無ければ最後の名詞の型、どちらも無ければ型なし（数えるが票にしない。`untyped` として manifest に）。この順は固定の規則（同点の解消ではない）。
- evidence の行: `(述語, "role_distribution", 出所, "<助詞>|<名詞の型>", n, base=その述語のその出所での型つきの項の総数)`。述語ごと出所ごとに `rd_store_min` 以上の型つきの項があるときだけ保存。∅（読点）は述語の腕に入れない（格助詞 9 種だけ）。
- `arm_verdict("role_distribution")`（判定は `coarse_types` の 1 か所。builder と問い合わせが同じ関数を使う）。K62 の逆引き:
  1. `base < rd_min_total` → 票なし。
  2. 有意な助詞 Sig: 助詞 p の型つきの数 n_p が `rd_particle_min` 以上、かつ n_p ≥ `rd_particle_share_pct`% × base。
  3. 各 p ∈ Sig の有意な型 Types(p): n_{p,t} ≥ `rd_type_share_pct`% × n_p。
  4. K62 の型 T が候補になるのは、(a) Sig のうち K62 の 6 助詞（が を に で へ から）に入るものが、すべて T の行の助詞に含まれ、(b) その各 p で Types(p) ⊆ T の行の型、(c) T の区別の行の少なくとも 1 つが有意（p ∈ Sig かつ t ∈ Types(p)）。と・まで・より は表に無い助詞なので候補の判定には使わない（数は見せる）。
  5. 候補がちょうど 1 つ → その型。0 または 2 → 票なし（割れは票にしない。同点は棄権）。
- この腕は単独では決めない（`threshold_met=True` でも `met=False`、`why="AGREEMENT_ONLY"`）。生成の型との一致だけに使う。
- 帰結: K62 の `P_MOVE` に に+PLACE の行は無いので、に+PLACE が有意な移動の動詞は (a)(b) で候補にならない。再現率は低く、精度を優先する設計である。

### 12.5 名詞の「時・場所・数量」の腕 `slot`（出所ごと。`ARMS_BY_SOURCE`）
- 12.3 の数えから、名詞の語ごとに出所ごとに、型ごとに別の数を数える（型をまたいで足さない）。`TIME`: 印が ∅ か に で、述語が「過去」の印つき。`PLACE`: 印が で か に で、述語の段 1 の型（`DECIDED`・direct・生成の腕なし）が `P_MOVE` か `P_EXIST`（**動詞の一覧を書かない。配置の型で決める**）。`QUANTITY`: 既存の `counters`（算用数字の直後の 1 形態素）のその語の数をそのまま使う（新しく数えない）。
- 行 `(語, "slot", 出所, 型, n, base=その出所での名詞の使用数)`。builder は出所ごとの基準率（その出所の全名詞の使用のうちその構文に出た割合）に対する持ち上げが `slot_lift_pct`%（= `ctx_min_lift_pct` と同じ 300）以上の型だけを行にする。
- `arm_verdict("slot")`: 最上位の型の数 ≥ `slot_min` かつ ≥ `slot_share_pct`% × base。同点は全部並べる。
- この腕も単独では決めない（`AGREEMENT_ONLY`）。W3-a2 の `gen_definition` の格上げ（生成でない腕で、自分の閾値を満たし、最上位がちょうど [T]）の相手にだけなる。したがって `slot` で direct になった語の `decided_by` には必ず `gen_definition` が入る（W3-b1 の門 4 に当たる。仕様どおり）。名詞の生成は W3-a2 の物をそのまま使う（作り直さない）。

### 12.6 生成の腕 `gen_frame` と格上げの規則（`coarse_types.decide_word` の 1 か所）
- 票の行 `(語, "gen_frame", "generated:<model>:<effort>", 述語の型, 1, None)`。枠の行（票でない。`NON_VOTE_ARMS`）`(語, "gen_frame_slot", 同じ出所, "<助詞>|<名詞の型>", 1, None)`。名前空間に P を含む語だけ（名詞には付けない）。
- `GEN_ARMS = (gen_definition, gen_frame)`。生成が決め手に入った語は、直接でも推定の材料（head の段・donor・単位の族）にしない。
- 判定（`gen_frame` の行がある語）: (1) 生成の腕と `role_distribution`・`slot` を除いて判定（`_decide_base`）。`DECIDED`／`MULTIPLE` ならそれが最終（`why="GENERATED_NOT_DECIDING"`）。(2) `UNPLACED` で `gen_frame` の型が 1 つ T のとき、`role_distribution` の腕のうち自分の閾値を満たした（票のある）ものを R とする。**格上げ（direct）**: |R| ≥ `rd_min_sources`、R のすべての腕の票が [T]、かつ R の各腕について「生成の枠の助詞の集合 ⊇ その腕の有意な助詞の集合（9 種全部。と・まで・より を含む）」→ `DECIDED`・`origin=direct`・`decided_by = sorted(R の腕 + ["gen_frame"])`。R の腕に T と違う型の票がある → `estimated(generated)`・`why="DISTRIBUTION_DISAGREES"`（MULTIPLE にはしない: 分布の腕は単独で決めない腕で、直接の候補として並べない）。型は一致するが助詞の包含が成り立たない → `estimated(generated)`・`why="FRAME_PARTICLES_NOT_COVERED"`。R が空、または |R| < `rd_min_sources` → `estimated(generated)`（`why` なし）。(3) 生成が棄権（null）・枠が採れない → 何もしない。
- 推定（生成）の答えの形は W3-a2 と同じ（`estimate_basis="generated"`）。`estimate_basis` に新しい値を作らない。
- 帰結: K62 は 2 型だけなので、生成と分布の一致で `direct` になる述語の型は `P_MOVE` と `P_COMMUNICATE` だけ。ほかの 11 型は `estimated(generated)` に留まる。
- 格上げのうち、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）だった語の数を別に出す（codex が書いた枠と codex が書いたコーパスの一致であることを隠さない）。
- `gen_frame` で格上げした述語は、W3-b1 の門 4（`'gen_definition' in decided_by` の文字列だけを見る）を通る。読解器が使うかは W3-b2 で決める。答えに `generated_frame: true` を付けて機械的に区別できるようにする。

### 12.7 既存の `frame` 腕（`PRED_FRAME_RULES`）の扱い
削除しない。設定 `frame_decides`（`DEFAULT_CONFIG` の既定は True。古い配置で保存された判定を再現するため）で決め手に入れるかを切り替える。False のとき `frame@src` は `threshold_met` のまま `met=False`、`why="FRAME_NOT_DECIDING"`。
**決め方（dev の動詞を測る前に書く）**: dev の動詞（12.11）について、R5 で `decided_by` に `frame@` を含む語の正答・誤決定を数え、**正答が誤決定の 3 倍以上なら True、そうでなければ False**。どちらも 0 のときは False（決め手の無いものを決め手に入れない）。数は `dev_frame_legacy.txt` に。W3-a の凍結データの数字（決め手の 18 語のうち正答 2・誤決定 11）は根拠にしない。

### 12.8 設定・dev の格子・選び方
新しい設定（`DEFAULT_CONFIG` に追記。既存の設定の値は変えない。既定値は古い配置で今の判定を再現する値）と、dev で試す格子（厳しい側から並べる。この並びが最後の同数の解消の順）:

| 設定 | 意味 | 格子 |
|---|---|---|
| `frame_decides` | 既存の `frame` 腕を決め手にするか | 12.7 の規則で 1 つに決まる |
| `rd_store_min` | 分布の行を保存する床 | 固定 20（格子の `rd_min_total` の最小値以下） |
| `rd_min_total` | 分布の腕の型つきの項の最小 | 100 / 50 / 20 |
| `rd_particle_min` | 有意な助詞の最小数 | 10 / 5 |
| `rd_particle_share_pct` | 有意な助詞の割合 | 30 / 20 / 10 |
| `rd_type_share_pct` | 助詞の中で有意な型の割合 | 70 / 50 |
| `rd_min_sources` | 格上げに要る分布の腕の数 | 2 / 1 |
| `slot_min` | slot の最小数 | 20 / 10 / 5 |
| `slot_share_pct` | slot の割合 | 30 / 20 / 10 |
| `slot_lift_pct` | 基準率に対する持ち上げ | 固定 300（= `ctx_min_lift_pct`） |

**選び方**: 述語は dev の動詞で、`origin=direct` の誤決定が 0 の設定のうち、`origin=direct` の正答が最多のもの。誤決定が 0 の設定が無ければ、誤決定が最少の設定のうち同じ規則。同数なら direct の答えが少ない（より厳しい）もの、なお同数なら格子の並びで先のもの。名詞（slot）は dev の語彙（L2）で、`direct` の誤決定が slot なし（段 1 と同じ判定）より増えない設定のうち、direct の正答が最多のもの。同数の扱いは述語と同じ。格子の評価は **1 つの dev 配置の保存された evidence から `ct.decide_word` を設定を変えて呼び直す**（判定は evidence と設定だけの関数。保存の床と持ち上げは固定なので結果に効かない）。選んだ値で dev 配置を 1 回作り直し、問い合わせの入口で同じ数になることを確かめる。**凍結データを見て設定・規則を変えない**。

### 12.9 述語の枠の生成（`tools/gen_coarse_evidence.py --kind pred`）
- 名詞の形（プロンプト・schema・argv・sha256 `ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65`）は 1 バイトも変えない。述語は `--kind pred`（既定 `noun`）。台帳・再開・再試行・上限・並列・stdin を閉じる・`--codex-bin` 必須・道具の使用の棄却は既存の仕組みをそのまま使う。
- `needs --kind pred`: 見出し語のうち ns が P か NP、state が UNPLACED か MULTIPLE、かつ抽出段の cache の品詞の数で動詞（V）の使用が形容詞・形状詞（A+S）の使用より多い語（一覧を作るための絞りで、型の票ではない。全出所の和を使う）。`n_seen` の降順、境界の同点は全部入れる。検査データを読まない。上位 5,000 語。
- 呼び出し: `gpt-6-luna`・effort `low`・`--slots 12`・`--max-calls 1500`・`-s read-only`・stdin を閉じる・束 40 語。
- プロンプトは 13 の述語型 id と名詞 17 型の id を `coarse_types.PRED_TYPES`・`NOUN_TYPES` の説明つきで機械的に並べる（手で写さない）。助詞は 9 種。語ごとに `ptype`（13 の id か null）と `frame`（`[{"particle": 9 種, "types": [17 型 id…]}]`）。例に検査データの語を使わない。
- 出力の検査: 束に無い語は捨てて数える（`foreign`）、同じ語が 2 回返ったら採らない（`dup_dropped`）、同じ助詞が 1 語の frame に 2 回あればその語の frame を採らない（`frame_dup_particle`）、ptype が null なら棄権、enum の外は採らない（`invalid`）。

### 12.10 問い合わせの新しい欄（§11.6 の契約への追記）
すべての答えに、既存のキーの値と順を変えずに、最後に次のキーを足す。
- `frame_status`（**閉じた一覧**）: `CONFIRMED`（下の `frame` がある）・`NOT_CONFIRMED`（P の direct だが `gen_frame` の格上げで決まっていない）・`ESTIMATED`（推定）・`NOT_PREDICATE`（名前空間が P でない、または型が P_ でない）・`NO_ANSWER`（UNPLACED・UNKNOWN・MULTIPLE）・`NO_PLACEMENT`・`NO_FRAME_TABLE`（`generated_frames` 表の無い古い配置で、P の direct の答え）。
- `frame`: `CONFIRMED` のときだけ `{助詞: [名詞の型, …]}`、ほかは null。中身 = 格上げに加わった分布の腕の有意な助詞の和集合 S（集合の和で、数は足さない）の各 p について、生成の枠の p の型（ソート）。S に無い生成の助詞は `frame` に入れず `frame_unconfirmed`（表示用。`CONFIRMED` のときだけ付く。読解器は使わない）に出す。助詞の並びは `ROLE_PARTICLES` の順。
- `generated_frame`（直接の答えだけ）: `decided_by` に `gen_frame` があれば true。`gen_frame` の腕の `axes` に `provenance`（model・effort・batch_id）。
- `axes["role_distribution@…"]`・`axes["gen_frame"]` の `top` は `decide_word` の判定を出す（数の鍵が「助詞|型」なので最大の鍵は意味が無い）。ほかの腕の `top` の出し方は変えない。
- 不変条件: `frame` が null でない ⇔ `frame_status == CONFIRMED` ⇒ `namespace == "P"`・`state == DECIDED`・`origin == direct`・`gen_frame ∈ decided_by`・鍵はすべて格助詞 9 種・値は空でない 17 型のソート済みの並び。
- `why` の閉じた一覧（新規分）: `AGREEMENT_ONLY`・`FRAME_NOT_DECIDING`・`DISTRIBUTION_DISAGREES`・`FRAME_PARTICLES_NOT_COVERED`（既存の `GENERATED_NOT_DECIDING`・`GENERATED_SPLIT`・`SEEDED`・`OUTRANKED`・`ROLE_SINGLE_SOURCE`・`RECOVERED_NOT_DECIDING` はそのまま）。

（W3-b5 追記 2026-10-04 06:10:50 +0900）**問い合わせの新しい鍵 `frame_generated`**（常に出す。`frame` とは独立）: 値は `null` か `{"origin": "generated", "constructed": true, "ptype": <生成の枠の表の ptype>, "frame": <生成の枠の表の frame をそのまま。{助詞: [型…]}>, "provenance": {"model", "effort", "batch_id", "attempt"}}`。引く語は答えの `spelling.normalized`（配置を引いた NFKC の形）。`null` になるのは、配置が開けない（`NO_PLACEMENT`）・配置に `generated_frames` 表が無い・表にその語の行が無いとき。置き場所は W3-a3 の末尾の鍵（`generated_frame`・`frame_status`・`frame`・`frame_unconfirmed`・`frame_disagreement` のうち答えにあるもの）の最初の鍵の直前（`spelling` の後ろ）。既存の鍵の値と順は変わらない（`frame_generated` を除いた答えは基点と byte 一致。r7・r8 の全語でテストする）。`frame`（CONFIRMED のときだけ）・`frame_status`・`frame_unconfirmed` の意味と値は変わらない。不変条件: `frame_generated` が null でないなら `origin == "generated"`・`constructed == true`・`frame` の鍵は格助詞 9 種・値は 17 型の文字列の並び。生成の枠は構成物であって証拠でない。読解器はこれを `frame_required` の行の許可（読んでよいか）にだけ使い、型の決定や同点の解消には使わない（docs/READING_SOUNDNESS.md §10F K200〜K203）。（W3-b5 追記 2026-10-04 07:39:33 +0900: 第 2 ラウンドの表の変更 2 の後、`frame_required` の行は 0 行で、読解器はこの鍵を使って読む文を 1 文も持たない。鍵は契約として残る。）

### 12.11 検査データ・採点
- 抜き出しの枠: `artifacts/w3-a/pred_verb_freq.tsv`（材料の頻度の上位 3,000 の述語）の `class == V`、`seed == -`、`in_predicate_check == -` の行。**種と W3-a の述語の確認とは重ねない**。
- `tests/coarse_place/data/dev_verbs.jsonl`（dev、閾値を決める用）: 枠から `random.Random(20261004).sample` で 130 語に手で型を付ける。断片（語にならないもの）は `kind="unknown_fragment"`・`gold=[]`・`gold_unknown=true`。それに、材料に無い造語の動詞 20 語（`kind="unknown_coined"`）。
- `tests/coarse_place/data/verb_check_300.jsonl`（凍結の検査）: dev の 130 語を除いた残りから `random.Random(20261005).sample` で 260 語に型を付け、断片は unknown にし、造語の動詞を足して計 300 行（造語 40 語）。
- 行の形: `{"id","term","kind":"typed"|"unknown_fragment"|"unknown_coined","gold":[P_ 型,…],"gold_unknown":bool,"frame":{助詞:[名詞の型,…]}|null,"why":短い理由}`。`gold` は多義なら 2〜3 型まで。`frame` は `P_MOVE`・`P_COMMUNICATE` を gold に持つ語には必ず書く。frame の照合は報告だけ。
- 造語は配置 R5 の `headwords` に無いことを確かめて記録する（`coined_absent.txt`）。造語だけを `exclude_coined.jsonl` に書き、r6 の作成で `--exclude-terms` に渡す。**検査データのファイルそのものは `--exclude-terms` に渡さない**。
- 採点（W3-a の `PREREG.md` と同じ定義）: 正答 = `top` が空でなく gold と交わり `len(top) ≤ max(1, len(gold))`。誤決定 = `len(top)==1` かつ gold の外。**Q3 の分母**: 誤決定率 = `origin=="direct"` かつ誤決定 / typed の件数。分からない語で型を返す率 = `top != []`（直接・推定を問わない）/ unknown の件数。参考に direct の答えの中での誤決定の割合も出す。断片の語は材料にあるので生成の一覧に入りうる。モデルが型を返せば `estimated(generated)` になり「型を返す」に数える（一覧から手で除かない）。
- 凍結: `artifacts/w3-a3/FROZEN.json`（各ファイルの sha256・行数・凍結時刻 `frozen_at`、`PREREG.md` の sha256）。**凍結時刻 > この節の登録時刻**、かつ **凍結時刻 < 製品コードの最初の変更**。

### 12.12 受入基準（事前登録）
- **Q1** 分布の腕と格上げの規則が、検査データを書く前に docs に日時つきで登録されている。語の一覧が無い。
- **Q2** 生成は上限 1,500 回以内。成功した束の割合・所要時間・1 語あたりの呼び出し数を報告。
- **Q3** 動詞 300 語の凍結データで、`direct` の述語の型の **誤決定 ≤ 5%**、分からない語で型を返す ≤ 20%（目標の正答率は書かない。数だけ）。中間職の 100 語でも同じ条件。
- **Q4** W3-a の凍結データ L1〜L3 が悪化しない（W3-a2 の承認条件と同じ）。
- **Q5** 配置の作成が決定的（cache なしの 2 回の `content_sha256` が一致）。
- **Q6**（監査役が測る）隠しバンク B1 を `VERA_PLACEMENT` つきで流し、誤読 0・誤答 0 のまま `PLACEMENT_PREDICATE_UNIDENTIFIED` の件数が減る。**この基準は配置の側の変更では動かない見込みで、満たせないものとして報告する**: その理由を出すのは `origin/integ-w3b1:verantyx/semantic_read.py` の 760 行目だけで、英語の入力で、どの語も既知の動詞の閉じた一覧に無いときに、配置を一度も問い合わせずに足される（`_read_en`、758〜760 行）。日本語の経路にこの理由は無い。
- **Q7** 既存テストの失敗集合が基線（114 件）から増えない。

### 12.13 決めた順
登録（この節）→ 検査データの作成と凍結 → 既存 `frame` 腕の dev での判定（R5）→ 製品コード → 合成のテスト → 抽出の cache と述語の生成なしの配置（r6/base）→ 述語の一覧と生成 → dev の格子と設定の凍結 → 全量 r6（cache なし 2 回）→ 凍結データの測定 → 全体テストと文書。凍結データの測定のあとに規則・設定を変えない。

### 12.14 変更記録（登録のあとの変更はすべてここに日時・前後・理由を書く）
（登録時点では無し）
<!-- w3a3-prereg:end -->

<!-- w3a3-measure:begin -->
### 12.15 測定（登録の外。この節の数値は `artifacts/w3-a3/render_w3a3.py` が `artifacts/w3-a3/` の測定ファイルから描く。`render_w3a3.py --check` で一致を確かめる）

### 12.15.1 実行の順と時刻

登録 → 凍結 → 実装 → dev → 設定の凍結 → 全量 → 凍結データの測定、の順に、次の時刻で行った（出典: `prereg_time.txt`・`FROZEN.json`・`*.started`）。製品コードの最初の変更は凍結の後（`DECISIONS.md` D1）。

<!-- BEGIN table:w3a3_order -->
| 段 | 時刻（`date '+%F %T %z'`） |
|---|---|
| 事前登録（docs §12.1〜12.14） | 2026-10-03 18:49:53 +0900 〜 2026-10-03 18:51:03 +0900 |
| 検査データの凍結（`FROZEN.json` の `frozen_at`） | 2026-10-03 18:55:35 +0900 |
| r6/base の作成を始めた | 2026-10-03 19:04:20 +0900 |
| 述語の枠の生成（本番）を始めた | 2026-10-03 19:16:00 +0900 |
| dev の配置 d1 の作成を始めた | 2026-10-03 19:22:37 +0900 |
| 設定を凍結した（`config_w3a3.json`） | 2026-10-03 19:27:52 +0900 |
| 全量 r6/run1 の作成を始めた | 2026-10-03 19:33:17 +0900 |
<!-- END table:w3a3_order -->

### 12.15.2 述語の一覧と生成（Q2）

呼び出しは試し 1 回を含み、上限 1,500 の内。出典: `gen_pred_summary.json`・`needs_pred.meta.json`。名詞のプロンプトの sha256 は `ded30f48…` のまま変えていない（`test_the_noun_prompt_and_its_hash_did_not_change`）。

<!-- BEGIN table:w3a3_generation -->
| 項目 | 値 |
|---|---|
| 一覧の語数（境界の同点を全部入れた。頼んだ数 5000） | 5022 |
| 一覧の境界の頻度（`n_seen`）と、その頻度の語数 | 16 / 92 |
| 一覧の内訳（名前空間） | NP 34, P 4988 |
| 一覧の内訳（証拠の状態） | BELOW_THRESHOLD 2190, NO_EVIDENCE 2832 |
| モデル・effort・並列・束の大きさ | gpt-6-luna・low・12・40 |
| 呼び出し数（上限 1500） | 126 |
| 束の数・成功した束・成功の割合 | 126・126・1.0000 |
| 失敗した束・上限で走らなかった束 | 0・0 |
| 所要時間（台帳の最初の start から最後の end まで。試し呼び出しとの空きを含む） | 431.7 秒 |
| 呼び出しの時間の合計（並列の分を足したもの） | 4197.0 秒 |
| 1 語あたりの呼び出し数（呼び出し数 / 頼んだ語数） | 0.02509 |
| 答えが返った語・棄権（`ptype` null）・同じ助詞が 2 回の frame | 5022・234・5 |
| 束に無い語・重複・範囲外・戻らなかった語 | 0・0・0・0 |
| 述語のプロンプトの sha256（固定部） | 1509fd3014397232d48dfd00b0ae9d8df078b5f2fb3d54e9f53c2b17a76d68e2 |
| schema の sha256 | 68551a6ab548b7d5920d5c22cb0ca7eb114f47589ffd50a0b5ad6a488a84d882 |
| 台帳の sha256 | d21fe1e3064f6363440d75f3807c1ed3954fa5a03e70326a753586f46d13a0c4 |
| `frames.jsonl` の sha256 | 9a7e8decfc85d2dde8a0209cf983491cc6d4d0257697ab19ff18828b9ae89717 |
<!-- END table:w3a3_generation -->

一覧に載った検査データの動詞（数えただけ。一覧は検査データで変えていない）: dev の動詞 150 行のうち 126 行（typed 124・断片 2・造語 0）、凍結の 300 行のうち 260 行（typed 258・断片 2・造語 0）。造語は材料から除いたので一覧に載らない。

### 12.15.3 設定（dev で決めた値。ここから先は変えない）

`frame_decides` は §12.7 の規則どおり、R5 を dev の動詞で測った結果（`dev_frame_legacy.txt`）で決めた: `frame@` が決め手の語の正答 10・誤決定 11・その他 2 → 正答が誤決定の 3 倍に届かない → False。ほかの値は dev の格子（`dev_grid.py`、全行は `dev_grid.txt`）から §12.8 の選び方で選んだ。設定ファイルの sha256 は `config_w3a3.sha256`。

<!-- BEGIN table:w3a3_config -->
| 設定 | 意味 | 格子 | 値 |
|---|---|---|---|
| frame_decides | 既存の `frame` 腕を決め手にするか（§12.7 の規則で決まる） | 規則で 1 つ | False |
| rd_store_min | 分布の行を保存する床（固定） | 固定 20 | 20 |
| rd_min_total | 分布の腕の型つきの項の最小 | 100 / 50 / 20 | 20 |
| rd_particle_min | 有意な助詞の最小数 | 10 / 5 | 10 |
| rd_particle_share_pct | 有意な助詞の割合（%） | 30 / 20 / 10 | 30 |
| rd_type_share_pct | 助詞の中で有意な型の割合（%） | 70 / 50 | 50 |
| rd_min_sources | 格上げに要る分布の腕の数 | 2 / 1 | 1 |
| slot_min | slot の最小数 | 20 / 10 / 5 | 20 |
| slot_share_pct | slot の割合（%） | 30 / 20 / 10 | 30 |
| slot_lift_pct | 基準率に対する持ち上げ（%。固定） | 固定 300 | 300 |
<!-- END table:w3a3_config -->

述語の格子 72 行の選択: 格子の 51 行目（0 始まり）。dev の動詞での direct の数 = {"direct_correct": 3, "direct_wrong": 3, "direct_answers": 6, "unknown_direct": 1, "gen_frame_direct": 3}。新しい腕を全部外したときの数（参考）= {"direct_correct": 0, "direct_wrong": 3, "direct_answers": 3, "unknown_direct": 1, "gen_frame_direct": 0}。

slot の格子 9 行の選択: 格子の 0 行目。dev の語彙（L2、種を除く）での direct の数 = {"direct_correct": 299, "direct_wrong": 24, "direct_answers": 353, "unknown_direct": 0, "gen_frame_direct": 0}。slot の行を外したときの数 = {"direct_correct": 298, "direct_wrong": 24, "direct_answers": 352, "unknown_direct": 0, "gen_frame_direct": 0}。

### 12.15.4 配置 r6 の中身（`manifest_r6_run1.json`）

<!-- BEGIN table:w3a3_placement -->
| 項目 | 値 |
|---|---|
| 見出し語の数 | 1758845 |
| direct で置いた語（`placed_direct`） | 992686 |
| `estimated(generated)` の語（名詞の定義 + 述語の枠） | 20403 |
| `generated_frames` 表の行数 | 4788 |
| `evidence` 表の行数 | 1864292 |
| 作成の所要時間（秒。cache なし） | 516.7 |
<!-- END table:w3a3_placement -->

述語の枠の生成を配置に入れた結果（`generated_frames` の節。語数）:

<!-- BEGIN table:w3a3_gen_frames -->
| 項目 | 語数 |
|---|---|
| 読んだ行（`frames.jsonl`） | 4788 |
| 使った語（述語の見出し語） | 4788 |
| 棄権（`ptype` null） | 234 |
| 名前空間に P を含まない語（`ns_not_predicate`） | 0 |
| 材料に無い語 | 0 |
| 格上げ（direct。`decided_by` に `gen_frame`） | 48 |
| 　うち、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し） | 30 |
| 　うち、jawiki の腕が加わった | 18 |
| `estimated(generated)`（生成だけ・または一致せず） | 4740 |
| 　うち `DISTRIBUTION_DISAGREES` | 743 |
| 　うち `FRAME_PARTICLES_NOT_COVERED` | 54 |
| 生成が決めない（別の腕がすでに決めていた） | 0 |
<!-- END table:w3a3_gen_frames -->

項の連なりの数え（抽出段。出所ごと。理由別。数えなかった理由も数える）:

<!-- BEGIN table:w3a3_chains -->
| 出所 | counted | chain_broken | too_many_args | no_verb | sahen | voice | numeral_start | no_filler |
|---|---|---|---|---|---|---|---|---|
| codex:code | 2891396 | 2014128 | 28 | 43 | 1728884 | 136199 | 91896 | 4086 |
| codex:code_qa | 1211430 | 787989 | 30 | 431 | 569555 | 30191 | 130901 | 2869 |
| codex:conversation | 1733959 | 1160218 | 16 | 27694 | 189776 | 48783 | 63008 | 349 |
| codex:figurative_commonsense | 911544 | 302433 | 25 | 3961 | 63124 | 31433 | 4670 | 0 |
| codex:general_qa | 1831432 | 1152371 | 33 | 935 | 357100 | 89119 | 39022 | 542 |
| codex:narrative | 918086 | 379456 | 11 | 8745 | 28844 | 31313 | 13592 | 0 |
| codex:paraphrase_entail | 1219793 | 640157 | 96 | 2680 | 208553 | 161657 | 27017 | 6280 |
| codex:pro | 2632600 | 1152465 | 17 | 3 | 35579 | 76739 | 17769 | 0 |
| jawiki | 1676156 | 2006347 | 406 | 3921 | 844152 | 156307 | 619778 | 34941 |
<!-- END table:w3a3_chains -->

段 2 の内訳（出所ごと。型の分かった項・型なしの項・分布の行を持つ述語・slot の行）:

<!-- BEGIN table:w3a3_stage2 -->
| 出所 | 型つきの項 | 型なしの項 | 分布の行を持つ述語 | 分布の行 | slot TIME | slot PLACE | slot QUANTITY |
|---|---|---|---|---|---|---|---|
| codex:code | 1063319 | 1772839 | 596 | 17791 | 3674 | 4725 | 636 |
| codex:code_qa | 533437 | 653870 | 385 | 9674 | 1360 | 1793 | 829 |
| codex:conversation | 726295 | 890751 | 980 | 21628 | 3178 | 4257 | 159 |
| codex:figurative_commonsense | 382665 | 500592 | 1185 | 23937 | 2378 | 2002 | 6 |
| codex:general_qa | 789570 | 987995 | 1321 | 28888 | 3958 | 5328 | 323 |
| codex:narrative | 432973 | 462122 | 1045 | 21706 | 2151 | 1516 | 2 |
| codex:paraphrase_entail | 613863 | 584056 | 951 | 17418 | 3762 | 2206 | 169 |
| codex:pro | 1070636 | 1494573 | 1407 | 28942 | 2502 | 1486 | 1 |
| jawiki | 754709 | 833607 | 1013 | 23480 | 20641 | 57797 | 1406 |
<!-- END table:w3a3_stage2 -->

段 1 で型の分かった充填物の語 981743・述語の語 2583、新しい行を持つ語 104890。`evidence` の腕ごとの行数（新しい腕）: `role_distribution` 193464・`slot` 128245・`gen_frame` 4788・`gen_frame_slot` 15395。

### 12.15.5 述語の型（Q3。凍結データの動詞 300 語・配置 r6/run1）

出典: `eval_runs/001/summary.json`（`measure_w3a3.py verbs --data tests/coarse_place/data/verb_check_300.jsonl`）。数だけを書く（目標の正答率は書かない）。正答・誤決定の定義は §12.11。

<!-- BEGIN table:w3a3_q3 -->
| 項目 | 値 |
|---|---|
| typed の語・分からない語（断片・造語） | 258・42 |
| direct の答え（typed の中） | 5 |
| 　うち正答・誤決定 | 4・1 |
| **direct の誤決定 / typed**（Q3: ≤ 5%） | 1 / 258 = 0.4% → 満たす |
| direct の答えの中での誤決定の割合（参考） | 20.0% |
| **分からない語で型を返す / 分からない語**（Q3: ≤ 20%。direct・推定を問わない） | 1 / 42 = 2.4% → 満たす |
| typed のうち direct でない答え | None/other 5, estimated/correct 192, estimated/wrong_single 56 |
| typed 全体の正答・誤決定（direct か推定かを問わない。参考） | 196・57 |
| `frame_status` の分布 | CONFIRMED 5, ESTIMATED 249, NO_ANSWER 46 |
<!-- END table:w3a3_q3 -->

種類（`kind`）ごと:

<!-- BEGIN table:w3a3_q3_kind -->
| 種類 | 結果 |
|---|---|
| typed | correct 196, other 5, wrong_single 57 |
| unknown_coined | abstained 39, returned 1 |
| unknown_fragment | abstained 2 |
<!-- END table:w3a3_q3_kind -->

決め手の腕ごと（typed。腕名は出所を省いた）:

<!-- BEGIN table:w3a3_q3_arm -->
| 決め手 | 結果 |
|---|---|
| - | other(non-direct) 5 |
| est:morphology:kin | wrong_single(non-direct) 1 |
| gen_frame | correct(non-direct) 192, wrong_single(non-direct) 55 |
| gen_frame+role_distribution | correct 4, wrong_single 1 |
<!-- END table:w3a3_q3_arm -->

参考（dev の動詞 150 語・配置 d2。設定を決めた dev の数。`dev_runs/002`）: typed 127・分からない 23、direct の答え 6（正答 3・誤決定 3）、分からない語で型を返す 2 / 23。

### 12.15.6 W3-a の凍結データ L1〜L3（Q4。R5 との比較）

出典: `q4_compare.txt`（R5 の `artifacts/w3-a/eval_runs/041〜045` と、R6 の `eval_runs/` の最後の測定を読む。手で写していない）。W3-a2 の承認条件と同じ 4 項目（誤決定・罠・L3 の誤り・分からない語で型を返す が R5 以下）を満たすか: **満たす**。

<!-- BEGIN table:w3a3_q4 -->
| 項目 | R5 | r6/run1 | 差 |
|---|---|---|---|
| L2 direct の正答（分母 1072） | 567 | 567 | +0 |
| L2 direct の誤決定 | 47 | 47 | +0 |
| L2 語末の罠の誤決定 | 7 | 7 | +0 |
| L3 型が決まるべき語の正答（174 語） | 86 | 86 | +0 |
| L3 誤り | 9 | 9 | +0 |
| L3 分からない語で型を返す（60 語） | 9 | 9 | +0 |
| L1 トークンの被覆（21774 トークン） | 17217 | 17618 | +401 |
| L1 異なり語の被覆 | 5383 | 5625 | +242 |
| L1 配置された見出し語（direct） | 993027 | 992686 | -341 |
<!-- END table:w3a3_q4 -->

4 項目の判定: `L2 wrong<=47` = True, `trap<=7` = True, `L3 wrong<=9` = True, `unk_returned<=9` = True

併せて見た項目（R5 より下がっていないか）: L2 correct not lower = True, L1 token cover not lower = True, L3 correct not lower = True, L3 leaks (direct, not notation) none = True

R5 から上がった数 20 件・下がった数 11 件・変わらない数 38 件（全部の一覧は `q4_compare.txt`）。

下がった数（全部）:

- l1.placed_direct_headwords: R5 993027 -> new 992686 (-341)
- l1.tokens_by_basis.direct: R5 14832 -> new 14684 (-148)
- l1.tokens_by_basis.none: R5 4557 -> new 4156 (-401)
- l1.tokens_by_basis.proximity: R5 741 -> new 646 (-95)
- l1.tokens_by_origin.direct: R5 14832 -> new 14684 (-148)
- l1.tokens_by_origin.none: R5 4557 -> new 4156 (-401)
- l1.tokens_typed_by_basis.direct: R5 14832 -> new 14684 (-148)
- l1.tokens_typed_by_basis.proximity: R5 741 -> new 646 (-95)
- pred.all.wrong_single: R5 25 -> new 21 (-4)
- pred.non_seed.wrong_single: R5 22 -> new 20 (-2)
- pred.non_seed_now.wrong_single: R5 25 -> new 21 (-4)

### 12.15.7 決定性・判定の監査・全体テスト（Q5・Q7）

**Q5**（cache なし、同じ引数で 2 回作った `content_sha256`）:

```
verify run1: state OK content_sha256 5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1 bad []
verify run1 exit=0
verify run2: state OK content_sha256 5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1 bad []
verify run2 exit=0
['5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1', '5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1'] True
stage_cache arg (must be null for both): [None, None]
build durations (sec): [516.7, 526.4]
extraction_from_cache present: [False, False]
```

**判定の監査**（`audit_w3a3.py`、`audit_w3a3.txt`。全見出し語）:

<!-- BEGIN table:w3a3_audit -->
| 項目 | 値 |
|---|---|
| A 保存した判定と `decide_word` の再計算の差 | 0 |
| B `role_distribution`／`slot` だけで決まった語 | 0 |
| C `gen_frame` の格上げ（語数） | 48 |
| C 　うち登録した条件を破る語 | 0 |
| C 　うち票を出した分布の腕がすべて codex の出所の語 | 30 |
| D `gen_frame` で `estimated` の語（語数） | 4740 |
| D 　うち規則では格上げされるはずだった語 | 0 |
| E 述語の見出し語をすべて問い合わせた数 | 11141 |
| E 　不変条件を破る答え | 0 |
| E 　`frame_status` の分布 | CONFIRMED 48, ESTIMATED 5618, NOT_CONFIRMED 2581, NOT_PREDICATE 11, NO_ANSWER 2883 |
<!-- END table:w3a3_audit -->

**Q7**（全体テスト。`pytest_full.txt` の最後の行: `116 failed, 10276 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 295.86s (0:04:55)`）: 基線の失敗 114 件、今回の失敗 116 件、基線に無い失敗 2 件（`new_failures.txt`）。

### 12.15.9 slot（時・場所・数量）の確かめと、確認済みの答えの例

出典: `dev_time_place.txt`（`dev_time_place.py`、配置 d2、dev の語彙だけ）。**登録した設定では、dev の時の語で slot により direct になった語は無かった**。チケットの「`昨日` のような語が direct になる」は、登録した設定では満たせなかった（理由は `DECISIONS.md` D4-2: dev の時の語は過去の述語と使われる数が閾値に届かない）。

<!-- BEGIN table:w3a3_slot -->
| 項目 | 値 |
|---|---|
| dev の語彙のうち時・場所・数量の型を正解に持つ語（種を除く） | 167 |
| slot の行を外した判定で direct の語 | 86 |
| 登録した設定で direct の語 | 87 |
| slot の行で direct になった語 | 1 |
| 　うち正答・誤決定 | 1・0 |
<!-- END table:w3a3_slot -->

高頻度の過去の時の語 `昨日`（dev の語彙には無い。入口に直接問い合わせた）: `{"state": "DECIDED", "origin": "estimated", "estimate_basis": "generated", "top": ["TIME"], "decided_by": ["gen_definition"], "frame_status": "ESTIMATED"}`。保存された evidence の slot の行（出所・数・名詞の使用数・割合）: [('codex:general_qa', 2, 157, '1.3%'), ('codex:paraphrase_entail', 364, 4110, '8.9%'), ('jawiki', 1, 52, '1.9%')]。
設定を変えたのではなく、保存された evidence を別の `slot_share_pct` で決め直しただけの診断（登録の格子は 30 / 20 / 10）: 30 → DECIDED estimated TIME、10 → DECIDED estimated TIME、8 → DECIDED direct TIME、5 → DECIDED direct TIME。dev の語彙にはこの種の語が無く、dev の数で格子の下側を選ぶことはできない。dev の標本を足して設定を選び直すことはしなかった。

確認済みの述語の答えの例（r6/run1。`p7_lend_check_r6.txt`。契約の形の確認用で、語の一覧ではない）:

```
{
 "term": "うたう",
 "state": "DECIDED",
 "origin": "direct",
 "top": [
  "P_COMMUNICATE"
 ],
 "decided_by": [
  "gen_frame",
  "role_distribution@codex:general_qa",
  "role_distribution@codex:narrative",
  "role_distribution@jawiki"
 ],
 "generated_frame": true,
 "frame_status": "CONFIRMED",
 "frame": {
  "を": [
   "INFO_LANGUAGE",
   "WORK"
  ]
 },
 "frame_unconfirmed": {
  "で": [
   "PLACE"
  ]
 }
}
```

### 12.15.10 既知の穴・満たせないもの・読解器への申し送り（隠さない）

- **Q6 は配置の側では動かない**。`PLACEMENT_PREDICATE_UNIDENTIFIED` を出すのは `origin/integ-w3b1:verantyx/semantic_read.py` の 760 行目だけで、**英語の入力**で、どの語も既知の動詞の閉じた一覧に無いときに、配置を一度も問い合わせずに足される理由である（`_read_en`、758〜760 行）。日本語の経路にこの理由は無い。この ticket の許可パス（配置の側）の変更では、その件数は原理的に変わらない。英語の述語は置いていない・読解器には触れていない。Q6 は満たせないものとして監査役に返す。
- **直接になる述語の型は 2 型だけ**。K62 の表は `P_MOVE` と `P_COMMUNICATE` の 2 型・9 行だけで、逆引きの分布の腕はこの 2 型しか票にできない。ほかの 11 型の述語は、生成だけ → `estimated(generated)` に留まる（規則どおり。表は広げていない。広げる提案は、表の行を増やす変更が読解器の誤読を増やさないことを W3-b1 の側で測ってからにすること）。
- **再現率は低い**: K62 の `P_MOVE` に に+PLACE の行は無いので、に+PLACE が有意な移動の動詞は (a)(b) で候補にならない。と・まで・より は表に無いので候補に効かない。分布の腕は隣接する項だけを数え（長距離は数えない）、型の分かった充填物は段 1 で direct に置いた語に限るので、項の約半分は型なし（§12.15.4）。
- **W3-b1 の門 4 を `gen_frame` は通る**: 門 4 は `'gen_definition' in decided_by` の文字列だけを見る。述語の生成の腕を別の名前（`gen_frame`）にしたので、格上げした述語は門 4 を通る（読解器が direct として使いうる）。これは読解器の方針の変更に当たるので、答えに `generated_frame: true` を付けて機械的に区別できるようにした。読解器が使うかは W3-b2 で決める。`slot` で direct になった名詞は `decided_by` に必ず `gen_definition` が入り、門 4 に当たる（仕様どおり）。
- **codex が書いた枠と codex が書いたコーパスの一致**: 格上げ 48 語のうち 30 語は、票を出した分布の腕がすべて codex コーパスの出所（jawiki 無し）。生成した枠と生成したコーパスの一致であり、人が書いた出所の証拠ではない（`origin=direct` の意味は W3-a2 から変わらない: 生成でない腕が自分の閾値で合意した）。
- **`frame` は報告用**: 読解器の変更は W3-b2。K62 の表は固定のまま、配置の `frame` と一致する範囲でだけ使う（表に無い助詞は読まない）。この ticket では契約と欄だけ。
- **封筒のような名詞**: 名詞の生成は W3-a2 の物をそのまま使った（作り直していない）。上位語が型に通らず `no_type` になった名詞は残る。
- **断片の動詞**（語にならないもの）は材料にあるので生成の一覧に入りうる。モデルが型を返せば `estimated(generated)` になり、「分からない語で型を返す」に数える（一覧から手で除いていない）。
- **`昨日` のような過去の時の語は、登録した設定では direct にならなかった**（§12.15.9。`slot_share_pct` が 8 以下なら direct になるが、dev の語彙にはこの種の語が無く、dev の数では下側を選べなかった）。チケットの「やること 4」の小項目は満たせていない。
- `frame_decides=False` の判断は dev の小さい標本（決め手が `frame` の語 23 語）に基づく。W3-a の凍結データの数字（決め手の 18 語のうち正答 2・誤決定 11）は根拠にしていない。
- 検査データ（動詞 300 語・dev 150 語）は自作で、型は手で付けた。自作のデータで通ることは証拠にならない（隠しバンクと中間職の 100 語で測る）。
<!-- w3a3-measure:end -->

> **統合の注記（監査役、2026-10-03）**: W5-b の `spelling` と W3-a3 の `frame_status`/`frame` はどちらも「答えの最後」に足されたので、統合後の順は 既存の鍵 → `generated_frame` の前に `spelling` → `frame_status` → `frame`（→ `frame_unconfirmed`）とする。値は変えていない。

## 13. W5-d: 述語の枠の確認を「助詞ごとの型の一致」にする（事前登録）
<!-- w5d-prereg:begin -->
事前登録の時刻: 2026-10-03 23:07:22 +0900（`date '+%F %T %z'` の出力）。§12.10 の `frame_status` の意味の追記であり、§12 の区間（`w3a3-prereg`・`w3a3-measure`）の中は変えない。

- **P-J1**: 述語の型を direct にする条件（§12.6、`coarse_types._apply_gen_frame`）は変えない（`coarse_types.py` は許可パスの外）。変えるのは枠の確認（`frame_status == CONFIRMED` と `frame` を出す条件）だけ。結果として `命じる` は `DECIDED`・`direct`・`P_COMMUNICATE`・`generated_frame: true` のまま `frame_status: NOT_CONFIRMED`・`frame: null` になる。
- **P-J2 条件**: 格上げに加わった `role_distribution` の腕それぞれについて、`coarse_types.rd_analyze(その腕の数, cfg, base)["types"]` の各助詞 p（有意な型が空でないもの）と、生成の枠の p の型（`gen_frame_slot`）を比べる。生成の枠に p があり、両者の型の集合が交わらない → その助詞は矛盾。矛盾が 1 つでもあれば `NOT_CONFIRMED`。分布に有意な型が無い助詞・生成の枠に無い助詞は矛盾に数えない。「一致」を交わりで取る理由: チケットの文言は「矛盾する助詞」で、攻撃役の定義と同じ。包含・等号は r6 の 48 語のうち 43 語を外す（`frame_defs.py` の実測）。
- **P-J3 形**: 判定は `coarse_place.py` の純粋関数 1 つ（`frame_type_disagreement`）にまとめ、問い合わせ（`_direct`）と builder の数えの両方が呼ぶ。矛盾があるとき `frame`・`frame_unconfirmed` を出さず `frame_status = NOT_CONFIRMED`、答えの最後に `frame_disagreement` を足す（矛盾が無い答えには鍵を出さない）。`query()` の末尾の並びは `spelling` → `frame_status` → `frame`（→ `frame_unconfirmed` | `frame_disagreement`）。
- **P-J4 builder**: 配置の表は変えない。manifest の `generated_frames.outcomes` に `frame_confirmed`・`frame_types_disagree` を足すだけ。したがって r7 の `content_sha256` は r6 と同じになるはず（`5c969d45…`）。違えば止めて調べる。
- **P-J5 r7**: codex を呼ばない。r6 と同じ入力で cache なしで 2 回（`/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1`・`run2`）。`r6` には何も書かない。

### 宣言する規則どうしの衝突（実装役は解かずに宣言する。判断は監査役）
チケットの規則を字面どおりに入れると、旧い振る舞いをそのまま固定した既存テストが落ちる。実装役はチケットの規則どおりに作り、テストの期待は変えず（改訂が許された 1 関数を除く）、落ちた id を全部宣言する。

| # | 衝突 | 落ちる見込みのもの |
|---|---|---|
| K1 | W3-c2「型を確かめられない充填物は候補から外す」 × 配置なしで FILLED/TIE を期待する既存テスト・攻撃の外れ | `tests/test_question_cross_observe.py` の一部、攻撃の写しの 2 件 |
| K2 | R1「配置が無い日本語の名前は命名の文で導入されたものだけ」 × 配置なし（スタブ）の名前で振る既存テスト・R2 の攻撃テスト | `tests/test_routing_from_text*.py` の多数、攻撃の写しの R2 の 1 件 |
| K3 | A1「出典の本文が渡した文書の中にある」 × 存在しない文書を渡して `family: document` を人とする既存テスト | `tests/test_basis_policy_form.py`・`tests/test_basis_policy_w5c_r3.py` の一部 |
| K4 | D1「文面が同じときだけ格上げ」 × 別の文の記録で格上げすることを固定した既存テスト（改訂許可の 2 件の外） | `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer` |
| K5 | W3-a3 A1「枠の確認は助詞ごとの型の一致」 × 攻撃の写しの不変条件「gen_frame の格上げ語は全部 CONFIRMED」 | `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` |
| D1-改訂 | 許可された 2 件のうち設計上落ちる 1 件 | `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`（名前不変で改訂。前後の全文は BASIS_POLICY の測定の節） |

### 受入基準の測り方（G1〜G7。測る前に固定）
- G1: 攻撃の写し 5 本（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）。落ちてよいのは宣言した K1(2)・K2(1)・K5(1) の 4 id だけ。A02・R2・W3-a3 A1 は新しいテストで確かめる。
- G2: `artifacts/w5-d/scripts/run_questions_both.py`（実装役の 185 問、配置あり／なし）。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。正答の減少は変更前（`artifacts/w5-d/before/q185_*.json`）との差を数で。
- G3: 経路づけの凍結 4 本（`run_bank.py`、配置なし・r7）の misroutes と、自作の合成（`artifacts/w5-d/g3_synth/`、入力と期待を先に書き sha256 を凍結）。
- G4: `artifacts/w5-d/scripts/g4_probe.py`（入力を先に凍結）。自己申告の文書・文面違いの確認記録から `ANSWER_*` が 0。対照（本当に渡した文書の文・完全一致の記録）では答えが出ること。
- G5: r7 を cache なしで 2 回作り `verify` が両方 OK、`content_sha256` が run1 = run2 = r6（`5c969d45…`）。L1〜L3・動詞 300 語を `measure_w5d.py` で r6 と r7 で測り同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線 `dev_c875ed3_failures.txt` から増えない。増えた分は 1 件ずつ K1〜K5 または環境由来に当てる。当たらないものはコードを直す。
- 基線（変更前）の測定は `artifacts/w5-d/before/` に保存済み（この事前登録より前）。製品コードの差分はこの時点で空。

<!-- w5d-prereg:end -->

## 13.x W5-d の測定: 述語の枠の確認
<!-- w5d-measured:begin -->

測定の時刻: 2026-10-03 23:34:53 +0900。出典はすべて `artifacts/w5-d/` のファイル（下に名前を書く）。全体テスト: `pytest_full.txt` の最終行 `198 failed, 11889 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 341.39s (0:05:41)`。基線 `dev_c875ed3_failures.txt` に無い新しい失敗は 83 件（`new_failures.txt`）で、1 件ずつ `new_failures_explained.txt` に K1〜K5・改訂・環境由来のどれかを書いた。どれにも当たらないものは 0 件（`grep -v -E 'K[1-5]|D1-改訂|環境由来' new_failures_explained.txt` が空）。基線から直った失敗は 0 件（`fixed_failures.txt`）。

### 配置 r7（G5。`q5_determinism_r7.txt`・`g5_compare.txt`・`r6_query_after.txt`・`r7_inputs.sha256`）
- r7 を codex なし・cache なしで 2 回作った（`scripts/run_full_r7.sh`、ログ `build_full_r7_run1.log`・`build_full_r7_run2.log`）。`verify` は両方 `state OK`。`content_sha256` は run1 = run2 = r6/run1 = `5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1`。表は変わっていない（枠の確認は問い合わせの規則と manifest の数えだけ）。manifest の `generated_frames.outcomes`: `decided_direct_upgrade` 48 = `frame_confirmed` 35 ＋ `frame_types_disagree` 13。`excluded_terms_total` は 359（r6 と同じ）。
- r6 に新しい `query()` を当てても CONFIRMED 35・NOT_CONFIRMED 13（`r6_query_after.txt`。`うたう たたえる みせる 交わす 命じる 問い合わせる 潜める 示せる 薦める 見せ合う 言い換える 訴える 謳う` の 13 語は攻撃役の 13 語と一致、独立の再計算 `frame_defs.py` の式と一致）。`命じる` は `DECIDED`・`direct`・`P_COMMUNICATE`・`generated_frame: true` のまま `frame_status: NOT_CONFIRMED`・`frame: null`・`frame_disagreement: {"を": {"generated": ["GROUP_ORG","PERSON"], "distribution": {"role_distribution@jawiki": ["EVENT_ACT"]}}}`。
- 悪化なし（`g5_compare.txt`）: L1・L2・L3・動詞 300 語を r6（変更前のコード）と r7 で測り、`items.jsonl` は byte 一致、`summary.json` は出所の欄（builder の sha・配置のパス・時刻）を除いて一致。動詞 300 語: direct の誤決定 1・direct 5・型を返す率 0.0238（未知語）は r6 と同じ。述語の型の決定は変えていない。凍結 300 語は `verb_check_300.jsonl`。中間職の 100 語（`W3-a3/mid_frozen`）は実装役は開いていない。
- `tests/attack/w3a3/test_w5d_r7_frame_types.py`（r7 の路を固定。skip しない）5 件が通る。

### 宣言した衝突 K5（攻撃の写し）の実際の失敗 id
- `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`: 落ち方は `invariant_errors` に 13 語（`frame_status` が NOT_CONFIRMED）、`byte_differences` は空（`k5_check.txt`）。

### §12.10 の `frame_status` の意味の追記（§12 の区間は変えていない）
`CONFIRMED` は「生成の枠が分布に裏づけられ、**かつ**どの助詞も分布の有意な型と矛盾しない」。矛盾する助詞が 1 つでもある述語は `NOT_CONFIRMED`（述語の型は変えない）で、答えの最後に `frame_disagreement`。`query()` の末尾の鍵の並びは `spelling`（あれば）→ `generated_frame` → `frame_status` → `frame` →（`frame_unconfirmed` | `frame_disagreement`）。

### 既知の穴（隠さない）
1. 「一致」を交わりで取ったので、生成の枠が分布の型と**交わるが一部の型は分布に裏づけられない**枠は `CONFIRMED` に残る（r6 の 48 語のうち 43 − 13 = 30 語。`frame_defs_r6.txt`: 交わらない 13・生成の型が分布の型の部分集合でない 43・集合が等しくない 43。包含・等号を要求すると 48 語のうち 43 語が外れるため、より厳しい規則にはしなかった）。
2. 述語の型の決定（§12.6）は変えていない（`coarse_types.py` は許可パスの外）ので、`命じる` は `P_COMMUNICATE` の direct のまま（枠だけが未確認）。
3. r7 の manifest の `coarse_types_sha256` は r6 と違う（基点の dev の `coarse_types.py` が r6 を作った木のものと違うため。`coarse_types.py` は変更していない。`content_sha256` は同じ）。

<!-- w5d-measured:end -->

## W5-d 第 2 ラウンド（W5-d2）の事前登録
<!-- w5d2-prereg:begin -->
事前登録の時刻: 2026-10-04 00:31:06 +0900（`date '+%F %T %z'` の出力。第 2 ラウンドの製品コード・テストの変更より前）。ベースは `dev` = `c875ed3`。第 1 ラウンドの `w5d-prereg`・`w5d-measured` 区間は 1 文字も変えない（第 1 ラウンドの記録）。この節が置き換えるものは、後ろの `w5d2-measured` 区間の「置き換わった記述」に列挙する。

**監査役の裁定（2026-10-04 00:05）**: B1 規則の衝突で落ちる既存テスト 78 件＋攻撃の写し 4 件は改訂を許可（K1・K2 は偽の `PlacementLookup` の注入、K3・K4・K5 は期待の改訂。名前は変えず、前後の全文を docs に）。B2 D1 の比較は正規化しない完全一致を追認（チケットの文言「NFKC 正規化後」は撤回）。B3 `recompute_q.py --check` と `w3c2-entry` 区間の例は、配置を与えた例に取り直してよい（区間の規則の本文は変えない）。追加 9 質問の観測が `VERA_PLACEMENT` を読まないのは、この後では「本番では質問がほぼ全部棄権」を意味するので、`observe.py` の question の経路で、`--placement` が無く `VERA_PLACEMENT` があるときは `event_cross.default_lookup()` の lookup を使う（収まらなければ既知の穴として次のチケットへ）。

**第 2 ラウンドの判断（中間職の指示書 D2-1〜D2-8）**
- D2-1 K1（質問の十字 15 件）: 配置の JSON（穴の充填物だけに direct の型。穴の型と食い違う型は付けない）または `O.FilePlacement` を注入する。例外 1 件（`test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun`）は「配置なしで FILLED」が主題で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂。配置あり／なしの対のテストを足す。
- D2-2 K2（自由文→記録 52 件）: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型）を注入。配置なしが主題の 3 件は期待を新しい契約（配置なし → 棄権）に改訂。**裁定の申し送り（並列の名前の過剰棄権は直さず既知の穴）からの逸脱**: 偽の配置（全語 UNPLACED）を注入しても 11 件は `ハルとセキは同じ会社だ。` の部分名 `ハル`・`セキ` に配置の答えが無く `NAME_UNVERIFIED` → `INCOMPLETE_READING` で通らない。期待を書き換えれば「弱体化」になるので、`routing_from_text.py` だけで、日本語の並列の充填物の部分名それぞれを同じ lookup に問う（R-J1 の同じ規則を部分名の配置の答えに当てるだけ。新しい規則は足さない。英語は変えない）。配置が無ければ今どおり `NAME_UNVERIFIED`。
- D2-3 K3（10 件）: 期待の値は変えず、渡した文書を実在させる（`tmp_path` の `memo.txt` に出典の `text` を書く）。K4: `artifacts/w5-d/k4_proposal.diff` をそのまま当てる。K5: 48 語の導出・バイト一致・各条件は不変、`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`（後者は `frame is None`・`frame_disagreement`・助詞ごとの型が交わらない）、数は assert せず出力に一覧。
- D2-4 攻撃の写し 3 本の先頭行を `revised in W5-d2` に。G1-b は「先頭行と改訂した関数を除いて同一」。`data/` は同一。
- D2-5 D1: コードは変えない（正規化しない完全一致）。BASIS_POLICY に追認の理由を書く。
- D2-6 B3: `recompute_q.py` の `EXAMPLES` を 4 つ組（期待, 文書, 問い, 配置ファイル名）にし、`QD02`『どの人が客に切符を渡した？』（FILLED）と `QD01`『誰が生徒に地図を渡した？』（TIE）を `placement_q.json` つきに、`NO_ATTESTED_CELL` の例は今のまま。`--write` は 1 回だけ。凍結データは変えない。
- D2-7 追加 9: 製品の変更は `observe.py` の `_observe_question` の中だけ。`--placement` が無い（`StubLookup`）ときだけ `EC.default_lookup()`。充填物の型の確かめは同じ lookup に `surface` を問い直した答え。出力の `structure.placement` は実際に使った lookup の id。新しい鍵は足さない。**門**（どれか 1 つでも破れたらこの変更だけを戻して既知の穴に書く）: (1) r7 で 185 問の誤答 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない、(2) `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドと byte 一致、(3) 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なしと r7 の 2 通り）。FALSE_NONE の増分と TIE が FILLED に縮む件は数えて書くが門にしない。
- D2-8 置き場所: 本区間（事前登録）、`w5d2-measured`（測定）、`w5d2-amended`（改訂したテストの前後の全文。`artifacts/w5-d/r2/scripts/amended_texts.py` で生成）。K1・B3・D2-7 → OBSERVATION、K2・D2-2 → ROUTING_FROM_TEXT、K3・K4・D1 → BASIS_POLICY、K5 → COARSE_PLACEMENT、EVENT_CROSS には穴の型の節への 1 段落。

**測り方（測る前に固定。出力はすべて `artifacts/w5-d/r2/`）**
- G1: 攻撃の写し 36 本が全部通る（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）、K の 82 id が全部通る、G1-b は上のとおり。
- G2: 実装役の 185 問を（配置なしの環境 × place/noplace）と（`VERA_PLACEMENT=r7` × place/noplace）、攻撃 120 問を r7 で。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。
- G3: 経路づけの凍結 4 本（配置なし）と 2 本（r7）の misroutes 0、合成 `g3_synth` を同じ入力で流し直して配置なしで誤って振った数 0。r7 は第 1 ラウンドの 1 から増えない。D2-2 の影響として r7 の 2 本の単位ごとの状態を第 1 ラウンドと比べる。
- G4: `g4_probe` の写しを流し、入力の sha256 と `summary` が第 1 ラウンドと同じ（`basis_policy.py` は第 2 ラウンドで変えない）。
- G5: r7 は作り直さない。`verify` が `OK`、`content_sha256` が第 1 ラウンドと同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線から増えない。基線に無い失敗は環境由来だけ。K の id が残れば改訂を見直す。

**この文書の担当**: K5（攻撃の写し `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`）。r7・r6・`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えない。
<!-- w5d2-prereg:end -->

<!-- w5d2-amended:begin -->
#### `tests/attack/w3a3/test_attack_w3a3_r6.py` (before = the attack original attacks/W3-a3/test_attack_w3a3.py (first line dropped))

Added (helpers / tests, not amendments): none

##### `test_all_r6_generated_frame_upgrades` — before

```python
def test_all_r6_generated_frame_upgrades():
    pl, why = cp._open(PLACEMENT)
    assert pl is not None, why
    rows = pl.con.execute(
        "SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word"
    ).fetchall()
    words = [row[0] for row in rows]
    assert len(words) == 48

    results, frame_conflicts, invariant_errors, byte_diffs = [], [], [], []
    for word in words:
        answer = cp.query(word, placement=PLACEMENT)
        again = cp.query(word, placement=PLACEMENT)
        if _json_bytes(answer) != _json_bytes(again):
            byte_diffs.append(word)
        results.append(answer)

        if not (answer["state"] == "DECIDED" and answer["origin"] == "direct"
                and answer.get("generated_frame") is True
                and answer["frame_status"] == "CONFIRMED"
                and answer["namespace"] == "P" and answer["top"]):
            invariant_errors.append({"word": word, "answer": answer})
            continue

        gf = pl.generated_frame(word)
        generated = gf[5] if gf else {}
        if not gf or gf[4] != answer["top"][0]:
            invariant_errors.append({"word": word, "reason": "generated_type_differs",
                                     "generated_type": gf[4] if gf else None,
                                     "answer_top": answer["top"]})
        sig_particles, typed_sig = set(), []
        for key, arm in answer["axes"].items():
            if not key.startswith("role_distribution@") or not arm["met"]:
                continue
            raw = [r for r in pl.evidence(word)
                   if r[0] == "role_distribution" and key.endswith("@" + r[1])]
            counts = {r[2]: r[3] for r in raw}
            base = raw[0][4] if raw else None
            analysis = ct.rd_analyze(counts, pl.cfg, base)
            sig_particles.update(analysis["sig"])
            typed_sig.append((key, analysis["types"]))
            if ct.arm_verdict("role_distribution", counts, pl.cfg, base) != answer["top"]:
                invariant_errors.append({"word": word, "arm": key, "reason": "arm_top_differs"})

        expected = {p: sorted(set(generated.get(p, []))) for p in ct.ROLE_PARTICLES
                    if p in sig_particles and generated.get(p)}
        if answer["frame"] != expected:
            invariant_errors.append({"word": word, "reason": "frame_projection_differs",
                                     "expected": expected, "got": answer["frame"]})

        for key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                if not dist_types:
                    continue
                frame_types = set(answer["frame"].get(particle, []))
                if not frame_types or not frame_types.intersection(dist_types):
                    frame_conflicts.append({"word": word, "source": key, "particle": particle,
                                            "distribution_types": dist_types,
                                            "confirmed_frame_types": sorted(frame_types)})

    (OUT / "r6_48_queries.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in results),
        encoding="utf-8")
    summary = {"derived_words": len(words), "queried": len(results),
               "byte_differences": byte_diffs, "invariant_errors": invariant_errors,
               "disjoint_slot_conflicts": frame_conflicts}
    (OUT / "r6_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert not byte_diffs
    assert not invariant_errors
    assert not frame_conflicts, "confirmed frame slot types contradict significant distribution types"
```

##### `test_all_r6_generated_frame_upgrades` — after

```python
def test_all_r6_generated_frame_upgrades():
    # W5-d2 (auditor's ruling B1, K5): the invariants follow the rule of W5-d (docs/COARSE_PLACEMENT.md section 13): a predicate that a generated frame placed direct
    # is CONFIRMED only when no particle of the frame contradicts the distribution that backed it; a contradicted one is NOT_CONFIRMED (frame null, the contradiction
    # in frame_disagreement). The derivation of the 48 words, the byte identity of two queries, state/origin/generated_frame/namespace/top, the type of the
    # generated frame, and the verdict of every distribution arm are as they were; the number of NOT_CONFIRMED words is not asserted (it is written to the summary).
    pl, why = cp._open(PLACEMENT)
    assert pl is not None, why
    rows = pl.con.execute(
        "SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word"
    ).fetchall()
    words = [row[0] for row in rows]
    assert len(words) == 48

    results, frame_conflicts, invariant_errors, byte_diffs, not_confirmed = [], [], [], [], []
    for word in words:
        answer = cp.query(word, placement=PLACEMENT)
        again = cp.query(word, placement=PLACEMENT)
        if _json_bytes(answer) != _json_bytes(again):
            byte_diffs.append(word)
        results.append(answer)

        if not (answer["state"] == "DECIDED" and answer["origin"] == "direct"
                and answer.get("generated_frame") is True
                and answer["frame_status"] in ("CONFIRMED", "NOT_CONFIRMED")
                and answer["namespace"] == "P" and answer["top"]):
            invariant_errors.append({"word": word, "answer": answer})
            continue

        gf = pl.generated_frame(word)
        generated = gf[5] if gf else {}
        if not gf or gf[4] != answer["top"][0]:
            invariant_errors.append({"word": word, "reason": "generated_type_differs",
                                     "generated_type": gf[4] if gf else None,
                                     "answer_top": answer["top"]})
        sig_particles, typed_sig = set(), []
        for key, arm in answer["axes"].items():
            if not key.startswith("role_distribution@") or not arm["met"]:
                continue
            raw = [r for r in pl.evidence(word)
                   if r[0] == "role_distribution" and key.endswith("@" + r[1])]
            counts = {r[2]: r[3] for r in raw}
            base = raw[0][4] if raw else None
            analysis = ct.rd_analyze(counts, pl.cfg, base)
            sig_particles.update(analysis["sig"])
            typed_sig.append((key, analysis["types"]))
            if ct.arm_verdict("role_distribution", counts, pl.cfg, base) != answer["top"]:
                invariant_errors.append({"word": word, "arm": key, "reason": "arm_top_differs"})

        if answer["frame_status"] == "NOT_CONFIRMED":
            not_confirmed.append(word)
            disagreement = answer.get("frame_disagreement")
            if answer["frame"] is not None or "frame_unconfirmed" in answer \
                    or not isinstance(disagreement, dict) or not disagreement:
                invariant_errors.append({"word": word, "reason": "not_confirmed_shape", "frame": answer["frame"],
                                         "frame_disagreement": disagreement,
                                         "has_frame_unconfirmed": "frame_unconfirmed" in answer})
                continue
            for particle, entry in disagreement.items():
                gen_types = set(entry.get("generated") or [])
                arms = entry.get("distribution") or {}
                if not gen_types or not arms or any(gen_types & set(dt) for dt in arms.values()):
                    invariant_errors.append({"word": word, "reason": "disagreement_types_meet",
                                             "particle": particle, "entry": entry})
            continue

        expected = {p: sorted(set(generated.get(p, []))) for p in ct.ROLE_PARTICLES
                    if p in sig_particles and generated.get(p)}
        if answer["frame"] != expected:
            invariant_errors.append({"word": word, "reason": "frame_projection_differs",
                                     "expected": expected, "got": answer["frame"]})

        for key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                if not dist_types:
                    continue
                frame_types = set(answer["frame"].get(particle, []))
                if not frame_types or not frame_types.intersection(dist_types):
                    frame_conflicts.append({"word": word, "source": key, "particle": particle,
                                            "distribution_types": dist_types,
                                            "confirmed_frame_types": sorted(frame_types)})

    (OUT / "r6_48_queries.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in results),
        encoding="utf-8")
    summary = {"derived_words": len(words), "queried": len(results),
               "byte_differences": byte_diffs, "invariant_errors": invariant_errors,
               "disjoint_slot_conflicts": frame_conflicts, "not_confirmed": not_confirmed}
    (OUT / "r6_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert not byte_diffs
    assert not invariant_errors
    assert not frame_conflicts, "confirmed frame slot types contradict significant distribution types"
```

<!-- w5d2-amended:end -->

## W5-d 第 2 ラウンド（W5-d2）の測定
<!-- w5d2-measured:begin -->
測定の時刻: 2026-10-04 01:22:30 +0900。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。

**受入基準**（第 2 ラウンド）
- **G1**（`g1_rerun_r2b.txt`）: 攻撃の写し 36 本が `36 passed`、K の 72 関数（82 id）が全部通る（`102 passed`）、新しいテスト（第 1 ラウンドの 5 本＋第 2 ラウンドの追記）が `113 passed`。G1-b: 写しと原本の差は先頭行と改訂した関数・足したヘルパの中だけ（`g1b_hunks.txt`、`attack_copy_revisions.diff`。w5c の 2 本は原本と同一、`data/` も同一）。
- **G2**（`g2_185_*.json(l)`・`g2_attack120_r7.json(l)`・`g2_rerun_r2b.txt`）: `VERA_PLACEMENT` なしの 185 問は第 1 ラウンドの出力と byte 一致（place: 正答/誤答/FALSE_NONE/棄権 = 38 / 0 / 4 / 143、noplace: 26 / 0 / 4 / 155）。`VERA_PLACEMENT=r7`: place 73 / 0 / 6 / 106、noplace 66 / 0 / 8 / 111。誤答 0、型未確認の FILLED/TIE 0（4 通りとも `unchecked_fillers_in_FILLED_TIE` は 0・0・0・0）。正答は減っていない（第 1 ラウンドと同じか、r7 で増える）。攻撃の 120 問（r7、116 問は正解なしで採点されない）: FILLED 29・TIE 5、型未確認の FILLED/TIE 0、`wrong` 0 件。A01（`EN08-01`）は `NO_TYPED_CANDIDATE`（`letter`・`note` は `TYPE_UNCHECKED`）で FILLED/TIE にならない（`g2_r7_notes.txt`）。中間職の凍結 64 問・56 問は実装役が開かない約束なので測っていない（中間職が測る）。
- **G3**（`g3_rerun_r2b.txt`・`g3_*`）: 経路づけの凍結 4 本（配置なし）の misroutes は 0, 0, 0, 0、r7 の 2 本は 0, 0。合成 `g3_synth`（入力の sha256 は `g3_synth_inputs_check.txt` で第 1 ラウンドの凍結と一致）: 配置なし misroutes 0・普通名詞に振った数 0、r7 misroutes 1（第 1 ラウンドと同じ 1 件。`委員会` が推定の GROUP_ORG で通る既知の穴）、基点 1（`g3_synth_results/g3_synth_counts.json`）。D2-2 の影響: r7 の 2 本の 118 件を、D2-2 の呼び出しを外した写しと単位ごとに比べて変化した件数は 0（`g3_r7_diff.txt`）。
- **G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ（自己申告の文書 16 件で `ANSWER` 0、文面違いの確認記録 15 件で `ANSWER` 0・旧文が返った 0、対照は 4/4 と 2/2 で答える）。`verantyx/basis_policy.py` は第 2 ラウンドで変えていない（sha256 が `files_start.sha256` と同じ）。
- **G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は第 1 ラウンドと同じ。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。K5 の写しが通り、r6_audit_summary.json not_confirmed: 13 words; invariant_errors [] byte_differences []、第 1 ラウンドの 13 語と同じ集合（`命じる` を含む）。
- **平叙文の観測**（`q1_observe_cmp_r2b.txt`）: `o1_bytes.py --child` の出力が、配置なしと `VERA_PLACEMENT=r7` の 2 通りとも基点と byte 一致（`same: base vs now` が 2 行。この流しは前の流しとも byte 一致）。
- **G7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `117 failed, 11981 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 362.65s (0:06:02)`。失敗は一意に 117 件、基線に無い失敗は 2 件（`tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`、`tests/test_gen_coarse_evidence.py::test_the_stop_signal_ends_the_run_with_an_interrupted_record`）、基線にあって今は通る失敗は 0 件。基線に無い失敗の理由は `new_failures_explained.txt`（環境由来だけ）。K の id は失敗集合に 0 件。

**K5（攻撃の写し 1 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k3k4k5.txt`）: `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`。48 語の導出・2 回の問い合わせのバイト一致・`state`/`origin`/`generated_frame`/`namespace`/`top` の条件・`generated_type_differs`・`arm_top_differs` は変えていない。`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`: `CONFIRMED` の語は今までどおり `frame_projection_differs`・`frame_conflicts` が空であること。`NOT_CONFIRMED` の語は `frame is None`・`frame_disagreement` が空でない辞書・その各助詞で `generated` と（どれかの腕の）`distribution` の型の集合が交わらないこと・`frame_unconfirmed` の鍵が無いこと（違えば `invariant_errors`）。数（13）は assert せず、出力 `r6_audit_summary.json` の `not_confirmed` に語の一覧を書いた。`assert len(words) == 48` は元のまま。この写しは実行のたびに隣に 3 ファイル（`r6_48_queries.jsonl`・`r6_audit_summary.json`・`state_probes.json`）を書く。最後の実行のものを残してある（sha256: `r6_48_queries.jsonl` 213856af…、`r6_audit_summary.json` 962492c2…、`state_probes.json` c27484e4…）。

**G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は `5c969d454b39d39ac0e394191b5e985b4e0a10099591bb7b12fcc559e7d77ff1`（第 1 ラウンドと同じ）。`r6_audit_summary.json not_confirmed: 13 words; invariant_errors [] byte_differences []`、第 1 ラウンドの `r6_query_after.txt` の 13 語と同じ集合。`NOT_CONFIRMED` の 13 語は `うたう`・`たたえる`・`みせる`・`交わす`・`命じる`・`問い合わせる`・`潜める`・`示せる`・`薦める`・`見せ合う`・`言い換える`・`訴える`・`謳う`。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。

**第 2 ラウンドで置き換わった第 1 ラウンドの記述**（第 1 ラウンドの `w5d-*` 区間の中は 1 文字も変えていない。元の行は残し、この一覧が上書きする）
- 「K5 は宣言した衝突（攻撃の写し 1 件）」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。第 1 ラウンドの記述の `frame_status` は全部 `CONFIRMED` という不変条件は、`CONFIRMED` か `NOT_CONFIRMED` に置き換わった。
**この文書の担当の測定は上のとおり。全体の受入と判断は `artifacts/w5-d/DECISIONS.md` の「第 2 ラウンド（W5-d2）」と `artifacts/w5-d/r2/`。**
<!-- w5d2-measured:end -->

## 12.17 W3-a4: サ変の述語・枠の助詞の包含・配置 r8（事前登録と測定）
<!-- w3a4-prereg:begin -->
登録日時: `artifacts/w3-a4/prereg_time.txt` の 1 行目から 2 行目の間（`date '+%F %T %z'` の出力。この区間はその間に書いた）。この時点で製品コード（`verantyx/`・`tools/`）と試験（`tests/`）の差分は 0（手順 1 の確かめ: `git diff --stat -- verantyx tools tests` が空）。この区間に **語の一覧は無い**（規則・設定の名前・測り方だけ）。出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-a4/plan.md`（チケット W3-a4）。

### 12.17.1 規則（D1〜D8）
- **D1 サ変の述語の使用の数え（`analyze`）**: 形態素列で「普通名詞（pos2 が普通名詞）＋ する の動詞」を 1 つの述語の使用とし、見出し語は `<名詞の表記（原形）>する`（辞書形。名前空間は P）。辞書の細かい分類（pos3）は読まない（既存の試験が製品のコードの `pos3` を禁じる。原則「辞書の細かいラベルを使わない」）。`する` 自体の使用は今までどおり数えない。名詞側（`occ`・`is_sahen`・`sahen`・`pos[(w,"N")]`）は 1 か所も変えない（名詞の型は変えない）。「Nをする」・名詞的接尾辞で終わる連続は今までどおり。受身・使役（`される`・`させる`）も `する` のトークンがあるので同じ見出し語の使用に数える。
- **D2 サ変の連なり（`_chain_count`）**: 名詞の連続の直後が `する` のとき `chain_skips["sahen"]` は今までどおり数え（漏斗の和を r7 と比べられる）、その上で新しい数え `acc["chain_sahen"]` に `(フィラー, 項の表記, 助詞, 述語の見出し語, 過去か)` を入れる。`acc["chain"]` には入れない。内訳は `acc["sahen_chain_skips"]`（`no_common_noun`・`too_long`・`voice`・`counted`）。不変条件: 出所ごとに `sum(sahen_chain_skips.values()) == chain_skips["sahen"]`。名詞＋できる は今までどおり（できる の使用）で、既知の穴として宣言する（辞書の細かい分類を読まないので `確認できる` と助詞の省略の `日本語できる` を区別できない）。
- **D3 段 2（`_stage2`）**: 出所ごとに `chain` と `chain_sahen` の両方を同じ本体で読む（辞書は足し合わせない）。サ変の述語は分布の腕 `role_distribution@<出所>` を持つ。名詞の `slot` の TIME と基準率にもサ変の連なりが入り得る（名詞の判定が動き得る。測る: (d)）。
- **D4 抽出の cache と manifest**: `_empty_acc` に `chain_sahen`・`sahen_chain_skips`・`sahen_verb`。古い cache は同じ `STAGE_CACHE_STALE`・終了コード 4（新しい鍵の検査は既存の検査の後ろ）。manifest に `argument_chains.sahen_by_reason`・`argument_chains.sahen_verbs`。
- **D5 包含の規則（`coarse_types._apply_gen_frame` の包含だけ）**: 設定 `frame_cover_rule` ∈ {`all9`（既定。r5〜r7 の規則）, `he_by_ni_place`, `k62_he_by_ni_place`}。`all9` は腕の有意な助詞（9 種）がすべて生成の枠にあること。`he_by_ni_place` は同じだが「へ が生成の枠に無く `に|PLACE` の行がある」ときは へ を要求しない。`k62_he_by_ni_place` は有意な助詞のうち K62 の 6 助詞（が を に で へ から。`k62_particles()` から導く）だけを要求し、へ は同じ扱い。と・まで・より は K62 に無く、候補判定に使わない助詞である。既定を `all9` にするのは、既定を替えると r7 に問い合わせた答え（保存された evidence から判定を計算し直す）の `origin` が変わり、P1 に反するため。`K62_FRAMES`・閾値・`decide_word` の本体は触らない。r8 の設定ファイルだけが新しい値を持つ。
- **`frame_cover_rule` の選び方（事前登録）**: 既定は `k62_he_by_ni_place`（チケットの規則）。r7 の evidence で規則を適用して direct になる語（r7 では direct でない）を全件目視し、「明らかな誤り ÷ 語数」が 0.2 を超えたら `he_by_ni_place` に狭め、それでも超えたら `all9` に戻して P3 を満たせないものとして報告する。選んだ値は r8 を作る前に決めて凍結する（`config_w3a4.json`・`config_w3a4.sha256`）。`rd_*` の値は変えない（`rd_min_sources 1`・`rd_min_total 20`・`rd_particle_min 10`・`rd_particle_share_pct 30`・`rd_type_share_pct 50`・`rd_store_min 20`）。
- **覆われたとみなした へ の扱い**: `coarse_place.py` は触らない（契約を変えない）ので、覆われた へ は `frame_unconfirmed` に出ない。`frame` は今までどおり生成の枠の助詞からだけ作られるので「`frame` に生成の枠に無い助詞を入れない」は自動で満たされる。これは §12.10 の不変条件の確認（r8 の全数）で測り、へ を覆った語の数は manifest の `generated_frames.outcomes` に出す。既知の穴として宣言する。
- **D6 生成の一覧**: `tools/gen_coarse_evidence.py needs --sahen-min-uses N --exclude-frames PATH`（新しい引数）。語 w の出所ごとの `sahen_verb` の使用の最大（出所をまたいで足さない）が N 以上、配置の見出し語にあり、名前空間が P か NP で、状態が UNPLACED か MULTIPLE で、除外の枠（棄権の行も）に無い語。N は `rd_min_total`（20）。プロンプト・schema・束の形式・台帳の形・モデル（`gpt-6-luna`）・effort（`low`）は W3-a3 と同じ。
- **D7 生成の枠を 2 本読む**: `--generated-frames-add`・`--generated-frames-add-ledger`。2 本に同じ語があれば何も書かず `GENERATED_FRAMES_OVERLAP`・終了コード 5。manifest の `generated_frames` に `parts`（2 本のとき）。無いときは manifest の形も中身も今と同じ。
- **D8 r7 との差**: `--compare-to DIR`（読み取りのみ）。manifest の `compare_to` に headwords・ctx・generated_frames・outcomes の差。

### 12.17.2 受入基準の測り方（P1〜P7・(a)〜(d)）
- **P1**: 基点のコードと変更後のコードで、r7/run1 の `coarse_place.query` の出力（鍵の並びを含む JSON 文字列の sha256）を、`gen_frame` か `role_distribution` の行を持つ語の全部、残りの見出し語の無作為 10,000 語（`random.Random(20261004)`）、名詞 5 語で取って比べる（`artifacts/w3-a4/p1/r7_before.tsv` と `r7_after.tsv` の `cmp`）。`frame_status` が変わった語は全件列挙（期待 0）。反実仮想（既定を新しい規則にした場合に r7 の答えが変わる語）は別に記録する。
- **P2**: r8/run1 で 5 つのサ変の述語が ns=P の見出し語で、使用の数と項の分布（`role_distribution` の行）を持つこと（`p2_words.txt`）。`DECIDED` は求めない。
- **P3**: 包含の修正で direct になった語の全件を目視。明らかな誤り ÷ 語数 ≤ 0.2。direct から外れた語も全件列挙（期待 0）。
- **P4・(c)**: seed 281 語の (ns, state, origin, top, by) が r7 と同じ。違う語は全件列挙し理由を書く。
- **P5・(a)**: サ変の述語のうち、頻度上位 30（30 番目と同じ使用数の語は全部入れる）と、残りからの `random.Random(20261004).sample(sorted(残り), 30)` の 30 語の判定を目視して表にし、`direct` になった語（無作為標本の分母は direct の全部。200 語超なら `random.Random(20261005).sample(sorted(全部), 200)`）の型の正しさ（正しい ÷ 分母 ≥ 0.8。疑わしい は正しいに数えない）を数える。下回れば `sahen_upgrade=false`（サ変の述語は `estimated(generated)` 止まり）を既定にして記録する。**目視は実装役の読みで、正解データではない**。表は集計の前に sha256 を取る。
- **P6**: 監査役が隠しバンク B1 で測る（実装役は開かない）。
- **P7**: 既存テストの失敗集合が基線 `dev_c334fe6_failures.txt` から増えない。r8 の構築の所要時間と生成の費用（呼び出し数・effort）を manifest と `artifacts/w3-a4/` に記録する。
- **(d)**: ns に N を含む見出し語で state・origin・top のどれかが変わった数と上位 20 語（理由は腕の差で示す）。名詞 5 語（サ変の名詞）の行が r7 と同じ。
- **目視の基準**: 判定は 3 つ。正しい（語の最も普通の意味がその型の名称に当てはまり、13 型の中にそれより明らかに当てはまる型が無い）／明らかな誤り（当てはまらない、または別の型のほうが明らかに当てはまる）／疑わしい（言い切れない・多義）。物を場所へ動かす他動詞（使役の移動）は P_MOVE に当てはまるものとして扱う。物の受け渡し（相手に渡る）が主なら P_GIVE がより当てはまる＝明らかな誤り。
- **読解器との接続**（変更しない）: `semantic_read --text=… --placement <r8>` で述語の問い合わせが `coarse_place.query` に届くかを測り、届かなければ理由を既知の穴に書く。

### 12.17.3 §12.6 の包含の規則の変更記録（前の全文・後の全文）
**前**（§12.6「判定」の箇条の格上げの部分）:
> 格上げ（direct）: |R| ≥ `rd_min_sources`、R のすべての腕の票が [T]、かつ R の各腕について「生成の枠の助詞の集合 ⊇ その腕の有意な助詞の集合（9 種全部。と・まで・より を含む）」→ `DECIDED`・`origin=direct`・`decided_by = sorted(R の腕 + ["gen_frame"])`。

**前**（`_apply_gen_frame` の docstring の全文）:
> W3-a3 12.6: the predicate type a model wrote (``gen_frame``) with its frame (``gen_frame_slot`` rows, ``<particle>|<noun type>``).  It places a word nothing else decided as an ESTIMATE (generated).  It becomes DIRECT only when the ``role_distribution`` arms that reached their own threshold (R) (1) are at least ``rd_min_sources``, (2) all vote for exactly the generated type and (3) every significant particle of each of them is a particle of the generated frame.  A vote for another type is ``DISTRIBUTION_DISAGREES`` and a frame that misses a particle is ``FRAME_PARTICLES_NOT_COVERED``: both stay estimates (a split is not made: the distribution never decides on its own, so it is not offered as a candidate).

**後**（規則の文。§12.6 の本文は書き換えず、この追記が上書きする。`frame_cover_rule` の既定は `all9` なので既定の設定ではこの前の文のまま）:
> 格上げ（direct）: |R| ≥ `rd_min_sources`、R のすべての腕の票が [T]、かつ R の各腕について「生成の枠の助詞の集合 ⊇ その腕が要求する助詞の集合」。要求する助詞は設定 `frame_cover_rule` で決まる: `all9`（既定）は有意な助詞 9 種全部、`he_by_ni_place` は 9 種全部（ただし へ が枠に無く に|PLACE の行が枠にあるときは へ を除く）、`k62_he_by_ni_place` は有意な助詞のうち K62 の 6 助詞だけ（へ は同じ扱い）。`all9` 以外で格上げになった語の生成の腕に `cover`（覆った へ を持つ腕・無視した助詞）を付ける。

**後**（docstring の全文）:
> W3-a3 12.6 / W3-a4 12.17: the predicate type a model wrote (``gen_frame``) with its frame (``gen_frame_slot`` rows, ``<particle>|<noun type>``).  It places a word nothing else decided as an ESTIMATE (generated).  It becomes DIRECT only when the ``role_distribution`` arms that reached their own threshold (R) (1) are at least ``rd_min_sources``, (2) all vote for exactly the generated type and (3) every particle each of them needs is a particle of the generated frame.  What an arm needs is set by ``frame_cover_rule``: ``"all9"`` (the default: the rule of r5 to r7) needs every significant particle (the nine case particles); ``"he_by_ni_place"`` needs the same except that the particle he is waived when the frame has no he but has a ni|PLACE row; ``"k62_he_by_ni_place"`` needs only the significant particles that appear in the K62 table, with the same waiver.  A vote for another type is ``DISTRIBUTION_DISAGREES`` and a frame that misses a needed particle is ``FRAME_PARTICLES_NOT_COVERED``: both stay estimates (a split is not made: the distribution never decides on its own, so it is not offered as a candidate).

<!-- w3a4-prereg:end -->

<!-- w3a4-measured:begin -->
### 12.17.4 測定（登録の外。数値は `artifacts/w3-a4/` の測定ファイル。予想は書かない）
測定の時刻と出力はすべて `artifacts/w3-a4/`（ファイル名を添える）。目視の判定は **実装役の読みで、正解データではない**。

**実行の順と時刻**（`prereg_time.txt`・`config_frozen_time.txt`・`*.started`・`*.finished`）: 事前登録 02:12:49 → r7 の答えの「前」（`p1/r7_before.tsv`）→ 包含の切り替えと試験 → P3 の事前評価（目視表の sha256 は集計より先: `p3/judge.sha256.time` 02:15:02）→ 設定の凍結 02:15:10（`config_w3a4.json`、sha256 `73f9381e…3279`）→ サ変の数えの試験 → r8/base 02:23:45〜02:34:26 → 生成の試し 1 束 02:36:05〜02:36:39 → 生成の本番 02:36:46〜02:40:54 → P5 の事前評価（目視表の sha256 は集計より先: `p5/judge.sha256.time` 02:42:13）→ r8/run1 02:42:28〜02:47:03 → 測定 → 全体テスト（`pytest_full.started`〜`pytest_full.finished` 02:56:56）。

**設定**（`config_w3a4.json`）: `config_w3a3.json` の全行 + `"frame_cover_rule": "k62_he_by_ni_place"`。`rd_*` は変えていない（`rd_min_sources 1`・`rd_min_total 20`・`rd_particle_min 10`・`rd_particle_share_pct 30`・`rd_type_share_pct 50`・`rd_store_min 20`）。`frame_cover_rule` の値の選び方は §12.17.1 のとおり: `p3/p3_summary.txt` で `k62_he_by_ni_place` の明らかな誤りが 0/12、`he_by_ni_place` が 0/11 だったので、既定の `k62_he_by_ni_place` のまま。`sahen_upgrade`（D9）は入れていない（P5 が基準を満たしたため）。

**生成**（`gen_plan.txt`・`gen_sahen_summary.json`・`gen_sahen_sha256.txt`・`needs_sahen.meta.json`）: 一覧 3,485 語（出所内の最大の使用が 20 以上のサ変の述語。落ちた理由: 20 未満 10,741・名前空間が述語でない 1・すでに判定済み 8・除外の枠にある 10）。束 88、呼び出し 88 回（失敗 0、上限 264）、effort `low`、モデル `gpt-6-luna`、`wall_sec` 288.0、`sum_call_sec` 2,699.6。回答 3,485 語のうち棄権 243。プロンプトの sha256 `1509fd30…68e2`、schema の sha256 `68551a6a…d882`（`prompt_sha.txt`）は W3-a3 と同じ。`frames.jsonl` sha256 `ff9ddf02…fe50`。

**r8 の中身**（`manifest_r8_base.json`・`manifest_r8_run1.json`・`verify_r8_*.txt` はどちらも `OK`）: r8/run1 `content_sha256` = `89bd07e6c71d883cdeafaa96e906118cbfbc3dc45b1f15f2ce65bbec783382a5`（r8/base は `c1900987c33c6970550a143a69b91ea9d5220cbe1b055c3edac1fd5c0cf2c206`）。見出し語 1,766,903（r7: 1,758,845）、direct 992,779（r7: 992,686）、estimated(generated) 23,552（r7: 20,403）、`generated_frames` 8,030 行（r7: 4,788）、`role_distribution` の行がある語 4,208（r7: 2,441）。連なりの漏斗（出所の合計。`argument_chains`）: 既存の数え counted 15,026,396・chain_broken 9,595,564・voice 761,741・numeral_start 1,007,653・no_filler 49,067・no_verb 48,413・too_many_args 662、サ変 4,025,567（試行の 13.2%）。サ変の内訳（`sahen_by_reason`）: counted 3,501,422・voice 490,369・no_common_noun 33,757・too_long 19（和は 4,025,567 で、出所ごとにも一致: `r8_base_checks.txt`）。サ変の述語の使用の和 5,670,828（出所ごとの語数は `sahen_verbs`）。r7 の manifest と、既存の漏斗の 8 つの数は出所ごとにすべて同じ（`r8_base_checks.txt`）。outcomes（r7 → r8）: decided_direct_upgrade 48 → 130、decided_estimated_generated 4,740 → 7,900、DISTRIBUTION_DISAGREES 743 → 1,243、FRAME_PARTICLES_NOT_COVERED 54 → 54、frame_confirmed 35 → 99、frame_types_disagree 13 → 31、cover_he_by_ni_place 15、cover_ignored_non_k62 1（direct の 130 = 48 + 包含の修正の 12 + サ変の 70）。格上げのうち分布の腕がすべて codex の出所だった語: 30 → 80（`outcomes_before_after`: `diff_r7_r8.txt`）。

**r7 との差**（`diff_r7_r8.txt`・`manifest_r8_run1.json` の `compare_to`）: 増えた語 8,058（すべてサ変の述語。それ以外 0）、消えた語 0。判定が変わった語: P は 15（包含の修正の 12 語 + 既存の述語の見出し語にサ変の数えが加わった 3 語。後者は 3 語とも新しい枠が付いた）、N は 14（state/origin/top が変わった 11・by だけ 3。すべて時の語で、サ変の連なりの `slot` の TIME の数と基準率の変化）。`ctx` の行は 166,701 で、鍵ごとの違いは 0。構築の所要: r8/base（抽出を含む）635.9 秒、r8/run1（抽出は cache、`compare_to` に 8.5 秒を含む）272.5 秒（`timing.txt`・manifest の `duration_sec`・`stage_seconds`）。構築のときの機械の負荷は他の作業のため一定でない（`uptime` は 3〜10）。

**受入基準**
- **P1**（`p1/`）: 基点のコードで取った r7/run1 への問い合わせの出力（15,102 語: `gen_frame`・`role_distribution` の行を持つ語 5,097・無作為の見出し語 10,000・名詞 5）の sha256 が、変更後のコードでも `cmp` で一致（`p1_cmp.txt`: `same`。構築のあとにもう一度取った `r7_final.tsv` とも一致）。`frame_status` が変わった語 0（`frame_status_changed.txt`）。`test_coarse_place_w3a4_r7_unchanged.py`・`tests/attack/w3a3` は `10 passed`（`p1/p1_pytest.txt`）、`tests/attack/w3a3` の差 0。r7・r6 の読み取り専用物の sha256 は全部 OK（`readonly_after.txt`）。反実仮想（既定を新しい規則にした場合に r7 の答えが変わる語）は 12 語で `origin` が変わる（`p1/counterfactual_default_k62.txt`）。既定を `all9` にして設定で切り替えるのはこのため。
- **P2**（`p2_words.txt`）: 5 語とも ns=P、n_seen > 0、`role_distribution` の行あり（`ALL_OK`）。`確認する`: estimated P_COGNITION（n_seen 550,173）、`連絡する`: estimated P_COMMUNICATE（26,307）、`報告する`: direct P_COMMUNICATE（9,136。ただし `frame_status` は `NOT_CONFIRMED`）、`提出する`: estimated P_GIVE（7,873）、`参加する`: estimated P_ACT（14,176）。
- **P3**（`p3/p3_summary.txt`・`p3/p3_actual.tsv`・`p3/p3_diff.txt`）: 包含の修正で direct になった語 12、目視で正しい 8・疑わしい 4・明らかな誤り 0（0/12 = 0.000。基準 ≤ 0.2）。direct から外れた語 0。r7 → r8/run1 で判定が変わった r6 の枠の語は 12 語で、事前評価の一覧とちょうど同じ（i = 12・ii = 0・iii = 0。`diff` は空）。
- **P4・(c)**（`p4_seeds.txt`）: SEEDS_PRED 281 語の (ns, state, origin, top, by) が r7 と違う語は 0。`n_seen` だけが違う語は 1（判定ではない）: 辞書の見出し語 `対する` が 35,929 → 35,930（名詞＋する の「対」＋する が 1 回、サ変の述語の数えで加わった）。
- **P5・(a)**（`p5/p5_summary.txt`・`p5/pre_vs_run1.txt`・`p5/judge.sha256`）: 構築の前の事前評価で direct になったサ変の語は 70 語（全数。型は P_COMMUNICATE 57・P_MOVE 13）。目視で正しい 57・疑わしい 12・明らかな誤り 1（`意味する`）→ 57/70 = 0.8143（基準 ≥ 0.8。**余裕は小さく、疑わしい 12 語の読み方で割れる**）。事前評価の 3,485 語の判定は r8/run1 の見出し語表と全件一致（`pre_vs_run1.txt`: 違い 0）。(a) の 60 語の標本（上位 30 + `random.Random(20261004)` の無作為 30。`p5/sample60.tsv`）は direct が 2 語（どちらも正しい）、estimated(generated) が 57 語（正しい 42・疑わしい 15。門の外の参考）、型が付かなかった語（生成が棄権）が 1 語。
- **(b)**: P3 の表（`p3/cover_k62_he_by_ni_place.tsv`・`p3/judge_k62_he_by_ni_place.tsv`）。
- **(d)**（`d_nouns.txt`）: 名詞（ns に N を含む）の見出し語 1,747,849 のうち state/origin/top が変わった語 11、by だけ変わった語 3。上位はすべて TIME の語（`定刻`・`購入後`・`授業後`・`始業前` …）で、変わった腕は `slot@<出所>`（サ変の連なりが名詞の TIME の数と基準率に入るため）。サ変の名詞 5 語（確認・連絡・報告・提出・参加）の行は r7 と同じ（判定も腕も違いなし）。
- **P7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `117 failed, 12150 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 394.48s (0:06:34)`。基線 115 件に無い失敗は 2 件（`test_s6_two_runs_agree_except_timing_and_recount_matches`・`test_the_stop_signal_ends_the_run_with_an_interrupted_record`。どちらも W5-d2 と同じ環境由来。理由は `new_failures_explained.txt`）。基線にあって今は通る失敗は 0 件。生成の費用: 呼び出し 88 回・effort `low`・`wall_sec` 288.0（`gen_sahen_summary.json`）。既存の試験の行の削除 0（`git diff c334fe6 -- tests/` の `-` の行が 0）。
- **P6**: 実装役は隠しバンクを開いていない。r8/run1 のパス `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run1`、`content_sha256` `89bd07e6c71d883cdeafaa96e906118cbfbc3dc45b1f15f2ce65bbec783382a5`。
- **§12.10 の不変条件**（`frame_invariants_r8.txt`）: `generated_frames` の 8,030 語（CONFIRMED 99・NOT_CONFIRMED 31・ESTIMATED 7,900）で違反 0。`へ` を覆った語は 15 語で、どれも `frame` に へ が無い。
- **参考**（`ref_measure_cmp.txt`）: L1・L2・L3 と動詞 300 語の `items.jsonl` は r7 と r8/run1 でバイト一致。悪化なし。

**読解器との接続**（`reader_probe_r8.txt`・`reader_probe_r7.txt`・`reader_probe_more_r8.txt`。読解器は変えていない）: `係がデータを確認した`（句点あり・なし）は r7・r8 とも `AGENT_EVIDENCE_MISSING:係` で棄権し、`coarse_place.query` は 1 回も呼ばれない。したがって `確認する` の問い合わせは届かない。届かない理由は読解器が先に主語 `係` の型の証拠が無いとして棄権するため（`abstain.reasons`）。述語の問い合わせ自体は届く: 別の文で、読解器は述語を `<名詞>する`（辞書形）で問い合わせる（`部長が会議に参加した。` は `参加する`、`客が駅から空港へ移動した。` は `移動する` を問い合わせ、r8 の見出し語に当たる）。一方 `担当者がデータを確認した。`・`係が書類を提出した。`・`先生が学生に結果を連絡した。` は型の枠の規則（`rule: frame`）で読め、配置を問い合わせない。
**既知の穴（隠さない）**
1. **覆った へ は `frame_unconfirmed` に出ない**（C5。`coarse_place.py` を変えないため）。さらに、へ が生成の枠に無く に|PLACE で覆った 15 語は、どれも `frame` に へ が無い。うち 14 語が `frame_status` `CONFIRMED` で、その 12 語は `frame` が空 `{}`、2 語（`移す`・`通う`）は に だけ、残る 1 語（`昇る`）は `NOT_CONFIRMED`（`frame_invariants_r8.txt` の WAIVED の行）。分布の腕が有意とした へ は生成の枠に無いので `frame` に出せず、確認された枠が空に近い。direct・CONFIRMED の型 P_MOVE を支えるのは主に codex の出所の分布の腕。
2. **名詞＋できる は今までどおり** できる の使用（C6）。可能・受身・使役のうち受身・使役は する の後ろの助動詞で `voice`（490,369 件）に数え、連なりには入れない。
3. **普通名詞だけを使う**（C1。辞書の細かい分類を読まない）: `勉強する` のような語の他に `ディ・ドナテッロする` のような普通名詞と判定された固有の名の連続も見出し語になる（標本の 60 語に 1 語。生成が棄権し UNPLACED）。固有名詞・接尾辞で終わる連続は含めない。
4. **K62 は 2 型だけ**なので、サ変の述語の direct は P_COMMUNICATE（57）と P_MOVE（13）だけ。残りの 3,172 語は estimated(generated)。direct の 70 語のうち分布の腕が codex の出所だけで決まった語の数: 格上げ全体で 80（r7 は 30）。分布の腕が 1 つの出所（`rd_min_sources 1`）で足りる設定のため、サ変の direct 70 語のうち 49 語は 1 つの出所の腕だけに、39 語は codex の出所の腕だけに支えられている（`p5/pre_decisions.tsv` の `rd_sig` の数え。jawiki の腕を含むのは 31 語）。
5. **P5 の余裕**: 0.8143（57/70）。疑わしい 12 語を別の読みにすれば 0.8 を割る。読解器が `確認する` を配置に問い合わせない文があること（上記）と合わせて、サ変の述語の direct が読解に効くかは W3-b 側の別の測定が要る。
6. `報告する` は direct だが問い合わせの `frame_status` は `NOT_CONFIRMED`（腕の型の食い違い。`frame_types_disagree` の 18 語の増加の一つ）。
**第 2 ラウンド（レビュー r1 の M1。日時 2026-10-04 03:17〜03:22 +0900）**: 第 1 ラウンドの `verantyx/coarse_types.py` は `"slot_min": 20,` の行のコメントの前の空白が 1 字減っていた（値は同じ。閾値の行は触らない約束だった）。その行を基点と 1 バイトも違わない形に戻した（`git diff c334fe6 -- verantyx/coarse_types.py` の `+`/`-` の行に `slot_min` は無い）。直したあとの `coarse_types.py` の sha256 は `cb7e44f9…bb91`（第 1 ラウンドは `e20bbbc7…e5b7`）で、r8/run1 の manifest の `coarse_types_sha256` と合わなくなったため、**r8/run1 は消さず上書きせず**、同じ引数で `build/coarse-W3a/full/r8/run2` を作った（抽出は `r8/stage/extract.pkl` の cache から。`builder_sha256` は `21f94de6…e7c3` のまま）。run2 は `verify` が `OK`、`content_sha256` が run1 と同じ `89bd07e6c71d883cdeafaa96e906118cbfbc3dc45b1f15f2ce65bbec783382a5`（`placement.sqlite` の sha256 も同じ `106d892e…ec4`）。run1 と run2 の manifest の違いは時刻・所要時間・`coarse_types_sha256` だけ（`manifest_r8_run1_vs_run2.txt`）。run1 は空白 1 字の違うコードで作り、run2 は直したコードで作り、内容は同じ。P6 に渡す配置はどちらでもよい（内容が同じ）が、出所の記録が commit するコードと合うのは run2。所要時間 run2 277.0 秒（`timing.txt`）。出力: `build_r8_run2.{log,started,finished,exit}`・`verify_r8_run2.txt`・`manifest_r8_run2.json`・`code_sha_run2.txt`・`readonly_after_r2.txt`。

<!-- w3a4-measured:end -->

## 14. W5-e: 枠の確認で `frame` に残す型は「生成の枠と分布の型の交わり」だけ（事前登録）
<!-- w5e-a4-prereg:begin -->
事前登録の時刻: 2026-10-04 03:50:50 +0900（`date '+%F %T %z'`）。この節は A-4 の新しいテスト（`tests/coarse_place/test_coarse_place_w5e_frame_backing.py`）を書く前、製品コード（`verantyx/coarse_place.py`）を直す前に確定した。§12 の区間・§13 の区間は変えない。§12.10 の `frame` の意味（「格上げに加わった分布の腕の有意な助詞の和集合 S の各 p について、生成の枠の p の型」）は、この節で次のとおり **狭める**。

**命中（W5-d の攻撃 A-4）**: 生成の枠 `[ABSTRACT, INFO_LANGUAGE]` と分布（INFO_LANGUAGE だけ）が **一部しか交わらない** 助詞（例 `冠する` の `を`）が `CONFIRMED` のまま `frame["を"] = [ABSTRACT, INFO_LANGUAGE]` を出し、読解器（W3-b2）は frame に残った型だけを読むので、裏づけの無い `ABSTRACT` を読む。

### 規則（配置側。`coarse_place._direct`。読解器は変えない）
- `frame_status == CONFIRMED`（`_frame_status_of` の判定は変えない。`frame_type_disagreement` も変えない: builder が同じ関数を数えに使う）のとき、助詞 p ∈ S（有意な助詞の和集合）について **裏づけの型** `backed[p]` = 決定に加わった `role_distribution` の腕ごとの `coarse_types.rd_analyze(その腕の数, cfg, base)["types"][p]` の **和集合**（`frame_type_disagreement` と同じ `base` の取り方。別の関数 `frame_backing` にする）を作り、
  - `frame[p] = sorted(gen[p] ∩ backed[p])`（空なら p を `frame` に入れない）、
  - `frame_unconfirmed[p] = sorted(gen[p] − backed[p])`（空なら入れない）。
- S に無い助詞（分布が有意な型を持たない助詞）の扱いは今どおり（全部 `frame_unconfirmed`）。助詞の並びは `ROLE_PARTICLES` の順。
- 帰結: 1 つの助詞が `frame` と `frame_unconfirmed` の **両方** に出ることがある（今は出ない。型が分かれる）。`CONFIRMED` で `frame` が `{}` になりうる（r7 で何語か数える）。§12.10 の不変条件（`frame` が null でない ⇔ `CONFIRMED`、値は空でない 17 型のソート済みの並び）は保たれる。
- `state`・`origin`・`top`・`frame_status`・`decided_by`・`axes`・`generated_frame` は 1 語も変えない。r7 の sqlite（配置の表）は変えず、判定関数の変更だけ。**r7 の CONFIRMED の語で `frame` の型が減る語を全件列挙する**（`artifacts/w5-e/h5_frames_summary.txt`。数は測ってから書く）。
- 読解器（`semantic_reader`・`semantic_read`）は変えない。frame に残った型だけが読まれる。

### 宣言する規則どうしの衝突 K-A4（変えない。判断は監査役）
1. `tests/coarse_place/test_coarse_place_w5d_frame_types.py::test_a_frame_whose_types_meet_the_distribution_stays_confirmed`: コメントに「a frame wider than the distribution stays」と、退役する振る舞い（枠が分布より広くても `frame` に全部残る）そのものを固定している。
2. `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`: `frame` が生成の枠の全射影であることを固定している。

### 攻撃の写しの扱い
攻撃 A-4（`tests/attack/test_attack_w5d.py::test_frame_confirmed_partial_intersection_does_not_authorize_unbacked_type`。写しはバイト同一）は、`partial_frame_vector()` が分布と一部しか交わらない枠のベクトルを探して見つからないとき **skip** する作りで、この変更のあと skip になる見込み。**skip は通過に数えない**。代わりに新しいテストで、(a) r7 の `CONFIRMED` の全語で `frame` の型がすべて裏づけの型、(b) `冠する` の `frame["を"] == ["INFO_LANGUAGE"]`・`frame_unconfirmed["を"] == ["ABSTRACT"]`、(c) W3-b2 の `typed_frame_check_ja` が `冠する`＋ABSTRACT を受けないこと、(d) 本物の builder で作った合成の配置でも部分交差の助詞が `frame` と `frame_unconfirmed` に分かれること、を確かめる。

### 受入（H5。測る前に固定）
- r7 の `CONFIRMED` の語で `frame` の型が減る語の全件の数と語。`state`・`origin`・`top` が変わる語は 0。
- W3-b2 の凍結データ（r7）で誤読 0。`changed` の文は全件列挙して理由を書く（枠の型が減って棄権に変わる文だけ。ほかの理由で読みが変わった文があれば止めて報告）。
<!-- w5e-a4-prereg:end -->


## 14.x W5-e の測定: 枠の確認で `frame` に残す型（H5）
<!-- w5e-a4-measured:begin -->
測定の時刻: 2026-10-04 04:10:06 +0900。r7（`/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1`、読むだけ。表は変えていない）の `generated_frames` の全語を `artifacts/w5-e/scripts/frame_enum.py` で変更の前後に問い合わせた（`before/h5_frames.jsonl`・`h5_frames.jsonl`、要約 `h5_frames_summary.txt`）。凍結とテスト: `frozen_a4.sha256`・`frozen_a4_at.txt`、直す前に落ちる記録 `a4_before_fail.txt`（`8 failed, 4 passed`）。

```
words 4788 confirmed 35
state/origin/top/frame_status changed 0
frame reduced 30 non-confirmed changed 0
frame empty after (CONFIRMED) 0 particle vanished from frame 1
冠する {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"を": ["ABSTRACT"]}
切り出す {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"を": ["ABSTRACT", "EVENT_ACT"]}
受け付ける {"を": ["EVENT_ACT", "GROUP_ORG", "INFO_LANGUAGE", "PERSON"]} -> {"を": ["EVENT_ACT"]} {"を": ["GROUP_ORG", "INFO_LANGUAGE", "PERSON"]}
口ずさむ {"を": ["INFO_LANGUAGE", "WORK"]} -> {"を": ["WORK"]} {"を": ["INFO_LANGUAGE"]}
叫ぶ {"が": ["ANIMAL", "PERSON"], "を": ["INFO_LANGUAGE"]} -> {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]} {"が": ["ANIMAL"]}
呼び掛ける {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT", "INFO_LANGUAGE"], "に": ["GROUP_ORG", "PERSON"]}
呼べる {"を": ["ANIMAL", "GROUP_ORG", "PERSON"]} -> {"を": ["PERSON"]} {"が": ["PERSON"], "を": ["ANIMAL", "GROUP_ORG"]}
命ずる {"を": ["ABSTRACT", "EVENT_ACT"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT"], "に": ["GROUP_ORG", "PERSON"]}
唱える {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["ABSTRACT"]} {"を": ["EVENT_ACT", "INFO_LANGUAGE"]}
問う {"を": ["ABSTRACT", "INFO_LANGUAGE", "PERSON"]} -> {"を": ["INFO_LANGUAGE"]} {"が": ["PERSON"], "を": ["ABSTRACT", "PERSON"]}
広める {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["ABSTRACT"]} {"を": ["INFO_LANGUAGE"]}
戻れる {"に": ["PLACE"], "へ": ["PLACE"]} -> {"へ": ["PLACE"]} {"が": ["ANIMAL", "ARTIFACT", "PERSON"], "に": ["PLACE"]}
教え合う {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"が": ["GROUP_ORG", "PERSON"], "を": ["ABSTRACT"], "と": ["GROUP_ORG", "PERSON"]}
旅立つ {"が": ["ANIMAL", "PERSON"], "へ": ["PLACE"]} -> {"が": ["PERSON"], "へ": ["PLACE"]} {"が": ["ANIMAL"]}
明かす {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"が": ["PERSON"], "を": ["ABSTRACT"]}
書き表す {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"を": ["ABSTRACT"]}
歌える {"を": ["INFO_LANGUAGE", "WORK"]} -> {"を": ["WORK"]} {"を": ["INFO_LANGUAGE"]}
流れ出る {"から": ["ARTIFACT", "PLACE"]} -> {"から": ["PLACE"]} {"が": ["NATURAL_PHENOMENON", "SUBSTANCE_FOOD"], "から": ["ARTIFACT"]}
申し入れる {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT", "INFO_LANGUAGE"], "に": ["GROUP_ORG", "PERSON"]}
申し込める {"を": ["ABSTRACT", "ARTIFACT", "EVENT_ACT"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT", "ARTIFACT"], "に": ["GROUP_ORG", "PERSON", "PLACE"]}
詫びる {"を": ["ABSTRACT", "EVENT_ACT"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT"], "に": ["GROUP_ORG", "PERSON"]}
話し合う {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["ABSTRACT", "EVENT_ACT"]} {"が": ["GROUP_ORG", "PERSON"], "を": ["INFO_LANGUAGE"], "と": ["GROUP_ORG", "PERSON"]}
話せる {"を": ["ABSTRACT", "INFO_LANGUAGE"]} -> {"を": ["INFO_LANGUAGE"]} {"を": ["ABSTRACT"], "と": ["GROUP_ORG", "PERSON"]}
説く {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["ABSTRACT"]} {"を": ["EVENT_ACT", "INFO_LANGUAGE"], "に": ["PERSON"]}
読み上げる {"を": ["INFO_LANGUAGE", "WORK"]} -> {"を": ["INFO_LANGUAGE"]} {"を": ["WORK"]}
論ずる {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE"]} -> {"を": ["ABSTRACT"]} {"を": ["EVENT_ACT", "INFO_LANGUAGE"]}
起き上がる {"が": ["ANIMAL", "PERSON"], "から": ["PLACE"]} -> {"が": ["PERSON"], "から": ["PLACE"]} {"が": ["ANIMAL"]}
離れる {"から": ["ARTIFACT", "PERSON", "PLACE"]} -> {"から": ["PLACE"]} {"が": ["ARTIFACT", "PERSON", "PLACE"], "から": ["ARTIFACT", "PERSON"]}
頼める {"を": ["ABSTRACT", "EVENT_ACT", "INFO_LANGUAGE", "PERSON"]} -> {"を": ["EVENT_ACT"]} {"を": ["ABSTRACT", "INFO_LANGUAGE", "PERSON"]}
飛び出す {"が": ["ANIMAL", "ARTIFACT", "NATURAL_PHENOMENON", "PERSON"], "から": ["PLACE"]} -> {"が": ["ANIMAL"], "から": ["PLACE"]} {"が": ["ARTIFACT", "NATURAL_PHENOMENON", "PERSON"], "を": ["ARTIFACT", "PLACE"]}
```

- **`state`・`origin`・`top`・`frame_status` が変わった語は 0**（上の 2 行目）。`CONFIRMED` 以外で `frame` が変わった語は 0。`frame` の型が減った語は上の一覧のとおり。空の `frame` になる語は 0、助詞ごと `frame` から消える語は 1（`戻れる` の `に`。`frame_unconfirmed` に残る）。
- **W3-b2 の凍結データ（r7）**（`h5_w3b2_check.txt`・`h5_w3b2_check.json`）: `misread=0`、`before/h5_w3b2_check.json` とバイト一致。A-4 だけを入れた時点の入口の出力は変更前と 1 行も違わなかった（その時点の `diff` の `>` は 0 行。ファイルは B を入れたあとの流しで上書きした）。最後の木で変わる行は 35 行で、全部 B の門（`COORDINATION_UNDETERMINED`／`DISJUNCTION_UNDETERMINED`）の理由が足された棄権のままの文（`h5_w3b2_changed.tsv`、`h5_w3b2_changed_summary.txt`: `gate_reason_added` 32・`gate_reason_only` 3、読めた→棄権 0・棄権→読めた 0・読みの変化 0）。枠の型が減って棄権に変わった文は 0。
- **テスト**: `tests/coarse_place/test_coarse_place_w5e_frame_backing.py` は `10 passed`。攻撃 A-4（`test_frame_confirmed_partial_intersection_does_not_authorize_unbacked_type`）は **skip**（`partial_frame_vector()` が None: 攻撃のベクトルが消えた）。skip は通過に数えない。
- **宣言した衝突 K-A4**（書き換えていない。`a4_after_module.txt`）: `tests/coarse_place/test_coarse_place_w5d_frame_types.py::test_a_frame_whose_types_meet_the_distribution_stays_confirmed`、`tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`。後者は実行のたびに `tests/attack/w3a3/r6_48_queries.jsonl`・`r6_audit_summary.json` を書き換える（既存のテストの副作用。作業ツリーでは最後に基点の内容へ戻した）。
- **既知の穴**: 1 つの助詞が `frame` と `frame_unconfirmed` の両方に出る語がある（型が分かれる）。分布の有意な型の外にある生成の型は `frame_unconfirmed` にだけ出て読解器は読まない。
<!-- w5e-a4-measured:end -->

## 14.2 W5-e 第 2 ラウンド: 覆った へ を `frame_unconfirmed` に出す（W3-a4 の申し送り R1）（事前登録）
<!-- w5e2-r1-prereg:begin -->
事前登録の時刻は `artifacts/w5-e/r2/r1_prereg_at.txt`。この節は新しいテスト（`tests/coarse_place/test_coarse_place_w5e2_cover.py`）を書く前、製品コード（`verantyx/coarse_place.py`）を直す前に確定した。§14 の区間は変えない（追記）。

**由来**: W3-a4（`coarse_types.decide_word` の包含規則 `frame_cover_rule`）は、生成の枠が へ を持たず `に|PLACE` を持つとき、分布の有意な助詞 へ を「`に|PLACE` で覆った」ものとして枠の確認を通す（腕の `cover.he_by_ni_place` に腕の鍵が残る）。覆った へ は `frame` にも `frame_unconfirmed` にも出ないため、W3-a4 のレビューで r8 の `frame_status == CONFIRMED` なのに `frame == {}` の語が 12 語あった（申し送り R1）。

### 規則（配置側。`coarse_place._direct` の CONFIRMED の分岐。`decide_word`・閾値・`frame_type_disagreement`・`frame_backing`・`_frame_status_of` は不変）
- 新しい純粋関数 `frame_cover_unconfirmed(dec, gen_map) -> {助詞: [型]}`: `dec["arms"].get(ct.GEN_FRAME_ARM)` の `"cover"` の `"he_by_ni_place"` が **空でない**、かつ へ が `gen_map` に **無い**、かつ `gen_map.get(に)` に `PLACE` がある、ときだけ `{へ: ["PLACE"]}`。ほかは `{}`。助詞は `ct.CASE_PARTICLES_9[4]`（へ）・`[2]`（に）から取る（`coarse_types.py` に定数を足さない。W3-a4 の `HE_PARTICLE`・`NI_PLACE_SLOT` と同じ値）。
- 型 `PLACE` は覆った行 `に|PLACE` の型（モデルが書いた型。分布の型ではない）。**生成の型であり、分布は裏づけていない**ので `frame` には入れず `frame_unconfirmed` にだけ出す。
- `_direct` の CONFIRMED の分岐で、A-4 の `frame`／`unconfirmed` を作った直後・`frame_type_disagreement` の前に、この関数の結果を `unconfirmed` に足し、鍵を `ct.ROLE_PARTICLES` の順に並べ直す。`frame` には何も足さない。`frame_status` は変えない（CONFIRMED で `frame == {}` の語は残る。その数は報告する）。矛盾（disagreement）があれば従来どおり `frame = unconfirmed = None`。
- `cover["ignored"]`（K62 の外の と・まで・より）は **出さない**（裁定は「覆った助詞」だけ）。r8 での件数は参考に数えて報告する。
- `state`・`origin`・`top`・`frame_status`・`frame`・`decided_by`・`axes`・`generated_frame` は 1 語も変えない。変わる鍵は `frame_unconfirmed` だけ。

### この基点での効き方
この基点の `coarse_types.decide_word` は `cover` を書かない（W3-a4＝df4f001 の変更）ので、**この基点では r7・r8 とも答えは 1 バイトも変わらない**。W3-a4 の統合後に効く。確かめは (a) 手で作った `dec` での純粋関数の単体テスト、(b) scratchpad に df4f001 の `coarse_types.py` を重ねた複製での r8 の全数（`coarse_types.py` は許可パス外なので `$W` には置かない）、(c) r7 の不変（`$W` と重ねた複製でバイト一致）の 3 つ。

### 受入（測る前に固定）
- (b) 重ねた複製の r8（`generated_frames` 8,030 語）: 状態の数 ESTIMATED 7,900・CONFIRMED 99・NOT_CONFIRMED 31（W3-a4 のレビューの値）。R1 の有無で答えが変わる語は **14 語**、変わる鍵は `frame_unconfirmed` だけ、14 語とも `frame_unconfirmed["へ"] == ["PLACE"]` が足される。`state`・`origin`・`top`・`frame_status`・`frame` の変化 0。CONFIRMED で `frame == {}` の語は 14（基点の `coarse_place` で 12 語＝W3-a4 の R1 の 12 語、A-4 で 2 語増えて 14）。
- (c) r7（4,788 語）は重ねた複製と `$W` でバイト一致。R1 の有無でもバイト一致。
<!-- w5e2-r1-prereg:end -->

## 14.3 W5-e 第 2 ラウンド: K-A4 の改訂（監査役の判断 2026-10-04 04:42）
<!-- w5e2-ka4:begin -->
監査役の判断: 「K-A4（2）: W5-d のテストが CONFIRMED の枠の型の全集合を固定していたもの → 新しい規則に合わせて改訂」。§14 の宣言のとおり、退役させた振る舞い（枠が分布より広くても `frame` に全部残る）を固定していた 2 関数を、名前を変えずに「`frame` ＝ 生成の枠 ∩ 分布の裏づけ、外れた型は `frame_unconfirmed`」へ改訂する。

- `tests/coarse_place/test_coarse_place_w5d_frame_types.py::test_a_frame_whose_types_meet_the_distribution_stays_confirmed`: **期待は先に治具の分布から手で求めた**。同じファイルの builder の入力は `人が言葉を呟いた。`×14（が+PERSON・を+INFO_LANGUAGE）、`呟く` の生成の枠は `{が: [PERSON], を: [INFO_LANGUAGE, PERSON]}`。分布の裏づけは が=PERSON、を=INFO_LANGUAGE（PERSON は分布に無い）なので、`frame = {が: [PERSON], を: [INFO_LANGUAGE]}`、`frame_unconfirmed = {を: [PERSON]}`。`囁く`（枠 `{が: [PERSON], を: [INFO_LANGUAGE]}` は分布と完全に一致）の行は試して変わらなければ不変。
- `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades`（攻撃の写し。r6 の 48 語）: 期待の投影を「生成の枠 ∩ 分布の裏づけ（決定に加わった `role_distribution` の腕ごとの `ct.rd_analyze(...)["types"]` の和集合）」に、外れた型は `frame_unconfirmed` に変える。**期待は `cp.frame_backing`（製品の関数）で作らない**（製品の関数で期待を作ると検査にならない）。`ct.rd_analyze` は判定の規則そのものなので使う。ほかの assert（48 語の導出・2 回の問い合わせのバイト同一・`state`/`origin`/`generated_frame`/`namespace`/`top`・生成の枠の型・腕の判定・NOT_CONFIRMED の形・`disjoint_slot_conflicts`）は変えない。写しなので原本とは一致しなくなる（前後の sha256 は `artifacts/w5-e/r2/attack_copies_r2.sha256`）。

### 改訂前の全文

#### `tests/coarse_place/test_coarse_place_w5d_frame_types.py::test_a_frame_whose_types_meet_the_distribution_stays_confirmed` — 改訂前
```python
def test_a_frame_whose_types_meet_the_distribution_stays_confirmed(built):
    r = q("呟く", built["out"])
    assert r["frame_status"] == "CONFIRMED"
    assert r["frame"]["を"] == ["INFO_LANGUAGE", "PERSON"]               # the intersection rule: a frame wider than the distribution stays
    assert r["frame"]["が"] == ["PERSON"]
    assert "frame_disagreement" not in r and r["frame_unconfirmed"] == {}
    assert list(r)[-4:] == ["generated_frame", "frame_status", "frame", "frame_unconfirmed"]
    r = q("囁く", built["out"])
    assert r["frame_status"] == "CONFIRMED" and r["frame"] == {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]}
    assert "frame_disagreement" not in r
```

#### `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` — 改訂前
```python
def test_all_r6_generated_frame_upgrades():
    # W5-d2 (auditor's ruling B1, K5): the invariants follow the rule of W5-d (docs/COARSE_PLACEMENT.md section 13): a predicate that a generated frame placed direct
    # is CONFIRMED only when no particle of the frame contradicts the distribution that backed it; a contradicted one is NOT_CONFIRMED (frame null, the contradiction
    # in frame_disagreement). The derivation of the 48 words, the byte identity of two queries, state/origin/generated_frame/namespace/top, the type of the
    # generated frame, and the verdict of every distribution arm are as they were; the number of NOT_CONFIRMED words is not asserted (it is written to the summary).
    pl, why = cp._open(PLACEMENT)
    assert pl is not None, why
    rows = pl.con.execute(
        "SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word"
    ).fetchall()
    words = [row[0] for row in rows]
    assert len(words) == 48

    results, frame_conflicts, invariant_errors, byte_diffs, not_confirmed = [], [], [], [], []
    for word in words:
        answer = cp.query(word, placement=PLACEMENT)
        again = cp.query(word, placement=PLACEMENT)
        if _json_bytes(answer) != _json_bytes(again):
            byte_diffs.append(word)
        results.append(answer)

        if not (answer["state"] == "DECIDED" and answer["origin"] == "direct"
                and answer.get("generated_frame") is True
                and answer["frame_status"] in ("CONFIRMED", "NOT_CONFIRMED")
                and answer["namespace"] == "P" and answer["top"]):
            invariant_errors.append({"word": word, "answer": answer})
            continue

        gf = pl.generated_frame(word)
        generated = gf[5] if gf else {}
        if not gf or gf[4] != answer["top"][0]:
            invariant_errors.append({"word": word, "reason": "generated_type_differs",
                                     "generated_type": gf[4] if gf else None,
                                     "answer_top": answer["top"]})
        sig_particles, typed_sig = set(), []
        for key, arm in answer["axes"].items():
            if not key.startswith("role_distribution@") or not arm["met"]:
                continue
            raw = [r for r in pl.evidence(word)
                   if r[0] == "role_distribution" and key.endswith("@" + r[1])]
            counts = {r[2]: r[3] for r in raw}
            base = raw[0][4] if raw else None
            analysis = ct.rd_analyze(counts, pl.cfg, base)
            sig_particles.update(analysis["sig"])
            typed_sig.append((key, analysis["types"]))
            if ct.arm_verdict("role_distribution", counts, pl.cfg, base) != answer["top"]:
                invariant_errors.append({"word": word, "arm": key, "reason": "arm_top_differs"})

        if answer["frame_status"] == "NOT_CONFIRMED":
            not_confirmed.append(word)
            disagreement = answer.get("frame_disagreement")
            if answer["frame"] is not None or "frame_unconfirmed" in answer \
                    or not isinstance(disagreement, dict) or not disagreement:
                invariant_errors.append({"word": word, "reason": "not_confirmed_shape", "frame": answer["frame"],
                                         "frame_disagreement": disagreement,
                                         "has_frame_unconfirmed": "frame_unconfirmed" in answer})
                continue
            for particle, entry in disagreement.items():
                gen_types = set(entry.get("generated") or [])
                arms = entry.get("distribution") or {}
                if not gen_types or not arms or any(gen_types & set(dt) for dt in arms.values()):
                    invariant_errors.append({"word": word, "reason": "disagreement_types_meet",
                                             "particle": particle, "entry": entry})
            continue

        expected = {p: sorted(set(generated.get(p, []))) for p in ct.ROLE_PARTICLES
                    if p in sig_particles and generated.get(p)}
        if answer["frame"] != expected:
            invariant_errors.append({"word": word, "reason": "frame_projection_differs",
                                     "expected": expected, "got": answer["frame"]})

        for key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                if not dist_types:
                    continue
                frame_types = set(answer["frame"].get(particle, []))
                if not frame_types or not frame_types.intersection(dist_types):
                    frame_conflicts.append({"word": word, "source": key, "particle": particle,
                                            "distribution_types": dist_types,
                                            "confirmed_frame_types": sorted(frame_types)})

    (OUT / "r6_48_queries.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in results),
        encoding="utf-8")
    summary = {"derived_words": len(words), "queried": len(results),
               "byte_differences": byte_diffs, "invariant_errors": invariant_errors,
               "disjoint_slot_conflicts": frame_conflicts, "not_confirmed": not_confirmed}
    (OUT / "r6_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert not byte_diffs
    assert not invariant_errors
    assert not frame_conflicts, "confirmed frame slot types contradict significant distribution types"
```

### 改訂後の全文

#### `tests/coarse_place/test_coarse_place_w5d_frame_types.py::test_a_frame_whose_types_meet_the_distribution_stays_confirmed` — 改訂後
```python
def test_a_frame_whose_types_meet_the_distribution_stays_confirmed(built):
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A4）: A-4 で frame に残すのは「生成の枠 ∩ 分布の裏づけ」だけ。治具の分布（人が言葉を呟いた×14: が+PERSON・を+INFO_LANGUAGE）から手で求めた期待:
    # 呟く の生成の枠 を=[INFO_LANGUAGE, PERSON] のうち分布が裏づけるのは INFO_LANGUAGE だけ → frame[を]=[INFO_LANGUAGE]、外れた PERSON は frame_unconfirmed[を]
    r = q("呟く", built["out"])
    assert r["frame_status"] == "CONFIRMED"
    assert r["frame"]["を"] == ["INFO_LANGUAGE"]                          # the intersection rule (A-4): the PERSON the distribution does not back is not in frame
    assert r["frame"]["が"] == ["PERSON"]
    assert "frame_disagreement" not in r and r["frame_unconfirmed"] == {"を": ["PERSON"]}
    assert list(r)[-4:] == ["generated_frame", "frame_status", "frame", "frame_unconfirmed"]
    r = q("囁く", built["out"])
    assert r["frame_status"] == "CONFIRMED" and r["frame"] == {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]}
    assert "frame_disagreement" not in r
```

#### `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` — 改訂後
```python
def test_all_r6_generated_frame_upgrades():
    # W5-d2 (auditor's ruling B1, K5): the invariants follow the rule of W5-d (docs/COARSE_PLACEMENT.md section 13): a predicate that a generated frame placed direct
    # is CONFIRMED only when no particle of the frame contradicts the distribution that backed it; a contradicted one is NOT_CONFIRMED (frame null, the contradiction
    # in frame_disagreement). The derivation of the 48 words, the byte identity of two queries, state/origin/generated_frame/namespace/top, the type of the
    # generated frame, and the verdict of every distribution arm are as they were; the number of NOT_CONFIRMED words is not asserted (it is written to the summary).
    pl, why = cp._open(PLACEMENT)
    assert pl is not None, why
    rows = pl.con.execute(
        "SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word"
    ).fetchall()
    words = [row[0] for row in rows]
    assert len(words) == 48

    results, frame_conflicts, invariant_errors, byte_diffs, not_confirmed = [], [], [], [], []
    for word in words:
        answer = cp.query(word, placement=PLACEMENT)
        again = cp.query(word, placement=PLACEMENT)
        if _json_bytes(answer) != _json_bytes(again):
            byte_diffs.append(word)
        results.append(answer)

        if not (answer["state"] == "DECIDED" and answer["origin"] == "direct"
                and answer.get("generated_frame") is True
                and answer["frame_status"] in ("CONFIRMED", "NOT_CONFIRMED")
                and answer["namespace"] == "P" and answer["top"]):
            invariant_errors.append({"word": word, "answer": answer})
            continue

        gf = pl.generated_frame(word)
        generated = gf[5] if gf else {}
        if not gf or gf[4] != answer["top"][0]:
            invariant_errors.append({"word": word, "reason": "generated_type_differs",
                                     "generated_type": gf[4] if gf else None,
                                     "answer_top": answer["top"]})
        sig_particles, typed_sig = set(), []
        for key, arm in answer["axes"].items():
            if not key.startswith("role_distribution@") or not arm["met"]:
                continue
            raw = [r for r in pl.evidence(word)
                   if r[0] == "role_distribution" and key.endswith("@" + r[1])]
            counts = {r[2]: r[3] for r in raw}
            base = raw[0][4] if raw else None
            analysis = ct.rd_analyze(counts, pl.cfg, base)
            sig_particles.update(analysis["sig"])
            typed_sig.append((key, analysis["types"]))
            if ct.arm_verdict("role_distribution", counts, pl.cfg, base) != answer["top"]:
                invariant_errors.append({"word": word, "arm": key, "reason": "arm_top_differs"})

        if answer["frame_status"] == "NOT_CONFIRMED":
            not_confirmed.append(word)
            disagreement = answer.get("frame_disagreement")
            if answer["frame"] is not None or "frame_unconfirmed" in answer \
                    or not isinstance(disagreement, dict) or not disagreement:
                invariant_errors.append({"word": word, "reason": "not_confirmed_shape", "frame": answer["frame"],
                                         "frame_disagreement": disagreement,
                                         "has_frame_unconfirmed": "frame_unconfirmed" in answer})
                continue
            for particle, entry in disagreement.items():
                gen_types = set(entry.get("generated") or [])
                arms = entry.get("distribution") or {}
                if not gen_types or not arms or any(gen_types & set(dt) for dt in arms.values()):
                    invariant_errors.append({"word": word, "reason": "disagreement_types_meet",
                                             "particle": particle, "entry": entry})
            continue

        # W5-e2 (auditor's ruling K-A4, 2026-10-04 04:42): the frame keeps the generated types the distribution backs (generated frame ∩ the UNION over the deciding
        # distribution arms of the significant types, ct.rd_analyze: the rule of the decision itself, NOT cp.frame_backing); the generated types it does not back, and every
        # generated particle outside the significant ones, are in frame_unconfirmed
        backing = {}
        for _key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                backing.setdefault(particle, set()).update(dist_types)
        expected = {p: sorted(set(generated[p]) & backing.get(p, set())) for p in ct.ROLE_PARTICLES
                    if p in sig_particles and generated.get(p) and set(generated[p]) & backing.get(p, set())}
        expected_unconfirmed = {p: sorted(set(generated[p]) - (backing.get(p, set()) if p in sig_particles else set()))
                                for p in ct.ROLE_PARTICLES
                                if generated.get(p) and set(generated[p]) - (backing.get(p, set()) if p in sig_particles else set())}
        if answer["frame"] != expected or answer.get("frame_unconfirmed") != expected_unconfirmed:
            invariant_errors.append({"word": word, "reason": "frame_projection_differs",
                                     "expected": expected, "got": answer["frame"],
                                     "expected_unconfirmed": expected_unconfirmed, "got_unconfirmed": answer.get("frame_unconfirmed")})

        for key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                if not dist_types:
                    continue
                frame_types = set(answer["frame"].get(particle, []))
                if not frame_types or not frame_types.intersection(dist_types):
                    frame_conflicts.append({"word": word, "source": key, "particle": particle,
                                            "distribution_types": dist_types,
                                            "confirmed_frame_types": sorted(frame_types)})

    (OUT / "r6_48_queries.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in results),
        encoding="utf-8")
    summary = {"derived_words": len(words), "queried": len(results),
               "byte_differences": byte_diffs, "invariant_errors": invariant_errors,
               "disjoint_slot_conflicts": frame_conflicts, "not_confirmed": not_confirmed}
    (OUT / "r6_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert not byte_diffs
    assert not invariant_errors
    assert not frame_conflicts, "confirmed frame slot types contradict significant distribution types"
```

流した結果: `tests/coarse_place` と `tests/attack/w3a3/test_attack_w3a3_r6.py` は全通過（`artifacts/w5-e/r2/` の `k_a4_run.txt`）。後者は実行のたびに `r6_48_queries.jsonl`（と `r6_audit_summary.json`）を書き換える既存の副作用があり、流した直後に基点の内容へ戻した（改訂後の出力は `artifacts/w5-e/r2/r6_48_queries.after_ka4.jsonl` に写した）。
<!-- w5e2-ka4:end -->

## 14.2.x W5-e 第 2 ラウンドの測定: 覆った へ の R1（重ねた複製で r8 の全数）
<!-- w5e2-r1-measured:begin -->
事前登録（`r1_prereg_at.txt`）→ テストの凍結（`frozen_r1cover.sha256`・`frozen_r1cover_at.txt`）→ 直す前に落ちる記録（`r1cover_before_fail.txt`: `13 failed, 5 passed`）→ 製品（`coarse_place.frame_cover_unconfirmed` と `_direct` の数行）の順。出力はすべて `artifacts/w5-e/r2/`。

- **この基点（`$W`）では r7・r8 とも答えは 1 バイトも変わらない**: r7 の全 4,788 語を `frame_enum.py` で問い合わせ、第 1 ラウンドの `h5_frames.jsonl` とバイト一致（`h5_frames.jsonl`）。`coarse_types.py` は 1 行も変えていない（`git diff ca66d3e -- verantyx/coarse_types.py` は空）。新しいテスト `tests/coarse_place/test_coarse_place_w5e2_cover.py` は 18 件通過（純粋関数 5 通り以上・実在の r7 の語を `decide_word` を包んで `cover` を足した上で `_direct` に通す確かめ・r7 の不変）。
- **重ねた複製**（`$T/ov` = 今の `$W` の製品＋df4f001 の `coarse_types.py`、`ov0` = 同じで `coarse_place.py` だけ第 1 ラウンドの版、`ovb` = 同じで `coarse_place.py` だけ基点の版。スクリプトは `artifacts/w5-e/r2/scripts/`）で r8（`/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`）の `generated_frames` 8,030 語を問い合わせた（`h5_r8_r1.txt`）:
  - 状態の数は 3 つとも ESTIMATED 7,900・CONFIRMED 99・NOT_CONFIRMED 31（W3-a4 のレビューの値と一致＝重ねた複製が正しい）。
  - R1 の有無（`ov` 対 `ov0`）で答えが変わる語は **14 語**、違う鍵は `frame_unconfirmed` だけ、14 語とも `frame_unconfirmed["へ"] == ["PLACE"]` が足される: 向かえる・嫁ぐ・日帰りする・流れ込む・浸透する・潜る・異動する・移す・行ける・送り返す・逃げ込む・通う・進出する・飛び込む。`state`・`origin`・`top`・`frame_status`・`frame` の変化は 0。
  - CONFIRMED で `frame == {}` の語: 基点の `coarse_place`（`ovb`）で 12 語（W3-a4 の R1 の 12 語）、第 1 ラウンドの版（`ov0`）と今（`ov`）で 14 語（A-4 で `移す`・`通う` が増える: この 2 語の に は有意な助詞だが分布が型を裏づけないので `frame` から外れる）。R1 は `frame` を変えないので 14 語は残る。**覆った へ は `frame_unconfirmed` に出るようになった**（`frame_status` は変えていない）。
  - 参考: r8 の CONFIRMED 99 語のうち、`decide_word` が `cover` を記録する語は 99、`he_by_ni_place` が空でない語は 14（上の 14 語と同じ）、`cover["ignored"]` が空でない語は **0**（`h5_r8_ignored.txt`）。したがって `ignored` を出さない判断は r8 では何の語にも影響しない。
- r7（4,788 語）: 重ねた複製（`ov`）と `$W` の答えはバイト一致、R1 の有無（`ov` と `ov0`）でもバイト一致（`$T/q` の `cmp`。このツリーの `h5_frames.jsonl` との一致は上のとおり）。
- **W3-a4（df4f001）の統合後に効く**: 統合後に r8 で `frame_unconfirmed["へ"] == ["PLACE"]` の 14 語を確かめてほしい。
<!-- w5e2-r1-measured:end -->

## 12.18 W3-a6: 役割つきの枠・相対位置の語・配置 r9

基点 dev `0041606`、配置 r8/run2 が土台。配置側だけを変える（読解器・方針・cli は触らない。読解器が役割つきの枠を使うのは次のチケット）。

<!-- w3a6-prereg:begin -->
### 12.18.1 事前登録（測る前に固定。登録の時刻は `artifacts/w3-a6/prereg_time.txt` の前後 2 行）

**目的**: (1) 述語ごとに「助詞 → 役割（と型）」を生成コーパスから申告させる（`role_frame`）。(2) 申告した (助詞, 型) が分布の腕に裏づけられる役割だけを確認する。(3) 名詞の型に `RELATIVE_POSITION` を足し、生成で「相対位置・方向を表す語」と申告された語を、場所と分ける。(4) 配置 r9/run1 を作り r8 との差を数える。

**D1 型の一覧**: `NOUN_TYPES` の末尾に `RELATIVE_POSITION`（名称「相対位置・方向」）を 1 つ足す（既存の 17 個の id と並びは変えない。17 → 18）。`FRAME_NOUN_TYPES` は `NOUN_TYPES` から `RELATIVE_POSITION` を除いた 17 型（並びは同じ）で、述語の枠（W3-a3）と役割つきの枠の充填物の型はこの 17 型。`NOUN_TYPE_NOTES["RELATIVE_POSITION"]` の定義文は「他の物や場所を基準にした位置・方向を表す語。それ自体は場所ではない」。語の一覧は製品のどこにも置かない（生成の定義文と分布で決める）。`K62_FRAMES`・`DEFAULT_CONFIG`・既存の閾値・`ARMS`・`GEN_ARMS`・`AGREEMENT_ONLY_ARMS`・`NON_VOTE_ARMS` は変えない。

**D2 役割名**: `ROLE_NAMES` は `docs/READING_CONVENTIONS.md` §2 の表の 1 列目の 20 個を表の順に並べた閉じた一覧（`event_cross.ROLE_NAMES` と同じ値の写し。試験で照合）。`ROLE_DESCRIPTIONS` は §2 の「何を入れるか」から例の語・例の動詞を除いて書いた短い説明。

**D3 相対位置の生成（`gen_coarse_evidence.py --kind ntype`。W3-a2 の名詞の経路と同じ台帳・束・再開・上限）**: 名詞の形（定義文と上位語だけ聞く）は 1 バイトも変えず、新しい形で「定義文 1 文 ＋ 名詞の型（18 型から 1〜2 個）」を申告させる。対象の一覧 = r8 の見出し語のうち origin が direct・top に PLACE を含み・ns に名詞を含み・by の腕の名前に定義系の腕（definition・definition_recovered・title_qualifier・alias・paren_alias・seed）を含まない語。n_seen の降順、境界の同点は全部。検査データを読まない。プロンプトは型の一覧と補足を `ct` から機械的に並べ、例の語・語の一覧を書かない。モデル `gpt-6-luna`・effort `low`。

**D4 役割つきの枠の生成（`--kind role`）**: 対象の一覧 = r8 の `generated_frames` の全語 ∪ `SEEDS_PRED` の語のうち、見出し語で ns に述語を含む語。申告は `{助詞: [{"role", "types"}]}`（助詞は格助詞 9 種、役割は `ROLE_NAMES`、型は `FRAME_NOUN_TYPES`）。同じ助詞に役割が 2 つ以上あるときはそれぞれの型を分けて書かせる。判断できない語は null（棄権）。が の項は人・動物・組織なら agent、それ以外は entity（規約 §2 の機械的な規則）。プロンプトに役割の一覧・型の一覧・助詞を `ct` から機械的に並べ、例の語・例文・語の一覧を書かない。`effort low`。読みの捨て方（enum の外・型が空・同じ助詞の 2 回・同じ助詞の中の同じ役割の 2 回・型の重複）は語ごとに採らず理由別に数える。第8ラウンドでは監査役判断4（2026-10-04 20:35 +0900）により、9助詞ごとの典型的な役割と付加格の指示を追加する。詳細は §12.18.1.2 に記録する。

**D5 相対位置の判定（`decide_word` の新しい分岐。既存の行は変えない）**: 生成の行 `gen_relpos` を取り分けて残りで判定し、行があれば最後に適用する。判定が DECIDED か MULTIPLE で PLACE を含む → MULTIPLE（型に `RELATIVE_POSITION` を足す。origin は元のまま）。生成でない腕が自分の閾値を満たして `RELATIVE_POSITION` だけを指すときに限り direct の RELATIVE_POSITION にする（この配置にはそういう腕が無いので 0 語）。それ以外（PLACE を含まない・UNPLACED）は判定を変えない。帰結: 生成の申告は判定を狭める方向にだけ効く。PLACE の語を相対位置の単独の型にはしない。`why` に `RELPOS_ADDED` と `GENERATED_NOT_DECIDING` を足す。

**D6 役割つきの枠の確認（`role_frame_check`。builder と問い合わせが同じ関数）**: 分布の腕（`role_distribution` の出所ごと）に `rd_analyze` を適用し（W3-a3 §12.4 の閾値 `rd_*` をそのまま。新しい閾値は作らない）、有意な (助詞 p, 型 t) について、p の申告した役割のうち t を型に含むものの集合 R を取る。|R| = 1 → その役割に腕の票。|R| ≥ 2 → 割れ（同点は棄権。票にしない）。|R| = 0 → 申告に無い型（表示だけ）。票を入れた腕の数が `role_frame_min_sources`（既定は `rd_min_sources`）以上の役割が確認される。確認された役割の型は「申告した型 ∩ 票の型」。確認された役割が 1 つ以上で `CONFIRMED`、それ以外は `ESTIMATED`（生成だけ）。未確認の理由は `NOT_BACKED`・`SPLIT`・`PARTLY_BACKED` の閉じた一覧。

**D7 builder**: 新しい引数 `--generated-noun-types`・`--generated-noun-types-ledger`・`--role-frames`・`--role-frames-ledger`。引数がないときの動作・manifest の形・表は今のまま。新しい表 `generated_noun_types`・`role_frames` は入力があるときだけ作る。

**D8 問い合わせ**: 配置が `role_frames` の表を持つときだけ、答えの末尾に `role_frame_status`・`role_frame`・`role_frame_unconfirmed` の 3 鍵をこの順で足す（表の無い配置と配置なしは鍵が無く、答えは基点と byte 一致）。`role_frame_status` の閉じた一覧は `CONFIRMED`・`ESTIMATED`・`NO_ROLE_FRAME`。`role_frame` が null でない ⇔ CONFIRMED。

**D9 設定**: `role_frame_min_sources` の既定は 1（= r8 の `rd_min_sources`）。事前評価で、確認された役割の明らかな誤りが 1 割を超えたら 2、それでも超えたら 3 に上げる（上げる方向だけ）。3 でも超えたら 3 のまま N4 を満たせないものとして報告する。決めたら凍結する。

**測り方（受入基準）**: N1 = r7・r8 の全見出し語の `query` の答え全体（`json.dumps(ensure_ascii=False)` の sha256）と配置なしの固定の語の答え、読解の入口の出力が基点と byte 一致。N2 = 10述語・11役割行（試験データにだけ置く）の `role_frame` が期待の役割を含み、CONFIRMED の役割は `backed_by` の腕の有意な (助詞, 型) に裏づけられる。N3 = 相対位置の語 15 語（試験データにだけ置く）が PLACE 単独の direct でない、PLACE から変わった名詞の全件の目視で明らかな誤りが 1 割以下。N4 = 無作為 60 語（`random.Random(20261004)`）の CONFIRMED の役割の明らかな誤りが 1 割以下。N5 = seed の判定が r8 と同じ。N7 = 既存テストの失敗集合が基線から増えない。

**目視の基準**: 役割は「正しい（その述語の最も普通の意味で、その助詞の項がその役割に当たる文が普通に作れ、規約 §2・§4.1 に合い、型もその役割で来る名詞として当てはまる）／明らかな誤り（その助詞がその役割を取らない、規約が別の役割を指す、型がその役割に来ない）／疑わしい」。相対位置は「正しい（その語の最も普通の意味が他の物や場所を基準にした位置・方向）／明らかな誤り（本当の場所・施設・地名のようにそれ自体が場所の語を相対位置にした）／疑わしい」。**目視は実装役の読みで、正解データではない**。表は集計の前に sha256 を取る。役割の目視は確認の結果を見ずに申告だけを見て書く。

**生成の上限**: 2 つの形の合計で 1,500 回以内。2 つの形を同時に走らせない。試しの束の後にプロンプトを変えない（変えたら新しい台帳）。
<!-- w3a6-prereg:end -->

### 12.18.1.1 監査役判断2による事前登録修正（2026-10-04 17:18:27 +0900）

監査役の追加指示（2026-10-04 17:15 +0900）に基づき、検査期待と生成契約を次のように改める。この記録を期待データ・生成対象一覧・プロンプトの更新より先に置き、旧版は `artifacts/w3-a6/current-r1/freeze_pre_r6.sha256` と `freeze_final_pre_r6.sha256` に保存する。

**N2「集める」の期待**

- 変更前: `{"pred": "集める", "particle": "に", "role": "place"}`
- 変更後: `{"pred": "集める", "particle": "に", "role": "goal"}`
- 理由: 独立検査文「学芸員が展示室に資料を集めた」では、資料が移る到達点を「に」が表す。`READING_CONVENTIONS.md` §2 の `goal` と §4.1 の「に＋場所・物で、物がそこに移る」規則に合うため、期待を `goal` に合わせる。

**役割枠生成の型重複契約**

- 変更前のプロンプト規則: 「同じ助詞に役割が 2 つ以上あるときは、それぞれの役割で来る名詞の型を役割ごとに分けて書く（同じ型を 2 つの役割に書かない）。types は空にしない。」
- 変更後の規則: 「同じ助詞に役割が 2 つ以上あるときは、役割ごとの型をそれぞれ申告する。同じ型を複数の役割に申告してよい。types は空にしない。」
- 理由: 型の重なりを禁止すると、モデルに曖昧な型を片方の役割へ押しつけることになる。重複型は保持し、確認器が `SPLIT` として数えて票にしない。

**期待データの件数注記**

- 変更前: `nine predicates`
- 変更後: `10 predicates, 11 role rows`
- 理由: 期待一覧の実際の内容と監査役が指定した件数を一致させる。期待行は上記「集める」の役割だけを変更し、一覧の語や行数は変えない。

この修正に合わせ、r8/run2 から D3・D4 の規則で `needs_ntype.jsonl` と `needs_role.jsonl` を再生成する。`generate_and_collect.sh` はこの2一覧を作った後に生成・回収を行う手順へ更新する。プロンプトの再生成・hash 凍結と対象一覧の再生成までは行うが、このラウンドでは codex を起動せず、r9/run1 および N2〜N5 は次ラウンドに残す。

### 12.18.1.2 第8ラウンド・監査役判断4の事前登録（2026-10-04 20:38:46 +0900）

監査役判断4（2026-10-04 20:35 +0900）と第7ラウンドレビューのN2・N7指摘に基づく。次の規則・目標は試行出力を見る前に固定し、試しの束と本番の生成は監査役が外で実行する。この節の追記時点で第8ラウンドのモデル呼び出しは0回。

**役割枠プロンプトの一般化**: `ROLE_NAMES` と `FRAME_NOUN_TYPES` は既存どおり `coarse_types` から列挙する。9助詞の典型的な役割をモデルに明示する対応表は、が＝`agent`/`entity`（規約の主語規則。使役の `causer`、述語の意味に合う `experiencer`/`attribute` もありうる）、を＝`patient`/`causee`（経路・起点など他の通常用法は述語に応じた役割）、に＝`recipient`/`goal`/`result`/`place`/`time`/`beneficiary`/`causee`/受身動作主の `agent`（述語の意味に合う `experiencer`/`attribute` もありうる）、で＝`place`/`instrument`/`cause`（通常伴う `companion` もありうる）、へ＝`goal`、と＝`companion`/`quotation`/`standard`/`value`、から＝`source`/`cause`/`time`/受身動作主の `agent`、まで＝`time`/`goal`/`place`（範囲の終端）、より＝`source`/`standard`/受身動作主の `agent` とする。これは典型の対応であり、助詞だけで役割を決める規則ではない。入力語の普通の意味で述語に通常伴う格を、項だけでなく場所・時・原因・手段・同行・起点・終点・比較基準などの付加格も含めて申告させる。付加格は、その述語に普通に伴わないなら足さない。役割と型は別々に判断させる。語・述語・例文の一覧はプロンプトに加えない。試行後にこのプロンプトを変更しない。変更する場合は新しい台帳名を使い、試行結果を同一版の評価に混ぜない。

**役割対応表の事前登録補足（2026-10-04 20:51:13 +0900）**: 20:38:46版の対応表には `causer`・`causee`・`beneficiary`・`value` と `に`・`から`・`より` の受身動作主 `agent` を明記していなかった。更新版は、が＝`agent`/`entity`/`causer`（述語の意味に合う `experiencer`/`attribute` も含む）、を＝`patient`/`causee`、に＝`recipient`/`goal`/`result`/`place`/`time`/`beneficiary`/`causee`/受身動作主の `agent`（規約に合う `experiencer`・`attribute` もありうる）、で＝`place`/`instrument`/`cause`（普通に伴う `companion` もありうる）、へ＝`goal`、と＝`companion`/`quotation`/`standard`/`value`、から＝`source`/`cause`/`time`/受身動作主の `agent`、まで＝`time`/`goal`/`place`、より＝`source`/`standard`/受身動作主の `agent` を明示する。理由は、9助詞の典型だけでなく、閉じた規約にある通常の役割をモデルに省略させないため。語の一覧や述語の例は加えず、同じ「通常伴う付加格も含める」規則を保つ。この追記も試行出力を見る前の登録であり、プロンプトhash・スクリプトhash・needsと試行束のhashを更新して再凍結する。

**試行束の抽出と判定**: 母集団は凍結した `needs_role.jsonl`（r8/run2由来の8,311語）。語を辞書順にした列に対し `random.Random(20261004).sample(words, 40)` を使い、抽出順で40語を1束にする。欠落・棄権・無効回答も分母40に含め、`parse_output_role` で有効に回収された各語の枠に各助詞を少なくとも1つ申告した異なる語の数を率の分子とする。run1の申告率は で 4.5%、へ 2.1%、から 5.0%（監査役判断4に付された第8ラウンド指示。入力記録とSHA-256は `artifacts/w3-a6/current-r2/auditor_run1_rates.txt`）。40語束では、でが2語以上（5.0%）、へが1語以上（2.5%）、からが3語以上（7.5%）で、3条件を同時に満たした場合にだけ「試行束の申告率がrun1から上がった」と判定する。からは2/40がちょうど5.0%で改善にならないため、3語を下限とする。達成はプロンプトの適合性や申告の正しさの証拠ではなく、監査役が本番生成へ進むか決めるための事前登録した通過条件である。試行出力のない現時点では未測定である。

**run1率の出典表記訂正（2026-10-04 20:56:18 +0900）**: 変更前は上記の出典を第7ラウンドレビューと記した。変更後は、これらの3値を実際に指定した監査役判断4付きの第8ラウンド指示と記録する。第7ラウンドレビュー本文にはこの3値が掲載されていなかったためで、数値・判定基準は変えない。指示ファイルのSHA-256は `auditor_run1_rates.txt` に残す。

**新しい台帳と範囲**: needs一覧を `artifacts/w3-a6/current-r2/needs_role_v2.jsonl` に凍結し、試行40語を `trial_needs_role.jsonl` に凍結する。試しの束は別出力先の `gen_role_v2_trial` に1束・最大1呼出・再試行なしで作る。本番用 `generate_and_collect.sh` は `--kind role` だけを `build/coarse-W3a/full/r9/gen_role_v2/` に実行・回収・要約する。名詞型（`--kind ntype`）と `gen_ntype` は実行しない。どちらのスクリプトも `gpt-6-luna`・`effort low` を使い、needs・prompt/schema・試行一覧・両スクリプトのhashを同じディレクトリの凍結ファイルで照合してから呼び出す。呼出回数の上限は試行1回、本番は40語束に対し最大624回（208束×最大3試行）とし、台帳・summaryで実数を記録する。ここでは両スクリプトを作成・hash凍結するだけで、実行しない。

**既存テストの固定値更新（監査役判断4、2026-10-04 20:35 +0900）**:

- `tests/coarse_place/test_coarse_place_types.py::test_inventory_only_grows`: 変更前は `17 == len(ct.NOUN_TYPES)`、変更後は `18 == len(ct.NOUN_TYPES)`。理由は `RELATIVE_POSITION` を名詞型に追加するチケット契約。既存17型のidは保ち、述語枠と役割枠では `FRAME_NOUN_TYPES` の17型を使い続ける。
- `tests/test_gen_coarse_evidence_pred.py::test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word`: 変更前は `ct.NOUN_TYPES` の一覧と13+17の総数を期待、変更後は `ct.FRAME_NOUN_TYPES` の一覧と13+17を期待する。述語プロンプトは新しい名詞型を含まないため、従来の述語プロンプトhashを維持する。
- `tests/test_gen_coarse_evidence_pred.py::test_the_schema_is_closed_and_its_enums_are_the_inventories`: 変更前は述語frame enumを `list(ct.NOUN_TYPES)` と17型で期待、変更後は `list(ct.FRAME_NOUN_TYPES)` と17型で期待する。`NOUN_TYPES` 自体は18型、述語frame schemaは17型のまま。

3件ともテスト名は維持し、データ・条件の削除や弱体化はしない。テストdocstringにも変更日時・変更前後・契約上の理由を記録する。

### 12.18.1.3 第9ラウンド・run2測定の事前登録（2026-10-04 22:38:09 +0900）

監査役の追加指示に基づき、完了済みの `gen_role_v2` 生成を再実行せず、その `role_frames.jsonl` と既存の `gen_ntype/noun_types.jsonl` を使って `r9/run2` を構築し `verify` する。`gen_role_v2`・`gen_ntype` の生成台帳と生成物は読み取り専用とし、`r9/run1` は比較用に保持する。

- **N2**: 凍結期待 `tests/coarse_place/data/w3a6_expect.json` の10述語・11役割行ごとに、run1・run2それぞれの申告、確認状態、未確認状態、および確認を支える分布の腕と有意な型を表にする。run2の確認済み役割は `backed_by` に列挙された腕が有意な `(助詞, 型)` を示すことを照合する。
- **N3**: 既存の凍結相対位置語と相対位置目視ラベルを再利用し、run2で再問い合わせする。r8からPLACE判定が変わった全名詞について、run2の `state/origin/top` と既登録目視ラベルを出す。目視は正解データではない。
- **N4/D9**: 固定標本は `artifacts/w3-a6/n4_claims_prefreeze.jsonl` の60語を使う。`gen_role_v2` のこの標本に対する申告を取り出し、確認結果を見ずに全申告を既登録の目視基準で「正しい／疑わしい／誤り」に分類する。申告とラベルを結合したファイルのSHA-256を、確認結果との結合より先に記録する。run2の実分布に対し `role_frame_min_sources` 候補1、2、3を評価し、確認済み役割行中の明らかな誤り率が10%以下となる最小候補を選ぶ。3でも超過したら3を固定しN4未達とする。確認役割が0行なら誤り率は未測定として合格扱いしない。選択値を凍結設定に記録してrun2を構築する。
- **N5**: 凍結された281述語seedの `namespace/state/origin/top` をrun2とr8で比較し、相違があれば全件と理由を列挙する。
- **申告率・manifest**: run1（旧 `gen_role`）とv2の粒子別申告率は、各助詞について、少なくとも1役割を申告した異なる述語語数 ÷ 凍結対象8,311語で算出する。欠落・棄権も分母に含め、申告率は正しさの根拠としない。別の測定manifestにrun1/run2双方の配置SHA-256・構築時間、gen_ntypeと両role生成のモデル・effort・呼出数・所要時間、粒子別run1→v2申告率を記録する。測定物とN2/N3/N4/N5の集計は `artifacts/w3-a6/r9/` に保存する。

<!-- w3a6-measured:begin -->
測定日: 2026-10-04（事前登録・期待凍結・製品差分の時刻は `artifacts/w3-a6/prereg_timeline.txt`）。開始時の差分は指示書 §0.1 の想定と異なり、既存の途中作業を保持して続行した（`artifacts/w3-a6/initial_state.txt`）。

- 生成対象一覧は r8/run2 の読み取り専用配置から作った。名詞型は 2,721 語、役割枠は 8,311 語で、凍結期待にある位置語と述語はすべて一覧に含まれた（`artifacts/w3-a6/needs_ntype.meta.json`、`needs_role.meta.json`、`needs_check.txt`）。40語束・3回/束の上限は各207回・624回（`artifacts/w3-a6/gen_plan.txt`）。
- N1 の全体回答は r7 1,758,845行、r8 1,766,903行で前後一致した。配置なし200語と読解入口の配置なし・r8（各4,149行）も前後一致した（`artifacts/w3-a6/n1/n1_cmp.txt`）。
- W3-a6 の生成器・型・判定・builder・query の追加試験を含む確認は48件通過した（`artifacts/w3-a6/tests_core.txt`）。構築前の関連試験は1,055件通過し、失敗5件は C1 に記録した5件のみだった（`artifacts/w3-a6/tests_pre_gen.txt`）。述語プロンプトとschemaの既存hash、および名詞プロンプトhashは維持された（`artifacts/w3-a6/prompt_sha.txt`）。
- 実装依頼のネットワーク禁止に従い、モデル生成・試しの束・本番生成は行っていない（実呼び出し0回、`artifacts/w3-a6/gen_plan.txt`）。`role_frame_min_sources` の事前評価と凍結、config、r9/run1 の構築は未実施。したがって N2〜N5、r8→r9 全差分、不変条件、r9の生成・構築時間とcontent hashは未測定である。
- 目視判定は行っていない。人工テストと偽codexの通過は、生成回答の正確さを示すものではない。

- 最終全体テストは 189 failed, 15,115 passed, 46 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed で終了した（`artifacts/w3-a6/pytest_full.txt`）。基線115件に対し新規74件・解消0件（`failure_delta.txt`）。新規は C1 の5件、原因を個別確認できていない conduct系68件、指示書の環境由来候補にある `test_s6_two_runs_agree_except_timing_and_recount_matches` 1件に分かれる。conduct系のrun台帳55件にsandbox-execの `Operation not permitted` が記録されたが、全体コマンドが `--tb=no` のため68件それぞれとの因果対応は未確認（`sandbox_full_evidence.txt`、`new_failures_explained.txt`）。N7 は未達。
- 最終の読み取り専用hash照合、モジュール由来確認、status確認と作業報告は `artifacts/w3-a6/impl.r1.md`、`readonly_after.txt`、`check_modules_final.txt` に記録する。

### 第2ラウンドの再確認（2026-10-04）

- N1 を基点 `0041606` と現在のツリーで再計算した。r7/run1 は双方 1,758,845 行・SHA-256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`、r8/run2 は双方 1,766,903 行・`5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`、配置なしは双方200行・`a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。読解入口の配置なし・r8 は各4,149行でそれぞれ `84b2c118d271153e92eb5c189b16867bc5da01992d2745673a9b3866e16e99c7`・`ce351ef41bd9cb3ee67867025911720d0214924f2ec662a56a4e7347801c7924`。5比較はすべて `cmp` 一致（`artifacts/w3-a6/r2/n1/query_results.txt`、`cmp_all.txt`、`entry_hashes.txt`）。N1関連試験40件も通過（`artifacts/w3-a6/r2/tests_n1.txt`）。
- W3-a6の追加試験を含む確認は48件通過（`artifacts/w3-a6/r2/tests_core.txt`）。凍結期待のhashは `bea8c8a1dd97dbb6b1f5c4bd7d44c44ac7b322036cc2366027e714b37814af33` のままで、実測ファイルには10述語・11役割行・15語がある（`expect_inventory.txt`）。「9述語」という見出しとの差は変えていない。
- 全体試験は `189 failed, 15123 passed, 38 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 572.56s`。基線115件との差は新規74・解消0（`artifacts/w3-a6/r2/pytest_full_r2.txt`、`failure_delta.txt`）。新規74件は計画済みC1の5件、sandbox自己検査で失敗したconduct系68件、未コミットの作業差分を検出した `test_s6_two_runs_agree_except_timing_and_recount_matches` 1件。conduct系68件はtraceback付き単独実行でも同じID集合で失敗し、`sandbox-exec` の単独プローブはexit 71・`Operation not permitted`（`conduct_tracebacks.txt`、`conduct_full_compare.txt`、`sandbox_probe.txt`）。S6 のrun metadata は `verantyx_untouched: false`（`bt-triage` の出力）。停止signal試験は全体実行では失敗IDに含まれなかったが、単独では基点と現在の双方で20秒timeoutを再現した（`triage_tests.txt`、`base_stop_test.txt`）。N7は未達。
- 全体試験後の攻撃用 `r6_48_queries.jsonl` は48行すべて `frame_generated` 鍵だけがHEADと異なっていた。HEADの内容へ戻し、SHA-256 `556436a80a9d521af1826722dc789b25773f01d0d6e41d6422530498b1bbb642` を確認した（`attack_side_effect.txt`、`attack_hashes_before_full.txt`、`attack_hashes_after_full.txt`）。
- 第2ラウンドはユーザーの明示したネットワーク禁止に従い、本物の生成呼び出しは行わなかった。共有ビルドにr9/run1はなく、生成後のN2〜N5・N6用測定は未実施（`r9_availability.txt`）。したがって生成とr9を求めた前回レビューの必須項目は未解決で、`role_frame_min_sources` も凍結していない。

### 第3ラウンドの再確認（2026-10-04）

- 前回レビューの必須修正3に従い、基点の `coarse_types.py` を `git show` からメモリ上で読み込むよう比較試験を変更した。基点履歴が無ければ失敗し、`skip`・`tempfile`・`mkdtemp` を使わない。対象6件は通過した（`artifacts/w3-a6/r3/tests_decide.txt`）。W3-a6関連48件とN1関連40件も通過（`tests_core.txt`、`tests_n1.txt`）。W3-a6関連試験の初回実行はbasetempの親ディレクトリ未作成でsetup errorになったため、親を作成して再実行した。初回出力は保存していないため、対象は再実行結果だけを採用する。
- 全体試験の最終行は `189 failed, 15123 passed, 38 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 438.51s`。基線との差は新規74・解消0（`artifacts/w3-a6/r3/after_failures.txt`、`new_failures.txt`、`fixed_failures.txt`）。内訳はC1の5件、conduct系68件、S6 1件。conduct系とS6を環境由来として除外しておらず、N7は未達（`new_failures_explained.txt`）。
- 全体試験が攻撃用 `r6_48_queries.jsonl` を48行更新した。HEADとの差の変更は `frame_generated` キーのみで、実行前SHA-256 `556436a80a9d521af1826722dc789b25773f01d0d6e41d6422530498b1bbb642` に復元した。他の2出力は前後でSHA-256が一致した（`attack_side_effect.txt`）。
- このラウンドでは製品コード・生成器・builder・配置を変更せず、ユーザーのネットワーク禁止を守って本物の生成を行わなかった。共有ビルドのr9/run1は無く、N2〜N6、閾値の事前評価、生成台帳と構築時間は未確認。第2ラウンドの全数N1比較を根拠として保持し、このラウンドは関連40試験で再確認した。
- 指定venvから読み込んだ `verantyx` モジュールの作業ツリー外一覧は空（`check_modules_final.txt`）。作業ツリーに `__pycache__` と `.pytest_cache` は見つからなかった。

### 第1レビュー指摘に基づく事前登録の訂正（2026-10-04 16:00:24 +0900）

本物の生成と新しい受入測定の前に、レビュー指摘に基づき、未承認のN7例外を除き、凍結期待に記録された述語数・役割行数にN2を合わせた。テスト期待と凍結データは変更していない。測り方段落の訂正前後を全文で記録する。

**訂正前**:

> **測り方（受入基準）**: N1 = r7・r8 の全見出し語の `query` の答え全体（`json.dumps(ensure_ascii=False)` の sha256）と配置なしの固定の語の答え、読解の入口の出力が基点と byte 一致。N2 = 述語 9 個（試験データにだけ置く）の `role_frame` が期待の役割を含み、CONFIRMED の役割は `backed_by` の腕の有意な (助詞, 型) に裏づけられる。N3 = 相対位置の語 15 個（試験データにだけ置く）が PLACE 単独の direct でない、PLACE から変わった名詞の全件の目視で明らかな誤りが 1 割以下。N4 = 無作為 60 語（`random.Random(20261004)`）の CONFIRMED の役割の明らかな誤りが 1 割以下。N5 = seed の判定が r8 と同じ。N7 = 既存テストの失敗集合が基線から増えない（`NOUN_TYPES` の追加による避けられない衝突は別に宣言する）。

**訂正後**:

> **測り方（受入基準）**: N1 = r7・r8 の全見出し語の `query` の答え全体（`json.dumps(ensure_ascii=False)` の sha256）と配置なしの固定の語の答え、読解の入口の出力が基点と byte 一致。N2 = 10述語・11役割行（試験データにだけ置く）の `role_frame` が期待の役割を含み、CONFIRMED の役割は `backed_by` の腕の有意な (助詞, 型) に裏づけられる。N3 = 相対位置の語 15 語（試験データにだけ置く）が PLACE 単独の direct でない、PLACE から変わった名詞の全件の目視で明らかな誤りが 1 割以下。N4 = 無作為 60 語（`random.Random(20261004)`）の CONFIRMED の役割の明らかな誤りが 1 割以下。N5 = seed の判定が r8 と同じ。N7 = 既存テストの失敗集合が基線から増えない。

N7は例外のない基準として扱う。既存テストとの契約衝突が残る場合も、N7は未達と記録する。

### 生成前の凍結（2026-10-04 16:00 +0900）

- r8/run2 から同じ規則で生成対象一覧を作り直し、従前の凍結一覧と両方とも `cmp` 一致した。名詞型 2,721 語、役割枠 8,311 語。SHA-256 と対象 meta は `artifacts/w3-a6/current-r1/freeze.sha256`、`needs_ntype.meta.json`、`needs_role.meta.json`。
- 役割枠の 8,030 語は r8 の `generated_frames` 全数、seed 281 語は重複なし。r8 のサ変生成枠 3,485 語のうち direct の P_COMMUNICATE/P_MOVE 70 語すべてが、この 8,030 語内に入っている（`artifacts/w3-a6/current-r1/sahen_role_coverage.txt`）。
- 訂正後の型プロンプトは template/schema SHA-256 `a22e217ad80fc6bd043864b6ee414ef931d3b174a08f1522ce6555b6a9496a29` / `e3db31ed9adba39b1a53979cbe84f5113bd778c90c1437a753ce8a67e995825e`。役割プロンプトは `681af73d25ac03a21afe840c7d9bc953d587f0ae4bc67ba8945460f89b77117d` / `2d5a9ed449bfdd4899e13048c4e40ddce895ffaa72b2b77f0702773159ddf5f1`（保存先 `artifacts/w3-a6/current-r1/prompt_ntype.txt`、`prompt_role.txt`）。
- 期待ファイル `tests/coarse_place/data/w3a6_expect.json` は SHA-256 `bea8c8a1dd97dbb6b1f5c4bd7d44c44ac7b322036cc2366027e714b37814af33` のまま。生成対象、期待ファイル、プロンプトの凍結hashは `artifacts/w3-a6/current-r1/freeze.sha256`。

### 最終役割プロンプトの凍結（2026-10-04 16:02:15 +0900）

最初の生成前凍結後、役割説明を規約 §2 にさらに揃えた（`agent` は授受表現で実際に動作した人、`time` は期限と助詞の有無、`causer` は動作をさせた側、`beneficiary` は恩恵・利益を受ける人を明記）。この修正までにモデル呼び出しは0回。名詞型・役割枠の入力一覧と期待ファイルは変わっていない。最終役割プロンプトの template/schema SHA-256 は `ade8ca7d2752d7547711e6613b5f7d00d5adb7656ae9183100938ed5c9e8c4d8` / `2d5a9ed449bfdd4899e13048c4e40ddce895ffaa72b2b77f0702773159ddf5f1`。生成には `prompt_role_v2.txt` と `freeze_final.sha256` の版を使い、生成後は変更しない。

### 生成結果の目視前登録（2026-10-04 16:05:58 +0900）

- N3は、凍結済み `needs_ntype` のうち生成回答が `RELATIVE_POSITION` を申告した語を全数対象にする。目視ラベルは語と生成定義文だけを使い、r9の判定結果を見る前に表を作ってhashを固定する。その後、r8/r9のstate・origin・topの全差分と突き合わせる。
- N4の標本母集団は凍結済み `needs_role` の語集合。辞書順に並べた重複なし一覧から `random.Random(20261004).sample(words, 60)` で非復元抽出する。回答欠落・null棄権も抽出結果に残し、別理由で数える。
- N4の目視表には各標本語の全申告助詞・役割・型を載せ、確認状態を見ずに正しい／疑わしい／明らかな誤りを付け、表hashを先に固定する。その後にCONFIRMED結果と結合し、明らかな誤り数／CONFIRMEDされた役割数を計算する。CONFIRMED役割が0件なら率を作らず未測定とする。
- これらの目視は実装役の読みで正解データではない。数えとハッシュは `artifacts/w3-a6/current-r1/` に保存する。

### 実装役の再実行記録（2026-10-04）

- N4の標本語は `needs_role` 8,311語から60語を抽出した。SHA-256 `a134ac9c47060072911630ee8de7f9fadaca3f1c480a3afe9c7710af983da198`（`artifacts/w3-a6/current-r1/role_sample_meta.json`、一覧は `role_sample_words.jsonl`）。役割生成の回答が得られなかったため目視表は作らず、N4は未測定。
- 関連試験 `tests/coarse_place`、`tests/test_gen_coarse_evidence.py`、`tests/test_gen_coarse_evidence_pred.py` は `356 passed, 3 failed in 22.65s`（`artifacts/w3-a6/current-r1/tests_related.txt`）。失敗は `test_inventory_only_grows` と述語プロンプト・schemaの17型固定の2件。NOUN_TYPESを18型にするチケット要件との契約衝突で、テスト期待は変更していない。全体テストは監査役指定に従い実行していない。
- Codexの監視実行は `2026-10-04 16:13:22 +0900` から `16:14:09 +0900`。名詞型は207プロセス試行／69束、役割枠は624プロセス試行／208束、各 `gpt-6-luna`・effort `low` 指定だったが、すべて `EXIT_1`、成果物出力0件。各エラー末尾は `failed to initialize in-process app-server client: Operation not permitted (os error 1)`（`generation_failure_counts.txt`）。summaryの `wall_sec` は名詞型11.6秒・役割枠35.3秒、`sum_call_sec` は45.8秒・140.2秒。モデル応答は一件も得ていない。出力とledgerは `build/coarse-W3a/full/r9/gen_ntype/`、`gen_role/` に保存されている。
- N1の全数query再計算は `2026-10-04 16:19:51` から `16:29:43 +0900`。r7は1,758,845語・293.9秒・SHA-256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`、r8は1,766,903語・297.1秒・`5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`、配置なし200語・0.0秒・`a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。3値とも以前の基点ハッシュと一致（`n1_r7_current.txt`、`n1_r8_current.txt`、`n1_none_current.txt`、比較記録 `n1_comparison.txt`）。読解入口の4149文は本作業では再実行していないが、前回レビューが配置なし・r8をともに基点とcmp一致と報告している（`/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W3-a6/review.r1.md` §N1）。その後読解器のコードは変更していない。
- detached起動の1回は開始記録だけで監視プロセスが残らず、ledger・raw応答・終了記録を作らなかった（`generation_attempt1.started`）。その後の監視実行は生成器のledger開始記録前にCodexを起動するので、モデル呼び出しに至っていないと判断した。再試行前後の記録は `generation.log`、`generation.started`、`generation.finished` と各summary/ledger。
- 実生成回答が0件のため、`role_frame_min_sources` は評価・凍結できず、r9/run1は構築していない。N2・N3・N4・N5は未測定。N6は監査役の測定項目で、実装役は隠しバンクを開いていない。N7全体失敗集合は監査役の測定待ち。
### 第7ラウンドの事前登録と実測（事前登録 2026-10-04 19:01:32 +0900、測定 2026-10-04）

監査役の追加指示に従い、生成済みr9を再実行せず、生成summaryと回答JSONLから測定した。N3/N4の申告・目視表とN5の語一覧はr9判定と比較を行う前に作成してsha256を固定した。凍結出力は `artifacts/w3-a6/r7_prefreeze_output.txt`、`r7_prefreeze.sha256`、`r7_visual_freeze.sha256`、`r7_n5_freeze.sha256`。

- `role_frame_min_sources` はD9の「誤り率が基準を超えたとき上げる方向だけ」の規則で候補1・2・3を評価した。60語の閾値1はCONFIRMED役割17行中、正しい15・疑わしい1・明らかな誤り1、1/17=5.88%。閾値2は1/7=14.29%、閾値3は1/6=16.67%。よって1のままにした（`n4_d9_thresholds_r7.json`、`n4_d9_measure_r7_final.txt`）。
- **N2**: 凍結期待10述語・11助詞役割行のうち、期待役割を申告した行は4、確認された期待役割は1、未確認は4（部分確認された型も未確認に計上）。述語行のstatusはCONFIRMED 8、ESTIMATED 3。`連絡する/に/recipient` はPERSONが `role_distribution@codex:narrative`・`paraphrase_entail`・`pro` の3腕で裏づけられCONFIRMED、GROUP_ORGはPARTLY_BACKED。`停泊する/に/place`、`通報する/に/recipient`、`分ける/に/result` は申告があるが裏づけなし。`確認する/で/place` にはinstrumentの申告だけで、その他の未申告期待行もある。backed_by検査は通ったが期待役割の申告が未達のためN2は未達。全表は `n2_predicate_role_rows_r7.jsonl`、集計は `n2_predicate_role_summary_r7.json`。
- **N3**: 必須15語は全てPLACE単独のdirectではなかった。r8からPLACE判定が変化した名詞292件を全件列挙し、目視は正しい253、疑わしい37、明らかな誤り2、未評価0。誤り率2/292=0.685%で基準内。全差分・目視表・集計は `n3_place_changes_r7.jsonl`、`n3_relpos_visual_labels_r7.jsonl`、`n3_summary_r7.json`。目視は実装役の判断で正解データではない。
- **N4**: `random.Random(20261004)` で8,311語から60語を抽出。81申告行を目視し、正しい57・疑わしい17・明らかな誤り7、回答棄権2語・欠落0語。閾値1では語statusがCONFIRMED 14、ESTIMATED 44、NO_ROLE_FRAME 2。CONFIRMED役割17行中の誤りは1（5.88%）で基準内。申告・目視・確認結合・集計は `n4_claims_prefreeze.jsonl`、`n4_visual_labels_r7.jsonl`、`n4_d9_confirmed_roles_r7.jsonl`、`n4_visual_labels_r7_summary.json`、`n4_d9_thresholds_r7.json`。目視は正解データではない。
- **N5**: 述語seed 281語のnamespace/state/origin/topを比較し、同一281・差分0。凍結語一覧hashは `n5_seed_words_prefreeze.meta.json`、比較表・空の差分一覧・集計は `n5_seed_comparison_r7.jsonl`、`n5_seed_differences_r7.jsonl`、`n5_summary_r7.json`。
- **N1**: query全数を再実行。配置なし200語は0.0秒、SHA-256 `a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。r7 1,758,845語は284.2秒・`3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`、r8 1,766,903語は289.6秒・`5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`。3値とも過去の基点hashと一致（`n1_current_none_r7.txt`、`n1_current_r7_r7.txt`、`n1_current_r8_r7.txt`）。読解入口の出力比較はこのラウンドで再実行しておらず、r2の `artifacts/w3-a6/r2/n1/cmp_all.txt`・`entry_hashes.txt` を参照した。
- **r9/run1・manifest**: `sh artifacts/w3-a6/scripts/build_r9_run1.sh` で構築し、`tools/build_coarse_placement.py verify --placement build/coarse-W3a/full/r9/run1` は `state: OK`・`bad: []`。headwords 1,766,903、evidence 1,948,020、generated_frames 8,030、generated_noun_types 2,704、role_frames 8,024、direct placement 992,773。構築268.2秒、content SHA-256 `72945370d9299600e1beca212fc2ed286940506d47fdd0fb50e403ee7bacb5a9`（`r9_verify_final.txt`、`r9_build_run1_summary_only.log`、`build/coarse-W3a/full/r9/run1/manifest.json`）。
- manifestは `summary.json` のsha256と生成量を保存した。名詞型は2,721要求・2,721回答、69呼出、effort low / gpt-6-luna、wall 461.4秒・sum_call 1,822.6秒、棄権17・欠落0。役割枠は8,311要求・8,266回答、208呼出、effort low / gpt-6-luna、wall 2,083.9秒・sum_call 8,263.8秒、欠落32・棄権242を別々に記録し未利用合計274。invalid 8、重複助詞5。総呼出277。
- **N6/N7**: 監査役の測定項目のため未実行。関連試験は358 passed、3 failed。失敗は `test_inventory_only_grows` と、述語prompt/schemaが旧17型を固定する2件（`tests_related_r7_final.txt`）。既存期待変更は監査役の明示許可が必要なため触れず、N7の契約衝突として残した。builder試験2件はpass（`tests_w3a6_build_r7_final.txt`）。
- **手順逸脱**: 初回buildは抽出stage cacheなしで全抽出を開始後、Ctrl-Cで終了コード130（`r9_build_run1_interrupted.log`）。r8抽出cacheをr9にコピーし、SHA-256 `7972cc236bae2953b06915eabe82a037dfce47a314877edb5a63ce43df1eef49` の一致を確認して再構築した。また候補buildではledger引数を付けてしまい、builderがr9 ledgerを読み取った。書換えはしていないが「ledgerに触らない」に反した。候補manifest/logを保存し、最終buildはledger引数を外し `summary.json` のみで記録した（`r9_manifest_candidate_with_ledger.json`、`r9_build_run1_with_ledger.log`、`r9_build_run1_summary_only.log`）。生成自体は再実行していない。
- module import 6件は全て作業ツリー内で `outside_tree []`（`check_modules_final_r7.txt`）。試験後の `__pycache__` / `.pytest_cache` は見つからなかった。主要実測のhash照合は `r7_final_hashes.sha256`。

### 第9ラウンド・run2実測（2026-10-04、詳細は `artifacts/w3-a6/r9/`）

- **N1**: 現行queryでr7全1,758,845語は285.8秒・SHA-256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`、r8全1,766,903語は288.9秒・`5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`、配置なし200語は0.0秒・`a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。基点の凍結回答と3件とも `cmp` exit 0。読解入口の配置なし・r8の凍結出力も4,149行ずつで `cmp` exit 0（入口自体は再実行せず、保存済み前後出力を比較）。記録は `n1_*_current.txt` と `n1_cmp_final.txt`。
- **N2**: 10述語・11役割行の期待申告はrun1 4/11からrun2 10/11へ増加。期待役割の確認はrun1 1/11、run2 2/11。run2の確認済み期待役割は `連絡する/に/recipient`（PERSON、3腕）と `運ぶ/へ/goal`（PLACE、narrative腕）で、双方の有意型の照合は通過した。`待つ/で/place`はrun2で申告されず、他の期待役割も未確認が残るためN2は未達。全11行・run1比較・腕と有意型は `n2_table_run1_vs_run2.md` と `n2_run1_vs_run2.jsonl`。
- **N3**: 必須の相対位置語15/15がPLACE単独directでない。r8からPLACE判定が変わった名詞292件を全件列挙し、目視は正しい253・疑わしい37・明らかな誤り2・未評価0、明らかな誤り率2/292=0.6849%。目視は正解データではない。詳細は `n3_required_words_run2.jsonl`、`n3_place_changes_run2.jsonl`、`n3_summary_run2.json`。
- **N4/D9**: 凍結60語のうちv2で採択された申告は58語・152役割行。目視ラベルは正しい129・疑わしい17・明らかな誤り6。D9候補1/2/3の確認済み役割行はそれぞれ21/6/6、明らかな誤りは各0行で、明らかな誤り率はいずれも0%。最小候補の `role_frame_min_sources=1` をrun2設定に固定した。閾値1では語状態がCONFIRMED 16、ESTIMATED 42、NO_ROLE_FRAME 2。目視は正解データではない。申告・ラベル・先行SHA-256は `n4_claims_run2_prefreeze.jsonl`、`n4_visual_labels_run2.jsonl`、`n4_visual_freeze.sha256`、確認結果は `n4_d9_run2_final.json`。
- **N5**: seed 281語はr8/run2とrun2で281/281一致、差分0。run1からrun2も281/281一致。全件は `n5_seed_comparison_run2.jsonl`、差分一覧は空の `n5_seed_differences_run2.jsonl`。
- **生成・構築manifest**: gen_ntypeは69呼出・gpt-6-luna/low・wall 461.4秒・sum_call 1,822.6秒。run1のgen_roleは208呼出・low・wall 2,083.9秒・sum_call 8,263.8秒。run2のgen_role_v2は208呼出・失敗0・8,255回答・low・wall 3,109.9秒・sum_call 12,327.2秒。構築時間はrun1 268.2秒、run2 474.0秒。run1 content SHA-256 `72945370d9299600e1beca212fc2ed286940506d47fdd0fb50e403ee7bacb5a9`、run2 `e58908eb4eba8820fed9eafcd1ff42a5a70cdfdf4c35a9646b5dd49aaa002a21`。run2 verifyは `OK`、headwords 1,766,903・evidence 1,948,020・generated_noun_types 2,704・role_frames 8,095・direct placement 992,773。両runの配置manifest・ファイルhash、生成呼出数・effort・時間、粒子別申告率を `manifest.json` に収録した。

|助詞|対象8,311語を分母にした申告率 run1→v2|採択済み枠を分母にした申告率 run1→v2|採択済み枠での増分（ポイント差）|
|---|---:|---:|---:|
|が|40.1% → 60.6%|41.5% → 62.2%|+20.7232|
|を|61.9% → 65.0%|64.1% → 66.8%|+2.6495|
|に|28.2% → 51.2%|29.2% → 52.6%|+23.4008|
|で|4.4% → 38.0%|4.5% → 39.0%|+34.5125|
|へ|2.0% → 4.8%|2.1% → 4.9%|+2.8478|
|と|5.1% → 10.9%|5.3% → 11.2%|+5.9076|
|から|4.8% → 15.9%|5.0% → 16.3%|+11.3213|
|まで|0.2% → 3.6%|0.2% → 3.7%|+3.4695|
|より|0.1% → 0.5%|0.1% → 0.5%|+0.4194|

申告率は申告の正しさを示さない。事前登録した主指標は対象8,311語を分母とする率。追加の有効回答分母は、既存のrun1参照値（で4.5%、へ2.1%、から5.0%）が、run1採択済み8,024枠で計算した値を小数1桁に丸めた値と一致することを確認するため、比較用に併記した。最初の8,311語分母版manifestも `manifest_preregistered_8311_denominator.json` に保存した。

- **関連テスト**: `tests/coarse_place tests/test_gen_coarse_evidence.py tests/test_gen_coarse_evidence_pred.py` は2回の全体実行とも360 passed・1 failed。失敗は `test_the_stop_signal_ends_the_run_with_an_interrupted_record` の `communicate(timeout=20)`。同テスト単独の再実行は1 passed in 0.49s。理由を確定できず、テストや期待は変更していない。出力は `tests_related.txt`、`tests_related_retry.txt`、`test_stop_signal_retry.txt`。全体テストとN6は監査役の担当範囲のため未実行。
- **手順記録**: 最初のr7 `cmp`は別ラウンドのscratchpad出力を参照してexit 1だった。ファイル内容SHA-256がその前後ログに記された総hashと異なると分かり、N1スクリプトの正規凍結出力 `scratchpad/W3-a6-impl/n1/` に対して比較し直すとr7/r8/配置なし・読解入口の全cmpがexit 0。失敗出力も `n1_r7_comparison.txt` に残した。検査JSONを読み取る補助確認で一度だけ指定外のsystem `python3` を使ったが、`verantyx`を読み込まず書込みもしないコマンドであり、その後の生成・測定・テストは指定venvを使用した。

<!-- w3a6-measured:end -->

## 12.19 W10-f05: 配置の層と文書駆動の育成（事前登録）

事前登録の日時は `artifacts/w10-f05/prereg_time.txt`（書く前と書いた後の 2 行）。検査データの凍結（`data_freeze_time.txt`）はこの節より後。以下の数値は閾値・件数の約束であり、測定値ではない（測定値は §12.19.M に出力ファイルつきで機械で貼る）。

### K290〜K297（チケットから）
- **K290 層は基底を上書きしない**: 基底が DECIDED（direct）の語は層を見ない。層の答えが使われるのは基底が UNPLACED／UNKNOWN／MULTIPLE のときだけ。MULTIPLE の場合、層の direct は基底の候補に含まれる型のときだけ使う（候補外なら `LAYER_TYPE_NOT_AMONG_CANDIDATES` で基底のまま）。
- **K291 direct の条件**: 層で direct になるのは (a) 生成×分布の一致（W3-a2/W3-a6 と同じ規則・閾値。分布の出所の数は文書の数で、`min_sources` は設定（既定 1）。文書が 1 本なら 1 本の中で `rd_*` の閾値を満たすこと）、(b) 人の確認、のどちらか。LLM の申告だけ・再読一致だけは `ESTIMATED` 止まり。
- **K292 分布は与えた文書だけ**: 文書群以外（生成コーパス・Web）を分布に混ぜない。文書ごとに出所を分け、同じ文書を 2 回数えない（本文の sha で重複を除く）。
- **K293 記録は変えない**: 文書の本文は 1 文字も変えない。層と台帳は記録とは別のファイル。層を外せば基点の振る舞いに戻る。
- **K294 台帳の連鎖**: 層への書き込みはすべて台帳の行（`promoted_to_layer`）として連鎖に残る。層の SQLite から台帳の行 id を引ける。
- **K295 後段**: `fake`（台本）で全規則をテスト、本物は Ollama のローカル接続だけ。後段の失敗は型つき失敗で、層に何も書かない。
- **K296 秘匿**: 既定で LLM へ渡すのは候補の語と、その語を含む文の型つきの穴の形。文の全文を渡す `--send-sentences` は明示のときだけ（台帳に印）。
- **K297 不変**: 層なし・`VERA_PLACEMENT_LAYER` 未設定のとき、`vera read/ask/serve` と `coarse_place.query` の出力は基点と byte 一致。

### 設計の確定（指示書 §1.1〜§1.9 の写し）
1. **層のファイル**（`verantyx/placement_layer.py`）: 1 層 = SQLite 1 ファイル。`spec` が `/` を含むか `.sqlite` で終われば **パス**、それ以外は **名前**（`^[A-Za-z0-9_.-]{1,64}$`）で `$VERA_PLACEMENT_LAYER_ROOT/<name>.sqlite`（ROOT が無ければ `LAYER_UNAVAILABLE:ROOT_UNSET`。ホームなどを探さない）。表 `meta(k,v)`（`schema=verantyx.placement_layer/1`・`name`・`base_content_sha256`・`created_ts`）と `entries(id, word(NFKC), ns, type, origin ∈ {layer_confirmed, layer_estimated, layer_human}, decided_by, evidence, role_frame, ledger_store_id, ledger_seq, ledger_key, ts)`。**追記のみ**（UPDATE・DELETE をしない）。書き込みは `write_entry` 1 つだけ: 先に台帳へ `promoted_to_layer` 行 → その `seq` を層の行に書く。層の `base_content_sha256` と基底の sha が違えば `LAYER_BASE_MISMATCH` で何も書かない。
2. **層の答え**: `coarse_place.query(term, …, placement=…, layer=None)`。`layer` も環境変数 `VERA_PLACEMENT_LAYER` も無い（空を含む）ときは今の答えをそのまま返す（鍵を足さない・`placement_layer` を import もしない）。層ありのとき、基底の `state` と層の行の畳み込み（direct の型の集合 D、推定の型の集合 E）で `layer`（`base`|`overlay:<name>`|`none`）と `layer_status`（閉じた一覧）を決める。
   - NO_PLACEMENT → `none`／`BASE_NO_PLACEMENT`。DECIDED（estimated 含む）→ `base`／`BASE_DECIDED`（層を見ない）。
   - UNPLACED/UNKNOWN/MULTIPLE: 層が開けない → `LAYER_UNAVAILABLE:<MISSING|UNREADABLE|ROOT_UNSET|BAD_NAME|BASE_MISMATCH>`、行なし → `LAYER_HAS_NO_ENTRY`、|D|≥2 → `LAYER_CONFLICT`（同点は棄権）、D 空・E あり → `LAYER_ESTIMATED_NOT_USED`（答えの核は変えない）。いずれも基底のまま。
   - UNPLACED/UNKNOWN で D={T} → 層の direct（`LAYER_DIRECT_USED`）。MULTIPLE で D={T}、T∈基底の `top` → 層の direct。T∉`top` → 基底のまま `LAYER_TYPE_NOT_AMONG_CANDIDATES`。
   - 層の direct の答えは基点の direct と同じ鍵・同じ順＋末尾に `layer`・`layer_status`。`decided_by` は `decide_word` の `by` そのまま（`gen_definition` を消さない）、人の確認は `["layer_human"]`。`frame_status` は名詞 `NOT_PREDICATE`・述語 `NOT_CONFIRMED`（`frame` は null）。`role_frame_*` は基底の答えにその鍵があるときだけ。`origin` に `layer_*` は入れない（契約で `ORIGIN_UNKNOWN`）。
3. **育成**（`verantyx/placement_grow.py`）: 文書を `document_loaders` で読み、本文の NFKC の sha で重複を除く。文は `cli._qc_records` で切る。builder の `tokenize`/`analyze` を **import して**数える。候補 = 基底（層なし）が UNPLACED／UNKNOWN／MULTIPLE の語（名詞と述語の両方に出る語は `KIND_SPLIT` で問わない）。LLM へは閉じた enum の JSON schema で、名詞は定義文・上位語・18 型、述語は述語の型と役割つきの枠。バッチの失敗・無効は `backend_failed`／`declaration_invalid:*` として台帳に残し層に書かない。既定で送るのは候補の語・種類と、その語を含む文（最大 3）の型つきの穴の形だけ。
4. **文書を分布の腕に**: 各文書は別の出所 `doc:<本文 sha の先頭 12>`。述語は `role_distribution`、名詞は `hearst`（builder と同じ数え方。充填物の型は **基底の型だけ**）。ほかの腕は作らず `ARM_NOT_BUILT:<腕>` と数える。設定は基底の `cfg` を写し `rd_min_sources=role_frame_min_sources=--min-sources` だけ置き換える（閾値は下げない）。判定は `coarse_types.decide_word`。直 direct かつ生成の腕が `by` に入る → `layer_confirmed`。文書の腕だけで決まり型が申告と同じ → `layer_confirmed`、違う → 書かない `GEN_DISAGREES_WITH_DOCUMENTS`。生成だけ（DECIDED/estimated）→ `layer_estimated`。それ以外は書かない（理由を数える）。上位語の基底の型が申告の型と違えば生成の票にしない（`HYPERNYM_TYPE_DISAGREES`）。
5. **昇格** `vera ledger promote --layer`: `fold()` の `promotable` の行について。`human_confirmed` → `layer_human`。`reread_agreed ≥ N` だけ → `layer_estimated`（direct にしない）。基底が DECIDED → `SKIP_BASE_DECIDED`。既に同じ (key, 層, origin) の行がある → `SKIP_ALREADY_PROMOTED`（何度流しても同じ）。`distribution_backed` だけは fill の証言なら基底が DECIDED なので skip、grow の証言なら育成の時に書いてある（`SKIP_ALREADY_IN_LAYER`）。`promoted_to_layer` 行 = `{type, key, word, candidate, declared_type, layer_name, layer_base_sha256, origin, decided_by, evidence, fill_id, from_seq}`。
6. **門 (c) のソブリン**: `VERA_SOVEREIGN_ROOT`・`VERA_SOVEREIGN_STORE` が **両方とも無い** → 今と同じ（`gate_log` に鍵を足さない・`sovereign_checked=False`）。あるとき `basis_policy._read_sovereign(True)` で読み、`ACTIVE_CONSENTED` の発話（`payload.text`／`payload.phrase`）を `decode_grammar.cross_of` で十字にして、同じ `_gate_c` を別の `records` で呼ぶ。矛盾 → `GATE_C_CONTRADICTS_SOVEREIGN:<event_id>`。`sovereign_checked=True` は実際に 1 件以上比べた（n>0）ときだけ。`c_sovereign={state, compared, note}` を `gate_log` に足す。`_gate_c` の戻り値は変えない。
7. **入口**: `vera read/ask/serve/chat --layer <name|path>`（= 環境変数 `VERA_PLACEMENT_LAYER`）。`FusionConfig.layer` があれば `vera` 欄の最後に `placement_layer = {name, status, growth}`（`vera.layer`（融合の層 0/1）とは別の鍵。J12）。
8. **育ちの指標** `vera placement growth --layer`: 語数（direct・human・estimated・conflict）、行数、最後に育った時刻、`--ledger-file` があれば台帳の行数（種類ごと）・この層への `promoted_to_layer` 行数・`chain_ok`。

### 判断の記録（指示書 §1.9）
J1 層の鍵は層が指定されたときだけ付く。J2 K290 は `state` だけで読む。J3 層の ESTIMATED は答えの核を変えない。J4 `decided_by` は `by` そのまま（名詞の生成×文書の一致は基点と同じく読解器に読まれない: `PLACEMENT_DIRECT_VIA_GENERATED`）。J5 文書の腕は `role_distribution`（述語）と `hearst`（名詞）だけ・充填物の型は基底だけ。J6 名詞・述語の両方に出る語は問わない。J7 上位語の基底の型が申告と違えば生成の票にしない。J8 文書だけで決まった型が申告と違えば書かない。J9 grow の証言は `ADOPTED`・`candidate=語自身`。J10 promote の規則。J11 direct の型が 2 つ以上 → `LAYER_CONFLICT`。J12 serve の鍵は `placement_layer`。J13 ソブリンは `ACTIVE_CONSENTED` の発話だけを比べる。J14 層の名前の解き方。J15 基点の CONFIRMED の役割枠は読解器に `ROLE_FRAME_INVALID:ENTRY_KEYS` で拒まれる既存の不整合（直さない・報告）。J16 層の述語の `frame_status` は `NOT_CONFIRMED`。

### 採点の定義（R5。検査データより前に登録）
文書 QA の問い 30（答えが文書にある 20・無い 10）を `vera ask --mode round5 --document <doc> [--layer <spec>] -- <問い>` で別プロセスで流す。`verdict == "ANSWER"` かつ `sorted(values) == sorted(expect.values)` → **正答**。`verdict == "ANSWER"` でそれ以外（`expect == "ABSTAIN"` の問いへの ANSWER を含む）→ **誤答**。それ以外 → **棄権**。出た verdict の種類はすべて数える。ANSWER 以外で `values` が空でないものは「要確認」として列挙する。条件: 3 条件（層なし・fake の層・本物の層）とも誤答 0。正答の増分を報告し、増えなければ理由を型（`READER_NOT_REACHED`・`LAYER_WORD_NOT_IN_QUESTION`・`LAYER_NO_DIRECT`）で機械的に出す。

### 検査データの仕様（実装より前に凍結）
主題は **自転車の整備**。`tests/fusion/w10f05/domain_bicycle.txt`（1 行 1 文、60〜100 文。読解器が読める平叙文中心＋`AやBなどのY` の文を数文）。基底 r9 で UNPLACED／MULTIPLE の語が 30 以上含まれること（`artifacts/w10-f05/candidates_r9.txt`）。`domain_bicycle_qa.jsonl`（30 行、`{id, question, expect}`。20 問は文書の 1 文に答え、うち 10 問以上は候補の語が問いか答えの文に入る。10 問は答えが文書に無く `expect="ABSTAIN"`）。`fake_declarations_bicycle.json`（候補の語ごとの fake の申告。わざと誤った型を 5 語以上、`_intended_wrong` に列挙）。`synthetic/`（3 経路を必ず働かせる証拠の行の組と、`hearst` を 2 回以上起こす短い文書 1 本）。隠しバンクの文は使わない。

### 12.19.M W10-f05 の測定（出力は `artifacts/w10-f05/`。数値は各ファイルから）
- **検査データ**（凍結 `data_freeze.sha256` / `data_freeze_time.txt`。事前登録 `prereg_time.txt` の後）: 自転車の整備の文書 79 文、基底 r9 で UNPLACED／UNKNOWN／MULTIPLE の語 69（`candidates_r9.txt`。述語は 1 のみ。断片語を含む）、問い 30（答えあり 20・なし 10）、fake の申告に誤り 6 語（`_intended_wrong`）。
- **R1（K297）**: 入口 4,149 文は none・r8・r9 とも基点と byte 一致（`r1_entry.txt`）。`query` の全数（1,766,903 語）は r8・r9 とも一致（`r1_query.txt`）。serve 310 行一致（`r1_serve.txt`）。z1 の 12 case 一致（`r1_z1_cmp.txt`）。
- **R2（K290）**: 基底 direct 50 語は層で別の型を書いても 2 鍵を除き byte 一致・`BASE_DECIDED`、MULTIPLE の候補内 10 語は `LAYER_DIRECT_USED`、候補外 10 語は `LAYER_TYPE_NOT_AMONG_CANDIDATES`（`r2_k290.json`）。
- **R3（fake）**: 候補 69、申告 64（名詞 63・述語 1）、`layer_confirmed` 2・`layer_estimated` 61・書かない 6（`DECLARATION_NULL` 5・`HYPERNYM_TYPE_DISAGREES` 1）（`r3_grow_fake.json`）。誤りを入れた 6 語のうち direct になった語は 0、estimated 5、書かれず 1（`r3_wrong_check.txt`）。`growth` の `chain_ok: true`（`r3_growth_fake.txt`）。台帳の証言 69 行はすべて `context.doc_id` が文書 id・`provenance.version` が `fake-table:3aa3348232be`（表の sha256 の先頭 12）。K291 の 3 経路（生成×文書・生成のみ・人の確認）は合成の証拠の行 10 件と `tests/test_w10f05_grow.py` で働く。
- **R4（本物 qwen3.5:4b）**（第 2 ラウンドで取り直し。第 1 ラウンドの出力は `r1_r4_*` に残す）: 候補 69、申告 68（名詞 68・述語 0）、`layer_confirmed` 3・`layer_estimated` 65・書かない 1（`DECLARATION_INVALID:DUPLICATE`）（`r4_grow_real.json`）。遅延は後段 84,535 ms（8 呼び出し、1 語あたり約 1,225 ms）・Vera 2,552 ms。計測の前後の負荷は `r4_uptime_before.txt`（1 分平均 4.42）・`r4_uptime_after.txt`（5.36）。**この計測は自分の全体テストとは並走していないが、他チケットの pytest 等が同じ機械で動いていた**（`r4_ps_pytest_before.txt`）。台帳の証言 69 行はすべて `context.doc_id` が文書 id、`provenance.version` が `ollama-digest:2a654d98e6fb…`（ローカルの `/api/tags`）。目視（正解データではない）: direct 3 語の誤り 0、estimated の明らかな誤り 8・割れる 3（`r4_visual_review.md`。層の中身は r1 と語・型・origin が完全に一致）。
- **R5（文書 QA 30）**: 層なし・fake の層・本物の層とも 正答 8・誤答 0・棄権 22（`r5_qa.txt`）。**正答は増えなかった**。答えのある 20 問のうち層なしで正答 8、残り 12 の理由は本物の層で `READER_NOT_REACHED` 5（読解器の理由は `ambiguous case role: で` 4・`unsupported source quantifier/exception/time` 1）、`LAYER_NO_DIRECT` 6、`LAYER_WORD_NOT_IN_QUESTION` 1（`r5_why_not_gained_real.txt`、fake は `r5_why_not_gained_fake.txt`）。
- **R6**: `tests/test_w10f05_sovereign.py`（7 件）と `tests/test_w10f04_fill.py` が通る。
- **R9**: 全体テスト `pytest_full.txt`（第 3 ラウンドの取り直し）。失敗 116 件（passed 15596）、基線に無い失敗 1（`test_s6_…`。チケットが未コミットの間の環境由来と名指し。基点の木でも失敗。`pytest_new_failures_check.txt`）。W10-f05 のテストの失敗は 0。

### 12.19.J 実装役の判断（J17 以降）
J17 `vera placement` は既存の面の配置コマンド（先頭の引数が store）なので、先頭が `grow`／`growth` のときだけ新しい口にした（その名の store は使えない）。J18 `coarse_place.query(layer=False)` は環境変数も効かない「基底だけ」（層の育成と昇格が使う）。J19 `HYPERNYM_TYPE_DISAGREES`（上位語の基底の型が申告の型と違う）のときは文書の腕が一致していても書かない（狭める方向）。J20 `DISTRIBUTION_DISAGREES`（文書の分布が別の述語の型に投票）は estimated にも書かない。J21 文書の腕だけで決まり型が申告と同じ名詞は `layer_confirmed`（`decided_by` は `hearst@doc:…`）。この経路の名詞は読解器に読まれる（`gen_definition` が `by` に入らないため）。J22 `FusionConfig(layer=)` は環境変数を自分で設定する（食い違えば `LAYER_ENV_CONFLICT`）。J23 `--min-sources` は `rd_min_sources` と `role_frame_min_sources` だけを置き換え、ほかの閾値は変えない。 J24（第 2 ラウンド）台帳の証言の `provenance.version` は空文字にしない: ollama はローカルの `/api/tags` の digest、fake は表／台本の sha256 先頭 12、取れないときは `VERSION_UNKNOWN:<理由>`（注入された chat 関数・ローカル以外の host・openai は取りに行かない）。`context.doc_id` は候補の語の初出の文書の出所、`context.doc_ids` は出現した出所の一覧。J25 `FusionConfig` は `layer` が無くても `VERA_PLACEMENT_LAYER` があればその層を `vera.placement_layer` に報告する（無ければ鍵なし）。

### 12.20 W3-a7 r10 の事前登録（2026-10-05 07:19:46 +0900。検査データ・テスト・生成前）

**対象と変更境界**: r10 はデータで到達を伸ばす実験である。実装コードの変更は `tools/gen_coarse_evidence.py run` の `--effort {low,medium,high}` と、その値を既存の生成呼び出し・`batches.json` の `meta.effort`・`summary.json`・回収行の `provenance.effort` に渡す処理だけとする。省略時は `low`。モデル名、役割プロンプト v2、schema、語の順序、束の大きさ、再試行、確認・配置・読解の規則は変えない。努力値は生成の台帳の `argv` にある `model_reasoning_effort` でも照合できるようにする。既定 `low` の互換性は、実装前に固定した同一 needs・同一引数から作った決定的な `batches.json` と比較し、役割プロンプト v2 の出力も凍結済み v2 と `cmp` する。基準ファイルと sha256 は `artifacts/w3-a7/current-r1/` に保存する。

**K320（努力値だけを変える比較）**: プロンプトの出力・template hash・schema hash、閾値、needs の語集合・順序、束の条件を v2 と同じに保つ。比較するのは effort `low` と `medium` だけ。申告率は凍結した同一40語を分母とし、格助詞9種それぞれについて `frame` に非空の型付き申告がある語数 / 40 を計算する。棄権・欠落・不正行を分母から外さず、別々に報告する。v2 の基準値は、同じ40語について凍結済み `artifacts/w3-a6/r9/n4_claims_run2_prefreeze.jsonl` の `source_status == ACCEPTED` な枠から同じ式で得る。各助詞で r10 が v2 以上なら申告率条件を満たす。同点を解消する順序は設けない。

**試しの束と U2**: 入力は `artifacts/w3-a6/current-r2/trial_needs_role_v2.jsonl` と同じ語・同じ順序の40語とし、全件を1束・1呼び出しで実行する。試しの束の40語は凍結済みN4標本60語の一部である。申告率条件は上記 K320 の9助詞すべてで比較する。明らかな誤り条件は、同じ40語の出力枠を、N4の人手ラベル `artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl` の `(word, particle, role, types)` と完全一致で照合し、`明らかな誤り` の数が v2 の同一40語における数を超えないこととする。回答欠落・棄権は別記する。v3 の申告に完全一致する人手ラベルが無い場合は `UNCLASSIFIED` と記録し、ラベルの不在を正しさや誤りに読み替えず、U2 の誤り条件を `UNKNOWN` とする。U2 は9助詞の比較と誤り条件がともに判定可能で、かつ条件を満たす場合だけ `PASS`。1助詞でも v2 を下回る場合は `FAIL`。人手ラベルの不足で判定できない場合は `UNKNOWN` とし、本番生成の許可条件にしない。

**K321（規則コード不変）**: effort 引数の追加・伝播以外に生成器の処理・builder・型確認・問い合わせ・読解器を変更しない。差分レビューでは製品変更がこの引数の追加・伝播だけであることを確認し、`tools/build_coarse_placement.py` および配置・読解側の既存ファイルの実装前後 SHA-256 が一致する記録を残す。生成データ・LLMの返答は `generated` で、真偽の証拠として扱わない。

**K322（D9の保守的な変更）**: N4の目視標本で CONFIRMED 役割に占める明らかな誤りが10%を超えた場合だけ、既存D9の `role_frame_min_sources` を上げる方向で扱う。努力値を低く戻すことでは補正しない。既存の確認規則を狭める必要がある場合は別台帳・別測定として残す。明らかな誤りが10%以下ならD9を変更しない。人手ラベルは `testimony` として扱い、正解データとは呼ばない。

**後続の測定範囲**: この第1ラウンドでは `--effort` の受入確認、needs・生成スクリプト・試行スクリプトの凍結までを行い、試しの束・本番生成は実行しない。監査役の生成後に r10/run1 の verify、N2〜N5、全60語のN4誤り率、分布被覆表、r9/run2との差分、U5、基線失敗集合をそれぞれ別出力で判定する。未実行を達成扱いにしない。

### 12.20.1 W3-a7 r10 試行判定・再試行ゲートの追補（2026-10-05 08:13:45 +0900。状態・ゲートの規則を試行データ・テスト・コード変更前に登録。ラベル文字列の対応は2026-10-05 08:16:15 +0900に同じくデータ・テスト・コード変更前に追記）

**40語の状態記録**: 試しの束の各語を、raw 応答と同じ試行の collector 出力に照らして、`response`（1つの妥当な非null frame。空 frame も応答として数える）、`abstain_null`（妥当な null frame）、`missing`（raw items に語がない）、`invalid_or_duplicate`（重複応答、型不正、助詞重複、役割重複、または raw 応答と collector 行の不一致）のいずれか1状態にする。40語すべての語別状態、各状態数、invalid/duplicate の内訳を結果へ記録する。判定は collector の行数だけから missing と invalid を推定しない。ラベルの無い申告は引き続き `UNCLASSIFIED` である。

**U2 の保守的な扱い**: `missing` または `invalid_or_duplicate` が1語以上あれば U2 は `UNKNOWN`（監査役に戻す）。この場合、欠落・不正の語を無申告や棄権と数えて PASS / FAIL の比較へ混ぜない。全40語が `response` または `abstain_null` の場合だけ、固定分母40で既登録の助詞別率と明らかな誤り数の規則を適用する。ラベル不在も従来どおり `UNKNOWN`、率の低下または明らかな誤りの増加は `FAIL` とする。

**凍結ラベルの文字列**: N4ラベルの `visual_label` にある文字列 `誤り` は、§12.19の定義上の「明らかな誤り」として数える。`正しい` と `疑わしい` は明らかな誤りに数えない。未知の文字列や同じ申告キーに対する重複ラベルは `UNCLASSIFIED` とする。

**追記専用の試行記録と本番ゲート**: それぞれの試行は一意な ID で始め、開始と完了を同じ append-only JSONL 台帳へ記録する。記録には参照した `freeze.sha256` の SHA-256、その manifest が列挙する凍結ファイルの hash、完了状態、固有の判定結果ファイルとその hash を含める。試行ごとの出力ディレクトリと判定結果ファイルは別 ID にする。途中失敗は trap で完了 `FAIL` を記録し、trap が動かず未完了になった場合もゲートは拒否する。生成ゲートは、現在の凍結 manifest と一致する最新開始試行が完了済み `PASS` で、結果ファイルの内容と hash も一致するときだけ通す。後の未完了・失敗・`UNKNOWN` の試行が過去の PASS を再利用することはできない。既存の固定名 `trial_threshold.result` はゲート根拠にしない。

**LLM を呼ばない判定器確認**: 凍結済み試行 needs 40語、N4 claims、N4 visual labels から組み立てた機械判定用入力について、1語の raw 行を除いたケースは `missing=1`、棄権数とは別に記録され、U2 `UNKNOWN` でなければならない。状態分類の fixture は4状態を別々に確認する。ゲート検査は PASS の後に次の試行を開始した状態・FAIL 完了状態で拒否し、同じ凍結入力に結び付く直近の完了 PASS だけを許可する。これらは実際の生成性能を主張しない。生成と本番実行は監査役の許可を待ち、このラウンドでは実行しない。

### 12.20.2 W3-a7 判定テストの harness 修正（2026-10-05 08:29:52 +0900。期待 fixture は変更せず再凍結前）

初回の LLM-free テスト出力 `artifacts/w3-a7/current-r2/tests_trial_gate.txt` では3件中2件が失敗した。1件は、欠落数と棄権数がどちらも1になり得るのに数値が異なることを要求した harness の誤りだった。固定した期待 fixture の状態名・各状態数・U2 `UNKNOWN` は変更せず、別名の状態カウンターを個別に検査する。もう1件は4状態 fixture の元データに含まれる第5語目の null 棄権も残していた（位置は `trial_source_state.txt`）。fixture の期待を変えず、4状態ケースの構成時に明示した null 以外の基準 null 行を空 frame の有効応答へ置き換え、状態数が狙った4分類だけを表すようにする。変更後のテストコードと同じ期待 fixture・凍結入力を再ハッシュしてから再実行する。

### 12.20.3 W3-a7 第3ラウンド測定と U2 逸脱の記録（2026-10-05 10:10:38 +0900。r10/run1 の構築・N2〜N5・被覆測定データ作成前）

**U2 の裁定と逸脱**: 凍結された試行結果 `artifacts/w3-a7/current-r1/trial_results/4f6b0bb9-22e7-40a5-96dd-361a2f3d6297.json` は `status=FAIL`、`reason=particle_claim_rate_below_v2` であり、`を` は同一40語中 v2 が30語、試行出力が28語だった。事前登録の規則では本番生成のゲートを通らない。監査役がこの2語を訂正と裁定して本番生成へ進めたため、これは事前登録からの逸脱として記録する。監査役の裁定は U2 の PASS に読み替えず、第3ラウンドの U2 は `FAIL (override)` として報告する。試行の入力・結果を変更せず、本番 `gen_role_v3` の再生成・追記・修復は行わない。

**使用入力と凍結**: r10/run1 は凍結済み r9 の名詞型生成入力（`gen_ntype`）と監査役が完了した `build/coarse-W3a/full/r10/gen_role_v3/` の生成データを使う。構築前に `gen_role_v3/role_frames.jsonl`・`summary.json`・`batches.json`・`schema.json`、r9/run2 の manifest と配置、r9 の設定、N2 の期待11行、N4の標本60語・既存ラベル、N5のseed一覧、関連する builder・配置コードの SHA-256 を `artifacts/w3-a7/current-r3/input_freeze.sha256` に記録する。gen_role_v3 の台帳は変更しない。検査結果は同じディレクトリに書き、生成物を根拠や正解データとして扱わない。

**N2**: `tests/coarse_place/data/w3a6_expect.json` の役割期待11行をそのまま使い、各述語・助詞・期待役割について、r9/run2 と r10/run1 の申告有無、`CONFIRMED` / `unconfirmed`、役割の `backed_by` と各出所の `(助詞, 型)` の票を並べる。出所を横断して票を合算しない。期待11行・述語数・根拠の腕を全行保存する。

**N3・N5 と全差分**: N3 は凍結した相対位置の期待語を r10 で再照会し、PLACE 単独 direct の有無を全件記録する。N5 は凍結した281 seed語の `(namespace, state, origin, top)` を r9/run2 と r10/run1 で比較し、異なる行をすべて保存する。別に r9/run2 から r10/run1 への `direct` 配置（`namespace, word, state, origin, top`）の変化を全件列挙し、`CONFIRMED` 役割は `(word, particle, role, types, backed_by)` の追加・除去・変更を全件列挙する。変更が0件でも0件と記録する。

**N4 と U4（分布の被覆）**: 凍結した同じ60語について r10 の申告を抽出し、Codex 実装役が再目視したラベルを別ファイルに記録する。ラベルの状態は `正しい` / `疑わしい` / `誤り` / `UNCLASSIFIED` とし、判定は `testimony` であって正解データではない。N4 の明らかな誤り率は r10 で `CONFIRMED` となった役割を分母にし、`誤り` 件数と未分類件数を別々に数える。上限（誤り＋未分類）も10%以下の場合だけ N4 を PASS とする。U4 は N2 の11行と N4 の60語について、助詞ごとに `role_distribution` の各出所が持つ有意な型・申告役割への票・型の分割を出所ごとに保存する。原因は同時に複数を記録できる。`CLAIM_ABSENT`（助詞または期待役割の申告なし）、`DISTRIBUTION_NO_ARM`（その助詞に有意な型を持つ腕なし）、`NO_SHARED_TYPE`（有意型はあるが申告型と交わらない）、`TYPE_SPLIT`（同じ助詞・型が同一出所内で複数役割へ割れ、票にならない）、`SUPPORTED`、`UNCLASSIFIED`、`SOURCE_ABSENT` を別の型として扱い、型不一致や出所欠落を偽・不支持と読み替えない。

**率と manifest**: v2 は r9/manifest の `gen_role_v2`、v3 は r10 の `gen_role_v3/summary.json` と構築入力から数える。全8,311要求語を分母とする率と、各世代の有効な異なる非null role-frame 語を分母とする率の両方を格助詞ごとに出し、分母・分子・effort・calls・成功／失敗バッチ・申告出所・入力 hash を残す。非null枠内での分子は、その助詞に少なくとも1つの型付き役割を申告した異なる語数とする。r9の manifest と同じ9助詞・同じ式を使う。率の比較は記述統計で、生成申告を事実の証拠にしない。

**実行境界**: 実装側は試行も本番の生成器も再実行しない。r10/run1 の構築と verify、N2〜N5、被覆・差分・manifest の生成に限る。U5 の隠し評価は監査役の範囲であり実行しない。受入基準 U6 は `tests/` 全体を最後に一度実行し、基線失敗集合と照合する。

### 12.20.4 W3-a7 第4ラウンド N4 盲検再測定の事前登録（2026-10-05 12:04:07 +0900。旧ラベルを読み替えず、新ラベル・結合・集計前）

第3ラウンドの `label_n4_v3.py` は固定語を誤り・疑わしいとし、残りを既定で正しいとしたうえ、確認状態を含む claims を参照していた。前回レビューでこのN4測定は盲検でないと判定されたため、旧ラベル・旧PASS・旧率は有効な判定に使わず、全て保持して履歴として扱う。本節の手順で新しい測定を別ファイルに作る。

**標本とラベル前凍結**: 標本は同じ凍結60語、対象は r10/run1 の v3 申告全件。ラベル前入力は `(word, particle, role, types)` の申告内容と60語の標本一覧に限り、`confirmed`、`confirmed_types`、`backed_by`、`unconfirmed_why`、旧目視ラベル、出所ごとの確認結果を含めない。1行は1つの申告役割。語の申告が無い場合も標本一覧には残す。申告行と標本一覧、抽出手順の hash を目視前に固定する。

**目視基準**: §12.19 の既登録基準を適用する。最も普通の語義で、その助詞の項が役割に当たる普通の文が作れ、規約§2・§4.1と型にも合う場合を `正しい`、助詞がその役割を取らない・規約が別役割を指す・型が役割に来ない場合を `誤り`、多義・言い切れない場合を `疑わしい`、標本語だけでは判断できない場合を `UNCLASSIFIED` とする。ラベルは `testimony` であり正解データではない。目視中は確認状態、確認の根拠、分布、旧ラベルを参照しない。全申告に個別ラベルを明示し、欠落・重複・未登録キーを既定の正しさにせず `UNCLASSIFIED` として数える。ラベル全件と hash を確認結果との結合前に固定する。

**後結合と率**: ラベルファイルの凍結が済んでから、同一 `(word, particle, role, types)` の r10/run1 `CONFIRMED` 役割だけを結合する。分母は結合できた `CONFIRMED` 申告役割数、明らかな誤りは `誤り` 数、未分類は別数で報告する。`誤り + UNCLASSIFIED` の保守的上限も分母で割り、これが10%以下で、結合・ラベルの欠落や重複が無い場合だけN4をPASSとする。分母0、結合不能、または上限が10%を超える場合はN4をPASSにしない。閾値超過時のD9は既登録K322どおり、`role_frame_min_sources` を上げる方向でのみ扱う。

**U4分類**: N2 11行・N4 60語×9助詞の出所別表を作り、登録済み原因だけを主表に使う: `CLAIM_ABSENT`、`DISTRIBUTION_NO_ARM`、`NO_SHARED_TYPE`、`TYPE_SPLIT`、`SUPPORTED`、`UNCLASSIFIED`、`SOURCE_ABSENT`。複数原因は同時に記録可能で、出所を横断して票を足さない。第3ラウンドの補助分類 `PARTLY_BACKED` は登録済み原因へ混ぜず、旧表の履歴に残す。

**第4ラウンドの境界**: 監査役が生成を終えた `gen_role_v3`、生成台帳、既存r10/run1は読み取り専用とし、生成・台帳更新・配置再構築は行わない。試行FAILはFAILのまま維持し、監査役の裁定をPASSに読み替えない。N4盲検再測定とU4主表は `artifacts/w3-a7/current-r4/` に別出力し、旧出力は変更しない。
