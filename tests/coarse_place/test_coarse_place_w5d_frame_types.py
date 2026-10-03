"""W5-d (docs/COARSE_PLACEMENT.md section 13): a generated predicate frame is CONFIRMED only when no particle of it
contradicts the distribution that backed it.  A synthetic placement made by the real builder (the fixtures are those of
test_coarse_place_w3a3_query.py, which stays as it was): one verb whose generated frame types the object as a PERSON
while the distribution says INFO_LANGUAGE (a contradiction -> NOT_CONFIRMED, the predicate type itself unchanged), one
whose frame lists both types (they meet -> CONFIRMED), and the manifest's two new counts."""
import json
from pathlib import Path

import pytest

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import build, check_invariants, make_codex_db, q  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401
from test_coarse_place_w3a3_query import BATCH, CFG, frow  # noqa: F401


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w5dframe")
    texts = (["人が言葉を叫んだ。"] * 14          # が+PERSON, を+INFO_LANGUAGE: a communication verb
             + ["人が言葉を呟いた。"] * 14        # the same distribution, a second verb
             + ["人が言葉を囁いた。"] * 14)       # and a third (its frame misses を entirely)
    cdir = tmp / "cx"
    for fam in ("conversation", "narrative"):
        make_codex_db(cdir, fam, texts)
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    fr = tmp / "frames.jsonl"
    rows = [frow("叫ぶ", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["PERSON"]}),                      # を contradicts
            frow("呟く", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE", "PERSON"]}),     # を meets the distribution
            frow("囁く", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]})]               # the plain agreement
    fr.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    ledger = tmp / "ledger.jsonl"
    ledger.write_text(json.dumps({"ev": "start", "batch": BATCH, "attempt": 1}) + "\n"
                      + json.dumps({"ev": "end", "batch": BATCH, "attempt": 1, "status": "ok"}) + "\n",
                      encoding="utf-8")
    extra = ["--generated-frames", str(fr), "--generated-frames-ledger", str(ledger)]
    out = tmp / "p"
    assert build(out, jawiki=jw, codex_dir=cdir, families="conversation,narrative", extra=extra, cfg=CFG) == 0
    return {"tmp": tmp, "out": out, "jw": jw, "cdir": cdir, "extra": extra}


def test_a_frame_that_contradicts_its_distribution_is_not_confirmed(built):
    r = q("叫ぶ", built["out"])
    # the predicate type is not changed: still a direct, decided P_COMMUNICATE placed by the generated frame
    assert (r["state"], r["origin"], r["top"]) == ("DECIDED", "direct", ["P_COMMUNICATE"])
    assert r["generated_frame"] is True and "gen_frame" in r["decided_by"]
    assert r["frame_status"] == "NOT_CONFIRMED"
    assert r["frame"] is None
    assert "frame_unconfirmed" not in r
    assert r["frame_disagreement"] == {"を": {"generated": ["PERSON"],
                                              "distribution": {"role_distribution@codex:conversation": ["INFO_LANGUAGE"],
                                                               "role_distribution@codex:narrative": ["INFO_LANGUAGE"]}}}
    assert list(r)[-4:] == ["generated_frame", "frame_status", "frame", "frame_disagreement"]
    check_invariants(r)


def test_a_frame_whose_types_meet_the_distribution_stays_confirmed(built):
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A4）: A-4 で frame に残すのは「生成の枠 ∩ 分布の裏づけ」だけ。治具の分布（人が言葉を呟いた×14: が+PERSON・を+INFO_LANGUAGE）から手で求めた期待:
    # 呟く の生成の枠 を=[INFO_LANGUAGE, PERSON] のうち分布が裏づけるのは INFO_LANGUAGE だけ → frame[を]=[INFO_LANGUAGE]、外れた PERSON は frame_unconfirmed[を]
    r = q("呟く", built["out"])
    assert r["frame_status"] == "CONFIRMED"
    assert r["frame"]["を"] == ["INFO_LANGUAGE"]                          # the intersection rule (A-4): the PERSON the distribution does not back is not in frame
    assert r["frame"]["が"] == ["PERSON"]
    assert "frame_disagreement" not in r and r["frame_unconfirmed"] == {"を": ["PERSON"]}
    assert list(r)[-4:] == ["generated_frame", "frame_status", "frame", "frame_unconfirmed"]
    r = q("囁く", built["out"])
    assert r["frame_status"] == "CONFIRMED" and r["frame"] == {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]}
    assert "frame_disagreement" not in r


def test_the_disagreement_key_is_never_on_an_answer_without_one(built):
    for w in ("呟く", "囁く", "町", "ダミー", "全然ない語", "行く"):
        r = q(w, built["out"])
        assert "frame_disagreement" not in r
        assert "_dis" not in r
    r = q("叫ぶ", built["out"])                      # and a contradicted frame has it, with a null frame
    assert r["frame_status"] == "NOT_CONFIRMED" and r["frame"] is None and r["frame_disagreement"]


def test_the_pure_function_agrees_with_the_query_and_two_queries_are_byte_equal(built):
    pl, _why = cp._open(str(built["out"]))
    for w, want in (("叫ぶ", True), ("呟く", False), ("囁く", False)):
        ev = pl.evidence(w)
        dec = ct.decide_word(list(ev), pl.cfg)
        d = cp.frame_type_disagreement(ev, dec["by"], dec, pl.cfg)
        assert bool(d) is want, (w, d)
        assert d == (q(w, built["out"]).get("frame_disagreement") or {})
        assert cp.frame_type_disagreement(ev, dec["by"], dec, pl.cfg) == d                   # pure
    a = json.dumps(q("叫ぶ", built["out"]), ensure_ascii=False, sort_keys=False)
    b = json.dumps(q("叫ぶ", built["out"]), ensure_ascii=False, sort_keys=False)
    assert a == b and a.encode("utf-8") == b.encode("utf-8")
    # a word that the generated frame did not decide has nothing to contradict
    ev = pl.evidence("囁く")
    dec = ct.decide_word(list(ev), pl.cfg)
    assert cp.frame_type_disagreement(ev, [k for k in dec["by"] if k != "gen_frame"], dec, pl.cfg) == {}


def test_the_manifest_counts_confirmed_and_contradicted_frames(built):
    m = json.loads((Path(built["out"]) / "manifest.json").read_text(encoding="utf-8"))
    o = m["generated_frames"]["outcomes"]
    assert o["decided_direct_upgrade"] == 3
    assert o["frame_types_disagree"] == 1 and o["frame_confirmed"] == 2
    assert o["frame_confirmed"] + o["frame_types_disagree"] == o["decided_direct_upgrade"]


def test_the_tables_are_the_same_as_before_the_confirmation_rule(built):
    """The placement's content hash does not depend on the frame confirmation: it is a query-time rule and a count in the
    manifest's outcomes (not hashed content), so a re-build gives the same content hash."""
    out2 = built["tmp"] / "p2"
    assert build(out2, jawiki=built["jw"], codex_dir=built["cdir"], families="conversation,narrative",
                 extra=built["extra"], cfg=CFG, jobs=3) == 0
    m1 = json.loads((Path(built["out"]) / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    assert m1["content_sha256"] == m2["content_sha256"]
