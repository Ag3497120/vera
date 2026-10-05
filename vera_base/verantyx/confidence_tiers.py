"""W12-c1: the staircase of knowledge for `vera serve --no-llm` (docs/INITIAL_LAYERS.md sections 5 and 6).

The same question is answered by a staircase of the structure Vera carries: the base alone, the base with the vocabulary layer, the base with a domain layer,
the base with the domain layer and the user's layer.  What the answer carries is NOT a probability: it is the number of stages of its own structure
that gave the same answer (`agree`, an integer): of the stages that ANSWERED (`answered`), those whose answer is the same as the one shown. Abstentions are not
counted (agreeing abstentions are not evidence); if the shown result is an abstention, or the stages conflict, `agree` is 0. `counted` is the number of stages
consulted.  vera1 measured the shape of this
(verantyx/resolution.py): unanimity of several rungs was right every time, a rung with no single leader ABSTAINS, and breaking the tie by a fixed
order (insertion, lexicographic) manufactured agreement (73.3% -> 23.7%).  So here:

  * a stage that was not consulted does not count (`NOT_CONSULTED_BY_READER` for the vocabulary stage: the reader does not read it yet; `NOT_ROUTED`
    when none of the stage's direct words is in the question or in the documents, type `UNKNOWN_NO_EVIDENCE`; `NOT_AVAILABLE` when there is no such layer);
  * two different ANSWERs among the counted stages are not decided: `--profile strict` abstains with `TIERS_CONFLICT`;
  * nothing here is a probability: no float, no key named prob / confidence / score.

This module is pure except for `TierRunner`, which runs the stages inside ONE lock and ONE thread (the placement's SQLite connection belongs to the thread that
opened it) and sets `VERA_PLACEMENT_LAYER` to the stage's value for the duration of the stage only (`stage_env`: unset for the base, restored afterwards,
also on an exception).  The reading itself (semantic_reader / semantic_read) is not touched.
"""
from __future__ import annotations

import concurrent.futures
import contextlib
import copy
import json
import os
import threading
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

SCHEMA = "verantyx.confidence_tiers/2"   # /1's `agree` also counted agreeing abstentions; /2 counts only the stages that answered
BASE = "base"
VOCAB = "vocab"
DEFAULT_ORDER = ("base", "vocab", "law", "law+user")

COUNTED = "COUNTED"
NOT_CONSULTED_BY_READER = "NOT_CONSULTED_BY_READER"
NOT_ROUTED = "NOT_ROUTED"
NOT_AVAILABLE = "NOT_AVAILABLE"
STATUSES = (COUNTED, NOT_CONSULTED_BY_READER, NOT_ROUTED, NOT_AVAILABLE)

PROFILES = ("strict", "assume")
ASSUMPTIONS_NOT_WIRED = "NOT_WIRED_UNTIL_W3-e3"        # K412: until the assumed reading exists, `assume` says so instead of silently equalling `strict`
ASSUMPTIONS_NOT_USED = "NOT_USED_IN_STRICT"
TIERS_CONFLICT_TEXT = "段によって答えが食い違うので答えられません（TIERS_CONFLICT）。"

#: `decode_grammar.conclude` looks `FIXED_TEXT[reading["type"]]` up and `RECORDS` is not in that table: the no-LLM entrance writes the type it abstains with (docs section 6).
NO_LLM_FIXED_TYPE = {"NO_RECORD": "NO_RECORD", "STRUCTURE_UNDETERMINED": "STRUCTURE_UNDETERMINED", "RECORDS": "ABSTAIN"}


class TierError(Exception):
    def __init__(self, error: str, detail: str = "") -> None:
        super().__init__(error)
        self.error, self.detail = error, detail


# ------------------------------------------------------------------------------------------------------------------------ pure parts
def answer_outcomes() -> Tuple[str, ...]:
    from . import decode_grammar as G
    return tuple(G.ANSWER_OUTCOMES)


def signature_of(content: str, vera: Dict[str, Any]) -> Dict[str, Any]:
    """K411: (the type of the result, the values) of one stage's answer. An ANSWER's values are the structured filler (else the text); an abstention's signature is its type and its fixed text."""
    out = vera.get("outcome") or {}
    oc = out.get("outcome")
    if oc in answer_outcomes():
        filler = (vera.get("reading") or {}).get("filler")
        vals = [str(filler)] if filler is not None else None
        return {"outcome": oc, "values": sorted(vals) if vals else None, "text": None if vals else content}
    return {"outcome": oc, "values": None, "text": content}


def _sig_key(sig: Optional[Dict[str, Any]]) -> Optional[str]:
    return None if sig is None else json.dumps(sig, ensure_ascii=False, sort_keys=True)


def is_answer(sig: Optional[Dict[str, Any]]) -> bool:
    return sig is not None and sig.get("outcome") in answer_outcomes()


def routed_words(direct_words: Sequence[str], texts: Sequence[str]) -> List[str]:
    """K410: the stage's direct words that occur in the question or in the documents (a string test, like `why_not_gained.py`). Empty = `NOT_ROUTED`."""
    blob = "\n".join(texts)
    return sorted(w for w in direct_words if w and w in blob)


def combine(tiers: Sequence[Dict[str, Any]], profile: str = "strict") -> Dict[str, Any]:
    """The `confidence_tiers` field from the stages' records `{name, status, signature, ...}` (in the staircase's order).
    `shown_tier` is the last COUNTED stage (its answer is the one shown); `counted` the number of COUNTED stages; `answered` how many of them gave an ANSWER;
    `agree` (K403, clarified in round 3): if the shown result is an ANSWER and the stages do not conflict, the number of counted ANSWER stages with the same
    signature as the shown one; otherwise 0 (agreeing abstentions are not counted; a shown abstention or a conflict gives 0);
    `conflict` is True when two counted stages gave different ANSWERs (strict: `TIERS_CONFLICT`, the caller abstains; nothing is chosen)."""
    if profile not in PROFILES:
        raise TierError("BAD_PROFILE", profile)
    counted = [t for t in tiers if t.get("status") == COUNTED]
    if not counted:
        raise TierError("NO_COUNTED_TIER", "the base stage is always counted")
    shown = counted[-1]
    key = _sig_key(shown["signature"])
    answers = {_sig_key(t["signature"]) for t in counted if is_answer(t["signature"])}
    conflict = len(answers) >= 2
    answered = sum(1 for t in counted if is_answer(t["signature"]))
    agree = 0
    if is_answer(shown["signature"]) and not conflict:
        agree = sum(1 for t in counted if is_answer(t["signature"]) and _sig_key(t["signature"]) == key)
    return {"schema": SCHEMA, "agree": agree, "answered": answered, "counted": len(counted), "shown_tier": shown["name"], "conflict": conflict,
            "tiers": [{k: v for k, v in t.items() if k in ("name", "status", "signature", "reason", "layer_words_in_text")} for t in tiers]}


def no_llm_plan(turn: Dict[str, Any]) -> Dict[str, Any]:
    """The turn of `plan_turn` for an entrance that never calls an LLM: a reading that would have gone to the LLM is answered by a fixed text of a type `conclude` knows."""
    if not turn.get("call_llm"):
        return turn
    t = dict(turn)
    reading = dict(turn["reading"])
    orig = reading["type"]
    reading["type"] = NO_LLM_FIXED_TYPE.get(orig, "ABSTAIN")
    t.update({"call_llm": False, "reading": reading, "skip_reason": "NO_LLM", "no_llm_orig_type": orig})
    return t


def no_llm_annotate(turn: Dict[str, Any], vera: Dict[str, Any]) -> None:
    """After `conclude`: `vera.reading.type` is what the reader said (not the type written for the fixed text); the written type is `vera.no_llm_fixed_as`; no LLM was called."""
    orig = turn.get("no_llm_orig_type")
    if orig is not None:
        vera["no_llm_fixed_as"] = vera["reading"]["type"]
        vera["reading"]["type"] = orig
    vera["no_llm"] = True


# ------------------------------------------------------------------------------------------------------------------------ the stage's environment
@contextlib.contextmanager
def stage_env(spec: Optional[str]) -> Iterator[None]:
    """`VERA_PLACEMENT_LAYER` = `spec` for the stage (unset for the base: `spec` is None), the previous value back afterwards even if the stage raises (T5)."""
    from . import placement_layer as PL
    old = os.environ.get(PL.ENV_LAYER)
    try:
        if spec is None:
            os.environ.pop(PL.ENV_LAYER, None)
        else:
            os.environ[PL.ENV_LAYER] = str(spec)
        yield
    finally:
        if old is None:
            os.environ.pop(PL.ENV_LAYER, None)
        else:
            os.environ[PL.ENV_LAYER] = old


def parse_tier(arg: str) -> Tuple[str, str]:
    """`NAME=SPEC` -> (name, spec). `base` is implicit (it is the placement alone) and cannot be given."""
    if "=" not in arg:
        raise TierError("BAD_TIER", "want NAME=SPEC, got %r" % arg)
    name, spec = arg.split("=", 1)
    name, spec = name.strip(), spec.strip()
    if not name or not spec:
        raise TierError("BAD_TIER", "want NAME=SPEC, got %r" % arg)
    if name == BASE:
        raise TierError("TIER_BASE_IS_IMPLICIT", "the base stage is the placement alone and is always there")
    return name, spec


class _Stage:
    def __init__(self, name: str, spec: Optional[str], kind: str) -> None:
        self.name, self.spec, self.kind = name, spec, kind        # kind: "base" | "vocab" | "layer" | "missing"
        self.cfg = None
        self.direct_words: List[str] = []
        self.sha256: Optional[str] = None
        self.text = ""


def _sha256_file(path: str) -> Optional[str]:
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for b in iter(lambda: fh.read(1 << 20), b""):
                h.update(b)
        return h.hexdigest()
    except OSError:
        return None


class TierRunner:
    """The staircase of a `vera serve --no-llm`. One lock, one thread for everything that reads the placement."""

    def __init__(self, tier_specs: Sequence[Tuple[str, str]], documents: Sequence[str], *, profile: str = "strict", model: str = "vera-no-llm",
                 order: Sequence[str] = DEFAULT_ORDER, with_default_missing: bool = True, pool: Optional[concurrent.futures.ThreadPoolExecutor] = None) -> None:
        if profile not in PROFILES:
            raise TierError("BAD_PROFILE", profile)
        names = [n for n, _ in tier_specs]
        if len(set(names)) != len(names):
            raise TierError("DUPLICATE_TIER", ",".join(names))
        self.profile = profile
        self.documents = list(documents)
        self.model = model
        self.llm_calls = 0
        self.lock = threading.Lock()
        # one thread for everything that reads the placement or a layer (their SQLite connections are cached per process and belong to the thread that opened them): a caller that makes
        # several runners in one process (the measurement scripts) hands every runner the same single-worker pool
        self.pool = pool if pool is not None else concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="vera-tiers")
        self.last: List[Dict[str, Any]] = []
        given = dict(tier_specs)
        stages: List[_Stage] = [_Stage(BASE, None, "base")]
        for n in order[1:]:                                        # the staircase always lists its steps; one with no layer is NOT_AVAILABLE, not absent
            if n in given:
                stages.append(_Stage(n, given[n], "vocab" if n == VOCAB else "layer"))
            elif with_default_missing:
                stages.append(_Stage(n, None, "missing"))
        for n in names:
            if n not in order:                                     # a stage the staircase has no default name for: after the named ones, in the order given
                stages.append(_Stage(n, given[n], "vocab" if n == VOCAB else "layer"))
        self.stages = stages
        self.base_sha = self.run(self._open_base)
        for s in self.stages:
            self.run(self._prepare, s)

    # ---- everything that touches the placement or a layer runs in the one thread
    def run(self, fn: Callable, *args: Any) -> Any:
        return self.pool.submit(fn, *args).result()

    def _open_base(self) -> Optional[str]:
        from . import coarse_place
        pl, _why = coarse_place._open(os.environ.get("VERA_PLACEMENT"))
        return getattr(pl, "sha", None)

    def _never(self, model, msgs, fmt):          # an LLM that must never be called (the counter proves it)
        self.llm_calls += 1
        raise AssertionError("the no-LLM entrance called an LLM")

    def _prepare(self, s: _Stage) -> None:
        from . import decode_grammar as G
        from . import placement_layer as PL
        from .vera_server import FusionConfig
        if s.kind in ("missing", "vocab"):
            s.sha256 = _sha256_file(s.spec) if s.spec else None
            if s.spec and s.sha256 is None:                    # a named file that cannot be read is refused, not recorded as `sha256: null` (review r1 O2)
                raise TierError("TIER_FILE_NOT_FOUND", "%s=%s: no readable file" % (s.name, s.spec))
            return
        if s.kind == "layer":
            layer, why = PL.open_layer(s.spec, self.base_sha)
            if layer is None:
                raise TierError("TIER_LAYER_UNAVAILABLE", "%s=%s: %s" % (s.name, s.spec, why))
            s.direct_words = sorted({e["word"] for e in layer.all_entries() if e["origin"] in PL.DIRECT_ORIGINS})
            path, _n, _w = PL.resolve(s.spec)
            s.sha256 = _sha256_file(path) if path else None
        with stage_env(s.spec if s.kind == "layer" else None):
            cfg = FusionConfig(model=self.model, documents=self.documents, records=None, strict=False, llm_chat=self._never)
            cfg._vera_thread.shutdown(wait=False)
            cfg._vera_thread = self.pool                            # every stage shares the one placement thread
            cfg.no_llm = True
            cfg.records = G.load_records(list(self.documents))      # a sentence is read with the stage's layer: the record depends on it
        s.cfg = cfg
        s.text = "\n".join(r["text"] for r in cfg.records.records)

    # ---- one turn
    def initial_layers(self) -> Dict[str, Any]:
        return {"base_content_sha256": self.base_sha,
                "tiers": [{"name": s.name, "kind": s.kind, "spec": s.spec, "sha256": s.sha256,
                           "direct_words": len(s.direct_words) if s.kind == "layer" else None} for s in self.stages]}

    def stage_answer(self, name: str, messages, vera_opts=None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """The answer of ONE stage whatever its routing (for the consistency gate of docs section 2, K417: the same stage answered in another process must give the same bytes)."""
        from . import vera_server as VS
        s = next(x for x in self.stages if x.name == name)
        if s.cfg is None:
            raise TierError("STAGE_HAS_NO_CONFIG", name)
        with self.lock:
            with stage_env(s.spec if s.kind == "layer" else None):
                return VS.fusion_turn(messages, vera_opts, s.cfg, max_tokens)

    def turn(self, messages, vera_opts, main_cfg, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        from . import vera_server as VS
        question = VS._last_user_text(messages) if isinstance(messages, list) and all(isinstance(m, dict) for m in messages) else ""
        t0 = time.perf_counter()
        records: List[Dict[str, Any]] = []
        results: Dict[str, Dict[str, Any]] = {}
        per_ms: Dict[str, float] = {}
        with self.lock:
            for s in self.stages:
                rec: Dict[str, Any] = {"name": s.name, "status": None, "signature": None}
                if s.kind == "missing":
                    rec["status"] = NOT_AVAILABLE
                elif s.kind == "vocab":
                    rec["status"] = NOT_CONSULTED_BY_READER
                else:
                    found: List[str] = []
                    if s.kind == "layer":
                        found = routed_words(s.direct_words, [question, s.text])
                        rec["layer_words_in_text"] = len(found)
                    if s.kind == "layer" and not found:
                        rec["status"] = NOT_ROUTED
                        rec["reason"] = "UNKNOWN_NO_EVIDENCE"
                    else:
                        t1 = time.perf_counter()
                        with stage_env(s.spec if s.kind == "layer" else None):
                            res = VS.fusion_turn(messages, vera_opts, s.cfg, max_tokens)       # a bad request raises here (from the base stage, which runs first)
                        per_ms[s.name] = round((time.perf_counter() - t1) * 1000.0, 3)
                        rec["status"] = COUNTED
                        rec["signature"] = signature_of(res["content"], res["vera"])
                        results[s.name] = res
                records.append(rec)
        ct = combine(records, self.profile)
        res = copy.deepcopy(results[ct["shown_tier"]])
        vera = res["vera"]
        if ct["conflict"]:                                            # strict and assume alike (K412): nothing is chosen
            res["content"] = TIERS_CONFLICT_TEXT
            vera["outcome"] = {"outcome": "TIERS_CONFLICT", "content_shown": False, "reason": "COUNTED_TIERS_GAVE_DIFFERENT_ANSWERS", "basis_policy": None}
        self.last = [dict(r, result=results.get(r["name"])) for r in records]
        total = (time.perf_counter() - t0) * 1000.0
        vera["timing"] = {"vera_ms": round(total, 3), "llm_ms": 0.0, "tiers_ms": per_ms}
        vera["no_llm"] = True
        vera["profile"] = self.profile
        vera["assumptions"] = []
        vera["assumptions_status"] = ASSUMPTIONS_NOT_WIRED if self.profile == "assume" else ASSUMPTIONS_NOT_USED
        vera["confidence_tiers"] = ct
        vera["initial_layers"] = self.initial_layers()
        return res
