"""Conservative test and demo selection from a repository's Python imports."""

from __future__ import annotations

import ast
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path


_SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "round5-dev",
    "sealed",
    "heldout",
    "Verantyx-Vera-alpha",
}


@dataclass(frozen=True)
class Dependency:
    """An importer-to-imported-module edge and how it was found."""

    path: str
    reason: str


@dataclass(frozen=True)
class Affected:
    """A selected test/demo and one shortest chain to a changed file."""

    path: str
    category: str
    chain: tuple[str, ...]
    reasons: tuple[str, ...]

    def explain(self) -> str:
        pieces = [self.chain[0]]
        for reason, path in zip(self.reasons, self.chain[1:]):
            pieces.extend((f"-[{reason}]->", path))
        return " ".join(pieces)


@dataclass(frozen=True)
class ImpactReport:
    changed: tuple[str, ...]
    affected: tuple[Affected, ...]

    @property
    def tests(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.affected if item.category == "test")

    @property
    def demos(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.affected if item.category == "demo")

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.affected)


def _module_name(path: str) -> str:
    relative = Path(path).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _source_paths(root: Path) -> tuple[str, ...]:
    """List in-repository Python files without entering excluded data trees."""

    root_real = root.resolve()
    found: list[str] = []
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        names[:] = [
            name
            for name in names
            if name not in _SKIP_DIRS and not (Path(directory) / name).is_symlink()
        ]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = Path(directory) / filename
            try:
                if not path.resolve().is_relative_to(root_real):
                    continue
            except OSError:
                continue
            found.append(path.relative_to(root).as_posix())
    return tuple(sorted(found))


def _root_category(path: str) -> str | None:
    name = Path(path).name
    if name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if name == "demo.py" or name.startswith("demo_") or name.endswith("_demo.py"):
        return "demo"
    return None


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _constant_string(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left, constants)
        right = _constant_string(node.right, constants)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        chunks: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            chunks.append(value.value)
        return "".join(chunks)
    return None


def _relative_name(name: str, package: str, level: int) -> str | None:
    if level <= 0:
        return name
    package_parts = package.split(".") if package else []
    keep = len(package_parts) - level + 1
    if keep < 0:
        return None
    base = package_parts[:keep]
    if name:
        base.extend(name.split("."))
    return ".".join(base)


class _ImportVisitor(ast.NodeVisitor):
    def __init__(self, path: str, module: str, modules: dict[str, tuple[str, ...]]):
        self.path = path
        self.module = module
        self.package = module if Path(path).name == "__init__.py" else module.rpartition(".")[0]
        self.modules = modules
        self.dependencies: set[Dependency] = set()
        self.unresolved = False
        self.constants: dict[str, str] = {}
        self.importlib_aliases: set[str] = {"importlib"}
        self.import_module_aliases: set[str] = set()
        self.builtins_aliases: set[str] = {"builtins"}
        self.builtin_import_aliases: set[str] = {"__import__"}
        self.pkgutil_aliases: set[str] = {"pkgutil"}
        self.iter_modules_aliases: set[str] = set()
        self.walk_packages_aliases: set[str] = set()

    def _add_module(self, name: str | None, reason: str) -> None:
        if not name:
            return
        for path in self.modules.get(name, ()):
            self.dependencies.add(Dependency(path, reason))

    def _add_from_import(self, name: str, imported: str, reason: str) -> None:
        self._add_module(name, reason)
        if imported != "*":
            self._add_module(f"{name}.{imported}" if name else imported, reason)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._add_module(alias.name, "import")
            if alias.name == "importlib":
                self.importlib_aliases.add(alias.asname or "importlib")
            if alias.name == "pkgutil":
                self.pkgutil_aliases.add(alias.asname or "pkgutil")
            if alias.name == "builtins":
                self.builtins_aliases.add(alias.asname or "builtins")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        name = _relative_name(node.module or "", self.package, node.level)
        self._add_module(name, "import")
        for alias in node.names:
            imported_name = alias.asname or alias.name
            self._add_from_import(name or "", alias.name, "import")
            if name == "importlib" and alias.name == "import_module":
                self.import_module_aliases.add(imported_name)
            if name == "builtins" and alias.name == "__import__":
                self.builtin_import_aliases.add(imported_name)
            if name == "pkgutil":
                if alias.name == "iter_modules":
                    self.iter_modules_aliases.add(imported_name)
                if alias.name == "walk_packages":
                    self.walk_packages_aliases.add(imported_name)

    def _dynamic_name(self, value: str, package: str | None = None) -> str | None:
        if not value.startswith("."):
            return value
        if not package:
            return None
        level = len(value) - len(value.lstrip("."))
        return _relative_name(value[level:], package, level)

    def _is_import_module(self, func: ast.AST) -> bool:
        dotted = _dotted(func)
        if dotted in self.import_module_aliases:
            return True
        if isinstance(func, ast.Attribute) and func.attr == "import_module":
            return _dotted(func.value) in self.importlib_aliases
        return False

    def _is_pkgutil_discovery(self, func: ast.AST) -> bool:
        dotted = _dotted(func)
        if dotted in self.iter_modules_aliases or dotted in self.walk_packages_aliases:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {"iter_modules", "walk_packages"}:
            return _dotted(func.value) in self.pkgutil_aliases
        return False

    def _is_builtin_import(self, func: ast.AST) -> bool:
        dotted = _dotted(func)
        if dotted in self.builtin_import_aliases:
            return True
        return (
            isinstance(func, ast.Attribute)
            and func.attr == "__import__"
            and _dotted(func.value) in self.builtins_aliases
        )

    @staticmethod
    def _argument(node: ast.Call, name: str, position: int) -> ast.AST | None:
        if position < len(node.args):
            return node.args[position]
        for keyword in node.keywords:
            if keyword.arg == name:
                return keyword.value
        return None

    def visit_Call(self, node: ast.Call) -> None:
        func = _dotted(node.func)
        if self._is_pkgutil_discovery(node.func):
            # Package discovery is runtime-dependent. The graph builder widens
            # this source to every local module below.
            self.unresolved = True
        elif self._is_import_module(node.func):
            name_arg = self._argument(node, "name", 0)
            target = _constant_string(name_arg, self.constants) if name_arg is not None else None
            package = None
            package_arg = self._argument(node, "package", 1)
            if package_arg is not None:
                package = _constant_string(package_arg, self.constants)
                if isinstance(package_arg, ast.Name) and package_arg.id in {"__package__", "__name__"}:
                    package = self.package
            name = self._dynamic_name(target, package) if target is not None else None
            if name is None:
                self.unresolved = True
            else:
                self._add_module(name, "dynamic import")
        elif self._is_builtin_import(node.func):
            target_arg = self._argument(node, "name", 0)
            target = _constant_string(target_arg, self.constants) if target_arg is not None else None
            level = 0
            level_arg = self._argument(node, "level", 4)
            if level_arg is not None:
                try:
                    level = int(ast.literal_eval(level_arg))
                except (ValueError, TypeError, SyntaxError):
                    self.unresolved = True
            name = _relative_name(target or "", self.package, level) if target is not None else None
            if name is None:
                self.unresolved = True
            else:
                self._add_module(name, "dynamic import")
                fromlist_arg = self._argument(node, "fromlist", 3)
                if isinstance(fromlist_arg, (ast.List, ast.Tuple)):
                    for item in fromlist_arg.elts:
                        imported = _constant_string(item, self.constants)
                        if imported and imported != "*":
                            self._add_module(f"{name}.{imported}", "dynamic import")
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "find_spec":
            if _dotted(node.func.value) in self.importlib_aliases:
                target = _constant_string(node.args[0], self.constants) if node.args else None
                if target is None:
                    self.unresolved = True
                else:
                    self._add_module(target, "dynamic import")
        self.generic_visit(node)


def _read_imports(path: Path, relative: str, module: str, modules: dict[str, tuple[str, ...]]) -> tuple[set[Dependency], bool]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    except (OSError, UnicodeError, SyntaxError):
        return set(), True
    visitor = _ImportVisitor(relative, module, modules)
    visitor.visit(tree)
    return visitor.dependencies, visitor.unresolved


def _normalise_changed(changed_files: tuple[str, ...], root: Path) -> tuple[str, ...]:
    root_real = root.resolve()
    result: list[str] = []
    for value in changed_files:
        path = Path(value)
        if path.is_absolute():
            try:
                value = path.resolve().relative_to(root_real).as_posix()
            except (OSError, ValueError):
                value = path.as_posix()
        else:
            value = Path(os.path.normpath(value)).as_posix()
        result.append(value)
    return tuple(sorted(set(result)))


def analyze_impact(changed_files: tuple[str, ...] | list[str] | str | Path, repo: str | Path = ".") -> ImpactReport:
    """Return tests and demos that can depend on any changed Python file.

    Imports are parsed with :mod:`ast`. An unknown Python file, a parse failure,
    or an unresolved dynamic import widens selection so an uncertain edge never
    removes a test from the result.
    """

    root = Path(repo)
    root_real = root.resolve()
    source_paths = _source_paths(root)
    module_candidates: dict[str, list[str]] = {}
    for path in source_paths:
        module = _module_name(path)
        if module:
            module_candidates.setdefault(module, []).append(path)
    modules = {name: tuple(sorted(paths)) for name, paths in module_candidates.items()}

    dependencies: dict[str, set[Dependency]] = {path: set() for path in source_paths}
    unresolved_sources: set[str] = set()
    roots: dict[str, str] = {}
    for path in source_paths:
        category = _root_category(path)
        if category:
            roots[path] = category
        module = _module_name(path)
        absolute = root / path
        edges, unresolved = _read_imports(absolute, path, module, modules)
        dependencies[path].update(edges)
        if unresolved:
            unresolved_sources.add(path)

    # Discovery and nonconstant loads may reach any in-repository module.
    for source in unresolved_sources:
        for target in source_paths:
            if target != source:
                dependencies[source].add(Dependency(target, "UNRESOLVED"))

    if isinstance(changed_files, (str, Path)):
        changed_files = (str(changed_files),)
    changed = _normalise_changed(tuple(changed_files), root_real)
    unknown_python = any(path.endswith(".py") and path not in dependencies for path in changed)
    affected: dict[str, Affected] = {}

    def add_affected(path: str, chain: tuple[str, ...], reasons: tuple[str, ...]) -> None:
        category = roots[path]
        candidate = Affected(path, category, chain, reasons)
        previous = affected.get(path)
        if previous is None or (len(candidate.chain), candidate.chain, candidate.reasons) < (
            len(previous.chain), previous.chain, previous.reasons
        ):
            affected[path] = candidate

    if unknown_python:
        for root_path in sorted(roots):
            add_affected(root_path, (root_path, "UNRESOLVED", changed[0]), ("UNRESOLVED",))
    else:
        reverse: dict[str, list[tuple[str, str]]] = {}
        for importer, edges in dependencies.items():
            for edge in edges:
                reverse.setdefault(edge.path, []).append((importer, edge.reason))
        for target in changed:
            if target not in dependencies:
                continue
            # Walk from the changed leaf back to its importers, preserving one
            # shortest reason chain for every reachable test/demo.
            toward_changed: dict[str, tuple[str, str] | None] = {target: None}
            queue: deque[str] = deque([target])
            while queue:
                dependency = queue.popleft()
                for importer, reason in sorted(reverse.get(dependency, ())):
                    if importer not in toward_changed:
                        toward_changed[importer] = (dependency, reason)
                        queue.append(importer)
            for root_path in roots:
                if root_path not in toward_changed:
                    continue
                chain = [root_path]
                reasons: list[str] = []
                current = root_path
                while current != target:
                    step = toward_changed[current]
                    if step is None:
                        break
                    current, reason = step
                    reasons.append(reason)
                    chain.append(current)
                if chain[-1] == target:
                    add_affected(root_path, tuple(chain), tuple(reasons))

    return ImpactReport(changed, tuple(affected[path] for path in sorted(affected)))


def affected_paths(
    changed_files: tuple[str, ...] | list[str] | str | Path, repo: str | Path = "."
) -> tuple[str, ...]:
    """Convenience API returning selected tests and demos in stable order."""

    return analyze_impact(changed_files, repo).paths
