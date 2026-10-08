# Air vs Pro: `test_legacy_and_round5_cli_outputs_are_byte_identical...` (10/20 on the Air)

## Verdict
Root cause: an **ambient corpus directory exists on the Air and not on the Pro**. It is not MeCab, not Python 3.11.14 vs .15, not locale, not a leaked path or timestamp.

- Air: `~/Projects/vera-corpus/build/` exists (about 4 GB; `writer.json` 11,207,322 bytes, `vera.db` 151,105,536 bytes, `pun_lexicon.json`, ...; dated Aug 31 to Oct 8).
- Pro: `~/Projects/vera-corpus` does not exist. There is no bundled `vera-corpus/` beside the package either (`verantyx/paths.py` checks `<repo>/vera-corpus/build/vera.db`; absent on both machines).
- `verantyx/paths.py::corpus_root()` falls back to `~/Projects/vera-corpus`, so `meaning_assets.BUILD` is `~/Projects/vera-corpus/build`.
- `verantyx/question.py::_typo_assets()` returns None when `BUILD/writer.json` is missing, so `_typo_reading` yields `LACK_OF_ASSET`. With the file present it loads the lattice/vocab and runs `typo_recovery.recover`, and the trace records `status: ran` plus a real verdict.
- `cli_baseline.json` was recorded on a machine without the corpus (the "asset absent" path). The Pro still has no corpus, so it matches; the Air does not.
- Only the 10 legacy `ask` cases (idx 0-9) reach this code. The round5 cases (idx 10-19) never touch the typo/sense assets, so they match on both machines.

## Evidence (one record_cli process on the Air, tree identical to the Pro worktree; rsync dry-run showed no file differences)
Case 0 (`--store <TMP>/store.json ask 東京は日本の首都ですか`), first differing byte: char index 725 of 4222 (baseline) vs 4199 (Air).
Around it, baseline bytes: `..."status": "abstained",\n      "verdict": "LACK_OF_ASSET"\n    },...`
Air bytes: `..."status": "ran",\n      "verdict": "IN_VOCABULARY"\n    },...`
(first differing byte is the `a` of `abstained` vs `r` of `ran` in the `typo_recovery.recover` trace step.)

Unified diff (identical shape in all 10 legacy cases; only the trace differs, rc = 0 and stderr hash equal in all):

    {"part": "typo_recovery.recover", "status": "abstained"->"ran", "verdict": "LACK_OF_ASSET"->"IN_VOCABULARY"}
    {"part": "meaning_assets.lattice", "status": "abstained"->"ran", "reason": "writer.json"->""}

Per-case typo verdict on the Air: IN_VOCABULARY for idx 0,1,2,5,6,7,9; UNKNOWN_NO_CANDIDATE for idx 3,4 (`2+3は`, `1+1=`; there the typo step's status was "ran" in both runs, so only its verdict and the lattice step differ: 6 diff lines instead of 8); TYPO_CANDIDATE for idx 8 (`ペンギンは飛べますか`). The top-level kind/ability/verdict/text of the answer are unchanged.

Baseline hash for case 0 stdout (sha256): 037d1ddffce89ebbf8787a5703da8146a22d55474f2af070b484b89648fe1854.

## Confirmation
- `record_cli.py check` on the Air, as is: `10 / 20 identical` (rc 1).
- Same with `HOME=/tmp/nohome_t9` (so `Path.home()/Projects/vera-corpus` does not exist): `20 / 20 identical` (rc 0). Nothing else changed.
- Setting `VERA_CORPUS_ROOT=<empty dir>` from outside does NOT help: `record_cli.env()` strips every `VERA_*` variable before spawning the CLI, so the override is dropped and the run stays at 10/20.

## Ruled out
- Placements: byte-identical on both machines (tools/determinism_probe.py), and not on this code path anyway.
- fugashi/unidic versions are the same on both (1.5.2 / 1.0.8) and the failing diff is in an asset-presence trace field, not a tokenization difference. Python 3.11.14 vs 3.11.15 is irrelevant: the divergence is explained fully by a file-existence check, and removing the file from view makes the Air pass.
- Wall-clock (`*_ms`) fields are masked by `MS` and not involved. Paths are replaced by `<TMP>` and not involved. stderr hashes are equal in all 20.

## Smallest fix
In `experiments/line3/t7/record_cli.py::env()`, after the `VERA_` stripping, pin the corpus to a path that cannot exist, which reproduces the recording condition on any machine:

    e.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT,
             VERA_CORPUS_ROOT=os.path.join(HERE, "_work", "no_corpus"))

(`_work` is git-ignored; the directory need not exist because `question.py` only tests `BUILD/writer.json`.) `cli_baseline.json` stays untouched and the Pro result is unchanged (the corpus was already absent there). Not verified by running (no repo edits made); the equivalent `HOME=` override was run and gave 20/20.

Alternative without code change (environment note only): on the Air, run this one test with `HOME` pointing at an empty directory, e.g. `tools/air.sh run 'HOME=/tmp/nohome python3.11 -m pytest ...'` (PYTHONPATH in air.sh is already expanded from the real `$HOME`, so it keeps working).

## Side notes
- The Air tree's `PRO_HEAD` file reads 4fa1000 while the Pro HEAD is 650aed8 (and the Pro tree has uncommitted changes): `air.sh push` copies the working tree, not HEAD, so `PRO_HEAD` is stale-looking but the content matched in the dry-run.
- Anything else in the suite that reads `~/Projects/vera-corpus` (core_abilities `GENERAL`, `PUN_LEXICON`, meaning_assets) may likewise behave differently on the Air than on the Pro; those results are machine-dependent until the corpus root is pinned.
- Home dir user names differ (Pro `motonisihikoudai`, Air `motonishikoudai`); no output depends on it here.
