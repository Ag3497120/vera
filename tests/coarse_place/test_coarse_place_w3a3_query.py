"""W3-a3: what a query answers with the new fields (docs section 12.10) on a small synthetic placement
made by the real builder: the frame of a confirmed predicate, the closed list of frame_status values,
the invariants for every headword, an old placement (no generated_frames table) and the rule that a
generated claim is never lent to another word."""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import MINI, build, check_invariants, make_codex_db, q  # noqa: F401
from test_coarse_place_review3 import write_jawiki  # noqa: F401

BATCH = "b00000_0123456789ab"
CFG = {"left_attested": False, "rd_store_min": 5, "rd_min_total": 10, "rd_particle_min": 3,
       "rd_particle_share_pct": 10, "rd_type_share_pct": 50, "rd_min_sources": 2,
       "frame_decides": False, "slot_min": 3, "slot_share_pct": 10}
STATUS = {"CONFIRMED", "NOT_CONFIRMED", "ESTIMATED", "NOT_PREDICATE", "NO_ANSWER", "NO_PLACEMENT",
          "NO_FRAME_TABLE"}


def frow(word, ptype, frame, batch=BATCH):
    return {"word": word, "ptype": ptype, "frame": frame, "abstained": ptype is None,
            "provenance": {"origin": "generated", "model": "gpt-6-luna", "effort": "low",
                           "batch_id": batch, "attempt": 1, "out_sha256": "0" * 64}}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("w3a3q")
    texts = (["人が言葉を叫んだ。"] * 14          # a communication verb: が+PERSON, を+INFO_LANGUAGE
             + ["人が町へ急いだ。"] * 14          # a motion verb: が+PERSON, へ+PLACE
             + ["人が言葉を呟いた。"] * 14        # a communication verb whose generated frame misses を
             + ["人が言葉を囁いた。"] * 2)        # too few arguments for any distribution
    cdir = tmp / "cx"
    for fam in ("conversation", "narrative"):
        make_codex_db(cdir, fam, texts)
    jw = tmp / "jw.jsonl"
    write_jawiki(jw, [("ダミー", "ダミーは、日本の町である。")])
    fr = tmp / "frames.jsonl"
    rows = [frow("叫ぶ", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"], "に": ["PERSON"]}),
            frow("急ぐ", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"], "へ": ["PLACE"]}),
            frow("呟く", "P_COMMUNICATE", {"が": ["PERSON"]}),
            frow("囁く", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]}),
            frow("駅", "P_MOVE", {"が": ["PERSON"]}),                       # a noun: no frame is attached
            frow("断片語", None, {}),                                       # an abstention
            frow("材料にない語", "P_ACT", {"を": ["ARTIFACT"]})]            # not in the material
    fr.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    ledger = tmp / "ledger.jsonl"
    ledger.write_text(json.dumps({"ev": "start", "batch": BATCH, "attempt": 1}) + "\n"
                      + json.dumps({"ev": "end", "batch": BATCH, "attempt": 1, "status": "ok"}) + "\n",
                      encoding="utf-8")
    extra = ["--generated-frames", str(fr), "--generated-frames-ledger", str(ledger)]
    out = tmp / "p"
    assert build(out, jawiki=jw, codex_dir=cdir, families="conversation,narrative", extra=extra, cfg=CFG) == 0
    return {"tmp": tmp, "out": out, "jw": jw, "cdir": cdir, "extra": extra}


def test_a_confirmed_predicate_carries_its_frame_its_provenance_and_the_distribution_arms(built):
    r = q("叫ぶ", built["out"])
    assert (r["state"], r["origin"], r["top"]) == ("DECIDED", "direct", ["P_COMMUNICATE"])
    assert r["decided_by"] == ["gen_frame", "role_distribution@codex:conversation",
                               "role_distribution@codex:narrative"]
    assert r["frame_status"] == "CONFIRMED" and r["generated_frame"] is True
    assert r["frame"] == {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]}          # the significant particles only
    assert r["frame_unconfirmed"] == {"に": ["PERSON"]}                       # what the model wrote beyond: shown only
    assert list(r["frame"]) == [p for p in ct.ROLE_PARTICLES if p in r["frame"]]
    assert r["axes"]["gen_frame"]["provenance"] == {"model": "gpt-6-luna", "effort": "low", "batch_id": BATCH}
    rd = r["axes"]["role_distribution@codex:conversation"]
    assert rd["top"] == ["P_COMMUNICATE"] and rd["met"] is True and rd["significant_particles"] == ["が", "を"]
    assert rd["generated"] is True                                          # a codex-corpus arm: the old meaning
    assert r["axes"]["gen_frame"]["generated"] is False
    check_invariants(r)


def test_the_new_keys_come_last_and_the_old_ones_keep_their_order(built):
    r = q("叫ぶ", built["out"])
    keys = list(r)
    old = ["term", "namespace", "state", "origin", "estimate_basis", "constructed", "top", "candidates",
           "axes", "neighbors", "seen_in_material", "context", "placement"]
    assert keys[:len(old)] == old
    assert keys[-4:] == ["generated_frame", "frame_status", "frame", "frame_unconfirmed"]
    for t in ("昨日", "ホゲ", "2024年", "全然ない語"):
        rr = q(t, built["out"])
        assert list(rr)[-2:] == ["frame_status", "frame"] and rr["frame"] is None


def test_a_generated_frame_the_distribution_contradicts_or_does_not_cover_is_an_estimate(built):
    r = q("急ぐ", built["out"])
    assert (r["origin"], r["estimate_basis"], r["top"]) == ("estimated", "generated", ["P_COMMUNICATE"])
    assert r["frame_status"] == "ESTIMATED" and r["frame"] is None and r["generated_frame"] is True
    assert r["axes"]["gen_frame"]["why"] == "DISTRIBUTION_DISAGREES"
    assert r["axes"]["role_distribution@codex:conversation"]["top"] == ["P_MOVE"]
    assert r["axes"]["role_distribution@codex:conversation"]["met"] is False
    assert r["neighbors"][0]["via"] == "generated:" + BATCH
    r = q("呟く", built["out"])
    assert r["origin"] == "estimated" and r["frame_status"] == "ESTIMATED"
    assert r["axes"]["gen_frame"]["why"] == "FRAME_PARTICLES_NOT_COVERED"
    r = q("囁く", built["out"])                                # no distribution at all: an estimate, no reason
    assert r["origin"] == "estimated" and r["axes"]["gen_frame"]["why"] is None
    check_invariants(r)


def test_the_closed_list_of_frame_status_for_every_headword_and_every_probe(built):
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % built["out"], uri=True)
    words = [r[0] for r in con.execute("SELECT word FROM headwords ORDER BY word")]
    probes = words + ["ニセ叫ぶ", "全然ない語", "10kg", "2024年"]
    seen = set()
    for w in probes:
        r = q(w, built["out"])
        check_invariants(r)
        st = r["frame_status"]
        assert st in STATUS, (w, st)
        seen.add(st)
        if r["frame"] is not None:                              # the invariant of a non-null frame
            assert st == "CONFIRMED" and r["namespace"] == "P" and r["state"] == "DECIDED"
            assert r["origin"] == "direct" and "gen_frame" in r["decided_by"]
            assert r["frame"] and all(p in ct.CASE_PARTICLES_9 for p in r["frame"])
            for ts in r["frame"].values():
                assert ts and ts == sorted(ts) and all(t in ct.NOUN_TYPES for t in ts)
        if st == "CONFIRMED":
            assert r["frame"] is not None
        if st == "ESTIMATED":
            assert r["origin"] == "estimated"
        if st == "NO_ANSWER":
            assert r["state"] in ("UNPLACED", "UNKNOWN", "MULTIPLE")
        if st == "NOT_PREDICATE":
            assert r["namespace"] != "P" or not r["top"][0].startswith("P_")
        assert st != "NO_FRAME_TABLE"                           # this placement has the table
    assert {"CONFIRMED", "ESTIMATED", "NOT_PREDICATE", "NO_ANSWER"} <= seen


def test_a_seed_predicate_is_direct_but_not_confirmed_and_a_noun_is_not_a_predicate(built):
    r = q("行く", built["out"])
    assert r["origin"] == "direct" and r["frame_status"] in ("NOT_CONFIRMED",) and r["frame"] is None
    assert r["generated_frame"] is False
    r = q("町", built["out"])
    assert r["frame_status"] == "NOT_PREDICATE" and r["frame"] is None
    assert q("2024年", built["out"])["frame_status"] == "NOT_PREDICATE"
    assert q("全然ない語", built["out"])["frame_status"] == "NO_ANSWER"


def test_no_placement_has_a_status_and_no_frame(tmp_path):
    r = cp.query("叫ぶ", placement=str(tmp_path / "nowhere"))
    assert r["state"] == "NO_PLACEMENT" and r["frame_status"] == "NO_PLACEMENT" and r["frame"] is None
    r = cp.query("叫ぶ", placement=None)
    assert r["frame_status"] == "NO_PLACEMENT"


def test_a_placement_without_the_generated_frames_table_opens_and_answers_as_before(built, tmp_path):
    old = tmp_path / "old"
    shutil.copytree(built["out"], old)
    con = sqlite3.connect(str(old / "placement.sqlite"))
    con.execute("DROP TABLE generated_frames")
    con.commit()
    con.close()
    m = json.loads((old / "manifest.json").read_text(encoding="utf-8"))
    del m["outputs"]["tables"]["generated_frames"]
    (old / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    new, was = q("行く", built["out"]), q("行く", old)
    assert was["frame_status"] == "NO_FRAME_TABLE" and new["frame_status"] == "NOT_CONFIRMED"
    strip = lambda r: {k: v for k, v in r.items() if k not in ("frame_status", "placement")}
    assert strip(new) == strip(was)                              # nothing but the new key differs
    # the evidence rows remain, so a stored decision is still answered (its frame is the distribution's)
    r = q("叫ぶ", old)
    assert r["origin"] == "direct" and "gen_frame" in r["decided_by"]
    assert r["frame_status"] == "NO_FRAME_TABLE" and r["frame"] is None
    # a noun is a noun in an old placement too
    assert q("町", old)["frame_status"] == "NOT_PREDICATE"


def test_a_predicate_placed_by_a_generated_frame_is_not_lent_to_a_longer_word(built):
    r = q("叫ぶ", built["out"])
    assert "gen_frame" in r["decided_by"]
    # the head stage must not take 叫ぶ (placed with a generated frame) as the right-hand word of a compound
    c = q("ニセ叫ぶ", built["out"])
    assert c["top"] == [] and c["state"] in ("UNKNOWN", "UNPLACED")
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % built["out"], uri=True)
    samples = [smp.split("|") for (smp,) in con.execute("SELECT sample FROM unit_sample")]
    assert not [x for x in samples if "叫ぶ" in x]               # and it is no member of a unit family
    by = con.execute("SELECT by, origin FROM headwords WHERE word='叫ぶ'").fetchone()
    assert by[1] == "direct" and "gen_frame" in by[0].split("+")


def test_the_manifest_counts_the_generated_frames_by_outcome_and_reason(built):
    m = json.loads((built["out"] / "manifest.json").read_text(encoding="utf-8"))
    g = m["generated_frames"]
    assert g["rows_read"] == 6 and g["dropped_by_reason"]["abstained"] == 1          # the abstention is dropped
    assert g["dropped_by_reason"]["ns_not_predicate"] == 1 and g["dropped_by_reason"]["not_in_material"] == 1
    assert g["used"] == 4 and g["calls"] == 1 and g["batches_ok"] == 1 and g["model"] == "gpt-6-luna"
    o = g["outcomes"]
    assert o["decided_direct_upgrade"] == 1 and o["decided_direct_upgrade_all_sources_codex"] == 1
    assert o["decided_estimated_generated"] == 3
    assert o["DISTRIBUTION_DISAGREES"] == 1 and o["FRAME_PARTICLES_NOT_COVERED"] == 1
    ch = m["argument_chains"]["skipped_or_counted_by_reason"]
    assert ch["codex:conversation"]["counted"] > 0 and "jawiki" in ch
    assert any(x["name"].startswith("generated predicate frames") and x["origin"] == "generated"
               for x in m["materials"])
    assert m["outputs"]["tables"]["generated_frames"] == 4


def test_the_table_is_hashed_verify_counts_it_and_the_build_is_deterministic(built, tmp_path):
    out2 = tmp_path / "p2"
    assert build(out2, jawiki=built["jw"], codex_dir=built["cdir"], families="conversation,narrative",
                 extra=built["extra"], cfg=CFG, jobs=3) == 0
    m1 = json.loads((built["out"] / "manifest.json").read_text(encoding="utf-8"))
    m2 = json.loads((out2 / "manifest.json").read_text(encoding="utf-8"))
    assert m1["content_sha256"] == m2["content_sha256"]
    assert bcp.main(["verify", "--placement", str(built["out"])]) == 0
    bad = tmp_path / "bad"
    shutil.copytree(built["out"], bad)
    con = sqlite3.connect(str(bad / "placement.sqlite"))
    con.execute("UPDATE generated_frames SET model='x' WHERE word='叫ぶ'")
    con.commit()
    con.close()
    assert bcp.main(["verify", "--placement", str(bad)]) == 4
    # a build without the generated frames hashes differently and has the table, empty
    out3 = tmp_path / "p3"
    assert build(out3, jawiki=built["jw"], codex_dir=built["cdir"], families="conversation,narrative",
                 cfg=CFG) == 0
    m3 = json.loads((out3 / "manifest.json").read_text(encoding="utf-8"))
    assert m3["content_sha256"] != m1["content_sha256"] and m3["generated_frames"] is None
    assert m3["outputs"]["tables"]["generated_frames"] == 0
    r = q("叫ぶ", out3)
    assert r["state"] == "UNPLACED" and r["frame_status"] == "NO_ANSWER"      # the distribution alone decides nothing
    con3 = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out3, uri=True)
    ev = con3.execute("SELECT arm, src, type, n, base FROM evidence WHERE word='叫ぶ'").fetchall()
    d = ct.decide_word(ev, dict(ct.DEFAULT_CONFIG, **CFG))
    a = d["arms"]["role_distribution@codex:conversation"]
    assert a["threshold_met"] is True and a["met"] is False and a["why"] == "AGREEMENT_ONLY"
