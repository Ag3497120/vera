"""コードとキーのパスだけを通す小さな道具（問題の中身が出力に混ざらないようにする。v2 の要約と publish が共有する）。"""
from __future__ import annotations

import re

CODE_RE = re.compile(r"^[A-Z][A-Z_0-9]*(\[\d+\])?(:[A-Za-z0-9_.\[\]*]+)?$")
HEAD_RE = re.compile(r"^[A-Z][A-Z_0-9]*")
KEYPATH_RE = re.compile(r"^[A-Za-z0-9_.\[\]<>*:]+$")


def clean_code(s: object) -> str:
    """ASCII のコードとキーのパスだけを通す。合わないものは `<コード>:<redacted>`。"""
    if isinstance(s, str) and CODE_RE.match(s):
        return s
    m = HEAD_RE.match(s) if isinstance(s, str) else None
    return f"{m.group(0)}:<redacted>" if m else "<redacted>"


def clean_key(s: object) -> str:
    return s if isinstance(s, str) and KEYPATH_RE.match(s) else "<non-ascii>"
