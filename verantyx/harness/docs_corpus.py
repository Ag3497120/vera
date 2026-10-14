"""Documents -> the corpus the loom reads.

The loom corpus is a JSONL file with one row per SENTENCE: {"sha": sha256(sent), "title": <document title>, "sent": <sentence>, "source": "<title>#<index>"}
(the same shape as the research corpora; the loom reads `sent` and `source`, and takes the article title from `source` minus the trailing `#N`).

Splitting is deliberately plain and deterministic, so that a quote can always be found again in the document: the text is never rewritten (no normalisation,
no translation); a sentence is a run of characters ending at one of 。！？!? (with any closing brackets / quotes that follow) or at a line break.  A blank line
only separates paragraphs.  Markdown markers at the start of a line (#, >, -, *, +, a numbered list marker) are removed, nothing else is.

Documents: .txt and .md (UTF-8).  A directory is walked recursively in sorted order; the title of a document is its file name without the extension.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Dict, Iterable, List, Sequence, Tuple

DOC_SUFFIXES = (".txt", ".md", ".markdown")
MAX_DOC_BYTES = 8 * 1024 * 1024
_END = "。！？!?"
_CLOSERS = "」』）)】〕］]”\"'’"
_MD_MARK = re.compile(r"^\s*(?:#{1,6}\s+|>+\s*|[-*+]\s+|\d{1,3}[.)]\s+)")
_FENCE = re.compile(r"^\s*(```|~~~)")


class DocsError(Exception):
    """A typed refusal while reading documents (`code` is a stable token)."""

    def __init__(self, msg: str, code: str = "docs_error") -> None:
        super().__init__("%s: %s" % (code, msg))
        self.code = code


def split_sentences(text: str) -> List[str]:
    """The sentences of a text, in order, each exactly as written (surrounding whitespace removed)."""
    out: List[str] = []
    in_fence = False
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _MD_MARK.sub("", raw).strip()
        if not line:
            continue
        buf: List[str] = []
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            buf.append(ch)
            if ch in _END:
                while i + 1 < n and line[i + 1] in _END + _CLOSERS:
                    i += 1
                    buf.append(line[i])
                s = "".join(buf).strip()
                if s:
                    out.append(s)
                buf = []
            i += 1
        s = "".join(buf).strip()
        if s:
            out.append(s)
    return out


def list_documents(path: str) -> List[Tuple[str, str]]:
    """[(title, file path)] for a file or a directory (recursive, sorted by relative path)."""
    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        files = []
        for dp, dn, fn in os.walk(path):
            dn[:] = sorted(d for d in dn if not d.startswith("."))
            for f in sorted(fn):
                if f.lower().endswith(DOC_SUFFIXES) and not f.startswith("."):
                    files.append(os.path.join(dp, f))
        files.sort(key=lambda p: os.path.relpath(p, path))
    else:
        raise DocsError("not a file or a directory: %s" % path, "docs_missing")
    if not files:
        raise DocsError("no .txt / .md document under %s" % path, "docs_empty")
    return [(os.path.splitext(os.path.basename(f))[0], f) for f in files]


def build_rows(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for title, f in list_documents(path):
        if os.path.getsize(f) > MAX_DOC_BYTES:
            raise DocsError("%s is larger than %d bytes" % (f, MAX_DOC_BYTES), "docs_too_large")
        try:
            text = open(f, encoding="utf-8").read()
        except UnicodeDecodeError as e:
            raise DocsError("%s is not UTF-8" % f, "docs_not_utf8") from e
        title = re.sub(r"#\d+$", "", title) or "doc"
        for k, s in enumerate(split_sentences(text)):
            rows.append({"sha": hashlib.sha256(s.encode("utf-8")).hexdigest(), "title": title, "sent": s, "source": "%s#%d" % (title, k)})
    if not rows:
        raise DocsError("the documents hold no sentence", "docs_empty")
    return rows


def corpus_bytes(rows: Iterable[Dict[str, str]]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode("utf-8")


def build_corpus(path: str) -> Tuple[bytes, List[Dict[str, str]]]:
    rows = build_rows(path)
    return corpus_bytes(rows), rows


def corpus_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
