"""W8-shadow: 影運用の道具（tools/ops/*）のテスト。

全部 tmp_path の中で行い、ops/ の実物には書かない。道具は subprocess で既定の入口として起動する。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

W = Path(__file__).resolve().parents[1]
PY = sys.executable
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")
HIDDEN = "/Users/motonisihikoudai/Projects/vera-impl/hidden"
TASK_REVIEW = {"jobs": [{"job": "review", "task": {"role": "review", "kind": "review", "size": "medium"}}],
               "author": "test"}


def need_r8():
    if not (R8 / "manifest.json").is_file():
        pytest.skip(f"ENV_MISSING[r8_placement]: {R8}")


def env_for(extra=None):
    e = dict(os.environ)
    e.pop("VERA_SOVEREIGN_ROOT", None)
    e.pop("VERA_SOVEREIGN_STORE", None)
    e["PYTHONPATH"] = str(W)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(extra or {})
    return e


def tool(name, args, cwd, extra_env=None):
    p = subprocess.run([PY, str(W / "tools" / "ops" / f"{name}.py"), *map(str, args)], cwd=str(cwd),
                       env=env_for(extra_env), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def jlast(out):
    return json.loads(out.strip().splitlines()[-1])


def entries(log):
    return [json.loads(x) for x in Path(log).read_text(encoding="utf-8").splitlines() if x.strip()]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def vera(args):
    p = subprocess.run([PY, "-m", "verantyx.cli", *map(str, args)], cwd=str(W), env=env_for(),
                       capture_output=True, text=True)
    return p.returncode, p.stdout


def events(root):
    rc, out = vera(["sovereign", "events", "--root", root, "--store-id", "plan"])
    return [json.loads(x) for x in out.splitlines() if x.strip()]


def decision_doc(path, sections, source="/x/src.md"):
    """sections: [(見出し, author|None, 本文)]。author None は宣言なし。"""
    meta = {"schema": "vera.ops.decision/1", "source": source, "source_lines": "1-1",
            "source_sha256": "0" * 64, "copied_at": "t", "copied_by": "test",
            "sections": {f"## {h}": a for h, a, _ in sections if a}}
    s = "<!-- ops-meta " + json.dumps(meta, ensure_ascii=False) + " -->\n"
    s += "\n".join(f"## {h}\n{b}\n" for h, a, b in sections)
    Path(path).write_text(s, encoding="utf-8")


def ticket(path, decl=None, blocks=1):
    body = "チケット本文。\n"
    for _ in range(blocks):
        body += "```shadow-task\n" + json.dumps(decl or TASK_REVIEW, ensure_ascii=False) + "\n```\n"
    Path(path).write_text(body, encoding="utf-8")


# ---------------------------------------------------------------- T-common
def test_common_hidden_paths_refused(tmp_path):
    rc, out, _ = tool("shadow_route", [HIDDEN + "/x.md", "--log", tmp_path / "l.jsonl", "--no-placement"], tmp_path)
    assert rc == 2 and jlast(out)["code"] == "REFUSED_HIDDEN_PATH"
    assert not (tmp_path / "l.jsonl").exists()
    rc, out, _ = tool("plan_ingest", ["--root", tmp_path / "r", "--decisions", HIDDEN], tmp_path)
    assert rc == 1 and jlast(out)["code"] == "REFUSED_HIDDEN_PATH"


def test_common_existing_log_lines_kept_byte_identical(tmp_path):
    log = tmp_path / "log.jsonl"
    old = '{"type":"entry","x":1}\nnot json at all\n'
    log.write_text(old, encoding="utf-8")
    t = tmp_path / "t.md"
    t.write_text("宣言なし\n", encoding="utf-8")
    rc, _, _ = tool("shadow_route", [t, "--log", log, "--no-placement"], tmp_path)
    assert rc == 0
    new = log.read_text(encoding="utf-8")
    assert new.startswith(old) and len(new) > len(old)


def test_common_run_vera_scrubs_sovereign_env(monkeypatch):
    monkeypatch.syspath_prepend(str(W / "tools" / "ops"))
    sys.modules.pop("_common", None)
    import _common as C

    seen = {}

    def fake_run(cmd, **kw):
        seen["env"], seen["cwd"], seen["cmd"] = kw["env"], kw["cwd"], cmd

        class P:
            returncode, stdout, stderr = 0, "{}", ""
        return P()

    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", "/fake")
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "fake")
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    C.run_vera(["ask", "--mode", "round5"], placement=str(R8))
    assert "VERA_SOVEREIGN_ROOT" not in seen["env"] and "VERA_SOVEREIGN_STORE" not in seen["env"]
    assert seen["cwd"] == str(C.ROOT) and seen["env"]["PYTHONPATH"] == str(C.ROOT)
    with pytest.raises(C.ToolError):
        C.run_vera(["ask", "--confirm"], placement=None)


def test_common_fake_sovereign_untouched_by_ask(tmp_path):
    fake = tmp_path / "fake"
    rc, _ = vera(["sovereign", "create", "--root", fake, "--store-id", "plan", "--owner", "o"])
    assert rc == 0
    f = fake / "stores" / "plan.sqlite"
    before = sha(f)
    root = tmp_path / "real"
    d = tmp_path / "dec"
    d.mkdir()
    decision_doc(d / "a.md", [("S", "owner", "花子は太郎に資料を渡した。")])
    assert tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)[0] == 0
    rc, out, _ = tool("shadow_ask", ["誰が太郎に資料を渡しましたか？", "--root", root, "--log", tmp_path / "a.jsonl",
                                    "--no-placement"], tmp_path,
                      {"VERA_SOVEREIGN_ROOT": str(fake), "VERA_SOVEREIGN_STORE": "plan"})
    assert rc == 0 and sha(f) == before


# ---------------------------------------------------------------- T-route
def test_route_declared_block_routes_with_test_sentence(tmp_path):
    need_r8()
    ag = tmp_path / "agents"
    ag.mkdir()
    (ag / "a.md").write_text("Opusがレビューをやる。\n", encoding="utf-8")
    t = tmp_path / "t.md"
    ticket(t)
    log = tmp_path / "log.jsonl"
    rc, out, _ = tool("shadow_route", [t, "--agents-dir", ag, "--policy", tmp_path / "none.md", "--log", log,
                                      "--placement", R8], tmp_path)
    assert rc == 0
    (e,) = entries(log)
    assert e["vera"]["called"] and e["vera"]["decision"] == "route" and e["vera"]["agent"] == "Opus"
    assert e["shadow_class"] == "route" and e["task_source"] == "block" and e["placement"]["content_sha256"]
    assert "チケット本文" not in json.dumps(e, ensure_ascii=False)  # 本文は記録しない


def test_route_real_ops_agents_one_line_per_job(tmp_path):
    need_r8()
    t = tmp_path / "t.md"
    decl = {"jobs": [{"job": "implement", "task": {"role": "implement", "kind": "feature", "size": "medium"}},
                     {"job": "review", "task": {"role": "review", "kind": "review", "size": "medium"}}],
            "author": "test"}
    ticket(t, decl)
    log = tmp_path / "log.jsonl"
    rc, _, _ = tool("shadow_route", [t, "--log", log, "--placement", R8], tmp_path)
    assert rc == 0
    es = entries(log)
    assert [e["job"] for e in es] == ["implement", "review"]
    assert all(e["vera"]["called"] and e["vera"]["rc"] == 0 for e in es)  # 決定の値は主張しない


def test_route_not_declared(tmp_path):
    t = tmp_path / "t.md"
    t.write_text("宣言なし\n", encoding="utf-8")
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--log", log, "--no-placement"], tmp_path)[0] == 0
    (e,) = entries(log)
    assert e["task_status"] == "TASK_NOT_DECLARED" and e["vera"]["called"] is False
    assert e["shadow_class"] == "not_called" and e["job"] is None


def test_route_block_and_task_file_conflict(tmp_path):
    t = tmp_path / "t.md"
    ticket(t)
    other = json.loads(json.dumps(TASK_REVIEW))
    other["jobs"][0]["task"]["size"] = "large"
    tf = tmp_path / "tf.json"
    tf.write_text(json.dumps(other), encoding="utf-8")
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--task-file", tf, "--log", log, "--no-placement"], tmp_path)[0] == 0
    (e,) = entries(log)
    assert e["task_status"] == "TASK_DECLARATION_CONFLICT" and e["vera"]["called"] is False


def test_route_two_blocks_ambiguous(tmp_path):
    t = tmp_path / "t.md"
    ticket(t, blocks=2)
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--log", log, "--no-placement"], tmp_path)[0] == 0
    (e,) = entries(log)
    assert e["task_status"] == "TASK_DECLARATION_AMBIGUOUS" and e["vera"]["called"] is False


def test_route_invalid_value_stops_before_vera(tmp_path):
    t = tmp_path / "t.md"
    bad = {"jobs": [{"job": "x", "task": {"role": "nonsense", "kind": "review", "size": "medium"}}]}
    ticket(t, bad)
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--log", log, "--no-placement"], tmp_path)[0] == 0
    (e,) = entries(log)
    assert e["task_status"] == "TASK_DECLARATION_INVALID" and e["vera"]["called"] is False


def test_route_explanation_is_exact_concatenation(tmp_path):
    ag = tmp_path / "agents"
    ag.mkdir()
    (ag / "b.md").write_text("二番目の文。\n", encoding="utf-8")
    (ag / "a.md").write_text("一番目の文。\n", encoding="utf-8")
    pol = tmp_path / "pol.md"
    pol.write_text("方針の文。\n", encoding="utf-8")
    t = tmp_path / "t.md"
    ticket(t)
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--agents-dir", ag, "--policy", pol, "--log", log, "--no-placement"],
                tmp_path)[0] == 0
    (e,) = entries(log)
    expect = "\n".join(p.read_text(encoding="utf-8") for p in (ag / "a.md", ag / "b.md", pol))
    assert Path(e["explanation"]["path"]).read_text(encoding="utf-8") == expect
    assert [Path(p["path"]).name for p in e["explanation"]["parts"]] == ["a.md", "b.md", "pol.md"]
    assert e["explanation"]["sha256"] == hashlib.sha256(expect.encode()).hexdigest()


def test_route_missing_placement_stops_without_writing(tmp_path):
    t = tmp_path / "t.md"
    ticket(t)
    log = tmp_path / "log.jsonl"
    rc, out, _ = tool("shadow_route", [t, "--log", log, "--placement", tmp_path / "nope"], tmp_path)
    assert rc == 2 and jlast(out)["code"] == "PLACEMENT_UNAVAILABLE" and not log.exists()


# ---------------------------------------------------------------- T-ingest
def two_docs(d):
    d.mkdir()
    decision_doc(d / "a.md", [("A1", "owner", "花子は太郎に資料を渡した。"), ("A2", "auditor", "次郎は太郎に鍵を渡した。")])
    decision_doc(d / "b.md", [("B1", "owner", "三郎は四郎に本を渡した。")])


def test_ingest_idempotent_then_correct(tmp_path):
    d, root = tmp_path / "dec", tmp_path / "root"
    two_docs(d)
    rc, out, _ = tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)
    r = jlast(out)
    assert rc == 0 and r["appended"] == 3 and r["skipped_unchanged"] == 0 and r["refused"] == []
    rc, out, _ = tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)
    r = jlast(out)
    assert r["appended"] == 0 and r["corrected"] == 0 and r["skipped_unchanged"] == 3
    n0 = len(events(root))
    decision_doc(d / "a.md", [("A1", "owner", "花子は太郎に本を渡した。"), ("A2", "auditor", "次郎は太郎に鍵を渡した。")])
    rc, out, _ = tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)
    r = jlast(out)
    assert r["corrected"] == 1 and r["appended"] == 0 and r["skipped_unchanged"] == 2
    evs = events(root)
    assert len(evs) == n0 + 1
    texts = [e["payload"]["text"] for e in evs]
    assert "花子は太郎に資料を渡した。" in texts and "花子は太郎に本を渡した。" in texts  # 前の事件は残る
    new = [e for e in evs if e["payload"]["text"] == "花子は太郎に本を渡した。"][0]
    old = [e for e in evs if e["payload"]["text"] == "花子は太郎に資料を渡した。"][0]
    assert new["payload"]["corrects"] == old["id"]


def test_ingest_missing_author_refuses_only_that_doc(tmp_path):
    d, root = tmp_path / "dec", tmp_path / "root"
    d.mkdir()
    decision_doc(d / "good.md", [("G", "owner", "太郎は花子に鍵を渡した。")])
    decision_doc(d / "bad.md", [("X", None, "宣言のない節。")])
    (d / "nometa.md").write_text("## S\nメタが無い。\n", encoding="utf-8")
    rc, out, _ = tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)
    r = jlast(out)
    assert rc == 0 and r["appended"] == 1
    reasons = {x["doc"]: x["reason"] for x in r["refused"]}
    assert reasons["ops/decisions/bad.md"].startswith("MISSING_AUTHOR")
    assert reasons["ops/decisions/nometa.md"] == "MISSING_META"


def test_ingest_copied_root_is_refused_and_original_untouched(tmp_path):
    d, root, copy = tmp_path / "dec", tmp_path / "root", tmp_path / "copy"
    two_docs(d)
    assert tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)[0] == 0
    shutil.copytree(root, copy)
    f = root / "stores" / "plan.sqlite"
    before = sha(f)
    decision_doc(d / "a.md", [("A1", "owner", "別の文。"), ("A2", "auditor", "次郎は太郎に鍵を渡した。")])
    rc, out, _ = tool("plan_ingest", ["--root", copy, "--decisions", d], tmp_path)
    assert rc == 1 and jlast(out)["code"] == "PLAN_SOVEREIGN_PATH_ELSEWHERE"
    assert sha(f) == before
    rc, out, _ = tool("shadow_ask", ["誰が太郎に資料を渡しましたか？", "--root", copy, "--log", tmp_path / "a.jsonl",
                                    "--no-placement"], tmp_path)
    (e,) = entries(tmp_path / "a.jsonl")
    assert e["shadow_class"] == "abstain" and e["sovereign"]["state"] == "PLAN_SOVEREIGN_PATH_ELSEWHERE"
    assert e["vera"]["called"] is False and sha(f) == before


# ---------------------------------------------------------------- T-ask
def ask_setup(tmp_path, sentences):
    d, root = tmp_path / "dec", tmp_path / "root"
    d.mkdir()
    decision_doc(d / "a.md", [(f"S{i}", "owner", s) for i, s in enumerate(sentences)])
    assert tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)[0] == 0
    return root


def ask(tmp_path, root, q):
    log = tmp_path / "ask.jsonl"
    rc, out, err = tool("shadow_ask", [q, "--root", root, "--log", log, "--placement", R8], tmp_path)
    assert rc == 0, (out, err)
    return entries(log)[-1]


def test_ask_answer_with_traced_evidence(tmp_path):
    need_r8()
    root = ask_setup(tmp_path, ["花子は太郎に資料を渡した。", "次郎は太郎に鍵を渡した。"])
    e = ask(tmp_path, root, "誰が太郎に資料を渡しましたか？")
    assert e["shadow_class"] == "answer" and e["vera"]["values"] == ["花子"]
    hana = [x["id"] for x in events(root) if x["payload"]["text"] == "花子は太郎に資料を渡した。"]
    assert e["evidence_events"] == hana
    lines = [x for x in Path(e["document"]["path"]).read_text(encoding="utf-8").splitlines() if x.strip()]
    texts = [x["payload"]["text"] for x in events(root)]
    assert lines and all(any(ln in t for t in texts) for ln in lines)  # 構成した行が無い


def test_ask_two_givers_is_not_an_answer(tmp_path):
    need_r8()
    root = ask_setup(tmp_path, ["花子は太郎に資料を渡した。", "次郎は太郎に資料を渡した。"])
    e = ask(tmp_path, root, "誰が太郎に資料を渡しましたか？")
    assert e["shadow_class"] != "answer" and e["vera"]["verdict"] == "AMBIGUOUS"


def test_ask_unrecorded_question_is_not_an_answer(tmp_path):
    need_r8()
    root = ask_setup(tmp_path, ["花子は太郎に資料を渡した。", "次郎は太郎に鍵を渡した。"])
    e = ask(tmp_path, root, "誰が四郎に地図を渡しましたか？")
    assert e["shadow_class"] != "answer"


def test_ask_store_missing_is_typed_abstention(tmp_path):
    rc, out, _ = tool("shadow_ask", ["何ですか？", "--root", tmp_path / "none", "--log", tmp_path / "a.jsonl",
                                    "--no-placement"], tmp_path)
    (e,) = entries(tmp_path / "a.jsonl")
    assert rc == 0 and e["shadow_class"] == "abstain" and e["vera"]["called"] is False
    assert e["sovereign"]["state"] == "UNKNOWN_STORE"


# ---------------------------------------------------------------- T-verdict / T-report
def route_entry(i, cls):
    return {"schema": "vera.ops.shadow.route/1", "type": "entry", "entry_id": f"r{i}", "shadow_class": cls,
            "task_source": "block", "task_status": "OK" if cls != "not_called" else "TASK_NOT_DECLARED",
            "vera": {"called": cls != "not_called", "decision": "route" if cls == "route" else None,
                     "undecided_reason": "ABSTAINED" if cls == "undecided" else None,
                     "abstention_type": "INCOMPLETE_READING" if cls == "undecided" else None},
            "verdict": None}


def ask_entry(i, cls, verdict=None, called=True, state="OK"):
    return {"schema": "vera.ops.shadow.ask/1", "type": "entry", "entry_id": f"a{i}", "shadow_class": cls,
            "sovereign": {"state": state}, "vera": {"called": called, "verdict": verdict}, "verdict": None}


def vrow(ref, v):
    return {"type": "verdict", "ref": ref, "verdict": v, "by": "t"}


def write_log(p, rows, tail=""):
    Path(p).write_text("".join(json.dumps(r) + "\n" for r in rows) + tail, encoding="utf-8")


def report(route, ask, n=30):
    rc, out, err = tool("shadow_report", ["--route-log", route, "--ask-log", ask, "--n", n], W)
    return rc, (json.loads(out) if out.strip() else None)


@pytest.fixture
def hand_logs(tmp_path):
    rl, al = tmp_path / "route.jsonl", tmp_path / "ask.jsonl"
    # r1 conflict, r2 agree, r3 agree, r4 undecided+agree, r5 pending(route), r6 not_called
    write_log(rl, [route_entry(1, "route"), vrow("r1", "agree"), vrow("r1", "disagree"),
                   route_entry(2, "route"), route_entry(3, "route"), vrow("r2", "agree"), vrow("r3", "agree"),
                   route_entry(4, "undecided"), vrow("r4", "agree"), route_entry(5, "route"),
                   route_entry(6, "not_called"), vrow("ghost", "agree")])
    # a1 correct, a2 wrong, a3 untraced, a4 abstain, a5 sovereign abstain, a6 correct
    write_log(al, [ask_entry(1, "answer"), vrow("a1", "correct"), ask_entry(2, "answer"), vrow("a2", "wrong"),
                   ask_entry(3, "answer_untraced"), ask_entry(4, "abstain", "UNKNOWN_X"),
                   ask_entry(5, "abstain", None, False, "UNKNOWN_STORE"), ask_entry(6, "answer"),
                   vrow("a6", "correct")])
    return rl, al


def test_report_counts_streak_and_eligibility(hand_logs):
    rl, al = hand_logs
    rc, d = report(rl, al, 2)
    assert rc == 0
    r = d["route"]
    assert r["total_entries"] == 6 and r["by_class"] == {"route": 4, "undecided": 1, "not_called": 1, "error": 0}
    assert r["verdicts"]["agree"] == 2 and r["verdicts"]["verdict_conflict"] == 1
    assert r["verdicts"]["pending"] == 1 and r["verdicts"]["verdict_on_abstain"] == 1
    assert r["verdicts"]["abstain_unjudged"] == 1 and r["verdicts"]["disagree"] == 0
    assert r["streak"] == 2 and r["orphan_verdict_rows"] == 1
    assert r["by_undecided_reason"] == {"ABSTAINED": 1} and r["by_abstention_type"] == {"INCOMPLETE_READING": 1}
    assert r["by_task_source"] == {"block": 6}
    assert r["eligible_for_promotion"]["eligible"] is True
    assert report(rl, al, 3)[1]["route"]["eligible_for_promotion"]["eligible"] is False
    a = d["ask"]
    assert a["total_entries"] == 6
    assert a["by_class"] == {"answer": 3, "answer_untraced": 1, "abstain": 2, "unclassified_output": 0, "error": 0}
    assert a["verdicts"]["correct"] == 2 and a["verdicts"]["wrong"] == 1 and a["verdicts"]["pending"] == 1
    assert a["verdicts"]["abstain_unjudged"] == 2
    assert a["by_abstain_type"] == {"UNKNOWN_X": 1, "SOVEREIGN_UNKNOWN_STORE": 1}
    assert a["streak"] == 1
    assert a["eligible_for_promotion"]["eligible"] is False  # N=2 に対して streak 1
    assert report(rl, al, 1)[1]["ask"]["eligible_for_promotion"]["eligible"] is True


def test_report_unparseable_lines_listed_and_block_promotion(hand_logs):
    rl, al = hand_logs
    with open(al, "a", encoding="utf-8") as f:
        f.write("{broken json\n")
    rc, d = report(rl, al, 1)
    assert rc == 0 and d["ask"]["unparseable_lines"] == [10]
    assert d["ask"]["eligible_for_promotion"]["eligible"] is False
    assert d["ask"]["eligible_for_promotion"]["reason"] == "UNPARSEABLE_LINES"


def test_report_unknown_class_fails_sum_check(tmp_path):
    rl, al = tmp_path / "r.jsonl", tmp_path / "a.jsonl"
    write_log(rl, [route_entry(1, "mystery")])
    write_log(al, [])
    rc, out, _ = tool("shadow_report", ["--route-log", rl, "--ask-log", al], W)
    assert rc == 2 and json.loads(out)["verdict"] == "SUM_MISMATCH"


def test_report_missing_log_is_empty_not_error(tmp_path):
    rl = tmp_path / "r.jsonl"
    write_log(rl, [route_entry(1, "route")])
    rc, d = report(rl, tmp_path / "nope.jsonl")
    assert rc == 0 and d["ask"]["total_entries"] == 0 and d["ask"]["log_present"] is False


def test_verdict_tool_append_only_and_typed_refusals(tmp_path):
    log = tmp_path / "log.jsonl"
    write_log(log, [route_entry(1, "route"), ask_entry(2, "answer")])
    before = log.read_text(encoding="utf-8")
    rc, out, _ = tool("shadow_verdict", ["--log", log, "--ref", "nope", "--verdict", "agree", "--by", "t"], tmp_path)
    assert rc == 1 and jlast(out)["verdict"] == "UNKNOWN_REF" and log.read_text(encoding="utf-8") == before
    rc, out, _ = tool("shadow_verdict", ["--log", log, "--ref", "r1", "--verdict", "correct", "--by", "t"], tmp_path)
    assert rc == 1 and jlast(out)["verdict"] == "VERDICT_KIND_MISMATCH" and log.read_text(encoding="utf-8") == before
    rc, out, _ = tool("shadow_verdict", ["--log", log, "--ref", "r1", "--verdict", "agree", "--by", "t",
                                        "--note", "n"], tmp_path)
    assert rc == 0
    now = log.read_text(encoding="utf-8")
    assert now.startswith(before)
    row = json.loads(now[len(before):])
    assert row["type"] == "verdict" and row["ref"] == "r1" and row["verdict"] == "agree"
    rc, out, _ = tool("shadow_verdict", ["--log", log, "--ref", "a2", "--verdict", "wrong", "--by", "t"], tmp_path)
    assert rc == 0


def test_manual_verdict_field_conflicting_with_row_counts_as_conflict(tmp_path):
    rl, al = tmp_path / "r.jsonl", tmp_path / "a.jsonl"
    e = route_entry(1, "route")
    e["verdict"] = "agree"
    write_log(rl, [e, vrow("r1", "disagree")])
    write_log(al, [])
    rc, d = report(rl, al)
    assert d["route"]["verdicts"]["verdict_conflict"] == 1 and d["route"]["streak"] == 0


# ---------------------------------------------------------------- T-isolation
def test_isolation_verantyx_does_not_reference_shadow_tools():
    needles = ("ops/shadow", "tools.ops", "tools/ops", "shadow_route", "shadow_ask", "shadow_report",
               "shadow_verdict", "plan_ingest", "route_log", "ask_log")
    hits = []
    for p in (W / "verantyx").rglob("*.py"):
        s = p.read_text(encoding="utf-8", errors="replace")
        hits += [(str(p.relative_to(W)), n) for n in needles if n in s]
    assert hits == []


def test_isolation_tools_import_only_standard_library():
    import ast

    std = set(sys.stdlib_module_names)
    local = {"_common", "plan_ingest", "verantyx"}  # verantyx は route 宣言の値の一覧の import だけ
    for p in (W / "tools" / "ops").glob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                mods = [node.module.split(".")[0]]
            for m in mods:
                assert m in std or m in local, (p.name, m)


# ---------------------------------------------------------------- r2 追加
def test_real_ops_explanation_has_no_provenance_line():
    """M1: 実物の ops/agents＋routing_policy.md から合成した説明文に「出所」の行が無い。"""
    parts = sorted((W / "ops" / "agents").glob("*.md"), key=lambda p: p.name) + [W / "ops" / "routing_policy.md"]
    assert len(parts) == 6
    expl = "\n".join(p.read_text(encoding="utf-8") for p in parts)
    assert "出所" not in expl
    assert all(p.read_text(encoding="utf-8").strip() for p in parts)
    src = json.loads((W / "ops" / "agents" / "SOURCES.json").read_text(encoding="utf-8"))
    assert set(src) == {p.name for p in parts[:-1]} | {"../routing_policy.md"}  # 出所は連結の対象外のファイルに


def test_route_duplicate_job_name_is_invalid(tmp_path):
    t = tmp_path / "t.md"
    j = {"job": "x", "task": {"role": "review", "kind": "review", "size": "medium"}}
    ticket(t, {"jobs": [j, j], "author": "test"})
    log = tmp_path / "log.jsonl"
    assert tool("shadow_route", [t, "--log", log, "--no-placement"], tmp_path)[0] == 0
    (e,) = entries(log)
    assert e["task_status"] == "TASK_DECLARATION_INVALID" and e["vera"]["called"] is False


def test_common_rec_path_is_relative_inside_root(monkeypatch):
    """M5: ROOT の下は相対パス、外は実パス。"""
    monkeypatch.syspath_prepend(str(W / "tools" / "ops"))
    sys.modules.pop("_common", None)
    import _common as C

    assert C.rec_path({"path": str(W / "ops/shadow/raw/x.json"), "sha256": "a"}) == \
        {"path": "ops/shadow/raw/x.json", "sha256": "a"}
    outside = os.path.realpath("/tmp")
    assert C.rec_path({"path": "/tmp", "sha256": "a"})["path"] == outside


def test_route_log_paths_are_not_absolute_inside_root(tmp_path, monkeypatch):
    """M5: ROOT の下に置いたログの explanation/raw のパスは相対。作業ツリーには何も書かない（ROOT を tmp_path に差し替え、vera は偽物）。"""
    monkeypatch.syspath_prepend(str(W / "tools" / "ops"))
    for m in ("_common", "shadow_route"):
        sys.modules.pop(m, None)
    import _common as C
    import shadow_route as SR

    fake_root = tmp_path / "tree"
    (fake_root / "agents").mkdir(parents=True)
    (fake_root / "agents" / "a.md").write_text("Opusがレビューをやる。\n", encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", fake_root)
    monkeypatch.setattr(C, "run_vera", lambda args, placement: (0, json.dumps(
        {"decision": "undecided", "undecided_reason": "ABSTAINED", "abstention": {"type": "INCOMPLETE_READING"}}), ""))
    monkeypatch.setattr(C, "tree_info", lambda: {"git_head": None, "verantyx_clean": None})
    t = tmp_path / "t.md"
    ticket(t)
    log = fake_root / "ops" / "shadow" / "log.jsonl"
    rc = SR.main([str(t), "--log", str(log), "--no-placement",
                  "--agents-dir", str(fake_root / "agents"), "--policy", str(fake_root / "none.md")])
    assert rc == 0
    (e,) = entries(log)
    assert not Path(e["explanation"]["path"]).is_absolute() and not Path(e["raw"]["path"]).is_absolute()
    assert str(tmp_path) not in json.dumps(e["explanation"]) + json.dumps(e["raw"])
    assert (fake_root / e["raw"]["path"]).is_file() and (fake_root / e["explanation"]["path"]).is_file()


def test_ingest_duplicate_section_refused_and_stable(tmp_path):
    """M4: 同じ見出しが 2 つある文書はその文書だけ refused。何度流しても事件の数は変わらない。"""
    d, root = tmp_path / "dec", tmp_path / "root"
    d.mkdir()
    decision_doc(d / "good.md", [("G", "owner", "太郎は花子に鍵を渡した。")])
    decision_doc(d / "dup.md", [("D", "auditor", "一つ目の文。"), ("D", "auditor", "二つ目の文。")])
    counts = []
    for _ in range(3):
        rc, out, _ = tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)
        r = jlast(out)
        assert rc == 0
        reasons = {x["doc"]: x["reason"] for x in r["refused"]}
        assert reasons == {"ops/decisions/dup.md": "DUPLICATE_SECTION:## D"}
        counts.append(len(events(root)))
    assert counts == [1, 1, 1]


def test_ask_correction_exports_only_new_text(tmp_path):
    """訂正のあとの書き出しには新しい本文だけが入り、古い本文は入らない。"""
    need_r8()
    d, root = tmp_path / "dec", tmp_path / "root"
    d.mkdir()
    decision_doc(d / "a.md", [("A1", "owner", "花子は太郎に資料を渡した。")])
    assert tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)[0] == 0
    decision_doc(d / "a.md", [("A1", "owner", "花子は太郎に本を渡した。")])
    assert jlast(tool("plan_ingest", ["--root", root, "--decisions", d], tmp_path)[1])["corrected"] == 1
    e = ask(tmp_path, root, "誰が太郎に本を渡しましたか？")
    text = (tmp_path / e["document"]["path"] if not Path(e["document"]["path"]).is_absolute()
            else Path(e["document"]["path"])).read_text(encoding="utf-8")
    assert "本を渡した" in text and "資料を渡した" not in text
    assert len(e["sovereign"]["events_used"]) == 1
