"""Build step of the C library (`python -m verantyx.accel.build`): compiles verantyx/accel/vxcore.c with the system C compiler into a cache directory.

This is the ONLY place of the accelerator that runs a process (the compiler).  It lives outside `verantyx/loom` and is never imported by it: the loom (and `verantyx.accel` at
run time) only LOADS an already-built library (cbind.py) and fails loudly when it is not there, so a run never starts a process, whatever `VERA_ACCEL` says.  CI runs this step once
before the `VERA_ACCEL=c` suites; a developer runs it once per checkout (the file name holds the sha of the C source and the platform, so a changed source is a new file, never a stale one).

  python -m verantyx.accel.build            build (if absent) and print the library path
  python -m verantyx.accel.build --force    rebuild
Environment: CC (default cc), VERA_ACCEL_CACHE (default verantyx/accel/_build), VERA_ACCEL_LIB (cbind loads exactly this file; never built).
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "vxcore.c")


def cache_dir() -> str:
    return os.environ.get("VERA_ACCEL_CACHE") or os.path.join(HERE, "_build")


def lib_name() -> str:
    ext = {"Darwin": "dylib", "Windows": "dll"}.get(platform.system(), "so")
    with open(SOURCE, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()[:12]
    return "libvxcore-%s-%s-%s.%s" % (sha, platform.system().lower(), platform.machine().lower(), ext)


def lib_path() -> str:
    return os.path.join(cache_dir(), lib_name())


def command(out: str) -> List[str]:
    cc = os.environ.get("CC") or "cc"
    shared = ["-dynamiclib"] if platform.system() == "Darwin" else ["-shared"]
    return [cc, "-std=c11", "-O2", "-fPIC", "-Wall", "-Wextra"] + shared + ["-o", out, SOURCE]


def ensure(force: bool = False) -> str:
    out = lib_path()
    if os.path.exists(out) and not force:
        return out
    os.makedirs(cache_dir(), exist_ok=True)
    tmp = out + ".tmp%d" % os.getpid()
    r = subprocess.run(command(tmp), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
    if r.returncode != 0:
        raise RuntimeError("the C compiler failed (%s):\n%s" % (" ".join(command(tmp)), r.stdout))
    os.replace(tmp, out)                                    # atomic: parallel workers never see a half-written library
    return out


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    print(ensure(force="--force" in argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
