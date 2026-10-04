"""T4 (the machine's part): none of the names of the self-made data appears in verantyx/routing_from_text.py, and which words of the
explanations do appear in it (a list only; a word that is an entry of a constant table points to that table and its reason in
docs/ROUTING_FROM_TEXT.md).

    python tests/routing_from_text/check_no_text_words.py        # exit 1 when ``failures`` is not empty
"""
import json
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "tests", "routing_from_text", "data")


def norm(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


def padded(text):
    """The text with every non-letter, non-digit replaced by a blank, for whole-word matching of ASCII words."""
    return " " + "".join(ch if ch.isalnum() else " " for ch in text) + " "


def appears(word, source, spaced):
    """A Latin word is looked for as a whole word ('sol' is not found in 'resolve'); a Japanese string as a substring."""
    return (" " + " ".join(word.split()) + " ") in spaced if all(ord(ch) < 128 for ch in word) else word in source


def main():
    from verantyx import routing_from_text as rt
    from verantyx.typed_edges import _tagger
    with open(os.path.join(ROOT, "verantyx", "routing_from_text.py"), encoding="utf-8") as handle:
        source = norm(handle.read())
    spaced = padded(source)
    items = []
    for name in ("items.jsonl", "items_reader_shaped.jsonl", "items_mid.jsonl", "items_mid_reader_shaped.jsonl"):
        items += [json.loads(line) for line in open(os.path.join(DATA, name), encoding="utf-8") if line.strip()]
    names = set()
    for item in items:
        names.update(item["expect"]["wrong_agents"])
        if item["expect"]["agent"]:
            names.add(item["expect"]["agent"])
        for value in item["task"]["already_used"].values():
            names.update([value] if isinstance(value, str) else value)
        names.update(item["task"]["running"])
    failures = sorted(n for n in names if appears(norm(n), source, spaced))
    entries = {}
    for constant in rt.CONSTANT_NAMES:
        value = getattr(rt, constant)
        pieces = []
        if isinstance(value, dict):
            for key, val in value.items():
                pieces.append(key[1] if isinstance(key, tuple) else key)
                if isinstance(val, frozenset):
                    pieces.extend(val)
        else:
            pieces.extend(value)
        for piece in pieces:
            entries.setdefault(norm(str(piece)), constant)
    words = {}
    for directory in ("explanations", "explanations_reader_shaped"):
        for name in sorted(os.listdir(os.path.join(DATA, directory))):
            if not name.endswith(".md"):
                continue
            text = open(os.path.join(DATA, directory, name), encoding="utf-8").read()
            for token in _tagger()(text):
                if token.feature.pos1 in ("名詞", "動詞"):
                    lemma = getattr(token.feature, "orthBase", None) or token.surface
                    if len(lemma) >= 2:
                        words.setdefault(norm(lemma), set()).add(name)
            for word in text.replace("\n", " ").split():
                word = "".join(ch for ch in word if ch.isalpha() and ord(ch) < 128)
                if len(word) >= 3:
                    words.setdefault(norm(word), set()).add(name)
    appearing = {}
    for word in sorted(words):
        if appears(word, source, spaced):
            appearing[word] = entries.get(word, "(not an entry of a constant table: part of the module's own prose or code)")
    report = {"failures": failures, "names_checked": sorted(names), "explanation_words_in_the_module": appearing}
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
