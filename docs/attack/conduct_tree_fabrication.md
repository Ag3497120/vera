# Conduct tree fabrication and provenance attack

The acceptance run completed in 0.09 seconds: 11 passed and 2 xfailed. Both
xfails are parameterized reproductions of the same anchor-membership defect.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| F-01 | ungrounded | Give `descend` a dict-backed arm holding `face`, force the router to select that arm, and pass an absent anchor (`missing` or `different-subject`). | `UNKNOWN_NO_ROUTE`, because the selected arm does not hold the named subject. | `ROUTED` to `unrelated-document`; the dict-backed profile has no `surface_mass`, so the anchor guard is skipped. Both parameter values xfailed. |

The expected behavior follows the module's named-subject anchor guard: an arm
that does not hold the anchor must stop descent. The test stubs only the router
to isolate whether `descend` enforces that guard on dict-backed profiles.

## What held

- A selected leaf arm retained its configured document identity.
- A router abstention returned `UNKNOWN_NO_ROUTE` at the current node.
- Term sequences reached the router in their original order, and caller-owned
  trails were not mutated.
- Anchor-aware profiles rejected an absent anchor and allowed an anchor they
  reported as present.
- Multilevel descent recorded each selected arm, while ordinary builds kept
  leaf stores as separate child objects.
- A federated hierarchy preserved the document name when its arm had a
  different sovereign name.

## What was not covered

- The tests stub `surface.route`; they do not validate its conduction scores,
  tie behavior, or face selection.
- No end-to-end answer generation or evidence record is part of this module's
  tested path, so this run does not establish traceability of later answers.
- The tests do not exercise large trees, stale or superseded records, or
  corpus-scale performance.
