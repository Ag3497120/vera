"""Hand-authored lowering oracles; these are not the independent 80 fixtures."""
from dataclasses import replace
import copy
import inspect
import json
import os
import sqlite3
import subprocess
import tempfile
import unittest

from verantyx.contract_budget import Budget
from verantyx.contract_ir import Boundary, ContractError, Goal, InputBinding, Interface, PlanNode, ProgramContract, TypedProgramPlan, ValueType
from verantyx.contract_lower import lower

I = ValueType("Int", low=-2147483647, high=2147483647)
T = ValueType("Text", max_length=32)
F = ValueType("Float64")
NI = ValueType("Nullable", item=I)


def seq(item=I):
    return ValueType("Seq", item=item, max_items=32)


def record(**fields):
    return ValueType("Record", fields=tuple(fields.items()))


def relation(**fields):
    return ValueType("Relation", item=record(**fields), max_items=32)


def fixture(profile, bindings, steps, *, interface=None, boundaries=()):
    """steps are explicit dependency/typed oracle descriptions, not inferred."""
    if interface is None:
        interface = Interface("requested", tuple(b.name for b in bindings))
    types = {b.name: b.type for b in bindings}
    goals, nodes = [], []
    for n, (kind, inputs, output, output_type, cfg) in enumerate(steps):
        config = json.dumps(cfg)
        goals.append(Goal(str(n), kind, tuple(inputs), output, config, (str(n),)))
        nodes.append(PlanNode(str(n), kind, tuple(inputs), output, tuple(types[i] for i in inputs), output_type, config, (str(n),), "hand-law", "registered-part"))
        types[output] = output_type
    returned = steps[-1][2] if steps else bindings[0].name
    ids = tuple(str(n) for n in range(len(steps)))
    c = ProgramContract("source", "ledger", profile, interface, tuple(bindings), tuple(goals), returned, types[returned], ids, tuple(boundaries), "gold_contract")
    p = TypedProgramPlan(c.hash, profile, tuple(nodes), returned, c.return_type, ids, tuple(boundaries))
    return c, p


def python_call(c, p, args, kwargs=None):
    artifact = lower(c, p, Budget())
    scope = {}
    exec(compile(artifact.source, "generated_hand_fixture", "exec"), scope)
    fn = scope[c.interface.name]
    snapshot = copy.deepcopy((args, kwargs))
    result = fn(*args, **(kwargs or {}))
    assert (args, kwargs) == snapshot, "input mutation"
    return result, fn


def js_call(c, p, args):
    artifact = lower(c, p, Budget())
    payload = json.dumps(args)
    script = artifact.source + "\nconst supplied = " + payload + ";\nconst before = JSON.stringify(supplied);\nconst result = module.exports[" + json.dumps(c.interface.name) + "](...supplied);\nif (JSON.stringify(supplied) !== before) throw Error('mutation');\nconsole.log(JSON.stringify(result));\n"
    # This generous diagnostic timeout isolates emitter meaning from runtime
    # startup under concurrent load. It is not the registered 200ms runner.
    completed = subprocess.run(["/opt/homebrew/bin/node", "--jitless", "--no-warnings", "-e", script], capture_output=True, text=True, timeout=10)
    if completed.returncode or completed.stderr:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


def js_batch(tasks):
    """Fresh VM per hand oracle, one diagnostic Node launch to limit startup."""
    prepared = []
    for c, p, args in tasks:
        artifact = lower(c, p, Budget())
        prepared.append({"source": artifact.source, "name": c.interface.name, "args": args})
    script = "const vm = require('node:vm'); const tasks = " + json.dumps(prepared) + ";\nconst outputs = [];\nfor (const t of tasks) { const ctx = vm.createContext({module:{exports:{}}}); vm.runInContext(t.source, ctx, {timeout:1000}); const before = JSON.stringify(t.args); outputs.push(ctx.module.exports[t.name](...t.args)); if (JSON.stringify(t.args) !== before) throw Error('mutation'); }\nconsole.log(JSON.stringify(outputs));"
    completed = subprocess.run(["/opt/homebrew/bin/node", "--jitless", "--no-warnings", "-e", script], capture_output=True, text=True, timeout=10)
    if completed.returncode or completed.stderr:
        raise AssertionError(completed.stderr)
    return json.loads(completed.stdout)


def sql_call(c, p, tables):
    artifact = lower(c, p, Budget())
    db = sqlite3.connect(":memory:")
    try:
        for b in c.inputs:
            fields = b.type.item.fields
            schema = ",".join('"' + name + '" ' + ("TEXT" if typ.kind == "Text" else "INTEGER") for name, typ in fields)
            db.execute('CREATE TABLE "' + b.name + '" (' + schema + ")")
            for row in tables[b.name]:
                db.execute('INSERT INTO "' + b.name + '" VALUES (' + ",".join("?" for _ in fields) + ")", [row[name] for name, _ in fields])
        db.execute("PRAGMA query_only=ON")
        cursor = db.execute(artifact.source)
        return tuple(d[0] for d in cursor.description), cursor.fetchall()
    finally:
        db.close()


def sh_call(c, p, lines, argv=()):
    artifact = lower(c, p, Budget())
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "artifact.sh")
        with open(path, "w") as handle:
            handle.write(artifact.source)
        stdin = "".join(str(value) + "\n" for value in lines)
        proc = subprocess.run(["/bin/sh", path, *map(str, argv)], input=stdin, capture_output=True, text=True, timeout=2)
        if proc.returncode or proc.stderr:
            raise AssertionError(proc.stderr)
        return proc.stdout


class ContractLowerTests(unittest.TestCase):
    def test_python_interface_parameter_binding_and_entry_empty(self):
        inputs = [InputBinding("source_values", seq()), InputBinding("cutoff", I, "keyword_only")]
        interface = Interface("selected_total", ("source_values", "cutoff"), ("cutoff",))
        boundary = Boundary("input_empty", "source_values", "-7", "empty")
        steps = [("filter", ["source_values"], "kept", seq(), {"predicate": {"op": "gt", "value": {"param": "cutoff"}}}),
                 ("aggregate", ["kept"], "total", I, {"subkind": "sum"})]
        c, p = fixture("python_pure_v1", inputs, steps, interface=interface, boundaries=[boundary])
        value, fn = python_call(c, p, [[-2, 0, 4, 8]], {"cutoff": 4})
        self.assertEqual(value, 8)
        self.assertEqual(str(inspect.signature(fn)), "(source_values, *, cutoff)")
        self.assertEqual(python_call(c, p, [[]], {"cutoff": 4})[0], -7)
        self.assertEqual(python_call(c, p, [[1]], {"cutoff": 4})[0], 0)

    def test_python_noncommutative_dependency_and_shuffled_node_order(self):
        inputs = [InputBinding("numbers", seq())]
        steps = [("map", ["numbers"], "squares", seq(), {"subkind": "square"}),
                 ("filter", ["squares"], "kept", seq(), {"predicate": {"op": "gt", "value": 3}})]
        c, p = fixture("python_pure_v1", inputs, steps)
        self.assertEqual(python_call(c, replace(p, nodes=tuple(reversed(p.nodes))), [[-2, -1, 2]])[0], [4, 4])
        opposite = [("filter", ["numbers"], "kept", seq(), {"predicate": {"op": "gt", "value": 3}}),
                    ("map", ["kept"], "squares", seq(), {"subkind": "square"})]
        c, p = fixture("python_pure_v1", inputs, opposite)
        self.assertEqual(python_call(c, p, [[-2, -1, 2]])[0], [])

    def test_three_valued_not_and_or_keep_only_true(self):
        typ = seq(record(value=NI, alternate=I))
        pred = {"op": "or", "args": [{"op": "not", "args": [{"op": "gt", "field": "value", "value": 0}]}, {"op": "eq", "field": "alternate", "value": 9}]}
        steps = [("filter", ["rows"], "out", typ, {"predicate": pred})]
        rows = [{"value": None, "alternate": 0}, {"value": None, "alternate": 9}, {"value": 0, "alternate": 1}, {"value": 3, "alternate": 1}]
        expected = [rows[1], rows[2]]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, [InputBinding("rows", typ)], steps)
            value = python_call(c, p, [rows])[0] if profile.startswith("python") else js_call(c, p, [rows])
            self.assertEqual(value, expected)

    def test_record_map_stable_descending_and_first_dedupe(self):
        typ = seq(record(key=I, amount=I))
        steps = [("map", ["rows"], "updated", typ, {"subkind": "multiply", "field": "amount", "value": -2}),
                 ("sort", ["updated"], "sorted", typ, {"field": "key", "descending": True}),
                 ("dedupe", ["sorted"], "out", typ, {"field": "key"})]
        rows = [{"key": 2, "amount": 1}, {"key": 1, "amount": 7}, {"key": 2, "amount": 99}]
        expected = [{"key": 2, "amount": -2}, {"key": 1, "amount": -14}]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, [InputBinding("rows", typ)], steps)
            self.assertEqual(python_call(c, p, [rows])[0] if profile.startswith("python") else js_call(c, p, [rows]), expected)

    def test_group_typed_key_aggregate_and_post_filter(self):
        typ = seq(record(category=T, amount=I))
        groups = ValueType("Groups", item=typ.item, fields=(("label", T), ("total", I)), max_items=32)
        outtype = seq(record(label=T, total=I))
        steps = [("group", ["rows"], "groups", groups, {"field": "category", "key_alias": "label", "value_alias": "total", "order": "first"}),
                 ("aggregate", ["groups"], "aggregated", outtype, {"subkind": "sum", "field": "amount", "key_alias": "label", "value_alias": "total", "order": "first"}),
                 ("filter", ["aggregated"], "out", outtype, {"predicate": {"op": "gt", "field": "total", "value": 5}})]
        rows = [{"category": "z", "amount": 4}, {"category": "a", "amount": 8}, {"category": "z", "amount": 3}]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, [InputBinding("rows", typ)], steps)
            self.assertEqual(python_call(c, p, [rows])[0] if profile.startswith("python") else js_call(c, p, [rows]), [{"label": "z", "total": 7}, {"label": "a", "total": 8}])

    def test_join_projection_multiplicity_and_antijoin(self):
        left, right = seq(record(code=I, left_value=I)), seq(record(reference=I, right_value=I))
        bindings = [InputBinding("left_rows", left), InputBinding("right_rows", right)]
        cfg = {"left_key": "code", "right_key": "reference", "projection": [{"side": "right", "field": "right_value", "alias": "r"}, {"side": "left", "field": "left_value", "alias": "l"}]}
        args = [[{"code": 2, "left_value": 4}, {"code": 2, "left_value": 5}, {"code": 1, "left_value": 99}], [{"reference": 2, "right_value": 9}, {"reference": 2, "right_value": 8}]]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, bindings, [("join", ["left_rows", "right_rows"], "out", seq(record(r=I, l=I)), cfg)])
            self.assertEqual(python_call(c, p, args)[0] if profile.startswith("python") else js_call(c, p, args), [{"r": 9, "l": 4}, {"r": 8, "l": 4}, {"r": 9, "l": 5}, {"r": 8, "l": 5}])
            c, p = fixture(profile, bindings, [("not_exists", ["left_rows", "right_rows"], "out", left, {"left_key": "code", "right_key": "reference"})])
            self.assertEqual(python_call(c, p, args)[0] if profile.startswith("python") else js_call(c, p, args), [args[0][2]])

    def test_ratio_float_zero_and_extrema_ties(self):
        typ = seq(record(top=I, bottom=I))
        steps = [("ratio", ["rows"], "out", seq(ValueType("Nullable", item=F)), {"numerator": "top", "denominator": "bottom", "zero": None})]
        rows = [{"top": 1, "bottom": 3}, {"top": 7, "bottom": 0}, {"top": 0, "bottom": -3}]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, [InputBinding("rows", typ)], steps)
            self.assertEqual(python_call(c, p, [rows])[0] if profile.startswith("python") else js_call(c, p, [rows]), [1 / 3, None, 0.0])
        c, p = fixture("python_pure_v1", [InputBinding("rows", typ)], [("aggregate", ["rows"], "out", typ, {"subkind": "max", "field": "top", "all_ties": True})])
        self.assertEqual(python_call(c, p, [rows + [rows[1]]])[0], [rows[1], rows[1]])

    def test_sql_map_dedupe_and_sort_uses_ordinal_not_rowid(self):
        typ = relation(value=I, note=T, ordinal=I)
        result = relation(total=I)
        steps = [("map", ["data"], "scaled", typ, {"subkind": "multiply", "field": "value", "value": 2}),
                 ("dedupe", ["scaled"], "first", typ, {"field": "note"}),
                 ("sort", ["first"], "sorted", typ, {"field": "value", "descending": True}),
                 ("map", ["sorted"], "projected", relation(selected=I), {"subkind": "pluck", "field": "value", "alias": "selected"})]
        c, p = fixture("sqlite_select_v1", [InputBinding("data", typ, ordinal="ordinal")], steps, interface=Interface("query", (), columns=("selected",)))
        rows = [{"value": 9, "note": "a", "ordinal": 3}, {"value": 2, "note": "a", "ordinal": 1}, {"value": 4, "note": "b", "ordinal": 2}]
        self.assertEqual(sql_call(c, p, {"data": rows}), (("selected",), [(8,), (4,)]))

    def test_sql_nullable_logic_group_then_scope_filter(self):
        typ = relation(value=NI, category=T, ordinal=I)
        nonnull = relation(value=I, category=T, ordinal=I)
        groups = ValueType("Groups", item=nonnull.item, fields=(("label", T), ("total", I)))
        out = relation(label=T, total=I)
        steps = [("filter", ["data"], "nonnull", nonnull, {"predicate": {"op": "not_null", "field": "value"}}),
                 ("group", ["nonnull"], "groups", groups, {"field": "category", "key_alias": "label", "value_alias": "total", "order": "first"}),
                 ("aggregate", ["groups"], "totals", out, {"subkind": "sum", "field": "value", "key_alias": "label", "value_alias": "total"}),
                 ("filter", ["totals"], "out", out, {"predicate": {"op": "gt", "field": "total", "value": 5}})]
        c, p = fixture("sqlite_select_v1", [InputBinding("data", typ, ordinal="ordinal")], steps, interface=Interface("query", (), columns=("label", "total")))
        rows = [{"value": None, "category": "x", "ordinal": 1}, {"value": 3, "category": "z", "ordinal": 2}, {"value": 8, "category": "a", "ordinal": 3}, {"value": 4, "category": "z", "ordinal": 4}]
        self.assertEqual(sql_call(c, p, {"data": rows}), (("label", "total"), [("z", 7), ("a", 8)]))

    def test_sql_join_different_keys_and_ratio_real_shape(self):
        left, right = relation(key=I, amount=I, ordinal=I), relation(reference=I, divisor=I, ordinal=I)
        joined = relation(top=I, bottom=I)
        out = relation(result=ValueType("Nullable", item=F))
        projection = [{"side": "left", "field": "amount", "alias": "top"}, {"side": "right", "field": "divisor", "alias": "bottom"}]
        steps = [("join", ["l", "r"], "joined", joined, {"left_key": "key", "right_key": "reference", "projection": projection}),
                 ("ratio", ["joined"], "out", out, {"numerator": "top", "denominator": "bottom", "zero": None})]
        c, p = fixture("sqlite_select_v1", [InputBinding("l", left, ordinal="ordinal"), InputBinding("r", right, ordinal="ordinal")], steps, interface=Interface("query", (), columns=("result",)))
        tables = {"l": [{"key": 1, "amount": 1, "ordinal": 1}], "r": [{"reference": 1, "divisor": 3, "ordinal": 2}, {"reference": 1, "divisor": 0, "ordinal": 1}]}
        self.assertEqual(sql_call(c, p, tables), (("result",), [(None,), (1 / 3,)]))

    def test_sql_empty_mean_and_entry_override(self):
        typ, out = relation(value=I, ordinal=I), relation(average=ValueType("Nullable", item=F))
        boundary = Boundary("input_empty", "data", '[{"average":0.0}]', "empty")
        steps = [("filter", ["data"], "kept", typ, {"predicate": {"op": "gt", "field": "value", "value": 5}}),
                 ("aggregate", ["kept"], "out", out, {"subkind": "mean", "field": "value"})]
        c, p = fixture("sqlite_select_v1", [InputBinding("data", typ, ordinal="ordinal")], steps, interface=Interface("query", (), columns=("average",)), boundaries=[boundary])
        self.assertEqual(sql_call(c, p, {"data": []}), (("average",), [(0.0,)]))
        self.assertEqual(sql_call(c, p, {"data": [{"value": 2, "ordinal": 1}]}), (("average",), [(None,)]))
        self.assertEqual(sql_call(c, p, {"data": [{"value": 8, "ordinal": 2}, {"value": 6, "ordinal": 1}]}), (("average",), [(7.0,)]))

    def test_posix_argv_role_binding_and_noncommutative_pipeline(self):
        bindings = [InputBinding("stream", seq()), InputBinding("limit", I), InputBinding("factor", I)]
        steps = [("map", ["stream"], "scaled", seq(), {"subkind": "multiply", "value": {"param": "factor"}}),
                 ("filter", ["scaled"], "kept", seq(), {"predicate": {"op": "gt", "value": {"param": "limit"}}}),
                 ("dedupe", ["kept"], "unique", seq(), {}),
                 ("sort", ["unique"], "ordered", seq(), {"descending": True}),
                 ("diff", ["ordered"], "out", seq(), {})]
        c, p = fixture("posix_numeric_stream_v1", bindings, steps, interface=Interface("shell", (), argv=("limit", "factor")))
        self.assertEqual(sh_call(c, p, [2, -3, 5, 2, 0], [3, 2]), "-6\n")
        self.assertEqual(sh_call(c, p, [], [3, 2]), "")
        self.assertEqual(sh_call(c, p, [0], [-1, -2]), "")

    def test_posix_mean_boundary_empty_and_zero_canonical(self):
        c, p = fixture("posix_numeric_stream_v1", [InputBinding("stream", seq())], [("aggregate", ["stream"], "out", ValueType("Nullable", item=F), {"subkind": "mean"})], interface=Interface("shell", ()))
        self.assertEqual(sh_call(c, p, []), "null\n")
        self.assertEqual(float(sh_call(c, p, [0, 0, 1])), 1 / 3)
        c, p = fixture("posix_numeric_stream_v1", [InputBinding("stream", seq())], [("map", ["stream"], "out", seq(), {"subkind": "multiply", "value": -2})], interface=Interface("shell", ()))
        self.assertEqual(sh_call(c, p, [0, 1, -1]), "0\n-2\n2\n")

    def test_typed_failure_identity_cycle_wrong_types_and_budget(self):
        c, p = fixture("python_pure_v1", [InputBinding("numbers", seq())], [("map", ["numbers"], "out", seq(), {"subkind": "abs"})])
        for broken in (replace(p, contract_hash="forged"), replace(p, return_type=I), replace(p, discharged=()), replace(p, nodes=(replace(p.nodes[0], inputs=("absent",)),)), replace(p, nodes=(replace(p.nodes[0], input_types=(I,)),))):
            with self.assertRaises(ContractError) as caught:
                lower(c, broken, Budget())
            self.assertEqual(caught.exception.code, "TYPE_OR_BINDING_FAILURE")
        budget = Budget(limits={"lowering": 1})
        with self.assertRaises(ContractError):
            lower(c, p, budget)
        self.assertEqual(budget.used["lowering"], 1)
        with self.assertRaises(ContractError):
            lower(c, p, budget)
        self.assertEqual(budget.used["lowering"], 1)

    def test_requested_function_names_can_shadow_builtins(self):
        steps = [("map", ["values"], "magnitudes", seq(), {"subkind": "abs"}),
                 ("aggregate", ["magnitudes"], "out", I, {"subkind": "sum"})]
        c, p = fixture("python_pure_v1", [InputBinding("values", seq())], steps, interface=Interface("sum", ("values",)))
        self.assertEqual(python_call(c, p, [[-2, 3]])[0], 5)
        c, p = fixture("node_commonjs_sync_v1", [InputBinding("values", seq())], steps, interface=Interface("Math", ("values",)))
        self.assertEqual(js_call(c, p, [[-2, 3]]), 5)

    def test_text_subkinds_ascii_space_and_literal_escaping(self):
        cases = [("upper", ["aB", " Z "], ["AB", " Z "], seq(T)),
                 ("lower", ["aB", " Z "], ["ab", " z "], seq(T)),
                 ("strip", ["  a  b  ", " "], ["a  b", ""], seq(T)),
                 ("length", ["  a  b  ", ""], [8, 0], seq(I))]
        for subkind, values, expected, output_type in cases:
            c, p = fixture("python_pure_v1", [InputBinding("texts", seq(T))], [("map", ["texts"], "out", output_type, {"subkind": subkind})])
            self.assertEqual(python_call(c, p, [values])[0], expected)
        literal = "x';alert(1);//"
        steps = [("filter", ["texts"], "out", seq(T), {"predicate": {"op": "eq", "value": literal}})]
        for profile in ("python_pure_v1", "node_commonjs_sync_v1"):
            c, p = fixture(profile, [InputBinding("texts", seq(T))], steps)
            self.assertEqual(python_call(c, p, [[literal, "x"]])[0] if profile.startswith("python") else js_call(c, p, [[literal, "x"]]), [literal])

    def test_sql_internal_names_do_not_capture_input_names(self):
        typ = relation(value=I, ordinal=I, _vera_orderr=I)
        steps = [("dedupe", ["_vera_cte0"], "out", typ, {"field": "value"})]
        interface = Interface("query", (), columns=("value", "ordinal", "_vera_orderr"))
        c, p = fixture("sqlite_select_v1", [InputBinding("_vera_cte0", typ, ordinal="ordinal")], steps, interface=interface)
        rows = [{"value": 2, "ordinal": 2, "_vera_orderr": 999}, {"value": 2, "ordinal": 1, "_vera_orderr": 555}]
        self.assertEqual(sql_call(c, p, {"_vera_cte0": rows}), (("value", "ordinal", "_vera_orderr"), [(2, 1, 555)]))

    def test_closed_configs_and_nonnull_arithmetic_are_required(self):
        for cfg in ({"subkind": "abs", "code": "dangerous"}, {"subkind": "multiply", "value": True}):
            c, p = fixture("python_pure_v1", [InputBinding("values", seq())], [("map", ["values"], "out", seq(), cfg)])
            with self.assertRaises(ContractError):
                lower(c, p, Budget())
        c, p = fixture("python_pure_v1", [InputBinding("values", seq(NI))], [("map", ["values"], "out", seq(), {"subkind": "abs"})])
        with self.assertRaises(ContractError) as caught:
            lower(c, p, Budget())
        self.assertEqual(caught.exception.code, "TYPE_OR_BINDING_FAILURE")

    def test_all_global_aggregate_subkinds_empty_and_float_type(self):
        examples = [("sum", [-3, 0, 7], 4, I, {}), ("count", [-3, 0, 7], 3, I, {}),
                    ("mean", [0, 0, 1], 1 / 3, ValueType("Nullable", item=F), {}),
                    ("mean", [], 0.0, F, {"empty": 0.0}),
                    ("min", [-3, 0, 7], -3, ValueType("Nullable", item=I), {}),
                    ("max", [-3, 0, 7], 7, ValueType("Nullable", item=I), {}),
                    ("min", [], -99, I, {"empty": -99}),
                    ("max", [], None, ValueType("Nullable", item=I), {})]
        tasks, expected = [], []
        for subkind, values, answer, output_type, extra in examples:
            cfg = {"subkind": subkind, **extra}
            steps = [("aggregate", ["numbers"], "out", output_type, cfg)]
            c, p = fixture("python_pure_v1", [InputBinding("numbers", seq())], steps)
            actual = python_call(c, p, [values])[0]
            self.assertEqual(actual, answer)
            self.assertIs(type(actual), type(answer))
            c, p = fixture("node_commonjs_sync_v1", [InputBinding("numbers", seq())], steps)
            tasks.append((c, p, [values]))
            expected.append(answer)
        self.assertEqual(js_batch(tasks), expected)

    def test_js_text_diff_all_ties_and_group_mean_subkinds(self):
        tasks, expected = [], []
        for subkind, result, output in [("upper", ["AB", " Z "], seq(T)), ("lower", ["ab", " z "], seq(T)), ("strip", ["aB", "Z"], seq(T)), ("length", [2, 3], seq(I))]:
            c, p = fixture("node_commonjs_sync_v1", [InputBinding("texts", seq(T))], [("map", ["texts"], "out", output, {"subkind": subkind})])
            tasks.append((c, p, [["aB", " Z "]]))
            expected.append(result)
        c, p = fixture("node_commonjs_sync_v1", [InputBinding("numbers", seq())], [("diff", ["numbers"], "out", seq(), {})])
        tasks.append((c, p, [[-2, 4, 4, -3]])); expected.append([6, 0, -7])
        c, p = fixture("node_commonjs_sync_v1", [InputBinding("numbers", seq())], [("aggregate", ["numbers"], "out", seq(), {"subkind": "min", "all_ties": True})])
        tasks.append((c, p, [[2, -1, -1, 0]])); expected.append([-1, -1])
        typ = seq(record(key=T, value=I))
        groups = ValueType("Groups", item=typ.item, fields=(("category", T), ("average", I)))
        output = seq(record(category=T, average=F))
        steps = [("group", ["rows"], "groups", groups, {"field": "key", "key_alias": "category", "value_alias": "average", "order": "key"}),
                 ("aggregate", ["groups"], "out", output, {"subkind": "mean", "field": "value"})]
        rows = [{"key": "z", "value": 1}, {"key": "a", "value": 5}, {"key": "z", "value": 2}]
        c, p = fixture("node_commonjs_sync_v1", [InputBinding("rows", typ)], steps)
        tasks.append((c, p, [rows])); expected.append([{"category": "a", "average": 5.0}, {"category": "z", "average": 1.5}])
        self.assertEqual(js_batch(tasks), expected)

    def test_sql_anti_join_all_ties_and_scalar_runtime_types(self):
        typ = relation(key=I, value=I, ordinal=I)
        right = relation(reference=I, ordinal=I)
        tables = {"left_rows": [{"key": 1, "value": 3, "ordinal": 3}, {"key": 2, "value": -1, "ordinal": 1}, {"key": 3, "value": -1, "ordinal": 2}],
                  "right_rows": [{"reference": 2, "ordinal": 1}, {"reference": 2, "ordinal": 2}]}
        c, p = fixture("sqlite_select_v1", [InputBinding("left_rows", typ, ordinal="ordinal"), InputBinding("right_rows", right, ordinal="ordinal")], [("not_exists", ["left_rows", "right_rows"], "out", typ, {"left_key": "key", "right_key": "reference"})], interface=Interface("query", (), columns=("key", "value", "ordinal")))
        self.assertEqual(sql_call(c, p, tables), (("key", "value", "ordinal"), [(3, -1, 2), (1, 3, 3)]))
        c, p = fixture("sqlite_select_v1", [InputBinding("left_rows", typ, ordinal="ordinal")], [("aggregate", ["left_rows"], "out", typ, {"subkind": "min", "field": "value", "all_ties": True})], interface=Interface("query", (), columns=("key", "value", "ordinal")))
        self.assertEqual(sql_call(c, p, {"left_rows": tables["left_rows"]}), (("key", "value", "ordinal"), [(2, -1, 1), (3, -1, 2)]))
        for subkind, answer, output_type in [("sum", 1, I), ("count", 3, I), ("mean", 1 / 3, ValueType("Nullable", item=F)), ("min", -1, ValueType("Nullable", item=I)), ("max", 3, ValueType("Nullable", item=I))]:
            out = relation(result=output_type)
            c, p = fixture("sqlite_select_v1", [InputBinding("left_rows", typ, ordinal="ordinal")], [("aggregate", ["left_rows"], "out", out, {"subkind": subkind, "field": "value", "alias": "result"})], interface=Interface("query", (), columns=("result",)))
            columns, rows = sql_call(c, p, {"left_rows": tables["left_rows"]})
            self.assertEqual(columns, ("result",)); self.assertEqual(rows, [(answer,)])
            self.assertIs(type(rows[0][0]), type(answer))

    def test_posix_sum_count_empty_and_entry_override(self):
        for subkind, answer in [("sum", "2\n"), ("count", "3\n")]:
            c, p = fixture("posix_numeric_stream_v1", [InputBinding("stream", seq())], [("aggregate", ["stream"], "out", I, {"subkind": subkind})], interface=Interface("shell", ()))
            self.assertEqual(sh_call(c, p, [-3, 0, 5]), answer)
            self.assertEqual(sh_call(c, p, []), "0\n")
        boundary = Boundary("input_empty", "stream", "-7", "entry")
        steps = [("filter", ["stream"], "kept", seq(), {"predicate": {"op": "gt", "value": 10}}), ("aggregate", ["kept"], "out", I, {"subkind": "sum"})]
        c, p = fixture("posix_numeric_stream_v1", [InputBinding("stream", seq())], steps, interface=Interface("shell", ()), boundaries=[boundary])
        self.assertEqual(sh_call(c, p, []), "-7\n")
        self.assertEqual(sh_call(c, p, [1]), "0\n")

    def test_sql_unsupported_diff_and_missing_ordinal(self):
        typ = relation(value=I)
        c, p = fixture("sqlite_select_v1", [InputBinding("data", typ)], [("diff", ["data"], "out", typ, {})], interface=Interface("query", (), columns=("value",)))
        with self.assertRaises(ContractError) as caught:
            lower(c, p, Budget())
        self.assertEqual(caught.exception.code, "BACKEND_UNSUPPORTED")
        c, p = fixture("sqlite_select_v1", [InputBinding("data", typ)], [("dedupe", ["data"], "out", typ, {"field": "value"})], interface=Interface("query", (), columns=("value",)))
        with self.assertRaises(ContractError):
            lower(c, p, Budget())


if __name__ == "__main__":
    unittest.main()
