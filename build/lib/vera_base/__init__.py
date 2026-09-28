"""Vera base for Japanese: rules + stereo-cross routing over predicate-argument records. No weights."""
import os, sys
from pathlib import Path
_here = Path(__file__).resolve().parent
os.environ.setdefault("VERA_GENERAL", str(_here / "data" / "general.db"))   # absent in the package: pack-only mode
os.environ.setdefault("VERA_PACK", str(_here / "data" / "chat_pack.json"))
os.environ.setdefault("VERA_PUN_LEXICON", str(_here / "data" / "pun_lexicon.json"))
sys.path.insert(0, str(_here))
from verantyx.chat import Chat          # noqa: E402,F401
from verantyx.base import Base          # noqa: E402,F401
from verantyx.verdict import judge, read_records   # noqa: E402,F401
from verantyx.bot import Bot            # noqa: E402,F401
from verantyx.crossverify import verify as crossverify   # noqa: E402,F401  (English claims vs Japanese docs, with a glossary)
from verantyx.cascade import verify as two_stage         # noqa: E402,F401  (optional local LLM for undecided claims)
