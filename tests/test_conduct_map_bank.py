"""Shape of the W2-g self-made fixtures (paraphrased questions; frozen before the code that uses them)."""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402,F401  (puts the repository root on sys.path)

from verantyx import conduct_ask as ca  # noqa: E402
from verantyx.project_frame import load_conduct_frame  # noqa: E402

W2G = Path(__file__).resolve().parent / "conduct_ask" / "w2g"


def _items() -> list[dict]:
    return [json.loads(ln) for ln in (W2G / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def _ids(name: str) -> list[str]:
    return [ln.strip() for ln in (W2G / name).read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_w2g_fixture_shape():
    items = _items()
    frames = sorted((W2G / "frames").glob("*.md"))
    assert len(items) >= 60 and len(frames) >= 6
    assert len({i["id"] for i in items}) == len(items)
    per_frame = collections.Counter(i["frame_id"] for i in items)
    assert set(per_frame) == {f.stem for f in frames}
    cat = collections.Counter(i["w2c"]["category"] for i in items)
    assert set(cat) == {"direct", "combined", "oov", "escalate"} and set(cat.values()) == {len(items) // 4}
    lang = collections.Counter(i["lang"] for i in items)
    assert lang["ja"] >= 24 and lang["en"] >= 24
    with_opts = [i for i in items if i["options"]]
    assert len(with_opts) >= 56 and len(items) - len(with_opts) <= 8
    assert any(len(i["options"]) == 3 for i in with_opts) and any(i["options"] == ["はい", "いいえ"] for i in with_opts)
    assert any(i["options"] == ["Yes", "No"] for i in with_opts)
    kinds = collections.Counter(i["w2g"].get("escalate_kind") for i in items if i["w2c"]["category"] == "escalate")
    assert kinds["A"] >= 3 and kinds["B"] >= 2 and kinds["C"] >= 2 and kinds["D"] >= 2
    assert kinds["E"] >= 2 and kinds["F"] >= 2 and kinds["G"] >= 1 and kinds["H"] >= 2
    held = set(_ids("holdout.txt"))
    assert len(held) == 2 and held <= set(per_frame)
    assert {next(i["lang"] for i in items if i["frame_id"] == h) for h in held} == {"ja", "en"}
    subset = _ids("claude_subset.txt")
    ids = {i["id"] for i in items}
    assert 0 < len(subset) <= 30 and set(subset) <= ids
    assert {i["frame_id"] for i in items if i["id"] in subset} == held
    views = {f.stem: ca.build_view(load_conduct_frame(str(f))) for f in frames}   # every frame loads
    for fid, v in views.items():
        assert v.phases and v.edges and v.policies
    for it in items:
        v = views[it["frame_id"]]
        rec_ids = ({e.ref.id for e in v.edges} | {p.ref.id for p in v.policies} | {d.ref.id for d in v.decisions}
                   | {a.ref.id for a in v.forbidden} | {a.ref.id for a in v.protected} | {c.id for c in v.criteria}
                   | {x.id for x in v.invariants} | {r.id for _, r in v.allow} | {e.id for e in v.escalations})
        assert set(it["expect"]["records"]) <= rec_ids, it["id"]
        exp = it["expect"]
        if exp["decision"] == "answer":
            if it["options"]:
                assert 0 <= exp["answer_option_index"] < len(it["options"]) and exp["answer"] == it["options"][exp["answer_option_index"]]
            else:
                assert exp["answer_option_index"] is None and exp["answer"]
        else:
            assert exp["answer"] is None and exp["answer_option_index"] is None and it["w2c"]["escalate_reason"]
        assert it["w2g"]["paraphrase"] is True and set(it["w2c"]) >= {"category", "oov_none", "escalate_reason", "trap", "permission"}


# ---- the second, fresh G3 data set (w2g2): written and frozen before the order / value changes of conduct_map.py -----------

W2G2 = Path(__file__).resolve().parent / "conduct_ask" / "w2g2"


def test_w2g2_fixture_shape():
    items = [json.loads(ln) for ln in (W2G2 / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    frames = sorted((W2G2 / "frames").glob("*.md"))
    assert len(items) == 64 and len(frames) == 6
    assert len({i["id"] for i in items}) == 64
    assert set(collections.Counter(i["frame_id"] for i in items)) == {f.stem for f in frames}
    cat = collections.Counter(i["w2c"]["category"] for i in items)
    assert dict(cat) == {"direct": 16, "combined": 16, "oov": 16, "escalate": 16}
    lang = collections.Counter(i["lang"] for i in items)
    assert lang["ja"] >= 24 and lang["en"] >= 24
    assert len({i["frame_id"] for i in items if i["lang"] == "ja"}) == 3 and len({i["frame_id"] for i in items if i["lang"] == "en"}) == 3
    with_opts = [i for i in items if i["options"]]
    assert len(with_opts) >= 56 and len(items) - len(with_opts) <= 8
    assert any(len(i["options"]) == 3 for i in with_opts) and any(i["options"] == ["はい", "いいえ"] for i in with_opts)
    assert any(i["options"] == ["Yes", "No"] for i in with_opts)
    chains = [i for i in items if i["w2c"]["category"] == "combined" and i["w2g"]["note"] == "order chain"]
    assert len(chains) >= 6
    kinds = collections.Counter(i["w2g"].get("escalate_kind") for i in items if i["w2c"]["category"] == "escalate")
    for k in ("B_PAST", "NEG", "ADVICE", "B_SUBJECT", "COND", "G", "D", "F", "H"):
        assert kinds[k] >= 1, k
    assert kinds["A"] >= 3 and kinds["C"] >= 2 and kinds["E"] >= 2
    held = {ln.strip() for ln in (W2G2 / "holdout.txt").read_text(encoding="utf-8").splitlines() if ln.strip()}
    assert len(held) == 2 and held <= {f.stem for f in frames}
    assert {next(i["lang"] for i in items if i["frame_id"] == h) for h in held} == {"ja", "en"}
    subset = [ln.strip() for ln in (W2G2 / "claude_subset.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert 0 < len(subset) <= 30 and set(subset) <= {i["id"] for i in items}
    assert {i["frame_id"] for i in items if i["id"] in subset} == held
    views = {f.stem: ca.build_view(load_conduct_frame(str(f))) for f in frames}
    for fid, v in views.items():
        assert v.phases and v.edges and v.policies
    for it in items:
        v = views[it["frame_id"]]
        rec_ids = ({e.ref.id for e in v.edges} | {p.ref.id for p in v.policies} | {d.ref.id for d in v.decisions}
                   | {a.ref.id for a in v.forbidden} | {a.ref.id for a in v.protected} | {c.id for c in v.criteria}
                   | {x.id for x in v.invariants} | {r.id for _, r in v.allow} | {e.id for e in v.escalations})
        exp = it["expect"]
        assert set(exp["records"]) <= rec_ids, it["id"]
        if exp["decision"] == "answer":
            if it["options"]:
                assert 0 <= exp["answer_option_index"] < len(it["options"]) and exp["answer"] == it["options"][exp["answer_option_index"]]
            else:
                assert exp["answer_option_index"] is None and exp["answer"]
        else:
            assert exp["answer"] is None and exp["answer_option_index"] is None and it["w2c"]["escalate_reason"]


# ---- the third, fresh G3 data set (w2g3): written and frozen before any reader was run on it (W2-g2) ---------------------------------------

W2G3 = Path(__file__).resolve().parent / "conduct_ask" / "w2g3"


def test_w2g3_fixture_shape():
    items = [json.loads(ln) for ln in (W2G3 / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    frames = sorted((W2G3 / "frames").glob("*.md"))
    assert len(items) == 60 and len(frames) == 6 and len({i["id"] for i in items}) == 60
    assert {f.stem for f in frames} == {"y01_hall", "y02_lunch", "y03_usedbooks", "y04_hives", "y05_water", "y06_stars"}
    assert set(collections.Counter(i["frame_id"] for i in items).values()) == {10}
    assert dict(collections.Counter(i["w2c"]["category"] for i in items)) == {"direct": 15, "combined": 15, "oov": 15, "escalate": 15}
    assert dict(collections.Counter(i["lang"] for i in items)) == {"ja": 30, "en": 30}
    assert not (W2G3 / "holdout.txt").exists() and not (W2G3 / "claude_subset.txt").exists()
    order = [i for i in items if i["expect"]["decision"] == "answer" and str(i["w2g"]["note"]).startswith("order")]
    assert len(order) >= 12
    kinds = collections.Counter(i["w2g"]["escalate_kind"] for i in items if i["expect"]["decision"] == "escalate")
    assert sum(kinds[k] for k in ("ORDER_DAYS", "ORDER_WHO", "ORDER_SUBJECT", "PREF_NOOPT")) >= 4 and kinds["PREF_NOOPT"] >= 1
    assert sum(1 for i in items if i["expect"]["decision"] == "answer" and i["options"] and len(i["options"]) >= 3) >= 10
    assert all(i["options"] is None or 2 <= len(i["options"]) <= 4 for i in items) and any(not i["options"] for i in items)
    others = set()
    for d in (W2G / "frames", W2G2 / "frames", W2G.parent / "fixtures" / "frames"):
        others |= {ln.strip() for f in d.glob("*.md") for ln in f.read_text(encoding="utf-8").splitlines() if len(ln.strip()) > 12 and not ln.startswith("[")}
    mine = {ln.strip() for f in frames for ln in f.read_text(encoding="utf-8").splitlines() if len(ln.strip()) > 12 and not ln.startswith("[")}
    assert mine and not (mine & others)                          # no sentence of the new frames is in an earlier data set's frames
    views = {f.stem: ca.build_view(load_conduct_frame(str(f))) for f in frames}
    for fid, v in views.items():
        assert v.phases and v.edges and v.policies and not v.skipped_records
    for it in items:
        v = views[it["frame_id"]]
        rec_ids = ({e.ref.id for e in v.edges} | {p.ref.id for p in v.policies} | {d.ref.id for d in v.decisions}
                   | {a.ref.id for a in v.forbidden} | {a.ref.id for a in v.protected} | {c.id for c in v.criteria}
                   | {x.id for x in v.invariants} | {r.id for _, r in v.allow} | {e.id for e in v.escalations})
        exp = it["expect"]
        assert set(exp["records"]) <= rec_ids, it["id"]
        if exp["decision"] == "answer":
            if it["options"]:
                assert 0 <= exp["answer_option_index"] < len(it["options"]) and exp["answer"] == it["options"][exp["answer_option_index"]]
            else:
                assert exp["answer_option_index"] is None and exp["answer"]
        else:
            assert exp["answer"] is None and exp["answer_option_index"] is None and it["w2c"]["escalate_reason"]


# ---- the runner's reservation of each question's worst case (W2-g2) -----------------------------------------------------------------------

import importlib.util  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402


def _runner():
    spec = importlib.util.spec_from_file_location("run_map_bank_under_test", W2G / "run_map_bank.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _first_ids(n):
    return [i["id"] for i in _items()[:n]]


def _argv(tmp_path, ids, *extra):
    subset = tmp_path / "subset.txt"
    subset.write_text("\n".join(ids) + "\n", encoding="utf-8")
    return ["--items", str(W2G / "items.jsonl"), "--frames", str(W2G / "frames"), "--mode", "codex", "--subset", str(subset),
            "--out", str(tmp_path / "root" / "run"), "--budget-root", str(tmp_path / "root"), *extra]


def _write_rows(path, n):
    with open(path, "a", encoding="utf-8") as fh:
        for _ in range(n):
            fh.write(json.dumps({"type": "map_ask", "verdict": "PICK", "step": "records"}) + "\n")


def _fake_run_one(R, per_question_rows, started, delay=0.0, timeout_ids=()):
    def run_one(item, frames, args, out):
        started.append(item["id"])
        time.sleep(delay)
        _write_rows(Path(args.ledger), per_question_rows)
        if item["id"] in timeout_ids:
            return {"decision": "escalate", "escalate_reason": "INTERNAL_ERROR", "escalate_detail": "RUN_TIMEOUT", "_exit": None, "_elapsed_s": 0.0}
        res = ca.answer_question(str(frames / f"{item['frame_id']}.md"), item["question"], item.get("options"))
        res["_exit"], res["_elapsed_s"] = 0, 0.0
        return res
    return run_one


def test_the_runner_stops_at_the_first_question_whose_worst_case_does_not_fit_and_keeps_the_file_order(tmp_path, monkeypatch):
    R = _runner()
    ids = _first_ids(5)
    (tmp_path / "root").mkdir()
    started: list = []
    monkeypatch.setattr(R, "run_one", _fake_run_one(R, 20, started))
    # worst case of a question = 2 + 24 = 26.  Each question writes 20 asks: 0+26 ok, 20+26 ok, 40+26 = 66 > 60 -> stop
    code = R.main(_argv(tmp_path, ids, "--total-budget", "60", "--workers", "1"))
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert code == 0 and started == ids[:2]
    assert summary["not_run_budget"] == ids[2:] and summary["not_run"] == [] and summary["total"] == 2
    assert summary["config"]["budget"]["worst_per_question"] == 26 and summary["config"]["budget"]["total"] == 60


def test_the_asks_of_other_ledgers_under_the_budget_root_and_of_running_questions_count(tmp_path, monkeypatch):
    R = _runner()
    ids = _first_ids(4)
    (tmp_path / "root" / "other").mkdir(parents=True)
    _write_rows(tmp_path / "root" / "other" / "ledger.jsonl", 30)
    started: list = []
    monkeypatch.setattr(R, "run_one", _fake_run_one(R, 3, started))
    # 30 + 26 = 56 <= 60: the first; then 33 + 26 = 59 <= 60: the second; 36 + 26 = 62 > 60: stop
    R.main(_argv(tmp_path, ids, "--total-budget", "60", "--workers", "1"))
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert started == ids[:2] and summary["not_run_budget"] == ids[2:]


def test_questions_in_flight_hold_their_reservation_and_start_in_file_order_with_several_workers(tmp_path, monkeypatch):
    R = _runner()
    ids = _first_ids(4)
    (tmp_path / "root").mkdir()
    started: list = []
    monkeypatch.setattr(R, "run_one", _fake_run_one(R, 5, started, delay=0.15))
    # room for two questions in flight (52 <= 60 < 78): the third waits for one of them to finish, then runs; none is skipped
    R.main(_argv(tmp_path, ids, "--total-budget", "60", "--workers", "3"))
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert sorted(started) == sorted(ids) and summary["not_run_budget"] == [] and summary["total"] == 4


def test_a_question_killed_by_the_timeout_is_counted_as_its_worst_case(tmp_path, monkeypatch):
    R = _runner()
    ids = _first_ids(3)
    (tmp_path / "root").mkdir()
    started: list = []
    monkeypatch.setattr(R, "run_one", _fake_run_one(R, 0, started, timeout_ids={ids[0]}))
    # the first writes nothing and is killed: its 26 are counted as lost, so 26 + 26 = 52 > 51 for the second
    R.main(_argv(tmp_path, ids, "--total-budget", "51", "--workers", "1"))
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert started == ids[:1] and summary["not_run_budget"] == ids[1:]


def test_the_run_budget_limits_this_runs_own_asks_and_a_question_that_can_never_fit_refuses_the_run(tmp_path, monkeypatch, capsys):
    R = _runner()
    ids = _first_ids(3)
    (tmp_path / "root").mkdir()
    started: list = []
    monkeypatch.setattr(R, "run_one", _fake_run_one(R, 10, started))
    R.main(_argv(tmp_path, ids, "--total-budget", "1000", "--run-budget", "40", "--workers", "3"))        # 26 <= 40; 10 + 26 = 36 <= 40; 20 + 26 > 40
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert started == ids[:2] and summary["not_run_budget"] == ids[2:]
    code = R.main(_argv(tmp_path, ids, "--total-budget", "1000", "--run-budget", "25", "--out", str(tmp_path / "root" / "never")))
    assert code == 3 and "REFUSED" in capsys.readouterr().out and not (tmp_path / "root" / "never" / "summary.json").exists()


def test_a_second_provider_that_hits_its_limit_three_times_in_a_row_stops_the_run(tmp_path, monkeypatch):
    R = _runner()
    ids = _first_ids(6)
    (tmp_path / "root").mkdir()

    def run_one(item, frames, args, out):
        res = ca.answer_question(str(frames / f"{item['frame_id']}.md"), item["question"], item.get("options"))
        res["_exit"], res["_elapsed_s"] = 0, 0.0
        res["mapping"] = {"route": "MAPPING_ONLY", "outcome": "ESCALATED:MAPPING_UNSETTLED/STEP1_FAILED:LIMIT_REACHED", "asks_used": 2,
                          "rule": {}, "step1": {"status": "FAILED", "asks": [{"provider": "codex", "failure": "LIMIT_REACHED"}] * 2}}
        return res
    monkeypatch.setattr(R, "run_one", run_one)
    R.main(_argv(tmp_path, ids, "--total-budget", "1000", "--workers", "1"))
    summary = json.loads((tmp_path / "root" / "run" / "summary.json").read_text(encoding="utf-8"))
    assert summary["aborted"] == "CODEX_LIMIT" and summary["total"] == 3 and summary["not_run"] == ids[3:]


def test_the_entry_gets_the_effort_and_the_time_limit_as_given(tmp_path, monkeypatch):
    R = _runner()
    seen = []

    class P:
        returncode, stdout = 0, "{}"

    def fake_run(argv, **kw):
        seen.append(list(argv))
        return P()
    monkeypatch.setattr(R.subprocess, "run", fake_run)
    item = _items()[0]
    out = tmp_path / "o"
    import argparse
    base = dict(mode="codex", second="codex", ledger=str(tmp_path / "l.jsonl"), map_max_asks=24, timeout=10.0)
    R.run_one(item, W2G / "frames", argparse.Namespace(map_effort="xhigh", map_timeout=600.0, **base), out)
    argv = seen[-1]
    assert argv[argv.index("--map-effort") + 1] == "xhigh" and argv[argv.index("--map-timeout") + 1] == "600.0"
    assert argv[argv.index("--map-max-asks") + 1] == "24" and argv[argv.index("--vocab-llm") + 1] == "codex"
    R.run_one(item, W2G / "frames", argparse.Namespace(map_effort=None, map_timeout=None, **base), out)
    assert "--map-effort" not in seen[-1] and "--map-timeout" not in seen[-1]
    R.run_one(item, W2G / "frames", argparse.Namespace(**{**base, "mode": "off"}, map_effort="xhigh", map_timeout=5.0), out)
    assert "--map-effort" not in seen[-1] and "--vocab-llm" not in seen[-1]
