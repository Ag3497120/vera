"""Adversarial, spec-driven checks for coordinated predicate scope."""

import pytest

from verantyx.one import Vera


def ask(doc, question):
    v = Vera.from_texts({"d": doc}, mode="semantic")
    try:
        return v.ask(question)
    finally:
        v.close()


def val(answer):
    return answer.get("verdict"), answer.get("values")


# Expected values below are derived by hand from the sentence and the feature
# specification: a plain te/renyō chain makes one clause per predicate, and a
# topic subject may carry forward only when a later clause has no own subject.
ANSWER_CASES = [
    # Two clauses: renyō + 、, shared topic subject, all three roles per clause.
    ("two_renyo_agent_first", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "誰が装置Zをカイに貸した？", ["ユラ"]),
    ("two_renyo_patient_first", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "何を貸した？", ["装置Z"]),
    ("two_renyo_recipient_first", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "装置Zを誰に貸した？", ["カイ"]),
    ("two_renyo_agent_second", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "誰が装置Yをメイに返した？", ["ユラ"]),
    ("two_renyo_patient_second", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "何を返した？", ["装置Y"]),
    ("two_renyo_recipient_second", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "装置Yを誰に返した？", ["メイ"]),
    # Same roles with a te-form connective.
    ("two_te_agent_first", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "誰が箱Aをケンに渡した？", ["アキ"]),
    ("two_te_patient_first", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "何を渡した？", ["箱A"]),
    ("two_te_recipient_first", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "箱Aを誰に渡した？", ["ケン"]),
    ("two_te_agent_second", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "誰が箱Bをレイに送った？", ["アキ"]),
    ("two_te_patient_second", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "何を送った？", ["箱B"]),
    ("two_te_recipient_second", "アキは箱Aをケンに渡して、箱Bをレイに送った。", "箱Bを誰に送った？", ["レイ"]),
    # Two-clause chain with another vocabulary set and reversed target order.
    ("two_other_agent_first", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "誰が鍵Cをオウに渡した？", ["リサ"]),
    ("two_other_patient_first", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "何を渡した？", ["鍵C"]),
    ("two_other_recipient_first", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "鍵Cを誰に渡した？", ["オウ"]),
    ("two_other_agent_second", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "誰が地図Dをナオに預けた？", ["リサ"]),
    ("two_other_patient_second", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "何を預けた？", ["地図D"]),
    ("two_other_recipient_second", "リサは鍵Cをオウに渡し、地図Dをナオに預けた。", "地図Dを誰に預けた？", ["ナオ"]),
    # Explicit subject of the later clause replaces the shared topic there.
    ("own_subject_first_agent", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "誰が地図をトモに見せた？", ["マキ"]),
    ("own_subject_first_patient", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "何を見せた？", ["地図"]),
    ("own_subject_first_recipient", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "地図を誰に見せた？", ["トモ"]),
    ("own_subject_second_agent", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "誰が鍵をリョウに渡した？", ["ミナ"]),
    ("own_subject_second_patient", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "何を渡した？", ["鍵"]),
    ("own_subject_second_recipient", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "鍵を誰に渡した？", ["リョウ"]),
    # Three predicates: every question selects the clause by its predicate or patient.
    ("three_agent_one", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "誰が地図を見せた？", ["マキ"]),
    ("three_patient_one", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "何を見せた？", ["地図"]),
    ("three_recipient_one", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "地図を誰に見せた？", ["トモ"]),
    ("three_agent_two", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "誰が鍵を渡した？", ["マキ"]),
    ("three_patient_two", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "何を渡した？", ["鍵"]),
    ("three_recipient_two", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "鍵を誰に渡した？", ["リョウ"]),
    ("three_agent_three", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "誰が箱を預けた？", ["マキ"]),
    ("three_patient_three", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "何を預けた？", ["箱"]),
    ("three_recipient_three", "マキは地図をトモに見せ、鍵をリョウに渡し、箱をナオに預けた。", "箱を誰に預けた？", ["ナオ"]),
    # Four predicates: roles in each clause remain local across a longer chain.
    ("four_agent_one", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "誰が本Aを渡した？", ["ヒナ"]),
    ("four_patient_one", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "何を渡した？", ["本A"]),
    ("four_recipient_one", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "本Aを誰に渡した？", ["イオ"]),
    ("four_agent_two", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "誰が本Bを届けた？", ["ヒナ"]),
    ("four_patient_two", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "何を届けた？", ["本B"]),
    ("four_recipient_two", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "本Bを誰に届けた？", ["ウメ"]),
    ("four_agent_three", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "誰が本Cを貸した？", ["ヒナ"]),  
    ("four_patient_three", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "何を貸した？", ["本C"]),  
    ("four_recipient_three", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "本Cを誰に貸した？", ["ルイ"]),  
    ("four_agent_four", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "誰が本Dを預けた？", ["ヒナ"]),
    ("four_patient_four", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "何を預けた？", ["本D"]),
    ("four_recipient_four", "ヒナは本Aをイオに渡し、本Bをウメに届け、本Cをルイに貸し、本Dをメイに預けた。", "本Dを誰に預けた？", ["メイ"]),
    # A で-phrase belongs to its own predicate; it is not borrowed by the other clause.
    ("te_location_first", "ソラは工具Pを工房Fで使って、箱Qをナオに渡した。", "工具Pをどこで使った？", ["工房F"]),
    ("te_location_second", "ソラは工具Pを工房Fで使って、箱Qをナオに渡した。", "箱Qを誰に渡した？", ["ナオ"]),
    # Same-meaning surface variants and reordered clauses retain the right bindings.
    ("variant_te_same_lend", "ユラは装置Zをカイに貸して、装置Yをメイに返した。", "装置Zを誰に貸した？", ["カイ"]),
    ("variant_reordered_return_first", "ユラは装置Yをメイに返し、装置Zをカイに貸した。", "装置Yを誰に返した？", ["メイ"]),
    ("variant_reordered_lend_second", "ユラは装置Yをメイに返し、装置Zをカイに貸した。", "装置Zを誰に貸した？", ["カイ"]),
    ("variant_names_objects", "ノアは装置Rをユキに貸し、装置Sをレオに返した。", "装置Sを誰に返した？", ["レオ"]),
    # A single changed noun changes the corresponding answer.
    ("swap_recipient_kai", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "装置Zを誰に貸した？", ["カイ"]),
    ("swap_recipient_ren", "ユラは装置Zをレンに貸し、装置Yをメイに返した。", "装置Zを誰に貸した？", ["レン"]),
    ("swap_patient_y", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "何を返した？", ["装置Y"]),
    ("swap_patient_x", "ユラは装置Zをカイに貸し、装置Xをメイに返した。", "何を返した？", ["装置X"]),
    # Yes/no questions: truth and falsity are both grounded in a single clause.
    ("yes_shared_later_clause", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "ユラは装置Yをメイに返した？", ["はい"]),
    ("yes_own_subject_clause", "マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "ミナは鍵をリョウに渡した？", ["はい"]),
]


@pytest.mark.parametrize("case,doc,question,expected", ANSWER_CASES, ids=[r[0] for r in ANSWER_CASES])
def test_plain_predicate_coordination_answers_clause_local_roles(case, doc, question, expected):
    assert val(ask(doc, question)) == ("ANSWER", expected)


# No question below has an answer licensed by one clause plus the allowed
# shared topic. In particular, particles or subjects must not cross a boundary
# introduced by anything other than plain te/renyō predicate coordination.
ABSTAIN_CASES = [
    # Adversative が, including the specified negative/positive contrast.
    ("adversative_subject_share", "マキは地図をトモに見せたが、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("adversative_subject_share_2", "ユラは箱Aをカイに送ったが、箱Bをメイに返した。", "誰が箱Bをメイに返した？"),
    ("negative_positive_contrast", "ユキは青箱を運ばなかったが、白箱を運んだ。", "誰が白箱を運んだ？"),
    ("negative_positive_contrast_2", "アキは鍵Aを渡さなかったが、鍵Bを渡した。", "誰が鍵Bを渡した？"),
    # Causal ので and から.
    ("causal_node", "マキは雨が降ったので、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("causal_node_2", "ユラは道が混んだので、箱をメイに運んだ。", "誰が箱をメイに運んだ？"),
    ("causal_kara", "マキは荷物が届いたから、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    ("causal_kara_2", "ソラは倉庫が暗かったから、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    # Conditional ば / たら / なら / と.
    ("conditional_ba", "マキが急げば、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    ("conditional_ba_2", "ユキが着けば、鍵をリョウに渡す。", "誰が鍵をリョウに渡す？"),
    ("conditional_tara", "マキが来たら、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    ("conditional_tara_2", "ユキが着いたら、鍵をリョウに渡す。", "誰が鍵をリョウに渡す？"),
    ("conditional_nara", "マキが来るなら、箱をナオに預ける。", "誰が箱をナオに預ける？"),
    ("conditional_nara_2", "ユキが着くなら、鍵をリョウに渡す。", "誰が鍵をリョウに渡す？"),
    ("conditional_to", "マキが来ると、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    ("conditional_to_2", "ユキが着くと、鍵をリョウに渡す。", "誰が鍵をリョウに渡す？"),
    # Concessive のに / ても.
    ("concessive_noni", "マキは忙しかったのに、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("concessive_temo", "マキが疲れていても、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("concessive_temo_2", "ユラが忙しくても、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    # Quoted content cannot supply the subject of the unquoted predicate.
    ("quoted_subject_does_not_escape", "「マキは箱Aを運んだ」と言い、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("quoted_subject_does_not_escape_2", "「ユラは地図を見せた」と書き、箱をナオに預けた。", "誰が箱をナオに預けた？"),
    # Hedges are not factual clauses that license topic-subject sharing.
    ("hedge_kamo_shirenai", "マキは地図を見せるかもしれないが、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("hedge_kamo_shirenu", "ユラは箱を預けるかもしれず、鍵をナオに渡した。", "誰が鍵をナオに渡した？"),
    ("hedge_darou", "マキは地図を見せるだろうが、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("hedge_daroushi", "ユラは箱を預けるだろうし、鍵をナオに渡す。", "誰が鍵をナオに渡す？"),
    ("hedge_hazu", "マキは地図を見せるはずだが、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("hedge_hazude", "ユラは箱を預けたはずで、鍵をナオに渡した。", "誰が鍵をナオに渡した？"),
    # Volitional meaning is not an asserted coordinated event.
    ("volitional_to_suru", "マキは地図を見せようとして、鍵をリョウに渡した。", "誰が鍵をリョウに渡した？"),
    ("volitional_chain", "ユラは箱を預けようとし、鍵をナオに渡した。", "誰が鍵をナオに渡した？"),
    # A later clause may not borrow earlier particles or objects.
    ("no_recipient_borrowing", "ユラは装置Zをカイに貸し、装置Yを返した。", "装置Yを誰に返した？"),
    ("no_patient_borrowing", "ユラは装置Zをカイに貸し、メイに返した。", "何を誰に返した？"),
    ("no_cross_clause_patient", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "装置Yを誰に貸した？"),
    ("no_cross_clause_recipient", "ユラは装置Zをカイに貸し、装置Yをメイに返した。", "装置Zを誰に返した？"),
    # A later explicit subject does not leak backward into an earlier clause.
    ("later_subject_not_backward", "箱Aを運び、ミナは箱Bを置いた。", "誰が箱Aを運んだ？"),
    ("later_subject_not_backward_2", "鍵を渡し、ユキは地図をトモに見せた。", "誰が鍵を渡した？"),
    # The later メイに phrase is compatible with either verb; it belongs only
    # to 返す by clause-local position and cannot fill 貸す's missing recipient.
    ("ambiguous_late_recipient", "ユラは装置Zを貸し、装置Yをメイに返した。", "装置Zを誰に貸した？"),
]


@pytest.mark.parametrize("case,doc,question", ABSTAIN_CASES, ids=[r[0] for r in ABSTAIN_CASES])
def test_non_coordination_or_cross_clause_inference_abstains(case, doc, question):
    answer = ask(doc, question)
    assert answer.get("verdict") != "ANSWER", answer



# SPEC CORRECTED (Claude). (1) The system is open-world: an unstated fact is UNKNOWN, never 'いいえ'; "no" needs a stated negative fact.
@pytest.mark.parametrize("doc,q", [
    ("ユラは装置Zをカイに貸し、装置Yをメイに返した。", "ユラは装置Yをカイに返した？"),
    ("ユラは装置Zをカイに貸し、装置Yをメイに返した。", "ユラは装置Zをメイに貸した？"),
    ("マキは地図をトモに見せ、ミナは鍵をリョウに渡した。", "マキは鍵をリョウに渡した？"),
])
def test_unstated_combinations_are_unknown_not_no(doc, q):
    assert ask(doc, q)["verdict"] != "ANSWER"


# (2) 疲れていたのに、…: the topic subject scopes over the main clause; the old single-Frame reading answers ユラ, which is the true value.
def test_concessive_main_clause_keeps_the_topic_subject():
    a = ask("ユラは疲れていたのに、箱をナオに預けた。", "誰が箱をナオに預けた？")
    assert a["verdict"] == "ANSWER" and a["values"] == ["ユラ"]
