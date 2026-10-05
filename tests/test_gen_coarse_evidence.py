"""The definition generator (W3-a2): the needs list, and `run` against a FAKE codex.

No test here ever calls the real codex: ``--codex-bin`` is always a script written
into tmp_path.  The fake takes its behaviour from a JSON file next to it (an
environment variable would not do: the project's py.sh clears the environment)."""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools import gen_coarse_evidence as gce

TREE = Path(__file__).resolve().parents[1]
PYTHON = sys.executable

FAKE = r'''#!%(python)s
import hashlib, json, os, sys, time, select
here = os.path.dirname(os.path.abspath(__file__))
cfg = json.load(open(os.path.join(here, "fake_cfg.json"), encoding="utf-8"))
argv = sys.argv[1:]
prompt = argv[-1]
words = []
for line in prompt.splitlines():
    if line.startswith("WORDS_JSON:"):
        words = json.loads(line[len("WORDS_JSON:"):].strip())
out = argv[argv.index("-o") + 1]
t0 = time.time()
rec = {"argv": argv, "t0": t0, "first": words[0] if words else None, "n": len(words)}
if cfg.get("check_stdin"):
    r, _, _ = select.select([0], [], [], 2.0)
    ok = bool(r) and os.read(0, 1) == b""
    if not ok:
        open(os.path.join(here, "STDIN_NOT_CLOSED"), "w").write("x")
        sys.exit(9)
time.sleep(cfg.get("sleep", 0))
key = words[0] if words else ""
cnt_path = os.path.join(here, "count_" + hashlib.md5(key.encode("utf-8")).hexdigest())
n = 0
if os.path.exists(cnt_path):
    n = int(open(cnt_path).read())
open(cnt_path, "w").write(str(n + 1))
rec["attempt_seen"] = n + 1
rec["t1"] = time.time()
with open(os.path.join(here, "calls.jsonl"), "a") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
if key in cfg.get("always_fail", []) or n < cfg.get("fail_first", {}).get(key, 0):
    sys.stderr.write("simulated failure\n")
    sys.exit(1)
if cfg.get("tool_use"):
    print(json.dumps({"type": "item.completed", "item": {"type": "command_execution"}}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}))
items = []
for w in words:
    if w in cfg.get("missing", []):
        continue
    if w in cfg.get("null", []):
        items.append({"word": w, "definition": None, "hypernym": None})
        continue
    items.append({"word": w, "definition": w + "は道具である。", "hypernym": "道具"})
    if w in cfg.get("dup", []):
        items.append({"word": w, "definition": w + "は人である。", "hypernym": "人"})
if cfg.get("foreign"):
    items.append({"word": "ゼンゼンチガウ", "definition": "x", "hypernym": "y"})
json.dump({"items": items}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
'''


def make_fake(tmp: Path, **cfg) -> Path:
    p = tmp / "fakecodex"
    p.write_text(FAKE % {"python": PYTHON}, encoding="utf-8")
    p.chmod(0o755)
    set_cfg(tmp, **cfg)
    return p


def set_cfg(tmp: Path, **cfg):
    (tmp / "fake_cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")


def write_needs(path: Path, n: int, prefix="語"):
    with open(path, "w", encoding="utf-8") as f:
        for i in range(n):
            f.write(json.dumps({"rank": i + 1, "word": "%s%03d" % (prefix, i), "freq": 1000 - i,
                                "state": "UNPLACED", "ns": "N", "kind": "token",
                                "evidence_status": "NO_EVIDENCE"}, ensure_ascii=False) + "\n")


def run(tmp, needs, out_dir, fake, *extra, bs=2):
    return gce.main(["run", "--needs", str(needs), "--out-dir", str(out_dir),
                     "--codex-bin", str(fake), "--batch-size", str(bs), *extra])


def ledger(out_dir):
    return [json.loads(l) for l in open(Path(out_dir) / "ledger.jsonl", encoding="utf-8")]


def starts(out_dir):
    return [e for e in ledger(out_dir) if e["ev"] == "start"]


def calls(tmp):
    p = tmp / "calls.jsonl"
    return [json.loads(l) for l in open(p, encoding="utf-8")] if p.exists() else []


@pytest.fixture
def env(tmp_path):
    needs = tmp_path / "needs.jsonl"
    write_needs(needs, 8)
    return tmp_path, needs, tmp_path / "G"


# --- the needs list -----------------------------------------------------------------------
def make_placement(tmp: Path, rows, evidence=()):
    d = tmp / "pl"
    d.mkdir()
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.execute("CREATE TABLE headwords(word TEXT PRIMARY KEY, ns TEXT, state TEXT, origin TEXT,"
                " top TEXT, kind TEXT, n_seen INTEGER, by TEXT) WITHOUT ROWID")
    con.execute("CREATE TABLE evidence(word TEXT, arm TEXT, src TEXT, type TEXT, n INTEGER, base INTEGER,"
                " PRIMARY KEY(word, arm, src, type)) WITHOUT ROWID")
    for r in rows:
        con.execute("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", r)
    for e in evidence:
        con.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)", e)
    con.commit()
    con.close()
    (d / "manifest.json").write_text(json.dumps({"content_sha256": "abc123"}), encoding="utf-8")
    return d


def test_needs_are_the_unplaced_and_multiple_words_by_frequency_with_the_boundary_tie_kept(tmp_path):
    rows = [("あ%02d" % i, "N", "UNPLACED", None, "", "token", 100 - i // 3, "") for i in range(30)]
    rows += [("ほげ", "N", "DECIDED", "direct", "PLACE", "token", 5000, "definition"),     # decided: not needed
             ("複数", "N", "MULTIPLE", "direct", "PERSON,PLACE", "token", 200, "role@a+role@b"),
             ("証拠なし", "NP", "UNPLACED", None, "", "token", 150, ""),
             ("閾値未満", "N", "UNPLACED", None, "", "token", 150, "")]
    ev = [("閾値未満", "role", "jawiki", "PLACE", 2, None),
          ("証拠なし", "ns_vote", "jawiki", "N", 3, None),
          ("複数", "role", "jawiki", "PLACE", 9, None)]
    pl = make_placement(tmp_path, rows, ev)
    out = tmp_path / "needs.jsonl"
    meta = tmp_path / "needs.meta.json"
    assert gce.main(["needs", "--placement", str(pl), "--n", "10", "--out", str(out),
                     "--meta", str(meta)]) == 0
    got = [json.loads(l) for l in open(out, encoding="utf-8")]
    m = json.loads(meta.read_text(encoding="utf-8"))
    fs = [g["freq"] for g in got]
    assert fs == sorted(fs, reverse=True)                                   # frequency order
    assert all(g["state"] in ("UNPLACED", "MULTIPLE") for g in got)
    assert "ほげ" not in {g["word"] for g in got}
    # the 10th word has some frequency; EVERY word with that frequency is in the list
    boundary = fs[9]
    all_at_boundary = [r for r in rows if r[2] != "DECIDED" and r[6] == boundary]
    assert sum(1 for g in got if g["freq"] == boundary) == len(all_at_boundary)
    assert len(got) > 10 and m["total"] == len(got) and m["boundary_freq"] == boundary
    assert m["n_at_boundary"] == len(all_at_boundary) and m["last_freq"] == boundary
    assert m["content_sha256"] == "abc123"
    # the three evidence statuses
    st = {g["word"]: g["evidence_status"] for g in got}
    assert st["複数"] == "SPLIT" and st["閾値未満"] == "BELOW_THRESHOLD" and st["証拠なし"] == "NO_EVIDENCE"
    # inside one frequency the display order is the string order, and ranks run 1..N
    same = [g["word"] for g in got if g["freq"] == boundary]
    assert same == sorted(same)
    assert [g["rank"] for g in got] == list(range(1, len(got) + 1))


def test_needs_fewer_words_than_requested_lists_them_all(tmp_path):
    rows = [("あ%d" % i, "N", "UNPLACED", None, "", "token", 10 + i, "") for i in range(5)]
    pl = make_placement(tmp_path, rows)
    out, meta = tmp_path / "n.jsonl", tmp_path / "m.json"
    assert gce.main(["needs", "--placement", str(pl), "--n", "60000", "--out", str(out),
                     "--meta", str(meta)]) == 0
    assert len(open(out, encoding="utf-8").read().splitlines()) == 5


def test_the_selection_never_reads_test_data():
    src = (TREE / "tools/gen_coarse_evidence.py").read_text(encoding="utf-8")
    assert "tests/coarse_place/data" not in src
    import inspect
    assert list(inspect.signature(gce.select_needs).parameters) == ["placement", "n"]


# --- parallel -----------------------------------------------------------------------------
def max_overlap(cs):
    ev = sorted([(c["t0"], 1) for c in cs] + [(c["t1"], -1) for c in cs])
    cur = best = 0
    for _t, d in ev:
        cur += d
        best = max(best, cur)
    return best


def test_calls_run_in_parallel_up_to_the_slot_count(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=0.5)
    write_needs(needs, 16)
    t0 = time.time()
    assert run(tmp, needs, G, fake, "--slots", "4") == 0           # 8 batches
    wall = time.time() - t0
    cs = calls(tmp)
    assert len(cs) == 8
    assert 2 <= max_overlap(cs) <= 4
    assert wall < 8 * 0.5                                            # not one after another


def test_slots_are_capped_at_twelve(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    with pytest.raises(SystemExit):
        run(tmp, needs, G, fake, "--slots", "13")


# --- the ledger -------------------------------------------------------------------------
def test_each_attempt_has_a_start_and_an_end_with_the_required_keys_and_it_is_append_only(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--slots", "2", "--limit-batches", "2") == 0
    first = (G / "ledger.jsonl").read_text(encoding="utf-8")
    ev = ledger(G)
    assert [e["ev"] for e in ev].count("start") == 2 and [e["ev"] for e in ev].count("end") == 2
    for e in ev:
        if e["ev"] == "start":
            assert set(e) >= {"batch", "attempt", "words_sha", "words", "prompt_sha256", "argv", "t"}
            assert e["prompt_sha256"] and e["words"] and e["attempt"] == 1
            assert not any("WORDS_JSON" in a for a in e["argv"])          # the prompt is not in argv
        else:
            assert set(e) >= {"batch", "attempt", "exit", "sec", "status", "reason", "n_items",
                              "n_missing", "out_path", "out_sha256", "stderr_tail", "t"}
            assert e["status"] == "ok" and e["exit"] == 0 and e["n_items"] == 2
            assert e["out_sha256"] == gce.sha256_file(e["out_path"])
    # a second run keeps every earlier line, byte for byte, and only adds
    assert run(tmp, needs, G, fake, "--slots", "2") == 0
    assert (G / "ledger.jsonl").read_text(encoding="utf-8").startswith(first)


# --- resume ------------------------------------------------------------------------------
def test_a_second_run_after_everything_succeeded_calls_nothing(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake) == 0
    n = len(starts(G))
    assert n == 4 and len(calls(tmp)) == 4
    assert run(tmp, needs, G, fake) == 0
    assert len(starts(G)) == n and len(calls(tmp)) == n


def test_a_run_stopped_by_limit_batches_is_continued_with_the_rest_only(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "1") == 0
    done = {e["batch"] for e in starts(G)}
    assert len(done) == 1
    assert run(tmp, needs, G, fake) == 0
    all_batches = [e["batch"] for e in starts(G)]
    assert len(all_batches) == 4 and len(set(all_batches)) == 4         # nothing was called twice


def test_a_changed_needs_list_stops_with_exit_3_and_touches_nothing(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "2") == 0
    before = (G / "ledger.jsonl").read_text(encoding="utf-8")
    bfile = (G / "batches.json").read_text(encoding="utf-8")
    write_needs(needs, 8, prefix="別")                                    # a different list
    assert run(tmp, needs, G, fake) == 3
    assert (G / "ledger.jsonl").read_text(encoding="utf-8") == before
    assert (G / "batches.json").read_text(encoding="utf-8") == bfile
    assert len(calls(tmp)) == 2


def test_a_call_that_was_killed_before_its_end_counts_as_one_attempt(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "1") == 0
    # forge the trace of a killed run: a start with no end for the second batch
    batches = json.loads((G / "batches.json").read_text(encoding="utf-8"))["batches"]
    b2 = batches[1]
    words = [json.loads(l)["word"] for l in open(needs, encoding="utf-8")][2:4]
    with open(G / "ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"ev": "start", "batch": b2["id"], "attempt": 1, "words_sha": b2["words_sha"],
                            "words": words, "prompt_sha256": "x", "argv": [], "t": gce.now_utc()}) + "\n")
    assert run(tmp, needs, G, fake) == 0
    s2 = [e for e in starts(G) if e["batch"] == b2["id"]]
    assert [e["attempt"] for e in s2] == [1, 2]                           # the killed one + the retry


# --- retry ------------------------------------------------------------------------------
def test_a_batch_that_fails_twice_succeeds_on_the_third_try_and_always_failing_stops_at_three(env):
    tmp, needs, G = env
    fake = make_fake(tmp, fail_first={"語000": 2}, always_fail=["語002"])
    assert run(tmp, needs, G, fake, "--slots", "2") == 0
    by = {}
    for e in starts(G):
        by.setdefault(e["words"][0], []).append(e["attempt"])
    assert by["語000"] == [1, 2, 3]                                       # 2 failures, then ok
    assert by["語002"] == [1, 2, 3]                                       # never more than 3
    assert by["語004"] == [1] and by["語006"] == [1]
    s = gce.summarize(str(G))
    assert s["batches_failed"] == 1 and s["batches_ok"] == 3 and s["calls"] == 8
    assert s["failure_reasons"] == {"failed": 5}              # 2 + 3 failed attempts
    # a later run does not call the exhausted batch again
    assert run(tmp, needs, G, fake) == 0
    assert len(starts(G)) == 8


# --- the cap -----------------------------------------------------------------------------
def test_the_call_cap_is_exact_and_counts_the_remaining_batches(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    write_needs(needs, 20)                                                # 10 batches
    assert run(tmp, needs, G, fake, "--max-calls", "5", "--slots", "4") == 0
    assert len(starts(G)) == 5 and len(calls(tmp)) == 5
    s = gce.summarize(str(G))
    assert s["calls"] == 5 and s["not_run_cap"] == 5 and s["batches_ok"] == 5
    # the cap is a budget for the whole ledger: a second run cannot start another call
    assert run(tmp, needs, G, fake, "--max-calls", "5") == 0
    assert len(starts(G)) == 5
    # raising it lets the rest through
    assert run(tmp, needs, G, fake, "--max-calls", "10") == 0
    assert len(starts(G)) == 10


def test_retries_are_inside_the_cap(env):
    tmp, needs, G = env
    fake = make_fake(tmp, always_fail=["語000"])
    assert run(tmp, needs, G, fake, "--max-calls", "4", "--slots", "1") == 0
    assert len(starts(G)) == 4


# --- stdin -----------------------------------------------------------------------------
def test_the_child_gets_a_closed_stdin_even_when_the_parents_stdin_stays_open(env):
    tmp, needs, G = env
    fake = make_fake(tmp, check_stdin=True)
    p = subprocess.Popen([PYTHON, str(TREE / "tools/gen_coarse_evidence.py"), "run",
                          "--needs", str(needs), "--out-dir", str(G), "--codex-bin", str(fake),
                          "--batch-size", "4", "--slots", "2"],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        out, err = p.communicate(timeout=60)                            # stdin is never closed by us
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0, err
    assert not (tmp / "STDIN_NOT_CLOSED").exists()
    assert gce.summarize(str(G))["batches_ok"] == 2


# --- the required arguments -----------------------------------------------------------------
def test_default_low_keeps_the_preregistered_role_batches_and_schema_byte_identical(tmp_path):
    needs = TREE / "artifacts/w3-a7/current-r1/needs_role_v3.jsonl"
    before = TREE / "artifacts/w3-a7/current-r1/default_low_before"
    out_dir = tmp_path / "default_low"
    assert gce.main(["run", "--kind", "role", "--needs", str(needs), "--out-dir", str(out_dir),
                     "--codex-bin", "/bin/false", "--batch-size", "40", "--slots", "4",
                     "--max-calls", "624", "--max-retries", "2", "--limit-batches", "0"]) == 0
    assert (out_dir / "batches.json").read_bytes() == (before / "batches.json").read_bytes()
    assert (out_dir / "schema.json").read_bytes() == (before / "schema.json").read_bytes()
    assert json.loads((out_dir / "batches.json").read_text(encoding="utf-8"))["meta"]["effort"] == "low"


def test_role_prompt_is_byte_identical_to_the_frozen_v2(capsys):
    assert gce.main(["prompt", "--kind", "role"]) == 0
    assert capsys.readouterr().out.encode("utf-8") == (
        TREE / "artifacts/w3-a7/current-r1/prompt_role_v2.txt").read_bytes()


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_effort_is_in_runtime_manifest_ledger_summary_and_collected_rows(env, effort):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--effort", effort, "--limit-batches", "1",
               "--max-retries", "0") == 0
    meta = json.loads((G / "batches.json").read_text(encoding="utf-8"))["meta"]
    assert meta["effort"] == effort
    start = starts(G)[0]
    assert 'model_reasoning_effort="%s"' % effort in start["argv"]
    assert gce.summarize(str(G))["effort"] == effort
    out = tmp / "collected.jsonl"
    assert gce.main(["collect", "--out-dir", str(G), "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows and all(row["provenance"]["effort"] == effort for row in rows)


def test_an_out_dir_cannot_mix_effort_values(env, capsys):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--effort", "low", "--limit-batches", "1",
               "--max-retries", "0") == 0
    ledger_before = (G / "ledger.jsonl").read_bytes()
    batches_before = (G / "batches.json").read_bytes()
    assert run(tmp, needs, G, fake, "--effort", "medium", "--limit-batches", "1",
               "--max-retries", "0") == gce.EXIT_LIST_CHANGED
    assert '"state": "EFFORT_CHANGED"' in capsys.readouterr().out
    assert (G / "ledger.jsonl").read_bytes() == ledger_before
    assert (G / "batches.json").read_bytes() == batches_before
    assert len(calls(tmp)) == 1


def test_effort_rejects_values_outside_the_closed_cli_choices(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    with pytest.raises(SystemExit):
        run(tmp, needs, G, fake, "--effort", "urgent")


def test_the_model_effort_and_sandbox_are_in_the_command_and_codex_bin_is_required(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "1",
               "--extra-config", "mcp_servers.x.enabled=false") == 0
    argv = calls(tmp)[0]["argv"]
    assert argv[argv.index("-m") + 1] == "gpt-6-luna"
    assert 'model_reasoning_effort="low"' in argv
    assert argv[argv.index("-s") + 1] == "read-only"
    assert "--ephemeral" in argv and "--skip-git-repo-check" in argv and "--json" in argv
    assert "mcp_servers.x.enabled=false" in argv
    assert argv[argv.index("-C") + 1] == str(G / "work" / "empty")
    assert os.listdir(G / "work" / "empty") == []                        # the working dir stays empty
    assert json.loads((G / "schema.json").read_text(encoding="utf-8"))["required"] == ["items"]
    sl = starts(G)[0]["argv"]
    assert sl[sl.index("-m") + 1] == "gpt-6-luna" and 'model_reasoning_effort="low"' in sl
    with pytest.raises(SystemExit):                                       # no --codex-bin: a usage error
        gce.main(["run", "--needs", str(needs), "--out-dir", str(G)])


def test_a_codex_that_cannot_be_started_is_a_typed_failure_not_a_crash(env):
    tmp, needs, G = env
    assert run(tmp, needs, G, tmp / "no-such-codex", "--limit-batches", "1", "--max-retries", "0") == 0
    e = [x for x in ledger(G) if x["ev"] == "end"][0]
    assert e["status"] == "failed" and e["reason"] == "OSERROR"


# --- tool use, bad output ------------------------------------------------------------------
def test_a_tool_use_in_the_event_stream_rejects_the_attempt(env):
    tmp, needs, G = env
    fake = make_fake(tmp, tool_use=True)
    assert run(tmp, needs, G, fake, "--limit-batches", "1", "--max-retries", "0") == 0
    e = [x for x in ledger(G) if x["ev"] == "end"][0]
    assert e["status"] == "tool_use" and e["reason"].startswith("TOOL_USE")
    assert gce.summarize(str(G))["batches_ok"] == 0


def test_a_timeout_is_a_failed_attempt_and_the_process_is_killed(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=5)
    t0 = time.time()
    assert run(tmp, needs, G, fake, "--limit-batches", "1", "--max-retries", "0",
               "--timeout", "0.5") == 0
    assert time.time() - t0 < 4
    e = [x for x in ledger(G) if x["ev"] == "end"][0]
    assert e["status"] == "timeout"


def test_output_checks_duplicates_are_not_taken_foreign_words_dropped_nulls_are_abstentions(env):
    tmp, needs, G = env
    fake = make_fake(tmp, dup=["語001"], foreign=True, null=["語000"], missing=[])
    assert run(tmp, needs, G, fake, "--limit-batches", "1") == 0           # batch 0 = 語000, 語001
    out = tmp / "defs.jsonl"
    assert gce.main(["collect", "--out-dir", str(G), "--out", str(out)]) == 0
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    assert [r["word"] for r in rows] == ["語000"]                          # 語001 came back twice: not taken
    assert rows[0]["abstained"] is True and rows[0]["definition"] is None
    s = gce.summarize(str(G))
    assert s["words_dup_dropped"] == 1 and s["words_foreign_dropped"] == 1
    assert s["words_abstained"] == 1 and s["words_answered"] == 1 and s["words_missing"] == 0
    # a word that does not come back is `missing`, not an abstention
    set_cfg(tmp, missing=["語002"])
    assert run(tmp, needs, G, fake, "--limit-batches", "2") == 0
    s2 = gce.summarize(str(G))
    assert s2["words_missing"] == 1


# --- collect / summarize -------------------------------------------------------------------
def test_collect_is_deterministic_in_batch_order_with_the_origin_on_every_row(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--slots", "4") == 0
    a, b = tmp / "a.jsonl", tmp / "b.jsonl"
    assert gce.main(["collect", "--out-dir", str(G), "--out", str(a)]) == 0
    assert gce.main(["collect", "--out-dir", str(G), "--out", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
    rows = [json.loads(l) for l in open(a, encoding="utf-8")]
    assert [r["word"] for r in rows] == ["語%03d" % i for i in range(8)]   # the list's order
    for r in rows:
        p = r["provenance"]
        assert p["origin"] == "generated" and p["model"] == "gpt-6-luna" and p["effort"] == "low"
        assert re.match(r"b\d{5}_[0-9a-f]{12}$", p["batch_id"]) and p["attempt"] == 1 and p["out_sha256"]
        assert r["abstained"] is False and r["definition"].endswith("である。")


def test_collect_refuses_an_output_file_that_changed(env):
    tmp, needs, G = env
    fake = make_fake(tmp)
    assert run(tmp, needs, G, fake, "--limit-batches", "1") == 0
    raw = next((G / "raw").iterdir())
    raw.write_text('{"items": []}', encoding="utf-8")
    out = tmp / "d.jsonl"
    assert gce.main(["collect", "--out-dir", str(G), "--out", str(out)]) == 4
    assert out.read_text(encoding="utf-8") == ""


def test_summarize_numbers_come_from_the_ledger(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=0.2)
    assert run(tmp, needs, G, fake, "--slots", "2") == 0
    s = gce.summarize(str(G))
    assert s["calls"] == 4 and s["batches_total"] == 4 and s["batches_ok"] == 4
    assert s["ok_rate"] == 1.0 and s["words_requested"] == 8 and s["words_answered"] == 8
    assert s["calls_per_word_requested"] == 0.5 and s["calls_per_word_answered"] == 0.5
    assert s["wall_sec"] >= 0.2 and s["sum_call_sec"] >= 0.8
    assert s["model"] == "gpt-6-luna" and s["effort"] == "low" and s["not_run_cap"] == 0
    outp = tmp / "sum.json"
    assert gce.main(["summarize", "--out-dir", str(G), "--out", str(outp)]) == 0
    assert json.loads(outp.read_text(encoding="utf-8"))["calls"] == 4


# --- the prompt -----------------------------------------------------------------------------
def test_the_prompt_has_a_words_line_and_no_example_words():
    p = gce.build_prompt(["アア", "イイ"])
    assert p.splitlines()[-1] == 'WORDS_JSON: ["アア", "イイ"]'
    assert gce.prompt_template_sha256() == gce.sha256_text(gce.PROMPT_HEAD + gce.WORDS_PREFIX)
    fz = (TREE / "tests/coarse_place/data")
    terms = set()
    for name in ("typed_vocab", "unknown_words", "dev_vocab", "dev_unknown", "predicate_check"):
        for line in (fz / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            terms.add(json.loads(line)["term"])
    # the examples in the prompt are place-holders (<語>), never a real word: every bracketed
    # span is a place-holder, and none of them is a test word
    spans = re.findall(r"[<「]([^>」]*)[>」]", gce.PROMPT_HEAD)
    assert spans and all(sp.startswith("語") or sp.startswith("上位語") or "…" in sp or "語" in sp
                         for sp in spans), spans
    assert not [t for t in terms if t in spans]


def test_the_stop_signal_ends_the_run_with_an_interrupted_record(env):
    tmp, needs, G = env
    fake = make_fake(tmp, sleep=30)
    p = subprocess.Popen([PYTHON, str(TREE / "tools/gen_coarse_evidence.py"), "run",
                          "--needs", str(needs), "--out-dir", str(G), "--codex-bin", str(fake),
                          "--batch-size", "2", "--slots", "2"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.time() + 20
    while time.time() < deadline:
        if (G / "ledger.jsonl").exists() and len(starts(G)) >= 2:
            break
        time.sleep(0.1)
    p.terminate()
    out, err = p.communicate(timeout=20)
    assert p.returncode == 130, (out, err)
    ev = ledger(G)
    ends = [e for e in ev if e["ev"] == "end"]
    assert ends and all(e["status"] == "interrupted" for e in ends)
    assert len([e for e in ev if e["ev"] == "start"]) == len(ends)
    # the interrupted attempts count as calls; a later run retries them
    set_cfg(tmp)
    assert run(tmp, needs, G, fake, "--slots", "2") == 0
    assert gce.summarize(str(G))["batches_ok"] == 4
