"""W3-a6 (docs 12.18, D3/D4): the noun-type form (``--kind ntype``) and the role-frame form (``--kind role``) of the generator,
against a FAKE codex (no test here reaches the real executable), and the two lists of words to ask."""
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from tools import gen_coarse_evidence as gce
from verantyx import coarse_types as ct

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / "tests/coarse_place/data"
EXPECT = json.loads((DATA / "w3a6_expect.json").read_text(encoding="utf-8"))
PYTHON = sys.executable
PRED_PROMPT_SHA = "1509fd3014397232d48dfd00b0ae9d8df078b5f2fb3d54e9f53c2b17a76d68e2"
PRED_SCHEMA_SHA = "68551a6ab548b7d5920d5c22cb0ca7eb114f47589ffd50a0b5ad6a488a84d882"
NOUN_PROMPT_SHA = "ded30f48c0a596575d061e75aa0768beb3008969a587a01d2ec39807af031f65"


def test_the_noun_and_predicate_forms_keep_their_prompt_and_schema_hashes():
    assert gce.prompt_template_sha256_pred() == PRED_PROMPT_SHA
    assert gce.schema_sha256(gce.PRED_SCHEMA) == PRED_SCHEMA_SHA
    assert gce.prompt_template_sha256() == NOUN_PROMPT_SHA
    assert "RELATIVE_POSITION" not in gce.PRED_PROMPT_HEAD
    assert json.dumps(gce.PRED_SCHEMA).count("RELATIVE_POSITION") == 0


def _test_terms():
    out = set(EXPECT["relative_position"]) | {r["pred"] for r in EXPECT["roles"]}
    for p in sorted(DATA.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                t = json.loads(line).get("term")
                if isinstance(t, str):
                    out.add(t)
    return {t for t in out if len(t) >= 2}


def _tokens(h):
    return set(h.replace("、", " ").replace("（", " ").replace("）", " ").replace("。", " ").split())


@pytest.mark.parametrize("head,types", [(gce.NTYPE_PROMPT_HEAD, ct.NOUN_TYPES), (gce.ROLE_PROMPT_HEAD, ct.FRAME_NOUN_TYPES)],
                         ids=["ntype", "role"])
def test_the_new_prompts_list_the_inventories_from_coarse_types_and_no_test_word(head, types):
    for k, v in types.items():
        assert "- %s: %s" % (k, v) in head
    # a type line is "- ID: name"; the role lines are "- id: text" with lower-case ids
    n_types = len(re.findall(r"^- [A-Z_]+: ", head, re.M))
    assert n_types == len(types) + (1 if head is gce.NTYPE_PROMPT_HEAD else 0)       # NTYPE: one more for the note
    for t in sorted(_test_terms()):
        assert t not in _tokens(head), t
    assert not [t for t in _test_terms() if t in re.findall(r"[<]([^>]*)[>]", head)]
    if head is gce.ROLE_PROMPT_HEAD:
        assert "が を に で へ と から まで より" in head


def test_the_ntype_prompt_holds_the_note_of_the_new_type_and_the_role_prompt_the_role_lines():
    """2026-10-04 20:51:13 +0900: extend the 20:38 mapping checks with causer/causee/beneficiary/value and passive agent; still all nine particles."""
    for k, v in ct.NOUN_TYPE_NOTES.items():
        assert "- %s: %s" % (k, v) in gce.NTYPE_PROMPT_HEAD
    assert "- RELATIVE_POSITION: 相対位置・方向" in gce.NTYPE_PROMPT_HEAD
    for k in ct.ROLE_NAMES:
        assert "- %s: %s" % (k, ct.ROLE_DESCRIPTIONS[k]) in gce.ROLE_PROMPT_HEAD
    assert len(re.findall(r"^- [a-z]+: ", gce.ROLE_PROMPT_HEAD, re.M)) == 20
    assert "RELATIVE_POSITION" not in gce.ROLE_PROMPT_HEAD
    for particle in ct.CASE_PARTICLES_9:
        assert "- %s: " % particle in gce.ROLE_PROMPT_HEAD
        assert particle in gce.ROLE_PARTICLE_GUIDANCE
    assert len(gce.ROLE_PARTICLE_GUIDANCE) == 9
    typical_roles = {
        "が": ("agent", "entity", "causer", "experiencer", "attribute"), "を": ("patient", "causee"),
        "に": ("recipient", "goal", "result", "place", "time", "beneficiary", "causee", "agent",
              "experiencer", "attribute"),
        "で": ("place", "instrument", "cause", "companion"), "へ": ("goal",),
        "と": ("companion", "quotation", "standard", "value"),
        "から": ("source", "cause", "time", "agent"),
        "まで": ("time", "goal", "place"), "より": ("source", "standard", "agent"),
    }
    for particle, roles in typical_roles.items():
        for role in roles:
            assert re.search(r"\b%s\b" % role, gce.ROLE_PARTICLE_GUIDANCE[particle])
    assert "中心的な項だけに限定せず" in gce.ROLE_PROMPT_HEAD
    assert "付加格も" in gce.ROLE_PROMPT_HEAD
    p = gce.build_prompt_role(["アア"])
    assert p.splitlines()[-1] == 'WORDS_JSON: ["アア"]'
    assert "同じ型を複数の役割に申告してよい" in gce.ROLE_PROMPT_HEAD
    assert "同じ型を 2 つの役割に書かない" not in gce.ROLE_PROMPT_HEAD
    assert gce.prompt_template_sha256_ntype() == gce.sha256_text(gce.NTYPE_PROMPT_HEAD + gce.WORDS_PREFIX)
    assert len({gce.prompt_template_sha256_ntype(), gce.prompt_template_sha256_role(), PRED_PROMPT_SHA, NOUN_PROMPT_SHA}) == 4


def test_fixed_role_expectations_have_ten_predicates_and_eleven_rows():
    assert len(EXPECT["roles"]) == 11
    assert len({row["pred"] for row in EXPECT["roles"]}) == 10


def test_the_new_schemas_are_closed_and_their_enums_are_the_inventories():
    it = gce.NTYPE_SCHEMA["properties"]["items"]["items"]
    assert gce.NTYPE_SCHEMA["additionalProperties"] is False and it["additionalProperties"] is False
    assert it["required"] == ["word", "definition", "types"]
    assert it["properties"]["types"]["items"]["enum"] == list(ct.NOUN_TYPES) and len(ct.NOUN_TYPES) == 18
    it = gce.ROLE_SCHEMA["properties"]["items"]["items"]
    assert it["additionalProperties"] is False and it["required"] == ["word", "frame"]
    fr = it["properties"]["frame"]["items"]
    assert fr["additionalProperties"] is False and fr["required"] == ["particle", "roles"]
    assert fr["properties"]["particle"]["enum"] == list(ct.CASE_PARTICLES_9)
    ro = fr["properties"]["roles"]["items"]
    assert ro["additionalProperties"] is False and ro["required"] == ["role", "types"]
    assert ro["properties"]["role"]["enum"] == list(ct.ROLE_NAMES)
    assert ro["properties"]["types"]["items"]["enum"] == list(ct.FRAME_NOUN_TYPES) and len(ct.FRAME_NOUN_TYPES) == 17


# --- the readers ---------------------------------------------------------------------------------
def nt(batch, items):
    return gce.parse_output_ntype(batch, {"items": items})


def test_the_ntype_reader_counts_foreign_dup_missing_abstained_invalid_and_no_type():
    b = ["a", "b", "c", "d", "e", "f", "g"]
    items = [{"word": "a", "definition": "d.", "types": ["PLACE", "RELATIVE_POSITION"]},
             {"word": "b", "definition": None, "types": []},                                     # abstention
             {"word": "c", "definition": "d.", "types": ["NOT_A_TYPE"]},                         # outside the enum
             {"word": "d", "definition": "d.", "types": ["PLACE", "PLACE"]},                     # repeated
             {"word": "e", "definition": "d.", "types": ["PLACE", "TIME", "WORK"]},              # three
             {"word": "f", "definition": "d.", "types": []},                                     # no type
             {"word": "x", "definition": "d.", "types": ["PLACE"]},                              # foreign
             {"word": "g", "definition": "d.", "types": ["TIME"]}, {"word": "g", "definition": "e.", "types": ["PLACE"]}]
    ans, st = nt(b, items)
    assert ans == {"a": ("d.", ["PLACE", "RELATIVE_POSITION"]), "b": (None, []), "f": ("d.", [])}
    assert st == {"foreign": 1, "dup_dropped": 1, "missing": 0, "abstained": 1, "answered": 3, "invalid": 3, "no_type": 1}
    with pytest.raises(ValueError):
        gce.parse_output_ntype(b, {"nothing": 1})


def ro(batch, items):
    return gce.parse_output_role(batch, {"items": items})


def entry(p, *roles):
    return {"particle": p, "roles": [{"role": r, "types": list(ts)} for r, ts in roles]}


def test_the_role_reader_keeps_a_clean_frame_in_particle_and_role_order_and_drops_the_rest_by_reason():
    b = ["a", "b", "c", "d", "e", "f", "g", "h"]
    items = [{"word": "a", "frame": [entry("で", ("cause", ["EVENT_ACT"]), ("instrument", ["ARTIFACT", "ABSTRACT"])),
                                      entry("が", ("agent", ["PERSON"]))]},
             {"word": "b", "frame": None},                                                           # abstention
             {"word": "c", "frame": [entry("に", ("goal", ["PLACE"])), entry("に", ("recipient", ["PERSON"]))]},   # particle twice
             {"word": "d", "frame": [entry("に", ("goal", ["PLACE"]), ("goal", ["ARTIFACT"]))]},                   # role twice
             {"word": "e", "frame": [entry("に", ("nothing", ["PLACE"]))]},                          # role outside the enum
             {"word": "f", "frame": [entry("に", ("goal", []))]},                                    # empty types
             {"word": "g", "frame": [entry("に", ("goal", ["PLACE", "PLACE"]))]},                    # repeated type
             {"word": "z", "frame": []}, {"word": "h", "frame": []}]
    ans, st = ro(b, items)
    assert ans["a"] == {"が": [{"role": "agent", "types": ["PERSON"]}],
                        "で": [{"role": "instrument", "types": ["ABSTRACT", "ARTIFACT"]},
                               {"role": "cause", "types": ["EVENT_ACT"]}]}
    assert list(ans["a"]) == ["が", "で"]
    assert ans["b"] is None and ans["h"] == {} and set(ans) == {"a", "b", "h"}
    assert st == {"foreign": 1, "dup_dropped": 0, "missing": 0, "abstained": 1, "answered": 3, "invalid": 3,
                  "frame_dup_particle": 1, "role_dup": 1}


def test_the_role_reader_drops_a_word_that_comes_back_twice_and_counts_missing():
    ans, st = ro(["a", "b"], [{"word": "a", "frame": []}, {"word": "a", "frame": []}])
    assert ans == {} and st["dup_dropped"] == 1 and st["missing"] == 1


def test_the_role_reader_preserves_a_shared_type_and_the_checker_counts_it_as_split():
    parsed, stats = ro(["集める"], [{"word": "集める", "frame": [
        entry("に", ("goal", ["PLACE"]), ("place", ["PLACE"]))]}])
    assert stats["invalid"] == 0 and stats["answered"] == 1
    assert parsed["集める"]["に"] == [
        {"role": "goal", "types": ["PLACE"]},
        {"role": "place", "types": ["PLACE"]},
    ]

    config = dict(ct.DEFAULT_CONFIG)
    config.update({"rd_min_total": 20, "rd_particle_min": 5, "rd_particle_share_pct": 10,
                   "rd_type_share_pct": 50, "rd_min_sources": 1})
    checked = ct.role_frame_check(parsed["集める"], [
        ("role_distribution", "jawiki", "に|PLACE", 40, 50),
        ("role_distribution", "jawiki", "が|PERSON", 10, 50),
    ], config)
    assert checked["status"] == "ESTIMATED"
    assert checked["arms"]["role_distribution@jawiki"]["split"] == [
        {"particle": "に", "type": "PLACE", "roles": ["goal", "place"]}]
    assert checked["arms"]["role_distribution@jawiki"]["votes"] == {}
    assert [row["why"] for row in checked["unconfirmed"]["に"]] == ["SPLIT", "SPLIT"]


# --- the lists -----------------------------------------------------------------------------------
@pytest.fixture
def small_placement(tmp_path):
    d = tmp_path / "pl"
    d.mkdir()
    (d / "manifest.json").write_text(json.dumps({"content_sha256": "x" * 64}), encoding="utf-8")
    con = sqlite3.connect(str(d / "placement.sqlite"))
    con.execute("CREATE TABLE headwords(word TEXT PRIMARY KEY, ns TEXT, state TEXT, origin TEXT, top TEXT, kind TEXT, "
                "n_seen INTEGER, by TEXT)")
    con.execute("CREATE TABLE generated_frames(word TEXT PRIMARY KEY, model TEXT, effort TEXT, batch_id TEXT, "
                "attempt INTEGER, ptype TEXT, frame TEXT)")
    rows = [("n1", "N", "DECIDED", "direct", "PLACE", "token", 50, "role@jawiki+role@codex:code"),
            ("n2", "N", "MULTIPLE", "direct", "PLACE,TIME", "token", 40, "role@jawiki+role@codex:code"),
            ("n3", "N", "DECIDED", "direct", "PLACE", "token", 40, "role@jawiki+gen_definition"),
            ("n4", "N", "DECIDED", "direct", "PLACE", "token", 90, "role@jawiki+definition@jawiki"),
            ("n5", "N", "DECIDED", "direct", "PLACE", "token", 80, "seed"),
            ("n6", "NP", "DECIDED", "direct", "PLACE", "token", 30, "hearst@jawiki"),
            ("n7", "P", "DECIDED", "direct", "PLACE", "token", 70, "role@jawiki"),
            ("n8", "N", "DECIDED", "direct", "TIME", "token", 70, "role@jawiki"),
            ("n9", "N", "DECIDED", "estimated", "PLACE", "token", 70, "gen_definition"),
            ("n10", "N", "DECIDED", "direct", "PLACE", "token", 20, "alias@jawiki"),
            ("n11", "N", "DECIDED", "direct", "PLACE", "token", 10, "paren_alias@jawiki"),
            ("n12", "N", "DECIDED", "direct", "PLACE", "token", 10, "title_qualifier@jawiki"),
            ("n13", "N", "DECIDED", "direct", "PLACE", "token", 10, "definition_recovered@jawiki"),
            ("v1", "P", "DECIDED", "direct", "P_MOVE", "token", 500, "gen_frame"),
            ("v2", "P", "DECIDED", "direct", "P_MOVE", "token", 300, "gen_frame"),
            ("v3", "N", "DECIDED", "direct", "PLACE", "token", 200, "role@jawiki"),
            ("v4", "NP", "UNPLACED", None, "", "token", 300, ""),
            ("s1", "P", "DECIDED", "direct", "P_GIVE", "token", 100, "seed"),
            ("s2", "N", "DECIDED", "direct", "PLACE", "token", 100, "seed")]
    con.executemany("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", rows)
    for w in ("v1", "v2", "v3", "gone"):
        con.execute("INSERT INTO generated_frames VALUES (?,?,?,?,?,?,?)", (w, "m", "low", "b", 1, "P_MOVE", "{}"))
    con.commit()
    con.close()
    return d


def test_the_ntype_list_keeps_direct_place_nouns_without_a_definition_like_arm(small_placement):
    rows, boundary, reasons = gce.select_needs_ntype(str(small_placement), 1000)
    assert [r["word"] for r in rows] == ["v3", "n1", "n2", "n3", "n6"]            # n_seen desc, string order inside one
    assert boundary == 30
    assert reasons["not_direct"] == 2                                              # n9 (estimated), v4 (no origin)
    assert reasons["no_place"] == 4                                                # n8, v1, v2, s1
    assert reasons["ns_not_noun"] == 1                                             # n7
    assert reasons["definition_like_arm"] == 7                                     # n4 n5 n10 n11 n12 n13 s2


def test_the_ntype_list_includes_the_whole_tie_at_the_boundary(small_placement):
    rows, boundary, _r = gce.select_needs_ntype(str(small_placement), 3)
    assert boundary == 40 and [r["word"] for r in rows] == ["v3", "n1", "n2", "n3"]       # n2 and n3 tie with the 3rd


def test_the_role_list_is_the_generated_frames_and_the_predicate_seeds_that_are_predicate_headwords(small_placement):
    seeds_pred = sorted(w for ws in ct.SEEDS_PRED.values() for w in ws)
    con = sqlite3.connect(str(small_placement / "placement.sqlite"))
    con.execute("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", (seeds_pred[0], "P", "DECIDED", "direct", "P_GIVE", "token", 5, "seed"))
    con.execute("INSERT INTO headwords VALUES (?,?,?,?,?,?,?,?)", (seeds_pred[1], "N", "DECIDED", "direct", "PLACE", "token", 5, "seed"))
    con.commit()
    con.close()
    rows, boundary, counts = gce.select_needs_role(str(small_placement), 1000)
    assert [r["word"] for r in rows] == ["v1", "v2", seeds_pred[0]]
    assert counts == {"from_generated_frames": 4, "from_seeds_pred": len(seeds_pred), "overlap": 0,
                      "not_headword": 1 + len(seeds_pred) - 2, "ns_not_predicate": 2}
    assert {r["word"]: r["source"] for r in rows}["v1"] == "generated_frames"


# --- run / collect / summarize against a fake codex --------------------------------------------------
FAKE = r'''#!%(python)s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
prompt = argv[-1]
words = []
for line in prompt.splitlines():
    if line.startswith("WORDS_JSON:"):
        words = json.loads(line[len("WORDS_JSON:"):].strip())
out = argv[argv.index("-o") + 1]
schema = json.load(open(argv[argv.index("--output-schema") + 1], encoding="utf-8"))
kind = "ntype" if "definition" in schema["properties"]["items"]["items"]["properties"] else "role"
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message"}}))
items = []
for w in words:
    if kind == "ntype":
        items.append({"word": w, "definition": "x。", "types": ["PLACE", "RELATIVE_POSITION"]})
    else:
        items.append({"word": w, "frame": [{"particle": "に", "roles": [{"role": "goal", "types": ["PLACE"]},
                                                                      {"role": "recipient", "types": ["PERSON"]}]}]})
json.dump({"items": items}, open(out, "w", encoding="utf-8"), ensure_ascii=False)
'''


def make_fake(tmp):
    p = tmp / "fakecodex"
    p.write_text(FAKE % {"python": PYTHON}, encoding="utf-8")
    p.chmod(0o755)
    return p


@pytest.mark.parametrize("kind", ["ntype", "role"])
def test_run_collect_summarize_with_a_fake_codex_use_low_effort_and_the_model(tmp_path, kind):
    needs = tmp_path / "needs.jsonl"
    needs.write_text("".join(json.dumps({"word": "w%02d" % i}) + "\n" for i in range(5)), encoding="utf-8")
    out_dir = tmp_path / "G"
    fake = make_fake(tmp_path)
    rc = gce.main(["run", "--kind", kind, "--needs", str(needs), "--out-dir", str(out_dir), "--codex-bin", str(fake),
                   "--batch-size", "2", "--slots", "2", "--max-calls", "10"])
    assert rc == 0
    led = [json.loads(l) for l in open(out_dir / "ledger.jsonl", encoding="utf-8")]
    starts = [e for e in led if e["ev"] == "start"]
    assert len(starts) == 3 and all(e["ev"] == "end" and e["status"] == "ok" for e in led if e["ev"] == "end")
    argv = starts[0]["argv"]
    assert "gpt-6-luna" in argv and "model_reasoning_effort=\"low\"" in argv
    assert sorted(sum((e["words"] for e in starts), [])) == ["w%02d" % i for i in range(5)]
    meta = json.load(open(out_dir / "batches.json", encoding="utf-8"))["meta"]
    assert meta["kind"] == kind and meta["schema_sha256"] == gce.schema_sha256(gce.KINDS[kind]["schema"])
    out = tmp_path / "out.jsonl"
    assert gce.main(["collect", "--kind", kind, "--out-dir", str(out_dir), "--out", str(out)]) == 0
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    assert sorted(r["word"] for r in rows) == ["w%02d" % i for i in range(5)]
    assert all(r["provenance"]["effort"] == "low" and r["provenance"]["model"] == "gpt-6-luna" for r in rows)
    if kind == "ntype":
        assert all(r["types"] == ["PLACE", "RELATIVE_POSITION"] and r["abstained"] is False for r in rows)
    else:
        assert all(r["frame"] == {"に": [{"role": "recipient", "types": ["PERSON"]}, {"role": "goal", "types": ["PLACE"]}]}
                   for r in rows)
    s = gce.summarize(str(out_dir))
    assert s["kind"] == kind and s["calls"] == 3 and s["batches_ok"] == 3 and s["words_answered"] == 5
    assert s["words_invalid"] == 0 and s["effort"] == "low" and s["model"] == "gpt-6-luna"
    if kind == "ntype":
        assert s["words_no_type"] == 0
    else:
        assert s["words_frame_dup_particle"] == 0 and s["words_role_dup"] == 0


def test_the_noun_and_predicate_outputs_are_unchanged_by_the_new_forms():
    # the two readers of the old forms give the same answer as before on a small input
    ans, st = gce.parse_output(["a"], {"items": [{"word": "a", "definition": "d", "hypernym": "h"}]})
    assert ans == {"a": ("d", "h")} and st["answered"] == 1 and "no_type" not in st
    ans, st = gce.parse_output_pred(["a"], {"items": [{"word": "a", "ptype": "P_MOVE", "frame": [
        {"particle": "に", "types": ["PLACE"]}]}]})
    assert ans == {"a": ("P_MOVE", {"に": ["PLACE"]})} and "role_dup" not in st
    ans, st = gce.parse_output_pred(["a"], {"items": [{"word": "a", "ptype": "P_MOVE", "frame": [
        {"particle": "に", "types": ["RELATIVE_POSITION"]}]}]})
    assert ans == {} and st["invalid"] == 1                    # the predicate form is still the 17 types
