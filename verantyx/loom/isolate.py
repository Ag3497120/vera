"""LOOM-d2: the OS half of enforcement layer L3 (docs/LINE3_LOOM_DESIGN.md 7.1, 9.1, 9.4; L-LOOM-85..).

The loom's Sandbox class confines the MCP server's file access in CODE; the harness's tests step runs text woven by a model.  Neither is a
wall against a process that is already running.  This module puts the operating system around such a process:

  mechanism   macOS `sandbox-exec` with the static profile tools/loom_isolation_profile.sb (deprecated by Apple, present and working here).
              The profile denies ALL network (inet, inet6 and unix-domain), fork and exec (but the one interpreter), every read outside the
              python runtime and the job's read roots, and every write outside the job's write roots.  Paths arrive as `-D` parameters, so the
              sha256 of the profile FILE names the rule set (`profile_sha`) and does not depend on the machine.
  launcher    `python -s -S -P -c BOOT <json>`: no user site, no site.py (so no .pth files, no sitecustomize), no cwd on sys.path; the
              environment is built from scratch (never copied from the caller).  This is `python -I -S` with one difference, stated plainly:
              -I also means -E, which would drop PYTHONHASHSEED=0, and the repository's determinism contract wants it; with an environment
              built from nothing, -E has nothing left to ignore.  BOOT sets the resource limits INSIDE the sandboxed process (soft = hard,
              so the job cannot raise them), puts the listed directories on sys.path, and runs pytest / a module / the probe.
  limits      RLIMIT_CPU, RLIMIT_FSIZE, RLIMIT_NOFILE, RLIMIT_CORE=0 are real on macOS.  RLIMIT_AS / RLIMIT_DATA are NOT: setrlimit refuses them
              (EINVAL) on this macOS.  Memory is therefore bounded by a WATCHDOG in the parent (RSS polled with `ps`, SIGKILL of the process
              group past the cap).  It is weaker than an rlimit (a burst between two polls is not seen) and the module says so.
  probe       `probe(policy)` runs a script INSIDE the sandbox with the very same profile, parameters and launcher, and records, as a typed
              result, whether: a connect() to the loopback and to a non-routable address and a unix-socket connect and a bind all fail with
              EPERM; a write outside the write roots fails (the control: a write inside works); a read of $HOME/.ssh, of $HOME, of a decoy
              file and of /etc/passwd fails; a read of the fixture works and returns the bytes the parent hashed; fork and exec fail; the
              rlimits are what was asked; the sysctl that returns the PARENT's environment (KERN_PROCARGS2) and the process table
              (KERN_PROC_ALL) are denied (or ctypes, the only way to call them from Python, cannot even be imported).  The gate of the harness is this result, not a token.

Fallback (the OVERRIDE only, never the gate): when the probe cannot pass (no sandbox-exec, a nested sandbox), `--isolation-confirmed <token>` makes
the harness run the same launcher WITHOUT sandbox-exec: `python -s -S -P`, a cleared environment, rlimits, the watchdog, stdin = /dev/null,
and the network "blocked" by replacing socket.socket in the process.  That is weaker by construction (an extension module goes around it), the
attest row says so (`mechanism: "python_fallback"`, `network: "monkeypatched"`), and no probe can pass it.  Nothing in this module reaches the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

MECHANISM = "sandbox-exec"
SANDBOX_EXEC = "/usr/bin/sandbox-exec"
PROFILE_PATH = Path(__file__).resolve().parents[2] / "tools" / "loom_isolation_profile.sb"
PY_FLAGS = ("-s", "-S", "-P")                      # python -I -S minus the -E that would drop PYTHONHASHSEED (see the module docstring)
N_RT, N_READ, N_LIST, N_WRITE = 20, 16, 4, 4        # slots of the profile; unused slots point at NOPLACE
NOPLACE = "/private/var/empty/.loom-no-place"
PROBE_TIMEOUT_S = 30
KILL_MEMORY = -10                                   # exit code the watchdog reports (the timeout is -9, as in L-LOOM-73)
KILL_TIMEOUT = -9


class IsolationUnavailable(Exception):
    """sandbox-exec cannot be used here; `reason` is a short typed code."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ---------------------------------------------------------------------------------------------------------------------------------
# the profile
# ---------------------------------------------------------------------------------------------------------------------------------
def profile_bytes() -> bytes:
    return PROFILE_PATH.read_bytes()


def profile_sha() -> str:
    """sha256 of the bytes of tools/loom_isolation_profile.sb: the same on every machine and every call (the paths are -D parameters)."""
    return hashlib.sha256(profile_bytes()).hexdigest()


def _real(p) -> str:
    return os.path.realpath(str(p))


# ---------------------------------------------------------------------------------------------------------------------------------
# the policy: the places
# ---------------------------------------------------------------------------------------------------------------------------------
def links_on(path: str, _depth: int = 0) -> List[str]:
    """Every symlink met while resolving `path` component by component (the venv's bin/python -> python3.11 -> /opt/homebrew/opt/python@3.11/...):
    the kernel checks metadata on each of them, not only on the real file."""
    if _depth > 16:
        return []
    cur = "/"
    parts = [x for x in path.split("/") if x]
    for i, part in enumerate(parts):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            tgt = os.readlink(cur)
            tgt = tgt if os.path.isabs(tgt) else os.path.normpath(os.path.join(os.path.dirname(cur), tgt))
            return [cur] + links_on(os.path.join(tgt, *parts[i + 1:]), _depth + 1)
    return []


def site_dirs() -> List[str]:
    """The site-packages directories of this interpreter, in sys.path order (what `-S` leaves out; BOOT puts them back explicitly, no .pth)."""
    out: List[str] = []
    for p in sys.path:
        if p and os.path.basename(p) in ("site-packages", "dist-packages") and os.path.isdir(p) and _real(p) not in out:
            out.append(_real(p))
    return out


def runtime_roots(extra: Iterable = ()) -> Tuple[str, ...]:
    """The python runtime the job may READ: the venv prefix, the framework prefix it links, the site-packages directories on sys.path and
    the dylib packages the extension modules link (openssl, mpdecimal, sqlite, xz) and every symlink on the way to them.  Real paths, de-duplicated, sorted."""
    roots = {_real(sys.prefix), _real(sys.base_prefix), _real(sys.exec_prefix)}
    roots.update(site_dirs())
    brew = "/opt/homebrew"
    for name in ("openssl@3", "mpdecimal", "sqlite", "xz"):          # the only /opt/homebrew dylibs lib-dynload/*.so link (otool -L)
        link = brew + "/opt/" + name
        if os.path.isdir(link):
            roots.add(_real(link))
            roots.update(links_on(link))
    roots.update(_real(e) for e in extra)
    roots.update(links_on(sys.executable))
    return tuple(sorted(r for r in roots if not any(r != o and (r == o or r.startswith(o.rstrip("/") + "/")) for o in roots)))


@dataclass(frozen=True)
class Policy:
    """What a job may touch.  `read` / `write` are real paths (a file or a folder: `subpath` matches both); `list` are folders whose NAMES (not
    contents) may be listed (a sys.path entry whose children are only partly readable); `runtime` is runtime_roots(); `python` is the
    interpreter as invoked (a venv symlink keeps its venv)."""
    read: Tuple[str, ...]
    write: Tuple[str, ...]
    list: Tuple[str, ...] = ()
    runtime: Tuple[str, ...] = field(default_factory=runtime_roots)
    python: str = field(default_factory=lambda: sys.executable)

    def __post_init__(self) -> None:
        for name, vals, cap in (("read", self.read, N_READ), ("write", self.write, N_WRITE), ("list", self.list, N_LIST), ("runtime", self.runtime, N_RT)):
            if len(vals) > cap:
                raise ValueError("policy %s has %d entries, the profile has %d slots" % (name, len(vals), cap))
            for v in vals:
                if not os.path.isabs(v):
                    raise ValueError("policy %s: %r is not an absolute path" % (name, v))
        if not os.path.exists(self.python):
            raise IsolationUnavailable("python_missing")

    @classmethod
    def make(cls, read: Iterable = (), write: Iterable = (), list: Iterable = (), python: Optional[str] = None) -> "Policy":
        rd = tuple(sorted({_real(p) for p in read}))
        wr = tuple(sorted({_real(p) for p in write}))
        ls = tuple(sorted({_real(p) for p in list}))
        return cls(read=rd, write=wr, list=ls, runtime=runtime_roots(), python=python or sys.executable)

    def params(self) -> Dict[str, str]:
        real = _real(self.python)
        app = os.path.join(os.path.dirname(os.path.dirname(real)), "Resources", "Python.app", "Contents", "MacOS", "Python")
        out = {"EXEC0": real, "EXEC1": _real(app) if os.path.exists(app) else NOPLACE, "NOPLACE": NOPLACE}
        for prefix, vals, cap in (("RT", self.runtime, N_RT), ("READ", self.read, N_READ), ("LIST", self.list, N_LIST), ("WRITE", self.write, N_WRITE)):
            for i in range(cap):
                out["%s%d" % (prefix, i)] = vals[i] if i < len(vals) else NOPLACE
        return out


def sandbox_argv(policy: Policy, argv: Sequence[str]) -> List[str]:
    """`sandbox-exec -f PROFILE -D K=V ... argv`.  sandbox-exec applies the profile and then exec()s argv in the same process id."""
    out = [SANDBOX_EXEC, "-f", str(PROFILE_PATH)]
    for k, v in sorted(policy.params().items()):
        out += ["-D", "%s=%s" % (k, v)]
    return out + list(argv)


# ---------------------------------------------------------------------------------------------------------------------------------
# the launcher
# ---------------------------------------------------------------------------------------------------------------------------------
_BOOT = r'''
import sys, os, json
cfg = json.loads(sys.argv[1])
import resource
for _n, _v in cfg["rlimits"]:
    try:
        resource.setrlimit(getattr(resource, _n), (_v, _v))
    except (ValueError, OSError):
        os._exit(97)
if cfg.get("block_socket"):                    # the WEAK fallback only (no sandbox-exec): not a wall, a seat belt against the careless
    import errno as _e, socket as _s

    def _denied(*_a, **_k):
        raise OSError(_e.EPERM, "network disabled (loom fallback)")
    _s.socket = _denied
    _s.create_connection = _denied
    _s.getaddrinfo = _denied
sys.path[:0] = cfg["path"]
kind = cfg["kind"]
if kind == "pytest":
    sys.argv = ["pytest"] + cfg["args"]
    import pytest

    class Rec:                                 # L-LOOM-116: the harness reads what pytest itself counted (collected / failed / exitstatus)
        def pytest_sessionfinish(self, session, exitstatus):
            try:
                with open(cfg["result_path"], "w", encoding="utf-8") as fh:
                    json.dump({"collected": int(session.testscollected), "failed": int(session.testsfailed), "exitstatus": int(exitstatus)}, fh)
            except BaseException:
                pass
    sys.exit(pytest.main(cfg["args"], plugins=[Rec()] if cfg.get("result_path") else []))
elif kind == "module":
    import runpy
    sys.argv = [cfg["module"]] + cfg["args"]
    runpy.run_module(cfg["module"], run_name="__main__", alter_sys=True)
elif kind == "probe":
    import errno, hashlib, socket, resource as _r

    def name(e):
        if isinstance(e, socket.timeout):
            return "TIMEOUT"
        return errno.errorcode.get(getattr(e, "errno", None) or 0, type(e).__name__)

    def attempt(fn):
        try:
            fn()
            return "OK"
        except BaseException as e:
            return name(e)

    def conn(family, addr):
        def f():
            s = socket.socket(family, socket.SOCK_STREAM)
            try:
                s.settimeout(1.0)
                s.connect(addr)
            finally:
                s.close()
        return f

    def udp():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.sendto(b"x", ("127.0.0.1", 9))
        finally:
            s.close()

    def bind():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
        finally:
            s.close()

    def wr(path, mode="w"):
        def f():
            with open(path, mode) as fh:
                fh.write("x")
        return f

    def rd(path):
        def f():
            with open(path, "rb") as fh:
                fh.read(16)
        return f

    def ls(path):
        return lambda: os.listdir(path)

    def fork():
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        os.waitpid(pid, 0)

    def execv():
        pid = os.posix_spawn("/bin/echo", ["echo"], {})
        os.waitpid(pid, 0)

    def sysctl():
        """KERN_PROCARGS2 of the PARENT (its arguments AND ENVIRONMENT) and KERN_PROC_ALL (the process table) through libc's sysctl().  A failed
        import of ctypes counts as blocked (under the profile `import ctypes` itself dies with EPERM: it calls os.uname(), a sysctl); if the
        library IS reachable, both calls must answer EPERM / EACCES."""
        try:
            import ctypes
        except BaseException as e:
            return {"ctypes_import": "blocked:" + name(e)}
        try:
            libc = ctypes.CDLL(None, use_errno=True)
        except BaseException as e:
            return {"ctypes_import": "OK", "libc": "blocked:" + name(e)}
        res = {"ctypes_import": "OK"}
        for key, mib in (("procargs2_parent", [1, 49, os.getppid()]), ("proc_all", [1, 14, 0, 0])):
            arr = (ctypes.c_int * len(mib))(*mib)
            size = ctypes.c_size_t(0)
            rc = libc.sysctl(arr, len(mib), None, ctypes.byref(size), None, 0)
            res[key] = "OK" if rc == 0 else errno.errorcode.get(ctypes.get_errno(), "errno_" + str(ctypes.get_errno()))
        return res

    p = cfg["probe"]
    out = {"net": {"loopback_closed_port": attempt(conn(socket.AF_INET, ("127.0.0.1", 9))),
                   "non_routable": attempt(conn(socket.AF_INET, ("192.0.2.1", 9))),
                   "unix_socket": attempt(conn(socket.AF_UNIX, "/var/run/mDNSResponder")),
                   "udp_sendto": attempt(udp), "bind_listen": attempt(bind)},
           "write_outside": {k: attempt(wr(v)) for k, v in p["write_outside"].items()},
           "write_inside": attempt(wr(p["write_inside"])),
           "read_secret": {k: attempt(ls(v) if k.startswith("ls_") else rd(v)) for k, v in p["read_secret"].items()},
           "proc": {"fork": attempt(fork), "exec": attempt(execv)},
           "sysctl": sysctl()}
    try:
        with open(p["fixture_file"], "rb") as fh:
            out["fixture"] = hashlib.sha256(fh.read()).hexdigest()
    except BaseException as e:
        out["fixture"] = name(e)
    out["rlimits"] = {n: _r.getrlimit(getattr(_r, n))[0] for n in p["rlimit_names"]}
    try:
        os.unlink(p["write_inside"])
    except OSError:
        pass
    sys.stdout.write("LOOM_PROBE " + json.dumps(out, sort_keys=True) + "\n")
    sys.stdout.flush()
else:
    os._exit(96)
'''
BOOT_SHA = hashlib.sha256(_BOOT.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Limits:
    cpu_s: Optional[int] = 50              # RLIMIT_CPU (soft = hard); the wall-clock timeout of the caller is the larger
    fsize_bytes: Optional[int] = 32 << 20  # RLIMIT_FSIZE
    nofile: Optional[int] = 256            # RLIMIT_NOFILE
    mem_rss_bytes: Optional[int] = 2 << 30  # parent-side watchdog (RLIMIT_AS does not exist on this macOS)

    def rlimits(self) -> List[Tuple[str, int]]:
        out = [("RLIMIT_CORE", 0)]
        if self.cpu_s is not None:
            out.append(("RLIMIT_CPU", self.cpu_s))
        if self.fsize_bytes is not None:
            out.append(("RLIMIT_FSIZE", self.fsize_bytes))
        if self.nofile is not None:
            out.append(("RLIMIT_NOFILE", self.nofile))
        return out

    def describe(self) -> dict:
        d = {"RLIMIT_CORE": 0, "RLIMIT_CPU": self.cpu_s, "RLIMIT_FSIZE": self.fsize_bytes, "RLIMIT_NOFILE": self.nofile,
             "rss_watchdog": self.mem_rss_bytes}
        return {k: v for k, v in d.items() if v is not None}


SERVER_LIMITS = Limits(cpu_s=None, fsize_bytes=256 << 20, nofile=512, mem_rss_bytes=None)     # a long-lived server: no CPU cap, no watchdog


def clean_env(scratch: str, extra: Optional[dict] = None) -> Dict[str, str]:
    """An environment built from nothing (the caller's is never copied)."""
    env = {"PATH": "/usr/bin:/bin", "HOME": scratch, "TMPDIR": scratch, "USER": "loom", "LOGNAME": "loom",
           "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env.update(extra or {})
    return env


def launcher_argv(policy: Policy, kind: str, args: Sequence[str] = (), path: Sequence[str] = (), limits: Limits = Limits(),
                  module: Optional[str] = None, probe: Optional[dict] = None, result_path: Optional[str] = None) -> List[str]:
    cfg = {"kind": kind, "args": list(args), "path": [str(p) for p in path], "rlimits": limits.rlimits()}
    if module is not None:
        cfg["module"] = module
    if result_path is not None:
        cfg["result_path"] = str(result_path)
    if probe is not None:
        cfg["probe"] = probe
    return sandbox_argv(policy, [policy.python] + list(PY_FLAGS) + ["-c", _BOOT, json.dumps(cfg, sort_keys=True)])


def fallback_argv(kind: str, python: str, args: Sequence[str] = (), path: Sequence[str] = (), limits: Limits = Limits(),
                  result_path: Optional[str] = None) -> List[str]:
    """The OVERRIDE launcher: the same interpreter flags, BOOT, rlimits and watchdog, but NO sandbox-exec, and the network 'blocked' only by
    replacing socket.socket in the process (a seat belt, not a wall: ctypes, `_socket` and any extension module go around it)."""
    cfg = {"kind": kind, "args": list(args), "path": [str(p) for p in path], "rlimits": limits.rlimits(), "block_socket": True}
    if result_path is not None:
        cfg["result_path"] = str(result_path)
    return [python] + list(PY_FLAGS) + ["-c", _BOOT, json.dumps(cfg, sort_keys=True)]


# ---------------------------------------------------------------------------------------------------------------------------------
# running a job
# ---------------------------------------------------------------------------------------------------------------------------------
@dataclass
class Outcome:
    exit_code: int
    output: str
    killed: Optional[str] = None            # "timeout" | "memory" | None


def _rss_bytes(pid: int) -> int:
    try:
        p = subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, timeout=5)
        return int(p.stdout.strip() or 0) * 1024
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0


def run_job(argv: Sequence[str], env: Dict[str, str], cwd: str, timeout: int, limits: Limits = Limits()) -> Outcome:
    """Run an already sandboxed argv: stdin = /dev/null, a wall-clock timeout, a parent-side RSS watchdog, its own process group (so the kill
    reaches every child).  Output is stdout + stderr."""
    p = subprocess.Popen(list(argv), cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         start_new_session=True)
    t0 = time.monotonic()
    killed = None
    last_rss = 0.0
    chunks: List[bytes] = []

    def drain():
        for ch in iter(lambda: p.stdout.read(65536), b""):
            chunks.append(ch)
    th = threading.Thread(target=drain, daemon=True)
    th.start()
    while p.poll() is None:
        if time.monotonic() - t0 > timeout:
            killed = "timeout"
        elif limits.mem_rss_bytes is not None and time.monotonic() - last_rss >= 0.25:
            last_rss = time.monotonic()
            if _rss_bytes(p.pid) > limits.mem_rss_bytes:
                killed = "memory"
        if killed:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except OSError:
                p.kill()
            break
        time.sleep(0.05)
    p.wait()
    th.join(5)
    out = b"".join(chunks).decode("utf-8", "replace")
    if killed == "timeout":
        return Outcome(KILL_TIMEOUT, "timeout", killed)
    if killed == "memory":
        return Outcome(KILL_MEMORY, "memory limit", killed)
    return Outcome(p.returncode, out, None)


# ---------------------------------------------------------------------------------------------------------------------------------
# the probe
# ---------------------------------------------------------------------------------------------------------------------------------
BLOCKED = ("EPERM", "EACCES")
PROPERTIES = ("network_blocked", "write_outside_blocked", "read_secret_blocked", "fixture_readable", "write_inside_ok", "process_blocked",
              "rlimits_set", "sysctl_procargs_blocked")


@dataclass(frozen=True)
class ProbeResult:
    """The proof, as a typed value.  status: "passed" (every property holds) | "failed" (a property does not) | "unavailable" (the sandbox
    could not be started: `reason`).  `properties` maps each of PROPERTIES to a bool; `evidence` is the raw outcome per attempt (errno names,
    never a path, never a time)."""
    status: str
    mechanism: str = MECHANISM
    profile_sha: str = ""
    reason: Optional[str] = None
    properties: Dict[str, bool] = field(default_factory=dict)
    evidence: Dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "passed"

    def to_row(self) -> dict:
        """What a LEDGER row may hold (L-LOOM-117): `status` and `properties` (and the typed `reason` of an unavailable probe).  The evidence is
        machine-dependent (ENOENT here, EPERM there for a file that is absent) and would make the same run hash differently on two machines."""
        d = {"status": self.status, "properties": dict(sorted(self.properties.items()))}
        if self.reason:
            d["reason"] = self.reason
        return d

    def report(self) -> dict:
        """to_row() plus the raw evidence: for an operator (stderr, the CLI, the `isolation_failed` result, the unhashed sidecar), never for a hash."""
        return dict(self.to_row(), evidence=self.evidence)


def available() -> Optional[str]:
    """None when sandbox-exec exists and starts, else a short reason."""
    if not os.path.exists(SANDBOX_EXEC):
        return "sandbox_exec_missing"
    if not PROFILE_PATH.exists():
        return "profile_missing"
    return None


def _make_decoys(home: str) -> Tuple[str, Dict[str, str], Dict[str, str]]:
    """A folder outside every root with a file that must not be readable and names where a write must not land."""
    base = tempfile.mkdtemp(prefix="loom_decoy_")
    secret = os.path.join(base, "secret.txt")
    with open(secret, "w", encoding="utf-8") as f:
        f.write("not for the job")
    nonce = os.path.basename(base)
    read_secret = {"decoy_file": secret,
                   "ls_home": home,
                   "ls_ssh": os.path.join(home, ".ssh"),
                   "ssh_ed25519": os.path.join(home, ".ssh", "id_ed25519"),
                   "ssh_rsa": os.path.join(home, ".ssh", "id_rsa"),
                   "ssh_known_hosts": os.path.join(home, ".ssh", "known_hosts"),
                   "etc_passwd": "/etc/passwd"}
    write_outside = {"decoy_dir": os.path.join(base, "w.txt"),
                     "home": os.path.join(home, ".loom_probe_" + nonce),
                     "tmp": "/tmp/.loom_probe_" + nonce,
                     "var_tmp": "/var/tmp/.loom_probe_" + nonce}
    return base, read_secret, write_outside


def _sysctl_blocked(got) -> bool:
    """L-LOOM-114: KERN_PROCARGS2 of the parent returns the parent's ENVIRONMENT (tokens included) and KERN_PROC_ALL the process table.  Blocked =
    ctypes cannot be imported / loaded (an import failure counts), or both calls answered EPERM / EACCES.  Anything else (incl. a missing key) is not."""
    if not isinstance(got, dict):
        return False
    imp = got.get("ctypes_import")
    if isinstance(imp, str) and imp.startswith("blocked:"):
        return True
    if isinstance(got.get("libc"), str) and got["libc"].startswith("blocked:"):
        return True
    return got.get("procargs2_parent") in BLOCKED and got.get("proc_all") in BLOCKED


def probe(policy: Policy, fixture_file: str, write_dir: str, limits: Limits = Limits(), home: Optional[str] = None,
          readonly_write_targets: Iterable = ()) -> ProbeResult:
    """Prove the properties from INSIDE the sandbox, with `policy`, the profile and the launcher a real job would get.

    `fixture_file`: a file under a read root (its sha256 is computed here and must come back identical).  `write_dir`: a folder under a write
    root (the control write, removed again).  `readonly_write_targets`: more paths under read roots where a write must fail (the fixture copy
    itself: the job cannot rewrite its own tests).  The decoy folder is made outside every root and removed afterwards."""
    why = available()
    if why:
        return ProbeResult("unavailable", profile_sha=profile_sha() if PROFILE_PATH.exists() else "", reason=why)
    home = home or os.path.expanduser("~")
    base, read_secret, write_outside = _make_decoys(home)
    try:
        for i, p in enumerate(readonly_write_targets):
            write_outside["readonly_%d" % i] = os.path.join(str(p), ".loom_probe_write")
        inside = os.path.join(write_dir, ".loom_probe_inside_%d" % os.getpid())
        want = hashlib.sha256(Path(fixture_file).read_bytes()).hexdigest()
        names = [n for n, _ in limits.rlimits()]
        argv = launcher_argv(policy, "probe", limits=limits, probe={
            "read_secret": read_secret, "write_outside": write_outside, "write_inside": inside, "fixture_file": fixture_file,
            "rlimit_names": names})
        env = clean_env(write_dir)
        res = run_job(argv, env, cwd=write_dir, timeout=PROBE_TIMEOUT_S, limits=Limits(mem_rss_bytes=1 << 30))
        line = next((ln for ln in res.output.splitlines() if ln.startswith("LOOM_PROBE ")), None)
        if line is None:
            low = res.output.lower()
            reason = "nested_sandbox" if "sandbox_apply" in low else ("probe_timeout" if res.killed == "timeout" else "sandbox_exec_failed")
            return ProbeResult("unavailable", profile_sha=profile_sha(), reason=reason)
        got = json.loads(line[len("LOOM_PROBE "):])
        leaked = [k for k, v in write_outside.items() if os.path.exists(v)]
        net = got["net"]
        props = {
            "network_blocked": all(v in BLOCKED for v in net.values()),
            "write_outside_blocked": all(v in BLOCKED for v in got["write_outside"].values()) and not leaked,
            "read_secret_blocked": all(v in BLOCKED or (v == "ENOENT" and not os.path.exists(read_secret[k])) for k, v in got["read_secret"].items()),
            "fixture_readable": got["fixture"] == want,
            "write_inside_ok": got["write_inside"] == "OK",
            "process_blocked": all(v in BLOCKED for v in got["proc"].values()),
            "rlimits_set": {k: v for k, v in got["rlimits"].items()} == {n: v for n, v in limits.rlimits()},
            "sysctl_procargs_blocked": _sysctl_blocked(got.get("sysctl")),
        }
        for k in leaked:
            try:
                os.unlink(write_outside[k])
            except OSError:
                pass
        evidence = {"net": net, "write_outside": got["write_outside"], "write_inside": got["write_inside"], "read_secret": got["read_secret"],
                    "fixture": "match" if props["fixture_readable"] else str(got["fixture"])[:16], "proc": got["proc"], "rlimits": got["rlimits"],
                    "sysctl": got.get("sysctl")}
        status = "passed" if all(props[k] for k in PROPERTIES) else "failed"
        return ProbeResult(status, profile_sha=profile_sha(), properties=props, evidence=evidence)
    finally:
        shutil.rmtree(base, ignore_errors=True)
        try:
            os.unlink(inside)
        except (OSError, UnboundLocalError):
            pass


def isolation_row(policy: Policy, result: ProbeResult, limits: Limits, flags: Sequence[str] = PY_FLAGS) -> dict:
    """What the attest row records as `isolation` (L-LOOM-86): the mechanism, the sha of the profile, the typed probe, the launcher's flags and
    limits.  No path, no time."""
    return {"mechanism": result.mechanism, "profile_sha": result.profile_sha, "boot_sha": BOOT_SHA, "python_flags": list(flags),
            "limits": limits.describe(), "network": "denied", "probe": result.to_row()}


# ---------------------------------------------------------------------------------------------------------------------------------
# the MCP server under the profile
# ---------------------------------------------------------------------------------------------------------------------------------
def _task_paths(tasks_path: str) -> Tuple[List[str], List[str]]:
    """(corpus files, fixture roots) named by the task bank, as absolute real paths (relative ones against the bank's folder is NOT done:
    the server resolves them against its own cwd, so this does too)."""
    files, roots = [], []
    for ln in Path(tasks_path).read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        row = json.loads(ln)
        if "corpus" in row:
            files.append(_real(row["corpus"]))
        if "fixture" in row:
            roots.append(_real(row["fixture"]))
    return files, roots


def server_policy(tasks_path: str, runs_dir: str, allow_roots: Iterable = ()) -> Policy:
    """Reads: the task bank, the corpus file(s), the fixture roots, `--allow-root`, the loom/verantyx SOURCE (the package folder; the repo root
    may be LISTED, its other files may not be read).  Writes: the runs dir."""
    files, roots = _task_paths(tasks_path)
    pkg = Path(__file__).resolve().parents[1]
    repo = pkg.parent
    Path(runs_dir).mkdir(parents=True, exist_ok=True)
    read = [tasks_path, str(pkg)] + files + roots + [str(r) for r in allow_roots]
    return Policy.make(read=read, write=[runs_dir], list=[str(repo)])


def serve_isolated(tasks_path: str, runs_dir: str, allow_roots: Iterable = (), stability: str = "strict_npa", evidence: str = "v1",
                   subject_scope: str = "clause_or_title") -> int:
    """`vera loom mcp --isolated`: prove the profile (probe, same policy), then REPLACE this process by the server under sandbox-exec (os.execve:
    stdin / stdout stay the MCP pipes).  Returns only on refusal: 3 = the probe did not pass (nothing was started)."""
    tasks_path, runs_dir = _real(tasks_path), _real(runs_dir)
    allow = [_real(r) for r in allow_roots]
    if not os.path.isfile(tasks_path):
        print(json.dumps({"status": "isolation_unavailable", "reason": "tasks_missing"}), file=sys.stderr)
        return 3
    try:
        policy = server_policy(tasks_path, runs_dir, allow)
    except (IsolationUnavailable, OSError, ValueError) as e:
        print(json.dumps({"status": "isolation_unavailable", "reason": getattr(e, "reason", type(e).__name__)}), file=sys.stderr)
        return 3
    res = probe(policy, fixture_file=tasks_path, write_dir=runs_dir, limits=SERVER_LIMITS)
    if not res.ok:
        print(json.dumps({"status": "isolation_failed", "probe": res.report()}, sort_keys=True), file=sys.stderr)
        return 3
    repo = str(Path(__file__).resolve().parents[2])
    args = ["loom", "mcp", "--tasks", tasks_path, "--runs-dir", runs_dir, "--stability", stability, "--evidence", evidence, "--subject-scope", subject_scope]
    for r in allow:
        args += ["--allow-root", r]
    argv = launcher_argv(policy, "module", args=args, path=[repo] + site_dirs(),
                         limits=SERVER_LIMITS, module="verantyx.cli")
    env = clean_env(runs_dir, {"LOOM_ISOLATED": res.profile_sha})
    # cwd is NOT changed: the task bank's relative corpus / fixture paths resolve against it, exactly as without --isolated (a cwd the
    # profile does not allow to read can still be the base of a path whose real location is allowed)
    os.execve(argv[0], argv, env)
    return 2                                 # unreachable


# ---------------------------------------------------------------------------------------------------------------------------------
# the tests step under the profile
# ---------------------------------------------------------------------------------------------------------------------------------
def tests_step_policy(work_root: str, scratch: str) -> Policy:
    """Reads: the whole temp folder (fixture copy + scratch); writes: the scratch folder only (the copy is read-only for the job)."""
    return Policy.make(read=[work_root], write=[scratch])


RESULT_NAME = "pytest_result.json"          # in the scratch folder: {collected, failed, exitstatus} as pytest counted them (the `rec` plugin of BOOT)


def pytest_job(policy: Policy, copy: str, scratch: str, test_files: Sequence[str], timeout: int, limits: Limits = Limits()) -> Outcome:
    argv = launcher_argv(policy, "pytest", args=["-q", "-p", "no:cacheprovider", "--rootdir", copy, "--"] + list(test_files), path=[copy] + site_dirs(),
                         limits=limits, result_path=os.path.join(scratch, RESULT_NAME))
    return run_job(argv, clean_env(scratch), cwd=copy, timeout=timeout, limits=limits)
