"""W3-a6 D7: optional generated type/frame tables and their placement outcomes."""
import json
import sqlite3
from pathlib import Path

from tools import build_coarse_placement as bcp
from verantyx import coarse_types as ct

from test_coarse_place_build import MINI, build, q


def _provenance(batch="b00000_0123456789ab"):
    return {"origin": "generated", "model": "gpt-6-luna", "effort": "low",
            "batch_id": batch, "attempt": 1, "out_sha256": "0" * 64}


def _ledger(path):
    events = [
        {"ev": "start", "batch": "b00000_0123456789ab", "attempt": 1,
         "t": "2026-10-04T00:00:00+00:00"},
        {"ev": "end", "batch": "b00000_0123456789ab", "attempt": 1, "status": "ok",
         "sec": 0.1, "t": "2026-10-04T00:00:00.100000+00:00"},
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def test_readers_count_abstentions_invalid_rows_duplicates_and_exclusions(tmp_path):
    ntypes = tmp_path / "ntypes.jsonl"
    _jsonl(ntypes, [
        {"word": "a", "definition": "a definition", "types": ["PLACE", "RELATIVE_POSITION"],
         "abstained": False, "provenance": _provenance()},
        {"word": "b", "definition": None, "types": [], "abstained": True, "provenance": _provenance()},
        {"word": "c", "definition": "bad", "types": ["NO_SUCH_TYPE"], "abstained": False,
         "provenance": _provenance()},
        {"word": "d", "definition": "contains HOLDOUT", "types": ["PLACE"], "abstained": False,
         "provenance": _provenance()},
        {"word": "e", "definition": "one", "types": ["PLACE"], "abstained": False,
         "provenance": _provenance()},
        {"word": "e", "definition": "two", "types": ["TIME"], "abstained": False,
         "provenance": _provenance()},
    ])
    rows, dropped, lines = bcp.read_generated_noun_types(str(ntypes), ["HOLDOUT"])
    assert set(rows) == {"a"} and rows["a"]["types"] == ["PLACE", "RELATIVE_POSITION"]
    assert dropped == {"abstained": 1, "invalid": 1, "excluded_term": 1, "dup_word": 1}
    assert lines == 6

    roles = tmp_path / "roles.jsonl"
    _jsonl(roles, [
        {"word": "p", "frame": {"に": [{"role": "goal", "types": ["PLACE"]}]},
         "abstained": False, "provenance": _provenance()},
        {"word": "a", "frame": None, "abstained": True, "provenance": _provenance()},
        {"word": "b", "frame": {"で": [{"role": "cause", "types": []}]},
         "abstained": False, "provenance": _provenance()},
        {"word": "c", "frame": {"に": [{"role": "goal", "types": ["PLACE"]},
                                           {"role": "goal", "types": ["TIME"]}]},
         "abstained": False, "provenance": _provenance()},
    ])
    rows, dropped, lines = bcp.read_role_frames(str(roles), [])
    assert rows["p"]["frame"] == {"に": [{"role": "goal", "types": ["PLACE"]}]}
    assert dropped == {"abstained": 1, "invalid": 2, "excluded_term": 0, "dup_word": 0}
    assert lines == 4


def test_optional_tables_are_created_only_for_inputs_and_record_generated_claims(tmp_path):
    plain = tmp_path / "plain"
    assert build(plain) == 0
    plain_manifest = json.loads((plain / "manifest.json").read_text(encoding="utf-8"))
    con = sqlite3.connect(str(plain / "placement.sqlite"))
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert not ({"generated_noun_types", "role_frames"} & tables)
    assert "generated_noun_types" not in plain_manifest and "role_frames" not in plain_manifest
    assert bcp.main(["verify", "--placement", str(plain)]) == 0

    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % plain, uri=True)
    candidate = con.execute("SELECT word FROM headwords WHERE ns='N' AND state='DECIDED' "
                            "AND origin='direct' AND top='PLACE' ORDER BY word LIMIT 1").fetchone()
    con.close()
    assert candidate is not None
    noun_word = candidate[0]
    predicate_word = next(w for values in ct.SEEDS_PRED.values() for w in values)

    ntype_path, role_path = tmp_path / "ntypes.jsonl", tmp_path / "roles.jsonl"
    ntype_rows = [
        {"word": noun_word, "definition": "constructed test definition", "types": ["RELATIVE_POSITION"],
         "abstained": False, "provenance": _provenance()},
        {"word": "__w3a6_absent_noun__", "definition": "constructed", "types": ["RELATIVE_POSITION"],
         "abstained": False, "provenance": _provenance()},
        {"word": predicate_word, "definition": "constructed", "types": ["RELATIVE_POSITION"],
         "abstained": False, "provenance": _provenance()},
    ]
    role_rows = [
        {"word": predicate_word, "frame": {"が": [{"role": "agent", "types": ["PERSON"]}]},
         "abstained": False, "provenance": _provenance()},
        {"word": noun_word, "frame": {"が": [{"role": "agent", "types": ["PERSON"]}]},
         "abstained": False, "provenance": _provenance()},
        {"word": "__w3a6_absent_predicate__", "frame": {}, "abstained": False,
         "provenance": _provenance()},
    ]
    _jsonl(ntype_path, ntype_rows)
    _jsonl(role_path, role_rows)
    nledger, rledger = tmp_path / "ntypes.ledger.jsonl", tmp_path / "roles.ledger.jsonl"
    _ledger(nledger)
    _ledger(rledger)
    out = tmp_path / "with_generated"
    extra = ["--generated-noun-types", str(ntype_path), "--generated-noun-types-ledger", str(nledger),
             "--role-frames", str(role_path), "--role-frames-ledger", str(rledger)]
    assert build(out, extra=extra) == 0
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["generated_noun_types"]["calls"] == 1
    assert manifest["generated_noun_types"]["effort"] == "low"
    assert manifest["generated_noun_types"]["outcomes"]["relpos_declared"] == 3
    assert manifest["generated_noun_types"]["outcomes"]["RELPOS_ADDED"] == 1
    assert manifest["generated_noun_types"]["outcomes"]["ns_not_noun"] == 1
    assert manifest["generated_noun_types"]["outcomes"]["not_in_material"] == 1
    assert manifest["role_frames"]["calls"] == 1 and manifest["role_frames"]["effort"] == "low"
    assert manifest["role_frames"]["outcomes"]["ESTIMATED"] == 1
    assert manifest["role_frames"]["outcomes"]["ns_not_predicate"] == 1
    assert manifest["role_frames"]["outcomes"]["not_in_material"] == 1
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % out, uri=True)
    top = con.execute("SELECT state, origin, top FROM headwords WHERE word=?", (noun_word,)).fetchone()
    n_row = con.execute("SELECT definition, types FROM generated_noun_types WHERE word=?", (noun_word,)).fetchone()
    role_row = con.execute("SELECT frame FROM role_frames WHERE word=?", (predicate_word,)).fetchone()
    con.close()
    assert top == ("MULTIPLE", "direct", "PLACE,RELATIVE_POSITION")
    assert n_row == ("constructed test definition", '["RELATIVE_POSITION"]')
    assert json.loads(role_row[0]) == {"が": [{"role": "agent", "types": ["PERSON"]}]}
    assert q(noun_word, out)["axes"]["gen_relpos"]["why"] == "RELPOS_ADDED"
    assert bcp.main(["verify", "--placement", str(out)]) == 0
