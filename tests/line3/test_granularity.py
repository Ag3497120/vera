"""F2 tests (L-480..): answers that are not one unit are assembled from the connections between the tiers
(docs/LINE3_F2_GRANULARITY.md).  Exactness on hand examples from the bank2 corpus (ハッシュ表, カール・マルクス,
3万2,500キロワット), cross-tier joining, traceability of every character, the option off = byte-identical, hash seeds,
no float."""
import ast
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from verantyx.line3 import ask as A
from verantyx.line3 import granularity as G
from verantyx.line3 import space as sp

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
S_HASH = "ハッシュ表ともいう。"
S_MARX = "19世紀にカール・マルクスが唱えた歴史観である。"
S_KW = "同社の水力発電所・赤尾発電所に送水し、最大3万2,500キロワットの電力を発生する。"
S_BRIDGE = "2007年（平成19年）、路線の廃止に伴い廃駅となった。"
SENTS = [S_HASH, S_MARX, S_KW, S_BRIDGE, "東京は日本の首都である。", "大阪は日本の西の都市である。"]


@pytest.fixture(scope="module")
def space():
    return sp.build_space([{"sent": s, "source": "t"} for s in SENTS])


def units(space, tier, sid):
    return list(space.tiers[tier].sentence_units[sid])


# ---- spans: the connection (containment of surface spans of units of different tiers) -----------------------------
@pytest.mark.parametrize("sid", range(len(SENTS)))
def test_spans_show_the_unit_in_every_tier(space, sid):
    ix = G.SpanIndex(space)
    for t in sp.TIERS:
        sps = ix.spans(t, sid)
        assert len(sps) == len(units(space, t, sid))
        for u, (a, b) in zip(units(space, t, sid), sps):
            assert ix.text(sid)[a:b] == u
        assert list(sps) == sorted(sps)                         # unit order = surface order


def test_run_unit_contains_the_word_and_char_units_inside_it(space):
    ix = G.SpanIndex(space)
    run = [(u, ab) for u, ab in zip(units(space, "RUN", 0), ix.spans("RUN", 0)) if u == "ハッシュ"][0][1]
    chars = [ix.text(0)[a:b] for a, b in ix.spans("CHAR", 0) if a >= run[0] and b <= run[1]]
    words = [ix.text(0)[a:b] for a, b in ix.spans("WORD", 0) if a >= run[0] and b <= run[1]]
    assert "".join(chars) == "ハッシュ" and "".join(words) == "ハッシュ"


# ---- assembly exactness on hand examples -------------------------------------------------------------------------
def test_hash_table_is_assembled_from_two_run_units(space):
    res = G.assemble(space, [("RUN", ["ハッシュ", "表"], [0])], "entry")
    assert [a.text for a in res] == ["ハッシュ表"]
    a = res[0]
    assert (a.sid, a.start, a.end) == (0, 0, 5)
    assert [(p.tier, p.unit) for p in a.parts] == [("RUN", "ハッシュ"), ("RUN", "表")]
    assert a.aligned_tiers == ("RUN", "WORD", "CHAR") and a.lifted_tier == "RUN"
    assert a.part_tiers == ("RUN",)


def test_karl_marx_keeps_the_dropped_middle_dot_as_surface(space):
    res = G.assemble(space, [("RUN", ["カール", "マルクス"], [1])], "entry")
    assert [a.text for a in res] == ["カール・マルクス"]
    assert G.trace_check(space, res[0]) == []


def test_amount_split_at_the_comma_is_joined(space):
    res = G.assemble(space, [("RUN", ["最大3万2", "500キロワット"], [2])], "entry")
    assert [a.text for a in res] == ["最大3万2,500キロワット"]


def test_units_with_a_letter_between_them_are_not_joined(space):
    # 日本 ... 首都: the particle の/である lies between (and is not a unit of the tier): not one string
    res = G.assemble(space, [("RUN", ["東京", "日本"], [4])], "entry")
    assert res == ()
    assert G.assemble(space, [("RUN", ["ハッシュ"], [0])], "entry") == ()          # a lone unit adds nothing


def test_bridge_over_a_function_word_is_an_option_off_by_default(space):
    ents = [("RUN", ["路線", "廃止"], [3])]
    assert G.assemble(space, ents, "entry") == ()
    res = G.assemble(space, ents, "entry", bridge=True)
    assert [a.text for a in res] == ["路線の廃止"]
    assert G.trace_check(space, res[0]) != []          # the strict trace refuses the bridged letter ...
    assert G.trace_check(space, res[0], bridge=True) == []     # ... and accepts it only when told the bridge was on


# ---- tiers: parts keep their tier; scope "all" joins across tiers ------------------------------------------------
def test_scope_all_joins_a_word_unit_and_a_run_unit(space):
    ents = [("WORD", ["ハッシュ"], [0]), ("RUN", ["表"], [0])]
    assert G.assemble(space, ents, "entry") == ()
    res = G.assemble(space, ents, "all")
    assert [a.text for a in res] == ["ハッシュ表"]
    assert [(p.tier, p.unit, p.entries) for p in res[0].parts] == [("WORD", "ハッシュ", (0,)), ("RUN", "表", (1,))]
    assert res[0].part_tiers == ("RUN", "WORD")


def test_a_unit_that_contains_the_other_adds_nothing(space):
    # RUN ともいう contains WORD いう: the joined span is just the RUN unit, which is already a candidate
    assert G.assemble(space, [("RUN", ["ともいう"], [0]), ("WORD", ["いう"], [0])], "all") == ()


def test_char_units_chain_into_the_whole_string(space):
    res = G.assemble(space, [("CHAR", list("ハッシュ表"), [0])], "entry")
    assert [a.text for a in res] == ["ハッシュ表"]
    assert [p.unit for p in res[0].parts] == list("ハッシュ表")
    assert res[0].aligned_tiers == ("RUN", "WORD", "CHAR")


def test_same_span_from_two_entries_is_one_string_with_both_entries(space):
    ents = [("RUN", ["ハッシュ", "表"], [0]), ("RUN", ["表", "ハッシュ"], [0])]
    res = G.assemble(space, ents, "entry")
    assert len(res) == 1 and res[0].entries == (0, 1)


def test_misaligned_edges_are_reported_by_aligned_tiers(space):
    # WORD units ハッシュ + 表 end on a boundary of every tier; take only the second half of ハッシュ with CHAR units:
    res = G.assemble(space, [("CHAR", ["シ", "ュ", "表"], [0])], "entry")
    assert [a.text for a in res] == ["シュ表"]
    assert res[0].aligned_tiers == ("CHAR",)             # the string starts inside a RUN and a WORD unit
    assert res[0].lifted_tier == "CHAR"


# ---- traceability -----------------------------------------------------------------------------------------------
def test_every_character_of_every_string_maps_to_units_and_the_sentence(space):
    ents = [("RUN", ["ハッシュ", "表", "カール", "マルクス", "最大3万2", "500キロワット"], [0, 1, 2]),
            ("WORD", ["ハッシュ", "表", "カール", "マルクス"], [0, 1]), ("CHAR", list("ハッシュ表マルクス"), [0, 1])]
    for scope in G.SCOPES:
        res = G.assemble(space, ents, scope)
        assert res
        for a in res:
            assert G.trace_check(space, a) == [], (scope, a.text)
            text = strip(space, a.sid)
            covered = set()
            for p in a.parts:
                assert text[p.start:p.end] == p.unit
                assert units(space, p.tier, a.sid)[p.idx] == p.unit
                covered.update(range(p.start, p.end))
            for i in range(a.start, a.end):
                assert i in covered or not sp._letterlike(text[i])


def strip(space, sid):
    return G.SpanIndex(space).text(sid)


def test_trace_check_refuses_a_forged_string(space):
    a = G.assemble(space, [("RUN", ["ハッシュ", "表"], [0])], "entry")[0]
    import dataclasses
    assert G.trace_check(space, dataclasses.replace(a, text="ハッシュ裏")) != []
    forged = dataclasses.replace(a, parts=(a.parts[0], dataclasses.replace(a.parts[1], unit="裏")))
    assert G.trace_check(space, forged) != []
    assert G.trace_check(space, dataclasses.replace(a, parts=a.parts[:1])) != []      # a letter in no part


def test_trace_check_refuses_a_repeated_unit_at_the_wrong_place(space):
    # カール・マルクス has ル twice: swapping the spans of the two CHAR ル parts keeps every surface and the coverage
    import dataclasses
    a = G.assemble(space, [("CHAR", list("カールマルクス"), [1])], "entry")[0]
    assert a.text == "カール・マルクス" and G.trace_check(space, a) == []
    i, j = [k for k, p in enumerate(a.parts) if p.unit == "ル"]
    ps = list(a.parts)
    ps[i], ps[j] = (dataclasses.replace(a.parts[i], start=a.parts[j].start, end=a.parts[j].end),
                    dataclasses.replace(a.parts[j], start=a.parts[i].start, end=a.parts[i].end))
    assert G.trace_check(space, dataclasses.replace(a, parts=tuple(ps))) != []


def test_scope_error_and_order(space):
    with pytest.raises(ValueError):
        G.assemble(space, [], "nope")
    ents = [("RUN", ["カール", "マルクス", "ハッシュ", "表"], [1, 0])]
    res = G.assemble(space, ents, "entry")
    assert [(a.sid, a.start) for a in res] == sorted((a.sid, a.start) for a in res)


# ---- the option in ask: off = byte-identical ---------------------------------------------------------------------
DATA = ["東京は日本の首都である。", "大阪は日本の西の都市である。", "京都は日本の古い都市である。",
        "東京は大きな都市である。", "富士山は日本一高い山である。", "東京タワーは東京にある。",
        "ハッシュ表ともいう。", "カール・マルクスが唱えた。"]


@pytest.fixture(scope="module")
def index(tmp_path_factory):
    p = tmp_path_factory.mktemp("f2") / "toy.jsonl"
    with open(p, "w", encoding="utf-8") as f:
        for s in DATA:
            f.write(json.dumps({"sent": s, "source": "toy"}, ensure_ascii=False) + "\n")
    return A.Index.from_jsonl(str(p))


def test_default_ask_is_byte_identical_and_has_no_assembled_key(index):
    c0 = A.ask(index, "東京は何の都市ですか")
    c1 = A.ask(index, "東京は何の都市ですか", granularity=None)
    assert c0.assembled is None and c0.to_bytes() == c1.to_bytes()
    assert "assembled" not in c0.answer_obj()
    assert A.format_text(c0) == A.format_text(c1) and "つなげた候補" not in A.format_text(c0)


def test_option_on_only_adds_the_assembled_part(index):
    q = "東京は何の都市ですか"
    off = A.ask(index, q)
    for g in (True, "entry", "all"):
        on = A.ask(index, q, granularity=g)
        a = on.answer_obj()
        extra = a.pop("assembled")
        assert json.dumps(a, sort_keys=True) == json.dumps(off.answer_obj(), sort_keys=True)     # the listed entries are untouched
        assert json.dumps(on.thought_obj(), sort_keys=True) == json.dumps(off.thought_obj(), sort_keys=True)
        assert extra["scope"] == (G.DEFAULT_SCOPE if g is True else g) and extra["n"] == len(extra["strings"])
        assert "つなげた候補" in A.format_text(on)
        for s in extra["strings"]:                                   # every shown string traces back
            assert s["text"] == strip(index.space, s["sid"])[s["span"][0]:s["span"][1]]
            assert s["sid"] in {x for _, e in on.entries for x in e.source_sids}


def test_assemble_combined_on_a_stub_lists_parts_and_tiers(space):
    ent = SimpleNamespace(words=("ハッシュ", "表"), source_sids=(0,))
    c = SimpleNamespace(entries=(("RUN", ent), ("WORD", SimpleNamespace(words=("ハッシュ", "表"), source_sids=(0,)))))
    obj = G.assemble_combined(c, space)
    assert obj["n"] == 1 and obj["strings"][0]["text"] == "ハッシュ表"
    s = obj["strings"][0]
    assert s["part_tiers"] == ["RUN", "WORD"] and s["aligned_tiers"] == ["RUN", "WORD", "CHAR"] and s["lifted_tier"] == "RUN"
    assert any("ハッシュ表" in line for line in G.format_lines(obj))


def test_g3j_the_flat_assembled_block_is_this_assembly_over_the_flat_entries(space):
    """G3-j (L-780..): the block flat/assembled of the combined list is `assemble(scope "all", no bridging)` over the flat entries (layer 0), nothing else; the
    strings and their spans equal those of the ask.py F2 hook on the same entries, and a unit of another tier joins (RUN ハッシュ + WORD 表)."""
    from verantyx.line3 import combined as CB
    stub = [("RUN", ("ハッシュ",), (0,)), ("WORD", ("表",), (0,)), ("RUN", ("カール", "マルクス"), (1,)), ("CHAR", tuple("東京"), (4,))]
    flat = CB.Source(CB.FLAT, CB.CHOICE, tuple(CB.Cand("flat/" + t, w, source_sids=s) for t, w, s in stub))
    src = CB.assembled_source(flat, space)
    want = G.assemble(space, stub, "all")
    assert [(c.words[0], c.detail["sid"], tuple(c.detail["span"])) for c in src.cands] == [(a.text, a.sid, (a.start, a.end)) for a in want]
    assert [c.words[0] for c in src.cands] == ["ハッシュ表", "カール・マルクス", "東京"]
    assert src.cands[0].detail["part_tiers"] == ["RUN", "WORD"]
    # the ask.py hook (c.entries as (tier, entry)) gives the same strings
    hook = G.assemble_combined(SimpleNamespace(entries=tuple((t, SimpleNamespace(words=w, source_sids=s)) for t, w, s in stub)), space)
    assert [(x["text"], x["sid"], tuple(x["span"])) for x in hook["strings"]] == [(c.words[0], c.detail["sid"], tuple(c.detail["span"])) for c in src.cands]


# ---- determinism, no float ---------------------------------------------------------------------------------------
SCRIPT = r"""
import json, sys
sys.path.insert(0, %r)
from verantyx.line3 import granularity as G, space as sp
S = %r
space = sp.build_space([{"sent": s, "source": "t"} for s in S])
ents = [("RUN", ["ハッシュ", "表", "カール", "マルクス", "最大3万2", "500キロワット"], [0, 1, 2]),
        ("WORD", ["ハッシュ", "表", "マルクス"], [0, 1]), ("CHAR", list("ハッシュ表マルクス"), [0, 1])]
print(json.dumps([[a.obj() for a in G.assemble(space, ents, sc)] for sc in G.SCOPES], ensure_ascii=False, sort_keys=True))
"""


def test_output_is_the_same_under_hash_seeds_0_1_12345():
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=ROOT)
        r = subprocess.run([sys.executable, "-c", SCRIPT % (ROOT, SENTS)], capture_output=True, env=env, timeout=240)
        assert r.returncode == 0, r.stderr.decode()[-500:]
        outs.append(r.stdout)
    assert outs[0] == outs[1] == outs[2] and len(outs[0]) > 100


def test_no_float_in_the_module_or_its_output(space):
    tree = ast.parse(open(G.__file__, encoding="utf-8").read())
    for n in ast.walk(tree):
        assert not (isinstance(n, ast.Constant) and isinstance(n.value, float))
        assert not (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div))
        assert not (isinstance(n, ast.Name) and n.id == "float")

    def walk(x):
        if isinstance(x, float):
            raise AssertionError("float")
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        if isinstance(x, (list, tuple)):
            [walk(v) for v in x]
    walk(G.assemble_combined(SimpleNamespace(entries=(("RUN", SimpleNamespace(words=("ハッシュ", "表"), source_sids=(0,))),)), space))
