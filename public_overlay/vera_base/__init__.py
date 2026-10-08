"""Vera base for Japanese: rules + stereo-cross routing over predicate-argument records. No weights."""
import os, sys
from pathlib import Path
_here = Path(__file__).resolve().parent
os.environ.setdefault("VERA_GENERAL", str(_here / "data" / "general.db"))   # absent in the package: pack-only mode
os.environ.setdefault("VERA_PACK", str(_here / "data" / "chat_pack.json"))
os.environ.setdefault("VERA_PUN_LEXICON", str(_here / "data" / "pun_lexicon.json"))
sys.path.insert(0, str(_here))
import importlib.util as _ilu          # noqa: E402
OPTIONAL_DEPENDENCIES = ("fugashi", "unidic_lite")


def dependency_status():
    """{name: "AVAILABLE" | "MISSING"} for the optional Japanese parser stack."""
    return {n: ("AVAILABLE" if _ilu.find_spec(n) is not None else "MISSING") for n in OPTIONAL_DEPENDENCIES}


from verantyx.chat import Chat as _Chat   # noqa: E402
if "MISSING" not in dependency_status().values():
    Chat = _Chat          # identical object: no behaviour change where the dependencies exist
else:
    class Chat(_Chat):    # only where a parser dependency is absent
        def __init__(self, *args, **kwargs):
            self._missing = None
            try:
                super().__init__(*args, **kwargs)
            except ModuleNotFoundError as exc:
                if exc.name not in OPTIONAL_DEPENDENCIES:
                    raise
                self._missing = exc.name

        def reply(self, *args, **kwargs):
            missing = self._missing
            if missing is None:
                try:
                    return super().reply(*args, **kwargs)
                except ModuleNotFoundError as exc:
                    if exc.name not in OPTIONAL_DEPENDENCIES:
                        raise
                    missing = exc.name
            return {"kind": "UNKNOWN_NO_PARSER", "missing": missing,
                    "text": f"{missing} が入っていないため、日本語を読めません。（python3 -m pip install fugashi unidic-lite）",
                    "install": "python3 -m pip install fugashi unidic-lite",
                    "sources": [], "evidence": []}
from verantyx.base import Base          # noqa: E402,F401
from verantyx.verdict import judge, read_records   # noqa: E402,F401
from verantyx.bot import Bot            # noqa: E402,F401
from verantyx.crossverify import verify as crossverify   # noqa: E402,F401  (English claims vs Japanese docs, with a glossary)
from verantyx.cascade import verify as two_stage         # noqa: E402,F401  (optional local LLM for undecided claims)
