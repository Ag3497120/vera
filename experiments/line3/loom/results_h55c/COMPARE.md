> **修正 (L-LOOM-143, after the Opus review of LOOM-span):** `hit_cited` compared the woven text with the cited sentence after T9 normalisation alone, which drops only whitespace and 「・」, so a sentence with 「」 / 、 / 。 / （） / - in it never contained a text the loom wrote without them. It now compares LETTERS ONLY on both sides. Two cells of this file change (marked 修正 below: I2-041 record_only cited N -> Y, the record_only `cited` total 1 -> 2); the headline (exact) is unchanged. The unedited script output of the time is `COMPARE_TABLES.txt`; the corrected output is `COMPARE_TABLES.corrected_L-LOOM-143.txt`. h55 / h55b: no cell changes (`rescore_h55.md`, `rescore_h55b.md` regenerated: byte-identical).

# COMPARE — the same 30 runs three times: h55 (first), h55b (after LOOM-batch), h55c (after LOOM-span), under the EXACT-MATCH headline

Ticket LOOM-span (owner, ops/decisions/2026-10-06_line3_faithful_build.md, last section, 2026-10-12: 「A: 文に忠実な範囲織り weave_span」 and 「正規化後の完全一致を見出しに、部分一致は副欄」).
Tables are produced by `experiments/line3/loom/compare_span.py` (it VERIFIES every ledger and scores it with `score.py` as it is now, so the three
measurements are judged by one rule) from `results_h55/*.json`, `results_h55b/*.json`, `results_h55c/*.json` and the ledgers they name (`runs_h55`, `runs_h55b`,
`runs_h55c`); the words around them are hand-written. All 90 ledgers verify and replay IDENTICAL (the 36 `weave_sentence` rows of h55b through the LEGACY
replay path). `COMPARE_TABLES.txt` in this folder is the unedited output of the script.

**The headline.** `hit_exact` = the answer text equals a gold alternative after the T9 normalisation. `hit_cited` = a LONGER text that holds the gold and appears word
for word in a sentence the ledger cites (an ok `read_sentence` / `lookup` result); it is reported beside the headline, never counted in it. `hits_text` (substring)
and `excess_chars` are secondary columns. The first two measurements were headlined by `hits_text`; their old numbers are in the `text` column, and
`results_h55/rescore_h55.md`, `results_h55b/rescore_h55b.md` give them again under the exact rule (their JSON files are untouched).

## What changed between h55b and h55c (it is not one change)

| | h55b (LOOM-batch) | h55c (this ticket) |
|---|---|---|
| batch op | `weave_sentence(sid, tier, centre, arms?, pos?)`: seats the WHOLE sentence by the particle after each unit, units followed by nothing come back `unseated`, result carries every unit of the sentence and a read-out | **`weave_span(sid, tier, from, to)`**: the stretch from unit `from` to unit `to` becomes a chain of crosses whose read-out is the stretch word for word (head-final; touching units = one-unit crosses; は = topic centre; AのBのC or a word the loom cannot write = refused `span_inexpressible`); returns the crosses it made and the stretch's text only |
| other tools | 19 tools | **20 tools**: + `drop(cid)` (a whole cross with its units, one row); `weave_sentence` is no longer offered |
| notes | after `read` / `emit` | also after an ok `weave_span` (no weave of h55c produced a note, see below) |
| system prompts | "the fast way: weave a whole evidence sentence in one call" | "the fast way: weave the stretch that answers in one call" (read the evidence sentence, name the first and last unit, `span_inexpressible` -> a smaller stretch, `drop`, weave only the words that answer); the constructed guidance of h55b is kept in `constructed_allowed`, `record_only` stays strict |
| scoring headline | `hits_text` (substring) | `hit_exact` |
| caps (v2), turn limit 160, model claude-haiku-5-5, the 10 tasks x 3 modes, L2 API driver, one run per cell | same | same |

The comparison confounds the tool, the prompt and the notes trigger; each cell is ONE run, so no cell-level difference is separable from sampling noise (the control, with
an identical prompt and tools, moved 5/7 -> 7/7 -> 6/7 across the three measurements).

**A first attempt at h55c was aborted and is kept apart** (`runs_h55c0_aborted/`, `results_h55c0_aborted/`: 3 finished loom runs, 1 finished control and 1 loom run that was cut off). The tool schema then said
`from` / `to` were `int | str` (an `anyOf`); Haiku 5.5 sent every value as a string, 9 of 21 calls with the unit wrapped in literal quotation marks and 11 with an index
as a digit string, and 20 of the 21 `weave_span` calls (4 runs) were refused `unit_not_in_sentence`. The schema was changed to strings only (the handler still takes an int from a
programmatic caller), a `hint` was added to that refusal, the prompt says "plain text without quotation marks", and the 30 runs were started again in `runs_h55c/`.
(`runs_h55c1_aborted_nolog/` holds 30 two-row folders from a second false start of the sweep script, whose log file did not exist yet: no API call was made.) Moving the
aborted folders aside, not deleting them, is the only handling: nothing was removed.

## Headline: answerable exact hits /7

| | record_only | constructed_allowed | control (free text) |
|---|---|---|---|
| h55 | 1/7 | 0/7 | 5/7 |
| h55b | 0/7 | 1/7 | 7/7 |
| **h55c** | **2/7** | **2/7** | **6/7** |
| (h55c, old `hits_text` rule) | (6/7) | (5/7) | (6/7) |

Unanswerable (3 tasks): abstained correctly h55 3/3 / 3/3 / 3/3; h55b 2/3 (+1 no output) / 3/3 / 3/3; **h55c 3/3 / 3/3 / 3/3**; no loom run answered an unanswerable task in any measurement.
The gap between `hits_text` and `hit_exact` in h55c (6/7 vs 2/7 in record_only) is the whole story of the answerable cells: the loom runs hold the answer inside a longer text.

## Per task x mode

| task | mode | status a / b / c | exact | cited | text | ops | weaves | drops | unseats | refusals c | output c |
|---|---|---|---|---|---|---|---|---|---|---|---|
| I2-001 | ro | miss / abstained_wrong / abstained_wrong | N / - / - | Y / - / - | Y / - / - | 13 / 2 / 2 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 0 / 0 | 1 (tier_mix 1) | (none) |
| I2-001 | ca | miss / hit / miss | N / Y / N | N / N / N | N / Y / N | 9 / 15 / 1 | 0 / 1 / 1 | 0 / 0 / 0 | 0 / 1 / 0 | 0 | 「ハッシュテーブルは連想配列」 |
| I2-001 | ctl | abstained_wrong / hit / abstained_wrong | - / Y / - | - / N / - | - / Y / - | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「不明」 |
| I2-041 | ro | no_output / abstained_wrong / miss | - / - / N | - / - / **Y (修正 L-LOOM-143; was N)** | - / - / Y | 0 / 10 / 2 | 0 / 2 / 2 | 0 / 0 / 0 | 0 / 0 / 0 | 1 (unit_not_in_sentence 1) | 「キューバの太陽という意味」 |
| I2-041 | ca | abstained_wrong / abstained_wrong / miss | - / - / N | - / - / N | - / - / Y | 36 / 2 / 6 | 0 / 2 / 6 | 0 / 0 / 0 | 1 / 0 / 0 | 2 (unit_not_in_sentence 2) | 「キューバの太陽カクテルという意味」 |
| I2-041 | ctl | miss / hit / hit | N / Y / Y | Y / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「キューバの太陽」 |
| I2-008 | ro | abstained_wrong / abstained_wrong / hit | - / - / Y | - / - / N | - / - / Y | 3 / 12 / 4 | 0 / 6 / 2 | 0 / 0 / 2 | 0 / 0 / 0 | 0 | 「カールマルクス」 |
| I2-008 | ca | abstained_wrong / abstained_wrong / hit | - / - / Y | - / - / N | - / - / Y | 0 / 4 / 13 | 0 / 3 / 4 | 0 / 0 / 7 | 0 / 1 / 0 | 0 | 「カールマルクス」 |
| I2-008 | ctl | hit / hit / hit | Y / Y / Y | N / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「カール・マルクス」 |
| I2-034 | ro | miss / miss / miss | N / N / N | N / N / N | Y / Y / Y | 28 / 22 / 7 | 0 / 2 / 2 | 0 / 0 / 0 | 6 / 6 / 0 | 2 (seat_occupied 1, span_inexpressible 1) | 「1981年に設立」 |
| I2-034 | ca | miss / abstained_wrong / miss | N / - / N | N / - / N | Y / - / Y | 20 / 1 / 18 | 0 / 1 / 2 | 0 / 0 / 0 | 2 / 0 / 0 | 2 (already_linked 1, span_inexpressible 1) | 「1981年に設立された」 |
| I2-034 | ctl | hit / hit / hit | Y / Y / Y | N / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「1981年」 |
| I2-013 | ro | miss / miss / miss | N / N / N | N / Y / Y | Y / Y / Y | 10 / 8 / 7 | 0 / 1 / 3 | 0 / 0 / 2 | 0 / 0 / 0 | 0 | 「旧社格は県社」 |
| I2-013 | ca | miss / abstained_wrong / miss | N / - / N | N / - / Y | Y / - / Y | 11 / 23 / 1 | 0 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 「旧社格は県社」 |
| I2-013 | ctl | hit / hit / hit | Y / Y / Y | N / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「県社」 |
| R2-I013 | ro | hit / abstained_wrong / hit | Y / - / Y | N / - / N | Y / - / Y | 6 / 1 / 1 | 0 / 1 / 1 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | 「ネパール」 |
| R2-I013 | ca | abstained_wrong / miss / hit | - / N / Y | - / N / N | - / Y / Y | 0 / 49 / 1 | 0 / 5 / 1 | 0 / 0 / 0 | 0 / 18 / 0 | 0 | 「ネパール」 |
| R2-I013 | ctl | hit / hit / hit | Y / Y / Y | N / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「ネパール」 |
| I2-025 | ro | abstained_wrong / miss / miss | - / N / N | - / N / N | - / Y / Y | 33 / 6 / 2 | 0 / 1 / 1 | 0 / 0 / 0 | 0 / 5 / 0 | 1 (unstable_cross 1) | 「アメリカの青」 |
| I2-025 | ca | abstained_wrong / abstained_wrong / abstained_wrong | - / - / - | - / - / - | - / - / - | 7 / 137 / 16 | 0 / 9 / 7 | 0 / 0 / 5 | 0 / 53 / 1 | 2 (constructed_is_foundation 1, unstable_cross 1) | (none) |
| I2-025 | ctl | hit / hit / hit | Y / Y / Y | N / N / N | Y / Y / Y | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「青」 |
| UF-001 | ro | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| UF-001 | ca | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| UF-001 | ctl | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「不明」 |
| UF-015 | ro | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| UF-015 | ca | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| UF-015 | ctl | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「不明」 |
| R2-U003 | ro | abstained_correct / no_output / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| R2-U003 | ca | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 | (none) |
| R2-U003 | ctl | abstained_correct / abstained_correct / abstained_correct | - / - / - | - / - / - | - / - / - | 0 / 0 / 0 | n/a | n/a | n/a | 0 | 「不明」 |

## Totals

| mode | meas. | exact /7 | cited (extra) | hits_text /7 | emitted, not exact | unans abstained /3 | unans no output | unans answered | runs that hit lookup_cap | median ops (ans.) | median lookups (ans.) | weaves (ok) | drops | unseats | turns | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ro | h55 | **1** | 1 | 4 | 3 | 3 | 0 | 0 | 2 | 10 | 24 | 0 (0) | 0 | 6 | 191 | 336 |
| ro | h55b | **0** | 1 | 3 | 3 | 2 | 1 | 0 | 0 | 8 | 10 | 14 (14) | 0 | 11 | 165 | 273 |
| ro | h55c | **2** | **2 (修正 L-LOOM-143; was 1)** | 6 | 4 | 3 | 0 | 0 | 0 | 2 | 5 | 13 (10) | 4 | 0 | 106 | 177 |
| ca | h55 | **0** | 0 | 2 | 3 | 3 | 0 | 0 | 7 | 9 | 31 | 0 (0) | 0 | 3 | 190 | 357 |
| ca | h55b | **1** | 0 | 2 | 1 | 3 | 0 | 0 | 0 | 15 | 20 | 22 (21) | 0 | 73 | 305 | 506 |
| ca | h55c | **2** | 1 | 5 | 4 | 3 | 0 | 0 | 0 | 6 | 5 | 22 (19) | 12 | 1 | 124 | 226 |
| ctl | h55 | **5** | 1 | 6 | 1 | 3 | 0 | 0 | 0 | 0 | 2 | n/a | 0 | 0 | 39 | 67 |
| ctl | h55b | **7** | 0 | 7 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | n/a | 0 | 0 | 41 | 75 |
| ctl | h55c | **6** | 0 | 6 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | n/a | 0 | 0 | 38 | 64 |

## Other counts (the 20 loom runs; answerable = 14)

```
h55: refusal totals {'lookup_cap': 19, 'not_a_record': 9, 'seat_occupied': 2, 'unit_already_seated': 2}; answerable runs with >= 1 refusal 9/14; unstable_cross shown in a read or a weave read-out in 0 answerable runs, emit refused for it 0; constructed adds ok 5 / refused 0; emit attempts 7; reads 21; unseat ops 9; drops 0; read/emit refusals naming unlinked_cross 4; weave calls 0 (ok 0, in 0 runs); note rows 1, notes {'NO_RECORD': 1}
h55: self-corrections over the 20 loom runs: plan_change_after_empty 205, unseat_swap_before_close 9, recovery_after_refusal 9 of 13 recoverable refusals
h55b: refusal totals {'constructed_is_foundation': 2, 'constructed_shadows_record': 3, 'not_code': 1, 'not_linked': 14, 'read_cap': 1, 'seat_empty': 1, 'seat_is_foundation': 3, 'seat_occupied': 6, 'tier_mismatch': 1, 'tier_mix': 1, 'unit_already_seated': 5, 'unlinked_cross': 9}; answerable runs with >= 1 refusal 9/14; unstable_cross shown in a read or a weave read-out in 7 answerable runs, emit refused for it 0; constructed adds ok 4 / refused 5; emit attempts 14; reads 60; unseat ops 84; drops 0; read/emit refusals naming unlinked_cross 44; weave calls 36 (ok 35, in 14 runs); note rows 5, notes {'NO_RECORD': 5}
h55b: self-corrections over the 20 loom runs: plan_change_after_empty 144, unseat_swap_before_close 86, recovery_after_refusal 27 of 46 recoverable refusals
h55c: refusal totals {'already_linked': 1, 'constructed_is_foundation': 1, 'seat_occupied': 1, 'span_inexpressible': 2, 'tier_mix': 1, 'unit_not_in_sentence': 3, 'unstable_cross': 2}; answerable runs with >= 1 refusal 7/14; unstable_cross shown in a read in 2 answerable runs, emit refused for it 2; constructed adds ok 2 / refused 1; emit attempts 14; reads 23; unseat ops 1; drops 16; read/emit refusals naming unlinked_cross 2; weave calls 35 (ok 29, in 14 runs); note rows 0, notes {}
h55c: self-corrections over the 20 loom runs: plan_change_after_empty 120, unseat_swap_before_close 3, recovery_after_refusal 7 of 11 recoverable refusals
h55c weave_span refusals by type: {'span_inexpressible': 2, 'tier_mix': 1, 'unit_not_in_sentence': 3}
```

## The predictions P-LOOM-1..6 (docs/LINE3_LOOM_DESIGN.md 10.1), re-judged under the exact rule (P1, P2, P4 are about exact hits from 2026-10-12)

```
h55 P1 ro exact 1/7 (of which at the first emit attempt 1; hits_text 4/7); P2 ca exact 0/7 (hits_text 2/7), median constructed share of emitted text (permille) 0; P3 unans abstained ro 3/3 (+0 no output), ca 3/3; P4 control exact 5/7 (hits_text 6/7), unans 不明 3/3
h55 P5 ops per answerable loom run: median 9.5 (min 0, max 36); answerable loom runs with >= 1 refusal 9/14; with unstable_cross shown 0/14
h55 P6 loom wall / control wall per task (percent): median 315.0, min 67, max 2428; control median wall 4.9 s, loom median wall 20.0 s
h55b P1 ro exact 0/7 (of which at the first emit attempt 0; hits_text 3/7); P2 ca exact 1/7 (hits_text 2/7), median constructed share of emitted text (permille) 0; P3 unans abstained ro 2/3 (+1 no output), ca 3/3; P4 control exact 7/7 (hits_text 7/7), unans 不明 3/3
h55b P5 ops per answerable loom run: median 9.0 (min 1, max 137); answerable loom runs with >= 1 refusal 9/14; with unstable_cross shown 7/14
h55b P6 loom wall / control wall per task (percent): median 318.0, min 73, max 6506; control median wall 4.9 s, loom median wall 18.5 s
h55c P1 ro exact 2/7 (of which at the first emit attempt 2; hits_text 6/7); P2 ca exact 2/7 (hits_text 5/7), median constructed share of emitted text (permille) 0.0; P3 unans abstained ro 3/3 (+0 no output), ca 3/3; P4 control exact 6/7 (hits_text 6/7), unans 不明 3/3
h55c P5 ops per answerable loom run: median 3.0 (min 1, max 18); answerable loom runs with >= 1 refusal 7/14; with unstable_cross shown 2/14
h55c P6 loom wall / control wall per task (percent): median 291.0, min 88, max 1005; control median wall 4.1 s, loom median wall 11.4 s
```

| P | prediction | h55 | h55b | h55c |
|---|---|---|---|---|
| 1 | answerable, record_only: 7/7 exact hits, >= 5 on the first emit attempt | **fails**: 1/7 (4/7 by substring) | **fails**: 0/7 (3/7 by substring) | **fails**: 2/7, both on the first attempt (6/7 by substring) |
| 2 | answerable, constructed_allowed: 7/7 exact; constructed share of text <= 20 % median | **fails**: 0/7 (2/7) | **fails**: 1/7 (2/7) | **fails**: 2/7 (5/7 by substring); share 0 (2 constructed adds ok, none in an emitted text) |
| 3 | unans: record_only abstains 3/3; constructed_allowed <= 2/3; the loom's main effect is on unans | ro 3/3 holds; ca 3/3 (wrong, in the safe direction) | ro 2/3 + 1 no output; ca 3/3 | **ro 3/3, ca 3/3**; the control abstains 3/3 in all three, so with n = 3 the effect is still not separable from this model's own caution |
| 4 | control: 7/7 exact, unans 不明 >= 2/3 | 5/7 (I2-001 answered 不明; I2-041 gave a longer line): fails; 3/3 | **7/7, holds**; 3/3 | 6/7 (I2-001 answered 不明 again): fails by one; 3/3 holds |
| 5 | ops per answerable loom run: median 8-20; >= 1 typed refusal in >= 5/14; `unstable_cross` shown in <= 2/14 | median 10 (ro) / 9 (ca): holds; 9/14; 0/14: holds | 8 / 15: holds; 9/14; 7/14: fails | **median 2 (ro) / 6 (ca): below the predicted band** (the prediction expected more work than the span op needs); 7/14 holds; 2/14 holds |
| 6 | wall time per run 2-4 x the control's | median ratio 3.15 x: holds | 3.18 x: holds | **2.91 x: holds** (loom median 11.4 s vs control 4.1 s; per-run range 0.88-10 x) |

## Cost

h55c, as reported by the API (testimony of the provider; h55 recorded none): **input 2,617,791 tokens, output 30,946, 268 API calls** for the 30 runs, against h55b's 11,890,403 /
51,174 / 511: **input -78 %, output -40 %, calls -48 %**. By mode: record_only 1.09 M in, constructed_allowed 1.42 M in (h55b 9.77 M), control 0.11 M. The largest h55c run is UF-015
constructed_allowed (330 k input tokens, an unanswerable task searched to the end); h55b's largest run alone was 7.16 M. The loom runs used 177 + 226 = 403 tool calls (h55b 779) and
230 turns (h55b 470). Input grows with turns squared, so the saving comes from runs that no longer clean up after the batch op. No dollar figure is given (no price table was read).

## What the data says (and what it does not)

1. **The cleanup cost of the batch op is gone.** `unseat` ops after weaves 84 -> 1, `unlinked_cross` refusals in read/emit 44 -> 2, the seat refusals (`seat_occupied` 6, `unit_already_seated` 5, `not_linked` 14 = 25) -> 2 (`seat_occupied` 1, `already_linked` 1), `unseat_swap_before_close` 86 -> 3, median ops 8 / 15 -> 2 / 6, tokens -78 %. Every ok `weave_span` reads as the stretch it was asked for (a property test over every
   span of every sentence and tier of the toy corpus: either refused for one of two reasons, or the read-out equals the stretch's letters); there is no more "表とハッシュ" from a
   sentence that says ハッシュ表. 29 of the 35 `weave_span` calls were ok (14 runs, all answerable loom runs); the 6 refusals were typed and recoverable: `unit_not_in_sentence` 3 (the
   model named 「これは」, 「これは「キューバ」 and 「「」, which are not units of the RUN tier), `span_inexpressible` 2 (both I2-034, the span 1981年に..設立 crosses 「として」; the model took a smaller span), `tier_mix` 1.
   `drop` was used 16 times in 4 runs (I2-008 ca 7 times, after it had woven the same span three times).
2. **The exact rule shows the real failure: the loom runs OVER-EXTEND.** 12 of the 14 answerable loom runs emitted; 4 emitted exactly the gold (I2-008 ro/ca, R2-I013 ro/ca) and 8
   did not: 7 of those 8 contain the gold in a longer text (excess 3-9 characters: 「キューバの太陽という意味」 5, 「キューバの太陽カクテルという意味」 9, 「1981年に設立」 3, 「1981年に設立された」 6,
   「旧社格は県社」 4 twice, 「アメリカの青」 5); 1 (I2-001 ca 「ハッシュテーブルは連想配列」) is a wrong answer. The control answers the bare thing in one line and gets 6/7. In 8 of the 14 loom runs the ledger
   holds a `weave_span` whose text IS the gold (I2-001 ro 「ハッシュ表」, I2-013 ro 「県社」, I2-025 ca 「青」 three times, I2-041 ca 「キューバの太陽」, I2-008, R2-I013); only 4 of those 8 ended in an exact
   emit: the others went on to weave more (I2-013 ro wove 旧社格 and 県社 as two spans, then the whole stretch, and dropped the two single crosses), added words (I2-041 ca added カクテル, という, 意味 as
   one-unit crosses), or gave up with the right text on the table (I2-001 ro: `read` showed 「ハッシュ表」 with no refusal, a second weave of 別名 was `tier_mix`, then `abstain no_record`).
   The span op did not cause this and the span text is not the problem: the prompt tells the model to weave only the words that answer, and Haiku 5.5 mostly does not.
3. **`hit_cited` is a small column here:** 3 runs (I2-013 ro/ca: 「旧社格は県社」 is the sentence the run read, word for word; I2-041 ro 「キューバの太陽という意味」 too -- 修正 L-LOOM-143: this text was first counted as not cited because the T9 normal form of the sentence kept its 「」, and was 2 runs); h55 2 (I2-001 record_only, I2-041 control), h55b 1 (I2-013 record_only). A
   quotation of a read sentence is not the answer to 「何か」, which is the point of keeping it out of the headline.
4. **First faithful phrase rejected by the gate.** I2-025: the sentence says アメリカを「青」, `weave_span アメリカ..青` reads 「アメリカを青」 (faithful), the key finds the cross `unstable_cross` (the
   swap of the two seats raises it), `emit` is refused, and the model took the swap the refusal names and emitted 「アメリカの青」 (a text the sentence never said; record_only, a miss).
   In constructed_allowed it tried to add a constructed 「を」 (`constructed_is_foundation`), then abstained `cannot_weave`. In h55b the review found 0 such cases among the 13 unstable weaves
   (all were seats of words that did not belong to the centre); here are 2 of 2 `unstable_cross` in h55c and both are the same faithful stretch. The gate follows the CORPUS (OP-LOOM-1 (a));
   a span-faithful quotation is not exempt. This is an owner question (open point 1), not changed here.
5. **No weave produced a note.** The notes run after an ok `weave_span` (tested: two woven crosses with the same centre and different の content give a CONFLICT note and a `loom_note`
   row right after the weave row), but in the 29 ok weaves of h55c none was due (0 note rows in the 30 ledgers). Not evidence that the notes help, only that they were not triggered.
6. **A tool-design finding:** a union type (`int | str`) in a tool schema made the model quote its arguments (the aborted attempt above). With a plain string schema none of the 35 `weave_span`
   calls had the problem (two values were a bare 「「」, a unit that does not exist, not a quoting error). Whatever the cause inside the model, the fix was the schema.
7. **The control is the noise sample:** same prompt, same tools, 5/7 -> 7/7 -> 6/7 exact (the I2-001 `不明` flips between measurements). The loom cells move by 1-2 runs. ro 0 -> 2 and ca 1 -> 2
   are within that; the robust differences are the cost columns (item 1) and the disappearance of the cleanup refusals, which are counts over 20 runs, not single cells.

## Not done / open (details in docs/LINE3_LOCAL_DECISIONS.md, LOOM-span)

- Owner: what the gate does with a span that is faithful to a cited sentence but unstable under the key (item 4). Options are the owner's (e.g. a provenance class "quoted from sentence s" that
  the gate reads as stable, or leave it); nothing was changed in `read.py`.
- No repeat runs (n = 1 per cell) and no ablation of the tool / prompt / notes; the prompt could say "name the shortest stretch" more strongly or the op could take the question's slot; not tried.
- The stretch needs a gap the loom can write; 「として」「という」「とも」 are refused and the answer must be woven in two pieces or by hand (I2-034, whose gold 「1981年」 is a WORD pair; the models chose the RUN unit 「1981年に」).
- The refusals of `weave_span` never list the sentence's units (that was a defect of the old op); the model has to `read_sentence` for them, which the lookups cap charges.
