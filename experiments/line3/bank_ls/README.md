# bank_ls: long work-log stories for the memory meter (instrument v2)

14 fictional work projects told as long logs (10-16 sessions, 96-160 messages, 600-840 sentences each) for the long-story meter of
`docs/LINE3_PUBLIC_DESIGN.md` section 6, in three splits that are **never mixed** (section 6.6):

| split | stories | use |
|---|---|---|
| `dev/` | 2 (LS-D01, LS-D02) | diagnosis, any number of times; the stories and questions may be read |
| `heldout_1/` | 6 (LS-H1-01..06) | the judging set of the current revision cycle: **one use only**; nobody who designs or implements the revision reads its stories or questions |
| `heldout_2/` | 6 (LS-H2-01..06) | reserved for the next revision cycle: untouched until then |

No story, scenario, sentence or question is shared between splits (checked, `check_cross.txt`: 0 shared sentences of >= 8 characters over 9,371, 0 shared
questions over 560, 0 speakers shared, largest shared 14-gram share between two stories 0.07 %). Each split has `stories.jsonl` (one story per line) and its own
`MANIFEST.json` (sha256 of every story as the author wrote it, of the packaged `stories.jsonl`, and counts). This README and `AUDIT_LS.md` carry **counts only** for
the held-out splits.

## Schema (the bank5 shape plus new keys)

```
{id, title,
 sessions:  [[{speaker, text}, ...], ...],                # 10-20 sessions of 8-25 messages; a sentence ends in 「。」
 plants:    [{kind, fact, values, message_refs: [[s, i], ...], note, old_refs?}],
 questions: [{q, gold, kind, refs: [[s, i], ...], checkpoint, form, stored_slot, asked_slot, subject_refs?, absent_terms?}],
 checkpoints:     [{index, fraction, after_session}],      # NEW
 ledger:          [{slot, value, ref}],                    # NEW (author's slot ledger; incomplete, see Known limits)
 subjectless_refs: [[s, i, k], ...]}                       # NEW (author-flagged sentences with no subject/topic of their own)
```

Refs are `[session, message]`, both 0-based (`subjectless_refs`: `[session, message, sentence]`). `mem_run.py --validate --bank <split>/stories.jsonl` loads every story.

- `plants.kind`: `contradiction | update | list_trap | repeat | reversal` as in bank5. Per story: **12 / 8 / 8 / 6 / 4**.
  contradiction = two messages, different values of one fact, no replacement marker (`message_refs` in message order, value i in ref i);
  update = ONE message `AからBに変更`-style (`message_refs` = [that message], `values` = [old, new]); **new key `old_refs`** = earlier message(s) that state the old value;
  reversal = `values` = [`AはBの前提`, `BはAの前提`] in two messages; list_trap = two look-alike facts that do not conflict (the two values may even be equal; enumeration trap);
  repeat = one sentence verbatim in >= 2 sessions (`values` = [the sentence], `message_refs` = every occurrence).
- `checkpoints`: four, after ~25 / 50 / 75 / 100 % of the sessions: `after_session = ceil(n*fraction)-1` (0-based, inclusive). The questions of checkpoint k are asked
  after session `after_session` of that checkpoint has been fed, and use only what appeared up to then. At least 3 / 6 / 9 / 12 contradictions and 2 / 4 / 6 / 8 updates are
  completed by checkpoints 0..3.
- `questions` (40 per story, 10 per checkpoint; **new key `checkpoint` = 0..3**): `kind` = `plain` (3 per checkpoint; a fact stated once; at least 4 per story are about one of
  the look-alike facts of a list_trap) | `contradiction` (3; gold `矛盾: X と Y`, X, Y in message order; `refs` = the plant's two refs) | `update` (2; gold = the new value;
  `refs` = the plant's message_refs) | **`absent`** (2; gold `記録なし`; `refs` = [], `subject_refs` = messages that mention the subject; `absent_terms` = strings that occur nowhere in the story; the
  asked fact is of a kind the story states for similar subjects but is stated nowhere, not even later). The harness's `canon_question_kind` maps `absent` to `plain`; a meter that
  scores absence must read `kind == "absent"` (or gold `記録なし`) itself. Each contradiction and each update plant is asked exactly once; the order of a checkpoint is mixed.
- Phrasing (new keys `form`, `stored_slot`, `asked_slot`): for non-absent questions `form` = `same` (`stored_slot`, the phrase the message uses for the slot, occurs in the question) or
  `rephrased` (it does not, and `asked_slot`, the question's own phrase for it, occurs in the question and in none of the referenced messages). At least 4 of the 8 non-absent
  questions of every checkpoint are rephrased: 20-32 of 32 per story (see `AUDIT_LS.md`). Absent questions have `form` = `absent`.
- `subjectless_refs`: sentences the author marked as having no explicit subject or topic of their own (topic carried from context); >= 30 % of the sentences in every story.

## Grading (as bank5, plus absence)

contradiction: the answer gives both values and marks the conflict (either order); update: the latest value (old value or a conflict report is wrong); plain: the value;
absent: abstain or say it is not recorded; any value is a confident wrong answer. Plants no question asks (list traps, repeats, reversals, and the contradictions/updates
of later checkpoints before they are asked) are for intake-time metering: flag contradictions and reversals, do NOT flag list traps or repeats.

## Provenance

- Authored by codex **gpt-6-luna** (`.claude/vera-audit/fleet.sh`, model L, effort max) in `vera-impl/bank7-author/ls/<key>/` (not in this repo), one fresh directory per story with no other
  file, from `vera-impl/bank2-author/PROMPT_LS_<key>.md` (all written 2026-10-13 10:12:45 +09:00 from `PROMPT_LS.template`). The brief names the topic and the rules above and contains no Vera
  code, document or gate rule. Each author wrote its own generator, checker (`check_ls.txt` PASS) and README (kept in the author directories).
  Topics (14 different): dev = a library's new building, a robot vacuum model; the held-out topics are not listed here.
- Job logs: `vera-impl/bank2-author/fleet-out7/` (first launch: 15 jobs), `fleet-out7b/`..`fleet-out7j/` (relaunches, resumes, repairs, audits). Four first-launch stories died with an API
  stream disconnect (`ls_h1_1`, `ls_h1_4`, `ls_h2_2`, `ls_h2_6`) and were rerun from scratch (the dead attempts are in `bank7-author/failed_attempts/`); `h1_4` died twice and its
  third run resumed the second attempt's files (`PROMPT_LS_h1_4_resume.md`); `h2_4` was rejected (404 repeated filler sentences) and regenerated with a no-repeat rule
  (`PROMPT_LS_h2_4_v2.md`, resumed once: `..._v2r.md`); `h2_1` and `h2_3` each had an unplanted inconsistency found by the independent reader and were repaired by their authors
  (`PROMPT_LS_h2_*_repair.md`; the pre-repair stories are `story.before_repair.jsonl` in the author directories).
- Independent check: a second codex pass (`PROMPT_LSAUDIT.md`) read each finished story **without the plants** and listed every contradiction, update, reversal and repeat; its output
  was compared with the plants by message refs (`AUDIT_LS.md`).
- `package_ls.py` builds the splits. Its only edit is mechanical and recorded per story in `MANIFEST.json` (`absent_refs_normalised`): `refs` of an `absent` question set to [].
- **No Vera system has read any of these stories**; the held-out splits were not read by the designer, only counted and mechanically checked (and, for the auditor, scanned for
  unplanted conflicts).

## Known limits (details in AUDIT_LS.md)

1. **Generated style**: the authors built the stories from structured sources by generators. Each story has a near-constant number of sentences per message, one or two fact sentences and
   filler/hand-work sentences per message, many with odd concrete detail. It is a work log in the sense of the brief (meetings, owners, deadlines, places, changes) but it is not
   natural prose in every message; the facts are stated in varied forms.
2. **Ledger is incomplete** (97-353 entries per story): it cannot prove that no unplanted slot carries two values; the independent reader and a lint cover the gap but not fully
   (its recall of the planted contradictions was 9-12 of 12).
3. **Subject-less share** is the author's own flag; a crude proxy (sentences without は / が / も) gives 25-77 %.
4. The `refs` of an `absent` question was normalised to [] by `package_ls.py`.
