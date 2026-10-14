"""MEM-b tests: the history key and the notes (docs/LINE3_LOOM_MEMORY_DESIGN.md 3.3-3.4, 9.4 T-MEM-13..19 and the SAME_QUESTION detection of T-MEM-20..25 that
needs no gate; L-MEM-06..10, 16).

The history rule under test: the key of write t is computed against the sentences BEFORE t, never against its own evidence.  SAME_QUESTION is built on a pluggable
`self_question` hook; here a stub (`memnotes.StubSelfQuestion`) stands in for the evidence gate of MEM-c."""


import json


import os


import pytest


from verantyx.loom import memnotes as mn


from verantyx.loom import memory as mem


from verantyx.loom import read as rd


from mem_common import (PROBE_NEW_RELATION, PROBE_REVERSAL, PROBE_SHAPE, PROBE_SQ, SECOND_TOKYO, SEEDS, STUB, filler, ledger_rows, new_store, notes_of, session,
                        write_all)


def _by_type(res, typ):
    return [n for n in res.get("notes", []) if n["type"] == typ]


def test_reversal_pr3_key_1_0_233_with_the_swap_centre_to_arm(tmp_path):
    s = session(tmp_path)
    a = s.write("認証の前提は決済")
    assert "REVERSAL" not in notes_of(a)
    b = s.write("決済の前提は認証")
    rev = _by_type(b, "REVERSAL")
    assert len(rev) == 1 and rev[0]["counted"] is True
    n = rev[0]
    assert n["key"] == [1, 0, 233] and n["best_key"] == [1, 1, 0] and n["swaps"] == [["centre", "+x:0"]] and n["centre"] == "前提"
    assert n["units"] == [{"seat": "+x:0", "unit": "決済", "particle": "の"}]
    k = next(k for k in b["keys"] if k["cid"] == n["cid"])
    assert k["np"]["status"] == "unstable" and k["np"]["key"] == [1, 0, 233] and k["npa"]["status"] == "unstable"
    assert [x["np"]["status"] for x in b["keys"] if x["cid"] != n["cid"]] == ["trivially_stable"]          # the lone 認証 cross has nothing to compare


def test_a_repeat_is_stable_1_1_377(tmp_path):
    s = session(tmp_path)
    s.write("田中の担当は認証")
    r = s.write("田中の担当は認証")
    assert "REVERSAL" not in notes_of(r) and "NEW_RELATION" not in notes_of(r)
    k = r["keys"][0]
    assert k["np"]["status"] == "stable" and k["np"]["key"] == [1, 1, 377] and k["np"]["improving"] == []


def test_the_key_is_computed_against_the_history_only(tmp_path):
    """The history rule: the corpus the key reads has exactly the t sentences BEFORE t (its sha is the sha of H[0..t-1]), and never holds the sentence itself."""
    seen = []
    real = rd.stability_of

    def spy(run, cross, mode):
        seen.append((run.corpus.n_sentences, run.corpus.corpus_sha, mode))
        return real(run, cross, mode)

    s = session(tmp_path)
    orig = mn.rd.stability_of
    mn.rd.stability_of = spy
    try:
        sents = ["認証の前提は決済", "田中の担当は認証", "認証の前提は決済", "決済の前提は認証"]
        for t, x in enumerate(sents):
            seen.clear()
            r = s.write(x)
            assert seen and all(n == t for n, _, _ in seen), (t, seen)
            assert all(sha == mem.hashlib.sha256(mem.rows_bytes(s.run.rows[:t])).hexdigest() for _, sha, _ in seen)
            assert r["history"]["sentences"] == t and r["history"]["corpus_sha"] == seen[0][1]
            assert {m for _, _, m in seen} == {"strict_np", "strict_npa"}
    finally:
        mn.rd.stability_of = orig


def test_a_sentence_never_confirms_itself(tmp_path):
    """If the key read its own sentence, a lone 「決済の前提は認証」 would confirm itself and the reversal could never show.  Each write is judged against the
    sentences BEFORE it only: the empty history says nothing, the history of one sentence says REVERSAL, and writing the same sentence again is judged against
    a history that now holds both orders (so it is a different reading, the key of write 2 is not the key of write 1)."""
    s = session(tmp_path)
    s.write("認証の前提は決済")
    r1 = s.write("決済の前提は認証")
    r2 = s.write("決済の前提は認証")
    assert "REVERSAL" in notes_of(r1) and r1["history"]["sentences"] == 1 and r2["history"]["sentences"] == 2
    k1 = next(k for k in r1["keys"] if k["centre"] == "前提")
    k2 = next(k for k in r2["keys"] if k["centre"] == "前提")
    assert k1["np"]["key"] != k2["np"]["key"]
    # the empty history says nothing about any sentence, however odd
    s2 = session(tmp_path, "m2")
    assert notes_of(s2.write("決済の前提は認証")) == []
    # a key never moves when only LATER sentences differ (it cannot read them)
    ra = session(tmp_path, "ma").write("決済の前提は認証")
    rb = session(tmp_path, "mb").write("決済の前提は認証")
    assert ra["keys"] == rb["keys"]
    sa, sb = session(tmp_path, "mc"), session(tmp_path, "md")
    for x in ("認証の前提は決済", "田中の担当は認証"):
        sa.write(x)
        sb.write(x)
    assert sa.write("決済の前提は認証")["keys"] == sb.write("決済の前提は認証")["keys"]


def test_reversal_from_an_earlier_session(tmp_path):
    st = new_store(tmp_path)
    s1 = st.begin("m")
    s1.write("認証の前提は決済")
    s1.commit()
    s2 = st.begin("m")
    r = s2.write("決済の前提は認証")
    assert "REVERSAL" in notes_of(r) and r["history"]["sentences"] == 1
    s2.commit()
    assert st.verify()["status"] == "OK"


def test_new_relation_pr6_np_stable_npa_unstable(tmp_path):
    s = session(tmp_path)
    write_all(s, ["会議は東京で行う", "研修は東京で行う"])
    r = s.write(PROBE_NEW_RELATION)
    nr = _by_type(r, "NEW_RELATION")
    assert len(nr) == 1 and nr[0]["counted"] is False                    # information, not a detection
    assert "REVERSAL" not in notes_of(r)
    k = next(k for k in r["keys"] if k["cid"] == nr[0]["cid"])
    assert k["np"]["status"] != "unstable" and k["npa"]["status"] == "unstable" and k["npa"]["key"] == [0, 0, 0]
    assert nr[0]["best_key"] == [0, 0, 110] and nr[0]["swaps"] == [["+x:0", "+y:0"]]          # moving 東京 from の to で
    assert "UNANCHORED" in notes_of(r)                                   # adj(東京, で) = 2: the floor of two sentences
    u = _by_type(r, "UNANCHORED")[0]
    assert u["unit"] == "東京" and u["have"] == 0 and u["evidence"] == [{"particle": "で", "n": 2}]


def test_unanchored_needs_two_sentences(tmp_path):
    s = session(tmp_path)
    s.write("会議は東京で行う")
    r = s.write(PROBE_NEW_RELATION)
    assert "NEW_RELATION" in notes_of(r) and "UNANCHORED" not in notes_of(r)


def test_op_mem_1_b_keeps_the_adhesion_out_of_the_key(tmp_path):
    """OP-MEM-1 (b): kind memory_answer.  The memory's adhesion stays empty, so `a` is 0 always: NEW_RELATION and UNANCHORED never fire; REVERSAL is unchanged."""
    sb = session(tmp_path, "b", kind_policy="b")
    write_all(sb, ["会議は東京で行う", "研修は東京で行う"])
    rb = sb.write(PROBE_NEW_RELATION)
    assert notes_of(rb) == [] and sb.run.corpus_cur.adhesion["WORD"].counts == {}
    assert all(row["kind"] == "memory_answer" for row in sb.run.rows)
    assert rb["kind"] == "memory_answer"
    rv = sb.write("認証の前提は決済")
    rv2 = sb.write("決済の前提は認証")
    assert "REVERSAL" in notes_of(rv2)
    sa = session(tmp_path, "a")
    write_all(sa, ["会議は東京で行う", "研修は東京で行う"])
    assert sa.run.corpus_cur.adhesion["WORD"].counts[("東京", "で")] == 2 and all(row["kind"] == "base" for row in sa.run.rows)


def test_op_mem_1_c_counts_only_earlier_sessions_for_adhesion(tmp_path):
    sc = session(tmp_path, "c", kind_policy="c")
    write_all(sc, ["会議は東京で行う", "研修は東京で行う"])
    assert "NEW_RELATION" not in notes_of(sc.write(PROBE_NEW_RELATION))          # the session's own sentences give no adhesion
    st = new_store(tmp_path, "c2")
    s1 = st.begin("m", kind_policy="c")
    write_all(s1, ["会議は東京で行う", "研修は東京で行う"])
    s1.commit()
    s2 = st.begin("m")
    r = s2.write(PROBE_NEW_RELATION)
    assert "NEW_RELATION" in notes_of(r) and "UNANCHORED" in notes_of(r)         # earlier sessions do
    assert all(row["kind"] == "base" for row in s2.run.rows)
    s2.commit()
    assert st.verify()["status"] == "OK"                                  # and the policy replays


def test_origin_new_and_history_n_per_unit(tmp_path):
    s = session(tmp_path)
    s.write("認証の前提は決済")
    r = s.write("認証の期限は金曜")
    by = {u["surface"]: (u["origin"], u["history_n"]) for u in r["units"]}
    assert by == {"認証": ("record", 1), "期限": ("new", 0), "金曜": ("new", 0)}
    assert r["marked"] == "認証の【新:期限】は【新:金曜】"
    uid = next(u["uid"] for u in r["units"] if u["surface"] == "認証")
    assert s.run.state.units[uid].kind == "record" and s.run.state.units[uid].prov["origin"] == "record"      # `kind` stays record; `origin` is the extra field
    ev = s.events()
    assert ev["units"] == {"new": 5, "record": 1}


def test_conflict_arm_is_reported_only_when_the_write_touches_it(tmp_path):
    s = session(tmp_path)
    got = {}
    for x in ["東京の支店は新宿", "大阪の支店は梅田", "認証の期限は金曜", "決済の期限は月曜", "認証の前提は決済", "決済の前提は認証", "田中の担当は認証", "田中の担当は決済", "会議は東京で行う"]:
        got[x] = [n for n in s.write(x).get("notes", []) if n["type"] == "CONFLICT"]
    fired = {x: n[0]["centre"] for x, n in got.items() if n}
    assert fired == {"大阪の支店は梅田": "支店", "決済の期限は月曜": "期限", "決済の前提は認証": "前提"}        # Pr3: the three enumerations, never 担当
    assert all(n["counted"] is False for ns in got.values() for n in ns)             # OP-MEM-2 (a): a note, not a detection
    assert got["会議は東京で行う"] == [] and got["田中の担当は決済"] == []              # an unrelated write is silent although the thread still holds the conflicts
    n = got["決済の期限は月曜"][0]
    assert [v["cids"] for v in n["variants"]] == [["c5"], ["c7"]] or len(n["variants"]) == 2


def test_same_question_on_the_probe_examples(tmp_path):
    s = session(tmp_path, self_question=STUB)
    assert notes_of(s.write("田中の担当は認証")) == []
    r = s.write(PROBE_SQ)
    sq = _by_type(r, "SAME_QUESTION")
    assert len(sq) == 1 and sq[0]["counted"] is True and sq[0]["question"] == "田中の担当は何ですか"
    assert [v["answers"] for v in sq[0]["variants"]] == [["認証"], ["決済"]]
    assert [[o["sid"] for o in v["occurrences"]] for v in sq[0]["variants"]] == [[0], [1]]
    assert sq[0]["variants"][0]["occurrences"][0]["source"] == "mem:t/1#0"
    assert r["clause"]["question"] == "田中の担当は何ですか" and r["clause"]["answer"] == ["決済"] and r["clause"]["subject"] == ["田中", "担当"]
    s.write("サーバーのポートは8080")
    r2 = s.write("サーバーのポートは9090")
    sq2 = _by_type(r2, "SAME_QUESTION")
    assert len(sq2) == 1 and [v["answers"] for v in sq2[0]["variants"]] == [["8080"], ["9090"]]
    ev = s.events()
    assert ev["notes"]["SAME_QUESTION"] == 2 and ev["detections"] == {"notes": 2, "reseat_content": 0, "headline": 2}
    assert ev["counted"] == {"SAME_QUESTION": 2, "REVERSAL": 0}


def test_lists_and_repeats_are_not_contradictions(tmp_path):
    s = session(tmp_path, self_question=STUB)
    got = [notes_of(s.write(x)) for x in ["認証の期限は金曜", "決済の期限は月曜", "認証の前提は決済", "東京の支店は新宿", "大阪の支店は梅田", "認証の期限は金曜"]]
    assert all("SAME_QUESTION" not in n for n in got)                    # different X: different questions; the same fact twice is one answer
    assert "CONFLICT" in got[1] and "CONFLICT" in got[4]                 # the enumerations are noted (uncounted) and nothing more
    assert s.events()["detections"]["notes"] == 0


def test_same_question_hook_contract(tmp_path):
    calls = []

    def hook(question, mem_):
        calls.append((question, mem_.t, len(mem_.rows_before), len(mem_.rows_after), mem_.corpus_before.n_sentences, mem_.corpus_after.n_sentences))
        return []
    hook.id = "recording.v1"
    s = session(tmp_path, self_question=hook)
    r = s.write("田中の担当は認証")
    assert calls == [("田中の担当は何ですか", 0, 0, 1, 0, 1)]
    assert [n["type"] for n in r["notes"]] == ["SELF_QUESTION_UNREADABLE"] and r["notes"][0]["counted"] is False        # the hook could not read sentence t
    s.write("会議は東京で行う")                                           # a clause 「会議は」 asks 「会議は何ですか」 too (no X)
    assert [c[0] for c in calls] == ["田中の担当は何ですか", "会議は何ですか"]
    s.write("fmt_numの戻り値は文字列")
    assert calls[-1][1] == 2 and calls[-1][2] == 2 and calls[-1][3] == 3
    s.write("赤色 青色")                                                   # no clause: the hook is not called
    n = len(calls)
    s.write("東京の天気")
    assert len(calls) == n
    assert s.events()["cost"]["unreadable"] == 3 and s.events()["detections"]["headline"] == 0
    assert s.run.hook_id == "recording.v1" and ledger_rows(s)[0]["result"]["header"]["self_question"] == "recording.v1"
    with pytest.raises(ValueError):
        mn.hook_id(lambda q, m: [])                                       # a hook without an id cannot be recorded
    with pytest.raises(ValueError):
        class Bad:
            id = "none"
        mn.hook_id(Bad())


def test_no_clause_no_question_when_the_topic_holds_another_arm(tmp_path):
    seen = []

    def hook(q, m):
        seen.append(q)
        return []
    hook.id = "h"
    s = session(tmp_path, self_question=hook)
    s.write("東京で会議は成功")                                             # T = [会議 topic with 東京 on で]: not a clause 「[X の] Y は A」
    s.write("認証の前提は決済")
    assert seen == ["認証の前提は何ですか"]


def test_answer_groups_one_sentence_one_statement():
    A = mn.Answer
    # T-MEM-20..25 without the gate: a sentence that passes nested stretches is ONE statement
    sets, comps = mn.answer_groups([A(0, "K3", (0, 0)), A(0, "K3の修正", (0, 1))])
    assert sets == {0: {"k3の修正": "K3の修正"}} and comps == [[0]]
    assert mn.same_question_note("q", [A(0, "K3", (0, 0)), A(0, "K3の修正", (0, 1))], 0, [{"source": "s0"}], "c1") is None      # ANSWER, never CHOICE
    rows = [{"source": "mem:t/1#0"}, {"source": "mem:t/1#1"}, {"source": "mem:t/1#2"}]
    # with 「今日の作業はK3のテスト」 as well: K3の修正 vs K3のテスト is a CHOICE
    n = mn.same_question_note("q", [A(0, "K3", (0, 0)), A(0, "K3の修正", (0, 1)), A(1, "K3", (0, 0)), A(1, "K3のテスト", (0, 1))], 1, rows, "c1")
    assert n["type"] == "SAME_QUESTION" or n is None
    # the maximal answers K3の修正 / K3のテスト do not intersect: CHOICE
    assert n is not None and [v["answers"] for v in n["variants"]] == [["K3の修正"], ["K3のテスト"]]
    # written twice: still ANSWER
    assert mn.same_question_note("q", [A(0, "K3の修正", (0, 1)), A(1, "K3の修正", (0, 1))], 1, rows, "c1") is None
    # 「K3」 alone from one sentence and 「K3の修正」 from another: a refinement is shown, never hidden
    n2 = mn.same_question_note("q", [A(0, "K3"), A(1, "K3の修正")], 1, rows, "c1")
    assert n2["type"] == "SAME_QUESTION" and [v["answers"] for v in n2["variants"]] == [["K3"], ["K3の修正"]]
    # agreement is transitive through the components (union-find in sid order): {a,b} {b,c} {d} -> two components
    sets, comps = mn.answer_groups([A(0, "a"), A(0, "b"), A(1, "b"), A(1, "c"), A(2, "d")])
    assert comps == [[0, 1], [2]]
    # occurrences are in sid order whatever the order of the answers
    n3 = mn.same_question_note("q", [A(2, "x"), A(0, "y"), A(1, "y")], 2, rows, "c1")
    assert [[o["sid"] for o in v["occurrences"]] for v in n3["variants"]] == [[0, 1], [2]]
    # the sentence itself unreadable
    assert mn.same_question_note("q", [A(0, "y")], 1, rows, "c1")["type"] == "SELF_QUESTION_UNREADABLE"
    # full-width / case / spaces are one answer
    assert mn.same_question_note("q", [A(0, "ＡＢＣ"), A(1, "abc ")], 1, rows, "c1") is None


def test_op_mem_2_switch(tmp_path):
    calls = []

    def hook(q, m):
        calls.append(q)
        return STUB(q, m)
    hook.id = "stub.v1"
    for pol, expect_sq, expect_conflict_counted in (("a", True, False), ("b", False, True), ("c", True, True)):
        calls.clear()
        s = session(tmp_path, "p" + pol, contradiction_policy=pol, self_question=hook)
        s.write("田中の担当は認証")
        r = s.write("田中の担当は決済")
        assert ("SAME_QUESTION" in notes_of(r)) is expect_sq
        assert bool(calls) is (pol != "b")                                # (b): no new reading, the hook is not even asked
        r2 = s.write("鈴木の担当は決済")
        s.write("認証の期限は金曜")
        r3 = s.write("決済の期限は月曜")
        c = _by_type(r3, "CONFLICT")
        assert c and c[0]["counted"] is expect_conflict_counted
        counted = s.events()["counted"]
        assert ("CONFLICT" in counted) is (pol != "a") and ("SAME_QUESTION" in counted) is (pol != "b")
        s.commit()
        assert s.store.verify(hook)["status"] == "OK"


def test_reseat_content_after_a_same_question_note(tmp_path):
    s = session(tmp_path, self_question=STUB)
    write_all(s, ["田中の担当は認証"])
    r = s.write("田中の担当は決済")
    assert "SAME_QUESTION" in notes_of(r)
    s.call("status", {})
    r2 = s.write("田中の担当は認証と決済")                                  # the model rephrases within 3 ops: another answer unit set for the same question
    assert r2["ok"] and r2["clause"]["answer"] == ["認証", "決済"]
    ev = s.events()
    assert [(x["trigger"], x["kind"]) for x in ev["reseats"]] == [("SAME_QUESTION", "content")]
    assert ev["detections"] == {"notes": 1 + 0, "reseat_content": 1, "headline": 2} or ev["detections"]["reseat_content"] == 1
    assert ev["cost"]["reseat_shape"] == 0


def test_reseat_content_after_a_reversal(tmp_path):
    s = session(tmp_path)
    s.write("認証の前提は決済")
    r = s.write("決済の前提は認証")
    assert "REVERSAL" in notes_of(r)
    r2 = s.write("前提の決済は認証")                                       # the pair 決済 / 前提 now in the order the history holds
    assert r2["ok"]
    ev = s.events()
    assert [(x["trigger"], x["kind"]) for x in ev["reseats"]] == [("REVERSAL", "content")]
    s2 = session(tmp_path, "m2")
    s2.write("認証の前提は決済")
    s2.write("決済の前提は認証")
    s2.write("決済の前提は認証と決済")                                       # keeps the flagged order: a rephrase, not a change of the pair order
    assert [(x["trigger"], x["kind"]) for x in s2.events()["reseats"]] == [("REVERSAL", "shape")]


def test_reseat_shape_after_a_refused_sentence_is_cost_not_detection(tmp_path):
    s = session(tmp_path, self_question=STUB)
    assert s.write(PROBE_SHAPE)["refusal"] == "span_inexpressible"
    assert s.write("東京の会議は成功")["ok"]                                # the same words, a shape the structure can seat
    ev = s.events()
    assert [(x["trigger"], x["kind"]) for x in ev["reseats"]] == [("span_inexpressible", "shape")]
    assert ev["unseatable"]["total"] == 1 and ev["cost"] == {"unseatable": 1, "reseat_shape": 1, "unreadable": 0}
    assert ev["detections"] == {"notes": 0, "reseat_content": 0, "headline": 0}          # OP-MEM-3 (a): nothing structural was detected
    s.run.unseatable_policy = "b"
    assert s.events()["detections"]["headline"] == 1                     # OP-MEM-3 (b): the literal reading counts every refused-then-rephrased write


def test_reseat_window_overlap_and_repeats(tmp_path):
    s = session(tmp_path)
    s.write(PROBE_SHAPE)
    for _ in range(3):
        s.call("status", {})                                             # 3 model ops pass
    s.write("東京の会議は成功")                                             # the 4th model op: outside the window
    assert s.events()["reseats"] == []
    s2 = session(tmp_path, "m2")
    s2.write(PROBE_SHAPE)
    s2.write("赤色の備品は多い")                                             # no shared unit of 2+ characters
    s2.write("東京の天気は晴れ")                                             # shares 東京
    assert [x["kind"] for x in s2.events()["reseats"]] == ["shape"] and s2.events()["reseats"][0]["to_i"] == 3
    s3 = session(tmp_path, "m3")
    s3.write(PROBE_SHAPE)
    s3.write(PROBE_SHAPE)                                                # the same refused text again: nothing was rephrased
    assert s3.events()["reseats"] == []


def test_events_are_read_from_the_ledger_only(tmp_path):
    s = session(tmp_path, self_question=STUB)
    write_all(s, ["田中の担当は認証", "田中の担当は決済", PROBE_SHAPE, "東京の会議は成功"])
    rows = ledger_rows(s)
    a = mn.session_events(rows, "a", "a")
    assert a == s.events()
    assert mn.session_events(rows, "b", "b")["counted"] == {"CONFLICT": 0, "REVERSAL": 0}
    assert json.loads(json.dumps(a)) == a                                 # plain JSON-able


def _fire(sess, probes):
    out = {}
    for name, text in probes:
        r = sess.write(text)
        out[name] = sorted(set(notes_of(r))) if r.get("ok") else ["REFUSED:" + r["refusal"] + "/" + r["detail"].get("reason", "")]
    return out


PROBES = [("shape", PROBE_SHAPE), ("reversal", PROBE_REVERSAL), ("same_question", PROBE_SQ), ("new_relation", PROBE_NEW_RELATION),
          ("conflict_arm", "決済の期限は月曜")]


def _grow(tmp_path, name, n_filler, with_second_tokyo):
    st = new_store(tmp_path, name)
    seeds = SEEDS + ["認証の期限は金曜"] + ([SECOND_TOKYO] if with_second_tokyo else [])
    batch = [seeds] + [filler(n_filler)[j:j + 55] for j in range(0, n_filler, 55)]
    for sents in batch:
        s = st.begin("m", self_question=STUB)
        for x in sents:
            assert s.write(x)["ok"], x
        s.commit()
    return st


@pytest.fixture(scope="module")
def firing(tmp_path_factory):
    base = tmp_path_factory.mktemp("firing")
    table = {}
    # 0 units: an empty store; every probe is the first thing the memory hears (a new store each, M0 each time)
    table[0] = {}
    for k, (name, text) in enumerate(PROBES):
        s = new_store(base, "z%d" % k).begin("m", self_question=STUB)
        table[0].update(_fire(s, [(name, text)]))
    units = {}
    for size, n_fill, second in ((10, 0, False), (100, 30, True), (1000, 335, True)):
        st = _grow(base, "g%d" % size, n_fill, second)
        s = st.begin("m", self_question=STUB)
        units[size] = len(s.run.state.units)
        table[size] = _fire(s, PROBES)
        s.commit()
        assert st.verify(STUB)["status"] == "OK"
    return table, units


def test_what_fires_at_0_10_100_1000_units(firing):
    table, units = firing
    assert 8 <= units[10] <= 13 and 100 <= units[100] < 130 and 1000 <= units[1000] < 1040          # the memories hold the sizes they are named for
    # (a) shape: fires with no data at all, at every size
    for size in (0, 10, 100, 1000):
        assert table[size]["shape"] == ["REFUSED:span_inexpressible/nested_particle_chain"]
    # (b) REVERSAL: never on the empty history, fires at 10 on a pair written once before in the other order (O: Pr3), and stays
    assert table[0]["reversal"] == []
    for size in (10, 100, 1000):
        assert "REVERSAL" in table[size]["reversal"]
    # (c) SAME_QUESTION: never on the empty history; fires at 10 on the second contradicting clause (O: Pr4), and stays
    assert table[0]["same_question"] == []
    for size in (10, 100, 1000):
        assert "SAME_QUESTION" in table[size]["same_question"]
    # (b) NEW_RELATION: never at 0; at 10 (one 東京で) and later it is information (not counted); UNANCHORED needs two sentences: absent at 10, present once there are 2
    assert table[0]["new_relation"] == []
    assert table[10]["new_relation"] == ["NEW_RELATION"]
    for size in (100, 1000):
        assert table[size]["new_relation"] == ["NEW_RELATION", "UNANCHORED"]
    # (c) CONFLICT/arm: within one write only on the empty history, i.e. never; fires from 10 on (the enumeration 認証/決済 の期限)
    assert table[0]["conflict_arm"] == []
    for size in (10, 100, 1000):
        assert "CONFLICT" in table[size]["conflict_arm"]


def test_the_firing_table_is_reported(firing, capsys):
    table, units = firing
    with capsys.disabled():
        print("\nMEM firing table (probe -> note types; units seated before the probes: %s)" % units)
        for name, _ in PROBES:
            print("  %-14s" % name + "  ".join("%4d: %s" % (size, ",".join(table[size][name]) or "-") for size in (0, 10, 100, 1000)))
