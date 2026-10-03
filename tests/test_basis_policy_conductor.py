"""W6-a item 6: the conductor and the routing never take anything but a declared human basis.

Nothing in conduct_*, conductor*, agent_* or routing_from_text imports the corpus, the policy or the
sovereign memory, and a routing ``Basis`` refuses every kind the policy produces other than a
declared one. Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from verantyx import basis_policy as bp
from verantyx.agent_routing import BASIS_KINDS, Basis

PKG = Path(__file__).resolve().parents[1] / "verantyx"
ROUTED = sorted({*PKG.glob("conduct_*.py"), *PKG.glob("conductor*.py"), *PKG.glob("agent_*.py"),
                 PKG / "routing_from_text.py"})
FORBIDDEN_IMPORTS = {"ability_corpus", "basis_policy", "sovereign"}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            names.add(base)
            names.update(f"{base}.{a.name}" if base else a.name for a in node.names)
    return names


def _leaf_parts(names: set[str]) -> set[str]:
    return {part for name in names for part in name.split(".")}


def test_the_files_under_test_exist():
    assert len(ROUTED) >= 8 and all(p.is_file() for p in ROUTED)


@pytest.mark.parametrize("path", ROUTED, ids=lambda p: p.name)
def test_routed_modules_do_not_import_the_corpus_the_policy_or_the_sovereign(path):
    assert not (_leaf_parts(_imported_modules(path)) & FORBIDDEN_IMPORTS)


@pytest.mark.parametrize("path", ROUTED, ids=lambda p: p.name)
def test_routed_modules_do_not_mention_the_reference_column(path):
    assert "reference_generated" not in path.read_text(encoding="utf-8")


def test_the_policy_module_imports_nothing_from_the_conductor_the_agents_or_the_routing():
    imported = _leaf_parts(_imported_modules(PKG / "basis_policy.py"))
    for name in imported:
        assert not name.startswith(("conduct", "agent_", "routing_from_text", "llm_choice")), name


@pytest.mark.parametrize("kind", [*bp.OUTCOMES, "generated", "constructed", "reference_generated",
                                  "human_confirmed", "REFERENCE_GENERATED", "CONSTRUCTED"])
def test_a_routing_basis_refuses_every_kind_the_policy_produces(kind):
    assert kind not in BASIS_KINDS
    with pytest.raises(ValueError):
        Basis(kind=kind, source="x", witnesses=("y",))


def test_a_routing_basis_still_accepts_the_declared_text_kind():
    assert Basis(kind="declared_text", source="x", witnesses=("y",)).kind == "declared_text"
    assert set(BASIS_KINDS) == {"declared_dsl", "declared_text"}
