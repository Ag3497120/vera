"""v2 バンクの実際の形式に合わせた検証・採点（docs/BANK_SCORE.md §12）。既定の profile（w1s）は W1-s のまま。"""
from __future__ import annotations

from pathlib import Path


def validate(bank: str, raw: dict, errs: list[str], frames_dir: Path | None) -> dict | None:
    """バンク別の v2 検証。誤りの型を errs に足し、採点用の case（W1-s と同じ形）を返す。"""
    if bank == "B1":
        from . import b1
        return b1.validate_item(raw, errs)
    if bank == "B2":
        from . import b2
        return b2.validate_item(raw, errs)
    if bank == "B3":
        from . import b3
        return b3.validate_item(raw, errs)
    from . import b5
    return b5.validate_item(raw, errs, frames_dir)
