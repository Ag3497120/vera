"""Prevent answer code from copying evaluation prompts or answer hints."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVALUATIONS = {"vera-ja-sealed1": 16, "vera-ja-sealed2": 16, "vera-ja-dev2": 36,
               "vera-ja-sealed3": 0, "vera-ja-sealed4": 0}
GENERIC_FORMS = ("文書には書かれていません。", "はい。この文から分かります。",
                 "しなければならない", "まだ決まっていません", "提示されていない",
                 "この文だけでは分かりません。", "必要な根拠が足りません。",
                 "創作（出典の断片を再構成）: ", "矛盾するとは確認できません。",
                 "。私は何でしょう？", "ていただけますか。",
                 "はい。同じ場面について両立しません。", "例が複数あります。",
                 "）の音が重なる言葉遊びです。", "の音を重ねました。）",
                 "を確認できません。", "候補が同点です。",
                 "印象に残りました。", "最新情報を確認してください。")
GENERIC_FORMS += ("明示してください。",)


def _strings(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_answerers_have_no_eight_character_dev_literal() -> None:
    files = []
    listed = (ROOT / "tools/eval_dirs.txt").read_text(encoding="utf-8").splitlines()
    names = [line.strip() for line in listed if line.strip() and not line.startswith("#")]
    assert set(EVALUATIONS) <= set(names)
    directories = []
    for name in names:
        if "*" in name:
            directories.extend((Path.home() / "Projects").glob(name))
        else:
            directories.append(Path.home() / "Projects" / name)
    for directory in directories:
        expected_count = EVALUATIONS.get(directory.name, 0)
        found = sorted(path for path in directory.rglob("*")
                       if path.is_file() and path.suffix.lower() in (".json", ".jsonl", ".txt", ".md")
                       and ("heldout" in path.parts or path.name.startswith(("doc_", "ab_", "schema_"))))
        if directory.exists():
            assert len(found) >= expected_count, f"evaluation files missing: {directory}"
        files.extend(found)
    if not files:
        pytest.skip("evaluation fixtures are unavailable")
    snippets: set[str] = set()
    for path in files:
        raw = path.read_text(encoding="utf-8")
        values = _strings(json.loads(raw)) if path.suffix.lower() == ".json" else (raw,)
        for value in values:
            snippets.update(value[i:i + 8] for i in range(len(value) - 7)
                            if re.search(r"[ぁ-んァ-ヶ一-鿿]", value[i:i + 8]))
    # These are fixed typed response forms in the public contract, rather
    # than topical answer content from an evaluation item. The others are
    # productive Japanese grammar or generic absence markers.
    protocol_windows = {form[i:i + 8] for form in GENERIC_FORMS
                        for i in range(len(form) - 7)}
    snippets -= protocol_windows
    for name in ("abilities.py", "answer.py", "family_library.py", "round3.py", "answer_slots.py",
                 "evidence_library.py", "code_spec.py", "code_compose.py"):
        source = (ROOT / "verantyx" / name).read_text(encoding="utf-8")
        overlap = snippets.intersection(source[i:i + 8] for i in range(len(source) - 7))
        assert not overlap, f"{name} contains spent text: {sorted(overlap)[:8]}"
