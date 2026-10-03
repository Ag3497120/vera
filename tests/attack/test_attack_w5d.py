"""Executable W5-d probes. Run with the repository Python and PYTHONPATH set to the tree."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx import basis_policy as bp, coarse_place as cp, event_cross as ec
from verantyx import observe as ob, routing_from_text as rt, semantic_read as semread, semantic_reader as sr, sovereign as sov
from verantyx.semantic_ir import Clause, Role, Span, Variable

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
# Integration (auditor, 2026-10-04): the suite runs split across two machines and the registered build lives outside the tree, so a machine without
# it SKIPS with a visible reason instead of failing (same treatment as the other r6/r7-pinned tests). Where the build exists nothing changes.
_needs_build = pytest.mark.skipif(not __import__('os').path.isdir(R7), reason="ENV_MISSING[coarse placement r7/run1]")
Q = "誰が商人に小包を渡した？"
S1 = "船長が商人に小包を渡した。"
S2 = "提督が商人に小包を渡した。"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("VERA_PLACEMENT", "VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(k, raising=False)


def write_doc(tmp, items):
    p = Path(tmp) / "doc.jsonl"
    p.write_text("".join(json.dumps({"id": i, "text": s, "lang": "ja"}, ensure_ascii=False) + "\n" for i, s in items), encoding="utf-8")
    return str(p)


def write_pl(tmp, lemmas):
    p = Path(tmp) / "pl.json"
    p.write_text(json.dumps({"lemmas": lemmas, "neighbors": {}}, ensure_ascii=False), encoding="utf-8")
    return str(p)


def observe(tmp, items, placement=None):
    r = ob.run_entry(anchor_text=Q, anchor_kind="question", lang="ja", structure_path=write_doc(tmp, items),
                     no_index=True, placement_path=placement)
    assert r.exit_code == 0, r.error
    return json.loads(r.stdout)


def test_obs_partial_type_agreement_does_not_hide_a_second_attested_answer(tmp_path):
    # Two sentences support the same question cross; only 船長 has a checked direct type.
    pl = write_pl(tmp_path, {
        "船長": {"state": "DECIDED", "origin": "direct", "types": ["PERSON"]},
        "提督": {"state": "UNPLACED", "origin": None, "types": []},
    })
    out = observe(tmp_path, [("s1", S1), ("s2", S2)], pl)["answer"]
    assert out["status"] != "FILLED" or {f["surface"] for f in out["fillers"]} != {"船長"}, json.dumps(out, ensure_ascii=False)


def test_obs_no_placement_still_abstains_instead_of_filling(tmp_path):
    a = observe(tmp_path, [("s1", S1)])["answer"]
    assert a["status"] == "NO_TYPED_CANDIDATE" and a["fillers"] == []


def test_obs_tie_with_two_direct_witnesses_is_order_independent(tmp_path):
    pl = write_pl(tmp_path, {w: {"state": "DECIDED", "origin": "direct", "types": ["PERSON"]} for w in ("船長", "提督")})
    a = observe(tmp_path, [("s1", S1), ("s2", S2)], pl)
    b = observe(tmp_path, [("s2", S2), ("s1", S1)], pl)
    assert a["answer"]["status"] == "TIE" and a["answer"] == b["answer"]
    assert a["focus"] == b["focus"] and a["ranks"] == b["ranks"]


@_needs_build
def test_route_r7_estimated_common_noun_is_not_mapped_as_an_agent(monkeypatch):
    monkeypatch.setenv("VERA_PLACEMENT", R7)
    place = cp.query("委員会", placement=R7)
    assert place["state"] == "DECIDED" and place["origin"] == "estimated", json.dumps(place, ensure_ascii=False)
    ex = rt.explain("委員会はテストを書く。\n", "attack.md")
    routed = rt.route_task(ex, {"role": "implement", "kind": "test_authoring", "size": "medium"})
    assert ex.extraction.units[0].status != "MAPPED" and routed["agent"] is None, json.dumps(routed, ensure_ascii=False)


def reading(lang, *clauses):
    return {"schema": "verantyx.semantic_read/1", "lang": lang, "readable": True, "clauses": list(clauses),
            "relations": [], "abstain": None, "unsupported": [],
            "clause_meta": [{"rule": "attack", "span": [0, 1]} for _ in clauses]}


def clause(pred, roles, pol="+"):
    return {"predicate": pred, "roles": roles, "polarity": pol, "tense": "nonpast", "modality": None, "voice": "active"}


def assignment(name="ハル"):
    return reading("ja", clause("任せる", {"recipient": name, "patient": "実装"}))


class AllUnplaced:
    id = "attack-unplaced/1"
    def lookup(self, lemma):
        return ec.PlaceResult("UNPLACED", provenance={"attack": True})


class PredicateTypedName(AllUnplaced):
    id = "attack-predicate-name/1"
    def lookup(self, lemma):
        if lemma == "ハル":
            return ec.PlaceResult("DECIDED", "direct", None, ("P_COMMUNICATE",), {"attack": True})
        return super().lookup(lemma)


def explain_marker(lookup, marker_reading):
    first = "実装はハルに任せる。"
    second = "やっぱりそのまま、実装はハルに任せる。"
    table = {first: assignment(), second: assignment(), "そのまま": marker_reading}
    return rt.explain(first + "\n追記：" + second + "\n", "attack.md", reader=lambda s: table[s], lookup=lookup).extraction


def test_route_r2_denial_keeps_original_and_affirmative_mismatch_does_not_replace_across_lookup_variants():
    neg = reading("ja", clause("変える", {"patient": "それ"}, pol="-"))
    pos = assignment()
    for lookup in (AllUnplaced(), PredicateTypedName()):
        kept = explain_marker(lookup, neg)
        assert all(r.superseded_by is None for r in kept.relations) and kept.auto_resolved == 0
        assert kept.additions_kept == 1
        mismatch = explain_marker(lookup, pos)
        assert all(r.superseded_by is None for r in mismatch.relations) and mismatch.auto_resolved == 0
        assert any(u.status == "AMBIGUOUS_RELATION" for u in mismatch.units)
    # Removing the fake lookup blocks names without creating a replacement or a hidden resolution.
    no_lookup = explain_marker(None, neg)
    assert no_lookup.auto_resolved == 0 and all(r.superseded_by is None for r in no_lookup.relations)


def doc_answer(src):
    return {"kind": "answer", "verdict": "ANSWER", "text": "答え。", "sources": [src], "evidence": [], "door": "test"}


def test_a1_self_declared_human_origin_cannot_replace_missing_document_text(tmp_path):
    doc = tmp_path / "memo.txt"
    doc.write_text("提出された本文には別のことが書かれている。", encoding="utf-8")
    src = {"family": "document", "source": "memo.txt", "origin": "human_confirmed", "text": "本文に無い事実。"}
    out, _ = bp.apply_to_ask(doc_answer(src), bp.AskPolicy(), query="何が書かれている？", mode="round5", documents=[str(doc)])
    assert out["basis_policy"]["basis_original"] == "UNKNOWN_ORIGIN" and out["kind"] == "unknown", json.dumps(out, ensure_ascii=False)


def test_a1_probe_text_in_any_submitted_document_counts_even_if_source_names_another_file(tmp_path):
    memo = tmp_path / "memo.txt"
    other = tmp_path / "other.txt"
    memo.write_text("memo.txt の本文。", encoding="utf-8")
    other.write_text("この一文は別ファイルだけにある。", encoding="utf-8")
    src = {"family": "document", "source": "memo.txt", "text": "この一文は別ファイルだけにある。"}
    out, _ = bp.apply_to_ask(doc_answer(src), bp.AskPolicy(), query="問い", mode="round5", documents=[str(memo), str(other)])
    # The preregistered A1 rule says "any one of the handed-over documents"; this is a miss, not a violation.
    assert out["basis_policy"]["basis_original"] == "HUMAN"


def test_a1_short_substring_newline_and_document_order_probes():
    for text in ("窓", "窓は"):
        short = bp.classify_sources([{"family": "document", "text": text}], user_documents=True, document_texts=["窓は閉まる。"])
        assert short.counts["human"] == 1  # Literal NFKC substring contract: short strings pass.
    src = {"family": "document", "text": "前半。\n後半。"}
    forward = bp.classify_sources([src], user_documents=True, document_texts=["無関係", "前半。\n後半。"])
    reverse = bp.classify_sources([src], user_documents=True, document_texts=["前半。\n後半。", "無関係"])
    split = bp.classify_sources([{"family": "document", "text": "前半。後半。"}], user_documents=True, document_texts=["前半。", "後半。"])
    assert forward.to_dict() == reverse.to_dict() and forward.counts["human"] == 1 and split.unknown_origin == 1


def generated(claim):
    src = {"family": "local", "source": "local:new:1", "source_file": "new.jsonl", "line": 1, "sha": "new", "origin": "generated", "text": claim}
    return {"kind": "answer", "verdict": "ANSWER", "text": claim, "sources": [src], "evidence": [claim], "door": "test"}


def create_store(root, sid):
    assert sov.create(str(root), sid, "owner", consent_promote=True)["verdict"] == "CREATED"


def confirm(claim, query):
    req, rc = bp.apply_to_ask(generated(claim), bp.AskPolicy(human_present=True), query=query, mode="legacy", documents=[])
    assert rc == 0 and req["verdict"] == "CONFIRM_REQUEST"
    out, rc = bp.apply_to_ask(generated(claim), bp.AskPolicy(confirm=(req["confirm"]["id"], "yes")), query=query, mode="legacy", documents=[])
    assert rc == 0 and out["verdict"] == "CONFIRMED_HUMAN_RECORD"


def test_d1_a_same_claim_record_for_another_query_does_not_lift(tmp_path, monkeypatch):
    root = tmp_path / "sov"
    create_store(root, "s1")
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root)); monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    confirm("コードはＡＢＣです。", "別の問い")
    out, _ = bp.apply_to_ask(generated("コードはＡＢＣです。"), bp.AskPolicy(), query="今の問い", mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0


def test_d1_record_in_another_sovereign_root_does_not_lift(tmp_path, monkeypatch):
    other, current = tmp_path / "other", tmp_path / "current"
    create_store(other, "s2"); create_store(current, "s1")
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(other)); monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s2")
    confirm("窓が光った。", "内容は何ですか？")
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(current)); monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    out, _ = bp.apply_to_ask(generated("窓が光った。"), bp.AskPolicy(), query="内容は何ですか？", mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0


@_needs_build
def test_d1_nfkc_variant_does_not_lift_and_conflicting_variants_abstain(tmp_path, monkeypatch):
    root = tmp_path / "sov"; create_store(root, "s1")
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", str(root)); monkeypatch.setenv("VERA_SOVEREIGN_STORE", "s1")
    q = "内容は何ですか？"
    confirm("コードはＡＢＣです。", q)
    out, _ = bp.apply_to_ask(generated("コードはABCです。"), bp.AskPolicy(), query=q, mode="legacy", documents=[])
    assert out["kind"] == "unknown" and out["basis_policy"]["sovereign"]["confirmed_records_used"] == 0
    confirm("コードはABCです。", q)
    out, _ = bp.apply_to_ask(generated("コードはABCです。"), bp.AskPolicy(), query=q, mode="legacy", documents=[])
    assert out["verdict"] == "AMBIGUOUS_CONFIRMED_RECORDS"


def partial_frame_vector():
    pl, why = cp._open(R7)
    assert why is None, why
    for (word,) in pl.con.execute("SELECT word FROM generated_frames ORDER BY word"):
        ans = cp.query(word, placement=R7)
        if ans.get("frame_status") != "CONFIRMED":
            continue
        supported = {}
        for key, axis in ans.get("axes", {}).items():
            if not key.startswith("role_distribution@") or not axis.get("met"):
                continue
            source = key.split("@", 1)[1]
            rows = [e for e in pl.evidence(word) if e[0] == "role_distribution" and e[1] == source]
            base = next((e[4] for e in rows if e[4] is not None), None)
            typed = cp.ct.rd_analyze(axis["counts"], pl.cfg, base)["types"]
            for particle, types in typed.items():
                supported.setdefault(particle, set()).update(types)
        for particle, types in (ans.get("frame") or {}).items():
            backed = supported.get(particle, set()); extra = set(types) - backed
            if backed & set(types) and extra:
                return word, particle, sorted(backed), sorted(types), sorted(extra), ans
    return None


@_needs_build
def test_frame_confirmed_partial_intersection_does_not_authorize_unbacked_type():
    vector = partial_frame_vector()
    if vector is None:
        pytest.skip("r7 has no confirmed frame with a partially unsupported backed slot")
    word, particle, backed, frame_types, extra, ans = vector
    kind, frame = sr.predicate_frame(ans)
    assert kind == "confirmed" and set(frame[particle]) & set(backed) and set(extra) <= set(frame[particle])
    role = SimpleNamespace(span=Span("attack", 0, 1, "壺"))
    typed = {"predicate_basis": "placement_direct_head:" + ans["top"][0], "roles": [("x", role)],
             "role_basis": {"x": "placement_direct_head:" + extra[0]}}
    why = sr.typed_frame_check_ja(sr._tokens("壺" + particle), typed, ans)
    # Exercise the actual W3-b2 path U plan too, when a direct noun with the extra type exists in r7.
    nouns, _ = cp._open(R7)
    filler = next((w for (w,) in nouns.con.execute(
        "SELECT word FROM headwords WHERE ns='N' AND state='DECIDED' AND origin='direct' AND top=? ORDER BY word", (extra[0],))), None)
    if filler is not None:
        sentence = filler + particle + word
        start = len(filler) + len(particle)
        role = Role("patient", filler, Span("attack", 0, len(filler), filler), "frame")
        clause = Clause("attack", Variable("event_attack", "event"), word,
                        Span("attack", start, len(sentence), word), (role,), Span("attack", 0, len(sentence), sentence))
        query = SimpleNamespace(query=lambda term: cp.query(term, placement=R7))
        planned, plan_reason = sr.typed_plan_u_w3b2_ja(
            clause, sr._tokens(sentence), query, voice="active", written=word,
            strip=lambda r: r.term, role_map=semread._ROLE_TABLE)
        print(json.dumps({"w3b2_sentence": sentence, "w3b2_role_basis": planned.get("role_basis") if planned else None,
                          "w3b2_reason": plan_reason}, ensure_ascii=False))
        assert planned is None, "W3-b2 plan accepted a filler type outside the backing distribution"
    print(json.dumps({"predicate": word, "particle": particle, "distribution": backed, "confirmed_frame": frame_types,
                      "unsupported_type": extra[0], "reader_gate": why}, ensure_ascii=False))
    assert why is not None, "W3-b2/W3-b1 frame gate accepted a frame-only type"
