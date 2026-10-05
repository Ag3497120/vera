"""W16-t6 (T6, K600-K603): `vera attest` — a completion claim is testimony; only what matches an observed event is recorded.

The spec (the only one) is docs/ATTEST.md. Three extractors (V: the fixed completion sentences, a: the JSON block, b: regular expressions) build the same claim
objects and hand them to ONE verifier. Votes are never merged across extractors. The LLM judge (c) is a comparison only: it never uses the verifier, never writes a
ledger row, never makes a RECORD. This module does not use any reader of Vera (the claims are read by fixed parsing).
Every external command goes through the single function `_spawn` (no shell, an executable that is never a string of the report).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

SCHEMA = "verantyx.attest/1"
RECORD, TESTIMONY, MISMATCH = "RECORD", "TESTIMONY", "MISMATCH"
MARKS = (RECORD, TESTIMONY, MISMATCH)
TESTIMONY_REASONS = ("OFF_FORM", "NO_COMPLETION_SECTION", "PATH_OUTSIDE_TREE", "AMBIGUOUS_PATH", "SHA_TOO_SHORT", "SHA_MALFORMED", "NO_EVENT", "LEDGER_UNVERIFIED",
                     "AMBIGUOUS_EVENT", "COMMAND_NOT_ALLOWED", "RERUN_TIMEOUT", "TOO_LARGE", "NO_BASE", "EVIDENCE_NOT_IN_TREE", "MATCHES_PAST_VERSION", "NO_COMMAND",
                     "NOT_A_FILE", "COLLECT_FAILED", "NO_NUMBER_IN_TEXT", "REV_UNREADABLE", "BASE_UNREADABLE", "NOT_IN_TESTS_DIR", "AMBIGUOUS_CLAIM", "COLLECT_SKIPPED")
MISMATCH_REASONS = ("FILE_MISSING", "SHA_DIFFERS", "COUNT_DIFFERS", "TEST_NOT_FOUND", "EXIT_CODE_DIFFERS", "NUMBER_NOT_IN_OUTPUT", "NOT_CHANGED_SINCE_BASE")
RECORD_REASONS = ("MATCH", "MATCH_PREFIX")
LLM_ANSWERS = ("LLM_YES", "LLM_NO", "LLM_UNKNOWN", "LLM_UNPARSEABLE")
EXTRACTORS = ("V", "a", "b")

ALLOWED_MODULE_FORMS = {"pytest": "pytest"}          # python -m <module>: pytest only (docs/ATTEST.md); verantyx.cli has writers, so it is not allowed
PYTHON_NAMES = ("python", "python3", "python3.11")
ALLOWED_FLAGS = ("-q", "-x", "--collect-only")
SHELL_META = frozenset(";|&$`><()\n\r\x00")
DEFAULT_TIMEOUT = 600.0
NUMBER_FILE_LIMIT = 8 * 1024 * 1024
SHA_FILE_LIMIT = 256 * 1024 * 1024
GIT_SUBCOMMANDS = ("show", "ls-files", "log", "rev-parse")

HEX = r"(?:[0-9a-fA-F]+(?:\.\.\.)?|\.\.\.)"
PATHTOK = r"[^\s()、。「」`]+"
RE_ACCEPT = re.compile(r"^- 受入 (?P<id>[^\s:]+): `(?P<cmd>[^`]+)` を実行し、終了コード (?P<n>-?\d+)(?:、出力 (?P<out>" + PATHTOK + r")\(sha256 (?P<sha>" + HEX + r")\))?。?$")
_ITEM = PATHTOK + r"\(sha256 " + HEX + r"\)"
RE_CHANGED = re.compile(r"^- 変更: (?P<body>" + _ITEM + r"(?:、" + _ITEM + r")*)。?$")
RE_CHANGED_ITEM = re.compile(r"(?P<path>" + PATHTOK + r")\(sha256 (?P<sha>" + HEX + r")\)")
RE_TESTS = re.compile(r"^- 追加したテスト: (?P<path>\S+) の (?P<n>\d+) 件が通った。?$")
RE_NUMBER = re.compile(r"^- 数値 (?P<id>[^\s:]+): 「(?P<text>[^」]+)」は (?P<path>\S+) にある。?$")
RE_SECTION = re.compile(r"^完了:$")
FILE_EXT = r"(?:py|txt|md|json|jsonl|tsv|csv|log|sha256|yaml|yml|toml|ini)"
RE_B_PATH = re.compile(r"(?:[\w.-]+/)*[\w.-]+\.%s\b" % FILE_EXT)
RE_B_EXIT = re.compile(r"(?:終了コード|exit code|exit status|returncode)\D{0,6}?(-?\d+)", re.I)
RE_B_CMD = re.compile(r"`([^`]+)`")
RE_B_TESTPATH = re.compile(r"tests/[\w./-]+\.py")
RE_B_PASSED = re.compile(r"(\d+)\s*(?:passed|件が通|件通)")
RE_B_SHA = re.compile(r"((?:[\w.-]+/)*[\w.-]+\.%s)\b\W{0,12}?(?:sha256\W{0,3})?\b([0-9a-fA-F]{12,64})\b" % FILE_EXT)
RE_B_QUOTE = re.compile(r"「([^」]*\d[^」]*)」")
RE_JSON_BLOCK = re.compile(r"```json[^\n]*\n(.*?)\n```", re.S)


def nfkc(s: Any) -> str:
    return unicodedata.normalize("NFKC", str(s))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fold_marks(marks: Sequence[str]) -> str:
    """Narrowing side: any MISMATCH -> MISMATCH, else any TESTIMONY -> TESTIMONY, else RECORD (all of them)."""
    if MISMATCH in marks:
        return MISMATCH
    if TESTIMONY in marks or not marks:
        return TESTIMONY
    return RECORD


# ===================================================================== the single place where a command is run
def _spawn(argv: Sequence[str], cwd: str, timeout: float, env: Optional[Dict[str, str]] = None) -> Tuple[Optional[int], bytes, bytes]:
    """The only function that starts a process: no shell, an explicit argv, a timeout. Returns (returncode or None on timeout, stdout, stderr)."""
    try:
        p = subprocess.run(list(argv), cwd=cwd, env=env, capture_output=True, timeout=timeout, shell=False)
    except Exception as e:                      # a timeout or a missing executable: reported, never raised into the verifier
        if type(e).__name__ == "TimeoutExpired":
            return None, b"", b"timeout"
        return 127, b"", ("%s: %s" % (type(e).__name__, e)).encode("utf-8", "replace")
    return p.returncode, p.stdout, p.stderr


def _child_env(tree: str) -> Dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}  # the allowed flags must not depend on the caller's environment
    env["PYTHONPATH"] = tree
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


# ===================================================================== the allowed forms of --rerun (T6-4)
def check_command(cmd: str, tree: str) -> Tuple[Optional[List[str]], str]:
    """(argv, '') when `cmd` is one of the allowed forms, else (None, why). Nothing is executed here. See docs/ATTEST.md."""
    if not isinstance(cmd, str) or not cmd.strip():
        return None, "EMPTY"
    if any(ch in SHELL_META for ch in cmd):
        return None, "SHELL_META"
    try:
        toks = shlex.split(cmd)
    except ValueError:
        return None, "UNPARSEABLE"
    if not toks:
        return None, "EMPTY"
    if toks[0] == "pytest":
        rest = toks[1:]
    elif toks[0] in PYTHON_NAMES and len(toks) >= 3 and toks[1] == "-m" and toks[2] in ALLOWED_MODULE_FORMS:
        rest = toks[3:]
    else:
        return None, "FORM_NOT_ALLOWED"
    flags: List[str] = []
    paths: List[str] = []
    real_tree = os.path.realpath(tree)
    tests_root = os.path.join(real_tree, "tests")
    i = 0
    while i < len(rest):
        t = rest[i]
        if t in ALLOWED_FLAGS:
            flags.append(t)
        elif t == "-k":
            if i + 1 >= len(rest) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_ .\-]*", rest[i + 1]):
                return None, "BAD_K_EXPR"
            flags += ["-k", rest[i + 1]]
            i += 1
        elif t == "-p":
            if i + 1 >= len(rest) or rest[i + 1] != "no:cacheprovider":
                return None, "BAD_P_VALUE"
            i += 1
        elif t.startswith("-"):
            return None, "FLAG_NOT_ALLOWED"
        else:
            file_part = t.split("::", 1)[0]
            if os.path.isabs(file_part) or ".." in Path(file_part).parts or not file_part.endswith(".py") or not file_part.startswith("tests/"):
                return None, "PATH_NOT_ALLOWED"
            real = os.path.realpath(os.path.join(real_tree, file_part))
            if not real.startswith(tests_root + os.sep):
                return None, "PATH_OUTSIDE_TESTS"
            paths.append(t)
        i += 1
    if not paths:
        return None, "NO_PATH"
    return [sys.executable, "-m", "pytest"] + flags + paths + ["-p", "no:cacheprovider"], ""


# ===================================================================== claims: three extractors
def _claim(kind: str, line: Optional[int], text: str, **kw: Any) -> Dict[str, Any]:
    d = {"kind": kind, "line": line, "text": text[:300]}
    d.update(kw)
    return d


def _offform(line: Optional[int], text: str, why: str = "") -> Dict[str, Any]:
    return _claim("offform", line, text, why=why)


def parse_v(report: str) -> Tuple[List[Dict[str, Any]], bool]:
    """V: the completion section in the fixed sentences. Returns (claims incl. offform ones, a section was found)."""
    lines = report.split("\n")
    claims: List[Dict[str, Any]] = []
    found = False
    i = 0
    while i < len(lines):
        if RE_SECTION.match(nfkc(lines[i]).strip()):
            found = True
            j = i + 1
            while j < len(lines):
                raw = lines[j]
                s = nfkc(raw).strip()
                if not s.startswith("- "):
                    break
                m = RE_ACCEPT.match(s)
                if m:
                    out = {"path": m["out"], "sha": m["sha"]} if m["out"] else None
                    claims.append(_claim("acceptance", j + 1, s, id=m["id"], cmd=m["cmd"], exit=int(m["n"]), out=out))
                elif RE_CHANGED.match(s):
                    for it in RE_CHANGED_ITEM.finditer(RE_CHANGED.match(s)["body"]):
                        claims.append(_claim("changed", j + 1, s, path=it["path"], sha=it["sha"]))
                elif RE_TESTS.match(s):
                    m = RE_TESTS.match(s)
                    claims.append(_claim("tests_added", j + 1, s, path=m["path"], count=int(m["n"]), passed=True))
                elif RE_NUMBER.match(s):
                    m = RE_NUMBER.match(s)
                    claims.append(_claim("number", j + 1, s, id=m["id"], numtext=m["text"], path=m["path"]))
                else:
                    claims.append(_offform(j + 1, s, "no sentence form matches"))
                j += 1
            i = j
        else:
            i += 1
    return claims, found


def parse_a(report: str) -> List[Dict[str, Any]]:
    """a: the ```json blocks that have an "attest" key. A broken block or an unknown kind is an offform claim (counted, not dropped)."""
    claims: List[Dict[str, Any]] = []
    for m in RE_JSON_BLOCK.finditer(report):
        body = m.group(1)
        if '"attest"' not in body:
            continue
        line = report.count("\n", 0, m.start()) + 1
        try:
            d = json.loads(body)
        except ValueError:
            claims.append(_offform(line, body[:120], "json block does not parse"))
            continue
        if not isinstance(d, dict) or d.get("attest") != 1 or not isinstance(d.get("claims"), list):
            claims.append(_offform(line, body[:120], "attest block has the wrong shape"))
            continue
        for c in d["claims"]:
            text = json.dumps(c, ensure_ascii=False)[:300]
            try:
                kind = c["kind"]
                if kind == "acceptance":
                    out = c.get("output")
                    if (not isinstance(c["command"], str) or type(c["exit_code"]) is not int
                            or (out is not None and not (isinstance(out["path"], str) and isinstance(out["sha256"], str)))):
                        raise TypeError("acceptance")
                    claims.append(_claim("acceptance", line, text, id=str(c.get("id", "")), cmd=nfkc(c["command"]), exit=c["exit_code"],
                                         out={"path": nfkc(out["path"]), "sha": nfkc(out["sha256"])} if out else None))
                elif kind == "changed":
                    files = c["files"]
                    if not isinstance(files, list) or not files:
                        raise TypeError("changed")
                    for f in files:
                        if not (isinstance(f["path"], str) and isinstance(f["sha256"], str)):
                            raise TypeError("changed")
                        claims.append(_claim("changed", line, text, path=nfkc(f["path"]), sha=nfkc(f["sha256"])))
                elif kind == "tests_added":
                    if not isinstance(c["path"], str) or type(c["count"]) is not int:
                        raise TypeError("tests_added")
                    claims.append(_claim("tests_added", line, text, path=nfkc(c["path"]), count=c["count"], passed=bool(c.get("passed", True))))
                elif kind == "number":
                    if not (isinstance(c["text"], str) and isinstance(c["path"], str)):
                        raise TypeError("number")
                    claims.append(_claim("number", line, text, id=str(c.get("id", "")), numtext=nfkc(c["text"]), path=nfkc(c["path"])))
                else:
                    raise TypeError("kind")
            except (KeyError, TypeError, AttributeError):
                claims.append(_offform(line, text, "unknown claim kind or missing field"))
    return claims


def parse_b(report: str) -> List[Dict[str, Any]]:
    """b: regular expressions over the free text, line by line (rules pre-registered in docs/ATTEST.md section 4). Duplicates of the same fact are dropped."""
    claims: List[Dict[str, Any]] = []
    seen = set()

    def add(c: Dict[str, Any]) -> None:
        key = json.dumps([c["kind"], c.get("cmd"), c.get("exit"), c.get("path"), c.get("sha"), c.get("count"), c.get("numtext")], ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            claims.append(c)

    for n, raw in enumerate(report.split("\n"), 1):
        s = nfkc(raw).strip()
        if not s:
            continue
        m = RE_B_EXIT.search(s)
        if m:
            cm = RE_B_CMD.search(s)
            add(_claim("acceptance", n, s, id="", cmd=cm.group(1) if cm else None, exit=int(m.group(1)), out=None))
        tps, pms = sorted(set(RE_B_TESTPATH.findall(s))), RE_B_PASSED.findall(s)
        if tps and pms:
            if len(tps) == 1 and len(pms) == 1:
                add(_claim("tests_added", n, s, path=tps[0], count=int(pms[0]), passed=True))
            else:       # amendment 1 (docs/ATTEST.md): several paths or several counts on one line cannot be paired: a tie is not decided
                add(_claim("tests_added", n, s, path=tps[0], count=None, passed=True, ambiguous=True))
        for sm in RE_B_SHA.finditer(s):
            add(_claim("file_sha", n, s, path=sm.group(1), sha=sm.group(2)))
        qm, pm2 = RE_B_QUOTE.search(s), RE_B_PATH.search(s)
        if qm and pm2:
            add(_claim("number", n, s, id="", numtext=qm.group(1), path=pm2.group(0)))
    return claims


# ===================================================================== numbers
def numbers_in(text: str) -> List[str]:
    """The numbers of a claim sentence: sha-like hex, paths and words that mix letters and digits (IDs such as T2-1, python3.11) are not numbers."""
    t = nfkc(text)
    t = re.sub(r"\b[0-9a-fA-F]{12,}\b", " ", t)
    t = RE_B_PATH.sub(" ", t)
    t = re.sub(r"[A-Za-z_]\w*(?:-\w+)+(?:\.\d+)*|[A-Za-z_][A-Za-z0-9_]*\d[A-Za-z0-9_]*(?:\.\d+)*", " ", t)
    out: List[str] = []
    for m in re.finditer(r"\d+(?:,\d{3})*(?:\.\d+)?", t):
        v = m.group(0).replace(",", "")
        if v not in out:
            out.append(v)
    return out


def number_present(n: str, filetext: str) -> bool:
    t = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", nfkc(filetext))
    return re.search(r"(?<![\w.])(?<![A-Za-z0-9]-)" + re.escape(n) + r"(?!\w)(?!\.\d)", t) is not None


# ===================================================================== T7 ledger (verified by T7's own verify, docs/ATTEST.md revision 7)
def _t7_locate(path: str) -> Tuple[Optional[Path], Path]:
    """(ledger dir, events.jsonl). A directory, or a file named exactly events.jsonl, can be given to T7's verify; any other file name cannot (dir None)."""
    p = Path(path)
    if p.is_dir():
        return p, p / "events.jsonl"
    if p.name == "events.jsonl":
        return p.parent, p
    return None, p


def _unverified(status: str, problems: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"status": status, "problems": problems}


def check_ledger(path: str, expected_head: Optional[str] = None) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]], Optional[bytes]]:
    """(events, None, bytes) only when ledger_events.verify (the T7 verify, with expected_head if given) says OK for THIS file;
    else (None, {"status", "problems"}, None). The events are read from the very bytes that were checked. Only kinds test_run / process_exit are events."""
    from . import ledger_events as _LE
    d, ev = _t7_locate(path)
    if d is None:
        return None, _unverified("UNVERIFIED", [{"line": None, "type": "LEDGER_PATH_NOT_T7"}]), None
    try:
        b0 = ev.read_bytes()
        v = _LE.verify(d, expected_head=expected_head)
        b1 = ev.read_bytes()
        text = b0.decode("utf-8")
    except (OSError, UnicodeError) as e:
        return None, _unverified("UNVERIFIED", [{"line": None, "type": "LEDGER_UNREADABLE", "error": type(e).__name__}]), None
    except Exception as e:                              # a verifier fault is never a verification
        return None, _unverified("UNVERIFIED", [{"line": None, "type": "LEDGER_VERIFY_FAILED", "error": type(e).__name__}]), None
    if b0 != b1:
        return None, _unverified("UNVERIFIED", [{"line": None, "type": "LEDGER_CHANGED_DURING_VERIFY"}]), None
    if v.get("status") != "OK":
        return None, _unverified(str(v.get("status")), list(v.get("problems") or [])), None
    events = []
    for ln in text.split("\n"):
        if not ln.strip():
            continue
        r = json.loads(ln)
        if r.get("kind") in ("test_run", "process_exit") and isinstance(r.get("data"), dict):
            d_ = r["data"]
            argv = None
            if isinstance(d_.get("argv"), list) and all(isinstance(x, str) for x in d_["argv"]):
                argv = list(d_["argv"])
            elif isinstance(d_.get("cmd"), str):
                try:
                    argv = shlex.split(d_["cmd"])
                except ValueError:
                    argv = None
            code = d_.get("exit_code", d_.get("returncode"))
            if argv is not None and type(code) is int:
                events.append({"argv": argv, "code": code, "sha": r["sha"], "kind": r["kind"]})
    return events, None, b0


def load_events(path: str, expected_head: Optional[str] = None) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """(events, '') for a ledger that T7's verify passes, else (None, why)."""
    events, check, _ = check_ledger(path, expected_head)
    if events is None:
        return None, "status=%s" % check["status"]
    return events, ""


def _problem_text(problems: List[Dict[str, Any]]) -> str:
    return ", ".join("%s@%s" % (p.get("type"), p["line"]) if p.get("line") is not None else str(p.get("type")) for p in problems) or "なし"


def _is_pytest_argv(argv: Sequence[str]) -> Optional[List[str]]:
    if argv and argv[0] == "pytest":
        return list(argv[1:])
    if len(argv) >= 3 and argv[0] in PYTHON_NAMES and argv[1] == "-m" and argv[2] == "pytest":
        return list(argv[3:])
    return None


# flags that only change the output, never which tests run (the whole list; anything else makes the event unusable as a basis)
_PASS_BASIS_FLAGS = frozenset({"-q", "-qq", "-v", "-vv", "-x", "--exitfirst", "-s", "--no-header", "--disable-warnings"})


def _pytest_run_paths(argv: Sequence[str]) -> Optional[List[str]]:
    """Paths of a pytest event that really ran every test of its paths (no collect-only / -k / -m / --lf / --deselect / unknown flag), else None."""
    rest = _is_pytest_argv(argv)
    if rest is None:
        return None
    paths: List[str] = []
    i = 0
    while i < len(rest):
        a = rest[i]
        if a == "-p":
            if i + 1 < len(rest) and rest[i + 1] == "no:cacheprovider":
                i += 2
                continue
            return None
        if a.startswith("-"):
            if a not in _PASS_BASIS_FLAGS:
                return None
        else:
            paths.append(a)
        i += 1
    return paths or None


def _passed_event_match(spec: str):
    """(argv, code) -> bool. Exit 0: any event whose paths include the claimed file (or the same node). Exit != 0: only an event whose single path is exactly the claim."""
    want_file = spec.split("::")[0]

    def m(argv: Sequence[str], code: int) -> bool:
        paths = _pytest_run_paths(argv)
        if paths is None:
            return False
        if code == 0:
            return any(x == spec or ("::" not in x and x == want_file) for x in paths)
        return len(paths) == 1 and paths[0] == spec
    return m


# ===================================================================== the one verifier
def F(sig: str, mark: str, reason: str, claimed: Any = None, actual: Any = None, evidence: Optional[Dict[str, Any]] = None, obs: str = "") -> Dict[str, Any]:
    return {"fact": sig, "mark": mark, "reason": reason, "claimed": claimed, "actual": actual, "evidence": evidence, "observation": obs}


class Verifier:
    def __init__(self, tree: str, *, ledger: Optional[str] = None, rerun: bool = False, base: Optional[str] = None, rev: Optional[str] = None,
                 search_dirs: Sequence[str] = (), partial: bool = False, history: bool = False, timeout: float = DEFAULT_TIMEOUT,
                 cache: Optional[Dict[Tuple[str, ...], Tuple[Optional[int], bytes, bytes]]] = None, ledger_head: Optional[str] = None) -> None:
        self.tree = os.path.abspath(tree)
        self.real_tree = os.path.realpath(self.tree)
        self.ledger_path, self.rerun, self.base, self.rev = ledger, rerun, base, rev
        self.search_dirs, self.partial, self.history, self.timeout = list(search_dirs), partial, history, timeout
        self._events: Optional[List[Dict[str, Any]]] = None
        self.ledger_head = ledger_head
        self._ledger_check: Optional[Dict[str, Any]] = None
        self._ledger_bytes: Optional[bytes] = None
        self._ledger_loaded = False
        self._runs: Dict[Tuple[str, ...], Tuple[Optional[int], bytes, bytes]] = cache if cache is not None else {}
        self._collect: Dict[str, Tuple[Optional[int], bytes, bytes]] = {}

    # ---- paths
    def resolve(self, raw: str) -> Tuple[Optional[str], Optional[str]]:
        """(absolute real path, None) or (None, reason). Mark of the reason: FILE_MISSING is a MISMATCH, every other reason is TESTIMONY."""
        p = nfkc(raw)
        if not p or "\x00" in p:
            return None, "PATH_OUTSIDE_TREE"
        cand = p if os.path.isabs(p) else os.path.join(self.tree, p)
        real = os.path.realpath(cand)
        if not (real == self.real_tree or real.startswith(self.real_tree + os.sep)):
            return None, "PATH_OUTSIDE_TREE"
        if os.path.exists(real):
            return (real, None) if os.path.isfile(real) else (None, "NOT_A_FILE")
        if self.search_dirs and "/" not in p:
            found = []
            for d in self.search_dirs:
                c = os.path.realpath(os.path.join(self.tree, d, p))
                if (c.startswith(self.real_tree + os.sep)) and os.path.isfile(c):
                    found.append(c)
            if len(found) == 1:
                return found[0], None
            if len(found) > 1:
                return None, "AMBIGUOUS_PATH"
        return None, "EVIDENCE_NOT_IN_TREE" if self.partial else "FILE_MISSING"

    def _rel(self, real: str) -> str:
        return os.path.relpath(real, self.real_tree)

    @staticmethod
    def _mark_of(reason: str) -> str:
        return MISMATCH if reason in MISMATCH_REASONS else TESTIMONY

    # ---- git (read-only sub-commands only; never writes into the tree)
    def _git(self, *args: str) -> Tuple[Optional[int], bytes, bytes]:
        if not args or args[0] not in GIT_SUBCOMMANDS:
            raise ValueError("git sub-command not allowed: %r" % (args[:1],))
        return _spawn(["git", "-C", self.real_tree] + list(args), self.real_tree, 60.0, None)

    @staticmethod
    def _safe_rev(rev: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_./~^@{}-]{1,100}", rev)) and not rev.startswith("-")

    def _blob(self, rev: str, relpath: str) -> Tuple[str, bytes]:
        """('ok'|'missing'|'badrev', bytes)"""
        if not self._safe_rev(rev):
            return "badrev", b""
        rc, _, _ = self._git("rev-parse", "--verify", "--quiet", rev + "^{commit}")
        if rc != 0:
            return "badrev", b""
        rc, out, _ = self._git("show", "%s:%s" % (rev, relpath))
        return ("ok", out) if rc == 0 else ("missing", b"")

    # ---- facts
    def file_sha(self, raw_path: str, claimed: str, sig_prefix: str = "file_sha") -> Dict[str, Any]:
        sig = "%s:%s" % (sig_prefix, nfkc(raw_path))
        real, why = self.resolve(raw_path)
        if why:
            return F(sig, self._mark_of(why), why, claimed, None, None, "ファイルを観測できなかった: %s" % why)
        rel = self._rel(real)
        if self.rev:
            st, data = self._blob(self.rev, rel)
            if st != "ok":
                if st == "missing":
                    return F(sig, MISMATCH, "FILE_MISSING", claimed, None, None, "rev %s にファイル %s は無い" % (self.rev, rel))
                return F(sig, TESTIMONY, "REV_UNREADABLE", claimed, None, None, "rev %s を読めない" % self.rev)
            actual = sha256_bytes(data)
        else:
            if os.path.getsize(real) > SHA_FILE_LIMIT:
                return F(sig, TESTIMONY, "TOO_LARGE", claimed, None, None, "ファイルが大きすぎる")
            h = hashlib.sha256()
            with open(real, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            actual = h.hexdigest()
        ev = {"path": rel, "sha256": actual}
        obs = "ファイル %s の実際の sha256: %s" % (rel, actual)
        c = nfkc(claimed).strip().lower()
        ell = c.endswith("...")
        c = c.rstrip(".")
        if not re.fullmatch(r"[0-9a-f]*", c) or len(c) > 64:
            return F(sig, TESTIMONY, "SHA_MALFORMED", claimed, actual, ev, obs)
        if len(c) < 12:
            return F(sig, TESTIMONY, "SHA_TOO_SHORT", claimed, actual, ev, obs)
        if (len(c) == 64 and not ell and c == actual) or (len(c) == 64 and ell and c == actual):
            return F(sig, RECORD, "MATCH", claimed, actual, ev, obs)
        if len(c) < 64 and actual.startswith(c):
            return F(sig, RECORD, "MATCH_PREFIX", claimed, actual, ev, obs)
        if self.history and not self.rev:
            for past in self._past_shas(rel):
                if past.startswith(c):
                    return F(sig, TESTIMONY, "MATCHES_PAST_VERSION", claimed, actual, ev, obs + "（過去の版の sha256 と一致: %s）" % past)
        return F(sig, MISMATCH, "SHA_DIFFERS", claimed, actual, ev, obs)

    def _past_shas(self, rel: str) -> List[str]:
        rc, out, _ = self._git("log", "--format=%H", "-n", "50", "--", rel)
        res = []
        if rc == 0:
            for h in out.decode("utf-8", "replace").split():
                st, data = self._blob(h, rel)
                if st == "ok":
                    res.append(sha256_bytes(data))
        return res

    def changed(self, raw_path: str) -> Dict[str, Any]:
        sig = "changed:%s" % nfkc(raw_path)
        real, why = self.resolve(raw_path)
        if why:
            return F(sig, self._mark_of(why), why, "changed", None, None, "ファイルを観測できなかった: %s" % why)
        if not self.base:
            return F(sig, TESTIMONY, "NO_BASE", "changed", None, None, "比べる基点（--base）が無い")
        rel = self._rel(real)
        st, data = self._blob(self.base, rel)
        if st == "badrev":
            return F(sig, TESTIMONY, "BASE_UNREADABLE", "changed", None, None, "基点 %s を読めない" % self.base)
        cur = sha256_bytes(Path(real).read_bytes())
        ev = {"path": rel, "sha256": cur}
        if st == "missing":
            return F(sig, RECORD, "MATCH", "changed", "base に無い（追加）", ev, "base %s に %s は無く、現在は sha256 %s" % (self.base, rel, cur))
        b = sha256_bytes(data)
        if b == cur:
            return F(sig, MISMATCH, "NOT_CHANGED_SINCE_BASE", "changed", "base と同一", ev, "base %s の sha256 %s と現在 %s は同じ" % (self.base, b, cur))
        return F(sig, RECORD, "MATCH", "changed", "base と違う", ev, "base の sha256 %s、現在 %s" % (b, cur))

    # events: ledger, then rerun
    def _load_ledger(self) -> None:
        if self._ledger_loaded:
            return
        self._ledger_loaded = True
        if self.ledger_path:
            self._events, self._ledger_check, self._ledger_bytes = check_ledger(self.ledger_path, self.ledger_head)

    def _run_cached(self, argv: List[str]) -> Tuple[Optional[int], bytes, bytes]:
        key = tuple(argv)
        if key not in self._runs:
            self._runs[key] = _spawn(argv, self.real_tree, self.timeout, _child_env(self.real_tree))
        return self._runs[key]

    def exit_code_for(self, argv_claim: List[str], match: Callable[[List[str]], bool], rerun_cmd: Optional[str], match_code: Optional[Callable[[List[str], int], bool]] = None) -> Dict[str, Any]:
        """{'code': int, 'source': ..., 'raw': str} or {'reason': R, 'raw': str}. Ledger events first, then (only with --rerun) an allowed re-run."""
        self._load_ledger()
        reason, raw, why_ev = "NO_EVENT", "台帳にも再実行にも、この出来事の観測が無い", None
        if self.ledger_path:
            if self._events is None:
                chk = self._ledger_check or _unverified("UNVERIFIED", [])
                reason = "LEDGER_UNVERIFIED"
                raw = "台帳が T7 の検証を通らない（status=%s、問題: %s）" % (chk["status"], _problem_text(chk["problems"]))
                why_ev = {"ledger": self.ledger_path, "status": chk["status"], "problems": chk["problems"]}
            else:
                hit = [e for e in self._events if match(e["argv"]) and (match_code is None or match_code(e["argv"], e["code"]))]
                codes = sorted({e["code"] for e in hit})
                if len(codes) == 1:
                    lb = self._ledger_bytes or b""
                    evd = {"path": self.ledger_path, "sha256": sha256_bytes(lb), "event_sha": sorted({e["sha"] for e in hit})}
                    return {"code": codes[0], "source": "ledger", "raw": "台帳の出来事の終了コード: %d" % codes[0], "evidence": evd}
                if len(codes) > 1:
                    reason, raw = "AMBIGUOUS_EVENT", "台帳の同じコマンドの終了コードが割れている: %s" % codes
        if self.rerun and rerun_cmd is not None:
            argv, why = check_command(rerun_cmd, self.real_tree)
            if argv is None:
                return {"reason": "COMMAND_NOT_ALLOWED", "raw": "許可された形ではないので再実行しない（%s）" % why}
            rc, out, err = self._run_cached(argv)
            if rc is None:
                return {"reason": "RERUN_TIMEOUT", "raw": "再実行が %s 秒を超えた" % self.timeout}
            return {"code": rc, "source": "rerun", "raw": "再実行の終了コード: %d" % rc,
                    "evidence": {"argv": list(argv), "stdout_sha256": sha256_bytes(out), "stderr_sha256": sha256_bytes(err)}}
        out = {"reason": reason, "raw": raw}
        if why_ev is not None:
            out["evidence"] = why_ev
        return out

    def exit_fact(self, cmd: Optional[str], claimed: int) -> Dict[str, Any]:
        if cmd is None:
            return F("exit:<none>", TESTIMONY, "NO_COMMAND", claimed, None, None, "コマンドが示されていない")
        cmd = nfkc(cmd)
        sig = "exit:%s" % cmd
        try:
            argv = shlex.split(cmd)
        except ValueError:
            argv = None
        if argv is None:
            ev = {"reason": "COMMAND_NOT_ALLOWED", "raw": "コマンドを解析できない"}
        else:
            ev = self.exit_code_for(argv, lambda a: a == argv, cmd)
        return self._exit_result(sig, claimed, ev)

    @staticmethod
    def _exit_result(sig: str, claimed: Any, ev: Dict[str, Any], passed: bool = False) -> Dict[str, Any]:
        if "reason" in ev:
            return F(sig, TESTIMONY, ev["reason"], claimed, None, ev.get("evidence"), ev["raw"])
        want = 0 if passed else claimed
        if ev["code"] == want:
            return F(sig, RECORD, "MATCH", claimed, ev["code"], ev.get("evidence"), ev["raw"])
        return F(sig, MISMATCH, "EXIT_CODE_DIFFERS", claimed, ev["code"], ev.get("evidence"), ev["raw"])

    # tests
    def _tests_path(self, raw: str) -> Tuple[Optional[str], Optional[str], str]:
        """(spec relative to the tree, reason, node part)"""
        p = nfkc(raw)
        file_part, _, node = p.partition("::")
        real, why = self.resolve(file_part)
        if why:
            return None, why, node
        rel = self._rel(real)
        if not (rel.startswith("tests" + os.sep) and rel.endswith(".py")):
            return None, "NOT_IN_TESTS_DIR", node
        return rel + (("::" + node) if node else ""), None, node

    def tests_facts(self, raw_path: str, claimed_n: int) -> List[Dict[str, Any]]:
        p = nfkc(raw_path)
        file_part = p.partition("::")[0]
        e_sig, c_sig, p_sig = "test_exists:%s" % p, "test_count:%s" % p, "test_passed:%s" % p
        # test_exists / outside / not-in-tests
        lexical = os.path.realpath(os.path.join(self.tree, file_part))
        inside = lexical == self.real_tree or lexical.startswith(self.real_tree + os.sep)
        if not inside:
            return [F(e_sig, TESTIMONY, "PATH_OUTSIDE_TREE", "exists", None, None, "tree の外を指している")]
        real, why = self.resolve(file_part)
        if why == "FILE_MISSING":
            return [F(e_sig, MISMATCH, "TEST_NOT_FOUND", "exists", "無い", None, "tree に %s は無い" % file_part)]
        if why:
            return [F(e_sig, self._mark_of(why), why, "exists", None, None, "観測できなかった: %s" % why)]
        spec, why2, _ = self._tests_path(p)
        if why2:
            return [F(e_sig, TESTIMONY, why2, "exists", None, None, "tests/ 以下の .py ではない: %s" % why2)]
        t_ev = {"path": self._rel(real), "sha256": sha256_bytes(Path(real).read_bytes())}
        facts = [F(e_sig, RECORD, "MATCH", "exists", "ある", dict(t_ev), "tests/ 以下に %s はある" % file_part)]
        # collected count
        argv, bad = check_command("pytest --collect-only -q " + shlex.quote(spec), self.real_tree)
        if argv is None:
            facts.append(F(c_sig, TESTIMONY, "COMMAND_NOT_ALLOWED", claimed_n, None, None, "収集の形が許可されない（%s）" % bad))
        else:
            rc, out, err = self._collect_cached(argv)
            text = out.decode("utf-8", "replace")
            m = re.search(r"(\d+) tests? collected", text)
            if m is None and rc == 5 and re.search(r"no tests collected", text):
                # -q hides skips: a module-level skip looks the same as a file with 0 tests.
                # Re-collect without -q (allowed form) and read the summary line.
                argv2, _bad2 = check_command("pytest --collect-only " + shlex.quote(spec), self.real_tree)
                if argv2 is None:
                    facts.append(F(c_sig, TESTIMONY, "COMMAND_NOT_ALLOWED", claimed_n, None, None, "収集の形が許可されない"))
                    rc = -1
                else:
                    rc2, out2, err2 = self._collect_cached(argv2)
                    text2 = out2.decode("utf-8", "replace")
                    if rc2 is None:
                        rc = None
                    elif rc2 == 5 and re.search(r"^collected 0 items\s*$", text2, re.M) and not re.search(r"skipped|error|deselected|xfail", text2, re.I):
                        m = re.match(r"(0)", "0")  # observed value 0: nothing skipped/errored
                        rc = 0
                    elif re.search(r"skipped", text2, re.I) and not re.search(r"error", text2, re.I):
                        facts.append(F(c_sig, TESTIMONY, "COLLECT_SKIPPED", claimed_n, None, None, "収集で skip（モジュール単位）になり件数を観測できない: %s" % text2[-160:].strip()))
                        rc = -1
                    else:
                        text = text2
                        rc = rc2 if rc2 not in (0, 5) else 1
            if rc == -1:
                pass
            elif rc is None:
                facts.append(F(c_sig, TESTIMONY, "RERUN_TIMEOUT", claimed_n, None, None, "収集が %s 秒を超えた" % self.timeout))
            elif rc != 0 or not m:
                facts.append(F(c_sig, TESTIMONY, "COLLECT_FAILED", claimed_n, None, None, "pytest の収集が終了コード %s（%s）" % (rc, (text + err.decode("utf-8", "replace"))[-160:].strip())))
            else:
                n = int(m.group(1))
                obs = "pytest --collect-only: %d 件を収集" % n
                facts.append(F(c_sig, RECORD if n == claimed_n else MISMATCH, "MATCH" if n == claimed_n else "COUNT_DIFFERS", claimed_n, n, dict(t_ev), obs))
        # passed
        node_cmd = "pytest -q " + shlex.quote(spec)
        ev = self.exit_code_for([], lambda a: _is_pytest_argv(a) is not None, node_cmd, _passed_event_match(spec))
        facts.append(self._exit_result(p_sig, "passed", ev, passed=True))
        return facts

    def _collect_cached(self, argv: List[str]) -> Tuple[Optional[int], bytes, bytes]:
        return self._run_cached(argv)

    def number_fact(self, numtext: str, raw_path: str) -> Dict[str, Any]:
        sig = "number:%s@%s" % (nfkc(numtext), nfkc(raw_path))
        nums = numbers_in(numtext)
        real, why = self.resolve(raw_path)
        if why:
            return F(sig, self._mark_of(why), why, nums, None, None, "ファイルを観測できなかった: %s" % why)
        if not nums:
            return F(sig, TESTIMONY, "NO_NUMBER_IN_TEXT", nums, None, None, "申告文に数値が無い")
        if os.path.getsize(real) > NUMBER_FILE_LIMIT:
            return F(sig, TESTIMONY, "TOO_LARGE", nums, None, None, "ファイルが大きすぎる")
        data = Path(real).read_bytes()
        text = data.decode("utf-8", "replace")
        ev = {"path": self._rel(real), "sha256": sha256_bytes(data)}
        missing = [n for n in nums if not number_present(n, text)]
        obs = "ファイル %s の先頭: %s" % (ev["path"], text[:1500])
        if missing:
            return F(sig, MISMATCH, "NUMBER_NOT_IN_OUTPUT", nums, {"missing": missing}, ev, obs)
        return F(sig, RECORD, "MATCH", nums, {"found": nums}, ev, obs)

    # ---- one claim
    def verify(self, c: Dict[str, Any]) -> List[Dict[str, Any]]:
        k = c["kind"]
        if k == "acceptance":
            facts = [self.exit_fact(c.get("cmd"), c["exit"])]
            if c.get("out"):
                facts.append(self.file_sha(c["out"]["path"], c["out"]["sha"]))
            return facts
        if k == "changed":
            return [self.file_sha(c["path"], c["sha"]), self.changed(c["path"])]
        if k == "file_sha":
            return [self.file_sha(c["path"], c["sha"])]
        if k == "tests_added":
            if c.get("ambiguous"):
                return [F("test_count:%s" % nfkc(c["path"]), TESTIMONY, "AMBIGUOUS_CLAIM", None, None, None, "1 行に複数のパスか複数の件数があり、組を決められない")]
            return self.tests_facts(c["path"], c["count"])
        if k == "number":
            return [self.number_fact(c["numtext"], c["path"])]
        return []


# ===================================================================== the run
def _result_claim(extractor: str, idx: int, c: Dict[str, Any], facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    if c["kind"] == "offform":
        mark, reasons = TESTIMONY, ["OFF_FORM"]
    else:
        mark = fold_marks([f["mark"] for f in facts])
        reasons = [f["reason"] for f in facts if f["mark"] == mark] or ["MATCH"]
    return {"claim_id": "%s-%d" % (extractor, idx), "extractor": extractor, "line": c.get("line"), "kind": c["kind"], "text": c["text"], "mark": mark,
            "reason": reasons[0], "reasons": reasons, "facts": facts, "why": c.get("why")}


def run_attest(report_text: str, tree: str, *, ledger: Optional[str] = None, rerun: bool = False, base: Optional[str] = None, rev: Optional[str] = None,
               extractors: Sequence[str] = ("V", "a"), partial: bool = False, search_dirs: Sequence[str] = (), history: bool = False,
               timeout: float = DEFAULT_TIMEOUT, report_path: Optional[str] = None, cache: Optional[Dict[Tuple[str, ...], Tuple[Optional[int], bytes, bytes]]] = None,
               ledger_head: Optional[str] = None) -> Dict[str, Any]:
    v = Verifier(tree, ledger=ledger, rerun=rerun, base=base, rev=rev, search_dirs=search_dirs, partial=partial, history=history, timeout=timeout, cache=cache, ledger_head=ledger_head)
    out: Dict[str, Any] = {"schema": SCHEMA, "report": {"path": report_path, "sha256": sha256_bytes(report_text.encode("utf-8"))}, "tree": {"path": v.real_tree},
                           "flags": {"ledger": ledger, "rerun": rerun, "base": base, "rev": rev, "extractors": list(extractors), "partial_tree": partial,
                                     "search_dirs": list(search_dirs), "history": history},
                           "extractors": {}, "notes": []}
    if ledger_head is not None:
        out["flags"]["ledger_head"] = ledger_head
    rc, so, _ = v._git("rev-parse", "HEAD")
    out["tree"]["head"] = so.decode().strip() if rc == 0 else None
    found_section = False
    for ex in extractors:
        if ex == "V":
            claims, found_section = parse_v(report_text)
        elif ex == "a":
            claims = parse_a(report_text)
        elif ex == "b":
            claims = parse_b(report_text)
        else:
            raise ValueError("unknown extractor %r" % ex)
        results = [_result_claim(ex, i + 1, c, v.verify(c)) for i, c in enumerate(claims)]
        counts = {m: sum(1 for r in results if r["mark"] == m) for m in MARKS}
        off = [{"line": r["line"], "text": r["text"]} for r in results if r["kind"] == "offform"]
        out["extractors"][ex] = {"claims": results, "counts": counts, "offform": off,
                                 "facts": {m: sum(1 for r in results for f in r["facts"] if f["mark"] == m) for m in MARKS}}
    allc = [r for e in out["extractors"].values() for r in e["claims"]]
    if not allc:
        out["notes"].append("NO_COMPLETION_SECTION")
    marks = [r["mark"] for r in allc]
    out["exit_code"] = 1 if MISMATCH in marks else (0 if marks and all(m == RECORD for m in marks) else 4)
    return out


def format_text(res: Dict[str, Any]) -> str:
    jp = {RECORD: "記録", TESTIMONY: "証言", MISMATCH: "食い違い"}
    lines = ["vera attest  report=%s  tree=%s" % (res["report"]["path"], res["tree"]["path"])]
    for ex, e in res["extractors"].items():
        c = e["counts"]
        lines.append("[%s] 申告 %d 件: 記録 %d / 証言 %d / 食い違い %d（読み飛ばした形外れの行 %d）" % (ex, sum(c.values()), c[RECORD], c[TESTIMONY], c[MISMATCH], len(e["offform"])))
        for r in e["claims"]:
            lines.append("  %s 行%s %s %s [%s] %s" % (r["claim_id"], r["line"], jp[r["mark"]], r["reason"], r["kind"], r["text"][:90]))
            for f in r["facts"]:
                lines.append("      %s %s %s  申告=%s 実際=%s" % (jp[f["mark"]], f["reason"], f["fact"][:70], json.dumps(f["claimed"], ensure_ascii=False)[:100],
                                                          json.dumps(f["actual"], ensure_ascii=False)[:100]))
    for n in res["notes"]:
        lines.append("注: " + n + "（完了の段が読めなかった）")
    return "\n".join(lines)


def cli_main(args: Any) -> int:
    """`vera attest`. Exit: 0 all RECORD / 1 a MISMATCH / 4 testimony only (or no completion section) / 2 bad argument / 3 the --record ledger is broken."""
    report, tree = Path(args.report), Path(args.tree)
    if not report.is_file() or not tree.is_dir():
        print(json.dumps({"kind": "unknown", "verdict": "BAD_ARGUMENT", "reason": "report or tree not found"}, ensure_ascii=False))
        return 2
    sel = {"structured": ("V", "a"), "V": ("V",), "a": ("a",), "b": ("b",), "all": ("V", "a", "b")}[getattr(args, "extractor", "structured")]
    rec = getattr(args, "record", None)
    led = None
    if rec:
        from .llm_choice import LedgerIntegrityError
        from .testimony_ledger import TestimonyLedger
        try:
            led = TestimonyLedger(rec)
        except LedgerIntegrityError as e:
            print(json.dumps({"kind": "unknown", "verdict": "LEDGER_BROKEN", "reason": str(e)}, ensure_ascii=False))
            return 3
    text = report.read_text(encoding="utf-8", errors="replace")
    res = run_attest(text, str(tree), ledger=getattr(args, "ledger", None), rerun=bool(getattr(args, "rerun", False)), base=getattr(args, "base", None),
                     rev=getattr(args, "rev", None), extractors=sel, partial=bool(getattr(args, "partial_tree", False)),
                     search_dirs=list(getattr(args, "search_dir", None) or []), history=bool(getattr(args, "history", False)),
                     timeout=float(getattr(args, "timeout", DEFAULT_TIMEOUT)), report_path=str(report),
                     ledger_head=getattr(args, "ledger_head", None))
    if led is not None:
        attest_id = hashlib.sha256(json.dumps([res["report"]["sha256"], res["flags"]], sort_keys=True).encode()).hexdigest()[:16]
        for ex, e in res["extractors"].items():
            for r in e["claims"]:
                led.record_attestation({"attest_id": attest_id, "claim_id": r["claim_id"], "extractor": ex, "mark": r["mark"], "reason": r["reason"], "facts": r["facts"],
                                        "report": res["report"], "tree": res["tree"], "flags": res["flags"], "claim_text": r["text"], "line": r["line"]})
        res["recorded_in"] = str(rec)
    print(json.dumps(res, ensure_ascii=False, indent=1) if getattr(args, "json", False) else format_text(res))
    return res["exit_code"]


# ===================================================================== (c) the LLM judge: comparison only (never a RECORD, never in a ledger)
LLM_MODEL = "qwen3.5:4b"
LLM_PROMPT_VERSION = 2          # 1 gave the judge the internal fact signature; 2 describes the point in plain Japanese (docs/ATTEST.md, amendment 2)
LLM_PROMPT = ("あなたは完了申告の照合係です。次の「申告」の一点が「観測」と一致するかだけを答えてください。\n申告: {claim}\n確かめたい点: {fact}\n"
              "観測: {obs}\n\n一致するなら「はい」、一致しないなら「いいえ」、観測からは判断できないなら「不明」。この 3 語のうち 1 語だけで答えてください。\n答え:")


def fact_phrase(fact: Dict[str, Any]) -> str:
    """The point to check, in plain Japanese (the judge is not shown the internal signature, the verifier's mark or its reason)."""
    kind, _, subject = fact["fact"].partition(":")
    cl = json.dumps(fact["claimed"], ensure_ascii=False)
    if kind == "file_sha":
        return "ファイル %s の sha256 が %s であること" % (subject, fact["claimed"])
    if kind == "changed":
        return "ファイル %s が基点から変更された（基点と内容が違う）こと" % subject
    if kind == "test_exists":
        return "テストファイル %s が存在すること" % subject
    if kind == "test_count":
        return "テストファイル %s から収集されるテストが %s 件であること" % (subject, cl)
    if kind == "test_passed":
        return "テスト %s が通った（終了コード 0）こと" % subject
    if kind == "exit":
        return "コマンド %s の終了コードが %s であること" % (subject, cl)
    if kind == "number":
        text, _, path = subject.rpartition("@")
        return "文「%s」の数値 %s がファイル %s の中に現れること" % (text, cl, path)
    return subject


def llm_prompt(claim_text: str, fact: Dict[str, Any]) -> str:
    return LLM_PROMPT.format(claim=claim_text, fact=fact_phrase(fact), obs=fact["observation"] or "観測なし")


def parse_llm_answer(text: Any) -> str:
    t = nfkc(text or "").strip().lstrip("「『\"' 答え:")
    for word, tag in (("はい", "LLM_YES"), ("いいえ", "LLM_NO"), ("不明", "LLM_UNKNOWN")):
        if t.startswith(word):
            return tag
    return "LLM_UNPARSEABLE"


def llm_judge(claim_text: str, fact: Dict[str, Any], generate: Optional[Callable[..., Dict[str, Any]]] = None, model: str = LLM_MODEL) -> Dict[str, Any]:
    """One answer of the judge. `generate` is the call site (tests put a fake in); the default is the local Ollama. The result is typed `generated`."""
    if generate is None:
        from .llm_local import ollama_generate as generate       # local Ollama only
    prompt = llm_prompt(claim_text, fact)
    r = generate(model, prompt, temperature=0.0, think=False, num_predict=64, timeout=120.0)
    raw = r.get("text") if isinstance(r, dict) and r.get("ok") else None
    return {"type": "generated", "answer": parse_llm_answer(raw), "raw": raw, "ok": bool(isinstance(r, dict) and r.get("ok")), "prompt": prompt}
