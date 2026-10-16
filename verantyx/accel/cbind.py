"""ctypes binding of the C library (vxcore.c): LOADS a library that `verantyx.accel.build` made; never compiles, never starts a process.

`mirror_of(tier)` copies a TierSpace's postings into a C Tier; `mirror_append` follows a chain (one more sentence); `CWeights` is `placement.Weights` whose cache misses are answered
by the C kernels (n_pair, p_pair): the same two integers `TierSpace.n_pair` / `p_pair` give.
"""
from __future__ import annotations

import ctypes
import os
from typing import Dict, List, Optional

from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp

ABI = 1
_LIB: Optional[ctypes.CDLL] = None


class AccelUnavailable(RuntimeError):
    pass


def lib() -> ctypes.CDLL:
    global _LIB
    if _LIB is not None:
        return _LIB
    from verantyx.accel import build
    path = os.environ.get("VERA_ACCEL_LIB") or build.lib_path()
    if not os.path.exists(path):
        raise AccelUnavailable("VERA_ACCEL=c needs the C library, which is not built: run `python -m verantyx.accel.build` (looked for %s)" % path)
    L = ctypes.CDLL(path)
    L.vx_abi.restype = ctypes.c_int
    if L.vx_abi() != ABI:
        raise AccelUnavailable("the C library %s has ABI %d, this binding wants %d: rebuild it" % (path, L.vx_abi(), ABI))
    vp, i32, i64 = ctypes.c_void_p, ctypes.c_int32, ctypes.c_int64
    L.vx_tier_new.restype = vp
    L.vx_tier_new.argtypes = []
    L.vx_tier_free.restype = None
    L.vx_tier_free.argtypes = [vp]
    L.vx_tier_nsent.restype = i64
    L.vx_tier_nsent.argtypes = [vp]
    L.vx_tier_clone.restype = vp
    L.vx_tier_clone.argtypes = [vp, i64]
    L.vx_tier_append.restype = ctypes.c_int
    L.vx_tier_append.argtypes = [vp, i64, ctypes.POINTER(i32), ctypes.POINTER(i32), i32]
    L.vx_n.restype = i64
    L.vx_n.argtypes = [vp, i32, i64]
    L.vx_n_pair.restype = i64
    L.vx_n_pair.argtypes = [vp, i32, i32, i64]
    L.vx_p_pair.restype = i64
    L.vx_p_pair.argtypes = [vp, i32, i32, i64]
    _LIB = L
    return L


class _Handle:
    """Owns a C Tier; shared by the mirrors of a chain; freed when the last mirror goes."""
    __slots__ = ("p",)

    def __init__(self, p: int) -> None:
        if not p:
            raise MemoryError("vxcore: out of memory")
        self.p = ctypes.c_void_p(p)

    def __del__(self) -> None:
        try:
            if _LIB is not None and self.p:
                _LIB.vx_tier_free(self.p)
        except Exception:
            pass


def _append(h: _Handle, ids: Dict[str, int], sid: int, units: tuple) -> None:
    """Append sentence `sid` whose unit list is `units`: distinct unit ids with the index of their first occurrence."""
    first: Dict[int, int] = {}
    for i, u in enumerate(units):
        k = ids.get(u)
        if k is None:
            k = ids[u] = len(ids)
        if k not in first:
            first[k] = i
    n = len(first)
    arr_u = (ctypes.c_int32 * max(n, 1))(*first.keys())
    arr_f = (ctypes.c_int32 * max(n, 1))(*first.values())
    rc = lib().vx_tier_append(h.p, sid, arr_u, arr_f, n)
    if rc != 0:
        raise RuntimeError("vxcore: append failed (%d)" % rc)


def mirror_of(tier: sp.TierSpace):
    from verantyx.accel.inc import _CMirror
    h = _Handle(lib().vx_tier_new())
    ids: Dict[str, int] = {}
    for sid, us in enumerate(tier.sentence_units):
        _append(h, ids, sid, us)
    return _CMirror(h, ids, tier.N)


def mirror_append(m, new_tier: sp.TierSpace, sid: int):
    """The mirror of `new_tier` = the tier of `m` (sentences < sid) plus its sentence `sid`.  In place when the Tier holds exactly the sentences below `sid`, else on a clone (a sibling
    already took the slot)."""
    from verantyx.accel.inc import _CMirror
    L = lib()
    h = m.h
    if L.vx_tier_nsent(h.p) != sid:
        h = _Handle(L.vx_tier_clone(h.p, sid))
    _append(h, m.ids, sid, new_tier.sentence_units[sid])
    return _CMirror(h, m.ids, sid + 1)


class CWeights(pl.Weights):
    """placement.Weights with the misses answered by the C kernels (`limit` = the number of sentences of the corpus)."""

    def __init__(self, tier: sp.TierSpace, mirror, limit: int) -> None:
        super().__init__(tier)
        self._m = mirror
        self._limit = limit

    def __call__(self, x, y):
        if x is None or y is None:
            return pl.ZERO2
        k = (x, y)
        v = self._c.get(k)
        if v is None:
            t = self.tier
            if x in t.postings and y in t.postings:
                L, m = lib(), self._m
                a, b = m.ids[x], m.ids[y]
                v = (int(L.vx_n_pair(m.h.p, a, b, self._limit)), int(L.vx_p_pair(m.h.p, a, b, self._limit)))
            else:
                v = pl.ZERO2
            self._c[k] = v
        return v
