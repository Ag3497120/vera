"""LOOM-batch tests that outlive LOOM-span: the cap profiles (docs/LINE3_LOOM_DESIGN.md 4; L-LOOM-122).

The batch seating `weave_sentence` of LOOM-batch (L-LOOM-123..126) was replaced by `weave_span` (LOOM-span); its live tests moved to
tests/core/test_loom_span.py (`weave_span`) and its REPLAY (legacy path) is tested there too.  What stays here: a run's caps are written into its
`begin` row, there are two named profiles, v1 = the first measurement and every ledger before LOOM-batch, v2 = what a new run gets (prose lookups 100,
ops 200), and every old ledger replays with its own caps.  The toy corpus is written to a temp file, so these tests do not depend on the bank; the
old-ledger tests read the stored runs (runs_h55, baseline_scripted) with the real corpus.
"""


import hashlib


import json


import os


import subprocess


import pytest


from verantyx.loom import ledger as lg


from verantyx.loom.mcp import LoomServer


from verantyx.loom.scripted import ScriptedWeaver


from verantyx.loom.state import CAPS, CAPS_V1, CAPS_V2, caps_profile_of


from loom_common import CORPUS, PY, ROOT, rows


SENTS = ["東京は日本の首都です。",                     # 0  東京(は) 日本(の) 首都
         "日本の首都は東京です。",                     # 1
         "ハッシュ表ともいう。",                       # 2  ハッシュ() 表(と) いう
         "彼が東京で日本の首都を見た。",               # 3  東京(で) 日本(の) 首都(を)
         "日本が勝った。",                             # 4  日本(が) 勝っ
         "東京の大学に通う学生と先生がいる。",         # 5  東京(の) 大学(に) 通う() 学生(と) 先生(が)
         "日本の大学の学生の先生の家の本。",           # 6  five units followed by の, then 本
         "日本の大学の学生。",                         # 7  日本(の) 大学(の) 学生
         "大学で学生が先生と本を読む。"]               # 8


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
    return LoomServer(toy_tasks(toy), str(tmp_path / "runs"), (), **dict({"evidence": "off"}, **kw))


def started(toy, tmp_path, task_id="toy/ca", run_id="r1", **kw):
    srv = srv_of(toy, tmp_path, **kw)
    w = ScriptedWeaver(srv, task_id, "test-weaver", run_id)
    assert w.begin()["ok"]
    return srv, w


def refused(res, type_):
    assert res["ok"] is False and res["refusal"] == type_, res
    return res["detail"]


def shape(srv, w):
    """The state without the counters: what a refused call must leave as it was."""
    o = srv.runs[w.run_id].run.state.to_obj()
    o.pop("counters")
    o.pop("guards")
    return json.dumps(o, sort_keys=True)


def test_the_cap_profiles_v1_is_the_first_measurement_and_v2_changes_only_the_prose_ops_and_lookups():
    assert CAPS is CAPS_V2 or CAPS == CAPS_V2
    assert CAPS_V1["prose"] == {"ops": 120, "lookups": 30, "reads": 20, "emit_attempts": 5, "constructed": 12, "unit_chars": 8, "max_L": 5, "crosses": 24, "max_depth": 8}
    assert CAPS_V2["prose"] == dict(CAPS_V1["prose"], ops=200, lookups=100) and CAPS_V2["code"] == CAPS_V1["code"]
    assert caps_profile_of("prose", CAPS_V1["prose"]) == "v1" and caps_profile_of("prose", CAPS_V2["prose"]) == "v2"
    assert caps_profile_of("code", CAPS_V2["code"]) == "v1" and caps_profile_of("prose", dict(CAPS_V1["prose"], lookups=31)) is None
    assert caps_profile_of("prose", None) is None and caps_profile_of("prose", "v2") is None


def test_a_new_run_gets_100_lookups_and_200_ops_in_its_begin_row_and_enforces_them(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro")
    r0 = rows(tmp_path / "runs" / "r1")[0]["result"]["task"]["caps"]
    assert (r0["lookups"], r0["ops"], r0["reads"], r0["emit_attempts"]) == (100, 200, 20, 5)
    for i in range(100):
        assert w.call("lookup", text="日本", tier="any")["ok"]
    assert refused(w.call("lookup", text="日本", tier="any"), "lookup_cap") == {"limit": 100}
    refused(w.call("read_sentence", sid=0), "lookup_cap")


def test_a_v1_server_keeps_the_old_caps_and_its_ledger_replays_with_them(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro", caps="v1")
    r0 = rows(tmp_path / "runs" / "r1")[0]["result"]["task"]["caps"]
    assert (r0["lookups"], r0["ops"]) == (30, 120)
    for i in range(30):
        assert w.call("lookup", text="日本", tier="any")["ok"]
    assert refused(w.call("lookup", text="日本", tier="any"), "lookup_cap") == {"limit": 30}
    w.call("abstain", type="unknown")
    d = tmp_path / "runs" / "r1"
    rep = lg.replay(d, toy)
    assert rep.status == "IDENTICAL" and rep.run.caps["lookups"] == 30           # the replay used the recorded caps, not the current ones
    assert lg.verify(d, corpus_path=toy)["status"] == "OK"
    # a server restarted on that folder reloads the run with ITS caps
    srv2 = srv_of(toy, tmp_path)
    assert srv2._entry("r1").run.caps["lookups"] == 30 and srv2._entry("r1").run.state.closed == ["abstained", "unknown"]
    refused(srv2.call("lookup", {"run_id": "r1", "text": "日本", "tier": "any"}), "run_closed")
    with pytest.raises(ValueError):
        srv_of(toy, tmp_path, caps="v3")


def test_a_recorded_cap_set_that_is_no_known_profile_is_refused_not_obeyed(toy, tmp_path):
    srv, w = started(toy, tmp_path, "toy/ro", caps="v1")
    w.call("lookup", text="日本", tier="any")
    d = tmp_path / "runs" / "r1"
    rs = rows(d)
    rs[0]["result"]["task"]["caps"]["lookups"] = 31
    (d / "ops.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rs), encoding="utf-8")
    rep = lg.replay(d, toy)
    assert rep.status == "INPUTS" and rep.mismatch == "caps_unknown"


def test_the_demo_keeps_the_v1_caps_so_its_bytes_stay_pinned(tmp_path):
    p = subprocess.run([PY, "-m", "verantyx.harness.cli", "loom", "demo", "--corpus", CORPUS, "--runs-dir", str(tmp_path / "runs")],
                       env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"), cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    caps = rows(tmp_path / "runs" / "demo_ca")[0]["result"]["task"]["caps"]
    assert caps == CAPS_V1["prose"]
