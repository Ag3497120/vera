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


def jq1(*args, **kw):
    """`evidence.judge_quote` under evidence.v1 (the rules of the first build): the pins of T-EV-01..15 below are v1's, and the 140 stored measurement ledgers carry v1.
    The tests of evidence.v2 (T-EV-16..) call `ev.judge_quote` itself (its default is the latest version)."""
    kw.setdefault("version", ev.EVIDENCE_V1)
    return ev.judge_quote(*args, **kw)


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
                j = jq1(corpus, qu, scope, sid, "WORD", i0, i1)
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
            if any(not jq1(corpus, qu, scope, sid, "WORD", i0, i1)["codes"] for sid, i0, i1 in occ):
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
                    if not jq1(corpus, qu, scope, sid, "WORD", k, k)["codes"]:
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


def _recorded_evidence(d):
    """The evidence version the run's `begin` row recorded (None = a ledger made before the gate).  The stored runs are selected by THIS, never by the name of their folder
    (LOOM-evidence-v4: the evidence.v2 runs h55f / reach_f / unans_f / unans_adv_f are tracked folders of the same shape as the evidence.v1 ones)."""
    ep = rows(d)[0]["result"].get("evidence_profile")
    return None if ep is None else ep["version"]


def _runs_by_version():
    out = {}
    for d in _stored_run_dirs():
        out.setdefault(_recorded_evidence(d), []).append(d)
    return out


def test_t_ev_07_every_ledger_made_before_the_gate_still_verifies_and_replays_identical():
    old = _runs_by_version().get(None, [])
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
    new = _runs_by_version().get("evidence.v1", [])
    assert len(new) == 140
    for d in new:
        v = lg.verify(d)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", d
        r0 = rows(d)[0]["result"]
        assert r0["evidence_profile"] == {"version": "evidence.v1", "subject_scope": "clause_or_title"} and r0["question"]["evidence"] == "evidence.v1"
        assert all(r["args"]["wv"] == "weave_span.v3" for r in rows(d) if r["op"] == "weave_span")


def test_t_ev_07_the_evidence_v2_ledgers_verify_and_carry_the_profile():
    new = _runs_by_version().get("evidence.v2", [])
    assert len(new) == 200
    for d in new:
        v = lg.verify(d)
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", d
        r0 = rows(d)[0]["result"]
        assert r0["evidence_profile"]["version"] == "evidence.v2" and r0["question"]["evidence"] == "evidence.v2"
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
    j = jq1(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", 0, 3)              # 旧社格は県社
    assert "answer_holds_question_unit" in j["codes"] and j["messages"][-1].startswith("the answer contains 「")
    j = jq1(corpus, ev.question_units(texts["I2-025"]), ev.SCOPE_TITLE, 143, "WORD", 2, 3)             # アメリカを青
    assert j["codes"][-1] == "answer_holds_question_unit" and j["messages"][-1] == "the answer contains 「アメリカ」, a word of the question; quote only what answers"
    sid_hash = occurrences(corpus, "ハッシュ表")[0][0]
    j = jq1(corpus, ev.question_units(texts["I2-001"]), ev.SCOPE_TITLE, sid_hash, "WORD", *occurrences(corpus, "ハッシュ表")[0][1:])
    assert "answer_holds_question_unit" not in j["codes"] and j["codes"] == ["no_slot_head"]          # ハッシュ is not a unit of the question: ハッシュテーブル is
    j = jq1(corpus, ev.question_units(texts["I2-034"]), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert j["codes"] == []


def test_t_ev_11_a_stretch_that_is_not_on_word_boundaries_and_an_open_question(corpus, texts):
    j = jq1(corpus, ev.question_units(texts["I2-034"]), ev.SCOPE_TITLE, 292, "RUN", 0, 0)             # the RUN unit 「1981年に」 holds a particle
    assert j["codes"] == ["answer_not_word_aligned"] and j["messages"][0].startswith("the stretch 「1981年に」 does not begin and end on words of sentence 292")
    j = jq1(corpus, ev.question_units(texts["ADV-028"]), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert "question_form_open" in j["codes"] and "has no particle after its question word" in j["messages"][0]
    j = jq1(corpus, ev.question_units("イギリスをどう塗りましたか"), ev.SCOPE_TITLE, 143, "WORD", 3, 3)
    assert "question_form_open" in j["codes"]


def test_t_ev_11_the_coordinators_example_needs_both_subject_words(corpus):
    qu = ev.question_units("レッド計画ではイギリスを何色としていましたか")
    assert qu.subject == ("レッド計画", "イギリス") and qu.particle == "と"
    j = jq1(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 3, 3)               # 青: アメリカを「青」と -- イギリス is not in its clause
    assert j["codes"] == ["no_subject"] and "「イギリス」" in j["messages"][0] and "「アメリカを「青」と色分け」" in j["messages"][0]
    j = jq1(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 1, 1)               # 赤: the subject is there but 、 follows
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
for sid, a0, a1 in ((86, 0, 3), (86, 2, 3), (86, 2, 2), (292, 0, 1), (292, 1, 1), (143, 3, 3), (579, 19, 19), (254, 0, 5), (188, 2, 10)):
    for scope in ("clause_or_title", "clause"):
        for ver in ("evidence.v1", "evidence.v2"):
            out.append(ev.judge_quote(corpus, ev.question_units("サンゴーカメラは何年に設立されましたか"), scope, sid, "WORD", a0, a1, ver))
            out.append(ev.judge_quote(corpus, qu, scope, sid, "WORD", a0, a1, ver))
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
    j = jq1(corpus, ev.question_units("サンゴーカメラは何年に設立されましたか"), ev.SCOPE_TITLE, 292, "WORD", 0, 1)
    assert j["evidence"]["slot"]["particle"] == "に"
    # a wrong arm is also what the records say: 青 is followed by と, so the question that asks for the word before を refuses it
    atts = [a for a in recs.attachments if a.sid == 143 and a.tier == "WORD" and a.unit == "青"]
    assert [a.particle for a in atts] == ["と"]
    j = jq1(corpus, ev.question_units("レッド計画ではアメリカを何を作りましたか"), ev.SCOPE_TITLE, 143, "WORD", 3, 3)
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
    assert srv.evidence_profile == ("evidence.v2", "clause_or_title")                       # evidence.v2 since the review (L-LOOM-191..)
    assert LoomServer(list(tasks.values()), str(tmp_path / "r1"), evidence="v1").evidence_profile == ("evidence.v1", "clause_or_title")
    with pytest.raises(ValueError):
        LoomServer(list(tasks.values()), str(tmp_path / "r2"), evidence="v6")                  # "v3" is a rule version since LOOM-reach (L-LOOM-201), "v4" since LOOM-evidence-v4 (L-LOOM-212), "v5" since LOOM-evidence-v5 (L-LOOM-219); "v6" is the unknown one
    with pytest.raises(ValueError):
        LoomServer(list(tasks.values()), str(tmp_path / "r3"), subject_scope="title")


@pytest.mark.parametrize("ver", ["v1", "v2"])
def test_t_ev_15_the_examples_in_the_agent_prompts_pass_the_gate(tmp_path, ver):
    sents = ["青葉堂の旧称は松風庵。", "青葉堂は1820年に建てられた。", "青葉堂は緑町にある。"]
    p = tmp_path / "toy.jsonl"
    p.write_text("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": "青葉堂", "sent": s, "source": "青葉堂#%d" % i}, ensure_ascii=False) + "\n"
                         for i, s in enumerate(sents)), encoding="utf-8")
    tks = [{"task_id": "t/%d" % i, "text": q, "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": str(p)}
           for i, q in enumerate(["青葉堂の旧称は何ですか", "青葉堂は何年に建てられましたか"])]
    srv = LoomServer(tks, str(tmp_path / "runs"), evidence=ver, subject_scope="clause")             # the strictest scope: no title needed
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


# ===============================================================================================================
# evidence.v2 (the review of 2026-10-12; L-LOOM-191..): T-EV-16..20
# ===============================================================================================================
V1, V2 = ev.EVIDENCE_V1, ev.EVIDENCE_V2
REACH_V1 = ["I2-003", "I2-004", "I2-005", "I2-006", "I2-013", "I2-014", "I2-018", "I2-025", "I2-034", "R2-I005", "R2-I007", "R2-I017"]
REACH_V2 = ["I2-003", "I2-004", "I2-005", "I2-006", "I2-013", "I2-014", "I2-018", "R2-I005", "R2-I007", "R2-I017"]     # I2-025 (no slot head) and I2-034 (設立 outside the clause) are lost


def _norm(x):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKC", x).casefold() if not ch.isspace() and ch != "・")


def _probe(corpus, q, sid, i0, i1, version):
    """(answer, codes) of the stretch WORD units i0..i1 of sentence `sid` for the question text `q`, under the title scope."""
    j = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, sid, "WORD", i0, i1, version)
    return j["answer"], j["codes"]


def _expect_word_units(corpus, sid, text):
    v = ev.view_of(corpus, sid)
    assert v.text == text, v.text
    return v


# ---- T-EV-16: F1, a predicate question with no subject word is refused (reach cost 0) ---------------------------------------------------------------
def test_t_ev_16_a_predicate_question_with_no_subject_is_refused_in_v2_and_the_two_probes(corpus):
    _expect_word_units(corpus, 399, "通称はPSE (ピー・エス・イー) 。")
    q = "IEEE 488の通称は何ですか"                                       # the subject IEEE 488 comes out empty: the cut has Y = 通称 and no X
    assert ev.question_units(q).form == "predicate" and ev.question_units(q).subject == ()
    assert _probe(corpus, q, 399, 1, 1, V1) == ("PSE", [])              # v1: any 「通称は A」 anywhere passes -- パリ経済学校#1 answers a question about IEEE 488
    assert _probe(corpus, q, 399, 1, 1, V2) == ("PSE", ["question_has_no_subject"])
    j = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 399, "WORD", 1, 1, V2)
    assert j["messages"] == ["the question 「IEEE 488の通称は何ですか」 has no subject word, so a sentence cannot be tied to it"]
    q = "駅番号は何ですか"                                               # JR-Y13 of 川原石駅 (the model's text was 「JRY13」: weave_span writes letters only)
    assert ev.question_units(q).subject == ()
    assert _probe(corpus, q, 19, 2, 4, V1) == ("JR-Y13", [])
    assert _probe(corpus, q, 19, 2, 4, V2) == ("JR-Y13", ["question_has_no_subject"])
    assert _probe(corpus, "川原石駅の駅番号は何ですか", 19, 2, 4, V2) == ("JR-Y13", [])          # with its subject the same quote passes


def test_t_ev_16_the_two_probes_through_the_server_v1_emits_and_v2_refuses(tmp_path):
    from loom_common import task as ltask
    tks = [ltask("p/ieee", "record_only", text="IEEE 488の通称は何ですか"), ltask("p/eki", "record_only", text="駅番号は何ですか")]
    for ver, ok in (("v1", True), ("v2", False)):
        srv = LoomServer(tks, str(tmp_path / ("runs_" + ver)), (), evidence=ver)
        srv.begin("p/ieee", "m", "a")
        assert srv.call("weave_span", {"run_id": "a", "sid": 399, "tier": "WORD", "first": "PSE", "last": "PSE"})["ok"]
        e = srv.call("emit", {"run_id": "a"})
        assert e["ok"] is ok and (e["text"] == "PSE" if ok else e["refusal"] == "no_evidence")
        srv.begin("p/eki", "m", "b")
        assert srv.call("weave_span", {"run_id": "b", "sid": 19, "tier": "WORD", "first": "JR", "last": "13"})["ok"]
        e = srv.call("emit", {"run_id": "b"})
        assert e["ok"] is ok and (e["text"] == "JRY13" if ok else _refused_evidence(e)["weaves"][0]["codes"] == ["question_has_no_subject"])
        assert lg.verify(tmp_path / ("runs_" + ver) / "b")["replay"]["status"] == "IDENTICAL"


# ---- T-EV-17: F2, the answer is a whole word / phrase -----------------------------------------------------------------------------------------------
def test_t_ev_17_pieces_of_a_word_are_refused_in_v2_and_were_admitted_in_v1(corpus):
    probes = [("川原石駅の駅番号は何ですか", 19, 2, 2, "JR"), ("千葉神社の旧社格は何ですか", 86, 2, 2, "県"),
              ("水戸東照宮は一般に何と呼ばれていますか", 122, 6, 6, "さん"), ("サンゴーカメラは何年に設立されましたか", 292, 1, 1, "年"),
              ("中之嶽神社では日本武尊のほか、祭神は何柱ですか", 190, 1, 1, "日本"), ("数河高原はどの気候区分に属しますか", 254, 5, 5, "気候")]
    for q, sid, i0, i1, piece in probes:
        a1, c1 = _probe(corpus, q, sid, i0, i1, V1)
        a2, c2 = _probe(corpus, q, sid, i0, i1, V2)
        assert a1 == a2 == piece
        assert "answer_glued" not in c1 and "answer_glued" in c2, (piece, c1, c2)
    j = ev.judge_quote(corpus, ev.question_units("中之嶽神社では日本武尊のほか、祭神は何柱ですか"), ev.SCOPE_TITLE, 190, "WORD", 1, 1, V2)
    assert j["messages"][0] == "the stretch 「日本」 of sentence 190 is glued to a neighbouring word (it is a piece of 「日本武尊外16柱」); quote the whole word, or the whole phrase, that answers"


def test_t_ev_17_the_whole_word_or_phrase_still_passes(corpus):
    assert _probe(corpus, "千葉神社の旧社格は何ですか", 86, 2, 3, V2) == ("県社", [])
    assert _probe(corpus, "水戸東照宮は一般に何と呼ばれていますか", 122, 5, 6, V2) == ("権現さん", [])
    assert _probe(corpus, "数河高原はどの気候区分に属しますか", 254, 2, 5, V2) == ("日本海側気候", [])
    assert _probe(corpus, "川原石駅の駅番号は何ですか", 19, 2, 4, V2) == ("JR-Y13", [])                  # 「-」 joins the pieces of one token; it is not a break
    assert _probe(corpus, "ソル・クバーノというカクテル名はどういう意味ですか", 348, 5, 6, V2)[1][:1] != ["answer_crosses_break"]       # キューバの太陽: the genitive の is inside a phrase


def test_t_ev_17_an_answer_does_not_cross_a_break_or_a_particle(corpus):
    q = "数河高原はどの気候区分に属しますか"                              # 「気象条件は日本海側気候」 (the review's probe): the topic particle は is inside the stretch
    assert _probe(corpus, q, 254, 0, 5, V1) == ("気象条件は日本海側気候", [])
    a, c = _probe(corpus, q, 254, 0, 5, V2)
    assert c == ["answer_crosses_break"]
    j = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 254, "WORD", 0, 5, V2)
    assert j["messages"] == ["the stretch 「気象条件は日本海側気候」 of sentence 254 crosses 「は」: an answer is one phrase, not a stretch over a comma, a bracket or a particle"]
    q = "和歌山バスではサウスウェーブ号を何線と案内していますか"             # a multi-word answer across 「、」: it widened its own clause to both sides
    a1, c1 = _probe(corpus, q, 188, 2, 10, V1)
    assert a1 == "和歌山千葉線」、京成バス千葉イーストでは「和歌山線" and c1 == []
    assert "answer_crosses_break" in _probe(corpus, q, 188, 2, 10, V2)[1]
    a, c = _probe(corpus, "レッド計画ではアメリカを何色としていましたか", 142, 8, 13, V2)           # across 「、」 and 「（」
    assert a == "合衆国が定めた、イギリス（大英帝国" and "answer_crosses_break" in c


def test_t_ev_17_the_clause_reads_a_stack_of_particles_such_as_tomo_in_v2(corpus):
    v = ev.view_of(corpus, 188)
    assert v.gap(10) == "」とも" and not ev.connective("」とも") and ev.connective("」とも", True)
    assert ev.clause_bounds(v, 9, 10) == (5, 10) and ev.clause_bounds(v, 9, 10, True) == (5, 11)
    q = "サウスウェーブ号は、京成バス千葉イーストでは何線と案内されていますか"
    assert _probe(corpus, q, 188, 9, 10, V1) == ("和歌山線", [])
    assert _probe(corpus, q, 188, 9, 10, V2) == ("和歌山線", [])


# ---- T-EV-18: the slot head is read in the CLAUSE (owner 2026-10-12) --------------------------------------------------------------------------------
def test_t_ev_18_the_slot_head_must_be_in_the_clause_and_none_is_refused(corpus):
    q = "サンゴーカメラは何年に設立されましたか"
    assert _probe(corpus, q, 292, 0, 1, V1) == ("1981年", [])                                 # v1: 設立 anywhere in the sentence
    a, c = _probe(corpus, q, 292, 0, 1, V2)
    assert (a, c) == ("1981年", ["no_slot_head"])                                              # v2: 設立 is after 「として」, outside the clause
    j = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 292, "WORD", 0, 1, V2)
    assert j["messages"] == ["the question's predicate 「設立」 is not in the clause 「1981年に永豊企業株式会社のカメラ事業部門」 of sentence 292: this clause does not say what is asked"]
    q = "レッド計画ではアメリカを何色としていましたか"                     # a slot question with NO head (何色と + the end): v1 skipped the check, v2 refuses
    assert ev.question_units(q).slot_head is None
    assert _probe(corpus, q, 143, 3, 3, V1) == ("青", [])
    a, c = _probe(corpus, q, 143, 3, 3, V2)
    assert (a, c) == ("青", ["no_slot_head"])
    j = ev.judge_quote(corpus, ev.question_units(q), ev.SCOPE_TITLE, 143, "WORD", 3, 3, V2)
    assert j["messages"] == ["the question 「レッド計画ではアメリカを何色としていましたか」 has no predicate word after its question word, so no clause can be tied to what it asks"]


# ---- T-EV-19: F3, exactly one answer ------------------------------------------------------------------------------------------------------------------
def test_t_ev_19_two_passing_quotes_are_multiple_answers_in_v2_and_were_joined_in_v1(tmp_path, tasks):
    for ver, expect_ok in (("v1", True), ("v2", False)):
        srv = server(tmp_path, tasks, evidence=ver, name="m_" + ver)
        srv.begin("bank2/I2-013.record_only", "t", "m1")
        for _ in range(2):                                                                                              # the same passing quote twice
            assert srv.call("weave_span", {"run_id": "m1", "sid": 86, "tier": "RUN", "first": "県社", "last": "県社"})["ok"]
        r = srv.call("read", {"run_id": "m1"})
        e = srv.call("emit", {"run_id": "m1"})
        if expect_ok:
            assert e["ok"] and e["text"] == "県社県社" and len(e["evidence"]) == 2                                          # v1 emitted two answers as one text
        else:
            assert len(r["evidence"]) == 2 and e["ok"] is False and e["refusal"] == "no_evidence"
            [ref] = [x for x in e["detail"]["refusals"] if x["type"] == "no_evidence"]
            assert ref["weaves"] == [] and [c["code"] for c in ref["crosses"]] == ["multiple_answers"] and ref["crosses"][0]["cid"] == "c2"
            assert ref["cross_messages"] == ["the thread holds 2 quotes that each read as an answer (「県社」、「県社」); emit exactly one"]
            drop = srv.call("drop", {"run_id": "m1", "cid": "c2"})
            assert drop["ok"]
            e2 = srv.call("emit", {"run_id": "m1"})
            assert e2["ok"] and e2["text"] == "県社"                                                                          # one answer left: it passes
        assert lg.verify(tmp_path / ("m_" + ver) / "m1")["replay"]["status"] == "IDENTICAL"


def test_t_ev_19_the_reviewers_1981_plus_year_case_is_now_two_refusals_not_a_text(tmp_path, tasks):
    srv = server(tmp_path, tasks, evidence="v2")
    srv.begin("bank2/I2-034.record_only", "t", "y1")
    assert srv.call("weave_span", {"run_id": "y1", "sid": 292, "tier": "WORD", "first": "1981", "last": "年"})["ok"]
    assert srv.call("weave_span", {"run_id": "y1", "sid": 292, "tier": "WORD", "first": "年", "last": "年"})["ok"]
    e = srv.call("emit", {"run_id": "y1"})
    assert e["ok"] is False
    assert sorted(set(c for _, cs in weave_codes(e) for c in cs)) == ["answer_glued", "no_slot_head"]


# ---- T-EV-20: the rule version, the begin row, the old ledgers ----------------------------------------------------------------------------------------
def test_t_ev_20_a_v2_run_records_v2_and_a_v1_run_keeps_the_v1_begin_row(tmp_path, tasks):
    from verantyx.loom.ops import EVIDENCE_RULE, EVIDENCE_RULE_V2
    s1, s2 = server(tmp_path, tasks, evidence="v1", name="v1"), server(tmp_path, tasks, evidence="v2", name="v2")
    b1, b2 = s1.begin("bank2/I2-013.record_only", "t", "x"), s2.begin("bank2/I2-013.record_only", "t", "x")
    assert b1["evidence_profile"]["version"] == "evidence.v1" and b1["question"]["evidence"] == "evidence.v1" and b1["rules"]["evidence"] == EVIDENCE_RULE
    assert b2["evidence_profile"]["version"] == "evidence.v2" and b2["question"]["evidence"] == "evidence.v2" and b2["rules"]["evidence"] == EVIDENCE_RULE_V2
    assert EVIDENCE_RULE_V2.startswith(EVIDENCE_RULE) and "whole word or phrase" in EVIDENCE_RULE_V2
    assert {k: v for k, v in b1["question"].items() if k != "evidence"} == {k: v for k, v in b2["question"].items() if k != "evidence"}        # the cut itself is the same
    for name in ("v1", "v2"):
        assert lg.verify(tmp_path / name / "x")["status"] == "OK"


def test_t_ev_20_a_ledger_cannot_change_its_rule_version_and_replays_under_the_recorded_one(tmp_path, tasks):
    srv = server(tmp_path, tasks, evidence="v2", name="rv")
    b, e = _scripted_i2_013(srv, "q1")
    assert e["ok"] and e["ev"] == "evidence.v2" and e["text"] == "県社"
    d = tmp_path / "rv" / "q1"
    assert lg.verify(d)["replay"]["status"] == "IDENTICAL"
    _reseal(d, lambda rs: rs[0]["result"]["evidence_profile"].update(version="evidence.v1"))
    assert lg.verify(d)["status"] == "REPLAY_DIFFERS"                                           # rules.evidence, question.evidence and every emit's `ev` are v2's


def test_t_ev_20_v1_decisions_are_unchanged_on_the_h55d_final_threads(tmp_path, tasks):
    """v1 still admits I2-013 / I2-025 / I2-034 (6 runs); v2 admits only I2-013 (2 runs): 青 has no slot head, 1981年's 設立 is outside its clause."""
    passed = {V1: [], V2: []}
    for ver in (V1, V2):
        srv = server(tmp_path, tasks, ev.SCOPE_TITLE, evidence="v1" if ver == V1 else "v2", name="h_" + ver)
        for mode in ("record_only", "constructed_allowed"):
            for base in ANSWERABLE_LOOM:
                tid, text, weaves = stored_final_thread(os.path.join(LOOMX, "runs_h55d", "%s.%s.api" % (base, mode)))
                res = reweave(srv, tid, "%s_%s" % (base, mode), weaves)
                if not weave_codes(res) and res["refusals"] == []:
                    passed[ver].append((base, mode))
    assert sorted(set(b for b, _ in passed[V1])) == ["I2-013", "I2-025", "I2-034"] and len(passed[V1]) == 6
    assert passed[V2] == [("I2-013", "record_only"), ("I2-013", "constructed_allowed")]


# ---- T-EV-21: the reach and the admission sweeps over multi-word stretches -------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sweep10(corpus, texts):
    """For 69 answerable + 60 unanswerable questions: every stretch of at most 10 WORD units of every sentence of the corpus that passes the gate (title scope: the more
    permissive scope; a stretch that passes under 'clause' passes under 'clause_or_title').  {id: {version: [(sid, i0, i1, text)]}}.  About 2 minutes."""
    import unicodedata  # noqa: F401
    unans = [r["#id"] for r in bank2_rows() if r["kind"] == "unans" and r["corpus"] == "fulllead"] + [r["#id"] for r in bank4_rows()]
    bases = [b for b in texts if b not in ANSWERABLE_LOOM and (b in unans or b.startswith(("UF-", "R2-U")))]
    items = {("ans", r["#id"]): (r["question"], [_norm(a) for a in r["gold"].split("|")]) for r in bank2_rows() if r["kind"] == "intra2" and r["corpus"] == "fulllead"}
    items.update({("unans", b): (texts[b], []) for b in bases})
    out = {}
    for key, (q, golds) in items.items():
        qu = ev.question_units(q)
        res = {V1: [], V2: []}
        for sid in range(corpus.n_sentences):
            v = ev.view_of(corpus, sid)
            n = len(v.units)
            for i in range(n):
                for j in range(i, min(n, i + 10)):
                    for ver in ((V2,) if key[0] == "unans" else (V1, V2)):
                        jq_ = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, ver)
                        if not jq_["codes"]:
                            res[ver].append((sid, i, j, jq_["answer"]))
        out[key] = dict(res, golds=golds)
    assert len(bases) == 60
    return out


def test_t_ev_21_no_stretch_of_up_to_ten_words_passes_for_an_unanswerable_question_in_v2(sweep10):
    un = {k: v for k, v in sweep10.items() if k[0] == "unans"}
    assert len(un) == 60
    assert {k: v[V2][:3] for k, v in un.items() if v[V2]} == {}


def test_t_ev_21_the_answerable_items_admit_no_wrong_stretch_in_v2_and_the_reach_is_10_of_69(sweep10):
    ans = {k[1]: v for k, v in sweep10.items() if k[0] == "ans"}
    assert len(ans) == 69

    def sets(ver):
        right = [k for k, v in ans.items() if any(_norm(t) in v["golds"] for _, _, _, t in v[ver])]
        wrong = [k for k, v in ans.items() if any(_norm(t) not in v["golds"] for _, _, _, t in v[ver])]
        only_wrong = [k for k in wrong if k not in right]
        return right, wrong, only_wrong
    r1, w1, o1 = sets(V1)
    assert r1 == REACH_V1
    assert (len(w1), len(o1)) == (21, 9)                      # v1: 21 of 69 answerable items admit at least one wrong stretch (the review counted 20), 9 admit only wrong ones
    r2, w2, o2 = sets(V2)
    assert r2 == REACH_V2 and w2 == [] and o2 == []           # v2: none, at the price of 2 of the 12 reachable items (the owner accepted 12 -> 10)


# ---- T-EV-22: a gated smoke test (the legacy loom tests run with evidence "off") ----------------------------------------------------------------------
@pytest.mark.parametrize("ver", ["v1", "v2"])
def test_t_ev_22_a_gated_run_keeps_its_notes_caps_and_stability(tmp_path, ver):
    sents = ["青葉堂の旧称は松風庵。", "青葉堂は1820年に建てられた。", "青葉堂は緑町にある。"]
    p = tmp_path / "toy.jsonl"
    p.write_text("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": "青葉堂", "sent": s, "source": "青葉堂#%d" % i}, ensure_ascii=False) + "\n"
                         for i, s in enumerate(sents)), encoding="utf-8")
    tk = {"task_id": "t/0", "text": "青葉堂の旧称は何ですか", "lang": "prose", "mode": "record_only", "tiers": ["RUN", "WORD", "CHAR"], "corpus": str(p)}
    srv = LoomServer([tk], str(tmp_path / "runs"), (), evidence=ver, caps="v1")                # strict_npa by default; the v1 caps (30 lookups) are the small ones
    b = srv.begin("t/0", "m", "g1")
    assert b["evidence_profile"]["version"] == "evidence." + ver and b["task"]["caps"]["lookups"] == 30 and srv.stability == "strict_npa"
    # notes: a QUESTION_ECHO note points at a quoted unit that is a word of the question, never blocks, never changes the text
    w1 = srv.call("weave_span", {"run_id": "g1", "sid": 0, "tier": "RUN", "first": "旧称", "last": "旧称"})
    assert w1["ok"] and [n["type"] for n in w1["notes"]] == ["QUESTION_ECHO"] and w1["notes"][0]["unit"] == "旧称"
    assert srv.call("weave_span", {"run_id": "g1", "sid": 0, "tier": "RUN", "first": "松風庵", "last": "松風庵"})["ok"]
    r = srv.call("read", {"run_id": "g1"})
    assert r["text"] == "旧称松風庵" and [n["type"] for n in r["notes"]] == ["QUESTION_ECHO"]
    assert [x["type"] for x in r["refusals"]] == ["no_evidence"] and r["refusals"][0]["weaves"][0]["answer"] == "旧称"
    assert [e["w"] for e in r["evidence"]] == [2] and r["evidence"][0]["copula"] == "Y は A"
    assert [s["status"] for s in r["stability"]] == ["trivially_stable", "trivially_stable"]            # the key gate runs under the evidence gate
    assert srv.call("emit", {"run_id": "g1"})["refusal"] == "no_evidence"
    # dropping the echo leaves one passing quote: it is emitted, with its stability, without the dropped cross's note
    assert srv.call("drop", {"run_id": "g1", "cid": "c1"})["ok"]
    e = srv.call("emit", {"run_id": "g1"})
    assert e["ok"] and e["text"] == "松風庵" and e["ev"] == "evidence." + ver and "notes" not in e and [s["cid"] for s in e["stability"]] == ["c2"]
    rs = rows(tmp_path / "runs" / "g1")
    assert [r_["op"] for r_ in rs if r_["actor"] == "loom"].count("loom_note") >= 2                       # the note rows are in the chain and replay
    v = lg.verify(tmp_path / "runs" / "g1")
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"
    # the caps: 30 lookups, the 31st is refused, in a gated run
    srv.begin("t/0", "m", "g2")
    for _ in range(30):
        assert srv.call("lookup", {"run_id": "g2", "text": "青葉堂", "tier": "any"})["ok"]
    x = srv.call("lookup", {"run_id": "g2", "text": "青葉堂", "tier": "any"})
    assert x["ok"] is False and x["refusal"] == "lookup_cap" and x["detail"] == {"limit": 30}
    v2 = lg.verify(tmp_path / "runs" / "g2")
    assert v2["status"] == "OK" and v2["replay"]["status"] == "IDENTICAL"


# ---- T-EV-23: route (1) as the final thread re-judged offline (score.final_thread_gate / layer_report) -----------------------------------------------------
def _score():
    import importlib.util
    name = "loom_score_for_evidence"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, os.path.join(LOOMX, "score.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules[name]


def _layer(run_dir):
    S = _score()
    final = S.final_thread_gate(run_dir, versions=S.FINAL_GATE_VERSIONS)
    return S.layer_report(rows(run_dir), None, final), final


def test_t_ev_23_route_one_is_the_final_thread_failing_the_gate_with_no_text(tmp_path):
    adv, ans = os.path.join(LOOMX, "runs_unans_adv_e"), os.path.join(LOOMX, "runs_h55e")
    L, f = _layer(os.path.join(adv, "ADV-001.record_only.api"))                          # a refused dry-run read, then no_record: shown
    assert f["profile"] == ["evidence.v1", "clause_or_title"] and f["held"] == 2 and f["verdicts"]["evidence.v1"]["fails"] and f["verdicts"]["evidence.v2"]["fails"]
    assert L["route1_final"] is True and L["route1_final_how"] == "shown" and L["stop_layer"] == "L_struct"
    L, f = _layer(os.path.join(adv, "ADV-021.record_only.api"))                          # a thread that fails, never read, never emitted: unseen (and v2 finds more wrong with it)
    assert L["route1_final"] is True and L["route1_final_how"] == "unseen" and L["stop_layer"] == "L_other"
    assert f["verdicts"]["evidence.v1"]["codes"] == ["no_evidence:no_slot_head"]
    assert f["verdicts"]["evidence.v2"]["codes"] == ["no_evidence:answer_crosses_break", "no_evidence:answer_glued", "no_evidence:no_slot_head"]
    L, f = _layer(os.path.join(adv, "ADV-013.constructed_allowed.api"))                  # told by a dry-run read, then dropped the thread: the final thread is empty
    assert f["held"] == 0 and L["route1_final"] is False and "route1_final_how" not in L and L["read_codes"] == {"no_evidence:no_slot_head": 1}
    L, f = _layer(os.path.join(ans, "I2-034.record_only.api"))                           # emitted a text: never route (1); v2 would refuse its thread
    assert L["route1_final"] is False and f["verdicts"]["evidence.v1"]["fails"] is False and f["verdicts"]["evidence.v2"]["codes"] == ["no_evidence:no_slot_head"]


def test_t_ev_23_a_run_without_a_gate_and_a_layer_report_without_a_final_thread_are_as_before():
    S = _score()
    old = os.path.join(LOOMX, "runs_unans_adv", "ADV-010.record_only.api")
    assert S.final_thread_gate(old, versions=S.FINAL_GATE_VERSIONS) is None
    L = S.layer_report(rows(old), None)
    assert "final_thread" not in L and "route1_final" not in L
    assert L == S.layer_report(rows(old), None, None)
    for c in ("answer_glued", "answer_crosses_break", "multiple_answers"):
        assert c in S.EVIDENCE_CONTENT_CODES and c in ev.CODES


# ===============================================================================================================
# evidence.v3 (docs/LINE3_LOOM_REACH_DESIGN.md; owner 2026-10-13 OP-RE-3 both, OP-RE-1 no inflected heads, OP-RE-2 not the default; L-LOOM-201..211): T-EV-24..30
# ===============================================================================================================
V3 = ev.EVIDENCE_V3
REACH_V3 = ["I2-001", "I2-003", "I2-004", "I2-005", "I2-006", "I2-008", "I2-012", "I2-013", "I2-014", "I2-018", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048",
            "R2-I005", "R2-I007", "R2-I008", "R2-I015", "R2-I017"]
NEW_V3 = ["I2-001", "I2-008", "I2-012", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048", "R2-I008", "R2-I015"]          # the 12 items v3 adds to v2's 10
assert sorted(set(REACH_V3) - set(REACH_V2)) == NEW_V3 and set(REACH_V2) <= set(REACH_V3) and len(REACH_V3) == 22
VIA_V3 = {"I2-001": "alias", "I2-026": "alias", "I2-035": "alias", "I2-008": "relative", "I2-032": "relative", "I2-048": "relative", "R2-I015": "relative"}
ANSWERS_V3 = {"I2-001": ["ハッシュ表"], "I2-008": ["カール・マルクス"], "I2-012": ["深川八幡宮"], "I2-026": ["アワド語"], "I2-027": ["ゴゴプラッタ"], "I2-032": ["製鋼所"],
              "I2-035": ["ライパン", "黒パン"], "I2-042": ["新潟市西区"], "I2-045": ["MtF"], "I2-048": ["イングランド"], "R2-I008": ["ウルトラプリニー式噴火"], "R2-I015": ["イングランド"]}
# the rule attribution of the design (§5): removing a rule loses exactly these ids
ABLATION_V3 = {"R1": ["I2-042"], "R2": ["I2-012", "I2-027", "I2-045"], "R3": ["I2-001", "I2-026", "I2-035"], "R3b": ["I2-026"], "R4": ["I2-008", "I2-032", "I2-048", "R2-I015"],
               "R5": ["R2-I008"], "R6": ["I2-048", "R2-I015"], "R7": ["I2-012"]}


def _all_items(texts):
    """[(kind, id, question text, golds)]: the 69 answerable bank2 items and the 60 unanswerable ones, as T-EV-21 takes them."""
    unans = [r["#id"] for r in bank2_rows() if r["kind"] == "unans" and r["corpus"] == "fulllead"] + [r["#id"] for r in bank4_rows()]
    bases = [b for b in texts if b not in ANSWERABLE_LOOM and (b in unans or b.startswith(("UF-", "R2-U")))]
    out = [("ans", r["#id"], r["question"], [_norm(a) for a in r["gold"].split("|")]) for r in bank2_rows() if r["kind"] == "intra2" and r["corpus"] == "fulllead"]
    out += [("unans", b, texts[b], []) for b in bases]
    assert len(out) == 129 and len(bases) == 60
    return out


# ---- T-EV-24: the question cut under v3 ----------------------------------------------------------------------------------------------------------------
def test_t_ev_24_the_v3_cut_adds_kinds_the_relative_head_and_the_alias_form_and_v1_v2_cuts_are_untouched(texts):
    items = _all_items(texts)
    tbl = {iid: [list(ev.question_units(q).kinds), ev.question_units(q).rel_head, ev.question_units(q).alias] for _, iid, q, _ in items}
    assert hashlib.sha256(json.dumps(tbl, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == "fdaab01d6cd4c910bb8fbab737b89ab59963c54fa99d8b8ae27f4d69f87799e5"
    assert (sum(1 for v in tbl.values() if v[0]), sum(1 for v in tbl.values() if v[1]), sum(1 for v in tbl.values() if v[2])) == (52, 5, 3)
    assert {k: v[1] for k, v in tbl.items() if v[1]} == {"I2-008": "唱え", "I2-032": "地", "I2-048": "優勝", "R2-I015": "優勝", "UF-017": "提唱"}              # R4: UF-017 has the variant, no subject
    assert sorted(k for k, v in tbl.items() if v[2]) == ["I2-001", "I2-026", "I2-035"]                                                                 # R3
    assert tbl["I2-042"][0] == ["区"] and tbl["I2-015"][0] == ["市", "区"] and tbl["I2-021"][0] == ["姓"] and tbl["R2-I013"][0] == ["国"] and tbl["I2-034"][0] == ["年"]
    assert ev.question_units("2017 FIFA U-17ワールドカップで優勝した国はどこですか").kinds == ()                                                           # 国 is Y here, not glued to a question word
    # UF-017: the relative variant is built, and the gate refuses it for the missing subject
    assert ev.question_units(texts["UF-017"]).subject == () and ev.question_units(texts["UF-017"]).rel_head == "提唱"
    # the written object: v3 only
    for _, iid, q, _ in items:
        qu = ev.question_units(q)
        o1, o2, o3 = (qu.to_obj(ev.SCOPE_TITLE, v) for v in (ev.EVIDENCE_V1, ev.EVIDENCE_V2, ev.EVIDENCE_V3))
        assert set(o1) == set(o2) == {"evidence", "subject_scope", "form", "slot", "y", "y_forms", "subject", "subject_level", "units"}              # v1 / v2: the object of before
        assert {k: v for k, v in o3.items() if k not in ("kinds", "relative", "alias")} == o2 | {"evidence": V3} and set(o3) - set(o2) == {"kinds", "relative", "alias"}
        assert o3["kinds"] == list(qu.kinds) and o3["alias"] is qu.alias and o3["relative"] == (None if qu.rel_head is None else {"head": qu.rel_head})
    objs = {iid: ev.question_units(q).to_obj(ev.SCOPE_TITLE, V3) for _, iid, q, _ in items}
    assert hashlib.sha256(json.dumps(objs, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == "3f3c3a4ea897a2876208ff4d001dc8a1da8025854d34e68b78aea97af9840eab"
    # v2 / v1 cuts of the 129 questions are what they were: the table CUT (T-EV-01) still holds
    for k, want in CUT.items():
        if k in texts:
            assert cut_of(texts[k]) == want


# ---- T-EV-25: per-rule probes on the real sentences ---------------------------------------------------------------------------------------------------
def _qtext(iid, texts):
    return {r["#id"]: r["question"] for r in bank2_rows()}.get(iid) or texts[iid]


def _verdict(corpus, texts, iid, sid, i0, i1, version=V3, **kw):
    qu = ev.question_units(_qtext(iid, texts))
    r = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, version) if not kw else ev._judge_v3(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, **kw)
    return r


# (item, answer, sid, i0, i1, via, rules the passing reading used)
PASS_V3 = [("I2-042", "新潟市西区", 356, 9, 12, None, ["R1"]),                                                       # R1: the kind noun of どの区 ends the answer
           ("I2-027", "ゴゴプラッタ", 159, 2, 2, None, ["R2"]), ("I2-045", "MtF", 526, 0, 0, None, ["R2"]),            # R2: one gloss before the particle
           ("I2-012", "深川八幡宮", 64, 1, 3, None, ["R2", "R7"]),                                                    # R2 + R7: 称さ for 呼ば
           ("I2-001", "ハッシュ表", 1, 0, 1, "alias", ["R3"]), ("I2-035", "ライパン", 297, 4, 4, "alias", ["R3"]), ("I2-035", "黒パン", 297, 13, 14, "alias", ["R3"]),
           ("I2-026", "アワド語", 151, 0, 1, "alias", ["R3", "R3b"]),
           ("I2-008", "カール・マルクス", 23, 2, 3, "relative", ["R4"]), ("I2-032", "製鋼所", 222, 8, 9, "relative", ["R4"]),
           ("I2-048", "イングランド", 396, 0, 0, "relative", ["R4", "R6"]), ("R2-I015", "イングランド", 396, 0, 0, "relative", ["R4", "R6"]),     # R4 + R6: 2017 FIFA U-17 in the title
           ("R2-I008", "ウルトラプリニー式噴火", 321, 3, 6, None, ["R5"])]                                            # R5: 「Y としては A」


@pytest.mark.parametrize("iid,ans,sid,i0,i1,via,rules", PASS_V3)
def test_t_ev_25_each_v3_rule_passes_its_real_sentence_and_v2_refuses_it(corpus, texts, iid, ans, sid, i0, i1, via, rules):
    r = _verdict(corpus, texts, iid, sid, i0, i1)
    assert r["answer"] == ans and r["codes"] == [] and r["failures"] == [] and r["evidence"] is not None, r
    assert sorted(r["rules"]) == sorted(rules)
    e = r["evidence"]
    assert e.get("via") == via and (e.get("head") == ev.question_units(_qtext(iid, texts)).rel_head if via == "relative" else "head" not in e)
    if via is None:
        assert r["reading"] == "base" and ("via" not in e)
    assert _verdict(corpus, texts, iid, sid, i0, i1, ev.EVIDENCE_V2)["codes"] != []                                    # v2 refuses every one of them


def test_t_ev_25_the_evidence_a_v3_pass_carries(corpus, texts):
    e = _verdict(corpus, texts, "R2-I008", 321, 3, 6)["evidence"]
    assert e["copula"] == "Y としては A" and e["y"] and e["subject"]
    e = _verdict(corpus, texts, "I2-008", 23, 2, 3)["evidence"]
    assert (e["via"], e["head"], e["slot"]) == ("relative", "唱え", {"particle": "が", "arm": e["slot"]["arm"]}) and e["slot"]["arm"] is not None
    e = _verdict(corpus, texts, "I2-001", 1, 0, 1)["evidence"]
    assert e["via"] == "alias" and "slot" not in e and "copula" not in e
    e = _verdict(corpus, texts, "I2-027", 159, 2, 2)["evidence"]
    assert e["slot"]["particle"] and "via" not in e


def test_t_ev_25_a_bare_kind_noun_a_piece_and_a_glued_prefix_are_refused(corpus, texts):
    for sid, i0, i1 in occurrences(corpus, "区"):                                                                       # 区 alone is never an answer to どの区 (T2 / the echo)
        assert _verdict(corpus, texts, "I2-042", sid, i0, i1)["codes"] != []
    r = _verdict(corpus, texts, "I2-042", 356, 12, 12)
    assert "answer_holds_question_unit" in r["codes"]
    for sid, i0, i1 in occurrences(corpus, "ハッシュ"):                                                                 # 「ハッシュ」 alone is a piece of ハッシュ表 / ハッシュテーブル
        assert _verdict(corpus, texts, "I2-001", sid, i0, i1)["codes"] != []
    r = _verdict(corpus, texts, "I2-021", 130, 6, 6)                                                                  # T2: 「姓」 for 何姓を (the kind noun is no echo of v2: 何姓 holds a question word)
    assert "answer_holds_question_unit" in r["codes"] and "answer_holds_question_unit" not in _verdict(corpus, texts, "I2-021", 130, 6, 6, version=V2)["codes"]
    assert "answer_holds_question_unit" not in _verdict(corpus, texts, "I2-021", 130, 6, 6, off=frozenset({"T2"}))["codes"]                  # T2 is what refuses it
    assert "answer_glued" in _verdict(corpus, texts, "I2-028", 171, 5, 6)["codes"]                                      # T1: 曲輪遺跡 is the end of 大曲輪遺跡 (the prefix 大 lies in the gap)
    assert "answer_glued" not in _verdict(corpus, texts, "I2-028", 171, 5, 6, version=V2)["codes"]
    assert _verdict(corpus, texts, "I2-028", 171, 5, 6, off=frozenset({"T1"}))["codes"] == []                           # without T1 the set admits this wrong stretch


NOT_ADOPTED_V3 = [("I2-007", "廃止"), ("I2-021", "永樂"), ("I2-029", "和歌山線"), ("R2-I005", "和歌山千葉線"), ("R2-I017", "成り立つ性質"), ("ADV-037", "11月6日")]


@pytest.mark.parametrize("iid,ans", NOT_ADOPTED_V3)
def test_t_ev_25_the_candidates_not_adopted_stay_refused_under_v3(corpus, texts, iid, ans):
    occ = occurrences(corpus, ans)
    assert occ
    for sid, i0, i1 in occ:
        assert _verdict(corpus, texts, iid, sid, i0, i1)["codes"] != [], (iid, ans, sid)


def test_t_ev_25_an_inflected_head_is_not_a_head_op_re_1(corpus, texts):
    """OP-RE-1 (owner: no): 伴う / 伴い, 名乗っ / 名乗り are different words.  I2-007's 路線の廃止 is not reached either."""
    qu = ev.question_units(_qtext("I2-021", texts))
    assert qu.slot_head == "名乗っ"
    sid, i0, i1 = [o for o in occurrences(corpus, "永樂") if o[0] == 130][0]
    r = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i0, i1, V3)
    assert "no_slot_head" in r["codes"]


def test_t_ev_25_the_alias_form_is_only_for_betsumei_and_a_naming_word_is_required(corpus, texts):
    """R3: ALIAS_Y = 別名 別称 異名.  Another asked item (通称) has no alias reading; a sentence without a naming word is refused."""
    assert ev.ALIAS_Y == frozenset({"別名", "別称", "異名"}) and ev.question_units("ハッシュテーブルの通称は何ですか").alias is False
    assert ev.question_units("ハッシュテーブルの別称は何ですか").alias and ev.question_units("ハッシュテーブルの異名は何ですか").alias
    qu = ev.question_units(_qtext("I2-001", texts))
    for sid in range(corpus.n_sentences):                                                                             # no stretch of sentence 0 or 2 passes (ハッシュ表 is in sentence 1)
        if sid in (0, 2):
            v = ev.view_of(corpus, sid)
            for i in range(len(v.units)):
                assert ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, i, V3)["codes"] != []


def test_t_ev_25_a_toy_corpus_checks_each_rule_from_both_sides(tmp_path):
    """Hand-made sentences: each rule passes its own pattern and is refused one step away (no corpus accident)."""
    sents = [  # (title, sentence)
        ("青葉堂", "青葉堂は松風庵ともいう。"),                               # R3 yes: 「A ともいう」 answers 別名 (the sentence has no 「別名」)
        ("青葉堂", "青葉堂は松風庵と呼ばれる。"),                             # no 「とも」 right after the answer: refused
        ("青葉堂", "青葉堂は松風庵とも歌われる。"),                           # 「とも」 but no naming word: refused
        ("青葉堂", "青葉堂は松風庵（まつかぜあん）に移された。"),              # R2 yes
        ("青葉堂", "青葉堂は松風庵（まつかぜあん）、緑町に移された。"),         # a comma after the gloss: no
        ("青葉堂", "青葉堂は松風庵（まつかぜあん）（旧称）に移された。"),        # two glosses: no
    ]
    p = tmp_path / "toy.jsonl"
    p.write_text("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": t, "sent": s, "source": "%s#%d" % (t, i)}, ensure_ascii=False) + "\n"
                         for i, (t, s) in enumerate(sents)), encoding="utf-8")
    c = Corpus.load(p.read_bytes())

    def passing(q, sid, off=frozenset()):
        qu = ev.question_units(q)
        v = ev.view_of(c, sid)
        return [v.text[v.spans[i][0]:v.spans[j][1]] for i in range(len(v.units)) for j in range(i, len(v.units)) if not ev._judge_v3(c, qu, ev.SCOPE_CLAUSE, sid, "WORD", i, j, off)["codes"]]
    assert passing("青葉堂の別名は何ですか", 0) == ["松風庵"] and passing("青葉堂の別名は何ですか", 0, frozenset({"R3"})) == []
    assert passing("青葉堂の別名は何ですか", 1) == [] and passing("青葉堂の別名は何ですか", 2) == []
    assert passing("青葉堂の通称は何ですか", 0) == []                                                              # 通称 is not an alias question (ALIAS_Y)
    assert passing("青葉堂は何に移されましたか", 3) == ["松風庵"] and passing("青葉堂は何に移されましたか", 3, frozenset({"R2"})) == []
    assert passing("青葉堂は何に移されましたか", 4) == [] and passing("青葉堂は何に移されましたか", 5) == []


# ---- T-EV-26: the sweep (as T-EV-21; v3 added) ------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def sweep_v3(corpus, texts):
    """For the 69 answerable + 60 unanswerable questions: every stretch of at most 10 WORD units of every sentence that passes the gate evidence.v3 (title scope).
    {(kind, id): [(sid, i0, i1, text, via)]}.  About 2 minutes."""
    out = {}
    for kind, iid, q, golds in _all_items(texts):
        qu = ev.question_units(q)
        res = []
        for sid in range(corpus.n_sentences):
            v = ev.view_of(corpus, sid)
            n = len(v.units)
            for i in range(n):
                for j in range(i, min(n, i + 10)):
                    r = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V3)
                    if not r["codes"]:
                        res.append((sid, i, j, r["answer"], (r["evidence"] or {}).get("via")))
        out[(kind, iid)] = res
    return out


def test_t_ev_26_the_reach_of_v3_is_22_of_69_with_no_wrong_stretch(sweep_v3, texts):
    golds = {iid: g for kind, iid, _, g in _all_items(texts) if kind == "ans"}
    ans = {k[1]: v for k, v in sweep_v3.items() if k[0] == "ans"}
    assert len(ans) == 69
    right = [k for k, v in ans.items() if any(_norm(t) in golds[k] for _, _, _, t, _ in v)]
    wrong = [k for k, v in ans.items() if any(_norm(t) not in golds[k] for _, _, _, t, _ in v)]
    assert right == REACH_V3 and len(right) == 22 and wrong == []
    assert sorted(set(right) - set(REACH_V2)) == NEW_V3                                          # v3 keeps v2's 10 and adds 12
    assert {k: sorted({t for _, _, _, t, _ in ans[k]}) for k in NEW_V3} == {k: sorted(v) for k, v in ANSWERS_V3.items()}
    via = {k: sorted({w for *_, w in ans[k] if w}) for k in ans if any(w for *_, w in ans[k])}
    assert via == {k: [w] for k, w in VIA_V3.items()}                                            # R3 / R4 are the readings that passed; every other pass is the question's own


def test_t_ev_26_no_stretch_passes_for_an_unanswerable_question_and_no_trap_value_is_admitted(sweep_v3):
    un = {k: v for k, v in sweep_v3.items() if k[0] == "unans"}
    assert len(un) == 60
    assert {k: v[:3] for k, v in un.items() if v} == {}
    traps = {r["#id"]: _norm(r["trap"]) for r in bank4_rows()}
    assert len(traps) == 35 and all(("unans", i) in sweep_v3 for i in traps)
    assert [i for i, t in traps.items() if any(_norm(x[3]) == t for x in sweep_v3[("unans", i)])] == []


def test_t_ev_26_v2_is_still_10_of_69_with_0_wrong_and_0_unanswerable(sweep10):
    ans = {k[1]: v for k, v in sweep10.items() if k[0] == "ans"}
    assert [k for k, v in ans.items() if any(_norm(t) in v["golds"] for _, _, _, t in v[V2])] == REACH_V2
    assert [k for k, v in ans.items() if any(_norm(t) not in v["golds"] for _, _, _, t in v[V2])] == []
    assert [k for k, v in sweep10.items() if k[0] == "unans" and v[V2]] == []


# ---- T-EV-27: ablation ---------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("rule", sorted(ABLATION_V3))
def test_t_ev_27_removing_a_rule_loses_exactly_its_ids(corpus, texts, sweep_v3, rule):
    """The rules widen (an OR of readings, an exemption, a longer read), so a stretch that passes with a rule off also passes with it on: the items reached with the rule off
    are those with a gold stretch, among v3's passing stretches, that still passes."""
    items = {iid: (q, g) for kind, iid, q, g in _all_items(texts) if kind == "ans"}
    lost = []
    for iid in REACH_V3:
        q, g = items[iid]
        qu = ev.question_units(q)
        golds = [(sid, i, j) for sid, i, j, t, _ in sweep_v3[("ans", iid)] if _norm(t) in g]
        assert golds
        if not any(not ev._judge_v3(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, frozenset({rule}))["codes"] for sid, i, j in golds):
            lost.append(iid)
    assert lost == ABLATION_V3[rule]


def test_t_ev_27_the_attribution_table_covers_exactly_the_twelve_new_ids():
    assert sorted(set().union(*ABLATION_V3.values())) == NEW_V3


def test_t_ev_27_without_t1_the_set_admits_a_wrong_stretch_for_i2_028(corpus, texts, sweep_v3):
    qu = ev.question_units(_qtext("I2-028", texts))
    assert [x for x in sweep_v3[("ans", "I2-028")]] == []                                          # v3: nothing passes for I2-028 (gold not WORD-aligned)
    assert not ev._judge_v3(corpus, qu, ev.SCOPE_TITLE, 171, "WORD", 5, 6, frozenset({"T1"}))["codes"]        # 曲輪遺跡 (a piece of the gold 大曲輪遺跡) passes without T1
    assert ev._judge_v3(corpus, qu, ev.SCOPE_TITLE, 171, "WORD", 5, 6)["codes"] == ["answer_glued"]


# ---- T-EV-28: versions, the begin row, the old ledgers, the freeze ----------------------------------------------------------------------------------------
def test_t_ev_28_v3_is_selectable_and_v2_stays_the_default_everywhere(tmp_path, tasks, monkeypatch):
    import inspect
    from verantyx import cli
    from verantyx.loom import mcp as lm
    assert ev.EVIDENCE_VERSIONS == (V1, V2, V3, "evidence.v4", "evidence.v5") and ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES == {"v1": V1, "v2": V2, "v3": V3, "v4": "evidence.v4", "v5": "evidence.v5"}
    assert inspect.signature(ev.judge_quote).parameters["version"].default == V2
    assert LoomServer(list(tasks.values()), str(tmp_path / "a")).evidence_profile == (V2, "clause_or_title")                   # OP-RE-2: v2 is the server default
    assert LoomServer(list(tasks.values()), str(tmp_path / "b"), evidence="v3").evidence_profile == (V3, "clause_or_title")
    with pytest.raises(ValueError):
        LoomServer(list(tasks.values()), str(tmp_path / "c"), evidence="v6")
    seen = []
    monkeypatch.setattr(lm, "serve", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r")]) == 0
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r"), "--evidence", "v3"]) == 0
    assert [a[4] for a in seen] == ["v2", "v3"]                                                                               # the CLI default is v2; --evidence v3 selects v3
    H = _harness()
    assert inspect.signature(H.run).parameters["evidence"].default is None                                                     # None = v2 for the api driver (unchanged)


def test_t_ev_28_a_v3_run_records_its_rules_and_the_kinds_and_replays_identically(tmp_path, tasks):
    from verantyx.loom.ops import EVIDENCE_RULE_V2, EVIDENCE_RULE_V3
    assert EVIDENCE_RULE_V3 == EVIDENCE_RULE_V2 + " " + ev.V3_RULE_SENTENCE and "kind word" in EVIDENCE_RULE_V3 and EVIDENCE_RULE_V3.startswith(EVIDENCE_RULE_V2)
    srv = server(tmp_path, tasks, evidence="v3", name="v3")
    b = srv.begin("bank2/I2-001.record_only", "t", "x")
    assert b["evidence_profile"] == {"version": V3, "subject_scope": "clause_or_title"} and b["rules"]["evidence"] == EVIDENCE_RULE_V3
    q = ev.question_units("ハッシュテーブルの別名は何ですか").to_obj("clause_or_title", V3)
    assert b["question"] == q and b["question"]["alias"] is True and b["question"]["kinds"] == [] and b["question"]["relative"] is None and b["question"]["evidence"] == V3
    # a v2 begin row has none of the new keys
    b2 = server(tmp_path, tasks, evidence="v2", name="v2").begin("bank2/I2-001.record_only", "t", "x")
    assert set(b2["question"]) == set(b["question"]) - {"kinds", "relative", "alias"} and b2["rules"]["evidence"] == EVIDENCE_RULE_V2


def _scripted_i2_001(srv, rid="r1"):
    srv.begin("bank2/I2-001.record_only", "test", rid)
    assert srv.call("weave_span", {"run_id": rid, "sid": 1, "tier": "WORD", "first": "ハッシュ", "last": "表"})["ok"]
    return srv.call("emit", {"run_id": rid})


def test_t_ev_28_a_v3_alias_answer_is_emitted_where_v2_refuses_it_and_both_replay_identically(tmp_path, tasks):
    s3, s2 = server(tmp_path, tasks, evidence="v3", name="r3"), server(tmp_path, tasks, evidence="v2", name="r2")
    e3, e2 = _scripted_i2_001(s3), _scripted_i2_001(s2)
    assert e3["ok"] and e3["text"] == "ハッシュ表" and e3["ev"] == V3 and [(x["via"], x["subject"]) for x in e3["evidence"]] == [("alias", [{"run": "ハッシュテーブル", "via": "title"}])]
    assert e2["ok"] is False and e2["refusal"] == "no_evidence"
    for name in ("r3", "r2"):
        v = lg.verify(tmp_path / name / "r1")
        assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL", v


def test_t_ev_28_a_v3_relative_answer_records_its_head(tmp_path, tasks):
    srv = server(tmp_path, tasks, evidence="v3", name="rel")
    srv.begin("bank2/I2-008.record_only", "t", "x")
    assert srv.call("weave_span", {"run_id": "x", "sid": 23, "tier": "WORD", "first": "カール", "last": "マルクス"})["ok"]
    e = srv.call("emit", {"run_id": "x"})
    assert e["ok"] and e["text"] == "カールマルクス" and e["ev"] == V3                                      # the units joined: 「・」 is not a WORD unit
    assert [(x["via"], x["head"], x["slot"]["particle"]) for x in e["evidence"]] == [("relative", "唱え", "が")]
    v = lg.verify(tmp_path / "rel" / "x")
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"


def test_t_ev_28_a_ledger_cannot_change_its_rule_version_between_v2_and_v3(tmp_path, tasks):
    s3, s2 = server(tmp_path, tasks, evidence="v3", name="f3"), server(tmp_path, tasks, evidence="v2", name="f2")
    _scripted_i2_001(s3, "a")
    _scripted_i2_013(s2, "b")
    _scripted_i2_013(s3, "c")
    d3, d2, dc = tmp_path / "f3" / "a", tmp_path / "f2" / "b", tmp_path / "f3" / "c"
    _reseal(d3, lambda rs: rs[0]["result"]["evidence_profile"].update(version=V2))
    assert lg.verify_chain(d3)["status"] == "OK" and lg.verify(d3)["status"] == "REPLAY_DIFFERS"                         # a forged v3 -> v2 relabel
    _reseal(d2, lambda rs: rs[0]["result"]["evidence_profile"].update(version=V3))
    assert lg.verify_chain(d2)["status"] == "OK" and lg.verify(d2)["status"] == "REPLAY_DIFFERS"                         # and v2 -> v3
    _reseal(dc, lambda rs: rs[0]["result"]["question"].update(kinds=["区"]))
    assert lg.verify(dc)["status"] == "REPLAY_DIFFERS"                                                                    # a forged kinds list


FROZEN_V3_RULES_DIGEST = "eca9ccd48aa6ddca8e74f33894acb380cc68667bd34950fd579c4e9bd9cf829d"
FROZEN_V3_EVIDENCE_SHA = "b9ae56b284807c147e314f59e3fb9ec5158cdc82fdde2056ec57cd4e30dd6ab2"        # the file as it was when v3 was frozen; evidence.v4 (LOOM-evidence-v4) is added to it, so the file pin moved to test_loom_evidence_v4.py


def test_t_ev_28_the_v3_rules_are_frozen_a_change_is_evidence_v4(tmp_path):
    """OP-RE-2 (owner): the rules are frozen before the held-out bank6 is written; the digest covers the closed lists, the rule sentence and the source of every v3 function.
    A rule change is evidence.v4 and needs a new held-out set (docs/LINE3_LOOM_REACH_DESIGN.md §6.2 step 1)."""
    assert ev.v3_rules_digest() == FROZEN_V3_RULES_DIGEST
    assert len(FROZEN_V3_EVIDENCE_SHA) == 64                                         # historical: evidence.py changed when evidence.v4 was added (the v3 digest above did not)
    assert ev.V3_RULE_IDS == ("R1", "R2", "R3", "R3b", "R4", "R5", "R6", "R7", "T1", "T2")
    assert sorted(ev.KIND_REL) == sorted("人物 人 者 国 チーム 選手 団体 施設 会社 組織 都市 街 場所".split()) and sorted(ev.ALIAS_Y) == ["別名", "別称", "異名"]
    assert sorted(ev.NAMING) == sorted("呼ば 呼ぶ 呼び 呼ん 称さ 称し 称する 称 いう 言う 云う".split())


# ---- T-EV-29: byte identity under three hash seeds -------------------------------------------------------------------------------------------------------
_DET_V3 = r'''
import sys, json, hashlib, csv
sys.path.insert(0, sys.argv[3])
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus
corpus = Corpus.load(open(sys.argv[1], "rb").read())
qs = [("I2-042", "五十嵐浜村が消滅した後、その地域は現在どの区の一部ですか", 356, 9, 12), ("I2-001", "ハッシュテーブルの別名は何ですか", 1, 0, 1), ("I2-008", "唯物史観を唱えた人物は誰ですか", 23, 2, 3),
      ("I2-027", None, 159, 2, 2), ("I2-028", None, 171, 5, 6), ("R2-I008", None, 321, 3, 6), ("I2-026", "アワディー語の別名は何ですか", 151, 0, 1), ("I2-012", None, 64, 1, 3)]
rows_ = {r["#id"]: r["question"] for r in csv.DictReader(open(sys.argv[2], encoding="utf-8"), delimiter="\t")}
out = []
for iid, q, sid, i0, i1 in qs:
    qu = ev.question_units(q or rows_[iid])
    out.append(qu.to_obj("clause_or_title", ev.EVIDENCE_V3))
    for ver in ("evidence.v2", "evidence.v3"):
        out.append(ev.judge_quote(corpus, qu, "clause_or_title", sid, "WORD", i0, i1, ver))
    out.append(ev.judge_quote(corpus, qu, "clause", sid, "WORD", i0, i1, "evidence.v3"))
out.append(ev.v3_rules_digest())
print(hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
'''


def test_t_ev_29_the_v3_cut_the_verdicts_and_the_digest_are_identical_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([PY, "-c", _DET_V3, CORPUS, BANK2_TSV, ROOT], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert p.returncode == 0, p.stderr[-800:]
        digests.add(p.stdout.strip())
    assert len(digests) == 1


# ---- T-EV-30: the held-out sweep (after bank6 exists) -----------------------------------------------------------------------------------------------------
def test_t_ev_30_the_held_out_bank6_sweep_waits_for_bank6():
    """OP-RE-2 (owner): v3 becomes the default only when the held-out bank6 passes (docs/LINE3_LOOM_REACH_DESIGN.md §6.2): the rules are frozen (T-EV-28), then codex writes bank6,
    Opus audits it, the sweep runs ONCE.  Until then the default is v2 and this test only says so; the ticket that adds `experiments/line3/bank6/` replaces it with the sweep
    pinned with the numbers of the single run (reach, wrong-admitting items, unanswerable admissions, trap admissions, per rule) and only then may EVIDENCE_LATEST change."""
    assert ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES["v2"] == V2
    assert sorted(ev.V3_RULE_IDS) == sorted(ABLATION_V3) + ["T1", "T2"]
