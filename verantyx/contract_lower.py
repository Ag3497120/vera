"""Closed, effect-free lowering of the registered B typed dependency plans.

This module preserves a supplied plan. It does not read natural language or
certify that the plan satisfies its source request. Dynamic oracle checks are
the responsibility of contract_verify/contract_sandbox.
"""
from __future__ import annotations

import json
import keyword
import re
from dataclasses import replace
from typing import Dict, List

from .contract_budget import Budget
from .contract_ir import Artifact, ContractError, ProgramContract, TypedProgramPlan, ValueType
from .contract_plan import boundary_type

_FAMILIES = frozenset(("filter", "map", "sort", "dedupe", "diff", "aggregate", "group", "join", "not_exists", "ratio"))
_COLLECTIONS = frozenset(("Seq", "Sequence", "Relation"))
_JS_RESERVED = frozenset("arguments await break case catch class const continue debugger default delete do else enum eval export extends false finally for function if implements import in instanceof interface let new null package private protected public return static super switch this throw true try typeof var void while with yield".split())
_CONFIG_KEYS = {
    "filter": {"predicate"}, "map": {"subkind", "field", "value", "alias"},
    "sort": {"field", "descending"}, "dedupe": {"field"}, "diff": set(),
    "aggregate": {"subkind", "field", "empty", "all_ties", "key_alias", "value_alias", "order", "alias"},
    "group": {"field", "key_alias", "value_alias", "order"},
    "join": {"left_key", "right_key", "projection"}, "not_exists": {"left_key", "right_key"},
    "ratio": {"numerator", "denominator", "zero", "alias"},
}


def _fail(message: str, code: str = "BACKEND_UNSUPPORTED") -> None:
    raise ContractError(code, "lowering", message)


def _identifier(name: str, language: str = "") -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", name):
        _fail("identifier is outside the registered profile")
    if language == "python" and keyword.iskeyword(name) or language == "js" and name in _JS_RESERVED:
        _fail("requested identifier is reserved in the target language")
    return name


def _row(typ: ValueType) -> ValueType:
    if typ.kind in _COLLECTIONS or typ.kind == "Groups":
        return typ.item or ValueType("Record", fields=typ.fields)
    return typ


def _fields(typ: ValueType) -> tuple:
    return tuple(name for name, _ in _row(typ).fields)


def _shape_equal(a: ValueType, b: ValueType) -> bool:
    return a.kind == b.kind and ((a.item is None and b.item is None) or (a.item is not None and b.item is not None and _shape_equal(a.item, b.item))) and tuple(n for n, _ in a.fields) == tuple(n for n, _ in b.fields) and all(_shape_equal(x, y) for (_, x), (_, y) in zip(a.fields, b.fields))


def _field_type(typ: ValueType, field: str) -> ValueType:
    typ = _row(typ)
    if field:
        for name, child in typ.fields:
            if name == field:
                return child
        _fail("field is absent from the bound operand", "TYPE_OR_BINDING_FAILURE")
    if typ.kind == "Record":
        _fail("record operands require an explicit field", "TYPE_OR_BINDING_FAILURE")
    return typ


def _result_shape(node, symbols: dict, profile: str) -> ValueType:
    """Check what these emit rules return, independently of supplied type tags."""
    source, cfg, kind = symbols[node.inputs[0]], node.config, node.kind
    item, field = _row(source), cfg.get("field", "")
    def mapped(value):
        if item.kind == "Record":
            return replace(source, item=replace(item, fields=tuple((name, value if name == field else typ) for name, typ in item.fields)))
        return replace(source, item=value)
    if kind == "filter":
        def refine(row, pred):
            if pred["op"] == "and":
                for child in pred["args"]:
                    row = refine(row, child)
            elif pred["op"] == "not_null":
                target = pred.get("field", "")
                if row.kind == "Record":
                    row = replace(row, fields=tuple((name, typ.item if name == target and typ.kind == "Nullable" else typ) for name, typ in row.fields))
                elif not target and row.kind == "Nullable": row = row.item
            return row
        return replace(source, item=refine(item, cfg["predicate"]))
    if kind == "map":
        value = _field_type(source, field)
        sub = cfg["subkind"]
        if sub == "pluck":
            if profile == "sqlite_select_v1":
                names = _fields(node.output_type)
                if len(names) != 1: _fail("SQLite projection must have one result column", "TYPE_OR_BINDING_FAILURE")
                if cfg.get("alias", names[0]) != names[0]: _fail("SQL projection alias differs from its declared schema", "TYPE_OR_BINDING_FAILURE")
                return replace(source, item=ValueType("Record", fields=((names[0], value),)))
            return replace(source, item=value)
        return mapped(ValueType("Int") if sub in ("square", "abs", "multiply", "length") else value)
    if kind in ("sort", "dedupe", "not_exists", "diff"):
        return source
    if kind == "group":
        return ValueType("Groups", item=item, fields=((cfg.get("key_alias", "key"), _field_type(source, field)), (cfg.get("value_alias", "value"), ValueType("Int"))))
    if kind == "aggregate":
        if cfg.get("all_ties"): return source
        value = ValueType("Float64" if cfg["subkind"] == "mean" else "Int")
        if source.kind != "Groups" and cfg.get("empty", 0 if cfg["subkind"] in ("sum", "count") else None) is None:
            value = ValueType("Nullable", item=value)
        if source.kind == "Groups":
            if len(source.fields) != 2: _fail("Groups schema must bind key/value aliases", "TYPE_OR_BINDING_FAILURE")
            ka, key_type = source.fields[0]
            va = source.fields[1][0]
            if cfg.get("key_alias", ka) != ka or cfg.get("value_alias", va) != va:
                _fail("group aggregate aliases disagree", "TYPE_OR_BINDING_FAILURE")
            return ValueType("Relation" if profile == "sqlite_select_v1" else "Seq", item=ValueType("Record", fields=((ka, key_type), (va, value))))
        if profile == "sqlite_select_v1":
            names = _fields(node.output_type)
            if len(names) != 1: _fail("SQLite aggregate must have one result column", "TYPE_OR_BINDING_FAILURE")
            if cfg.get("alias", names[0]) != names[0]: _fail("SQL aggregate alias differs from its declared schema", "TYPE_OR_BINDING_FAILURE")
            return ValueType("Relation", item=ValueType("Record", fields=((names[0], value),)))
        return value
    if kind == "join":
        fields = tuple((p["alias"], _field_type(symbols[node.inputs[p["side"] == "right"]], p["field"])) for p in cfg["projection"])
        return replace(source, item=ValueType("Record", fields=fields))
    if kind == "ratio":
        value = ValueType("Nullable", item=ValueType("Float64"))
        if profile == "sqlite_select_v1":
            names = _fields(node.output_type)
            if len(names) != 1: _fail("SQLite ratio must have one result column", "TYPE_OR_BINDING_FAILURE")
            if cfg.get("alias", names[0]) != names[0]: _fail("SQL ratio alias differs from its declared schema", "TYPE_OR_BINDING_FAILURE")
            value = ValueType("Record", fields=((names[0], value),))
        return replace(source, item=value)
    _fail("unregistered result shape")


def _validate_predicate(pred: dict, typ: ValueType, symbols: dict, budget: Budget, depth: int = 0, atoms=None) -> None:
    budget.charge("lowering", location="predicate")
    atoms = [0] if atoms is None else atoms
    if not isinstance(pred, dict) or depth > 3:
        _fail("predicate is outside the registered tree profile")
    op = pred.get("op")
    if op in ("and", "or", "not"):
        if set(pred) - {"op", "args"}: _fail("unregistered logical predicate configuration")
        args = pred.get("args", [])
        if not isinstance(args, list) or len(args) != (1 if op == "not" else 2):
            _fail("invalid logical predicate", "TYPE_OR_BINDING_FAILURE")
        for arg in args:
            _validate_predicate(arg, typ, symbols, budget, depth + 1, atoms)
        return
    atoms[0] += 1
    if atoms[0] > 4 or set(pred) - {"op", "field", "value"}:
        _fail("predicate atom limit or configuration violation")
    if op not in ("gt", "ge", "lt", "le", "eq", "ne", "even", "odd", "is_null", "not_null"):
        _fail("unregistered predicate operation")
    value_type = _field_type(typ, pred.get("field", ""))
    base_type = value_type.item if value_type.kind == "Nullable" else value_type
    if base_type is None or base_type.kind not in ("Int", "Text"):
        _fail("predicate operand is outside the initial profile")
    if base_type.kind == "Text" and op not in ("eq", "ne", "is_null", "not_null"):
        _fail("Text predicate supports exact equality only")
    value = pred.get("value")
    if isinstance(value, dict):
        if set(value) != {"param"} or value["param"] not in symbols or symbols[value["param"]].kind not in ("Int", "Text"):
            _fail("predicate parameter is unbound", "TYPE_OR_BINDING_FAILURE")
        other_kind = symbols[value["param"]].kind
    elif value is not None and type(value) not in (int, str):
        _fail("unregistered predicate literal")
    else:
        other_kind = "Int" if type(value) is int else "Text" if type(value) is str else "Null"
    if op not in ("even", "odd", "is_null", "not_null") and other_kind != base_type.kind:
        _fail("predicate operand types differ", "TYPE_OR_BINDING_FAILURE")


def _prepare(contract: ProgramContract, plan: TypedProgramPlan, budget: Budget) -> list:
    budget.charge("lowering", location="entry")
    if plan.contract_hash != contract.hash or plan.profile != contract.profile or plan.return_symbol != contract.return_symbol or not _shape_equal(plan.return_type, contract.return_type) or plan.boundaries != contract.boundaries:
        _fail("plan and contract identities disagree", "TYPE_OR_BINDING_FAILURE")
    if set(plan.discharged) != set(contract.requirement_ids):
        _fail("plan does not discharge the frozen requirements", "TYPE_OR_BINDING_FAILURE")
    if contract.effect != "pure_input_unchanged":
        _fail("only the pure effect profile is registered")
    if len(plan.nodes) > 8 or len({n.id for n in plan.nodes}) != len(plan.nodes):
        _fail("plan node limit or identity violation", "TYPE_OR_BINDING_FAILURE")
    if sum(n.kind == "aggregate" for n in plan.nodes) > 1:
        _fail("multiple aggregates are outside the initial profile")
    names = [binding.name for binding in contract.inputs]
    if len(set(names)) != len(names):
        _fail("duplicate input symbols", "TYPE_OR_BINDING_FAILURE")
    symbols = {binding.name: binding.type for binding in contract.inputs}
    parameters = {binding.name: binding.type for binding in contract.inputs if binding.type.kind in ("Int", "Text")}
    pending, ordered = list(plan.nodes), []
    if len({n.output for n in pending}) != len(pending) or any(n.output in symbols for n in pending):
        _fail("duplicate output bindings", "TYPE_OR_BINDING_FAILURE")
    while pending:
        ready = [n for n in pending if all(i in symbols for i in n.inputs)]
        if not ready:
            _fail("cyclic or unbound plan dependencies", "TYPE_OR_BINDING_FAILURE")
        for node in ready:
            budget.charge("lowering", location=node.id)
            if node.kind not in _FAMILIES or len(node.inputs) != (2 if node.kind in ("join", "not_exists") else 1):
                _fail("unregistered node or input arity")
            if contract.profile == "sqlite_select_v1" and node.kind == "diff":
                _fail("SQLite Diff is outside the initial profile")
            if tuple(symbols[i] for i in node.inputs) != node.input_types:
                _fail("input type differs from bound dependency", "TYPE_OR_BINDING_FAILURE")
            if any(symbols[i].kind not in _COLLECTIONS and symbols[i].kind != "Groups" for i in node.inputs):
                _fail("operator requires a collection", "TYPE_OR_BINDING_FAILURE")
            cfg = node.config
            if not isinstance(cfg, dict):
                _fail("node config must be a closed object", "TYPE_OR_BINDING_FAILURE")
            if set(cfg) - _CONFIG_KEYS[node.kind]:
                _fail("unregistered operator configuration")
            typ = symbols[node.inputs[0]]
            if typ.kind == "Groups" and node.kind != "aggregate":
                _fail("Groups must be consumed directly by their aggregate", "TYPE_OR_BINDING_FAILURE")
            if node.kind == "filter":
                _validate_predicate(cfg.get("predicate"), typ, parameters, budget)
            elif node.kind == "map":
                if cfg.get("subkind") not in ("square", "abs", "multiply", "pluck", "upper", "lower", "strip", "length"):
                    _fail("unregistered map subkind")
                operand_type = _field_type(typ, cfg.get("field", ""))
                if "alias" in cfg and cfg["subkind"] != "pluck":
                    _fail("arithmetic/string map aliases are outside the field-update profile")
                if cfg["subkind"] in ("square", "abs", "multiply") and operand_type.kind != "Int":
                    _fail("arithmetic map requires a non-null integer", "TYPE_OR_BINDING_FAILURE")
                if cfg["subkind"] in ("upper", "lower", "strip", "length") and operand_type.kind != "Text":
                    _fail("string map requires Text", "TYPE_OR_BINDING_FAILURE")
                value = cfg.get("value")
                if cfg["subkind"] == "multiply":
                    if isinstance(value, dict):
                        if set(value) != {"param"} or value["param"] not in parameters or parameters[value["param"]].kind != "Int":
                            _fail("multiply parameter is unbound or noninteger", "TYPE_OR_BINDING_FAILURE")
                    elif type(value) is not int:
                        _fail("multiply literal must be an integer", "TYPE_OR_BINDING_FAILURE")
            elif node.kind == "aggregate":
                if cfg.get("subkind") not in ("sum", "count", "mean", "min", "max"):
                    _fail("unregistered aggregate subkind")
                if cfg["subkind"] != "count":
                    if _field_type(typ, cfg.get("field", "")).kind != "Int":
                        _fail("aggregate requires a non-null integer operand", "TYPE_OR_BINDING_FAILURE")
                if cfg.get("all_ties") and cfg["subkind"] not in ("min", "max"):
                    _fail("all_ties applies only to extrema", "TYPE_OR_BINDING_FAILURE")
                if "all_ties" in cfg and type(cfg["all_ties"]) is not bool:
                    _fail("all_ties must be a boolean", "TYPE_OR_BINDING_FAILURE")
                if "empty" in cfg:
                    empty = cfg["empty"]
                    if cfg.get("all_ties"):
                        if empty != []: _fail("all-ties empty result must be an empty sequence", "TYPE_OR_BINDING_FAILURE")
                    elif empty is not None:
                        if cfg["subkind"] == "mean":
                            if type(empty) is not float or empty != 0.0: _fail("Mean empty sentinel must be Float64 0.0", "TYPE_OR_BINDING_FAILURE")
                        elif type(empty) is not int or not -1000 <= empty <= 1000:
                            _fail("integer aggregate sentinel is outside the profile", "TYPE_OR_BINDING_FAILURE")
                if typ.kind == "Groups" and cfg.get("all_ties"):
                    _fail("grouped all-ties aggregate is outside the profile")
            elif node.kind in ("sort", "dedupe", "group"):
                if node.kind == "sort" and "descending" in cfg and type(cfg["descending"]) is not bool:
                    _fail("sort direction must be a boolean", "TYPE_OR_BINDING_FAILURE")
                if _field_type(typ, cfg.get("field", "")).kind not in ("Int", "Text"):
                    _fail("ordering/group keys require non-null Int/Text", "TYPE_OR_BINDING_FAILURE")
                if node.kind == "group" and (_row(typ).kind != "Record" or cfg.get("order", "first") not in ("first", "key")):
                    _fail("group requires a record and explicit supported ordering", "TYPE_OR_BINDING_FAILURE")
                if node.kind == "group":
                    ka, va = cfg.get("key_alias", "key"), cfg.get("value_alias", "value")
                    _identifier(ka)
                    _identifier(va)
                    if ka == va: _fail("group result aliases must differ", "TYPE_OR_BINDING_FAILURE")
            elif node.kind in ("join", "not_exists"):
                left_key = _field_type(typ, cfg.get("left_key", ""))
                right_key = _field_type(symbols[node.inputs[1]], cfg.get("right_key", ""))
                if left_key.kind not in ("Int", "Text") or left_key.kind != right_key.kind:
                    _fail("join keys differ in type or nullability", "TYPE_OR_BINDING_FAILURE")
                if node.kind == "join":
                    projection = cfg.get("projection")
                    if not isinstance(projection, list) or not projection:
                        _fail("join requires explicit projection", "TYPE_OR_BINDING_FAILURE")
                    aliases = []
                    for col in projection:
                        budget.charge("lowering", location=node.id + ":projection")
                        if col.get("side") not in ("left", "right"):
                            _fail("join projection side is unbound", "TYPE_OR_BINDING_FAILURE")
                        _field_type(symbols[node.inputs[col["side"] == "right"]], col.get("field", ""))
                        aliases.append(col.get("alias"))
                    if len(set(aliases)) != len(aliases):
                        _fail("duplicate join projection aliases", "TYPE_OR_BINDING_FAILURE")
            elif node.kind == "ratio":
                if _field_type(typ, cfg.get("numerator", "")).kind != "Int" or _field_type(typ, cfg.get("denominator", "")).kind != "Int":
                    _fail("ratio requires non-null integer operands", "TYPE_OR_BINDING_FAILURE")
                if cfg.get("zero") is not None:
                    _fail("ratio zero policy must be explicit Null")
            elif node.kind == "diff" and _row(typ).kind != "Int":
                _fail("Diff requires an integer sequence", "TYPE_OR_BINDING_FAILURE")
            if not _shape_equal(_result_shape(node, symbols, contract.profile), node.output_type):
                _fail("declared output shape differs from emitted semantics", "TYPE_OR_BINDING_FAILURE")
            symbols[node.output] = node.output_type
            ordered.append(node)
            pending.remove(node)
    try:
        returned_type = boundary_type(symbols[plan.return_symbol], contract.boundaries) if plan.return_symbol in symbols else None
    except ContractError as error:
        raise ContractError(error.code, "lowering", error.message, error.details) from error
    if returned_type != plan.return_type or plan.return_type.kind == "Groups":
        _fail("return type is unbound or internal", "TYPE_OR_BINDING_FAILURE")
    for boundary in contract.boundaries:
        budget.charge("lowering", location="boundary")
        if boundary.trigger != "input_empty" or boundary.symbol not in names or symbols[boundary.symbol].kind not in _COLLECTIONS:
            _fail("only entry collection-empty overrides are registered")
    if len(contract.boundaries) > 1:
        _fail("multiple entry-empty overrides are outside the profile")
    return ordered


_PY_HELPERS = '''def @get(row, field):
    return row[field] if field else row

def @value(value, params):
    return params[value['param']] if isinstance(value, dict) else value

def @pred(row, pred, params):
    op = pred['op']
    if op in ('and', 'or', 'not'):
        values = [@pred(row, p, params) for p in pred['args']]
        if op == 'not':
            return None if values[0] is None else not values[0]
        if op == 'and':
            return False if False in values else True if all(v is True for v in values) else None
        return True if True in values else False if all(v is False for v in values) else None
    a = @get(row, pred.get('field', ''))
    if op == 'is_null': return a is None
    if op == 'not_null': return a is not None
    b = @value(pred.get('value'), params)
    if a is None or op not in ('even', 'odd') and b is None: return None
    if op == 'even': return a % 2 == 0
    if op == 'odd': return a % 2 != 0
    if op == 'gt': return a > b
    if op == 'ge': return a >= b
    if op == 'lt': return a < b
    if op == 'le': return a <= b
    if op == 'eq': return a == b
    return a != b

def @agg(rows, cfg):
    kind = cfg['subkind']
    if not rows: return cfg.get('empty', 0 if kind in ('sum', 'count') else None)
    if kind == 'count': return len(rows)
    values = [@get(r, cfg.get('field', '')) for r in rows]
    if kind == 'sum': return sum(values)
    if kind == 'mean': return float(sum(values) / len(values))
    return min(values) if kind == 'min' else max(values)

def @apply(kind, rows, other, cfg, params):
    field = cfg.get('field', '')
    if kind == 'filter': return [r for r in rows if @pred(r, cfg['predicate'], params) is True]
    if kind == 'map':
        out = []
        subkind = cfg['subkind']
        for r in rows:
            v = @get(r, field)
            if subkind == 'square': v = v * v
            elif subkind == 'abs': v = abs(v)
            elif subkind == 'multiply': v = v * @value(cfg['value'], params)
            elif subkind == 'upper': v = v.upper()
            elif subkind == 'lower': v = v.lower()
            elif subkind == 'strip': v = v.strip(' ')
            elif subkind == 'length': v = len(v)
            if subkind != 'pluck' and field:
                v = dict(r, **{field: v})
            out.append(v)
        return out
    if kind == 'sort': return sorted(rows, key=lambda r: @get(r, field), reverse=cfg.get('descending', False))
    if kind == 'dedupe':
        seen, out = [], []
        for r in rows:
            key = @get(r, field)
            if key not in seen:
                seen.append(key)
                out.append(r)
        return out
    if kind == 'diff': return [rows[i] - rows[i-1] for i in range(1, len(rows))]
    if kind == 'group':
        groups = []
        for r in rows:
            key = @get(r, field)
            matches = [g for g in groups if g[0] == key]
            if matches: matches[0][1].append(r)
            else: groups.append((key, [r]))
        if cfg.get('order') == 'key': groups = sorted(groups, key=lambda g: g[0])
        return groups
    if kind == 'aggregate':
        if cfg.get('_grouped'):
            return [{cfg.get('key_alias', 'key'): key, cfg.get('value_alias', 'value'): @agg(group, cfg)} for key, group in rows]
        if cfg.get('all_ties'):
            if not rows: return []
            extreme = @agg(rows, cfg)
            return [r for r in rows if @get(r, field) == extreme]
        return @agg(rows, cfg)
    if kind == 'join':
        return [{p['alias']: @get(l if p['side'] == 'left' else r, p['field']) for p in cfg['projection']}
                for l in rows for r in other if @get(l, cfg['left_key']) == @get(r, cfg['right_key'])]
    if kind == 'not_exists':
        return [l for l in rows if not any(@get(l, cfg['left_key']) == @get(r, cfg['right_key']) for r in other)]
    if kind == 'ratio':
        out = []
        for r in rows:
            a, b = @get(r, cfg['numerator']), @get(r, cfg['denominator'])
            out.append(None if b == 0 else 0.0 if a == 0 else a / b)
        return out
'''

_JS_HELPERS = '''function @get(row, field) { return field ? row[field] : row; }
function @value(value, params) { return value && typeof value === 'object' ? params[value.param] : value; }
function @pred(row, pred, params) {
  const op = pred.op;
  if (op === 'and' || op === 'or' || op === 'not') {
    const values = pred.args.map(p => @pred(row, p, params));
    if (op === 'not') return values[0] === null ? null : !values[0];
    if (op === 'and') return values.includes(false) ? false : values.every(v => v === true) ? true : null;
    return values.includes(true) ? true : values.every(v => v === false) ? false : null;
  }
  const a = @get(row, pred.field || '');
  if (op === 'is_null') return a === null;
  if (op === 'not_null') return a !== null;
  const b = @value(pred.value, params);
  if (a === null || (op !== 'even' && op !== 'odd' && b === null)) return null;
  if (op === 'even') return a % 2 === 0;
  if (op === 'odd') return a % 2 !== 0;
  if (op === 'gt') return a > b;
  if (op === 'ge') return a >= b;
  if (op === 'lt') return a < b;
  if (op === 'le') return a <= b;
  if (op === 'eq') return a === b;
  return a !== b;
}
function @agg(rows, cfg) {
  const kind = cfg.subkind;
  if (!rows.length) return Object.hasOwn(cfg, 'empty') ? cfg.empty : (kind === 'sum' || kind === 'count' ? 0 : null);
  if (kind === 'count') return rows.length;
  const values = rows.map(r => @get(r, cfg.field || ''));
  if (kind === 'sum' || kind === 'mean') {
    const total = values.reduce((a, b) => a + b, 0);
    return kind === 'sum' ? total : total / values.length;
  }
  return kind === 'min' ? Math.min(...values) : Math.max(...values);
}
function @apply(kind, rows, other, cfg, params) {
  const field = cfg.field || '';
  if (kind === 'filter') return rows.filter(r => @pred(r, cfg.predicate, params) === true);
  if (kind === 'map') return rows.map(r => {
    let v = @get(r, field);
    if (cfg.subkind === 'square') v *= v;
    else if (cfg.subkind === 'abs') v = Math.abs(v);
    else if (cfg.subkind === 'multiply') v *= @value(cfg.value, params);
    else if (cfg.subkind === 'upper') v = v.toUpperCase();
    else if (cfg.subkind === 'lower') v = v.toLowerCase();
    else if (cfg.subkind === 'strip') v = v.replace(/^ +| +$/g, '');
    else if (cfg.subkind === 'length') v = v.length;
    return cfg.subkind !== 'pluck' && field ? {...r, [field]: v} : v;
  });
  if (kind === 'sort') return rows.map((r, i) => [r, i]).sort((a, b) => {
    const x = @get(a[0], field), y = @get(b[0], field);
    return (x < y ? -1 : x > y ? 1 : 0) * (cfg.descending ? -1 : 1) || a[1] - b[1];
  }).map(x => x[0]);
  if (kind === 'dedupe') {
    const seen = new Set();
    return rows.filter(r => { const k = @get(r, field); if (seen.has(k)) return false; seen.add(k); return true; });
  }
  if (kind === 'diff') return rows.slice(1).map((v, i) => v - rows[i]);
  if (kind === 'group') {
    const groups = new Map();
    for (const r of rows) { const key = @get(r, field); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(r); }
    const result = Array.from(groups.entries());
    if (cfg.order === 'key') result.sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
    return result;
  }
  if (kind === 'aggregate') {
    if (cfg._grouped) return rows.map(([key, group]) => ({[cfg.key_alias || 'key']: key, [cfg.value_alias || 'value']: @agg(group, cfg)}));
    if (cfg.all_ties) { const extreme = @agg(rows, cfg); return rows.filter(r => @get(r, field) === extreme); }
    return @agg(rows, cfg);
  }
  if (kind === 'join') {
    const out = [];
    for (const l of rows) for (const r of other) if (@get(l, cfg.left_key) === @get(r, cfg.right_key)) {
      out.push(Object.fromEntries(cfg.projection.map(p => [p.alias, @get(p.side === 'left' ? l : r, p.field)])));
    }
    return out;
  }
  if (kind === 'not_exists') return rows.filter(l => !other.some(r => @get(l, cfg.left_key) === @get(r, cfg.right_key)));
  if (kind === 'ratio') return rows.map(r => { const a = @get(r, cfg.numerator), b = @get(r, cfg.denominator); return b === 0 ? null : a === 0 ? 0 : a / b; });
}
'''


def _function(contract: ProgramContract, nodes: list, language: str) -> str:
    interface = contract.interface
    _identifier(interface.name, language)
    params = list(interface.parameters)
    if set(params) != {b.name for b in contract.inputs} or len(set(params)) != len(params):
        _fail("requested parameters and input bindings disagree", "TYPE_OR_BINDING_FAILURE")
    for name in params:
        _identifier(name, language)
    kinds = {b.name: b.kind for b in contract.inputs}
    if language == "js" and (interface.keyword_only or any(k != "positional_or_keyword" for k in kinds.values())):
        _fail("JavaScript has no keyword-only profile")
    if language == "python" and any(k not in ("positional_or_keyword", "keyword_only") for k in kinds.values()):
        _fail("unsupported Python parameter kind")
    if set(interface.keyword_only) != {name for name, kind in kinds.items() if kind == "keyword_only"}:
        _fail("keyword-only declarations disagree", "TYPE_OR_BINDING_FAILURE")
    if interface.keyword_only and tuple(params[-len(interface.keyword_only):]) != interface.keyword_only:
        _fail("keyword-only parameters must follow positional parameters")
    prefix = "_vera_"
    while any(name.startswith(prefix) for name in params + [interface.name]):
        prefix += "x"
    literal = repr if language == "python" else lambda v: json.dumps(v, ensure_ascii=True, allow_nan=False)
    symbols = {name: name for name in params}
    types = {b.name: b.type for b in contract.inputs}
    helpers = (_PY_HELPERS if language == "python" else _JS_HELPERS).replace("@", prefix)
    if language == "python":
        builtin_names = ("isinstance", "dict", "all", "any", "len", "sum", "float", "min", "max", "abs", "sorted", "range")
        aliases = [prefix + name + " = " + name for name in builtin_names]
        for name in builtin_names:
            helpers = re.sub(r"\b" + name + r"\(", prefix + name + "(", helpers)
        # isinstance(..., dict) also needs the captured builtin class.
        helpers = helpers.replace(", dict)", ", " + prefix + "dict)")
        sig = params[:]
        if interface.keyword_only:
            sig.insert(len(params) - len(interface.keyword_only), "*")
        lines = ["\n".join(aliases), helpers, "def " + interface.name + "(" + ", ".join(sig) + "):"]
        lines.append("    " + prefix + "params = {" + ", ".join(repr(name) + ": " + name for name in params) + "}")
        for b in contract.boundaries:
            lines.append("    if not " + symbols[b.symbol] + ": return " + literal(b.value))
    else:
        builtin_names = ("Object", "Math", "Array", "Map", "Set")
        for name in builtin_names:
            helpers = re.sub(r"\b" + name + r"\b", prefix + name, helpers)
        opening = "module.exports = (function (" + ", ".join(prefix + name for name in builtin_names) + ") {"
        lines = [opening, helpers, "function " + interface.name + "(" + ", ".join(params) + ") {"]
        lines.append("  const " + prefix + "params = {" + ", ".join("[" + literal(name) + "]: " + name for name in params) + "};")
        for b in contract.boundaries:
            lines.append("  if (" + symbols[b.symbol] + ".length === 0) return " + literal(b.value) + ";")
    for i, node in enumerate(nodes):
        cfg = dict(node.config)
        if node.kind == "aggregate" and types[node.inputs[0]].kind == "Groups":
            cfg["_grouped"] = True
            cfg.setdefault("key_alias", types[node.inputs[0]].fields[0][0])
            cfg.setdefault("value_alias", types[node.inputs[0]].fields[1][0])
        out = prefix + "v" + str(i)
        args = [literal(node.kind), symbols[node.inputs[0]], symbols[node.inputs[1]] if len(node.inputs) == 2 else ("None" if language == "python" else "null"), literal(cfg), prefix + "params"]
        lines.append(("    " if language == "python" else "  const ") + out + " = " + prefix + "apply(" + ", ".join(args) + ")" + ("" if language == "python" else ";"))
        symbols[node.output], types[node.output] = out, node.output_type
    lines.append(("    return " if language == "python" else "  return ") + symbols[contract.return_symbol] + ("" if language == "python" else ";"))
    if language == "js":
        lines += ["}", "return {[" + literal(interface.name) + "]: " + interface.name + "};", "})(" + ", ".join(builtin_names) + ");"]
    return "\n".join(lines) + "\n"


def _quote(name: str) -> str:
    _identifier(name)
    return '"' + name.replace('"', '""') + '"'


def _sql_literal(value) -> str:
    if value is None: return "NULL"
    if type(value) is int: return str(value)
    if type(value) is float and value == 0.0: return "0.0"
    if type(value) is str: return "'" + value.replace("'", "''") + "'"
    _fail("SQL profile permits only closed scalar literals")


def _sql_pred(pred: dict, field_expr) -> str:
    op = pred["op"]
    if op in ("and", "or", "not"):
        args = [_sql_pred(p, field_expr) for p in pred["args"]]
        return "(NOT " + args[0] + ")" if op == "not" else "(" + (" AND " if op == "and" else " OR ").join(args) + ")"
    a = field_expr(pred.get("field", ""))
    if op == "is_null": return "(" + a + " IS NULL)"
    if op == "not_null": return "(" + a + " IS NOT NULL)"
    if op in ("even", "odd"): return "(" + a + " % 2 " + ("= 0" if op == "even" else "!= 0") + ")"
    if isinstance(pred.get("value"), dict): _fail("arbitrary SQLite parameters are outside the initial profile")
    return "(" + a + " " + {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "=", "ne": "!="}[op] + " " + _sql_literal(pred.get("value")) + ")"


def _sqlite(contract: ProgramContract, nodes: list) -> str:
    if any(b.type.kind != "Relation" for b in contract.inputs) or len(contract.inputs) > 2:
        _fail("SQLite input bindings must be at most two Relations")
    if contract.return_type.kind != "Relation":
        _fail("SQLite results must remain Relations")
    used_names = {f for b in contract.inputs for f in _fields(b.type)} | set(_fields(contract.return_type))
    table_names = {b.name for b in contract.inputs}
    ordinal = "_vera_order"
    while ordinal in used_names: ordinal += "x"
    qord = _quote(ordinal)
    ctes, states = [], {}
    def register(symbol, query, fields, ordered, group=None):
        name = "_vera_cte" + str(len(ctes))
        while name in table_names:
            name += "x"
        ctes.append(_quote(name) + " AS (" + query + ")")
        states[symbol] = (name, tuple(fields), ordered, group)
    for binding in contract.inputs:
        fields = _fields(binding.type)
        if not fields: _fail("SQLite requires an explicit input column schema")
        table = _quote(binding.name)
        cols = ", ".join(_quote(f) for f in fields)
        if binding.ordinal and binding.ordinal not in fields:
            _fail("SQLite ordinal is absent from its input schema", "TYPE_OR_BINDING_FAILURE")
        order = "ROW_NUMBER() OVER (ORDER BY " + _quote(binding.ordinal) + ")" if binding.ordinal else "0"
        register(binding.name, "SELECT " + cols + ", " + order + " AS " + qord + " FROM " + table, fields, bool(binding.ordinal))
    def agg_expr(cfg, value):
        sub = cfg["subkind"]
        if sub == "count": expr = "COUNT(*)"
        elif sub == "sum": expr = "SUM(" + value + ")"
        elif sub == "mean": expr = "CASE WHEN COUNT(*) = 0 THEN " + _sql_literal(cfg.get("empty")) + " ELSE CAST(SUM(" + value + ") AS REAL) / COUNT(*) END"
        else: expr = sub.upper() + "(" + value + ")"
        if sub != "mean":
            empty = cfg.get("empty", 0 if sub in ("sum", "count") else None)
            expr = "CASE WHEN COUNT(*) = 0 THEN " + _sql_literal(empty) + " ELSE " + expr + " END"
        return expr
    for node in nodes:
        cfg = node.config
        name, fields, ordered, group = states[node.inputs[0]]
        source = _quote(name)
        outfields = _fields(node.output_type)
        field = cfg.get("field", "")
        def fexpr(f):
            if not f:
                if len(fields) != 1: _fail("SQL scalar reference requires a one-column Relation")
                f = fields[0]
            return _quote(f)
        cols = ", ".join(_quote(f) for f in fields)
        query, outorder = "", ordered
        if node.kind == "filter":
            query = "SELECT " + cols + ", " + qord + " FROM " + source + " WHERE " + _sql_pred(cfg["predicate"], fexpr)
        elif node.kind == "map":
            sub = cfg["subkind"]
            value = fexpr(field)
            if sub == "pluck":
                if len(outfields) != 1: _fail("SQL pluck requires exactly one output column")
                selections = [value + " AS " + _quote(outfields[0])]
            else:
                if sub == "square": expr = "(" + value + " * " + value + ")"
                elif sub == "abs": expr = "ABS(" + value + ")"
                elif sub == "multiply": expr = "(" + value + " * " + _sql_literal(cfg.get("value")) + ")"
                else: _fail("SQLite string maps are outside the initial profile")
                selections = [(expr if f == (field or fields[0]) else _quote(f)) + " AS " + _quote(f) for f in fields]
            query = "SELECT " + ", ".join(selections) + ", " + qord + " FROM " + source
        elif node.kind == "sort":
            if not ordered: _fail("stable SQLite sort requires an explicit input ordinal")
            query = "SELECT " + cols + ", ROW_NUMBER() OVER (ORDER BY " + fexpr(field) + " COLLATE BINARY " + ("DESC" if cfg.get("descending") else "ASC") + ", " + qord + ") AS " + qord + " FROM " + source
            outorder = True
        elif node.kind == "dedupe":
            if not ordered: _fail("first-preserving SQLite dedupe requires an explicit ordinal")
            rank = ordinal + "r"
            while rank in used_names or rank in fields:
                rank += "x"
            query = "SELECT " + cols + ", " + qord + " FROM (SELECT " + cols + ", " + qord + ", ROW_NUMBER() OVER (PARTITION BY " + fexpr(field) + " ORDER BY " + qord + ") AS " + _quote(rank) + " FROM " + source + ") WHERE " + _quote(rank) + " = 1"
        elif node.kind == "group":
            if cfg.get("order", "first") == "first" and not ordered: _fail("first group order requires explicit ordinal")
            register(node.output, "SELECT " + cols + ", " + qord + " FROM " + source, fields, ordered, dict(cfg))
            continue
        elif node.kind == "aggregate":
            if group:
                if cfg.get("all_ties"): _fail("grouped all-ties aggregate is unsupported")
                key_alias, value_alias = cfg.get("key_alias", group.get("key_alias", "key")), cfg.get("value_alias", group.get("value_alias", "value"))
                key = fexpr(group["field"])
                order = "MIN(" + qord + ")" if group.get("order", "first") == "first" else "ROW_NUMBER() OVER (ORDER BY " + key + " COLLATE BINARY)"
                query = "SELECT " + key + " AS " + _quote(key_alias) + ", " + agg_expr(cfg, fexpr(field) if cfg["subkind"] != "count" else "*") + " AS " + _quote(value_alias) + ", " + order + " AS " + qord + " FROM " + source + " GROUP BY " + key
                outorder = True
            elif cfg.get("all_ties"):
                if cfg["subkind"] not in ("min", "max"): _fail("all_ties only applies to extrema")
                query = "SELECT " + cols + ", " + qord + " FROM " + source + " WHERE " + fexpr(field) + " = (SELECT " + cfg["subkind"].upper() + "(" + fexpr(field) + ") FROM " + source + ")"
            else:
                if len(outfields) != 1: _fail("global SQL aggregate requires one output column")
                query = "SELECT " + agg_expr(cfg, fexpr(field) if cfg["subkind"] != "count" else "*") + " AS " + _quote(outfields[0]) + ", 1 AS " + qord + " FROM " + source
                outorder = True
        elif node.kind in ("join", "not_exists"):
            right, rfields, rorder, _ = states[node.inputs[1]]
            condition = "l." + _quote(cfg["left_key"]) + " = r." + _quote(cfg["right_key"])
            if node.kind == "not_exists":
                query = "SELECT " + ", ".join("l." + _quote(f) for f in fields) + ", l." + qord + " AS " + qord + " FROM " + source + " AS l WHERE NOT EXISTS (SELECT 1 FROM " + _quote(right) + " AS r WHERE " + condition + ")"
            else:
                selections = [("l." if p["side"] == "left" else "r.") + _quote(p["field"]) + " AS " + _quote(p["alias"]) for p in cfg["projection"]]
                outorder = ordered and rorder
                order = "ROW_NUMBER() OVER (ORDER BY l." + qord + ", r." + qord + ")" if outorder else "0"
                query = "SELECT " + ", ".join(selections) + ", " + order + " AS " + qord + " FROM " + source + " AS l JOIN " + _quote(right) + " AS r ON " + condition
        elif node.kind == "ratio":
            if len(outfields) != 1: _fail("ratio projection requires one result column")
            a, b = fexpr(cfg["numerator"]), fexpr(cfg["denominator"])
            query = "SELECT CASE WHEN " + b + " = 0 THEN NULL WHEN " + a + " = 0 THEN 0.0 ELSE CAST(" + a + " AS REAL) / " + b + " END AS " + _quote(outfields[0]) + ", " + qord + " FROM " + source
        else:
            _fail("SQLite Diff is outside the initial profile")
        register(node.output, query, outfields, outorder)
    final, fields, ordered, _ = states[contract.return_symbol]
    columns = contract.interface.columns or fields
    if tuple(columns) != fields:
        _fail("SQL output columns and return schema disagree", "TYPE_OR_BINDING_FAILURE")
    if contract.interface.ordered and not ordered:
        _fail("ordered SQL output requires explicit ordinal semantics")
    selected = ", ".join(_quote(f) for f in columns)
    query = "SELECT " + selected + " FROM " + _quote(final)
    if contract.boundaries:
        boundary = contract.boundaries[0]
        table = _quote(boundary.symbol)
        value = boundary.value
        if value == []:
            query += " WHERE EXISTS (SELECT 1 FROM " + table + ")"
        elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict) and set(value[0]) == set(columns):
            query = "SELECT " + selected + " FROM (SELECT " + selected + ", " + qord + " FROM " + _quote(final) + " WHERE EXISTS (SELECT 1 FROM " + table + ") UNION ALL SELECT " + ", ".join(_sql_literal(value[0][f]) + " AS " + _quote(f) for f in columns) + ", 0 AS " + qord + " WHERE NOT EXISTS (SELECT 1 FROM " + table + "))"
        else: _fail("SQL input-empty override must have the exact Relation shape")
    if contract.interface.ordered: query += " ORDER BY " + qord
    return "WITH " + ",\n".join(ctes) + "\n" + query + ";\n"


def _awk_pred(pred: dict, params: dict) -> str:
    op = pred["op"]
    if pred.get("field"): _fail("POSIX record predicates are outside the profile")
    if op in ("and", "or", "not"):
        args = [_awk_pred(p, params) for p in pred["args"]]
        return "(!" + args[0] + ")" if op == "not" else "(" + (" && " if op == "and" else " || ").join(args) + ")"
    if op in ("is_null", "not_null"): _fail("POSIX null operands are outside the profile")
    if op in ("even", "odd"): return "(v % 2 " + ("== 0" if op == "even" else "!= 0") + ")"
    val = pred.get("value")
    if isinstance(val, dict): val = params[val["param"]]
    elif type(val) is int: val = str(val)
    else: _fail("POSIX predicates require integer values")
    return "(v " + {"gt": ">", "ge": ">=", "lt": "<", "le": "<=", "eq": "==", "ne": "!="}[op] + " " + val + ")"


def _posix(contract: ProgramContract, nodes: list) -> str:
    collections = [b for b in contract.inputs if b.type.kind in _COLLECTIONS]
    scalars = [b for b in contract.inputs if b.type.kind not in _COLLECTIONS]
    if len(collections) != 1 or _row(collections[0].type).kind != "Int" or any(b.type.kind != "Int" for b in scalars):
        _fail("POSIX profile accepts one integer stream and integer argv only")
    argv = contract.interface.argv
    if len(argv) > 2 or set(argv) != {b.name for b in scalars}:
        _fail("POSIX argv bindings disagree", "TYPE_OR_BINDING_FAILURE")
    params = {name: "p" + str(i) for i, name in enumerate(argv)}
    arrays, counts = {collections[0].name: "a0"}, {collections[0].name: "n0"}
    body = ["{ a0[++n0] = $0 + 0 }", "END {"]
    for boundary in contract.boundaries:
        value = boundary.value
        if value is None: token = "null"
        elif type(value) is int: token = str(value)
        elif type(value) is float and value == 0: token = "0.0"
        elif value == []: token = ""
        else: _fail("POSIX entry sentinel is outside the scalar/empty profile")
        body.append("  if (n0 == 0) { " + ("print \"" + token + "\"; " if token else "") + "exit 0 }")
    results = {}
    for idx, node in enumerate(nodes, 1):
        cfg, kind = node.config, node.kind
        a, n = arrays.get(node.inputs[0]), counts.get(node.inputs[0])
        if a is None: _fail("POSIX operator requires an integer stream")
        b, m = "a" + str(idx), "n" + str(idx)
        if cfg.get("field"): _fail("POSIX record fields are outside the profile")
        body.append("  " + m + " = 0")
        if kind == "filter":
            expr = _awk_pred(cfg["predicate"], params)
            body.append("  for (i=1; i<=" + n + "; i++) { v=" + a + "[i]; if (" + expr + ") " + b + "[++" + m + "]=v }")
        elif kind == "map":
            sub = cfg["subkind"]
            if sub == "square": expr = "v*v"
            elif sub == "abs": expr = "(v < 0 ? -v : v)"
            elif sub == "multiply":
                factor = cfg["value"]
                if isinstance(factor, dict): factor = params[factor["param"]]
                elif type(factor) is int: factor = str(factor)
                else: _fail("POSIX multiplication requires an integer coefficient")
                expr = "v*(" + factor + ")"
            else: _fail("POSIX map subkind is outside the initial profile")
            body.append("  for (i=1; i<=" + n + "; i++) { v=" + a + "[i]; " + b + "[++" + m + "]=" + expr + " }")
        elif kind == "diff":
            body.append("  for (i=2; i<=" + n + "; i++) " + b + "[++" + m + "]=" + a + "[i]-" + a + "[i-1]")
        elif kind == "sort":
            comp = "<" if cfg.get("descending") else ">"
            body += ["  for (i=1; i<=" + n + "; i++) " + b + "[++" + m + "]=" + a + "[i]",
                     "  for (i=2; i<=" + m + "; i++) { v=" + b + "[i]; j=i-1; while (j>=1 && " + b + "[j] " + comp + " v) { " + b + "[j+1]=" + b + "[j]; j-- } " + b + "[j+1]=v }"]
        elif kind == "dedupe":
            seen = "s" + str(idx)
            body.append("  for (i=1; i<=" + n + "; i++) { v=" + a + "[i]; key=sprintf(\"%.0f\", (v==0 ? 0 : v)); if (!(key in " + seen + ")) { " + seen + "[key]=1; " + b + "[++" + m + "]=v } }")
        elif kind == "aggregate":
            sub = cfg["subkind"]
            if sub not in ("sum", "count", "mean") or cfg.get("all_ties"): _fail("POSIX aggregate subkind is outside the profile")
            var = "r" + str(idx)
            body += ["  " + var + "=0", "  for (i=1; i<=" + n + "; i++) " + var + "+=" + ("1" if sub == "count" else a + "[i]")]
            empty = cfg.get("empty", 0 if sub in ("sum", "count") else None)
            if empty is not None and type(empty) not in (int, float): _fail("invalid POSIX aggregate sentinel")
            if sub == "mean": body.append("  if (" + n + ">0) " + var + "=" + var + "/" + n)
            if empty is not None: body.append("  if (" + n + "==0) " + var + "=" + str(empty))
            results[node.output] = (var, sub == "mean", n if empty is None else "")
            continue
        else: _fail("POSIX node family is outside the initial profile")
        arrays[node.output], counts[node.output] = b, m
    if contract.return_symbol in results:
        value, is_float, null_count = results[contract.return_symbol]
        print_stmt = "printf \"%.17g\\n\", (" + value + "==0 ? 0 : " + value + ")" if is_float else "printf \"%.0f\\n\", (" + value + "==0 ? 0 : " + value + ")"
        if null_count: print_stmt = "if (" + null_count + "==0) print \"null\"; else " + print_stmt
        body.append("  " + print_stmt)
    else:
        a, n = arrays[contract.return_symbol], counts[contract.return_symbol]
        body.append("  for (i=1; i<=" + n + "; i++) printf \"%.0f\\n\", (" + a + "[i]==0 ? 0 : " + a + "[i])")
    body.append("}")
    options = "".join(" -v p" + str(i) + "=\"${" + str(i + 1) + "}\"" for i in range(len(argv)))
    return "#!/bin/sh\nLC_ALL=C /usr/bin/awk" + options + " '" + "\n".join(body) + "'\n"


def lower(contract: ProgramContract, plan: TypedProgramPlan, budget: Budget) -> Artifact:
    """Emit one exact artifact or raise a typed failure; no execution occurs here."""
    try:
        nodes = _prepare(contract, plan, budget)
        budget.charge("lowering", location="backend")
        if contract.profile == "python_pure_v1": source = _function(contract, nodes, "python")
        elif contract.profile == "node_commonjs_sync_v1": source = _function(contract, nodes, "js")
        elif contract.profile == "sqlite_select_v1": source = _sqlite(contract, nodes)
        elif contract.profile == "posix_numeric_stream_v1": source = _posix(contract, nodes)
        else: _fail("unregistered backend profile")
        budget.charge("artifacts", location="artifact")
        budget.charge("artifact_bytes", len(source.encode("utf-8")), "artifact")
        budget.check("lowering", "return")
        return Artifact(contract.profile, source, plan.hash, contract.interface)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        raise ContractError("TYPE_OR_BINDING_FAILURE", "lowering", "malformed closed contract/plan: " + type(error).__name__) from error
