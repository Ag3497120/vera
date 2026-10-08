"""Two-stage verdicts: Vera first (0.1 ms, rules), Bonsai only for what the rules could not tie.

Vera's verdict stands when it is decisive by rule: SUPPORTED, CONTRADICTED, VIOLATES,
OUT_OF_SCOPE, and UNCONFIRMED for hedged claims or unmet conditions. A claim goes to
Bonsai when the rules may have missed a paraphrase: NOT_IN_DOCS or DIFFERENT while the
records share its predicate or a participant word, and UNCONFIRMED because the claim
could not be read. All of one document's escalated claims go in one call.

Bonsai's answer is checked in code before it is used: it must quote a record sentence
verbatim, and a verdict that would pass a claim (SUPPORTED) or stop one (CONTRADICTED,
VIOLATES) without a verified quote falls back to UNCONFIRMED. The harmful direction is
never taken on the model's word alone."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Dict, List

from verantyx.frames import read_all
from verantyx.typed_edges import _tagger
from verantyx.verdict import Item, judge, read_records

URL = "http://localhost:1234/v1/chat/completions"
MODEL = "prism-ml/bonsai-27b:2"
LABELS = ["SUPPORTED", "DIFFERENT", "CONTRADICTED", "VIOLATES", "UNCONFIRMED", "NOT_IN_DOCS", "OUT_OF_SCOPE"]
DECIDING = {"SUPPORTED", "CONTRADICTED", "VIOLATES"}

SCHEMA = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {
    "i": {"type": "integer"}, "label": {"type": "string", "enum": LABELS}, "quote": {"type": "string"}},
    "required": ["i", "label", "quote"]}}}, "required": ["results"]}

PROMPT = """次の文書に照らして、各主張を1つのラベルで判定してください。言い換え（同じ物・同じ行為を別の語で言ったもの）は同じとみなします。
ラベル: SUPPORTED=文書から導ける（条件・例外を満たす範囲で） / DIFFERENT=同じ出来事だが役や対象がずれていて、同時に成り立ち得る / CONTRADICTED=記録の事実と同時に成り立たない / VIOLATES=事実の主張が文書の禁止・義務に反する（条件・例外を満たすなら違反ではない） / UNCONFIRMED=文書の言葉からは裏付けも否定もできない / NOT_IN_DOCS=文書に無い出来事 / OUT_OF_SCOPE=事実の主張でない
quote には根拠にした文書の文を1文そのまま書く（無ければ空）。

# 文書（{kind}）
{doc}

# 主張
{claims}

JSON: {{"results": [{{"i": 番号, "label": "...", "quote": "..."}}, ...]}}"""


def _words(t: str) -> set:
    return {w.feature.lemma or w.surface for w in _tagger()(t)
            if w.feature.pos1 in ("名詞", "動詞") and len(w.surface) > 1}


def needs_llm(v: dict, claim: str, items: List[Item], doc_words: set) -> bool:
    verdict, why = v["verdict"], v.get("why", "")
    if verdict in ("SUPPORTED", "CONTRADICTED", "VIOLATES", "OUT_OF_SCOPE"):
        return False
    if verdict == "UNCONFIRMED":
        return why == "unread"
    # NOT_IN_DOCS / DIFFERENT: only when the records could be saying it in other words
    return len(_words(claim) & doc_words) >= 1


def _ask(prompt: str, timeout: int = 180) -> dict:
    body = {"model": MODEL, "temperature": 0, "max_tokens": 6000, "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "r", "schema": SCHEMA}}}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        m = json.loads(r.read())["choices"][0]["message"]
    for text in (m.get("content") or "", m.get("reasoning_content") or ""):
        a, b = text.find("{"), text.rfind("}")
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except ValueError:
                continue
    return {"results": []}


def verify(text: str, claims: List[str], doc_kind: str = "record", use_llm: bool = True) -> List[dict]:
    items = read_records(text, doc_kind)
    doc_sents = [s.strip() for s in re.split(r"(?<=。)", text) if s.strip()]
    doc_words = _words(text)
    out = []
    for c in claims:
        v = judge(items, c)
        out.append({"claim": c, **v, "stage": "vera"})
    esc = [i for i, (c, r) in enumerate(zip(claims, out)) if use_llm and needs_llm(r, c, items, doc_words)]
    if esc:
        t = time.time()
        prompt = PROMPT.format(kind="規程" if doc_kind == "rules" else "記録", doc=text,
                               claims="\n".join("%d. %s" % (i, claims[i]) for i in esc))
        try:
            res = {r.get("i"): r for r in _ask(prompt).get("results", [])}
        except Exception as e:  # recorded, not hidden: Vera's verdict stays
            res, err = {}, str(e)[:80]
        secs = time.time() - t
        for i in esc:
            r = res.get(i)
            if not r:
                out[i]["llm"] = "no answer"
                continue
            label, quote = r.get("label"), (r.get("quote") or "").strip()
            quoted = bool(quote) and any(quote in s or s in quote for s in doc_sents)
            if label in DECIDING and not quoted:
                label = "UNCONFIRMED"          # no verified quote: never pass or stop on the model's word
            if out[i]["verdict"] == "DIFFERENT" and label == "SUPPORTED":
                label = "DIFFERENT"            # rules found the roles differ; the model may not pass it over that
            out[i].update({"verdict": label, "stage": "bonsai", "quote": quote if quoted else "",
                           "vera_said": out[i]["verdict"], "llm_seconds": round(secs, 1)})
    return out
