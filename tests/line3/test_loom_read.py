"""LOOM-b tests: the read rule, the annotated output, the code skeleton (docs/LINE3_LOOM_DESIGN.md 3.4, 3.6, 5.3, L-LOOM-05; T-LOOM-10, 11).

Owner OP-LOOM-3 (a) 「重い助詞ほど後、中心の隣へ: が・を・と・で・に・の → 中心」.
"""
import pytest

from verantyx.line3 import foundation as fd
from verantyx.line3 import geometry as geo
from verantyx.loom import code as codelib
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from loom_common import CORPUS, TASKS, TOY, server, task, weaver

ARM_PARTICLE = {"+x": "の", "-x": "に", "+y": "で", "-y": "と", "+z": "を", "-z": "が"}


def add_all(w, texts):
    return [w.call("add", text=t, kind="constructed")["uid"] for t in texts]


def read_text(w):
    r = w.call("read")
    assert r["ok"], r
    return r


# ---------------------------------------------------------------------------------------------------------------
# the arm order (OP-LOOM-3 (a))
# ---------------------------------------------------------------------------------------------------------------
def test_arm_order_is_ascending_ladder_weight_which_is_reversed_axes():
    assert rd.ARM_ORDER == ("-z", "+z", "-y", "+y", "-x", "+x") == tuple(reversed(geo.AXES))
    assert [ARM_PARTICLE[a] for a in rd.ARM_ORDER] == ["が", "を", "と", "で", "に", "の"]
    nums = [fd.DEFAULT_SPEC.numerator(ARM_PARTICLE[a]) for a in rd.ARM_ORDER]
    assert nums == sorted(nums) == [13, 21, 34, 55, 89, 144]                      # the heaviest particle is read last, next to the centre


def test_six_arms_then_the_centre_then_wa(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:7])
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    for ax, u in zip(("-z", "+z", "-y", "+y", "-x", "+x"), us[:6]):
        w.call("seat", cid=c, seat="%s:0" % ax, uid=u)
    w.call("seat", cid=c, seat="centre", uid=us[6])
    w.call("topic", cid=c, on=True)
    w.call("link", cid=c)
    r = read_text(w)
    assert r["text"] == "Ωaが" "Ωbを" "Ωcと" "Ωdで" "Ωeに" "Ωfの" "Ωgは"
    assert r["refusals"] == []


def test_the_order_does_not_depend_on_the_order_of_seating(tmp_path):
    texts = set()
    for perm in ((0, 1, 2, 3, 4, 5), (5, 4, 3, 2, 1, 0), (2, 5, 0, 3, 1, 4)):
        w = weaver(server(tmp_path / str(perm[0]) / str(perm[1])), "prose/ca")
        us = add_all(w, TOY[:7])
        c = w.call("open_cross", tier="WORD", L=2)["cid"]
        w.call("seat", cid=c, seat="centre", uid=us[6])
        for i in perm:
            w.call("seat", cid=c, seat="%s:0" % geo.AXES[i], uid=us[i])
        w.call("link", cid=c)
        texts.add(read_text(w)["text"])
    assert len(texts) == 1
    # AXES index i holds TOY[i]: +x の first in AXES, last in reading
    assert texts.pop() == "Ωfが" "Ωeを" "Ωdと" "Ωcで" "Ωbに" "Ωaの" "Ωg"


def test_a_particle_is_read_only_when_its_arm_holds_a_unit(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:3])
    c = w.call("open_cross", tier="WORD", L=3)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[0])
    w.call("link", cid=c)
    assert read_text(w)["text"] == "Ωa"                                           # no arm, no particle, no は, no space, no 。
    w.call("seat", cid=c, seat="+x", uid=us[1])
    assert read_text(w)["text"] == "Ωbの" "Ωa"
    w.call("unseat", cid=c, seat="+x:1")
    assert read_text(w)["text"] == "Ωa"


def test_wa_only_with_topic_and_right_after_the_centre(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:2])
    c = w.call("open_cross", tier="WORD", L=2)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[0])
    w.call("seat", cid=c, seat="+x:0", uid=us[1])
    w.call("link", cid=c)
    assert read_text(w)["text"] == "Ωbの" "Ωa"
    w.call("topic", cid=c, on=True)
    assert read_text(w)["text"] == "Ωbの" "Ωaは"
    w.call("topic", cid=c, on=False)
    assert read_text(w)["text"] == "Ωbの" "Ωa"


def test_units_of_an_arm_read_outer_to_inner_and_seat_run_writes_them_in_reading_order(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:4])
    c = w.call("open_cross", tier="WORD", L=4)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[3])
    w.call("seat_run", cid=c, arm="+x", uids=us[:3])
    w.call("link", cid=c)
    assert read_text(w)["text"] == "Ωa" "Ωb" "Ωc" "の" "Ωd"
    # by hand: k = 0 is the outer end, so the units are read k ascending
    w2 = weaver(server(tmp_path / "h"), "prose/ca")
    us2 = add_all(w2, TOY[:4])
    c2 = w2.call("open_cross", tier="WORD", L=4)["cid"]
    w2.call("seat", cid=c2, seat="centre", uid=us2[3])
    for k, u in zip((0, 1, 2), us2[:3]):
        w2.call("seat", cid=c2, seat="+x:%d" % k, uid=u)
    w2.call("link", cid=c2)
    assert read_text(w2)["text"] == "ΩaΩbΩcの" "Ωd"


def test_the_thread_is_read_in_order_with_nothing_between_crosses(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:3])
    cs = []
    for u in us:
        c = w.call("open_cross", tier="WORD", L=1)["cid"]
        w.call("seat", cid=c, seat="centre", uid=u)
        cs.append(c)
    for c in (cs[2], cs[0], cs[1]):
        w.call("link", cid=c)
    assert read_text(w)["text"] == "ΩcΩaΩb"
    w.call("unlink", cid=cs[0])
    r = read_text(w)
    assert r["text"] == "ΩcΩb" and [x["type"] for x in r["refusals"]] == ["unlinked_cross"]            # never dropped silently
    w.call("link", cid=cs[0], pos=0)
    assert read_text(w)["text"] == "ΩaΩcΩb"


def test_an_unseated_unit_is_never_read(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    us = add_all(w, TOY[:2])
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[0])
    w.call("link", cid=c)
    assert read_text(w)["text"] == "Ωa"


def test_read_does_not_close_and_does_not_change_the_structure(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    us = add_all(w, TOY[:1])
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=us[0])
    w.call("link", cid=c)
    st = srv.runs[w.run_id].run.state
    before = st.to_obj()
    before["counters"]["reads"] += 2
    read_text(w)
    read_text(w)
    assert st.to_obj() == before and st.closed is None


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-10: the annotated output
# ---------------------------------------------------------------------------------------------------------------
def worked(tmp_path, model="m"):
    w = weaver(server(tmp_path), "demo/tokyo_ca", model=model)
    u1 = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    u2 = w.call("add", text="日本", kind="record", tier="WORD")["uid"]
    u3 = w.call("add", text="首都", kind="record", tier="WORD")["uid"]
    u4 = w.call("add", text="です", kind="constructed")["uid"]
    cs = [w.call("open_cross", tier="WORD", L=L)["cid"] for L in (1, 2, 1)]
    w.call("seat", cid=cs[0], seat="centre", uid=u1)
    w.call("topic", cid=cs[0], on=True)
    w.call("seat", cid=cs[1], seat="+x:0", uid=u2)
    w.call("seat", cid=cs[1], seat="centre", uid=u3)
    w.call("seat", cid=cs[2], seat="centre", uid=u4)
    for c in cs:
        w.call("link", cid=c)
    return w, cs


def test_every_character_belongs_to_exactly_one_segment(tmp_path):
    w, cs = worked(tmp_path, "claude-haiku-4-5")
    r = read_text(w)
    assert "".join(s["s"] for s in r["annotated"]) == r["text"] == "東京は日本の首都です"
    assert [s["kind"] for s in r["annotated"]] == ["record", "foundation", "record", "foundation", "record", "constructed"]
    assert sum(r["shares"].values()) == len(r["text"]) and r["shares"] == {"record": 6, "constructed": 2, "foundation": 2, "layout": 0}
    assert all(set(s) >= {"s", "kind", "cid"} for s in r["annotated"])


def test_the_three_provenance_kinds_cannot_be_passed_off_as_one_another(tmp_path):
    w, cs = worked(tmp_path, "claude-haiku-4-5")
    seg = {s["s"]: s for s in read_text(w)["annotated"]}
    assert seg["東京"]["prov"] == {"tier": "WORD", "n": 7} and seg["東京"]["uid"] == "u1" and seg["東京"]["seat"] == "centre"
    assert seg["首都"]["prov"] == {"tier": "WORD", "n": 4}
    assert seg["日本"]["prov"] == {"tier": "WORD", "n": 49} and seg["日本"]["seat"] == "+x:0" and seg["日本"]["cid"] == cs[1]
    assert seg["です"]["prov"] == {"by": "claude-haiku-4-5", "at": 4} and seg["です"]["tier"] is None
    assert seg["は"]["prov"] == {"kind": "foundation", "seats_sha": fd.seats_sha(), "ratio": "233/377"} and seg["は"]["seat"] == "centre"
    assert seg["の"]["prov"] == {"kind": "foundation", "seats_sha": fd.seats_sha(), "ratio": "144/377", "arm": "+x"} and seg["の"]["seat"] == "+x:1"
    assert "uid" not in seg["は"] and "uid" not in seg["の"]


def test_display_forms(tmp_path):
    w, cs = worked(tmp_path, "claude-haiku-4-5")
    segs = read_text(w)["annotated"]
    assert rd.render_marked(segs) == "東京は日本の首都【構成:です】"
    assert rd.render_display(segs) == "東京[rec WORD n=7] は[fnd 233/377] 日本[rec WORD n=49] の[fnd +x 144/377] 首都[rec WORD n=4] です[con by claude-haiku-4-5 @4]"


def test_adhesion_mark_is_the_count_of_the_units_bound_particle(tmp_path):
    w, cs = worked(tmp_path)
    seg = {s["s"]: s for s in read_text(w)["annotated"]}
    assert seg["日本"]["adhesion"] == {"particle": "の", "n": 20}                  # 2880 = 144 * 20
    assert seg["東京"]["adhesion"] == {"particle": "は", "n": 0}
    assert "adhesion" not in seg["首都"] and "adhesion" not in seg["です"]       # the centre without a topic, and a constructed unit, bind to nothing


@pytest.fixture(scope="module")
def corpus():
    return Corpus.load(open(CORPUS, "rb").read())


def adjacent_pair(corpus, tier="WORD"):
    T = corpus.tier(tier)
    for sid, us in enumerate(T.sentence_units):
        for a, b in zip(us, us[1:]):
            if a != b and corpus.join_attested(tier, a, b) is not None:
                return a, b, corpus.join_attested(tier, a, b)
    raise AssertionError("no attested pair")


def test_join_annotation_attested_and_unattested(tmp_path, corpus):
    a, b, att = adjacent_pair(corpus)
    T = corpus.tier("WORD")
    c_, d_ = next((x, y) for x in T.postings for y in T.postings if x != y and T.n_pair(x, y) == 0 and T.n(x) > 3 and T.n(y) > 3)
    for (x, y), expect in (((a, b), att), ((c_, d_), None)):
        w = weaver(server(tmp_path / x / y), "prose/ca")
        ux = w.call("add", text=x, kind="record", tier="WORD")["uid"]
        uy = w.call("add", text=y, kind="record", tier="WORD")["uid"]
        cx = w.call("open_cross", tier="WORD", L=1)["cid"]
        cy = w.call("open_cross", tier="WORD", L=1)["cid"]
        w.call("seat", cid=cx, seat="centre", uid=ux)
        w.call("seat", cid=cy, seat="centre", uid=uy)
        w.call("link", cid=cx)
        w.call("link", cid=cy)
        segs = read_text(w)["annotated"]
        assert segs[0].get("join") is None and segs[1]["join"] == {"prev": ux, "attested": expect}
    sid, s, e = att
    txt = corpus.spans().text(sid)
    assert txt[s:e].replace(" ", "") != "" and txt[s:e].startswith(a) and txt[s:e].endswith(b)


def test_join_is_display_only_never_a_gate(tmp_path, corpus):
    T = corpus.tier("WORD")
    c_, d_ = next((x, y) for x in T.postings for y in T.postings if x != y and T.n_pair(x, y) == 0 and T.n(x) > 3 and T.n(y) > 3)
    w = weaver(server(tmp_path), "prose/ca")
    ux = w.call("add", text=c_, kind="record", tier="WORD")["uid"]
    uy = w.call("add", text=d_, kind="record", tier="WORD")["uid"]
    cs = [w.call("open_cross", tier="WORD", L=1)["cid"] for _ in range(2)]
    w.call("seat", cid=cs[0], seat="centre", uid=ux)
    w.call("seat", cid=cs[1], seat="centre", uid=uy)
    for c in cs:
        w.call("link", cid=c)
    assert w.call("emit")["ok"] is True


# ---------------------------------------------------------------------------------------------------------------
# the code skeleton
# ---------------------------------------------------------------------------------------------------------------
def code_run(tmp_path, texts):
    w = weaver(server(tmp_path), "code/ca")
    return w, {t: w.call("add", text=t, kind="constructed")["uid"] for t in texts}


def test_code_is_head_initial_centre_first_then_arms_in_axes_order(tmp_path):
    w, u = code_run(tmp_path, ["print", "(", "a", ",", "b", ")"])
    c = w.call("open_cross", tier="CODE", L=2)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u["print"])
    for ax, t in zip(geo.AXES, ["(", "a", ",", "b", ")"]):
        w.call("seat", cid=c, seat="%s:1" % ax, uid=u[t])
    w.call("link", cid=c)
    r = read_text(w)
    assert r["text"] == "print(a, b)\n"
    assert [s["s"] for s in r["annotated"] if s["kind"] != "layout"] == ["print", "(", "a", ",", "b", ")"]
    assert "".join(s["s"] for s in r["annotated"]) == r["text"]
    assert r["shares"]["layout"] == 2 and r["shares"]["constructed"] == 10                  # the space after the comma and the newline


def test_code_arm_units_read_inner_to_outer_and_seat_run_starts_innermost(tmp_path):
    toks = ["x", "=", "foo", "(", "a", ",", "b", ")"]
    w, u = code_run(tmp_path, toks)
    c = w.call("open_cross", tier="CODE", L=8)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u["x"])
    r = w.call("seat_run", cid=c, arm="+x", uids=[u[t] for t in toks[1:]])
    assert [s["seat"] for s in r["seated"]] == ["+x:%d" % k for k in (7, 6, 5, 4, 3, 2, 1)]
    w.call("link", cid=c)
    assert read_text(w)["text"] == "x = foo(a, b)\n"


def test_code_indentation_by_depth_is_layout(tmp_path):
    w, u = code_run(tmp_path, ["def", "f", "(", "x", ")", ":", "return"])
    cs = [w.call("open_cross", tier="CODE", L=6, depth=d)["cid"] for d in (0, 0)]
    w.call("seat", cid=cs[0], seat="centre", uid=u["def"])
    w.call("seat_run", cid=cs[0], arm="+x", uids=[u[t] for t in ["f", "(", "x", ")", ":"]])
    w.call("seat", cid=cs[1], seat="centre", uid=u["return"])
    ux = w.call("add", text="x", kind="constructed")["uid"]
    w.call("seat_run", cid=cs[1], arm="+x", uids=[ux])
    w.call("set_depth", cid=cs[1], depth=1)
    for c in cs:
        w.call("link", cid=c)
    r = read_text(w)
    assert r["text"] == "def f(x):\n    return x\n"
    lay = [s for s in r["annotated"] if s["kind"] == "layout"]
    assert lay[0]["s"] == " " and any(s["s"] == "    " for s in lay) and sum(1 for s in lay if s["s"] == "\n") == 2
    assert codelib.parse_gate(r["text"]) is None
    assert not [x for x in r["refusals"] if x["type"] == "parse_error"]


@pytest.mark.parametrize("tokens,line", [
    (["a", "+", "b"], "a + b"),
    (["a", ".", "b", "(", ")"], "a.b()"),
    (["a", "[", "0", "]"], "a[0]"),
    (["f", "(", "x", ")", "[", "0", "]"], "f(x)[0]"),
    (["return", "(", "x", ")"], "return (x)"),                                   # a keyword is not a NAME: it keeps its space
    (["if", "x", ":"], "if x:"),
    (["d", "=", "{", "'k'", ":", "1", "}"], "d = {'k': 1}"),
    (["f", "(", "a", ",", "b", ")"], "f(a, b)"),
    (["x", "=", "-", "1"], "x = - 1"),
])
def test_code_spacing_table(tokens, line):
    seps = codelib.spaced(tokens)
    assert len(seps) == len(tokens) - 1
    out = tokens[0] + "".join(s + t for s, t in zip(seps, tokens[1:]))
    assert out == line
    assert codelib.line_keeps_tokens(line, tokens)


def test_a_line_that_would_retokenize_differently_is_layout_changed_tokens(tmp_path):
    w, u = code_run(tmp_path, ["1", ".", "real"])
    c = w.call("open_cross", tier="CODE", L=3)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u["1"])
    w.call("seat_run", cid=c, arm="+x", uids=[u["."], u["real"]])
    w.call("link", cid=c)
    r = read_text(w)
    assert "layout_changed_tokens" in [x["type"] for x in r["refusals"]]
    assert not codelib.line_keeps_tokens("1.real", ["1", ".", "real"])


def test_constructed_code_units_are_exactly_one_token(tmp_path):
    w = weaver(server(tmp_path), "code/ca")
    for ok in ("x", "foo", "=", "->", "(", "123", "1.5", "'a b'", '"s"', "日本", "**", ":="):
        assert w.call("add", text=ok, kind="constructed")["ok"], ok
    for bad in ("a b", "x+y", "f()", "# c", "", " x", "x ", "x" * 41, "if x", "\n"):
        r = w.call("add", text=bad, kind="constructed")
        assert r["ok"] is False and r["refusal"] == "bad_unit_text", (bad, r)
    assert codelib.is_one_token("'a b'") and not codelib.is_one_token("'a b")


def test_code_unit_cap_is_40_chars_and_a_code_constructed_unit_is_not_checked_against_the_prose_corpus(tmp_path):
    w = weaver(server(tmp_path), "code/ca")
    assert w.call("add", text="n" * 40, kind="constructed")["ok"]
    assert w.call("add", text="n" * 41, kind="constructed")["refusal"] == "bad_unit_text"
    assert w.call("add", text="日本", kind="constructed")["ok"]                       # no prose shadow check for code


def test_code_parse_gate_is_reported_by_read(tmp_path):
    w, u = code_run(tmp_path, ["def"])
    c = w.call("open_cross", tier="CODE", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u["def"])
    w.call("link", cid=c)
    r = read_text(w)
    assert r["text"] == "def\n"
    pe = [x for x in r["refusals"] if x["type"] == "parse_error"]
    assert len(pe) == 1 and pe[0]["lineno"] == 1 and isinstance(pe[0]["msg"], str)


def test_a_cross_with_no_unit_prints_nothing(tmp_path):
    w, u = code_run(tmp_path, ["x"])
    c = w.call("open_cross", tier="CODE", L=1)["cid"]
    w.call("link", cid=c)
    assert read_text(w)["text"] == ""
