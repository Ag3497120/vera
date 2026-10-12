# COMPARE — the first Haiku 5.5 measurement (h55) against the same 30 runs after LOOM-batch (h55b)

Ticket LOOM-batch (owner, ops/decisions/2026-10-06_line3_faithful_build.md, last section: 「両方入れて再計測して」). Tables are produced by
`experiments/line3/loom/compare_batch.py` from `results_h55/*.json`, `results_h55b/*.json` and the ledgers they name (`runs_h55`, `runs_h55b`); the
words around them are hand-written. Every one of the 60 ledgers verifies and replays IDENTICAL (`verify_status OK` in every result file; the 30 h55
ledgers replay with their own recorded caps, see test_loom_batch.py).

## What changed between the two measurements (it is not one change)

| | h55 (first measurement, `edf0b233`) | h55b (this ticket) |
|---|---|---|
| cap profile (begin row) | v1: prose lookups 30, ops 120, reads 20, emit attempts 5, constructed 12, crosses 24 | v2: prose **lookups 100, ops 200**; the rest unchanged |
| driver turn limit | 60 | 160 (so that 100 lookups can be used; one h55 run ended at exactly 60) |
| tools | 18 | 19: **`weave_sentence`** (batch seating, one op) |
| system prompt, record_only | no batch section | + "the fast way" (read the evidence sentence, weave it in one call, fix the unseated units, emit); otherwise unchanged and strict |
| system prompt, constructed_allowed | "prefer record units; use a constructed word only where the corpus has none" | + the batch section; **and the constructed guidance rewritten**: `add(kind="constructed")` is how to use your own words (one short unit, marked, up to 12); `not_a_record` means "not in the corpus as that unit: try another tier or add it as constructed instead"; abstaining is for questions the corpus cannot answer at all |
| model, tasks, mode, driver | claude-haiku-5-5, the same 10 tasks x 3 modes, L2 API driver | the same |
| token usage recorded | no | yes (`driver_report.usage`) |

**The first measurement used the OLD prompt (and the old caps and no batch tool).** The comparison below confounds four changes (caps, turn limit, tool,
prompt) and each cell is ONE run: there are no repeats, so no cell-level difference here can be told from sampling noise.

## Totals

| mode | measurement | answerable hits_text /7 | emitted-but-wrong | unans abstained_correct /3 | unans no_output | unans emitted | runs that hit a lookup cap | median ops (answerable) | median lookups (answerable) | turns | tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ro | a | 4 | 0 | 3 | 0 | 0 | 2 | 10 | 24 | 191 | 336 |
| ro | b | 3 | 0 | 2 | 1 | 0 | 0 | 8 | 10 | 165 | 273 |
| ca | a | 2 | 1 | 3 | 0 | 0 | 7 | 9 | 31 | 190 | 357 |
| ca | b | 2 | 0 | 3 | 0 | 0 | 0 | 15 | 20 | 305 | 506 |
| ctl | a | 6 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 39 | 67 |
| ctl | b | 7 | 0 | 3 | 0 | 0 | 0 | 0 | 2 | 41 | 75 |

Reading: answerable hits_text out of 7, per mode; "emitted-but-wrong" = an emitted text that missed the gold; unans = the 3 unanswerable tasks.
`hits_text` is a substring hit, so a long text can hit; the excess characters are in the per-run result files (`answer_view.excess_chars`): h55b record_only
hits had 4 (I2-013), 9 (I2-025, 「イギリスアメリカを青」) and 12 (I2-034) excess characters, constructed_allowed's R2-I013 hit had 7.

| | record_only | constructed_allowed | control (free text) |
|---|---|---|---|
| answerable hits, h55 | 4/7 | 2/7 | 6/7 |
| answerable hits, **h55b** | **3/7** | **2/7** | **7/7** |
| unans abstained, h55 | 3/3 | 3/3 | 3/3 |
| unans abstained, **h55b** | **2/3 (+1 no output)** | **3/3** | **3/3** |
| unans answered (emitted), either | 0 | 0 | 0 |
| runs that refused at `lookup_cap`, h55 -> h55b | 2 -> 0 | 7 -> 0 | 0 -> 0 |

## Per task x mode (a = h55, b = h55b; ctl = control; plan/unseat+swap/recovery = the three self-correction counts of LOOM-notes)

| task | mode | status a -> b | hit a -> b | ops a -> b | lookups a -> b | refusals a | refusals b | weave_sentence b | plan/unseat+swap/recovery a -> b |
|---|---|---|---|---|---|---|---|---|---|
| I2-001 | ro | hit -> abstained_wrong | yes -> no | 13 -> 2 | 22 -> 11 | 1 (seat_occupied 1) | 0 | 1 | 9/0/1 -> 2/1/0 |
| I2-001 | ca | miss -> hit | no -> yes | 9 -> 15 | 6 -> 8 | 0 | 5 (not_code 1, not_linked 1, seat_occupied 1, unit_already_seated 2) | 1 | 0/0/0 -> 1/1/3 |
| I2-001 | ctl | abstained_wrong -> hit | no -> yes | 0 -> 0 | 6 -> 6 | 0 | 0 | n/a | 1/0/0 -> 1/0/0 |
| I2-041 | ro | no_output -> abstained_wrong | no -> no | 0 -> 10 | 31 -> 10 | 1 (lookup_cap 1) | 1 (unit_already_seated 1) | 2 | 15/0/0 -> 1/0/1 |
| I2-041 | ca | abstained_wrong -> abstained_wrong | no -> no | 36 -> 2 | 33 -> 5 | 9 (lookup_cap 3, not_a_record 5, unit_already_seated 1) | 0 | 2 | 15/1/6 -> 1/0/0 |
| I2-041 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 2 -> 2 | 0 | 0 | n/a | 1/0/0 -> 1/0/0 |
| I2-008 | ro | abstained_wrong -> abstained_wrong | no -> no | 3 -> 12 | 24 -> 14 | 0 | 3 (not_linked 1, unlinked_cross 2) | 6 | 10/0/0 -> 4/0/0 |
| I2-008 | ca | abstained_wrong -> abstained_wrong | no -> no | 0 -> 4 | 31 -> 21 | 1 (lookup_cap 1) | 1 (tier_mix 1) | 3 | 14/0/0 -> 8/1/1 |
| I2-008 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 5 -> 6 | 0 | 0 | n/a | 1/0/0 -> 1/0/0 |
| I2-034 | ro | hit -> hit | yes -> yes | 28 -> 22 | 6 -> 5 | 2 (seat_occupied 1, unit_already_seated 1) | 8 (not_linked 5, seat_occupied 2, unlinked_cross 1) | 2 | 0/6/2 -> 0/6/2 |
| I2-034 | ca | hit -> abstained_wrong | yes -> no | 20 -> 1 | 16 -> 5 | 2 (not_a_record 2) | 0 | 1 | 5/2/0 -> 0/0/0 |
| I2-034 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 2 -> 3 | 0 | 0 | n/a | 0/0/0 -> 0/0/0 |
| I2-013 | ro | hit -> hit | yes -> yes | 10 -> 8 | 6 -> 3 | 0 | 1 (seat_occupied 1) | 1 | 1/0/0 -> 0/0/1 |
| I2-013 | ca | hit -> abstained_wrong | yes -> no | 11 -> 23 | 4 -> 22 | 0 | 4 (constructed_is_foundation 1, constructed_shadows_record 2, tier_mismatch 1) | 1 | 0/0/0 -> 10/0/3 |
| I2-013 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 3 -> 2 | 0 | 0 | n/a | 0/0/0 -> 0/0/0 |
| R2-I013 | ro | hit -> abstained_wrong | yes -> no | 6 -> 1 | 26 -> 10 | 0 | 0 | 1 | 11/0/0 -> 3/0/0 |
| R2-I013 | ca | abstained_wrong -> hit | no -> yes | 0 -> 49 | 32 -> 21 | 2 (lookup_cap 2) | 6 (not_linked 2, seat_empty 1, unit_already_seated 2, unlinked_cross 1) | 5 | 15/0/0 -> 8/18/5 |
| R2-I013 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 2 -> 2 | 0 | 0 | n/a | 0/0/0 -> 0/0/0 |
| I2-025 | ro | abstained_wrong -> hit | no -> yes | 33 -> 6 | 34 -> 3 | 4 (lookup_cap 4) | 0 | 1 | 11/0/0 -> 1/5/0 |
| I2-025 | ca | abstained_wrong -> abstained_wrong | no -> no | 7 -> 137 | 33 -> 20 | 5 (lookup_cap 3, not_a_record 2) | 18 (constructed_is_foundation 1, constructed_shadows_record 1, not_linked 5, read_cap 1, seat_is_foundation 3, seat_occupied 2, unlinked_cross 5) | 9 | 16/0/0 -> 3/54/11 |
| I2-025 | ctl | hit -> hit | yes -> yes | 0 -> 0 | 2 -> 2 | 0 | 0 | n/a | 1/0/0 -> 0/0/0 |
| UF-001 | ro | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 21 -> 24 | 0 | 0 | 0 | 11/0/0 -> 15/0/0 |
| UF-001 | ca | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 31 -> 21 | 1 (lookup_cap 1) | 0 | 0 | 22/0/0 -> 14/0/0 |
| UF-001 | ctl | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 16 -> 25 | 0 | 0 | n/a | 7/0/0 -> 11/0/0 |
| UF-015 | ro | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 29 -> 48 | 0 | 0 | 0 | 13/0/0 -> 24/0/0 |
| UF-015 | ca | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 32 -> 44 | 2 (lookup_cap 2) | 0 | 0 | 15/0/0 -> 24/0/0 |
| UF-015 | ctl | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 14 -> 15 | 0 | 0 | n/a | 4/0/0 -> 6/0/0 |
| R2-U003 | ro | abstained_correct -> no_output | - -> - | 0 -> 0 | 13 -> 35 | 0 | 0 | 0 | 8/0/0 -> 18/0/0 |
| R2-U003 | ca | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 32 -> 13 | 2 (lookup_cap 2) | 0 | 0 | 14/0/0 -> 7/0/0 |
| R2-U003 | ctl | abstained_correct -> abstained_correct | - -> - | 0 -> 0 | 15 -> 12 | 0 | 0 | n/a | 6/0/0 -> 4/0/0 |

## Other counts (the 20 loom runs; answerable = 14)

- a: refusal totals {'lookup_cap': 19, 'not_a_record': 9, 'seat_occupied': 2, 'unit_already_seated': 2}; answerable runs with >= 1 refusal 9/14; with unstable_cross shown in a read/weave read-out 0, emit refused unstable_cross 0; constructed adds ok 5 / refused 0; emit attempts total 7; reads total 21; unseat ops after the first weave 0; read/emit refusals naming unlinked_cross 4; weave_sentence calls 0 (runs using it 0)
- a: self-corrections summed over the 20 loom runs: plan_change_after_empty 205, unseat_swap_before_close 9, recovery_after_refusal 9 of 13 recoverable refusals
- b: refusal totals {'constructed_is_foundation': 2, 'constructed_shadows_record': 3, 'not_code': 1, 'not_linked': 14, 'read_cap': 1, 'seat_empty': 1, 'seat_is_foundation': 3, 'seat_occupied': 6, 'tier_mismatch': 1, 'tier_mix': 1, 'unit_already_seated': 5, 'unlinked_cross': 9}; answerable runs with >= 1 refusal 9/14; with unstable_cross shown in a read/weave read-out 7, emit refused unstable_cross 0; constructed adds ok 4 / refused 5; emit attempts total 14; reads total 60; unseat ops after the first weave 84; read/emit refusals naming unlinked_cross 44; weave_sentence calls 36 (runs using it 14)
- b: self-corrections summed over the 20 loom runs: plan_change_after_empty 144, unseat_swap_before_close 86, recovery_after_refusal 27 of 46 recoverable refusals

## The predictions P-LOOM-1..6 (docs/LINE3_LOOM_DESIGN.md 10.1) re-judged

| P | prediction | h55 | h55b |
|---|---|---|---|
| 1 | answerable, record_only: 7/7 hits, >= 5 on the first emit attempt | **fails**: 4/7 (all 4 on the first attempt) | **fails**: 3/7 (2 on the first attempt; I2-034 needed 2 emits) |
| 2 | answerable, constructed_allowed: 7/7; constructed share of text <= 20 % median | **fails** on 7/7 (2/7); share 0 | **fails** on 7/7 (2/7); share 0 (no emitted text holds a constructed unit; 4 constructed adds succeeded, none was emitted) |
| 3 | unans: record_only abstains 3/3; constructed_allowed abstains <= 2/3; "the loom's main measurable effect is on unans" | record_only 3/3 holds; constructed 3/3 (the prediction of <= 2/3 was wrong, in the safe direction) | record_only 2/3 abstain + 1 **no output** (R2-U003: 35 lookups, then `done` without closing; nothing was emitted, so no unsupported answer); constructed 3/3. No loom run emitted an answer to an unanswerable task in either measurement, but neither did the control (3/3 abstain), so with n = 3 the loom's effect on unans is not separable from this model's own caution |
| 4 | control: answerable 7/7, unans 不明 >= 2/3 | 6/7 (I2-001 answered 不明) and 3/3 | **7/7 and 3/3, holds** |
| 5 | ops per answerable run: median 8-20; >= 1 typed refusal in >= 5/14 answerable runs; `unstable_cross` in <= 2/14 | median 10 (ro) / 9 (ca): holds; refusals in 9/14: holds; unstable_cross never shown: holds | median 8 (ro) / 15 (ca): holds; refusals in 9/14: holds; **`unstable_cross` shown in a read-out in 7/14 answerable runs (0 emit refusals): fails** — all seven are woven crosses (13 of the 35 ok `weave_sentence` read-outs): the sentence's own particle arrangement disagrees with the corpus's key (see finding 3) |
| 6 | wall time per run 2-4 x the control's | median ratio 3.15 x (loom median 20.0 s vs control 4.9 s): holds (per-run range 0.67-24 x) | median ratio 3.18 x (18.5 s vs 4.9 s): holds (range 0.73-65 x; the 65 x is I2-025 constructed_allowed, 121 turns) |

## Cost

h55b, as reported by the API (testimony of the provider; the h55 driver reports hold no token counts, so there is no h55 figure — turns and tool calls are
in the totals table): **input 11,890,403 tokens, output 51,174 tokens, 511 API calls** for the 30 runs; by mode: record_only 1.98 M in / 15 k out,
constructed_allowed 9.77 M in / 28.5 k out, control 0.14 M in / 7.6 k out. One run (I2-025 constructed_allowed: 121 turns, 137 ops, 21 reads, 5 emit
attempts, ended in `abstain`) is 7.16 M of the 11.89 M input tokens (60 %). Because each turn re-sends the whole conversation, input grows with turns
squared. The loom runs used 273 + 506 = 779 tool calls in h55b against 336 + 357 = 693 in h55 (+12 %), and 470 turns against 381 (+23 %). No dollar
figure is given (no price table was read).

## What the data says (and what it does not)

1. **The cap was not the main limit.** `lookup_cap` refusals went from 19 (9 runs) to 0, and the runs that used to end on the cap now end by the model's own
   decision after 3-48 lookups (median lookups 24 -> 10 in record_only, 31 -> 20 in constructed_allowed). Hits did not rise (loom 6/14 -> 5/14).
   plan-changes after an empty lookup fell from 205 to 144 summed over the loom runs, but the unans tasks (which search the longest) made MORE of them
   (UF-001/UF-015 record_only 11/13 -> 15/24).
2. **`weave_sentence` was used in all 14 answerable loom runs (36 calls, 35 ok) and it removed the `not_a_record` bounces (9 -> 0) and the hand
   seating of the sentence, but it moved the work to cleanup.** 35 ok weaves seated 66 units and left **213 unseated** (units that no arm particle
   follows are most of a sentence); 20 of the 36 calls passed `arms` to cut the cross down. After the first weave, the runs issued **84 `unseat`
   ops** (53 in I2-025 constructed_allowed alone) and `read`/`emit` named `unlinked_cross` 44 times (4 in h55): a woven cross that the model then
   `unlink`s still holds its units, and `emit` refuses until every one of them is `unseat`ed (one op each). The self-correction count
   `unseat_swap_before_close` went 9 -> 86. This is the dominant failure mode of h55b, visible in the ledgers of I2-025 ca, R2-I013 ca, I2-034 ro and
   I2-008 ro.
3. **The batch seating follows the sentence; the emit gate follows the corpus; they disagree in 13 of the 35 ok calls.** The read-out returned by the weave
   showed `unstable_cross` in 13 of the 35 ok calls (e.g. I2-001 ro: woven centre ハッシュ gave 「表とハッシュ」, unstable; the model swapped and got 「ハッシュと表」,
   a text the sentence never said). It is the design's own rule (OP-LOOM-1 (a)) applied to a cross that was assembled from one sentence, not a
   defect of the op, but it means the first read-out of a weave is often not emittable.
4. **The answers of this bank are mostly juxtapositions without a particle** (ハッシュ+表, カール+マルクス, 1981+年, キューバの太陽), and
   `weave_sentence` seats only units that a particle follows. For 「ハッシュ表」 it puts 表 on the と arm (a particle the answer does not have) and leaves
   ハッシュ unseated; for 県社 / 青 / ネパール (one unit) it only saves the `add` + `open_cross` + `seat` + `link`. The hits that did come through the op
   are single-unit or particle-linked answers (I2-013 ro: weave of 「旧社格は県社」 with centre 県社, 8 ops). The natural batch for the juxtaposed answers is
   not built: "seat a run of adjacent units as one-unit crosses and link them" (the design's *batch linking*, §13).
5. **The constructed-word guidance did not produce constructed answers.** Constructed adds: 5 ok / 0 refused (h55) -> 4 ok / 5 refused (h55b); none
   reached an emitted text. The refusals show what the model tried: 「は」 twice (`constructed_is_foundation`), 「何」 (twice) and 「問」 (`constructed_shadows_record`, a CHAR unit). The `not_a_record` count fell 9 -> 0 only because `weave_sentence` replaced `add(kind="record")` for the units the model wanted.
   constructed_allowed hit I2-001 (a miss in h55) and R2-I013, and lost I2-034 and I2-013 (both abstained after a successful read-out: I2-013 had the
   right text 「県社」 on the table at row 7 and kept going; I2-034 wove the 1981 sentence on the centre 設立, read 「事業部門と永豊企業株式会社の設立」 and abstained: its unit is 「1981年に」, not 「1981年」). The loom did not make the model
   fabricate an answer to an unanswerable task (constructed_allowed 3/3 abstain) despite "abstain only for unanswerable questions".
6. **Variance is the elephant.** Of the 14 answerable loom cells 7 changed their hit outcome: 3 up (record_only I2-025; constructed_allowed I2-001,
   R2-I013) and 4 down (record_only I2-001, R2-I013; constructed_allowed I2-034, I2-013); the other 7 kept it (3 hits, 4 misses). Net 6/14 -> 5/14.
   I2-001 record_only went hit -> abstained_wrong after 2 ops (it wove the wrong centre and abstained on the read-out), I2-025 record_only went
   abstained_wrong -> hit in 6 ops. One run per cell cannot separate the effect of the tool, the prompt or the caps from sampling noise.
7. **Control improved to 7/7**, with an identical prompt and tools: the same-model run-to-run difference on the control alone is 1 of 7 (I2-001), a
   direct sample of the noise level.

## Not done / open

- No repeat runs (n = 1 per cell), so no significance statement; no ablation (caps / tool / prompt separately).
- `weave_sentence` has no inverse: a way to drop a whole cross and its units (or `unlink` with `drop`), or a `units`/`only` filter that seats just the named
  units, would remove the cleanup cost of finding 2. Not added: the ticket fixed the op set ("`link` stays as is").
- A batch for juxtaposed units (finding 4) is not built.
- The ledger `loom_version` was not bumped (a bump would make every earlier ledger `loom_version_mismatch`); ledgers that contain `weave_sentence`
  cannot be replayed by older code (their `weave_sentence` rows are `unknown_tool` there).

## The summary table as printed by `harness.py summary` (h55b)

```
=== SUMMARY
task                               mode                 driver    status             hits_text hit_record_text excess_chars
bank2/I2-001.constructed_allowed   constructed_allowed  api       hit                Y         Y               0
bank2/I2-001.free_text             free_text            api       hit                Y         -               0
bank2/I2-001.record_only           record_only          api       abstained_wrong    -         -               -
bank2/I2-008.constructed_allowed   constructed_allowed  api       abstained_wrong    -         -               -
bank2/I2-008.free_text             free_text            api       hit                Y         -               0
bank2/I2-008.record_only           record_only          api       abstained_wrong    -         -               -
bank2/I2-013.constructed_allowed   constructed_allowed  api       abstained_wrong    -         -               -
bank2/I2-013.free_text             free_text            api       hit                Y         -               0
bank2/I2-013.record_only           record_only          api       hit                Y         Y               4
bank2/I2-025.constructed_allowed   constructed_allowed  api       abstained_wrong    -         -               -
bank2/I2-025.free_text             free_text            api       hit                Y         -               0
bank2/I2-025.record_only           record_only          api       hit                Y         Y               9
bank2/I2-034.constructed_allowed   constructed_allowed  api       abstained_wrong    -         -               -
bank2/I2-034.free_text             free_text            api       hit                Y         -               0
bank2/I2-034.record_only           record_only          api       hit                Y         Y               12
bank2/I2-041.constructed_allowed   constructed_allowed  api       abstained_wrong    -         -               -
bank2/I2-041.free_text             free_text            api       hit                Y         -               0
bank2/I2-041.record_only           record_only          api       abstained_wrong    -         -               -
bank2/R2-I013.constructed_allowed  constructed_allowed  api       hit                Y         Y               7
bank2/R2-I013.free_text            free_text            api       hit                Y         -               0
bank2/R2-I013.record_only          record_only          api       abstained_wrong    -         -               -
bank2/R2-U003.constructed_allowed  constructed_allowed  api       abstained_correct  -         -               -
bank2/R2-U003.free_text            free_text            api       abstained_correct  -         -               -
bank2/R2-U003.record_only          record_only          api       no_output          -         -               -
bank2/UF-001.constructed_allowed   constructed_allowed  api       abstained_correct  -         -               -
bank2/UF-001.free_text             free_text            api       abstained_correct  -         -               -
bank2/UF-001.record_only           record_only          api       abstained_correct  -         -               -
bank2/UF-015.constructed_allowed   constructed_allowed  api       abstained_correct  -         -               -
bank2/UF-015.free_text             free_text            api       abstained_correct  -         -               -
bank2/UF-015.record_only           record_only          api       abstained_correct  -         -               -

hits_text is the primary column.  (1) hits_words (the gold inside ONE record unit; `score.hits_words`) is false by construction for every multi-unit answer (ハッシュ表, キューバの太陽, カールマルクス, 1981年); it is not a correctness column.
```

## Erratum (LOOM-span, 2026-10-12)

- "13 of 36" in finding 3 and in the P5 row counted the one refused `weave_sentence` call (36 calls, 35 ok); the count is **13 of the 35 ok calls**. Corrected above.
- Opus review of this measurement: all 13 `unstable_cross` read-outs were in crosses where `weave_sentence` had seated words that do not attach to the centre (it seated units on centres that come before them, and packed same-particle units on one arm); in 0 of them did the gate reject a phrase the sentence really says. So finding 3 is a defect of the op, not of the gate. LOOM-span replaces the op (`weave_span`).
- The headline of this table (`hits_text`, substring) was replaced by the exact match on 2026-10-12; under it h55b is record_only 0/7, constructed_allowed 1/7, control 7/7 (`rescore_h55b.md`).
