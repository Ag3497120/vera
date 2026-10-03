"""W3-a4 (docs section 12.17, P1): the answers of r7 do not change with the new cover rule.  The values in
``data/w3a4_r7_answer_sha.tsv`` are the sha256 of ``json.dumps(answer, ensure_ascii=False)`` for the words
the new rule would change, the 13 NOT_CONFIRMED words of W5-d and the 48 direct generated-frame words,
taken with the code before W3-a4.  The test does not skip: it needs r7.

Integration (auditor, 2026-10-04): W5-e (A-4, docs/COARSE_PLACEMENT.md) makes a CONFIRMED frame keep only the types the distribution
backs, which changes the `frame` of 30 CONFIRMED words on r7 on purpose (frame_status, state, origin and top unchanged); the hashes of
those 30 rows were re-frozen under dev with W5-e. The 43 other rows are the original W3-a4 values."""
import hashlib
import json
from pathlib import Path

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
# Integration (auditor, 2026-10-04): the suite runs split across two machines and the registered build lives outside the tree, so a machine without
# it SKIPS with a visible reason instead of failing (same treatment as the W5-d r7 tests). Where r7 exists nothing changes.
import os as _os
import pytest as _pytest
pytestmark = _pytest.mark.skipif(not _os.path.isdir(R7), reason="ENV_MISSING[coarse placement r7/run1]")
DATA = Path(__file__).resolve().parent / "data" / "w3a4_r7_answer_sha.tsv"


def rows():
    return [l.rstrip("\n").split("\t") for l in DATA.read_text(encoding="utf-8").splitlines()]


def test_r7_exists_and_the_default_rule_is_the_old_one():
    assert (Path(R7) / "placement.sqlite").exists()
    assert ct.DEFAULT_CONFIG["frame_cover_rule"] == "all9"
    pl, err = cp._open(R7)
    assert err is None and pl.cfg["frame_cover_rule"] == "all9"      # r7's stored config has no such key
    assert "frame_cover_rule" not in json.loads(pl.con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0])


def test_the_answers_of_r7_are_byte_identical_to_the_frozen_hashes():
    rs = rows()
    assert len(rs) == 73 and {r[0] for r in rs} == {"twelve", "not_confirmed", "direct"}
    bad = []
    for kind, w, sha, fs in rs:
        ans = cp.query(w, placement=R7)
        h = hashlib.sha256(json.dumps(ans, ensure_ascii=False).encode("utf-8")).hexdigest()
        if h != sha or ans.get("frame_status") != fs:
            bad.append((kind, w))
    assert not bad, bad


def test_the_twelve_words_the_new_rule_would_change_stay_estimates_on_r7():
    tw = [r[1] for r in rows() if r[0] == "twelve"]
    assert len(tw) == 12
    for w in tw:
        a = cp.query(w, placement=R7)
        assert a["origin"] == "estimated" and a["frame_status"] == "ESTIMATED", w
        assert a["decided_by"] == ["gen_frame"], w
