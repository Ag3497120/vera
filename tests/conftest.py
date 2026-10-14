"""Suite-wide setup: the Japanese tokenizer is required by every test (core dependency); stop early with a clear message when it is missing."""
import pytest


def pytest_sessionstart(session):
    try:
        import fugashi  # noqa: F401
        import unidic_lite  # noqa: F401
    except ImportError as e:  # pragma: no cover
        pytest.exit("fugashi and unidic-lite are required (pip install -e .): %s" % e, returncode=4)
