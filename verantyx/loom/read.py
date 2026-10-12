"""LOOM-b / LOOM-c: the read rule, the annotated output, stability under Vera's own key, and the emit gate
(docs/LINE3_LOOM_DESIGN.md 3.4-3.7, 5.3; owner OP-LOOM-1 (a) 「完全な鍵 (n,p,a)」, OP-LOOM-3 (a) 「が・を・と・で・に・の → 中心」).

THE READ RULE (exact)
  read(thread) = concat(read(c) for c in thread)                                no separator for prose
  prose cross  = for the arms in ARM_ORDER (ascending ladder weight: が -z, を +z, と -y, で +y, に -x, の +x):
                     [the arm's data units, outer -> inner (k ascending)] + [the arm's particle, if the arm holds >= 1 unit]
                 + [the centre unit] + ["は" if the cross is marked topic and has a centre]
  code cross   = "    " * depth + spaced([centre] + for the arms in AXES order: [the arm's units, inner -> outer]) + "\n"
Every character of `text` belongs to exactly ONE segment of `annotated`: record, constructed, foundation (the particles and は: the
structure's, not the model's) or layout (code only).  The loom adds no other character: no punctuation, no space in prose.

STABILITY (OP-LOOM-1 (a))
  A woven cross has to be a fixed point of Vera's FULL key (n, p, a) = placement.seated_key before it can be emitted (OP-LOOM-4: the
  centre word's は adhesion is counted in `a` only when the cross is marked topic, `loom_key`): no single
  swap of two DATA seats (an empty seat counts, so a swap is also a move) strictly raises the key.  Exactly the moves of
  placement.verify_class_foundation: a swap that touches a foundation seat is not a move, a swap of equal contents is a no-op, a
  swap that would empty the centre is not a move (L-77).  A constructed unit is "\\u0000C:" + uid in the flat (L-LOOM-19): it is
  never in the postings (weight 0, L-52) and never equal to another cell.  The refusal lists EVERY improving swap and names the
  best one(s); it never picks a winner by order.  `STABILITY_MODES` is the one-line switch for the owner's answer: strict_npa
  (default: the full key), strict_np (n, p only), report (annotation only).
"""
from __future__ import annotations

import hashlib
from typing import Dict, List, Optional, Tuple

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.line3 import placement as pl
from verantyx.loom import code as codelib
from verantyx.loom.state import (AXES, CENTRE, CODE, CONSTRUCTED, PROSE, RECORD, SPEC, LoomCross, LoomState, fmt_seat)

STABILITY_MODES = ("strict_npa", "strict_np", "report")
DEFAULT_STABILITY = "strict_npa"

# OP-LOOM-3 (a): ascending ladder weight, so the heaviest particle is read last, next to the centre
ARM_ORDER: Tuple[str, ...] = tuple(sorted(AXES, key=lambda ax: SPEC.numerator(SPEC.arm_of_axis(ax))))
CONSTRUCTED_PREFIX = "\u0000C:"                       # L-LOOM-19
REFUSAL_ORDER: Tuple[str, ...] = (
    "empty_thread", "unlinked_cross", "empty_centre", "leg_gap", "tier_mix", "constructed_forbidden", "no_evidence", "unstable_cross",
    "parse_error", "undefined_name", "import_not_allowed", "unsupported_construct", "cross_not_one_statement", "line_cross_mismatch", "layout_changed_tokens")
KINDS = ("record", "constructed", "foundation", "layout")


# ------------------------------------------------------------------------------------------------------------
# segments
# ------------------------------------------------------------------------------------------------------------
def _unit_seg(state: LoomState, uid: str, cid: str, seat: str) -> dict:
    u = state.units[uid]
    if u.kind == RECORD:
        prov = {"tier": u.tier, "n": u.prov["n"]}
    else:
        prov = {"by": u.prov["by"], "at": u.prov["at"]}
    return {"s": u.surface, "kind": u.kind, "uid": uid, "tier": u.tier, "cid": cid, "seat": seat, "prov": prov}


def _fnd_seg(particle: str, cid: str, seat: str, arm: Optional[str]) -> dict:
    prov = {"kind": "foundation", "seats_sha": fd.seats_sha(), "ratio": "%d/%d" % (SPEC.numerator(particle), SPEC.den)}
    if arm is not None:
        prov["arm"] = arm
    return {"s": particle, "kind": "foundation", "cid": cid, "seat": seat, "prov": prov}


def _layout_seg(s: str, cid: str) -> dict:
    return {"s": s, "kind": "layout", "cid": cid}


def read_prose(state: LoomState, cross: LoomCross) -> List[dict]:
    segs: List[dict] = []
    for ax in ARM_ORDER:
        arm = cross.arms[AXES.index(ax)]
        held = [(k, c) for k, c in enumerate(arm) if c is not None and not fd.is_constructed(c)]       # k ascending: outer -> inner
        for k, uid in held:
            segs.append(_unit_seg(state, uid, cross.cid, fmt_seat(ax, k)))
        if held:
            segs.append(_fnd_seg(SPEC.arm_of_axis(ax), cross.cid, fmt_seat(ax, cross.L - 1), ax))
    if cross.centre is not None:
        segs.append(_unit_seg(state, cross.centre, cross.cid, CENTRE))
        if cross.topic:
            segs.append(_fnd_seg(SPEC.centre, cross.cid, CENTRE, None))
    return segs


def read_code(state: LoomState, cross: LoomCross) -> Tuple[List[dict], bool]:
    """The segments of one code line and whether the re-tokenize safety net holds (layout_changed_tokens otherwise)."""
    cells: List[Tuple[str, str]] = []                  # (uid, seat) in reading order: centre, then each arm inner -> outer
    if cross.centre is not None:
        cells.append((cross.centre, CENTRE))
    for ax in AXES:
        arm = cross.arms[AXES.index(ax)]
        for k in range(cross.inner_k, -1, -1):
            if arm[k] is not None:
                cells.append((arm[k], fmt_seat(ax, k)))
    if not cells:
        return [], True
    surfaces = [state.units[u].surface for u, _ in cells]
    seps = codelib.spaced(surfaces)
    segs: List[dict] = []
    indent = "    " * cross.depth
    if indent:
        segs.append(_layout_seg(indent, cross.cid))
    for i, (uid, seat) in enumerate(cells):
        segs.append(_unit_seg(state, uid, cross.cid, seat))
        if i < len(seps) and seps[i]:
            segs.append(_layout_seg(seps[i], cross.cid))
    segs.append(_layout_seg("\n", cross.cid))
    line = "".join(s["s"] for s in segs)
    return segs, codelib.line_keeps_tokens(line[len(indent):], surfaces)


# ------------------------------------------------------------------------------------------------------------
# annotation (display only: F2, never a gate and never a score)
# ------------------------------------------------------------------------------------------------------------
def annotate(run, segs: List[dict]) -> None:
    corpus = run.corpus
    prev: Optional[dict] = None
    for sg in segs:
        if sg["kind"] == RECORD and sg["tier"] in corpus.adhesion:
            arm = None if sg["seat"] == CENTRE else sg["seat"].split(":")[0]
            adh = corpus.adhesion[sg["tier"]]
            if arm is not None:
                sg["adhesion"] = {"particle": SPEC.arm_of_axis(arm), "n": adh.adj(sg["s"], SPEC.arm_of_axis(arm))}
            elif run.state.crosses[sg["cid"]].topic:
                sg["adhesion"] = {"particle": SPEC.centre, "n": adh.adj(sg["s"], SPEC.centre)}
        if prev is not None and prev["kind"] == RECORD and sg["kind"] == RECORD and prev["tier"] == sg["tier"] and sg["tier"] in corpus.adhesion:
            sg["join"] = {"prev": prev["uid"], "attested": corpus.join_attested(sg["tier"], prev["s"], sg["s"])}
        prev = sg


def render_marked(segs: List[dict]) -> str:
    """The text form of the CLI: a constructed segment is 【構成:...】, everything else as it is."""
    return "".join("【構成:%s】" % s["s"] if s["kind"] == CONSTRUCTED else s["s"] for s in segs)


def render_display(segs: List[dict]) -> str:
    """The annotated line of design 3.5: 東京[rec WORD n=7] は[fnd 233/377] ... です[con by <model> @4]."""
    out = []
    for s in segs:
        if s["kind"] == RECORD:
            out.append("%s[rec %s n=%d]" % (s["s"], s["tier"], s["prov"]["n"]))
        elif s["kind"] == CONSTRUCTED:
            out.append("%s[con by %s @%d]" % (s["s"], s["prov"]["by"], s["prov"]["at"]))
        elif s["kind"] == "foundation":
            arm = s["prov"].get("arm")
            out.append("%s[fnd %s%s]" % (s["s"], (arm + " ") if arm else "", s["prov"]["ratio"]))
        else:
            out.append(s["s"].replace("\n", "\\n"))
    return " ".join(out)


# ------------------------------------------------------------------------------------------------------------
# stability (OP-LOOM-1)
# ------------------------------------------------------------------------------------------------------------
def _surface(state: LoomState, cell: Optional[str]) -> Optional[str]:
    if cell is None or fd.is_constructed(cell):
        return cell
    u = state.units[cell]
    return u.surface if u.kind == RECORD else CONSTRUCTED_PREFIX + u.uid


def geometry_cross(state: LoomState, cross: LoomCross) -> geo.Cross:
    return geo.Cross.make(L=cross.L, center=_surface(state, cross.centre), arms=[[_surface(state, c) for c in a] for a in cross.arms])


def _seat_name(seat: geo.Seat) -> str:
    return CENTRE if seat == geo.CENTER else fmt_seat(seat.arm, seat.k)


def loom_key(T, A, g: geo.Cross, w, topic: bool) -> Tuple[int, int, int]:
    """OP-LOOM-4 (L-LOOM-5x): the loom's key (n, p, a) of a seated cross.  (n, p) and the arm part of `a` are placement.seated_key's;
    the centre word's は adhesion (numerator(は) * adj(centre, は)) is counted in `a` ONLY when the model marked the cross as topic.
    Not a change of foundation.a_num or placement.seated_key (G1-b placement bytes): the unmarked variant is a_num over the same flat
    with the centre cell blanked, which drops exactly the centre term and nothing else."""
    n, p, a = pl.seated_key(T, A, g, w)
    if topic:
        return (n, p, a)
    flat = list(pl.from_cross(g))
    flat[0] = None
    return (n, p, fd.a_num(A, tuple(flat), g.L))


def _cmp_key(key: Tuple[int, int, int], mode: str) -> Tuple[int, ...]:
    return key[:2] if mode == "strict_np" else key


def stability_of(run, cross: LoomCross, mode: str) -> dict:
    """The stability entry of one prose cross: key (n, p, a), status, every improving swap [seat_a, seat_b, key_after] in
    geometry.moves_swap order (a list, not a winner), and the best of them."""
    corpus, state = run.corpus, run.state
    entry = {"cid": cross.cid, "tier": cross.tier}
    if cross.lang != PROSE:
        entry.update(status="not_applicable", key=None, improving=[])
        return entry
    if cross.centre is None:
        entry.update(status="not_evaluated", key=None, improving=[], reason="empty_centre")
        return entry
    T, A, w = corpus.tier(cross.tier), corpus.adhesion[cross.tier], corpus.weights(cross.tier)
    gc = geometry_cross(state, cross)
    base = loom_key(T, A, gc, w, cross.topic)
    improving: List[list] = []
    tested = 0
    all_zero = True
    for p, q in geo.moves_swap(gc.L):
        vp, vq = gc.get(p), gc.get(q)
        if fd.is_constructed(vp if vp is None else str(vp)) or fd.is_constructed(vq if vq is None else str(vq)):
            continue                                   # OP-G1-4: a swap that touches a foundation seat is not a move
        if vp == vq:
            continue                                   # a no-op
        g2 = geo.swap(gc, p, q)
        if g2.center is None:
            continue                                   # L-77: not a state
        k2 = loom_key(T, A, g2, w, cross.topic)
        tested += 1
        if k2 != (0, 0, 0):
            all_zero = False
        if _cmp_key(k2, mode) > _cmp_key(base, mode):
            improving.append([_seat_name(p), _seat_name(q), list(k2)])
    if improving:
        status = "unstable"
    elif tested == 0 or (base == (0, 0, 0) and all_zero):
        status = "trivially_stable"                    # L-LOOM-19 (+ L-LOOM-26: nothing can move)
    else:
        status = "stable"
    entry.update(status=status, key=list(base), improving=improving, moves_tested=tested)
    if improving:
        best = max(_cmp_key(tuple(i[2]), mode) for i in improving)
        entry["best_key"] = [i[2] for i in improving if _cmp_key(tuple(i[2]), mode) == best][0]
        entry["best_swaps"] = [[i[0], i[1]] for i in improving if _cmp_key(tuple(i[2]), mode) == best]
    return entry


# ------------------------------------------------------------------------------------------------------------
# the gate
# ------------------------------------------------------------------------------------------------------------
# L-LOOM-146.  What `unstable_cross` says about a cross that quotes a corpus sentence (made by `weave_span.v2`, unchanged since): no swap is listed.
SPAN_UNSTABLE_ADVICE = ("this stretch is faithful to sentence %d but unstable under the key; a swap would change the quoted text, so none is offered: "
                        "choose another stretch, or abstain")

def _has_content(c: LoomCross) -> bool:
    return bool(c.uids())


def _leg_gaps(cross: LoomCross) -> List[dict]:
    out = []
    for ax in AXES:
        arm = cross.arms[AXES.index(ax)]
        ks = [k for k in range(0, cross.inner_k + 1) if arm[k] is not None]
        if ks and (max(ks) != cross.inner_k or ks != list(range(min(ks), cross.inner_k + 1))):
            out.append({"type": "leg_gap", "cid": cross.cid, "arm": ax, "seats": [fmt_seat(ax, k) for k in ks]})
    return out


def evaluate(run) -> dict:
    """Every check of design 3.7, returning EVERY refusal found (L-LOOM-06: fixed order, then thread position) together with the
    read-out.  `read` returns this as a dry run; `emit` closes the run when `refusals` is empty."""
    state = run.state
    mode = run.stability_mode
    linked = [state.crosses[cid] for cid in state.thread]
    refusals: List[Tuple[int, int, dict]] = []

    def add(r: dict, pos: int = 0) -> None:
        refusals.append((REFUSAL_ORDER.index(r["type"]), pos, r))

    if not any(_has_content(c) or c.topic for c in linked):
        add({"type": "empty_thread"})
    for cid, c in state.crosses.items():
        if not c.linked and _has_content(c):
            add({"type": "unlinked_cross", "cid": cid}, int(cid[1:]))
    for pos, c in enumerate(linked):
        if c.centre is None and (_has_content(c) or (c.lang == PROSE and c.topic)):
            add({"type": "empty_centre", "cid": c.cid}, pos)
        for g in _leg_gaps(c):
            add(g, pos)
    tiers = {c.cid: c.tier for c in linked if _has_content(c)}
    if len(set(tiers.values())) > 1:
        add({"type": "tier_mix", "tiers": dict(sorted(tiers.items(), key=lambda kv: int(kv[0][1:])))})
    if run.mode == "record_only":
        for pos, c in enumerate(linked):
            for uid in c.uids():
                if state.units[uid].kind == CONSTRUCTED:
                    add({"type": "constructed_forbidden", "cid": c.cid, "uid": uid}, pos)

    evidence: List[dict] = []
    if run.evidence is not None:                       # LOOM-evidence (L-LOOM-184): after constructed_forbidden, before unstable_cross; prose only (the profile is for prose runs)
        from verantyx.loom import evidence as evl
        g = evl.gate(run)
        evidence = g["evidence"]
        if g["refusal"] is not None:
            add(g["refusal"])

    stab: List[dict] = []
    for pos, c in enumerate(linked):
        if not _has_content(c) and not c.topic:
            continue
        e = stability_of(run, c, mode)
        if e["status"] == "unstable" and c.span is not None:
            # L-LOOM-146: a cross `weave_span.v2` made and nobody changed quotes sentence `c.span` word for word; EVERY improving swap would change the quoted
            # text, so none is offered.  The status stays "unstable" (the key is the key); only the advice differs.
            e = dict(e, improving=[], best_swaps=[], improving_n=len(e["improving"]), span={"sid": c.span, "faithful": True})
        stab.append(e)
        if e["status"] == "unstable" and mode != "report":
            r = {"type": "unstable_cross", "cid": c.cid, "key": e["key"], "improving": e["improving"],
                 "best_key": e["best_key"], "best_swaps": e["best_swaps"], "mode": mode}
            if c.span is not None:
                r["span"] = e["span"]
                r["advice"] = SPAN_UNSTABLE_ADVICE % c.span
            add(r, pos)

    segs: List[dict] = []
    code_lang = any(c.lang == CODE for c in linked)
    line_cids: List[str] = []                          # code: the cross that printed line i + 1 (a cross with no unit prints nothing)
    for pos, c in enumerate(linked):
        if c.lang == PROSE:
            segs.extend(read_prose(state, c))
        else:
            cs, ok = read_code(state, c)
            segs.extend(cs)
            if cs:
                line_cids.append(c.cid)
            if not ok:
                add({"type": "layout_changed_tokens", "cid": c.cid}, pos)
    text = "".join(s["s"] for s in segs)
    if code_lang:
        pe = codelib.parse_gate(text)
        if pe is not None:
            add(dict(pe, type="parse_error"))
        else:
            for r in codelib.gate_refusals(text, run.code_index, run.context_names(), line_cids):
                add(r, state.thread.index(r["cid"]) if "cid" in r else 0)
    annotate(run, segs)
    refusals.sort(key=lambda t: (t[0], t[1]))
    shares = {k: 0 for k in KINDS}
    for s in segs:
        shares[s["kind"]] += len(s["s"])
    return {"text": text, "annotated": segs, "refusals": [r for _, _, r in refusals], "stability": stab, "shares": shares,
            "output_sha": hashlib.sha256(text.encode("utf-8")).hexdigest(), "evidence": evidence}
