"""PREREGISTERED_2026-09-27_typed_edges — P2, P3 and the P1 sample.

    python3.11 tools/measure_typed_edges.py human   # jawiki+aozora lines
    python3.11 tools/measure_typed_edges.py codex FILE...   # sentences.jsonl
    python3.11 tools/measure_typed_edges.py report

Human side: only lines holding an item's subject AND one of its axis tokens
are extracted. `ask_property` can only return a hit for an edge whose word
contains an axis token about that subject, so this prefilter gives the same
verdicts as extracting all 61M lines — it saves time, it changes nothing.
Independence unit: 40-line blocks (the size of one Codex batch).
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verantyx.typed_edges import ask_property, build, extract  # noqa: E402

ROOT = Path(__file__).resolve().parent
BANK = json.loads((ROOT / "commonsense_bank_2026-08-14.json").read_text())["items"]
HELDOUT = json.loads((ROOT / "commonsense_heldout_2026-09-27.json").read_text())["items"]
NO_BANK = json.loads((ROOT / "commonsense_no_bank_2026-09-27.json").read_text())["items"]
OUT = Path.home() / "Projects" / "vera-corpus" / "build"
HUMAN_DB, CODEX_DB = OUT / "typed_human.db", OUT / "typed_codex.db"
SENT = (Path.home() / "Downloads" / "vera-cleanroom-transfer-20260926" /
        "vera-engine" / "corpora-large" / "sentences")


def _scan(path: str):
    keep = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for n, line in enumerate(f):
            s = line.strip()
            for it in BANK:
                if it["subject"] in s and any(a in s for a in it["axis_tokens"]):
                    keep.append((hashlib.sha1(s.encode()).hexdigest(), s,
                                 "human:%s:%d" % (Path(path).stem, n // 40)))
                    break
    return keep


INHERIT = json.loads((ROOT / "inheritance_heldout_2026-09-27.json").read_text())["items"]
ALL_ITEMS = BANK + NO_BANK + HELDOUT + INHERIT


def _all_axes(axis):
    from verantyx.typed_edges import _opposite
    return list(axis) + _opposite(axis)


def _scan_isa(args):
    path, subjects = args
    keep = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for n, line in enumerate(f):
            if "\t" in line:
                continue            # tokenized duplicate of a real line
            s = line.strip()
            k = s.find("は")
            if 0 < k <= 8 and s[:k] in subjects:
                keep.append((hashlib.sha1(s.encode()).hexdigest(), s,
                             "human:%s:%d" % (Path(path).stem, n // 40)))
    return keep


def _scan_terms(args):
    path, pairs = args
    keep = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for n, line in enumerate(f):
            if "\t" in line:
                continue
            s = line.strip()
            for term, axes in pairs:
                if term in s and any(a in s for a in axes):
                    keep.append((hashlib.sha1(s.encode()).hexdigest(), s,
                                 "human:%s:%d" % (Path(path).stem, n // 40)))
                    break
    return keep


def human2() -> None:
    """v5: no tab duplicates, opposite poles kept, hypernym lines included."""
    from verantyx.typed_edges import isa as _isa
    files = sorted(str(p) for p in SENT.glob("*.txt"))
    subjects = {it["subject"] for it in ALL_ITEMS}
    rows = []
    with ProcessPoolExecutor(8) as ex:
        for part in ex.map(_scan_isa, [(f, subjects) for f in files]):
            rows.extend(part)
    from collections import defaultdict
    ups = defaultdict(set)
    for _sha, text, src in rows:
        for x, y in _isa(text):
            ups[(x, y)].add(src)
    hyper = {x: {y for (x2, y), ss in ups.items() if x2 == x and len(ss) >= 2}
             for x in subjects}
    axes_of = defaultdict(set)
    for it in ALL_ITEMS:
        ax = _all_axes(it["axis_tokens"])
        axes_of[it["subject"]].update(ax)
        for y in hyper.get(it["subject"], ()):
            axes_of[y].update(ax)
    pairs = [(t, sorted(a)) for t, a in axes_of.items()]
    with ProcessPoolExecutor(8) as ex:
        for part in ex.map(_scan_terms, [(f, pairs) for f in files]):
            rows.extend(part)
    print(json.dumps({"isa_lines_and_term_lines": len(rows),
                      "hypernyms": {x: sorted(v)[:6] for x, v in hyper.items() if v},
                      **build(HUMAN_DB, rows)}, ensure_ascii=False))


def inherit_report() -> None:
    from verantyx.typed_edges import ask_inherit, ask_property
    rep = {}
    for name, db in (("human", HUMAN_DB), ("codex", CODEX_DB)):
        for mode in ("own", "inherit"):
            t = {"yes_correct": 0, "yes_refused": 0, "yes_wrong": 0,
                 "no_correct": 0, "no_refused": 0, "no_wrong": 0}
            rows = []
            for it in INHERIT:
                r = (ask_inherit(db, HUMAN_DB, it["subject"], it["axis_tokens"])
                     if mode == "inherit" else
                     ask_property(db, it["subject"], it["axis_tokens"]))
                v = r["verdict"]
                yes = v in ("ATTESTED", "INHERITED_YES")
                no = v in ("NEGATIVE_ATTESTED", "INHERITED_NO")
                e = it["expected"]
                k = e + ("_correct" if (yes and e == "yes") or (no and e == "no")
                         else "_wrong" if yes or no else "_refused")
                t[k] += 1
                rows.append((it["question"], it["kind"], e, v, r.get("via") or r.get("inherit")))
            rep["%s/%s" % (name, mode)] = {"tally": t, "rows": rows}
    print(json.dumps(rep, ensure_ascii=False, indent=1, default=str))
    files = sorted(str(p) for p in SENT.glob("*.txt"))
    rows = []
    with ProcessPoolExecutor(8) as ex:
        for part in ex.map(_scan, files):
            rows.extend(part)
    print(json.dumps({"prefiltered_lines": len(rows),
                      **build(HUMAN_DB, rows)}, ensure_ascii=False))


def codex(files) -> None:
    rows = []
    for fp in files:
        for line in open(fp, encoding="utf-8"):
            r = json.loads(line)
            rows.append((hashlib.sha1(r["text"].encode()).hexdigest(),
                         r["text"], r["source"]))
    print(json.dumps(build(CODEX_DB, rows), ensure_ascii=False))


def bank_on(db: Path):
    out = {"ANSWERED_CORRECT": 0, "TYPED_REFUSAL": 0, "WRONG": 0}
    rows = []
    for it in BANK:
        r = ask_property(db, it["subject"], it["axis_tokens"])
        # Bank is all expected=yes: ATTESTED is correct; a negative verdict
        # asserts the opposite and is WRONG; CONFLICT / NOT_ATTESTED refuse.
        if r["verdict"] == "ATTESTED":
            k = "ANSWERED_CORRECT"
        elif r["verdict"] == "NEGATIVE_ATTESTED":
            k = "WRONG"
        else:
            k = "TYPED_REFUSAL"
        out[k] += 1
        rows.append({"q": it["question"], "outcome": k, **r})
    return out, rows


def report() -> None:
    import sqlite3

    rep = {}
    for name, db in (("human", HUMAN_DB), ("codex", CODEX_DB)):
        if not db.exists():
            continue
        con = sqlite3.connect(str(db))
        n, hit = con.execute("SELECT count(*), sum(n_edges>0) FROM tsent").fetchone()
        con.close()
        tally, rows = bank_on(db)
        no = {"CORRECT_NO": 0, "TYPED_REFUSAL": 0, "WRONG_YES": 0}
        no_rows = []
        for it in NO_BANK:
            r = ask_property(db, it["subject"], it["axis_tokens"])
            k = ("WRONG_YES" if r["verdict"] == "ATTESTED" else
                 "CORRECT_NO" if r["verdict"] == "NEGATIVE_ATTESTED" else "TYPED_REFUSAL")
            no[k] += 1
            no_rows.append((it["question"], k, r["pos_sources"], r["neg_sources"],
                            [e["text"][:40] for e in r["evidence"][:2]]))
        rep.setdefault("_no", {})[name] = no_rows
        ho = {"yes_correct": 0, "yes_refused": 0, "yes_wrong": 0,
              "no_correct": 0, "no_refused": 0, "no_wrong": 0}
        ho_rows = []
        for it in HELDOUT:
            r = ask_property(db, it["subject"], it["axis_tokens"])
            v = r["verdict"]
            e = it["expected"]
            if v == "ATTESTED":
                k = e + ("_correct" if e == "yes" else "_wrong")
            elif v == "NEGATIVE_ATTESTED":
                k = e + ("_correct" if e == "no" else "_wrong")
            else:
                k = e + "_refused"
            ho[k] += 1
            ho_rows.append((it["question"], e, v, r["pos_sources"], r["neg_sources"]))
        rep.setdefault("_heldout", {})[name] = ho_rows
        rep[name] = {"sentences": n, "with_edge": hit, "no_bank": no, "heldout": ho,
                     "coverage": round(hit / max(n, 1), 3), "bank": tally,
                     "per_item": [(r["q"], r["outcome"], r["pos_sources"],
                                   r["neg_sources"]) for r in rows]}
        (OUT / ("typed_bank_%s.json" % name)).write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


def p1_sample(db: Path, dest: Path, n: int = 100, seed: int = 20260927) -> None:
    """P1: 100 random sentence->edge pairs for the person to mark."""
    import sqlite3

    con = sqlite3.connect(str(db))
    shas = [r[0] for r in con.execute(
        "SELECT sha FROM tsent WHERE n_edges>0 ORDER BY sha")]
    random.Random(seed).shuffle(shas)
    lines = ["# P1 判定用 — 文と、そこから取った辺（正しければ ○、誤りは × と理由）", ""]
    k = 0
    for sha in shas:
        text = con.execute("SELECT text FROM tsent WHERE sha=?", (sha,)).fetchone()[0]
        es = con.execute("SELECT head, rel, dep, pol FROM tedges WHERE sha=?",
                         (sha,)).fetchall()
        e = random.Random(seed + k).choice(es)
        k += 1
        arrow = "%s ─%s→ %s%s" % (e[0], e[1], e[2], "（否定）" if e[3] == "-" else "")
        lines.append("%d. %s\n   → %s　[ ]" % (k, text, arrow))
        if k >= n:
            break
    con.close()
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(dest)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "human":
        human()
    elif cmd == "codex":
        codex(sys.argv[2:])
    elif cmd == "human2":
        human2()
    elif cmd == "inherit":
        inherit_report()
    elif cmd == "report":
        report()
    elif cmd == "p1":
        p1_sample(CODEX_DB, Path(sys.argv[2]))
