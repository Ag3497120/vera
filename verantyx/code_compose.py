"""Compose closed code parts, then independently execute specification checks."""
from __future__ import annotations

import ast
import copy
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from .code_spec import Operation, Specification, read_spec


PARTS = {kind: "code_parts:v1:" + kind for kind in
         ("filter", "map", "aggregate", "group", "sort", "diff", "dedupe", "join", "not_exists", "ratio")}


def _value(item: Any, operation: Operation) -> Any:
    return item[operation.field] if operation.field else item


def _predicate(value: Any, operation: Operation) -> bool:
    comparator = operation.comparator
    if comparator == "even":
        return value % 2 == 0
    if comparator == "odd":
        return value % 2 != 0
    if comparator == "==":
        return value == operation.value
    if comparator == "!=":
        return value != operation.value
    if value is None:
        return False
    return {">": lambda: value > operation.value, "<": lambda: value < operation.value,
            ">=": lambda: value >= operation.value, "<=": lambda: value <= operation.value}[comparator]()


def reference(spec: Specification, data: Any, other: list | None = None) -> Any:
    values = list(data.values()) if spec.shape == "dict" else list(data)
    if not values and spec.empty_stated:
        return copy.deepcopy(spec.empty)
    grouped = None
    for operation in spec.operations:
        kind = operation.kind
        if kind == "filter":
            values = [item for item in values if _predicate(_value(item, operation), operation)]
        elif kind == "map":
            transformed = []
            for item in values:
                value = _value(item, operation)
                mapped = {"square": lambda: value ** 2, "abs": lambda: abs(value),
                          "upper": lambda: value.upper(), "lower": lambda: value.lower(),
                          "strip": lambda: value.strip(), "length": lambda: len(value),
                          "multiply": lambda: value * operation.value, "pluck": lambda: value}[operation.comparator]()
                transformed.append(dict(item, **{operation.field: mapped})
                                   if operation.field and operation.comparator != "pluck" else mapped)
            values = transformed
        elif kind == "sort":
            values = sorted(values, key=lambda item: _value(item, operation), reverse=operation.descending)
        elif kind == "diff":
            values = [current - previous for previous, current in zip(values, values[1:])]
        elif kind == "dedupe":
            distinct, seen = [], []
            for item in values:
                key = _value(item, operation)
                if key not in seen:
                    seen.append(key)
                    distinct.append(item)
            values = distinct
        elif kind == "group":
            grouped = {}
            for item in values:
                grouped.setdefault(str(item[operation.field]), []).append(item)
        elif kind in ("join", "not_exists"):
            if kind == "join":
                values = [dict(item, **match) for item in values for match in other or []
                          if item[operation.field] == match[operation.field]]
            else:
                values = [item for item in values if not any(item[operation.field] == match[operation.field]
                                                           for match in other or [])]
        elif kind == "ratio":
            values = [item[operation.field] / item[operation.value] if item[operation.value] else spec.zero_division
                      for item in values]
        elif kind == "aggregate":
            def aggregate(items):
                amounts = [_value(item, operation) for item in items]
                if operation.comparator == "count":
                    return len(amounts)
                if not amounts:
                    return spec.empty if spec.empty_stated else 0 if operation.comparator == "sum" else None
                if operation.comparator == "sum":
                    return math.fsum(amounts)
                if operation.comparator == "mean":
                    return math.fsum(amounts) / len(amounts)
                extreme = min(amounts) if operation.comparator == "min" else max(amounts)
                return [item for item in items if _value(item, operation) == extreme] if spec.all_ties else extreme
            return {key: aggregate(items) for key, items in grouped.items()} if grouped is not None else aggregate(values)
    return grouped if grouped is not None else values


def samples(spec: Specification) -> list[tuple[Any, list | None]]:
    group_keys = {operation.field for operation in spec.operations if operation.kind == "group"}
    string_ops = any(operation.kind == "map" and operation.comparator in ("upper", "lower", "strip", "length")
                     for operation in spec.operations)
    null_filter = any(operation.kind == "filter" and operation.value is None and operation.comparator in ("==", "!=")
                      for operation in spec.operations)
    numeric = [-3, 0, 2, 2, 7]
    for operation in spec.operations:
        if operation.kind == "filter" and isinstance(operation.value, (int, float)):
            numeric.extend([operation.value - 1, operation.value, operation.value + 1])
    base = [" Ab ", "", "xy", "xy"] if string_ops else numeric
    if null_filter and not string_ops:
        base += [None]
    if spec.shape == "records":
        rows = []
        for index, value in enumerate(base):
            numeric_fields = {operation.field for operation in spec.operations if operation.kind in
                              ("filter", "aggregate", "sort", "ratio", "dedupe", "join", "not_exists", "map")}
            row = {key: ("alpha" if index % 2 else "beta") if key in group_keys else
                   value if key in numeric_fields else index * 3 + field_index
                   for field_index, key in enumerate(spec.fields)}
            for operation in spec.operations:
                if operation.kind == "filter" and isinstance(operation.value, str):
                    row[operation.field] = operation.value if index % 2 else "other"
                if operation.kind == "ratio":
                    row[operation.value] = 0 if index == 0 else index
            rows.append(row)
        base = rows
    second = [copy.deepcopy(base[1]), copy.deepcopy(base[-1])] if spec.shape == "records" and base else None
    arrays = [base, [], base[:1], list(reversed(base)), base[:2] * 2]
    if spec.shape == "dict":
        return [({f"item_{index}": value for index, value in enumerate(values)}, None) for values in arrays]
    return [(values, second) for values in arrays]


def _python_value(operation: Operation, variable: str = "item") -> str:
    return f"{variable}[{operation.field!r}]" if operation.field else variable


def python_code(spec: Specification) -> str:
    joined = any(operation.kind in ("join", "not_exists") for operation in spec.operations)
    lines = [f"def {spec.name}(data" + (", other" if joined else "") + "):",
             "    values = list(data.values())" if spec.shape == "dict" else "    values = list(data)"]
    if spec.empty_stated:
        lines += ["    if not values:", f"        return {spec.empty!r}"]
    group = None
    for operation in spec.operations:
        value = _python_value(operation)
        if operation.kind == "filter":
            if operation.comparator in ("even", "odd"):
                predicate = f"{value} % 2 {'==' if operation.comparator == 'even' else '!='} 0"
            elif operation.value is None:
                predicate = f"{value} is {'not ' if operation.comparator == '!=' else ''}None"
            else:
                predicate = f"{value} {operation.comparator} {operation.value!r}"
                if operation.comparator not in ("==", "!="):
                    predicate = f"{value} is not None and " + predicate
            lines += [f"    values = [item for item in values if {predicate}]"]
        elif operation.kind == "map":
            expression = {"square": f"{value} ** 2", "abs": f"abs({value})", "upper": f"{value}.upper()",
                          "lower": f"{value}.lower()", "strip": f"{value}.strip()", "length": f"len({value})",
                          "multiply": f"{value} * {operation.value!r}", "pluck": value}[operation.comparator]
            if operation.field and operation.comparator != "pluck":
                expression = f"dict(item, **{{{operation.field!r}: {expression}}})"
            lines += [f"    values = [{expression} for item in values]"]
        elif operation.kind == "sort":
            lines += [f"    values = sorted(values, key=lambda item: {value}, reverse={operation.descending})"]
        elif operation.kind == "diff":
            lines += ["    values = [values[index] - values[index - 1] for index in range(1, len(values))]"]
        elif operation.kind == "dedupe":
            lines += ["    distinct = []", "    seen = []", "    for item in values:",
                      f"        key = {value}", "        if key not in seen:", "            seen.append(key)",
                      "            distinct.append(item)", "    values = distinct"]
        elif operation.kind == "group":
            group = operation.field
            lines += ["    groups = {}", "    for item in values:",
                      f"        groups.setdefault(str(item[{group!r}]), []).append(item)"]
        elif operation.kind == "join":
            lines += ["    values = [dict(item, **match) for item in values for match in other",
                      f"              if item[{operation.field!r}] == match[{operation.field!r}]]"]
        elif operation.kind == "not_exists":
            lines += ["    values = [item for item in values if not any(",
                      f"        item[{operation.field!r}] == match[{operation.field!r}] for match in other)]"]
        elif operation.kind == "ratio":
            lines += [f"    values = [item[{operation.field!r}] / item[{operation.value!r}]",
                      f"              if item[{operation.value!r}] else {spec.zero_division!r} for item in values]"]
        elif operation.kind == "aggregate":
            default = spec.empty if spec.empty_stated else 0 if operation.comparator in ("sum", "count") else None
            lines += ["    def aggregate(items):", f"        amounts = [{value} for item in items]"]
            if operation.comparator == "count":
                lines += ["        return len(amounts)"]
            else:
                lines += ["        if not amounts:", f"            return {default!r}"]
                if operation.comparator == "sum":
                    lines += ["        return sum(amounts)"]
                elif operation.comparator == "mean":
                    lines += ["        return sum(amounts) / len(amounts)"]
                elif spec.all_ties:
                    lines += [f"        extreme = {operation.comparator}(amounts)",
                              f"        return [item for item in items if {value} == extreme]"]
                else:
                    lines += [f"        return {operation.comparator}(amounts)"]
            lines += ["    return {key: aggregate(items) for key, items in groups.items()}" if group else
                      "    return aggregate(values)"]
            return "\n".join(lines) + "\n"
    lines += ["    return groups" if group else "    return values"]
    return "\n".join(lines) + "\n"


def _js_value(operation: Operation, variable: str = "item") -> str:
    return variable + "[" + json.dumps(operation.field) + "]" if operation.field else variable


def javascript_code(spec: Specification) -> str:
    joined = any(operation.kind in ("join", "not_exists") for operation in spec.operations)
    lines = [f"function {spec.name}(data" + (", other" if joined else "") + ") {",
             "  let values = Object.values(data);" if spec.shape == "dict" else "  let values = [...data];"]
    if spec.empty_stated:
        lines += [f"  if (!values.length) return {json.dumps(spec.empty)};"]
    group = None
    for operation in spec.operations:
        value = _js_value(operation)
        if operation.kind == "filter":
            comparator = {"==": "===", "!=": "!=="}.get(operation.comparator, operation.comparator)
            predicate = (f"{value} % 2 {'===' if operation.comparator == 'even' else '!=='} 0"
                         if operation.comparator in ("even", "odd") else f"{value} {comparator} {json.dumps(operation.value)}")
            if operation.comparator in (">", "<", ">=", "<="):
                predicate = f"{value} !== null && " + predicate
            lines += [f"  values = values.filter(item => {predicate});"]
        elif operation.kind == "map":
            expression = {"square": f"{value} ** 2", "abs": f"Math.abs({value})", "upper": f"{value}.toUpperCase()",
                          "lower": f"{value}.toLowerCase()", "strip": f"{value}.trim()", "length": f"{value}.length",
                          "multiply": f"{value} * {json.dumps(operation.value)}", "pluck": value}[operation.comparator]
            if operation.field and operation.comparator != "pluck":
                expression = "({...item, [" + json.dumps(operation.field) + "]: " + expression + "})"
            lines += [f"  values = values.map(item => {expression});"]
        elif operation.kind == "sort":
            left, right = _js_value(operation, "left.item"), _js_value(operation, "right.item")
            direction = -1 if operation.descending else 1
            lines += ["  values = values.map((item, index) => ({item, index}))",
                      f"    .sort((left, right) => ({left} < {right} ? {-direction} : {left} > {right} ? {direction} : left.index - right.index))",
                      "    .map(entry => entry.item);"]
        elif operation.kind == "diff":
            lines += ["  values = values.slice(1).map((item, index) => item - values[index]);"]
        elif operation.kind == "dedupe":
            lines += ["  const seen = new Set();", "  values = values.filter(item => {",
                      f"    const key = JSON.stringify({value});", "    if (seen.has(key)) return false;",
                      "    seen.add(key);", "    return true;", "  });"]
        elif operation.kind == "group":
            group = operation.field
            lines += ["  const groups = Object.create(null);", "  for (const item of values) {",
                      f"    const key = String(item[{json.dumps(group)}]);", "    (groups[key] ??= []).push(item);", "  }"]
        elif operation.kind == "join":
            field = json.dumps(operation.field)
            lines += [f"  values = values.flatMap(item => other.filter(match => item[{field}] === match[{field}])",
                      "    .map(match => ({...item, ...match}))); "]
        elif operation.kind == "not_exists":
            field = json.dumps(operation.field)
            lines += [f"  values = values.filter(item => !other.some(match => item[{field}] === match[{field}]));"]
        elif operation.kind == "ratio":
            numerator, denominator = json.dumps(operation.field), json.dumps(operation.value)
            lines += [f"  values = values.map(item => item[{denominator}] === 0 ? {json.dumps(spec.zero_division)} : item[{numerator}] / item[{denominator}]);"]
        elif operation.kind == "aggregate":
            default = spec.empty if spec.empty_stated else 0 if operation.comparator in ("sum", "count") else None
            lines += ["  function aggregate(items) {", f"    const amounts = items.map(item => {value});"]
            if operation.comparator == "count":
                lines += ["    return amounts.length;"]
            else:
                lines += [f"    if (!amounts.length) return {json.dumps(default)};"]
                if operation.comparator in ("sum", "mean"):
                    suffix = " / amounts.length" if operation.comparator == "mean" else ""
                    lines += ["    return amounts.reduce((total, amount) => total + amount, 0)" + suffix + ";"]
                else:
                    comparison = "<" if operation.comparator == "min" else ">"
                    lines += [f"    const extreme = amounts.reduce((best, amount) => amount {comparison} best ? amount : best);"]
                    lines += [f"    return items.filter(item => {value} === extreme);" if spec.all_ties else "    return extreme;"]
            lines += ["  }", "  return Object.fromEntries(Object.entries(groups).map(([key, items]) => [key, aggregate(items)]));"
                      if group else "  return aggregate(values);"]
            return "\n".join(lines + ["}"]) + "\n"
    return "\n".join(lines + ["  return groups;" if group else "  return values;", "}"]) + "\n"


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(int(value)) if isinstance(value, bool) else repr(value)


def sql_code(spec: Specification) -> str:
    selection, filters, grouping, ordering = "base.*", [], "", ""
    table = _quote_identifier(spec.table) + " AS base"
    joined = False
    for operation in spec.operations:
        column = "base." + _quote_identifier(operation.field) if operation.field else "*"
        if operation.kind == "filter":
            if not operation.field:
                raise ValueError("SQL filter column")
            if operation.value is None:
                filters.append(column + (" IS NOT NULL" if operation.comparator == "!=" else " IS NULL"))
            elif operation.comparator in ("even", "odd"):
                filters.append(column + " % 2 " + ("=" if operation.comparator == "even" else "!=" ) + " 0")
            else:
                filters.append(f"{column} {operation.comparator} {_sql_literal(operation.value)}")
        elif operation.kind == "group":
            grouping = column
        elif operation.kind == "aggregate":
            aggregate = {"sum": "SUM", "mean": "AVG", "count": "COUNT", "min": "MIN", "max": "MAX"}[operation.comparator]
            operand = "*" if aggregate == "COUNT" else column
            expression = f"{aggregate}({operand})"
            if operation.comparator in ("sum", "count") or spec.empty_stated:
                default = spec.empty if spec.empty_stated else 0
                if default is not None:
                    expression = f"COALESCE({expression}, {_sql_literal(default)})"
            if spec.all_ties and operation.comparator in ("min", "max") and not grouping:
                conditions = " WHERE " + " AND ".join(filters) if filters else ""
                filters.append(f"{column} = (SELECT {aggregate}({_quote_identifier(operation.field)}) FROM "
                               f"{_quote_identifier(spec.table)} AS base{conditions})")
                selection = "base.*"
            else:
                selection = (grouping + ", " if grouping else "") + expression + ' AS "result"'
        elif operation.kind == "sort":
            ordering = column + (" DESC" if operation.descending else " ASC")
            if spec.stable and not grouping:
                ordering += ", base.rowid ASC"
        elif operation.kind == "dedupe":
            selection = "DISTINCT " + (column if operation.field else "base.*")
        elif operation.kind in ("join", "not_exists"):
            other = _quote_identifier(spec.other_table)
            condition = f"base.{_quote_identifier(operation.field)} = other.{_quote_identifier(operation.field)}"
            if operation.kind == "join":
                table += f" JOIN {other} AS other ON {condition}"
                joined = True
            else:
                filters.append(f"NOT EXISTS (SELECT 1 FROM {other} AS other WHERE {condition})")
        elif operation.kind == "ratio":
            denominator = "base." + _quote_identifier(operation.value)
            selection = f"CASE WHEN {denominator} = 0 THEN {_sql_literal(spec.zero_division)} ELSE 1.0 * {column} / {denominator} END AS result"
        elif operation.kind == "map" and operation.comparator == "pluck":
            selection = column
        else:
            raise ValueError("SQL part " + operation.kind)
    if joined and selection == "base.*":
        selection = "base.*"
    return (f"SELECT {selection}\nFROM {table}" + ("\nWHERE " + " AND ".join(filters) if filters else "") +
            ("\nGROUP BY " + grouping if grouping else "") + ("\nORDER BY " + ordering if ordering else "") + ";\n")


def shell_code(spec: Specification) -> str:
    if spec.shape != "list" or spec.fields:
        raise ValueError("shell input must be one numeric value per line")
    stages = []
    for operation in spec.operations:
        if operation.kind == "sort":
            stages.append("sort -nr" if operation.descending else "sort -n")
        elif operation.kind == "dedupe":
            stages.append("awk '!seen[$0]++'")
        elif operation.kind == "diff":
            stages.append("awk 'NR > 1 { print $1 - previous } { previous = $1 }'")
        elif operation.kind == "filter":
            if operation.value is None and operation.comparator not in ("even", "odd"):
                raise ValueError("shell null representation")
            predicate = ("$1 % 2 " + ("==" if operation.comparator == "even" else "!=") + " 0"
                         if operation.comparator in ("even", "odd") else f"$1 {operation.comparator} {_sql_literal(operation.value)}")
            if isinstance(operation.value, str):
                raise ValueError("shell string filter")
            stages.append("awk '" + predicate + "'")
        elif operation.kind == "map":
            expression = {"square": "$1 * $1", "multiply": f"$1 * {operation.value}",
                          "abs": "($1 < 0 ? -$1 : $1)"}.get(operation.comparator)
            if expression is None:
                raise ValueError("shell transform " + operation.comparator)
            stages.append("awk '{ print " + expression + " }'")
        elif operation.kind == "aggregate" and operation.comparator in ("sum", "mean", "count"):
            default_value = spec.empty if spec.empty_stated else 0 if operation.comparator in ("sum", "count") else None
            default = "null" if default_value is None else str(default_value)
            expression = {"sum": "total", "mean": "total / count", "count": "count"}[operation.comparator]
            stages.append("awk '{ total += $1; count++ } END { if (count) printf \"%.17g\\n\", " + expression +
                          '; else print "' + default + '" }' + "'")
        else:
            raise ValueError("shell part " + operation.kind)
    return "#!/bin/sh\n" + " |\n".join(stages) + "\n"


def _equivalent(actual: Any, expected: Any) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(actual, list) and isinstance(expected, list):
        return len(actual) == len(expected) and all(_equivalent(left, right) for left, right in zip(actual, expected))
    if isinstance(actual, dict) and isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_equivalent(actual[key], expected[key]) for key in actual)
    return actual == expected


def verify(spec: Specification, code: str) -> dict:
    fixtures = samples(spec)
    expected = [reference(spec, data, other) for data, other in fixtures]
    if spec.language == "sql":
        results = []
        for (data, other), wanted in zip(fixtures, expected):
            with sqlite3.connect(":memory:") as con:
                columns = ",".join(_quote_identifier(key) for key in spec.fields)
                if not columns:
                    raise ValueError("SQL table columns")
                for name, records in ((spec.table, data), (spec.other_table, other or [])):
                    con.execute(f"CREATE TABLE {_quote_identifier(name)} ({columns})")
                    con.executemany(f"INSERT INTO {_quote_identifier(name)} VALUES ({','.join('?' for key in spec.fields)})",
                                    [tuple(row[key] for key in spec.fields) for row in records])
                cursor = con.execute(code)
                rows = cursor.fetchall()
                names = [column[0] for column in cursor.description]
                if isinstance(wanted, dict):
                    actual = {str(row[0]): row[1] for row in rows}
                elif not isinstance(wanted, list):
                    actual = rows[0][0] if rows else None
                elif wanted and isinstance(wanted[0], dict):
                    actual = [dict(zip(names, row)) for row in rows]
                elif wanted:
                    actual = [row[0] for row in rows]
                else:
                    actual = [] if not rows else [dict(zip(names, row)) for row in rows]
                if not _equivalent(actual, wanted):
                    raise ValueError("SQL spec check mismatch")
                results.append({"input": data, "expected": wanted, "passed": True})
        return {"syntax": "sqlite", "checks": results, "passed": True}
    joined = any(operation.kind in ("join", "not_exists") for operation in spec.operations)
    payload = [{"data": data, "other": other, "expected": wanted}
               for (data, other), wanted in zip(fixtures, expected)]
    with tempfile.TemporaryDirectory(prefix="vera-code-") as directory:
        root = Path(directory)
        if spec.language == "python":
            ast.parse(code)
            runner = code + "\nimport json, sys, copy\nresults = []\nfor case in json.load(sys.stdin):\n"
            runner += "    original = copy.deepcopy(case['data'])\n    original_other = copy.deepcopy(case['other'])\n"
            runner += f"    actual = {spec.name}(case['data']" + (", case['other']" if joined else "") + ")\n"
            runner += "    results.append({'actual': actual, 'unchanged': case['data'] == original and case['other'] == original_other})\nprint(json.dumps(results))\n"
            path = root / "check.py"
            path.write_text(runner, encoding="utf-8")
            command = [sys.executable, "-I", "-S", str(path)]
            syntax = "ast.parse"
        elif spec.language == "javascript":
            node = shutil.which("node")
            if not node:
                raise ValueError("node is unavailable")
            path = root / "check.js"
            path.write_text(code, encoding="utf-8")
            syntax_check = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, timeout=5)
            if syntax_check.returncode:
                raise ValueError("node --check failed")
            runner = code + "\nconst fs = require('fs');\nconst cases = JSON.parse(fs.readFileSync(0, 'utf8'));\n"
            runner += "const results = cases.map(entry => { const original = JSON.stringify(entry.data); const originalOther = JSON.stringify(entry.other);\n"
            runner += f"  const actual = {spec.name}(entry.data" + (", entry.other" if joined else "") + ");\n"
            runner += "  return {actual, unchanged: JSON.stringify(entry.data) === original && JSON.stringify(entry.other) === originalOther}; });\nconsole.log(JSON.stringify(results));\n"
            path.write_text(runner, encoding="utf-8")
            command, syntax = [node, str(path)], "node --check"
        else:
            path = root / "check.sh"
            path.write_text(code, encoding="utf-8")
            checked = subprocess.run(["sh", "-n", str(path)], capture_output=True, text=True, timeout=5)
            if checked.returncode:
                raise ValueError("sh -n failed")
            checks = []
            for (data, other), wanted in zip(fixtures, expected):
                completed = subprocess.run(["sh", str(path)], input="".join(str(value) + "\n" for value in data),
                                           capture_output=True, text=True, timeout=5, cwd=root)
                if completed.returncode:
                    raise ValueError("shell unit check failed")
                values = [None if line == "null" else float(line) for line in completed.stdout.splitlines()]
                actual = values if isinstance(wanted, list) else values[0] if len(values) == 1 else None
                if not _equivalent(actual, wanted):
                    raise ValueError("shell specification check mismatch")
                checks.append({"input": data, "expected": wanted, "passed": True})
            return {"syntax": "sh -n", "checks": checks, "passed": True,
                    "scope": "newline-delimited numeric input"}
        completed = subprocess.run(command, input=json.dumps(payload), capture_output=True,
                                   text=True, timeout=5, cwd=root)
        if completed.returncode or len(completed.stdout) > 1000000:
            raise ValueError("generated unit checks failed: " + completed.stderr[-300:])
        results = json.loads(completed.stdout)
        if len(results) != len(expected) or any(not _equivalent(result.get("actual"), wanted) or not result.get("unchanged")
                                               for result, wanted in zip(results, expected)):
            raise ValueError("specification check mismatch")
        return {"syntax": syntax, "checks": [dict(case, passed=True) for case in payload], "passed": True}


def _refuse(issue: str, spec: Specification | None = None) -> dict:
    return {"kind": "unknown", "verdict": "UNKNOWN_CODE_SPEC", "text": "コード仕様を確認できません: " + issue,
            "how_to_resolve": "入力の形、処理の順序、出力と境界条件を明示してください。",
            "evidence": [], "sources": [], "spec": spec.as_dict() if spec else None,
            "trace": [{"part": "code_spec.read_spec", "status": "abstained", "reason": issue}]}


def answer(text: str) -> dict:
    if len(text) > 100000:
        return _refuse("specification exceeds the bounded reader")
    given = re.search(r"```(?:python|py|javascript|js)?\s*\n(.*?)```", text, re.S)
    if given is None and re.search(r"説明|解説|直して|修正|fix|explain", text, re.I):
        given = re.search(r"(?<!`)`([^`\n]+)`(?!`)", text)
    if given and re.search(r"説明|解説|直して|修正|fix|explain", text, re.I):
        try:
            return explain_or_fix(text, given.group(1))
        except (ValueError, SyntaxError, TypeError, OSError, subprocess.TimeoutExpired) as error:
            return _refuse(str(error))
    try:
        spec = read_spec(text)
    except (ValueError, SyntaxError, TypeError) as error:
        return _refuse(str(error))
    if spec.issues:
        return _refuse(", ".join(dict.fromkeys(spec.issues)), spec)
    builders = {"python": python_code, "javascript": javascript_code, "sql": sql_code, "shell": shell_code}
    try:
        code = builders[spec.language](spec)
        verification = verify(spec, code)
    except (ValueError, TypeError, KeyError, SyntaxError, sqlite3.Error, OSError, subprocess.TimeoutExpired) as error:
        result = _refuse(str(error), spec)
        result["trace"].append({"part": "code_compose.verify", "status": "abstained", "reason": str(error)})
        return result
    sources = [{"family": "code_parts", "source": PARTS[operation.kind], "text": operation.kind}
               for operation in dict.fromkeys(spec.operations)]
    sources.append({"family": "user", "source": "user:spec", "text": text})
    return {"kind": "answer", "verdict": "ANSWER", "text": "仕様から合成し検査しました。\n```" + spec.language + "\n" + code + "```",
            "code": code, "spec": spec.as_dict(), "verification": verification,
            "evidence": [text, *[source["text"] for source in sources[:-1]]], "sources": sources,
            "path": "spec_parts_execute", "trace": [
                {"part": "code_spec.read_spec", "status": "ran", "spec": spec.as_dict()},
                {"part": "code_compose.parts", "status": "ran", "parts": [operation.kind for operation in spec.operations]},
                {"part": "code_compose.verify", "status": "ran", "syntax": verification["syntax"],
                 "checks": len(verification["checks"]), "passed": True}]}


def explain_or_fix(text: str, given: str) -> dict:
    javascript = bool(re.search(r"javascript|\bjs\b", text, re.I))
    fixes = []
    wants_fix = bool(re.search(r"直して|修正|fix|repair", text, re.I))
    if not wants_fix:
        try:
            recognised = re.findall(r"\b(?:function|return|filter|map|reduce|sort)\b", given) if javascript else [
                type(node).__name__ for node in ast.walk(ast.parse(given))
                if isinstance(node, (ast.FunctionDef, ast.For, ast.If, ast.Return, ast.ListComp, ast.Call))]
        except SyntaxError:
            return _refuse("Python syntax")
        if not recognised:
            return _refuse("unrecognised code structure")
        return {"kind": "answer", "verdict": "ANSWER", "text": "認識した構文: " + ", ".join(dict.fromkeys(recognised)) +
                "。条件や返り値の全体は未検証です。", "evidence": [given],
                "sources": [{"family": "user", "source": "user:code", "text": given}],
                "trace": [{"part": "code_compose.explain", "status": "ran", "scope": "recognised syntax"}]}
    if javascript:
        changed = re.sub(r"\.filter\(Boolean\)", ".filter(value => value !== null && value !== undefined)", given)
        if changed != given:
            fixes = ["truthiness_to_null"]
            if not re.search(r"数値|numbers?|0|ゼロ|null", text, re.I):
                return _refuse("truthiness filter input type")
            if not shutil.which("node"):
                return _refuse("node is unavailable")
            with tempfile.TemporaryDirectory(prefix="vera-fix-") as directory:
                path = Path(directory) / "fix.js"
                path.write_text(changed, encoding="utf-8")
                checked = subprocess.run([shutil.which("node"), "--check", str(path)], capture_output=True, timeout=5)
                if checked.returncode:
                    return _refuse("JavaScript syntax")
                check = subprocess.run([shutil.which("node"), "-e",
                    "const before=[0,1,null].filter(Boolean); const after=[0,1,null].filter(value => value !== null && value !== undefined);"
                    "if(JSON.stringify(before)!=='[1]' || JSON.stringify(after)!=='[0,1]') process.exit(1);"],
                    capture_output=True, timeout=5)
                if check.returncode:
                    return _refuse("null fix check")
                expression = re.search(r"(" + r"[A-Za-z_][A-Za-z0-9_]*" + r")\.filter\(Boolean\)", given)
                matched = expression.group(0) if expression else ""
                if not matched:
                    return _refuse("filter expression")
                verified_expression = matched.replace(expression.group(1), "data", 1).replace(
                    ".filter(Boolean)", ".filter(value => value !== null && value !== undefined)")
                spec = Specification("javascript", "list", "check_filter", (), [Operation("filter", comparator="!=", value=None)])
                verification = verify(spec, "function check_filter(data) { return " + verified_expression + "; }")
        else:
            recognised = re.findall(r"\b(?:function|return|filter|map|reduce|sort)\b", given)
            if not recognised:
                return _refuse("unrecognised JavaScript")
            return {"kind": "answer", "verdict": "ANSWER", "text": "認識した構文: " + ", ".join(dict.fromkeys(recognised)) +
                    "。動作全体は検証していません。", "evidence": [given],
                    "sources": [{"family": "user", "source": "user:code", "text": given}],
                    "trace": [{"part": "code_compose.explain", "status": "ran", "scope": "recognised syntax"}]}
    else:
        try:
            tree = ast.parse(given)
        except SyntaxError:
            return _refuse("Python syntax")
        for node in ast.walk(tree):
            if isinstance(node, ast.comprehension):
                node.ifs = [ast.Compare(left=condition, ops=[ast.IsNot()], comparators=[ast.Constant(None)])
                            if isinstance(condition, ast.Name) and isinstance(node.target, ast.Name) and
                            condition.id == node.target.id else condition for condition in node.ifs]
        changed = ast.unparse(ast.fix_missing_locations(tree))
        if ast.dump(tree) != ast.dump(ast.parse(given)):
            if not re.search(r"数値|numbers?|0|ゼロ|None", text, re.I):
                return _refuse("truthiness filter input type")
            fixes = ["truthiness_to_null"]
            before = [value for value in [0, 1, None] if value]
            after = [value for value in [0, 1, None] if value is not None]
            if before != [1] or after != [0, 1]:
                return _refuse("null fix check")
            ast.parse(changed)
            comprehensions = [node for node in ast.walk(tree) if isinstance(node, ast.ListComp)]
            if len(comprehensions) != 1 or len(comprehensions[0].generators) != 1:
                return _refuse("unsupported surrounding comprehension")
            comprehension = comprehensions[0]
            generator = comprehension.generators[0]
            if (not isinstance(generator.iter, ast.Name) or not isinstance(generator.target, ast.Name) or
                    not isinstance(comprehension.elt, ast.Name) or comprehension.elt.id != generator.target.id or
                    generator.is_async or len(generator.ifs) != 1 or not isinstance(generator.ifs[0], ast.Compare)):
                return _refuse("unverified null-filter surroundings")
            generator.iter = ast.Name(id="data", ctx=ast.Load())
            expression = ast.unparse(ast.fix_missing_locations(comprehension))
            spec = Specification("python", "list", "check_filter", (), [Operation("filter", comparator="!=", value=None)])
            verification = verify(spec, "def check_filter(data):\n    return " + expression + "\n")
        else:
            recognised = [type(node).__name__ for node in ast.walk(tree)
                          if isinstance(node, (ast.FunctionDef, ast.For, ast.If, ast.Return, ast.ListComp, ast.Call))]
            return {"kind": "answer", "verdict": "ANSWER", "text": "認識した構文: " + ", ".join(dict.fromkeys(recognised)) +
                    "。動作全体は検証していません。", "evidence": [given],
                    "sources": [{"family": "user", "source": "user:code", "text": given}],
                    "trace": [{"part": "code_compose.explain", "status": "ran", "scope": "AST structure"}]}
    return {"kind": "answer", "verdict": "ANSWER", "text": "数値0を残し、欠損値だけを除外する修正です。\n```" +
            ("javascript" if javascript else "python") + "\n" + changed + "\n```", "code": changed,
            "evidence": [given, changed], "sources": [{"family": "user", "source": "user:code", "text": given},
            {"family": "code_parts", "source": "code_parts:v1:truthiness_to_null", "text": "explicit null filter"}],
            "verification": dict(verification, before=[1], after=[0, 1], scope="matched null-filter expression"),
            "trace": [{"part": "code_compose.fix", "status": "ran", "patterns": fixes}]}
