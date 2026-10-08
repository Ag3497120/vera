"""W3-a3: the argument chains of ``analyze`` (docs section 12.3) and the stale-cache stop.

Synthetic sentences go through the real tagger and ``analyze``; nothing here is a test-data word."""
import json
import pickle
from collections import Counter

import fugashi
import pytest

from tools import build_coarse_placement as bcp

TAGGER = fugashi.Tagger()


def run(text):
    acc = bcp._empty_acc()
    bcp.analyze(bcp.tokenize(TAGGER, text), acc, 12)
    return acc


def chains(text):
    return dict(run(text)["chain"])


def skips(text):
    return dict(run(text)["chain_skips"])


def test_a_pair_then_a_verb_is_counted_with_the_filler_the_mark_and_the_verb():
    c = chains("太郎が学校へ行った。")
    assert c[("太郎", "太郎", "が", "行く", True)] == 1
    assert c[("学校", "学校", "へ", "行く", True)] == 1
    assert len(c) == 2


def test_two_pairs_between_the_mark_and_the_verb_are_walked_over():
    c = chains("先生が生徒に本を渡した。")
    assert {k[:3] for k in c} == {("先生", "先生", "が"), ("生徒", "生徒", "に"), ("本", "本", "を")}
    assert all(k[3] == "渡す" for k in c)


def test_a_fourth_pair_is_not_counted_and_the_reason_is_counted():
    text = "太郎が次郎に本を庭で駅へ走った。"
    c, sk = chains(text), skips(text)
    assert not [k for k in c if k[0] == "太郎"]            # four pairs after the mark: too many
    assert sk.get("too_many_args") == 1
    assert ("次郎", "次郎", "に", "走る", True) in c         # three pairs from the next run: counted


def test_a_comma_an_adverb_or_a_missing_particle_breaks_the_chain_and_is_counted():
    for text in ("太郎が、走った。", "太郎が急に走った。", "太郎が犬走った。"):
        c, sk = chains(text), skips(text)
        assert not [k for k in c if k[0] == "太郎"], text
        assert sk.get("chain_broken", 0) >= 1, text
    # a topic marker and の are not marks, and a run followed by は breaks a chain
    assert not [k for k in chains("太郎は学校へ行った。") if k[0] == "太郎"]
    assert [k for k in chains("太郎の弟が学校へ行った。") if k[0] == "弟"]


def test_no_verb_at_the_end_of_the_text_is_counted():
    assert skips("太郎が学校へ。").get("no_verb", 0) >= 1
    assert skips("太郎が学校へ").get("no_verb", 0) >= 1


def test_a_verbal_noun_with_suru_is_not_counted_but_wo_suru_is():
    assert not chains("太郎が勉強した。") and skips("太郎が勉強した。").get("sahen") == 1
    c = chains("太郎が勉強をした。")
    assert c.get(("勉強", "勉強", "を", "する", True)) == 1


def test_a_voice_auxiliary_after_the_verb_is_not_counted():
    for text in ("太郎が次郎に殴られた。", "子供が野菜を食べさせた。", "先生に本を読ませた。"):
        assert not chains(text), text
        assert skips(text).get("voice", 0) >= 1, text
    assert chains("子供が野菜を食べた。")                       # the plain form is


def test_the_past_mark_is_the_ta_auxiliary_after_the_verb():
    assert chains("学校へ行った。")[("学校", "学校", "へ", "行く", True)] == 1
    assert chains("学校へ行く。")[("学校", "学校", "へ", "行く", False)] == 1
    assert chains("学校へ行かなかった。")[("学校", "学校", "へ", "行く", True)] == 1   # a negated past is a past
    assert chains("学校へ行っていた。")[("学校", "学校", "へ", "行く", False)] == 1    # "te iru": the verb is first


def test_a_comma_is_a_mark_written_as_empty_and_it_chains_on():
    c = chains("昨日、学校へ行った。")
    assert c[("昨日", "昨日", "∅", "行く", True)] == 1
    assert c[("学校", "学校", "へ", "行く", True)] == 1


def test_a_run_that_starts_with_a_numeral_is_not_counted():
    c, sk = chains("三人が走った。"), skips("三人が走った。")
    assert not [k for k in c if k[0].startswith("三")] and sk.get("numeral_start", 0) >= 1


def test_the_whole_run_and_its_last_noun_are_both_kept():
    # the same two words ``occ`` keeps: the run as written and its last NOUN token (a suffix is no head)
    keys = [k for k in chains("日本料理が好きだ。太郎が日本料理を食べた。") if k[2] == "を"]
    assert len(keys) == 1 and keys[0][0] == "日本料理" and keys[0][1] == "料理"
    keys = [k for k in chains("日本料理店が開いた。") if k[2] == "が"]
    assert len(keys) == 1 and keys[0][0] == "日本料理店" and keys[0][1] == ""      # ends in a suffix: no head


def test_counts_are_per_source_accumulators_and_empty_acc_has_the_keys():
    a = bcp._empty_acc()
    assert isinstance(a["chain"], Counter) and isinstance(a["chain_skips"], Counter)
    x, y = run("学校へ行った。"), run("学校へ行った。")
    x["chain"].update(y["chain"])
    assert x["chain"][("学校", "学校", "へ", "行く", True)] == 2


def test_an_old_extraction_cache_stops_with_a_typed_reason_and_exit_4(tmp_path, capsys):
    pkl = tmp_path / "old.pkl"
    old = {"occ": {}, "pos": {}, "sahen": {}, "counters": {}, "counters2": {}, "counter_nums": {},
           "defs": [], "aliases": [], "paren_aliases": [], "hearst": {}, "inputs": [], "skips": {}, "excl": {}}
    with open(pkl, "wb") as f:
        pickle.dump(old, f)
    rc = bcp.main(["build", "--jawiki", str(tmp_path / "none.jsonl"), "--out", str(tmp_path / "out"),
                   "--stage-cache", str(pkl)])
    assert rc == bcp.EXIT_STAGE_CACHE_STALE == 4
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["state"] == "STAGE_CACHE_STALE" and set(out["missing"]) == {"chain", "chain_skips"}
    assert not (tmp_path / "out").exists()                      # nothing was built
