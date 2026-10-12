"""MEM-d tests: the harness entry points (`experiments/line3/loom/mem_run.py`), the toy task, the four arms end to end with a recorded client, determinism, the old stores.
No network: `driver.ReplayClient` plays a recorded script; nothing here calls an API."""
import gzip
import hashlib
import json
import os
import subprocess
import sys

import pytest

from verantyx.loom import driver as drv
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem
from mem_common import ROOT
import mem_run_loader

mr = mem_run_loader.load()
PY = sys.executable
T = lambda name, **a: ("tool", name, a)
TOY = os.path.join(ROOT, "experiments", "line3", "loom", "mem_toy.jsonl")


def toy():
    return mr.find_task("MEM-TOY1", TOY)


def structure_script(order):
    """The recorded turns of a structure arm on the toy task (what a careful model would do), questions in `order`."""
    S = [
        [T("declare_topic", text="リリース準備"), T("write", text="認証の担当は田中"), T("report", contradictions=[])],
        [T("write", text="認証の期限は金曜"), T("report", contradictions=[])],
        [T("write", text="決済の期限は月曜"), T("report", contradictions=[])],
        [T("write", text="サーバーのポートは8080"), T("report", contradictions=[])],
        [T("write", text="認証の前提は決済"), T("report", contradictions=[])],
        [T("declare_topic", text="リリース準備"), T("write", text="認証の担当は佐藤"), T("report", contradictions=[["1-1", "2-1"]])],
        [T("recall", question="サーバーのポートは何ですか"), T("report", contradictions=[])],
        [T("write", text="決済の前提は認証"), T("report", contradictions=[["1-5", "2-3"]])],
        [T("write", text="会場は東京"), T("report", contradictions=[])],
        [T("declare_topic", text="リリース準備"), T("write", text="サーバーのポートは9090"), T("supersede", new_sid=8, old_sid=3, reason="変更"), T("report", contradictions=[])],
        [T("write", text="決済の担当は鈴木"), T("report", contradictions=[])],
        [T("report", contradictions=[])],
    ]
    Q = {0: [[T("recall", question="認証の担当は何ですか")], [T("abstain", type="contested")]],
         1: [[T("recall", question="サーバーのポートは何ですか")], [T("weave_span", sid=8, tier="WORD", first="9090", last="9090")], [T("emit")]],
         2: [[T("recall", question="認証の期限は何ですか")], [T("weave_span", sid=1, tier="WORD", first="金曜", last="金曜")], [T("emit")]],
         3: [[T("recall", question="決済の担当は何ですか")], [T("weave_span", sid=9, tier="WORD", first="鈴木", last="鈴木")], [T("emit")]]}
    return S + [t for k in order for t in Q[k]]


def baseline_script(arm, order):
    rep = lambda p=(): T("report", contradictions=[list(x) for x in p])
    S = []
    for s_, n in enumerate((5, 4, 3)):
        for i in range(n):
            calls = [T("log_append", text="%d-%d メモ" % (s_ + 1, i + 1))] if arm == "log" else []
            S.append(calls + [rep([["1-1", "2-1"]] if (s_, i) == (1, 0) else ())])
    ans = {0: ("contested", ["田中", "佐藤"]), 1: ("value", ["9090"]), 2: ("value", ["金曜"]), 3: ("none", [])}
    Q = []
    for k in order:
        kind, vals = ans[k]
        Q += ([[T("log_read", grep="")]] if arm == "log" else []) + [[T("answer", kind=kind, values=vals)]]
    return S + Q


def run(tmp_path, arm, repeat=1, script=None, name="out"):
    order = mr.question_order("MEM-TOY1", repeat, 4)
    script = script or (structure_script(order) if arm in md.STRUCTURE_ARMS else baseline_script(arm, order))
    return mr.run_one(toy(), arm, repeat, client=drv.ReplayClient(script), model="fake-model", out_root=str(tmp_path / name)), str(tmp_path / name)


# -- the bank ----------------------------------------------------------------------------------------------------------------------------------
def test_the_toy_task_has_the_bank5_schema():
    t = toy()
    assert t["id"] == "MEM-TOY1" and [len(s) for s in t["sessions"]] == [5, 4, 3] and len(t["plants"]) == 5 and len(t["questions"]) == 4
    assert [p["kind"] for p in t["plants"]] == ["contradiction", "update", "list_trap", "repeat", "reversal"]
    assert [q["kind"] for q in t["questions"]] == ["contradicted", "updated", "plain", "plain"]
    assert mr.bank_problems(t) == []
    raw = json.loads(open(TOY, encoding="utf-8").readline())
    assert set(raw) == {"id", "title", "sessions", "plants", "questions"} and set(raw["plants"][0]) == {"kind", "fact", "values", "message_refs", "note"}
    assert set(raw["questions"][0]) == {"q", "gold", "kind", "refs"} and set(raw["sessions"][0][0]) == {"speaker", "text"}


def test_bank5_normalisation_and_problems(tmp_path):
    raw = json.loads(open(TOY, encoding="utf-8").readline())
    # refs are 0-based in the audited bank; a bank whose refs are all 1-based is detected from the values and shifted
    one = json.loads(json.dumps(raw))
    for p in one["plants"]:
        p["message_refs"] = [[s + 1, i + 1] for s, i in p["message_refs"]]
    assert mr.normalize_task(one)["plants"] == mr.normalize_task(raw)["plants"]
    bad = json.loads(json.dumps(raw))
    bad["plants"][0]["message_refs"] = [[0, 0], [2, 2]]
    with pytest.raises(mr.MemRunError) as e:
        mr.normalize_task(bad)
    assert e.value.code == "bad_refs"
    for broken in ({"id": ""}, dict(raw, sessions=[]), dict(raw, sessions=[[{"speaker": "a"}]]), dict(raw, questions=[{"q": "x"}]), dict(raw, plants=[{"values": "x", "message_refs": []}])):
        with pytest.raises(mr.MemRunError) as e2:
            mr.normalize_task(broken)
        assert e2.value.code == "bad_task"
    # kinds of the audited bank (question kinds contradiction | update | plain) are canonicalised
    assert [mr.canon_question_kind(k) for k in ("contradiction", "contradicted", "update", "updated", "plain")] == ["contradicted", "contradicted", "updated", "updated", "plain"]
    # the audited shape (3 sessions, 10 questions, 6/3/4/2/2 plants, 4/3/3 question kinds) is checked by `bank_problems(task, BANK5_SHAPE)`
    assert any("4 questions, want 10" in x for x in mr.bank_problems(toy(), mr.BANK5_SHAPE)) and any("plant kinds" in x for x in mr.bank_problems(toy(), mr.BANK5_SHAPE))
    t = json.loads(json.dumps(toy()))
    t["questions"][0]["gold"] = "田中"
    assert any("not 「矛盾" in x for x in mr.bank_problems(t))
    t["questions"][0]["gold"] = "矛盾: 田中 と 佐藤"
    t["questions"][2]["gold"] = "矛盾: a と b"
    assert any("has a contradiction gold" in x for x in mr.bank_problems(t))
    p = tmp_path / "dup.jsonl"
    p.write_text(open(TOY, encoding="utf-8").read() * 2, encoding="utf-8")
    with pytest.raises(mr.MemRunError):
        mr.load_tasks(str(p))


def test_the_audited_bank5_is_the_default_bank_when_it_exists_and_validates_against_its_shape(monkeypatch):
    """The audited bank5 (experiments/line3/bank5/bank5.jsonl, on line3; this worktree gets it with the merge) is searched first, the toy task after it; with the file present every
    task must meet the audited shape (3 sessions, 10 questions, 6/3/4/2/2 plants, 4/3/3 question kinds)."""
    monkeypatch.delenv("MEM_BANK", raising=False)
    assert mr.bank_paths(None) == ([mr.BANK5] if os.path.isfile(mr.BANK5) else []) + [mr.TOY_BANK] and mr.bank_paths("x.jsonl") == ["x.jsonl"]
    if os.path.isfile(mr.BANK5):
        ts = mr.load_tasks(mr.BANK5)
        assert sorted(ts) == ["MEM-T0%d" % k for k in range(1, 7)]
        for t in ts.values():
            assert mr.bank_problems(t, mr.BANK5_SHAPE) == [], t["id"]
    assert mr.find_task("MEM-TOY1")["id"] == "MEM-TOY1"


def test_question_order_is_shuffled_deterministically_and_is_the_same_for_every_arm():
    a = mr.question_order("MEM-T01", 1, 10)
    assert sorted(a) == list(range(10)) and a == mr.question_order("MEM-T01", 1, 10) and a != list(range(10))
    assert a != mr.question_order("MEM-T01", 2, 10) and a != mr.question_order("MEM-T02", 1, 10)


def test_gold_reading_and_hits():
    assert mr.gold_values("矛盾: 田中 と 佐藤") == ("contested", ["田中", "佐藤"]) and mr.gold_values("9090") == ("value", ["9090"])
    q = {"gold": "矛盾: 田中 と 佐藤"}
    assert mr.answer_hit({"kind": "contested", "values": ["佐藤", "田中"]}, q) is True and mr.answer_hit({"kind": "value", "values": ["田中"]}, q) is False
    assert mr.answer_hit({"kind": "contested", "values": ["田中", "鈴木"]}, q) is False and mr.answer_hit({"kind": "none", "values": []}, q) is None
    assert mr.answer_hit({"kind": "contested", "values": ["8080", "9090"]}, {"gold": "9090"}) is False        # an update answered with 矛盾 is wrong
    assert mr.answer_hit({"kind": "value", "values": [" 9090 "]}, {"gold": "9090"}) is True


def test_noticed_and_false_pairs_are_lookups():
    t = toy()
    nt = mr.plants_noticed(t, [["1-1", "2-1"], ["1-4", "3-1"], ["1-2", "1-3"]])
    assert [(n["kind"], n["noticed"]) for n in nt] == [("contradiction", True), ("update", True), ("list_trap", True), ("repeat", False), ("reversal", False)]
    assert mr.false_pairs(t, [["1-1", "2-1"], ["1-4", "3-1"], ["1-2", "1-3"], ["1-5", "2-3"]]) == [["1-4", "3-1"], ["1-2", "1-3"]]       # an update, a list trap: false alarms


# -- the plan ------------------------------------------------------------------------------------------------------------------------------
def test_prepare_lists_the_tools_of_each_arm(tmp_path):
    for arm in md.ARMS:
        p = mr.prepare(toy(), arm, "claude-haiku-5-5", str(tmp_path))
        assert p["story"]["tools"] == [mr.TOOL_PREFIX + n for n in md.STORY_TOOLS[arm]] and p["question"]["tools"] == [mr.TOOL_PREFIX + n for n in md.QUESTION_TOOLS[arm]]
        assert p["arm_label"] == md.ARM_LABEL[arm] and p["sessions"] == [5, 4, 3] and "--repeat 1" in p["command"] and not os.path.exists(p["run_dir"])
    assert mr.prepare(toy(), "notes", "m", "o")["story"]["agent"] == "mem-writer" and mr.prepare(toy(), "blind", "m", "o")["question"]["agent"] == "mem-answer"


# -- the arms, end to end ----------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("arm", ["notes", "blind"])
def test_a_structure_arm_runs_the_toy_task_and_every_ledger_verifies(tmp_path, arm):
    r, out = run(tmp_path, arm)
    assert r["ended"] == "story_complete" and r["store"] == {"verify": "OK", "sentences": 10, "sessions": 3}
    assert [a["hit"] for a in sorted(r["answers"], key=lambda a: a["index"])] == [True, True, True, True]
    assert [a["index"] for a in r["answers"]] == mr.question_order("MEM-TOY1", 1, 4) == r["question_order"]
    assert [(n["kind"], n["noticed"]) for n in r["noticed"]] == [("contradiction", True), ("update", False), ("list_trap", False), ("repeat", False), ("reversal", True)]
    assert r["false_pairs"] == [] and r["reports"]["pairs"] == [["1-1", "2-1"], ["1-5", "2-3"]]
    ev = [s["events"] for s in r["sessions"]]
    assert [e["detections"]["notes"] for e in ev] == [0, 2, 1] and ev[2]["supersedes"] == {"ok": 1, "sentences": 1, "refused": {}} and ev[1]["topics"]["expanded"] == 1
    assert r["snapshot"]["superseded"] == 1 and r["cost"]["turns_without_report"] == 0 and r["cost"]["api_calls"] == 12 + len(structure_script(r["question_order"])) - 12
    sc = mr.score_run(os.path.join(out, "MEM-TOY1", arm, "r01"), toy())
    assert sc["verified"] is True and sc["noticed"] == 2 and sc["planted"] == 2 and sc["answers"] == {"hit": 4, "miss": 0, "none": 0, "n": 4}
    assert set(sc["checks"]) == {"store", "a0001", "a0002", "a0003", "a0004"}
    assert r["tools"]["story"] == list(md.STORY_TOOLS[arm]) and r["tools"]["question"] == list(md.QUESTION_TOOLS[arm])


def test_the_two_structure_arms_leave_the_same_bytes_on_the_same_script(tmp_path):
    ra, oa = run(tmp_path, "notes", name="a")
    rb, ob = run(tmp_path, "blind", name="b")
    for k in ("s0001", "s0002", "s0003"):
        assert open(os.path.join(oa, "MEM-TOY1", "notes", "r01", "store", "sessions", k, "ops.jsonl"), "rb").read() == \
            open(os.path.join(ob, "MEM-TOY1", "blind", "r01", "store", "sessions", k, "ops.jsonl"), "rb").read()
    assert ra["system_prompt_sha256"] != rb["system_prompt_sha256"] and ra["sessions"][1]["events"] == rb["sessions"][1]["events"]


@pytest.mark.parametrize("arm", ["context", "log"])
def test_a_baseline_arm_runs_the_toy_task_and_every_ledger_verifies(tmp_path, arm):
    r, out = run(tmp_path, arm)
    assert r["ended"] == "story_complete" and "store" not in r and "snapshot" not in r
    by_index = {a["index"]: a for a in r["answers"]}
    assert by_index[0]["hit"] is True and by_index[1]["hit"] is True and by_index[2]["hit"] is True and by_index[3]["hit"] is None
    assert r["reports"]["pairs"] == [["1-1", "2-1"]] and r["tools"]["story"] == list(md.STORY_TOOLS[arm])
    sc = mr.score_run(os.path.join(out, "MEM-TOY1", arm, "r01"), toy())
    assert sc["verified"] is True and sc["answers"] == {"hit": 3, "miss": 0, "none": 1, "n": 4}
    if arm == "log":
        assert open(os.path.join(out, "MEM-TOY1", "log", "r01", "store", "log.txt"), encoding="utf-8").read().count("\n") == 12


def test_a_run_never_overwrites_a_folder(tmp_path):
    run(tmp_path, "context")
    with pytest.raises(mr.MemRunError) as e:
        run(tmp_path, "context")
    assert e.value.code == "run_exists"


def test_an_api_error_in_the_story_ends_the_run_without_questions(tmp_path):
    class Boom:
        class messages:
            @staticmethod
            def create(**kw):
                raise RuntimeError("x")
    r = mr.run_one(toy(), "notes", 1, client=Boom(), model="m", out_root=str(tmp_path / "o"))
    assert r["ended"] == "story_api_error" and r["answers"] == [] and r["sessions"][0]["committed"] is False and len(r["sessions"]) == 1
    assert mem.verify_store(os.path.join(str(tmp_path), "o", "MEM-TOY1", "notes", "r01", "store"), mem.FROM_HEADER)["status"] == "EMPTY"       # an abandoned session is not memory


def test_the_questions_arrive_in_the_shuffled_order_in_a_fresh_conversation_each(tmp_path):
    seen = []

    class Rec(drv.ReplayClient):
        def _create(self, **kw):
            seen.append(json.dumps(kw["messages"], ensure_ascii=False, default=str))
            return super()._create(**kw)
    order = mr.question_order("MEM-TOY1", 2, 4)
    mr.run_one(toy(), "context", 2, client=Rec(baseline_script("context", order)), model="m", out_root=str(tmp_path / "o"))
    qs = [m for m in seen if "This is the result of begin" in m]
    assert len(qs) == 4
    texts = [toy()["questions"][k]["q"] for k in order]
    assert [next(t for t in texts if t in m) for m in qs] == texts
    assert all(m.count('"role": "user"') == 1 for m in qs)                          # one user message: nothing of the story is in a question conversation


# -- determinism and replay -------------------------------------------------------------------------------------------------------------
def _digest(root):
    h = hashlib.sha256()
    for dp, dn, fn in sorted(os.walk(root)):
        dn.sort()
        for f in sorted(fn):
            if f in ("timing.jsonl", ".lock") or f.startswith("."):
                continue
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, root).encode())
            data = open(p, "rb").read()
            if f == "result.json":
                o = json.loads(data)
                o.pop("wall")
                data = json.dumps(o, sort_keys=True, ensure_ascii=False).encode()
            h.update(data)
    return h.hexdigest()


def test_the_same_script_twice_gives_the_same_bytes(tmp_path):
    for arm in ("notes", "log"):
        run(tmp_path, arm, name="a")
        run(tmp_path, arm, name="b")
        assert _digest(str(tmp_path / "a" / "MEM-TOY1" / arm)) == _digest(str(tmp_path / "b" / "MEM-TOY1" / arm))


def test_the_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    code = ("import sys, hashlib; sys.path.insert(0, %r); sys.path.insert(0, %r)\n"
            "import test_mem_run as t, tempfile, pathlib\n"
            "d = pathlib.Path(tempfile.mkdtemp(dir=%r)); t.run(d, 'notes')\n"
            "print(t._digest(str(d / 'out' / 'MEM-TOY1' / 'notes')))\n") % (ROOT, os.path.join(ROOT, "tests", "line3"), str(tmp_path))
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        outs.append(subprocess.run([PY, "-c", code], env=env, capture_output=True, text=True, timeout=600, cwd=ROOT).stdout.strip())
    assert len(outs[0]) == 64 and outs[0] == outs[1] == outs[2]


def test_a_tampered_answer_ledger_fails_the_scoring_check(tmp_path):
    r, out = run(tmp_path, "notes")
    d = os.path.join(out, "MEM-TOY1", "notes", "r01")
    p = os.path.join(d, "store", "answers", "a0001", "ops.jsonl")
    data = open(p, "rb").read()
    open(p, "wb").write(data.replace(b'"verdict"', b'"verdicT"', 1))
    sc = mr.score_run(d, toy())
    assert sc["verified"] is False and sc["checks"]["a0001"] == "TAMPERED"


# -- the CLI ----------------------------------------------------------------------------------------------------------------------------------
def test_cli_list_prepare_replay_and_score(tmp_path, capsys):
    assert mr.main(["--list", "--bank", TOY]) == 0 and "MEM-TOY1" in capsys.readouterr().out
    assert mr.main(["--validate", "--bank", TOY]) == 0 and "ok" in capsys.readouterr().out
    assert mr.main(["--prepare", "--bank", TOY, "--task", "MEM-TOY1", "--arm", "log", "--out", str(tmp_path)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["story"]["tools"] == [mr.TOOL_PREFIX + n for n in ("log_append", "log_read", "report")]
    script = tmp_path / "script.json"
    script.write_text(json.dumps([[list(b) for b in t] for t in baseline_script("context", mr.question_order("MEM-TOY1", 1, 4))]), encoding="utf-8")
    assert mr.main(["--bank", TOY, "--task", "MEM-TOY1", "--arm", "context", "--repeat", "1", "--driver", "replay", "--script", str(script), "--out", str(tmp_path / "o")]) == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("MEM-TOY1 A0 r01 story_complete noticed=1/2")
    assert mr.main(["--bank", TOY, "--score", str(tmp_path / "o" / "MEM-TOY1" / "context" / "r01"), "--task", "MEM-TOY1"]) == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
    assert mr.main(["--bank", TOY, "--task", "MEM-TOY1", "--arm", "context", "--driver", "replay", "--script", str(script), "--out", str(tmp_path / "o")]) == 2        # exists
    assert mr.main(["--bank", TOY, "--task", "MEM-TOY1", "--arm", "context", "--out", str(tmp_path / "o2")]) == 2                  # no --driver: nothing is run, no client is built
    assert "no_driver" in capsys.readouterr().err and not (tmp_path / "o2").exists()
    assert mr.main(["--bank", TOY, "--task", "NOPE", "--arm", "context", "--prepare"]) == 2
    assert mr.main(["--bank", TOY, "--arm", "context"]) == 2


# -- old stores ---------------------------------------------------------------------------------------------------------------------------------
def unpack_old(tmp_path):
    g = json.load(gzip.open(os.path.join(ROOT, "tests", "line3", "golden_mem_store_pre_memd.json.gz"), "rt", encoding="utf-8"))
    root = tmp_path / "old"
    for rel, text in g["files"].items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return str(root)


def test_a_store_written_before_memd_replays_identical_under_its_recorded_hook_and_rules(tmp_path):
    """The golden store was written by wt/line3 cb1420cb (3 sessions, 12 sentences, recalls, notes, a frozen-op refusal), before any of MEM-d."""
    root = unpack_old(tmp_path)
    v = mem.verify_store(root, mem.FROM_HEADER)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and (v["sessions"], v["sentences"]) == (3, 12)
    assert mem.verify_store(root)["status"] == "OK"                                               # the default hook of that code is the default hook now
    head = mem.MemStore(root).head()
    assert all("mem_profile" not in json.loads(open(os.path.join(root, "sessions", e["run_id"], "ops.jsonl"), encoding="utf-8").readline())["result"]["header"] for e in head["sessions"])


def test_a_v2_session_can_be_added_to_an_old_store_and_the_whole_replays(tmp_path):
    root = unpack_old(tmp_path)
    st = mem.MemStore(root)
    s = st.begin("m", profile=mem.PROFILE_V2)
    s.call("declare_topic", {"text": "リリース準備"})
    s.write("締め切りは水曜")
    assert s.call("supersede", {"new_sid": 4, "old_sid": 0, "reason": "変更"})["ok"]            # sid 4 田中の担当は決済 (session 2) replaces the group of sid 0 田中の担当は認証 (sessions 1 and 3)
    s.commit()
    v = mem.verify_store(root, mem.FROM_HEADER)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL" and v["sessions"] == 4
    snap = ma.write_snapshot(root)
    assert snap["superseded"] == 2
    a = ma.AnswerSession(root, "田中の担当は何ですか", "m", snapshot=snap)
    r = a.call("recall", {"question": "田中の担当は何ですか"})
    assert r["history"] and r["history"][0]["occurrences"][0]["sid"] == 0
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK"
    s2 = st.begin("m")                                                                              # the API default is still mem.v1
    assert s2.run.profile == mem.PROFILE_V1 and s2.run.superseded            # ... and it knows what the store's ledgers superseded
    s2.commit()
    assert mem.verify_store(root, mem.FROM_HEADER)["status"] == "OK"


def test_the_pre_memd_default_session_bytes_are_unchanged(tmp_path):
    """A v1 session written now equals the bytes the golden store holds for the same calls (the first session of mk_old_store: writes, two recalls, status, lookup, a frozen op)."""
    root = unpack_old(tmp_path)
    new = tmp_path / "new"
    s = mem.MemStore(str(new), "old").begin("m-old")
    for t in ["田中の担当は認証", "認証の期限は金曜", "東京で会議を開く", "認証の前提は決済", "fmt_numの戻り値は文字列"]:
        s.write(t)
    s.call("recall", {"question": "田中の担当は何ですか"})
    s.call("recall", {"question": "サーバーのポートは何ですか"})
    s.call("status", {})
    s.call("lookup", {"text": "田中", "tier": "WORD"})
    s.call("unseat", {"cid": "c1", "seat": "centre"})
    s.commit()
    assert open(new / "sessions" / "s0001" / "ops.jsonl", "rb").read() == open(os.path.join(root, "sessions", "s0001", "ops.jsonl"), "rb").read()
    assert open(new / "memory.jsonl", "rb").read().startswith(b"")
