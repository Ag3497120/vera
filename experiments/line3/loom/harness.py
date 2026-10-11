"""LOOM-g: the harness (docs/LINE3_LOOM_DESIGN.md 9.3, 9.4, 10.1).  The non-model steps around a loom run: prepare, drive, verify, output, score, record.

  python experiments/line3/loom/harness.py prepare --task I2-041 --mode record_only [--driver subagent]   # prints the call to make; writes nothing
  python experiments/line3/loom/harness.py run     --task I2-041 --mode record_only --driver scripted     # begin, drive, verify, score, results/*.json
  python experiments/line3/loom/harness.py run     --task I2-041 --mode record_only --driver api --model claude-haiku-4-5   # needs `anthropic` + a key
  python experiments/line3/loom/harness.py [--runs-dir DIR] note --subagent-transcript PATH [--requested-model haiku]     # after a subagent run (RECOMMENDED, L-LOOM-60)
  python experiments/line3/loom/harness.py note    RUN_DIR --free-text-file F [--agent loom-weaver-record-only]   # the by-hand path (RUN_DIR from `find`)
  python experiments/line3/loom/harness.py find    [--task I2-041]                                          # candidates only; refuses scripted folders; warns on >1
  python experiments/line3/loom/harness.py close   RUN_DIR
  python experiments/line3/loom/harness.py score   RUN_DIR [--driver subagent]                            # from the folder alone
  python experiments/line3/loom/harness.py [--results-dir DIR] summary                                    # hits_text | hit_record_text | excess_chars, footnote hits_words

FOLDERS (L-LOOM-64).  The OPERATOR folders `runs/` and `results/` are where the MCP server and the subagent / api drivers write; they never hold a scripted
run.  The scripted baseline (gold-informed scripts, not a measurement) lives in `baseline_scripted/{runs,results}/`, which is the default of `--driver scripted`
only.  `find` and `score` default to the operator folders.

DRIVERS.  `scripted`: the deterministic weaver of the core (SPEC below = one script per bank2 task, WRITTEN WITH THE GOLD KNOWN; the demo tasks use the worked example).
`api`: the L2 driver (verantyx/loom/driver.py) with a real client from `make_anthropic_client` (the `anthropic` SDK, imported only there; NOT run in
this build: no key, no network) or a fake one in tests.  `subagent`: run by the OPERATOR through the Claude Code subagent (a stub here: `run` explains
the steps and exits 2); the server the operator's session started wrote the run folder, and `score RUN_DIR` scores it from that folder alone.

THE SEQUENCE of `run` (design 9.4): begin the run (the mode comes from the task; the model id is testimony) -> harness_meta -> the driver ->
(free text is only ever hashed: `free_text_dropped`; a control's answer is `free_text_control`) -> `abandoned` if the run is not closed -> verify
(chain + replay) -> output (the emit row of a verified ledger) -> score -> `results/<base>.<mode>.<driver>.json`.  An existing run folder or results file
is never overwritten and never deleted: `run` refuses (use another `--runs-dir` / `--results-dir`).  The MODE `free_text` is the CONTROL (no loom,
the final text is scored; every result says `control: true`).  Nothing here reads the hidden bank; the gold is read from bank2.tsv by score.py only.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from verantyx.ledger_events import LedgerError                                  # noqa: E402
from verantyx.loom import driver as drv                                         # noqa: E402
from verantyx.loom import ledger as lg                                          # noqa: E402
from verantyx.loom import mcp as lm                                             # noqa: E402
from verantyx.loom.mcp import LoomServer, append_outside_row                     # noqa: E402
from verantyx.loom.ops import MODEL_OPS                                         # noqa: E402
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo                  # noqa: E402


def _load_sibling(name: str, fname: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


score = _load_sibling("loom_score", "score.py")

BANK = os.path.join(HERE, "tasks_bank2.jsonl")
RUNS_DIR = os.path.join(HERE, "runs")                       # the OPERATOR folders: what `.mcp.json` serves, what subagent / api runs write
RESULTS_DIR = os.path.join(HERE, "results")
BASELINE_DIR = os.path.join(HERE, "baseline_scripted")      # the scripted baseline: gold-informed scripts, never a model result
BASELINE_RUNS = os.path.join(BASELINE_DIR, "runs")
BASELINE_RESULTS = os.path.join(BASELINE_DIR, "results")
TOOL_PREFIX = "mcp__vera-loom__"                            # every tool of a loom subagent starts with this (T-LOOM-34)
BEGIN_TOOL = TOOL_PREFIX + "begin"
_RUN_ID_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
HITS_WORDS_FOOTNOTE = ("hits_words (the gold inside ONE record unit; `score.hits_words`) is false by construction for every multi-unit answer "
                       "(ハッシュ表, キューバの太陽, カールマルクス, 1981年); it is not a correctness column")
SCRIPTED_NOTE = ("SCRIPTED: the text is the script's own words (SPEC in harness.py), WRITTEN WITH THE GOLD KNOWN; its hit is not a measurement of anything "
                 "(a harness check only)")


def default_dirs(driver: str) -> tuple:
    """(runs dir, results dir) a driver writes to by default: the scripted baseline folder for `scripted`, the operator folders otherwise."""
    return (BASELINE_RUNS, BASELINE_RESULTS) if driver == "scripted" else (RUNS_DIR, RESULTS_DIR)
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")
DRIVERS = ("scripted", "api", "subagent")
META_DRIVER = {"scripted": "scripted", "api": "L2-api", "subagent": "L1-subagent"}
AGENT_OF_MODE = {"record_only": "loom-weaver-record-only", "constructed_allowed": "loom-weaver", "free_text": "loom-control"}
DEFAULT_API_MODEL = "claude-haiku-4-5"
API_DRIVER_NOTE = ("\n\n(Driver note: the run has already been begun for you. Skip the `begin` step; its result is in the first message. "
                   "Never pass run_id. When you are finished call `done`.)\n")
API_CONTROL_NOTE = "\n\n(Driver note: the run has already been begun for you. Skip the `begin` step; its result is in the first message.)\n"


class HarnessError(Exception):
    """A refusal of the harness.  `code` is a stable token (tests and scripts match it): `control_mismatch`, `agent_mismatch`, `not_an_l1_run`,
    `already_noted`, `transcript_*`, `run_folder_not_found`, ...; `str()` starts with it."""

    def __init__(self, msg: str, code: Optional[str] = None) -> None:
        super().__init__(("%s: %s" % (code, msg)) if code else msg)
        self.code = code


# ------------------------------------------------------------------------------------------------------------
# agent definitions (L1 files) and the bank
# ------------------------------------------------------------------------------------------------------------
def parse_agent_file(path: str) -> tuple:
    """(front matter dict, body) of a Claude Code subagent file: `---` / `key: value` lines / `---` / body.  `tools` is parsed to a list."""
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        raise HarnessError("%s: no front matter" % path)
    end = text.index("\n---\n", 4)
    meta: Dict[str, Any] = {}
    for ln in text[4:end].splitlines():
        if ln.strip():
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
    if "tools" in meta:
        meta["tools"] = [t.strip() for t in meta["tools"].split(",") if t.strip()]
    return meta, text[end + 5:]


def agent_file(label: str) -> str:
    return os.path.join(AGENTS_DIR, AGENT_OF_MODE[label] + ".md")


def agent_definition_sha(label: str) -> str:
    return hashlib.sha256(open(agent_file(label), "rb").read()).hexdigest()


def abs_row(row: dict) -> dict:
    """The task row as the in-process server needs it: relative corpus / fixture paths resolved against the repository root."""
    r = dict(row)
    for k in ("corpus", "fixture"):
        if k in r and not os.path.isabs(r[k]):
            r[k] = os.path.join(ROOT, r[k])
    return r


def label_of(row: dict) -> str:
    return score.CONTROL if row.get("control") == score.CONTROL else row["mode"]


def base_of(row: dict) -> str:
    return row.get("base") or row["task_id"].replace("/", "_")


def select_task(bank: Dict[str, dict], task: str, mode: Optional[str] = None) -> dict:
    """`task` is a bank task_id, a bank2 id / base (`I2-041`), or a demo task id; `mode` picks among the modes of a base."""
    rows = [r for r in bank.values() if task in (r["task_id"], base_of(r), r.get("bank2_id"))]
    if mode is not None:
        rows = [r for r in rows if label_of(r) == mode]
    if len(rows) != 1:
        raise HarnessError("task %r mode %r selects %d rows (%s)" % (task, mode, len(rows), ", ".join(sorted(r["task_id"] for r in rows)) or "none"))
    return rows[0]


def run_name(row: dict, driver: str, tag: str = "") -> str:
    """The run folder (<= 64 characters of the server's alphabet) and the stem of the results file: <base>.<mode>.<driver>[.tag]."""
    name = "%s.%s.%s%s" % (base_of(row), label_of(row), driver, ("." + tag) if tag else "")
    return name


def results_path(results_dir: str, row: dict, driver: str, tag: str = "") -> str:
    return os.path.join(results_dir, run_name(row, driver, tag) + ".json")


# ------------------------------------------------------------------------------------------------------------
# the scripted weaver: one script per bank2 task (data), the worked example for the demo tasks
# ------------------------------------------------------------------------------------------------------------
# kind: single | seq | pair | abstain.   single/seq: one cross per word, linked in the order given.   pair: (head, modifier): the modifier on the の arm
# of a cross whose centre is the head (「キューバの太陽」).   abstain: look the words up, then abstain(no_record).
SPEC: Dict[str, tuple] = {
    "I2-001": ("seq", "WORD", ["ハッシュ", "表"]),
    "I2-041": ("pair", "WORD", ["太陽", "キューバ"]),
    "I2-008": ("seq", "WORD", ["カール", "マルクス"]),
    "I2-034": ("seq", "WORD", ["1981", "年"]),
    "I2-013": ("single", "RUN", ["県社"]),
    "R2-I013": ("single", "WORD", ["ネパール"]),
    "I2-025": ("single", "WORD", ["青"]),
    "UF-001": ("abstain", ["衝突処理", "衝突"]),
    "UF-015": ("abstain", ["立案", "軍人"]),
    "R2-U003": ("abstain", ["貯水容量", "立方メートル"]),
}


def spec_text(spec: tuple) -> str:
    """What the script's weave reads as (also the answer a scripted CONTROL gives); 不明 for an abstaining script."""
    if spec[0] == "abstain":
        return "不明"
    if spec[0] == "pair":
        return spec[2][1] + "の" + spec[2][0]
    return "".join(spec[2])


class _Begun(ScriptedWeaver):
    """A ScriptedWeaver whose run the harness has begun already (the core's scripts call `begin()` themselves)."""

    def __init__(self, server: LoomServer, task_id: str, model: str, run_id: str, begin_result: dict) -> None:
        super().__init__(server, task_id, model, run_id)
        self.run_id = run_id
        self._begin_result = begin_result

    def begin(self) -> dict:
        return self._begin_result


def weave_spec(w: ScriptedWeaver, spec: tuple) -> dict:
    kind = spec[0]
    if kind == "abstain":
        for word in spec[1]:
            w.call("lookup", text=word, tier="any")
        return w.call("abstain", type="no_record")
    tier = spec[1]
    words = spec[2]
    for word in words:
        w.call("lookup", text=word, tier="any")
    uids = [w.call("add", text=word, kind="record", tier=tier).get("uid") for word in words]
    if kind == "pair":
        head, mod = uids
        cid = w.call("open_cross", tier=tier, L=2).get("cid")
        w.call("seat", cid=cid, seat="+x:0", uid=mod)
        w.call("seat", cid=cid, seat="centre", uid=head)
        w.call("link", cid=cid, pos=0)
    else:
        for pos, uid in enumerate(uids):
            cid = w.call("open_cross", tier=tier, L=1).get("cid")
            w.call("seat", cid=cid, seat="centre", uid=uid)
            w.call("link", cid=cid, pos=pos)
    return w.call("emit")


def drive_scripted(srv: LoomServer, row: dict, run_id: str, begin_result: dict, model: str) -> dict:
    label = label_of(row)
    base = row.get("bank2_id")
    w = _Begun(srv, row["task_id"], model, run_id, begin_result)
    if label == score.CONTROL:
        spec = SPEC.get(base or "")
        if spec is None:
            raise HarnessError("no scripted control for %r" % base)
        look = spec[1] if spec[0] == "abstain" else spec[2]
        for word in look:
            w.call("lookup", text=word, tier="any")
        return {"control_text": spec_text(spec)}
    if base in SPEC:
        weave_spec(w, SPEC[base])
    elif row["task_id"].startswith("demo/tokyo"):
        weave_tokyo(w)
    else:
        raise HarnessError("no scripted weave for task %r" % row["task_id"])
    return {}


# ------------------------------------------------------------------------------------------------------------
# the API driver (L2) side
# ------------------------------------------------------------------------------------------------------------
def make_anthropic_client():
    """The real client.  `anthropic` is imported HERE and only here (the loom package imports no SDK); credentials come from the environment or an
    `ant auth login` profile.  Not called in this build (no key, no network)."""
    try:
        import anthropic
    except ImportError as e:
        raise HarnessError("the `anthropic` SDK is not installed (pip install anthropic); the L2 driver is tested with a fake client only") from e
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("keyring_loom", os.path.join(os.path.dirname(os.path.abspath(__file__)), "keyring_loom.py"))
    _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)   # outside the loom package: it shells out to `security`
    resolve_api_key = _mod.resolve_api_key
    key = resolve_api_key()
    if not key:
        raise HarnessError("no API key: set ANTHROPIC_API_KEY or run `python tools/vera_api_key.py set` (macOS Keychain)")
    return anthropic.Anthropic(api_key=key)


def mcp_tool_objects(bank_path: str, runs_dir: str) -> List[Any]:
    """The tool objects (name, description, inputSchema) of the SAME FastMCP wrapper the MCP door serves."""
    m = lm.build(bank_path, runs_dir)
    if m is None:
        raise HarnessError("the MCP SDK is not installed (pip install \"mcp[cli]\")")
    return asyncio.run(m.list_tools())


def system_prompt(label: str) -> str:
    _, body = parse_agent_file(agent_file(label))
    return body + (API_CONTROL_NOTE if label == score.CONTROL else API_DRIVER_NOTE)


def drive_api(srv: LoomServer, row: dict, run_id: str, begin_result: dict, model: str, client: Any, mcp_tools: Sequence[Any],
              extra: Optional[dict] = None) -> dict:
    label = label_of(row)
    control = label == score.CONTROL
    choice, strict = drv.tool_choice_for(model)
    tools = drv.api_tools(mcp_tools, strict, control)
    sysp = system_prompt(label)
    res = drv.run_episode(client, srv, run_id, model, sysp, drv.first_message(begin_result), tools, tool_choice=choice,
                          max_turns=drv.MAX_TURNS[row["lang"]], control=control, extra=extra)
    rep = res.to_obj()
    rep["system_prompt_sha256"] = hashlib.sha256(sysp.encode("utf-8")).hexdigest()
    rep["tools"] = [t["name"] for t in tools]
    out = {"driver_report": rep, "response_models": res.response_models, "system_prompt_sha256": rep["system_prompt_sha256"]}
    if control:
        out["control_text"] = res.control_text
    return out


# ------------------------------------------------------------------------------------------------------------
# the results file
# ------------------------------------------------------------------------------------------------------------
def _rel(path: str) -> str:
    p = os.path.abspath(path)
    return os.path.relpath(p, ROOT) if p.startswith(ROOT + os.sep) else p


def result_object(rs: "score.RunScore", driver: str, run_dir: str, extra: Optional[dict] = None) -> dict:
    s = rs.to_obj()
    facts = s.pop("facts") or {}
    ann = s.pop("annotated")
    cnote = None
    if rs.control:
        cnote = "FREE-TEXT CONTROL: no loom; the answer line of the final text is the output; for comparison with the loom only"
        if driver == "scripted":
            cnote += ". " + SCRIPTED_NOTE
    obj = {
        "schema": "loom-result-1", "task_id": rs.task_id, "base": rs.base, "mode": rs.mode, "driver": driver, "control": rs.control,
        "control_note": cnote, "model_result": driver != "scripted",
        "answer_view": {"hits_text": s.get("hits_text"), "hit_record_text": s.get("hit_record_text"), "excess_chars": s.get("excess_chars")},
        "footnotes": {"hits_words": HITS_WORDS_FOOTNOTE},
        "ledger": _rel(os.path.join(run_dir, "ops.jsonl")), "ledger_head": facts.get("head"),
        "output_text": rs.text, "annotated": ann, "score": s,
        "op_counts": {"by_op": facts.get("ops_by_name"), "by_class": facts.get("ops_by_class"), "model_rows": facts.get("model_rows"),
                      "rows": facts.get("rows"), "emit_attempts": facts.get("emit_attempts")},
        "refusals": facts.get("refusals"), "self_corrections": facts.get("self_corrections"),
        "free_text_dropped": facts.get("free_text_dropped"), "closing": facts.get("closing"), "abandoned": facts.get("abandoned"),
        "harness_meta": facts.get("harness_meta"), "declared_model": facts.get("declared_model"),
        "wall": {"ledger_ns": facts.get("ledger_wall_ns")},
    }
    tc = os.path.join(str(run_dir), "transcript_check.json")
    obj["t_loom_34"] = "unchecked"
    if os.path.isfile(tc):
        with open(tc, encoding="utf-8") as f:
            chk = json.load(f)
        obj["transcript_check"] = chk
        obj["t_loom_34"] = chk.get("t_loom_34", "unchecked")
    if extra:
        for k, v in extra.items():
            if k == "wall_driver_ns":
                obj["wall"]["driver_ns"] = v
            else:
                obj[k] = v
    return obj


def write_result(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        raise HarnessError("results file exists (never overwritten): %s" % path)
    with open(path, "x", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n")


def score_folder(run_dir: str, driver: str, bank: Dict[str, dict], gold: Dict[str, dict], results_dir: str, tag: str = "",
                 extra: Optional[dict] = None, head: Optional[str] = None, corpus_path: Optional[str] = None) -> tuple:
    """verify -> output -> score from the folder ALONE, then the results file.  The same path for every driver."""
    rs = score.score_run(run_dir, bank, gold, head=head, corpus_path=corpus_path)
    row = bank.get(rs.task_id)
    if row is None:
        raise HarnessError("task %r of %s is not in the bank" % (rs.task_id, run_dir))
    obj = result_object(rs, driver, run_dir, extra)
    path = results_path(results_dir, row, driver, tag)
    write_result(path, obj)
    return rs, path, obj


# ------------------------------------------------------------------------------------------------------------
# run / prepare / note / close
# ------------------------------------------------------------------------------------------------------------
def prepare(row: dict, driver: str, model: Optional[str] = None) -> dict:
    """What the operator (or the harness) does for this task.  Writes nothing."""
    label = label_of(row)
    agent = AGENT_OF_MODE[label]
    out = {"task_id": row["task_id"], "mode": label, "driver": driver, "text": row["text"], "agent": agent,
           "agent_definition_sha256": agent_definition_sha(label), "control": label == score.CONTROL}
    if driver == "subagent":
        out["agent_call"] = {"tool": "Agent", "subagent_type": agent, "model": model or "haiku", "prompt": "task_id: %s" % row["task_id"]}
        out["after"] = [
            "do NOT read the subagent's final message back to the user and do not quote it; find its transcript: ~/.claude/projects/<slug>/<session>/subagents/agent-<agentId>.jsonl "
            "(the agentId is in the Agent tool's result; <slug> is the session's working directory with / replaced by -)",
            "python experiments/line3/loom/harness.py note --subagent-transcript PATH --requested-model %s   (prints RUN_DIR; the run comes from the begin result inside "
            "the transcript; the control / agent come from the bank; every tool name is checked against mcp__vera-loom__; exit 1 on a violation)" % (model or "haiku"),
            "python experiments/line3/loom/harness.py close RUN_DIR%s" % (" --reason control_free_text" if label == score.CONTROL else ""),
            "python experiments/line3/loom/harness.py score RUN_DIR --driver subagent",
        ]
        out["by_hand"] = "without a transcript: `harness.py find --task %s --mode %s`, then `note RUN_DIR --free-text-file F`" % (row.get("bank2_id") or row["task_id"], label)
        out["restart_needed"] = "the project's .mcp.json and .claude/agents/*.md load at session start: restart Claude Code once (docs/LOOM_SANDBOX.md)"
    else:
        out["command"] = "python experiments/line3/loom/harness.py run --task %s --mode %s --driver %s%s" % (
            row.get("bank2_id") or row["task_id"], label, driver, (" --model " + (model or DEFAULT_API_MODEL)) if driver == "api" else "")
    return out


def run(row: dict, driver: str, *, bank_path: str, bank: Dict[str, dict], gold: Dict[str, dict], runs_dir: str, results_dir: str, model: Optional[str] = None,
        client: Any = None, mcp_tools: Optional[Sequence[Any]] = None, tag: str = "", extra_api: Optional[dict] = None) -> tuple:
    """begin -> harness_meta -> driver -> free text -> abandoned -> verify -> output -> score -> results file.  Returns (RunScore, results path, object)."""
    if driver == "subagent":
        raise HarnessError("the subagent driver is run by the operator through the Claude Code Agent tool (the harness cannot call it): see "
                           "`prepare --driver subagent`, then `note`, `close`, `score RUN_DIR`")
    label = label_of(row)
    rpath = results_path(results_dir, row, driver, tag)
    if os.path.exists(rpath):
        raise HarnessError("results file exists (never overwritten): %s" % rpath)
    name = run_name(row, driver, tag)
    if driver == "api":
        model = model or DEFAULT_API_MODEL
        if client is None:
            client = make_anthropic_client()
        if mcp_tools is None:
            mcp_tools = mcp_tool_objects(bank_path, runs_dir)
    else:
        model = model or "scripted-weaver"
    srv = LoomServer([abs_row(row)], runs_dir)
    b = srv.begin(row["task_id"], model, name)
    if not b.get("ok"):
        raise HarnessError("begin refused: %s" % json.dumps(b, ensure_ascii=False, sort_keys=True))
    meta = {"driver": META_DRIVER[driver], "requested_model": model}
    if driver == "api":
        meta["agent_definition_sha"] = hashlib.sha256(system_prompt(label).encode("utf-8")).hexdigest()
    srv.harness(name, "harness_meta", meta)
    t0 = time.monotonic_ns()
    if driver == "scripted":
        rep = drive_scripted(srv, row, name, b, model)
    elif driver == "api":
        rep = drive_api(srv, row, name, b, model, client, mcp_tools, extra_api)
        if rep.get("response_models"):
            srv.harness(name, "harness_meta", {"response_model": rep["response_models"][0]})
    else:
        raise HarnessError("unknown driver %r" % driver)
    wall = time.monotonic_ns() - t0
    control_text = rep.pop("control_text", None)
    if label == score.CONTROL:
        if control_text is not None:
            raw = control_text.encode("utf-8")
            srv.harness(name, "free_text_control", {"sha256": hashlib.sha256(raw).hexdigest(), "chars": len(control_text), "text": control_text})
    if srv.closed(name) is None:                                   # every ledger ends closed; a control never emits, its close is `abandoned control_free_text`
        srv.harness(name, "abandoned", {"reason": "control_free_text" if label == score.CONTROL else "no_close"})
    extra = {"wall_driver_ns": wall}
    if rep:
        extra["driver_report"] = rep.get("driver_report", rep)
    return score_folder(srv.run_dir(name), driver, bank, gold, results_dir, tag, extra)


# ------------------------------------------------------------------------------------------------------------
# the subagent transcript (L-LOOM-60): the mechanical path of an L1 run
# ------------------------------------------------------------------------------------------------------------
TRANSCRIPT_PIN = """WHAT IS PARSED (best effort: Claude Code's subagent transcript is not a documented format; pinned as seen on 2.1.x, anything else is a typed refusal):
  the file is UTF-8 JSON Lines; every line is an object.  Rows whose `type` is `user` or `assistant` (others: attachment, ... are ignored, `isMeta` user rows too)
  carry `message` = {role == the row type, content = a string or a list of blocks {type: ...}}; an assistant message also has `model`.  Blocks read:
  `text` {text}, `tool_use` {id, name, input}, `tool_result` {tool_use_id, content = a string or a list of {type: text, text}}.  One API message may be split over
  several assistant rows (one block each).  The FINAL TEXT is the `text` blocks of the assistant rows after the last user row, joined with a newline; a transcript
  whose last assistant block is a tool_use, or that has no assistant text, is refused.  The RUN ID is `run_id` of the JSON in the tool_result of the one
  successful `mcp__vera-loom__begin` call."""


def _text_of_result(content: Any) -> Optional[str]:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    return None


def parse_subagent_transcript(path: str) -> dict:
    """The facts of a subagent transcript (see TRANSCRIPT_PIN): sha256 of the file bytes, the tool names called, the begin call (run_id, task_id), the final
    assistant text, the response models.  Raises HarnessError `transcript_*` if the shape is not the pinned one."""
    try:
        with open(path, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise HarnessError("cannot read %s (%s)" % (path, type(e).__name__), "transcript_unreadable") from e
    rows: List[dict] = []
    for n, ln in enumerate(text.splitlines(), 1):
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError as e:
            raise HarnessError("line %d is not JSON" % n, "transcript_shape") from e
        if not isinstance(r, dict):
            raise HarnessError("line %d is not an object" % n, "transcript_shape")
        rows.append(r)
    if not rows:
        raise HarnessError("the transcript is empty", "transcript_shape")
    turns: List[tuple] = []                                            # (role, blocks, model)
    for r in rows:
        t = r.get("type")
        if t not in ("user", "assistant") or (t == "user" and r.get("isMeta")):
            continue
        m = r.get("message")
        if not isinstance(m, dict) or m.get("role") != t:
            raise HarnessError("a %s row has no message with role %s" % (t, t), "transcript_shape")
        c = m.get("content")
        if isinstance(c, str):
            blocks = [{"type": "text", "text": c}]
        elif isinstance(c, list) and all(isinstance(b, dict) and isinstance(b.get("type"), str) for b in c):
            blocks = c
        else:
            raise HarnessError("a %s message has content of an unknown shape" % t, "transcript_shape")
        model = m.get("model") if t == "assistant" else None
        turns.append((t, blocks, model if isinstance(model, str) else None))
    if not any(t[0] == "assistant" for t in turns):
        raise HarnessError("no assistant row", "transcript_shape")
    uses: List[dict] = []
    results: Dict[str, Optional[str]] = {}
    models: List[str] = []
    for role, blocks, model in turns:
        if model and model not in models and not model.startswith("<"):
            models.append(model)
        for b in blocks:
            if role == "assistant" and b["type"] == "tool_use":
                if not isinstance(b.get("name"), str) or not isinstance(b.get("id"), str):
                    raise HarnessError("a tool_use block without a string id / name", "transcript_shape")
                uses.append(b)
            elif role == "user" and b["type"] == "tool_result":
                if not isinstance(b.get("tool_use_id"), str):
                    raise HarnessError("a tool_result block without tool_use_id", "transcript_shape")
                results[b["tool_use_id"]] = _text_of_result(b.get("content"))
    last_user = max((i for i, t in enumerate(turns) if t[0] == "user"), default=-1)
    tail = turns[last_user + 1:]
    if not tail:
        raise HarnessError("the transcript ends with a user row: the subagent did not finish", "transcript_unfinished")
    if any(b["type"] == "tool_use" for t in tail for b in t[1]):
        raise HarnessError("the last assistant row is a tool call: the subagent did not finish", "transcript_unfinished")
    final = "\n".join(b["text"] for t in tail for b in t[1] if b["type"] == "text" and isinstance(b.get("text"), str))
    if not final.strip():
        raise HarnessError("the subagent's last turn has no text", "transcript_no_final_text")
    begins = []
    for u in uses:
        if u["name"] != BEGIN_TOOL:
            continue
        payload = None
        try:
            payload = json.loads(results.get(u["id"]) or "")
        except ValueError:
            pass
        if isinstance(payload, dict) and payload.get("ok") is True and isinstance(payload.get("run_id"), str):
            inp = u.get("input") if isinstance(u.get("input"), dict) else {}
            begins.append({"run_id": payload["run_id"], "task_id": inp.get("task_id"), "model": inp.get("model")})
    if not begins:
        raise HarnessError("no successful %s call with a run_id in its result" % BEGIN_TOOL, "transcript_no_begin")
    if len(begins) > 1:
        raise HarnessError("%d successful begin calls (%s): one subagent, one run" % (len(begins), ", ".join(b["run_id"] for b in begins)), "transcript_multiple_begins")
    names = [u["name"] for u in uses]
    return {"sha256": hashlib.sha256(raw).hexdigest(), "rows": len(rows), "tool_names": names, "begin": begins[0], "final_text": final, "models": models}


def locate_run(tr: dict, runs_dir: str) -> str:
    """The run folder of a parsed transcript: `runs_dir/<run_id>` (the id the server returned to the subagent), checked against row 0 of its ledger."""
    rid = tr["begin"]["run_id"]
    if not _RUN_ID_RX.match(rid) or rid in (".", ".."):
        raise HarnessError("the run id %r is not a run id" % rid, "transcript_shape")
    d = os.path.join(runs_dir, rid)
    p = os.path.join(d, "ops.jsonl")
    if not os.path.isfile(p):
        raise HarnessError("no run folder %s (is --runs-dir the folder the server wrote to?)" % d, "run_folder_not_found")
    with open(p, encoding="utf-8") as f:
        first = json.loads(f.readline())
    if (first.get("result") or {}).get("run_id") != rid:
        raise HarnessError("row 0 of %s does not name run %s" % (p, rid), "run_folder_not_found")
    tid = tr["begin"].get("task_id")
    if isinstance(tid, str) and first["args"].get("task_id") != tid:
        raise HarnessError("the transcript began %r, the ledger says %r" % (tid, first["args"].get("task_id")), "transcript_task_mismatch")
    return d


def transcript_check(tr: dict, ledger_rows: Sequence[dict], transcript_path: str, expected_agent: str) -> dict:
    """T-LOOM-34, automatic.  Every `tool_use` of the subagent must be a loom tool (name starts with `mcp__vera-loom__`); and the ledger cannot hold more
    model rows than the subagent made loom calls (each call writes at most one row), else somebody else (the parent session) called the loom on this run.
    Written next to the ledger as `transcript_check.json` (outside the chain, like meta.json: testimony)."""
    names = tr["tool_names"]
    loom = [n for n in names if n.startswith(TOOL_PREFIX)]
    non_loom = sorted(set(n for n in names if not n.startswith(TOOL_PREFIX)))
    model_rows = sum(1 for r in ledger_rows if r.get("actor") == "model")
    viol = ["non_loom_tool:%s" % n for n in non_loom]
    if model_rows > len(loom):
        viol.append("ledger_rows_not_in_transcript:%d model rows, %d loom calls" % (model_rows, len(loom)))
    agent_type = None
    mp = transcript_path[:-len(".jsonl")] + ".meta.json" if transcript_path.endswith(".jsonl") else None
    if mp and os.path.isfile(mp):
        try:
            with open(mp, encoding="utf-8") as f:
                at = json.load(f).get("agentType")
            agent_type = at if isinstance(at, str) else None
        except (OSError, ValueError):
            agent_type = None
    if agent_type is not None and agent_type != expected_agent:
        viol.append("agent_type:%s (expected %s)" % (agent_type, expected_agent))
    return {"schema": "loom-transcript-check-1", "t_loom_34": "violations" if viol else "pass", "violations": viol,
            "transcript_sha256": tr["sha256"], "transcript_rows": tr["rows"], "tool_uses": len(names), "loom_calls": len(loom),
            "non_loom_tools": non_loom, "ledger_model_rows": model_rows, "agent_type": agent_type, "response_models": tr["models"],
            "final_text_sha256": hashlib.sha256(tr["final_text"].encode("utf-8")).hexdigest(), "final_text_chars": len(tr["final_text"])}


def note_ex(run_dir: Optional[str], free_text_file: Optional[str], control: bool, agent: Optional[str], requested_model: Optional[str],
            driver: str = "L1-subagent", *, bank: Optional[Dict[str, dict]] = None, transcript: Optional[str] = None,
            runs_dir: Optional[str] = None) -> tuple:
    """The harness rows after a subagent run: harness_meta (driver, requested model, the agent file's sha, and with a transcript the provider's response
    model) and the final message as `free_text_dropped` (sha256 + length only) or, for the CONTROL, `free_text_control` (the text IS the output).

    What is a control, and which agent, comes from the LEDGER'S ROW 0 and the BANK, never from the caller (L-LOOM-61): `control=True` on a run that is not a
    control, or `agent` other than the bank's agent for the run's mode, is a typed refusal (`control_mismatch`, `agent_mismatch`) and nothing is written; so
    the text of a weaver run is never stored.  A folder that already has a `harness_meta` driver row (scripted, api, or an earlier note) is refused.
    With `transcript` the run folder, the final text and the T-LOOM-34 check come from the transcript (RUN_DIR may be omitted).  Returns (rows, check|None)."""
    bank = bank if bank is not None else score.load_bank(BANK)
    tr = None
    if transcript:
        if free_text_file:
            raise HarnessError("--subagent-transcript supplies the final text; do not also pass --free-text-file", "note_conflict")
        tr = parse_subagent_transcript(transcript)
        located = locate_run(tr, runs_dir or RUNS_DIR)
        if run_dir is not None and os.path.realpath(run_dir) != os.path.realpath(located):
            raise HarnessError("RUN_DIR %s is not the run the transcript began (%s)" % (run_dir, located), "run_dir_mismatch")
        run_dir = located
    if run_dir is None:
        raise HarnessError("give RUN_DIR or --subagent-transcript", "note_no_run")
    if not os.path.isfile(os.path.join(str(run_dir), "ops.jsonl")):
        raise HarnessError("%s has no ops.jsonl" % run_dir, "run_folder_not_found")
    lines, _ = lg.read_lines(run_dir)
    ledger_rows = [json.loads(ln) for ln in lines]
    task_id = ledger_rows[0]["args"].get("task_id")
    row = bank.get(task_id or "")
    if row is None:
        raise HarnessError("row 0 of %s names task %r, which is not in the bank" % (run_dir, task_id), "task_not_in_bank")
    label = label_of(row)
    is_control = label == score.CONTROL
    expected_agent = AGENT_OF_MODE[label]
    if control and not is_control:
        raise HarnessError("--control given, but %s is a %s run (task %s), not a control" % (run_dir, label, task_id), "control_mismatch")
    if agent is not None and agent != expected_agent:
        raise HarnessError("--agent %s, but a %s run is driven by %s" % (agent, label, expected_agent), "agent_mismatch")
    prior = [r["args"].get("driver") for r in ledger_rows if r["op"] == "harness_meta" and "driver" in r["args"]]
    if prior:
        raise HarnessError("%s already has a harness_meta driver row (%s); only an un-noted operator folder can be noted" % (run_dir, prior[0]),
                           "already_noted" if prior[0] == driver else "not_an_l1_run")
    if any(r["op"] in ("free_text_dropped", "free_text_control") for r in ledger_rows):
        raise HarnessError("%s already has a free-text row" % run_dir, "already_noted")
    chk_path = os.path.join(str(run_dir), "transcript_check.json")
    if tr and os.path.exists(chk_path):
        raise HarnessError("%s exists (never overwritten)" % chk_path, "already_noted")
    meta = {"driver": driver, "agent_definition_sha": agent_definition_sha(label)}
    if requested_model:
        meta["requested_model"] = requested_model
    check = None
    raw = None
    if tr:
        check = transcript_check(tr, ledger_rows, transcript, expected_agent)
        if tr["models"]:
            meta["response_model"] = tr["models"][0]
        raw = tr["final_text"].encode("utf-8")
    elif free_text_file:
        with open(free_text_file, "rb") as f:
            raw = f.read()
    done: List[str] = []
    append_outside_row(run_dir, "harness", "harness_meta", meta)
    done.append("harness_meta")
    if raw is not None:
        text = raw.decode("utf-8", errors="replace")
        a: Dict[str, Any] = {"sha256": hashlib.sha256(raw).hexdigest(), "chars": len(text)}
        if is_control:
            a["text"] = text
        append_outside_row(run_dir, "harness", "free_text_control" if is_control else "free_text_dropped", a)
        done.append("free_text_control" if is_control else "free_text_dropped")
    if check is not None:
        with open(chk_path, "x", encoding="utf-8") as f:
            f.write(json.dumps(check, ensure_ascii=False, sort_keys=True, indent=1) + "\n")
        check = dict(check, run_dir=str(run_dir))
    return done, check


def note(run_dir: Optional[str], free_text_file: Optional[str], control: bool, agent: Optional[str], requested_model: Optional[str],
         driver: str = "L1-subagent", **kw: Any) -> List[str]:
    """`note_ex` without the transcript check: the list of rows written."""
    return note_ex(run_dir, free_text_file, control, agent, requested_model, driver, **kw)[0]


def find_runs(bank: Dict[str, dict], runs_dir: str, results_dir: str, task: Optional[str] = None, mode: Optional[str] = None,
              driver: str = "subagent", refused: Optional[List[dict]] = None) -> List[dict]:
    """The CANDIDATE run folders of an L1 run under `runs_dir`: row 0 names a bank task (optionally one task / mode), newest first, with whether they are
    closed, noted and whether a `driver` results file exists already.  Folders whose ledger carries a `harness_meta` driver other than `L1-subagent` (scripted,
    L2-api) are REFUSED: they are never returned (they go to `refused` if a list is passed).  It VERIFIES nothing (score does).  This is the by-hand fallback;
    with a transcript, `note --subagent-transcript` names the run from the begin result and needs no search.  A caller that finds more than one unscored
    candidate must not pick the newest (the CLI warns and exits 3)."""
    out: List[dict] = []
    if not os.path.isdir(runs_dir):
        return out
    for d in os.listdir(runs_dir):
        p = os.path.join(runs_dir, d, "ops.jsonl")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()
            rows = [json.loads(ln) for ln in lines]
            first, last = rows[0], rows[-1]
        except (ValueError, IndexError):
            continue
        row = bank.get(first["args"].get("task_id", ""))
        if row is None or (task is not None and task not in (row["task_id"], base_of(row), row.get("bank2_id"))) or \
                (mode is not None and label_of(row) != mode):
            continue
        drivers = [r["args"]["driver"] for r in rows if r["op"] == "harness_meta" and "driver" in r["args"]]
        if drivers and drivers[0] != "L1-subagent":
            if refused is not None:
                refused.append({"run_dir": os.path.join(runs_dir, d), "task_id": row["task_id"], "driver": drivers[0]})
            continue
        out.append({"run_dir": os.path.join(runs_dir, d), "task_id": row["task_id"], "mode": label_of(row), "rows": len(lines),
                    "declared_model": first["args"].get("model"), "scored": os.path.exists(results_path(results_dir, row, driver)),
                    "noted": bool(drivers), "mtime_ns": os.stat(p).st_mtime_ns, "last_op": last["op"]})
    return sorted(out, key=lambda r: (-r["mtime_ns"], r["run_dir"]))


def summary_table(results_dir: str) -> str:
    """One line per results file: hits_text (primary), hit_record_text and excess_chars beside it, then the footnote on hits_words."""
    yn = lambda v: "-" if v is None else ("Y" if v else "N")
    lines = ["%-34s %-20s %-9s %-18s %-9s %-15s %s" % ("task", "mode", "driver", "status", "hits_text", "hit_record_text", "excess_chars")]
    if os.path.isdir(results_dir):
        for fn in sorted(os.listdir(results_dir)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(results_dir, fn), encoding="utf-8") as f:
                o = json.load(f)
            v = o.get("answer_view") or {}
            lines.append("%-34s %-20s %-9s %-18s %-9s %-15s %s" % (o["task_id"], o["mode"], o["driver"], o["score"]["status"], yn(v.get("hits_text")),
                                                                  yn(v.get("hit_record_text")), "-" if v.get("excess_chars") is None else v["excess_chars"]))
    lines.append("")
    lines.append("hits_text is the primary column.  (1) " + HITS_WORDS_FOOTNOTE + ".")
    return "\n".join(lines)


def close(run_dir: str, reason: str = "no_close") -> str:
    rep = lg.replay(run_dir, None)
    if not rep.identical or rep.run is None:
        raise HarnessError("the run does not replay (%s)" % (rep.mismatch or rep.first_diff))
    if rep.run.state.closed is not None:
        return "closed: %s" % json.dumps(rep.run.state.closed)
    append_outside_row(run_dir, "harness", "abandoned", {"reason": reason})
    return "closed: abandoned"


# ------------------------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------------------------
def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="harness", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default=BANK)
    ap.add_argument("--runs-dir", dest="runs_dir", default=None, help="default: the operator folder runs/ (the scripted driver: baseline_scripted/runs/)")
    ap.add_argument("--results-dir", dest="results_dir", default=None, help="default: the operator folder results/ (the scripted driver: baseline_scripted/results/)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list", help="the tasks of the bank")
    p = sub.add_parser("prepare")
    p.add_argument("--task", required=True)
    p.add_argument("--mode", default=None, help="record_only | constructed_allowed | free_text")
    p.add_argument("--driver", choices=DRIVERS, default="subagent")
    p.add_argument("--model", default=None)
    p = sub.add_parser("run")
    p.add_argument("--task", required=True)
    p.add_argument("--mode", default=None)
    p.add_argument("--driver", choices=DRIVERS, required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--tag", default="")
    p = sub.add_parser("note", help="harness rows after a subagent run; the control / agent come from the bank, a mismatching flag is refused")
    p.add_argument("run_dir", nargs="?", default=None, help="omit with --subagent-transcript (the run is named by the begin result in the transcript)")
    p.add_argument("--free-text-file", dest="free_text_file", default=None)
    p.add_argument("--subagent-transcript", dest="subagent_transcript", default=None, help="~/.claude/projects/<slug>/<session>/subagents/agent-<id>.jsonl")
    p.add_argument("--control", action="store_true", help="optional; refused unless the run IS a control")
    p.add_argument("--agent", default=None, help="optional; refused unless it is the bank's agent for the run's mode")
    p.add_argument("--requested-model", dest="requested_model", default=None)
    p = sub.add_parser("find", help="the run folders under --runs-dir that belong to a task (newest first)")
    p.add_argument("--task", default=None)
    p.add_argument("--mode", default=None)
    p = sub.add_parser("summary", help="table of a results folder: hits_text | hit_record_text | excess_chars (+ footnote on hits_words)")
    p = sub.add_parser("close")
    p.add_argument("run_dir")
    p.add_argument("--reason", default="no_close")
    p = sub.add_parser("score")
    p.add_argument("run_dir")
    p.add_argument("--driver", choices=DRIVERS, default="subagent")
    p.add_argument("--tag", default="")
    p.add_argument("--head", default=None, help="the HEAD sha pinned outside the folder")
    p.add_argument("--corpus", default=None, help="the corpus file, when the path in the run's meta.json no longer exists (the repository moved)")
    a = ap.parse_args(argv)
    d_runs, d_res = default_dirs(getattr(a, "driver", None) if a.cmd in ("run", "score") else "operator")
    a.runs_dir = a.runs_dir or d_runs
    a.results_dir = a.results_dir or d_res
    bank = score.load_bank(a.bank)
    try:
        if a.cmd == "list":
            for r in bank.values():
                print("%-40s %-20s %s" % (r["task_id"], label_of(r), r["text"]))
            return 0
        if a.cmd == "prepare":
            print(json.dumps(prepare(select_task(bank, a.task, a.mode), a.driver, a.model), ensure_ascii=False, sort_keys=True, indent=1))
            return 0
        if a.cmd == "run":
            row = select_task(bank, a.task, a.mode)
            if a.driver == "subagent":
                print(json.dumps(prepare(row, "subagent", a.model), ensure_ascii=False, sort_keys=True, indent=1))
                print("the subagent driver is run by the operator through the Claude Code Agent tool; this harness cannot call it.", file=sys.stderr)
                return 2
            rs, path, _ = run(row, a.driver, bank_path=a.bank, bank=bank, gold=score.load_gold(), runs_dir=a.runs_dir, results_dir=a.results_dir,
                              model=a.model, tag=a.tag)
            print("%s %s %s -> %s" % (rs.task_id, rs.status, json.dumps(rs.text, ensure_ascii=False), _rel(path)))
            return 0
        if a.cmd == "find":
            refused: List[dict] = []
            found = find_runs(bank, a.runs_dir, a.results_dir, a.task, a.mode, refused=refused)
            for r in found:
                print("%s  %s  %s  rows=%d  last=%s  %s%s" % (r["run_dir"], r["task_id"], r["mode"], r["rows"], r["last_op"], "scored" if r["scored"] else "unscored",
                                                         "  noted" if r["noted"] else ""))
            for r in refused:
                print("harness: refused %s (%s): written by the %s driver, not an operator L1 run" % (r["run_dir"], r["task_id"], r["driver"]), file=sys.stderr)
            open_ = [r for r in found if not r["scored"]]
            if len(open_) > 1:
                print("harness: AMBIGUOUS: %d unscored candidates%s; the newest is NOT picked.  Name the run by its transcript instead: "
                      "note --subagent-transcript PATH" % (len(open_), (" for task %s" % a.task) if a.task else ""), file=sys.stderr)
                return 3
            return 0
        if a.cmd == "summary":
            print(summary_table(a.results_dir))
            return 0
        if a.cmd == "note":
            done, check = note_ex(a.run_dir, a.free_text_file, a.control, a.agent, a.requested_model, bank=bank, transcript=a.subagent_transcript,
                                  runs_dir=a.runs_dir)
            if check is not None:
                print("RUN_DIR=%s" % check["run_dir"])
            print(",".join(done))
            if check is not None:
                print("T-LOOM-34: %s (%d tool calls, %d loom)" % (check["t_loom_34"], check["tool_uses"], check["loom_calls"]))
                for v in check["violations"]:
                    print("harness: T-LOOM-34 VIOLATION: %s" % v, file=sys.stderr)
                return 1 if check["violations"] else 0
            return 0
        if a.cmd == "close":
            print(close(a.run_dir, a.reason))
            return 0
        if a.cmd == "score":
            rs, path, _ = score_folder(a.run_dir, a.driver, bank, score.load_gold(), a.results_dir, a.tag, head=a.head, corpus_path=a.corpus)
            print("%s %s %s -> %s" % (rs.task_id, rs.status, json.dumps(rs.text, ensure_ascii=False), _rel(path)))
            return 0 if rs.status != "run_not_verified" else 1
    except (HarnessError, LedgerError) as e:
        print("harness: %s" % e, file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
