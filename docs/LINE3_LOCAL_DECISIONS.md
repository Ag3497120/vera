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

## Placement (verantyx/line3/placement.py, module docstring)

| id | decision | location |
|---|---|---|
| L-60 | Pool = the units admitted to the cross. Moves = the 23 non-identity rotations and the swap of any two seats (empty seats included, geometry.moves_swap). No replacement by units outside the cross (design 3.4 "pool の外の単位とも" is NOT implemented; the T4 brief says rotations + seat swaps). | placement.py module docstring |
| L-61 | (kept; now exactly the owner's "区別しない" decision) State identity for ties = (centre, multiset of legs read outer to inner, empty seats kept). The key cannot see which leg is which, so leg permutations are one state; rotations only change orientation (key is rotation-invariant). The concrete Cross puts the legs in canonical sorted order with identity orientation (a label, not a winner). | placement.py |
| L-62 | **SUPERSEDED by the owner's decision after the T4 measurement (2026-10-06: tied arrangements are grown together as one state; see L-70). Kept for the record; no longer implemented.** Result status: STABLE = exactly one terminal state and no single move gives a different state of equal key; TIED = several terminals; PLATEAU = one terminal but a different state of equal key is one move away; BUDGET = branch budget exceeded. Only STABLE lets a cross grow (N-05). | placement.py |
| L-63 | Growth starts from the seed alone at the centre (L=1), stable by definition. Candidates = units v != seed with n(seed,v) > 0, grouped by n(seed,v) descending (M-1(b)); the anchor of the order is the SEED, not the current centre. | placement.py |
| L-64 | (kept, applied to every member of the class, see L-72) A group is inserted simultaneously and order-free: every step scores all (member, empty seat) pairs, best gain wins, ties branch; then local search to fixed points branching on all tied best improving moves. | placement.py |
| L-65 | L = minimal with 6L+1 >= units; growing L prepends an empty outer seat to every leg (edges unchanged, empties toward the outer end, design L-09). | placement.py |
| L-66 | **SUPERSEDED by L-73** (the 8-branch / 64-state budget). Kept for the record. | placement.py |
| L-67 | Energy log record per placed unit: r0, E_Q, E_Q/r0 (None if r0 = 0), in seat order (centre, AXES, k ascending), plus the three-ratio verdict; query as a set (L-51). | placement.py |
| L-68 | (stop reasons are now "exhausted" / "budget" / "max_groups"; the centre is now a set `centres`) Placement.capacity = number of units in the last stable state (== size); stop reason and the breaking group (units, share, status) are recorded. The same unit set may sit in the cross with a different centre than the seed (recorded: centre, centre_moved). | placement.py |

## Placement T4b: tied arrangements grown as one state (verantyx/line3/placement.py)

Owner's decisions after the T4 measurement (binding): tied arrangements are kept together as ONE state and grown; arm assignment is not distinguished; no replacement with units outside the cross; growth order by shares with the original seed.

| id | decision | location |
|---|---|---|
| L-70 | A state is a CLASS: a set of arrangements of one key, closed under single seat swaps that keep the key, and with no member from which a single move improves the key ("stable" = this fixed point of the class). No member is picked by order; the representative `Placement.cross` is the first member in canonical sorted order (a label, not a winner). Arm assignment is quotiented out (L-61). | placement.py |
| L-71 | Settling: level by level every state moves by ALL its best improving single moves (all tied results kept); terminals of the best key are taken, their closure under equal-key swaps is the class; if any member of the closure has an improving move, those moves' results (from every member) are climbed again until none has. Branches ending at the same key are the same class (union). | placement.py `_settle` |
| L-72 | Growth: the next share-group (shares with the original seed, equal shares together) is inserted into EVERY member (L-64 greedy insertion, all tied placements kept), all results are settled (L-71), the best-key class is kept. A step cannot "break" any more; it can only hit the budget. The lone seed's class is built like any other (seed at the centre or at an arm end: 2 members at L=1). | placement.py `build_cross` |
| L-73 | Budget (explicit, never a silent cut; replaces L-66): `Budget(max_class, max_states)`; max_class = most arrangements in one class, max_states = most distinct states handled in one growth step (insertion + climbing + closure). Exceeding either = BUDGET: growth stops, the previous class is restored (N-05), `Placement.stop == "budget"`, `Step.reason` names the budget, and the budget used is stored in every Placement (to_json_obj "budget"). Defaults 1000 / 20000. | placement.py |
| L-74 | Verification: `verify_class` (independent of the search; geometry's swap/rotate/edges) checks one key, every member a fixed point against all single moves, and closure under equal-key moves. `verify_fixed_point` is applied to every member in the tests. | placement.py |
| L-75 | `observe_class` takes the energy log on every member of the class (members in canonical order); `observe` / `energy_log` use the representative. Which member (or all) the later stages read is not decided here (see open points). | placement.py |

### T4b measurement (S300, 240 evenly spaced seeds per tier, budget max_class 1000 / max_states 20000 / max_moves 400000; every sampled 1 in 8 verified with verify_class: 0 failures)

| tier | capacity min / median / mean / max | stop: exhausted / budget | which budget | class size median / mean / max | time |
|---|---|---|---|---|---|
| RUN | 1 / 1 / 2.90 / 27 | 45 / 195 | max_moves 173, max_states 22 | 2 / 4.04 / 100 | 99.5 s |
| WORD | 1 / 1 / 3.80 / 32 | 12 / 228 | max_moves 221, max_states 7 | 2 / 4.47 / 354 | 77.3 s |
| CHAR | 1 / 14 / 25.17 / 140 | 1 / 239 | max_moves 235, max_states 4 | 2 / 1.66 / 8 | 179.9 s |

(T4 for comparison, strict tie rule: medians RUN 1, WORD 1, CHAR 3.) S3000 RUN/WORD were NOT run: at the S300 rate (0.3-0.4 s per seed) the 16193 / 13132 seeds need over an hour each, not under 10 minutes.

What the numbers mean: stability is now always reached (no step "breaks"); capacity is limited only by the explicit budget. A first group of many units with the same share (typical for RUN/WORD: 15-24 units with n(seed,v)=1) has an astronomically large tied class (units without mutual edges may float to any seat; the class is closed under those moves), so it cannot be enumerated and the step ends as BUDGET with the lone-seed class restored (class size 2 = seed at the centre or at an arm end; capacity 1). Symmetric toys grow (e.g. "A B C": capacity 3; "A B"/"B A": class of 2, centres A and B). Class sizes of kept states are reported per Step.class_size and Placement.class_size.


## Other local labels in the design (docs/LINE3_DESIGN.md §8.2)

L-01 to L-14, L-19 (kind; also used as L-40 in space.py), L-20 (observation record; a different item from geometry L-20) and L-21 to L-23 are design defaults, not yet recorded by code. Note the number clash: design L-19/L-20 (kind, observation record) versus geometry L-19/L-20 (serialisation, swap identity).

## OPEN POINTS (owner questions; behaviour not changed)

- RUN tier: question words are not separate units (`units_run('半田岩はどこにありますか')` gives `['半田岩', 'はどこにありますか']`), unlike the WORD and CHAR tiers. The T1 docstring now states this; whether the RUN tier should split them is the owner's decision.
- T4b (class growth): (a) With the owner's rule, "stable" is always reachable, so capacity is decided only by the budget; for groups of many equal-share units the full tied class cannot be enumerated (RUN/WORD median capacity is still 1, now because of BUDGET, not because of a tie). Whether to (i) raise the budget, (ii) represent the class implicitly (e.g. also treat arrangements that differ only by permuting interchangeable units - same share and same pair weights to every cross member - as one arrangement), or (iii) restrict the class to arrangements where every placed unit has a non-zero edge, is a meaning-level choice left to the owner. (b) The class includes the lone seed at an arm end with an empty centre (equal key 0); whether an empty centre counts as an arrangement is not decided. (c) The energy log / three ratios are taken on the representative (or every member via observe_class); which member the later stages read is not decided. (d) The class members have different centres, so "the centre" is a set (I-02, centres). 
- T4 placement (see report): (1) leg-to-leg arrangement: the I-04 key is identical for all 30 rotation classes of leg permutations, so the stability definition does not fix which arm holds which leg; sections (I-09 windows) do see adjacency. Left undetermined (L-61). (2) Budget values (L-66) change the capacity of some seeds (CHAR, S300: 2 of 233 sampled). (3) Design 3.4 "pool の外の単位とも" replacement not implemented (L-60). (4) Order anchor of M-1(b) is the fixed seed although the search may move the centre (L-63/L-68). (5) A lone seed is declared stable by definition (L-63); with moves into empty seats it has equal-key alternatives.
