"""PREREGISTERED_2026-09-27_verify_layer — build the bench and run it.

    python3.11 tools/bench_verify.py sentences-050
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verantyx.typed_edges import _tagger  # noqa: E402
from verantyx.verify import compile_docs, verify  # noqa: E402

SENT = (Path.home() / "Downloads" / "vera-cleanroom-transfer-20260926" /
        "vera-engine" / "corpora-large" / "sentences")

_A = {"う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た", "ぬ": "な",
      "ぶ": "ば", "む": "ま", "る": "ら"}
PAIRS = [("熱い", "冷たい"), ("暑い", "寒い"), ("厚い", "薄い"), ("重い", "軽い"),
         ("硬い", "柔らかい"), ("明るい", "暗い"), ("白い", "黒い"), ("甘い", "苦い")]
OPP = {a: b for a, b in PAIRS} | {b: a for a, b in PAIRS}


def negate(verb: str) -> str | None:
    if verb.endswith("する"):
        return verb[:-2] + "しない"
    if verb in ("来る", "くる"):
        return verb[:-1] + "ない" if verb == "来る" else "こない"
    toks = list(_tagger()(verb))
    if not toks:
        return None
    ctype = str(toks[-1].feature.cType)
    if "一段" in ctype and verb.endswith("る"):
        return verb[:-1] + "ない"
    if "五段" in ctype and verb[-1] in _A:
        return verb[:-1] + _A[verb[-1]] + "ない"
    return None


def load_docs(name: str, n: int = 3000) -> list:
    out = []
    for line in open(SENT / (name + ".txt"), encoding="utf-8", errors="ignore"):
        if "\t" in line or not line.strip():
            continue
        out.append(line.strip())
        if len(out) >= n:
            break
    return out


def build_bench(store: Path, docs: list) -> dict:
    con = sqlite3.connect(str(store))
    rows = con.execute(
        "SELECT sha, ev, rel, dep, head FROM tedges WHERE pol='+' AND mod='assert' "
        "AND rel IN ('が','を','に','で') ORDER BY sha, ev").fetchall()
    events = {}
    for sha, ev, rel, dep, head in rows:
        events.setdefault((sha, ev, head), {})[rel] = dep
    evs = [(k, r) for k, r in events.items() if "が" in r and len(r) >= 2
           and all(len(v) >= 1 for v in r.values())][:200]
    ga_pool = [r["が"] for _, r in evs]
    items = []
    for i, ((sha, ev, verb), r) in enumerate(evs):
        other = next(c for c in ("を", "に", "で") if c in r)
        a, b = r["が"], r[other]
        items.append({"kind": "T", "text": f"{a}が{b}{other}{verb}。"})
        items.append({"kind": "F1", "text": f"{b}が{a}{other}{verb}。"})
        nv = negate(verb)
        if nv:
            items.append({"kind": "F2", "text": f"{a}が{b}{other}{nv}。"})
        sub = next((g for g in ga_pool[i + 1:] + ga_pool[:i] if g != a), None)
        if sub:
            items.append({"kind": "F3", "text": f"{sub}が{b}{other}{verb}。"})
    attrs = con.execute(
        "SELECT DISTINCT head, dep FROM tedges WHERE rel='属性' AND pol='+' AND mod='assert'"
    ).fetchall()
    n4 = 0
    for head, dep in attrs:
        if dep in OPP and n4 < 100:
            items.append({"kind": "T4", "text": f"{head}は{dep}。"})
            items.append({"kind": "F4", "text": f"{head}は{OPP[dep]}。"})
            n4 += 1
    con.close()
    return {"items": items}


def presence(doc_text: str, claim: str) -> str:
    toks = [t for t in _tagger()(claim) if t.feature.pos1 in ("名詞", "動詞", "形容詞")]
    ok = all((t.feature.orthBase or t.surface) in doc_text or t.surface in doc_text
             for t in toks)
    return "SUPPORTED" if ok and toks else "UNSUPPORTED"


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "sentences-050"
    docs = load_docs(name)
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / (name + ".txt")
        f.write_text("\n".join(docs), encoding="utf-8")
        store = Path(d) / "store.db"
        comp = compile_docs([f], store)
        bench = build_bench(store, docs)
        doc_text = "\n".join(docs)
        res = {}
        pres = {}
        rows = []
        for it in bench["items"]:
            v = verify(store, it["text"])
            verdicts = [c["verdict"] for s in v["sentences"] for c in s["claims"]
                        if c["verdict"] != "NOT_ASSERTED"]
            # A claim text is judged by its worst claim.
            order = ["CONTRADICTED", "UNSUPPORTED", "NOT_IN_DOCS", "SUPPORTED"]
            worst = next((o for o in order if o in verdicts), "NO_CLAIM")
            res.setdefault(it["kind"], Counter())[worst] += 1
            pres.setdefault(it["kind"], Counter())[presence(doc_text, it["text"])] += 1
            rows.append({**it, "verdict": worst})
    out = {"docs": name, "compile": comp,
           "vera": {k: dict(c) for k, c in sorted(res.items())},
           "presence_baseline": {k: dict(c) for k, c in sorted(pres.items())}}
    for k, c in sorted(res.items()):
        n = sum(c.values())
        if k.startswith("T"):
            out.setdefault("lines", {})[k] = {
                "n": n, "supported": round(c["SUPPORTED"] / n, 3),
                "false_alarm_contradicted": round(c["CONTRADICTED"] / n, 3)}
        else:
            out.setdefault("lines", {})[k] = {
                "n": n, "missed_as_supported": round(c["SUPPORTED"] / n, 3),
                "contradicted": round(c["CONTRADICTED"] / n, 3)}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    Path(Path.home() / "Projects" / "vera-corpus" / "build" /
         ("bench_verify_%s.jsonl" % name)).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
