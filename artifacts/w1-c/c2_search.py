"""C2: run the pre-registered phrases (c2_phrases.json) through Corpus.search (public API, unchanged).

Per phrase: state, hit count (limit stated), the first hit's family/source_file/line/sha/origin and a
round trip back to the physical line of the source file (record sha equal, phrase contained in the
body the builder's own extract_body makes from that original record). For ticket phrases that return
no hit the same script computes, directly on the raw corpus files, whether the words occur at all.
Nothing here changes how the search works to make a phrase match.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, FAMS, HERE, IDX, dump, raw_lines_at  # noqa: E402
from tools import build_p4_corpus_index as bi  # noqa: E402
from verantyx.ability_corpus import Corpus  # noqa: E402

LIMIT = 1000


def run(corpus: Corpus, phrase: str, fam: str) -> dict:
    r = corpus.search(phrase, fam, limit=LIMIT)
    first = r[0] if r else None
    return dict(family=fam, state=r.state, hits=len(r), limit=LIMIT, limit_reached=len(r) >= LIMIT,
                first=None if first is None else dict(family=first.family, source_file=first.source_file,
                                                      line=first.line, sha=first.sha, origin=first.origin,
                                                      generator=first.generator, kind=first.kind),
                _witness=first)


def round_trip(res: dict, phrase: str) -> None:
    w = res.pop("_witness")
    if w is None:
        return
    line = raw_lines_at(CORPUS, w.source_file, {w.line}).get(w.line)
    rec = json.loads(line) if line else None
    body = bi.extract_body(rec, w.family, bi.SOURCES[w.family])[1] if rec else ""
    res["round_trip"] = dict(source_line_found=rec is not None, sha_equal=rec is not None and str(rec.get("sha")) == w.sha,
                             phrase_in_witness_text=phrase.strip() in w.text, phrase_in_source_record_body=phrase.strip() in body,
                             origin_is_generated=w.origin == "generated")
    rt = res["round_trip"]
    rt["ok"] = all(rt[k] for k in ("source_line_found", "sha_equal", "phrase_in_witness_text",
                                    "phrase_in_source_record_body", "origin_is_generated"))


def raw_absence_evidence() -> dict:
    """Scan every *.jsonl under the corpus root (bytes, no parsing) for the words of the two unmatched phrases."""
    terms = {"携帯データ": "携帯データ", "脱水機": "脱水機", "異音": "異音",
             "Wi-Fiなし 携帯データ": "Wi-Fiなし 携帯データ", "脱水機の異音": "脱水機の異音"}
    enc = {k: (v.encode("utf-8"), json.dumps(v, ensure_ascii=True)[1:-1].encode("ascii")) for k, v in terms.items()}
    per = {k: dict(lines=0, files=[]) for k in terms}
    both_same_line = dict(lines=0, files=[])
    dialogues: dict[str, dict[str, set]] = {}
    files = sorted(p for p in CORPUS.rglob("*.jsonl") if p.is_file())
    for path in files:
        rel = str(path.relative_to(CORPUS))
        hit = {k: 0 for k in terms}
        both = 0
        with path.open("rb") as handle:
            for raw in handle:
                present = {k for k, (u, a) in enc.items() if u in raw or a in raw}
                for k in present:
                    hit[k] += 1
                if {"脱水機", "異音"} <= present:
                    both += 1
                if rel.endswith("utterances.jsonl") and ({"脱水機", "異音"} & present):
                    try:
                        d = json.loads(raw).get("dialogue_id")
                    except json.JSONDecodeError:
                        continue
                    for k in ("脱水機", "異音"):
                        if k in present:
                            dialogues.setdefault(rel, {}).setdefault(k, set()).add(d)
        for k, n in hit.items():
            if n:
                per[k]["lines"] += n
                per[k]["files"].append(dict(path=rel, lines=n))
        if both:
            both_same_line["lines"] += both
            both_same_line["files"].append(dict(path=rel, lines=both))
    co_dialogue = {rel: len(d.get("脱水機", set()) & d.get("異音", set())) for rel, d in dialogues.items()}
    return dict(files_scanned=len(files), searched_forms="UTF-8 text and the JSON \\uXXXX-escaped form of each term",
                lines_containing=per, lines_with_both_脱水機_and_異音=both_same_line,
                dialogue_ids_with_both_脱水機_and_異音_by_file=co_dialogue,
                dialogue_ids_with_脱水機={rel: len(d.get("脱水機", set())) for rel, d in dialogues.items()},
                dialogue_ids_with_異音={rel: len(d.get("異音", set())) for rel, d in dialogues.items()})


def main() -> int:
    t0 = time.perf_counter()
    reg = json.loads((HERE / "c2_phrases.json").read_text())
    corpus = Corpus(IDX)
    out = dict(index=str(IDX), registered="artifacts/w1-c/c2_phrases.json", ticket=[], self_chosen=[],
               negative_controls=[])
    for t in reg["ticket"]:
        entry = dict(phrase=t["phrase"], expected_families=t["expected_families"], by_family=[], all_families_diagnostic=[])
        for fam in t["expected_families"]:
            res = run(corpus, t["phrase"], fam)
            round_trip(res, t["phrase"])
            entry["by_family"].append(res)
        for fam in FAMS:  # diagnostic only: where else does the phrase occur (never summed across families)
            res = run(corpus, t["phrase"], fam)
            res.pop("_witness")
            entry["all_families_diagnostic"].append(dict(family=fam, state=res["state"], hits=res["hits"]))
        found = [r for r in entry["by_family"] if r["state"] == "FOUND" and r["round_trip"]["ok"]]
        entry["satisfied"] = bool(found)
        out["ticket"].append(entry)
    for c in reg["self_chosen"]:
        res = run(corpus, c["phrase"], c["family"])
        round_trip(res, c["phrase"])
        res.update(phrase=c["phrase"], registered_row=dict(row_id=c["row_id"], source_file=c["source_file"], line=c["line"]))
        res["satisfied"] = res["state"] == "FOUND" and res["round_trip"]["ok"]
        out["self_chosen"].append(res)
    for c in reg["negative_controls"]:
        if not c["phrase"]:
            out["negative_controls"].append(dict(family=c["family"], state=c["state"]))
            continue
        res = run(corpus, c["phrase"], c["family"])
        res.pop("_witness")
        res.update(phrase=c["phrase"], heldout_file=c["heldout_file"], heldout_line=c["heldout_line"],
                   satisfied=res["state"] == "NO_MATCH")
        out["negative_controls"].append(res)
    unmatched = [e["phrase"] for e in out["ticket"] if not e["satisfied"]]
    out["unmatched_ticket_phrases"] = unmatched
    out["raw_corpus_absence_evidence"] = raw_absence_evidence() if unmatched else None
    per_family = {f: sum(1 for r in out["self_chosen"] if r["family"] == f and r["satisfied"]) for f in FAMS}
    out["summary"] = dict(ticket_phrases=len(out["ticket"]), ticket_satisfied=sum(e["satisfied"] for e in out["ticket"]),
                          self_chosen=len(out["self_chosen"]), self_chosen_satisfied=sum(r["satisfied"] for r in out["self_chosen"]),
                          self_chosen_satisfied_per_family=per_family,
                          negative_controls_drawn=sum(1 for n in out["negative_controls"] if "satisfied" in n),
                          negative_controls_no_match=sum(1 for n in out["negative_controls"] if n.get("satisfied")),
                          elapsed_seconds=round(time.perf_counter() - t0, 3))
    dump(HERE / "c2_search.json", out)
    for e in out["ticket"]:
        print("ticket", e["phrase"], [(r["family"], r["state"], r["hits"]) for r in e["by_family"]], "satisfied" if e["satisfied"] else "NOT satisfied")
    print(json.dumps(out["summary"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
