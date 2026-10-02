#!/usr/bin/env python3
"""Executable contract example for the semantic construction registry."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

from verantyx.constructions import discover
from verantyx.semantic_ir import Clause, Role, Span, Variable, View
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import Rejected, license_clause


_TOY_MODULE = r'''from verantyx.constructions import Construction, Reading, TypedNote, register
from verantyx.semantic_ir import Clause, Role, Span, Variable

SOURCE = "Nori glorp."

def _reading(ctx, name, role_name):
    if ctx.sentence_text != SOURCE:
        return None
    sentence = ctx.sentence_span
    role_span = Span(ctx.document_id, sentence.start, sentence.start + 4, "Nori")
    predicate_span = Span(ctx.document_id, sentence.start + 5, sentence.start + 10, "glorp")
    clause = Clause(
        name + "_clause", Variable(name + "_event", "event"), "glorp",
        predicate_span, (Role(role_name, "Nori", role_span),), sentence, sentence,
        rule=name,
    )
    return Reading((clause,), (sentence,), (TypedNote("toy-lexeme", predicate_span, "glorp"),))

def _license(clause, source, name, role_name):
    return (
        source == SOURCE and clause.rule == name and clause.span.text == SOURCE
        and clause.predicate == "glorp" and clause.predicate_span.text == "glorp"
        and len(clause.roles) == 1 and clause.roles[0].name == role_name
        and clause.roles[0].term == "Nori" and clause.roles[0].span.text == "Nori"
    )

register(Construction(
    "demo_alpha", 10,
    lambda ctx: _reading(ctx, "demo_alpha", "agent"),
    lambda clause, source: _license(clause, source, "demo_alpha", "agent"),
))
register(Construction(
    "demo_beta", 5,
    lambda ctx: _reading(ctx, "demo_beta", "patient"),
    lambda clause, source: _license(clause, source, "demo_beta", "patient"),
))
'''


def main():
    old_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    with tempfile.TemporaryDirectory(prefix="vera-construction-demo-") as directory:
        Path(directory, "demo_construction_module.py").write_text(_TOY_MODULE, encoding="utf-8")
        sys.path.insert(0, directory)
        try:
            importlib.import_module("demo_construction_module")
            names = {item.name for item in discover()}
            assert {"demo_alpha", "demo_beta"} <= names

            os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
            conflict = document_view({"toy": "Nori glorp."})
            alternatives = [c for c in conflict.clauses if c.rule in ("demo_alpha", "demo_beta")]
            assert {c.rule for c in alternatives} == {"demo_alpha", "demo_beta"}
            assert all(c.unsupported for c in alternatives)
            assert all(any("ambiguous construction readings" in reason for reason in c.unsupported)
                       for c in alternatives)

            os.environ["VERA_CONSTRUCTIONS_OFF"] = "demo_beta"
            selected = document_view({"toy": "Nori glorp."})
            licensed = next(c for c in selected.clauses if c.rule == "demo_alpha")
            assert not licensed.unsupported
            license_clause(licensed, selected)

            os.environ["VERA_CONSTRUCTIONS_OFF"] = "demo_alpha,demo_beta"
            disabled = document_view({"toy": "Nori glorp."})
            assert not any(c.rule in ("demo_alpha", "demo_beta") for c in disabled.clauses)

            span = Span("toy", 0, 11, "Nori glorp.")
            bad = Clause(
                "unlicensed_clause", Variable("unlicensed_event", "event"), "glorp",
                Span("toy", 5, 10, "glorp"),
                (Role("agent", "Nori", Span("toy", 0, 4, "Nori")),), span, span,
                rule="unlicensed_rule",
            )
            bad_view = View({"toy": "Nori glorp."}, (bad,))
            rejected = False
            try:
                license_clause(bad, bad_view)
            except Rejected:
                rejected = True
            assert rejected
        finally:
            sys.path.remove(directory)
            sys.modules.pop("demo_construction_module", None)
            if old_off is None:
                os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
            else:
                os.environ["VERA_CONSTRUCTIONS_OFF"] = old_off
    print("DEMO OK")


if __name__ == "__main__":
    main()
