"""W3-a4 (docs section 12.17): the verbal-noun predicate through the real builder on a small synthetic
placement: a headword with namespace P and a distribution arm, the manifest's sahen counts, and the
frame-cover rule on a generated frame."""
import json

import pytest

from tools import build_coarse_placement as bcp

from test_coarse_place_build import build, check_invariants, make_codex_db, q  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401
from test_coarse_place_w3a3_query import BATCH, CFG, frow  # noqa: F401

CFG4 = dict(CFG, frame_cover_rule="k62_he_by_ni_place")
WORD = "移動する"


def frames(tmp, rows):
    fr = tmp / "frames.jsonl"
    fr.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    ledger = tmp / "ledger.jsonl"
    ledger.write_text(json.dumps({"ev": "start", "batch": BATCH, "attempt": 1}) + "\n"
                      + json.dumps({"ev": "end", "batch": BATCH, "attempt": 1, "status": "ok"}) + "\n",
                      encoding="utf-8")
    return ["--generated-frames", str(fr), "--generated-frames-ledger", str(ledger)]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w3a4b")
    texts = (["人が町へ移動した。"] * 14          # a common noun + する: が+PERSON, へ+PLACE
             + ["人が町へ急いだ。"] * 14)         # an ordinary motion verb with the same frame
    cdir = tmp / "cx"
    for fam in ("conversation", "narrative"):
        make_codex_db(cdir, fam, texts)
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    out = {}
    for name, frame in (("direct", {"が": ["PERSON"], "へ": ["PLACE"]}),
                        ("he_waived", {"が": ["PERSON"], "に": ["PLACE"]}),
                        ("he_missing", {"が": ["PERSON"]})):
        extra = frames(tmp, [frow(WORD, "P_MOVE", frame), frow("急ぐ", "P_MOVE", {"が": ["PERSON"], "へ": ["PLACE"]})])
        p = tmp / name
        assert build(p, jawiki=jw, codex_dir=cdir, families="conversation,narrative", extra=extra, cfg=CFG4) == 0
        out[name] = p
    return {"tmp": tmp, "jw": jw, "cdir": cdir, **out}


def test_the_noun_plus_suru_is_a_predicate_headword_with_a_distribution_arm(built):
    r = q(WORD, built["direct"])
    assert r["state"] != "UNKNOWN"
    assert r["namespace"] == "P"
    arms = [k for k in r["axes"] if k.startswith("role_distribution@")]
    assert arms, r["axes"].keys()
    check_invariants(r)


def test_a_generated_frame_is_confirmed_by_the_distribution_under_the_rule(built):
    r = q(WORD, built["direct"])
    assert (r["state"], r["origin"], r["top"]) == ("DECIDED", "direct", ["P_MOVE"])
    assert r["frame_status"] == "CONFIRMED" and r["frame"] == {"が": ["PERSON"], "へ": ["PLACE"]}


def test_he_is_covered_by_ni_place_and_is_not_shown_in_frame(built):
    r = q(WORD, built["he_waived"])
    assert (r["state"], r["origin"], r["top"]) == ("DECIDED", "direct", ["P_MOVE"])
    assert "へ" not in (r["frame"] or {})                       # section 12.10: frame holds only the frame's particles
    assert r["frame_status"] in ("CONFIRMED", "NOT_CONFIRMED")


def test_a_frame_without_he_or_ni_place_stays_an_estimate(built):
    r = q(WORD, built["he_missing"])
    assert (r["state"], r["origin"], r["top"]) == ("DECIDED", "estimated", ["P_MOVE"])


def test_the_manifest_counts_the_verbal_noun_chains_by_reason_and_use(built):
    m = json.loads((built["direct"] / "manifest.json").read_text(encoding="utf-8"))
    ac = m["argument_chains"]
    for src, by in ac["sahen_by_reason"].items():
        assert sum(by.values()) == ac["skipped_or_counted_by_reason"][src].get("sahen", 0), src
    assert ac["sahen_verbs"]["codex:narrative"] == {"distinct": 1, "uses": 14}
    assert ac["sahen_by_reason"]["codex:narrative"] == {"counted": 28}
    st2 = ac["stage2"]["per_source"]["codex:narrative"]
    assert st2["sahen_chains"] == 28 and st2["chains"] >= 28


def test_the_manifest_counts_the_words_the_cover_rule_helped(built):
    def outcomes(name):
        m = json.loads((built[name] / "manifest.json").read_text(encoding="utf-8"))
        return m["generated_frames"]["outcomes"]
    assert outcomes("he_waived").get("cover_he_by_ni_place") == 1
    assert "cover_he_by_ni_place" not in outcomes("direct")        # the frame has he: nothing was waived
    assert "cover_ignored_non_k62" not in outcomes("he_waived")
