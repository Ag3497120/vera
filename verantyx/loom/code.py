"""The CODE tier (docs/LINE3_LOOM_DESIGN.md 3.4 code skeleton, 5.2, L-LOOM-05, L-LOOM-11..13, L-LOOM-70..; owner OP-LOOM-2 (a)
「Python のトークン 1 つ、文ごとに 1 十字」).

LOOM-core part (L-LOOM-05, L-LOOM-36): the token view of Python (`tokenize`: NAME / OP / NUMBER / STRING), the one-token check of a
constructed code unit, the code spacing table and the re-tokenize safety net, and the parse gate (`ast.parse`).

LOOM-code part (this ticket, L-LOOM-70..):
  CodeIndex   the record index of a fixture repo, built from {relpath: bytes} that the CALLER read (this module opens no file): every
              NAME / OP / NUMBER / STRING token with (path, line, col), the logical lines as "sentences", the definitions (def / class /
              assignment / import names with their scope), the modules.  Test files are NOT indexed (they would put the answer's names
              into the corpus).
  gate_refusals(text, index, context_names, line_cids)
              the gates of a code thread that need the whole text: unsupported_construct (a closed allow-list), import_not_allowed,
              cross_not_one_statement, undefined_name (definition-first).  The parse gate and layout_changed_tokens stay in read.py.
              The `tests` step is NOT here: it runs a process and the loom package imports none; it is the harness
              (experiments/line3/loom/code_harness.py), after emit, and its result enters the ledger as an `attest` row (design 5.2).
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import keyword
import tokenize
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

KEPT_TYPES = tuple(getattr(tokenize, n) for n in ("NAME", "OP", "NUMBER", "STRING", "FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END")
                   if hasattr(tokenize, n))
NO_SPACE_BEFORE = frozenset((")", "]", "}", ",", ":", "."))
NO_SPACE_AFTER = frozenset(("(", "[", "{", "."))


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


# ------------------------------------------------------------------------------------------------------------
# LOOM-code: the record index of a fixture repo (L-LOOM-11, L-LOOM-70)
# ------------------------------------------------------------------------------------------------------------
INDEX_VERSION = "code_index.v1"
INDEX_TOKEN_TYPES = (tokenize.NAME, tokenize.OP, tokenize.NUMBER, tokenize.STRING)
OCC_SHOWN = 8                 # occurrences carried in a unit's provenance / a lookup match (the count n is always complete)
SIDS_SHOWN = 20
SENTENCES_SHOWN = 5
SENTENCE_CHARS = 200


def indexed_path(rel: str) -> bool:
    """Which files of a fixture root are in the record index: every `*.py` outside `tests/`, `__pycache__` and dot-folders.  The tests
    are held out: a test file names the function the task asks for, and an index that holds the answer's names is not a corpus."""
    parts = rel.split("/")
    return (rel.endswith(".py") and "__pycache__" not in parts and parts[0] != "tests" and not any(p.startswith(".") for p in parts)
            and not parts[-1].startswith("test_"))


def module_of(rel: str) -> str:
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _binding_names(target) -> List[ast.Name]:
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for e in target.elts for n in _binding_names(e)]
    if isinstance(target, ast.Starred):
        return _binding_names(target.value)
    return []


class CodeIndex:
    """Deterministic: the same bytes give the same index, object for object; every listing is in path / source order."""

    def __init__(self, files: Dict[str, bytes]) -> None:
        self.paths: List[str] = sorted(p for p in files if indexed_path(p))
        self.file_sha: Dict[str, str] = {p: hashlib.sha256(files[p]).hexdigest() for p in self.paths}
        self.sha = hashlib.sha256(json.dumps({"v": INDEX_VERSION, "files": self.file_sha}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.sentences: List[dict] = []                        # sid -> {source, text, tokens}
        self.postings: Dict[str, List[Tuple[str, int, int, int]]] = {}       # surface -> [(path, line, col, sid)]
        self.defs: List[dict] = []                             # {name, kind, path, line, col, scope}
        self.module_path: Dict[str, str] = {}
        for p in self.paths:
            self.module_path[module_of(p)] = p
            try:
                text = files[p].decode("utf-8")
                self._tokens(p, text)
                self._defs(p, ast.parse(text))
            except (UnicodeDecodeError, tokenize.TokenError, SyntaxError, IndentationError, ValueError) as e:
                raise ValueError("fixture file %s does not parse: %s" % (p, e))
        self.top: Dict[str, Dict[str, dict]] = {}              # module -> {name -> first module-level definition}
        for d in self.defs:
            if d["scope"] == "<module>":
                self.top.setdefault(module_of(d["path"]), {}).setdefault(d["name"], d)

    # -- tokens -----------------------------------------------------------------------------------------------------
    def _tokens(self, path: str, text: str) -> None:
        lines = text.splitlines()
        group: List[tokenize.TokenInfo] = []

        def close() -> None:
            if not group:
                return
            sid = len(self.sentences)
            first, last = group[0].start[0], group[-1].end[0]
            src = " ".join(l.strip() for l in lines[first - 1:last])[:SENTENCE_CHARS]
            self.sentences.append({"source": "%s:%d" % (path, first), "text": src, "tokens": [t.string for t in group]})
            for t in group:
                if t.start[0] == t.end[0]:                     # a token that spans lines (a triple-quoted string) is not a unit
                    self.postings.setdefault(t.string, []).append((path, t.start[0], t.start[1], sid))
            del group[:]

        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type in INDEX_TOKEN_TYPES:
                group.append(tok)
            elif tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
                close()
        close()

    # -- definitions --------------------------------------------------------------------------------------------------
    def _add_def(self, name: str, kind: str, path: str, node, scope: str) -> None:
        self.defs.append({"name": name, "kind": kind, "path": path, "line": node.lineno, "col": node.col_offset, "scope": scope})

    def _defs(self, path: str, tree: ast.Module) -> None:
        def body(stmts, scope: str) -> None:
            for n in stmts:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._add_def(n.name, "def", path, n, scope)
                    body(n.body, n.name if scope == "<module>" else scope + "." + n.name)
                elif isinstance(n, ast.ClassDef):
                    self._add_def(n.name, "class", path, n, scope)
                    body(n.body, n.name if scope == "<module>" else scope + "." + n.name)
                else:
                    targets: List[ast.Name] = []
                    if isinstance(n, ast.Assign):
                        targets = [x for t in n.targets for x in _binding_names(t)]
                    elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                        targets = _binding_names(n.target)
                    elif isinstance(n, (ast.For, ast.AsyncFor)):
                        targets = _binding_names(n.target)
                    for x in targets:
                        self._add_def(x.id, "assign", path, x, scope)
                    if isinstance(n, ast.Import):
                        for a in n.names:
                            self._add_def(a.asname or a.name.split(".")[0], "import", path, n, scope)
                    elif isinstance(n, ast.ImportFrom):
                        for a in n.names:
                            if a.name != "*":
                                self._add_def(a.asname or a.name, "import", path, n, scope)
                    for field in ("body", "orelse", "finalbody"):
                        sub = getattr(n, field, None)
                        if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                            body(sub, scope)
                    for h in getattr(n, "handlers", []) or []:
                        body(h.body, scope)

        body(tree.body, "<module>")

    # -- queries -------------------------------------------------------------------------------------------------------
    @property
    def n_sentences(self) -> int:
        return len(self.sentences)

    def occurrences(self, surface: str) -> Optional[List[Tuple[str, int, int, int]]]:
        return self.postings.get(surface)

    def prov(self, surface: str) -> dict:
        """The provenance of a record unit: {tier, n, occ (the first OCC_SHOWN [path, line, col]), files {path: sha256} of those}."""
        occ = self.postings[surface]
        shown = occ[:OCC_SHOWN]
        return {"tier": "CODE", "n": len(occ), "occ": [[p, l, c] for p, l, c, _ in shown], "files": {p: self.file_sha[p] for p in sorted({o[0] for o in shown})}}

    def match(self, surface: str) -> Optional[dict]:
        """A `lookup` match for a surface of the CODE tier, or None."""
        occ = self.postings.get(surface)
        if occ is None:
            return None
        sids = sorted({o[3] for o in occ})
        return {"tier": "CODE", "surface": surface, "n": len(occ), "occ": [[p, l, c] for p, l, c, _ in occ[:OCC_SHOWN]], "sids": sids[:SIDS_SHOWN],
                "sentences": [self.sentence(s) for s in sids[:SENTENCES_SHOWN]]}

    def sentence(self, sid: int) -> dict:
        s = self.sentences[sid]
        return {"sid": sid, "source": s["source"], "text": s["text"]}

    def top_names(self, rel: str) -> List[str]:
        return sorted(self.top.get(module_of(rel), {})) if rel in self.file_sha else []

    def defined_in(self, name: str, limit: int = 3) -> List[str]:
        """Where a module-level definition of `name` sits in the fixture: ["path:line", ...] (the hint an `undefined_name` carries)."""
        out = ["%s:%d" % (d["path"], d["line"]) for d in self.defs if d["scope"] == "<module>" and d["name"] == name and d["kind"] != "import"]
        return out[:limit]


# ------------------------------------------------------------------------------------------------------------
# LOOM-code: the gates of a code thread (L-LOOM-12, L-LOOM-13, L-LOOM-71..)
# ------------------------------------------------------------------------------------------------------------
# sorted(dir(builtins)) of CPython 3.11 without the names `site` adds (copyright credits exit help license quit); pinned by a test
BUILTINS: Tuple[str, ...] = (
    'ArithmeticError', 'AssertionError', 'AttributeError', 'BaseException', 'BaseExceptionGroup', 'BlockingIOError', 'BrokenPipeError',
    'BufferError', 'BytesWarning', 'ChildProcessError', 'ConnectionAbortedError', 'ConnectionError', 'ConnectionRefusedError',
    'ConnectionResetError', 'DeprecationWarning', 'EOFError', 'Ellipsis', 'EncodingWarning', 'EnvironmentError', 'Exception',
    'ExceptionGroup', 'False', 'FileExistsError', 'FileNotFoundError', 'FloatingPointError', 'FutureWarning', 'GeneratorExit', 'IOError',
    'ImportError', 'ImportWarning', 'IndentationError', 'IndexError', 'InterruptedError', 'IsADirectoryError', 'KeyError',
    'KeyboardInterrupt', 'LookupError', 'MemoryError', 'ModuleNotFoundError', 'NameError', 'None', 'NotADirectoryError', 'NotImplemented',
    'NotImplementedError', 'OSError', 'OverflowError', 'PendingDeprecationWarning', 'PermissionError', 'ProcessLookupError',
    'RecursionError', 'ReferenceError', 'ResourceWarning', 'RuntimeError', 'RuntimeWarning', 'StopAsyncIteration', 'StopIteration',
    'SyntaxError', 'SyntaxWarning', 'SystemError', 'SystemExit', 'TabError', 'TimeoutError', 'True', 'TypeError', 'UnboundLocalError',
    'UnicodeDecodeError', 'UnicodeEncodeError', 'UnicodeError', 'UnicodeTranslateError', 'UnicodeWarning', 'UserWarning', 'ValueError',
    'Warning', 'ZeroDivisionError', '__build_class__', '__debug__', '__doc__', '__import__', '__loader__', '__name__', '__package__',
    '__spec__', 'abs', 'aiter', 'all', 'anext', 'any', 'ascii', 'bin', 'bool', 'breakpoint', 'bytearray', 'bytes', 'callable', 'chr',
    'classmethod', 'compile', 'complex', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exec', 'filter', 'float', 'format',
    'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'hex', 'id', 'input', 'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
    'locals', 'map', 'max', 'memoryview', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'range', 'repr',
    'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'vars', 'zip')
SITE_ADDED_BUILTINS = ("copyright", "credits", "exit", "help", "license", "quit")
STDLIB_ALLOWED: Tuple[str, ...] = ("math", "itertools", "functools", "collections", "re", "json", "fractions", "typing", "dataclasses", "operator", "string")
# Names the loom does not let a woven text even READ (L-LOOM-78; the first list refused only their calls): `f = eval` / `[open][0](p)` /
# `functools.partial(eval, s)` name them without calling them.  A speed bump on the way to the tests step, NOT a wall (L-LOOM-72).
BLOCKED_NAMES: Tuple[str, ...] = ("eval", "exec", "compile", "__import__", "open", "getattr", "setattr",
                                  "globals", "locals", "vars", "breakpoint", "input", "delattr")

# The supported subset (L-LOOM-13, revised): def / return / assignment / call statement / if / for / import, and the expressions they need
# (names, constants, calls, operators, attributes, subscripts, tuples, lists, one list comprehension form).  Everything else is refused
# with its AST class name; a few have a name of their own (decorator, else_clause, star_args, ...).
_ALLOWED_STMT = (ast.FunctionDef, ast.Return, ast.Assign, ast.Expr, ast.If, ast.For, ast.Import, ast.ImportFrom)
_ALLOWED_EXPR = (ast.Name, ast.Constant, ast.Call, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.Attribute, ast.Subscript, ast.Slice,
                 ast.Tuple, ast.List, ast.ListComp)
_ALLOWED_AUX = (ast.Module, ast.Load, ast.Store, ast.operator, ast.unaryop, ast.boolop, ast.cmpop, ast.comprehension, ast.arguments, ast.arg,
                ast.keyword, ast.alias)
_ALLOWED = _ALLOWED_STMT + _ALLOWED_EXPR + _ALLOWED_AUX


def _nodes(tree) -> Iterable[ast.AST]:
    """Every node of a tree, breadth first (the order of ast.walk; spelled out because the file-touching test reads call names)."""
    todo = [tree]
    for n in todo:
        todo.extend(ast.iter_child_nodes(n))
        yield n


def _line(n, fallback: int = 1) -> int:
    return getattr(n, "lineno", None) or fallback


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name.startswith("__") and name.endswith("__")


def unsupported_constructs(tree: ast.Module) -> List[dict]:
    out: List[dict] = []
    seen = set()
    nodes = list(_nodes(tree))
    called = {id(n.func) for n in nodes if isinstance(n, ast.Call)}

    def add(construct: str, line: int) -> None:
        if (construct, line) not in seen:
            seen.add((construct, line))
            out.append({"type": "unsupported_construct", "construct": construct, "line": line})

    for n in nodes:
        line = _line(n)
        if not isinstance(n, _ALLOWED):
            add(type(n).__name__, line)
            continue
        if isinstance(n, ast.FunctionDef):
            for d in n.decorator_list:
                add("decorator", _line(d, line))
            a = n.args
            if a.posonlyargs or a.kwonlyargs or a.vararg or a.kwarg:
                add("def_signature", line)
            if n.returns is not None or any(x.annotation is not None for x in a.args):
                add("annotation", line)
            if n.type_comment is not None:
                add("type_comment", line)
        elif isinstance(n, (ast.If, ast.For)) and n.orelse:
            add("else_clause", _line(n.orelse[0], line))
        elif isinstance(n, ast.Expr) and not isinstance(n.value, ast.Call):
            add("expr_statement", line)
        elif isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            add("star_import", line)
        elif isinstance(n, ast.Call):
            if any(k.arg is None for k in n.keywords):
                add("star_args", line)
        elif isinstance(n, ast.Name):
            # a blocked name in ANY context: called (`call:eval`), or merely read / bound (`name:eval`); a dunder name (`__loader__`,
            # `__builtins__`, `__spec__`) is refused whole (`dunder_name`), a dunder attribute (`().__class__`) as `dunder_attribute`
            if n.id in BLOCKED_NAMES:
                add(("call:" if id(n) in called else "name:") + n.id, line)
            elif _is_dunder(n.id):
                add("dunder_name", line)
        elif isinstance(n, ast.Attribute) and _is_dunder(n.attr):
            add("dunder_attribute", line)
        elif isinstance(n, ast.comprehension) and n.is_async:
            add("AsyncComprehension", line)
    out.sort(key=lambda r: (r["line"], r["construct"]))
    return out


def _import_refusals(tree: ast.Module, index: Optional[CodeIndex]) -> List[dict]:
    modules = index.module_path if index is not None else {}
    top = index.top if index is not None else {}
    out: List[dict] = []
    for n in _nodes(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name not in modules and a.name not in STDLIB_ALLOWED:
                    out.append({"type": "import_not_allowed", "module": a.name, "line": n.lineno, "reason": "module"})
        elif isinstance(n, ast.ImportFrom):
            if n.level:
                out.append({"type": "import_not_allowed", "module": "." * n.level + (n.module or ""), "line": n.lineno, "reason": "relative"})
            elif n.module in STDLIB_ALLOWED:
                continue
            elif n.module not in modules:
                out.append({"type": "import_not_allowed", "module": n.module, "line": n.lineno, "reason": "module"})
            else:
                for a in n.names:
                    if a.name != "*" and a.name not in top.get(n.module, {}) and (n.module + "." + a.name) not in modules:
                        out.append({"type": "import_not_allowed", "module": n.module, "name": a.name, "line": n.lineno, "reason": "name"})
    out.sort(key=lambda r: (r["line"], r["module"], r.get("name", "")))
    return out


class _DefinitionFirst:
    """L-LOOM-12: a Name in Load context must be bound EARLIER in the text, in the same or an enclosing scope (def / class names are bound
    before their body, so recursion works; a function body that names a LATER module-level def is refused), or be a builtin, or be a
    context name (a top-level name of the target file)."""

    def __init__(self, base: Iterable[str]) -> None:
        self.scopes: List[set] = [set(base)]
        self.out: List[dict] = []

    def bound(self, name: str) -> bool:
        return any(name in s for s in self.scopes)

    def bind(self, name: str) -> None:
        self.scopes[-1].add(name)

    def body(self, stmts) -> None:
        for s in stmts:
            self.stmt(s)

    def stmt(self, n) -> None:
        if isinstance(n, ast.FunctionDef):
            for d in n.args.defaults:
                self.expr(d)
            self.bind(n.name)
            self.scopes.append({a.arg for a in n.args.args})
            self.body(n.body)
            self.scopes.pop()
        elif isinstance(n, ast.Return):
            if n.value is not None:
                self.expr(n.value)
        elif isinstance(n, ast.Assign):
            self.expr(n.value)
            for t in n.targets:
                self.target(t)
        elif isinstance(n, ast.Expr):
            self.expr(n.value)
        elif isinstance(n, ast.If):
            self.expr(n.test)
            self.body(n.body)
        elif isinstance(n, ast.For):
            self.expr(n.iter)
            self.target(n.target)
            self.body(n.body)
        elif isinstance(n, ast.Import):
            for a in n.names:
                self.bind(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    self.bind(a.asname or a.name)

    def target(self, t) -> None:
        if isinstance(t, ast.Name):
            self.bind(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                self.target(e)
        else:
            self.expr(t)

    def expr(self, n) -> None:
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load) and not self.bound(n.id):
                self.out.append({"type": "undefined_name", "name": n.id, "line": n.lineno, "col": n.col_offset})
        elif isinstance(n, ast.ListComp):
            self.scopes.append(set())
            for g in n.generators:
                self.expr(g.iter)
                self.target(g.target)
                for c in g.ifs:
                    self.expr(c)
            self.expr(n.elt)
            self.scopes.pop()
        else:
            for c in ast.iter_child_nodes(n):
                self.expr(c)


def gate_refusals(text: str, index: Optional[CodeIndex], context_names: Iterable[str], line_cids: Sequence[str]) -> List[dict]:
    """The refusals of the whole-text code gates on a text that PARSES (the caller runs `parse_gate` first), in (type, line) order.

    `line_cids[i]` is the cross that printed line i + 1 of `text` (a cross with no unit prints nothing), so every refusal can name its
    cross.  Gates: unsupported_construct; import_not_allowed; cross_not_one_statement (every printed line starts exactly one statement,
    OP-LOOM-2 「文ごとに 1 十字」); undefined_name (definition-first), which runs only on a tree without unsupported constructs."""
    tree = ast.parse(text)
    out: List[dict] = []
    unsup = unsupported_constructs(tree)
    out.extend(unsup)
    out.extend(_import_refusals(tree, index))
    starts: Dict[int, int] = {}
    for n in _nodes(tree):
        if isinstance(n, ast.stmt):
            starts[n.lineno] = starts.get(n.lineno, 0) + 1
    n_lines = len(text.splitlines())
    if n_lines == len(line_cids):
        for i in range(len(line_cids)):
            k = starts.get(i + 1, 0)
            if k != 1:
                out.append({"type": "cross_not_one_statement", "line": i + 1, "statements": k,
                            "reason": "continuation" if k == 0 else "several_statements"})
    else:                                                  # L-LOOM-83: was a silent skip; a cross that prints two lines breaks the line <-> cross map
        out.append({"type": "line_cross_mismatch", "line": 0, "lines": n_lines, "crosses": len(line_cids)})
    if not unsup:
        df = _DefinitionFirst(set(BUILTINS) | set(context_names))
        df.body(tree.body)
        for r in df.out:
            if index is not None:
                r["defined_in"] = index.defined_in(r["name"])
        out.extend(df.out)
    for r in out:
        if 1 <= r["line"] <= len(line_cids):
            r["cid"] = line_cids[r["line"] - 1]
    out.sort(key=lambda r: (r["type"], r["line"], r.get("col", 0)))
    return out
