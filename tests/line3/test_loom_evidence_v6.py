"""LOOM-evidence-v6 (L-LOOM-226..): evidence.v6 = evidence.v2 PLUS the refusal-only safety rules, and the DEFAULT of the loom.  The owner's choice (ops/decisions/2026-10-06_line3_faithful_build.md,
last section): 「安全の規則だけを v2 に足して既定に」 -- the reach-widening rules of v3..v5 (R1..R7, T1, T2) are NOT in it.  v6 is a PURE FILTER over the v2 verdict: a stretch passes v6 iff it passes
v2 AND every check passes:
  CH   (v4) every noun of the question's subject chain is read in the clause around the answer;
  SU   (v5) the question's subject phrase was read in full, else `subject_unreadable`;
  TW   (v5) a kind word alone is no subject, and the article title stands in for a subject word only as a whole word of it;
  NEG  (new) the answer is not cut off from a negation that follows it in its clause (`answer_polarity_cut`; B8b-A23 「コモロの鉄道はどのような運行状況ですか？」: v2 passes 「運行」 of
       「運行されていない」).
This file pins the freeze (the v3 / v4 / v5 digests unchanged), the default switch points, NEG on the grammar layer's units, the pure-filter property on toy corpora, on a sample of the real corpus and
on the stored v2 passes of the four dev / burnt banks (the CI sweeps ev6/out_*.json when present), a v6 run through the server, the ledger rules (a ledger replays under the version its begin row
records; a ledger without a profile has no gate), the purity and three hash seeds."""
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

V1, V2, V3, V4, V5, V6 = ev.EVIDENCE_V1, ev.EVIDENCE_V2, ev.EVIDENCE_V3, ev.EVIDENCE_V4, ev.EVIDENCE_V5, ev.EVIDENCE_V6
EV5DIR = os.path.join(ROOT, "experiments/line3/loom/ev5")
EV6DIR = os.path.join(ROOT, "experiments/line3/loom/ev6")

# ---- the freeze (L-LOOM-226; recorded BEFORE any CI sweep of v6 and before any new held-out bank) ---------------------------------------------------------
FROZEN_V3_RULES_DIGEST = "eca9ccd48aa6ddca8e74f33894acb380cc68667bd34950fd579c4e9bd9cf829d"
FROZEN_V4_RULES_DIGEST = "dae4c99ad17ee178249f83d3ba734cbb48f0ac1c1c336dd4866ecf0e5f915fc6"
FROZEN_V5_RULES_DIGEST = "355722c438c9ce917634a2abcaa3cb9ba785d945988af2e0b4aac9ab38c24ff4"
FROZEN_V6_RULES_DIGEST = "3efb08c90a81338de9c3afaaa7354f0da099af552eef9a41a53e88634dbae83e"
FROZEN_V6_EVIDENCE_SHA = "8b2371fbbf737b7807eb22a941dbcbb402666445cab88357ce5f65a5ccd3c315"
# The first freeze (WIP 59f8fe40, the file the CI sweeps ran on) differs from this one in ONE string: the sentence shown to the model said "a kind word alone", and test_loom_control asserts that
# "kind" (the bank's label) never reaches the model, so it now says "a category word alone".  No verdict code changed, so the sweeps made by the first file stay valid (L-LOOM-236).
V6_SWEEP_SHAS = (FROZEN_V6_EVIDENCE_SHA, "56b28acc75283c45221b0909815729cd8645c7b1f5f434a93f0de77940287954")
V6_SWEEP_DIGESTS = (FROZEN_V6_RULES_DIGEST, "c79d0d4fed0bc9432fe71b063a6204c471add5605ee376866d8916b9fe8fab8f")


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def _toy(sents):
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "toy.jsonl")
    open(p, "w", encoding="utf-8").write("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": t, "sent": s, "source": "%s#%d" % (t, i)}, ensure_ascii=False) + "\n"
                                                  for i, (t, s) in enumerate(sents)))
    return p


def _passing(c, q, sid, version, scope=ev.SCOPE_TITLE):
    qu = ev.question_units(q)
    v = ev.view_of(c, sid)
    return [v.text[v.spans[i][0]:v.spans[j][1]] for i in range(len(v.units)) for j in range(i, len(v.units)) if not ev.judge_quote(c, qu, scope, sid, "WORD", i, j, version)["codes"]]


def _stretches(c, sid, maxlen=10):
    n = len(ev.view_of(c, sid).units)
    return [(i, j) for i in range(n) for j in range(i, min(n, i + maxlen))]


# ---- T-EV6-01: the freeze ---------------------------------------------------------------------------------------------------------------------------------
def test_t_ev6_01_v3_v4_v5_are_untouched_and_v6_is_frozen():
    assert ev.v3_rules_digest() == FROZEN_V3_RULES_DIGEST
    assert ev.v4_rules_digest() == FROZEN_V4_RULES_DIGEST
    assert ev.v5_rules_digest() == FROZEN_V5_RULES_DIGEST
    assert ev.v6_rules_digest() == FROZEN_V6_RULES_DIGEST
    assert hashlib.sha256(open(os.path.join(ROOT, "verantyx/loom/evidence.py"), "rb").read()).hexdigest() == FROZEN_V6_EVIDENCE_SHA
    assert ev.V6_RULE_IDS == ("CH", "SU", "TW", "NEG") and ev.V6_OFF == frozenset()
    assert not set(ev.V6_RULE_IDS) & {"R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7", "T1", "T2"}              # no reach-widening rule is in v6
    assert "kind" not in ev.V6_RULE_SENTENCE and "kind" not in ev.EVIDENCE_V6 and "answer_polarity_cut" in ev.CODES      # the model never sees the bank's `kind` label (test_loom_control) and "subject_unreadable" in ev.CODES
    assert ev.NEG_UNITS == frozenset({"ない", "なかっ", "なく", "なけれ", "ず", "ぬ", "ざる", "ざれ"}) and ev.NEG_PAIRS == (("ませ", "ん"),)


def test_t_ev6_01_v6_is_selectable_and_the_default_everywhere_v2_is_the_default_today(tmp_path, monkeypatch):
    import inspect
    from verantyx import cli
    from verantyx.loom import isolate
    from verantyx.loom import mcp as lm
    from verantyx.loom.ops import EVIDENCE_RULE_V2, EVIDENCE_RULE_V6, EVIDENCE_RULES
    assert ev.EVIDENCE_VERSIONS == (V1, V2, V3, V4, V5, V6) and ev.EVIDENCE_LATEST == V6 and ev.PROFILE_NAMES["v6"] == V6 and ev.PROFILE_NAMES["v2"] == V2
    assert inspect.signature(ev.judge_quote).parameters["version"].default == V6                      # EVIDENCE_LATEST
    assert EVIDENCE_RULES[V6] == EVIDENCE_RULE_V6 == EVIDENCE_RULE_V2 + " " + ev.V6_RULE_SENTENCE
    t = [{"task_id": "x", "text": "花園町駅の隣駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": CORPUS}]
    assert LoomServer(t, str(tmp_path / "a"), ()).evidence_profile == (V6, "clause_or_title")                 # LoomServer
    assert LoomServer(t, str(tmp_path / "b"), (), evidence="v2").evidence_profile == (V2, "clause_or_title")   # v2 stays selectable
    assert LoomServer(t, str(tmp_path / "c"), (), evidence="v6").evidence_profile == (V6, "clause_or_title")
    with pytest.raises(ValueError):
        LoomServer(t, str(tmp_path / "d"), (), evidence="v7")
    assert LoomServer(t, str(tmp_path / "e"), (), evidence="off").evidence_profile is None
    for fn in (lm.LoomServer.__init__, lm.LoomServer.from_file, lm.build, lm.serve, isolate.serve_isolated):   # the other signatures of the server door
        assert inspect.signature(fn).parameters["evidence"].default == "v6", fn
    seen = []
    monkeypatch.setattr(lm, "serve", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r")]) == 0              # CLI
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r"), "--evidence", "v2"]) == 0
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r"), "--evidence", "v6"]) == 0
    assert [a[4] for a in seen] == ["v6", "v2", "v6"]
    for f in ("run_bank.py", "run_reach.py"):                                                                  # the bank runners
        src = open(os.path.join(ROOT, "experiments/line3/loom", f), encoding="utf-8").read()
        assert '"--evidence", default="v6"' in src and '"v6"' in src, f
    src = open(os.path.join(ROOT, "experiments/line3/loom/harness.py"), encoding="utf-8").read()                # the harness: None = v6 for the api driver
    assert '("v6" if driver == "api" else "off")' in src


def test_t_ev6_01_the_memory_gates_are_pinned_to_v2_not_to_the_latest():
    """memanswer.ANSWER_EVIDENCE and memrecall.RECALL_VERSION name evidence.v2 explicitly: they do NOT take EVIDENCE_LATEST, and their replay does not read the recorded version
    (L-LOOM-226 open point 1).  The stored memory stores / answer runs therefore replay exactly as before; switching them is a separate step with new hook ids."""
    from verantyx.loom import memanswer, memrecall
    assert memanswer.ANSWER_EVIDENCE == (V2, "clause") and memrecall.RECALL_VERSION == V2


# ---- T-EV6-02: NEG, on the grammar layer's units ----------------------------------------------------------------------------------------------------------
NEG_CASES = [("鉄道は運行されていない。", "ない"), ("鉄道は運行されなかった。", "なかっ"), ("鉄道は運行されず、貨物のみである。", "ず"), ("鉄道は運行されません。", "ません"), ("鉄道は運行されませんでした。", "ません"),
             ("鉄道は運行されぬ。", "ぬ"), ("鉄道は運行ではなく、廃止である。", "なく"), ("鉄道は運行されたが現在はない。", "ない"), ("鉄道は運行されていない（廃止）。", "ない")]
POS_CASES = ["鉄道は運行され、乗客は少なくない。", "鉄道は運行ないし廃止された。", "鉄道は運行された。", "ナイル川の鉄道は運行された。", "鉄道は運行され、廃止されていない。", "鉄道は運行され、現在もない。"]


def test_t_ev6_02_neg_reads_the_ending_after_the_answer_up_to_the_clause_end():
    c = Corpus.load(open(_toy([("鉄道", s) for s, _ in NEG_CASES] + [("鉄道", s) for s in POS_CASES]), "rb").read())
    for sid, (s, neg) in enumerate(NEG_CASES):
        v = ev.view_of(c, sid)
        i = v.units.index("運行")
        got = ev._neg_after(v, v.spans[i][1])
        assert got is not None and got[0] == neg, (s, got)
        assert v.text[v.spans[i][1]:got[1]].endswith(neg[-1])                                                  # the tail is the text from the answer's end to the ending's end
    for k, s in enumerate(POS_CASES):
        v = ev.view_of(c, len(NEG_CASES) + k)
        i = v.units.index("運行")
        assert ev._neg_after(v, v.spans[i][1]) is None, s                                                      # a comma / 。 ends the clause; 「ないし」 is one word, not 「ない」+「し」
    v = ev.view_of(c, 0)                                                                                       # 運行されていない: an ending inside the answer is not seen
    assert ev._neg_after(v, len(v.text)) is None


def test_t_ev6_02_neg_refuses_a_cut_answer_with_its_own_code_and_message_and_only_where_v2_passes():
    c = Corpus.load(open(_toy([("コモロの鉄道", "コモロの鉄道は運行されていない。"), ("コモロの鉄道", "コモロの鉄道は運行され、乗客は少なくない。")]), "rb").read())
    q = "コモロの鉄道はどのような運行状況ですか？"
    assert _passing(c, q, 0, V2) == ["運行"] and _passing(c, q, 0, V6) == []
    assert _passing(c, q, 1, V2) == ["運行"] and _passing(c, q, 1, V6) == ["運行"]                              # the comma ends the clause: nothing follows in it
    qu = ev.question_units(q)
    v = ev.view_of(c, 0)
    i = v.units.index("運行")
    r = ev.judge_quote(c, qu, ev.SCOPE_TITLE, 0, "WORD", i, i, V6)
    assert r["codes"] == ["answer_polarity_cut"] and r["evidence"] is None and r["answer"] == "運行" and r["failures"][0]["negation"] == "ない"
    assert "されていない" in r["messages"][0] and "negation" in r["messages"][0]
    r2 = ev.judge_quote(c, qu, ev.SCOPE_TITLE, 0, "WORD", i, i, V2)
    assert r2["codes"] == [] and r2["evidence"] is not None                                                    # v2 passes it: that is the finding
    r6 = ev._judge_v6(c, qu, ev.SCOPE_TITLE, 0, "WORD", i, i, frozenset({"NEG"}))                              # NEG off (tests only): the v2 verdict
    assert r6["codes"] == [] and r6["evidence"] == r2["evidence"]


def test_t_ev6_02_b8b_a23_on_the_real_corpus(corpus):
    """The bank8 case: sentence 411 「2025年現在、鉄道は運行されていない。」: v2 passes 「運行」 alone, v6 refuses it; no stretch of the sentence passes v6.  B8b-A28 (「…の中央部に位置」) is not a
    polarity case and stays admitted (L-LOOM-226 open point 3)."""
    q = "2025年現在、コモロの鉄道はどのような運行状況ですか？"
    assert _passing(corpus, q, 411, V2) == ["運行"] and _passing(corpus, q, 411, V6) == []
    r = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 411, "WORD", 4, 4, V6)
    assert r["codes"] == ["answer_polarity_cut"] and "されていない" in r["messages"][0]
    q28 = "アラローはマヨルカ島のどのあたりに位置していますか？"
    assert _passing(corpus, q28, 441, V6) == _passing(corpus, q28, 441, V2) and "中央部" in _passing(corpus, q28, 441, V6)


# ---- T-EV6-03: CH, SU, TW are the v4 / v5 code paths on top of the v2 verdict -------------------------------------------------------------------------------
def test_t_ev6_03_ch_su_and_tw_refuse_what_v2_admitted(corpus):
    ch = ev.judge_quote(corpus, ev.question_units("花園町駅の隣駅の駅番号は何ですか？"), ev.SCOPE_TITLE, 21, "WORD", 2, 3, V6)                  # B6-U35: Y17, a statement about the station itself
    assert ev.judge_quote(corpus, ev.question_units("花園町駅の隣駅の駅番号は何ですか？"), ev.SCOPE_TITLE, 21, "WORD", 2, 3, V2)["codes"] == []
    assert ch["codes"] == ["no_subject"] and ch["failures"][0]["subject"] == "隣駅" and ch["chain"] == ["花園町駅", "隣駅"]
    v4 = ev.judge_quote(corpus, ev.question_units("花園町駅の隣駅の駅番号は何ですか？"), ev.SCOPE_TITLE, 21, "WORD", 2, 3, V4)
    assert v4["codes"] == ch["codes"] and v4["messages"] == ch["messages"]                                                                      # the very message of v4's chain rule
    qu = ev.question_units("ネノの属するネノ県の人口は何人ですか？")                                                                          # B7-U43
    su = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 504, "WORD", 6, 8, V6)
    assert ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 504, "WORD", 6, 8, V2)["codes"] == []
    assert "subject_unreadable" in su["codes"] and "question_has_no_subject" in su["codes"] and su["evidence"] is None
    assert any(f.get("unread") == ["ネノ", "ネノ"] for f in su["failures"])
    for q in ("ネノの属するネノ県の人口は何人ですか？",):                                                                                        # SU refuses EVERY stretch of the question
        for (i, j) in _stretches(corpus, 504, 3):
            assert "subject_unreadable" in ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 504, "WORD", i, j, V6)["codes"]


def test_t_ev6_03_tw_from_both_sides_on_a_toy_corpus():
    c = Corpus.load(open(_toy([("テレゴ県", "人口は20万人である。"), ("花園町駅", "駅番号はY17である。"), ("六日町駅", "駅番号はY17である。"), ("テレゴ山", "標高は3776メートルである。")]), "rb").read())
    assert _passing(c, "県の人口は何人ですか", 0, V2) == ["20万人"] and _passing(c, "県の人口は何人ですか", 0, V6) == []                    # a kind word alone is no subject
    assert _passing(c, "テレゴ県の人口は何人ですか", 0, V6) == ["20万人"] and _passing(c, "花園町駅の駅番号は何ですか", 1, V6) == ["Y17"]  # the whole title word passes
    assert _passing(c, "六日町駅の駅番号は何ですか", 2, V6) == ["Y17"]
    for q in ("六の駅番号は何ですか", "日町駅の駅番号は何ですか"):                                                                             # a piece of the title is a containment
        assert _passing(c, q, 2, V2) == ["Y17"] and _passing(c, q, 2, V6) == []
    assert _passing(c, "六の駅番号は何ですか", 2, V6, ev.SCOPE_CLAUSE) == _passing(c, "六の駅番号は何ですか", 2, V2, ev.SCOPE_CLAUSE)           # the clause scope is not touched by TW
    assert _passing(c, "テレゴ山の標高は何メートルですか", 3, V6) == _passing(c, "テレゴ山の標高は何メートルですか", 3, V2) == ["3776メートル"]


def test_t_ev6_03_the_begin_object():
    qu = ev.question_units("ネノの属するネノ県の人口は何人ですか？")
    o = ev.begin_question_obj6(qu, ev.SCOPE_TITLE, V6)
    assert o == dict(qu.to_obj(ev.SCOPE_TITLE, V6), chain=["県"], unread=["ネノ", "ネノ"]) and o["evidence"] == V6
    q2 = ev.question_units("花園町駅の隣駅の駅番号は何ですか？")
    assert ev.begin_question_obj6(q2, ev.SCOPE_TITLE, V6)["chain"] == ["花園町駅", "隣駅"] and ev.begin_question_obj6(q2, ev.SCOPE_TITLE, V6)["unread"] == []
    for ver in (V1, V2, V3, V4, V5):                                                                                                      # the older objects are exactly what they were
        assert ev.begin_question_obj6(qu, ev.SCOPE_TITLE, ver) == ev.begin_question_obj(qu, ev.SCOPE_TITLE, ver)


# ---- T-EV6-04: the pure-filter property --------------------------------------------------------------------------------------------------------------------
TOY = [("テレゴ県", "人口は20万人である。"), ("花園町駅", "花園町駅の駅番号はY17である。"), ("六日町駅", "駅番号はY17である。"), ("テレゴ山", "標高は3776メートルである。"),
       ("花園町駅", "花園町駅の隣駅の駅番号はOR08である。"), ("青葉堂", "青葉堂は松風庵ともいう。"), ("コモロの鉄道", "コモロの鉄道は運行されていない。"), ("コモロの鉄道", "コモロの鉄道は運行され、乗客は少なくない。"),
       ("A社", "A社の設立は1990年に行われ、廃止されていない。"), ("B社", "B社の本社は大阪には置かれませんでした。"), ("C社", "C社の本社は京都にあり、神戸にはない。"), ("D社", "D社の社長は田中ではなく鈴木である。")]
TOY_QS = ["県の人口は何人ですか", "テレゴ県の人口は何人ですか", "ネノの属するネノ県の人口は何人ですか", "六の駅番号は何ですか", "花園町駅の隣駅の駅番号は何ですか", "花園町駅の駅番号は何ですか", "青葉堂の別名は何ですか",
          "何年に設立されましたか", "テレゴ山の標高は何メートルですか", "コモロの鉄道はどのような運行状況ですか", "A社の設立は何年ですか", "B社の本社はどこに置かれましたか", "C社の本社はどこにありますか",
          "D社の社長は誰ですか"]


def test_t_ev6_04_v6_passes_a_subset_of_v2_on_the_toy_corpora_and_never_raises():
    c = Corpus.load(open(_toy(TOY), "rb").read())
    n = n6 = 0
    for q in TOY_QS:
        qu = ev.question_units(q)
        for sid in range(len(TOY)):
            k = len(ev.view_of(c, sid).units)
            pairs = [(i, j) for i in range(k) for j in range(i, k)] + [(-1, 0), (0, k), (k, k), (2, 1), (-1, -1)]            # every stretch of the sentence, and some outside it
            for scope in (ev.SCOPE_TITLE, ev.SCOPE_CLAUSE):
                for i, j in pairs:
                    r6 = ev.judge_quote(c, qu, scope, sid, "WORD", i, j, V6)
                    n += 1
                    assert isinstance(r6["codes"], list) and (r6["evidence"] is None) == bool(r6["codes"])
                    if not (0 <= i <= j < k):
                        assert "answer_not_word_aligned" in r6["codes"]
                        continue
                    r2 = ev.judge_quote(c, qu, scope, sid, "WORD", i, j, V2)
                    if r6["codes"] == []:
                        n6 += 1
                        assert r2["codes"] == [] and r6["evidence"] == r2["evidence"] and r6["answer"] == r2["answer"] and r6["clause"] == r2["clause"]         # same verdict, same evidence
                    assert set(r2["codes"]) <= set(r6["codes"])                                                                                             # a refusal stays a refusal, v2's codes stay
                    off = ev._judge_v6(c, qu, scope, sid, "WORD", i, j, frozenset(ev.V6_RULE_IDS))
                    assert off["codes"] == r2["codes"] and off["messages"] == r2["messages"] and off["evidence"] == r2["evidence"]                          # every rule off = v2
    assert n > 4000 and n6 > 0


def test_t_ev6_04_v6_passes_a_subset_of_v2_on_a_sample_of_the_real_corpus(corpus):
    qs = ["花園町駅の隣駅の駅番号は何ですか？", "コモロの鉄道はどのような運行状況ですか？", "ネノの属するネノ県の人口は何人ですか？", "唯物史観を唱えた人物は誰ですか", "フェミニズムは別名で何と呼ばれていますか？",
          "千葉神社の旧社格は何ですか", "サンゴーカメラは何年に設立されましたか"]
    sids = list(range(0, corpus.n_sentences, 37)) + [21, 37, 411, 441, 504]
    n = 0
    for q in qs:
        qu = ev.question_units(q)
        for sid in sids:
            for (i, j) in _stretches(corpus, sid, 5):
                n += 1
                r6 = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V6)
                if not r6["codes"]:
                    assert ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V2)["codes"] == []
    assert n > 3000


def _derived_summary(tmp_path, name):
    """v6 of a stored ev5 sweep: the stored v2 passes of `name` (title scope, 1..10 WORD units, the product gate) filtered through the live v6 gate (a pure filter: nothing else can pass).
    Returns ev6/report.py's summary and subset() of a sweep-shaped output written to tmp_path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ev6_report", os.path.join(EV6DIR, "report.py"))
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    c = Corpus.load(open(CORPUS, "rb").read())
    d = json.load(open(os.path.join(EV5DIR, "out_%s.json" % name), encoding="utf-8"))
    res = []
    for iid, out, chain in d["res"]:
        qu = ev.question_units(next(it["q"] for it in d["items"] if it["id"] == iid))
        o = {V2: out[V2], "_lost": [], "_violations": []}
        o[V6] = []
        for x in out[V2]:
            r = ev.judge_quote(c, qu, ev.SCOPE_TITLE, x[0], "WORD", x[1], x[2], V6)
            if r["codes"]:
                o["_lost"].append([x[0], x[1], x[2], x[3], r["codes"], r["messages"][0]])
            else:
                o[V6].append(x)
        for k in R.VERS[2:]:
            o[k] = o[V6]
        res.append([iid, o, chain])
    d2 = dict(d, res=res, v6_digest=ev.v6_rules_digest())
    json.dump(d2, open(tmp_path / ("out_%s.json" % name), "w"), ensure_ascii=False)
    R.HERE = str(tmp_path)
    return R


def test_t_ev6_04_the_stored_v2_passes_of_the_four_sets_filtered_through_v6(tmp_path):
    """The numbers, derived offline and exactly (a pure filter can only drop stretches of the stored v2 passes of experiments/line3/loom/ev5/out_*.json; the CI sweep ev6/sweep.py then
    recomputes them over every stretch).  dev129 bank2 + bank4 (69 + 60), bank6 (26 + 34), bank7 (32 + 47), bank8 (35 + 50)."""
    got = {}
    for name in ("dev129", "bank6", "bank7", "bank8"):
        if name == "bank8" and not os.path.exists(os.path.join(EV5DIR, "out_bank8.json")):
            pytest.skip("out_bank8.json absent")
        R = _derived_summary(tmp_path, name)
        s = R.summary(name)
        assert R.subset(name)["violations"] == []
        got[name] = {v: (len(s[v]["reach"]), s[v]["wrong"], s[v]["unans"]) for v in (V2, V6)}
        got[name]["lost"] = sorted((i, "+".join(c)) for i, _k, _q, _a, c in R.lost(name))
    assert got["dev129"][V2] == got["dev129"][V6] == (10, [], []) and got["dev129"]["lost"] == []                                       # the dev set: v6 changes nothing
    assert got["bank6"][V2] == (3, ["B6-A05", "B6-A20", "B6-A27"], ["B6-U35", "B6-U36"]) and got["bank6"][V6] == (3, ["B6-A05", "B6-A20", "B6-A27"], [])
    assert got["bank6"]["lost"] == [("B6-U35", "no_subject"), ("B6-U36", "no_subject")]                                                  # CH closes both
    assert got["bank7"][V2] == (1, [], ["B7-U43"]) and got["bank7"][V6] == (1, [], [])
    assert got["bank7"]["lost"] == [("B7-U43", "subject_unreadable+question_has_no_subject+no_subject")]                                # SU / TW close it
    assert got["bank8"][V2] == (3, ["B8b-A23", "B8b-A28"], []) and got["bank8"][V6] == (3, ["B8b-A28"], [])
    assert got["bank8"]["lost"] == [("B8b-A23", "answer_polarity_cut")]                                                                  # NEG closes it; A28 is not a polarity case


def test_t_ev6_04_the_ci_sweeps_when_present_are_pure_filters_made_by_the_frozen_file():
    """experiments/line3/loom/ev6/out_{dev129,bank6,bank7,bank8}.json are produced on CI by ev6/sweep.py (every stretch of 1..10 WORD units of every sentence, v2 and v6 and four ablations)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("ev6_report", os.path.join(EV6DIR, "report.py"))
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    present = [n for n in ("dev129", "bank6", "bank7", "bank8") if os.path.exists(os.path.join(EV6DIR, "out_%s.json" % n))]
    if not present:
        pytest.skip("the CI sweeps ev6/out_*.json are not committed yet")
    for name in present:
        d = json.load(open(os.path.join(EV6DIR, "out_%s.json" % name), encoding="utf-8"))
        assert d["evidence_sha"] in V6_SWEEP_SHAS and d["v6_digest"] in V6_SWEEP_DIGESTS
        sb = R.subset(name)
        assert sb["violations"] == [] and sb["swept_violations"] == 0 and sb["n_v6"] <= sb["n_v2"]
        s = R.summary(name)
        for v in R.VERS[1:]:
            assert set(s[v]["reach"]) <= set(s[V2]["reach"]) and set(s[v]["unans"]) <= set(s[V2]["unans"]) and set(s[v]["wrong"]) <= set(s[V2]["wrong"])


# ---- T-EV6-05: a v6 run through the server; the ledger rules ------------------------------------------------------------------------------------------------
def _reseal(d, edit):
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


def test_t_ev6_05_a_v6_run_records_its_profile_refuses_a_cut_answer_and_replays_identically(tmp_path):
    p = _toy([("コモロの鉄道", "コモロの鉄道は運行されていない。"), ("花園町駅", "花園町駅の駅番号はY17である。")])
    t = [{"task_id": "toy/neg", "text": "コモロの鉄道はどのような運行状況ですか？", "lang": "prose", "mode": "record_only", "corpus": p},
         {"task_id": "toy/ok", "text": "花園町駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": p}]

    def run(version, name, task, sid, first, last):
        srv = LoomServer(t, str(tmp_path / name), (), **({} if version is None else {"evidence": version}))
        b = srv.begin(task, "t", "x")
        assert srv.call("weave_span", {"run_id": "x", "sid": sid, "tier": "WORD", "first": first, "last": last})["ok"]
        return b, srv.call("emit", {"run_id": "x"}), tmp_path / name / "x"
    b6, e6, d6 = run(None, "dflt", "toy/ok", 1, "Y", "17")                                                      # no evidence argument: the DEFAULT is v6
    assert b6["evidence_profile"] == {"version": V6, "subject_scope": "clause_or_title"} and b6["question"]["evidence"] == V6 and b6["question"]["unread"] == [] and b6["question"]["chain"] == ["花園町駅"]
    from verantyx.loom.ops import EVIDENCE_RULE_V6
    assert b6["rules"]["evidence"] == EVIDENCE_RULE_V6
    assert e6["ok"] and e6["text"] == "Y17" and e6["ev"] == V6
    assert lg.verify(d6)["status"] == "OK" and lg.verify(d6)["replay"]["status"] == "IDENTICAL"
    _, e2n, d2n = run("v2", "v2neg", "toy/neg", 0, "運行", "運行")
    assert e2n["ok"] and e2n["text"] == "運行"                                                                  # v2 emits the cut answer ...
    _, e6n, d6n = run(None, "v6neg", "toy/neg", 0, "運行", "運行")
    assert e6n["ok"] is False and e6n["refusal"] == "no_evidence"                                               # ... v6 refuses it, with its own typed code
    rj = [r for r in rows(d6n) if r["op"] == "emit"][0]["result"]
    assert "answer_polarity_cut" in json.dumps(rj, ensure_ascii=False)
    for d in (d2n, d6n):
        assert lg.verify(d)["status"] == "OK" and lg.verify(d)["replay"]["status"] == "IDENTICAL"             # a v2 ledger replays under v2 although the default is v6
    assert rows(d2n)[0]["result"]["evidence_profile"]["version"] == V2
    for d, to in ((d6, V2), (d2n, V6)):                                                                          # a forged relabel is a replay difference
        _reseal(d, lambda rs, to=to: rs[0]["result"]["evidence_profile"].update(version=to))
        assert lg.verify_chain(d)["status"] == "OK" and lg.verify(d)["status"] == "REPLAY_DIFFERS"


def test_t_ev6_05_a_ledger_without_a_profile_has_no_gate_and_does_not_change_meaning(tmp_path):
    """Every ledger either records its evidence profile (replayed by it) or records none (no gate at all): the new default changes neither.  `evidence="off"` writes the second kind."""
    p = _toy([("コモロの鉄道", "コモロの鉄道は運行されていない。")])
    t = [{"task_id": "toy/neg", "text": "コモロの鉄道はどのような運行状況ですか？", "lang": "prose", "mode": "record_only", "corpus": p}]
    srv = LoomServer(t, str(tmp_path / "off"), (), evidence="off")
    b = srv.begin("toy/neg", "t", "x")
    assert "evidence_profile" not in b and "question" not in b and "evidence" not in b["rules"]
    assert srv.call("weave_span", {"run_id": "x", "sid": 0, "tier": "WORD", "first": "運行", "last": "運行"})["ok"]
    e = srv.call("emit", {"run_id": "x"})
    assert e["ok"] and e["text"] == "運行" and "ev" not in e                                                   # no gate: the cut answer goes out, as it always did without a gate
    d = tmp_path / "off" / "x"
    assert lg.verify(d)["status"] == "OK" and lg.verify(d)["replay"]["status"] == "IDENTICAL"
    rep = lg.replay(d)
    assert rep.status == "IDENTICAL" and rep.run.evidence is None                                                # replay does not invent a profile
    _reseal(d, lambda rs: rs[0]["result"].update(evidence_profile={"version": "evidence.v9", "subject_scope": "clause_or_title"}))
    assert lg.replay(d).status == "INPUTS" and lg.replay(d).mismatch == "evidence_profile_unknown"             # an unknown recorded version is refused, never mapped to a default


# ---- T-EV6-06: byte identity under three hash seeds ------------------------------------------------------------------------------------------------------------
_DET_V6 = r'''
import sys, json, hashlib
sys.path.insert(0, sys.argv[2])
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus
corpus = Corpus.load(open(sys.argv[1], "rb").read())
out = []
for q, sid, i0, i1 in (("2025年現在、コモロの鉄道はどのような運行状況ですか？", 411, 4, 4), ("花園町駅の隣駅の駅番号は何ですか？", 21, 2, 3), ("ネノの属するネノ県の人口は何人ですか？", 504, 6, 8),
                       ("アラローはマヨルカ島のどのあたりに位置していますか？", 441, 4, 5), ("県の人口は何人ですか", 504, 6, 8)):
    qu = ev.question_units(q)
    out.append(ev.begin_question_obj6(qu, "clause_or_title", ev.EVIDENCE_V6))
    for ver in ("evidence.v2", "evidence.v6"):
        out.append(ev.judge_quote(corpus, qu, "clause_or_title", sid, "WORD", i0, i1, ver))
    out.append(ev.judge_quote(corpus, qu, "clause", sid, "WORD", i0, i1, "evidence.v6"))
    v = ev.view_of(corpus, sid)
    out.append([ev._neg_after(v, e) for e in sorted({s[1] for s in v.spans})])
out += [ev.v3_rules_digest(), ev.v4_rules_digest(), ev.v5_rules_digest(), ev.v6_rules_digest()]
print(hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
'''


def test_t_ev6_06_the_v6_verdicts_the_neg_reading_and_the_digests_are_identical_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([PY, "-c", _DET_V6, CORPUS, ROOT], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert p.returncode == 0, p.stderr[-800:]
        digests.add(p.stdout.strip())
    assert len(digests) == 1


# ---- T-EV6-07: purity -------------------------------------------------------------------------------------------------------------------------------------
def test_t_ev6_07_the_gate_is_pure():
    """No clock, float, subprocess or network in verantyx/loom/evidence.py (the whole file, v1..v6)."""
    src = open(os.path.join(ROOT, "verantyx/loom/evidence.py"), encoding="utf-8").read()
    for bad in ("subprocess", "import time", "import socket", "urllib", "float(", "random", "datetime", "os.environ", "import os"):
        assert bad not in src, bad
