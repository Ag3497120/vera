"""Independent SQL witness fixtures. No subprocess or OS-isolation evidence.

Root owns execution. These diagnostic fixtures are not raw/B80/sealed scores.
Only artifact source changes; the source, ledger, contract and plan stay frozen.
"""
from dataclasses import asdict, replace
import copy
import hashlib
import sqlite3
import unittest
from unittest.mock import patch
from verantyx.contract_budget import Budget
from verantyx.contract_ir import (Artifact, ContractError, Goal, InputBinding,
    Interface, ProgramContract, RequestSource, Requirement, RequirementLedger,
    Span, ValueType, canonical)
from verantyx.contract_plan import synthesize
from verantyx.contract_verify import accepts, interpret, select_witnesses, verify

CLEANUP={"group_signalled":False,"leader_reaped":True,"group_absence_confirmed":True,
         "cleanup_error":None,"deadline_exceeded":False}
SCOPE="owned new-session PGID; process-fork denial observed by trusted probe"

def fixture(join=False,count=False):
    scalar=ValueType("Int",low=-3,high=3);ordinal=ValueType("Int",low=1,high=32)
    fields=(("id",scalar),("ord",ordinal)) if join else (("a",ValueType("Nullable",item=scalar)),("b",ValueType("Nullable",item=scalar)),("ord",ordinal))
    row=ValueType("Record",fields=fields);relation=ValueType("Relation",item=row,max_items=32)
    names=("left_rows","right_rows") if join else ("input_rows",)
    inputs=tuple(InputBinding(n,relation,ordinal="ord") for n in names)
    if join:
        cfg={"left_key":"id","right_key":"id","projection":[{"side":"left","field":"id","alias":"left_id"},{"side":"right","field":"id","alias":"right_id"}]}
        goals=[Goal("pair","join",names,"result",canonical(cfg),("r0",))]
        output=ValueType("Relation",item=ValueType("Record",fields=(("left_id",scalar),("right_id",scalar))),max_items=1024)
        columns=("left_id","right_id");symbol="result"
        sql='SELECT l."id" AS "left_id",r."id" AS "right_id" FROM "left_rows" AS l JOIN "right_rows" AS r ON l."id"=r."id" ORDER BY l."ord",r."ord"'
        changed=sql.replace('JOIN "right_rows"','JOIN "left_rows"')
    else:
        goals=[Goal("keep","filter",names,"kept",canonical({"predicate":{"op":"is_null","field":"a"}}),("r0",))]
        output=relation;columns=("a","b","ord");symbol="kept"
        sql='SELECT "a","b","ord" FROM "input_rows" WHERE "a" IS NULL ORDER BY "ord"'
        if count:
            goals.append(Goal("count","aggregate",("kept",),"result",canonical({"subkind":"count","alias":"n"}),("r1",)))
            output=ValueType("Relation",item=ValueType("Record",fields=(("n",ValueType("Int",low=0,high=32)),)),max_items=1)
            columns=("n",);symbol="result";sql='SELECT count(*) AS "n" FROM "input_rows" WHERE "a" IS NULL'
        changed=sql.replace('"a" IS NULL','"b" IS NULL')
    interface=Interface("query",names,columns=columns);source=RequestSource("r3 independent diagnostic "+str((join,count)))
    span=(Span(0,len(source.raw),source.raw),)
    requirements=[Requirement("interface","interface",span,payload_json=canonical(interface)),Requirement("profile","profile",span,payload_json=canonical({"profile":"sqlite_select_v1"}))]
    for i,b in enumerate(inputs):requirements.append(Requirement("d"+str(i),"domain",span,target=b.name,payload_json=canonical({"type":asdict(b.type),"ordinal":b.ordinal})))
    for i,g in enumerate(goals):requirements.append(Requirement("r"+str(i),"relation",span,payload_json=canonical({"kind":g.kind,"inputs":g.inputs,"output":g.output,"config":g.config})))
    requirements.extend((Requirement("return","return",span,payload_json=canonical({"symbol":symbol})),Requirement("effect","effect",span,payload_json=canonical({"effect":"pure_input_unchanged"}))))
    ledger=RequirementLedger(source.hash,tuple(requirements))
    contract=ProgramContract(source.hash,ledger.hash,"sqlite_select_v1",interface,inputs,tuple(goals),symbol,output,tuple(r.id for r in requirements),origin="diagnostic_fixture")
    plan=synthesize(contract,Budget());artifact=Artifact(contract.profile,sql,plan.hash,interface)
    return source,ledger,contract,plan,artifact,replace(artifact,source=changed)

def independent_runner(profile,source,interface,cases,**hooks):
    # Logical probe/batch accounting is mocked; actual subprocess count is zero.
    for _ in range(2):hooks["before_launch"]()
    results=[];quote=lambda s:'"'+s.replace('"','""')+'"'
    for index,case in enumerate(cases):
        hooks["before_case"]();connection=sqlite3.connect(":memory:")
        try:
            for name,table in case["tables"].items():
                schema=table["schema"]
                connection.execute("CREATE TABLE "+quote(name)+" ("+",".join(quote(c["name"])+" "+c["type"] for c in schema)+")")
                connection.executemany("INSERT INTO "+quote(name)+" VALUES ("+",".join("?" for c in schema)+")",table["rows"])
            cursor=connection.execute(source);rows=[list(r) for r in cursor.fetchall()];columns=[c[0] for c in cursor.description]
        finally:connection.close()
        tag=lambda v:"null" if v is None else "integer" if type(v) is int else "real" if type(v) is float else "text"
        results.append({"status":"EXECUTED","exit_code":0,"index":index,"stdout":"","stderr":"","process_stderr":"","cleanup":copy.deepcopy(CLEANUP),"rows":rows,"columns":columns,"row_types":[[tag(v) for v in r] for r in rows],"schema_matches":True,"sqlite_version":"3.53.2"})
    return {"status":"EXECUTED","artifact_sha256":hashlib.sha256(source.encode()).hexdigest(),"results":results,
        "isolation":{"verified":True,"fork_denied":True,"descendant_scope":SCOPE,"probe_cleanup":copy.deepcopy(CLEANUP),"checks":{n:True for n in ("external_read","external_write","local_write","network","unlisted_exec","fork_denied")}},
        "stats":{"launches":2,"cases_reserved":len(cases),"cases_attempted":len(cases),"cases_finished":len(cases),"unconfirmed_starts":0,"output_bytes":0,"output_reserved_bytes":0,"children":[{"cleanup":copy.deepcopy(CLEANUP)},{"cleanup":copy.deepcopy(CLEANUP)}]}}

class WitnessR3Tests(unittest.TestCase):
    def setUp(self):
        clock=patch("verantyx.contract_budget.time.monotonic",return_value=0.0);clock.start();self.addCleanup(clock.stop)

    def test_correct_and_mutant_pairs_use_identical_frozen_ledger(self):
        for join,count in ((False,False),(False,True),(True,False)):
            with self.subTest(join=join,count=count):
                source,ledger,contract,plan,correct,mutant=fixture(join,count)
                with patch("verantyx.contract_verify.run_artifact",side_effect=independent_runner):
                    self.assertEqual(verify(source,ledger,contract,plan,correct,Budget())["status"],"finite_verified")
                    with self.assertRaises(ContractError) as error:verify(source,ledger,contract,plan,mutant,Budget())
                self.assertEqual(error.exception.code,"VERIFICATION_FAILED")
                self.assertTrue(any(not c["passed"] for c in error.exception.details["checks"]))
                self.assertEqual(correct.plan_hash,mutant.plan_hash)

    def test_null_independence_and_final_count_contrast(self):
        _,_,contract,_,_,_=fixture(count=True)
        changed=replace(contract,goals=(replace(contract.goals[0],config_json=canonical({"predicate":{"op":"is_null","field":"b"}})),contract.goals[1]))
        selected=select_witnesses(contract,Budget());self.assertEqual(len(selected),12)
        self.assertTrue(any(interpret(contract,b,Budget())!=interpret(changed,b,Budget()) for _,b in selected))
        rows=[r for _,b in selected for r in b["input_rows"]]
        self.assertTrue(any(r["a"] is None and r["b"] is not None for r in rows))
        self.assertTrue(any(r["b"] is None and r["a"] is not None for r in rows))
        for _,b in selected:self.assertTrue(accepts(b["input_rows"],contract.inputs[0].type,domain=True))

    def test_bilateral_empty_and_input_values_are_independent(self):
        _,_,contract,_,_,_=fixture(join=True);selected=select_witnesses(contract,Budget())
        self.assertTrue(any(b["left_rows"] and not b["right_rows"] for _,b in selected))
        self.assertTrue(any(b["right_rows"] and not b["left_rows"] for _,b in selected))
        self.assertTrue(any(b["left_rows"]!=b["right_rows"] for _,b in selected))

    def test_missing_witness_capacity_holds_before_runner(self):
        source,ledger,contract,plan,correct,_=fixture()
        with patch("verantyx.contract_verify.run_artifact") as runner:
            with self.assertRaises(ContractError) as error:verify(source,ledger,contract,plan,correct,Budget(limits={"witnesses":11}))
        self.assertEqual(error.exception.code,"VERIFICATION_BUDGET");runner.assert_not_called()

if __name__=="__main__":unittest.main()
