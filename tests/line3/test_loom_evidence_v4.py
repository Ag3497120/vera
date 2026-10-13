"""LOOM-evidence-v4 (docs/LINE3_PUBLIC_DESIGN.md §5, L-LOOM-212..): evidence.v4 = evidence.v3 MINUS R7 (the naming-verb rule whose 「いう」 inside 「という」 admitted B6-U05) PLUS the
subject-chain rule (every noun of 「XのYの…Z」 must be in the answer's clause: closes B6-U35 / U36).  Selectable, NOT the default (OP-PUB-6: only if the held-out bank7 admits no
unanswerable question).  The v3 rules stay frozen: this file pins that, the freeze of v4 itself, the rule on real and toy sentences, and the dev-set probe (bank2, bank4, bank6)."""
import csv
import hashlib
import json
import os
import subprocess

import pytest

from verantyx.loom import evidence as ev
from verantyx.loom import ledger as lg
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from loom_common import CORPUS, PY, ROOT, rows

V2, V3, V4 = ev.EVIDENCE_V2, ev.EVIDENCE_V3, ev.EVIDENCE_V4
EV4DIR = os.path.join(ROOT, "experiments/line3/loom/ev4")
BANK6_TSV = os.path.join(ROOT, "experiments/line3/bank6/bank6.tsv")

# ---- the freeze (recorded BEFORE any held-out bank7 probe; see L-LOOM-216) -----------------------------------------------------------------------------
FROZEN_V3_RULES_DIGEST = "eca9ccd48aa6ddca8e74f33894acb380cc68667bd34950fd579c4e9bd9cf829d"
FROZEN_V4_RULES_DIGEST = "dae4c99ad17ee178249f83d3ba734cbb48f0ac1c1c336dd4866ecf0e5f915fc6"
FROZEN_V4_EVIDENCE_SHA = "17407dfb4763dd55a80e37d320fe25f1908d4ae4b430d9daabea7b97ce93d3db"


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def _bank6():
    return list(csv.DictReader(open(BANK6_TSV, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))


def _toy(tmp_path, sents):
    p = tmp_path / "toy.jsonl"
    p.write_text("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": t, "sent": s, "source": "%s#%d" % (t, i)}, ensure_ascii=False) + "\n"
                         for i, (t, s) in enumerate(sents)), encoding="utf-8")
    return p


def _passing(c, q, sid, version, scope=ev.SCOPE_TITLE):
    qu = ev.question_units(q)
    v = ev.view_of(c, sid)
    return [v.text[v.spans[i][0]:v.spans[j][1]] for i in range(len(v.units)) for j in range(i, len(v.units)) if not ev.judge_quote(c, qu, scope, sid, "WORD", i, j, version)["codes"]]


# ---- T-EV4-01: the freeze --------------------------------------------------------------------------------------------------------------------------
def test_t_ev4_01_the_v3_rules_are_untouched_and_v4_is_frozen():
    assert ev.v3_rules_digest() == FROZEN_V3_RULES_DIGEST                                                    # v4 added code; no function the v3 digest covers changed
    assert ev.v4_rules_digest() == FROZEN_V4_RULES_DIGEST
    assert len(FROZEN_V4_EVIDENCE_SHA) == 64                                                                 # historical: evidence.py changed when evidence.v5 was added (the v3 and v4 digests above did not); the file pin moved to test_loom_evidence_v5.py
    assert ev.V4_RULE_IDS == ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "T1", "T2", "CH") and ev.V4_OFF == frozenset({"R7"})
    assert set(ev.V4_RULE_IDS) - {"CH"} == set(ev.V3_RULE_IDS) - {"R7"}
    assert ev.V4_RULE_SENTENCE.startswith(ev.V3_RULE_SENTENCE.rstrip(".").rsplit(";", 1)[0])             # the v3 sentence's rules, then the chain sentence


def test_t_ev4_01_v4_is_selectable_and_v2_stays_the_default_everywhere(tmp_path, monkeypatch):
    import inspect
    from verantyx import cli
    from verantyx.loom import mcp as lm
    from verantyx.loom.ops import EVIDENCE_RULE_V2, EVIDENCE_RULE_V4, EVIDENCE_RULES
    assert ev.EVIDENCE_VERSIONS == (ev.EVIDENCE_V1, V2, V3, V4, ev.EVIDENCE_V5) and ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES["v4"] == V4
    assert inspect.signature(ev.judge_quote).parameters["version"].default == V2
    assert EVIDENCE_RULES[V4] == EVIDENCE_RULE_V4 == EVIDENCE_RULE_V2 + " " + ev.V4_RULE_SENTENCE
    t = [{"task_id": "x", "text": "花園町駅の隣駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": CORPUS}]
    assert LoomServer(t, str(tmp_path / "a"), ()).evidence_profile == (V2, "clause_or_title")
    assert LoomServer(t, str(tmp_path / "b"), (), evidence="v4").evidence_profile == (V4, "clause_or_title")
    seen = []
    monkeypatch.setattr(lm, "serve", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r")]) == 0
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r"), "--evidence", "v4"]) == 0
    assert [a[4] for a in seen] == ["v2", "v4"]


# ---- T-EV4-02: the chain ----------------------------------------------------------------------------------------------------------------------------
def test_t_ev4_02_the_subject_chain_is_the_genitive_walk_of_the_cut():
    sc = lambda q: ev.subject_chain(ev.question_units(q))                                                    # noqa: E731
    assert sc("花園町駅の隣駅の駅番号は何ですか？") == ("花園町駅", "隣駅")
    assert sc("親会社の創業者は誰ですか？") == ("親会社",) and sc("ハッシュテーブルの別名は何ですか") == ("ハッシュテーブル",)
    assert sc("フェミニズムは別名で何と呼ばれていますか？") == () and sc("何年に設立されましたか") == ()          # not an x_chain: no chain


def test_t_ev4_02_the_chain_agrees_with_the_cut_of_every_dev_question():
    """The chain is recomputed from the cut's own text (the gate never reads a row): outermost noun first == `subject[0]` exactly when the cut says x_chain, and cutting the cut's text
    again gives the same cut."""
    qs = []
    for name in ("dev129", "bank6"):
        qs += [it["q"] for it in json.load(open(os.path.join(EV4DIR, "out_%s.json" % name), encoding="utf-8"))["items"]]
    assert len(qs) == 189
    long = []
    for q in qs:
        qu = ev.question_units(q)
        again = ev.question_units(qu.text)
        assert (again.text, again.units, again.subject, again.form) == (qu.text, qu.units, qu.subject, qu.form)
        ch = ev.subject_chain(qu)
        assert bool(ch) == (qu.subject_level == "x_chain") and (not ch or ch[0] == qu.subject[0])
        if len(ch) > 1:
            long.append(ch)
    assert len(long) == 15 and ("花園町駅", "隣駅") in long and ("海浦駅", "隣駅") in long


def test_t_ev4_02_the_v4_begin_object_is_the_v3_object_plus_the_chain():
    for q in ("花園町駅の隣駅の駅番号は何ですか？", "ハッシュテーブルの別名は何ですか", "何年に設立されましたか"):
        qu = ev.question_units(q)
        o4, o3 = ev.question_obj(qu, ev.SCOPE_TITLE, V4), qu.to_obj(ev.SCOPE_TITLE, V3)
        assert o4 == dict(o3, evidence=V4, chain=list(ev.subject_chain(qu)))
        for v in (ev.EVIDENCE_V1, V2, V3):                                                                  # the older versions' objects are as they were
            assert ev.question_obj(qu, ev.SCOPE_TITLE, v) == qu.to_obj(ev.SCOPE_TITLE, v)


# ---- T-EV4-03: the two failures of bank6, on the real sentences ---------------------------------------------------------------------------------------
@pytest.mark.parametrize("iid,sid,i0,i1,ans", [("B6-U05", 16, 12, 12, "男女"), ("B6-U35", 21, 2, 3, "Y17"), ("B6-U36", 37, 2, 3, "OR08")])
def test_t_ev4_03_the_bank6_admissions_of_v3_are_refused_in_v4(corpus, iid, sid, i0, i1, ans):
    q = {r["#id"]: r["question"] for r in _bank6()}[iid]
    qu = ev.question_units(q)
    r3 = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, V3)
    r4 = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, V4)
    assert r3["answer"] == r4["answer"] == ans and r3["codes"] == [] and r3["evidence"] is not None            # v3 (and v2 for U35 / U36) admits it
    assert r4["codes"] != [] and r4["evidence"] is None and r4["rules"] == []
    if iid == "B6-U05":
        assert r3["rules"] == ["R7"] and r4["codes"] == ["no_slot_head"]                                  # R7 is the only reason v3 passed; v4 has no naming-verb rule
    else:
        assert r3["rules"] == [] and r4["codes"] == ["no_subject"] and r4["failures"][0]["subject"] == "隣駅"
        assert ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, V2)["codes"] == []


def test_t_ev4_03_the_naming_verb_in_a_toy_sentence_without_r7(tmp_path):
    """R7 gone: 「という」 is not a naming verb of the clause.  The alias form (R3) 「A ともいう」 is NOT R7 and stays."""
    c = Corpus.load(_toy(tmp_path, [("青葉堂", "青葉堂は松風庵ともいう。"), ("青葉堂", "青葉堂という店は松風庵に移された。"), ("青葉堂", "青葉堂は松風庵と呼ばれる。")]).read_bytes())
    assert _passing(c, "青葉堂の別名は何ですか", 0, V4) == ["松風庵"] == _passing(c, "青葉堂の別名は何ですか", 0, V3)       # R3 alias kept
    q = "青葉堂は何と呼ばれていますか"
    assert _passing(c, q, 2, V3) == _passing(c, q, 2, V4) == ["松風庵"]                                       # the head 呼ば is read as itself, no R7 needed
    assert "松風庵" not in _passing(c, q, 1, V4)                                                              # 「という」 + 「に」: no 呼ば in the clause, no R7


def test_t_ev4_03_the_chain_rule_in_a_toy_corpus_from_both_sides(tmp_path):
    sents = [("花園町駅", "花園町駅の駅番号はY17である。"),                         # the station's OWN number
             ("花園町駅", "花園町駅の隣駅の駅番号はOR08である。"),                   # the neighbour's number: both nouns in the clause
             ("海浦駅", "海浦駅は花園町駅の隣駅で、駅番号はOR08である。"),            # not one clause (comma)
             ("花園町駅", "花園町駅の駅番号は、Y17である。"),
             ("親会社", "親会社の創業者は山田太郎である。")]
    c = Corpus.load(_toy(tmp_path, sents).read_bytes())
    qn = "花園町駅の隣駅の駅番号は何ですか"
    assert _passing(c, qn, 0, V3) == ["Y17"] and _passing(c, qn, 0, V4) == []                                  # the bank6 U35 failure in miniature
    assert _passing(c, qn, 3, V3) == ["Y17"] and _passing(c, qn, 3, V4) == []
    assert _passing(c, qn, 1, V3) == ["OR08"] == _passing(c, qn, 1, V4)                                        # the legitimate answer passes
    u = ev.view_of(c, 1).units
    k = next(i for i in range(len(u)) if "".join(u[i:i + 2]) == "OR08")                                       # OR | 08: two WORD units
    r = ev.judge_quote(c, ev.question_units(qn), ev.SCOPE_TITLE, 1, "WORD", k, k + 1, V4)
    assert r["rules"] == ["CH"] and r["chain"] == ["花園町駅", "隣駅"] and r["evidence"]["subject"] == [{"run": "花園町駅", "via": "clause"}]
    assert _passing(c, qn, 2, V4) == []
    assert _passing(c, "花園町駅の駅番号は何ですか", 0, V4) == ["Y17"]                                         # no chain: a one-noun subject is as in v3
    assert _passing(c, "親会社の創業者は誰ですか", 4, V4) == _passing(c, "親会社の創業者は誰ですか", 4, V3) == ["山田太郎"]
    # the title may stand in for the OUTERMOST noun only; the inner noun must be in the clause even in the title scope
    c2 = Corpus.load(_toy(tmp_path, [("花園町駅", "駅番号はOR08である。"), ("花園町駅", "隣駅の駅番号はOR08である。")]).read_bytes())
    assert _passing(c2, qn, 0, V3) == ["OR08"] and _passing(c2, qn, 0, V4) == []
    assert _passing(c2, qn, 1, V3) == ["OR08"] == _passing(c2, qn, 1, V4)
    assert _passing(c2, qn, 1, V4, ev.SCOPE_CLAUSE) == []                                                     # clause scope: the outermost noun is not in the clause either


# ---- T-EV4-04: a v4 run through the server; the ledger replays ------------------------------------------------------------------------------------------
def test_t_ev4_04_a_v4_run_records_its_profile_emits_and_replays_identically_and_cannot_be_relabelled(tmp_path):
    p = _toy(tmp_path, [("花園町駅", "花園町駅の駅番号はY17である。"), ("花園町駅", "花園町駅の隣駅の駅番号はOR08である。")])
    t = [{"task_id": "toy/ro", "text": "花園町駅の隣駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": str(p)}]

    def run(version, name, sid, first, last):
        srv = LoomServer(t, str(tmp_path / name), (), evidence=version)
        b = srv.begin("toy/ro", "t", "x")
        assert srv.call("weave_span", {"run_id": "x", "sid": sid, "tier": "WORD", "first": first, "last": last})["ok"]
        return b, srv.call("emit", {"run_id": "x"}), tmp_path / name / "x"
    b4, e4, d4 = run("v4", "v4", 1, "OR", "08")
    assert b4["evidence_profile"] == {"version": V4, "subject_scope": "clause_or_title"} and b4["question"]["evidence"] == V4 and b4["question"]["chain"] == ["花園町駅", "隣駅"]
    assert e4["ok"] and e4["text"] == "OR08" and e4["ev"] == V4
    assert lg.verify(d4)["status"] == "OK" and lg.verify(d4)["replay"]["status"] == "IDENTICAL"
    _, e3, d3 = run("v3", "v3", 0, "Y", "17")                                                              # v3 emits the station's own number ...
    assert e3["ok"] and e3["text"] == "Y17"
    _, e4w, d4w = run("v4", "v4w", 0, "Y", "17")                                                           # ... v4 refuses it with a typed reason
    assert e4w["ok"] is False and e4w["refusal"] == "no_evidence"
    assert lg.verify(d4w)["status"] == "OK" and lg.verify(d4w)["replay"]["status"] == "IDENTICAL"
    # a forged relabel is a replay difference, in both directions (the begin row's rules / question change)
    for d, to in ((d4, V3), (d3, V4)):
        _reseal(d, lambda rs, to=to: rs[0]["result"]["evidence_profile"].update(version=to))
        assert lg.verify_chain(d)["status"] == "OK" and lg.verify(d)["status"] == "REPLAY_DIFFERS"


def _reseal(d, edit):
    """Rewrite a ledger with `edit(rows)` applied and the whole chain sealed again (so that ONLY the replay can tell)."""
    rs = rows(d)
    edit(rs)
    prev = lg.GENESIS
    lines = []
    for i, r in enumerate(rs):
        r["i"], r["prev"] = i, prev
        r["sha"] = lg.row_sha(r)
        prev = r["sha"]
        lines.append(lg.line_of(r))
    (d / "ops.jsonl").write_bytes(b"".join(lines))
    (d / "HEAD").write_text(prev + "\n")


# ---- T-EV4-05: the dev-set probe (stored output pinned; v4 recomputed live and equal to it) ---------------------------------------------------------
def _report():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ev4_report", os.path.join(EV4DIR, "report.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


REACH_V2 = ["I2-003", "I2-004", "I2-005", "I2-006", "I2-013", "I2-014", "I2-018", "R2-I005", "R2-I007", "R2-I017"]
REACH_V3 = ["I2-001", "I2-003", "I2-004", "I2-005", "I2-006", "I2-008", "I2-012", "I2-013", "I2-014", "I2-018", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048",
            "R2-I005", "R2-I007", "R2-I008", "R2-I015", "R2-I017"]
REACH_V4 = [i for i in REACH_V3 if i != "I2-012"]                       # R7 gained exactly I2-012; nothing else is lost
BANK6_REACH_V2, BANK6_REACH_V3 = ["B6-A05", "B6-A13", "B6-A27"], ["B6-A05", "B6-A13", "B6-A15", "B6-A24", "B6-A27"]
BANK6_WRONG = ["B6-A05", "B6-A20", "B6-A27"]                            # v2 behaviour (rules = []), identical in v3 and v4


def test_t_ev4_05_the_probe_outputs_were_made_by_the_frozen_file():
    for name in ("dev129", "bank6"):
        d = json.load(open(os.path.join(EV4DIR, "out_%s.json" % name), encoding="utf-8"))
        assert d["evidence_sha"] == FROZEN_V4_EVIDENCE_SHA


def test_t_ev4_05_the_stored_probe_numbers_v2_v3_v4():
    R = _report()
    d = R.summary("dev129")                                              # bank2 (69 answerable) + bank4 (60 unanswerable)
    assert (d[V2]["reach"], d[V3]["reach"], d[V4]["reach"]) == (REACH_V2, REACH_V3, REACH_V4) and len(REACH_V4) == 21
    assert all(d[v]["wrong"] == [] and d[v]["unans"] == [] and d[v]["traps"] == [] for v in (V2, V3, V4))
    b = R.summary("bank6")                                               # 26 answerable + 34 unanswerable
    assert (b[V2]["reach"], b[V3]["reach"], b[V4]["reach"]) == (BANK6_REACH_V2, BANK6_REACH_V3, BANK6_REACH_V3)
    assert all(b[v]["wrong"] == BANK6_WRONG for v in (V2, V3, V4))
    assert (b[V2]["unans"], b[V3]["unans"], b[V4]["unans"]) == (["B6-U35", "B6-U36"], ["B6-U05", "B6-U35", "B6-U36"], [])
    assert b[V3]["adm"]["B6-U05"][0][5] == ["R7"] and b[V4]["shape"] == {"S1-alias": "0/5", "S2-place": "0/5", "S3-person": "0/5", "S4-toshite": "0/6", "S5-paren": "0/4",
                                                                           "S6-naming": "0/5", "S7-near": "0/4"}


@pytest.fixture(scope="module")
def live_v4(corpus):
    """Every stretch of at most 10 WORD units of every sentence that passes evidence.v4 (title scope), for the 129 dev-set questions and the 60 bank6 questions; the same cut as
    sweep.py.  {set: {id: [[sid, i, j, text, reading, rules, via, source, clause]]}}.  About 3 minutes."""
    out = {}
    for name in ("dev129", "bank6"):
        d = json.load(open(os.path.join(EV4DIR, "out_%s.json" % name), encoding="utf-8"))
        res = {}
        for it in d["items"]:
            qu = ev.question_units(it["q"])
            got = []
            for sid in range(corpus.n_sentences):
                n = len(ev.view_of(corpus, sid).units)
                for i in range(n):
                    for j in range(i, min(n, i + 10)):
                        x = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V4)
                        if not x["codes"]:
                            e = x["evidence"] or {}
                            got.append([sid, i, j, x["answer"], x.get("reading") or "base", x.get("rules") or [], e.get("via"), x["source"], x["clause"]])
            res[it["id"]] = got
        out[name] = (d, res)
    return out


def test_t_ev4_05_the_live_v4_sweep_equals_the_stored_one_and_admits_no_unanswerable_question(live_v4):
    for name, (d, res) in live_v4.items():
        stored = {iid: o[V4] for iid, o, _c in d["res"]}
        assert res == stored
        kinds = {it["id"]: it["kind"] for it in d["items"]}
        assert [i for i, k in kinds.items() if k == "unans" and res[i] and (name != "bank6" or i not in ("B6-U07", "B6-U09", "B6-U10") or any("市" in x[3] or "区" in x[3] for x in res[i]))] == []


# ---- T-EV4-06: byte identity under three hash seeds -------------------------------------------------------------------------------------------------
_DET_V4 = r'''
import sys, json, hashlib, csv
sys.path.insert(0, sys.argv[2])
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus
corpus = Corpus.load(open(sys.argv[1], "rb").read())
rows_ = {r["#id"]: r["question"] for r in csv.DictReader(open(sys.argv[3], encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE)}
out = []
for iid, sid, i0, i1 in (("B6-U05", 16, 12, 12), ("B6-U35", 21, 2, 3), ("B6-U36", 37, 2, 3), ("B6-A15", 21, 2, 3), ("B6-A24", 21, 2, 3)):
    qu = ev.question_units(rows_[iid])
    out.append(ev.question_obj(qu, "clause_or_title", ev.EVIDENCE_V4))
    out.append(list(ev.subject_chain(qu)))
    for ver in ("evidence.v3", "evidence.v4"):
        out.append(ev.judge_quote(corpus, qu, "clause_or_title", sid, "WORD", i0, i1, ver))
    out.append(ev.judge_quote(corpus, qu, "clause", sid, "WORD", i0, i1, "evidence.v4"))
out += [ev.v3_rules_digest(), ev.v4_rules_digest()]
print(hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
'''


def test_t_ev4_06_the_v4_cut_the_verdicts_and_the_digests_are_identical_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([PY, "-c", _DET_V4, CORPUS, ROOT, BANK6_TSV], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert p.returncode == 0, p.stderr[-800:]
        digests.add(p.stdout.strip())
    assert len(digests) == 1


def test_t_ev4_07_the_gate_is_pure_and_the_default_waits_for_bank7():
    """OP-PUB-6 (owner): v4 becomes the default only when the held-out bank7 shows 0 unanswerable admissions.  Until that single probe is pinned the default stays v2.  No clock, float,
    subprocess or network in verantyx/loom/evidence.py."""
    assert ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES["v2"] == V2
    src = open(os.path.join(ROOT, "verantyx/loom/evidence.py"), encoding="utf-8").read()
    for bad in ("subprocess", "import time", "import socket", "urllib", "float(", "random", "datetime"):
        assert bad not in src, bad
