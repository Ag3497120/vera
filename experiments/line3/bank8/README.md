# bank8: held-out bank (35 answerable + 50 unanswerable), kept OUTSIDE every git worktree

`bank8.tsv`: 85 Japanese questions over the frozen fulllead corpus (`S300_fulllead.jsonl`, sha256 `d987fdee...`, identical to `experiments/line3/data/S300_fulllead.jsonl`;
sentence split = the lead split on 「。」, evidence ids `title#i`, 0-based). Columns (tab-separated, header starts with `#`): `#id kind shape subject question gold evidence notes audit`,
the bank6/bank7 columns. **35 answerable**, **50 unanswerable**: S1-alias 5, S2-place 5, S3-person 5, S4-toshite 5, S5-paren 5, S6-naming 5, S7-near 5, S8-chain 5,
and the new **S9-name 10**. Ids are the authors' (gaps = dropped items; `B8-` = round 1, `B8b-` = round 2).

- `gold`: answerable = verbatim phrase(s) of the cited sentence, alternatives separated by `|`; empty for unanswerable.
- `evidence`: answerable = the answer sentence; unanswerable = the subject sentence plus, where different, the tempting sentence, `;`-separated. For S8/S9 the tempting
  sentence is the one that holds the asked fact for another entity (it may be in an article that an earlier bank uses).
- **S9-name** (new): the subject is a rare proper name (katakana or unusual kanji; small town, village, station, shrine, bridge, embassy) and the corpus states the asked fact
  (旧社格, 駅番号, 面積, 橋長, 旧村域, 地区名) only for a *different* entity that shares a kind word with it (神社, 駅, 県, 橋, 村, 大使館); `check8.py` `KIND` records the word per item.
- notes (unanswerable) = what the sentence says / why the asked fact is absent / the plausible wrong answer, starting with the shape number.

## Provenance

- Authored by codex **gpt-6-luna** (effort max, workspace-write sandbox) with the same launcher as bank7 (`.claude/vera-audit/fleet.sh`, model L), in two rounds, each in a fresh
  directory under `vera-impl/bank8-author/`: `work8/` (round 1: the corpus only) and `work8b/` (round 2: the corpus plus `EXCLUDED_ARTICLES.txt`, 182 titles used by banks 2/3/4/6/7).
  Both logs (`bank2-author/fleet-out8/bank8.log`, `fleet-out8b/bank8b.log`) show only the corpus (and the exclusion list) was opened; no Vera code, document or rule was visible to the author.
- **`PROMPT8.md` was written at 2026-10-13T11:49:15+09:00** (sha256 `6fd9bd6f...`); round 1 launched 11:49:18 and its `bank8.tsv` was written 12:08:51.
  `PROMPT8b.md` was written at 2026-10-13T12:12:17+09:00 (sha256 `5c9e6504...`); first launch failed on a network error, relaunched 12:31:13; `bank8b.tsv` written 13:16:24.
  Briefs: `vera-impl/bank2-author/PROMPT8.md`, `PROMPT8b.md`; jobs `jobs8.tsv`, `jobs8b.tsv`. The brief shapes S1..S8 are bank7's; S9 is new.
- Audited by **Claude Sonnet 5.5** on 2026-10-13, blind to the rules: [AUDIT8.md](AUDIT8.md) (every one of the 206 authored items valid / fixed / dropped / surplus with a reason).
  The auditor wrote the 3 S8 re-wordings (B8b-U45, U47, U48) and the `|` gold alternatives of 13 answerables; everything else is the author's text.
- `MANIFEST.json` = sha256 of every file and of the authors' originals, written before any Vera system read the bank. **No Vera system has read this bank.**
- Written to `vera-impl/bank8-author/package/`, deliberately not inside a git worktree.

## Deviations from the brief (details in AUDIT8.md)

1. **Two rounds.** Round 1 landed on articles earlier banks already use (85 of 102 items; 18 answerables repeated an earlier gold, 14 unanswerables an earlier asked fact). Round 2 used an
   exclusion list of the used articles (the brief said "only the corpus file"; round 1 obeyed that). The final bank is 79 round-2 items + 6 round-1 items (B8-U09, U11, U39, U55, U58, U60).
2. Round 2's final message and `README8b.md` were lost to a network error; `check8b.txt` was produced by running the author's script (PASS).
3. S8: the author's relative-clause chains (B8b-U45, U47, U48) were re-worded by the auditor into the literal 「XのYのZ」 form.
4. Added to the brief for both rounds: at most 2 items per article and part (checker: at most 3 per article in all).

## Known limits

- 4 kept items share their *subject* article with an earlier bank and ask another fact (AUDIT8.md); 11 more cite an earlier-used article only as the tempting sentence (B8-U55 counts in both lists).
- Some S9 items have the same relation (駅番号 x3, 旧社格 x2, 旧村域 x2).
- Several unanswerables are answerable from outside knowledge (e.g. 面積, 人口, 旧社格); matters for `no_tools` / `free_text` controls, not for the gate.
- No S8 item of the brief's station-neighbour kind has a real neighbour in the corpus (the corpus has no 隣 relation); the S8 items are chains whose Z-fact is held only by another entity.

## Checks

`python3 check8.py > check8.txt` -> `check8.txt`: **PASS, 0 errors**: corpus sha, header/ids, counts (35 / 50, shapes >= 5, S9 >= 8), question form (ends in 「？」, no negation),
evidence resolution, verbatim golds not equal to the title or in the question, 52 recorded absence searches with 0 hits, S8 chain form, S9 kind word shared by both article titles,
per-article caps, zero identical question text and zero same-(article, gold) against banks 2/3/4/6/7 and `questions.tsv`, same-article wording similarity max 0.06.
