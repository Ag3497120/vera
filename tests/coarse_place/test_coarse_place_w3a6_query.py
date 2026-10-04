"""W3-a6 D8: query fields are appended only for placements with role_frames."""
import json
import sqlite3

from tools import build_coarse_placement as bcp
from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

from test_coarse_place_build import build, make_codex_db
from test_coarse_place_review3 import write_jawiki
from test_coarse_place_w3a3_query import CFG, frow


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _ledger(path):
    events = [
        {"ev": "start", "batch": "b00000_0123456789ab", "attempt": 1,
         "t": "2026-10-04T00:00:00+00:00"},
        {"ev": "end", "batch": "b00000_0123456789ab", "attempt": 1, "status": "ok",
         "sec": 0.1, "t": "2026-10-04T00:00:00.100000+00:00"},
    ]
    path.write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")


def _role(word, frame):
    return {"word": word, "frame": frame, "abstained": False,
            "provenance": {"origin": "generated", "model": "gpt-6-luna", "effort": "low",
                           "batch_id": "b00000_0123456789ab", "attempt": 1, "out_sha256": "0" * 64}}


def _build(tmp_path, role_path=None, role_ledger=None):
    root = tmp_path / ("with_roles" if role_path is not None else "without_roles")
    root.mkdir()
    texts = ["人が言葉を叫んだ。"] * 14
    cdir = root / "cx"
    for family in ("conversation", "narrative"):
        make_codex_db(cdir, family, texts)
    jawiki = root / "jw.jsonl"
    write_jawiki(jawiki, [("構成語", "構成語は、検査用の語である。")])
    frame_path = root / "predicate_frames.jsonl"
    _jsonl(frame_path, [frow("叫ぶ", "P_COMMUNICATE", {"が": ["PERSON"], "を": ["INFO_LANGUAGE"]})])
    frame_ledger = root / "predicate_frames.ledger.jsonl"
    _ledger(frame_ledger)
    extra = ["--generated-frames", str(frame_path), "--generated-frames-ledger", str(frame_ledger)]
    if role_path is not None:
        extra += ["--role-frames", str(role_path), "--role-frames-ledger", str(role_ledger)]
    out = root / "placement"
    assert build(out, jawiki=jawiki, codex_dir=cdir, families="conversation,narrative", extra=extra,
                 cfg=dict(CFG, role_frame_min_sources=2)) == 0
    return out


def test_confirmed_role_fields_follow_the_shared_distribution_check_and_are_last(tmp_path):
    frame = {"が": [{"role": "agent", "types": ["PERSON"]}],
             "を": [{"role": "patient", "types": ["INFO_LANGUAGE"]}]}
    role_path, role_ledger = tmp_path / "roles.jsonl", tmp_path / "roles.ledger.jsonl"
    _jsonl(role_path, [_role("叫ぶ", frame)])
    _ledger(role_ledger)
    placement = _build(tmp_path, role_path, role_ledger)

    answer = cp.query("叫ぶ", placement=str(placement))
    assert list(answer)[-3:] == ["role_frame_status", "role_frame", "role_frame_unconfirmed"]
    assert answer["role_frame_status"] == "CONFIRMED" and answer["role_frame"] is not None
    assert answer["role_frame"] == {
        "が": [{"role": "agent", "types": ["PERSON"],
               "backed_by": ["role_distribution@codex:conversation", "role_distribution@codex:narrative"]}],
        "を": [{"role": "patient", "types": ["INFO_LANGUAGE"],
               "backed_by": ["role_distribution@codex:conversation", "role_distribution@codex:narrative"]}],
    }
    assert answer["role_frame_unconfirmed"] == {}
    assert cp.query("叫ぶ", placement=str(placement))["role_frame"] == answer["role_frame"]
    assert bcp.main(["verify", "--placement", str(placement)]) == 0


def test_table_without_a_word_row_reports_no_role_frame_and_old_placements_have_no_new_keys(tmp_path):
    role_path, role_ledger = tmp_path / "roles.jsonl", tmp_path / "roles.ledger.jsonl"
    _jsonl(role_path, [_role("叫ぶ", {"が": [{"role": "agent", "types": ["PERSON"]}]})])
    _ledger(role_ledger)
    with_roles = _build(tmp_path, role_path, role_ledger)
    known_seed = next(w for values in ct.SEEDS_PRED.values() for w in values if w != "叫ぶ")
    no_row = cp.query(known_seed, placement=str(with_roles))
    assert no_row["role_frame_status"] == "NO_ROLE_FRAME"
    assert no_row["role_frame"] is None and no_row["role_frame_unconfirmed"] is None

    old = _build(tmp_path)
    cp._CACHE.clear()
    answer = cp.query("叫ぶ", placement=str(old))
    assert not {"role_frame_status", "role_frame", "role_frame_unconfirmed"} & set(answer)
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % old, uri=True)
    tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert "role_frames" not in tables and "generated_noun_types" not in tables
    assert bcp.main(["verify", "--placement", str(old)]) == 0
