"""Shape of the W2-g self-made fixtures (paraphrased questions; frozen before the code that uses them)."""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402,F401  (puts the repository root on sys.path)

from verantyx import conduct_ask as ca  # noqa: E402
from verantyx.project_frame import load_conduct_frame  # noqa: E402

W2G = Path(__file__).resolve().parent / "conduct_ask" / "w2g"


def _items() -> list[dict]:
    return [json.loads(ln) for ln in (W2G / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]


def _ids(name: str) -> list[str]:
    return [ln.strip() for ln in (W2G / name).read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_w2g_fixture_shape():
    items = _items()
    frames = sorted((W2G / "frames").glob("*.md"))
    assert len(items) >= 60 and len(frames) >= 6
    assert len({i["id"] for i in items}) == len(items)
    per_frame = collections.Counter(i["frame_id"] for i in items)
    assert set(per_frame) == {f.stem for f in frames}
    cat = collections.Counter(i["w2c"]["category"] for i in items)
    assert set(cat) == {"direct", "combined", "oov", "escalate"} and set(cat.values()) == {len(items) // 4}
    lang = collections.Counter(i["lang"] for i in items)
    assert lang["ja"] >= 24 and lang["en"] >= 24
    with_opts = [i for i in items if i["options"]]
    assert len(with_opts) >= 56 and len(items) - len(with_opts) <= 8
    assert any(len(i["options"]) == 3 for i in with_opts) and any(i["options"] == ["はい", "いいえ"] for i in with_opts)
    assert any(i["options"] == ["Yes", "No"] for i in with_opts)
    kinds = collections.Counter(i["w2g"].get("escalate_kind") for i in items if i["w2c"]["category"] == "escalate")
    assert kinds["A"] >= 3 and kinds["B"] >= 2 and kinds["C"] >= 2 and kinds["D"] >= 2
    assert kinds["E"] >= 2 and kinds["F"] >= 2 and kinds["G"] >= 1 and kinds["H"] >= 2
    held = set(_ids("holdout.txt"))
    assert len(held) == 2 and held <= set(per_frame)
    assert {next(i["lang"] for i in items if i["frame_id"] == h) for h in held} == {"ja", "en"}
    subset = _ids("claude_subset.txt")
    ids = {i["id"] for i in items}
    assert 0 < len(subset) <= 30 and set(subset) <= ids
    assert {i["frame_id"] for i in items if i["id"] in subset} == held
    views = {f.stem: ca.build_view(load_conduct_frame(str(f))) for f in frames}   # every frame loads
    for fid, v in views.items():
        assert v.phases and v.edges and v.policies
    for it in items:
        v = views[it["frame_id"]]
        rec_ids = ({e.ref.id for e in v.edges} | {p.ref.id for p in v.policies} | {d.ref.id for d in v.decisions}
                   | {a.ref.id for a in v.forbidden} | {a.ref.id for a in v.protected} | {c.id for c in v.criteria}
                   | {x.id for x in v.invariants} | {r.id for _, r in v.allow} | {e.id for e in v.escalations})
        assert set(it["expect"]["records"]) <= rec_ids, it["id"]
        exp = it["expect"]
        if exp["decision"] == "answer":
            if it["options"]:
                assert 0 <= exp["answer_option_index"] < len(it["options"]) and exp["answer"] == it["options"][exp["answer_option_index"]]
            else:
                assert exp["answer_option_index"] is None and exp["answer"]
        else:
            assert exp["answer"] is None and exp["answer_option_index"] is None and it["w2c"]["escalate_reason"]
        assert it["w2g"]["paraphrase"] is True and set(it["w2c"]) >= {"category", "oov_none", "escalate_reason", "trap", "permission"}


# ---- the second, fresh G3 data set (w2g2): written and frozen before the order / value changes of conduct_map.py -----------

W2G2 = Path(__file__).resolve().parent / "conduct_ask" / "w2g2"


def test_w2g2_fixture_shape():
    items = [json.loads(ln) for ln in (W2G2 / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    frames = sorted((W2G2 / "frames").glob("*.md"))
    assert len(items) == 64 and len(frames) == 6
    assert len({i["id"] for i in items}) == 64
    assert set(collections.Counter(i["frame_id"] for i in items)) == {f.stem for f in frames}
    cat = collections.Counter(i["w2c"]["category"] for i in items)
    assert dict(cat) == {"direct": 16, "combined": 16, "oov": 16, "escalate": 16}
    lang = collections.Counter(i["lang"] for i in items)
    assert lang["ja"] >= 24 and lang["en"] >= 24
    assert len({i["frame_id"] for i in items if i["lang"] == "ja"}) == 3 and len({i["frame_id"] for i in items if i["lang"] == "en"}) == 3
    with_opts = [i for i in items if i["options"]]
    assert len(with_opts) >= 56 and len(items) - len(with_opts) <= 8
    assert any(len(i["options"]) == 3 for i in with_opts) and any(i["options"] == ["はい", "いいえ"] for i in with_opts)
    assert any(i["options"] == ["Yes", "No"] for i in with_opts)
    chains = [i for i in items if i["w2c"]["category"] == "combined" and i["w2g"]["note"] == "order chain"]
    assert len(chains) >= 6
    kinds = collections.Counter(i["w2g"].get("escalate_kind") for i in items if i["w2c"]["category"] == "escalate")
    for k in ("B_PAST", "NEG", "ADVICE", "B_SUBJECT", "COND", "G", "D", "F", "H"):
        assert kinds[k] >= 1, k
    assert kinds["A"] >= 3 and kinds["C"] >= 2 and kinds["E"] >= 2
    held = {ln.strip() for ln in (W2G2 / "holdout.txt").read_text(encoding="utf-8").splitlines() if ln.strip()}
    assert len(held) == 2 and held <= {f.stem for f in frames}
    assert {next(i["lang"] for i in items if i["frame_id"] == h) for h in held} == {"ja", "en"}
    subset = [ln.strip() for ln in (W2G2 / "claude_subset.txt").read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert 0 < len(subset) <= 30 and set(subset) <= {i["id"] for i in items}
    assert {i["frame_id"] for i in items if i["id"] in subset} == held
    views = {f.stem: ca.build_view(load_conduct_frame(str(f))) for f in frames}
    for fid, v in views.items():
        assert v.phases and v.edges and v.policies
    for it in items:
        v = views[it["frame_id"]]
        rec_ids = ({e.ref.id for e in v.edges} | {p.ref.id for p in v.policies} | {d.ref.id for d in v.decisions}
                   | {a.ref.id for a in v.forbidden} | {a.ref.id for a in v.protected} | {c.id for c in v.criteria}
                   | {x.id for x in v.invariants} | {r.id for _, r in v.allow} | {e.id for e in v.escalations})
        exp = it["expect"]
        assert set(exp["records"]) <= rec_ids, it["id"]
        if exp["decision"] == "answer":
            if it["options"]:
                assert 0 <= exp["answer_option_index"] < len(it["options"]) and exp["answer"] == it["options"][exp["answer_option_index"]]
            else:
                assert exp["answer_option_index"] is None and exp["answer"]
        else:
            assert exp["answer"] is None and exp["answer_option_index"] is None and it["w2c"]["escalate_reason"]
