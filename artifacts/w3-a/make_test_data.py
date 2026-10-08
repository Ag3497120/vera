"""Build the frozen test data from the hand-written spec files (W3-a).

typed_vocab_spec.txt  -> tests/coarse_place/data/typed_vocab.jsonl
dev_vocab_spec.txt    -> tests/coarse_place/data/dev_vocab.jsonl
unknown_spec.txt      -> tests/coarse_place/data/unknown_words.jsonl
dev_unknown_spec.txt  -> tests/coarse_place/data/dev_unknown.jsonl
predicate_spec.txt    -> tests/coarse_place/data/predicate_check.jsonl

The gold (the types) is hand-written in the spec files.  This script only
(1) parses, (2) checks the boundary shape (known type ids, no duplicates,
dev and test disjoint), and (3) fills in the context_role / context_predicate
of the unknown words mechanically with the same rule the measurement uses
(the particle right after the word; the first verb after it).
"""
import json
import os
import re
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402

A = os.path.join(W, "artifacts/w3-a")
D = os.path.join(W, "tests/coarse_place/data")
os.makedirs(D, exist_ok=True)
SEEDS = {w for v in ct.SEEDS_NOUN.values() for w in v}
ROLES = set(ct.ROLE_PARTICLES)


def parse_vocab(path):
    out, cat, gold = [], None, None
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#") and not line.startswith("##"):
            continue
        if line.startswith("##"):
            cat = line[2:].strip()
            continue
        if line.startswith("@"):
            gold = [g.strip() for g in line[1:].split(",") if g.strip()]
            for g in gold:
                assert g in ct.NOUN_TYPES, (path, g)
            continue
        for tok in line.split():
            if tok.endswith("?"):
                continue
            m = re.match(r"^([^()]+)(?:\((.*)\))?$", tok)
            assert m, tok
            term, note = m.group(1), m.group(2)
            trap_unit = trap_sug = None
            if note and ">" in note.split(";")[0]:
                head, _, rest = note.partition(";")
                trap_unit, _, trap_sug = head.partition(">")
                assert trap_sug in ct.NOUN_TYPES, (tok, trap_sug)
                note = rest
            out.append({"term": term, "gold": list(gold), "section": cat,
                        "trap_unit": trap_unit, "trap_suggests": trap_sug,
                        "note": note})
    return out


def to_category(e):
    sec = e["section"]
    if sec == "trap":
        return "polysemous" if len(e["gold"]) > 1 else "daily"
    return sec


def write_vocab(entries, path, prefix):
    seen = set()
    rows = []
    for e in entries:
        if e["term"] in seen:
            raise SystemExit("duplicate term %s" % e["term"])
        seen.add(e["term"])
    for i, e in enumerate(entries, 1):
        trap = e["trap_unit"] is not None
        row = {"id": "%s%04d" % (prefix, i), "term": e["term"],
               "gold": e["gold"], "category": to_category(e),
               "suffix_trap": trap}
        if trap:
            row["trap_unit"] = e["trap_unit"]
            row["trap_suggests"] = e["trap_suggests"]
        if e["note"]:
            row["note"] = e["note"]
        rows.append(row)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def context_of(tagger, sentence, term):
    """The particle right after `term` (if one of the 12) and the first verb
    after it, by the same rule the measurement script uses."""
    toks = list(tagger(sentence))
    i = 0
    surf = ""
    # find the token span that spells the term
    for start in range(len(toks)):
        acc = ""
        for end in range(start, len(toks)):
            acc += toks[end].surface
            if acc == term:
                nx = toks[end + 1] if end + 1 < len(toks) else None
                role = None
                if (nx is not None and nx.feature.pos1 == "助詞"
                        and nx.surface in ROLES):
                    role = nx.surface
                pred = None
                for v in toks[end + 1:]:
                    if v.feature.pos1 == "動詞":
                        pred = v.feature.orthBase or v.surface
                        break
                return role, pred
            if not term.startswith(acc):
                break
    return None, None


def write_unknown(spec, path, prefix):
    import fugashi
    tagger = fugashi.Tagger()
    rows, seen = [], set()
    kinds = {"coinage", "neologism", "compound", "proper"}
    cur = None
    for raw in open(spec, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip() or line.startswith("#") and not line.startswith("##"):
            continue
        if line.startswith("##"):
            cur = line[2:].strip()
            continue
        term, kind, gold, sent, why = line.split("|")
        assert kind in kinds, line
        assert term in sent, line
        assert term not in seen, term
        seen.add(term)
        g = [] if gold == "-" else gold.split(",")
        for x in g:
            assert x in ct.NOUN_TYPES, line
        role, pred = context_of(tagger, sent, term)
        rows.append({"term": term, "kind": kind,
                     "context_sentence": sent, "context_role": role,
                     "context_predicate": pred, "gold": g,
                     "gold_unknown": not g, "why": why})
    for i, r in enumerate(rows, 1):
        r["id"] = "%s%03d" % (prefix, i)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            order = ["id", "term", "kind", "context_sentence", "context_role",
                     "context_predicate", "gold", "gold_unknown", "why"]
            f.write(json.dumps({k: r[k] for k in order},
                               ensure_ascii=False) + "\n")
    return rows


def write_pred(spec, path):
    rows = []
    for raw in open(spec, encoding="utf-8"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        term, gold, note = line.split("|")
        assert gold in ct.PRED_TYPES, line
        if "サ変のため参考" in note:
            continue
        rows.append({"term": term, "gold": [gold], "note": note})
    seen = set()
    out = []
    for r in rows:
        if r["term"] in seen:
            continue
        seen.add(r["term"])
        out.append(r)
    seeds_p = {w for v in ct.SEEDS_PRED.values() for w in v}
    for i, r in enumerate(out, 1):
        r["id"] = "P%03d" % i
        r["seed_overlap"] = r["term"] in seeds_p
    with open(path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps({k: r[k] for k in ("id", "term", "gold", "note",
                                                  "seed_overlap")},
                               ensure_ascii=False) + "\n")
    return out


def main():
    typed = parse_vocab(os.path.join(A, "typed_vocab_spec.txt"))
    dev = parse_vocab(os.path.join(A, "dev_vocab_spec.txt"))
    tset = {e["term"] for e in typed}
    dropped = [e["term"] for e in dev if e["term"] in tset]
    dev = [e for e in dev if e["term"] not in tset]
    t_rows = write_vocab(typed, os.path.join(D, "typed_vocab.jsonl"), "V")
    d_rows = write_vocab(dev, os.path.join(D, "dev_vocab.jsonl"), "D")
    u = write_unknown(os.path.join(A, "unknown_spec.txt"),
                      os.path.join(D, "unknown_words.jsonl"), "U")
    du = write_unknown(os.path.join(A, "dev_unknown_spec.txt"),
                       os.path.join(D, "dev_unknown.jsonl"), "DU")
    uset = {r["term"] for r in u}
    assert not (uset & {r["term"] for r in du}), "unknown/dev_unknown overlap"
    p = write_pred(os.path.join(A, "predicate_spec.txt"),
                   os.path.join(D, "predicate_check.jsonl"))
    from collections import Counter
    print("typed", len(t_rows), Counter(r["category"] for r in t_rows))
    print("trap", sum(r["suffix_trap"] for r in t_rows))
    print("types", sorted(Counter(g for r in t_rows for g in r["gold"]).items()))
    print("multi-gold", sum(len(r["gold"]) > 1 for r in t_rows))
    print("dev", len(d_rows), "dropped dev dupes", dropped)
    print("seed overlap typed",
          sorted(r["term"] for r in t_rows if r["term"] in SEEDS))
    print("unknown", len(u), "typed", sum(not r["gold_unknown"] for r in u),
          "unk", sum(r["gold_unknown"] for r in u))
    print("dev_unknown", len(du), "unk", sum(r["gold_unknown"] for r in du))
    print("pred", len(p), "non-seed", sum(not r["seed_overlap"] for r in p))
    print("ctx roles", Counter(r["context_role"] for r in u))
    print("ctx preds", Counter(r["context_predicate"] for r in u).most_common(14))


if __name__ == "__main__":
    main()
