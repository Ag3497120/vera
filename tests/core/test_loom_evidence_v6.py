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


FROZEN_V3_RULES_DIGEST = "eca9ccd48aa6ddca8e74f33894acb380cc68667bd34950fd579c4e9bd9cf829d"


FROZEN_V4_RULES_DIGEST = "dae4c99ad17ee178249f83d3ba734cbb48f0ac1c1c336dd4866ecf0e5f915fc6"


FROZEN_V5_RULES_DIGEST = "355722c438c9ce917634a2abcaa3cb9ba785d945988af2e0b4aac9ab38c24ff4"


FROZEN_V6_RULES_DIGEST = "3efb08c90a81338de9c3afaaa7354f0da099af552eef9a41a53e88634dbae83e"


FROZEN_V6_EVIDENCE_SHA = "8b2371fbbf737b7807eb22a941dbcbb402666445cab88357ce5f65a5ccd3c315"


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


def test_t_ev6_01_the_memory_gates_record_their_version_new_runs_get_v6_stored_runs_replay_under_theirs(tmp_path):
    """PUB-M6c (designer decision L-PUB-76; this test said "pinned to v2" before it): the gate of NEW memory answer runs and of the sessions the doors open is `memrecall.MEM_GATE_VERSION`, an explicit
    constant (evidence.v6), not EVIDENCE_LATEST; it is RECORDED in the begin row (`evidence_profile` / `evidence_version` + hook id) and replay reads the record, never a default.  `RECALL_VERSION` (the original
    hook, gate.evidence.v2) and the meaning of `mem.DEFAULT` (the API default of `begin` / `verify_store`: gate.evidence.v2+subject) are FROZEN, and a begin row without a recorded profile is evidence.v2."""
    from verantyx.loom import memanswer, memory as mem, memrecall
    assert memrecall.MEM_GATE_VERSION == V6 and memanswer.ANSWER_EVIDENCE == (V6, "clause") and memanswer.LEGACY_EVIDENCE == (V2, "clause")
    assert memrecall.RECALL_VERSION == V2 and mem.DEFAULT_HOOK_FACTORY is memrecall.GateSubjectSelfQuestion                  # frozen
    assert memrecall.hook_classes(V6)[1].id == "gate.evidence.v6+subject" and mem.HOOKS["gate.evidence.v6+subject"] is memrecall.hook_classes(V6)[1]
    assert mem.latest_hook().evidence_version == V6


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


def test_t_ev6_07_the_gate_is_pure():
    """No clock, float, subprocess or network in verantyx/loom/evidence.py (the whole file, v1..v6)."""
    src = open(os.path.join(ROOT, "verantyx/loom/evidence.py"), encoding="utf-8").read()
    for bad in ("subprocess", "import time", "import socket", "urllib", "float(", "random", "datetime", "os.environ", "import os"):
        assert bad not in src, bad
