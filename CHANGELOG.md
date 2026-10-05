# Changelog

## v0.9-preview (not published; base: dev `d1942e2`)

Positioning: **a trustworthy record and verdict for the work AI agents do in Japanese** (see `public_overlay/README.md`). Nothing here has been pushed, tagged or uploaded; that needs the owner's permission.

### What is in this preview (from the auditor's record `docs/AUDIT_2026-10-06.md`)

| Ticket | Content | merge |
|---|---|---|
| W14-bench | public benchmark v1 (176 questions x 5 systems, run1 machine-graded) | `5e51985` |
| W16-t6 | `vera attest`: check completion claims against file hashes, collected tests, exit codes, numbers in output | `2685b34` |
| W16-t10 | wheel repairs, smoke test in a fresh venv, placement packing and `vera placement fetch` | `df25ce8` |
| W16-t7 | append-only, hash-chained ledger, `vera run`, hook template, secret redaction | `3baa0cb` |
| W16-t8 | human confirmation wired to decision points, `vera confirm`, measuring tools | `f299d8f` |
| W16-t2 | one answering path for ask, serve and chat | `a7507b3` |
| W16-t7b | the hook command reads pinned code; hooks never return exit code 2 | `739e0d3` |
| W16-t1b | modal auxiliaries are not read as events; name-plus-title answers are not cut | `8ddfddf` |
| W16-t3 | serve layer 0: the document goes to the LLM and its verbatim quotes are checked (`anchored` / `unanchored` / `conflict`) | `2730c38` |
| W16-t3b | quote check narrowed after the first attack wave: role particles, tense, one quote carries the answer, a cited source with another directory is `relocated` | `1d37c57` |
| W16-t6b | attest uses only ledgers that pass the T7 verification (else `TESTIMONY`, `LEDGER_UNVERIFIED`); `--ledger-head` | `995fa4b` |
| W16-t7c | redaction also checks the full-width, percent-decoded and base64-decoded forms of each token and redacts the whole original token | `ccfc839` |
| W16-t11 | documentation: README rewritten, numbers table with denominators, `tools/readme_numbers_check.py`, known issues | (this change) |

Measured numbers, with denominators and sources: `public_overlay/README.md` (table) and `public_overlay/EVAL.md`. Known holes: `public_overlay/KNOWN_ISSUES.md`.

### Reproduce

```bash
python -m benchmarks.public_v1.run --system Ap --backend ollama --model qwen3.8:27b-mlx --out <dir>
python -m benchmarks.public_v1.score --run <dir> --out <dir>/table
```

Systems A, B, C and D run the same runner with `--system A|B|C|D --model qwen3.5:4b`; C and D also take `--placement <placement>`. Temperature 0, no randomness, ties abstain (`docs/BENCHMARK_PUBLIC.md`, "Reproduce"). Hosted-API systems are not measured (no network was allowed). Recompute every README number from its source: `python tools/readme_numbers_check.py numbers`.

### Release assets (built, **not uploaded**)

Full list with the commands and the checks: `artifacts/w16-t11/release_assets.md` (development tree).

| Asset | sha256 | State |
|---|---|---|
| `verantyx_vera-0.1.0a1-py3-none-any.whl` (built with `tools/release/smoke_wheel.sh` from a working tree whose `verantyx/` is identical to the base commit; the README in it was the edited one) | `bf39208a0afa614d2ce5fef85b7570ee01c71edc1fb6d95ad5ffc00ddf7b15d5` | not uploaded |
| placement packing `r9-run2.tar` (built by the auditor in T10; not rebuilt here) | `12c1b1cb6a76d0143b827b9328060da5623dc93729c0131defe6447ace551890` | not uploaded |

The sha256 of a wheel **changes every time it is built** (measured: two builds of the same tree gave different values). When the wheel is rebuilt for the release, take the sha256 again and update this table and the README. There are two distributions in the tree (`verantyx_vera 0.1.0a1` from the root `pyproject.toml`, `vera-ja 0.2.0a1` in `public_overlay/`); which one ships is for the auditor and the owner to decide. **The wheel listed here was built from the product code of `ecde332`; it does not contain the product code of `d1942e2` (`attest`, `quote_check`, `ledger_events`, `cli`). Rebuild it before the release and take its sha256 again.**

### Before publishing: what to remove or check

Run `python tools/readme_numbers_check.py prepublish`; it must report zero hits for: local user name, absolute paths into a home or temporary directory, internal names, references to the hidden bank, e-mail addresses, secret shapes, and the account name read from `git config user.name`. It covers `public_overlay/README.md`, `KNOWN_ISSUES.md`, `EVAL.md`, `public_overlay/docs/README_LEGACY_d25a73a.md` and this file (`CHANGELOG.md`); five files in all, the same list as the default of the checker.

Outside the files this change may edit (not changed; for the auditor to decide): `public_overlay/pyproject.toml` (`Homepage`) and `public_overlay/vera_base/corpus.py` name the v0.1.0 release URL under the author's account. The scan of those two files is saved as `artifacts/w16-t11/r4_outside_scope.txt`.

### Not done / pending

- The output of the serve layer 0 example in the README is to be pasted by the auditor (marker `AUDITOR_RUNS: serve-layer0`).
- Attack results of the first attack wave are in the README ("Attack results"; from `docs/AUDIT_2026-10-06.md` at `d1942e2`). The next wave is not scheduled.
- Human grading of the W14 benchmark.
