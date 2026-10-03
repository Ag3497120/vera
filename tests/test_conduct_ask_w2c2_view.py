"""W2-c2 round 3 (auditor's ruling B1): a markdown frame and the jsonl compiled from it give the same view and the same answers.

``project_frame.compile_frame`` writes a CHOICE / CONFIRM / SCOPE line of ``[decisions]`` as TWO records: a DECISION (witness has no
``question_kind``) and a POLICY that names it (``witness.authority_record_id``).  The markdown view reads such a line as a policy only;
before this round the jsonl view also kept the DECISION of the pair as a decision of its own, which gave every policy term a "subject"
entry (a value that matches but whose subject is not asked looked like an answer).  The pair is told by the id, never by a word or a value.

What is NOT fixed here (documented in docs/CONDUCT_ASK.md section 11): the completion criteria are words by their id (markdown ``c1``,
jsonl a hash id) and one example frame has a policy condition that the compiler normalises (``欠測の扱い`` / ``欠測扱い``).  Both are pinned below
as they are, so that a change shows."""
from __future__ import annotations

import collections
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "conduct_ask"))
from verantyx import conduct_ask as ca  # noqa: E402
from verantyx.memory_frame import Memory  # noqa: E402
from verantyx.project_frame import FrameCompileError, compile_frame, load_conduct_frame, load_frame  # noqa: E402

CA = ROOT / "tests" / "conduct_ask"
MAP_EMPTY = str(CA / "w2c2" / "map_fake_empty.json")
SETS = {"fixtures": CA / "fixtures", "w2g": CA / "w2g", "w2g2": CA / "w2g2", "w2g3": CA / "w2g3", "w2c2": CA / "w2c2", "supp": CA / "w2c2" / "supp"}
FRAME_FILES = sorted(CA.glob("**/frames/*.md")) + sorted((ROOT / "docs" / "frames" / "examples").glob("*.md"))
# the compiler cannot encode these frames (FrameCompileError: e.g. Japanese-only entries it has no typed record for): counted, not hidden
EXPECTED_FRAME_FILES, EXPECTED_COMPILABLE, EXPECTED_NOT_COMPILABLE = 42, 13, 29  # integration: W2-h added docs/frames/examples/routing_two_lineages.md (compiles)


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.fixture(scope="module")
def compiled(tmp_path_factory) -> dict:
    """{markdown path: jsonl path} for every frame that compiles, and the list of those that do not (with the error type)."""
    tmp = tmp_path_factory.mktemp("w2c2view")
    ok: dict[str, str] = {}
    bad: list[tuple[str, str]] = []
    for k, f in enumerate(FRAME_FILES):
        log = tmp / f"{k:02d}_{f.stem}.jsonl"
        try:
            compile_frame(load_frame(f), Memory(str(log)))
        except FrameCompileError as exc:
            bad.append((str(f), type(exc).__name__))
            continue
        ok[str(f)] = str(log)
    return {"ok": ok, "bad": bad}


def terms(view: "ca.FrameView") -> dict:
    """Every exact term -> the multiset of the groups of its entries, without the completion criteria (their words are their ids)."""
    idx = ca.TermIndex(view)
    out = {}
    for t, es in idx.exact.items():
        groups = sorted(e.group for e in es if e.group != "criterion")
        if groups:
            out[t] = groups
    return out


def test_the_number_of_frames_that_compile_is_pinned_and_the_rest_are_counted(compiled):
    assert len(FRAME_FILES) == EXPECTED_FRAME_FILES
    assert len(compiled["ok"]) == EXPECTED_COMPILABLE
    assert len(compiled["bad"]) == EXPECTED_NOT_COMPILABLE
    assert {t for _, t in compiled["bad"]} == {"FrameCompileError"}


def test_markdown_and_jsonl_views_have_the_same_decisions_and_the_same_terms(compiled):
    known_differences = {}
    for md, log in compiled["ok"].items():
        vm, vj = ca.build_view(load_conduct_frame(md)), ca.build_view(load_conduct_frame(log))
        dm = collections.Counter((d.subject, d.value) for d in vm.decisions)
        dj = collections.Counter((d.subject, d.value) for d in vj.decisions)
        assert dm == dj, (md, dm - dj, dj - dm)
        tm, tj = terms(vm), terms(vj)
        diff = {k: (tm.get(k), tj.get(k)) for k in set(tm) | set(tj) if tm.get(k) != tj.get(k)}
        if diff:
            known_differences[Path(md).name] = diff
    # the one known difference: the compiler normalises the condition of a policy (witness.condition keeps the markdown's words)
    assert known_differences == {"experiment_data_pipeline.md": {"欠測の扱い": (["policy"], None), "欠測扱い": (None, ["policy"])}}


def test_the_decision_of_a_policy_pair_is_found_by_the_id_and_not_by_a_word(compiled, tmp_path):
    """Remove ``authority_record_id`` from every POLICY of the compiled f05_retry: the four DECISIONs that were the pair's come back
    into ``decisions`` (so the fix cannot be a match on words or values)."""
    md = str(CA / "fixtures" / "frames" / "f05_retry.md")
    log = Path(compiled["ok"][md])
    vm = ca.build_view(load_conduct_frame(md))
    v_fixed = ca.build_view(load_conduct_frame(str(log)))
    assert [(d.subject, d.value) for d in v_fixed.decisions] == [(d.subject, d.value) for d in vm.decisions]
    out, removed = [], 0
    for ln in log.read_text(encoding="utf-8").splitlines():
        e = json.loads(ln)
        r = e.get("record") if e.get("op") == "write" else None
        if r and r["kind"] == "POLICY" and isinstance(r.get("witness"), dict) and "authority_record_id" in r["witness"]:
            del r["witness"]["authority_record_id"]
            removed += 1
        out.append(json.dumps(e, ensure_ascii=False))
    assert removed == 4
    cut = tmp_path / "f05_nolink.jsonl"
    cut.write_text("\n".join(out) + "\n", encoding="utf-8")
    v_cut = ca.build_view(load_conduct_frame(str(cut)))
    back = {(d.subject, d.value) for d in v_cut.decisions} - {(d.subject, d.value) for d in v_fixed.decisions}
    assert back == {("circuit breaker", "out of scope"), ("adding a runtime dependency", "not permitted"), ("jitter", "full jitter"),
                    ("clock source", "monotonic clock")}


def test_a_plain_decision_with_the_same_subject_as_a_policy_is_kept(tmp_path):
    """The pair is told by the id: a frame with a plain decision AND a policy on the same subject ("jitter") keeps the plain decision and
    only the plain decision as a decision, in markdown and after compiling."""
    src = (CA / "fixtures" / "frames" / "f05_retry.md").read_text(encoding="utf-8")
    assert "D5: CHOICE | jitter | full jitter" in src and "D6: CHOICE | clock source | monotonic clock" in src
    md = tmp_path / "same_subject.md"
    md.write_text(src.replace("D6: CHOICE | clock source | monotonic clock", "D6: CHOICE | clock source | monotonic clock\nD7: jitter => off in unit tests"),
                  encoding="utf-8")
    log = tmp_path / "same_subject.jsonl"
    compile_frame(load_frame(md), Memory(str(log)))
    vm, vj = ca.build_view(load_conduct_frame(str(md))), ca.build_view(load_conduct_frame(str(log)))
    dm = collections.Counter((d.subject, d.value) for d in vm.decisions)
    dj = collections.Counter((d.subject, d.value) for d in vj.decisions)
    assert dm == dj and ("jitter", "off in unit tests") in dm and ("jitter", "full jitter") not in dm


def answer_six(res: dict) -> tuple:
    m = res.get("mapping") or {}
    return (res["decision"], res["answer"], res["answer_option_index"], res["escalate_reason"], res["escalate_detail"], m.get("outcome"))


def test_markdown_and_jsonl_frames_give_the_same_answers_over_all_the_data(compiled):
    """Every question of the frozen W2-c / W2-g data, the new data and the supplement whose frame compiles, off and with the empty
    made-up mapping (``mapping.outcome`` included: a view that differs only in a subject entry showed up there)."""
    comparisons, frames, diffs = 0, set(), []
    for sname, d in SETS.items():
        for ln in (d / "items.jsonl").read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            it = json.loads(ln)
            md = str(d / "frames" / f"{it['frame_id']}.md")
            if md not in compiled["ok"]:
                continue
            frames.add(md)
            for mode in ("off", "fakemap"):
                kw = {"vocab_llm": "fake", "map_fake": MAP_EMPTY} if mode == "fakemap" else {}
                a = ca.answer_question(md, it["question"], it.get("options"), **kw)
                b = ca.answer_question(compiled["ok"][md], it["question"], it.get("options"), **kw)
                comparisons += 1
                if answer_six(a) != answer_six(b):
                    diffs.append((sname, it["id"], mode, answer_six(a), answer_six(b)))
    assert diffs == []
    assert comparisons == 236 and len(frames) == 8
