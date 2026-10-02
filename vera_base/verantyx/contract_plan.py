"""Bounded dependency synthesis over the existing ten code-part families.

Named value relations determine dependencies. Registry order, source clause
order and neighbouring identifier distance do not choose a program meaning.
"""
from __future__ import annotations

import keyword
import re
from dataclasses import replace
from typing import Tuple

from .code_compose import PARTS
from .rewrite_core import Var, match
from .contract_budget import Budget
from .contract_ir import (ContractError, Goal, PlanNode, ProgramContract,
                          PROFILES, TypedProgramPlan, ValueType, canonical)

MANIFEST = {"version": "contract-laws-v1", "parts": dict(PARTS),
            "families": tuple(PARTS), "map": ("square", "abs", "multiply", "pluck", "upper", "lower", "strip", "length"),
            "aggregate": ("sum", "count", "mean", "min", "max"),
            "predicate": ("eq", "ne", "lt", "le", "gt", "ge", "even", "odd", "is_null", "not_null", "and", "or", "not")}
CONFIG_KEYS = {"filter":{"predicate"}, "map":{"subkind","field","value","alias"},
    "aggregate":{"subkind","field","empty","all_ties","key_alias","value_alias","order","alias"},
    "group":{"field","key_alias","value_alias","order"}, "sort":{"field","descending"},
    "diff":set(), "dedupe":{"field"}, "join":{"left_key","right_key","projection"},
    "not_exists":{"left_key","right_key"}, "ratio":{"numerator","denominator","zero","alias"}}
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,31}\Z")
JS_RESERVED = frozenset("break case catch class const continue debugger default delete do else export extends finally for function if import in instanceof let new return super switch this throw try typeof var void while with yield await enum implements interface package private protected public static null true false arguments eval".split())


def identifier(name: str, profile: str = "") -> bool:
    return bool(IDENTIFIER.fullmatch(name)) and not keyword.iskeyword(name) and (profile != "node_commonjs_sync_v1" or name not in JS_RESERVED)


def _fail(message: str, code: str = "TYPE_OR_BINDING_FAILURE") -> None:
    raise ContractError(code, "synthesis", message)


def _base(t: ValueType) -> ValueType:
    return t.item if t.kind == "Nullable" and t.item else t


def _field(item: ValueType, field: str) -> ValueType:
    if item.kind == "Record":
        if not field:
            _fail("record operation requires a bound field")
        return item.field(field)
    if field:
        _fail("field reference on a scalar item")
    return item


def _integer(t: ValueType, nullable: bool = False) -> ValueType:
    if (t.kind == "Nullable" and not nullable) or _base(t).kind != "Int":
        _fail("non-null integer refinement required")
    return _base(t)


def _range(low: int, high: int) -> ValueType:
    if max(abs(low), abs(high)) > 2147483647:
        _fail("intermediate integer domain exceeds registered profile", "DOMAIN_UNSUPPORTED")
    return ValueType("Int", low=low, high=high)


def _operand(value, symbols: dict) -> ValueType:
    if isinstance(value, dict):
        if set(value) != {"param"} or value["param"] not in symbols:
            _fail("unbound scalar parameter")
        return symbols[value["param"]]
    if type(value) is int:
        return ValueType("Int", low=value, high=value)
    if isinstance(value, str):
        return ValueType("Text", max_length=len(value))
    _fail("operand must be an explicit literal or bound parameter")


def check_predicate(p: dict, item: ValueType, symbols: dict, budget: Budget,
                    depth: int = 0, atoms: list | None = None) -> None:
    atoms = atoms if atoms is not None else [0]
    budget.charge("synthesis", location="predicate binding")
    if depth > 3 or not isinstance(p, dict) or p.get("op") not in MANIFEST["predicate"]:
        _fail("predicate outside registered domain")
    op = p["op"]
    allowed = {"op","args"} if op in ("and","or","not") else {"op","field"} if op in ("even","odd","is_null","not_null") else {"op","field","value"}
    if set(p)-allowed:
        _fail("uninterpreted predicate fields", "SYNTHESIS_UNSUPPORTED")
    if op in ("and", "or", "not"):
        args = p.get("args", [])
        if not isinstance(args, list) or len(args) != (1 if op == "not" else 2):
            _fail("logical predicate arity")
        for child in args:
            check_predicate(child, item, symbols, budget, depth + 1, atoms)
        return
    atoms[0] += 1
    if atoms[0] > 4:
        _fail("predicate has more than four atomic conditions")
    typ = _field(item, p.get("field", ""))
    if op in ("is_null", "not_null"):
        return
    if op in ("even", "odd"):
        _integer(typ, nullable=True)
        return
    other = _operand(p.get("value"), symbols)
    if _base(typ).kind != other.kind or other.kind not in ("Int", "Text"):
        _fail("predicate operand types disagree")
    if other.kind == "Text" and op not in ("eq", "ne"):
        _fail("text comparison supports only exact equality", "SYNTHESIS_UNSUPPORTED")


def _refine(item: ValueType, p: dict) -> ValueType:
    """Only a proved not-null atom (or conjunct) introduces a refinement."""
    if p.get("op") == "and":
        for child in p["args"]:
            item = _refine(item, child)
    elif p.get("op") == "not_null":
        field = p.get("field", "")
        if item.kind == "Record":
            item = replace(item, fields=tuple((name, _base(typ) if name == field else typ) for name, typ in item.fields))
        elif not field:
            item = _base(item)
    return item


def infer_goal(goal: Goal, types: Tuple[ValueType, ...], symbols: dict,
               profile: str, budget: Budget) -> ValueType:
    budget.charge("synthesis", location=goal.id + ":operator law")
    if goal.kind not in PARTS:
        _fail("unregistered operator family", "SYNTHESIS_UNSUPPORTED")
    if len(types) != (2 if goal.kind in ("join", "not_exists") else 1):
        _fail("operator input arity")
    if match(("container", Var("item")), ("container", types[0].item)) is None:
        _fail("structural binding failed")
    source, cfg, kind = types[0], goal.config, goal.kind
    if not isinstance(cfg,dict) or set(cfg)-CONFIG_KEYS[kind]:
        _fail("uninterpreted operator constraints", "SYNTHESIS_UNSUPPORTED")
    if source.kind not in ("Seq", "Relation", "Groups") or source.item is None:
        _fail("sequence/record relation input required")
    if source.kind == "Groups" and kind != "aggregate":
        _fail("Groups must be consumed by their aggregate")
    item, field = source.item, cfg.get("field", "")
    if kind == "filter":
        check_predicate(cfg.get("predicate"), item, symbols, budget)
        return replace(source, item=_refine(item, cfg["predicate"]))
    if kind == "map":
        subkind = cfg.get("subkind")
        if subkind not in MANIFEST["map"]:
            _fail("unregistered map subkind", "SYNTHESIS_UNSUPPORTED")
        value = _field(item, field)
        if subkind == "pluck":
            if profile == "sqlite_select_v1":
                alias=cfg.get("alias")
                if not isinstance(alias,str) or not identifier(alias):
                    _fail("SQL projection requires a named output alias")
                return replace(source,item=ValueType("Record",fields=((alias,value),)))
            return replace(source, item=value)
        if subkind in ("square", "abs", "multiply"):
            n = _integer(value)
            if n.low is None or n.high is None:
                _fail("arithmetic input range is unspecified", "DOMAIN_UNSPECIFIED")
            if subkind == "square":
                mapped = _range(0 if n.low <= 0 <= n.high else min(n.low*n.low, n.high*n.high), max(n.low*n.low, n.high*n.high))
            elif subkind == "abs":
                mapped = _range(0 if n.low <= 0 <= n.high else min(abs(n.low), abs(n.high)), max(abs(n.low), abs(n.high)))
            else:
                multiplier = _integer(_operand(cfg.get("value"), symbols))
                if multiplier.low is None or multiplier.high is None or multiplier.low < -10 or multiplier.high > 10:
                    _fail("multiply coefficient exceeds registered range", "DOMAIN_UNSUPPORTED")
                values = [a*b for a in (n.low, n.high) for b in (multiplier.low, multiplier.high)]
                mapped = _range(min(values), max(values))
        else:
            if value.kind != "Text" or value.max_length is None or value.max_length > 32:
                _fail("bounded ASCII Text required", "DOMAIN_UNSUPPORTED")
            mapped = ValueType("Int", low=0, high=value.max_length) if subkind == "length" else value
        return replace(source, item=replace(item, fields=tuple((name, mapped if name == field else typ) for name, typ in item.fields)) if item.kind == "Record" else mapped)
    if kind in ("sort", "dedupe", "group"):
        key = _field(item, field)
        if key.kind not in ("Int", "Text"):
            _fail("non-null scalar key required")
        if kind != "group":
            return source
        if item.kind != "Record":
            _fail("Group requires record input")
        ka, va = cfg.get("key_alias", "key"), cfg.get("value_alias", "value")
        if ka == va or not identifier(ka) or not identifier(va) or cfg.get("order", "first") not in ("first", "key"):
            _fail("invalid group aliases or order")
        return ValueType("Groups", item=item, fields=((ka, key), (va, ValueType("Int"))), max_items=source.max_items)
    if kind == "diff":
        n = _integer(item)
        return replace(source, item=_range(n.low-n.high, n.high-n.low))
    if kind == "aggregate":
        subkind = cfg.get("subkind")
        if subkind not in MANIFEST["aggregate"]:
            _fail("unregistered aggregate subkind", "SYNTHESIS_UNSUPPORTED")
        if subkind == "count":
            result = ValueType("Int", low=0, high=source.max_items)
        else:
            n = _integer(_field(item, field))
            if n.low is None or n.high is None or source.max_items is None:
                _fail("aggregate range unspecified", "DOMAIN_UNSPECIFIED")
            result = _range(min(0, n.low*source.max_items), max(0, n.high*source.max_items)) if subkind == "sum" else ValueType("Float64") if subkind == "mean" else n
        empty = cfg.get("empty", 0 if subkind in ("sum", "count") else None)
        if cfg.get("all_ties"):
            if subkind not in ("min","max") or source.kind=="Groups" or "empty" in cfg and cfg["empty"]!=[]:
                _fail("unsupported all-ties aggregate or non-list empty policy")
            return source
        if empty is not None and (type(empty) not in (int, float) or abs(empty) > 1000 or (subkind == "mean" and (type(empty) is not float or empty != 0.0)) or (subkind != "mean" and type(empty) is not int)):
            _fail("empty aggregate sentinel outside registered contract")
        if result.kind=="Int" and type(empty) is int:
            result=replace(result,low=min(result.low,empty) if result.low is not None else None,
                           high=max(result.high,empty) if result.high is not None else None)
        if source.kind == "Groups":
            ka, kt = source.fields[0]
            va = source.fields[1][0]
            if cfg.get("key_alias", ka) != ka or cfg.get("value_alias", va) != va:
                _fail("group result aliases disagree")
            # Groups only exist when at least one original row has their key.
            rt = result
            return ValueType("Relation" if profile == "sqlite_select_v1" else "Seq", item=ValueType("Record", fields=((ka, kt), (va, rt))), max_items=source.max_items)
        rt=ValueType("Nullable", item=result) if empty is None else result
        if profile=="sqlite_select_v1":
            alias=cfg.get("alias")
            if not isinstance(alias,str) or not identifier(alias):
                _fail("SQL aggregate requires a named output column")
            return ValueType("Relation",item=ValueType("Record",fields=((alias,rt),)),max_items=1)
        return rt
    if kind in ("join", "not_exists"):
        right = types[1]
        if item.kind != "Record" or right.kind not in ("Seq", "Relation") or right.item is None or right.item.kind != "Record":
            _fail("join requires two record collections")
        left_key = item.field(cfg.get("left_key", ""))
        right_key = right.item.field(cfg.get("right_key", ""))
        if left_key.kind not in ("Int", "Text") or left_key.kind != right_key.kind:
            _fail("join key types disagree or nullable")
        if kind == "not_exists":
            return source
        fields = []
        for projection in cfg.get("projection", []):
            budget.charge("synthesis", location="join projection")
            if projection.get("side") not in ("left", "right") or not identifier(projection.get("alias", "")):
                _fail("invalid projection")
            typ = (item if projection["side"] == "left" else right.item).field(projection.get("field", ""))
            fields.append((projection["alias"], typ))
        if not fields or len(fields) > 8 or len({n for n,t in fields}) != len(fields):
            _fail("explicit, nonconflicting join projection required")
        return replace(source, item=ValueType("Record", fields=tuple(fields)), max_items=(source.max_items or 0)*(right.max_items or 0))
    if kind == "ratio":
        _integer(item.field(cfg.get("numerator", "")))
        _integer(item.field(cfg.get("denominator", "")))
        if cfg.get("zero") is not None:
            _fail("Ratio zero denominator is explicitly Null")
        rt=ValueType("Nullable", item=ValueType("Float64"))
        if profile=="sqlite_select_v1":
            alias=cfg.get("alias")
            if not isinstance(alias,str) or not identifier(alias):
                _fail("SQL ratio requires a named output alias")
            return replace(source,item=ValueType("Record",fields=((alias,rt),)))
        return replace(source, item=rt)
    _fail("operator unavailable", "SYNTHESIS_UNSUPPORTED")


def shape_equal(a: ValueType, b: ValueType) -> bool:
    """Output bounds may be less precise; observable kind/schema may not."""
    return a.kind == b.kind and ((a.item is None and b.item is None) or (a.item is not None and b.item is not None and shape_equal(a.item,b.item))) and tuple(n for n,t in a.fields) == tuple(n for n,t in b.fields) and all(shape_equal(x,y) for (_,x),(_,y) in zip(a.fields,b.fields))


def refines(actual: ValueType, requested: ValueType) -> bool:
    if not shape_equal(actual,requested): return False
    if requested.low is not None and (actual.low is None or actual.low<requested.low): return False
    if requested.high is not None and (actual.high is None or actual.high>requested.high): return False
    if requested.max_items is not None and (actual.max_items is None or actual.max_items>requested.max_items): return False
    if requested.max_length is not None and (actual.max_length is None or actual.max_length>requested.max_length): return False
    if actual.item and not refines(actual.item,requested.item): return False
    return all(refines(x,y) for (_,x),(_,y) in zip(actual.fields,requested.fields))


def boundary_type(typ: ValueType,boundaries: tuple) -> ValueType:
    def merge(t,value):
        if t.kind=="Nullable": return t if value is None else replace(t,item=merge(t.item,value))
        if t.kind=="Int" and type(value) is int and -1000<=value<=1000:
            return replace(t,low=min(t.low,value) if t.low is not None else None,high=max(t.high,value) if t.high is not None else None)
        if t.kind=="Float64" and type(value) is float and value==0.0: return t
        if t.kind=="Record" and type(value) is dict and set(value)=={n for n,child in t.fields}:
            return replace(t,fields=tuple((n,merge(child,value[n])) for n,child in t.fields))
        _fail("entry sentinel does not preserve its requested type/schema","BACKEND_UNSUPPORTED")
    for boundary in boundaries:
        if boundary.trigger!="input_empty":
            _fail("unregistered boundary trigger")
        value=boundary.value
        if typ.kind=="Int" and type(value) is int and -1000<=value<=1000:
            typ=replace(typ,low=min(typ.low,value) if typ.low is not None else None,
                        high=max(typ.high,value) if typ.high is not None else None)
        elif typ.kind in ("Seq","Relation") and value==[]:
            pass
        elif typ.kind=="Relation" and type(value) is list and len(value)==1 and typ.item and typ.item.kind=="Record":
            typ=replace(typ,item=merge(typ.item,value[0]),max_items=max(typ.max_items,1) if typ.max_items is not None else None)
        elif typ.kind=="Nullable" and value is None:
            pass
        else:
            _fail("input-empty return union outside current implementation","BACKEND_UNSUPPORTED")
    return typ


def validate_input_type(typ: ValueType, budget: Budget, *, inside: bool = False) -> None:
    budget.charge("synthesis", location="input domain")
    if typ.kind == "Int":
        if typ.low is None or typ.high is None or not -1000 <= typ.low <= typ.high <= 1000:
            _fail("explicit integer domain within -1000..1000 required", "DOMAIN_UNSUPPORTED")
    elif typ.kind == "Text":
        if typ.max_length is None or not 0 <= typ.max_length <= 32:
            _fail("explicit bounded ASCII Text domain required", "DOMAIN_UNSUPPORTED")
    elif typ.kind == "Nullable" and typ.item and typ.item.kind == "Int":
        validate_input_type(typ.item, budget, inside=True)
    elif typ.kind in ("Seq", "Relation") and not inside and typ.item:
        if typ.max_items is None or not 0 <= typ.max_items <= 32:
            _fail("explicit collection size bound within 0..32 required", "DOMAIN_UNSUPPORTED")
        validate_input_type(typ.item, budget, inside=True)
    elif typ.kind == "Record" and inside:
        if not 1 <= len(typ.fields) <= 6 or len({n for n,t in typ.fields}) != len(typ.fields):
            _fail("flat, unique record schema required")
        for name, child in typ.fields:
            if not identifier(name) or child.kind in ("Record", "Seq", "Relation", "Groups"):
                _fail("invalid field/nested schema", "DOMAIN_UNSUPPORTED")
            validate_input_type(child, budget, inside=True)
    else:
        _fail("input type outside registered profile", "DOMAIN_UNSUPPORTED")


def synthesize(contract: ProgramContract, budget: Budget | None = None) -> TypedProgramPlan:
    budget = budget or Budget()
    if contract.profile not in PROFILES:
        _fail("unregistered backend", "BACKEND_UNSUPPORTED")
    if contract.effect != "pure_input_unchanged":
        _fail("effect outside pure profile", "SYNTHESIS_UNSUPPORTED")
    names = [x.name for x in contract.inputs]
    if len(names) != len(set(names)) or any(not identifier(n,contract.profile) for n in names):
        _fail("input symbols are invalid or collide")
    if len([x for x in contract.inputs if x.type.kind in ("Seq", "Relation")]) not in (1,2) or len([x for x in contract.inputs if x.type.kind not in ("Seq", "Relation")]) > 2:
        _fail("input count outside profile")
    if tuple(names) != contract.interface.parameters or tuple(x.name for x in contract.inputs if x.kind == "keyword_only") != contract.interface.keyword_only:
        _fail("requested interface and input bindings disagree")
    if not identifier(contract.interface.name, contract.profile) and contract.profile in PROFILES[:2]:
        _fail("invalid requested function name")
    symbols = {x.name:x.type for x in contract.inputs}
    for x in contract.inputs:
        validate_input_type(x.type,budget)
    budget.capacity("symbols", len(symbols))
    if not contract.goals:
        _fail("no supported desired relation", "CONTRACT_INCOMPLETE")
    goal_ids = {g.id for g in contract.goals}
    outputs = {g.output for g in contract.goals}
    if len(goal_ids) != len(contract.goals) or len(outputs) != len(contract.goals) or outputs.intersection(symbols):
        _fail("goal identity or output binding collision")
    if any(not identifier(g.output) for g in contract.goals):
        _fail("invalid intermediate symbol")
    requirements = set(contract.requirement_ids)
    if len(requirements) != len(contract.requirement_ids):
        _fail("duplicate requirement identity")
    todo, nodes, depths, reached = list(contract.goals), [], {x.name:0 for x in contract.inputs}, set()
    budget.capacity("live_states", 1)
    while todo:
        ready = []
        for goal in todo:
            budget.charge("synthesis", location=goal.id+":dependency binding")
            if all(name in symbols for name in goal.inputs):
                ready.append(goal)
        if not ready:
            _fail("dependency cycle or unbound input symbol")
        for goal in sorted(ready, key=lambda x:x.output):
            if not set(goal.requirement_ids).issubset(requirements) or not goal.requirement_ids:
                _fail("unbound requirement proof")
            types = tuple(symbols[name] for name in goal.inputs)
            result = infer_goal(goal,types,symbols,contract.profile,budget)
            depth = max(depths[name] for name in goal.inputs)+1
            budget.capacity("depth",depth,goal.id)
            budget.charge("nodes", location=goal.id)
            budget.charge("proof", len(goal.requirement_ids)+1, goal.id)
            budget.capacity("symbols",len(symbols)+1,goal.id)
            nodes.append(PlanNode(goal.id,goal.kind,goal.inputs,goal.output,types,result,goal.config_json,goal.requirement_ids,"contract-laws-v1:"+goal.kind,PARTS[goal.kind]))
            symbols[goal.output], depths[goal.output] = result, depth
            reached.update(goal.requirement_ids)
            todo.remove(goal)
    returned_type=boundary_type(symbols.get(contract.return_symbol,ValueType("Unknown")),contract.boundaries)
    if contract.return_symbol not in outputs or not refines(returned_type,contract.return_type):
        _fail("requested return type/shape is not derived")
    ancestors, frontier = set(), [contract.return_symbol]
    by_output = {node.output:node for node in nodes}
    while frontier:
        symbol = frontier.pop()
        budget.charge("synthesis",location="return dependency closure")
        if symbol in by_output and symbol not in ancestors:
            ancestors.add(symbol)
            frontier.extend(by_output[symbol].inputs)
    if ancestors != outputs:
        _fail("a required computation is absent from returned dependencies")
    # Nonoperator requirements are checked by source/interface/domain/effect gates.
    reached.update(requirements)
    budget.charge("plans")
    return TypedProgramPlan(contract.hash,contract.profile,tuple(nodes),contract.return_symbol,
                            returned_type,tuple(sorted(reached)),contract.boundaries)
