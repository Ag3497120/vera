"""The frame DSL additions: write allowlist, machine-checkable criteria, forbidden actions
(not permitted even with approval) versus protected actions (approval can unlock),
conflict precedence, agent settings.  Every example frame is compiled and its records are
compared with what the file itself says, using a small independent reader."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards)
from test_conduct_entry_support import (EXAMPLE_FRAMES, FIXED_CLOCK, MINIMAL_FRAME, ROOT, VERA_FRAME,
                                        compiled_records)

NEW_SECTIONS = ("write_allowlist", "forbidden_actions", "conflict_precedence", "agent_settings")
BASE_LINES = len(MINIMAL_FRAME.splitlines())
ROW_LINE = BASE_LINES + 2  # the first entry under a section header appended to MINIMAL_FRAME


def sections_of(text):
    """Independent reader: section name -> list of entry rows (comments and blanks dropped)."""
    result, current = {}, None
    for raw in text.splitlines():
        row = raw.strip()
        if not row or row.startswith("#"):
            continue
        header = re.fullmatch(r"\[([a-z_]+)\]", row)
        if header:
            current = header.group(1)
            result[current] = []
        else:
            result[current].append(row)
    return result


def parse_tail(extra, base=MINIMAL_FRAME):
    from verantyx.project_frame import parse_frame

    return parse_frame(base + extra, source="t.md")


def parse_error(extra, base=MINIMAL_FRAME):
    from verantyx.project_frame import FrameParseError

    with pytest.raises(FrameParseError) as info:
        parse_tail(extra, base)
    return info.value


# ------------------------------------------------------------ example frames
def test_dsl_there_are_at_least_three_original_example_frames_in_different_domains():
    assert len(EXAMPLE_FRAMES) >= 3
    vera_rows = {row for rows in sections_of(VERA_FRAME.read_text(encoding="utf-8")).values() for row in rows}
    projects, goals = set(), set()
    for path in EXAMPLE_FRAMES:
        sec = sections_of(path.read_text(encoding="utf-8"))
        rows = {row for rows in sec.values() for row in rows}
        shared = {row for row in rows & vera_rows if row != "none: none"}
        assert shared == set(), (path.name, shared)  # not a copy of the existing frame
        projects.add(sec["goal"][0])
        goals.add(sec["goal"][1])
    assert len(projects) == len(goals) == len(EXAMPLE_FRAMES)
    assert all("Vera" not in p for p in projects)


@pytest.mark.parametrize("path", EXAMPLE_FRAMES, ids=lambda p: p.stem)
def test_dsl_example_frame_uses_every_new_element(path):
    sec = sections_of(path.read_text(encoding="utf-8"))
    for name in ("write_allowlist", "forbidden_actions", "conflict_precedence"):
        assert sec.get(name) and sec[name] != ["none: none"], (path.name, name)
    assert any('"kind":"command_exit"' in row for row in sec["completion_criteria"])


def test_dsl_the_examples_exercise_japanese_names_empty_lists_and_agent_settings():
    texts = [p.read_text(encoding="utf-8") for p in EXAMPLE_FRAMES]
    assert any(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", t.split("[forbidden_actions]")[1].split("[conflict_precedence]")[0])
               for t in texts)  # a Japanese forbidden action compiles
    assert any("none: none" in t for t in texts)
    assert sum("[agent_settings]" in t for t in texts) >= 2


@pytest.mark.parametrize("path", EXAMPLE_FRAMES, ids=lambda p: p.stem)
def test_dsl_example_frame_records_match_what_the_file_says(path, tmp_path):
    text = path.read_text(encoding="utf-8")
    sec = sections_of(text)
    records = compiled_records(path, tmp_path)
    by_section = {}
    for index, record in enumerate(records):
        by_section.setdefault(record["witness"].get("section"), []).append((index, record))

    # [write_allowlist] -> DECISION "write allowlist <ID>" = path
    expected = [tuple(part.strip() for part in row.split(":", 1)) for row in sec["write_allowlist"]]
    got = by_section["write_allowlist"]
    assert [(r["witness"]["allowlist_id"], r["witness"]["write_path"]) for _, r in got] == expected
    for _, r in got:
        assert r["kind"] == "DECISION"
        assert r["slots"]["choice"] == r["witness"]["write_path"]
        assert r["slots"]["subject"] == f"write allowlist {r['witness']['allowlist_id']}"

    # [forbidden_actions] -> INVARIANT that no approval lifts; never an ESCALATE (nobody may approve)
    rows = [tuple(part.strip() for part in row.split("=>")) for row in sec["forbidden_actions"]]
    got = by_section["forbidden_actions"]
    assert [(r["witness"]["forbidden_action"], r["witness"]["reason"]) for _, r in got] == rows
    for n, (_, r) in enumerate(got, 1):
        action = r["witness"]["forbidden_action"]
        assert r["kind"] == "INVARIANT"
        assert r["slots"] == {"subject": f"forbidden action F{n}",
                              "rule": f"{action} is not permitted even with human approval"}
        assert r["witness"]["approval_effect"] == "NOT_PERMITTED" and r["witness"]["authority_boundary"] is True
        assert not any(x["kind"] == "ESCALATE" and action in (x["witness"].get("condition"), x["slots"]["subject"])
                       for x in records)
    # protected actions keep their old shape: no approval_effect key, and they do have an ESCALATE
    protected = [r for r in records if r["witness"].get("protected_action")]
    assert len(protected) >= len([r for r in sec["protected_actions"] if r != "none: none"]) > 0
    assert not any("approval_effect" in r["witness"] for r in protected)

    # [conflict_precedence] -> exactly the declared pairs, nothing completed by transitivity
    rows = [re.fullmatch(r"(\w+):\s*(\w+)\s*>\s*(\w+):\s*(.+)", row).groups() for row in sec["conflict_precedence"]]
    got = by_section["conflict_precedence"]
    assert [(r["witness"]["precedence_id"], r["witness"]["higher"], r["witness"]["lower"], r["witness"]["reason"])
            for _, r in got] == [tuple(x) for x in rows]
    for _, r in got:
        assert r["slots"]["choice"] == f"{r['witness']['higher']} over {r['witness']['lower']}"
        assert r["slots"]["subject"] == f"precedence {r['witness']['precedence_id']}"

    # [agent_settings]
    if "agent_settings" in sec:
        rows = [tuple(part.strip() for part in row.split(":", 1)) for row in sec["agent_settings"]]
        assert [(r["witness"]["setting"], r["witness"]["value"]) for _, r in by_section["agent_settings"]] == rows
        for _, r in by_section["agent_settings"]:
            assert r["slots"] == {"subject": f"agent setting {r['witness']['setting']}", "choice": r["witness"]["value"]}
    else:
        assert "agent_settings" not in by_section

    # machine-checkable criteria carry their command and expected exit in the acceptance witness
    commands = [json.loads(row.split("|", 1)[1]) for row in sec["completion_criteria"] if '"command_exit"' in row]
    accepted = [r["witness"]["acceptance"]["witness"] for r in records if r["kind"] == "ACCEPTANCE"
                and r["witness"]["acceptance"]["witness"].get("kind") == "command_exit"]
    assert accepted == commands and commands

    # every record of an optional section comes after every record of the required nine
    new_indexes = [i for name in NEW_SECTIONS for i, _ in by_section.get(name, [])]
    old_indexes = [i for name, items in by_section.items() if name not in NEW_SECTIONS for i, _ in items]
    assert old_indexes and new_indexes and max(old_indexes) < min(new_indexes)


def test_dsl_example_frame_precedence_leaves_unordered_pairs_unordered():
    from verantyx.project_frame import parse_frame

    spec = parse_frame((EXAMPLE_FRAMES[0].parent / "library_catalog_search.md").read_text(encoding="utf-8"), source="x")
    declared = {(r.higher, r.lower) for r in spec.precedence}
    assert declared == {("forbidden_actions", "protected_actions"), ("philosophy_invariants", "completion_criteria")}
    # forbidden_actions vs completion_criteria is not declared: it stays unordered (no invented winner)
    assert ("forbidden_actions", "completion_criteria") not in declared
    assert ("completion_criteria", "forbidden_actions") not in declared


# ------------------------------------------------------------ the existing frame is unchanged
ADDED_COMMENT_PREFIXES = ("# Optional sections", "# [write_allowlist]", "# [forbidden_actions]",
                          "# [conflict_precedence]", "# [agent_settings]", "# A machine-checkable")


def test_dsl_existing_frame_text_without_our_additions_compiles_exactly_as_before(tmp_path):
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame, parse_frame

    text = VERA_FRAME.read_text(encoding="utf-8")
    original = "\n".join(line for line in text.rsplit("\n[write_allowlist]", 1)[0].splitlines()
                         if not line.startswith(ADDED_COMMENT_PREFIXES) and not line.startswith("C6:")) + "\n"
    spec = parse_frame(original, source="docs/frames/vera_project_frame.md")
    assert spec.declared_sections == () and spec.write_allowlist == spec.forbidden_actions == ()
    assert spec.precedence == spec.agent_settings == ()
    comp = compile_frame(spec, Memory(str(tmp_path / "m.jsonl"), now=FIXED_CLOCK))
    now = [{"id": r["id"], "kind": r["kind"], "slots": r["slots"], "witness": r.get("witness"), "sentence": r.get("sentence")}
           for r in comp.records]
    before = json.loads((ROOT / "artifacts" / "w1-d" / "compile_before.json").read_text(encoding="utf-8"))
    assert len(before) == 56 == len(now)  # 56 was measured on the base commit (artifacts/w1-d/compile_before.json)
    assert now == before  # ids, order, slots, witnesses and sentences: identical


def test_dsl_the_shipped_vera_frame_only_adds_records_it_declares(tmp_path):
    records = compiled_records(VERA_FRAME, tmp_path)
    sections = [r["witness"].get("section") for r in records]
    assert sections.count("write_allowlist") == 4
    assert not any(s in ("forbidden_actions", "conflict_precedence", "agent_settings") for s in sections)
    c6 = [r for r in records if r["kind"] == "ACCEPTANCE" and "covenant guard" in r["slots"]["subject"]]
    assert len(c6) == 1 and c6[0]["witness"]["acceptance"]["witness"] == {
        "kind": "command_exit", "command": ["python", "-m", "verantyx.cli", "doctor"], "expected_exit": 0}


def test_dsl_the_format_notes_in_the_canonical_frame_cover_every_new_element():
    head = VERA_FRAME.read_text(encoding="utf-8").split("[goal]")[0]
    for word in ("[write_allowlist]", "[forbidden_actions]", "[protected_actions]", "[conflict_precedence]",
                 "[agent_settings]", "command_exit", "human-judged", "no globs"):
        assert word in head


def test_dsl_without_optional_sections_nothing_changes_and_absence_differs_from_none_none():
    plain = parse_tail("")
    assert plain.declared_sections == ()
    empty = parse_tail("[write_allowlist]\nnone: none\n")
    assert empty.declared_sections == ("write_allowlist",) and empty.write_allowlist == ()
    # required sections are still required: dropping one is still an error
    from verantyx.project_frame import FrameParseError, parse_frame

    with pytest.raises(FrameParseError, match="missing required section"):
        parse_frame(MINIMAL_FRAME.replace("[phases]\nP1: Do the work\n", ""), source="t")


# ------------------------------------------------------------ [write_allowlist]
BAD_PATHS = ["src/*.py", "*", "a?b", "dir/[ab]", "/etc", "/", "C:/x", "~/x", ".", "..", "a/../b", "a/./b",
             "src/", "a//b", ".git", ".git/hooks", "a\\b"]
GOOD_PATHS = ["src", "docs/frames", "a b/c", "日本語/ディレクトリ", "tools/run_project.py", ".github/workflows", ".gitignore"]


@pytest.mark.parametrize("path", BAD_PATHS)
def test_dsl_allowlist_rejects_a_path_the_runtime_could_not_match_and_says_the_line(path):
    err = parse_error(f"[write_allowlist]\nW1: {path}\n")
    # A row ending in ']' is taken for a section header by the (unchanged) line reader, so the
    # bracket glob is rejected with that message instead; it is still refused, with its line.
    reasons = ("invalid write path", "section header must be an exact") if path.endswith("]") else ("invalid write path",)
    assert err.line == ROW_LINE and any(r in err.message for r in reasons)


@pytest.mark.parametrize("path", GOOD_PATHS)
def test_dsl_allowlist_accepts_what_the_runtime_normaliser_accepts(path):
    from verantyx.agent_runtime import normalize_allowlist

    spec = parse_tail(f"[write_allowlist]\nW1: {path}\n")
    assert [item.path for item in spec.write_allowlist] == [path]
    assert normalize_allowlist([path]) == (path,)


def test_dsl_allowlist_globs_are_rejected_because_the_runtime_would_silently_match_nothing():
    from verantyx.agent_runtime import _allowed_path, normalize_allowlist

    assert normalize_allowlist(["src/*.py"]) == ("src/*.py",)  # the runtime does not complain...
    assert _allowed_path("src/a.py", ["src/*.py"]) is False   # ...and never matches: hence the parse-time error


def test_dsl_allowlist_semantics_are_prefix_not_substring():
    from verantyx.agent_runtime import _allowed_path

    assert _allowed_path("tests/x.py", ["tests"]) and _allowed_path("tests", ["tests"])
    assert not _allowed_path("tests2/x.py", ["tests"]) and not _allowed_path("my-tests/x.py", ["tests"])


def test_dsl_allowlist_duplicates_and_empty_entries_are_errors_with_the_second_line():
    assert parse_error("[write_allowlist]\nW1: src\nW1: docs\n").line == ROW_LINE + 1
    assert parse_error("[write_allowlist]\nW1: src\nW2: src\n").line == ROW_LINE + 1
    assert "must not be empty" in parse_error("[write_allowlist]\nW1:\n").message
    assert "'none: none'" in parse_error("[write_allowlist]\n").message
    assert "unknown section" in parse_error("[write_allowlst]\nW1: src\n").message
    assert "duplicate section" in parse_error("[write_allowlist]\nW1: src\n[write_allowlist]\nW2: docs\n").message
    assert parse_error("[write_allowlist]\nnot an entry\n").line == ROW_LINE


# ------------------------------------------------------------ forbidden vs protected
FORBIDDEN_BASE = MINIMAL_FRAME.replace("[protected_actions]\nnone: none\n",
                                       "[protected_actions]\npublish => Needs a human => human\n")


def test_forbidden_action_that_is_also_protected_is_a_syntax_error_naming_both_lines():
    err = parse_error("[forbidden_actions]\nPublish => No\n", FORBIDDEN_BASE)
    assert err.line == ROW_LINE and "both forbidden and protected" in err.message and "line" in err.message
    # same action after Unicode normalisation / case folding / spacing
    for variant in ("ＰＵＢＬＩＳＨ", "PUBLISH", "  publish  "):
        assert "both forbidden and protected" in parse_error(f"[forbidden_actions]\n{variant} => No\n", FORBIDDEN_BASE).message


def test_forbidden_action_duplicates_and_malformed_rows_are_errors():
    assert parse_error("[forbidden_actions]\nformat disk => No\nFormat   Disk => No again\n").line == ROW_LINE + 1
    assert "action => reason" in parse_error("[forbidden_actions]\nformat disk\n").message
    assert "action => reason" in parse_error("[forbidden_actions]\na => b => c\n").message
    assert "must not be empty" in parse_error("[forbidden_actions]\nformat disk =>\n").message


def test_forbidden_action_authority_is_three_valued_and_undeclared_is_not_allowed():
    from verantyx.project_frame import action_authority

    spec = parse_tail("[forbidden_actions]\ndrop table => Never\n", FORBIDDEN_BASE)
    assert action_authority(spec, "Drop  TABLE") == "FORBIDDEN"
    assert action_authority(spec, "publish") == "APPROVAL_REQUIRED"
    assert action_authority(spec, "rm -rf") == "UNDECLARED"
    assert action_authority(spec, "") == "UNDECLARED"
    assert action_authority(spec, "drop") == "UNDECLARED"  # exact name, not a prefix or similarity
    with pytest.raises(TypeError):
        action_authority(spec, None)


def test_forbidden_actions_become_approval_proof_invariants_and_protected_ones_do_not(tmp_path):
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame

    spec = parse_tail("[forbidden_actions]\ndrop table => Never\nreset history => Never\n", FORBIDDEN_BASE)
    records = compile_frame(spec, Memory(str(tmp_path / "m.jsonl"), now=FIXED_CLOCK)).records
    forbidden = [r for r in records if r["witness"].get("approval_effect") == "NOT_PERMITTED"]
    assert [r["witness"]["forbidden_action"] for r in forbidden] == ["drop table", "reset history"]
    assert len([r for r in records if r["kind"] == "ESCALATE" and r["witness"].get("protected_action")]) == 1
    assert not [r for r in records if r["kind"] == "ESCALATE" and "drop table" in r["witness"].get("condition", "")]


# ------------------------------------------------------------ [conflict_precedence]
@pytest.mark.parametrize("row,fragment", [
    ("R1: forbidden_actions > nonsense: x", "unknown rule family"),
    ("R1: nonsense > forbidden_actions: x", "unknown rule family"),
    ("R1: forbidden_actions > forbidden_actions: x", "over itself"),
    ("R1: protected_actions > forbidden_actions: approval wins", "never overrides a forbidden action"),
    ("R1: forbidden_actions > protected_actions", "ID: HIGHER > LOWER: reason"),
    ("R1 forbidden_actions > protected_actions: x", "ID: HIGHER > LOWER: reason"),
    ("R1: forbidden_actions > philosophy_invariants > protected_actions: x", "exactly one '>'"),
    ("R1: forbidden_actions protected_actions: x", "exactly one '>'"),
    ("R1: forbidden_actions > protected_actions:", "must not be empty"),
    ("1R: forbidden_actions > protected_actions: x", "invalid precedence id"),
])
def test_precedence_rejects_malformed_rows_with_a_line_number(row, fragment):
    err = parse_error(f"[conflict_precedence]\n{row}\n")
    assert err.line == ROW_LINE and fragment in err.message


def test_precedence_rejects_duplicates_and_cycles():
    assert "duplicate precedence" in parse_error(
        "[conflict_precedence]\nR1: forbidden_actions > protected_actions: a\nR2: forbidden_actions > protected_actions: b\n").message
    assert "duplicate precedence id" in parse_error(
        "[conflict_precedence]\nR1: forbidden_actions > protected_actions: a\nR1: philosophy_invariants > completion_criteria: b\n").message
    two = parse_error("[conflict_precedence]\nR1: philosophy_invariants > completion_criteria: a\n"
                      "R2: completion_criteria > philosophy_invariants: b\n")
    assert "cycle" in two.message
    three = parse_error("[conflict_precedence]\nR1: philosophy_invariants > completion_criteria: a\n"
                        "R2: completion_criteria > protected_actions: b\nR3: protected_actions > philosophy_invariants: c\n")
    assert "cycle" in three.message


def test_precedence_rejects_a_chain_from_protected_to_forbidden_at_the_closing_line():
    # two links: the rule that closes the path (R2) is reported
    two = parse_error("[conflict_precedence]\nR1: protected_actions > philosophy_invariants: x\n"
                      "R2: philosophy_invariants > forbidden_actions: y\n")
    assert two.line == ROW_LINE + 1
    assert "forbidden_actions" in two.message and "chain" in two.message and "approval" in two.message
    # three links
    three = parse_error("[conflict_precedence]\nR1: protected_actions > completion_criteria: x\n"
                        "R2: completion_criteria > philosophy_invariants: y\n"
                        "R3: philosophy_invariants > forbidden_actions: z\n")
    assert three.line == ROW_LINE + 2 and "chain" in three.message
    # the chain is closed by the first-declared edge's partner declared later, in any order
    reordered = parse_error("[conflict_precedence]\nR1: philosophy_invariants > forbidden_actions: y\n"
                            "R2: protected_actions > philosophy_invariants: x\n")
    assert reordered.line == ROW_LINE + 1 and "chain" in reordered.message


def test_precedence_accepts_the_reverse_chain_and_chains_that_do_not_reach_forbidden():
    reverse = parse_tail("[conflict_precedence]\nR1: forbidden_actions > philosophy_invariants: a\n"
                         "R2: philosophy_invariants > protected_actions: b\n")
    assert [(r.higher, r.lower) for r in reverse.precedence] == [
        ("forbidden_actions", "philosophy_invariants"), ("philosophy_invariants", "protected_actions")]
    longer = parse_tail("[conflict_precedence]\nR1: forbidden_actions > completion_criteria: a\n"
                        "R2: completion_criteria > philosophy_invariants: b\n"
                        "R3: philosophy_invariants > protected_actions: c\n")
    assert len(longer.precedence) == 3
    not_reaching = parse_tail("[conflict_precedence]\nR1: protected_actions > philosophy_invariants: a\n"
                              "R2: philosophy_invariants > completion_criteria: b\n")
    assert len(not_reaching.precedence) == 2


def test_precedence_chain_is_kept_as_declared_and_unordered_pairs_get_no_winner(tmp_path):
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame

    spec = parse_tail("[conflict_precedence]\nR1: forbidden_actions > philosophy_invariants: a\n"
                      "R2: completion_criteria > philosophy_invariants: b\n")
    assert [(r.higher, r.lower) for r in spec.precedence] == [
        ("forbidden_actions", "philosophy_invariants"), ("completion_criteria", "philosophy_invariants")]
    records = compile_frame(spec, Memory(str(tmp_path / "m.jsonl"), now=FIXED_CLOCK)).records
    pairs = [(r["witness"]["higher"], r["witness"]["lower"]) for r in records
             if r["witness"].get("section") == "conflict_precedence"]
    assert pairs == [("forbidden_actions", "philosophy_invariants"), ("completion_criteria", "philosophy_invariants")]
    # forbidden_actions and completion_criteria are both above philosophy_invariants but unordered
    # with each other: no record orders them, in either direction.
    assert ("forbidden_actions", "completion_criteria") not in pairs and ("completion_criteria", "forbidden_actions") not in pairs


# ------------------------------------------------------------ [agent_settings]
@pytest.mark.parametrize("row,fragment", [
    ("unknown_key: x", "unknown agent setting"),
    ("codex_model: gpt 6", "model must be"),
    ('codex_model: "quoted"', "model must be"),
    ("codex_model: -x", "model must be"),
    ("claude_effort: HIGH", "effort must be"),
    ('codex_effort: high" -c x="1', "effort must be"),
    ("max_concurrency: 0", "positive integer"),
    ("max_concurrency: 03", "positive integer"),
    ("max_concurrency: many", "positive integer"),
    ("max_concurrency: -2", "positive integer"),
    ("codex_model", "key: value"),
])
def test_agent_settings_reject_values_that_could_reach_a_command_line(row, fragment):
    err = parse_error(f"[agent_settings]\n{row}\n")
    assert err.line == ROW_LINE and fragment in err.message


def test_agent_settings_duplicates_are_errors_and_valid_values_are_kept_verbatim():
    assert "duplicate agent setting" in parse_error("[agent_settings]\ncodex_model: a\ncodex_model: b\n").message
    spec = parse_tail("[agent_settings]\ncodex_model: gpt-6-luna\ncodex_effort: xhigh\nclaude_model: claude-opus-5-5\n"
                      "claude_effort: max\nmax_concurrency: 60\n")
    assert {i.key: i.value for i in spec.agent_settings} == {
        "codex_model": "gpt-6-luna", "codex_effort": "xhigh", "claude_model": "claude-opus-5-5",
        "claude_effort": "max", "max_concurrency": "60"}


# ------------------------------------------------------------ machine-checkable criteria
def test_frame_machine_criteria_use_the_existing_command_exit_witness_and_nothing_new():
    spec = parse_tail("")
    assert [c.human_judged for c in spec.criteria] == [False]
    assert spec.criteria[0].witness == {"kind": "command_exit", "command": ["true"], "expected_exit": 0}
    err = parse_error("", MINIMAL_FRAME.replace('"expected_exit":0', '"expected_exit":"zero"'))
    assert "expected_exit must be an integer" in err.message
    err = parse_error("", MINIMAL_FRAME.replace('"kind":"command_exit"', '"kind":"shell"'))
    assert "machine witness kind" in err.message
