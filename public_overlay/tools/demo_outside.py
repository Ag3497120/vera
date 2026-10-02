"""Small, frozen demonstration of the semantic outside hand-over."""
from __future__ import annotations

import json
import re
from types import SimpleNamespace

from verantyx.semantic_outside import explain_outside


_checks = 0


def check(condition: bool, message: str) -> None:
    global _checks
    _checks += 1
    if not condition:
        raise AssertionError(message)


class DemoSpan:
    def __init__(self, source: str, start: int, end: int, text: str):
        self.source = source
        self.start = start
        self.end = end
        self.text = text

    def valid(self, sources: dict[str, str]) -> bool:
        raw = sources.get(self.source)
        return (isinstance(raw, str) and 0 <= self.start < self.end <= len(raw)
                and raw[self.start:self.end] == self.text)


def _span(source: str, raw: str, start: int, end: int) -> DemoSpan:
    return DemoSpan(source, start, end, raw[start:end])


def make_view(term: str, units: tuple[str, ...], *, repetitions: int,
              include_term: bool = True,
              framing_words: tuple[str, ...] = (),
              role_terms: tuple[str, ...] | None = None,
              held_context_terms: tuple[str, ...] = ()):
    """Build source text and source-bound fake clause roles by hand."""
    held_source = "held"
    held_terms = role_terms if role_terms is not None else units
    held_text = ((term + " ") if include_term else "") + " ".join(held_terms)
    if held_context_terms:
        held_text += " " + " ".join(held_context_terms)
    sources = {held_source: held_text}
    roles = []
    cursor = len(term) + 1 if include_term else 0
    for index, unit in enumerate(held_terms):
        start = held_text.find(unit, cursor)
        if start < 0:
            raise AssertionError("demo role term is absent from held source")
        end = start + len(unit)
        roles.append(SimpleNamespace(
            name=f"unit_{index}", term=unit,
            span=_span(held_source, held_text, start, end),
        ))
        cursor = end + 1

    for index in range(4):
        source = f"lex-{index}"
        words = [term] if include_term else []
        words.extend(framing_words)
        if repetitions:
            words.extend(unit for unit in units for _ in range(repetitions))
        sources[source] = " ".join(words)

    clause = SimpleNamespace(
        id="hand-built-clause",
        span=_span(held_source, held_text, 0, len(held_text)),
        predicate="co-occurs",
        predicate_span=_span(held_source, held_text, 0, len(term)),
        roles=tuple(roles),
    )
    return SimpleNamespace(sources=sources, clauses=(clause,))


class FakeAsker:
    """Return only a listed choice index or null, on a fixed accuracy schedule."""

    _option_line = re.compile(r"^(\d+): (\{.*\})$", re.MULTILINE)

    def __init__(self, target: str, schedule: list[bool]):
        self.target = target
        self.schedule = list(schedule)
        self.prompts: list[str] = []
        self.correct = 0

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        call_index = len(self.prompts) - 1
        should_be_correct = (self.schedule[call_index]
                             if call_index < len(self.schedule) else False)
        options = []
        for number, payload in self._option_line.findall(prompt):
            try:
                item = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                options.append((int(number), item.get("term")))
        selected = next((number for number, term in options
                         if should_be_correct and term == self.target), None)
        if selected is not None:
            self.correct += 1
        return json.dumps({"choice": selected}, ensure_ascii=False)


def verify_result(result) -> None:
    data = result.to_dict()
    check(result.constructed is True, "OutsideResult must remain constructed")
    check(result.evidence is False, "constructed output must not be evidence")
    check(result.answer is False, "outside output must never be an answer")
    check(result.route != "ANSWER", "outside route must not be ANSWER")
    check(data["constructed"] is True, "serialized result must retain its marker")
    check(data["generated"]["constructed"] is True,
          "generated text must retain its marker")
    check(data["generated"]["evidence"] is False,
          "generated text must not be evidence")
    check(data["generated"]["answer"] is False,
          "generated text must not be an answer")
    check("（構成的説明 — 証言ではない）" in result.text,
          "display text must carry the construction marker")
    if result.choice is not None:
        for item in result.choice.get("evidence", ()):
            check(item.get("constructed") is True,
                  "choice evidence must keep the construction marker")
            check(item.get("counts_as_evidence") is False,
                  "choice candidates must not count as evidence")
    if result.construction is not None:
        candidate = result.construction.to_dict()
        check(result.construction.constructed is True,
              "candidate must remain constructed")
        check(result.construction.evidence is False,
              "candidate must not be evidence")
        check(candidate["constructed"] is True,
              "serialized candidate must retain its marker")
        check(candidate["answer"] is False,
              "candidate must never be an answer")


def verify_spans(view, result) -> int:
    resolved = 0
    if result.construction is None:
        return resolved
    for unit in result.construction.provenance:
        check(bool(unit.clauses), "each spoken unit needs source provenance")
        for item in unit.clauses:
            span = item.span
            raw = view.sources.get(span.source)
            check(raw is not None, "provenance source must exist in the View")
            check(raw[span.start:span.end] == span.text,
                  "provenance span text must resolve against its source")
            resolved += 1
    return resolved


def run_demo() -> None:
    term = "電荷密度"
    units = ("電荷", "密度")
    view = make_view(term, units, repetitions=3)
    asker_100 = FakeAsker("電荷", [True, True])
    result_100 = explain_outside(view, term, asker=asker_100)
    verify_result(result_100)
    check(result_100.status == "CANDIDATES", "known structure should construct")
    check(result_100.construction is not None,
          "unit explanation should return a typed construction")
    check(result_100.construction.kind == "EXPLAINED_BY_UNITS",
          "the hand-built compound should use the unit route")
    check(result_100.adopted_term == "電荷", "100% asker should pick the gold term")
    check(result_100.testimony is not None,
          "adopted closed choice must be returned as testimony")
    check(result_100.testimony["support"] == "testimony",
          "adopted choice provenance must say testimony")
    check(asker_100.correct == 2, "100% fake asker must be correct twice")
    check(asker_100.prompts[0] != asker_100.prompts[1],
          "resolver must issue independently worded asks")
    resolved_spans = verify_spans(view, result_100)
    check(resolved_spans > 0, "constructed units must retain resolvable spans")

    # Two further fixed schedules contain exactly ten asks each.
    # 8/10 correct asks and 5/10 correct asks exercise agreement and abstention.
    asker_80 = FakeAsker("電荷", [True] * 8 + [False] * 2)
    results_80 = [explain_outside(view, term, asker=asker_80)
                  for _ in range(5)]
    asker_50 = FakeAsker("電荷", [item for _ in range(5)
                                  for item in (True, False)])
    results_50 = [explain_outside(view, term, asker=asker_50)
                  for _ in range(5)]
    for item in (*results_80, *results_50):
        verify_result(item)
        check(item.construction is not None,
              "choice quality must not change the structural candidate")
        check(item.construction.kind == "EXPLAINED_BY_UNITS",
              "choice must not rewrite or remove the construction")
    check(asker_80.correct == 8 and len(asker_80.prompts) == 10,
          "80% fake asker schedule must be exactly 8/10")
    check(asker_50.correct == 5 and len(asker_50.prompts) == 10,
          "50% fake asker schedule must be exactly 5/10")
    check(results_80[-1].adopted_term is None,
          "paired null replies at 80% must not be adopted")
    check(results_80[-1].choice["decision"] == "UNRESOLVED",
          "paired null replies must stay unresolved")
    check(all(item.adopted_term is None for item in results_50),
          "one correct and one null ask must not be adopted")
    check(all(item.choice["decision"] == "UNRESOLVED" for item in results_50),
          "disagreement across the two asks must remain unresolved")

    bare = explain_outside(
        make_view("発明者", ("発明", "者"), repetitions=3,
                  include_term=False,
                  framing_words=("発明研究", "担当者")),
        "発明者")
    verify_result(bare)
    check(bare.status == "ABSTAIN_BARE_SUFFIX_SPLIT",
          "bare suffix split must abstain")
    check(bare.construction is None,
          "bare suffix abstention must not emit an explanation candidate")

    nonword = explain_outside(
        make_view(term, units, repetitions=0), term)
    verify_result(nonword)
    check(nonword.status == "ABSTAIN_UNIT_NOT_A_WORD",
          "unattested units must abstain as non-words")
    check(nonword.construction is None,
          "non-word abstention must not emit an explanation candidate")

    kin_units = ("電荷量", "電荷計", "粒子密度", "運動")
    kin_view = make_view(
        term, kin_units, repetitions=3, include_term=False,
        framing_words=(), role_terms=("電荷量", "電荷計", "運動"),
        held_context_terms=("電荷", "密度"))
    kin = explain_outside(kin_view, term)
    verify_result(kin)
    check(kin.status == "CANDIDATES", "attested kin should construct")
    check(kin.construction is not None,
          "kin route should return a typed construction")
    check(kin.construction.kind == "KIN_NEIGHBOURHOOD",
          "unheld target should stay a kin neighbourhood")
    check(bool(kin.construction.families),
          "kin result should name its positional families")
    check(verify_spans(kin_view, kin) > 0,
          "kin units must retain resolvable source spans")

    print(f"assertions: {_checks}")
    print("DEMO OK")


if __name__ == "__main__":
    run_demo()
