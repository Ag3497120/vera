# COMPARE — the same 30 runs four times: h55, h55b (LOOM-batch), h55c (LOOM-span), h55d (LOOM-span after the Opus review), under the EXACT-MATCH headline

Ticket LOOM-span, review fixes (docs/LINE3_LOCAL_DECISIONS.md, `## LOOM-span（審査後の修正）`, L-LOOM-143..150). Tables are produced by `experiments/line3/loom/compare_h55d.py`
(it VERIFIES every ledger and scores it with `score.py` as it is now, so the four measurements are judged by one rule) from `results_h55*/*.json` and the ledgers they name;
the words around them are hand-written. `COMPARE_TABLES.txt` in this folder is the unedited output of the script. All 120 ledgers of the four measurements verify and
replay IDENTICAL (so do the 30 scripted baseline ledgers).

One run per cell, model `claude-haiku-5-5`, the L2 API driver, caps v2, turn limit 160, the 10 tasks x 3 modes, sequential. The key came from the Keychain through
`keyring_loom.py` and was never printed; a grep of the new ledgers, results and log for the key prefix finds nothing; only the Anthropic API was called.

## What changed between h55c and h55d (it is, again, more than one change: the confound is stated, not separated)

| | h55c | h55d |
|---|---|---|
| tool arguments of `weave_span` | `from` / `to` through a FastMCP alias hack | **`first` / `last`** (inclusive), a plain `@mcp.tool()`; the ledger still stores `from` / `to` (L-LOOM-145) |
| `unstable_cross` of a woven cross | lists the improving swap; the model took it (I2-025) | a cross made by `weave_span.v2` (not edited since) lists **no swap**; the refusal says "faithful to sentence N but unstable under the key; choose another stretch, or abstain" (L-LOOM-146) |
| prompts (both loom modes) | "weave only the words that answer" | + **"NEVER weave a word that appears in the question; answer with the SHORTEST span that answers, often ONE unit"** with three invented one-unit examples (L-LOOM-147) |
| notes | CONFLICT / UNANCHORED / NO_RECORD | + **`QUESTION_ECHO`** (notes.v2): a prose thread unit of >= 2 characters that is a word of the question; non-blocking, gold-free (L-LOOM-147) |
| `hit_cited` | T9-normalised substring | letters only on both sides (L-LOOM-143); the headline is unchanged |

The examples in the prompts are NOT the ones the review named (青, 県社, 1981 + 年): those are the golds of I2-025, I2-013 and I2-034, `test_no_gold_in_the_agent_prompts` forbids them
and a prompt that holds the answer of a measured task measures nothing. The prompts use invented sentences of the same shape (桃山院, 赤, 1975 + 年).

## Headline: answerable exact hits /7

| | record_only | constructed_allowed | control (free text) |
|---|---|---|---|
| h55 | 1/7 | 0/7 | 5/7 |
| h55b | 0/7 | 1/7 | 7/7 |
| h55c | 2/7 | 2/7 | 6/7 |
| **h55d** | **6/7** | **5/7** | **6/7** |
| (h55d, old `hits_text` rule) | (6/7) | (5/7) | (7/7) |

Unanswerable (3 tasks): abstained correctly 3/3 in every cell of h55d (loom ro, loom ca, control); no loom run answered an unanswerable task in any measurement.
Over-extension is gone from the loom cells: **the exact rule and the substring rule now agree** (6 = 6, 5 = 5). The control did not move (6/7; its one miss, I2-041, is a line 「「キューバの太陽」という意味」 that holds the gold; in h55b and h55c the same task was an exact hit).

## Over-extension, before and after (answerable loom runs that EMITTED a text that holds the gold and is longer than it)

| | emitted (of 14) | over-extended | exact | the others |
|---|---|---|---|---|
| h55 | 7 | 5 | 1 | 1 |
| h55b | 5 | 4 | 1 | 0 |
| h55c | 12 | **7** | 4 | 1 wrong (I2-001 ca) |
| h55d | 14 | **0** | 11 | 3 do not hold the gold: I2-008 ro and ca emitted 「マルクス」, I2-001 ca 「連想配列」 |

h55c's seven (5 + 9 + 3 + 6 + 4 + 4 + 5 characters over): 「キューバの太陽という意味」, 「キューバの太陽カクテルという意味」, 「1981年に設立」, 「1981年に設立された」, 「旧社格は県社」 twice, 「アメリカの青」.
The same seven tasks in h55d: 「キューバの太陽」 twice, 「1981年」 twice, 「県社」 twice, 「青」 (ro; ca also 「青」), all exact.

**The cost of the rule is under-extension.** I2-008 (gold カール・マルクス, two units in the sentence) was woven and emitted as the one unit 「マルクス」 in both loom modes (h55c: both exact). The prompt says "SHORTEST span ... often ONE unit"; two of the 14 runs took
it one unit too far. I2-001 ca 「連想配列」 is the same wrong answer as in h55c (「ハッシュテーブルは連想配列」), now without the extra words. Not changed after seeing this: the ticket asks for one re-measure of one condition.

## QUESTION_ECHO

In h55d the note was shown in 2 ledgers (6 `loom_note` rows): I2-001 record_only on 「ハッシュ」 (after the weave, the read and the emit; the unit is the first half of the answer ハッシュ表 and a substring of the question's ハッシュテーブル: a FALSE POSITIVE on an exact hit, which did not stop the run) and I2-025 record_only on 「アメリカ」
(after the weave of アメリカを青; the model then read the other sentence, wove 青 alone, dropped the first cross and emitted 「青」; it also saw the no-swap `unstable_cross` advice in the same moment, so the two effects are not separable).
Applied BACKWARDS to the final threads of the earlier measurements (`echo_units` in the table, same definition, replayed ledgers): **h55c 11 units in 8 of the 12 runs that emitted: all 7 over-extended runs and the wrong I2-001 ca; none of the 4 exact hits.** h55d: 1 unit in 1 of 14 runs (the false positive above).
So as a detector of the failure the note separates the cases well in this sample (7 of 7 over-extensions flagged, 0 of 4 exact hits flagged in h55c) and has one false positive in h55d; n = 14 per measurement, one run per cell.
In 12 of the 14 answerable loom runs of h55d no echo note was ever shown and none over-extended: the prompt rule (or sampling) did the work there; the note's own contribution is not isolated.

## The predictions P-LOOM-1..6 (docs/LINE3_LOOM_DESIGN.md 10.1), re-judged

| P | prediction | h55c | h55d |
|---|---|---|---|
| 1 | answerable, record_only: 7/7 exact hits, >= 5 on the first emit attempt | fails: 2/7 | **fails by one: 6/7, all 6 on the first attempt** (the one miss is I2-008, 「マルクス」) |
| 2 | answerable, constructed_allowed: 7/7 exact; constructed share of text <= 20 % median | fails: 2/7; share 0 | **fails: 5/7** (I2-001 「連想配列」, I2-008 「マルクス」); share 0 (no constructed unit was added in any h55d run) |
| 3 | unans: record_only abstains 3/3; constructed_allowed <= 2/3 | ro 3/3, ca 3/3 | ro 3/3 holds; ca 3/3 (wrong direction for the "<= 2/3" part, right for safety); the control abstains 3/3 too, so with n = 3 the effect is not separable from the model's own caution |
| 4 | control: 7/7 exact, unans 不明 >= 2/3 | 6/7 | 6/7 fails by one (I2-041: the line holds the gold, is not equal to it); 3/3 holds |
| 5 | ops per answerable loom run: median 8-20; >= 1 typed refusal in >= 5/14; `unstable_cross` shown in <= 2/14 | median 3; 7/14; 2/14 | **median 1 (min 1, max 4): below the band; 0/14 runs with any refusal: fails the "refusals" part (the structure was used without a mistake); `unstable_cross` shown 1/14: holds** |
| 6 | wall time per run 2-4 x the control's | 2.91 x | **1.71 x** (loom median 6.1 s, control 4.0 s; per-run range 1.02-3.05 x): below the band, i.e. the loom is cheaper than predicted |

## Cost (API-reported usage, testimony of the provider)

| | input tokens | output tokens | API calls | loom tool calls | turns | median ops (answerable ro / ca) |
|---|---|---|---|---|---|---|
| h55b | 11,890,403 | 51,174 | 511 | 779 | 470 | 8 / 15 |
| h55c | 2,617,791 | 30,946 | 268 | 403 | 230 | 2 / 6 |
| h55d | **2,363,157** | **28,445** | **232** | **347** | **192** | **1 / 1** |

h55d against h55c: input -9.7 %, output -8 %, calls -13 %, loom tool calls -14 %. The largest h55d run is UF-015 record_only (510,802 input tokens, an unanswerable task searched to the caps; h55c's largest was 330 k): the saving is on the answerable tasks, where every loom run used 1-4 ops.
Refusals: 0 in all 30 runs (h55c 11: `unit_not_in_sentence` 3, `span_inexpressible` 2, `unstable_cross` 2, `tier_mix` 1, `already_linked` 1, `constructed_is_foundation` 1, `seat_occupied` 1); `weave_span` 15 calls, 15 ok, in the 14 answerable loom runs; `drop` 1 (I2-025 ro); unseat 0.

## What the data says (and what it does not)

1. Over-extension went from 7 of 14 to 0 of 14 and the exact headline from 2/7, 2/7 to 6/7, 5/7 in the two loom modes, at lower cost. That is a large movement, but it is ONE run per cell, the control (the same prompt and the same read-only tools in all four measurements) moved 5 -> 7 -> 6 -> 6 of 7, and four things changed at once
   (first/last, the rule in the prompt, the echo note, the no-swap advice). The rule in the prompt is the likeliest main cause (12 of the 14 runs never saw an echo note), the note and the advice are each visible in one run (I2-025 ro). No ablation was made.
2. The I2-025 case, the one the review looked at, is closed: both loom modes emit 「青」. In ro the model first wove アメリカを青, was shown the note and the faithful-but-unstable refusal (no swap offered), and chose a different stretch; in ca it wove 青 alone from the start.
   Nothing in h55d took a swap that changes quoted text. The gate itself is unchanged for hand-built crosses and for crosses a model edited; whether a faithful stretch should be exempted from the key altogether (the review's option (b)) is still the owner's decision and is not implemented.
3. The new failure is the opposite of the old one: 「マルクス」 for カール・マルクス (2 runs) and 「連想配列」 (1). The prompt's "shortest span" needs a counterweight ("a name or a number that is written as several units is ONE answer"); not tried.
4. `hit_cited` is 0 in all 14 answerable loom runs of h55d (nothing is longer than the gold any more); with the letters-only comparison h55c's column is 3 runs (I2-013 ro/ca, I2-041 ro), see its COMPARE.md.
5. Unanswerable tasks: 9 of 9 abstained correctly in every cell; the loom's main effect on them remains not separable from the model's own caution (the control does the same).

## Not done / open

- Owner: option (b) of the review (an attestation exemption for a faithful span) is not implemented; (a) is, and it was enough for I2-025 in this run.
- The prompt's "shortest span" under-shoots on multi-unit names (item 3); n = 1 per cell, no ablation of prompt / note / advice; the QUESTION_ECHO false positive (ハッシュ in ハッシュ表) shows that a substring floor of 2 characters is not a definition of "the question's own word".
- The aborted attempts of the earlier ticket stay where they are (untracked).
