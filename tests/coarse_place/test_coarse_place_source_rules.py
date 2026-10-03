"""Source-level rules for W3-a: no sense labels from the dictionary, no models,
no network, and no test word hard-coded in the source."""
import json
import re
from pathlib import Path

from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / "tests/coarse_place/data"
NEW_FILES = ["verantyx/coarse_types.py", "verantyx/coarse_place.py",
             "tools/build_coarse_placement.py", "tools/gen_coarse_evidence.py"]
FORBIDDEN_IMPORTS = ["torch", "sklearn", "gensim", "transformers", "openai",
                     "anthropic", "requests", "urllib.request", "socket"]


def src(rel):
    return (TREE / rel).read_text(encoding="utf-8")


def test_no_semantic_dictionary_labels_in_the_new_sources():
    for rel in NEW_FILES:
        text = src(rel)
        # the strings are named in the ticket as the labels NOT to use; the
        # check itself spells them in pieces so it does not trip on itself
        for needle in ("pos" + "3", "pos" + "4", "人" + "名", "地" + "名"):
            assert needle not in text, (rel, needle)


def test_no_model_or_network_imports():
    files = NEW_FILES + ["artifacts/w3-a/measure_w3a.py"]
    for rel in files:
        text = src(rel)
        for mod in FORBIDDEN_IMPORTS:
            pat = r"^\s*(import|from)\s+%s(\s|$|\.)" % re.escape(mod)
            assert not re.search(pat, text, re.M), (rel, mod)


def _exempt_stop_words():
    """Words the review allowed in the source although a test word is spelled
    the same: STOP WORDS only (they give no type), each named with its place."""
    rows = json.loads((TREE / "artifacts/w3-a/source_word_exemptions.json")
                      .read_text(encoding="utf-8"))
    out = {}
    for r in rows:
        assert r["placement"] in ("GENERIC_HEADS", "META_HEADS"), r
        assert r["reason"].strip(), r
        out[r["word"]] = r["placement"]
    return out


def test_test_words_are_not_hard_coded_in_the_sources():
    fz = json.loads((TREE / "artifacts/w3-a/FROZEN.json").read_text(encoding="utf-8"))
    allowed = set(fz["seed_overlap_terms"])
    seeds = {w for ws in ct.SEEDS_NOUN.values() for w in ws}
    seeds |= {w for ws in ct.SEEDS_PRED.values() for w in ws}
    terms = set()
    for name in ("typed_vocab", "unknown_words", "dev_vocab", "dev_unknown", "predicate_check"):
        for line in (DATA / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            terms.add(json.loads(line)["term"])
    exempt = _exempt_stop_words()
    terms = {t for t in terms if len(t) >= 2} - allowed - seeds - set(exempt)
    for rel in NEW_FILES:
        text = src(rel)
        # the ticket's own trap words appear in coarse_types.py only in a
        # docstring-free test list; the sources must not quote any test word
        for t in sorted(terms):
            assert ('"%s"' % t) not in text and ("'%s'" % t) not in text, (rel, t)


def test_the_unknown_words_are_never_a_seed():
    seeds = {w for ws in ct.SEEDS_NOUN.values() for w in ws}
    for name in ("unknown_words", "dev_unknown"):
        for line in (DATA / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            assert json.loads(line)["term"] not in seeds


def test_exempt_words_are_stop_words_only_and_appear_nowhere_else():
    """An exempt word may be spelled in the source only inside the stop-word tuple
    it is exempted for -- never as a seed, a notation rule or anywhere else."""
    exempt = _exempt_stop_words()
    seeds = {w for ws in ct.SEEDS_NOUN.values() for w in ws}
    seeds |= {w for ws in ct.SEEDS_PRED.values() for w in ws}
    for w, place in exempt.items():
        assert w in getattr(ct, place), (w, place)
        assert w not in seeds
        for rel in NEW_FILES:
            text = src(rel)
            for m in re.finditer(r"""["']%s["']""" % re.escape(w), text):
                head = text[:m.start()]
                # the nearest assignment above the occurrence must be the named tuple
                last = max(head.rfind("\n%s:" % place), head.rfind("\n%s =" % place))
                other = max(head.rfind("\nSEEDS_"), head.rfind("\nPRED_FRAME_RULES"),
                            head.rfind("\ndef "), head.rfind("\nDEFAULT_CONFIG"),
                            head.rfind("\n_RE_"), head.rfind("\nTIME_UNITS"))
                assert rel == "verantyx/coarse_types.py" and last > other, (rel, w)
