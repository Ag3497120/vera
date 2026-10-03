"""Which entries of the constant tables of verantyx/routing_from_text.py are words or phrases of the self-made explanations?

The tables were frozen before the tasks were written and before the entry was run on the data, but the implementer had read the text of
e1-e6 before writing them (docs/ROUTING_FROM_TEXT.md, chapter 7).  This lists, for e1-e6 and for r1-r2 separately, every entry that occurs in
the text: a Japanese entry as a substring of the NFKC text or as the dictionary form of one of its morphemes (動かさない has 動かす), an
English entry as a whole word or phrase, with the regular endings -s -es -ed -ing -ies (so that 'a' is not found in every word).  The tables of form (sentence ends, closers, list markers, markup characters) and the part-of-speech names are not words of a
topic and are left out.  Output: JSON on stdout (artifacts/w2-h2/constants_in_data.json).

    python tests/routing_from_text/constants_in_data.py
"""
import json
import os
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import verantyx.routing_from_text as m  # noqa: E402

DATA = os.path.join(ROOT, "tests", "routing_from_text", "data")
SETS = {"e1-e6": ("explanations", ["e1", "e2", "e3", "e4", "e5", "e6"]), "r1-r2": ("explanations_reader_shaped", ["r1", "r2"])}
LEFT_OUT = {"SENTENCE_ENDS", "CLOSERS", "LIST_MARKERS", "MARKUP_CHARS", "NON_NAME_POS"}


def norm(text):
    return unicodedata.normalize("NFKC", text).casefold()


def words_of(text):
    out, current = [], []
    for ch in text:
        if ch.isalnum():
            current.append(ch)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def entries(name):
    """-> [(lang, term)] of one table."""
    table = getattr(m, name)
    if isinstance(table, dict):
        found = []
        for key, value in table.items():
            if isinstance(key, tuple):
                found.append((key[0], key[1]))
            else:                     # {lang: frozenset of terms}
                found.extend((key, term) for term in value)
        return found
    return [("ja" if any(ord(ch) > 0x2E80 for ch in term) else "en", term) for term in table]


def lemmas_of(text):
    from verantyx.typed_edges import _tagger
    found = set()
    for word in _tagger()(unicodedata.normalize("NFKC", text)):
        for form in (word.surface, getattr(word.feature, "lemma", None), getattr(word.feature, "orthBase", None)):
            if form:
                found.add(norm(form))
    return found


def endings(word):
    forms = {word, word + "s", word + "es", word + "ed", word + "ing"}
    if word.endswith("e"):
        forms |= {word + "d", word[:-1] + "ing"}
    if word.endswith("y"):
        forms.add(word[:-1] + "ies")
    return forms


def occurs(lang, term, text, words, lemmas):
    key = norm(term)
    if lang == "ja":
        return key in text or key in lemmas
    parts = words_of(key)
    if not parts:
        return False
    last = parts[-1]
    return any(words[i:i + len(parts) - 1] == parts[:-1] and words[i + len(parts) - 1] in endings(last)
               for i in range(len(words) - len(parts) + 1))


def main():
    result = {}
    for label, (directory, ids) in SETS.items():
        text = "\n".join(open(os.path.join(DATA, directory, i + ".md"), encoding="utf-8").read() for i in ids)
        text = norm(text)
        words = words_of(text)
        lemmas = lemmas_of(text)
        per_table = {}
        for name in m.CONSTANT_NAMES:
            if name in LEFT_OUT:
                continue
            hits = sorted({f"{lang}:{term}" for lang, term in entries(name) if occurs(lang, term, text, words, lemmas)})
            if hits:
                per_table[name] = hits
        result[label] = per_table
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
