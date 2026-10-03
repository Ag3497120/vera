"""W3-a4 (docs section 12.17): a common noun + する is counted as one predicate use and its argument chains
go to ``chain_sahen`` (never to ``chain``).  Sentences go through the real tagger and ``analyze``."""
import json
import pickle
from collections import Counter

import fugashi

from tools import build_coarse_placement as bcp

TAGGER = fugashi.Tagger()
SAHEN_KEYS = ("chain_sahen", "sahen_chain_skips", "sahen_verb")


def run(text):
    acc = bcp._empty_acc()
    bcp.analyze(bcp.tokenize(TAGGER, text), acc, 12)
    return acc


def test_a_common_noun_and_suru_is_one_predicate_use_and_its_chain_is_apart():
    a = run("係がデータを確認した。")
    assert a["pos"][("確認する", "V")] == 1
    assert a["sahen_verb"]["確認する"] == 1
    assert a["pos"][("する", "V")] == 0                       # する itself is still not counted
    assert a["pos"][("確認", "N")] == 1 and a["sahen"]["確認"] == 1     # the noun's own votes stay
    assert a["chain_sahen"][("係", "係", "が", "確認する", True)] == 1
    assert a["chain_sahen"][("データ", "データ", "を", "確認する", True)] == 1
    assert not a["chain"]
    assert a["chain_skips"]["sahen"] == 2
    assert a["sahen_chain_skips"]["counted"] == 2


def test_the_noun_side_is_the_same_as_before_the_change():
    # the noun keeps its role vote with the first verb (する) and its sahen vote
    a = run("係がデータを確認した。")
    assert not [k for k in a["occ"] if k[0] == "確認"]
    assert a["occ"][("データ", "を", "する")] == 1
    assert a["occ"][("係", "が", "する")] == 1


def test_passive_and_causative_count_the_use_but_not_the_chain():
    for text in ("資料が確認された。", "部下に確認させた。"):
        a = run(text)
        assert a["sahen_verb"]["確認する"] == 1, text
        assert a["pos"][("確認する", "V")] == 1, text
        assert not a["chain_sahen"] and not a["chain"], text
        assert a["sahen_chain_skips"]["voice"] >= 1, text


def test_a_noun_plus_wo_suru_is_still_the_verb_suru():
    a = run("太郎が勉強をした。")
    assert not a["sahen_verb"] and not a["chain_sahen"]
    assert a["chain"][("勉強", "勉強", "を", "する", True)] == 1
    assert a["chain"][("太郎", "太郎", "が", "する", True)] == 1
    assert a["pos"][("する", "V")] == 1


def test_a_proper_noun_or_a_run_that_ends_in_a_suffix_is_no_sahen_predicate():
    a = run("東京する。")
    assert not a["sahen_verb"] and a["pos"][("する", "V")] == 0
    b = run("太郎が報告書した。")
    assert not b["sahen_verb"] and not b["chain_sahen"]
    assert b["sahen_chain_skips"]["no_common_noun"] == 1 and b["chain_skips"]["sahen"] == 1
    assert b["pos"][("する", "V")] == 1                       # the suffix is no noun token: する is counted as before


def test_a_noun_plus_dekiru_is_the_verb_dekiru_as_before():
    a = run("彼が確認できる。")
    assert not a["sahen_verb"] and a["pos"][("できる", "V")] == 1


def test_a_headword_longer_than_the_limit_is_not_counted():
    acc = bcp._empty_acc()
    bcp.analyze(bcp.tokenize(TAGGER, "係がデータを確認した。"), acc, 3)      # 確認する is 4 characters
    assert not acc["sahen_verb"] and ("確認する", "V") not in acc["pos"]
    assert acc["sahen_chain_skips"]["too_long"] == 2 and acc["chain_skips"]["sahen"] == 2


def test_the_funnel_invariant_holds_over_several_sentences():
    acc = bcp._empty_acc()
    for t in ("係がデータを確認した。", "資料が確認された。", "太郎が報告書した。", "部長が部下に結果を報告した。",
              "彼が確認して帰った。", "部下に確認させた。", "東京する。", "太郎が勉強をした。"):
        bcp.analyze(bcp.tokenize(TAGGER, t), acc, 12)
    assert sum(acc["sahen_chain_skips"].values()) == acc["chain_skips"]["sahen"] > 0
    assert set(acc["sahen_chain_skips"]) <= {"counted", "voice", "no_common_noun", "too_long"}


def test_empty_acc_has_the_new_keys_and_they_accumulate():
    a = bcp._empty_acc()
    for k in SAHEN_KEYS:
        assert isinstance(a[k], Counter)
    x, y = run("係がデータを確認した。"), run("係がデータを確認した。")
    x["chain_sahen"].update(y["chain_sahen"])
    assert x["chain_sahen"][("係", "係", "が", "確認する", True)] == 2


def test_a_cache_without_the_new_keys_stops_with_exit_4_and_names_exactly_them(tmp_path, capsys):
    pkl = tmp_path / "w3a3.pkl"
    old = {"occ": {}, "pos": {}, "sahen": {}, "counters": {}, "counters2": {}, "counter_nums": {},
           "chain": {}, "chain_skips": {},
           "defs": [], "aliases": [], "paren_aliases": [], "hearst": {}, "inputs": [], "skips": {}, "excl": {}}
    with open(pkl, "wb") as f:
        pickle.dump(old, f)
    out_dir = tmp_path / "out"
    rc = bcp.main(["build", "--jawiki", str(tmp_path / "none.jsonl"), "--out", str(out_dir),
                   "--stage-cache", str(pkl)])
    assert rc == bcp.EXIT_STAGE_CACHE_STALE == 4
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["state"] == "STAGE_CACHE_STALE" and set(out["missing"]) == set(SAHEN_KEYS)
    assert not out_dir.exists()
