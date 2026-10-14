"""Suite-wide setup: the Japanese tokenizer is required by every test (core dependency); stop early with a clear message when it is missing."""
import pytest


def pytest_sessionstart(session):
    try:
        import fugashi  # noqa: F401
        import unidic_lite  # noqa: F401
    except ImportError as e:  # pragma: no cover
        pytest.exit("fugashi and unidic-lite are required (pip install -e .): %s" % e, returncode=4)


@pytest.fixture
def gate_v2(monkeypatch):
    """The gate of NEW answer runs and of the sessions the doors open (`mem.LATEST`) is evidence.v6 (`memrecall.MEM_GATE_VERSION`).  A test that pins the `evidence_profile` of a new
    answer run to evidence.v2 uses this fixture, which sets that one constant back to evidence.v2 for the test; v2 stays selectable and replayable.  The meaning of `mem.DEFAULT` (the API
    default of `begin` / `verify_store`) is frozen at gate.evidence.v2+subject and needs no fixture.  The new default is asserted in tests/core/test_pub_m6c.py."""
    from verantyx.loom import evidence as _ev
    from verantyx.loom import memanswer as _ma
    from verantyx.loom import memrecall as _mr
    monkeypatch.setattr(_mr, "MEM_GATE_VERSION", _ev.EVIDENCE_V2)
    monkeypatch.setattr(_ma, "ANSWER_EVIDENCE", (_ev.EVIDENCE_V2, _ev.SCOPE_CLAUSE))


RECORDED_PYTHON = (3, 11, 14)


def pytest_collection_modifyitems(config, items):
    """Golden digests (names starting with GOLDEN) are bytes of ledgers, and every ledger header records the Python it was made under: on any other Python they cannot match.
    CI pins 3.11.14, where they are asserted."""
    import sys
    if tuple(sys.version_info[:3]) == RECORDED_PYTHON:
        return
    skip = pytest.mark.skip(reason="golden ledger bytes record Python %d.%d.%d; this is %d.%d.%d (CI pins %d.%d.%d)" % (RECORDED_PYTHON + tuple(sys.version_info[:3]) + RECORDED_PYTHON))
    for item in items:
        fn = getattr(item, "function", None)
        names = getattr(getattr(fn, "__code__", None), "co_names", ())
        if any(n.startswith("GOLDEN") for n in names):
            item.add_marker(skip)
