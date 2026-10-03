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

### 11.7 既知の穴

- 生成した定義文の精度は、凍結した検査データでは「推定（生成）」の語の正答・誤決定の件数（第 11.5 節の表）でしか分からない。検査データに無い語の精度は測っていない。
- 一覧は頻度だけで選ぶため、機能語に近い名詞（こと・ため など）や述語も含む。モデルが `null` で答えた語は棄権として数える。
- F1 の止め方は、連鎖から正しい型を渡せていた語（定義が割れた語を上位語に持つ記事など）も未配置にする。その代わりに誤った型の広がりは止まる（第 11.1 節の表）。
- `definition_recovered` を決め手にする判断は dev の小さい標本（決め手がこの腕だけの語）に基づく。
- 標本の外の設定（`donor_contra_min` など）は dev の 1 つの配置で選んだ。
- 欧文の単位の規則（第 11.8 節）は、dev ではなく抽出段の表の中身（私とレビューが挙げた実在の単位と非単位の小さい集合）で選んだ。`mm`（出所 `codex:code_qa` では日付の書式としても出る）と `em` は表に残らない。事前に書いた候補の格子に後から `K=6` を足した（DECISIONS §6-2）。
- 時の単位を頭に持つ 2 形態素の単位（`年後`・`日前`・`世紀末` など）が表に入り、`3年後` が数量になる（W3-a から続く既存の問題で、今回は直していない）。
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
