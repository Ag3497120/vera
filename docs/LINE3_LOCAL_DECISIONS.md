# LINE3 local decisions (design §8.2)

Every local decision recorded in the code so far, copied from the code's own words. Nothing here is an owner decision; none changes meaning-level behaviour. Meaning-level questions are listed at the end as open points.

## Geometry (verantyx/line3/geometry.py)

| id | decision | location |
|---|---|---|
| L-15 | Composition convention: (g*h)(a) = g(h(a)), i.e. h acts first. | geometry.py, class Rotation docstring |
| L-16 | G24 index order = lexicographic perm; an index is a label, never a tie-break winner. | geometry.py, _build_group |
| L-17 | Opaque cell values limited to int, str or None so that serialisation is exact and hash-seed independent (L-02: no floats). | geometry.py, _check_cell |
| L-18 | Contents are not moved by a rotation; the orientation g in G24 is stored (design §3.3 `orientation : g`). | geometry.py, class Cross docstring |
| L-19 | Cross serialisation is exact, deterministic bytes including orientation. | geometry.py, Cross.serialize |
| L-20 | swap(p, p) is the identity (allowed, so the move is total). | geometry.py, swap |

## Space (verantyx/line3/space.py, module docstring)

| id | decision | location |
|---|---|---|
| L-30 | RUN content runs come from verantyx.lang.ja_content_runs (design 3.1 default); the text between consecutive runs (incl. runs that function dropped: digits, dates, stop words) is cut at every non-letter/number/mark character and each piece is a unit (design 3.1: "は", "の", "にある"). | space.py module docstring |
| L-31 | Surfaces are kept as written (no Unicode normalisation, no case folding). | space.py module docstring |
| L-32 | A character is "letter-like" iff its Unicode category starts with L, N or M; everything else (punctuation P*, symbols S*, separators Z*, controls C*) is dropped in every tier. A WORD token is a unit iff it contains at least one letter-like character; a unit is its whole surface (L-31). | space.py module docstring |
| L-33 | Sentence id = position in the input sequence. Duplicate sentences are stored separately and each counts in N (no silent de-duplication). | space.py module docstring |
| L-34 | n(u,v) and p(u,v) are computed on demand from postings / stored word order (L-13) and never cached; the serialisation stores units, postings, sentence unit lists and r0 only. | space.py module docstring |
| L-35 | Serialisation = canonical JSON (sorted keys, compact, UTF-8, units sorted by code point; sorting is for byte identity, never to pick a winner). | space.py module docstring |
| L-36 | A sentence with no unit in a tier stays a sentence (counts in N). | space.py module docstring |
| L-40 | Every sentence has a `kind` in KINDS (base / memory_query / memory_answer / memory_user, design L-19) and a `source`. Missing kind = "base"; an unknown kind raises ValueError (no silent coercion). `Space.sentences` stays (text, source) pairs; kinds live in the parallel tuple `Space.kinds`. | space.py module docstring |
| L-41 | Append (`Space.append`, `TierSpace.append`) returns a NEW immutable object; old sids, old postings (as prefixes) and old sentence_units are unchanged, new sentences get sids N..N+k-1. Appending == building from scratch on all sentences, byte for byte (tested). | space.py module docstring |
| L-42 | `postings_union(tier, units)` = sorted distinct sids of the union of the units' postings (M-1(c): a bundled state's quantity). A unit not in the tier raises KeyError (no silent skip); an empty set gives (). | space.py module docstring |
| L-43 | FORMAT bumped to line3.space.v2 because every sentence entry now carries "kind"; the serialisation of the unchanged part is otherwise untouched. | space.py module docstring |
| L-44 | `strip_attribution` is applied to every sentence text BEFORE it is split into units (build_space, Space.append); the stored sentence text keeps the original, only the units are computed from the stripped text. | space.py module docstring |

Note: L-44 is the number given to the `strip_attribution`-before-splitting step (space.py `build_space` and `Space.append`; previously unnumbered).

## Energy (verantyx/line3/energy.py, module docstring)

| id | decision | location |
|---|---|---|
| L-50 | n(q,q) = n(q): a query unit shares every sentence with itself, so a placed query unit gets +n(q)/N (literal reading of the N-01 formula). | energy.py module docstring |
| L-51 | The query is a set: repeated query units count once. | energy.py module docstring |
| L-52 | Query units or placed units absent from the space have n = 0 (energy 0, no shared sentences); they are neither errors nor evidence. | energy.py module docstring |
| L-53 | Placed unit absent from the space: r0 = 0 (same rule as L-52). | energy.py module docstring |
| L-54 | A section looks along every arm visible in its window (I-09); each arm is walked separately; the section points to the terminus with the strictly greatest energy (same unit from several arms is one candidate; a tie between different units, or no terminus, points nowhere). | energy.py module docstring |
| L-55 | Walk (design 4.4 R1): outer end k=0 -> ... -> k=L-1 -> centre. A step x -> y is taken iff y is not an empty seat, the edge is evidenced (n(x,y) > 0) and E_s(y) >= E_s(x) ("does not drop"). The unit where the walk stops is the terminus (the centre unit if the centre is reached). A walk starting on an empty seat has no terminus. | energy.py module docstring |
| L-56 | A unit placed on several seats gets the sum of its per-seat F and B. Pairs of seats holding the same unit contribute nothing. | energy.py module docstring |
| L-57 | A "working" section is one whose pointer is not None. The section ratio R1 points to u iff there is at least one working section and all working sections point to u. Working sections that point to different units give status "section_disagreement" (design 4.8); R1 is then None. | energy.py module docstring |
| L-58 | A maximum must be strictly positive to point at a unit: an all-zero quantity carries no evidence and points nowhere. | energy.py module docstring |
| L-59 | A section's energy is E_q when a query unit q is attached to it (I-07, design 4.1) and E_Q otherwise. | energy.py module docstring |

## Other local labels in the design (docs/LINE3_DESIGN.md §8.2)

L-01 to L-14, L-19 (kind; also used as L-40 in space.py), L-20 (observation record; a different item from geometry L-20) and L-21 to L-23 are design defaults, not yet recorded by code. Note the number clash: design L-19/L-20 (kind, observation record) versus geometry L-19/L-20 (serialisation, swap identity).

## OPEN POINTS (owner questions; behaviour not changed)

- RUN tier: question words are not separate units (`units_run('半田岩はどこにありますか')` gives `['半田岩', 'はどこにありますか']`), unlike the WORD and CHAR tiers. The T1 docstring now states this; whether the RUN tier should split them is the owner's decision.
