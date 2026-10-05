"""r3 (12.21.7; hand-written): the candidate pool and, after it, the data files synthetic_r3.jsonl / confirmations_truth_r3.jsonl.

  python make_synthetic_r3.py pool  --placement P --out DIR     tries every candidate on the base (no layer), and for frame_reach also with `set` alone and `set`+`frame`; writes candidate_pool_r3.tsv
  python make_synthetic_r3.py write                             writes the data files from ADOPTED (the ids the pool run adopted by the rule registered in docs 12.21.7)

Adoption rule (registered before the exploration): frame_kept = abstains on the base with a 12.10 frame reason; frame_reach = abstains on the base, abstains with `set` alone,
and is read with `set`+`frame`; control = does not contain a confirmed word or its stem.  Nothing is changed after the freeze.
"""
import json, os, sys

D = os.path.dirname(os.path.abspath(__file__))


def clause(pred, agent, goal):
    return [{"predicate": pred, "roles": {"agent": agent, "goal": goal}, "polarity": "+", "tense": "past", "voice": "active"}]


# (id, group, text, expect, predicate dictionary form)
KEPT = [("k01", "田中が駅へ移動した。", "移動する"), ("k02", "鈴木が倉庫へ移動した。", "移動する"), ("k03", "山田が病院へ移動した。", "移動する"),
        ("k04", "田中が空港へ出発した。", "出発する"), ("k05", "鈴木が駅へ出発した。", "出発する"), ("k06", "山田が倉庫へ出発した。", "出発する"),
        ("k07", "田中が机を移した。", "移す"), ("k08", "鈴木が荷物を移した。", "移す"), ("k09", "田中が駅に通った。", "通う"), ("k10", "鈴木が病院に通った。", "通う"),
        ("k11", "田中が倉庫へ引っ越した。", "引っ越す"), ("k12", "山田が駅へ引っ越した。", "引っ越す"),
        # run 2 (after run 1: only 移動する and 避難する have a CONFIRMED 12.10 frame that refuses が on the base)
        ("k13", "太郎が病院へ移動した。", "移動する"), ("k14", "田中が空港へ移動した。", "移動する"), ("k15", "田中が駅へ避難した。", "避難する"),
        ("k16", "鈴木が倉庫へ避難した。", "避難する"), ("k17", "太郎が病院へ避難した。", "避難する"), ("k18", "鈴木が空港へ避難した。", "避難する")]
REACH = [("r01", "田中", "学校", "出向く"), ("r02", "鈴木", "会社", "出向く"), ("r03", "山田", "学校", "出向く"), ("r04", "太郎", "会社", "転勤する"), ("r05", "田中", "学校", "転勤する"),
         ("r06", "鈴木", "会社", "出張する"), ("r07", "山田", "会社", "出張する"), ("r08", "太郎", "学校", "赴く")]
CONTROL = ["田中が本を読んだ。", "鈴木が手紙を書いた。", "太郎が走った。", "整備士が倉庫で点検した。", "山田が学校で勉強した。", "鈴木が机を拭いた。"]
INFL = {"出向く": "出向いた", "転勤する": "転勤した", "出張する": "出張した", "赴く": "赴いた"}
# the ids adopted by the rule (filled in after the pool run; see candidate_pool_r3.tsv)
ADOPTED_KEPT = ["k01", "k02", "k13", "k14", "k15", "k16", "k17", "k18"]
ADOPTED_REACH = ["r01", "r02", "r04", "r05", "r08"]
ADOPTED_CONTROL = ["c01", "c02", "c03", "c04", "c05", "c06"]


def reach_text(a, g, p):
    return "%sが%sへ%s。" % (a, g, INFL[p])


def pool(placement, out):
    import contextlib, io, tempfile
    from verantyx import cli, semantic_read as SR
    os.makedirs(out, exist_ok=True)

    def run(argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main(argv)
        return rc, buf.getvalue()

    def read(text, layer=None):
        old = os.environ.get("VERA_PLACEMENT_LAYER")
        try:
            if layer:
                os.environ["VERA_PLACEMENT_LAYER"] = layer
            else:
                os.environ.pop("VERA_PLACEMENT_LAYER", None)
            return SR.read(text, placement=placement)
        finally:
            if old is None:
                os.environ.pop("VERA_PLACEMENT_LAYER", None)
            else:
                os.environ["VERA_PLACEMENT_LAYER"] = old

    def cfm(layer, ledger, *a):
        rc, o = run(["confirm"] + list(a) + ["--by", "pool", "--layer", layer, "--ledger-file", ledger, "--placement", placement])
        assert rc == 0, (a, o)

    def reasons(rd):
        return "+".join((rd.get("abstain") or {}).get("reasons") or []) if not rd.get("readable") else "READ"
    rows = []
    for cid, text, pred in KEPT:
        layer, ledger = os.path.join(out, "pool_k_%s.sqlite" % cid), os.path.join(out, "pool_k_%s.jsonl" % cid)
        for p in (layer, ledger):
            assert not os.path.exists(p), p
        base = read(text)
        cfm(layer, ledger, "set", pred, "P_MOVE")
        s = read(text, layer)
        rows.append(("frame_kept", cid, text, pred, reasons(base), reasons(s), ""))
    for cid, a, g, pred in REACH:
        text = reach_text(a, g, pred)
        layer, ledger = os.path.join(out, "pool_r_%s.sqlite" % cid), os.path.join(out, "pool_r_%s.jsonl" % cid)
        for p in (layer, ledger):
            assert not os.path.exists(p), p
        base = read(text)
        cfm(layer, ledger, "set", pred, "P_MOVE")
        s1 = read(text, layer)
        cfm(layer, ledger, "frame", pred, "へ", "goal", "GROUP_ORG")
        s2 = read(text, layer)
        rows.append(("frame_reach", cid, text, pred, reasons(base), reasons(s1), reasons(s2)))
    for i, text in enumerate(CONTROL, 1):
        rows.append(("control", "c%02d" % i, text, "", reasons(read(text)), "", ""))
    with open(os.path.join(out, "candidate_pool_r3.tsv"), "w", encoding="utf-8") as f:
        f.write("group\tid\ttext\tpredicate\tbase\tafter_set\tafter_set_and_frame\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
        f.write("# candidates=%d (frame_kept %d, frame_reach %d, control %d)\n" % (len(rows), len(KEPT), len(REACH), len(CONTROL)))


def write():
    rows, truth = [], []
    for cid, text, pred in KEPT:
        if cid in ADOPTED_KEPT:
            rows.append({"id": cid, "text": text, "expect": "ABSTAIN", "group": "frame_kept"})
    for p in sorted({pred for cid, _t, pred in KEPT if cid in ADOPTED_KEPT}):
        truth.append({"op": "set", "word": p, "type": "P_MOVE", "reason": "the base's own type (frame_kept: a human type alone must not drop the base's frame)"})
    for cid, a, g, pred in REACH:
        if cid in ADOPTED_REACH:
            rows.append({"id": cid, "text": reach_text(a, g, pred), "expect": clause(pred, a, g), "group": "frame_reach"})
    for p in sorted({pred for cid, _a, _g, pred in REACH if cid in ADOPTED_REACH}):
        truth.append({"op": "set", "word": p, "type": "P_MOVE", "reason": "frame_reach: the base has no confirmed type frame"})
        truth.append({"op": "frame", "predicate": p, "particle": "へ", "role": "goal", "types": ["GROUP_ORG"], "reason": "goal may be an organisation (学校・会社)"})
    for i, text in enumerate(CONTROL, 1):
        if "c%02d" % i in ADOPTED_CONTROL:
            rows.append({"id": "c%02d" % i, "text": text, "expect": None, "group": "control"})
    with open(os.path.join(D, "synthetic_r3.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(D, "confirmations_truth_r3.jsonl"), "w", encoding="utf-8") as f:
        for t in truth:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "pool":
        a = dict(zip(sys.argv[2::2], sys.argv[3::2]))
        pool(a["--placement"], a["--out"])
    else:
        write()
