"""S2: 正規化・文字列の採点規則（合格例と不合格例）。"""
from tools.bank_score import checks as C
from tools.bank_score import lemma
from tools.bank_score.normalize import (char_count, detect_language, norm, split_sentences)

P, F, U = C.PASS, C.FAIL, C.UNJUDGED


# ---- 正規化 --------------------------------------------------------------------
def test_norm_nfkc_case_space_punct():
    assert norm("  ＡＢＣ　ｄｅｆ。 ") == "abc def"
    assert norm("「月曜日」！") == "月曜日"
    assert norm("Monday.") == norm("monday")
    assert norm("３．５") == "3.5"  # 数字中の句読点は内側なので残る


def test_norm_internal_punct_kept_edges_stripped():
    assert norm("a, b") == "a, b"
    assert norm("...a...") == "a"


def test_norm_non_string_is_empty():
    assert norm(None) == ""


def test_char_count_nfkc_and_strip():
    assert char_count("  ＡＢ　") == 2
    assert char_count("あいう") == 3


def test_split_sentences_terminators_and_numbers():
    assert split_sentences("今日は晴れ。明日は雨！本当？") == ["今日は晴れ", "明日は雨", "本当"]
    assert split_sentences("Pi is 3.14 and more. It is long.") == ["Pi is 3.14 and more", "It is long"]
    # 規則どおり、前が数字の `.` は文末としない（"Total 5. Next" は分けない。既知の限界として docs に書く）
    assert split_sentences("Total 5. Next") == ["Total 5. Next"]
    assert split_sentences("一行目\n二行目\n\n三行目") == ["一行目", "二行目", "三行目"]
    assert split_sentences("") == []
    assert split_sentences("。。。") == []


def test_detect_language():
    assert detect_language("こんにちは") == "ja"
    assert detect_language("Hello there") == "en"
    assert detect_language("漢字のみ") == "ja"  # 仮名「の」を含む
    assert detect_language("日本語") is None  # 漢字だけ
    assert detect_language("1234") is None


# ---- must_contain_any: 外側は全部必須、内側はどれか 1 つ ------------------------
def test_must_contain_any_outer_all_inner_any_pass():
    r = C.check_must_contain_any([["月曜", "Monday"], ["休館"]], "図書館は月曜日に休館します。")
    assert r["result"] == P


def test_must_contain_any_outer_missing_group_fails():
    r = C.check_must_contain_any([["月曜", "Monday"], ["休館"]], "図書館は月曜日に開館します。")
    assert r["result"] == F
    assert r["detail"]["missing_groups"] == [["休館"]]


def test_must_contain_any_two_singleton_groups_both_required():
    # B2_chat.md の例 [["月曜日"],["Monday"]] は V2 の読み方では「両方必須」
    assert C.check_must_contain_any([["月曜日"], ["Monday"]], "月曜日です")["result"] == F
    assert C.check_must_contain_any([["月曜日"], ["Monday"]], "月曜日 (Monday) です")["result"] == P


def test_must_contain_normalizes_case_width_and_edges():
    assert C.check_must_contain_any([["ＭＯＮＤＡＹ"]], "it is monday.")["result"] == P


def test_must_contain_all_and_must_not_contain():
    assert C.check_must_contain_all(["水筒", "帽子"], "水筒と帽子")["result"] == P
    assert C.check_must_contain_all(["水筒", "帽子"], "水筒だけ")["result"] == F
    assert C.check_must_not_contain(["手紙"], "手紙を書く")["result"] == F
    assert C.check_must_not_contain(["手紙"], "物語を書く")["result"] == P


# ---- must_not_equal -------------------------------------------------------------
def test_must_not_equal_whole_and_sentence_copy_fail():
    doc = "図書館は火曜日が休室日です。開室は十時からです。"
    assert C.check_must_not_equal(True, "図書館は火曜日が休室日です。", [doc])["result"] == F
    # 出力の一文が文書の一文と一致
    assert C.check_must_not_equal(True, "火曜です。開室は十時からです", [doc])["result"] == F
    assert C.check_must_not_equal(True, doc, [doc])["result"] == F


def test_must_not_equal_paraphrase_passes_and_explicit_list():
    doc = "図書館は火曜日が休室日です。"
    assert C.check_must_not_equal(True, "休みは火曜日です。", [doc])["result"] == P
    assert C.check_must_not_equal(["休みは火曜日です"], "休みは火曜日です。", [doc])["result"] == F
    assert C.check_must_not_equal(False, doc, [doc]) is None


def test_must_not_equal_empty_output_does_not_match():
    assert C.check_must_not_equal(True, "", ["何か。"])["result"] == P


# ---- max_chars・文数・言語・圧縮・形式 ------------------------------------------
def test_max_chars_pass_fail_and_boundary():
    assert C.check_max_chars(5, "あいうえお")["result"] == P
    assert C.check_max_chars(5, "あいうえおか")["result"] == F
    assert C.check_max_chars(5, "  ＡＢＣＤＥ  ")["result"] == P


def test_sentence_count_pass_fail():
    assert C.check_count({"min": 2, "max": 3}, len(split_sentences("一つ。二つ。")), "n")["result"] == P
    assert C.check_count({"min": 2, "max": 3}, len(split_sentences("一つ。")), "n")["result"] == F
    assert C.check_count({"min": 2, "max": 3}, len(split_sentences("あ。い。う。え。")), "n")["result"] == F


def test_language_pass_fail_unjudged():
    assert C.check_language("ja", "こんにちは")["result"] == P
    assert C.check_language("en", "こんにちは")["result"] == F
    assert C.check_language("ja", "日本語")["result"] == U


def test_compression_pass_fail_unjudged():
    mats = ["あ" * 100]
    assert C.check_compression(0.5, "い" * 40, mats)["result"] == P
    assert C.check_compression(0.5, "い" * 60, mats)["result"] == F
    assert C.check_compression(0.5, "い", [""])["result"] == U


def test_form_bullets_pass_fail_and_haiku_needs_reader():
    assert C.check_form("bullets", "・水筒\n・帽子\n・タオル")["result"] == P
    assert C.check_form("bullets", "水筒と帽子")["result"] == F
    assert C.check_form("bullets", "・水筒\n説明の行")["result"] == F
    assert C.check_form("箇条書き", "1. a\n2. b")["result"] == P
    assert C.check_form("haiku", "古池や")["result"] == U


# ---- 辞書形での順序 -------------------------------------------------------------
def test_lemma_forms_cover_closed_table():
    assert "増やし" in lemma.ja_forms("増やす")  # 五段 す
    assert "開け" in lemma.ja_forms("開ける")  # 一段
    assert "割引にな" in lemma.ja_forms("割引になる")
    assert "勉強し" in lemma.ja_forms("勉強する")  # サ変
    assert "来た" in lemma.ja_forms("来る")  # カ変
    assert "高かっ" in lemma.ja_forms("高い")  # 形容詞
    assert "書い" in lemma.ja_forms("書く") and "読ん" in lemma.ja_forms("読む") and "待っ" in lemma.ja_forms("待つ")
    assert "stopped" in lemma.en_forms("stop") and "making" in lemma.en_forms("make")
    assert "studies" in lemma.en_forms("study")


def test_find_positions_ja_en_and_kanji_guard():
    assert lemma.find_positions("先に増やしたので客が増えた", "増やす") == [2]
    assert lemma.find_positions("意見を聞く", "見る") == []  # 漢字の連なりの一部は除く
    assert lemma.find_positions("花を見た", "見る") == [2]
    assert lemma.find_positions("She opened it and closes it", "open") == [4]
    assert lemma.find_positions("reopened", "open") == []  # 語境界


def test_order_pass_ja():
    assert C.check_order(["開ける", "閉める"], "ミナは箱を開けた。それから窓を閉めた。")["result"] == P


def test_order_fail_ja_reversed():
    assert C.check_order(["開ける", "閉める"], "ミナは窓を閉めた。それから箱を開けた。")["result"] == F


def test_order_unjudged_mixed_occurrences_tie_is_not_broken():
    r = C.check_order(["開ける", "閉める"], "開けて、閉めて、また開けた。")
    assert r["result"] == U and r["detail"]["reason"] == "ORDER_MIXED_OR_OVERLAP"


def test_order_unjudged_when_lemma_not_found():
    r = C.check_order(["開ける", "閉める"], "箱を開けた。")
    assert r["result"] == U and r["detail"]["missing"] == ["閉める"]


def test_order_en_pass_fail():
    assert C.check_order(["load", "leave", "reach"], "The crew loads the truck, which leaves at six and reaches town.")["result"] == P
    assert C.check_order(["load", "leave"], "The truck leaves after the crew loaded it.")["result"] == F


def test_order_irregular_verb_is_unjudged_not_guessed():
    # 行く→行った は不規則変化なので表に無い。当てずに判定不能にする
    assert C.check_order(["行く", "帰る"], "学校に行った。それから家に帰った。")["result"] == U


# ---- 文のチェック（3 ラベル） ---------------------------------------------------
def test_labels_from_verdict_type_and_from_text():
    assert C.check_labels("anything", "REFUTED")[0] == "REFUTED"
    assert C.check_labels("The claim is SUPPORTED by the document.", None)[0] == "SUPPORTED"


def test_labels_three_listed_does_not_pass():
    lab, info = C.check_labels("SUPPORTED REFUTED NOT_IN_DOCS", None)
    assert lab is None and info["result"] == F
    assert C.check_labels("no label here", None)[0] is None


def test_labels_unsupported_word_is_not_a_label():
    assert C.check_labels("this is unsupported", None)[0] is None
