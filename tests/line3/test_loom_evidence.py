"""LOOM-evidence tests (docs/LINE3_LOOM_EVIDENCE_GATE.md; T-EV-01..15): the reader's evidence gate at emit.

The numbers pinned here are the design's own (its probe was a scratch script; these tests rebuild it from the corpus, bank2.tsv, bank4.tsv and the stored ledgers):
the 12 of 69 answerable bank2 items the gate can reach under OP-EV-1 (a) (0 under (b)), 0 of 60 unanswerable items for which ANY single corpus unit passes, the 33
word-aligned bank4 trap values all refused, the h55d record_only hits I2-013 / I2-025 / I2-034 admitted and I2-001 / I2-041 / R2-I013 refused with the stated codes,
ADV-010 / ADV-001 refused with the exact messages.  Nothing here calls a model.
"""
import csv
import glob
import hashlib
import json
import os
import re
import subprocess
import sys

import pytest

from verantyx.loom import evidence as ev
from verantyx.loom import ledger as lg
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from verantyx.loom.ops import WEAVE_SPAN_V3, WEAVE_SPAN_WV
from loom_common import CORPUS, PY, ROOT, rows

LOOMX = os.path.join(ROOT, "experiments/line3/loom")
BANK2_TSV = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
BANK4_TSV = os.path.join(ROOT, "experiments/line3/bank4/bank4.tsv")
TASK_FILES = ("tasks_bank2.jsonl", "tasks_unans.jsonl", "tasks_unans_adv.jsonl")
ANSWERABLE_LOOM = ("I2-001", "I2-008", "I2-013", "I2-025", "I2-034", "I2-041", "R2-I013")
SCOPES = (ev.SCOPE_TITLE, ev.SCOPE_CLAUSE)


# ---------------------------------------------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


@pytest.fixture(scope="module")
def tasks():
    """task_id -> the task row (absolute corpus path), every loom mode of the three banks."""
    out = {}
    for f in TASK_FILES:
        for ln in open(os.path.join(LOOMX, f), encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                if r.get("control"):
                    continue
                row = dict(r, corpus=os.path.join(ROOT, r["corpus"]))
                got = out.setdefault(r["task_id"], row)
                assert {k: v for k, v in got.items() if k != "kind"} == {k: v for k, v in row.items() if k != "kind"}          # a task in two banks is the same row
    return out


@pytest.fixture(scope="module")
def texts():
    """base id -> the question text the loom sees (bank2 answerable loom tasks, bank2 unans, bank4)."""
    out = {}
    for f in TASK_FILES:
        for ln in open(os.path.join(LOOMX, f), encoding="utf-8"):
            if ln.strip():
                r = json.loads(ln)
                out.setdefault(r.get("bank2_id") or r["base"], r["text"])
    return out


def bank2_rows():
    return list(csv.DictReader(open(BANK2_TSV, encoding="utf-8"), delimiter="\t"))


def bank4_rows():
    out = []
    for r in csv.DictReader(open(BANK4_TSV, encoding="utf-8"), delimiter="\t"):
        r["trap"] = re.search(r"c\)\s*(.*)$", r["notes"]).group(1).strip()
        out.append(r)
    return out


def server(tmp_path, tasks, scope=ev.SCOPE_TITLE, evidence="v1", name="runs"):
    return LoomServer(list(tasks.values()), str(tmp_path / name), (), evidence=evidence, subject_scope=scope)


def occurrences(corpus, s):
    """Every (sid, i0, i1) at which the string `s` is a WORD-aligned stretch of a sentence of the corpus (WORD unit indexes)."""
    out = []
    for sid in range(corpus.n_sentences):
        v = ev.view_of(corpus, sid)
        pos = v.text.find(s)
        while pos >= 0:
            end = pos + len(s)
            i0 = next((k for k, sp_ in enumerate(v.spans) if sp_[0] == pos), None)
            i1 = next((k for k, sp_ in enumerate(v.spans) if sp_[1] == end), None)
            if i0 is not None and i1 is not None and i0 <= i1:
                out.append((sid, i0, i1))
            pos = v.text.find(s, pos + 1)
    return out


def final_weaves(rows_):
    """The weave_span rows of a stored (h55d / unans_adv) ledger whose crosses were not dropped: [(sid, tier, from, to)] in ledger order."""
    made, dropped = [], set()
    for r in rows_:
        if r["actor"] != "model" or not r["result"].get("ok"):
            continue
        if r["op"] == "weave_span":
            made.append((r["result"]["sid"], r["result"]["tier"], r["result"]["from"], r["result"]["to"], [c["cid"] for c in r["result"]["crosses"]]))
        if r["op"] == "drop":
            dropped.add(r["result"]["cid"])
    return [m[:4] for m in made if not set(m[4]) & dropped]


def stored_final_thread(d):
    rs = rows(d)
    emitted = [r for r in rs if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("ok")]
    return rs[0]["args"]["task_id"], (emitted[0]["result"]["text"] if emitted else None), final_weaves(rs)


def reweave(srv, tid, rid, weaves):
    srv.begin(tid, "test", rid)
    for sid, tier, f, t in weaves:
        r = srv.call("weave_span", {"run_id": rid, "sid": sid, "tier": tier, "first": f, "last": t})
        assert r["ok"], r
    return srv.call("read", {"run_id": rid})


def weave_codes(res):
    """[(answer, codes)] of the no_evidence refusal of a read / refused emit result."""
    out = []
    for r in res.get("refusals") or (res.get("detail") or {}).get("refusals") or []:
        if r["type"] == "no_evidence":
            out += [(w["answer"], w["codes"]) for w in r["weaves"]]
    return out


# ---------------------------------------------------------------------------------------------------------------
# T-EV-01: the question's units
# ---------------------------------------------------------------------------------------------------------------
CUT = {   # item -> (form, slot phrase, effective particle, slot noun, slot head, fallback, Y, Y forms, subject, level)   (the table of design 3.1, extended)
    "I2-001": ("predicate", "何", None, None, None, False, "別名", ("別名",), ("ハッシュテーブル",), "x_chain"),
    "I2-008": ("predicate", "誰", None, None, None, False, "人物", ("人物",), ("唯物史観",), "case"),
    "I2-013": ("predicate", "何", None, None, None, False, "旧社格", ("旧社格", "社格"), ("千葉神社",), "x_chain"),
    "I2-025": ("slot", "何色", "と", None, None, True, None, (), ("レッド計画", "アメリカ"), "case"),
    "I2-034": ("slot", "何年", "に", None, "設立", False, None, (), ("サンゴーカメラ",), "topic"),
    "I2-041": ("predicate", "どういう意味", None, None, None, False, "いうカクテル名", ("いうカクテル名", "カクテル名"), (), None),
    "R2-I013": ("slot", "どこ", "で", "国", "使わ", False, None, (), ("アワディー語",), "topic"),
    "ADV-001": ("predicate", "いつ", None, None, None, False, "月日", ("月日",), ("CUBEJUICE",), "ga"),
    "ADV-010": ("predicate", "何", None, None, None, False, "名称", ("名称",), ("競技会場",), "x_chain"),
    "ADV-025": ("predicate", "何メートル", None, None, None, False, "堤頂長", ("堤頂長", "頂長"), ("赤尾ダム",), "x_chain"),
    "ADV-005": ("predicate", "何", None, None, None, False, "名前", ("名前",), ("大邱FC",), "x_chain"),
    "ADV-015": ("predicate", "何色", None, None, None, True, "色数", ("色数",), ("ウズベキスタン",), "x_chain"),
    "ADV-033": ("slot", "どの市町村", "に", None, "本社", False, None, (), ("レベリオンR13", "本社"), "case"),
    "ADV-028": ("open", "何人", None, None, None, False, None, (), ("2022年アジア競技大会", "ビーチバレーボール男子競技"), "case"),
    "ADV-035": ("open", "何年", None, None, None, False, None, (), ("ChatGPT",), "ga"),
}


def cut_of(text):
    q = ev.question_units(text)
    return (q.form, q.slot_phrase, q.particle, q.slot_noun, q.slot_head, q.fallback, q.y, q.y_forms, q.subject, q.subject_level)


def test_t_ev_01_the_question_cut_of_the_measured_questions(texts):
    for item, want in CUT.items():
        assert cut_of(texts[item]) == want, item


def test_t_ev_01_forms_over_the_banks(texts):
    from collections import Counter
    b2 = Counter(ev.question_units(r["question"]).form for r in bank2_rows() if r["kind"] == "intra2" and r["corpus"] == "fulllead")
    assert b2 == {"predicate": 35, "slot": 23, "open": 11}
    by_kind = {}
    for r in bank4_rows():
        by_kind.setdefault(r["kind"], Counter())[ev.question_units(r["question"]).form] += 1
    assert by_kind == {"near-fact": {"predicate": 8}, "same-slot": {"predicate": 10}, "numeric": {"predicate": 7, "open": 1},
                       "entity-swap": {"slot": 5, "predicate": 1, "open": 3}}
    for it in ("ADV-031", "ADV-033", "ADV-034", "ADV-037", "ADV-038"):
        assert ev.question_units(texts[it]).form == "slot"
    assert [ev.question_units(texts[i]).form for i in ("ADV-035", "ADV-036", "ADV-040", "ADV-028")] == ["open"] * 4


def test_t_ev_01_the_whole_cut_table_is_pinned_by_its_hash(texts):
    """The cut of all 67 distinct bank questions as canonical JSON: a change of ANY rule of design 3 is a new evidence version (L-LOOM-170), never an edit of v1."""
    tbl = {k: ev.question_units(t).to_obj(ev.SCOPE_TITLE) for k, t in sorted(texts.items())}
    assert len(tbl) == 67
    blob = json.dumps(tbl, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(blob).hexdigest() == CUT_TABLE_SHA, hashlib.sha256(blob).hexdigest()


CUT_TABLE_SHA = "df1fb2e1488f6414b0089718f8d761c48725dbcda06c7a1cb5b49c55a8a124e5"


def test_t_ev_01_the_object_begin_returns_is_read_only_and_complete(texts):
    o = ev.question_units(texts["I2-034"]).to_obj(ev.SCOPE_TITLE)
    assert o == {"evidence": "evidence.v1", "subject_scope": "clause_or_title", "form": "slot",
                 "slot": {"phrase": "何年", "particle": "に", "noun": None, "head": "設立", "fallback": False}, "y": None, "y_forms": [],
                 "subject": ["サンゴーカメラ"], "subject_level": "topic", "units": ["サンゴーカメラ", "設立"]}


# ---------------------------------------------------------------------------------------------------------------
# T-EV-02: clauses
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("sid,a0,a1,source,clause", [
    (292, 0, 1, "サンゴーカメラ#1", "1981年に永豊企業株式会社のカメラ事業部門"),        # として breaks on the right
    (143, 3, 3, "レッド計画#1", "アメリカを「青」と色分け"),                              # 青: the sentence's と is a connective, し、 is not
    (143, 1, 1, "レッド計画#1", "イギリスを「赤"),                                         # 赤: 、 breaks on the right (the closing quote lies outside the last unit)
    (86, 2, 3, "千葉神社#1", "旧社格は県社"),
    (579, 19, 19, "2025年世界水泳選手権マダガスカル選手団#0", "シンガポールで開催"),     # まで breaks on the left, された on the right
    (123, 17, 18, "CUBE JUICE#0", "ソロユニットで2002年にビクターエンタテインメント"),   # より breaks
    (324, 1, 3, "赤尾ダム#1", "29.2メートルの重力式コンクリートダム"),                    # で、 breaks
    (348, 5, 6, "ソル・クバーノ#1", "キューバの太陽」という意味"),                          # これは breaks on the left
    (152, 9, 9, "アワディー語#2", "やネパールに話者"),
])
def test_t_ev_02_the_clause_of_a_quoted_stretch(corpus, sid, a0, a1, source, clause):
    v = ev.view_of(corpus, sid)
    assert v.source == source
    lo, hi = ev.clause_bounds(v, a0, a1)
    assert ev.clause_text(v, lo, hi) == clause


def test_t_ev_02_connective_gaps():
    for g in ("", "に", "を「", "」と", "は、", "では", "には", "をも", "の", " ", "・"):
        assert ev.connective(g), g
    for g in ("、", "。", "より", "として", "という", "から", "まで", "された", "（", "は、が", "とも"):         # 「とも」 is ONE token (ハッシュ表ともいう stops at 表)
        assert not ev.connective(g), g


# ---------------------------------------------------------------------------------------------------------------
# T-EV-03 / 04: the stored final threads
# ---------------------------------------------------------------------------------------------------------------
def test_t_ev_03_the_h55d_answerable_final_threads_under_both_scopes(tmp_path, tasks):
    srv_a, srv_b = server(tmp_path, tasks, ev.SCOPE_TITLE, name="ra"), server(tmp_path, tasks, ev.SCOPE_CLAUSE, name="rb")
    want_a = {"I2-001": ["no_slot_head"], "I2-008": ["no_slot_head"], "I2-013": None, "I2-025": None, "I2-034": None, "I2-041": ["no_slot_head"],
              "R2-I013": ["wrong_arm", "no_slot_head"]}
    want_b = {"I2-001": ["no_subject", "no_slot_head"], "I2-008": ["no_subject", "no_slot_head"], "I2-013": ["no_subject"], "I2-025": ["no_subject"],
              "I2-034": ["no_subject"], "I2-041": ["no_slot_head"], "R2-I013": ["no_subject", "wrong_arm", "no_slot_head"]}
    passed_a = passed_b = 0
    for mode in ("record_only", "constructed_allowed"):
        for base in ANSWERABLE_LOOM:
            d = os.path.join(LOOMX, "runs_h55d", "%s.%s.api" % (base, mode))
            tid, text, weaves = stored_final_thread(d)
            assert text is not None and len(weaves) >= 1
            for srv, want, tag in ((srv_a, want_a, "a"), (srv_b, want_b, "b")):
                res = reweave(srv, tid, "%s_%s_%s" % (base, mode, tag), weaves)
                got = weave_codes(res)
                if tag == "a":
                    passed_a += not got
                else:
                    passed_b += not got
                w_ = ["no_slot_head"] if (tag, base, mode) == ("b", "I2-001", "constructed_allowed") else want[base]          # 連想配列 sits in a sentence that holds the subject
                if w_ is None:
                    assert got == [] and res["refusals"] == [] and len(res["evidence"]) == 1, (base, mode, tag, got)
                else:
                    assert [c for _, c in got] == [w_], (base, mode, tag, got)
    assert (passed_a, passed_b) == (6, 0)                       # under (a) the exact hits I2-013 / I2-025 / I2-034 pass in BOTH modes (3 + 3); under (b) none


def test_t_ev_03_the_evidence_a_passing_quote_carries(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    res = reweave(srv, "bank2/I2-034.record_only", "r1", final_weaves(rows(os.path.join(LOOMX, "runs_h55d", "I2-034.record_only.api"))))
    [e] = res["evidence"]
    assert e == {"w": 1, "sid": 292, "source": "サンゴーカメラ#1", "clause": "1981年に永豊企業株式会社のカメラ事業部門", "subject": [{"run": "サンゴーカメラ", "via": "title"}],
                 "slot": {"particle": "に", "arm": "-x"}} and res["ev"] == "evidence.v1"
    res = reweave(srv, "bank2/I2-013.record_only", "r2", final_weaves(rows(os.path.join(LOOMX, "runs_h55d", "I2-013.record_only.api"))))
    [e] = res["evidence"]
    assert e["copula"] == "Y は A" and e["y"] == "旧社格" and e["subject"] == [{"run": "千葉神社", "via": "title"}] and e["clause"] == "旧社格は県社"
    res = reweave(srv, "bank2/I2-025.record_only", "r3", final_weaves(rows(os.path.join(LOOMX, "runs_h55d", "I2-025.record_only.api"))))
    [e] = res["evidence"]
    assert e["subject"] == [{"run": "レッド計画", "via": "title"}, {"run": "アメリカ", "via": "clause"}] and e["slot"] == {"particle": "と", "arm": "-y"}


def test_t_ev_04_adv_001_and_adv_010_are_refused_with_the_designs_messages(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    title = "2025年世界水泳選手権マダガスカル選手団"
    for mode in ("record_only", "constructed_allowed"):
        tid, text, weaves = stored_final_thread(os.path.join(LOOMX, "runs_unans_adv", "ADV-010.%s.api" % mode))
        assert text == "シンガポール"
        res = reweave(srv, tid, "a10" + mode, weaves)
        [r] = [r for r in res["refusals"] if r["type"] == "no_evidence"]
        [w] = r["weaves"]
        assert w["codes"] == ["no_subject", "no_slot_head"] and w["clause"] == "シンガポールで開催" and w["sid"] == 579 and w["answer"] == "シンガポール"
        assert w["messages"] == ["the subject 「競技会場」 of the question is not in the clause 「シンガポールで開催」 of sentence 579 (nor in its article title 「%s」)" % title,
                                 "the asked item 「名称」 is not in the clause 「シンガポールで開催」: this sentence does not state what is asked"]
    tid, text, weaves = stored_final_thread(os.path.join(LOOMX, "runs_unans_adv", "ADV-001.constructed_allowed.api"))
    assert text == "2002年"
    res = reweave(srv, tid, "a1ca", weaves)
    [r] = [r for r in res["refusals"] if r["type"] == "no_evidence"]
    [w] = r["weaves"]
    assert w["codes"] == ["no_slot_head"] and w["clause"] == "ソロユニットで2002年にビクターエンタテインメント"
    assert w["messages"] == ["the asked item 「月日」 is not in the clause 「ソロユニットで2002年にビクターエンタテインメント」: this sentence does not state what is asked"]
    tid, text, weaves = stored_final_thread(os.path.join(LOOMX, "runs_unans_adv", "ADV-001.record_only.api"))
    assert text == "2002年メジャーデビュー" and len(weaves) == 2
    res = reweave(srv, tid, "a1ro", weaves)
    [r] = [r for r in res["refusals"] if r["type"] == "no_evidence"]
    assert [(w["answer"], w["codes"]) for w in r["weaves"]] == [("2002年", ["no_slot_head"]), ("メジャー・デビュー", ["no_slot_head", "answer_holds_question_unit"])]
    assert r["weaves"][1]["messages"][1] == "the answer contains 「メジャーデビュー」, a word of the question; quote only what answers"


# ---------------------------------------------------------------------------------------------------------------
# T-EV-05: the trap values; T-EV-06: the admission sweep and the reach number
# ---------------------------------------------------------------------------------------------------------------
def test_t_ev_05_the_bank4_trap_values_are_refused(corpus):
    from collections import Counter
    aligned = Counter()
    for r in bank4_rows():
        qu = ev.question_units(r["question"])
        occ = occurrences(corpus, r["trap"])
        if occ:
            aligned[r["kind"]] += 1
        for sid, i0, i1 in occ:
            for scope in SCOPES:
                j = ev.judge_quote(corpus, qu, scope, sid, "WORD", i0, i1)
                assert j["codes"], (r["#id"], r["trap"], sid, scope)
    assert aligned == {"near-fact": 8, "same-slot": 8, "numeric": 8, "entity-swap": 9} and sum(aligned.values()) == 33


def test_t_ev_06_the_reach_over_the_whole_bank2_is_12_of_69_and_0_without_the_title(corpus):
    reach = {s: [] for s in SCOPES}
    n = 0
    for r in bank2_rows():
        if r["kind"] != "intra2" or r["corpus"] != "fulllead":
            continue
        n += 1
        qu = ev.question_units(r["question"])
        occ = [o for alt in r["gold"].split("|") for o in occurrences(corpus, alt)]
        for scope in SCOPES:
            if any(not ev.judge_quote(corpus, qu, scope, sid, "WORD", i0, i1)["codes"] for sid, i0, i1 in occ):
                reach[scope].append(r["#id"])
    assert n == 69
    assert reach[ev.SCOPE_TITLE] == ["I2-003", "I2-004", "I2-005", "I2-006", "I2-013", "I2-014", "I2-018", "I2-025", "I2-034", "R2-I005", "R2-I007", "R2-I017"]
    assert reach[ev.SCOPE_CLAUSE] == []


# slow (about 25 s): 67 questions x 2 scopes x every WORD unit of the 592 sentences
def test_t_ev_06_no_single_unit_of_the_corpus_passes_for_an_unanswerable_question(corpus, texts):
    unans = [r["#id"] for r in bank2_rows() if r["kind"] == "unans" and r["corpus"] == "fulllead"] + [r["#id"] for r in bank4_rows()]
    bases = [b for b in texts if b not in ANSWERABLE_LOOM and (b in unans or b.startswith(("UF-", "R2-U")))]
    assert len(bases) == 60, len(bases)
    admitted = {}
    for scope in SCOPES:
        for b in list(texts):
            qu = ev.question_units(texts[b])
            hit = []
            for sid in range(corpus.n_sentences):
                v = ev.view_of(corpus, sid)
                for k in range(len(v.units)):
                    if not ev.judge_quote(corpus, qu, scope, sid, "WORD", k, k)["codes"]:
                        hit.append((v.units[k], sid))
            if b in bases:
                assert hit == [], (scope, b, hit[:3])
            elif b in ANSWERABLE_LOOM:
                admitted[(scope, b)] = sorted({u for u, _ in hit})
    assert {k: v for k, v in admitted.items() if v and k[0] == ev.SCOPE_TITLE} == {
        (ev.SCOPE_TITLE, "I2-013"): ["県"], (ev.SCOPE_TITLE, "I2-025"): ["青"], (ev.SCOPE_TITLE, "I2-034"): ["年"], (ev.SCOPE_TITLE, "I2-041"): ["Sol"]}
    assert {k: v for k, v in admitted.items() if v and k[0] == ev.SCOPE_CLAUSE} == {(ev.SCOPE_CLAUSE, "I2-041"): ["Sol"]}


# ---------------------------------------------------------------------------------------------------------------
# T-EV-07: the ledgers before the gate
# ---------------------------------------------------------------------------------------------------------------
def _stored_run_dirs():
    dirs = []
    for d in sorted(glob.glob(os.path.join(LOOMX, "runs*")) + glob.glob(os.path.join(LOOMX, "baseline_scripted", "runs"))):
        if "aborted" in d:
            continue                                                    # the half-made first attempt of the LOOM-evidence-3 measurement (an earlier build of this gate), kept as it is
        dirs += [os.path.join(d, r) for r in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, r, "ops.jsonl"))]
    return dirs


def test_t_ev_07_every_ledger_made_before_the_gate_still_verifies_and_replays_identical():
    old = [d for d in _stored_run_dirs() if not re.search(r"runs_(h55e|unans_e|unans_adv_e)", d)]
    assert len(old) >= 390
    bad = []
    for d in old:
        v = lg.verify(d)
        if v["status"] != "OK" or v["replay"]["status"] != "IDENTICAL":
            bad.append((d, v["status"]))
        r0 = rows(d)[0]["result"]
        assert "evidence_profile" not in r0 and "question" not in r0 and "evidence" not in r0["rules"]            # no gate: the begin row is as it was
        assert not any(r["op"] == "emit" and "ev" in r["result"] for r in rows(d))
    assert bad == []


def test_t_ev_07_the_measurement_ledgers_of_the_gate_verify_and_carry_the_profile():
    new = [d for d in _stored_run_dirs() if re.search(r"runs_(h55e|unans_e|unans_adv_e)", d)]
    assert len(new) == 140
    for d in new:
        v = lg.verify(d)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", d
        r0 = rows(d)[0]["result"]
        assert r0["evidence_profile"] == {"version": "evidence.v1", "subject_scope": "clause_or_title"} and r0["question"]["evidence"] == "evidence.v1"
        assert all(r["args"]["wv"] == "weave_span.v3" for r in rows(d) if r["op"] == "weave_span")


# ---------------------------------------------------------------------------------------------------------------
# T-EV-08: a new v1 run and its replay
# ---------------------------------------------------------------------------------------------------------------
def _scripted_i2_013(srv, rid="r1"):
    b = srv.begin("bank2/I2-013.record_only", "test", rid)
    assert srv.call("read_sentence", {"run_id": rid, "sid": 86})["ok"]
    assert srv.call("weave_span", {"run_id": rid, "sid": 86, "tier": "RUN", "first": "県社", "last": "県社"})["ok"]
    e = srv.call("emit", {"run_id": rid})
    return b, e


def test_t_ev_08_a_new_run_records_the_profile_and_the_question_and_replays_identically(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    b, e = _scripted_i2_013(srv)
    assert e["ok"] and e["text"] == "県社" and e["ev"] == "evidence.v1" and len(e["evidence"]) == 1
    assert b["evidence_profile"] == {"version": "evidence.v1", "subject_scope": "clause_or_title"}
    assert b["question"] == ev.question_units("千葉神社の旧社格は何ですか").to_obj("clause_or_title") and "evidence" in b["rules"]
    d = tmp_path / "runs" / "r1"
    r0 = rows(d)[0]["result"]
    assert r0["question"] == b["question"] and r0["evidence_profile"] == b["evidence_profile"]                 # in the hashed row 0
    assert rows(d)[[r["op"] for r in rows(d)].index("weave_span")]["args"]["wv"] == WEAVE_SPAN_V3 == WEAVE_SPAN_WV
    v = lg.verify(d)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    emit_row = [r for r in rows(d) if r["op"] == "emit"][0]
    assert emit_row["result"]["ev"] == "evidence.v1"


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


def test_t_ev_08_a_forged_question_is_replay_differs_and_an_unknown_profile_is_inputs(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    _scripted_i2_013(srv, "f1")
    _scripted_i2_013(srv, "f2")
    d1, d2 = tmp_path / "runs" / "f1", tmp_path / "runs" / "f2"
    _reseal(d1, lambda rs: rs[0]["result"]["question"].update(subject=[]))
    assert lg.verify_chain(d1)["status"] == "OK"
    v = lg.verify(d1)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"] == {"i": 0, "field": "result"}
    _reseal(d2, lambda rs: rs[0]["result"]["evidence_profile"].update(version="evidence.v9"))
    v = lg.verify(d2)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "evidence_profile_unknown"
    d3 = tmp_path / "runs" / "f3"
    _scripted_i2_013(srv, "f3")
    _reseal(d3, lambda rs: rs[0]["result"]["evidence_profile"].update(subject_scope="title"))
    assert lg.verify(d3)["replay"]["mismatch"] == "evidence_profile_unknown"


def test_t_ev_08_the_scope_is_recorded_and_replayed_as_recorded(tmp_path, tasks):
    for scope in SCOPES:
        srv = server(tmp_path, tasks, scope, name="r_" + scope)
        b, e = _scripted_i2_013(srv, "s1")
        assert b["evidence_profile"]["subject_scope"] == scope and b["question"]["subject_scope"] == scope
        assert e["ok"] is (scope == ev.SCOPE_TITLE)
        assert lg.verify(tmp_path / ("r_" + scope) / "s1")["replay"]["status"] == "IDENTICAL"


def test_t_ev_08_evidence_off_writes_the_begin_row_of_old(tmp_path, tasks):
    srv = server(tmp_path, tasks, evidence="off")
    b = srv.begin("bank2/I2-013.record_only", "t", "o1")
    assert "evidence_profile" not in b and "question" not in b and "evidence" not in b["rules"]
    assert lg.verify(tmp_path / "runs" / "o1")["status"] == "OK"


# ---------------------------------------------------------------------------------------------------------------
# T-EV-09 / 10 / 11: quotation only; the order of refusals; the echo rule
# ---------------------------------------------------------------------------------------------------------------
def _refused_evidence(res):
    assert res["ok"] is False and res["refusal"] == "no_evidence", res
    [r] = [r for r in res["detail"]["refusals"] if r["type"] == "no_evidence"]
    return r


def test_t_ev_09_a_hand_seated_record_cross_is_not_quoted(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    srv.begin("bank2/I2-013.record_only", "t", "h1")
    call = lambda tool, **a: srv.call(tool, dict(a, run_id="h1"))
    uid = call("add", text="県社", kind="record", tier="RUN")["uid"]
    cid = call("open_cross", tier="RUN", L=1)["cid"]
    call("seat", cid=cid, seat="centre", uid=uid)
    call("link", cid=cid)
    r = _refused_evidence(call("emit"))
    assert r["weaves"] == [] and [(c["cid"], c["code"]) for c in r["crosses"]] == [(cid, "not_quoted")]


def test_t_ev_09_a_constructed_unit_is_refused_in_both_modes_in_prose(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    srv.begin("bank2/I2-013.constructed_allowed", "t", "c1")
    call = lambda tool, **a: srv.call(tool, dict(a, run_id="c1"))
    uid = call("add", text="ΩΩ", kind="constructed")["uid"]
    cid = call("open_cross", tier="RUN", L=1)["cid"]
    call("seat", cid=cid, seat="centre", uid=uid)
    call("link", cid=cid)
    r = _refused_evidence(call("emit"))
    assert sorted((c["cid"], c["code"]) for c in r["crosses"]) == [(cid, "constructed_unit"), (cid, "not_quoted")]
    # a constructed unit AFTER an evidenced quote is still refused: the quote passes on its own, the extra cross does not
    assert call("weave_span", sid=86, tier="RUN", first="県社", last="県社")["ok"]
    r = _refused_evidence(call("emit"))
    assert sorted(c["code"] for c in r["crosses"]) == ["constructed_unit", "not_quoted"] and r["weaves"] == []


def test_t_ev_09_changing_one_cross_of_a_weave_makes_the_weave_not_quoted(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    sid = 292                                                                  # 1981 + 年 (two crosses) of I2-034
    def start(rid):
        srv.begin("bank2/I2-034.record_only", "t", rid)
        r = srv.call("weave_span", {"run_id": rid, "sid": sid, "tier": "WORD", "first": "1981", "last": "年"})
        assert r["ok"] and len(r["crosses"]) == 2
        assert srv.call("read", {"run_id": rid})["refusals"] == []
        return [c["cid"] for c in r["crosses"]]
    c1, c2 = start("w0")
    assert srv.call("emit", {"run_id": "w0"})["ok"]                            # the intact weave passes
    c1, c2 = start("w1")                                                       # drop one cross
    assert srv.call("drop", {"run_id": "w1", "cid": c2})["ok"]
    r = _refused_evidence(srv.call("emit", {"run_id": "w1"}))
    assert [(c["cid"], c["code"]) for c in r["crosses"]] == [(c1, "not_quoted")] and r["weaves"] == []
    c1, c2 = start("w2")                                                       # unseat and seat the same unit again
    uid = srv.call("status", {"run_id": "w2"})["crosses"][c1]["seats"]["centre"]
    assert srv.call("unseat", {"run_id": "w2", "cid": c1, "seat": "centre"})["ok"] and srv.call("seat", {"run_id": "w2", "cid": c1, "seat": "centre", "uid": uid})["ok"]
    assert sorted(c["cid"] for c in _refused_evidence(srv.call("emit", {"run_id": "w2"}))["crosses"]) == [c1, c2]                # the weave is no longer intact: both are not quoted
    c1, c2 = start("w3")                                                       # unlink and link again at the same place keeps the text and the order: still a quote
    assert srv.call("unlink", {"run_id": "w3", "cid": c2})["ok"] and srv.call("link", {"run_id": "w3", "cid": c2})["ok"]
    assert srv.call("emit", {"run_id": "w3"})["ok"]
    c1, c2 = start("w4")                                                       # reorder the thread: not consecutive in creation order
    assert srv.call("unlink", {"run_id": "w4", "cid": c1})["ok"] and srv.call("link", {"run_id": "w4", "cid": c1})["ok"]
    assert sorted(c["cid"] for c in _refused_evidence(srv.call("emit", {"run_id": "w4"}))["crosses"]) == [c1, c2]
    srv.begin("bank2/I2-025.record_only", "t", "w5")                           # swap: アメリカを青 -> a swapped cross is not a quote
    r = srv.call("weave_span", {"run_id": "w5", "sid": 143, "tier": "WORD", "first": "アメリカ", "last": "青"})
    cid = r["crosses"][0]["cid"]
    assert srv.call("swap", {"run_id": "w5", "cid": cid, "seat_a": "-z:0", "seat_b": "+z:0"})["ok"]           # a move of アメリカ to the が arm: no longer the quoted text
    assert [(c["cid"], c["code"]) for c in _refused_evidence(srv.call("emit", {"run_id": "w5"}))["crosses"]] == [(cid, "not_quoted")]


def test_t_ev_10_an_unstable_and_evidence_less_thread_lists_both_and_no_evidence_comes_first(tmp_path, tasks):
    srv = server(tmp_path, tasks)
    srv.begin("bank2/I2-025.record_only", "t", "o1")
    r = srv.call("weave_span", {"run_id": "o1", "sid": 143, "tier": "WORD", "first": "アメリカ", "last": "青"})
    assert r["ok"] and r["text"] == "アメリカを青"
    res = srv.call("emit", {"run_id": "o1"})
    assert res["ok"] is False and res["refusal"] == "no_evidence"
    types = [x["type"] for x in res["detail"]["refusals"]]
    assert types == ["no_evidence", "unstable_cross"] and res["detail"]["refusals"][1]["advice"].startswith("this stretch is faithful to sentence 143")
    emit_row = [x for x in rows(tmp_path / "runs" / "o1") if x["op"] == "emit"][0]
    assert emit_row["result"]["refusal"] == "no_evidence"
    # a stable cross without evidence is refused too, and an evidenced cross that is unstable is refused by the key only
    srv.begin("bank2/I2-013.record_only", "t", "o2")
    assert srv.call("weave_span", {"run_id": "o2", "sid": 86, "tier": "RUN", "first": "旧社格", "last": "県社"})["ok"]
    res = srv.call("emit", {"run_id": "o2"})
    assert res["refusal"] == "no_evidence"
    [w] = _refused_evidence(res)["weaves"]
    assert w["codes"] == ["no_slot_head", "answer_holds_question_unit"]                   # the answer holds the asked item 旧社格 itself, so it cannot also be read as 「Y は A」


def test_t_ev_11_the_answer_holds_no_word_of_the_question(corpus, texts):
    qu = ev.question_units(texts["I2-013"])
    sid = 86
    v = ev.view_of(corpus, sid)
    j = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", 0, 3)              # 旧社格は県社
    assert "answer_holds_question_unit" in j["codes"] and j["messages"][-1].startswith("the answer contains 「")
    j = ev.judge_quote(corpus, ev.question_units(texts["I2-025"]), ev.SCOPE_TITLE, 143, "WORD", 2, 3)             # アメリカを青
    assert j["codes"][-1] == "answer_holds_question_unit" and j["messages"][-1] == "the answer contains 「アメリカ」, a word of the question; quote only what answers"
    sid_hash = occurrences(corpus, "ハッシュ表")[0][0]
    j = ev.judge_quote(corpus, ev.question_units(texts["I2-001"]), ev.SCOPE_TITLE, sid_hash, "WORD", *occurrences(corpus, "ハッシュ表")[0][1:])
    assert "answer_holds_question_unit" not in j["codes"] and j["codes"] == ["no_slot_head"]          # ハッシュ is not a unit of the question: ハッシュテーブル is
    j = ev.judge_quote(corpus, ev.question_units(texts["I2-034"]), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert j["codes"] == []


def test_t_ev_11_a_stretch_that_is_not_on_word_boundaries_and_an_open_question(corpus, texts):
    j = ev.judge_quote(corpus, ev.question_units(texts["I2-034"]), ev.SCOPE_TITLE, 292, "RUN", 0, 0)             # the RUN unit 「1981年に」 holds a particle
    assert j["codes"] == ["answer_not_word_aligned"] and j["messages"][0].startswith("the stretch 「1981年に」 does not begin and end on words of sentence 292")
    j = ev.judge_quote(corpus, ev.question_units(texts["ADV-028"]), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert "question_form_open" in j["codes"] and "has no particle after its question word" in j["messages"][0]
    j = ev.judge_quote(corpus, ev.question_units("イギリスをどう塗りましたか"), ev.SCOPE_TITLE, 143, "WORD", 3, 3)
    assert "question_form_open" in j["codes"]


def test_t_ev_11_the_coordinators_example_needs_both_subject_words(corpus):
    qu = ev.question_units("レッド計画ではイギリスを何色としていましたか")
    assert qu.subject == ("レッド計画", "イギリス") and qu.particle == "と"
    j = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 3, 3)               # 青: アメリカを「青」と -- イギリス is not in its clause
    assert j["codes"] == ["no_subject"] and "「イギリス」" in j["messages"][0] and "「アメリカを「青」と色分け」" in j["messages"][0]
    j = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 1, 1)               # 赤: the subject is there but 、 follows
    assert j["codes"] == ["wrong_arm"]


# ---------------------------------------------------------------------------------------------------------------
# T-EV-12: determinism
# ---------------------------------------------------------------------------------------------------------------
_DET = r'''
import hashlib, json, sys
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus
corpus = Corpus.load(open(sys.argv[1], "rb").read())
out = []
for f in ("tasks_bank2.jsonl", "tasks_unans.jsonl", "tasks_unans_adv.jsonl"):
    for ln in open(sys.argv[2] + "/" + f, encoding="utf-8"):
        r = json.loads(ln)
        out.append(ev.question_units(r["text"]).to_obj("clause_or_title"))
qu = ev.question_units("千葉神社の旧社格は何ですか")
for sid, a0, a1 in ((86, 0, 3), (86, 2, 3), (292, 0, 1), (143, 3, 3), (579, 19, 19)):
    for scope in ("clause_or_title", "clause"):
        out.append(ev.judge_quote(corpus, ev.question_units("サンゴーカメラは何年に設立されましたか"), scope, sid, "WORD", a0, a1))
        out.append(ev.judge_quote(corpus, qu, scope, sid, "WORD", a0, a1))
print(hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
'''


def test_t_ev_12_the_cut_the_clause_and_the_payload_are_identical_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([PY, "-c", _DET, CORPUS, LOOMX], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert p.returncode == 0, p.stderr[-800:]
        digests.add(p.stdout.strip())
    assert len(digests) == 1


# ---------------------------------------------------------------------------------------------------------------
# T-EV-13 / 14: the gate reads what the reader's own records say
# ---------------------------------------------------------------------------------------------------------------
def test_t_ev_13_the_slot_arm_is_an_attachment_of_the_readers_records(corpus):
    from verantyx.line3 import wiring
    recs = wiring.records_of(corpus.space)
    for sid, a1, p in ((292, 1, "に"), (143, 3, "と")):
        v = ev.view_of(corpus, sid)
        end = v.spans[a1][1]
        atts = [a for a in recs.attachments if a.sid == sid and a.tier == "WORD" and a.end == end]
        assert [a.particle for a in atts] == [p]
    j = ev.judge_quote(corpus, ev.question_units("サンゴーカメラは何年に設立されましたか"), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert j["evidence"]["slot"]["particle"] == "に"
    # a wrong arm is also what the records say: 青 is followed by と, so the question that asks for the word before を refuses it
    atts = [a for a in recs.attachments if a.sid == 143 and a.tier == "WORD" and a.unit == "青"]
    assert [a.particle for a in atts] == ["と"]
    j = ev.judge_quote(corpus, ev.question_units("レッド計画ではアメリカを何を作りましたか"), ev.SCOPE_TITLE, 143, "WORD", 3, 3)
    assert "wrong_arm" in j["codes"]


def test_t_ev_14_the_run_cut_is_the_readers_query_units(corpus, texts):
    from verantyx.line3 import wiring
    from verantyx.line3 import grammar as gm
    for b, t in texts.items():
        units = [u for u in wiring.intake(corpus.space, t).units if any(gm._content(w) for w, _, _ in gm.words_of(u))]
        assert ev.run_units(t) == units, b


# ---------------------------------------------------------------------------------------------------------------
# T-EV-15: code tasks and the prompts
# ---------------------------------------------------------------------------------------------------------------
def test_t_ev_15_code_tasks_have_no_profile_and_a_bare_run_has_none(tmp_path):
    from loom_common import task as ltask
    from verantyx.loom.ops import Run
    srv = LoomServer([ltask("code/ca", "constructed_allowed", lang="code")], str(tmp_path / "runs"))                # evidence v1 is the default of the server
    b = srv.begin("code/ca", "m", "k1")
    assert b["ok"] and "evidence_profile" not in b and "question" not in b and "evidence" not in b["rules"]
    corpus = Corpus.load(open(CORPUS, "rb").read())
    r = Run(corpus, ltask("p", "record_only"), "m", "x")
    assert r.evidence is None and "evidence_profile" not in r.begin_body()["result"]
    with pytest.raises(ValueError):
        Run(corpus, ltask("p", "record_only"), "m", "x", evidence=("evidence.v0", "clause"))


def test_t_ev_15_the_server_defaults_are_the_gate_with_the_title(tmp_path, tasks):
    srv = LoomServer(list(tasks.values()), str(tmp_path / "runs"))
    assert srv.evidence_profile == ("evidence.v1", "clause_or_title")
    with pytest.raises(ValueError):
        LoomServer(list(tasks.values()), str(tmp_path / "r2"), evidence="v2")
    with pytest.raises(ValueError):
        LoomServer(list(tasks.values()), str(tmp_path / "r3"), subject_scope="title")


def test_t_ev_15_the_examples_in_the_agent_prompts_pass_the_gate(tmp_path):
    sents = ["青葉堂の旧称は松風庵。", "青葉堂は1820年に建てられた。", "青葉堂は緑町にある。"]
    p = tmp_path / "toy.jsonl"
    p.write_text("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": "青葉堂", "sent": s, "source": "青葉堂#%d" % i}, ensure_ascii=False) + "\n"
                         for i, s in enumerate(sents)), encoding="utf-8")
    tks = [{"task_id": "t/%d" % i, "text": q, "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": str(p)}
           for i, q in enumerate(["青葉堂の旧称は何ですか", "青葉堂は何年に建てられましたか"])]
    srv = LoomServer(tks, str(tmp_path / "runs"), evidence="v1", subject_scope="clause")             # the strictest scope: no title needed
    srv.begin("t/0", "m", "e0")
    assert srv.call("weave_span", {"run_id": "e0", "sid": 0, "tier": "RUN", "first": "松風庵", "last": "松風庵"})["ok"]
    e = srv.call("emit", {"run_id": "e0"})
    assert e["ok"] and e["text"] == "松風庵" and e["evidence"][0]["copula"] == "Y は A"
    srv.begin("t/1", "m", "e1")
    assert srv.call("weave_span", {"run_id": "e1", "sid": 1, "tier": "WORD", "first": "1820", "last": "年"})["ok"]
    e = srv.call("emit", {"run_id": "e1"})
    assert e["ok"] and e["text"] == "1820年" and e["evidence"][0]["slot"]["particle"] == "に"
    # the longer text the prompt warns against (1820年に建て) is not the answer: the particle after ITS last word is not に, and it holds the slot head
    srv.begin("t/1", "m", "e2")
    assert srv.call("weave_span", {"run_id": "e2", "sid": 1, "tier": "WORD", "first": "1820", "last": "建て"})["ok"]
    [w] = _refused_evidence(srv.call("emit", {"run_id": "e2"}))["weaves"]
    assert "wrong_arm" in w["codes"] or "answer_holds_question_unit" in w["codes"]
    for body in (open(os.path.join(ROOT, ".claude/agents", f), encoding="utf-8").read() for f in ("loom-weaver.md", "loom-weaver-record-only.md")):
        assert "青葉堂の旧称は松風庵" in body and "青葉堂は1820年に建てられた" in body


# ---------------------------------------------------------------------------------------------------------------
# the harness and the scorer with the gate (a fake client; no model)
# ---------------------------------------------------------------------------------------------------------------
def _harness():
    import importlib.util
    name = "loom_harness"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(LOOMX, "harness.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _api(tmp_path, H, base, mode, script, bank_file, **kw):
    from verantyx.loom import driver as drv
    from verantyx.loom.ops import MODEL_OPS
    bank_path = os.path.join(LOOMX, bank_file)
    bank = H.score.load_bank(bank_path)
    client = drv.ReplayClient(script, allowed_tools={n for n in MODEL_OPS if n != "begin"} | {"done"})
    tools = H.mcp_tool_objects(bank_path, str(tmp_path / "toolruns"))
    out = H.run(H.select_task(bank, base, mode), "api", bank_path=bank_path, bank=bank, gold=H.score.load_gold(), runs_dir=str(tmp_path / "runs"),
                results_dir=str(tmp_path / "res"), model="claude-haiku-4-5", client=client, mcp_tools=tools, **kw)
    return client, out


L = lambda name, **a: ("tool", name, a)


def test_the_api_harness_runs_with_the_gate_by_default_and_the_first_message_carries_the_question(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    H = _harness()
    client, (rs, path, obj) = _api(tmp_path, H, "I2-013", "record_only", [[L("read_sentence", sid=86)], [L("weave_span", sid=86, tier="RUN", first="県社", last="県社")], [L("emit")]],
                                   "tasks_bank2.jsonl")
    assert rs.status == "hit" and rs.text == "県社" and rs.stop_layer == "L_none"
    first = client.calls[0]
    assert first["n_messages"] == 1
    d = tmp_path / "runs" / "I2-013.record_only.api"
    r0 = rows(d)[0]["result"]
    assert r0["evidence_profile"]["subject_scope"] == "clause_or_title" and r0["question"]["subject"] == ["千葉神社"]
    from verantyx.loom import driver as drv
    fm = drv.first_message(dict(r0, isolated=False))
    assert '"question"' in fm and "千葉神社" in fm and '"evidence"' in fm                  # the loom's own cut and the rule reach the model, read-only
    assert [t["name"] for t in first["tools"]] and "weave_span" in [t["name"] for t in first["tools"]]


def test_a_refused_quote_is_a_structural_refusal_with_its_codes_in_the_layer_report(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    H = _harness()
    script = [[L("read_sentence", sid=579)], [L("weave_span", sid=579, tier="WORD", first="シンガポール", last="シンガポール")], [L("emit")], [L("abstain", type="unknown")]]
    client, (rs, path, obj) = _api(tmp_path, H, "ADV-010", "record_only", script, "tasks_unans_adv.jsonl")
    assert rs.status == "abstained_correct" and rs.stop_layer == "L_struct"
    assert rs.layer["struct_refusals"] == {"no_evidence": 1} and rs.layer["struct_codes"] == {"no_evidence:no_slot_head": 1, "no_evidence:no_subject": 1}
    assert rs.layer["stop_layer_detail"] == "then_abstained"


def test_run_bank_and_harness_flags_choose_the_gate(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    H = _harness()
    script = [[L("read_sentence", sid=579)], [L("weave_span", sid=579, tier="WORD", first="シンガポール", last="シンガポール")], [L("emit")]]
    client, (rs, path, obj) = _api(tmp_path, H, "ADV-010", "record_only", script, "tasks_unans_adv.jsonl", evidence="off")
    assert rs.status == "answered_unans" and rs.text == "シンガポール"                      # evidence off = the gate of before: the trap value goes out
    assert "evidence_profile" not in rows(tmp_path / "runs" / "ADV-010.record_only.api")[0]["result"]
