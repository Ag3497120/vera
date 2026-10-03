"""Hypernym extraction, hypernym pairs from text, and the chain (W3-a)."""
import json
from collections import Counter

import fugashi
import pytest

from tools import build_coarse_placement as bcp
from verantyx import coarse_types as ct

TAGGER = fugashi.Tagger()


def hyp(sentence):
    return bcp.hypernym_phrases(TAGGER, bcp.first_sentence(sentence))


def test_first_sentence_ignores_a_full_stop_inside_brackets():
    s = "甲（こうとも、1886年（明治19年）12月6日。- ）は、日本の作家。次の文。"
    assert bcp.first_sentence(s) == "甲（こうとも、1886年（明治19年）12月6日。- ）は、日本の作家。"
    assert bcp.first_sentence("括弧なし") == "括弧なし"
    assert bcp.strip_parens("AB（cd（e）f）G(x)H") == "ABGH"


@pytest.mark.parametrize("sent,expect", [
    ("土手（どて）は、川に沿って築かれた場所。", ["場所"]),
    ("歌い手は、歌を歌う人のこと。", ["人"]),
    ("石土手は、石を積んだ場所の一種である。", ["場所"]),
    ("長谷川裕一（はせがわ ゆういち、1961年 - ）は、日本の漫画家・同人作家・特撮評論家。",
     ["特撮評論家", "同人作家", "漫画家"]),
    ("『史記』（しき）は、中国前漢の武帝の時代に司馬遷によって編纂された歴史書である。", ["歴史書"]),
])
def test_hypernym_phrases(sent, expect):
    ys, why = hyp(sent)
    assert why == "" and ys == expect


def test_a_verb_ending_gives_no_phrase_with_a_typed_reason():
    ys, why = hyp("太郎は昨日、東京へ行った。")
    assert ys == [] and why.startswith("ends_")


def test_first_clause_fallback():
    sent = "筋肉痛は、筋肉に生じる痛みであり、その原因はさまざまである。"
    assert hyp(sent)[0] == []
    assert bcp.first_clause_phrases(TAGGER, sent) == ["痛み"]
    assert bcp.first_clause_phrases(TAGGER, "犬が走った。") == []        # no topic marker


def test_hearst_pairs():
    h = Counter()
    for s in ["犬や猫などの動物を飼う。", "信念や理想といった概念を学ぶ。"]:
        bcp._hearst_scan(bcp.tokenize(TAGGER, s), h, 12)
    assert h[("犬", "動物")] == 1 and h[("猫", "動物")] == 1
    assert h[("信念", "概念")] == 1 and h[("理想", "概念")] == 1
    h2 = Counter()
    bcp._hearst_scan(bcp.tokenize(TAGGER, "彼などの人がいる。"), h2, 12)
    assert ("彼", "人") not in h2               # a pronoun is not a content noun run


def test_chain_types_a_hypernym_of_a_hypernym():
    seeds = {"人": "PERSON"}
    defs = [("作家", None, ["人"], []), ("小説家", None, ["作家"], []),
            ("甲", None, ["小説家"], []), ("乙", None, ["用語"], [])]
    cfg = dict(ct.DEFAULT_CONFIG)
    defc, qualc, donors, rounds = bcp.resolve_definitions(defs, seeds, cfg)
    assert donors["作家"] == "PERSON" and donors["小説家"] == "PERSON"
    assert dict(defc["甲"]) == {"PERSON": 1}
    assert "乙" not in defc, "a hypernym that is only a word about words says nothing"
    assert len(rounds) >= 3


def test_suffix_fallback_needs_two_characters():
    donors = {"会社": "GROUP_ORG", "人": "PERSON"}
    assert bcp.type_of("アカ会社", donors, 2) == "GROUP_ORG"
    assert bcp.type_of("アカ人", donors, 2) is None                      # only a 1-char tail
    assert bcp.type_of("言葉", {"言葉": "INFO_LANGUAGE"}, 2) is None     # META head


def test_qualified_articles_never_count_as_the_plain_definition():
    seeds = {"動物": "ANIMAL", "企業": "GROUP_ORG"}
    defs = [("ライオン", "動物", ["動物"], ["動物"]), ("ライオン", "企業", ["企業"], ["企業"])]
    defc, qualc, donors, _ = bcp.resolve_definitions(defs, seeds, dict(ct.DEFAULT_CONFIG))
    assert "ライオン" not in defc and "ライオン" not in donors
    assert dict(qualc["ライオン"]) == {"ANIMAL": 1, "GROUP_ORG": 1}


def test_leave_one_out_and_lift_make_a_biased_context_vote_only_for_the_real_type():
    cfg = dict(ct.DEFAULT_CONFIG)
    cfg.update({"min_seen": 1, "ctx_min_total": 4, "ctx_min_share_pct": 60, "ctx_min_lift_pct": 150,
                "role_min": 1, "role_min_share_pct": 60, "ctx_store_min": 1,
                "role_min_sources": 1})
    foods = ["料理", "食品", "飲料", "野菜"]
    people = ["人", "選手", "俳優", "歌手"]
    occ = Counter()
    for w in foods:
        occ[(w, "を", "食べる")] += 3
    for w in people:
        occ[(w, "が", "笑う")] += 3
    occ[("ホゲ", "を", "食べる")] += 4
    occ[("ホゲ", "が", "笑う")] += 1            # a minority use: no majority of the votes
    ex = {"occ": {"s": occ}, "pos": {"s": Counter({("ホゲ", "N"): 5})}, "sahen": {"s": Counter()},
          "counters": {"s": Counter()}, "defs": [], "aliases": [], "hearst": {}}
    res = bcp.resolve_all(ex, cfg)
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    assert row[2] == "DECIDED" and row[4] == "SUBSTANCE_FOOD" and row[7] == "role@s"
    ev = {(e[1], e[2], e[3]): e[4] for e in res["evidence"] if e[0] == "ホゲ"}
    # the votes are kept as evidence; the word's own 4 uses were not counted against it
    assert ev[("role", "s", "SUBSTANCE_FOOD")] == 4
    # the weakest arm alone is not a decision when two sources are required
    cfg2 = dict(cfg, role_min_sources=2)
    row2 = {r[0]: r for r in bcp.resolve_all(ex, cfg2)["headwords"]}["ホゲ"]
    assert row2[2] == "UNPLACED" and row2[4] == ""


def test_a_word_whose_sources_split_is_multiple_not_pooled():
    cfg = dict(ct.DEFAULT_CONFIG)
    cfg.update({"min_seen": 1, "ctx_min_total": 4, "ctx_min_share_pct": 60, "ctx_min_lift_pct": 150,
                "role_min": 2, "role_min_share_pct": 60, "ctx_store_min": 1,
                "role_min_sources": 2})
    foods = ["料理", "食品", "飲料", "野菜"]
    people = ["人", "選手", "俳優", "歌手"]
    def src(extra):
        occ = Counter()
        for w in foods:
            occ[(w, "を", "食べる")] += 3
        for w in people:
            occ[(w, "が", "笑う")] += 3
        occ.update(extra)
        return occ
    ex = {"occ": {"a": src({("ホゲ", "を", "食べる"): 3}), "b": src({("ホゲ", "が", "笑う"): 3})},
          "pos": {"a": Counter({("ホゲ", "N"): 3}), "b": Counter({("ホゲ", "N"): 3})},
          "sahen": {"a": Counter(), "b": Counter()}, "counters": {"a": Counter(), "b": Counter()},
          "defs": [], "aliases": [], "hearst": {}}
    res = bcp.resolve_all(ex, cfg)
    row = {r[0]: r for r in res["headwords"]}["ホゲ"]
    assert row[2] == "MULTIPLE" and row[4] == "PERSON,SUBSTANCE_FOOD"
