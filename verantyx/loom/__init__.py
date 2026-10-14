"""織機 (the loom): the model's only output channel is operating Vera's structure (docs/LINE3_LOOM_DESIGN.md).

The package is a new one next to verantyx/line3; it imports geometry / foundation / placement / space / granularity and modifies
none of them.  Everything is exact (int / Fraction), deterministic and independent of PYTHONHASHSEED.

  state    Unit, LoomCross, LoomState and the seating rules (design 3)
  corpus   the corpus the loom reads: the three tiers, the adhesion tables, the shas
  ops      the 20 operations as typed-refusal functions, the per-run caps, Run.step (one ledger row per call)
  read     the read rule, the annotated output, joins / adhesion marks, stability under the full key, the emit gate (design 3.4-3.7)
  code     the CODE tier's layout helpers only (spacing, one-token check); the code index and the definition-first gate are LOOM-e
  ledger   rows, the chain, append under flock, verify, replay, emitted_output (the L4 consumer)
  mcp      LoomServer (runs, sandbox, one ledger per run) and the FastMCP wrapper `vera loom mcp`
  scripted the deterministic scripted weaver (a fake model that issues operations)
  notes    LOOM-notes: the typed notes CONFLICT / UNANCHORED / NO_RECORD (a pass that points and lets pass) and the self-correction metrics
"""
LOOM_VERSION = "loom.v1"
