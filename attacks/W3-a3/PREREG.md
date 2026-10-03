# W3-a3 attack preregistration

Registered 2026-10-03 13:08 UTC, before writing the attack test.

## Scope

Read only the specified `full/r6/run1` placement and the public query path. Derive the audit set from the placement itself: every headword with `origin=direct` and `gen_frame` in `by` (the documented 48 entries). Do not hand-select the set.

## Checks

1. Query every derived word and retain its JSON. Check the documented direct/frame invariants and audit its type and frame against its generated frame row and each qualifying `role_distribution` arm.
2. A frame contradiction is a qualifying significant particle whose role-distribution noun-type set is disjoint from the types exposed for that particle by the confirmed output frame. Report the word and both sets; do not require non-significant distributions to agree.
3. Query each derived word twice through the public API; serialized JSON bytes must match.
4. Probe the requested time words and representative inflected, compound, and verbal-noun forms. Compare `state`, `origin`, `top`, and `frame_status`; a probe is a hit only if an output contradicts §12 or conflates an unknown/estimated result with a direct one.

No product code, placement, or frozen test data will be changed. The r6 path is read only. This document's SHA-256 freezes the checks before the attack test is written.
