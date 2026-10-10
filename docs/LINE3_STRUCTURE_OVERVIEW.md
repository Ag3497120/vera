# Line 3 structure overview (3D)

A single self-contained page that looks down on the whole built line-3 structure, drawn from built data and not from a schematic.

## What the view shows

| Object | What it is | Source in the build |
|---|---|---|
| Three translucent boxes: RUN, WORD, CHAR | the three tier sovereigns, side by side | `placements_*_{RUN,WORD,CHAR}_<level>*.pkl` |
| Small octahedral crosses inside a box | one stable cross per unit of the tier: six arms, one bead per seat | `Placement.cross` (centre, `arms`, `twin_sets`, `stop`, `class_size`) |
| Large wireframe octahedra above a box ("layer 1") | an upper cross that packs the stable states of lower crosses. Its seats are the lower crosses; they are drawn inside it, on its arms, and connected to its centre | `matryoshka.LayerStack.layer1("same")` then `Layer.cross_for(bundle)` |
| "Slide band" in front | the sliding windows. One window cross holds sentence N on the x arms and sentence N+1 on the z arms (reserved). Windows of one article sit in a column along z and are linked, because window j+1 starts at the sentence window j ended on | `slidewin_*.pkl` (`slide_place.SlidePlacement.doc`) |
| Foundation cross above RUN | the grammar layer: は at the centre, の に で と を が on the six arms in ladder order (Fibonacci weights as exact fractions). Sphere size is the number of RUN attachments of that particle. Faint lines go to a sample (at most 40 per particle) of RUN crosses whose kind is that particle; a tied kind joins each tied particle | `grammar.records_of_space`, `Records.kind` |
| Stacked discs at the right | the carry tower: units per level of the committed c3b measurement | `experiments/line3/carry/c3b/results/c3b_RUN_low_close.json` |

Controls: toggle each sovereign, layer 1, windows, grammar and carry; a minimum-fill slider; camera buttons (Overview, Top down, per sovereign, Nests, Slide, Grammar); hover for a label; click a cross, nest or window for its centre, arms with seats, stability and sentences in the right panel. The right panel holds the counts.

## Real data and layout

Real (read from the build, exported as ints, strings and exact `p/q` fractions): the units, the centre, every seat word on every arm (nearest the centre first), the seat counts, `stop`, the size of the tied class (`tied`, and `exp` for the twin-expanded class), the number of twins, the sentences that contain the centre, which lower crosses sit on a layer-1 cross, each window's seats with their sentence side, its per-axis key, evidence and improving-move counts, the grammar kind of each RUN/WORD cross and window, the particle totals, the carry level sizes.

Layout only (a choice of the page, not data): where a cross sits inside a sovereign (sorted by fill, then size, on a grid); the distances between sovereigns, nests, windows and the tower; the bead spacing and arm length scale; the order of nests (the ones packing the most lower crosses first); the dots on the tower discs; sphere sizes and the sampling of grammar lines. A lower cross that sits inside a layer-1 cross is drawn there and not in the field; one cross may sit in several nests and is then drawn in each.

## Stability

The design's stability `inv` (`cycle.EndState.inv`, L-103) is a query-time quantity: it is computed while a question is read and a build does not store it. The page therefore colours by what the build does hold: the **fill** of the stable state, placed units over (candidate units + the seed), as an exact fraction, together with `stop` (`exhausted` = every candidate placed, `budget` = the step that broke the budget was restored away, `max_groups` = the pool of an upper layer was cut) and the tied class size. Windows carry the recorded per-axis judgement (`stable_strict`, `improving_moves_left`). The slider filters crosses and nests by fill; it does not filter windows.

## Which corpus

The page is built from `experiments/line3/bank2/data/fulllead_sents.jsonl` (592 sentences of 300 real articles, sources `title#i`), because only a corpus with several sentences per article has windows. S300 cannot be windowed: its sources are `jawiki:page:N`, one sentence each, and `line3 build --structure slide` refuses it ("source is not 'title#i'"). Flat caches: `vera-impl/cache/f1b/placements_45efdaedb7ab_{RUN,WORD,CHAR}_mid_ordered-forward.pkl` (ordered insertion, level mid). Window cache: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_cf35f420cea6.pkl` (z_deep order, padding one, per-axis stability, unit_sid seats, seat_empty_axis deny, growth z_reserved: the spec the code computes today for level mid). Of its 592 windows, 292 hold a real sentence N+1 and 300 close an article with a constructed pad (empty z arms; never evidence).

## Layer 1: what was built and what was sampled

The upper crosses are built by the exporter with the library's own `LayerStack.layer1("same")` and `Layer.cross_for` (bounds `fast`: level low, 3 share-groups in the pool) over the whole tier's bundle space, one per seed, at an even stride over the seeds (at most 800 per tier; the rest are counted, not built). Three seeds were skipped for taking over 5 s (their seeds are in `meta.layers.stats`). Only 12 nests per tier are drawn: an even spread over the ranking by number of members, largest first, so both big and small nests show. Because the library hands every permutation of a twin set to `itertools.product` before the first arrangement exists, the exporter swaps in a lazy `expand_flats` that yields the same arrangements in the same order while it builds layer 1; build_cross uses only the first one.

## Exporter

```
PYTHONPATH=. PYTHONHASHSEED=0 python tools/export_structure_json.py \
    --data experiments/line3/bank2/data/fulllead_sents.jsonl --cache FLAT_CACHE_DIR --windows-cache WINDOW_CACHE_DIR \
    --out structure.json --level mid --layers on --layers-per-tier 12 --layers-sample 800 \
    --carry-json experiments/line3/carry/c3b/results/c3b_RUN_low_close.json
python tools/build_structure_overview.py --json structure.json --out index.html
```

The exporter reads caches and builds nothing except the layer-1 crosses (`--layers on`, library `fast` bounds, one process, a wall-clock cap per tier). Caps, recorded in `meta.truncated`: at most 12 seats per arm (the true count stays in `n`), 8 sentence ids per cross (the count stays in `ns`), at most `--layers-per-tier` nests per tier (an even spread over the member ranking), `--layers-sample` upper crosses built per tier. Open the page directly (`file://`); three.js loads from `cdn.jsdelivr.net`. A deep link such as `index.html#slide`, `#nest`, `#gram`, `#RUN` or `#sel-R12` sets the first camera or selection.
