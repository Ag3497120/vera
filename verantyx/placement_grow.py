"""W10-f05 (A11, docs/COARSE_PLACEMENT.md section 12.19): document-driven growth of a placement layer -- "read the documents and the domain's vocabulary grows into the placement".

    vera placement grow --documents f... --layer NAME --backend ollama|openai|fake --ledger-file L [--placement BASE]

(a) the documents are read (`document_loaders`, one body = one source: a body that is read twice is counted once, K292), the nouns and predicates are listed with the extraction of
    the builder (`tools.build_coarse_placement.tokenize` / `analyze`, imported, never copied), and the words the BASE placement leaves UNPLACED / UNKNOWN / MULTIPLE become candidates;
(b) an LLM (the routing role: `llm_backend`) is asked, for each candidate, a noun's definition + hypernym + one of the 18 types, or a predicate's type + role frame, with a closed enum
    JSON schema.  By default it is sent the candidate and the TYPED SHAPES of the sentences that hold it (K296), never the sentences.  Every answer is a TESTIMONY written to the ledger (K294);
(c) the documents themselves are an arm of the distribution (K292): `role_distribution` for a predicate, `hearst` for a noun, one source per document, the filler types from the BASE only (a layer
    never props itself up), and `coarse_types.decide_word` -- the one function of the builder -- decides with the generated arm added;
(d) what agrees is written to the layer as `layer_confirmed` (direct), what only the model said as `layer_estimated` (never read by the reader), and nothing else (K291).  A back end that fails
    writes nothing to the layer (K295).  `layer_human` is written by `vera ledger promote` from a human's `vera ledger confirm`, never here.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import itertools
import json
import os
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import coarse_place
from . import coarse_types as ct
from . import placement_layer as PL
from . import semantic_reader as R
from . import llm_backend

MODEL_VERSION_UNKNOWN = "VERSION_UNKNOWN"     # a typed value, never an empty string (the version of a testimony's source is `<digest>` or `VERSION_UNKNOWN:<reason>`)
BASIS = "LLM_TESTIMONY_PLACEMENT"
UNDECIDED_STATES = ("UNPLACED", "UNKNOWN", "MULTIPLE")
ARMS_NOT_BUILT = ("role", "slot", "definition", "sahen", "pos_class")     # the arms the documents do not feed (J5)
MAX_SHAPES = 3
KINDS = ("noun", "predicate")


def _nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


def _sha(text: str) -> str:
    return hashlib.sha256(_nfkc(text).encode("utf-8")).hexdigest()


def resolve_model_version(backend: str, model: str, *, ollama_url: Optional[str] = None, fake_digest: Optional[str] = None, injected: bool = False, timeout: float = 5.0) -> str:
    """The version of the model that answers (the provenance of a testimony).  ollama: the digest from the LOCAL ``/api/tags`` (127.0.0.1 / localhost / [::1] only; nothing else is asked);
    fake: ``fake-table:<12 hex of the table sha256>`` (``fake_digest`` given by the caller); anything that cannot be had is ``VERSION_UNKNOWN:<reason>`` (typed, never empty)."""
    if backend == "fake":
        return fake_digest if fake_digest else "%s:FAKE_WITHOUT_DIGEST" % MODEL_VERSION_UNKNOWN
    if injected:                                 # a caller's own chat function: nothing is asked of any endpoint
        return "%s:%s_ENDPOINT_HAS_NO_VERSION" % (MODEL_VERSION_UNKNOWN, backend.upper())
    if backend == "ollama":
        import urllib.parse
        import urllib.request
        url = ollama_url or llm_backend.OLLAMA_URL
        host = urllib.parse.urlparse(url).hostname or ""
        if host not in ("127.0.0.1", "localhost", "::1"):
            return "%s:NOT_LOCAL_HOST" % MODEL_VERSION_UNKNOWN
        try:
            with urllib.request.urlopen(url.rstrip("/") + "/api/tags", timeout=timeout) as resp:
                tags = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:                 # a typed unknown, not a crash and not an empty string
            return "%s:TAGS_FAILED:%s" % (MODEL_VERSION_UNKNOWN, type(exc).__name__)
        for m in tags.get("models") or []:
            if model in (m.get("name"), m.get("model")) and m.get("digest"):
                return "ollama-digest:%s" % m["digest"]
        return "%s:MODEL_NOT_IN_TAGS" % MODEL_VERSION_UNKNOWN
    return "%s:%s_HAS_NO_VERSION_ENDPOINT" % (MODEL_VERSION_UNKNOWN, backend.upper())


def _tools():
    """The builder's extraction and the generator's question forms: imported, never copied."""
    from tools import build_coarse_placement as bcp
    from tools import gen_coarse_evidence as gce
    return bcp, gce


# ------------------------------------------------------------------------------------------------------------------------ the questions (K295, K296)
def noun_schema() -> Dict[str, Any]:
    return {"type": "object", "additionalProperties": False, "required": ["items"],
            "properties": {"items": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["word", "definition", "hypernym", "type"],
                "properties": {"word": {"type": "string"}, "definition": {"type": ["string", "null"]}, "hypernym": {"type": ["string", "null"]},
                               "type": {"type": ["string", "null"], "enum": list(ct.NOUN_TYPES) + [None]}}}}}}


def predicate_schema() -> Dict[str, Any]:
    _bcp, gce = _tools()
    frame = copy.deepcopy(gce.ROLE_SCHEMA["properties"]["items"]["items"]["properties"]["frame"])
    return {"type": "object", "additionalProperties": False, "required": ["items"],
            "properties": {"items": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["word", "ptype", "frame"],
                "properties": {"word": {"type": "string"}, "ptype": {"type": ["string", "null"], "enum": list(ct.PRED_TYPES) + [None]}, "frame": frame}}}}}


_NOTE_SHAPES = ("- SHAPES_JSON は、各語が現れる文の形（〈語〉が対象の語、〈型〉は文の中のほかの語の型、助詞などはそのまま）。手がかりとして使ってよい。文の中身は渡されない。\n\n")
_NOTE_SENTENCES = "- SENTENCES_JSON は、各語が現れる文（最大 3 つ）。手がかりとして使ってよい。\n\n"


def noun_head(send_sentences: bool = False) -> str:
    """The generator's definition + hypernym rules (W3-a2), with the noun types listed from `coarse_types` (W3-a6)."""
    _bcp, gce = _tools()
    types = "\n".join("- %s: %s" % (k, v) for k, v in ct.NOUN_TYPES.items())
    notes = "\n".join("- %s: %s" % (k, v) for k, v in ct.NOUN_TYPE_NOTES.items())
    return (gce.PROMPT_HEAD + "名詞の型（id: 名称）:\n" + types + "\n\n型の補足:\n" + notes + "\n\n追加の規則:\n"
            "- type は名詞の型の id から 1 つ。当てはまる型が選べない、断片で語にならない語は type を null にする。無理に作らない。\n"
            + (_NOTE_SENTENCES if send_sentences else _NOTE_SHAPES))


def predicate_head(send_sentences: bool = False) -> str:
    """The generator's role-frame form (W3-a6 v2) with the predicate types listed from `coarse_types`."""
    _bcp, gce = _tools()
    types = "\n".join("- %s: %s" % (k, v) for k, v in ct.PRED_TYPES.items())
    return (gce.ROLE_PROMPT_HEAD + "述語の型（id: 名称）:\n" + types + "\n\n追加の規則:\n"
            "- 各語に ptype（述語の型の id）も書く。当てはまる型が選べない、断片で語にならない語は ptype を null、frame を null にする。\n"
            + (_NOTE_SENTENCES if send_sentences else _NOTE_SHAPES))


def build_prompt(kind: str, words: Sequence[str], context: Dict[str, List[str]], send_sentences: bool) -> str:
    _bcp, gce = _tools()
    head = noun_head(send_sentences) if kind == "noun" else predicate_head(send_sentences)
    ctx_key = "SENTENCES_JSON: " if send_sentences else "SHAPES_JSON: "
    return head + gce.WORDS_PREFIX + json.dumps(list(words), ensure_ascii=False) + "\n" + ctx_key + json.dumps({w: context.get(w, []) for w in words}, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------------------------------------------------ fake back ends (tests; K295)
class TableBackend:
    """A scripted back end for tests and for the CLI's ``--backend fake``: the words of the question are looked up in a table (word -> declaration; a word that is not in it is answered
    with nulls, an abstention).  ``__fail_batches__`` (a list of call indexes) are answered with a typed failure.  Everything sent is kept in ``sent``."""

    def __init__(self, table: Dict[str, Any]) -> None:
        self.table = {k: v for k, v in table.items() if not str(k).startswith("_")}
        self.fail = set(table.get("__fail_batches__") or [])
        self.sent: List[Dict[str, Any]] = []
        self.calls = 0

    def __call__(self, model: str, messages, fmt, *, timeout: float = 180.0, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        self.sent.append({"model": model, "messages": json.loads(json.dumps(list(messages), ensure_ascii=False)), "fmt": json.loads(json.dumps(fmt, ensure_ascii=False)) if fmt is not None else None})
        i = self.calls
        self.calls += 1
        if i in self.fail:
            return {"ok": False, "content": None, "usage": {}, "error": {"type": "TIMEOUT", "detail": "scripted"}}
        prompt = "\n".join(str(m.get("content", "")) for m in messages if m.get("role") == "user")
        words = []
        for line in prompt.split("\n"):
            if line.startswith("WORDS_JSON: "):
                words = json.loads(line[len("WORDS_JSON: "):])
        item_props = (((fmt or {}).get("properties") or {}).get("items") or {}).get("items", {}).get("properties", {})
        pred = "ptype" in item_props
        items = []
        for w in words:
            d = self.table.get(w) or {}
            if pred:
                items.append({"word": w, "ptype": d.get("ptype"), "frame": d.get("frame")})
            else:
                items.append({"word": w, "definition": d.get("definition"), "hypernym": d.get("hypernym"), "type": d.get("type")})
        return {"ok": True, "content": json.dumps({"items": items}, ensure_ascii=False), "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}, "error": None}


# ------------------------------------------------------------------------------------------------------------------------ parsing the answers
def parse_noun_batch(words: Sequence[str], content: Any) -> Dict[str, Tuple[Optional[Dict[str, Any]], Optional[str]]]:
    """``{word: (declaration, None) | (None, reason)}``.  A word that is missing, repeated, or answered with an invalid type is `DECLARATION_INVALID:*`; null is `DECLARATION_NULL`."""
    _bcp, gce = _tools()
    data, bad = _json(content)
    if bad:
        return {w: (None, "DECLARATION_INVALID:" + bad) for w in words}
    try:
        seen, _foreign = gce._by_word(words, data)
    except ValueError:
        return {w: (None, "DECLARATION_INVALID:NO_ITEMS") for w in words}
    out: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[str]]] = {}
    for w in words:
        got = seen.get(w)
        if not got:
            out[w] = (None, "DECLARATION_INVALID:MISSING")
        elif len(got) > 1:
            out[w] = (None, "DECLARATION_INVALID:DUPLICATE")      # a word that comes back twice is not taken: no entry is chosen by order
        else:
            it = got[0]
            t, d, h = it.get("type"), it.get("definition"), it.get("hypernym")
            if t is None:
                out[w] = (None, "DECLARATION_NULL")
            elif not isinstance(t, str) or t not in ct.NOUN_TYPES or (d is not None and not isinstance(d, str)) or (h is not None and not isinstance(h, str)):
                out[w] = (None, "DECLARATION_INVALID:TYPE")
            else:
                out[w] = ({"type": t, "kind": "noun", "definition": d, "hypernym": h, "frame": None}, None)
    return out


def parse_predicate_batch(words: Sequence[str], content: Any) -> Dict[str, Tuple[Optional[Dict[str, Any]], Optional[str]]]:
    _bcp, gce = _tools()
    data, bad = _json(content)
    if bad:
        return {w: (None, "DECLARATION_INVALID:" + bad) for w in words}
    try:
        seen, _foreign = gce._by_word(words, data)
    except ValueError:
        return {w: (None, "DECLARATION_INVALID:NO_ITEMS") for w in words}
    out: Dict[str, Tuple[Optional[Dict[str, Any]], Optional[str]]] = {}
    for w in words:
        got = seen.get(w)
        if not got:
            out[w] = (None, "DECLARATION_INVALID:MISSING")
            continue
        if len(got) > 1:
            out[w] = (None, "DECLARATION_INVALID:DUPLICATE")
            continue
        pt, fr = got[0].get("ptype"), got[0].get("frame")
        if pt is None:
            out[w] = (None, "DECLARATION_NULL")
            continue
        if not isinstance(pt, str) or pt not in ct.PRED_TYPES:
            out[w] = (None, "DECLARATION_INVALID:PTYPE")
            continue
        frame: Optional[Dict[str, List[dict]]] = None
        if fr is not None:
            ans, info = gce.parse_output_role([w], {"items": [{"word": w, "frame": fr}]})
            if w not in ans:
                out[w] = (None, "DECLARATION_INVALID:FRAME")
                continue
            frame = ans[w] or None
        out[w] = ({"type": pt, "kind": "predicate", "definition": None, "hypernym": None, "frame": frame}, None)
    return out


def _json(content: Any):
    if not isinstance(content, str) or not content.strip():
        return None, "EMPTY_CONTENT"
    try:
        return json.loads(content), None
    except ValueError:
        return None, "BAD_JSON"


# ------------------------------------------------------------------------------------------------------------------------ the decision of one candidate (K291; pure)
def normalize_frame(frame: Any) -> Optional[Dict[str, List[dict]]]:
    """The role frame as `{particle: [{role, types}]}`: a back end's list form `[{particle, roles}]` is read with the generator's own reader (None when it is not a valid frame)."""
    if frame is None or isinstance(frame, dict):
        return frame or None
    _bcp, gce = _tools()
    ans, _info = gce.parse_output_role(["w"], {"items": [{"word": "w", "frame": frame}]})
    return (ans.get("w") or None) if "w" in ans else None


def _slot_rows(src: str, frame: Optional[Dict[str, List[dict]]]) -> List[tuple]:
    rows = []
    for p in ct.CASE_PARTICLES_9:
        types = sorted({t for e in (frame or {}).get(p, []) for t in e["types"]})
        for t in types:
            rows.append(("gen_frame_slot", src, "%s|%s" % (p, t), 1, None))
    return rows


def decide_candidate(word: str, decl: Dict[str, Any], doc_rows: Sequence[tuple], cfg: Dict[str, Any], *, model: str = "", hypernym_base_type: Optional[str] = None) -> Dict[str, Any]:
    """The declaration (``decl``: noun `{type, ...}`, predicate `{type: the ptype, frame}`) laid over the documents' rows.  Returns ``{"write": "layer_confirmed" | "layer_estimated" | None,
    "reason": a closed reason when nothing is written, "decision": {state, tops, by, origin}, "rows": the rows decided on}``.  Direct only when the generated arm and the documents agree (or the
    documents alone decided exactly the declared type); a model alone is an estimate; a contradiction by the documents writes nothing."""
    kind = decl["kind"]
    t = decl["type"]
    decl = dict(decl, frame=normalize_frame(decl.get("frame")))
    gen_src = "generated:%s:layer" % (model or "unknown")
    garm = ct.GEN_ARM if kind == "noun" else ct.GEN_FRAME_ARM
    if kind == "noun" and hypernym_base_type is not None and hypernym_base_type != t:
        return {"write": None, "reason": "HYPERNYM_TYPE_DISAGREES", "decision": None, "rows": list(doc_rows)}
    gen_rows = [(ct.GEN_ARM, gen_src, t, 1, None)] if kind == "noun" else [(ct.GEN_FRAME_ARM, gen_src, t, 1, None)] + _slot_rows(gen_src, decl.get("frame"))
    ev = [tuple(r) for r in doc_rows] + gen_rows
    dec = ct.decide_word(ev, cfg)
    summary = {"state": dec["state"], "tops": list(dec.get("tops") or []), "by": list(dec.get("by") or []), "origin": dec.get("origin")}
    out = {"write": None, "reason": None, "decision": summary, "rows": ev, "dec": dec}
    if dec["state"] == "DECIDED" and dec.get("origin") == "direct":
        if garm in dec["by"] or dec["tops"][0] == t:
            out["write"] = "layer_confirmed"
        else:
            out["reason"] = "GEN_DISAGREES_WITH_DOCUMENTS"
    elif dec["state"] == "DECIDED":
        why = (dec["arms"].get(garm) or {}).get("why")
        if why == "DISTRIBUTION_DISAGREES":
            out["reason"] = "DISTRIBUTION_DISAGREES"
        else:
            out["write"] = "layer_estimated"
    elif dec["state"] == "MULTIPLE":
        out["reason"] = "DOCUMENT_ARMS_SPLIT"
    else:
        out["reason"] = "NOT_PLACED:%s" % ((dec["arms"].get(garm) or {}).get("why") or dec["state"])
    return out


# ------------------------------------------------------------------------------------------------------------------------ documents
def read_documents(paths: Sequence[str]) -> Dict[str, Any]:
    """Each file once (by the NFKC sha of its body): ``{"docs": [{"path","source","sha","records"}], "skipped": [...], "loaded": n}`` (K292, K293: the files are only read)."""
    from pathlib import Path
    from . import cli
    from . import document_loaders as DL
    files: List[str] = []
    skipped: List[Dict[str, Any]] = []
    for item in paths:
        p = Path(item)
        if p.is_dir():
            files.extend(sorted(str(f) for f in p.rglob("*") if f.is_file() and f.suffix.lower() in DL.SUPPORTED))
        else:
            files.append(str(p))
    docs, seen = [], {}
    for f in files:
        res = DL.load_path(f)
        if res.get("verdict") != "ANSWER":
            skipped.append({"path": f, "verdict": res.get("verdict"), "reason": "UNREADABLE_DOCUMENT"})
            continue
        sha = _sha(res["document"].text)
        if sha in seen:
            skipped.append({"path": f, "reason": "DUPLICATE_DOCUMENT:%s" % sha, "same_as": seen[sha]})
            continue
        seen[sha] = f
        records, _where, _n, _sk = cli._qc_records([f])
        docs.append({"path": f, "source": "doc:%s" % sha[:12], "sha": sha, "records": [r["text"] for r in records]})
    return {"docs": docs, "skipped": skipped, "loaded": len(docs)}


# ------------------------------------------------------------------------------------------------------------------------ the typed shape of a sentence (K296)
def _shape(toks, hit: Tuple[int, int], type_of_token: Callable[[Tuple[str, str, str, Optional[str]]], str]) -> str:
    out, i = [], 0
    while i < len(toks):
        if i == hit[0]:
            out.append("〈語〉")
            i = hit[1]
            continue
        s, p1, _p2, _ob = toks[i]
        out.append(s if p1 in ("助詞", "助動詞", "補助記号") else "〈%s〉" % type_of_token(toks[i]))
        i += 1
    return "".join(out)


def _find_hit(toks, word: str, kind: str) -> Optional[Tuple[int, int]]:
    n = len(toks)
    for i in range(n):
        if kind == "noun":
            for j in range(i + 1, min(n, i + 6) + 1):
                if "".join(t[0] for t in toks[i:j]) == word or (j == i + 1 and (toks[i][3] or toks[i][0]) == word):
                    return (i, j)
        else:
            t = toks[i]
            if t[1] in ("動詞", "形容詞", "形状詞") and (t[3] or t[0]) == word:
                return (i, i + 1)
            if i + 1 < n and word.endswith("する") and toks[i][1] == "名詞" and toks[i + 1][3] == "する" and (toks[i][3] or toks[i][0]) + "する" == word:
                return (i, i + 2)
    return None


# ------------------------------------------------------------------------------------------------------------------------ the run
class _Base:
    """The base placement alone (layer=False: a layer never props itself up), cached."""

    def __init__(self, placement: Optional[str]) -> None:
        self.placement = placement
        self._q: Dict[str, Dict[str, Any]] = {}
        self._t: Dict[str, Optional[str]] = {}

    def query(self, w: str) -> Dict[str, Any]:
        if w not in self._q:
            self._q[w] = coarse_place.query(w, placement=self.placement, layer=False)
        return self._q[w]

    def noun_type(self, w: str) -> Optional[str]:
        """The type the READER may use for ``w`` (the K62 gate), noun types only."""
        if w not in self._t:
            t, why = R.placement_type(self.query(w))
            self._t[w] = t if (why is None and t and not t.startswith("P_")) else None
        return self._t[w]

    def get(self, w: str, default=None):                      # a `donors` for `bcp.type_of`
        return self.noun_type(w) or default


def grow(documents: Sequence[str], layer_spec: str, *, backend: str, model: str, ledger_path: str, placement: Optional[str] = None,
         chat: Optional[Callable] = None, min_sources: int = 1, max_words: int = 200, batch_size: int = 10, send_sentences: bool = False,
         timeout: float = 180.0, ollama_url: Optional[str] = None, dump_sent: Optional[str] = None, model_version: Optional[str] = None, clock: Callable[[], float] = time.perf_counter) -> Dict[str, Any]:
    """One growth run; returns the report (also what `vera placement grow` prints as one JSON line).  A typed refusal is `{"verdict": ...}` and writes nothing."""
    from .llm_choice import LedgerIntegrityError
    from .testimony_ledger import TestimonyLedger, key_of
    t_start = clock()
    llm_ms = 0.0
    if min_sources < 1 or batch_size < 1 or max_words < 1:
        return {"verdict": "BAD_ARGUMENT", "reason": "min_sources, batch_size and max_words must be positive"}
    layer_path, layer_name, why = PL.resolve(layer_spec)
    if layer_path is None:
        return {"verdict": "LAYER_UNAVAILABLE:%s" % why, "reason": layer_spec}
    pl, nop = coarse_place._open(placement)
    if pl is None:
        return {"verdict": "NO_PLACEMENT", "reason": nop[0] if nop else "UNSET"}
    if os.path.exists(layer_path):
        lay, lwhy = PL.open_layer(layer_path, pl.sha)
        if lay is None:
            return {"verdict": "LAYER_UNAVAILABLE:%s" % lwhy, "reason": layer_path}
    try:
        ledger = TestimonyLedger(ledger_path)
    except LedgerIntegrityError as exc:
        return {"verdict": "LEDGER_INTEGRITY", "reason": "%s line %s %s" % (exc.kind, exc.line_no, exc.detail)}
    rows_before = len(ledger.entries())
    bcp, _gce = _tools()
    import fugashi
    cfg = dict(pl.cfg)
    cfg["rd_min_sources"] = cfg["role_frame_min_sources"] = int(min_sources)
    maxc = cfg["max_word_chars"]
    base = _Base(placement)

    # ---- (a) the documents and the candidates
    read = read_documents(documents)
    tagger = fugashi.Tagger()
    accs: Dict[str, dict] = {}
    sent_words: List[Tuple[str, str, list, List[str]]] = []     # (doc source, sentence text, tokens, the words of the sentence in the order the extraction met them)
    for d in read["docs"]:
        acc = bcp._empty_acc()
        for text in d["records"]:
            toks = bcp.tokenize(tagger, text)
            bcp.analyze(toks, acc, maxc)
            one = bcp._empty_acc()
            bcp.analyze(toks, one, maxc)
            sent_words.append((d["source"], text, toks, list(dict.fromkeys(w for (w, _k) in one["pos"]))))
        accs[d["source"]] = acc
    kinds: Dict[str, set] = defaultdict(set)
    order: List[str] = []
    seen_order = set()
    for _src, _text, _toks, ws in sent_words:
        for w in ws:
            if w not in seen_order:
                seen_order.add(w)
                order.append(w)
    for acc in accs.values():
        for (w, k), _n in acc["pos"].items():
            kinds[w].add("N" if k == "N" else "P")
    counters: Counter = Counter()
    candidates: List[Tuple[str, str]] = []
    for w in order:
        ks = kinds.get(w)
        if not ks:
            continue
        if len(ks) > 1:
            counters["KIND_SPLIT"] += 1
            continue
        a = base.query(w)
        if a["state"] == "NO_PLACEMENT":
            return {"verdict": "NO_PLACEMENT", "reason": "the base placement did not open"}
        if a["state"] not in UNDECIDED_STATES:
            counters["BASE_DECIDED"] += 1
            continue
        candidates.append((w, "noun" if "N" in ks else "predicate"))
    skipped_budget = max(0, len(candidates) - max_words)
    candidates = candidates[:max_words]
    cand_words = {w for w, _k in candidates}

    # the typed shapes (or, with --send-sentences, the sentences) that hold each candidate
    def tok_type(tok) -> str:
        w = tok[3] or tok[0]
        a = base.query(w)
        t, _why = R.placement_type(a)
        return t if t else "未定"

    context: Dict[str, List[str]] = {}
    first_sentence: Dict[str, str] = {}
    first_doc: Dict[str, str] = {}
    doc_ids_of: Dict[str, List[str]] = {}
    n_sent: Counter = Counter()
    for src, text, toks, ws in sent_words:
        wset = set(ws)
        for w, k in candidates:
            if w not in wset:
                continue
            n_sent[w] += 1
            first_sentence.setdefault(w, text)
            first_doc.setdefault(w, src)
            if src not in doc_ids_of.setdefault(w, []):
                doc_ids_of[w].append(src)
            if len(context.setdefault(w, [])) >= MAX_SHAPES:
                continue
            if send_sentences:
                context[w].append(text)
                continue
            hit = _find_hit(toks, w, k)
            if hit is not None:
                shp = _shape(toks, hit, tok_type)
                if shp not in context[w]:
                    context[w].append(shp)

    # ---- (b) the questions
    sent_log: List[Dict[str, Any]] = []

    def ask(kind: str, batch: Sequence[str]) -> Dict[str, Any]:
        nonlocal llm_ms
        prompt = build_prompt(kind, batch, context, send_sentences)
        fmt = noun_schema() if kind == "noun" else predicate_schema()
        msgs = [{"role": "user", "content": prompt}]
        sent_log.append({"model": model, "kind": kind, "words": list(batch), "messages": msgs})
        t0 = clock()
        try:
            res = chat(model, msgs, fmt)
        except Exception as exc:                  # a back end that raises is a typed failure, never a crash
            res = {"ok": False, "content": None, "error": {"type": "CONNECT_FAILED", "detail": "%s: %s" % (type(exc).__name__, exc)}}
        llm_ms += (clock() - t0) * 1000.0
        return res

    injected_chat = chat is not None
    if chat is None:
        chat = llm_backend.make_chat(backend, url=ollama_url, timeout=timeout) if backend == "ollama" else llm_backend.make_chat(backend, timeout=timeout)
    version = model_version if model_version else resolve_model_version(backend, model, ollama_url=ollama_url, injected=injected_chat)
    decls: Dict[str, Tuple[Optional[Dict[str, Any]], str, Optional[str]]] = {}   # word -> (declaration, status, reason)
    asked = 0
    for kind in KINDS:
        words = [w for w, k in candidates if k == kind]
        for i in range(0, len(words), batch_size):
            batch = words[i:i + batch_size]
            asked += len(batch)
            res = ask(kind, batch)
            if not res.get("ok"):
                for w in batch:
                    decls[w] = (None, "BACKEND_FAILED", "BACKEND_FAILED:%s" % (res.get("error") or {}).get("type", "BAD_RESPONSE"))
                continue
            parsed = (parse_noun_batch if kind == "noun" else parse_predicate_batch)(batch, res.get("content"))
            for w, (decl, reason) in parsed.items():
                decls[w] = (decl, "ADOPTED", None) if decl is not None else (None, "NOT_ADOPTED", reason)

    # ---- the testimony: one ledger row per candidate (K294)
    fills: Dict[str, Dict[str, Any]] = {}
    for w, kind in candidates:
        decl, status, reason = decls.get(w, (None, "NOT_ADOPTED", "DECLARATION_INVALID:NOT_ASKED"))
        fid = "grow-" + uuid.uuid4().hex[:16]
        d_ledger = None
        if decl is not None:
            d_ledger = {"type": decl["type"], "role": None, "kind": kind, "definition": decl.get("definition"), "hypernym": decl.get("hypernym"), "frame": decl.get("frame")}
        ctx = {"doc_id": first_doc.get(w), "doc_ids": list(doc_ids_of.get(w, [])), "sentence_sha256": _sha(first_sentence[w]) if w in first_sentence else None, "n_sentences": n_sent[w]}
        if send_sentences and w in first_sentence:
            ctx["sentence"] = first_sentence[w]
        row = ledger.record_decision({"fill_id": fid, "word": w, "declaration": d_ledger, "candidate": w, "hole": None,
                                      "provenance": {"backend": backend, "model": model, "version": version, "send_sentences": bool(send_sentences)}, "context": ctx,
                                      "gate_log": [], "status": status, "reason": reason or ("PLACEMENT_DECLARATION" if status == "ADOPTED" else status), "choice_decision_id": None,
                                      "basis": "%s:%s" % (BASIS, model) if status == "ADOPTED" else None, "mask_user_text": not send_sentences, "records_checked": 0})
        fills[w] = {"fill_id": fid, "kind": kind, "decl": decl, "status": status, "reason": reason, "seq": row["row"]["seq"]}

    # ---- (c) the documents as an arm of the distribution (K292)
    donors = base
    min_suffix = cfg["min_suffix_chars"]
    rd_by_word: Dict[str, List[tuple]] = defaultdict(list)
    hearst_by_word: Dict[str, List[tuple]] = defaultdict(list)
    case9 = set(ct.CASE_PARTICLES_9)
    adopted_preds = {w for w, f in fills.items() if f["status"] == "ADOPTED" and f["kind"] == "predicate"}
    adopted_nouns = {w for w, f in fills.items() if f["status"] == "ADOPTED" and f["kind"] == "noun"}
    for src, acc in accs.items():
        rd: Dict[str, Counter] = defaultdict(Counter)
        for (fr, fh, m, verb, _past), n in itertools.chain(acc["chain"].items(), acc["chain_sahen"].items()):
            if verb not in adopted_preds or m not in case9:
                continue
            ft = base.noun_type(fr) if fr else None
            if ft is None and fh:
                ft = base.noun_type(fh)
            if ft is not None:
                rd[verb][(m, ft)] += n
        for verb, c in rd.items():
            total = sum(c.values())
            if total >= cfg["rd_store_min"]:
                for (part, typ), n in sorted(c.items()):
                    rd_by_word[verb].append(("role_distribution", src, "%s|%s" % (part, typ), n, total))
        hs: Dict[str, Counter] = defaultdict(Counter)
        for (a, y), n in acc["hearst"].items():
            if a in adopted_nouns:
                t = bcp.type_of(y, donors, min_suffix)
                if t:
                    hs[a][t] += n
        for a, c in hs.items():
            for t, n in sorted(c.items()):
                hearst_by_word[a].append(("hearst", src, t, n, None))

    # ---- (d) decide and write
    written: Counter = Counter()
    not_written: Counter = Counter()
    wrote_words: Dict[str, str] = {}
    for w, f in fills.items():
        if f["status"] != "ADOPTED":
            not_written[f["reason"]] += 1
            continue
        decl = f["decl"]
        rows = list(rd_by_word.get(w, []) if f["kind"] == "predicate" else hearst_by_word.get(w, []))
        hyp_t = None
        if f["kind"] == "noun" and decl.get("hypernym"):
            hyp_t = base.noun_type(_nfkc(decl["hypernym"]))
        res = decide_candidate(w, decl, rows, cfg, model=model, hypernym_base_type=hyp_t)
        if res["write"] is None:
            not_written[res["reason"]] += 1
            continue
        t = decl["type"]
        key = key_of(w, w, t, None)
        by = list(res["dec"]["by"])
        doc_rows = [list(r) for r in rows]
        evidence = {"model": model, "doc_ids": sorted({r[1] for r in rows}), "decision": res["decision"], "doc_rows": doc_rows,
                    "declaration": {"definition": decl.get("definition"), "hypernym": decl.get("hypernym"), "kind": f["kind"]}, "fill_id": f["fill_id"]}
        if res["write"] == "layer_confirmed":
            ledger.mark_distribution_backed(w, w, t, None, f["fill_id"], {"state": res["decision"]["state"], "top": res["decision"]["tops"], "origin": res["decision"]["origin"], "decided_by": by})
        try:
            PL.write_entry(layer_path, ledger, base_sha256=pl.sha, word=w, type=t, origin=res["write"], decided_by=by, evidence=evidence, role_frame=decl.get("frame"), key=key,
                           fill_id=f["fill_id"], candidate=w, from_seq=[f["seq"]])
        except PL.LayerError as exc:
            return {"verdict": exc.type, "reason": exc.detail, "written": dict(written), "note": "the run stopped at its first layer error; rows already written stay (append only)"}
        written[res["write"]] += 1
        wrote_words[w] = res["write"]
    ledger.promote_pending()

    if dump_sent:
        with open(dump_sent, "w", encoding="utf-8") as fh:
            for rec in sent_log:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total_ms = (clock() - t_start) * 1000.0
    declared = Counter(f["kind"] for f in fills.values() if f["status"] == "ADOPTED")
    return {"verdict": "GREW", "layer": layer_name, "layer_path": layer_path, "base_content_sha256": pl.sha,
            "documents": {"read": read["loaded"], "skipped": read["skipped"], "sources": [d["source"] for d in read["docs"]], "sentences": len(sent_words)},
            "candidates": len(candidates) + skipped_budget, "candidates_asked": asked, "skipped_budget": skipped_budget,
            "not_candidate": dict(counters), "declared": {"noun": declared.get("noun", 0), "predicate": declared.get("predicate", 0)},
            "backend_failed": sum(1 for f in fills.values() if f["status"] == "BACKEND_FAILED"),
            "written": {o: written.get(o, 0) for o in PL.ORIGINS}, "not_written": dict(sorted(not_written.items())),
            "arms_not_built": ["ARM_NOT_BUILT:%s" % a for a in ARMS_NOT_BUILT], "min_sources": int(min_sources), "send_sentences": bool(send_sentences),
            "timing": {"vera_ms": round(total_ms - llm_ms, 3), "llm_ms": round(llm_ms, 3), "calls": len(sent_log)},
            "ledger": {"path": str(ledger_path), "rows_added": len(ledger.entries()) - rows_before, "store_id": ledger.store_id}}
