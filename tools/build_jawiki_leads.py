"""Stream namespace-zero Wikipedia leads and redirects into a separate sovereign."""
from __future__ import annotations

import argparse
import bz2
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def plain(text: str) -> str:
    text = re.sub(r"<!--.*?-->|<ref\b[^>]*>.*?</ref>|<ref\b[^>]*/>", "", text, flags=re.S | re.I)
    for _ in range(30):
        changed = re.sub(r"\{\{[^{}]*\}\}", "", text, flags=re.S)
        if changed == text:
            break
        text = changed
    text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.S)
    text = re.sub(r"\[\[(?:ファイル|画像|File|Image|Category|カテゴリ):[^\]]*\]\]", "", text, flags=re.I)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"<[^>]+>|'{2,5}", "", text)
    return html.unescape(text).strip()


def first_paragraph(text: str) -> str:
    cleaned = plain(text)
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith(("=", "#", "*", "|", "!", "{{", "}}")):
            if lines:
                break
            continue
        lines.append(stripped)
    return " ".join(lines)


def build(source: Path, output: Path, *, limit: int | None = None) -> dict:
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    articles, redirects = 0, 0
    opener = bz2.open if source.suffix == ".bz2" else open
    try:
        with opener(source, "rb") as stream, temporary.open("w", encoding="utf-8") as target:
            iterator = ET.iterparse(stream, events=("start", "end"))
            _, root = next(iterator)
            for event, element in iterator:
                if event != "end" or element.tag.rsplit("}", 1)[-1] != "page":
                    continue
                namespace = element.tag[:-4]
                title = element.findtext(namespace + "title") or ""
                if element.findtext(namespace + "ns") != "0":
                    root.clear()
                    continue
                redirect = element.find(namespace + "redirect")
                if redirect is not None:
                    row = {"title": title, "redirect": redirect.get("title"), "split": "train"}
                    redirects += 1
                else:
                    content = element.findtext(namespace + "revision/" + namespace + "text") or ""
                    lead = first_paragraph(content)
                    if not lead:
                        root.clear()
                        continue
                    page_id = element.findtext(namespace + "id") or title
                    row = {"title": title, "text": lead, "source": "jawiki:page:" + page_id,
                           "sha": hashlib.sha256((title + "\n" + lead).encode()).hexdigest(), "split": "train"}
                    articles += 1
                target.write(json.dumps(row, ensure_ascii=False) + "\n")
                root.clear()
                if limit is not None and articles >= limit:
                    break
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"articles": articles, "redirects": redirects, "partial": limit is not None,
            "source_bytes": source.stat().st_size, "output": str(output)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path.home() / "Projects/vera-corpus/raw/jawiki-latest-pages-articles.xml.bz2")
    parser.add_argument("--out", type=Path, default=Path.home() / "Projects/vera-corpus/build/round4/jawiki_leads.jsonl")
    parser.add_argument("--limit", type=int, help="explicit partial development build, never a full-corpus claim")
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.out, limit=args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
