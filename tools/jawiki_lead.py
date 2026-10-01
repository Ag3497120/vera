# -*- coding: utf-8 -*-
"""jawiki 本文ダンプ → 記事のリード段落(定義的本文)だけを取り出す。

事前登録: experiments/mass_defs_ingest/PREREG2_WIKT_JAWIKI.md
閉じた規則のみ。テンプレート・表・ref・ファイル埋め込みは落とし、
[[リンク|表示]] は表示側を残す。最初の見出し(==)までがリード。
"""
from __future__ import annotations

import bz2
import html
import re
from pathlib import Path
from typing import Iterator, Tuple

_TMPL = re.compile(r"\{\{[^{}]*\}\}")
_TABLE = re.compile(r"\{\|.*?\|\}", re.S)
_REF = re.compile(r"<ref[^>]*?/>|<ref[^>]*>.*?</ref>", re.S | re.I)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")
_FILE = re.compile(r"\[\[(?:ファイル|File|Image|画像):[^\[\]]*(?:\[\[[^\[\]]*\]\][^\[\]]*)*\]\]")
_LINK = re.compile(r"\[\[([^\[\]|]+)\|([^\[\]]+)\]\]")
_LINK2 = re.compile(r"\[\[([^\[\]|]+)\]\]")
_EXT = re.compile(r"\[https?://[^\]]*\]")
_QUOTE = re.compile(r"'{2,5}")
_HEAD = re.compile(r"^\s*={2,}", re.M)
_BLANKS = re.compile(r"\n{2,}")


def strip_wikitext(t: str) -> str:
    # 実体参照を先に戻す。XML の中では <ref> が &lt;ref&gt; として現れる
    # ので、戻す前に剥がすと ref がまるごと本文に残る(実測)。
    t = html.unescape(html.unescape(t))
    t = _COMMENT.sub("", t)
    t = _REF.sub("", t)
    t = _TABLE.sub("", t)
    for _ in range(4):          # ネストしたテンプレートを内側から
        t2 = _TMPL.sub("", t)
        if t2 == t:
            break
        t = t2
    t = _FILE.sub("", t)
    t = _EXT.sub("", t)
    t = _LINK.sub(r"\2", t)
    t = _LINK2.sub(r"\1", t)
    t = _TAG.sub("", t)
    t = _QUOTE.sub("", t)
    t = re.sub(r"^[*#:;].*$", "", t, flags=re.M)   # 箇条書きはリードでは注記
    return _BLANKS.sub("\n", t).strip()


def leads(path: Path, *, max_chars: int = 600) -> Iterator[Tuple[str, str]]:
    """(題名, リード本文) — 本文名前空間・非リダイレクトのみ。"""
    title = None
    in_text = False
    buf: list = []
    with bz2.open(path, "rt", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "<title>" in line:
                m = re.search(r"<title>([^<]*)</title>", line)
                title = m.group(1) if m else None
                continue
            if title is None or ":" in title:
                continue
            if "<text" in line:
                in_text = True
                buf = [line.split(">", 1)[1] if ">" in line else ""]
                if "</text>" in line:
                    in_text = False
                    body = buf[0].split("</text>")[0]
                    out = _emit(title, body, max_chars)
                    if out:
                        yield out
                continue
            if in_text:
                if "</text>" in line:
                    in_text = False
                    buf.append(line.split("</text>")[0])
                    out = _emit(title, "".join(buf), max_chars)
                    if out:
                        yield out
                    buf = []
                else:
                    buf.append(line)
                    if len(buf) > 400:      # リードだけ要る — 長い記事は打ち切る
                        in_text = False
                        out = _emit(title, "".join(buf), max_chars)
                        if out:
                            yield out
                        buf = []


def _emit(title: str, body: str, max_chars: int):
    if body.lstrip().startswith(("#REDIRECT", "#転送", "#redirect")):
        return None
    lead = _HEAD.split(body, 1)[0]
    text = strip_wikitext(lead)
    if len(text) < 40:
        return None
    return title, text[:max_chars]
