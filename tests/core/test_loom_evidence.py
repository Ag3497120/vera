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


BANK2_TSV = os.path.join(ROOT, "tests/fixtures/line3/bank2/bank2.tsv")


BANK4_TSV = os.path.join(ROOT, "tests/fixtures/line3/bank4/bank4.tsv")


TASK_FILES = ("tasks_bank2.jsonl", "tasks_unans.jsonl", "tasks_unans_adv.jsonl")


ANSWERABLE_LOOM = ("I2-001", "I2-008", "I2-013", "I2-025", "I2-034", "I2-041", "R2-I013")


SCOPES = (ev.SCOPE_TITLE, ev.SCOPE_CLAUSE)


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


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


CUT_TABLE_SHA = "df1fb2e1488f6414b0089718f8d761c48725dbcda06c7a1cb5b49c55a8a124e5"


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


def _recorded_evidence(d):
    """The evidence version the run's `begin` row recorded (None = a ledger made before the gate).  The stored runs are selected by THIS, never by the name of their folder
    (LOOM-evidence-v4: the evidence.v2 runs h55f / reach_f / unans_f / unans_adv_f are tracked folders of the same shape as the evidence.v1 ones)."""
    ep = rows(d)[0]["result"].get("evidence_profile")
    return None if ep is None else ep["version"]


def _scripted_i2_013(srv, rid="r1"):
    b = srv.begin("bank2/I2-013.record_only", "test", rid)
    assert srv.call("read_sentence", {"run_id": rid, "sid": 86})["ok"]
    assert srv.call("weave_span", {"run_id": rid, "sid": 86, "tier": "RUN", "first": "県社", "last": "県社"})["ok"]
    e = srv.call("emit", {"run_id": rid})
    return b, e


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


def _refused_evidence(res):
    assert res["ok"] is False and res["refusal"] == "no_evidence", res
    [r] = [r for r in res["detail"]["refusals"] if r["type"] == "no_evidence"]
    return r


def test_t_ev_11_the_coordinators_example_needs_both_subject_words(corpus):
    qu = ev.question_units("レッド計画ではイギリスを何色としていましたか")
    assert qu.subject == ("レッド計画", "イギリス") and qu.particle == "と"
    j = jq1(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 3, 3)               # 青: アメリカを「青」と -- イギリス is not in its clause
    assert j["codes"] == ["no_subject"] and "「イギリス」" in j["messages"][0] and "「アメリカを「青」と色分け」" in j["messages"][0]
    j = jq1(corpus, qu, ev.SCOPE_TITLE, 143, "WORD", 1, 1)               # 赤: the subject is there but 、 follows
    assert j["codes"] == ["wrong_arm"]


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


L = lambda name, **a: ("tool", name, a)


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


V3 = ev.EVIDENCE_V3


REACH_V3 = ["I2-001", "I2-003", "I2-004", "I2-005", "I2-006", "I2-008", "I2-012", "I2-013", "I2-014", "I2-018", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048",
            "R2-I005", "R2-I007", "R2-I008", "R2-I015", "R2-I017"]


NEW_V3 = ["I2-001", "I2-008", "I2-012", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048", "R2-I008", "R2-I015"]          # the 12 items v3 adds to v2's 10


assert sorted(set(REACH_V3) - set(REACH_V2)) == NEW_V3 and set(REACH_V2) <= set(REACH_V3) and len(REACH_V3) == 22


VIA_V3 = {"I2-001": "alias", "I2-026": "alias", "I2-035": "alias", "I2-008": "relative", "I2-032": "relative", "I2-048": "relative", "R2-I015": "relative"}


ANSWERS_V3 = {"I2-001": ["ハッシュ表"], "I2-008": ["カール・マルクス"], "I2-012": ["深川八幡宮"], "I2-026": ["アワド語"], "I2-027": ["ゴゴプラッタ"], "I2-032": ["製鋼所"],
              "I2-035": ["ライパン", "黒パン"], "I2-042": ["新潟市西区"], "I2-045": ["MtF"], "I2-048": ["イングランド"], "R2-I008": ["ウルトラプリニー式噴火"], "R2-I015": ["イングランド"]}


ABLATION_V3 = {"R1": ["I2-042"], "R2": ["I2-012", "I2-027", "I2-045"], "R3": ["I2-001", "I2-026", "I2-035"], "R3b": ["I2-026"], "R4": ["I2-008", "I2-032", "I2-048", "R2-I015"],
               "R5": ["R2-I008"], "R6": ["I2-048", "R2-I015"], "R7": ["I2-012"]}


PASS_V3 = [("I2-042", "新潟市西区", 356, 9, 12, None, ["R1"]),                                                       # R1: the kind noun of どの区 ends the answer
           ("I2-027", "ゴゴプラッタ", 159, 2, 2, None, ["R2"]), ("I2-045", "MtF", 526, 0, 0, None, ["R2"]),            # R2: one gloss before the particle
           ("I2-012", "深川八幡宮", 64, 1, 3, None, ["R2", "R7"]),                                                    # R2 + R7: 称さ for 呼ば
           ("I2-001", "ハッシュ表", 1, 0, 1, "alias", ["R3"]), ("I2-035", "ライパン", 297, 4, 4, "alias", ["R3"]), ("I2-035", "黒パン", 297, 13, 14, "alias", ["R3"]),
           ("I2-026", "アワド語", 151, 0, 1, "alias", ["R3", "R3b"]),
           ("I2-008", "カール・マルクス", 23, 2, 3, "relative", ["R4"]), ("I2-032", "製鋼所", 222, 8, 9, "relative", ["R4"]),
           ("I2-048", "イングランド", 396, 0, 0, "relative", ["R4", "R6"]), ("R2-I015", "イングランド", 396, 0, 0, "relative", ["R4", "R6"]),     # R4 + R6: 2017 FIFA U-17 in the title
           ("R2-I008", "ウルトラプリニー式噴火", 321, 3, 6, None, ["R5"])]                                            # R5: 「Y としては A」


NOT_ADOPTED_V3 = [("I2-007", "廃止"), ("I2-021", "永樂"), ("I2-029", "和歌山線"), ("R2-I005", "和歌山千葉線"), ("R2-I017", "成り立つ性質"), ("ADV-037", "11月6日")]


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


def test_t_ev_27_the_attribution_table_covers_exactly_the_twelve_new_ids():
    assert sorted(set().union(*ABLATION_V3.values())) == NEW_V3


def _scripted_i2_001(srv, rid="r1"):
    srv.begin("bank2/I2-001.record_only", "test", rid)
    assert srv.call("weave_span", {"run_id": rid, "sid": 1, "tier": "WORD", "first": "ハッシュ", "last": "表"})["ok"]
    return srv.call("emit", {"run_id": rid})


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
