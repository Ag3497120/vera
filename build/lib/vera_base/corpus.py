"""The Codex sentence corpus, fetched from the GitHub release on first use (not in the pip package)."""
from __future__ import annotations

import gzip
import json
import os
import urllib.request
from pathlib import Path
from typing import Iterator

URL = os.environ.get("VERA_CORPUS_URL", "https://github.com/{owner}/{repo}/releases/download/v0.1.0/codex_sentences_ja.jsonl.gz")
CACHE = Path(os.environ.get("VERA_HOME", Path.home() / ".cache" / "vera")) / "codex_sentences_ja.jsonl.gz"


def fetch(url: str = URL) -> Path:
    """Download once (about 50 MB) into ~/.cache/vera and return the path."""
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(CACHE)
    return CACHE


def sentences() -> Iterator[dict]:
    with gzip.open(fetch(), "rt", encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)
