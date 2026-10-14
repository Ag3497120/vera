"""MEM-c tests: recall and the self-question through the evidence gate (docs/LINE3_LOOM_MEMORY_DESIGN.md 4.3, 6, 9.4 T-MEM-20..25 [the recall / gate part]; L-MEM-11, 12, 13, 21;
docs/LINE3_LOCAL_DECISIONS.md "MEM-c").

What is under test: ONE reader (`evidence.judge_quote`, unchanged) behind two doors -- the hook `gate.evidence.v2` of MEM-b (`self_question`) and the tool `recall`.
The probes of the design (Pr4, Pr7) are rebuilt here; the stub (`stub.v1`) is run beside the gate on the same writes; what the gate cannot read in memory is pinned as a
KNOWN LIMIT (those tests document the present behaviour, so that a later fix is a deliberate change of a test, not a silent one)."""


import hashlib


import json


import os


import subprocess


import sys


import pytest


from verantyx.loom import evidence as ev


from verantyx.loom import memguard as mg


from verantyx.loom import memnotes as mn


from verantyx.loom import memory as mem


from verantyx.loom import memrecall as mr


from verantyx.loom.corpus import Corpus


from verantyx.loom.state import Refuse


from mem_common import PROBE_REVERSAL, ROOT, STUB, ledger_rows, new_store, notes_of, session, write_all


GATE = mr.GateSelfQuestion()                  # gate.evidence.v2 (MEM-c): the hook of the stores written before the whole-subject guard; they replay with exactly this behaviour


SUBJ = mr.GateSubjectSelfQuestion()           # gate.evidence.v2+subject (MEM-c2): the default of a new store


PR4 = ["田中の担当は認証", "認証の期限は金曜", "田中の担当は決済", "決済の期限は月曜", "会議は東京で開く", "サーバーのポートは8080", "会議は大阪で行う", "サーバーのポートは9090"]


def recall(s, q):
    r = s.call("recall", {"question": q})
    assert r["ok"] is True, r
    return r


def groups(r):
    """[(answers, [sid, ...])] of a recall result."""
    return [(g["answers"], [o["sid"] for o in g["occurrences"]]) for g in r["answers"]]


def by_type(res, typ):
    return [n for n in res.get("notes", []) if n["type"] == typ]


@pytest.fixture
def pr4(tmp_path):
    s = session(tmp_path)                                   # the default hook of a new store: the gate
    write_all(s, PR4)
    return s


def test_the_default_hook_of_a_new_store_is_the_gate_with_the_subject_guard(tmp_path):
    s = session(tmp_path)
    h = ledger_rows(s)[0]["result"]["header"]
    assert (h["self_question"], h["evidence_version"]) == ("gate.evidence.v2+subject", "evidence.v2")
    assert s.run.hook_id == SUBJ.id == mr.GATE_SUBJECT_HOOK_ID and s.run.evidence_version == SUBJ.evidence_version == ev.EVIDENCE_V2 and SUBJ.subject_guard is True
    assert GATE.id == mr.GATE_HOOK_ID == "gate.evidence.v2" and GATE.subject_guard is False and GATE.evidence_version == ev.EVIDENCE_V2
    assert {"stub.v1", "gate.evidence.v2", "gate.evidence.v2+subject"} <= set(mem.HOOKS)               # PUB-M6c: the hooks of the other evidence versions (gate.evidence.v3..v6, with +subject) are registered too, so a session replays under the gate it recorded
    assert "evidence.v2" in ledger_rows(s)[0]["result"]["rules"]["recall"]
    # the old gate hook is still selectable and records its own id
    s1 = session(tmp_path, "oldgate", self_question=GATE)
    h1 = ledger_rows(s1)[0]["result"]["header"]
    assert (h1["self_question"], h1["evidence_version"]) == ("gate.evidence.v2", "evidence.v2")
    # no hook / the stub: no evidence version in the header, the MEM-a/b header and rules, recall refused as before
    s2 = session(tmp_path, "nohook", self_question=None)
    h2 = ledger_rows(s2)[0]["result"]
    assert (h2["header"]["self_question"], h2["header"]["evidence_version"]) == ("none", None) and h2["rules"] == mem.MEM_RULES
    s3 = session(tmp_path, "stub", self_question=STUB)
    h3 = ledger_rows(s3)[0]["result"]["header"]
    assert (h3["self_question"], h3["evidence_version"]) == ("stub.v1", None)
    for sess in (s2, s3):
        r = sess.call("recall", {"question": "田中の担当は何ですか"})
        assert r["ok"] is False and r["refusal"] == "recall_unavailable" and r["detail"]["ticket"] == "MEM-c"


def test_the_stub_can_be_kept_as_the_default(tmp_path, monkeypatch):
    """The switch: tests that want the pre-MEM-c behaviour pass the stub (or None) explicitly, or replace the factory of the default."""
    monkeypatch.setattr(mem, "DEFAULT_HOOK_FACTORY", mn.StubSelfQuestion)
    s = new_store(tmp_path, "a").begin("m")
    assert s.run.hook_id == "stub.v1" and s.run.evidence_version is None
    monkeypatch.setattr(mem, "DEFAULT_HOOK_FACTORY", lambda: None)
    assert new_store(tmp_path, "b").begin("m").run.hook_id == "none"
    monkeypatch.setattr(mem, "DEFAULT_HOOK_FACTORY", mr.GateSelfQuestion)
    assert new_store(tmp_path, "c").begin("m").run.hook_id == "gate.evidence.v2"
    with pytest.raises(ValueError):
        class Bad:
            id = "bad.v1"
            evidence_version = "evidence.v9"
        mem.MemRun("t", 1, "s0001", "m", self_question=Bad())


def test_recall_on_an_empty_store_is_none_for_every_question(tmp_path):
    s = session(tmp_path)
    for q in ("田中の担当は何ですか", "会議はどこで開きますか", "何ですか", "サーバーのポートは何ですか"):
        r = recall(s, q)
        assert r["verdict"] == "NONE" and r["answers"] == [] and r["sentences"] == 0 and r["candidates"] == 0 and r["judged"] == 0
    assert s.status()["recalls"] == 4 and s.status()["sentences"] == 0                     # recall changes nothing but its own counter


def test_pr4_recall_choice_answer_none(pr4):
    r = recall(pr4, "田中の担当は何ですか")
    assert r["verdict"] == "CHOICE" and groups(r) == [(["認証"], [0]), (["決済"], [2])]          # contested facts stay listed, in sid order, never ranked
    o = r["answers"][0]["occurrences"][0]
    assert o == {"sid": 0, "source": "mem:t/1#0", "session": 1, "role": "model", "answer": "認証", "span": [2, 2], "clause": "田中の担当は認証"}
    assert r["evidence"] == "evidence.v2" and r["scope"] == "clause" and r["question"]["subject"] == ["田中"] and r["question"]["y_forms"] == ["担当"]
    r = recall(pr4, "サーバーのポートは何ですか")
    assert r["verdict"] == "CHOICE" and groups(r) == [(["8080"], [5]), (["9090"], [7])]
    r = recall(pr4, "認証の期限は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["金曜"], [1])]                           # the enumeration trap: 認証の期限 and 決済の期限 are two questions
    r = recall(pr4, "決済の期限は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["月曜"], [3])]
    r = recall(pr4, "鈴木の担当は何ですか")
    assert r["verdict"] == "NONE" and r["answers"] == [] and r["candidates"] == 2 and r["judged"] == 12
    assert r["codes"] == {"answer_crosses_break": 4, "answer_holds_question_unit": 8, "no_slot_head": 8, "no_subject": 12, "not_copular": 2}
    assert r["issues"] == [] and r["looked_for"] == ["担当"]
    assert set(r) == {"ok", "text", "verdict", "question", "evidence", "scope", "sentences", "candidates", "judged", "answers", "codes", "issues", "looked_for"}


def test_pr4_a_slot_question_needs_the_slot_head_as_written(pr4):
    """「会議はどこで開きますか」 against 「会議は東京で開く」: the slot head is 開き, the memory says 開く -> no sentence is even judged (the gate reads surfaces, not lemmas)."""
    r = recall(pr4, "会議はどこで開きますか")
    assert r["verdict"] == "NONE" and r["candidates"] == 0 and r["codes"] == {} and r["issues"] == ["no_sentence_holds_the_question_words"] and r["looked_for"] == ["開き"]
    r = recall(pr4, "会議はどこで行いますか")
    assert r["verdict"] == "NONE" and r["issues"] == ["no_sentence_holds_the_question_words"] and r["looked_for"] == ["行い"]


def test_a_slot_question_is_answered_when_the_memory_uses_the_question_form(tmp_path):
    s = session(tmp_path)
    write_all(s, ["会議は東京で開きます"])
    r = recall(s, "会議はどこで開きますか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["東京"], [0])] and r["answers"][0]["occurrences"][0]["clause"] == "会議は東京で開き"
    s.write("会議は大阪で開きます")
    r = recall(s, "会議はどこで開きますか")
    assert r["verdict"] == "CHOICE" and groups(r) == [(["東京"], [0]), (["大阪"], [1])]
    assert "SAME_QUESTION" not in notes_of(s.write("会議は福岡で開きます"))             # the self-question is a PREDICATE clause 「Y は何ですか」: a slot contradiction is not counted
    r = recall(s, "会議はどこで開きますか")
    assert [g[0] for g in groups(r)] == [["東京"], ["大阪"], ["福岡"]]


def test_recall_questions_the_gate_cannot_use_say_why(pr4):
    r = recall(pr4, "田中の担当は")                      # no question word, no 「〜は何」 head
    assert r["verdict"] == "NONE" and "question_form_open" in r["issues"] and r["question"]["form"] == "open"
    r = recall(pr4, "担当は何ですか")                    # a predicate question with no subject word is tied to no sentence (evidence.v2 F1)
    assert r["verdict"] == "NONE" and r["issues"] == ["question_has_no_subject"] and r["candidates"] == 2 and r["codes"]["question_has_no_subject"] == 12


def test_pr7_nested_stretches_are_one_statement(tmp_path):
    s = session(tmp_path)
    s.write("今日の作業はK3の修正")
    r = recall(s, "今日の作業は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["K3の修正"], [0])]                    # {K3, K3の修正} pass: ONE statement, only the maximal one is kept
    assert r["answers"][0]["occurrences"][0]["span"] == [2, 4]                                   # units 今日 作業 K 3 修正: the stretch K 3 の 修正
    s.write("今日の作業はK3の修正")                                                          # written twice: still ANSWER
    r = recall(s, "今日の作業は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["K3の修正"], [0, 1])]
    r2 = s.write("今日の作業はK3のテスト")                                                    # K3の修正 vs K3のテスト: CHOICE (they do not share a maximal answer)
    assert r2["ok"] and by_type(r2, "SAME_QUESTION") and by_type(r2, "SAME_QUESTION")[0]["counted"]
    r = recall(s, "今日の作業は何ですか")
    assert r["verdict"] == "CHOICE" and groups(r) == [(["K3の修正"], [0, 1]), (["K3のテスト"], [2])]


def test_pr7_a_refinement_is_shown_never_hidden(tmp_path):
    s = session(tmp_path)
    write_all(s, ["今日の作業はK3の修正", "今日の作業はK4の修正"])
    r = recall(s, "今日の作業は何ですか")
    assert r["verdict"] == "CHOICE" and [g[0] for g in groups(r)] == [["K3の修正"], ["K4の修正"]]


def test_pr7_an_enumeration_loses_items_known_limit(tmp_path):
    """KNOWN LIMIT: 「mulの引数はaとb」 -> {a} only (evidence.v2 refuses an answer that crosses a break, the second item is not an answer of its own)."""
    s = session(tmp_path)
    w = s.write("mulの引数はaとb")
    r = recall(s, "mulの引数は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["a"], [0])]
    assert by_type(w, "SELF_QUESTION_UNREADABLE") == []


CUT_SUBJECTS = ["fmt_numの戻り値は文字列", "担当者の名前は佐藤", "ops.pyの責任は書き込み", "add関数の引数は2つ"]          # the word cut shortened the subject (fmt|num, 担当|者, ops|.|py, add|関数)


CUT_QUESTIONS = {"fmt_numの戻り値は文字列": "numの戻り値は何ですか", "担当者の名前は佐藤": "者の名前は何ですか", "ops.pyの責任は書き込み": "pyの責任は何ですか", "add関数の引数は2つ": "関数の引数は何ですか"}


def test_pr7_readable_and_unreadable_clauses(tmp_path):
    """The 19 clauses of Pr7 and more, each alone in a fresh memory (the default hook = the gate + the whole-subject guard): the self-question asked of the sentence itself
    (the clause cut of MEM-b) is read back by the gate, or reported SELF_QUESTION_UNREADABLE.  Pinned as measured (docs MEM-c, MEM-c2): 10 readable by the sentence's own
    subject, 4 unreadable because the word cut shortened the subject (reason `subject_cut`), 5 unreadable because the gate cannot read the clause."""
    readable = {"田中の担当は認証": ["認証"], "サーバーのポートは8080": ["8080"], "認証の期限は金曜": ["金曜"], "今日の作業はK3の修正": ["K3の修正"], "mulの引数はaとb": ["a"],
                "会議の場所は東京": ["東京"], "予算の上限は100万円": ["100万円"], "テストの結果は成功": ["成功"], "リリースの日付は10月15日": ["10月15日"],
                "Pythonのバージョンは3.11": ["3.11"]}
    unreadable = ["K3の原因はimportの欠落", "次の手順は計測", "締め切りは金曜", "Airのコア数は4", "会議は東京で行う"]
    for k, text in enumerate(list(readable) + CUT_SUBJECTS + unreadable):
        s = new_store(tmp_path, "p%d" % k).begin("m")
        w = s.write(text)
        assert w["ok"], (text, w)
        un = by_type(w, "SELF_QUESTION_UNREADABLE")
        if text in readable:
            assert un == [], text
            r = recall(s, w["clause"]["question"])
            assert r["verdict"] == "ANSWER" and r["answers"][0]["answers"] == readable[text], (text, r["answers"])
        elif text in CUT_SUBJECTS:
            assert w["clause"]["question"] == CUT_QUESTIONS[text]
            assert len(un) == 1 and un[0]["counted"] is False and un[0]["reason"] == "subject_cut", text            # the gate could read it; the guard refused it
            r = recall(s, w["clause"]["question"])
            assert r["verdict"] == "NONE" and r["answers"] == [] and r["issues"] == ["subject_cut"] and [c["sid"] for c in r["subject_cut"]] == [0], text
        else:
            assert len(un) == 1 and un[0]["counted"] is False and "reason" not in un[0], text                       # the gate itself cannot read it: no reason is claimed
            assert recall(s, w["clause"]["question"])["verdict"] == "NONE" and "subject_cut" not in recall(s, w["clause"]["question"]), text
    assert len(readable) == 10 and len(CUT_SUBJECTS) == 4 and len(unreadable) == 5


def test_pr7_the_old_gate_hook_still_reads_the_four_cut_subjects(tmp_path):
    """`gate.evidence.v2` (no guard) is unchanged: the four cut-subject sentences are READ (as shorter questions) -- the behaviour the stores written with it replay."""
    for k, text in enumerate(CUT_SUBJECTS):
        s = new_store(tmp_path, "o%d" % k).begin("m", self_question=GATE)
        w = s.write(text)
        assert by_type(w, "SELF_QUESTION_UNREADABLE") == [], text
        r = recall(s, w["clause"]["question"])
        assert r["verdict"] == "ANSWER" and "subject_cut" not in r and "issues" not in r, text


PROBES = [("田中の担当 認証/決済", ["田中の担当は認証", "田中の担当は決済"], True),
          ("サーバーのポート 8080/9090", ["サーバーのポートは8080", "サーバーのポートは9090"], True),
          ("認証の期限 金曜 / 決済の期限 月曜", ["認証の期限は金曜", "決済の期限は月曜"], False),
          ("同じ事実を2回", ["田中の担当は認証", "田中の担当は認証"], False)]


@pytest.mark.parametrize("hook", [STUB, GATE, SUBJ], ids=["stub.v1", "gate.evidence.v2", "gate.evidence.v2+subject"])
def test_same_question_fires_on_the_planted_contradictions_all_hooks(tmp_path, hook):
    for k, (label, sents, fires) in enumerate(PROBES):
        s = new_store(tmp_path, "%s%d" % (hook.id, k)).begin("m", self_question=hook)
        got = [by_type(s.write(x), "SAME_QUESTION") for x in sents]
        assert got[0] == [] and (len(got[1]) == 1) is fires, label
        if fires:
            n = got[1][0]
            assert n["counted"] is True and [len(v["answers"]) for v in n["variants"]] == [1, 1] and [[o["sid"] for o in v["occurrences"]] for v in n["variants"]] == [[0], [1]]


def test_the_gate_and_the_stub_agree_on_the_probes_and_reversal_is_unaffected(tmp_path):
    """Same writes under both hooks: the SAME_QUESTION notes of the probes are identical, and every other note (REVERSAL, CONFLICT, NEW_RELATION, UNANCHORED, keys)
    is byte-identical: the hook only reads, it never touches the key or the weave."""
    seq = ["認証の前提は決済", "田中の担当は認証", "会議は東京で行う", PROBE_REVERSAL, "田中の担当は決済", "サーバーのポートは8080", "研修は東京で行う", "東京の天気は晴れ",
           "サーバーのポートは9090", "認証の期限は金曜", "決済の期限は月曜"]
    res = {}
    for hook in (STUB, GATE, SUBJ):
        s = new_store(tmp_path, hook.id).begin("m", self_question=hook)
        res[hook.id] = [s.write(x) for x in seq]
    assert [[n for n in r.get("notes", [])] for r in res["gate.evidence.v2"]] == [[n for n in r.get("notes", [])] for r in res["gate.evidence.v2+subject"]]     # nothing in this story has a cut subject
    other = lambda r: [n for n in r.get("notes", []) if n["type"] not in ("SAME_QUESTION", "SELF_QUESTION_UNREADABLE")]
    for a, b in zip(res["stub.v1"], res["gate.evidence.v2"]):
        assert other(a) == other(b) and a["keys"] == b["keys"] and a["crosses"] == b["crosses"] and a["marked"] == b["marked"]
    sq = {h: [(i, [v["answers"] for v in n["variants"]]) for i, r in enumerate(rs) for n in by_type(r, "SAME_QUESTION")] for h, rs in res.items()}
    assert sq["stub.v1"] == sq["gate.evidence.v2"] == [(4, [["認証"], ["決済"]]), (8, [["8080"], ["9090"]])]
    rev = [n for n in by_type(res["gate.evidence.v2"][3], "REVERSAL")]
    assert len(rev) == 1 and rev[0]["counted"] is True and rev[0]["key"] == [1, 0, 233]
    # UNREADABLE differs: the stub answers any 「<subject>は…」 sentence literally, the gate needs a copular clause 「Y は A」
    unr = {h: [i for i, r in enumerate(rs) if by_type(r, "SELF_QUESTION_UNREADABLE")] for h, rs in res.items()}
    assert unr == {"stub.v1": [], "gate.evidence.v2": [2, 6], "gate.evidence.v2+subject": [2, 6]}                                    # 「会議は東京で行う」 「研修は東京で行う」: the stub reads them literally, the gate cannot


def test_same_question_across_sessions_and_recall_over_the_whole_memory(tmp_path):
    st = new_store(tmp_path)
    s1 = st.begin("m")
    s1.write("田中の担当は認証")
    s1.write("認証の期限は金曜", role="user")
    s1.commit()
    s2 = st.begin("m")
    r = s2.write("田中の担当は決済")                                    # session 2 contradicts session 1: the self-question reads the whole memory
    sq = by_type(r, "SAME_QUESTION")
    assert len(sq) == 1 and [o["source"] for v in sq[0]["variants"] for o in v["occurrences"]] == ["mem:t/1#0", "mem:t/2#0"]
    s2.commit()
    s3 = st.begin("m")                                                  # a session that only reads
    rc = recall(s3, "田中の担当は何ですか")
    assert rc["verdict"] == "CHOICE" and groups(rc) == [(["認証"], [0]), (["決済"], [2])]
    assert [[o["session"] for o in g["occurrences"]] for g in rc["answers"]] == [[1], [2]]
    ru = recall(s3, "認証の期限は何ですか")
    assert ru["verdict"] == "ANSWER" and ru["answers"][0]["occurrences"][0]["role"] == "user" and ru["answers"][0]["occurrences"][0]["source"] == "mem:t/1#1:user"
    # L-MEM-13: no retraction.  The earlier answer is not replaced by the later one, nor by writing it again.
    s3.write("田中の担当は認証")
    rc = recall(s3, "田中の担当は何ですか")
    assert rc["verdict"] == "CHOICE" and groups(rc) == [(["認証"], [0, 3]), (["決済"], [2])]
    s3.commit()
    assert st.verify()["status"] == "OK"


def test_the_contradiction_policy_b_does_not_ask_the_hook_but_recall_still_works(tmp_path):
    asked = []

    class Spy(mr.GateSelfQuestion):

        def __call__(self, q, m):
            asked.append(q)
            return super().__call__(q, m)
    s = new_store(tmp_path).begin("m", contradiction_policy="b", self_question=Spy())
    write_all(s, ["田中の担当は認証", "田中の担当は決済"])
    assert asked == [] and recall(s, "田中の担当は何ですか")["verdict"] == "CHOICE"
    assert s.events()["detections"]["notes"] == 0 and s.events()["counted"].get("SAME_QUESTION") is None


def test_the_hook_calls_the_gate_with_the_memory_parameters(tmp_path, monkeypatch):
    calls = []
    real = ev.judge_quote

    def spy(corpus, qu, scope, sid, tier, i0, i1, version=ev.EVIDENCE_LATEST):
        calls.append((corpus.n_sentences, scope, sid, tier, i0, i1, version))
        return real(corpus, qu, scope, sid, tier, i0, i1, version)
    monkeypatch.setattr(ev, "judge_quote", spy)
    s = session(tmp_path)
    s.write("田中の担当は認証")
    n1 = len(calls)
    assert n1 == 6 and all(c[0] == 1 and c[1] == "clause" and c[3] == "WORD" and c[6] == "evidence.v2" and c[2] == 0 for c in calls)       # all 6 stretches of a 3-unit sentence
    s.write("会議は東京で開く")                                         # 「会議は何ですか」: the sentences holding 会議 are judged (sentence 1 only)
    n2 = len(calls)
    assert {(c[0], c[2]) for c in calls[n1:n2]} == {(2, 1)}
    s.write("田中の担当は決済")                                         # 「田中の担当は何ですか」: C_t has 3 sentences; the ones holding 担当 are judged, 会議 is not
    new = calls[n2:]
    assert {c[0] for c in new} == {3} and {c[2] for c in new} == {0, 2}
    assert all(0 <= c[5] - c[4] <= 3 for c in calls)                              # every stretch of at most 4 units, and only those
    assert {(c[2], c[4], c[5]) for c in new if c[2] == 0} == {(0, i0, i1) for i0 in range(3) for i1 in range(i0, 3)}
    n = len(calls)
    recall(s, "田中の担当は何ですか")                                    # recall: the same loop over the whole memory
    assert all(c[0] == 3 and c[1] == "clause" and c[6] == "evidence.v2" for c in calls[n:]) and {c[2] for c in calls[n:]} == {0, 2}


def test_the_gate_passes_a_memory_stretch_only_as_a_whole_answer_in_its_clause(tmp_path):
    """The gate is called UNCHANGED on the memory corpus: of the stretches of 「田中の担当は認証」 only 「認証」 passes 「田中の担当は何ですか」; the subject is read in the
    clause (scope clause: a memory sentence has no article title, its title would be `mem:t/1`) and another subject finds no evidence."""
    s = session(tmp_path)
    s.write("田中の担当は認証")
    c = s.run.corpus_cur
    qu = ev.question_units("田中の担当は何ですか")
    res = {(a, b): ev.judge_quote(c, qu, ev.SCOPE_CLAUSE, 0, "WORD", a, b, ev.EVIDENCE_V2) for a in range(3) for b in range(a, 3)}
    assert [k for k, r in res.items() if not r["codes"]] == [(2, 2)]
    ok = res[(2, 2)]
    assert ok["answer"] == "認証" and ok["clause"] == "田中の担当は認証" and ok["evidence"]["subject"] == [{"run": "田中", "via": "clause"}] and ok["evidence"]["copula"] == "Y は A"
    assert res[(0, 2)]["codes"] == ["answer_crosses_break", "no_subject", "no_slot_head", "answer_holds_question_unit"]
    other = ev.question_units("鈴木の担当は何ですか")
    for scope in (ev.SCOPE_CLAUSE, ev.SCOPE_TITLE):                       # the memory source is no title that holds a subject: 鈴木 is found neither way
        assert ev.judge_quote(c, other, scope, 0, "WORD", 2, 2, ev.EVIDENCE_V2)["codes"] == ["no_subject"]


def test_hook_contract_answers_over_h0_to_t_with_spans(tmp_path):
    seen = []

    class Rec(mr.GateSelfQuestion):
        id = "gate.evidence.v2"

        def __call__(self, q, m):
            out = super().__call__(q, m)
            seen.append((q, m.t, m.corpus_after.n_sentences, m.corpus_before.n_sentences, [(a.sid, a.text, a.span) for a in out]))
            return out
    s = new_store(tmp_path).begin("m", self_question=Rec())
    s.write("今日の作業はK3の修正")
    assert seen == [("今日の作業は何ですか", 0, 1, 0, [(0, "K3", (2, 3)), (0, "K3の修正", (2, 4))])]       # the passing stretches of ONE sentence; the longest is the statement
    answers = seen[0][4]
    sets, comps = mn.answer_groups([mn.Answer(*a) for a in answers])
    assert comps == [[0]] and list(sets[0].values()) == ["K3の修正"]


def test_norm_answer_is_the_gates_ignore_set():
    assert mn.norm_answer("「金曜」") == mn.norm_answer("金曜") == "金曜"
    assert mn.norm_answer("ＡＢＣ") == mn.norm_answer("abc ") == "abc"
    assert mn.norm_answer("東京・大阪") == "東京大阪" and mn.norm_answer("a　b") == "ab"
    assert all(ch not in mn.norm_answer("“x” 'y' 『z』") for ch in ev.IGNORE)
    assert mn.same_question_note("q", [mn.Answer(0, "「金曜」"), mn.Answer(1, "金曜")], 1, [{"source": "a"}, {"source": "b"}], "c1") is None


QUESTIONS = ["田中の担当は何ですか", "サーバーのポートは何ですか", "認証の期限は何ですか", "決済の期限は何ですか", "鈴木の担当は何ですか", "会議はどこで開きますか", "会議はどこで行いますか",
             "会議はどこで行うか", "担当は何ですか", "田中の担当は", "認証の前提は何ですか", "東京の天気は何ですか", "今日の作業は何ですか", "ポートは何ですか"]


def test_the_prefilter_drops_nothing_the_gate_would_pass(tmp_path):
    s = session(tmp_path)
    write_all(s, PR4 + ["認証の前提は決済", "決済の前提は認証", "会議は東京で行う", "東京の天気は晴れ", "今日の作業はK3の修正", "今日の作業はK3のテスト", "会議は福岡で開きます"])
    corpus = s.run.corpus_cur
    for q in QUESTIONS:
        a = mr.recall(corpus, q)
        b = mr.recall(corpus, q, prefilter=False)
        assert (a["verdict"], a["answers"]) == (b["verdict"], b["answers"]), q
        assert a["candidates"] <= b["candidates"] == corpus.n_sentences and a["judged"] <= b["judged"]


def test_recall_over_memory_never_reads_a_base_corpus(tmp_path, monkeypatch):
    base = Corpus(json.dumps({"sent": "田中の担当は認証", "source": "wiki#1", "kind": "base"}, ensure_ascii=False).encode() + b"\n")
    for fn in (lambda: mr.assert_memory_corpus(base), lambda: mr.recall(base, "田中の担当は何ですか"), lambda: mr.judge_memory(base, "田中の担当は何ですか"),
               lambda: GATE("田中の担当は何ですか", mn.MemoryBefore(0, {}, (), (), Corpus(b""), base))):
        with pytest.raises(Refuse) as e:
            fn()
        assert e.value.type == "not_memory_row"
    mr.assert_memory_corpus(Corpus(b""))                                                      # the empty memory is a memory corpus
    s = session(tmp_path)
    write_all(s, PR4)
    mr.assert_memory_corpus(s.run.corpus_cur)
    built = []
    for name in ("__init__", "load"):
        orig = getattr(Corpus, name)

        def spy(*a, _o=orig, _n=name, **k):
            built.append(_n)
            return _o(*a, **k)
        monkeypatch.setattr(Corpus, name, staticmethod(spy) if name == "load" else spy)
    opened = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda *a, **k: (opened.append(str(a[0])), real_open(*a, **k))[1])
    recall(s, "田中の担当は何ですか")
    monkeypatch.undo()
    sess_dir = str(s.ledger.dir)
    assert built == [] and all(p.startswith(sess_dir) for p in opened), (built, opened)         # no corpus is built; the only files touched are the session's own ledger rows
    # a tampered in-memory history is refused by the guard, not read
    s.run.rows = s.run.rows[:1] + [{"kind": "base", "sent": "x", "source": "wiki#1"}]
    r = s.call("recall", {"question": "田中の担当は何ですか"})
    assert r["ok"] is False and r["refusal"] == "not_memory_row"


def test_recall_refusals_and_counters(tmp_path):
    s = session(tmp_path)
    s.write("田中の担当は認証")
    assert s.call("recall", {})["refusal"] == "bad_args"
    assert s.call("recall", {"question": 5})["refusal"] == "bad_args"
    assert s.call("recall", {"question": "田中", "extra": 1})["refusal"] == "bad_args"
    assert s.call("recall", {"question": "x" * 65})["refusal"] == "args_too_large"
    assert s.call("recall", {"question": "田中\nの担当は何ですか"})["refusal"] == "bad_question"
    assert s.call("recall", {"question": ""})["refusal"] == "bad_question"
    assert s.call("recall", {"question": "AKIAIOSFODNN7EXAMPLE"})["refusal"] == "secret_shaped_unit"          # a secret-shaped query is redacted in the ledger and refused
    st0 = s.status()
    assert st0["sentences"] == 1
    for k in range(60 - st0["recalls"]):
        s.call("recall", {"question": "田中の担当は何ですか"})
    r = s.call("recall", {"question": "田中の担当は何ですか"})
    assert r["ok"] is False and r["refusal"] == "recall_cap" and r["detail"]["limit"] == 60
    assert s.status()["sentences"] == 1 and s.status()["memory_sha"] == st0["memory_sha"]      # recall never changes the memory


def test_recall_after_a_refused_write_sees_only_the_committed_sentences(tmp_path):
    s = session(tmp_path)
    s.write("田中の担当は認証")
    assert s.write("東京で会議を開く")["refusal"] == "span_inexpressible"
    assert s.write("田中の担当は\n決済")["refusal"] == "bad_sentence"
    r = recall(s, "田中の担当は何ですか")
    assert r["verdict"] == "ANSWER" and r["sentences"] == 1


def test_known_limit_subjectless_clause_is_unreadable_and_says_why(tmp_path):
    s = session(tmp_path)
    w = s.write("締め切りは金曜")
    assert [n["type"] for n in w["notes"]] == ["SELF_QUESTION_UNREADABLE"] and w["clause"]["question"] == "締め切りは何ですか"
    r = recall(s, "締め切りは何ですか")
    assert r["verdict"] == "NONE" and r["issues"] == ["question_has_no_subject"]
    w2 = s.write("締め切りは月曜")                                      # so a subject-less contradiction is NOT detected: both stay, unread
    assert [n["type"] for n in w2["notes"]] == ["SELF_QUESTION_UNREADABLE"] and s.events()["detections"]["notes"] == 0 and s.events()["cost"]["unreadable"] == 2


def test_old_gate_hook_reads_a_cut_identifier_as_a_shorter_question_and_over_merges(tmp_path):
    """PINNED FOR REPLAY (hook `gate.evidence.v2`, no guard; stores written with it replay with exactly this behaviour).  The clause cut starts at the first WORD UNIT, and
    the unit filter drops a short Latin prefix (fmt_, int_, K, add): 「fmt_numの戻り値は…」 asks 「numの戻り値は何ですか」.  The gate reads that fine -- so two DIFFERENT
    functions, fmt_num and int_num, are one question (a false SAME_QUESTION).  MEM-c2 fixes it in the NEW hook (the next test), not here."""
    s = new_store(tmp_path, "old").begin("m", self_question=GATE)
    w1 = s.write("fmt_numの戻り値は文字列")
    assert w1["clause"]["question"] == "numの戻り値は何ですか" and by_type(w1, "SAME_QUESTION") == [] and by_type(w1, "SELF_QUESTION_UNREADABLE") == []
    w2 = s.write("int_numの戻り値は整数")
    sq = by_type(w2, "SAME_QUESTION")
    assert len(sq) == 1 and [v["answers"] for v in sq[0]["variants"]] == [["文字列"], ["整数"]]             # a false alarm: two functions
    assert recall(s, "numの戻り値は何ですか")["verdict"] == "CHOICE"
    for q in ("fmt_numの戻り値は何ですか", "fmtnumの戻り値は何ですか", "int_numの戻り値は何ですか"):
        assert recall(s, q)["verdict"] == "NONE", q                                                    # the typed identifier cannot be read as a subject
    s2 = new_store(tmp_path, "k3").begin("m", self_question=GATE)
    w = s2.write("K3の原因はimportの欠落")
    assert w["clause"]["question"] == "3の原因は何ですか" and [n["type"] for n in w["notes"]] == ["SELF_QUESTION_UNREADABLE"] and "reason" not in w["notes"][0]
    r = recall(s2, "K3の原因は何ですか")                                 # typed whole, the gate reads it
    assert r["verdict"] == "ANSWER" and groups(r) == [(["importの欠落"], [0])]


CUT_PAIRS = [("fmt_numの戻り値は文字列", "int_numの戻り値は整数"), ("add関数の引数は2つ", "sub関数の引数は3つ"), ("担当者の名前は佐藤", "責任者の名前は鈴木"),
             ("ops.pyの責任は書き込み", "cli.pyの責任は入力"), ("K3の担当は田中", "K3の担当は鈴木")]


TRUE_PAIRS = [("田中の担当は認証", "田中の担当は決済"), ("サーバーのポートは8080", "サーバーのポートは9090"), ("会議の場所は東京", "会議の場所は大阪"),
              ("今日の作業はK3の修正", "今日の作業はK3のテスト"), ("Pythonのバージョンは3.11", "Pythonのバージョンは3.12"), ("mulの引数はaとb", "mulの引数はcとd"),
              ("メモ、田中の担当は認証", "メモ、田中の担当は決済")]


def pair_notes(tmp_path, tag, hook, a, b):
    s = new_store(tmp_path, tag).begin("m", self_question=hook)
    return s, by_type(s.write(a), "SAME_QUESTION"), s.write(b)


def test_the_subject_guard_turns_cut_subjects_unreadable_never_same_question(tmp_path):
    """The owner's rule (2026-10-12): the question's subject must equal the sentence's WHOLE subject; cut short = UNREADABLE (counted as coverage, never a detection)."""
    for k, (a, b) in enumerate(CUT_PAIRS):
        for tag, hook, fires in (("old", GATE, k < 4), ("new", SUBJ, False)):                          # K3の担当 was already unreadable under the old hook
            s, sq_a, wb = pair_notes(tmp_path, "c%d%s" % (k, tag), hook, a, b)
            assert sq_a == [] and (len(by_type(wb, "SAME_QUESTION")) == 1) is fires, (a, b, tag)
            if tag == "new":
                un = by_type(wb, "SELF_QUESTION_UNREADABLE")
                assert len(un) == 1 and un[0]["counted"] is False and s.events()["detections"]["notes"] == 0 and s.events()["cost"]["unreadable"] == 2, (a, b)
                assert un[0].get("reason") == ("subject_cut" if k < 4 else None), (a, b)                # K3: the gate itself cannot read 「3の原因…」, so no reason is claimed


def test_the_subject_guard_keeps_the_true_same_question_probes(tmp_path):
    for k, (a, b) in enumerate(TRUE_PAIRS):
        for tag, hook in (("old", GATE), ("new", SUBJ)):
            s, sq_a, wb = pair_notes(tmp_path, "t%d%s" % (k, tag), hook, a, b)
            sq = by_type(wb, "SAME_QUESTION")
            assert sq_a == [] and len(sq) == 1 and sq[0]["counted"] is True and by_type(wb, "SELF_QUESTION_UNREADABLE") == [], (a, b, tag)
    s, _, wb = pair_notes(tmp_path, "pair-same", SUBJ, "田中の担当は認証", "田中の担当は認証")
    assert by_type(wb, "SAME_QUESTION") == []                                                          # the same fact twice is no contradiction


def test_the_guard_also_refuses_a_longer_written_subject_known_cost(tmp_path):
    """KNOWN COST (choose missed detection over false detection): a subject that merely HAS a prefix before the question (新サーバー, 昨日田中, 東京の田中 ...) is a longer subject
    as written, so it is unreadable too -- even when both sentences have the same prefix (a true contradiction is missed)."""
    for a, b in (("新サーバーのポートは8080", "新サーバーのポートは9090"), ("昨日田中の担当は認証", "昨日田中の担当は決済"), ("ログイン画面の背景は青", "ログイン画面の背景は赤")):
        s, sq_a, wb = pair_notes(tmp_path, "x" + a[:2], SUBJ, a, b)
        assert sq_a == [] and by_type(wb, "SAME_QUESTION") == [] and by_type(wb, "SELF_QUESTION_UNREADABLE")[0]["reason"] == "subject_cut", (a, b)
        _, _, wo = pair_notes(tmp_path, "y" + a[:2], GATE, a, b)
        assert len(by_type(wo, "SAME_QUESTION")) == 1, (a, b)                                          # the old hook did detect these: the true detections the guard loses


def test_a_cut_sentence_never_joins_a_later_question(tmp_path):
    """The guard is on every answer, not only on sentence t's: an earlier cut sentence is not an occurrence of a later (whole-subject) question, and the other way round."""
    s = new_store(tmp_path, "mix").begin("m")
    assert by_type(s.write("fmt_numの戻り値は文字列"), "SELF_QUESTION_UNREADABLE")
    w = s.write("numの戻り値は整数")                                    # whole subject `num`: readable, and NOT contradicted by fmt_num's answer
    assert by_type(w, "SAME_QUESTION") == [] and by_type(w, "SELF_QUESTION_UNREADABLE") == []
    r = recall(s, "numの戻り値は何ですか")
    assert r["verdict"] == "ANSWER" and groups(r) == [(["整数"], [1])]                                  # ANSWER from the whole-subject sentence; the cut one is listed, not merged
    assert r["issues"] == ["subject_cut"] and r["subject_cut"] == [{"sid": 0, "source": "mem:t/1#0", "session": 1, "role": "model", "answers": ["文字列"], "clause": "numの戻り値は文字列"}]
    old = new_store(tmp_path, "mixold").begin("m", self_question=GATE)
    old.write("fmt_numの戻り値は文字列")
    assert len(by_type(old.write("numの戻り値は整数"), "SAME_QUESTION")) == 1                           # the old hook merged them


def test_recall_with_a_cut_subject_is_none_with_issue_subject_cut(tmp_path):
    s = session(tmp_path)
    s.write("fmt_numの戻り値は文字列")
    s.write("int_numの戻り値は整数")
    r = recall(s, "numの戻り値は何ですか")
    assert r["verdict"] == "NONE" and r["answers"] == [] and r["issues"] == ["subject_cut"]
    assert [(c["sid"], c["answers"], c["clause"]) for c in r["subject_cut"]] == [(0, ["文字列"], "numの戻り値は文字列"), (1, ["整数"], "numの戻り値は整数")]
    assert r["candidates"] == 2 and r["sentences"] == 2 and r["judged"] > 0                           # the sentences were found and judged; the guard refused them
    # a result without a cut has none of the new keys (the shape of every earlier recall)
    s2 = session(tmp_path, "plain")
    s2.write("田中の担当は認証")
    r2 = recall(s2, "田中の担当は何ですか")
    assert "subject_cut" not in r2 and "issues" not in r2 and r2["verdict"] == "ANSWER"
    # the no-guard hook's sessions never get the new keys either
    s3 = new_store(tmp_path, "old").begin("m", self_question=GATE)
    s3.write("fmt_numの戻り値は文字列")
    r3 = recall(s3, "numの戻り値は何ですか")
    assert r3["verdict"] == "ANSWER" and "subject_cut" not in r3 and "issues" not in r3


def test_mid_token_rule():
    f = mr.mid_token
    assert [f("fmt_numの", 4), f("担当者の", 2), f("ops.pyの", 4), f("add関数の", 3), f("K3の", 1), f("新サーバーの", 1), f("v-2の", 2), f("a・bの", 2)] == [True] * 8
    assert [f("田中の担当は", 0), f("メモ、田中の", 3), f("a 田中の", 2), f("a。田中の", 2), f("a\n田中の", 2), f("「田中", 1)] == [False] * 6
    assert f("", 0) is False


def test_the_guard_changes_nothing_but_the_hook_answers(tmp_path):
    """On a story without a cut subject the two gate hooks write the same rows, key for key (only the begin row's hook id differs); the guard never touches a key or a weave."""
    seq = [x for p in TRUE_PAIRS for x in p] + ["認証の前提は決済", "決済の前提は認証", "会議は東京で行う", "東京の天気は晴れ"]
    rows = {}
    for hook in (GATE, SUBJ):
        s = new_store(tmp_path, "r" + hook.id).begin("m", self_question=hook)
        write_all(s, seq)
        rows[hook.id] = [{k: v for k, v in r.items() if k not in ("sha", "prev")} for r in ledger_rows(s)[1:]]
    assert rows["gate.evidence.v2"] == rows["gate.evidence.v2+subject"]


STORY_GATE = [["認証の前提は決済", "田中の担当は認証", "東京で会議を開く", "会議は東京で行う", PROBE_REVERSAL], ["田中の担当は決済", "サーバーのポートは8080", "研修は東京で行う", "東京の天気は晴れ"],
              ["サーバーのポートは9090", "認証の期限は金曜", "決済の期限は月曜", "鈴木の担当は決済", "田中の担当は認証と決済"]]


def run_story(tmp_path, name, hook, recalls=True):
    st = new_store(tmp_path, name)
    for k, sents in enumerate(STORY_GATE):
        s = st.begin("test-model", self_question=hook)
        write_all(s, sents)
        if recalls:
            for q in ("田中の担当は何ですか", "サーバーのポートは何ですか", "認証の期限は何ですか", "鈴木の担当は何ですか"):
                r = s.call("recall", {"question": q})
                assert r["ok"] is (hook is not None and getattr(hook, "evidence_version", None) is not None)
        assert s.commit()["ok"]
    return st


@pytest.mark.parametrize("hook", [GATE, SUBJ], ids=["gate.evidence.v2", "gate.evidence.v2+subject"])
def test_gate_store_replays_byte_for_byte_with_recall_rows(tmp_path, hook):
    st = run_story(tmp_path, "g", hook)
    v = st.verify(hook)
    assert v["status"] == "OK" and v["sessions"] == 3 and v["sentences"] == 13 and v["replay"]["status"] == "IDENTICAL"
    assert st.replay(hook).identical and st.replay(mem.FROM_HEADER).identical
    rows = ledger_rows(os.path.join(st.sessions_dir, "s0003"))
    assert [r["result"]["verdict"] for r in rows if r["op"] == "recall"] == ["CHOICE", "CHOICE", "ANSWER", "ANSWER"]          # 田中の担当, ポート, 認証の期限, 鈴木の担当 (written in session 3)
    h = rows[0]["result"]["header"]
    assert (h["self_question"], h["evidence_version"]) == (hook.id, "evidence.v2")
    # the hook is code, recorded by id: another hook (or none) cannot replay it -- the old gate hook and the guarded one are two hooks
    for other in (STUB, None, GATE if hook is SUBJ else SUBJ):
        rep = st.replay(other)
        assert rep.status == "INPUTS" and rep.mismatch == "self_question_mismatch"
    assert st.verify(STUB)["status"] == "REPLAY_INPUTS_MISMATCH"
    # the hook DEFAULT (the API default of a NEW store, frozen at the guarded gate v2) replays the stores written with it and not the old ones; replay / verify now default to FROM_HEADER (PUB-M6e)
    assert (st.replay(mem.DEFAULT).status == "IDENTICAL") is (hook is SUBJ) and st.replay().identical
    assert mem.main(["verify", "--store", str(st.path), "--hook", "header"]) == 0
    assert mem.main(["verify", "--store", str(st.path), "--hook", hook.id]) == 0


def test_a_forged_recall_row_is_replay_differs(tmp_path):
    """A recall row whose result says something the gate does not produce (a sha-valid chain): the replay finds it, at that row."""
    st = run_story(tmp_path, "forge", SUBJ)
    d = os.path.join(st.sessions_dir, "s0003")
    rows = ledger_rows(d)
    i = next(k for k, r in enumerate(rows) if r["op"] == "recall" and r["result"]["verdict"] == "CHOICE")
    rows[i]["result"]["answers"] = rows[i]["result"]["answers"][:1]                  # a CHOICE silently made an answer: contested facts hidden
    rows[i]["result"]["verdict"] = "ANSWER"
    prev = mem.GENESIS
    out = []
    for r in rows:
        r = mem.lg.seal(r["i"], prev, {k: v for k, v in r.items() if k not in ("v", "i", "prev", "sha")})
        prev = r["sha"]
        out.append(mem.lg.line_of(r))
    open(os.path.join(d, "ops.jsonl"), "wb").write(b"".join(out))
    open(os.path.join(d, "HEAD"), "w").write(prev + "\n")
    h = json.loads(st.head_path.read_text())
    h["sessions"][2]["head"] = prev
    st.head_path.write_text(json.dumps(h, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
    rep = st.replay()
    assert rep.status == "DIFFERS" and rep.first_diff["session"] == "s0003" and rep.first_diff["i"] == i and rep.first_diff["field"] == "result"


def test_stub_store_still_replays_under_the_stub_and_not_under_the_default(tmp_path):
    st = run_story(tmp_path, "s", STUB, recalls=False)
    assert st.verify(STUB)["status"] == "OK" and st.replay(STUB).identical and st.replay(mem.FROM_HEADER).identical
    d = st.replay(mem.DEFAULT)                                           # the hook DEFAULT is the gate: a different id (replay / verify default to FROM_HEADER since PUB-M6e)
    assert d.status == "INPUTS" and d.mismatch == "self_question_mismatch" and st.replay().identical
    assert mem.main(["replay", "--store", str(st.path), "--hook", "default"]) == 2
    assert mem.main(["replay", "--store", str(st.path)]) == 0
    assert mem.main(["replay", "--store", str(st.path), "--hook", "stub.v1"]) == 0
    assert mem.main(["verify", "--store", str(st.path), "--hook", "header"]) == 0
    assert mem.main(["verify", "--store", str(st.path), "--hook", "gate.evidence.v2"]) == 1
    h = ledger_rows(os.path.join(st.sessions_dir, "s0001"))[0]["result"]["header"]
    assert (h["self_question"], h["evidence_version"]) == ("stub.v1", None)


def test_a_store_may_change_its_hook_between_sessions(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m", self_question=STUB)
    s.write("田中の担当は認証")
    s.commit()
    s = st.begin("m")                                                    # the default: the gate with the subject guard
    s.write("田中の担当は決済")
    assert recall(s, "田中の担当は何ですか")["verdict"] == "CHOICE"
    s.commit()
    s = st.begin("m", self_question=GATE)                                # ... and back to the gate without it
    s.write("田中の担当は承認")
    s.commit()
    assert st.verify(mem.FROM_HEADER)["status"] == "OK"
    assert [r["result"]["header"]["self_question"] for r in (ledger_rows(os.path.join(st.sessions_dir, d))[0] for d in ("s0001", "s0002", "s0003"))] == ["stub.v1", SUBJ.id, GATE.id]
    assert all(st.verify(h)["status"] == "REPLAY_INPUTS_MISMATCH" for h in (STUB, GATE, SUBJ))


GOLDEN_MEM_AB = {"stub.v1": "fcc86cf2f9d7904bdc20f0baeb4631510f29c8f457a44b04be47648cd2c133a3", "none": "0f6a6210679164e46a0a48668f3d0646b2407059fd0ee96fd0e711fbcc4d003b"}


_STORY_AB = [["認証の前提は決済", "田中の担当は認証", "東京で会議を開く", "会議は東京で行う", "決済の前提は認証"],
             ["田中の担当は決済", "サーバーのポートは8080", "研修は東京で行う", "東京の天気は晴れ"],
             ["サーバーのポートは9090", "認証の期限は金曜", "決済の期限は月曜", "鈴木の担当は決済", "田中の担当は認証と決済"]]


def digest_of(st):
    h = hashlib.sha256()
    for rid in ("s0001", "s0002", "s0003"):
        h.update(open(os.path.join(st.sessions_dir, rid, "ops.jsonl"), "rb").read())
    h.update(open(st.memory_path, "rb").read())
    h.update(open(st.head_path, "rb").read())
    return h.hexdigest()


@pytest.mark.parametrize("name,hook", [("stub.v1", STUB), ("none", None)])
def test_mem_ab_ledgers_are_byte_identical(tmp_path, name, hook):
    st = new_store(tmp_path, "ab" + name)
    for sents in _STORY_AB:
        s = st.begin("test-model", self_question=hook)
        write_all(s, sents)
        s.commit()
    assert digest_of(st) == GOLDEN_MEM_AB[name]


GOLDEN_GATE_V2 = {"story": "334eabfab691862842c80bb0c4ef42caf985040dae6256b59d9dcc3846f26c6c", "cut": "e925b0163283c59e92a7d5e74aeae931d557fc139ec484aa505a4fca374e013f"}


_STORIES_GOLDEN = {"story": _STORY_AB,
                   "cut": [["fmt_numの戻り値は文字列", "田中の担当は認証", "add関数の引数は2つ"], ["int_numの戻り値は整数", "sub関数の引数は3つ", "numの戻り値は真偽", "田中の担当は決済"],
                           ["担当者の名前は佐藤", "責任者の名前は鈴木", "新サーバーのポートは8080", "サーバーのポートは9090"]]}


_QS_GOLDEN = ("田中の担当は何ですか", "numの戻り値は何ですか", "fmt_numの戻り値は何ですか", "関数の引数は何ですか", "者の名前は何ですか", "サーバーのポートは何ですか")


@pytest.mark.parametrize("name", ["story", "cut"])
def test_old_gate_hook_stores_are_byte_identical_and_replay(tmp_path, name):
    st = new_store(tmp_path, "gold" + name)
    for sents in _STORIES_GOLDEN[name]:
        s = st.begin("test-model", self_question=GATE)
        write_all(s, sents)
        for q in _QS_GOLDEN:
            s.call("recall", {"question": q})
        assert s.commit()["ok"]
    assert digest_of(st) == GOLDEN_GATE_V2[name]
    assert st.verify(mem.FROM_HEADER)["status"] == "OK" and st.verify(GATE)["status"] == "OK"
    if name == "cut":                                                    # what the old hook wrote: the merged answer and the false alarm, as recorded
        rows = ledger_rows(os.path.join(st.sessions_dir, "s0003"))
        merged = [r["result"] for r in rows if r["op"] == "recall" and r["args"]["question"] == "numの戻り値は何ですか"]
        assert merged[0]["verdict"] == "CHOICE" and "subject_cut" not in merged[0]


_SCRIPT = r"""
import sys, hashlib, os, json, pathlib
sys.path.insert(0, os.path.join(%(root)r, "tests", "core"))
from test_mem_recall import run_story, GATE, SUBJ, digest_of

for h in (GATE, SUBJ):
    st = run_story(pathlib.Path(sys.argv[1]), "det" + h.id, h)
    print(digest_of(st), st.verify(h)["status"], hashlib.sha256(json.dumps(st.rows(), sort_keys=True).encode()).hexdigest()[:8])
"""


def test_gate_store_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    py = os.environ.get("VERA_TEST_PYTHON") or sys.executable
    seen = set()
    for seed in ("0", "1", "12345"):                                     # one process at a time
        out = subprocess.run([py, "-c", _SCRIPT % {"root": ROOT}, str(tmp_path / seed)], env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT),
                             capture_output=True, text=True, timeout=600)
        assert out.returncode == 0, out.stderr
        lines = [ln.split() for ln in out.stdout.strip().splitlines()]
        assert len(lines) == 2 and all(ln[1] == "OK" for ln in lines)
        seen.add(tuple((ln[0], ln[2]) for ln in lines))
    assert len(seen) == 1
