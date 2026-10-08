"""W3-d1 (K310, K311, K313): the forms table and its layers. The default table holds exactly the values that were in the code (copied here from base 6bc410d);
a layer can only add; an override is FORMS_OVERRIDE_REFUSED; the variable is read at every call."""
from __future__ import annotations

import copy
import itertools
import json
from dataclasses import replace
from pathlib import Path

import pytest

from verantyx import realize
from verantyx import semantic_realize as SR
from verantyx.semantic_reader import document_view

ART = Path(__file__).resolve().parents[1] / "artifacts" / "w3-d1"
OLD_ROLE_ORDER = ("recipient", "goal", "patient", "origin", "location")                                # copied from 6bc410d semantic_realize.py
OLD_ROLE_PARTICLE = {"recipient": "に", "goal": "へ", "patient": "を", "origin": "から", "location": "で"}
VERBS = ["渡す", "歩く", "行く", "出て行く", "食べる", "する", "勉強する", "来る", "くる", "買う", "書く", "泳ぐ", "話す", "待つ", "死ぬ", "飛ぶ", "読む", "帰る",
         "見る", "寝る", "考える", "答える", "歌う", "働く", "届ける", "開く", "押す", "立つ", "選ぶ", "笑う", "送る", "届く", "着る", "起きる", "出る", "入る",
         "走る", "案内する", "持ってくる", "連れて来る", "犬", "赤い", "ゔ", "あ"]


def one_clause(text: str):
    view = document_view({"doc": text})
    assert len(view.clauses) == 1
    return view.clauses[0]


@pytest.fixture(autouse=True)
def no_env_layer(monkeypatch):
    monkeypatch.delenv("VERA_REALIZE_FORMS", raising=False)


def base():
    return json.loads(Path(SR._FORMS_PATH).read_text(encoding="utf-8"))


def write(tmp_path, name, obj):
    path = tmp_path / name
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return path


def layer(**keys):
    out = {"schema": SR.FORMS_SCHEMA, "version": SR.REALIZE_FORMS_VERSION, "lang": "ja"}
    out.update(keys)
    return out


def test_the_default_table_holds_the_values_that_were_in_the_code():
    table = SR.load_forms()
    assert tuple(table["role_order"]) == OLD_ROLE_ORDER == SR._ROLE_ORDER
    assert table["role_particle"] == OLD_ROLE_PARTICLE == SR._ROLE_PARTICLE
    assert table["topic_particles"] == ["は", "が"] and list(table["styles"]) == ["plain", "polite"]
    assert table["version"] == SR.REALIZE_FORMS_VERSION == 1
    assert table["copula"] == {"topic": "は", "attribute_link": "の", "substance_link": "の"}
    assert table["styles"]["plain"]["copula"] == {"affirmative": "だ", "affirmative_adjective": "", "affirmative_aru": "である", "negative": "ではない"}
    assert table["styles"]["polite"]["copula"]["negative"] == "ではありません" and table["styles"]["polite"]["measure"] == "です"


@pytest.mark.parametrize("verb", VERBS)
def test_table_conjugation_is_the_old_conjugation_for_all_eight_combinations(verb):
    for past, neg, polite in itertools.product((False, True), repeat=3):
        try:
            old = realize.conjugate(verb, past=past, neg=neg, polite=polite)
        except Exception as exc:                                    # the old function raises for an empty/odd verb: the new one must raise the same way
            with pytest.raises(type(exc)):
                SR.conjugate_by_style(verb, "polite" if polite else "plain", past=past, neg=neg)
            continue
        assert SR.conjugate_by_style(verb, "polite" if polite else "plain", past=past, neg=neg) == old, (verb, past, neg, polite)


def test_the_quirks_of_the_old_conjugation_are_kept():
    assert SR.conjugate_by_style("出て行く", "plain", past=True) == "行った" == realize.conjugate("出て行く", past=True)
    assert SR.conjugate_by_style("ゔ", "plain") is None is realize.conjugate("ゔ")


def test_a_layer_that_adds_a_style_adds_variants_that_pass_the_checks(tmp_path):
    path = ART / "t3_layer_add_style.json"
    clause = replace(one_clause("マキがリオに青鍵を渡した。"), polarity="-", time="nonpast")
    base_texts = [x.text for x in SR.realize_variants(clause) if isinstance(x, SR.Realized)]
    layered = SR.realize_variants(clause, forms=str(path))
    texts = [x.text for x in layered if isinstance(x, SR.Realized)]
    assert set(base_texts) < set(texts) and len(texts) > len(base_texts)
    added = [x for x in layered if isinstance(x, SR.Realized) and x.style == "polite_casual"]
    assert added and all(x.text.endswith("渡さないです。") for x in added)
    assert all(x.checks["roundtrip"]["passed"] and x.checks["term_lineage"]["passed"] for x in added)         # emitted only because the checks passed
    one = SR.realize_clause(clause, "polite_casual", forms=str(path))
    assert isinstance(one, SR.Realized) and one.text == "マキはリオに青鍵を渡さないです。"
    assert SR.realize_clause(clause, "polite_casual").reason == "INVALID_STYLE"                         # without the layer the style is unknown
    assert SR.realize_clause(clause, "polite_casual").detail == "style must be plain or polite"


def test_a_style_added_by_a_layer_is_still_checked_by_the_unchanged_reader(tmp_path):
    bad = layer(styles={"broken": {"verb": {"affirmative": {"nonpast": ["dict", "ね"], "past": ["ta", "ね"]},
                                           "negative": {"nonpast": ["a", "ね"], "past": ["a", "ね"]}},
                                   "copula": {"affirmative": "だ", "affirmative_adjective": "", "affirmative_aru": "である", "negative": "ではない"},
                                   "measure": "だ", "period": "。"}})
    clause = one_clause("マキがリオに青鍵を渡した。")
    result = SR.realize_clause(clause, "broken", forms=write(tmp_path, "b.json", bad))
    assert isinstance(result, SR.Refused) and result.reason in ("ROUNDTRIP_MISMATCH", "TERM_LINEAGE_MISMATCH")


@pytest.mark.parametrize("name", ["t3_layer_override_particle.json", "t3_layer_override_style.json"])
def test_overrides_are_refused_as_a_whole(name):
    with pytest.raises(SR.FormsError) as err:
        SR.load_forms(str(ART / name))
    assert err.value.reason == "FORMS_OVERRIDE_REFUSED"
    assert SR.load_forms() == SR.base_forms()                       # nothing of the refused layer was loaded


def test_every_kind_of_override_is_refused(tmp_path):
    b = base()
    swapped_order = list(reversed(b["role_order"]))
    cases = {
        "patient_particle": layer(role_particle={"patient": "が"}),
        "swap_order": layer(role_order=swapped_order),
        "drop_first_order": layer(role_order=b["role_order"][1:]),
        "topic_order": layer(topic_particles=["が", "は"]),
        "topic_partial": layer(topic_particles=["が"]),
        "version": {**layer(), "version": 2},
        "style_value": layer(styles={"plain": {**b["styles"]["plain"], "period": "．"}}),
        "style_slot": layer(styles={"polite": {**b["styles"]["polite"], "measure": "でした"}}),
        "conjugation": layer(conjugation={**b["conjugation"], "suru": {**b["conjugation"]["suru"], "stem": "せ"}}),
        "copula": layer(copula={**b["copula"], "topic": "が"}),
        "mixed_valid_and_override": layer(role_particle={"instrument": "で", "patient": "が"}),
    }
    for label, content in cases.items():
        with pytest.raises(SR.FormsError) as err:
            SR.load_forms(write(tmp_path, label + ".json", content))
        assert err.value.reason == "FORMS_OVERRIDE_REFUSED", (label, err.value)


def test_additions_and_same_value_duplicates_are_allowed(tmp_path):
    b = base()
    ok = layer(role_particle={**b["role_particle"], "instrument": "で"}, role_order=b["role_order"] + ["instrument"], topic_particles=["は", "が", "も"])
    table = SR.load_forms(write(tmp_path, "ok.json", ok))
    assert table["role_particle"]["instrument"] == "で" and table["role_order"][-1] == "instrument" and table["topic_particles"] == ["は", "が", "も"]
    same = layer(styles={"plain": b["styles"]["plain"]}, role_particle=b["role_particle"], conjugation=b["conjugation"], copula=b["copula"])
    assert SR.load_forms(write(tmp_path, "same.json", same)) == SR.base_forms()
    only_new = layer(role_order=["instrument"])                    # entries that are all new are appended
    assert SR.load_forms(write(tmp_path, "new.json", only_new))["role_order"] == b["role_order"] + ["instrument"]


def test_invalid_layers_are_refused_with_their_own_type(tmp_path):
    b = base()
    style = copy.deepcopy(b["styles"]["polite"])
    missing = {k: v for k, v in style.items() if k != "period"}
    bad_stem = copy.deepcopy(style)
    bad_stem["verb"]["affirmative"]["nonpast"] = ["zzz", "ます"]
    cases = {
        "unknown_top_key": layer(read_back_rules={"x": 1}),
        "check_set_key": layer(_PARTICLES=["は"]),
        "missing_style_key": layer(styles={"extra": missing}),
        "unknown_style_key": layer(styles={"extra": {**style, "extra_key": 1}}),
        "bad_stem": layer(styles={"extra": bad_stem}),
        "not_an_object": [1, 2],
        "bad_schema": {**layer(), "schema": "other/1"},
        "bad_role_particle": layer(role_particle={"instrument": 3}),
        "dup_in_added": layer(role_order=["x", "x"]),
    }
    for label, content in cases.items():
        with pytest.raises(SR.FormsError) as err:
            SR.load_forms(write(tmp_path, label + ".json", content))
        assert err.value.reason == "FORMS_INVALID", (label, err.value)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(SR.FormsError) as err:
        SR.load_forms(str(broken))
    assert err.value.reason == "FORMS_INVALID"


def test_a_missing_path_is_forms_not_found(tmp_path):
    with pytest.raises(SR.FormsError) as err:
        SR.load_forms(str(tmp_path / "nope.json"))
    assert err.value.reason == "FORMS_NOT_FOUND"
    with pytest.raises(SR.FormsError):
        SR.realize_clause(one_clause("マキがリオに青鍵を渡した。"), "plain", forms=str(tmp_path / "nope.json"))


def test_the_variable_is_read_at_every_call(monkeypatch):
    clause = replace(one_clause("マキがリオに青鍵を渡した。"), polarity="-", time="nonpast")
    assert SR.realize_clause(clause, "polite_casual").reason == "INVALID_STYLE"
    monkeypatch.setenv("VERA_REALIZE_FORMS", str(ART / "t3_layer_add_style.json"))
    assert isinstance(SR.realize_clause(clause, "polite_casual"), SR.Realized)
    monkeypatch.setenv("VERA_REALIZE_FORMS", str(ART / "t3_layer_override_particle.json"))
    with pytest.raises(SR.FormsError):
        SR.realize_clause(clause, "plain")
    monkeypatch.delenv("VERA_REALIZE_FORMS")
    assert isinstance(SR.realize_clause(clause, "plain"), SR.Realized)
    monkeypatch.setenv("VERA_REALIZE_FORMS", "")                    # empty = no layer
    assert SR.load_forms() == SR.base_forms()


def test_several_layers_in_the_variable_are_applied_in_order(monkeypatch, tmp_path):
    import os
    extra = write(tmp_path, "extra.json", layer(role_particle={"instrument": "で"}))
    monkeypatch.setenv("VERA_REALIZE_FORMS", os.pathsep.join([str(ART / "t3_layer_add_style.json"), str(extra)]))
    table = SR.load_forms()
    assert "polite_casual" in table["styles"] and table["role_particle"]["instrument"] == "で"
    monkeypatch.setenv("VERA_REALIZE_FORMS", os.pathsep.join([str(extra), str(ART / "t3_layer_override_style.json")]))
    with pytest.raises(SR.FormsError) as err:
        SR.load_forms()
    assert err.value.reason == "FORMS_OVERRIDE_REFUSED"


def test_the_default_output_does_not_depend_on_a_layer_that_only_adds_a_role(tmp_path):
    clause = one_clause("マキがリオに青鍵を渡した。")
    extra = write(tmp_path, "extra.json", layer(role_particle={"instrument": "で"}))
    assert [x.as_dict() for x in SR.realize_variants(clause)] == [x.as_dict() for x in SR.realize_variants(clause, forms=str(extra))]
