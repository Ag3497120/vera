"""Make the bundled `verantyx` importable for the tests without PYTHONPATH (same as PYTHONPATH=vera_base)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vera_base"))
