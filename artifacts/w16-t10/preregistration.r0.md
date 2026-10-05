# W16-t10 acceptance expectations (frozen before fixtures or implementation)

Registered: 2026-10-05 22:58 Asia/Tokyo. These are ticket acceptance checks, not measured outcomes.

1. Build a wheel from this worktree, install it in a new virtual environment, and run from an empty directory outside the worktree.
2. `vera --help`: exit 0 and stdout contains `usage: vera`.
3. `vera read 'ハルはミナに本を渡した。'`: exit 0 and one JSON object with schema `verantyx.semantic_read/1`, language `ja`, boolean `readable`, and list `clauses`.
4. `vera ask '誰が肥料を運んだ？' --mode round5 --document <temporary document>`: exit 0 and one JSON object with string `verdict`. This is a startup/shape check, not a truth or answer-quality claim.
5. Start `vera serve --no-llm` on loopback with an isolated store; GET `/v1/models` must return HTTP 200, JSON object, list-valued `data`, and first model id `vera-no-llm`; stop the process and require exit 0.
6. The wheel zip must contain members under `verantyx/constructions/` and `verantyx/data/`.
7. Trace successful runtime reads through builtins.open, io.open, read-only os.open, and sqlite3.connect. Compare only reads under installed `site-packages/verantyx/` against exact wheel-relative member paths. Do not infer unobserved files. Target missing-member count: 0.
8. Pack/fetch uses a tar archive and SHA-256 sidecar with `file://`; require digest equality, successful extraction, and printed `VERA_PLACEMENT` destination. A placement-backed `vera read` is separately required for P3; synthetic data, if used, is typed `constructed` and cannot establish that an external r9 asset works.
9. Do not run the whole test suite. P4 base-line comparison is for the auditor.

Non-package inputs (temporary user document, isolated store, logs, Python runtime modules) are recorded separately and excluded from the package-data comparison. Reads performed entirely inside native/OS libraries may not be visible to the Python-level tracer and must be disclosed as a measurement limit.
