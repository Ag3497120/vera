"""L-PUB-160..: the accelerator (verantyx/accel) gives the same bytes as the plain code.  VERA_ACCEL=py is the reference; `inc` (incremental Python) and `c` (+ the C kernels) must agree
with it object for object, byte for byte.  The heavy identity runs (dev stories, meter_v1 stores, PYTHONHASHSEED 0/1/12345) are experiments/line3/pub/accel/identity.py (CI commands in
docs/LINE3_LOCAL_DECISIONS.md L-PUB-165); this file is the fast part."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import random
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3", "pub", "m5m6"))

from verantyx import accel  # noqa: E402
from verantyx.accel import build, cbind, inc  # noqa: E402
from verantyx.accel.compare import check_corpora  # noqa: E402
from verantyx.line3 import space as sp  # noqa: E402
from verantyx.loom import memory as mem  # noqa: E402
from verantyx.loom.corpus import Corpus  # noqa: E402
from verantyx.loom.state import LoomState, canonical  # noqa: E402

VOCAB = ["認証", "モジュール", "担当", "期限", "予算", "決済画面", "検索機能", "田中", "佐藤", "鈴木", "3月5日", "12万円", "高", "大阪", "京都", "東京", "公開", "変更", "確認", "仕様", "画面", "基盤"]
PART = ["は", "の", "を", "に", "で", "が", "と", "から", "まで", "も"]


def sentence(rng: random.Random) -> str:
    n = rng.randint(2, 6)
    out = []
    for _ in range(n):
        out.append(rng.choice(VOCAB))
        if rng.random() < 0.8:
            out.append(rng.choice(PART))
    if rng.random() < 0.3:
        out.insert(rng.randint(0, len(out)), "、")
    return "".join(out) + "。"


def make_rows(seed: int, n: int, kinds=("base",)) -> list:
    rng = random.Random(seed)
    return [{"kind": rng.choice(kinds), "sent": sentence(rng), "source": "mem:t/1#%d" % i} for i in range(n)]


@pytest.fixture(scope="module")
def lib():
    try:
        return build.ensure()
    except (OSError, RuntimeError) as e:                       # no C compiler on this machine: the C tests are skipped, never faked
        pytest.skip("no C compiler: %s" % e)


@pytest.fixture(autouse=True)
def _fresh():
    inc.reset()
    yield
    inc.reset()


# ------------------------------------------------------------------------------------------------------------
# the corpus
# ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed,kinds", [(1, ("base",)), (2, ("base", "memory_answer")), (3, ("base", "memory_answer", "memory_user", "memory_query"))])
def test_incremental_corpus_equals_plain(seed, kinds):
    rows = make_rows(seed, 45, kinds)
    for t in range(len(rows) + 1):
        data = mem.rows_bytes(rows[:t])
        c = inc.corpus_of(data)
        p = Corpus(data)
        check_corpora(c, p, deep=(t % 15 == 0))


def test_weights_spans_follow_carry_over_exactly():
    rows = make_rows(7, 40)
    c = None
    for t in range(1, len(rows) + 1):
        data = mem.rows_bytes(rows[:t])
        c = inc.corpus_of(data)
        p = Corpus(data)
        for tier in ("WORD", "RUN", "CHAR"):                    # touch every lazily built cache on the incremental corpus so the next one carries it
            us = c.tier(tier).units()
            rng = random.Random(t)
            for _ in range(30):
                x, y = rng.choice(us), rng.choice(us + ["nope"])
                assert c.weights(tier)(x, y) == p.weights(tier)(x, y)
            assert c.particle_after(tier, t - 1) == p.particle_after(tier, t - 1)
        assert c.spans().spans("WORD", t - 1) == p.spans().spans("WORD", t - 1)
    # a unit that was OUTSIDE the space when its pair was cached (weight 0, L-52) must be re-read once a sentence brings it in
    base = [{"kind": "base", "sent": "認証の担当は田中。", "source": "mem:t/1#0"}]
    c0 = inc.corpus_of(mem.rows_bytes(base))
    assert c0.weights("WORD")("認証", "予算") == (0, 0)
    c1 = inc.corpus_of(mem.rows_bytes(base + [{"kind": "base", "sent": "認証の予算は五万円。", "source": "mem:t/1#1"}]))
    assert c1.weights("WORD")("認証", "予算") == Corpus(mem.rows_bytes(base + [{"kind": "base", "sent": "認証の予算は五万円。", "source": "mem:t/1#1"}])).weights("WORD")("認証", "予算")
    assert c0.weights("WORD")("認証", "予算") == (0, 0)           # the parent is untouched


def test_a_sibling_and_a_rewritten_last_row_are_not_confused():
    rows = make_rows(11, 12)
    d0 = mem.rows_bytes(rows[:11])
    c0 = inc.corpus_of(d0)
    a = inc.corpus_of(mem.rows_bytes(rows[:11] + [rows[11]]))
    other = dict(rows[11], sent="別の文の予算は決まった。")
    b = inc.corpus_of(mem.rows_bytes(rows[:11] + [other]))        # a refused write leaves a sibling: same parent, another sentence
    check_corpora(a, Corpus(mem.rows_bytes(rows[:11] + [rows[11]])), deep=True)
    check_corpora(b, Corpus(mem.rows_bytes(rows[:11] + [other])), deep=True)
    check_corpora(c0, Corpus(d0), deep=True)
    # clause_at is written into the last row AFTER its corpus was built (memory._write_v4): the bytes differ, the space does not
    row_clause = dict(rows[11], clause_at=3)
    c = inc.corpus_of(mem.rows_bytes(rows[:11] + [row_clause]))
    check_corpora(c, Corpus(mem.rows_bytes(rows[:11] + [row_clause])), deep=True)
    assert c.corpus_sha != a.corpus_sha and c.space.sha256() == a.space.sha256()


def _rows_corpus(rows):
    return inc.corpus_of_rows(rows, inc.row_lines(rows, mem.row_line))


def test_rows_path_finds_its_parent_by_what_the_space_reads():
    """memory._write_v4 sets `clause_at` on a row AFTER its corpus was built, and rebuilds: the rows of the next write differ (in bytes) from the rows its parent corpus was built from."""
    rows = make_rows(31, 30)
    built = []
    for t in range(1, 31):
        part = [dict(r) for r in rows[:t]]
        for r in part[:-1]:
            r["clause_at"] = 0                                   # every earlier row has gained a clause_at since its corpus was made
        c = _rows_corpus(part)
        built.append(c)
        check_corpora(c, Corpus(mem.rows_bytes(part)), deep=(t % 10 == 0))
        part[-1]["clause_at"] = 2                                # ... and the row just written gets one too: the rebuild of the same rows
        c2 = _rows_corpus(part)
        check_corpora(c2, Corpus(mem.rows_bytes(part)))
        assert c2.space is c.space and c2.corpus_sha != c.corpus_sha     # the space is shared, not rebuilt
    # the jump of more rows than the tail limit goes through the plain code, and still agrees
    big = make_rows(37, 20)
    check_corpora(_rows_corpus(big), Corpus(mem.rows_bytes(big)), deep=True)
    # a sibling: the same history, another last sentence
    a = make_rows(41, 9)
    b = a[:8] + [dict(a[8], sent="別の文の期限は決まった。")]
    _rows_corpus(a[:8])
    check_corpora(_rows_corpus(a), Corpus(mem.rows_bytes(a)), deep=True)
    check_corpora(_rows_corpus(b), Corpus(mem.rows_bytes(b)), deep=True)


def test_blank_lines_and_empty_corpus():
    rows = make_rows(5, 4)
    d = mem.rows_bytes(rows)
    c = inc.corpus_of(d)
    c2 = inc.corpus_of(d + b"\n\n")
    assert c2.corpus_sha == hashlib.sha256(d + b"\n\n").hexdigest()
    check_corpora(c2, Corpus(d + b"\n\n"))
    check_corpora(inc.corpus_of(b""), Corpus(b""))
    assert c.space.N == 4


def test_lazy_shas_are_the_plain_values():
    rows = make_rows(13, 9)
    c = inc.corpus_of(mem.rows_bytes(rows[:8]))
    c = inc.corpus_of(mem.rows_bytes(rows))
    p = Corpus(mem.rows_bytes(rows))
    assert (c.space_sha, c.adhesion_sha, c.seats_sha) == (p.space_sha, p.adhesion_sha, p.seats_sha)


def test_the_plain_corpus_is_not_changed_by_importing_the_accelerator():
    assert type(Corpus(b"")) is Corpus
    assert "space_sha" in Corpus(b"").__dict__


# ------------------------------------------------------------------------------------------------------------
# rows as bytes, the state's JSON
# ------------------------------------------------------------------------------------------------------------
def test_rows_bytes_memo_equals_plain_with_every_optional_field():
    rows = make_rows(17, 6)
    rows[1]["topic_at"] = 3
    rows[2]["clause_at"] = 0
    rows[3]["turn"] = "1-2"
    rows[4]["unshaped"] = True
    rows[5]["weave_refused"] = "no_unit"
    rows[0]["kind"] = "memory_answer"
    del rows[5]["kind"]
    for _ in range(2):                                           # second call: from the memo
        assert inc.rows_bytes(rows, mem.row_line) == "".join(mem.row_line(r) for r in rows).encode("utf-8")
    rows[1]["topic_at"] = 4                                      # a changed field is a changed line
    assert inc.rows_bytes(rows, mem.row_line) == "".join(mem.row_line(r) for r in rows).encode("utf-8")
    with pytest.raises(KeyError):
        inc.rows_bytes([{"sent": "x"}], mem.row_line)


def _story(path, n, mode, monkeypatch):
    import perf
    monkeypatch.setenv("VERA_ACCEL", mode)
    inc.reset()
    st = mem.MemStore(os.path.join(path, "store"), "p")
    s, w, sess = None, 0, 0
    while w < n:
        if s is not None:
            s.commit()
        s = st.begin("t", profile=mem.PROFILE_V4)
        sess += 1
        s.call("declare_topic", {"text": "基盤整備%d" % sess})
        for _ in range(14):
            if w >= n:
                break
            s.call("write", {"text": perf.sentence(w)})
            w += 1
    s.call("recall", {"question": "決済画面1の期限はいつですか"})
    s.commit()
    return st.index().index_sha, tree(path)


def tree(root):
    out = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f in ("timing.jsonl", ".lock"):                   # wall-clock log, never hashed
                continue
            p = os.path.join(d, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def test_dispatch_py_is_the_plain_code(monkeypatch, tmp_path):
    monkeypatch.delenv("VERA_ACCEL", raising=False)
    assert accel.mode() == "py"
    rows = make_rows(19, 3)
    assert type(mem.build_corpus(rows)) is Corpus
    monkeypatch.setenv("VERA_ACCEL", "bogus")
    with pytest.raises(ValueError):
        accel.mode()


def test_stores_are_byte_identical_py_inc(monkeypatch, tmp_path):
    n = 30                                                       # one change clause (every 25th sentence) is in
    a = _story(str(tmp_path / "py"), n, "py", monkeypatch)
    b = _story(str(tmp_path / "inc"), n, "inc", monkeypatch)
    assert a == b


def test_stores_are_byte_identical_py_c_and_the_c_kernels_ran(monkeypatch, tmp_path, lib):
    n = 30
    calls = {"k": 0}
    real = cbind.CWeights.__call__

    def counting(self, x, y):
        calls["k"] += 1
        return real(self, x, y)

    monkeypatch.setattr(cbind.CWeights, "__call__", counting)
    a = _story(str(tmp_path / "py"), n, "py", monkeypatch)
    b = _story(str(tmp_path / "c"), n, "c", monkeypatch)
    assert a == b
    assert calls["k"] > 0                                        # the C path was not silently skipped


def test_check_mode_compares_every_corpus_and_state_sha(monkeypatch, tmp_path, lib):
    monkeypatch.setenv("VERA_ACCEL_CHECK", "1")
    a = _story(str(tmp_path / "py"), 18, "py", monkeypatch)
    b = _story(str(tmp_path / "c"), 18, "c", monkeypatch)        # raises AssertionError on the first corpus / state sha that differs
    assert a == b


def test_state_json_equals_plain_on_a_real_run_and_after_a_drop(monkeypatch, tmp_path):
    import perf
    monkeypatch.setenv("VERA_ACCEL", "py")
    st = mem.MemStore(str(tmp_path / "store"), "p")
    s = st.begin("t", profile=mem.PROFILE_V4)
    s.call("declare_topic", {"text": "基盤整備1"})
    for i in range(12):
        s.call("write", {"text": perf.sentence(i)})
        state = s.run.state
        assert inc.loom_json(state, canonical, LoomState) == canonical(state.to_obj())
    cross = next(iter(state.crosses.values()))
    state.drop_cross(cross)                                      # the 'made' counters differ from the registry sizes now
    assert inc.loom_json(state, canonical, LoomState) == canonical(state.to_obj())
    u = next(iter(state.units.values()))
    u.prov["history_n"] = 99
    assert inc.loom_json(state, canonical, LoomState) == canonical(state.to_obj())
    state.thread.append("c1")
    state.counters["ops"] += 1
    assert inc.loom_json(state, canonical, LoomState) == canonical(state.to_obj())


# ------------------------------------------------------------------------------------------------------------
# the C kernels against the Python methods
# ------------------------------------------------------------------------------------------------------------
def test_c_kernels_equal_tierspace_on_random_tiers(lib):
    rng = random.Random(23)
    words = ["w%d" % i for i in range(40)] + ["の", "は"]
    texts = [" ".join(rng.choice(words) for _ in range(rng.randint(1, 12))) for _ in range(80)]
    units = tuple(tuple(t.split()) for t in texts)
    post = {}
    for sid, us in enumerate(units):
        for u in dict.fromkeys(us):
            post.setdefault(u, []).append(sid)
    tier = sp.TierSpace("WORD", units, {u: tuple(v) for u, v in post.items()}, None)
    m = cbind.mirror_of(tier)
    L = cbind.lib()
    us = sorted(tier.postings)
    for _ in range(600):
        x, y = rng.choice(us), rng.choice(us)
        a, b = m.ids[x], m.ids[y]
        assert L.vx_n(m.h.p, a, 10**9) == tier.n(x)
        assert L.vx_n_pair(m.h.p, a, b, 10**9) == tier.n_pair(x, y)
        assert L.vx_p_pair(m.h.p, a, b, 10**9) == tier.p_pair(x, y)
    # the prefix semantics: `limit` = the corpus of the first sentences
    for lim in (0, 1, 17, 79, 80):
        pre = sp.TierSpace("WORD", units[:lim], {u: tuple(s for s in v if s < lim) for u, v in post.items() if any(s < lim for s in v)}, None)
        for _ in range(100):
            x, y = rng.choice(us), rng.choice(us)
            if x in pre.postings and y in pre.postings:
                a, b = m.ids[x], m.ids[y]
                assert (L.vx_n_pair(m.h.p, a, b, lim), L.vx_p_pair(m.h.p, a, b, lim)) == (pre.n_pair(x, y), pre.p_pair(x, y))
    assert L.vx_n(m.h.p, 10**6, 80) == 0                          # an id the tier never saw


def test_c_mirror_chain_clone_on_sibling(lib):
    rows = make_rows(29, 20)
    p = [Corpus(mem.rows_bytes(rows[:t])) for t in range(1, 21)]
    m = cbind.mirror_of(p[9].tier("WORD"))
    a = cbind.mirror_append(m, p[10].tier("WORD"), 10)            # in place
    sib = rows[:10] + [dict(rows[10], sent="認証の担当は鈴木。")]
    ps = Corpus(mem.rows_bytes(sib))
    b = cbind.mirror_append(m, ps.tier("WORD"), 10)               # the slot is taken: a clone
    assert a.h is m.h and b.h is not m.h
    L = cbind.lib()
    for mir, corp in ((m, p[9]), (a, p[10]), (b, ps)):
        t = corp.tier("WORD")
        us = sorted(t.postings)
        for x in us[:15]:
            for y in us[:15]:
                assert (L.vx_n_pair(mir.h.p, mir.ids[x], mir.ids[y], corp.space.N), L.vx_p_pair(mir.h.p, mir.ids[x], mir.ids[y], corp.space.N)) == (t.n_pair(x, y), t.p_pair(x, y))


def test_a_missing_library_is_a_loud_error_not_a_fallback(monkeypatch):
    monkeypatch.setenv("VERA_ACCEL_LIB", "/nonexistent/libvxcore.so")
    monkeypatch.setattr(cbind, "_LIB", None)
    with pytest.raises(cbind.AccelUnavailable):
        cbind.lib()


def test_build_is_idempotent_and_named_by_source_sha(lib):
    assert build.ensure() == lib and os.path.basename(lib).startswith("libvxcore-")
    assert hashlib.sha256(open(build.SOURCE, "rb").read()).hexdigest()[:12] in lib


# ------------------------------------------------------------------------------------------------------------
# the rules: nothing but the build module starts a process; the loom imports the accelerator only through the hook
# ------------------------------------------------------------------------------------------------------------
def _imports(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


def test_only_build_py_starts_a_process_and_no_module_reads_a_clock_or_the_net():
    d = os.path.join(ROOT, "verantyx", "accel")
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".py"):
            continue
        names = _imports(os.path.join(d, fn))
        assert not (names & {"socket", "ssl", "urllib", "http", "requests", "time", "datetime"}), fn
        if fn != "build.py":
            assert "subprocess" not in names, fn


def test_the_loom_package_does_not_import_ctypes_or_the_build_module():
    loom = os.path.join(ROOT, "verantyx", "loom")
    for fn in sorted(os.listdir(loom)):
        if fn.endswith(".py"):
            src = open(os.path.join(loom, fn), encoding="utf-8").read()
            assert "ctypes" not in _imports(os.path.join(loom, fn)), fn
            assert "accel.build" not in src and "accel import build" not in src, fn
