"""G2-f tests (L-540..): the grammar layer -- particle records, kinds, the question's slot and granularity pattern, the
grammar cross with its 24 rotations as moves, the read order.  Hand-computed toy corpus; the numbers of the G2 probes
(experiments/line3/g2/probe_particles.py) reproduced on bank2 fulllead (2314 WORD attachments, kinds 1118 / 178 / 2261,
slot 20 of 69 intra2 with 11 matching the gold's particle); ties are groups, never broken by order; the 24 proper
rotations; hash seeds; no float."""
import ast
import itertools
import json
import os
import statistics
import subprocess
import sys
from fractions import Fraction

import pytest

from verantyx.lang import strip_attribution
from verantyx.line3 import geometry as geo
from verantyx.line3 import grammar as Gr
from verantyx.line3 import space as sp
from verantyx.line3.granularity import SpanIndex

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SENTS_PATH = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
BANK2 = os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv")

TOY = ["猫は魚を食べる。", "猫の魚に猫が来た。", "東京の首都は何ですか", "猫と魚、猫は寝る。"]


# ---------------------------------------------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def toy():
    return Gr.build_records(TOY)


@pytest.fixture(scope="module")
def rows():
    return [json.loads(l) for l in open(SENTS_PATH, encoding="utf-8")]


@pytest.fixture(scope="module")
def corpus(rows):
    return Gr.build_records([r["sent"] for r in rows])


@pytest.fixture(scope="module")
def space(rows):
    return sp.build_space([{"sent": r["sent"], "source": r["source"]} for r in rows])


@pytest.fixture(scope="module")
def bank():
    rs = [l.rstrip("\n").split("\t") for l in open(BANK2, encoding="utf-8") if not l.startswith("#")]
    return [r[:7] for r in rs if r[2] == "fulllead"]


def att(rec, tier):
    return [(a.sid, a.start, a.end, a.unit, a.particle, a.p_start, a.p_end) for a in rec.attachments if a.tier == tier]


# ---------------------------------------------------------------------------------------------------------------
# (1) records by hand
# ---------------------------------------------------------------------------------------------------------------
def test_word_records_on_the_toy_corpus_by_hand(toy):
    #  s0 猫は魚を食べる。   s1 猫の魚に猫が来た。   s2 東京の首都は何ですか   s3 猫と魚、猫は寝る。
    assert att(toy, "WORD") == [
        (0, 0, 1, "猫", "は", 1, 2), (0, 2, 3, "魚", "を", 3, 4),
        (1, 0, 1, "猫", "の", 1, 2), (1, 2, 3, "魚", "に", 3, 4), (1, 4, 5, "猫", "が", 5, 6),
        (2, 0, 2, "東京", "の", 2, 3), (2, 3, 5, "首都", "は", 5, 6),
        (3, 0, 1, "猫", "と", 1, 2), (3, 4, 5, "猫", "は", 5, 6)]
    assert toy.counts("WORD", "猫") == {"は": 2, "の": 1, "が": 1, "と": 1}
    assert toy.counts("WORD", "魚") == {"に": 1, "を": 1}
    assert toy.n_head("WORD", "猫") == 5 and toy.n_attached("WORD", "猫") == 5
    assert toy.n_head("WORD", "魚") == 3 and toy.n_attached("WORD", "魚") == 2     # 魚、 : punctuation skipped, 猫 follows
    assert toy.n_head("WORD", "食べる") == 1 and toy.n_attached("WORD", "食べる") == 0
    assert toy.count("WORD", "猫", "は") == 2 and toy.count("WORD", "猫", "で") == 0
    assert toy.particle_totals("WORD") == {"は": 3, "の": 2, "に": 1, "を": 1, "が": 1, "で": 0, "と": 1}


def test_a_particle_is_never_a_head_and_function_units_have_no_records(toy):
    for a in toy.attachments:
        assert a.unit not in Gr.P7
    assert ("WORD", "は") not in toy.heads and ("WORD", "た") not in toy.heads and ("WORD", "何") not in toy.heads


def test_follow_labels_account_for_every_head(toy):
    for tier in ("RUN", "WORD"):
        heads = sum(n for (t, _), n in toy.heads.items() if t == tier)
        assert sum(toy.follow[tier].values()) == heads
    assert toy.follow["WORD"]["other"] == 1 and toy.follow["WORD"]["end"] == 2 and toy.follow["WORD"]["straddle"] == 0


def test_run_tier_adjacency_is_read_on_the_word_cut_and_a_straddle_is_counted(toy):
    # RUN 食 / 寝 end inside the WORD 食べる / 寝る: nothing is decided, and it is counted (L-542)
    assert toy.follow["RUN"]["straddle"] == 2
    assert toy.n_attached("RUN", "食") == 0 and toy.n_head("RUN", "食") == 1
    assert toy.counts("RUN", "猫") == toy.counts("WORD", "猫")
    assert [a for a in toy.attachments if a.tier == "RUN"] == [
        Gr.Attachment("RUN", a.sid, a.start, a.end, a.unit, a.particle, a.p_start, a.p_end)
        for a in toy.attachments if a.tier == "WORD"]


def test_char_has_no_records(toy):
    assert toy.tiers() == ("RUN", "WORD") and all(a.tier != "CHAR" for a in toy.attachments)


def test_trace_check_reads_every_attachment_against_its_sentence(toy):
    assert Gr.trace_check(toy, lambda sid: TOY[sid]) == []
    a0 = toy.attachments[0]
    bad = Gr.Records((Gr.Attachment(a0.tier, a0.sid, a0.start + 1, a0.end + 1, a0.unit, a0.particle, a0.p_start, a0.p_end),),
                     {("WORD", a0.unit): 1}, {"WORD": {k: 0 for k in Gr.FOLLOW_LABELS}}, 4, [0, 1, 2, 3])
    assert Gr.trace_check(bad, lambda sid: TOY[sid]) != []


def test_the_attribution_is_stripped_and_sids_are_positions():
    rec = Gr.build_records(["猫は魚を食べる。", "犬の魚。"])
    assert [(a.sid, a.unit, a.particle) for a in rec.attachments if a.tier == "WORD"] == [
        (0, "猫", "は"), (0, "魚", "を"), (1, "犬", "の")]


def test_records_of_space_skips_memory_sentences_and_keeps_sids():
    rows_ = [{"sent": TOY[0], "source": "a"}, {"sent": "犬の魚。", "source": "m", "kind": sp.MEMORY_USER},
             {"sent": TOY[3], "source": "b"}]
    s = sp.build_space(rows_)
    rec = Gr.records_of_space(s)
    assert rec.sids == (0, 2) and {a.sid for a in rec.attachments} == {0, 2} and rec.n_sentences == 3
    base = sp.build_space([rows_[0], rows_[2]])
    assert [(a.unit, a.particle) for a in Gr.records_of_space(base).attachments] == [(a.unit, a.particle) for a in rec.attachments]


# ---------------------------------------------------------------------------------------------------------------
# (2) kind, ties
# ---------------------------------------------------------------------------------------------------------------
def test_kind_on_the_toy_corpus(toy):
    assert toy.kind("WORD", "猫") == Gr.Kind("particle", ("は",), 2)
    assert toy.kind("WORD", "東京") == Gr.Kind("particle", ("の",), 1)
    assert toy.kind("WORD", "食べる") == Gr.NONE_KIND
    assert toy.kind("WORD", "魚") == Gr.Kind("tied", ("に", "を"), 1)         # を 1, に 1: a labelled group
    assert toy.kind_totals("WORD") == {"particle": 3, "tied": 1, "none": 2}
    assert toy.kind_distribution("WORD") == {"は": 2, "の": 1, "tied": 1, "none": 2}


def test_a_constructed_tie_is_a_group_never_broken_by_order():
    a = Gr.kind_of_counts({"の": 3, "に": 3, "は": 1})
    b = Gr.kind_of_counts({"は": 1, "に": 3, "の": 3})                        # same counts, other insertion order
    assert a == b == Gr.Kind("tied", ("の", "に"), 3)
    assert Gr.kind_of_counts({"と": 2, "で": 2, "が": 2}).particles == ("が", "で", "と")      # P7 order = label only
    assert Gr.kind_of_counts({"の": 3, "に": 2}) == Gr.Kind("particle", ("の",), 3)
    assert Gr.kind_of_counts({}) == Gr.NONE_KIND and Gr.kind_of_counts({"の": 0}) == Gr.NONE_KIND


def test_the_tie_does_not_depend_on_the_order_of_the_sentences():
    fwd = Gr.build_records(["猫は寝る。", "猫の寝る。"])
    rev = Gr.build_records(["猫の寝る。", "猫は寝る。"])
    assert fwd.kind("WORD", "猫") == rev.kind("WORD", "猫") == Gr.Kind("tied", ("は", "の"), 1)


# ---------------------------------------------------------------------------------------------------------------
# reproduction of the G2 probe on bank2 fulllead
# ---------------------------------------------------------------------------------------------------------------
def test_2314_word_attachments_and_their_particles(corpus, rows):
    assert corpus.n_attachments("WORD") == 2314
    assert corpus.particle_totals("WORD") == {"は": 357, "の": 623, "に": 456, "を": 214, "が": 163, "で": 292, "と": 209}
    assert sum(n for (t, _), n in corpus.heads.items() if t == "WORD") == 7892          # content tokens
    assert Gr.trace_check(corpus, lambda sid: rows[sid]["sent"]) == []               # I-G2-1 on all of them


def test_kind_distribution_1118_178_2261(corpus):
    assert corpus.kind_totals("WORD") == {"particle": 1118, "tied": 178, "none": 2261}
    assert corpus.kind_distribution("WORD") == {"の": 297, "に": 205, "は": 195, "で": 130, "を": 114, "と": 101, "が": 76,
                                                "tied": 178, "none": 2261}
    assert len(corpus.units("WORD")) == 3557


def test_run_records_measured_on_the_word_cut(corpus):
    # not in the G2 doc: RUN adjacency read on the WORD cut (L-542); the straddles are counted, not dropped
    assert corpus.n_attachments("RUN") == 2134
    assert corpus.follow["RUN"]["straddle"] == 353
    assert sum(corpus.follow["RUN"].values()) == sum(n for (t, _), n in corpus.heads.items() if t == "RUN") == 5027


def test_question_slot_20_of_69_and_11_of_20_match_the_golds_particle(bank):
    src = {r["source"]: r["sent"] for r in (json.loads(l) for l in open(SENTS_PATH, encoding="utf-8"))}
    intra = [r for r in bank if r[1] == "intra2"]
    assert len(intra) == 69 and len(bank) == 94
    n_slot = match = 0
    slot_marg, gold_marg = {}, {}
    by_slot = {}
    for qid, kind, _, subj, q, gold, ev in intra:
        rd = Gr.read_question(q)
        _, gp, lab = Gr.answer_particle(strip_attribution(src[ev]), gold.split("|"))
        assert lab != "notfound"
        if rd.slot_particle:
            n_slot += 1
            ok = gp == rd.slot_particle
            match += ok
            by_slot.setdefault(rd.slot_particle, [0, 0])
            by_slot[rd.slot_particle][0] += ok
            by_slot[rd.slot_particle][1] += 1
        slot_marg[rd.slot_particle] = slot_marg.get(rd.slot_particle, 0) + 1
        gold_marg[gp] = gold_marg.get(gp, 0) + 1
    assert (n_slot, match) == (20, 11)
    assert by_slot == {"の": [5, 6], "に": [3, 5], "を": [2, 3], "と": [1, 6]}
    chance = Fraction(sum(slot_marg.get(p, 0) * gold_marg.get(p, 0) for p in Gr.P7), len(intra))   # exact
    assert chance == Fraction(139, 69)                                                            # the doc: 2.0
    # unans: 5 with a P7 slot, all に
    un = [Gr.read_question(r[4]).slot_particle for r in bank if r[1] == "unans"]
    assert [p for p in un if p] == ["に"] * 5
    # 91 of 94 questions have an interrogative
    assert sum(1 for r in bank if Gr.read_question(r[4]).slot is not None) == 91


def test_particles_after_the_question_content_tokens_as_the_probe(bank):
    c = {p: 0 for p in Gr.P7}
    for r in bank:
        for f in Gr.read_question(r[4]).frames:
            if f.particle:
                c[f.particle] += 1
    assert c == {"は": 81, "の": 68, "に": 29, "を": 15, "が": 13, "で": 30, "と": 16}


# ---------------------------------------------------------------------------------------------------------------
# (3) the question side by hand
# ---------------------------------------------------------------------------------------------------------------
def test_slot_is_the_particle_after_the_interrogative_phrase():
    rd = Gr.read_question("何年に設立されましたか")
    assert rd.slot == Gr.Slot("何年", (0, 2), "に", "particle") and rd.slot_particle == "に" and rd.predicate is None
    rd = Gr.read_question("東京の首都は何ですか")
    assert rd.slot.particle is None and rd.slot.after == "other:です"
    assert rd.frames == (Gr.Frame("東京", (0, 2), "の", "particle"), Gr.Frame("首都", (3, 5), "は", "particle"))
    assert Gr.read_question("猫は魚を食べる").slot is None and Gr.read_question("猫は魚を食べる").predicate is None


def test_predicate_slot_of_the_x_no_y_wa_nani_question_is_a_separate_field():
    rd = Gr.read_question("東京の首都は何ですか")
    assert rd.predicate == Gr.Predicate("首都", (3, 5), "東京", (0, 2))
    assert rd.slot_particle is None                                   # never merged into the P7 slot (L-548)
    rd = Gr.read_question("この山の高さは何メートルですか")
    assert rd.predicate == Gr.Predicate("高さ", (4, 6), "山", (2, 3))
    assert Gr.read_question("唯物史観を唱えた人物は誰ですか").predicate.y == "人物"
    assert Gr.read_question("NGC 36を発見したのはいつですか").predicate is None     # a cleft: the unit before は is の
    assert Gr.read_question("何年に設立されましたか").predicate is None


def test_answer_particle_follows_the_probe_rule():
    s = "ハッシュ表ともいう。"
    assert Gr.answer_particle(s, ["ハッシュ表"]) == ((0, 5), "と", "particle")
    assert Gr.answer_particle(s, ["xyz", "ハッシュ"])[2] == "straddle" or Gr.answer_particle(s, ["xyz", "ハッシュ"])[1] is None
    assert Gr.answer_particle(s, ["なし"]) == (None, None, "notfound")
    assert Gr.answer_particle("猫は寝る。", ["寝る"])[2] == "end"


TOY_SPACE = ["東京都の人口は多い。", "京都市の面積は広い。", "大阪府の名産は多い。"]


def toy_item(q, unit):
    s = sp.build_space([{"sent": t, "source": "t"} for t in TOY_SPACE])
    ix = SpanIndex(s)
    return s, ix, {p.unit: p for p in Gr.read_question(q, s, ix).pattern}[unit]


def standin_pairs(item):
    return sorted({(x.unit, x.part, x.sid) for x in item.standins})


def test_granularity_pattern_types_t1_to_t5_and_their_standins_by_hand():
    #   RUN : 東京都 人口 多い | 京都市 面積 広い | 大阪府 名産 多い      WORD: 東京/都 .. 京都/市 .. 大阪/府 ..
    s, ix, p = toy_item("京都市の人口は何ですか", "京都市")
    assert p.type == "T1" and p.standins == () and p.via == "" and p.n_standins == 0              # in the space
    s, ix, p = toy_item("東京の人口は何ですか", "東京")                                              # RUN unknown, WORD 東京 known
    assert (p.type, p.via, p.span) == ("T2", "WORD", (0, 2)) and standin_pairs(p) == [("東京都", "東京", 0)]
    assert p.n_standins == 1 and p.n_sentences == 1 and p.pool == 8
    s, ix, p = toy_item("大阪市の人口は何ですか", "大阪市")                                          # both WORD parts known
    assert p.type == "T2" and [(x.unit, x.known) for x in p.word_parts] == [("大阪", True), ("市", True)]
    assert standin_pairs(p) == [("京都市", "市", 1), ("大阪府", "大阪", 2)] and (p.n_standins, p.n_sentences) == (2, 2)
    s, ix, p = toy_item("横浜府の人口は何ですか", "横浜府")                                          # some WORD parts known
    assert p.type == "T3" and [(x.unit, x.known) for x in p.word_parts] == [("横浜", False), ("府", True)]
    assert standin_pairs(p) == [("大阪府", "府", 2)]
    s, ix, p = toy_item("京阪の人口は何ですか", "京阪")                                              # no WORD part, CHAR parts known
    assert (p.type, p.via) == ("T4", "CHAR") and [(x.unit, x.known) for x in p.char_parts] == [("京", True), ("阪", True)]
    assert standin_pairs(p) == [("京都市", "京", 1), ("大阪府", "阪", 2), ("東京都", "京", 0)] and p.n_standins == 3
    s, ix, p = toy_item("鎌倉の人口は何ですか", "鎌倉")                                              # nothing known
    assert (p.type, p.via, p.standins, p.n_standins) == ("T5", "", (), 0)
    for q, u in (("東京の人口は何ですか", "東京"), ("京阪の人口は何ですか", "京阪")):                       # provenance of every stand-in
        s, ix, p = toy_item(q, u)
        for st in p.standins:
            assert ix.text(st.sid)[st.span[0]:st.span[1]] == st.unit and ix.text(st.sid)[st.part_span[0]:st.part_span[1]] == st.part
            assert st.span[0] <= st.part_span[0] and st.part_span[1] <= st.span[1]


def test_without_a_space_there_is_no_pattern():
    assert Gr.read_question("東京の人口は何ですか").pattern is None


def test_g1_unknown_word_numbers_139_92_74_118_47(space, bank):
    ix = SpanIndex(space)
    items = []
    for r in bank:
        items += [p for p in Gr.read_question(r[4], space, ix).pattern if p.type != "T1"]
    assert len(items) == 139                                                       # RUN unknown words of the 94 questions
    assert sum(1 for p in items if any(x.known for x in p.word_parts)) == 92        # >= 1 WORD part in the space
    assert sum(1 for p in items if p.word_parts and all(x.known for x in p.word_parts)) == 74
    assert sum(1 for p in items if any(x.known for x in p.char_parts)) == 118      # >= 1 CHAR part in the space
    types = {}
    for p in items:
        types[p.type] = types.get(p.type, 0) + 1
    assert types == {"T2": 74, "T3": 18, "T4": 32, "T5": 15}
    via_word = [p.n_standins if p.via == "WORD" else 0 for p in items]            # G1's L_RW: no stand-in for T4 / T5
    assert via_word.count(0) == 47
    # stand-ins per unknown word as measured here (the G1 doc says median 3, p90 132, max 151; see L-550)
    n = len(via_word)                                                              # p90 = sorted[(9 * n) // 10] (L-550)
    assert statistics.median(via_word) == 2 and max(via_word) == 136 and sorted(via_word)[(9 * n) // 10] == 119
    # G1 2.4(5)'s 3 / 132 / 151 are reproduced by STRING containment (a RUN unit of the space whose string contains a
    # known WORD part, e.g. 年代記 for 年, where the WORD cut is 年代+記) -- not by G1 3.2's span containment (L-550)
    runp = space.tiers["RUN"].postings
    sub = [len({v for v in runp if any(x.unit in v for x in p.word_parts if x.known)}) if p.via == "WORD" else 0
           for p in items]
    assert (statistics.median(sub), sorted(sub)[(9 * n) // 10], max(sub), sub.count(0)) == (3, 132, 151, 47)
    assert all({s.unit for s in p.standins} <= {v for v in runp if any(x.unit in v for x in p.word_parts if x.known)}
               for p in items if p.via == "WORD")
    for p in items:                                                                # every stand-in traces to the sentence
        for st in p.standins:
            assert ix.text(st.sid)[st.span[0]:st.span[1]] == st.unit and st.unit in space.tiers[st.tier].postings
            assert ix.text(st.sid)[st.part_span[0]:st.part_span[1]] == st.part
            assert st.span[0] <= st.part_span[0] and st.part_span[1] <= st.span[1]
        assert p.n_standins == len({st.unit for st in p.standins}) and p.n_sentences == len({st.sid for st in p.standins})


# ---------------------------------------------------------------------------------------------------------------
# (4) the grammar cross, the 24 rotations, the alignment
# ---------------------------------------------------------------------------------------------------------------
def test_the_ladder_weights_are_exact_fibonacci_fractions():
    assert [Gr.WEIGHTS[p] for p in Gr.LADDER] == [Fraction(n, 377) for n in (233, 144, 89, 55, 34, 21, 13)]
    assert all(isinstance(w, Fraction) for w in Gr.WEIGHTS.values())
    assert sum(Gr.WEIGHTS.values()) == Fraction(589, 377)
    assert Gr.CENTRE_PARTICLE == "は" and Gr.ARM_PARTICLES == ("の", "に", "で", "と", "を", "が")
    assert set(Gr.LADDER) == set(Gr.P7)


def test_the_foundation_cross_has_the_ladder_on_x_y_z_in_axes_order():
    c = Gr.foundation_cross()
    assert c.L == 1 and c.center == "は" and c.orientation == geo.IDENTITY
    assert [(geo.AXES[i], c.arms[i][0]) for i in range(6)] == [
        ("+x", "の"), ("-x", "に"), ("+y", "で"), ("-y", "と"), ("+z", "を"), ("-z", "が")]
    assert Gr.foundation_obj()["arms"][0] == ["+x", "の", "144/377"]
    assert len(Gr.foundation_sha()) == 64


def test_the_24_proper_rotations_are_exactly_the_moves():
    # independent enumeration: signed permutation matrices with determinant +1 acting on e1..e3 -> permutations of the arms
    perms = set()
    for pi in itertools.permutations(range(3)):
        for sg in itertools.product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for col in range(3):
                m[pi[col]][col] = sg[col]
            det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1]) - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
                   + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
            if det != 1:
                continue
            perm = [0] * 6
            for axis in range(3):
                for k, sign in enumerate((1, -1)):                    # arm 2*axis = +, 2*axis+1 = -
                    img = [m[r][axis] * sign for r in range(3)]
                    row = next(r for r in range(3) if img[r] != 0)
                    perm[2 * axis + k] = 2 * row + (0 if img[row] == 1 else 1)
            perms.add(tuple(perm))
    assert len(perms) == 24 and perms == {r.perm for r in geo.G24}
    a = Gr.align([{} for _ in range(6)])
    assert len(a.scores) == len(geo.G24) == 24
    assert all(r.preserves_opposites() for r in geo.G24)


def test_alignment_score_is_exact_and_equals_the_direct_formula():
    counts = [{"の": 7, "に": 2}, {"に": 5, "で": 1}, {"で": 4, "が": 9}, {"と": 3, "の": 6}, {"を": 8, "は": 2}, {"が": 1, "と": 5}]
    a = Gr.align(counts)
    for idx, r in enumerate(geo.G24):
        direct = sum(counts[r.perm[i]].get(Gr.ARM_PARTICLES[i], 0) for i in range(6))     # grammar arm i faces data arm r(i)
        assert a.scores[idx] == Gr.align_score(counts, r) == direct
    assert all(isinstance(s, int) for s in a.scores)
    assert a.identity_score == a.scores[geo.G24.index(geo.IDENTITY)] == 7 + 5 + 4 + 3 + 8 + 1


def test_alignment_identity_data_gives_a_unique_identity():
    counts = [{p: 10} for p in Gr.ARM_PARTICLES]                      # data arm j holds exactly what follows ARM_PARTICLES[j]
    a = Gr.align(counts)
    assert a.best == 60 and a.best_indices == (geo.G24.index(geo.IDENTITY),) and not a.tied
    # a 180-degree turn about z: +x <-> -x, +y <-> -y, the z arms stay
    turn = geo.Rotation((1, 0, 3, 2, 4, 5))
    assert turn in geo.G24
    counts2 = [{Gr.ARM_PARTICLES[turn.perm[j]]: 10} for j in range(6)]
    b = Gr.align(counts2)
    assert b.best == 60 and b.best_indices == (geo.G24.index(turn.inverse()),)
    # a non-involutive rotation pins the convention (grammar arm i faces data arm r(i), not r^-1(i))
    r = next(x for x in geo.G24 if x.compose(x) != geo.IDENTITY and x.compose(x).compose(x) == geo.IDENTITY)    # order 3
    assert r.inverse() != r
    counts3 = [{Gr.ARM_PARTICLES[r.perm[j]]: 10} for j in range(6)]
    c = Gr.align(counts3)
    assert c.best == 60 and c.best_indices == (geo.G24.index(r.inverse()),)
    assert Gr.align_score(counts3, r) < 60 and Gr.align_score(counts3, r.inverse()) == 60


def test_alignment_ties_are_a_group_never_broken_by_index():
    a = Gr.align([{} for _ in range(6)])                              # no data: all 24 tie at 0
    assert a.best == 0 and a.best_indices == tuple(range(24)) and a.tied
    counts = [{"の": 5}, {"の": 5}, {}, {}, {}, {}]                   # の faces +x or -x: several rotations reach 5
    b = Gr.align(counts)
    ref = [i for i, r in enumerate(geo.G24) if r.perm[0] in (0, 1)]    # grammar arm 0 (の) lands on data arm 0 or 1
    assert b.best == 5 and list(b.best_indices) == ref and len(ref) == 8 and b.tied


def test_window_grammar_cross_and_data_arm_counts(toy):
    g = Gr.grammar_cross(toy, "w0", [3, 0])                            # sids given out of order, window id opaque
    assert g.sids == (0, 3) and g.tiers == ("WORD",) and g.foundation == Gr.foundation_sha()
    assert dict(g.counts) == {"は": 2, "の": 0, "に": 0, "を": 1, "が": 0, "で": 0, "と": 1}
    assert g.kind == Gr.Kind("tied", ("を", "と"), 1)                   # over the six arms: は (2) is the centre (L-549)
    assert g.seats("を") == (("WORD", "魚"),) and g.seats("は") == (("WORD", "猫"),) and g.seats("の") == ()
    assert g.cross == Gr.foundation_cross()
    both = Gr.grammar_cross(toy, "w1", [0, 1, 2, 3])
    assert dict(both.counts)["は"] == 3 and both.kind == Gr.Kind("particle", ("の",), 2)     # not は 3
    assert toy.kind("WORD", "猫") == Gr.Kind("particle", ("は",), 2)  # a unit's kind (G2 4.1) keeps は
    assert Gr.grammar_cross(toy, 1, []).kind == Gr.NONE_KIND
    # data arms: units seated on the six arms -> exact attachment counts in the window
    arms = [["猫"], ["魚"], [], [("WORD", "東京")], [], ["猫", "魚"]]
    cnt = Gr.data_arm_counts(toy, arms)
    assert cnt[0] == {"は": 2, "の": 1, "が": 1, "と": 1} and cnt[1] == {"に": 1, "を": 1} and cnt[2] == {}
    assert cnt[3] == {"の": 1} and cnt[5] == {"は": 2, "の": 1, "に": 1, "を": 1, "が": 1, "と": 1}
    assert Gr.data_arm_counts(toy, arms, sids=[0])[0] == {"は": 1}
    a = Gr.align(cnt)
    assert a.best == max(a.scores) and set(a.best_indices) == {i for i, s in enumerate(a.scores) if s == a.best}


# ---------------------------------------------------------------------------------------------------------------
# (5) the read order
# ---------------------------------------------------------------------------------------------------------------
K = {"の": Gr.Kind("particle", ("の",), 3), "に": Gr.Kind("particle", ("に",), 2), "は": Gr.Kind("particle", ("は",), 1),
     "tie1": Gr.Kind("tied", ("の", "に"), 2), "tie2": Gr.Kind("tied", ("で", "と"), 1), "none": Gr.NONE_KIND}
CANDS = [("a", K["の"]), ("b", K["に"]), ("c", K["tie1"]), ("d", K["none"]), ("e", K["は"]), ("f", K["の"]), ("g", K["tie2"]),
         ("h", K["tie1"])]


def groups(order):
    return [(g.reason, g.members) for g in order.groups]


def test_read_order_match_first_then_ladder_weight_ties_as_groups():
    o = Gr.read_order("の", CANDS)
    assert groups(o) == [("match", ("a", "f")), ("particle", ("e",)), ("particle", ("b",)), ("tied", ("c", "h")),
                         ("tied", ("g",)), ("none", ("d",))]
    o = Gr.read_order(None, CANDS)                                    # no slot: ladder weight only (は 233 > の 144 > に 89)
    assert groups(o) == [("particle", ("e",)), ("particle", ("a", "f")), ("particle", ("b",)), ("tied", ("c", "h")),
                         ("tied", ("g",)), ("none", ("d",))]
    o = Gr.read_order("に", CANDS)
    assert groups(o)[0] == ("match", ("b",)) and groups(o)[1] == ("particle", ("e",)) and groups(o)[2] == ("particle", ("a", "f"))
    assert o.flat() == ("b", "e", "a", "f", "c", "h", "g", "d")
    assert sorted(o.flat()) == sorted(c[0] for c in CANDS)            # only an order: the set is unchanged


def test_a_tied_kind_never_matches_a_slot_and_equal_kinds_are_never_split():
    o = Gr.read_order("の", [("x", K["tie1"]), ("y", K["tie1"])])
    assert groups(o) == [("tied", ("x", "y"))]                        # tied is not "match" even though it contains の
    o = Gr.read_order("で", [("x", Gr.Kind("particle", ("で",), 1)), ("y", Gr.Kind("particle", ("で",), 9))])
    assert groups(o) == [("match", ("x", "y"))]                       # the count of the kind is not a tie-break


def test_read_order_is_independent_of_the_input_order():
    ref = Gr.read_order("の", CANDS).to_bytes()
    for perm in itertools.islice(itertools.permutations(CANDS), 0, 40320, 997):
        assert Gr.read_order("の", list(perm)).to_bytes() == ref


def test_read_order_from_a_question_reading_and_the_predicate_only_question():
    assert Gr.read_order(Gr.read_question("何年に設立されましたか"), CANDS).slot == "に"
    pred = Gr.read_question("東京の首都は何ですか")
    assert pred.predicate is not None and Gr.read_order(pred, CANDS).slot is None      # a predicate-only question: no match group
    assert Gr.read_order(pred, CANDS).to_bytes() == Gr.read_order(None, CANDS).to_bytes()


def test_read_order_refuses_what_it_cannot_order():
    with pytest.raises(ValueError):
        Gr.read_order("から", CANDS)
    with pytest.raises(ValueError):
        Gr.read_order("の", [("a", K["の"]), ("a", K["に"])])
    assert Gr.read_order("の", []).groups == ()


# ---------------------------------------------------------------------------------------------------------------
# (6) bytes, hash seeds, no float
# ---------------------------------------------------------------------------------------------------------------
SCRIPT = r'''
import hashlib, json, sys
sys.path.insert(0, %r)
from verantyx.line3 import grammar as Gr, space as sp, geometry as geo
rows = [json.loads(l) for l in open(%r, encoding="utf-8")]
space = sp.build_space([{"sent": r["sent"], "source": r["source"]} for r in rows])
rec = Gr.records_of_space(space)
qs = [l.rstrip("\n").split("\t") for l in open(%r, encoding="utf-8") if not l.startswith("#")]
qs = [r[4] for r in qs if r[2] == "fulllead"]
from verantyx.line3.granularity import SpanIndex
ix = SpanIndex(space)
rds = [Gr.read_question(q, space, ix) for q in qs]
g = Gr.grammar_cross(rec, 0, range(0, 40))
a = Gr.align(Gr.data_arm_counts(rec, [["猫"], ["地図"], ["駅"], ["国"], ["年"], ["人"]], range(0, 592)))
cands = [(i, rec.kind("WORD", u)) for i, u in enumerate(rec.units("WORD")[:300])]
o = Gr.read_order(rds[0], cands)
h = hashlib.sha256()
for b in [rec.to_bytes()] + [r.to_bytes() for r in rds] + [g.to_bytes(), a.to_bytes(), o.to_bytes()]:
    h.update(hashlib.sha256(b).digest())
print(h.hexdigest(), len(rec.to_bytes()), len(rds[0].to_bytes()))
'''


def test_bytes_are_identical_under_hash_seeds_0_1_12345():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", SCRIPT % (ROOT, SENTS_PATH, BANK2)], capture_output=True, env=env, timeout=240)
        assert r.returncode == 0, r.stderr.decode()[-800:]
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and len(outs[0]) > 60


def test_to_bytes_is_canonical_json_without_float(corpus, space, bank):
    def walk(x):
        assert not isinstance(x, float)
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        if isinstance(x, list):
            [walk(v) for v in x]
    ix = SpanIndex(space)
    objs = [corpus.to_bytes(), Gr.read_question(bank[0][4], space, ix).to_bytes(), Gr.grammar_cross(corpus, 0, [0, 1]).to_bytes(),
            Gr.align([{} for _ in range(6)]).to_bytes(), Gr.read_order("の", CANDS).to_bytes()]
    for b in objs:
        walk(json.loads(b.decode("utf-8")))
        assert b == json.dumps(json.loads(b.decode("utf-8")), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert json.loads(Gr.grammar_cross(corpus, 0, [0]).to_bytes().decode("utf-8"))["foundation"] == Gr.foundation_sha()
    assert Gr.records_of_space(space).to_bytes() == corpus.to_bytes()               # a base-only space: same sids, same bytes
    assert corpus.to_bytes() == Gr.build_records([json.loads(l)["sent"] for l in open(SENTS_PATH, encoding="utf-8")]).to_bytes()


def test_no_float_and_no_division_in_the_module():
    tree = ast.parse(open(Gr.__file__, encoding="utf-8").read())
    for n in ast.walk(tree):
        assert not (isinstance(n, ast.Constant) and isinstance(n.value, float))
        assert not (isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Div, ast.Pow)))
        assert not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("float", "round"))


def test_nothing_hooks_into_the_question_path():
    src = open(Gr.__file__, encoding="utf-8").read()
    for mod in ("ask", "cycle", "placement", "matryoshka", "energy", "carry"):
        assert ("import %s" % mod) not in src and ("line3.%s " % mod) not in src.replace("line3.granularity", "")
    assert "cli" not in [n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module]
    # importing the module loads none of the question path (transitively)
    code = ("import sys; import verantyx.line3.grammar; print(sorted(m for m in sys.modules if m.split('.')[-1] in "
            "('ask', 'cycle', 'placement', 'matryoshka', 'energy', 'carry', 'carry_query', 'cli', 'readout')))")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=dict(os.environ, PYTHONPATH=ROOT), timeout=120)
    assert r.returncode == 0 and r.stdout.strip() == b"[]", r.stderr.decode()[-800:]
    # and no module of the question path imports grammar (nothing is hooked in yet)
    for name in ("ask", "cycle", "placement", "matryoshka", "energy", "carry", "carry_query", "readout"):
        path = os.path.join(ROOT, "verantyx", "line3", name + ".py")
        tree = ast.parse(open(path, encoding="utf-8").read())
        mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        names = [a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names]
        assert not any("grammar" in m for m in mods) and "grammar" not in names and not any(x.endswith(".grammar") for x in names)
