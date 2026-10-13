"""PUB-M1 tests: the shape exchanger (verantyx/loom/memshape.py; docs/LINE3_PUBLIC_DESIGN.md 4.2).  Hand-written sentences for every shape, every F0 reason, the chains, the change
clause, the clause cut; the frozen table (SHAPES_SHA); the agreement of its units and gaps with the loom's corpus; purity (no clock / float / process) and byte-identity across PYTHONHASHSEED."""
import ast
import json
import os
import subprocess
import sys

import pytest

from verantyx.line3 import grammar as gm
from verantyx.loom import memshape as ms
from verantyx.loom.corpus import Corpus
from loom_common import ROOT


def one(sentence):
    e = ms.exchange(sentence)
    assert len(e.clauses) == 1, [c.text for c in e.clauses]
    return e.clauses[0]


def arms(c):
    return [(a.particle, a.seat.text, [(x.particle, x.seat.text, [(y.particle, y.seat.text) for y in x.arms]) for x in a.arms]) for a in c.arms]


# -- the frozen table ----------------------------------------------------------------------------------------------------------------------------
def test_the_shape_table_is_frozen():
    assert ms.SHAPES_VERSION == "shape.v1"
    assert ms.SHAPES_SHA == "1908323f8690db16ebc7ea90ff46e00cb175ba6fd61021b6f31468c72dff7497"            # any edit of a rule or constant changes this: a new table is a new version, never an edit
    assert ms.SHAPE_ORDER == ("F1", "F2", "F3", "F4", "F0") and set(ms.SHAPE_NAMES) == set(ms.SHAPE_ORDER)
    assert ms._shapes_sha() == ms.SHAPES_SHA


# -- F1 属性 ---------------------------------------------------------------------------------------------------------------------------------------
def test_f1_attribute():
    c = one("障害訓練の開催地は大阪")
    assert c.shape == "F1" and c.centre == "開催地" and c.centre_units == ("開催", "地")
    assert arms(c) == [("の", "障害訓練", [])] and c.value.text == "大阪" and c.value.units == ("大阪",)
    assert c.span == (0, 11) and c.text == "障害訓練の開催地は大阪" and c.reason is None and c.change is None and not c.via_topic


def test_f1_with_a_copula_tail_and_a_number():
    c = one("手動同期の上限は5回です。")
    assert c.shape == "F1" and arms(c) == [("の", "手動同期", [])] and c.value.text == "5回" and c.tail == "です"
    assert c.span == (0, 12)                                           # the clause ends at the last letter, the 。 is outside


def test_f1_chain_of_three_the_centre_is_the_last_the_arm_of_the_arm_is_the_first():
    c = one("A社のB事業の担当は田中")
    assert c.shape == "F1" and c.centre == "担当"
    assert arms(c) == [("の", "B事業", [("の", "A社", [])])] and c.value.text == "田中"
    c = one("田中のB事業の担当者の連絡先は不明")
    assert arms(c) == [("の", "担当者", [("の", "B事業", [("の", "田中")])])] and c.value.text == "不明"


def test_f1_the_doubled_topic_of_the_meter_is_a_chain_not_a_refusal():
    c = one("在庫管理アプリ小規模リリースの在庫管理アプリ小規模リリースの認証モジュール担当は田中")
    assert c.shape == "F1" and c.centre == "認証モジュール担当" and c.centre_units == ("認証", "モジュール", "担当") and arms(c) == [("の", "在庫管理アプリ小規模リリース", [("の", "在庫管理アプリ小規模リリース", [])])]


def test_f1_value_may_hold_a_no():
    c = one("今日の作業はK3の修正")
    assert c.shape == "F1" and c.value.text == "K3の修正" and c.value.units[-1] == "修正"


# -- F2 主題値 ---------------------------------------------------------------------------------------------------------------------------------------
def test_f2_topic_value():
    c = one("認証モジュール担当は田中です。")
    assert c.shape == "F2" and c.centre == "認証モジュール担当" and c.centre_units == ("認証", "モジュール", "担当") and c.arms == () and c.value.text == "田中" and c.tail == "です"


def test_f2_numbers_and_paths_and_versions():
    assert one("CDNキャッシュTTLは120秒").value.text == "120秒"
    assert one("価格は2,400円です").value.text == "2,400円"                # a comma between digits is no cut
    assert one("本番配布版はv2.4").value.text == "v2.4"
    assert one("共有ドライブは/release/testです").value.text == "release/test"


# -- F3 出来事 ---------------------------------------------------------------------------------------------------------------------------------------
def test_f3_event_with_arguments_in_the_reading_order():
    c = one("田中が営業部で資料を作成した")
    assert c.shape == "F3" and c.centre == "作成" and not c.via_topic
    assert [p for p, _, _ in arms(c)] == ["が", "を", "で"]            # OP-LOOM-3: が を と で に の, then the centre
    assert dict((p, t) for p, t, _ in arms(c)) == {"が": "田中", "を": "資料", "で": "営業部"}
    c = one("田中が部長に昇進した")
    assert c.shape == "F3" and c.centre == "昇進" and arms(c) == [("が", "田中", []), ("に", "部長", [])]


def test_f3_an_argument_may_be_a_no_chain():
    c = one("田中が認証の修正を担当した")
    assert c.shape == "F3" and c.centre == "担当" and arms(c) == [("が", "田中", []), ("を", "修正", [("の", "認証", [])])]


def test_f3_topic_as_subject():
    c = one("会議は東京で開催する")
    assert c.shape == "F3" and c.via_topic and c.centre == "開催" and arms(c) == [("が", "会議", []), ("で", "東京", [])]
    c = one("会議は延期しました")
    assert c.shape == "F3" and c.via_topic and arms(c) == [("が", "会議", [])]


def test_f3_predicate_forms():
    assert one("会議は来週に延期になった").centre == "延期"            # サ変 + になる
    assert one("会議は東京で行う").centre == "行う"                     # a verb in its dictionary form
    assert one("会議を東京で開催する").shape == "F4"


# -- F4 主語なし -------------------------------------------------------------------------------------------------------------------------------------
def test_f4_no_subject():
    c = one("会議を開く")
    assert c.shape == "F4" and c.centre == "開く" and arms(c) == [("を", "会議", [])]
    c = one("完了しました")
    assert c.shape == "F4" and c.centre == "完了" and c.arms == ()
    c = one("東京で日本の首都を調べる")
    assert c.shape == "F4" and c.centre == "調べる" and arms(c) == [("を", "首都", [("の", "日本", [])]), ("で", "東京", [])]


def test_f4_a_taigen_dome_predicate_needs_an_argument():
    c = one("認証の期限を変更")
    assert c.shape == "F4" and c.centre == "変更" and arms(c) == [("を", "期限", [("の", "認証", [])])]
    assert one("認証の期限").reason == "no_relation"


# -- the change clause -------------------------------------------------------------------------------------------------------------------------------
def test_change_clause_with_a_topic():
    c = one("QA締切は6/12から6/14に変更になりました")
    assert c.shape == "F2" and c.centre == "QA締切" and c.centre_units == ("QA", "締切") and c.value.text == "6/14" and c.change.old.text == "6/12" and c.change.new.text == "6/14"


def test_change_clause_on_an_attribute_and_with_a_wo():
    c = one("認証の期限は金曜から月曜に変更")
    assert c.shape == "F1" and arms(c) == [("の", "認証", [])] and c.value.text == "月曜" and c.change.old.text == "金曜"
    c = one("期限を金曜から月曜に変更しました")
    assert c.shape == "F2" and c.centre == "期限" and c.change.new.text == "月曜"


def test_change_clause_without_a_slot_is_f4():
    c = one("金曜から月曜に変更")
    assert c.shape == "F4" and c.centre == "変更" and c.change.old.text == "金曜" and c.change.new.text == "月曜" and c.value.text == "月曜"


def test_kara_outside_a_change_clause_and_he_are_not_a_gap():
    c = one("会議は金曜から開催する")
    assert c.shape == "F0" and c.reason == "gap_is_not_a_particle" and c.detail == "から"
    c = one("期限は金曜から月曜へ変更")
    assert c.shape == "F0" and c.reason == "gap_is_not_a_particle"


# -- F0, every reason --------------------------------------------------------------------------------------------------------------------------------
F0_CASES = [
    ("はい", "no_unit"),
    ("担当表では認証モジュール担当は田中です", "gap_is_not_a_particle"),
    ("会議の開催も不明", "gap_is_not_a_particle"),
    ("彼は担当ではない", "negated"),
    ("会議を東京で開催しない", "negated"),
    ("認証の担当は誰ですか", "question"),
    ("認証の担当は田中ですか?", "question"),
    ("河合が責任者", "no_predicate"),
    ("田中が東京の本社", "no_predicate"),
    ("田中です", "no_relation"),
    ("認証の期限", "no_relation"),
    ("東京で会議は金曜", "case_before_topic"),
    ("田中は担当は営業", "two_topics"),
    ("田中が佐藤が参加する", "repeated_case_particle"),
    ("田中と佐藤を呼ぶ", "coordination"),
    ("締め切りは高い", "value_not_noun"),
]


@pytest.mark.parametrize("sentence,reason", F0_CASES)
def test_f0_reasons(sentence, reason):
    c = one(sentence)
    assert c.shape == "F0" and c.reason == reason and c.centre is None and c.arms == () and c.value is None
    assert c.reason in ms.F0_REASONS


def test_inflected_verbs_are_events_with_the_lemma_as_centre_and_the_surface_kept():
    """Owner: the memory takes inflected verbs in (the output gate does not): the centre is the tokenizer's lemma, the written form stays in `surface`."""
    for sentence, centre, surface, shape in (("会議を開いた", "開く", "開いた", "F4"), ("決めた", "決める", "決めた", "F4"), ("資料が遅れている", "遅れる", "遅れている", "F3"), ("会議を開く", "開く", "開く", "F4"),
                                             ("会議は決まった", "決まる", "決まった", "F3"), ("変換バッチは読込みます", "読み込む", "読込みます", "F3"), ("東京で切替リハーサルを行い", "行う", "行い", "F4")):
        c = one(sentence)
        assert (c.shape, c.centre, c.surface) == (shape, centre, surface), sentence
        assert c.centre_units[-1] == centre and c.reason is None
    c = one("会議は延期しました")
    assert c.centre == "延期" and c.surface is None                      # a サ変 noun is its own centre: no surface
    assert one("会議を開いていない").reason == "negated"
    assert "inflected_head" not in ms.F0_REASONS


def test_the_event_centre_is_the_predicate_only_quantity_and_bare_nouns_have_their_own_seats():
    c = one("52本保管します")
    assert (c.shape, c.centre, c.centre_units) == ("F4", "保管", ("保管",)) and c.quantity.text == "52本" and c.quantity.units == ("52", "本") and c.object_bare is None and c.surface is None
    c = one("培養用予備液は52本保管します")
    assert (c.shape, c.centre) == ("F3", "保管") and c.quantity.text == "52本" and arms(c) == [("が", "培養用予備液", [])]
    c = one("3日延期した")
    assert (c.shape, c.centre) == ("F4", "延期") and c.quantity.text == "3日" and c.object_bare is None
    c = one("資料送付済み")
    assert (c.shape, c.centre, c.centre_units) == ("F4", "送付", ("送付",)) and c.object_bare.text == "資料" and c.quantity is None and c.surface == "送付済み"
    c = one("資料は送付済み")
    assert (c.shape, c.centre, c.via_topic) == ("F3", "送付", True) and arms(c) == [("が", "資料", [])]
    c = one("会議資料保管します")
    assert c.centre == "保管" and c.object_bare.text == "会議資料" and c.quantity is None
    c = one("会議資料を3日保管した")                                    # 3日 touches the predicate, 会議資料 has its particle: an argument
    assert c.centre == "保管" and c.quantity.text == "3日" and arms(c) == [("を", "会議資料", [])]
    c = one("10台設置した")
    assert c.centre == "設置" and c.quantity.text == "10台"
    c = one("田中が3日遅れている")
    assert (c.centre, c.surface, c.quantity.text) == ("遅れる", "遅れている", "3日")
    assert one("会議を開く").quantity is None and one("会議を開く").object_bare is None


def test_the_tokens_do_not_depend_on_what_the_function_word_cache_holds():
    """`is_function_unit` runs the same tagger on a unit and used to overwrite the sentence's lattice (features read as 'BOS/EOS') depending on what it had cached."""
    from verantyx.line3 import funcwords
    s = "約3日延期した"
    funcwords._cache.clear()
    cold = ms._tokens(s)
    warm = ms._tokens(s)
    assert cold == warm and all(t.pos1 != "BOS/EOS" for t in cold)
    funcwords._cache.clear()
    assert ms.exchange("資料送付済み") == ms.exchange("資料送付済み")


def test_every_f0_reason_has_a_test():
    assert set(r for _, r in F0_CASES) == set(ms.F0_REASONS)


def test_f0_keeps_its_span_and_text():
    c = one("田中です")
    assert c.span == (0, 4) and c.text == "田中です"


# -- the clause cut ----------------------------------------------------------------------------------------------------------------------------------
def test_hard_cut_and_comma_cut():
    e = ms.exchange("リリース窓口担当は小林、翻訳確認は渡辺です。手順書確認は小林です。")
    assert e.shapes() == ("F2", "F2", "F2") and [c.text for c in e.clauses] == ["リリース窓口担当は小林", "翻訳確認は渡辺です", "手順書確認は小林です"]
    assert [c.span for c in e.clauses] == [(0, 11), (12, 21), (22, 32)]
    assert all(e.text[c.span[0]:c.span[1]] == c.text for c in e.clauses)


def test_a_label_before_a_colon_is_not_a_clause():
    e = ms.exchange("監視設定メモ: 本番監視ポートは8443、検証ログ受信ポートは8088です。")
    assert e.shapes() == ("F2", "F2") and [t for _, t in e.skipped] == ["label"] and e.text[e.skipped[0][0][0]:e.skipped[0][0][1]] == "監視設定メモ"
    assert ms.exchange("会議は9:30に開始する").shapes() == ("F3",)         # a colon between digits is part of the time


def test_empty_and_punctuation_only_texts_have_no_clause():
    for t in ("", "。", "  ", "、、。"):
        e = ms.exchange(t)
        assert e.clauses == () and e.skipped == ()


def test_a_mixed_sentence_gives_each_clause_its_own_shape():
    e = ms.exchange("会議は東京で開催され、資料は共有した")
    assert e.shapes() == ("F3", "F3")
    e = ms.exchange("田中、佐藤が参加する")
    assert e.shapes() == ("F0", "F3") and e.clauses[0].reason == "no_relation"          # an enumeration is not an adverbial


def test_nfc_and_attribution_are_taken_as_the_corpus_takes_them():
    import unicodedata
    s = unicodedata.normalize("NFD", "ポートの番号は8443")
    c = one(s)
    assert c.shape == "F1" and unicodedata.is_normalized("NFC", ms.exchange(s).text)


# -- the leading adverbial ------------------------------------------------------------------------------------------------------------------------
def test_a_leading_adverbial_is_attached_to_the_next_clause_and_is_not_a_clause():
    e = ms.exchange("昨日、会議は延期した")
    assert e.shapes() == ("F3",) and [a.text for a in e.clauses[0].adverbial] == ["昨日"] and e.clauses[0].adverbial[0].span == (0, 2)
    e = ms.exchange("来週は、会議を開く")
    assert e.shapes() == ("F4",) and [a.text for a in e.clauses[0].adverbial] == ["来週は"]
    e = ms.exchange("では、認証の期限は金曜です")
    assert e.shapes() == ("F1",) and [a.text for a in e.clauses[0].adverbial] == ["では"] and e.clauses[0].adverbial[0].units == ()
    e = ms.exchange("昨日、来週は、会議は延期した")
    assert e.shapes() == ("F3",) and [a.text for a in e.clauses[0].adverbial] == ["昨日", "来週は"]


def test_an_adverbial_with_no_clause_after_it_stays_a_clause_of_f0():
    e = ms.exchange("昨日、")
    assert e.shapes() == ("F0",) and e.clauses[0].reason == "no_relation" and e.clauses[0].adverbial == ()
    e = ms.exchange("昨日、。会議は延期した")
    assert e.shapes() == ("F0", "F3") and e.clauses[1].adverbial == ()
    e = ms.exchange("昨日、メモ: 会議は延期した")
    assert e.shapes() == ("F0", "F3")                                                  # the label between them: the adverbial is flushed as it was


def test_a_bare_self_introduction_and_an_enumeration_are_not_adverbials():
    assert ms.exchange("田中です。会議は延期した").shapes() == ("F0", "F3")
    e = ms.exchange("はい、田中です")
    assert e.shapes() == ("F0",) and e.clauses[0].reason == "no_relation" and [a.text for a in e.clauses[0].adverbial] == ["はい"]
    assert ms.exchange("田中、佐藤、鈴木が参加する").shapes() == ("F0", "F0", "F3")


# -- agreement with the loom's grammar layer --------------------------------------------------------------------------------------------------------
SAMPLES = ["障害訓練の開催地は大阪", "A社のB事業の担当は田中", "田中が営業部で資料を作成した", "認証モジュール担当は田中", "東京で日本の首都を調べる", "担当表では認証モジュール担当は田中です",
           "期限を金曜から月曜に変更", "在庫管理アプリ小規模リリースの認証モジュール担当は田中"]


@pytest.mark.parametrize("s", SAMPLES)
def test_tokens_are_the_grammar_layers_words(s):
    got = [(t.s, t.a, t.b) for t in ms._tokens(s)]
    assert got == gm.words_of(s)


@pytest.mark.parametrize("s", SAMPLES)
def test_units_and_gaps_are_the_loom_corpus_ones(s):
    """Where the sentence has no verb ending cut into light-verb tokens (し, なり), the exchanger's units are the loom's WORD units and its gaps are `Corpus.span_gaps`."""
    c = Corpus(json.dumps({"sent": s, "source": "t"}, ensure_ascii=False).encode("utf-8") + b"\n")
    units = list(c.tier("WORD").sentence_units[0])
    toks = ms._tokens(s)
    mine = [t for t in toks if not t.fn]
    if [t.s for t in mine] != units:                                    # 田中が営業部で資料を作成した: the loom keeps し as a unit, the exchanger reads it as part of the verb ending
        assert s == "田中が営業部で資料を作成した" or s == "期限を金曜から月曜に変更"
        return
    ok, gaps = c.span_gaps("WORD", 0, 0, len(units) - 1)
    assert ok
    mine_gaps = ["".join(t.s for t in toks if mine[k].b <= t.a and t.b <= mine[k + 1].a) for k in range(len(mine) - 1)]
    assert mine_gaps == gaps


def test_the_gap_judgement_is_todays_span_inexpressible():
    """A single-clause sentence is F0 gap_is_not_a_particle exactly when the loom's weave_span would refuse it for a gap that is not a particle."""
    for s, refused in (("担当表では認証モジュール担当は田中です", True), ("会議の開催も不明", True), ("障害訓練の開催地は大阪", False), ("田中が営業部で資料を作成した", False)):
        c = one(s)
        assert (c.reason == "gap_is_not_a_particle") is refused, s


# -- the record --------------------------------------------------------------------------------------------------------------------------------------
def test_to_obj_is_json_and_stable():
    e = ms.exchange("A社のB事業の担当は田中です。会議を開く")
    o = e.to_obj()
    s = json.dumps(o, ensure_ascii=False, sort_keys=True)
    assert json.loads(s) == o and o["v"] == "shape.v1" and [c["shape"] for c in o["clauses"]] == ["F1", "F4"]
    assert ms.shapes_of("A社のB事業の担当は田中です。会議を開く") == ("F1", "F4")
    assert ms.exchange("A社のB事業の担当は田中です。会議を開く") == e


def test_the_exchanger_is_pure_the_same_answer_twice_and_no_state():
    a = ms.exchange("会議は東京で開催する")
    ms.exchange("全然別の文は不明")
    assert ms.exchange("会議は東京で開催する") == a


MEM_PURITY_FORBIDDEN_IMPORTS = {"time", "datetime", "random", "subprocess", "socket", "os", "sys", "uuid", "secrets"}


def test_memshape_has_no_clock_float_process_or_environment():
    src = open(os.path.join(ROOT, "verantyx", "loom", "memshape.py"), encoding="utf-8").read()
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            assert not ({a.name.split(".")[0] for a in n.names} & MEM_PURITY_FORBIDDEN_IMPORTS)
        if isinstance(n, ast.ImportFrom) and n.module:
            assert n.module.split(".")[0] not in MEM_PURITY_FORBIDDEN_IMPORTS
        if isinstance(n, ast.Constant):
            assert not isinstance(n.value, float)
        if isinstance(n, ast.Name):
            assert n.id not in ("float", "set", "frozenset", "eval", "exec", "open", "print")
        if isinstance(n, ast.Div):
            raise AssertionError("true division")


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_byte_identical_across_hash_seeds(seed):
    code = ("import json;from verantyx.loom import memshape as ms;"
            "S=['障害訓練の開催地は大阪','A社のB事業の担当は田中です。会議を開く','田中が営業部で資料を作成した','担当表では認証モジュール担当は田中です','QA締切は6/12から6/14に変更になりました','監視設定メモ: 本番ポートは8443、検証は8088です'];"
            "print(ms.SHAPES_SHA);print(json.dumps([ms.exchange(s).to_obj() for s in S],ensure_ascii=False,sort_keys=True))")
    env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT, check=True).stdout
    ref = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=dict(env, PYTHONHASHSEED="0"), cwd=ROOT, check=True).stdout
    assert out == ref and out.startswith(ms.SHAPES_SHA)
