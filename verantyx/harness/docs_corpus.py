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
import stat
from typing import Dict, Iterable, List, Sequence, Tuple

DOC_SUFFIXES = (".txt", ".md", ".markdown")
MAX_DOC_BYTES = 8 * 1024 * 1024
_END = "。！？!?"
_CLOSERS = "」』）)】〕］]”\"'’"
_OPEN = "「『（(【〔［["
_CLOSE = "」』）)】〕］]"
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
        depth = 0                                       # inside 「」 『』 （） ... a terminator does not end the sentence; a line break resets it
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            buf.append(ch)
            if ch in _OPEN:
                depth += 1
            elif ch in _CLOSE and depth > 0:
                depth -= 1
            elif ch in _END and depth == 0:
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


def _escape_title(t: str) -> str:
    """A '#' in a file name would be read as the sentence-number separator of the source label (料金#3.md would collide with 料金.md); it becomes the full-width ＃."""
    return t.replace("#", "＃")


def list_documents(path: str) -> List[Tuple[str, str]]:
    """[(title, file path)] for a file or a directory (recursive, sorted by relative path).

    * only regular files with an allowed extension (.txt .md .markdown); a FIFO, a device or a socket is skipped (opening a FIFO would hang);
    * a symbolic link is followed only when its target is a regular file INSIDE the documents root: a link that points outside is refused (`docs_symlink_outside`), never read;
    * a single FILE given as the documents must have an allowed extension and be a regular file too (`docs_bad_extension`, `docs_not_regular`);
    * the title of a document (and so the label of its sentences, `<title>#<n>`) is its file name without the extension; when two documents would share a title it is their relative path
      (without, then with the extension), so every label names exactly one sentence of one file.  `#` in a name is escaped."""
    if os.path.exists(path) and not os.path.isdir(path):
        if not path.lower().endswith(DOC_SUFFIXES):
            raise DocsError("%s: only %s documents are read" % (path, " / ".join(DOC_SUFFIXES)), "docs_bad_extension")
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise DocsError("%s is not a regular file" % path, "docs_not_regular")
        return [(_escape_title(os.path.splitext(os.path.basename(path))[0]) or "doc", path)]
    if not os.path.isdir(path):
        raise DocsError("not a file or a directory: %s" % path, "docs_missing")
    root = os.path.realpath(path)
    files: List[str] = []
    for dp, dn, fn in os.walk(path):                       # os.walk does not descend into symbolic links to directories
        dn[:] = sorted(d for d in dn if not d.startswith("."))
        for f in sorted(fn):
            if not (f.lower().endswith(DOC_SUFFIXES) and not f.startswith(".")):
                continue
            full = os.path.join(dp, f)
            real = os.path.realpath(full)
            if os.path.islink(full) and not (real == root or real.startswith(root + os.sep)):
                raise DocsError("%s is a symbolic link to %s, outside the documents folder" % (full, real), "docs_symlink_outside")
            try:
                if not stat.S_ISREG(os.stat(real).st_mode):
                    continue
            except OSError:
                continue
            files.append(full)
    files.sort(key=lambda p: os.path.relpath(p, path))
    if not files:
        raise DocsError("no .txt / .md document under %s" % path, "docs_empty")
    rels = [os.path.relpath(f, path).replace(os.sep, "/") for f in files]
    stems = [os.path.splitext(r)[0] for r in rels]
    bases = [os.path.basename(x) for x in stems]
    out: List[Tuple[str, str]] = []
    for f, r, st, b in zip(files, rels, stems, bases):
        title = b if bases.count(b) == 1 else st if stems.count(st) == 1 else r
        out.append((_escape_title(title) or "doc", f))
    return out


def build_rows(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for title, f in list_documents(path):
        if os.path.getsize(f) > MAX_DOC_BYTES:
            raise DocsError("%s is larger than %d bytes" % (f, MAX_DOC_BYTES), "docs_too_large")
        try:
            with open(f, "rb") as fh:
                raw = fh.read(MAX_DOC_BYTES + 1)
            if len(raw) > MAX_DOC_BYTES:
                raise DocsError("%s is larger than %d bytes" % (f, MAX_DOC_BYTES), "docs_too_large")
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            raise DocsError("%s is not UTF-8" % f, "docs_not_utf8") from e
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
