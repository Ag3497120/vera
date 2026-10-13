"""LOOM-evidence-v5 (L-LOOM-219..): evidence.v5 = evidence.v4 PLUS two rules, from the one held-out failure of bank7 (B7-U43 「ネノの属するネノ県の人口は何人ですか？」, admitted by v2, v3 and v4: the
katakana name ネノ drops out of the question cut, the subject becomes the bare kind noun 県, and the title 「テレゴ県」 of another article read it).
  SU  a question whose subject phrase holds a piece the cut dropped (a katakana / kanji / Latin name) is refused `subject_unreadable`;
  TW  the article title stands in for a subject word only as a WHOLE word of the title, and a subject of kind words alone (県 市 駅 ...) is `question_has_no_subject`.
Selectable, NOT the default.  This file pins the freeze (v3 and v4 digests unchanged), the rules on real and toy questions, the dev-set probe (bank2, bank4, bank6, bank7) and the purity."""
import csv
import hashlib
import json
import os
import subprocess

import pytest

from verantyx.loom import evidence as ev
from verantyx.loom import ledger as lg
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from loom_common import CORPUS, PY, ROOT, rows

V2, V3, V4, V5 = ev.EVIDENCE_V2, ev.EVIDENCE_V3, ev.EVIDENCE_V4, ev.EVIDENCE_V5
EV5DIR = os.path.join(ROOT, "experiments/line3/loom/ev5")
BANK7_TSV = os.path.join(ROOT, "experiments/line3/bank7/bank7.tsv")

# ---- the freeze (recorded BEFORE any held-out bank8 probe; see L-LOOM-219..; to be recorded in docs/LINE3_LOCAL_DECISIONS.md after the CI run) ---------------------------------------------------------------------------
FROZEN_V3_RULES_DIGEST = "eca9ccd48aa6ddca8e74f33894acb380cc68667bd34950fd579c4e9bd9cf829d"
FROZEN_V4_RULES_DIGEST = "dae4c99ad17ee178249f83d3ba734cbb48f0ac1c1c336dd4866ecf0e5f915fc6"
FROZEN_V5_RULES_DIGEST = "355722c438c9ce917634a2abcaa3cb9ba785d945988af2e0b4aac9ab38c24ff4"
FROZEN_V5_EVIDENCE_SHA = "712249cc0cb481ea9c9b4dd60f3721b0d8db287062876c58f0cbde347a93efe6"


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def _toy(sents):
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "toy.jsonl")
    open(p, "w", encoding="utf-8").write("".join(json.dumps({"sha": hashlib.sha256(s.encode()).hexdigest(), "title": t, "sent": s, "source": "%s#%d" % (t, i)}, ensure_ascii=False) + "\n"
                                                  for i, (t, s) in enumerate(sents)))
    return p


def _passing(c, q, sid, version, scope=ev.SCOPE_TITLE):
    qu = ev.question_units(q)
    v = ev.view_of(c, sid)
    return [v.text[v.spans[i][0]:v.spans[j][1]] for i in range(len(v.units)) for j in range(i, len(v.units)) if not ev.judge_quote(c, qu, scope, sid, "WORD", i, j, version)["codes"]]


# ---- T-EV5-01: the freeze ------------------------------------------------------------------------------------------------------------------------------
def test_t_ev5_01_v3_and_v4_are_untouched_and_v5_is_frozen():
    assert ev.v3_rules_digest() == FROZEN_V3_RULES_DIGEST
    assert ev.v4_rules_digest() == FROZEN_V4_RULES_DIGEST
    assert ev.v5_rules_digest() == FROZEN_V5_RULES_DIGEST
    assert hashlib.sha256(open(os.path.join(ROOT, "verantyx/loom/evidence.py"), "rb").read()).hexdigest() == FROZEN_V5_EVIDENCE_SHA
    assert ev.V5_RULE_IDS == ev.V4_RULE_IDS + ("SU", "TW") and ev.V5_OFF == ev.V4_OFF == frozenset({"R7"})
    assert ev.V5_RULE_SENTENCE.startswith(ev.V4_RULE_SENTENCE)
    assert ev.KIND_REL <= ev.KIND_SUFFIX and {"県", "市", "区", "町", "村", "駅", "線", "社", "人", "年"} <= ev.KIND_SUFFIX
    assert "subject_unreadable" in ev.CODES


def test_t_ev5_01_v5_is_selectable_and_v2_stays_the_default_everywhere(tmp_path, monkeypatch):
    import inspect
    from verantyx import cli
    from verantyx.loom import mcp as lm
    from verantyx.loom.ops import EVIDENCE_RULE_V2, EVIDENCE_RULE_V5, EVIDENCE_RULES
    assert ev.EVIDENCE_VERSIONS == (ev.EVIDENCE_V1, V2, V3, V4, V5) and ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES["v5"] == V5
    assert inspect.signature(ev.judge_quote).parameters["version"].default == V2
    assert EVIDENCE_RULES[V5] == EVIDENCE_RULE_V5 == EVIDENCE_RULE_V2 + " " + ev.V5_RULE_SENTENCE
    t = [{"task_id": "x", "text": "花園町駅の隣駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": CORPUS}]
    assert LoomServer(t, str(tmp_path / "a"), ()).evidence_profile == (V2, "clause_or_title")
    assert LoomServer(t, str(tmp_path / "b"), (), evidence="v5").evidence_profile == (V5, "clause_or_title")
    seen = []
    monkeypatch.setattr(lm, "serve", lambda *a, **k: seen.append(a) or 0)
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r")]) == 0
    assert cli.main(["loom", "mcp", "--tasks", "t.jsonl", "--runs-dir", str(tmp_path / "r"), "--evidence", "v5"]) == 0
    assert [a[4] for a in seen] == ["v2", "v5"]


# ---- T-EV5-02: SU, on the real questions ----------------------------------------------------------------------------------------------------------------
def test_t_ev5_02_su_reads_the_subject_phrase_and_only_the_names_the_cut_dropped():
    un = lambda q: ev.subject_unread(ev.question_units(q))                                                    # noqa: E731
    assert un("ネノの属するネノ県の人口は何人ですか？") == ("ネノ", "ネノ")
    assert un("ネノ（Neno）の現地語での別名は何ですか？") == ("ネノ",)
    assert un("ネノ県は何年に設立されましたか") == ("ネノ",)
    assert un("花園町駅の隣駅の駅番号は何ですか？") == () and un("ハッシュテーブルの別名は何ですか") == ()
    assert un("SL函館大沼号の牽引機として使われた機関車の形式は何ですか") == ()                                    # the hiragana tail 「われた」 is grammar, not a dropped name
    assert un("IEEE 488の後継規格にはどのような通信方式が使われていますか") == ()
    assert un("何年に設立されましたか") == ()


def test_t_ev5_02_su_fires_on_exactly_two_dev_questions_of_the_four_banks():
    fired = {}
    for name in ("bank2", "bank4", "bank6", "bank7"):
        for r in csv.DictReader(open(os.path.join(ROOT, "experiments/line3/%s/%s.tsv" % (name, name)), encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE):
            if r["question"] and ev.subject_unread(ev.question_units(r["question"])):
                fired[r["#id"]] = name
    assert fired == {"B7-U02": "bank7", "B7-U43": "bank7"}


def test_t_ev5_02_the_question_level_refusal_and_the_begin_object(corpus):
    q = "ネノの属するネノ県の人口は何人ですか？"
    qu = ev.question_units(q)
    o = ev.begin_question_obj(qu, ev.SCOPE_TITLE, V5)
    assert o == dict(ev.question_obj(qu, ev.SCOPE_TITLE, V4), evidence=V5, unread=["ネノ", "ネノ"])
    for v in (ev.EVIDENCE_V1, V2, V3, V4):                                                                   # the older versions' objects are as they were
        assert ev.begin_question_obj(qu, ev.SCOPE_TITLE, v) == ev.question_obj(qu, ev.SCOPE_TITLE, v)
    assert ev.begin_question_obj(ev.question_units("花園町駅の駅番号は何ですか"), ev.SCOPE_TITLE, V5)["unread"] == []
    # B7-U43 as v4 admitted it: sentence 504, answer 「20万人」
    v = ev.view_of(corpus, 504)
    hits4 = [(i, j) for i in range(len(v.units)) for j in range(i, min(len(v.units), i + 10)) if not ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 504, "WORD", i, j, V4)["codes"]]
    assert hits4
    for i, j in hits4:
        r5 = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, 504, "WORD", i, j, V5)
        assert r5["codes"] == ["subject_unreadable", "question_has_no_subject"] and r5["evidence"] is None and r5["rules"] == []
        assert r5["failures"][0]["unread"] == ["ネノ", "ネノ"]


# ---- T-EV5-03: TW, toy corpus from both sides -------------------------------------------------------------------------------------------------------------
def test_t_ev5_03_tw_a_kind_word_alone_is_no_subject_and_the_title_stands_in_only_as_a_whole_word():
    c = Corpus.load(open(_toy([("テレゴ県", "人口は20万人である。"), ("花園町駅", "駅番号はY17である。"), ("六日町駅", "駅番号はY17である。"), ("テレゴ山", "標高は3776メートルである。")]), "rb").read())
    assert _passing(c, "県の人口は何人ですか", 0, V4) == ["20万人"] and _passing(c, "県の人口は何人ですか", 0, V5) == []             # the B7-U43 mechanism, without the unreadable name
    assert ev.kind_only_subject(ev.question_units("県の人口は何人ですか")) and not ev.kind_only_subject(ev.question_units("テレゴ県の人口は何人ですか"))
    r = ev.judge_quote(c, ev.question_units("県の人口は何人ですか"), ev.SCOPE_TITLE, 0, "WORD", 1, 3, V5)                          # 20|万|人
    assert r["codes"] == ["question_has_no_subject"]
    assert _passing(c, "テレゴ県の人口は何人ですか", 0, V5) == ["20万人"]                                                           # the whole title word passes
    assert _passing(c, "花園町駅の駅番号は何ですか", 1, V4) == _passing(c, "花園町駅の駅番号は何ですか", 1, V5) == ["Y17"]
    assert _passing(c, "六日町駅の駅番号は何ですか", 2, V5) == ["Y17"]
    for q in ("六の駅番号は何ですか", "日町駅の駅番号は何ですか"):                                                                  # a piece of the title is a containment
        assert _passing(c, q, 2, V4) == ["Y17"] and _passing(c, q, 2, V5) == []
        assert "no_subject" in ev.judge_quote(c, ev.question_units(q), ev.SCOPE_TITLE, 2, "WORD", 2, 3, V5)["codes"]                  # Y|17: a typed refusal
    assert _passing(c, "六の駅番号は何ですか", 2, V5, ev.SCOPE_CLAUSE) == _passing(c, "六の駅番号は何ですか", 2, V4, ev.SCOPE_CLAUSE)    # the clause scope is not touched
    r = ev.judge_quote(c, ev.question_units("テレゴ山の標高は何メートルですか"), ev.SCOPE_TITLE, 3, "WORD", 1, 2, V5)                          # 3776|メートル
    assert r["codes"] == [] and r["rules"] == ["TW"] and r["evidence"]["subject"] == [{"run": "テレゴ山", "via": "title"}]


def test_t_ev5_03_with_su_and_tw_off_v5_is_v4_byte_for_byte(corpus):
    off = frozenset({"SU", "TW"})
    for q in ("花園町駅の隣駅の駅番号は何ですか？", "ハッシュテーブルの別名は何ですか", "唯物史観を唱えた人物は誰ですか", "フェミニズムは別名で何と呼ばれていますか？", "ネノの属するネノ県の人口は何人ですか？"):
        qu = ev.question_units(q)
        for sid in range(0, corpus.n_sentences, 7):
            n = len(ev.view_of(corpus, sid).units)
            for i in range(n):
                for j in range(i, min(n, i + 6)):
                    a = ev.judge_quote(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, V4)
                    b = ev._judge_v5(corpus, qu, ev.SCOPE_TITLE, sid, "WORD", i, j, off)
                    assert (a["codes"], a["messages"], a["evidence"], a["rules"], a["clause"], a["answer"], a["chain"]) == (b["codes"], b["messages"], b["evidence"], b["rules"], b["clause"], b["answer"], b["chain"])


def test_t_ev5_03_the_v5_gate_never_raises_on_any_stretch_of_the_toy_corpora():
    """Every stretch (also those outside the sentence) of the toy sentences, for a set of questions, under every version that has its own path of the v5 kind: no exception; an out-of-range
    stretch is `answer_not_word_aligned`."""
    sents = [("テレゴ県", "人口は20万人である。"), ("花園町駅", "花園町駅の駅番号はY17である。"), ("六日町駅", "駅番号はY17である。"), ("テレゴ山", "標高は3776メートルである。"), ("花園町駅", "花園町駅の隣駅の駅番号はOR08である。"),
             ("青葉堂", "青葉堂は松風庵ともいう。")]
    c = Corpus.load(open(_toy(sents), "rb").read())
    qs = ["県の人口は何人ですか", "テレゴ県の人口は何人ですか", "ネノの属するネノ県の人口は何人ですか", "六の駅番号は何ですか", "花園町駅の隣駅の駅番号は何ですか", "青葉堂の別名は何ですか", "何年に設立されましたか", "テレゴ山の標高は何メートルですか", ""]
    n = 0
    for q in qs:
        qu = ev.question_units(q)
        for sid in range(len(sents)):
            k = len(ev.view_of(c, sid).units)
            for i in range(-1, k + 2):
                for j in range(-1, k + 2):
                    for scope in (ev.SCOPE_TITLE, ev.SCOPE_CLAUSE):
                        r = ev.judge_quote(c, qu, scope, sid, "WORD", i, j, V5)
                        n += 1
                        assert isinstance(r["codes"], list) and (r["evidence"] is None) == bool(r["codes"])
                        if not (0 <= i <= j < k) and not set(r["codes"]) & {"subject_unreadable", "question_has_no_subject"}:
                            assert "answer_not_word_aligned" in r["codes"]
    assert n > 1000


# ---- T-EV5-04: a v5 run through the server; the ledger replays -----------------------------------------------------------------------------------------------
def test_t_ev5_04_a_v5_run_records_its_profile_refuses_and_replays_identically_and_cannot_be_relabelled(tmp_path):
    p = _toy([("テレゴ県", "人口は20万人である。"), ("花園町駅", "花園町駅の駅番号はY17である。")])
    t = [{"task_id": "toy/kind", "text": "県の人口は何人ですか", "lang": "prose", "mode": "record_only", "corpus": p},
         {"task_id": "toy/ok", "text": "花園町駅の駅番号は何ですか", "lang": "prose", "mode": "record_only", "corpus": p}]

    def run(version, name, task, sid, first, last):
        srv = LoomServer(t, str(tmp_path / name), (), evidence=version)
        b = srv.begin(task, "t", "x")
        assert srv.call("weave_span", {"run_id": "x", "sid": sid, "tier": "WORD", "first": first, "last": last})["ok"]
        return b, srv.call("emit", {"run_id": "x"}), tmp_path / name / "x"
    b5, e5, d5 = run("v5", "v5ok", "toy/ok", 1, "Y", "17")
    assert b5["evidence_profile"] == {"version": V5, "subject_scope": "clause_or_title"} and b5["question"]["evidence"] == V5 and b5["question"]["unread"] == []
    assert e5["ok"] and e5["text"] == "Y17" and e5["ev"] == V5
    assert lg.verify(d5)["status"] == "OK" and lg.verify(d5)["replay"]["status"] == "IDENTICAL"
    _, e4k, d4k = run("v4", "v4k", "toy/kind", 0, "20", "人")
    assert e4k["ok"] and e4k["text"] == "20万人"                                                                 # v4 emits the other article's population ...
    _, e5k, d5k = run("v5", "v5k", "toy/kind", 0, "20", "人")
    assert e5k["ok"] is False and e5k["refusal"] == "no_evidence"                                                # ... v5 refuses it with a typed reason
    assert lg.verify(d5k)["status"] == "OK" and lg.verify(d5k)["replay"]["status"] == "IDENTICAL"
    for d, to in ((d5, V4), (d4k, V5)):                                                                          # a forged relabel is a replay difference
        _reseal(d, lambda rs, to=to: rs[0]["result"]["evidence_profile"].update(version=to))
        assert lg.verify_chain(d)["status"] == "OK" and lg.verify(d)["status"] == "REPLAY_DIFFERS"


def _reseal(d, edit):
    rs = rows(d)
    edit(rs)
    prev = lg.GENESIS
    lines = []
    for i, r in enumerate(rs):
        r["i"], r["prev"] = i, prev
        r["sha"] = lg.row_sha(r)
        prev = r["sha"]
        lines.append(lg.line_of(r))
    (d / "ops.jsonl").write_bytes(b"".join(lines))
    (d / "HEAD").write_text(prev + "\n")


# ---- T-EV5-05: the dev-set probe (stored output; v5 recomputed live and equal to it) ----------------------------------------------------------------------------
def _report():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ev5_report", os.path.join(EV5DIR, "report.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_t_ev5_05_the_probe_outputs_were_made_by_the_frozen_file():
    for name in ("dev129", "bank6", "bank7"):
        d = json.load(open(os.path.join(EV5DIR, "out_%s.json" % name), encoding="utf-8"))
        assert d["evidence_sha"] == FROZEN_V5_EVIDENCE_SHA


REACH_V4_DEV129 = ["I2-001", "I2-003", "I2-004", "I2-005", "I2-006", "I2-008", "I2-013", "I2-014", "I2-018", "I2-026", "I2-027", "I2-032", "I2-035", "I2-042", "I2-045", "I2-048",
                   "R2-I005", "R2-I007", "R2-I008", "R2-I015", "R2-I017"]


def test_t_ev5_05_the_stored_probe_numbers_v4_v5():
    """The committed outputs (experiments/line3/loom/ev5/out_{dev129,bank6,bank7}.json, produced on CI by sweep.py) with the frozen file's sha."""
    R = _report()
    d = R.summary("dev129")                                                        # bank2 (69 answerable) + bank4 (60 unanswerable)
    assert d[V4]["reach"] == d[V5]["reach"] == REACH_V4_DEV129 and len(d[V5]["reach"]) == 21
    assert d[V5]["wrong"] == [] and d[V5]["unans"] == [] and d[V5]["traps"] == []
    assert d["v5-noSU"]["reach"] == d["v5-noTW"]["reach"] == d[V5]["reach"]        # neither rule costs a dev129 item
    b6 = R.summary("bank6")                                                        # 26 answerable + 34 unanswerable
    assert b6[V5]["reach"] == b6[V4]["reach"] == ["B6-A05", "B6-A13", "B6-A15", "B6-A24", "B6-A27"] and b6[V5]["wrong"] == b6[V4]["wrong"] == ["B6-A05", "B6-A20", "B6-A27"]
    assert b6[V4]["unans"] == b6[V5]["unans"] == [] and b6["v5-noSU"]["reach"] == b6["v5-noTW"]["reach"] == b6[V5]["reach"]
    b7 = R.summary("bank7")                                                        # 32 answerable + 47 unanswerable (a dev set since the v4 probe)
    assert b7[V2]["unans"] == b7[V3]["unans"] == b7[V4]["unans"] == ["B7-U43"] and b7[V5]["unans"] == []          # the held-out failure is closed
    assert b7[V5]["reach"] == b7[V4]["reach"] == ["B7-A22", "B7-A23", "B7-A25", "B7-A36"] and b7[V5]["wrong"] == []


# ---- T-EV5-06: byte identity under three hash seeds -------------------------------------------------------------------------------------------------------
_DET_V5 = r'''
import sys, json, hashlib, csv
sys.path.insert(0, sys.argv[2])
from verantyx.loom import evidence as ev
from verantyx.loom.corpus import Corpus
corpus = Corpus.load(open(sys.argv[1], "rb").read())
out = []
for q, sid, i0, i1 in (("ネノの属するネノ県の人口は何人ですか？", 504, 0, 1), ("花園町駅の隣駅の駅番号は何ですか？", 21, 2, 3), ("ハッシュテーブルの別名は何ですか", 1, 0, 1), ("県の人口は何人ですか", 504, 3, 4)):
    qu = ev.question_units(q)
    out.append(ev.begin_question_obj(qu, "clause_or_title", ev.EVIDENCE_V5))
    out.append(list(ev.subject_unread(qu)))
    for ver in ("evidence.v4", "evidence.v5"):
        out.append(ev.judge_quote(corpus, qu, "clause_or_title", sid, "WORD", i0, i1, ver))
    out.append(ev.judge_quote(corpus, qu, "clause", sid, "WORD", i0, i1, "evidence.v5"))
out += [ev.v3_rules_digest(), ev.v4_rules_digest(), ev.v5_rules_digest()]
print(hashlib.sha256(json.dumps(out, sort_keys=True, ensure_ascii=False).encode()).hexdigest())
'''


def test_t_ev5_06_the_v5_cut_the_verdicts_and_the_digests_are_identical_under_three_hash_seeds():
    digests = set()
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        p = subprocess.run([PY, "-c", _DET_V5, CORPUS, ROOT], env=env, capture_output=True, text=True, timeout=300, cwd=ROOT)
        assert p.returncode == 0, p.stderr[-800:]
        digests.add(p.stdout.strip())
    assert len(digests) == 1


def test_t_ev5_07_the_gate_is_pure_and_the_default_waits_for_bank8():
    assert ev.EVIDENCE_LATEST == V2 and ev.PROFILE_NAMES["v2"] == V2
    src = open(os.path.join(ROOT, "verantyx/loom/evidence.py"), encoding="utf-8").read()
    for bad in ("subprocess", "import time", "import socket", "urllib", "float(", "random", "datetime"):
        assert bad not in src, bad
