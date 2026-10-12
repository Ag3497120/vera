"""LOOM-span tests: `weave_span` (span weaving), `drop`, the rule version `wv`, the LEGACY `weave_sentence` replay, notes after a weave, the exact-match
scoring (docs/LINE3_LOOM_DESIGN.md 4, 10.1; L-LOOM-130..).

weave_span(sid, tier, from, to) = ONE op: the stretch of a corpus sentence from unit `from` to unit `to` becomes a CHAIN of crosses whose read-out is
that stretch word for word (a unit followed by an arm particle goes on that arm of the cross whose centre is the very next unit; touching units are
one-unit crosses; a unit followed by は is a topic centre; anything the loom cannot write between two units, or a nested AのBのC, is refused
`span_inexpressible` and nothing changes).  The toy corpus is written to a temp file, so most tests do not depend on the bank; the old-ledger tests read
the stored runs (runs_h55, runs_h55b, runs_h55c, runs_h55d, baseline_scripted) with the real corpus.
"""
import asyncio
import hashlib
import itertools
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from verantyx.line3 import space as sp
from verantyx.loom import driver as drv
from verantyx.loom import ledger as lg
from verantyx.loom import mcp as lm
from verantyx.loom import notes as notelib
from verantyx.loom import ops as opsmod
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from verantyx.loom.ops import CLASS_OF, LEGACY_OPS, MODEL_OPS, STATE_CHANGING, WEAVE_SPAN_WV, Run
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo_batch
from verantyx.loom.state import CAPS
from loom_common import CORPUS, PY, ROOT, rows

SENTS = ["東京は日本の首都です。",                     # 0  東京(は) 日本(の) 首都
         "日本の首都は東京です。",                     # 1  日本(の) 首都(は) 東京
         "ハッシュ表ともいう。",                       # 2  ハッシュ() 表(とも) いう
         "彼が東京で日本の首都を見た。",               # 3  東京(で) 日本(の) 首都(を)
         "日本が勝った。",                             # 4  日本(が) 勝っ
         "東京の大学に通う学生と先生がいる。",         # 5  東京(の) 大学(に) 通う() 学生(と) 先生(が)
         "日本の大学の学生の先生の家の本。",           # 6  日本 大学 学生 先生 家 (all の) 本
         "日本の大学の学生。",                         # 7  日本(の) 大学(の) 学生
         "大学で学生が先生と本を読む。",               # 8  大学(で) 学生(が) 先生(と) 本(を) 読む
         "カール・マルクスが唱えた。",                 # 9  カール(・) マルクス(が) 唱え
         "1981年に設立された。",                       # 10 1981 年 (に) 設立
         "日本は日本の首都。",                         # 11 日本(は) 日本(の) 首都: a unit twice
         "ハッシュ表という名前。"]                     # 12 ハッシュ() 表(という) 名前
ARM_OF = {"の": "+x", "に": "-x", "で": "+y", "と": "-y", "を": "+z", "が": "-z"}


@pytest.fixture(scope="module")
def toy(tmp_path_factory):
    d = tmp_path_factory.mktemp("toy")
    p = d / "toy.jsonl"
    rs = [{"sha": hashlib.sha256(s.encode()).hexdigest(), "title": "t%d" % i, "sent": s, "source": "t%d#0" % i} for i, s in enumerate(SENTS)]
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs), encoding="utf-8")
    return str(p)


def toy_tasks(toy):
    def t(task_id, mode, tiers):
        return {"task_id": task_id, "text": "織れ", "lang": "prose", "mode": mode, "tiers": tiers, "corpus": toy}
    return [t("toy/ca", "constructed_allowed", ["WORD"]), t("toy/ro", "record_only", ["RUN", "WORD", "CHAR"]),
            {"task_id": "toy/code", "text": "書け", "lang": "code", "mode": "constructed_allowed", "corpus": toy}]


def srv_of(toy, tmp_path, **kw):
    return LoomServer(toy_tasks(toy), str(tmp_path / "runs"), (), **kw)


def started(toy, tmp_path, task_id="toy/ro", run_id="r1", **kw):
    srv = srv_of(toy, tmp_path, **kw)
    w = ScriptedWeaver(srv, task_id, "test-weaver", run_id)
    assert w.begin()["ok"]
    return srv, w


def _bare(state):
    o = state.to_obj()
    o.pop("counters")
    o.pop("guards")
    return json.dumps(o, sort_keys=True)


def span(w, sid, f, t, tier="WORD"):
    return w.call("weave_span", sid=sid, tier=tier, **{"from": f, "to": t})


def refused(res, type_):
    assert res["ok"] is False and res["refusal"] == type_, res
    return res["detail"]


def shape(srv, w):
    """The state without the counters: what a refused call must leave as it was."""
    o = srv.runs[w.run_id].run.state.to_obj()
    o.pop("counters")
    o.pop("guards")
    return json.dumps(o, sort_keys=True)


# ---------------------------------------------------------------------------------------------------------------
# the worked examples: the read-out is the stretch, word for word
# ---------------------------------------------------------------------------------------------------------------
def test_the_nihon_no_shuto_chain_from_東京は日本の首都です(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    r = span(w, 0, "日本", "首都")
    assert r["ok"] and r["wv"] == "weave_span.v2" and (r["sid"], r["tier"], r["from"], r["to"]) == (0, "WORD", 1, 2)
    assert r["text"] == "日本の首都" and r["thread"] == ["c1"]
    [c] = r["crosses"]
    assert c["cid"] == "c1" and c["L"] == 2 and c["topic"] is False and c["centre"]["surface"] == "首都"
    assert [(s["seat"], s["surface"], s["particle"]) for s in c["seated"]] == [("+x:0", "日本", "の")]       # 日本 on the の arm, next to its centre
    st = srv.runs[w.run_id].run.state
    # units are made for the STRETCH only (the sentence's 東京 is not a unit of this run), in sentence order, as record units like `add` makes them
    assert [(u.uid, u.surface, u.kind, u.tier) for u in st.units.values()] == [("u1", "日本", "record", "WORD"), ("u2", "首都", "record", "WORD")]
    assert st.crosses["c1"].linked and st.pool() == [] and st.counters["constructed"] == 0
    rd = w.call("read")
    assert rd["text"] == "日本の首都" and rd["refusals"] == [] and [e["status"] for e in rd["stability"]] == ["stable"]
    e = w.call("emit")
    assert e["ok"] and e["text"] == "日本の首都"
    d = tmp_path / "runs" / "r1"
    assert lg.verify(d, corpus_path=toy)["status"] == "OK"


def test_the_whole_sentence_is_a_two_cross_chain_with_a_topic_centre(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    r = span(w, 0, 0, 2)
    assert r["ok"] and r["text"] == "東京は日本の首都"
    c1, c2 = r["crosses"]
    assert (c1["centre"]["surface"], c1["topic"], c1["L"], c1["seated"]) == ("東京", True, 1, [])
    assert (c2["centre"]["surface"], c2["topic"], c2["L"], [s["surface"] for s in c2["seated"]]) == ("首都", False, 2, ["日本"])
    assert r["thread"] == ["c1", "c2"]
    assert w.call("read")["text"] == "東京は日本の首都"
    e = w.call("emit")
    assert e["ok"] and e["text"] == "東京は日本の首都"


def test_touching_units_become_one_unit_crosses_linked_in_order(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    r = span(w, 2, "ハッシュ", "表")                                              # ハッシュ表: no particle between the units
    assert r["ok"] and r["text"] == "ハッシュ表" and r["thread"] == ["c1", "c2"]
    assert [(c["centre"]["surface"], c["L"], c["seated"], c["topic"]) for c in r["crosses"]] == [("ハッシュ", 1, [], False), ("表", 1, [], False)]
    assert w.call("emit")["text"] == "ハッシュ表"
    # 「カール・マルクス」: the 「・」 between the units is not a letter, the loom writes none, the T9 normaliser ignores it (kept apart from the words)
    srv2, w2 = started(toy, tmp_path / "b")
    r2 = span(w2, 9, 0, 1)
    assert r2["ok"] and r2["text"] == "カールマルクス" and len(r2["crosses"]) == 2
    assert w2.call("emit")["text"] == "カールマルクス"
    # 「1981年」: a number and its counter
    srv3, w3 = started(toy, tmp_path / "c")
    r3 = span(w3, 10, 0, 1)
    assert r3["ok"] and r3["text"] == "1981年" and [c["centre"]["surface"] for c in r3["crosses"]] == ["1981", "年"]
    assert w3.call("emit")["text"] == "1981年"


def test_a_chain_AのBのC_cannot_be_written_and_is_refused_with_nothing_changed(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    base = shape(srv, w)
    d = refused(span(w, 7, 0, 2), "span_inexpressible")                           # 日本の大学の学生
    assert d == {"reason": "nested_particle_chain", "units": ["日本", "大学", "学生"], "particles": ["の", "の"]}
    d = refused(span(w, 3, 0, 2), "span_inexpressible")                           # 東京で日本の首都: で then の: the middle unit would be an arm unit AND a centre
    assert d["reason"] == "nested_particle_chain" and d["particles"] == ["で", "の"]
    refused(span(w, 6, 0, 5), "span_inexpressible")                               # five の in a row
    assert shape(srv, w) == base
    # the two halves are fine one at a time, and the second one can reuse the unit the first one ends on only as a new unit
    assert span(w, 7, 0, 1)["text"] == "日本の大学"
    assert span(w, 7, 1, 2)["text"] == "大学の学生"
    assert w.call("read")["text"] == "日本の大学大学の学生"                          # two crosses with 大学 as the centre: the loom wrote what was asked, twice


def test_a_word_the_loom_cannot_write_between_two_units_is_refused(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    base = shape(srv, w)
    d = refused(span(w, 2, 1, 2), "span_inexpressible")                            # 表 とも いう (WORD): とも is not one particle
    assert d == {"reason": "gap_is_not_a_particle", "between": ["表", "いう"], "gap": "とも"}
    assert shape(srv, w) == base
    assert span(w, 2, 0, 1)["text"] == "ハッシュ表"                                   # the part before it is fine


def test_head_final_every_arm_unit_sits_on_the_very_next_unit_and_one_particle_per_arm(toy, tmp_path):
    """Every unit that a particle follows sits on THAT particle's arm of the cross whose centre is the unit right after the particle; nothing is seated
    on a centre that comes before it; no arm of any cross holds two units (the read rule has one particle per arm)."""
    srv, w = started(toy, tmp_path)
    r = span(w, 5, 0, 1)                                                          # 東京(の) 大学
    assert [(s["surface"], s["seat"].split(":")[0]) for c in r["crosses"] for s in c["seated"]] == [("東京", "+x")] and r["crosses"][0]["centre"]["surface"] == "大学"
    r = span(w, 5, 1, 2)                                                          # 大学(に) 通う
    assert [(s["surface"], s["seat"].split(":")[0], s["particle"]) for c in r["crosses"] for s in c["seated"]] == [("大学", "-x", "に")]
    srv2, w2 = started(toy, tmp_path / "b")
    for sid, f, t in ((8, 0, 1), (8, 1, 2), (8, 2, 3), (8, 3, 4), (3, 1, 2), (4, 0, 1)):
        r = span(w2, sid, f, t)
        assert r["ok"], (sid, f, t, r)
        for c in r["crosses"]:
            assert len(c["seated"]) <= 1                                           # one unit per cross: nothing can pack two units on one arm
            for s in c["seated"]:
                assert ARM_OF[s["particle"]] == s["seat"].split(":")[0]
    st = srv2.runs[w2.run_id].run.state
    for cross in st.crosses.values():
        for ai in range(6):                                                         # the data seats of every arm hold at most one unit
            assert sum(1 for k in range(cross.inner_k + 1) if cross.arms[ai][k] is not None) <= 1
        assert len(cross.uids()) <= 2
    assert w2.call("read")["text"] == "大学で学生" + "学生が先生" + "先生と本" + "本を読む" + "日本の首都" + "日本が勝っ"


def expected_readout(corpus, tier, sid, i0, i1):
    """THE INVARIANT of weave_span (L-LOOM-144): the units of the stretch VERBATIM (a unit keeps whatever characters it has: ビー・ジーズ, S-37, JR-Y13)
    and, between two neighbours, the LETTERS of the text between their spans (punctuation, quotes, brackets, spaces and 「・」 dropped).  Computed here
    from the sentence text and the unit spans alone, not through `Corpus.span_gaps`."""
    idx = corpus.spans()
    text = idx.text(sid)
    sps = idx.spans(tier, sid)
    units = corpus.tier(tier).sentence_units[sid]
    return "".join(units[j] + ("".join(ch for ch in text[sps[j][1]:sps[j + 1][0]] if sp._has_letter(ch)) if j < i1 else "") for j in range(i0, i1 + 1))


def check_one_stretch(corpus, task, sid, tier, i0, i1):
    """Weave the stretch on a fresh run: refused (for one of the two reasons, state untouched) -> False; woven -> the thread reads exactly the
    invariant read-out, every cross has at most one arm unit, that unit is the one right before its centre and its arm is the particle between them
    -> True."""
    run = Run(corpus, task, "m", "rid")
    before = _bare(run.state)
    res = run.step("model", "weave_span", {"sid": sid, "tier": tier, "from": i0, "to": i1})["result"]
    if not res["ok"]:
        assert res["refusal"] == "span_inexpressible" and res["detail"]["reason"] in ("gap_is_not_a_particle", "nested_particle_chain"), res
        assert _bare(run.state) == before, (sid, tier, i0, i1)
        return False
    want = expected_readout(corpus, tier, sid, i0, i1)
    got = run.step("model", "read", {})["result"]["text"]
    assert got == want, (sid, tier, i0, i1, got, want)
    assert res["text"] == want and res["from"] == i0 and res["to"] == i1
    units = list(corpus.tier(tier).sentence_units[sid])
    pos = i0                                                                  # walk the stretch: each cross takes its arm unit (if any) and then its centre
    for c in res["crosses"]:
        assert len(c["seated"]) <= 1 and c["L"] == (2 if c["seated"] else 1)
        for s_ in c["seated"]:
            assert units[pos] == s_["surface"] and units[pos + 1] == c["centre"]["surface"]       # head-final: the very next unit is the centre
            pos += 1
        pos += 1
    assert pos == i1 + 1
    return True


def test_the_readout_is_the_units_verbatim_with_letters_only_gaps_for_every_span_of_the_toy_corpus(toy):
    """The property of the op over EVERY sentence, tier and stretch of the toy corpus: either the call is refused (span_inexpressible, for one of the two
    reasons) or the thread reads the stretch's units verbatim with letters-only gaps (here no unit holds a non-letter, so that is also exactly the letters
    of the slice of the sentence), and a refused call changes nothing."""
    corpus = Corpus.load(open(toy, "rb").read())
    idx = corpus.spans()
    task = {"task_id": "p", "text": "x", "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": toy}
    n_ok = n_ref = 0
    for sid in range(corpus.n_sentences):
        text = idx.text(sid)
        for tier in ("RUN", "WORD", "CHAR"):
            n = len(corpus.tier(tier).sentence_units[sid])
            sps = idx.spans(tier, sid)
            for i0, i1 in itertools.combinations_with_replacement(range(n), 2):
                if check_one_stretch(corpus, task, sid, tier, i0, i1):
                    n_ok += 1
                    letters = "".join(ch for ch in text[sps[i0][0]:sps[i1][1]] if ch.isalnum() or ch in "ー々")
                    assert expected_readout(corpus, tier, sid, i0, i1) == letters, (sid, tier, i0, i1)       # toy units hold letters only
                else:
                    n_ref += 1
    assert n_ok > 100 and n_ref > 20


def test_a_sampled_run_over_the_real_corpus_keeps_the_invariant_in_all_three_tiers():
    """About 200 random stretches of fulllead (a fixed seed; all three tiers; every stretch whose units hold a non-letter -- ビー・ジーズ, S-37, JR-Y13 --
    that a bounded scan finds is added): refused for one of the two reasons with the state untouched, or the read-out is the units verbatim with
    letters-only gaps.  (The full sweep over every stretch of fulllead takes 31 s and was run by hand once; this is its seeded sample.)"""
    import random
    with open(CORPUS, "rb") as f:
        corpus = Corpus.load(f.read())
    task = {"task_id": "p", "text": "x", "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": CORPUS}
    rng = random.Random(20261012)
    picks = []
    for tier in ("RUN", "WORD", "CHAR"):
        for _ in range(67):
            sid = rng.randrange(corpus.n_sentences)
            n = len(corpus.tier(tier).sentence_units[sid])
            if n == 0:
                continue
            i0 = rng.randrange(n)
            picks.append((sid, tier, i0, min(n - 1, i0 + rng.randrange(0, 6))))
    odd = 0
    for sid in range(min(corpus.n_sentences, 3000)):                          # units that keep punctuation: a stretch of exactly that unit and one next to it
        for tier in ("RUN", "WORD", "CHAR"):
            us = corpus.tier(tier).sentence_units[sid]
            for k, u in enumerate(us):
                if not all(sp._has_letter(ch) for ch in u) and odd < 12:
                    picks.append((sid, tier, k, k))
                    picks.append((sid, tier, k, min(len(us) - 1, k + 1)))
                    odd += 1
    assert len(picks) >= 190
    n_ok = sum(1 for (sid, tier, i0, i1) in picks if check_one_stretch(corpus, task, sid, tier, i0, i1))
    assert n_ok > 50, n_ok
    assert odd >= 1                                                           # the corpus does hold units with a non-letter in them (the reason for the wording)
    assert any(expected_readout(corpus, t, s_, i0, i1) != "".join(ch for ch in expected_readout(corpus, t, s_, i0, i1) if sp._has_letter(ch))
               for (s_, t, i0, i1) in picks)                                  # ...and at least one sampled read-out keeps a non-letter, so "letters only" would be wrong

def test_touching_units_become_one_unit_crosses_linked_in_order(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    r = span(w, 2, "ハッシュ", "表")                                              # ハッシュ表: no particle between the units
    assert r["ok"] and r["text"] == "ハッシュ表" and r["thread"] == ["c1", "c2"]
    assert [(c["centre"]["surface"], c["L"], c["seated"], c["topic"]) for c in r["crosses"]] == [("ハッシュ", 1, [], False), ("表", 1, [], False)]
    assert w.call("emit")["text"] == "ハッシュ表"
    # 「カール・マルクス」: the 「・」 between the units is not a letter, the loom writes none, the T9 normaliser ignores it (kept apart from the words)
    srv2, w2 = started(toy, tmp_path / "b")
    r2 = span(w2, 9, 0, 1)
    assert r2["ok"] and r2["text"] == "カールマルクス" and len(r2["crosses"]) == 2
    assert w2.call("emit")["text"] == "カールマルクス"
    # 「1981年」: a number and its counter
    srv3, w3 = started(toy, tmp_path / "c")
    r3 = span(w3, 10, 0, 1)
    assert r3["ok"] and r3["text"] == "1981年" and [c["centre"]["surface"] for c in r3["crosses"]] == ["1981", "年"]
    assert w3.call("emit")["text"] == "1981年"


def test_a_chain_AのBのC_cannot_be_written_and_is_refused_with_nothing_changed(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    base = shape(srv, w)
    d = refused(span(w, 7, 0, 2), "span_inexpressible")                           # 日本の大学の学生
    assert d == {"reason": "nested_particle_chain", "units": ["日本", "大学", "学生"], "particles": ["の", "の"]}
    d = refused(span(w, 3, 0, 2), "span_inexpressible")                           # 東京で日本の首都: で then の: the middle unit would be an arm unit AND a centre
    assert d["reason"] == "nested_particle_chain" and d["particles"] == ["で", "の"]
    refused(span(w, 6, 0, 5), "span_inexpressible")                               # five の in a row
    assert shape(srv, w) == base
    # the two halves are fine one at a time, and the second one can reuse the unit the first one ends on only as a new unit
    assert span(w, 7, 0, 1)["text"] == "日本の大学"
    assert span(w, 7, 1, 2)["text"] == "大学の学生"
    assert w.call("read")["text"] == "日本の大学大学の学生"                          # two crosses with 大学 as the centre: the loom wrote what was asked, twice


def test_a_word_the_loom_cannot_write_between_two_units_is_refused(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    base = shape(srv, w)
    d = refused(span(w, 2, 1, 2), "span_inexpressible")                            # 表 とも いう (WORD): とも is not one particle
    assert d == {"reason": "gap_is_not_a_particle", "between": ["表", "いう"], "gap": "とも"}
    assert shape(srv, w) == base
    assert span(w, 2, 0, 1)["text"] == "ハッシュ表"                                   # the part before it is fine


def test_head_final_every_arm_unit_sits_on_the_very_next_unit_and_one_particle_per_arm(toy, tmp_path):
    """Every unit that a particle follows sits on THAT particle's arm of the cross whose centre is the unit right after the particle; nothing is seated
    on a centre that comes before it; no arm of any cross holds two units (the read rule has one particle per arm)."""
    srv, w = started(toy, tmp_path)
    r = span(w, 5, 0, 1)                                                          # 東京(の) 大学
    assert [(s["surface"], s["seat"].split(":")[0]) for c in r["crosses"] for s in c["seated"]] == [("東京", "+x")] and r["crosses"][0]["centre"]["surface"] == "大学"
    r = span(w, 5, 1, 2)                                                          # 大学(に) 通う
    assert [(s["surface"], s["seat"].split(":")[0], s["particle"]) for c in r["crosses"] for s in c["seated"]] == [("大学", "-x", "に")]
    srv2, w2 = started(toy, tmp_path / "b")
    for sid, f, t in ((8, 0, 1), (8, 1, 2), (8, 2, 3), (8, 3, 4), (3, 1, 2), (4, 0, 1)):
        r = span(w2, sid, f, t)
        assert r["ok"], (sid, f, t, r)
        for c in r["crosses"]:
            assert len(c["seated"]) <= 1                                           # one unit per cross: nothing can pack two units on one arm
            for s in c["seated"]:
                assert ARM_OF[s["particle"]] == s["seat"].split(":")[0]
    st = srv2.runs[w2.run_id].run.state
    for cross in st.crosses.values():
        for ai in range(6):                                                         # the data seats of every arm hold at most one unit
            assert sum(1 for k in range(cross.inner_k + 1) if cross.arms[ai][k] is not None) <= 1
        assert len(cross.uids()) <= 2
    assert w2.call("read")["text"] == "大学で学生" + "学生が先生" + "先生と本" + "本を読む" + "日本の首都" + "日本が勝っ"


def test_the_readout_equals_the_sentence_slice_for_every_span_of_the_toy_corpus(toy):
    """The property of the op: for EVERY sentence, tier and stretch of the toy corpus, either the call is refused (span_inexpressible, for one of the two
    reasons) or the thread reads EXACTLY the stretch's letters (punctuation dropped), every cross has at most one arm unit, that unit is the one right
    before its centre and its arm is the particle between them, and a refused call changes nothing."""
    corpus = Corpus.load(open(toy, "rb").read())
    idx = corpus.spans()
    task = {"task_id": "p", "text": "x", "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": toy}
    n_ok = n_ref = 0
    for sid in range(corpus.n_sentences):
        text = idx.text(sid)
        for tier in ("RUN", "WORD", "CHAR"):
            n = len(corpus.tier(tier).sentence_units[sid])
            sps = idx.spans(tier, sid)
            for i0, i1 in itertools.combinations_with_replacement(range(n), 2):
                run = Run(corpus, task, "m", "rid")
                before = _bare(run.state)
                res = run.step("model", "weave_span", {"sid": sid, "tier": tier, "from": i0, "to": i1})["result"]
                if not res["ok"]:
                    assert res["refusal"] == "span_inexpressible" and res["detail"]["reason"] in ("gap_is_not_a_particle", "nested_particle_chain"), res
                    assert _bare(run.state) == before, (sid, tier, i0, i1)
                    n_ref += 1
                    continue
                n_ok += 1
                want = "".join(ch for ch in text[sps[i0][0]:sps[i1][1]] if ch.isalnum() or ch in "ー々")
                got = run.step("model", "read", {})["result"]["text"]
                assert got == want, (sid, tier, i0, i1, got, want)
                assert res["text"] == want and res["from"] == i0 and res["to"] == i1
                units = list(corpus.tier(tier).sentence_units[sid])
                pos = i0                                                          # walk the stretch: each cross takes its arm unit (if any) and then its centre
                for c in res["crosses"]:
                    assert len(c["seated"]) <= 1 and c["L"] == (2 if c["seated"] else 1)
                    for s in c["seated"]:
                        assert units[pos] == s["surface"] and units[pos + 1] == c["centre"]["surface"]       # head-final: the very next unit is the centre
                        pos += 1
                    assert units[pos] == c["centre"]["surface"]
                    pos += 1
                assert pos == i1 + 1                                              # every unit of the stretch, once, in order
    assert n_ok > 100 and n_ref > 5


# ---------------------------------------------------------------------------------------------------------------
# from / to, the refusals, what a call returns
# ---------------------------------------------------------------------------------------------------------------
def test_from_and_to_are_indexes_or_surfaces_and_a_repeated_unit_is_told_apart_by_its_index(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    a = span(w, 0, "日本", "首都")
    b = span(w, 0, 1, 2)
    assert (a["from"], a["to"], a["text"]) == (b["from"], b["to"], b["text"]) == (1, 2, "日本の首都")
    c = span(w, 11, 1, 2)                                                       # 日本(は) 日本(の) 首都: the SECOND 日本 by index
    assert c["from"] == 1 and c["text"] == "日本の首都"
    d = span(w, 11, "日本", "首都")                                              # by surface: the FIRST 日本 -> the whole sentence
    assert (d["from"], d["to"], d["text"]) == (0, 2, "日本は日本の首都")
    e = span(w, 11, "日本", "日本")                                              # `to` is searched from `from` on: the same unit
    assert (e["from"], e["to"], e["text"]) == (0, 0, "日本")
    # a one-unit stretch is one cross; a bool is not an index
    assert span(w, 0, 2, 2)["text"] == "首都"
    refused(w.call("weave_span", sid=0, tier="WORD", **{"from": True, "to": 1}), "bad_args")


def test_a_refusal_says_only_what_was_asked_and_a_success_does_not_return_the_rest_of_the_sentence(toy, tmp_path):
    """Review defect 5: `centre_not_in_sentence` listed ALL the units of the sentence and the success result listed the unseated ones, i.e. the weave
    returned the whole sentence's units without charging a read.  weave_span returns the stretch's crosses and nothing else."""
    srv, w = started(toy, tmp_path)
    before = w.call("status")["counters"]
    r = span(w, 0, "日本", "首都")
    assert "東京" not in json.dumps(r, ensure_ascii=False) and set(r) == {"ok", "wv", "sid", "tier", "from", "to", "text", "crosses", "thread"}
    assert not {"units", "unseated", "readout"} & set(r)
    after = w.call("status")["counters"]
    assert (after["lookups"], after["reads"], after["emit_attempts"]) == (before["lookups"], before["reads"], before["emit_attempts"])
    for args, typ, keys in (({"from": "京都", "to": 2}, "unit_not_in_sentence", {"which", "text"}),
                            ({"from": 0, "to": "ない"}, "unit_not_in_sentence", {"which", "text"}),
                            ({"from": 0, "to": 9}, "span_out_of_range", {"which", "index"}),
                            ({"from": -1, "to": 1}, "span_out_of_range", {"which", "index"}),
                            ({"from": 2, "to": 0}, "bad_span", {"from", "to", "reason"})):
        d = refused(w.call("weave_span", sid=0, tier="WORD", **args), typ)
        assert set(d) - {"hint"} == keys and "units" not in d and "東京" not in json.dumps(d, ensure_ascii=False)


def test_each_refusal_leaves_the_state_as_it_was(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ca")
    span(w, 1, 0, 1)
    base = shape(srv, w)
    d = refused(span(w, 9999, 0, 1), "unknown_sid")
    assert d["sid"] == 9999 and d["n"] == len(SENTS)
    refused(span(w, -1, 0, 1), "unknown_sid")
    assert refused(span(w, 0, 0, 1, "RUN"), "tier_not_in_task")["tiers"] == ["WORD"]                  # the task has WORD only
    refused(span(w, 0, 0, 1, "CODE"), "tier_not_in_task")
    refused(span(w, 0, 0, 1, "LINE"), "bad_args")
    refused(w.call("weave_span", sid=0, tier="WORD", **{"from": 0}), "bad_args")                       # `to` is required
    refused(w.call("weave_span", sid=0, tier="WORD", to=1), "bad_args")
    refused(w.call("weave_span", sid="0", tier="WORD", **{"from": 0, "to": 1}), "bad_args")
    refused(w.call("weave_span", sid=0, tier="WORD", extra=1, **{"from": 0, "to": 1}), "bad_args")
    refused(w.call("weave_span", sid=0, tier="WORD", wv="weave_span.v9", **{"from": 0, "to": 1}), "bad_args")
    refused(w.call("weave_span", sid=0, tier="WORD", **{"from": [0], "to": 1}), "bad_args")
    refused(span(w, 0, 2, 0), "bad_span")
    assert shape(srv, w) == base


def test_a_run_tier_is_cut_from_the_same_sentence_with_that_tiers_units_and_tiers_do_not_mix(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    r = span(w, 2, "ハッシュ", "表", "RUN")                                         # RUN: ハッシュ 表 ともいう
    assert r["ok"] and r["tier"] == "RUN" and r["text"] == "ハッシュ表"
    base = shape(srv, w)
    assert refused(span(w, 0, 1, 2, "WORD"), "tier_mix") == {"tier": "WORD", "thread_tiers": ["RUN"]}       # one tier per thread, refused up front
    refused(span(w, 0, 1, 2, "CHAR"), "tier_mix")
    assert shape(srv, w) == base


def test_the_cross_cap_and_a_code_task_refuse(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    for _ in range(CAPS["prose"]["crosses"] - 1):
        assert w.call("open_cross", tier="WORD", L=1)["ok"]
    base = shape(srv, w)
    assert refused(span(w, 2, 0, 1), "cross_cap") == {"limit": 24, "needed": 2}                           # 2 crosses would make 25
    assert shape(srv, w) == base
    assert span(w, 0, 2, 2)["ok"]                                                                         # one more fits
    srv2, wc = started(toy, tmp_path / "c", "toy/code")
    refused(span(wc, 0, 0, 1), "not_prose")


def test_only_record_units_are_made_in_both_modes(toy, tmp_path):
    for task_id in ("toy/ca", "toy/ro"):
        srv, w = started(toy, tmp_path / task_id.split("/")[1], task_id)
        assert span(w, 0, 0, 2)["ok"]
        st = srv.runs[w.run_id].run.state
        assert {u.kind for u in st.units.values()} == {"record"} and st.counters["constructed"] == 0
        assert all(u.prov["n"] >= 1 and u.prov["tier"] == "WORD" for u in st.units.values())


def test_one_op_one_row_with_the_derived_crosses_in_the_row_and_the_ops_cap_counts_it_once(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    assert CLASS_OF["weave_span"] == "ops" and "weave_span" in STATE_CHANGING and "weave_span" in MODEL_OPS and "drop" in STATE_CHANGING
    before = w.call("status")
    n_rows = len(rows(tmp_path / "runs" / "r1"))
    r = span(w, 0, 0, 2)
    after = w.call("status")
    assert after["counters"]["ops"] == before["counters"]["ops"] + 1 and (after["counters"]["lookups"], after["counters"]["reads"]) == (0, 0)
    rs = rows(tmp_path / "runs" / "r1")
    assert len(rs) == n_rows + 2 and rs[-2]["op"] == "weave_span" and rs[-2]["actor"] == "model"       # + the status row after it
    assert rs[-2]["args"] == {"from": 0, "sid": 0, "tier": "WORD", "to": 2, "wv": "weave_span.v2"}       # the rule version is in the args
    assert rs[-2]["result"]["crosses"] == r["crosses"]                                                    # the derived crosses and seats are IN the row
    cap = CAPS["prose"]["ops"]
    srv2, w2 = started(toy, tmp_path / "b", "toy/ro")
    for _ in range(cap - 1):
        span(w2, 9999, 0, 1)                                                                              # unknown_sid every time: refused calls count in their class
    assert span(w2, 0, 0, 2)["ok"]                                                                        # the cap-th op
    assert refused(span(w2, 0, 0, 2), "ops_cap") == {"limit": cap}


def test_the_existing_rules_hold_after_a_span_weave(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    r = span(w, 0, "日本", "首都")
    cid = r["crosses"][0]["cid"]
    seat = r["crosses"][0]["seated"][0]
    spare = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    assert refused(w.call("seat", cid=cid, seat=seat["seat"], uid=spare), "seat_occupied")["uid"] == seat["uid"]       # empty seats only
    refused(w.call("seat", cid=cid, seat="+z", uid=seat["uid"]), "unit_already_seated")                                  # a unit instance sits once
    refused(w.call("seat", cid=cid, seat="+x:1", uid=spare), "seat_is_foundation")                                       # the particle seat is not yours
    refused(w.call("link", cid=cid), "already_linked")
    assert w.call("unseat", cid=cid, seat=seat["seat"])["ok"] and w.call("seat", cid=cid, seat=seat["seat"], uid=seat["uid"])["ok"]
    e = w.call("emit")
    assert e["ok"] and e["text"] == "日本の首都"


def test_a_span_the_corpus_key_dislikes_is_still_refused_by_emit_but_no_swap_is_offered(toy, tmp_path):
    """Faithful to the SENTENCE, gated by the CORPUS: 日本が勝っ is what the sentence says, but 日本 has の evidence in 5 sentences and が in one, so the
    cross is unstable.  The weave does not hide or fix it (and does not run a free read): `read` / `emit` refuse it `unstable_cross`; since L-LOOM-146
    the refusal of a cross `weave_span.v2` made lists NO swap (every improving swap would change the quoted text) and says which sentence it quotes."""
    srv, w = started(toy, tmp_path, "toy/ro")
    r = span(w, 4, 0, 1)
    assert r["ok"] and r["text"] == "日本が勝っ" and "refusals" not in r
    rd_ = w.call("read")
    ref = rd_["refusals"]
    assert [x["type"] for x in ref] == ["unstable_cross"]
    assert ref[0]["improving"] == [] and ref[0]["best_swaps"] == [] and ref[0]["span"] == {"sid": 4, "faithful": True}
    assert "faithful to sentence 4" in ref[0]["advice"] and "unstable under the key" in ref[0]["advice"] and "another stretch" in ref[0]["advice"] and "abstain" in ref[0]["advice"]
    st = [e for e in rd_["stability"] if e["cid"] == ref[0]["cid"]][0]
    assert st["status"] == "unstable" and st["improving"] == [] and st["best_swaps"] == [] and st["improving_n"] >= 1       # the key is still the key; only the swaps are not listed
    e = w.call("emit")
    assert e["refusal"] == "unstable_cross" and e["detail"]["refusals"] == ref
    assert lg.verify(tmp_path / "runs" / "r1", corpus_path=toy)["status"] == "OK"


def test_a_cross_that_is_not_exactly_the_quoted_stretch_gets_its_swaps_back(toy, tmp_path):
    """The marker is cleared by anything that changes the cross: the same stretch woven by rule v1 (what the h55c ledgers name), a cross taken apart and
    put together again, a hand-built cross: all three list the improving swap, as before L-LOOM-146."""
    srv, w = started(toy, tmp_path, "toy/ro")
    r1 = w.call("weave_span", sid=4, tier="WORD", wv="weave_span.v1", **{"from": 0, "to": 1})
    assert r1["ok"] and r1["wv"] == "weave_span.v1"
    ref = w.call("read")["refusals"]
    assert ref[0]["type"] == "unstable_cross" and ref[0]["best_swaps"] and "span" not in ref[0] and "advice" not in ref[0]
    srv2, w2 = started(toy, tmp_path / "b", "toy/ro")
    r2 = span(w2, 4, 0, 1)
    c2 = r2["crosses"][0]
    assert w2.call("read")["refusals"][0]["best_swaps"] == []
    seat = c2["seated"][0]["seat"]
    assert w2.call("unseat", cid=c2["cid"], seat=seat)["ok"] and w2.call("seat", cid=c2["cid"], seat=seat, uid=c2["seated"][0]["uid"])["ok"]
    ref2 = w2.call("read")["refusals"][0]
    assert ref2["type"] == "unstable_cross" and ref2["best_swaps"] and "span" not in ref2           # nobody can say the cross is still the quoted stretch
    srv3, w3 = started(toy, tmp_path / "c", "toy/ro")
    a = w3.call("add", text="日本", kind="record", tier="WORD")["uid"]
    b = w3.call("add", text="勝っ", kind="record", tier="WORD")["uid"]
    cc = w3.call("open_cross", tier="WORD", L=2)["cid"]
    assert w3.call("seat", cid=cc, seat="centre", uid=b)["ok"] and w3.call("seat", cid=cc, seat="-z:0", uid=a)["ok"] and w3.call("link", cid=cc)["ok"]
    ref3 = w3.call("read")["refusals"][0]
    assert ref3["type"] == "unstable_cross" and ref3["best_swaps"] and "span" not in ref3


def test_the_i2_025_stretch_is_refused_unstable_with_no_swap_offered(tmp_path):
    """The case that made the reviewer look (h55c, I2-025): the sentence says アメリカを「青」, `weave_span` reads 「アメリカを青」, `emit` is refused
    `unstable_cross`.  Before L-LOOM-146 the refusal named the swap and the model took it (「アメリカの青」, text the sentence never said).  Now the refusal
    names the sentence (143) and offers no swap; the stretch is not altered, the run can weave another stretch or abstain."""
    from loom_common import task as ltask, server as lserver, weaver as lweaver
    srv = lserver(tmp_path, tasks=[ltask("p/ro", "record_only")])
    w = lweaver(srv, "p/ro", "r1")
    assert "アメリカを「青」" in w.call("read_sentence", sid=143)["text"]
    r = w.call("weave_span", sid=143, tier="WORD", **{"from": "アメリカ", "to": "青"})
    assert r["ok"] and r["text"] == "アメリカを青" and r["wv"] == "weave_span.v2"
    rd_ = w.call("read")
    assert rd_["text"] == "アメリカを青"
    ref = rd_["refusals"]
    assert [x["type"] for x in ref] == ["unstable_cross"] and ref[0]["improving"] == [] and ref[0]["best_swaps"] == []
    assert ref[0]["span"]["sid"] == 143 and "faithful to sentence 143" in ref[0]["advice"]
    e = w.call("emit")
    assert e["ok"] is False and e["refusal"] == "unstable_cross" and e["detail"]["refusals"][0]["best_swaps"] == []
    assert not any("seat" in k for k in e["detail"]["refusals"][0])                                                       # no seat pair anywhere in the refusal
    assert w.call("abstain", type="cannot_weave")["ok"]
    assert lg.verify(tmp_path / "runs" / "r1")["status"] == "OK"


# ---------------------------------------------------------------------------------------------------------------
# drop
# ---------------------------------------------------------------------------------------------------------------
def test_drop_removes_a_whole_cross_with_its_units_in_one_op(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    r = span(w, 0, 0, 2)                                                           # c1 (東京, u1), c2 (日本 u2 + 首都 u3)
    sha_before_drop = srv.runs[w.run_id].run.state.sha()
    st = srv.runs[w.run_id].run.state
    assert "made" not in st.to_obj()                                              # every state made without a drop hashes as it did before LOOM-span
    n_rows = len(rows(tmp_path / "runs" / "r1"))
    d = w.call("drop", cid="c2")
    assert d == {"ok": True, "cid": "c2", "removed": [{"uid": "u3", "surface": "首都"}, {"uid": "u2", "surface": "日本"}], "thread": ["c1"]}
    assert list(st.units) == ["u1"] and list(st.crosses) == ["c1"] and st.thread == ["c1"] and st.counters["ops"] == 2
    assert st.to_obj()["made"] == {"units": 3, "crosses": 2}                       # ids are never reused: the next unit is u4, the next cross c3
    assert len(rows(tmp_path / "runs" / "r1")) == n_rows + 1 and rows(tmp_path / "runs" / "r1")[-1]["op"] == "drop"
    assert w.call("read")["text"] == "東京は"
    r2 = span(w, 0, 1, 2)
    assert [c["cid"] for c in r2["crosses"]] == ["c3"] and r2["crosses"][0]["centre"]["uid"] == "u5" and r2["crosses"][0]["seated"][0]["uid"] == "u4"
    assert w.call("read")["text"] == "東京は日本の首都"
    assert w.call("emit")["text"] == "東京は日本の首都"
    assert sha_before_drop != st.sha()
    assert lg.verify(tmp_path / "runs" / "r1", corpus_path=toy)["status"] == "OK"


def test_drop_gives_back_cross_cap_room_but_not_the_constructed_budget_and_the_ops_cap_bounds_both(toy, tmp_path):
    """L-LOOM-148: the cross cap counts the crosses that exist, so a dropped cross makes room again; the constructed budget counts units EVER made, so a
    dropped constructed unit does not; what bounds the cycle is the ops cap (every add, weave and drop is one op)."""
    srv, w = started(toy, tmp_path, "toy/ca")
    st = srv.runs[w.run_id].run.state
    for _ in range(CAPS["prose"]["crosses"] - 1):
        assert w.call("open_cross", tier="WORD", L=1)["ok"]
    assert refused(span(w, 2, 0, 1), "cross_cap") == {"limit": 24, "needed": 2}                           # the whole chain or nothing
    assert w.call("drop", cid="c1")["ok"] and w.call("drop", cid="c2")["ok"]
    assert span(w, 2, 0, 1)["ok"]                                                                         # room again
    n_before = st.counters["constructed"]
    cid = w.call("open_cross", tier="WORD", L=1)["cid"]
    u = w.call("add", text="ΩΩ", kind="constructed")["uid"]
    assert w.call("seat", cid=cid, seat="centre", uid=u)["ok"] and w.call("drop", cid=cid)["ok"]
    assert st.counters["constructed"] == n_before + 1                                                     # NOT given back
    assert st.counters["ops"] == sum(1 for x in rows(tmp_path / "runs" / "r1") if x["actor"] == "model" and x["op"] in STATE_CHANGING)          # a refused op counts too


def test_drop_takes_an_unlinked_cross_too_and_refuses_what_is_not_there(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ca")
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    u = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    w.call("seat", cid=c, seat="centre", uid=u)
    pool = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    d = w.call("drop", cid=c)
    assert d["ok"] and d["removed"] == [{"uid": u, "surface": "日本"}] and d["thread"] == []
    st = srv.runs[w.run_id].run.state
    assert list(st.units) == [pool] and st.pool() == [pool]                         # a unit in the pool is not in a cross: it stays
    base = shape(srv, w)
    refused(w.call("drop", cid=c), "unknown_cid")                                  # twice
    refused(w.call("drop", cid="c99"), "unknown_cid")
    refused(w.call("drop"), "bad_args")
    refused(w.call("drop", cid=1), "bad_args")
    refused(w.call("drop", cid=c, extra=1), "bad_args")
    assert shape(srv, w) == base
    w.call("abstain", type="unknown")
    refused(w.call("drop", cid="c1"), "run_closed")


def test_drop_of_the_constructed_unit_does_not_give_the_constructed_budget_back(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ca")
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    u = w.call("add", text="ΩΩ", kind="constructed")["uid"]
    w.call("seat", cid=c, seat="centre", uid=u)
    assert w.call("drop", cid=c)["ok"]
    assert srv.runs[w.run_id].run.state.counters["constructed"] == 1               # the budget counts units ever made


# ---------------------------------------------------------------------------------------------------------------
# the rule version
# ---------------------------------------------------------------------------------------------------------------
def test_a_weave_span_row_names_its_rule_version_and_a_model_may_name_it_too(toy, tmp_path):
    srv, w = started(toy, tmp_path)
    r = span(w, 0, 1, 2)
    r2 = w.call("weave_span", sid=0, tier="WORD", wv="weave_span.v1", **{"from": 1, "to": 2})
    assert r["ok"] and r2["ok"] and r["wv"] == WEAVE_SPAN_WV == "weave_span.v2" and r2["wv"] == "weave_span.v1"
    rs = [x for x in rows(tmp_path / "runs" / "r1") if x["op"] == "weave_span"]
    assert [x["args"]["wv"] for x in rs] == ["weave_span.v2", "weave_span.v1"] and {k: v for k, v in rs[0]["args"].items() if k != "wv"} == {k: v for k, v in rs[1]["args"].items() if k != "wv"}
    # a refused weave_span is stamped too (the stamp is on the row, whatever the result)
    refused(span(w, 9999, 0, 1), "unknown_sid")
    assert rows(tmp_path / "runs" / "r1")[-1]["args"]["wv"] == "weave_span.v2"
    assert lg.verify(tmp_path / "runs" / "r1", corpus_path=toy)["status"] == "OK"       # v1 and v2 rows replay in one ledger


def test_a_later_rule_never_turns_an_old_ledger_into_replay_differs(toy, tmp_path, monkeypatch):
    srv, w = started(toy, tmp_path)
    span(w, 0, 0, 2)
    span(w, 2, 0, 1)
    w.call("emit")
    d = tmp_path / "runs" / "r1"
    assert lg.verify(d, corpus_path=toy)["status"] == "OK"
    old = (d / "ops.jsonl").read_bytes()

    def v3(run, sid, tier, f, t):                                                  # a different rule: it would give another result for every call
        raise opsmod.Refuse("bad_span", {"reason": "v3 says no"})
    monkeypatch.setitem(opsmod.WEAVE_SPAN_RULES, "weave_span.v3", v3)
    monkeypatch.setattr(opsmod, "WEAVE_SPAN_WV", "weave_span.v3")                  # the current rule moved on
    rep = lg.replay(d, toy)
    assert rep.status == "IDENTICAL" and b"".join(rep.lines) == old               # the old rows name v2 and are replayed by v2
    assert lg.verify(d, corpus_path=toy)["status"] == "OK"
    # a NEW run is stamped with the new rule and replays by it
    srv2 = srv_of(toy, tmp_path / "new")
    w2 = ScriptedWeaver(srv2, "toy/ro", "m", "n1")
    w2.begin()
    r = span(w2, 0, 0, 2)
    assert r["refusal"] == "bad_span"
    assert rows(tmp_path / "new" / "runs" / "n1")[-1]["args"]["wv"] == "weave_span.v3"
    assert lg.verify(tmp_path / "new" / "runs" / "n1", corpus_path=toy)["status"] == "OK"
    # a row that names a rule this code does not have is not obeyed
    refused(w2.call("weave_span", sid=0, tier="WORD", wv="weave_span.v7", **{"from": 0, "to": 1}), "bad_args")


# ---------------------------------------------------------------------------------------------------------------
# QUESTION_ECHO (notes.v2, L-LOOM-147)
# ---------------------------------------------------------------------------------------------------------------
def echo_started(toy, tmp_path, text, notes=None, mode="record_only"):
    t = {"task_id": "toy/q", "text": text, "lang": "prose", "mode": mode, "tiers": ["RUN", "WORD", "CHAR"], "corpus": toy}
    srv = LoomServer([t], str(tmp_path / "runs"), (), **({} if notes is None else {"notes": notes}))
    w = ScriptedWeaver(srv, "toy/q", "test-weaver", "r1")
    assert w.begin()["ok"]
    return srv, w


def test_question_echo_flags_a_woven_unit_that_is_a_word_of_the_question_and_never_blocks(toy, tmp_path):
    srv, w = echo_started(toy, tmp_path, "日本の首都は何ですか")
    r = span(w, 0, 0, 2)                                                           # 東京は日本の首都: 日本 and 首都 are in the question, 東京 is not
    assert r["ok"] and r["text"] == "東京は日本の首都"
    echo = [n for n in r["notes"] if n["type"] == "QUESTION_ECHO"]
    assert [(n["unit"], n["cid"], n["seat"]) for n in echo] == [("首都", "c2", "centre"), ("日本", "c2", "+x:0")]
    assert all(set(n) == {"type", "cid", "seat", "uid", "unit"} for n in echo)
    nrow = rows(tmp_path / "runs" / "r1")[-1]
    assert nrow["actor"] == "loom" and nrow["args"]["nv"] == "notes.v2" and nrow["args"]["of"] == "weave_span" and nrow["args"]["notes"] == r["notes"]
    e = w.call("emit")                                                             # a note never blocks
    assert e["ok"] and e["text"] == "東京は日本の首都" and [n["type"] for n in e["notes"]] == ["QUESTION_ECHO", "QUESTION_ECHO"]
    assert lg.verify(tmp_path / "runs" / "r1", corpus_path=toy)["status"] == "OK"
    assert notelib.note_summary(rows(tmp_path / "runs" / "r1"))["by_type"]["QUESTION_ECHO"] == 2
    # the answer alone carries no echo
    srv2, w2 = echo_started(toy, tmp_path / "b", "日本の首都は何ですか")
    r2 = span(w2, 0, 0, 0)
    assert r2["ok"] and r2["text"] == "東京" and "notes" not in r2


def test_question_echo_has_a_floor_of_two_characters_folds_width_and_reads_only_the_question(toy, tmp_path):
    srv, w = echo_started(toy, tmp_path, "サンゴーカメラは何年に設立されましたか")
    r = span(w, 10, 0, 1)                                                          # 1981 + 年: 年 is in 何年, but it is one character
    assert r["ok"] and r["text"] == "1981年" and "notes" not in r
    srv2, w2 = echo_started(toy, tmp_path / "b", "ＩＴの首都")                     # full-width letters and an unrelated question: nothing to flag
    assert "notes" not in span(w2, 4, 0, 0)
    srv3, w3 = echo_started(toy, tmp_path / "c", "１９８１年の設立")                 # NFKC: the question says 1981 in full-width digits
    r3 = span(w3, 10, 0, 1)
    assert [n["unit"] for n in r3["notes"]] == ["1981"]                            # 1981 yes (>= 2 characters, equal after NFKC), 年 no (one character)


def test_a_notes_v1_server_has_no_echo_note_and_a_v1_begin_row_is_as_it_was(toy, tmp_path):
    srv, w = echo_started(toy, tmp_path, "日本の首都は何ですか", notes="notes.v1")
    b = rows(tmp_path / "runs" / "r1")[0]
    assert "notes_profile" not in b["result"]
    r = span(w, 0, 1, 2)
    assert r["ok"] and "notes" not in r and w.call("emit")["ok"]
    assert all(x["actor"] != "loom" for x in rows(tmp_path / "runs" / "r1"))
    assert lg.verify(tmp_path / "runs" / "r1", corpus_path=toy)["status"] == "OK"
    srv2, w2 = echo_started(toy, tmp_path / "b", "日本の首都は何ですか")
    assert rows(tmp_path / "b" / "runs" / "r1")[0]["result"]["notes_profile"] == "notes.v2"
    assert w2.call("weave_span", sid=0, tier="WORD", **{"from": 1, "to": 2})["notes"]
    with pytest.raises(ValueError):
        echo_started(toy, tmp_path / "c", "x", notes="notes.v9")


def test_the_run_a_ledger_recorded_with_decides_its_notes_not_the_current_code(toy, tmp_path):
    """A notes.v1 ledger whose weave units ARE words of its question replays IDENTICAL with no note row (the h55c ledgers are exactly that)."""
    srv, w = echo_started(toy, tmp_path, "日本の首都は何ですか", notes="notes.v1")
    span(w, 0, 1, 2)
    w.call("read")
    w.call("emit")
    rep = lg.replay(tmp_path / "runs" / "r1", toy)
    assert rep.status == "IDENTICAL" and rep.notes_stale == []
    # a begin row that names a notes profile the code does not know is an INPUTS status, not a crash
    d = tmp_path / "runs" / "r1"
    lines = (d / "ops.jsonl").read_bytes().split(b"\n")
    forged = json.loads(lines[0])
    forged["result"]["notes_profile"] = "notes.v9"
    lines[0] = json.dumps(forged, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    d2 = tmp_path / "forged"
    d2.mkdir()
    (d2 / "ops.jsonl").write_bytes(b"\n".join(lines))
    (d2 / "meta.json").write_bytes((d / "meta.json").read_bytes())
    rep2 = lg.replay(d2, toy)
    assert rep2.status in ("INPUTS", "DIFFERS")


# ---------------------------------------------------------------------------------------------------------------
# notes after a weave (review defect 6)
# ---------------------------------------------------------------------------------------------------------------
def test_loom_notes_run_after_a_weave_and_the_note_row_follows_the_weave_row(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    a = span(w, 5, 0, 1)                                                           # 東京の大学
    assert a["ok"] and "notes" not in a and notelib.NOTE_AFTER_OPS == ("read", "emit", "weave_span")
    b = span(w, 7, 0, 1)                                                           # 日本の大学: the same centre 大学 with another の content
    assert b["ok"] and [n["type"] for n in b["notes"]] == ["CONFLICT"]
    n = b["notes"][0]
    assert (n["kind"], n["centre"], n["particle"]) == ("arm_contents", "大学", "の") and [[u["s"] for u in v["units"]] for v in n["variants"]] == [["東京"], ["日本"]]
    rs = rows(tmp_path / "runs" / "r1")
    assert [(r["actor"], r["op"]) for r in rs[-2:]] == [("model", "weave_span"), ("loom", "loom_note")]
    assert rs[-1]["args"]["of"] == "weave_span" and rs[-1]["args"]["notes"] == b["notes"] and "notes" not in rs[-2]["result"]
    refused(span(w, 9999, 0, 1), "unknown_sid")                                    # a refused weave has no notes due
    assert rows(tmp_path / "runs" / "r1")[-1]["op"] == "weave_span"
    d = tmp_path / "runs" / "r1"
    v = lg.verify(d, corpus_path=toy)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["notes_stale"] == []
    # a note row dropped from the middle of the ledger is a replay difference (the loom owes it)
    srv2 = srv_of(toy, tmp_path / "x")
    w2 = ScriptedWeaver(srv2, "toy/ro", "m", "x1")
    w2.begin()
    span(w2, 5, 0, 1)
    span(w2, 7, 0, 1)
    w2.call("status")
    assert lg.verify(tmp_path / "x" / "runs" / "x1", corpus_path=toy)["status"] == "OK"
    assert notelib.note_summary(rows(tmp_path / "x" / "runs" / "x1"))["observations"] == 2


# ---------------------------------------------------------------------------------------------------------------
# the LEGACY weave_sentence: no longer a tool, still replayable
# ---------------------------------------------------------------------------------------------------------------
def legacy(srv, w, **args):
    """A weave_sentence row as LOOM-batch wrote it: only a run that is being replayed executes the legacy op, so the test sets the flag the replay sets."""
    e = srv.runs[w.run_id]
    e.run.replaying = True
    try:
        return srv._exec(e, "model", "weave_sentence", args)
    finally:
        e.run.replaying = False


def test_weave_sentence_is_not_a_tool_any_more(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    assert "weave_sentence" not in MODEL_OPS and LEGACY_OPS == ("weave_sentence",) and len(MODEL_OPS) == 20
    n = len(rows(tmp_path / "runs" / "r1"))
    refused(w.call("weave_sentence", sid=0, tier="WORD", centre="首都"), "unknown_tool")             # the door
    assert len(rows(tmp_path / "runs" / "r1")) == n
    run = srv.runs[w.run_id].run                                                                      # and Run.step: a live call is refused, with a row
    body = run.step("model", "weave_sentence", {"sid": 0, "tier": "WORD", "centre": "首都"})
    assert body["result"]["refusal"] == "unknown_tool" and run.state.crosses == {}


def test_a_ledger_recorded_with_weave_sentence_verifies_and_replays_identical(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    r = legacy(srv, w, sid=0, tier="WORD", centre="首都")
    assert r["ok"] and r["readout"]["text"] == "日本の首都" and [u["surface"] for u in r["unseated"]] == ["東京"]       # the LOOM-batch result, unchanged
    assert "units" in legacy(srv, w, sid=0, tier="WORD", centre="京都")["detail"]                      # the legacy refusal still names the sentence's units
    legacy(srv, w, sid=5, tier="WORD", centre="通う")
    w.call("read")
    w.call("emit")
    d = tmp_path / "runs" / "r1"
    ws = [x for x in rows(d) if x["op"] == "weave_sentence"]
    assert len(ws) == 3 and all("wv" not in x["args"] for x in ws)                                     # legacy rows carry no rule version
    v = lg.verify(d, corpus_path=toy)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    rep = lg.replay(d, toy)
    assert b"".join(rep.lines) == (d / "ops.jsonl").read_bytes()
    # a server restarted on the folder reloads the run; the reloaded run does NOT execute the legacy op on a live call
    srv2 = srv_of(toy, tmp_path)
    assert srv2._entry("r1") is not None
    refused(srv2.call("weave_sentence", {"run_id": "r1", "sid": 0, "tier": "WORD", "centre": "首都"}), "unknown_tool")
    assert srv2._entry("r1").run.replaying is False
    # the legacy ledger keeps counting: its rows are `ops` class, and the self-correction meter still sees a refused legacy row as a refusal
    assert CLASS_OF["weave_sentence"] == "ops" and "weave_sentence" in STATE_CHANGING
    sc = notelib.self_corrections(rows(d))
    assert sc["refusals_recoverable"] >= 1                                                             # the centre_not_in_sentence row of weave_sentence


def test_a_forged_legacy_result_is_replay_differs(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    legacy(srv, w, sid=3, tier="WORD", centre="首都")
    d = tmp_path / "runs" / "r1"
    rs = rows(d)
    rs[1]["result"]["seated"][0]["seat"] = "+x:0"
    prev = "0" * 64
    from verantyx.ledger_events import canonical
    out = []
    for r in rs:
        r["prev"] = prev
        body = {k: v for k, v in r.items() if k != "sha"}
        r["sha"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
        prev = r["sha"]
        out.append(canonical(r))
    (d / "ops.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")
    (d / "HEAD").write_text(prev + "\n", encoding="utf-8")
    v = lg.verify(d, corpus_path=toy)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == 1


def test_all_the_stored_h55b_ledgers_with_weave_sentence_rows_verify_and_replay_identical():
    base = os.path.join(ROOT, "experiments/line3/loom/runs_h55b")
    if not os.path.isdir(base):
        pytest.skip("no stored runs_h55b")
    n_runs = n_weave = 0
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if not os.path.exists(os.path.join(d, "ops.jsonl")):
            continue
        v = lg.verify(d, corpus_path=CORPUS)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", (name, v["status"], v.get("replay"))
        n_weave += sum(1 for r in rows(d) if r["op"] == "weave_sentence")
        n_runs += 1
    assert n_runs == 30 and n_weave == 36


def test_every_old_ledger_replays_identical_and_the_demo_bytes_are_unchanged(tmp_path):
    got = 0
    for sub in ("runs_h55", "runs_h55b", "runs_h55c", "runs_h55d", "baseline_scripted/runs"):
        base = os.path.join(ROOT, "experiments/line3/loom", sub)
        if not os.path.isdir(base):
            pytest.skip("no stored %s" % sub)
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if os.path.exists(os.path.join(d, "ops.jsonl")):
                rep = lg.replay(d, CORPUS)
                assert rep.status == "IDENTICAL", (sub, name, rep.mismatch, rep.first_diff)
                got += 1
    assert got >= 150
    # the demo: the pinned worked example of design 3.5 is written by hand (no weave op), so its bytes are what they were
    from test_loom_notes import HEAD_PYTHON, TOKYO_CA_HEAD, TOKYO_CA_SHA, TOKYO_RO_HEAD
    p = subprocess.run([PY, "-m", "verantyx.cli", "loom", "demo", "--corpus", CORPUS, "--runs-dir", str(tmp_path / "runs")],
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    for d in ("demo_ca", "demo_ro"):
        assert not [r for r in rows(tmp_path / "runs" / d) if r["op"] in ("weave_span", "weave_sentence", "drop")]
    assert json.loads(next(l for l in (tmp_path / "runs/demo_ca/ops.jsonl").read_text().splitlines() if '"op":"emit"' in l))["result"]["output_sha"] == TOKYO_CA_SHA
    if sys.version_info[:3] == HEAD_PYTHON:
        assert (tmp_path / "runs/demo_ca/HEAD").read_text().strip() == TOKYO_CA_HEAD
        assert (tmp_path / "runs/demo_ro/HEAD").read_text().strip() == TOKYO_RO_HEAD


# ---------------------------------------------------------------------------------------------------------------
# the scripted weaver, determinism, replay
# ---------------------------------------------------------------------------------------------------------------
def test_the_scripted_span_weaver_says_東京は日本の首都_in_four_rows_one_op(toy, tmp_path):
    srv = srv_of(toy, tmp_path)
    w = ScriptedWeaver(srv, "toy/ro", "scripted-weaver", "b1")
    e = weave_tokyo_batch(w, 0)
    assert e["ok"] and e["text"] == "東京は日本の首都"
    d = tmp_path / "runs" / "b1"
    rs = rows(d)
    assert [r["op"] for r in rs] == ["begin", "read_sentence", "weave_span", "emit"]
    assert sum(1 for r in rs if r["op"] in STATE_CHANGING) == 1 and rs[-1]["result"]["shares"]["constructed"] == 0
    v = lg.verify(d, corpus_path=toy)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["replay"]["text"] == "東京は日本の首都"


_RUNNER = """
import sys
from verantyx.loom.mcp import LoomServer
from verantyx.loom.scripted import ScriptedWeaver
toy, runs = sys.argv[1], sys.argv[2]
t = [{"task_id": "toy/ro", "text": "x", "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": toy}]
srv = LoomServer(t, runs)
w = ScriptedWeaver(srv, "toy/ro", "scripted-weaver", "d1")
w.begin()
w.call("weave_span", sid=0, tier="WORD", **{"from": 0, "to": 2})
w.call("weave_span", sid=7, tier="WORD", **{"from": 0, "to": 2})        # refused: a row, too
w.call("weave_span", sid=5, tier="WORD", **{"from": 0, "to": 1})        # a conflict note is due
w.call("weave_span", sid=7, tier="WORD", **{"from": 0, "to": 1})
w.call("drop", cid="c3")
w.call("weave_span", sid=2, tier="WORD", **{"from": "ハッシュ", "to": "表"})
w.call("read")
w.call("status")
e = w.call("emit")
print(e.get("text"), e.get("refusal"))
"""


def test_the_ledger_is_byte_identical_across_hash_seeds_0_1_12345(toy, tmp_path):
    blobs, heads, outs = set(), set(), set()
    for seed in ("0", "1", "12345"):
        runs = tmp_path / ("seed" + seed)
        p = subprocess.run([PY, "-c", _RUNNER, toy, str(runs)], env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT), cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        assert p.returncode == 0, p.stderr
        outs.add(p.stdout.strip())
        blobs.add((runs / "d1" / "ops.jsonl").read_bytes())
        heads.add((runs / "d1" / "HEAD").read_text())
    assert len(blobs) == 1 and len(heads) == 1 and len(outs) == 1
    ops_ = [json.loads(l)["op"] for l in blobs.pop().decode().splitlines()]
    assert {"weave_span", "drop", "loom_note"} <= set(ops_)


def test_replay_of_a_run_with_spans_drops_refusals_and_notes_is_identical_byte_for_byte(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    for sid, f, t in ((3, 1, 2), (5, 0, 1), (7, 0, 1), (8, 3, 4), (2, 0, 1)):
        assert span(w, sid, f, t)["ok"]
    span(w, 7, 0, 2)                                                               # a refusal is a row, too
    w.call("drop", cid="c2")
    w.call("read")
    w.call("emit")
    d = tmp_path / "runs" / "r1"
    rep = lg.replay(d, toy)
    assert rep.status == "IDENTICAL", (rep.mismatch, rep.first_diff)
    assert b"".join(rep.lines) == (d / "ops.jsonl").read_bytes()
    assert lg.verify(d, corpus_path=toy)["status"] == "OK"


def test_a_forged_span_result_is_replay_differs(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    span(w, 3, 1, 2)
    d = tmp_path / "runs" / "r1"
    rs = rows(d)
    rs[1]["result"]["crosses"][0]["seated"][0]["seat"] = "+x:1"
    prev = "0" * 64
    from verantyx.ledger_events import canonical
    out = []
    for r in rs:
        r["prev"] = prev
        body = {k: v for k, v in r.items() if k != "sha"}
        r["sha"] = hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
        prev = r["sha"]
        out.append(canonical(r))
    (d / "ops.jsonl").write_text("\n".join(out) + "\n", encoding="utf-8")
    (d / "HEAD").write_text(prev + "\n", encoding="utf-8")
    v = lg.verify(d, corpus_path=toy)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == 1


def test_the_door_maps_first_and_last_to_the_stored_from_and_to_and_refuses_both_spellings(toy, tmp_path):
    """L-LOOM-145: the model's names are first / last (inclusive); the ledger stores from / to exactly as before; a programmatic caller may still say
    from / to; first together with from (or last with to) is a door refusal (bad_args, no row)."""
    srv, w = started(toy, tmp_path)
    r = w.call("weave_span", sid=0, tier="WORD", first="日本", last="首都")
    assert r["ok"] and r["text"] == "日本の首都" and (r["from"], r["to"]) == (1, 2)
    assert [x for x in rows(tmp_path / "runs" / "r1") if x["op"] == "weave_span"][0]["args"] == {"from": "日本", "sid": 0, "tier": "WORD", "to": "首都", "wv": "weave_span.v2"}
    n = len(rows(tmp_path / "runs" / "r1"))
    for kw in ({"first": "日本", "from": "日本", "last": "首都"}, {"first": "日本", "last": "首都", "to": "首都"}):
        refused(w.call("weave_span", sid=0, tier="WORD", **kw), "bad_args")
    assert len(rows(tmp_path / "runs" / "r1")) == n
    assert w.call("weave_span", sid=1, tier="WORD", **{"from": "日本", "to": "東京"})["ok"]


# ---------------------------------------------------------------------------------------------------------------
# the door: MCP schema, the API tools, the agent files
# ---------------------------------------------------------------------------------------------------------------
def test_the_mcp_tools_are_listed_with_first_and_last_and_a_call_goes_through(toy, tmp_path):
    bank = tmp_path / "bank.jsonl"
    bank.write_text("".join(json.dumps(t) + "\n" for t in toy_tasks(toy)), encoding="utf-8")
    m = lm.build(str(bank), str(tmp_path / "runs"))
    tools = {t.name: t for t in asyncio.run(m.list_tools())}
    assert list(tools) == list(MODEL_OPS) and len(tools) == 20 and "weave_sentence" not in tools
    t = tools["weave_span"]
    assert set(t.inputSchema["required"]) == {"run_id", "sid", "tier", "first", "last"} and set(t.inputSchema["properties"]) == {"run_id", "sid", "tier", "first", "last"}
    assert t.inputSchema["properties"]["first"]["type"] == "string" and t.inputSchema["properties"]["last"]["type"] == "string"    # strings only (no anyOf: see mcp.py)
    assert "from" not in t.inputSchema["properties"] and "to" not in t.inputSchema["properties"]
    assert "WORD FOR WORD" in t.description and "span_inexpressible" in t.description
    assert set(tools["drop"].inputSchema["required"]) == {"run_id", "cid"}

    async def go():
        await m.call_tool("begin", {"task_id": "toy/ro", "model": "mcp-test"})
    asyncio.run(go())
    rid = next(iter(m.loom_server.runs))

    async def call(name, args):
        content, _ = await m.call_tool(name, args)
        return json.loads(content[0].text)
    out = asyncio.run(call("weave_span", {"run_id": rid, "sid": 0, "tier": "WORD", "first": "日本", "last": "首都"}))
    assert out["ok"] and out["text"] == "日本の首都" and rows(tmp_path / "runs" / rid)[-1]["op"] == "weave_span"
    assert rows(tmp_path / "runs" / rid)[-1]["args"] == {"from": "日本", "sid": 0, "tier": "WORD", "to": "首都", "wv": "weave_span.v2"}
    out = asyncio.run(call("drop", {"run_id": rid, "cid": "c1"}))
    assert out["ok"] and [u["surface"] for u in out["removed"]] == ["首都", "日本"]
    with pytest.raises(Exception):
        asyncio.run(call("weave_span", {"run_id": rid, "sid": 0, "tier": "WORD", "last": "首都"}))        # `first` is required by the schema


def test_the_api_driver_offers_the_tools_runs_a_span_weave_and_counts_usage(toy, tmp_path):
    bank = tmp_path / "bank.jsonl"
    bank.write_text("".join(json.dumps(t) + "\n" for t in toy_tasks(toy)), encoding="utf-8")
    m = lm.build(str(bank), str(tmp_path / "runs"))
    tools = drv.api_tools(asyncio.run(m.list_tools()))
    names = [t["name"] for t in tools]
    assert "weave_span" in names and "drop" in names and "weave_sentence" not in names and "begin" not in names and names[-1] == "done" and len(names) == 20
    ws = next(t for t in tools if t["name"] == "weave_span")
    assert "run_id" not in ws["input_schema"]["properties"] and ws["input_schema"]["additionalProperties"] is False
    assert set(ws["input_schema"]["required"]) == {"sid", "tier", "first", "last"} and ws["input_schema"]["properties"]["first"]["type"] == "string"
    srv = m.loom_server
    rid = srv.begin("toy/ro", "fake-model", "api1")["run_id"]
    client = drv.ReplayClient([[("tool", "read_sentence", {"sid": 0}), ("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "日本", "last": "首都"})],
                               [("tool", "emit", {})]], allowed_tools=names)
    orig = client._create

    def with_usage(**kw):
        r = orig(**kw)
        r.usage = SimpleNamespace(input_tokens=100, output_tokens=7, cache_read_input_tokens=None)
        return r
    client.messages = SimpleNamespace(create=with_usage)
    res = drv.run_episode(client, srv, rid, "fake-model", "sys", "go", tools)
    assert res.ended == "closed" and res.turns == 2
    assert res.to_obj()["usage"] == {"calls": 2, "input_tokens": 200, "output_tokens": 14, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    assert rows(tmp_path / "runs" / rid)[-1]["result"]["text"] == "日本の首都"
    ws_row = [r for r in rows(tmp_path / "runs" / rid) if r["op"] == "weave_span"][0]
    assert ws_row["args"] == {"from": "日本", "sid": 0, "tier": "WORD", "to": "首都", "wv": "weave_span.v2"}       # the ledger stores from / to (L-LOOM-145)
    assert drv.MAX_TURNS["prose"] == 160


def test_the_agent_files_name_the_tools_and_only_the_constructed_prompt_says_to_use_your_own_words():
    d = os.path.join(ROOT, ".claude/agents")
    ca = open(os.path.join(d, "loom-weaver.md"), encoding="utf-8").read()
    ro = open(os.path.join(d, "loom-weaver-record-only.md"), encoding="utf-8").read()
    for body in (ca, ro):
        tools = body.split("\n")[3]
        assert "mcp__vera-loom__weave_span" in tools and "mcp__vera-loom__drop" in tools and "weave_sentence" not in body
        assert "`weave_span(run_id, sid, tier, first, last)`" in body and "span_inexpressible" in body and "`drop(run_id, cid)`" in body
        assert "without quotation marks" in body
        assert "WORD FOR WORD" in body
        assert "NEVER weave a word that appears in the question" in body and "SHORTEST span that answers" in body      # L-LOOM-147
        assert "1975 + 年" in body and "no swap is offered for it" in body and "do not rearrange the quoted words" in body   # one-unit examples; L-LOOM-146
    assert 'add(run_id, text, kind="constructed")' in ca and "does NOT mean give up" in ca and "Abstaining is for questions the corpus cannot answer" in ca
    assert "YOUR OWN words" in ca
    # record_only stays strict: no instruction to add constructed words, no 'instead as constructed'
    assert "YOUR OWN words" not in ro and "does NOT mean give up" not in ro and "constructed_forbidden" in ro and "abstain; do not approximate" in ro


# ---------------------------------------------------------------------------------------------------------------
# the exact-match scoring over the stored measurements
# ---------------------------------------------------------------------------------------------------------------
def _rescore():
    import importlib.util
    path = os.path.join(ROOT, "experiments/line3/loom/rescore.py")
    spec = importlib.util.spec_from_file_location("loom_rescore_t", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_stored_measurements_rescored_under_the_exact_match_headline():
    rs = _rescore()
    want = {"results_h55": (1, 0, 5), "results_h55b": (0, 1, 7), "results_h55c": (2, 2, 6)}        # exact hits /7: record_only, constructed_allowed, control
    old_text = {"results_h55": (4, 2, 6), "results_h55b": (3, 2, 7)}                                    # hits_text /7 as the first two measurements were scored
    for name, exp in want.items():
        d = os.path.join("experiments/line3/loom", name)
        if not os.path.isdir(os.path.join(ROOT, d)):
            pytest.skip("no stored %s" % name)
        rows_ = rs.rescore_dir(d)
        assert len(rows_) == 30 and all(r["verify"] == "OK" and r["replay_verified"] for r in rows_)
        got = tuple(sum(1 for r in rows_ if r["mode"] == m and r["kind"] == "answerable" and r["hit_exact"]) for m in rs.MODES)
        assert got == exp, (name, got)
        if name in old_text:                                                                          # the old column is still there, as a secondary one
            assert tuple(sum(1 for r in rows_ if r["mode"] == m and r["kind"] == "answerable" and r["old_hits_text"]) for m in rs.MODES) == old_text[name]
        assert all(r["hit_exact"] is None or isinstance(r["hit_exact"], bool) for r in rows_)
        assert all(not (r["hit_exact"] and r["hit_cited"]) for r in rows_)                            # an exact hit is never "cited"
    # the rescore files written next to the JSON files say the same
    for name, lab in (("results_h55", "h55"), ("results_h55b", "h55b")):
        f = os.path.join(ROOT, "experiments/line3/loom", name, "rescore_%s.md" % lab)
        if os.path.exists(f):
            txt = open(f, encoding="utf-8").read()
            assert "30 of 30 are OK and replay IDENTICAL" in txt and "hit_exact (new headline)" in txt


def test_the_exact_headline_and_the_cited_column_on_real_ledgers():
    rs = _rescore()
    d = "experiments/line3/loom/results_h55b"
    if not os.path.isdir(os.path.join(ROOT, d)):
        pytest.skip("no stored results_h55b")
    by = {(r["base"], r["mode"]): r for r in rs.rescore_dir(d)}
    r = by[("I2-025", "record_only")]                                       # 「イギリスアメリカを青」: holds the gold, equals nothing, is in no cited sentence word for word
    assert r["text"] == "イギリスアメリカを青" and r["hits_text"] is True and r["hit_exact"] is False and r["hit_cited"] is False and r["excess_chars"] == 9
    r = by[("I2-013", "record_only")]                                       # 「旧社格は県社」: the read sentence says exactly that: cited, but not the headline
    assert r["text"] == "旧社格は県社" and r["hit_exact"] is False and r["hit_cited"] is True and r["status"] == "miss"
    r = by[("I2-001", "constructed_allowed")]
    assert r["hit_exact"] is True and r["hit_cited"] is False and r["status"] == "hit"


def test_hit_cited_compares_letters_only_on_both_sides():
    """L-LOOM-143: `weave_span` writes no quotation mark, bracket or hyphen, so a woven text is compared with the cited sentence on LETTERS ONLY.  The T9
    normaliser alone keeps 「」 、 。 （） - in the sentence and the quoted text was then never a substring of it."""
    S = _rescore().score
    sent = "イギリスを「赤」、アメリカを「青」と色分けし、万一米英間に戦争が起こった場合の作戦について軍部に研究させていた。"
    assert S.hit_cited("青", "アメリカを青", [sent]) is True                                   # was False: the 「」 around 青 sat in the normalised sentence
    assert S.hit_cited("青", "アメリカを青", ["アメリカを青と色分けした。"]) is True              # a sentence without quotation marks still works
    assert S.hit_cited("青", "アメリカの青", [sent]) is False                                  # the swapped text (の for を) is not in the sentence
    assert S.hit_cited("青", "イギリスアメリカを青", [sent]) is False                          # units stuck together across 「赤」、 are not a quotation
    assert S.hit_cited("青", "青", [sent]) is False                                           # an exact hit is never cited
    assert S.hit_cited("1981年", "1981年に設立", ["同社は（1981年に設立）された。"]) is True
    assert S.letters_only("ビー・ジーズ「S-37」、（JR）") == "ビージーズs37jr"
    assert S.hit_cited("Y17", "JR-Y17駅", ["花園町駅の駅番号はJR-Y17。"]) is False           # the text is not in the sentence (no 駅 after 17 there)
    assert S.hit_cited("Y17", "JR-Y17駅", ["花園町駅の駅番号はJR-Y17。駅"]) is True           # (punctuation between them does not matter, letters do)
    assert S.hit_cited("Y17", "JRY17", ["駅番号はJR-Y17である。"]) is True                   # hyphen dropped on both sides


def test_the_h55c_cited_column_after_the_letters_only_comparison():
    rs = _rescore()
    d = "experiments/line3/loom/results_h55c"
    if not os.path.isdir(os.path.join(ROOT, d)):
        pytest.skip("no stored results_h55c")
    rows_ = rs.rescore_dir(d)
    by = {(r["base"], r["mode"]): r for r in rows_}
    got = tuple(sum(1 for r in rows_ if r["mode"] == m and r["kind"] == "answerable" and r["hit_cited"]) for m in rs.MODES)
    assert got == (2, 1, 0)
    r = by[("I2-041", "record_only")]                                       # 「キューバの太陽という意味」: the sentence says it word for word (it has 「」 around ソル・クバーノ)
    assert r["text"] == "キューバの太陽という意味" and r["hit_cited"] is True and r["hit_exact"] is False
    assert by[("I2-041", "constructed_allowed")]["hit_cited"] is False      # 「キューバの太陽カクテルという意味」 is not in any sentence
    assert by[("I2-025", "record_only")]["text"] == "アメリカの青" and by[("I2-025", "record_only")]["hit_cited"] is False
    # the stretch the run really wove (「アメリカを青」, before it took the swap) IS a quotation of the sentence it read
    cited = rs.score.cited_sentences(rows(os.path.join(ROOT, "experiments/line3/loom/runs_h55c/I2-025.record_only.api")))
    assert rs.score.hit_cited("青", "アメリカを青", cited) is True


def test_the_stored_runs_name_the_rules_they_were_recorded_under():
    """L-LOOM-146/147: h55c's weave rows say weave_span.v1 and its begin rows name no notes profile (notes.v1: no echo note is ever due on them, so they
    replay IDENTICAL under today's code); h55d's weave rows say weave_span.v2 and its begin rows name notes.v2."""
    base = os.path.join(ROOT, "experiments/line3/loom")
    for sub, wv, prof in (("runs_h55c", "weave_span.v1", None), ("runs_h55d", "weave_span.v2", "notes.v2")):
        d0 = os.path.join(base, sub)
        if not os.path.isdir(d0):
            pytest.skip("no stored %s" % sub)
        n_runs = n_weave = 0
        for name in sorted(os.listdir(d0)):
            d = os.path.join(d0, name)
            if not os.path.exists(os.path.join(d, "ops.jsonl")):
                continue
            rs = rows(d)
            assert rs[0]["result"].get("notes_profile") == prof, (sub, name)
            for r in rs:
                if r["op"] == "weave_span":
                    assert r["args"]["wv"] == wv, (sub, name)
                    n_weave += 1
            n_runs += 1
        assert n_runs == 30 and n_weave > 0
    # and a h55d ledger shows what the new advice did: I2-025 record_only was shown the faithful-but-unstable refusal without a swap and wove 青 alone
    rs = rows(os.path.join(base, "runs_h55d/I2-025.record_only.api"))
    reads = [r for r in rs if r["actor"] == "model" and r["op"] == "read" and r["result"].get("refusals")]
    assert reads and reads[0]["result"]["refusals"][0]["type"] == "unstable_cross" and reads[0]["result"]["refusals"][0]["best_swaps"] == []
    assert reads[0]["result"]["refusals"][0]["span"] == {"faithful": True, "sid": 143}
    assert [r for r in rs if r["op"] == "emit" and r["actor"] == "model"][-1]["result"]["annotated"][0]["s"] == "青"


def test_the_h55d_numbers_under_the_exact_headline():
    rs = _rescore()
    d = "experiments/line3/loom/results_h55d"
    if not os.path.isdir(os.path.join(ROOT, d)):
        pytest.skip("no stored results_h55d")
    rows_ = rs.rescore_dir(d)
    assert len(rows_) == 30 and all(r["verify"] == "OK" and r["replay_verified"] for r in rows_)
    got = tuple(sum(1 for r in rows_ if r["mode"] == m and r["kind"] == "answerable" and r["hit_exact"]) for m in rs.MODES)
    assert got == (6, 5, 6)
    loom = [r for r in rows_ if r["mode"] != "free_text" and r["kind"] == "answerable" and r["text"] is not None]
    assert len(loom) == 14 and not [r for r in loom if r["hits_text"] and not r["hit_exact"]]            # over-extension: none (h55c: 7)
    assert sorted(r["text"] for r in loom if not r["hits_text"]) == ["マルクス", "マルクス", "連想配列"]       # the three emits that do not hold the gold
    assert all(r["status"] == "abstained_correct" for r in rows_ if r["kind"] == "unans")

