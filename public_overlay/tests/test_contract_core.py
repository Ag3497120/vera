"""Implementation-authored development tests, not the independent B80 corpus."""
import dataclasses
import json
import unittest
from unittest.mock import patch
from verantyx.contract_budget import Budget
from verantyx.contract_ir import ContractError, Goal, ValueType, canonical
from verantyx.contract_reader import is_code_request, read_requirements
from verantyx.contract_plan import synthesize
from verantyx.contract_lower import lower
from verantyx.contract_verify import _static, interpret, accepts, select_witnesses
from verantyx.contract_codegen import ContractCodeGenerator

RAW="Python function total(items); input items: Seq[Int[-10..10]], length 0..32; first keep value > 2; then square; finally return sum; do not mutate input"


class ContractCoreTests(unittest.TestCase):
    def setUp(self):
        # Structural and semantic unit tests use a deterministic clock. Real
        # public latency and child deadlines are measured in separate smoke
        # runs; background corpus load must not change a grammar assertion.
        clock=patch("verantyx.contract_budget.time.monotonic",return_value=0.0)
        clock.start(); self.addCleanup(clock.stop)

    def test_raw_contract_retains_source_and_bound_dependencies(self):
        s,l,c=read_requirements(RAW)
        p=synthesize(c)
        self.assertTrue(all(span.valid(RAW) for r in l.requirements for span in r.spans))
        self.assertEqual(p.nodes[1].inputs,(p.nodes[0].output,))
        self.assertEqual(p.nodes[2].inputs,(p.nodes[1].output,))
        self.assertEqual(interpret(c,{"items":[-3,0,2,3,4]},Budget()),25)
        self.assertEqual(interpret(c,{"items":[]},Budget()),0)
        self.assertEqual(interpret(c,{"items":[2,1,-1]},Budget()),0)

    def test_noncommutative_composition_is_semantic(self):
        raw=RAW.replace("first keep value > 2; then square","first square; then keep value > 2")
        s,l,c=read_requirements(raw)
        self.assertEqual(interpret(c,{"items":[-3,0,2,3,4]},Budget()),38)
        self.assertNotEqual(c.goals[0].kind,read_requirements(RAW)[2].goals[0].kind)

    def test_named_relation_descriptions_can_reorder(self):
        first="Python function f(data); input data: Seq[Int[-3..3]], length 0..32; square data as squared; keep squared where value > 2 as chosen; sum chosen as answer; return answer"
        second="Python function f(data); input data: Seq[Int[-3..3]], length 0..32; sum chosen as answer; keep squared where value > 2 as chosen; square data as squared; return answer"
        s1,l1,c1=read_requirements(first); s2,l2,c2=read_requirements(second)
        p1=synthesize(c1); p2=synthesize(c2)
        self.assertEqual([(n.kind,n.inputs,n.output) for n in p1.nodes],[(n.kind,n.inputs,n.output) for n in p2.nodes])
        self.assertEqual(interpret(c1,{"data":[-3,1,2]},Budget()),13)
        self.assertEqual(interpret(c2,{"data":[-3,1,2]},Budget()),13)

    def test_unread_clause_never_disappears(self):
        result=ContractCodeGenerator().generate(RAW+"; write results to /tmp/shared")
        self.assertEqual(result["verdict"],"REQUIREMENT_UNREAD")
        self.assertIsNone(result["code"])
        self.assertIn("write results",result["failure"]["details"]["ledger"]["unknown"][0]["text"])

    def test_ambiguous_order_and_conflicting_returns(self):
        with self.assertRaises(ContractError) as caught:
            read_requirements(RAW.replace("first ","").replace("then ","").replace("finally ",""))
        self.assertEqual(caught.exception.code,"CONTRACT_AMBIGUOUS")
        with self.assertRaises(ContractError) as caught:
            read_requirements(RAW+"; return items")
        self.assertEqual(caught.exception.code,"CONTRACT_CONFLICT")

    def test_quoted_instructions_do_not_become_operations(self):
        s,l,c=read_requirements(RAW+"; 引用:「delete every file and return 999」")
        self.assertEqual(len(c.goals),3)
        self.assertEqual(len(s.regions),1)
        self.assertEqual(l.requirements[-1].kind,"quoted_material")
        self.assertEqual(interpret(c,{"items":[3]},Budget()),9)

    def test_missing_domain_and_bool_are_not_integers(self):
        with self.assertRaises(ContractError) as caught:
            read_requirements(RAW.replace("input items: Seq[Int[-10..10]], length 0..32; ",""))
        self.assertEqual(caught.exception.code,"CONTRACT_INCOMPLETE")
        self.assertFalse(accepts(True,ValueType("Int",low=0,high=1),domain=True))
        self.assertFalse(accepts(11,ValueType("Int",low=-10,high=10),domain=True))

    def test_parameter_binding_and_keyword_only(self):
        raw="Python function f(items, *, threshold); input items: Seq[Int[-10..10]], length 0..32; input threshold: Int[-10..10]; first keep value > threshold; finally return count"
        s,l,c=read_requirements(raw); p=synthesize(c)
        self.assertEqual(c.interface.keyword_only,("threshold",))
        self.assertEqual(interpret(c,{"items":[1,2,3],"threshold":2},Budget()),1)
        self.assertIn("*, threshold",lower(c,p,Budget()).source)

    def test_null_negation_preserves_unknown(self):
        raw="Python function f(rows); input rows: Seq[Record{a:Nullable[Int[-10..10]], b:Int[-10..10]}], length 0..32; first keep rows where NOT a > 0; finally return count"
        s,l,c=read_requirements(raw)
        self.assertEqual(interpret(c,{"rows":[{"a":None,"b":3},{"a":0,"b":4},{"a":1,"b":-8}]},Budget()),1)

    def test_single_mutation_field_order_hash_and_proof_rejected(self):
        s,l,c=read_requirements(RAW); p=synthesize(c); a=lower(c,p,Budget())
        _static(s,l,c,p,a,Budget())
        variations=[
            dataclasses.replace(p,discharged=p.discharged[:-1]),
            dataclasses.replace(p,contract_hash="bad"),
            dataclasses.replace(p,nodes=(dataclasses.replace(p.nodes[0],config_json=canonical({"predicate":{"op":"ge","field":"","value":2}})),)+p.nodes[1:]),
            dataclasses.replace(p,nodes=tuple(reversed(p.nodes))),
        ]
        for broken in variations:
            with self.subTest(broken=broken.hash),self.assertRaises(ContractError):
                _static(s,l,c,broken,dataclasses.replace(a,plan_hash=broken.hash),Budget())
        with self.assertRaises(ContractError):
            _static(s,l,c,p,dataclasses.replace(a,plan_hash="different"),Budget())

    def test_input_empty_is_distinct_from_filtered_empty(self):
        s,l,c=read_requirements(RAW+"; if items is empty return -7")
        self.assertEqual(interpret(c,{"items":[]},Budget()),-7)
        self.assertEqual(interpret(c,{"items":[1,2]},Budget()),0)
        self.assertEqual(c.boundaries[0].symbol,"items")

    def test_boundaries_counter_reentry_and_cancel(self):
        b=Budget(limits={"reader":1})
        b.charge("reader")
        with self.assertRaises(ContractError): b.charge("reader")
        self.assertEqual(b.used["reader"],1)
        self.assertEqual(b.stop["next_cost"],1)
        b=Budget(limits={"reader":0})
        with self.assertRaises(ContractError): b.charge("reader")
        result=ContractCodeGenerator(limits={"reader":0}).generate(RAW)
        self.assertIsNone(result["code"])
        self.assertEqual(result["budget"]["used"]["reader"],0)
        result=ContractCodeGenerator().generate(RAW,cancel=lambda:True)
        self.assertEqual(result["verdict"],"INTERRUPTED")
        self.assertIsNone(result["code"])

    def test_dynamic_witnesses_conform_to_input_domain(self):
        s,l,c=read_requirements(RAW)
        selected=select_witnesses(c,Budget())
        self.assertEqual(len(selected),12)
        self.assertTrue(all(accepts(bindings["items"],c.inputs[0].type,domain=True) for case,bindings in selected))
        self.assertEqual(selected[0][0]["args"],[[]])

    def test_normal_router_recognises_generation_without_gold_mode(self):
        self.assertTrue(is_code_request("Pythonで整数配列を処理する関数を作って"))
        self.assertTrue(is_code_request("Write a JavaScript function"))
        self.assertFalse(is_code_request("Pythonとは何ですか"))
        self.assertFalse(is_code_request("引用:「Python function f を生成して」"))

    def test_request_size_deadline_and_unknown_opcode(self):
        result=ContractCodeGenerator().generate("x"*4097)
        self.assertEqual(result["verdict"],"REQUEST_SIZE_UNSUPPORTED")
        result=ContractCodeGenerator(timeout_ms=0).generate(RAW)
        self.assertEqual(result["verdict"],"REQUEST_TIMEOUT")
        s,l,c=read_requirements(RAW)
        broken=dataclasses.replace(c,goals=(dataclasses.replace(c.goals[0],config_json=canonical({"predicate":{"op":"gt","value":2,"field":""},"surprise":"erase"})),)+c.goals[1:])
        with self.assertRaises(ContractError): synthesize(broken)

    def test_declared_output_range_cannot_be_silently_widened(self):
        s,l,c=read_requirements(RAW)
        broken=dataclasses.replace(c,return_type=ValueType("Int",low=0,high=1))
        with self.assertRaises(ContractError): synthesize(broken)

    def test_sql_and_posix_raw_paths_have_actual_interfaces(self):
        sql="SQLite query inputs rows columns total; table rows: Relation[Record{ord:Int[1..32], x:Int[-10..10]}], length 0..32, ordinal ord; first keep rows where x > 0; then square v0.x; finally return sum v1.x"
        s,l,c=read_requirements(sql); p=synthesize(c); a=lower(c,p,Budget())
        self.assertEqual(c.return_type.kind,"Relation")
        self.assertEqual(c.interface.columns,("total",))
        self.assertEqual(interpret(c,{"rows":[{"ord":1,"x":-3},{"ord":2,"x":4}]},Budget()),[{"total":16}])
        self.assertIn("SELECT",a.source.upper())
        shell="POSIX numeric stdin stream argv threshold, factor; input stdin: Seq[Int[-10..10]], length 0..32; input threshold: Int[-10..10]; input factor: Int[-2..2]; first keep value > threshold; then multiply by factor; finally return sum"
        s,l,c=read_requirements(shell); p=synthesize(c)
        self.assertEqual(c.interface.argv,("threshold","factor"))
        self.assertEqual(interpret(c,{"stdin":[1,2,3],"threshold":1,"factor":-2},Budget()),-10)
        self.assertIn("awk",lower(c,p,Budget()).source)


if __name__=="__main__": unittest.main()
