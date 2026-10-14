"""What Vera Harness recognises as a secret in TEXT IT RECORDS (a user's memory message, a question, a document sentence), and how it is replaced.  Pure; no I/O.

Detection runs on an NFKC-normalised copy (full-width `ｐａｓｓｗｏｒｄ＝ｈｕ７…`, `＝`, `：` become ASCII), and the span found there is mapped back to the ORIGINAL text, which is what gets
replaced by 「[redacted:<sha256-8 of the original span>]」.  Recognised, exactly:

  labels      password, passwd, passphrase, pwd, pass, secret, client_secret, token, auth, key, api_key, apikey, access_key, private_key, credential(s), パスワード, 暗証番号, 合言葉
              (case-insensitive; as a whole word or the end of an identifier such as DB_PASSWORD), followed by `=` or `:` (also full-width, or `%3D`), or, for the Japanese labels, は; optional
              quotes and spaces (also tab, newline, no-break and zero-width spaces) around the separator.  The VALUE is the whole token to the next white space, 。 or 、 (it may continue after a
              CJK character: password=Hu7n漢terQz), whatever its length, `!` and `?` included; a quoted value runs to its closing quote.
  CLI         --password X, --passwd X, --token X, --secret X, --pass X, --api-key X, --key X (the value is the next token)
  URLs        scheme://user:pass@host  (user:pass is replaced)
  tokens      sk-…, Bearer …, ghp_/gho_/ghu_/ghs_/ghr_…, github_pat_…, AKIA…, AIza…, xox[abprs]-…, private-key blocks, whatever their length; plus the ledger's own detector for encoded variants

NOT detected: a secret with no label and no known prefix (a bare password in a sentence, a card or ID number, an address, a personal name...).  Do not type those into a memory, a question or a
document you give to Vera."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import List, Tuple

_WS = "\\s\u200b\u200c\u200d\ufeff"
_LABELS = (r"client[_-]?secret|api[_-]?key|apikey|access[_-]?key|private[_-]?key|passphrase|passwd|password|credentials?|secret|token|auth|pwd|pass|key|パスワード|暗証番号|合言葉")
_LABEL = re.compile(r"(?i)(?:%s)[\"']?[%s]*(?:%%3d|[=:]|(?<=ド)は|(?<=号)は|(?<=葉)は)[%s]*" % (_LABELS, _WS, _WS))
_CLI = re.compile(r"(?i)(?<![\w-])--(?:password|passwd|pass|token|secret|api-key|apikey|key)[%s]+" % _WS)
_URL = re.compile(r"(?i)[a-z][a-z0-9+.\-]*://([^/\s@:]+:[^/\s@]+)@")
_TOKEN_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)\bBearer[%s]+[^%s。、]+" % (_WS, _WS)),
    re.compile(r"gh[pousr]_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"AKIA[0-9A-Z]+"),
    re.compile(r"AIza[0-9A-Za-z_\-]+"),
    re.compile(r"xox[abprs]-[A-Za-z0-9\-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"),
)
_END = re.compile(r"[%s。、]" % _WS)
_QUOTES = "\"'`“”‘’"


def _normalise(text: str) -> Tuple[str, List[int]]:
    """(NFKC copy, for each character of the copy the index of the original character it came from)."""
    out: List[str] = []
    idx: List[int] = []
    for i, ch in enumerate(text):
        n = unicodedata.normalize("NFKC", ch)
        out.append(n)
        idx.extend([i] * len(n))
    return "".join(out), idx


def find_spans(text: str) -> List[Tuple[int, int]]:
    """The secret spans of `text` as (start, end) in the ORIGINAL string, merged and sorted."""
    d, idx = _normalise(text)
    spans: List[List[int]] = []

    def add(s: int, e: int) -> None:
        if e > s:
            spans.append([s, e])

    for pat in _TOKEN_PATTERNS:
        for m in pat.finditer(d):
            add(m.start(), m.end())
    for m in _URL.finditer(d):
        add(m.start(1), m.end(1))
    for rx in (_LABEL, _CLI):
        for m in rx.finditer(d):
            st = m.end()
            if st < len(d) and d[st] in _QUOTES:                       # a quoted value runs to its closing quote
                close = d.find(d[st], st + 1)
                add(st, (close + 1) if close != -1 else (_END.search(d, st).start() if _END.search(d, st) else len(d)))
            else:
                e = _END.search(d, st)
                add(st, e.start() if e else len(d))
    spans.sort()
    merged: List[List[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    out = []
    for s, e in merged:
        o0 = idx[s]
        o1 = idx[e - 1] + 1
        out.append((o0, o1))
    # the mapping can make two spans overlap in the original (multi-character expansions): merge again
    res: List[List[int]] = []
    for s, e in out:
        if res and s <= res[-1][1]:
            res[-1][1] = max(res[-1][1], e)
        else:
            res.append([s, e])
    return [(s, e) for s, e in res]


def marker(span_text: str) -> Tuple[str, str]:
    h = hashlib.sha256(span_text.encode("utf-8")).hexdigest()[:8]
    return "[redacted:%s]" % h, h


def redact(text: str) -> Tuple[str, List[str]]:
    """(text with every secret span replaced, the sha256-8 of each replaced span in text order)."""
    shas: List[str] = []
    t = text
    for s, e in reversed(find_spans(text)):
        m, h = marker(t[s:e])
        shas.append(h)
        t = t[:s] + m + t[e:]
    return t, list(reversed(shas))
