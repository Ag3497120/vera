"""W3-a3: the source rules of W3-a, applied again with the new verb test data (dev_verbs, verb_check_300):
no test word is quoted in the product sources, no model or network import, no dictionary sense
labels, and the verb data are not read by the code that makes the generation list."""
import json
import re
from pathlib import Path

from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / "tests/coarse_place/data"
PRODUCT = ["verantyx/coarse_types.py", "verantyx/coarse_place.py",
           "tools/build_coarse_placement.py", "tools/gen_coarse_evidence.py"]
FORBIDDEN_IMPORTS = ["torch", "sklearn", "gensim", "transformers", "openai",
                     "anthropic", "requests", "urllib.request", "socket"]
VERB_DATA = ("dev_verbs", "verb_check_300")


def src(rel):
    return (TREE / rel).read_text(encoding="utf-8")


def verb_terms():
    out = set()
    for name in VERB_DATA:
        for line in (DATA / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            out.add(json.loads(line)["term"])
    return out


#: Two spellings of the copula "ある" that a verb test word happens to share.  They are quoted in the OLD
#: ``hypernym_phrases`` (strip a trailing copula before a noun phrase: grammar, no type is decided by it),
#: not in anything this ticket wrote.  Each is allowed only inside that function.
COPULA_SPELLINGS = {"あり": "tools/build_coarse_placement.py", "在る": "tools/build_coarse_placement.py"}


def test_no_verb_test_word_is_quoted_in_the_product_sources():
    seeds = {w for ws in ct.SEEDS_NOUN.values() for w in ws} | {w for ws in ct.SEEDS_PRED.values() for w in ws}
    terms = {t for t in verb_terms() if len(t) >= 2} - seeds
    assert len(terms) > 300
    for rel in PRODUCT:
        text = src(rel)
        for t in sorted(terms):
            quoted = ('"%s"' % t) in text or ("'%s'" % t) in text or ("「%s」" % t) in text
            if t in COPULA_SPELLINGS and rel == COPULA_SPELLINGS[t]:
                i = text.index("def hypernym_phrases(")
                inside = text[i:text.index("\ndef ", i + 1)]
                assert text.count('"%s"' % t) == inside.count('"%s"' % t) >= 1, (rel, t)   # only there
                continue
            assert not quoted, (rel, t)


def test_the_verb_data_never_overlap_a_seed_and_the_coined_terms_are_in_the_exclude_file():
    seeds = {w for ws in ct.SEEDS_PRED.values() for w in ws}
    assert not (verb_terms() & seeds)
    coined = set()
    for name in VERB_DATA:
        for line in (DATA / (name + ".jsonl")).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r["kind"] == "unknown_coined":
                coined.add(r["term"])
    excl = {json.loads(l)["term"] for l in (TREE / "artifacts/w3-a3/exclude_coined.jsonl")
            .read_text(encoding="utf-8").splitlines() if l.strip()}
    assert coined == excl and len(coined) == 60


def test_no_model_or_network_imports_and_no_dictionary_sense_labels():
    for rel in PRODUCT + ["artifacts/w3-a3/measure_w3a3.py"]:
        text = src(rel)
        for mod in FORBIDDEN_IMPORTS:
            pat = r"^\s*(import|from)\s+%s(\s|$|\.)" % re.escape(mod)
            assert not re.search(pat, text, re.M), (rel, mod)
    for rel in PRODUCT:
        for needle in ("pos" + "3", "pos" + "4", "人" + "名", "地" + "名"):
            assert needle not in src(rel), (rel, needle)


def test_the_list_of_verbs_to_generate_is_made_without_the_test_data():
    text = src("tools/gen_coarse_evidence.py")
    assert "tests/coarse_place/data" not in text and "dev_verbs" not in text and "verb_check" not in text
    import inspect
    from tools import gen_coarse_evidence as gce
    assert list(inspect.signature(gce.select_needs_pred).parameters) == ["placement", "n", "stage_cache"]


def test_the_k62_copy_holds_type_ids_and_particles_only_and_the_code_has_no_verb_list():
    for _t, _r, p, ts, _k in ct.K62_FRAMES:
        assert p in ct.CASE_PARTICLES_9 and all(x in ct.NOUN_TYPES for x in ts)
    # the new code names predicate TYPES (ids), never a list of verbs: no run of three or more quoted
    # words ending in a verb-like る/う/く in the pieces this ticket added
    for rel in ("tools/build_coarse_placement.py", "verantyx/coarse_place.py"):
        text = src(rel)
        i = text.find("def _chain_count")
        j = text.find("def _hearst_scan")
        block = text[i:j] + text[text.find("def _stage2"):text.find("def _resolve_stage")]
        assert not re.search(r'["\'][ぁ-んァ-ヶ一-龥]{2,}["\']\s*,\s*["\'][ぁ-んァ-ヶ一-龥]{2,}["\']', block), rel
