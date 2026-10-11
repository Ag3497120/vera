"""The CODE tier, LOOM-core part only (docs/LINE3_LOOM_DESIGN.md 3.4 code skeleton, 5.2, L-LOOM-05; owner OP-LOOM-2 (a)
「Python のトークン 1 つ、文ごとに 1 十字」).

What is here: the token view of Python (`tokenize`: NAME / OP / NUMBER / STRING), the one-token check of a constructed code unit, the
code spacing table and the re-tokenize safety net, and the parse gate (`ast.parse`).  These are what the READ RULE of a code cross
needs (LOOM-b) and what the emit gate can say about a code thread today.

What is NOT here (ticket LOOM-e, "LOOM-code"): the record index of a fixture repo (path:line:col, file sha), `add record tier=CODE`,
the definition-first gate, the import gate, `unsupported_construct`, the fixture and the K1-K5 tasks.  Until those exist a code
thread can be read and parsed but never emitted (read.py reports `code_gates_incomplete`).
"""
from __future__ import annotations

import ast
import io
import keyword
import tokenize
from typing import List, Optional, Sequence, Tuple

KEPT_TYPES = tuple(getattr(tokenize, n) for n in ("NAME", "OP", "NUMBER", "STRING", "FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
                   if hasattr(tokenize, n))
NO_SPACE_BEFORE = frozenset((")", "]", "}", ",", ":", "."))
NO_SPACE_AFTER = frozenset(("(", "[", "{", "."))
GATES_MISSING_IN_CORE: Tuple[str, ...] = ("definition_first", "imports", "unsupported_construct")


def tokens_of(text: str) -> List[Tuple[int, str]]:
    """The kept tokens (type, string) of `text`, in order.  Raises tokenize.TokenError / IndentationError / SyntaxError on bad input."""
    out: List[Tuple[int, str]] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in KEPT_TYPES:
                out.append((tok.type, tok.string))
            elif tok.type in (tokenize.COMMENT, tokenize.ERRORTOKEN):
                out.append((tok.type, tok.string))   # not a kept type: makes the check fail rather than vanish
    except tokenize.TokenError as e:
        # "EOF in multi-line statement": an unclosed ( [ { (one token of a statement that continues in another cross) ends the stream;
        # the tokens read so far are the tokens of the text.  An unterminated string / triple quote is not that: it stays an error.
        if "multi-line statement" not in str(e):
            raise
    return out


def is_one_token(text: str) -> bool:
    """A constructed code unit is exactly one NAME / OP / NUMBER / STRING token and nothing else (L-LOOM-11)."""
    if not text or text != text.strip() or "\n" in text:
        return False
    try:
        toks = tokens_of(text)
    except (tokenize.TokenError, SyntaxError):
        return False
    return len(toks) == 1 and toks[0][0] in KEPT_TYPES and toks[0][1] == text


def _is_name(t: str) -> bool:
    return t.isidentifier() and not keyword.iskeyword(t)


def spaced(tokens: Sequence[str]) -> List[str]:
    """L-LOOM-05: the separators between tokens.  Returns len(tokens) - 1 strings (one space or empty), so the caller can mark every
    separator as layout.  No space before ) ] } , : . ; none after ( [ { . ; none between a NAME (not a keyword), ) or ] and a
    following ( or [; one space everywhere else."""
    seps: List[str] = []
    for prev, cur in zip(tokens, tokens[1:]):
        if cur in NO_SPACE_BEFORE or prev in NO_SPACE_AFTER or (cur in ("(", "[") and (_is_name(prev) or prev in (")", "]"))):
            seps.append("")
        else:
            seps.append(" ")
    return seps


def line_keeps_tokens(line: str, surfaces: Sequence[str]) -> bool:
    """The safety net: re-tokenize the read line; its kept tokens must equal the seated surfaces, in order (`layout_changed_tokens`)."""
    try:
        toks = tokens_of(line.strip(" ") + "\n")
    except (tokenize.TokenError, SyntaxError):
        return False
    return [s for _, s in toks] == list(surfaces) and all(t in KEPT_TYPES for t, _ in toks)


def parse_gate(text: str) -> Optional[dict]:
    """None when `ast.parse` accepts the text, else {lineno, offset, msg}."""
    try:
        ast.parse(text)
    except SyntaxError as e:
        return {"lineno": e.lineno, "offset": e.offset, "msg": e.msg}
    except (ValueError, RecursionError) as e:
        return {"lineno": None, "offset": None, "msg": str(e)[:200]}
    return None
