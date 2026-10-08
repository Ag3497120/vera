"""W3-a3: draw the verb samples and write the verb test data from the hand-written specs.

  make_verb_data.py sample   -> writes artifacts/w3-a3/dev_verbs_sample.txt, verb_check_sample.txt
                                (the drawn words only; the answers are written by hand in *_spec.txt)
  make_verb_data.py build    -> reads dev_verbs_spec.txt / verb_check_spec.txt and writes
                                tests/coarse_place/data/dev_verbs.jsonl, verb_check_300.jsonl,
                                artifacts/w3-a3/exclude_coined.jsonl

The drawing rule is registered in docs/COARSE_PLACEMENT.md section 12.11: the frame is the rows of
artifacts/w3-a/pred_verb_freq.tsv with class V, seed '-' and in_predicate_check '-'; dev =
random.Random(20261004).sample(frame, 130); check = random.Random(20261005).sample(frame minus dev, 260).
Spec line:  term|kind|gold (comma separated P_ ids, or - )|frame (JSON or - )|why
"""
import json
import os
import random
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
A = os.path.join(W, "artifacts/w3-a3")
D = os.path.join(W, "tests/coarse_place/data")
TSV = os.path.join(W, "artifacts/w3-a/pred_verb_freq.tsv")


def frame_words():
    rows = [l.rstrip("\n").split("\t") for l in open(TSV, encoding="utf-8")]
    hdr = rows[0]
    ix = {h: i for i, h in enumerate(hdr)}
    out = []
    for r in rows[1:]:
        if r[ix["class"]] == "V" and r[ix["seed"]] == "-" and r[ix["in_predicate_check"]] == "-":
            out.append(r[ix["word"]])
    return out


def draw():
    fr = frame_words()
    dev = random.Random(20261004).sample(fr, 130)
    rest = [w for w in fr if w not in set(dev)]
    chk = random.Random(20261005).sample(rest, 260)
    return fr, dev, chk


def cmd_sample():
    fr, dev, chk = draw()
    open(os.path.join(A, "dev_verbs_sample.txt"), "w", encoding="utf-8").write("\n".join(dev) + "\n")
    open(os.path.join(A, "verb_check_sample.txt"), "w", encoding="utf-8").write("\n".join(chk) + "\n")
    print(json.dumps({"frame": len(fr), "dev": len(dev), "check": len(chk)}))


def parse_frame(text, macros):
    """"が:PERSON,ANIMAL;に:PLACE" -> {"が": [...], "に": [...]}.  "@name" expands a macro
    defined in the spec header (a line "%name=が:...;...").  A JSON object is read as it is."""
    text = text.strip()
    if text == "-":
        return None
    if text.startswith("{"):
        return json.loads(text)
    if text.startswith("@"):
        text = macros[text[1:]]
    out = {}
    for part in text.split(";"):
        if not part.strip():
            continue
        p, ts = part.split(":", 1)
        out[p.strip()] = sorted(x.strip() for x in ts.split(",") if x.strip())
    return out


def read_spec(path, prefix):
    rows = []
    macros = {}
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("%"):
            k, v = line[1:].split("=", 1)
            macros[k.strip()] = v.strip()
            continue
        term, kind, gold, frame, why = line.split("|", 4)
        assert kind in ("typed", "unknown_fragment", "unknown_coined"), line
        g = [] if gold.strip() == "-" else [x.strip() for x in gold.split(",")]
        fr = parse_frame(frame, macros)
        rows.append({"term": term, "kind": kind, "gold": g, "gold_unknown": kind != "typed",
                     "frame": fr, "why": why})
    for i, r in enumerate(rows, 1):
        r["id"] = "%s%03d" % (prefix, i)
    return [{"id": r["id"], "term": r["term"], "kind": r["kind"], "gold": r["gold"],
             "gold_unknown": r["gold_unknown"], "frame": r["frame"], "why": r["why"]} for r in rows]


def check_spec(rows, sample, name):
    typed_or_frag = [r["term"] for r in rows if r["kind"] != "unknown_coined"]
    if sorted(typed_or_frag) != sorted(sample):
        print("SPEC_MISMATCH", name, set(typed_or_frag) ^ set(sample))
        sys.exit(2)
    for r in rows:
        if r["kind"] == "typed":
            assert r["gold"] and len(r["gold"]) <= 3, r
            if set(r["gold"]) & {"P_MOVE", "P_COMMUNICATE"}:
                assert r["frame"], ("frame needed", r)
        else:
            assert r["gold"] == [] and r["gold_unknown"], r


def cmd_build():
    fr, dev, chk = draw()
    dr = read_spec(os.path.join(A, "dev_verbs_spec.txt"), "DV")
    cr = read_spec(os.path.join(A, "verb_check_spec.txt"), "VC")
    check_spec(dr, dev, "dev")
    check_spec(cr, chk, "check")
    nd = sum(r["kind"] == "unknown_coined" for r in dr)
    nc = sum(r["kind"] == "unknown_coined" for r in cr)
    assert len(dr) == 130 + nd == 150 and nd == 20, (len(dr), nd)
    assert len(cr) == 300 and nc == 40, (len(cr), nc)
    for path, rows in ((os.path.join(D, "dev_verbs.jsonl"), dr), (os.path.join(D, "verb_check_300.jsonl"), cr)):
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    coined = sorted({r["term"] for r in dr + cr if r["kind"] == "unknown_coined"})
    with open(os.path.join(A, "exclude_coined.jsonl"), "w", encoding="utf-8") as f:
        for t in coined:
            f.write(json.dumps({"term": t}, ensure_ascii=False) + "\n")
    print(json.dumps({"dev": len(dr), "check": len(cr), "coined": len(coined)}))


if __name__ == "__main__":
    {"sample": cmd_sample, "build": cmd_build}[sys.argv[1]]()
