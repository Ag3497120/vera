"""LOOM-g: the scorer of a loom run (docs/LINE3_LOOM_DESIGN.md 7.1 L4, 10.1).  A typed result, from a run FOLDER alone.

THE GATE (L4).  `score_run` calls `ledger.verify` first (chain + replay) and refuses a run that is not OK: status `run_not_verified`, nothing
else of the run is looked at.  The output of a weaving run is the text of its successful `emit` row (`ledger.emitted_output`, the same
function as `vera loom output`); free text, lookups, reads, statuses and refused emits are never output.  A CONTROL run (task row carries
`"control": "free_text"`; no loom, free-text answer; design 9.3 / 10.1) is the one place where free text IS the output: its text is the last
`free_text_control` row of a verified ledger.  Every result of a control run says `control: true` and its mode is `free_text`.

THE RULE (T9, experiments/line3/t9/scorer.py, loaded, not copied; the headline changed on 2026-10-12, LOOM-span, owner decision).  Gold alternatives are
separated by `|`; every text is normalised the T9 way (NFKC, casefold, no whitespace, no 「・」, digits).  A loom output is ONE candidate text (the text of the
emit row).
    hit_exact         THE HEADLINE.  The normalised answer text EQUALS a normalised gold alternative.  `status` hit / miss and `correct` follow it.
    hit_cited         a LONGER text (it holds a gold alternative but is not equal to one) counts only if it appears word for word (LETTERS ONLY on both
                      sides, as a substring: L-LOOM-143) in a corpus sentence THE LEDGER CITES: a sentence in the result of an ok `read_sentence` or `lookup` row of the run.
                      A quotation of what the run itself read; never a hit of the headline.  False when hit_exact is true.
    hits_text         SECONDARY.  The old substring rule: a normalised gold alternative is a substring of the normalised text.
    excess_chars      SECONDARY.  Normalised characters of the text beyond the shortest gold alternative it contains.
  Three stricter views are reported beside them and never replace them (the OP-F2-5 caveat: a long text can hit by substring):
    hits_words        the gold inside ONE record unit's surface (`hits_words(gold, record surfaces)`)
    hit_record_text   the gold inside the concatenation of the record and foundation segments only (the constructed words removed)
Before 2026-10-12 the headline was hits_text (the first two measurements, results_h55 and results_h55b, were scored that way); `rescore_h55.md` and
`rescore_h55b.md` give them again under the exact rule (their JSON files are append-only and untouched).
Unanswerable questions (`unans`): correct = abstained (a control: the answer line starts with 「不明」).
A CONTROL is scored on its ANSWER LINE only (first non-empty NFKC line, `answer_line`): `hit_exact`, `hits_text` and `excess_chars` look at that line, and so
does the abstention test; the rest of its message is kept in `text` and scored nowhere (L-LOOM-59).

Nothing here reads a gold from the task bank the MCP server serves (tasks_bank2.jsonl holds none); the gold comes from bank2.tsv, read here.
No float anywhere: shares are integer permille of the characters of the text.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from verantyx.line3 import space as sp                                         # noqa: E402
from verantyx.loom import ledger as lg                                         # noqa: E402
from verantyx.loom.ops import CLASS_OF, LEGACY_OPS, MODEL_OPS, STATE_CHANGING  # noqa: E402

BANK2_TSV = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
T9_SCORER = os.path.join(ROOT, "experiments/line3/t9/scorer.py")

STATUSES = ("hit", "miss", "abstained_correct", "abstained_wrong", "answered_unans", "no_output", "run_not_verified", "unscored")
OUTCOMES = ("emitted", "abstained", "no_output", "not_verified")
KINDS = ("record", "constructed", "foundation", "layout")
CONTROL = "free_text"
NO_TOOLS = "no_tools"                       # LOOM-control (L-LOOM-150): the control with NO tools at all (a plain messages call)
CONTROLS = (CONTROL, NO_TOOLS)              # the `control` value of a task row / the `mode` label of a control run
LAYERS = ("L_meta", "L_struct", "L_none_marked", "L_none", "L_other")    # LOOM-control: which layer ended a run (see `layer_report`)


def _load_scorer():
    name = "loom_t9_scorer"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, T9_SCORER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


t9 = _load_scorer()


# ------------------------------------------------------------------------------------------------------------
# the task side: the bank the server serves (no gold) and the gold table
# ------------------------------------------------------------------------------------------------------------
def load_bank(path: str) -> Dict[str, dict]:
    """task_id -> the task row, exactly as the server's bank file holds it (extra keys `base`, `bank2_id`, `control` are the harness's)."""
    out: Dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            if ln.strip():
                r = json.loads(ln)
                if r["task_id"] in out:
                    raise ValueError("duplicate task_id %r in %s" % (r["task_id"], path))
                out[r["task_id"]] = r
    return out


def load_gold(tsv: str = BANK2_TSV) -> Dict[str, dict]:
    """bank2 id -> {kind, question, gold}.  `kind` is `intra2` / `unans` / ...; gold is `""` for unans."""
    out: Dict[str, dict] = {}
    with open(tsv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            out[r["#id"]] = {"kind": r["kind"], "question": r["question"], "gold": r["gold"]}
    return out


@dataclass(frozen=True)
class TaskFacts:
    task_id: str
    base: str
    mode: str                       # record_only | constructed_allowed | free_text (a control)
    control: bool
    kind: str                       # answerable | unans | none (no gold: a demo task)
    gold: str

    @staticmethod
    def of(row: dict, gold_tbl: Dict[str, dict]) -> "TaskFacts":
        control = row.get("control") in CONTROLS
        base = row.get("base") or row["task_id"].replace("/", "_")
        g = gold_tbl.get(row.get("bank2_id") or "")
        declared = row.get("kind")                      # LOOM-control: a bank row may DECLARE `"kind": "unans"` (the ADV-nnn items are not in bank2.tsv);
        if declared not in (None, "unans"):             # `normalize_task` drops the key, the model never sees it, and it holds no gold
            raise ValueError("task %r: kind must be \"unans\" when present, not %r" % (row["task_id"], declared))
        if g is None:
            kind, gold = ("unans", "") if declared == "unans" else ("none", "")
        else:
            kind = "unans" if g["kind"] == "unans" else "answerable"
            gold = g["gold"]
            if declared == "unans" and kind != "unans":
                raise ValueError("task %r declares kind unans, bank2.tsv says %r" % (row["task_id"], g["kind"]))
        return TaskFacts(row["task_id"], base, row["control"] if control else row["mode"], control, kind, gold)


# ------------------------------------------------------------------------------------------------------------
# the pure scoring rules
# ------------------------------------------------------------------------------------------------------------
def excess_chars(gold: str, text: str) -> Optional[int]:
    """Normalised characters of `text` beyond the shortest gold alternative it contains; None if none is contained."""
    t = t9.norm(text)
    hits = [g for g in t9.golds(gold) if g in t]
    return None if not hits else len(t) - min(len(g) for g in hits)


def segment_chars(annotated: Sequence[dict]) -> Dict[str, int]:
    out = {k: 0 for k in KINDS}
    for seg in annotated:
        out[seg["kind"]] = out.get(seg["kind"], 0) + len(seg["s"])
    return out


def share_permille(chars: Dict[str, int]) -> Dict[str, int]:
    total = sum(chars.values())
    return {k: (0 if total == 0 else (1000 * v) // total) for k, v in chars.items()}


def hit_exact(gold: str, text: str) -> bool:
    """The headline: the normalised text IS a normalised gold alternative."""
    return t9.norm(text) in t9.golds(gold)


def letters_only(x: str) -> str:
    """The comparison form of `hit_cited` (L-LOOM-143): `t9.norm`, then only the characters `space._has_letter` calls letters.  The T9 normaliser drops
    whitespace and 「・」 and nothing else, so 「アメリカを「青」」 keeps its quotation marks there; the loom's `weave_span` writes none of them (its gaps are
    letters only), so a text it wove is compared with the corpus sentence on the same footing: letters on both sides."""
    return "".join(ch for ch in t9.norm(x) if sp._has_letter(ch))


def hit_cited(gold: str, text: str, cited: Optional[Sequence[str]]) -> bool:
    """A longer text (it holds a gold alternative, it is not equal to one) that appears word for word in a sentence the ledger cites.  "Word for word" is
    judged on LETTERS ONLY on both sides (`letters_only`: punctuation, quotes, brackets, hyphens and 「・」 are not compared), the same footing as the loom's
    own `weave_span` read-out (L-LOOM-143)."""
    if cited is None or hit_exact(gold, text) or not t9.hits_text(gold, text):
        return False
    t = letters_only(text)
    return bool(t) and any(t in letters_only(c) for c in cited)


def answer_view(gold: str, text: str, annotated: Optional[Sequence[dict]], cited: Optional[Sequence[str]] = None) -> dict:
    """The T9 rule on a text (+ its annotation, if any; + the sentences the ledger cites)."""
    out: Dict[str, Any] = {"hit_exact": hit_exact(gold, text), "hit_cited": hit_cited(gold, text, cited), "hits_text": t9.hits_text(gold, text),
                           "excess_chars": excess_chars(gold, text), "hits_words": None, "hit_record_text": None}
    if annotated is not None:
        recs = [s["s"] for s in annotated if s["kind"] == "record"]
        out["hits_words"] = t9.hits_words(gold, recs)
        out["hit_record_text"] = t9.hits_text(gold, "".join(s["s"] for s in annotated if s["kind"] in ("record", "foundation")))
    return out


def answer_line(text: str) -> str:
    """A control's ANSWER LINE (design 10.1): the first non-empty line of the NFKC-normalised text, trimmed; "" if there is none.  The control agent is
    told to answer in ONE line; everything after the first line is not the answer (L-LOOM-59), so a rambling control that names the gold in line 2 is not a hit."""
    for ln in unicodedata.normalize("NFKC", text).splitlines():
        if ln.strip():
            return ln.strip()
    return ""


def control_abstains(text: str) -> bool:
    """A control's answer line that starts with 「不明」 is an abstention."""
    return answer_line(text).startswith("不明")


# ------------------------------------------------------------------------------------------------------------
# the run side: facts read from a VERIFIED ledger
# ------------------------------------------------------------------------------------------------------------
_NON_RECOVERABLE = frozenset(("run_closed", "unknown_tool", "cap_exceeded", "ops_cap", "lookup_cap", "read_cap", "emit_cap", "args_too_large"))


def self_corrections(rows: Sequence[dict]) -> dict:
    """The three self-corrections of the meter (design LOOM-notes (3); fixed as L-LOOM-56), read from the ledger and nothing else.
      unseat_swap_before_close   an ok `unseat` / `swap` row of the model before the row that closes the run (all of them if it never closed)
      plan_change_after_empty    an ok `lookup` with no match, whose NEXT model row is a lookup / add with other text or tier, or a read_sentence
                                 (the next row being `abstain` is a conclusion, not a plan change)
      recovery_after_refusal     a refused model row of a closing-capable or state-changing op (a cap, run_closed, unknown_tool are not
                                 recoverable and are left out) that is followed later by an ok row of the SAME op
    """
    model = [r for r in rows if r["actor"] == "model"]
    close_i = None
    for r in model:
        if r["op"] in ("emit", "abstain") and r["result"].get("ok") is True and r["result"].get("status") in ("emitted", "abstained"):
            close_i = r["i"]
            break
    out: Dict[str, Any] = {"unseat_swap_before_close": [], "plan_change_after_empty": [], "recovery_after_refusal": [],
                           "refusals_recoverable": 0}
    for r in model:
        if r["op"] in ("unseat", "swap") and r["result"].get("ok") is True and (close_i is None or r["i"] < close_i):
            out["unseat_swap_before_close"].append({"i": r["i"], "op": r["op"]})
    for k, r in enumerate(model):
        if r["op"] == "lookup" and r["result"].get("ok") is True and r["result"].get("matches") == []:
            nxt = model[k + 1] if k + 1 < len(model) else None
            if nxt is None:
                continue
            if nxt["op"] == "read_sentence" or (nxt["op"] in ("lookup", "add") and
                                                (nxt["args"].get("text"), nxt["args"].get("tier")) != (r["args"].get("text"), r["args"].get("tier"))):
                out["plan_change_after_empty"].append({"i": r["i"], "next_i": nxt["i"], "next_op": nxt["op"]})
    for k, r in enumerate(model):
        res = r["result"]
        if res.get("ok") is False and res.get("refusal") not in _NON_RECOVERABLE and r["op"] in MODEL_OPS + LEGACY_OPS:
            out["refusals_recoverable"] += 1
            if any(q["op"] == r["op"] and q["result"].get("ok") is True for q in model[k + 1:]):
                out["recovery_after_refusal"].append({"i": r["i"], "op": r["op"], "refusal": res.get("refusal")})
    out["counts"] = {"unseat_swap_before_close": len(out["unseat_swap_before_close"]),
                     "plan_change_after_empty": len(out["plan_change_after_empty"]),
                     "recovery_after_refusal": len(out["recovery_after_refusal"]), "refusals_recoverable": out["refusals_recoverable"]}
    return out


def cited_sentences(rows: Sequence[dict]) -> List[str]:
    """The corpus sentences a run CITES (LOOM-span scoring): the `text` of every sentence in the result of an ok model `read_sentence` row and in the
    `matches[*].sentences` of an ok model `lookup` row, in ledger order, without repeats.  Rows of a ledger that has already verified."""
    out: List[str] = []
    seen = set()

    def add(t: Any) -> None:
        if isinstance(t, str) and t not in seen:
            seen.add(t)
            out.append(t)

    for r in rows:
        if r.get("actor") != "model" or r["result"].get("ok") is not True:
            continue
        if r["op"] == "read_sentence":
            add(r["result"].get("text"))
        elif r["op"] == "lookup":
            for m in r["result"].get("matches") or []:
                for sen in m.get("sentences") or []:
                    add(sen.get("text") if isinstance(sen, dict) else None)
    return out


def run_facts(run_dir: str) -> dict:
    """Everything the meter columns need, from the rows of a ledger that has ALREADY verified (the caller guarantees it)."""
    lines, _ = lg.read_lines(run_dir)
    rows = [json.loads(ln) for ln in lines]
    model = [r for r in rows if r["actor"] == "model"]
    by_op: Dict[str, int] = {}
    by_class: Dict[str, int] = {}
    refusals: Dict[str, int] = {}
    for r in model:
        by_op[r["op"]] = by_op.get(r["op"], 0) + 1
        by_class[CLASS_OF.get(r["op"], "other")] = by_class.get(CLASS_OF.get(r["op"], "other"), 0) + 1
        if r["result"].get("ok") is False:
            refusals[r["result"].get("refusal", "?")] = refusals.get(r["result"].get("refusal", "?"), 0) + 1
    begin = rows[0]
    dropped = [r["args"] for r in rows if r["op"] == "free_text_dropped"]
    controls = [r for r in rows if r["op"] == "free_text_control"]
    meta = [r["args"] for r in rows if r["op"] == "harness_meta"]
    closing = None
    for r in model:
        if r["op"] in ("emit", "abstain") and r["result"].get("ok") is True and r["result"].get("status") in ("emitted", "abstained"):
            closing = {"i": r["i"], "op": r["op"], "status": r["result"]["status"], "type": r["result"].get("type")}
            break
    abandoned = [r["args"].get("reason") for r in rows if r["op"] == "abandoned"]
    emit_rows = [r for r in model if r["op"] == "emit"]
    timing = os.path.join(str(run_dir), "timing.jsonl")
    wall = None
    if os.path.exists(timing):
        with open(timing, encoding="utf-8") as f:
            ts = [json.loads(ln)["t_ns"] for ln in f if ln.strip()]
        wall = max(ts) if ts else None
    return {
        "task_id": begin["args"]["task_id"], "declared_model": begin["args"]["model"], "run_id": begin["result"].get("run_id"),
        "mode": begin["result"]["task"]["mode"], "rows": len(rows), "model_rows": len(model),
        "ops_by_name": dict(sorted(by_op.items())), "ops_by_class": dict(sorted(by_class.items())),
        "refusals": dict(sorted(refusals.items())), "refused_total": sum(refusals.values()),
        "emit_attempts": len(emit_rows), "closing": closing, "abandoned": abandoned,
        "free_text_dropped": {"n": len(dropped), "chars": sum(d["chars"] for d in dropped), "sha256": [d["sha256"] for d in dropped]},
        "free_text_control_rows": len(controls),
        "harness_meta": meta, "self_corrections": self_corrections(rows),
        "ledger_wall_ns": wall, "head": rows[-1]["sha"],
    }


# ------------------------------------------------------------------------------------------------------------
# LOOM-control: which LAYER ended a run (L-LOOM-151).  Read from the rows of a verified ledger and nothing else.
# ------------------------------------------------------------------------------------------------------------
BUILD_OPS = tuple(STATE_CHANGING) + ("emit",)               # every model op that tries to put something into the thread or out of the loom
WEAVE_ATTEMPT_OPS = tuple(STATE_CHANGING)                   # ... without the emit (counted apart)


def _is_close(r: dict) -> bool:
    return r["op"] in ("emit", "abstain") and r["result"].get("ok") is True and r["result"].get("status") in ("emitted", "abstained")


def layer_report(rows: Sequence[dict], control: Optional[str] = None) -> dict:
    """THE STOP LAYER of one run, and the counts it rests on, from the ledger rows alone (nothing is passed in out of band except whether the task is a control).

      L_meta         the run ended in an abstention (a loom `abstain`; a control: the answer line 「不明」) and the model made 0 build attempts (no weave / seat / add /
                     open_cross / link / ... / emit row, accepted or refused): the model's OWN re-check (route 2).
      L_struct       at least one build op (any state-changing op or an emit) was REFUSED by the loom for a structural reason (not a cap, not run_closed, not
                     unknown_tool: `_NON_RECOVERABLE`), and the run then abstained or produced no output: the structure refused (route 1).  `struct_refusals` lists the types.
      L_none_marked  the run emitted a text that contains a constructed unit (constructed_allowed only; the text is marked, not stopped).
      L_none         the run emitted a text with only record / foundation / layout units, or a control ANSWERED.
      L_other        none of the four: an abstention after build ops that were all accepted (`abstain_after_build`), or no output without a structural refusal
                     (`no_output_no_refusal`: a cap, max_turns, an API error, 'done').  Reported, never folded into L_meta.

    A refusal that came BEFORE an emit does not make the run L_struct (it emitted: L_none / L_none_marked) but is listed in `struct_refusals_before_emit`:
    the structure fired and the run went on to answer.  `control` is None for a loom run, else the control label (free_text / no_tools): a control answered is
    L_none, a control 「不明」 is L_meta (no build op exists in a control).  Counts are of MODEL rows up to and including the closing row (all rows if it never closed).
    """
    model = [r for r in rows if r["actor"] == "model"]
    end_i = next((r["i"] for r in model if _is_close(r)), None)
    upto = [r for r in model if end_i is None or r["i"] <= end_i]
    counts = {"lookups": 0, "empty_lookups": 0, "read_sentences": 0, "reads": 0, "weave_attempts": 0, "emit_attempts": 0, "refusals": 0}
    refusals: Dict[str, int] = {}
    struct: Dict[str, int] = {}
    for r in upto:
        op = r["op"]
        res = r["result"]
        if op == "lookup":
            counts["lookups"] += 1
            if res.get("ok") is True and res.get("matches") == []:
                counts["empty_lookups"] += 1
        elif op == "read_sentence":
            counts["read_sentences"] += 1
        elif op == "read":
            counts["reads"] += 1
        elif op == "emit":
            counts["emit_attempts"] += 1
        elif op in WEAVE_ATTEMPT_OPS:
            counts["weave_attempts"] += 1
        if res.get("ok") is False:
            typ = str(res.get("refusal", "?"))
            counts["refusals"] += 1
            refusals[typ] = refusals.get(typ, 0) + 1
            if op in BUILD_OPS and typ not in _NON_RECOVERABLE:
                struct[typ] = struct.get(typ, 0) + 1
    attempts = counts["weave_attempts"] + counts["emit_attempts"]
    out: Dict[str, Any] = dict(counts, build_attempts=attempts, refusal_types=dict(sorted(refusals.items())),
                               struct_refusals=dict(sorted(struct.items())), struct_refusals_total=sum(struct.values()))
    emit = next((r for r in model if r["op"] == "emit" and r["result"].get("ok") is True and r["result"].get("status") == "emitted"), None)
    abstain = next((r for r in model if r["op"] == "abstain" and r["result"].get("ok") is True and r["result"].get("status") == "abstained"), None)
    detail = ""
    if control is not None:
        txt = None
        for r in rows:
            if r["op"] == "free_text_control":
                txt = r["args"]["text"]
        if txt is None:
            layer, outcome, detail = "L_other", "no_output", "control_no_text"
        elif control_abstains(txt):
            layer, outcome = "L_meta", "不明"
        else:
            layer, outcome = "L_none", "answered"
        out["control_outcome"] = outcome
    elif emit is not None:
        marked = any(seg.get("kind") == "constructed" for seg in (emit["result"].get("annotated") or []))
        layer, detail = ("L_none_marked", "constructed_unit_in_text") if marked else ("L_none", "")
        out["struct_refusals_before_emit"] = out["struct_refusals_total"]
    elif out["struct_refusals_total"] >= 1:
        layer = "L_struct"
        detail = "then_abstained" if abstain is not None else "then_no_output"
    elif abstain is not None and attempts == 0:
        layer = "L_meta"
    elif abstain is not None:
        layer, detail = "L_other", "abstain_after_build"
    else:
        layer, detail = "L_other", "no_output_no_refusal"
    out["stop_layer"] = layer
    out["stop_layer_detail"] = detail
    return out


# ------------------------------------------------------------------------------------------------------------
# the typed result
# ------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RunScore:
    task_id: str
    base: str
    mode: str                                   # record_only | constructed_allowed | free_text
    control: bool                               # True: a free-text control (NOT a loom output; for comparison only)
    kind: str                                   # answerable | unans | none
    status: str                                 # one of STATUSES
    outcome: str                                # one of OUTCOMES
    correct: Optional[bool]                     # None when there is nothing to judge (no gold, no output, not verified)
    verify_status: str
    replay_verified: bool
    text: Optional[str] = None
    output_sha: Optional[str] = None
    abstain_type: Optional[str] = None
    hit_exact: Optional[bool] = None            # THE HEADLINE (2026-10-12): the normalised text equals a normalised gold alternative
    hit_cited: Optional[bool] = None            # a longer text that holds the gold AND appears word for word in a sentence the ledger cites
    hits_text: Optional[bool] = None            # secondary: the old substring rule (the headline before 2026-10-12)
    hits_words: Optional[bool] = None
    hit_record_text: Optional[bool] = None
    excess_chars: Optional[int] = None
    chars: Dict[str, int] = field(default_factory=dict)
    share_permille: Dict[str, int] = field(default_factory=dict)
    annotated: Optional[List[dict]] = None
    answer_line: Optional[str] = None           # a control only: the line that was scored (L-LOOM-59); `text` is the whole final message
    stop_layer: Optional[str] = None            # LOOM-control: one of LAYERS (see `layer_report`); None when the run did not verify
    layer: Optional[dict] = None                # LOOM-control: the counts the layer rests on (lookups, empty lookups, reads, weave attempts, refusals by type)
    stability: Optional[list] = None
    facts: Optional[dict] = None
    note: str = ""

    def to_obj(self) -> dict:
        return asdict(self)


def _rows_of(run_dir: str) -> List[dict]:
    lines, _ = lg.read_lines(run_dir)
    return [json.loads(ln) for ln in lines]


def _closing_row(run_dir: str) -> Tuple[Optional[dict], Optional[dict]]:
    """(the successful emit row, the successful abstain row) of a verified ledger."""
    lines, _ = lg.read_lines(run_dir)
    emit = abstain = None
    for ln in lines:
        r = json.loads(ln)
        if r["actor"] != "model" or r["result"].get("ok") is not True:
            continue
        if r["op"] == "emit" and r["result"].get("status") == "emitted" and emit is None:
            emit = r
        if r["op"] == "abstain" and r["result"].get("status") == "abstained" and abstain is None:
            abstain = r
    return emit, abstain


def _last_control_text(run_dir: str) -> Optional[str]:
    lines, _ = lg.read_lines(run_dir)
    text = None
    for ln in lines:
        r = json.loads(ln)
        if r["op"] == "free_text_control":
            text = r["args"]["text"]
    return text


def score_run(run_dir: str, bank_rows: Dict[str, dict], gold_tbl: Dict[str, dict], head: Optional[str] = None,
              corpus_path: Optional[str] = None, loader=lg.default_loader) -> RunScore:
    """Verify the folder, then score it.  The task is found from row 0 of the ledger and the bank; nothing is passed in out of band."""
    v = lg.verify(run_dir, head, corpus_path, loader)
    if v["status"] != "OK":
        tid = _task_id_unverified(run_dir)
        row = bank_rows.get(tid or "", {})
        tf = TaskFacts.of(row, gold_tbl) if row else None
        return RunScore(tid or "?", tf.base if tf else "?", tf.mode if tf else "?", bool(tf and tf.control), tf.kind if tf else "none",
                        "run_not_verified", "not_verified", None, v["status"], False,
                        note="the ledger does not verify (%s); nothing of this run is output" % v["status"])
    facts = run_facts(run_dir)
    row = bank_rows.get(facts["task_id"])
    if row is None:
        raise KeyError("task %r is not in the bank" % facts["task_id"])
    tf = TaskFacts.of(row, gold_tbl)
    replay_ok = v.get("replay", {}).get("status") == "IDENTICAL"
    lay = layer_report(_rows_of(run_dir), tf.mode if tf.control else None)
    base = dict(task_id=tf.task_id, base=tf.base, mode=tf.mode, control=tf.control, kind=tf.kind, verify_status="OK", replay_verified=replay_ok,
                facts=facts, stop_layer=lay["stop_layer"], layer=lay)
    if tf.control:
        return _score_control(run_dir, tf, base)
    out = lg.emitted_output(run_dir, head, corpus_path, loader)
    if out["status"] == "run_not_verified":                                 # cannot happen after an OK verify; kept as the L4 contract
        return RunScore(status="run_not_verified", outcome="not_verified", correct=None, **dict(base, verify_status=out["verify"], replay_verified=False))
    emit, abstain = _closing_row(run_dir)
    if out["status"] == "emitted":
        text = out["text"]
        assert emit is not None and emit["result"]["output_sha"] == out["output_sha"] and emit["result"]["text"] == text
        ann = emit["result"]["annotated"]
        chars = segment_chars(ann)
        common = dict(text=text, output_sha=out["output_sha"], chars=chars, share_permille=share_permille(chars), annotated=ann,
                      stability=emit["result"].get("stability"), outcome="emitted", **base)
        if tf.kind == "none":
            return RunScore(status="unscored", correct=None, note="no gold for this task (a demo task)", **common)
        if tf.kind == "unans":
            return RunScore(status="answered_unans", correct=False, note="an unanswerable question was answered with an output", **common)
        view = answer_view(tf.gold, text, ann, cited_sentences(_rows_of(run_dir)))
        ok = view["hit_exact"]
        return RunScore(status="hit" if ok else "miss", correct=ok, hit_exact=view["hit_exact"], hit_cited=view["hit_cited"], hits_text=view["hits_text"],
                        hits_words=view["hits_words"], hit_record_text=view["hit_record_text"], excess_chars=view["excess_chars"], **common)
    if abstain is not None:
        typ = abstain["result"]["type"]
        if tf.kind == "unans":
            return RunScore(status="abstained_correct", outcome="abstained", correct=True, abstain_type=typ, **base)
        if tf.kind == "answerable":
            return RunScore(status="abstained_wrong", outcome="abstained", correct=False, abstain_type=typ,
                            note="an answerable question was abstained", **base)
        return RunScore(status="unscored", outcome="abstained", correct=None, abstain_type=typ, note="no gold for this task", **base)
    return RunScore(status="no_output", outcome="no_output", correct=None if tf.kind == "none" else False,
                    note="the run closed with neither emit nor abstain (abandoned: %s)" % (facts["abandoned"] or "not closed"), **base)


def _score_control(run_dir: str, tf: TaskFacts, base: dict) -> RunScore:
    text = _last_control_text(run_dir)
    note = ("CONTROL (free text, no loom): the answer line IS the output; for comparison with the loom only" if tf.mode == CONTROL else
            "CONTROL (no tools at all, a plain messages call): the answer line IS the output; for comparison with the loom only")
    if text is None:
        return RunScore(status="no_output", outcome="no_output", correct=None if tf.kind == "none" else False, note=note + "; no free_text_control row", **base)
    chars = {"record": 0, "constructed": 0, "foundation": 0, "layout": 0}
    line = answer_line(text)
    common = dict(text=text, output_sha=None, chars=chars, share_permille={}, answer_line=line, **base)
    if control_abstains(text):
        if tf.kind == "unans":
            return RunScore(status="abstained_correct", outcome="abstained", correct=True, abstain_type="不明", note=note, **common)
        if tf.kind == "answerable":
            return RunScore(status="abstained_wrong", outcome="abstained", correct=False, abstain_type="不明", note=note, **common)
        return RunScore(status="unscored", outcome="abstained", correct=None, abstain_type="不明", note=note, **common)
    if tf.kind == "none":
        return RunScore(status="unscored", outcome="emitted", correct=None, note=note, **common)
    if tf.kind == "unans":
        return RunScore(status="answered_unans", outcome="emitted", correct=False, note=note, **common)
    view = answer_view(tf.gold, line, None, cited_sentences(_rows_of(run_dir)))              # the ANSWER LINE is scored, not the whole message (L-LOOM-59)
    ok = view["hit_exact"]
    return RunScore(status="hit" if ok else "miss", outcome="emitted", correct=ok, hit_exact=ok, hit_cited=view["hit_cited"], hits_text=view["hits_text"],
                    excess_chars=view["excess_chars"], note=note, **common)


def _task_id_unverified(run_dir: str) -> Optional[str]:
    """The task id from row 0 of an UNVERIFIED ledger, for the label of the refusal only (never trusted for a score)."""
    try:
        with open(os.path.join(str(run_dir), "ops.jsonl"), encoding="utf-8") as f:
            return json.loads(f.readline())["args"]["task_id"]
    except Exception:
        return None
