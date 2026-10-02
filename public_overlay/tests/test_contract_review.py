"""Independent implementation review probes, never B80 or sealed fixtures.

2026-09-30 initial review: the first three mutations were accepted by _static
at 12:17 UTC, before the producer patched those gates. At 12:21 the remaining
observation/boundary checks failed and invalid raw inputs raised three uncaught
exceptions. After producer fixes, this file passed all six tests at 12:24 UTC.
These are static/mocked review checks, not public latency, B80 scores or actual
OS-isolation evidence. No generated source is executed by these tests.
"""
from dataclasses import replace
import unittest
from unittest.mock import patch

from verantyx.contract_budget import Budget
from verantyx.contract_ir import ContractError, ValueType, canonical
from verantyx.contract_reader import read_requirements
from verantyx.contract_plan import synthesize
from verantyx.contract_lower import lower
from verantyx.contract_verify import _static, interpret, select_witnesses, verify
from verantyx.contract_codegen import ContractCodeGenerator


RAW = ("Python function f(items); input items: Seq[Int[-10..10]], "
       "length 0..32; finally return sum")


class ContractIndependentReviewTests(unittest.TestCase):
    def setUp(self):
        # Isolate law/constraint checks from background workload. This clock
        # is not a measurement of public latency or OS safety.
        clock = patch("verantyx.contract_budget.time.monotonic", return_value=0.0)
        clock.start()
        self.addCleanup(clock.stop)

    def objects(self, raw=RAW):
        source, ledger, contract = read_requirements(raw)
        plan = synthesize(contract)
        artifact = lower(contract, plan, Budget())
        return source, ledger, contract, plan, artifact

    def test_unrequested_empty_policy_cannot_enter_frozen_contract(self):
        source, ledger, contract, _, _ = self.objects()
        cfg = contract.goals[0].config
        cfg["empty"] = -7
        changed = replace(contract, goals=(replace(contract.goals[0], config_json=canonical(cfg)),))
        plan = synthesize(changed)
        artifact = lower(changed, plan, Budget())
        self.assertEqual(interpret(changed, {"items": []}, Budget()), -7)
        with self.assertRaises(ContractError):
            _static(source, ledger, changed, plan, artifact, Budget())

    def test_static_return_domain_does_not_accept_shape_only(self):
        source, ledger, contract, plan, artifact = self.objects()
        changed = replace(contract, return_type=ValueType("Int", low=0, high=1))
        plan = replace(plan, contract_hash=changed.hash)
        artifact = replace(artifact, plan_hash=plan.hash)
        with self.assertRaises(ContractError):
            _static(source, ledger, changed, plan, artifact, Budget())

    def test_input_empty_trigger_cannot_be_disabled(self):
        source, ledger, contract, plan, artifact = self.objects(RAW + "; if items is empty return -7")
        changed = replace(contract, boundaries=(replace(contract.boundaries[0], trigger="not_the_entry"),))
        plan = replace(plan, contract_hash=changed.hash, boundaries=changed.boundaries)
        artifact = replace(artifact, plan_hash=plan.hash)
        self.assertEqual(interpret(changed, {"items": []}, Budget()), 0)
        with self.assertRaises(ContractError):
            _static(source, ledger, changed, plan, artifact, Budget())

    def test_missing_protocol_observations_remain_unverified(self):
        source, ledger, contract, plan, artifact = self.objects()
        results = []
        for _, bindings in select_witnesses(contract, Budget()):
            results.append({"status": "EXECUTED", "exit_code": 0,
                            "signature_matches": True, "mutation": {"unchanged": True},
                            "value": interpret(contract, bindings, Budget())})
        # Missing output captures and OS-boundary checks are unknown, not an
        # independently observed empty stream / successful security probe.
        observations = {"status": "EXECUTED", "artifact_sha256": artifact.hash,
                        "isolation": {"verified": True}, "results": results}
        with patch("verantyx.contract_verify.run_artifact", return_value=observations):
            with self.assertRaises(ContractError):
                verify(source, ledger, contract, plan, artifact, Budget())

    def test_literal_comparison_witnesses_distinguish_boundary_mutations(self):
        raw = ("Python function f(items); input items: Seq[Int[-100..100]], "
               "length 0..32; first keep value > 37; finally return count")
        _, _, contract = read_requirements(raw)
        selected = select_witnesses(contract, Budget())
        values = {x for _, bindings in selected for x in bindings["items"]}
        self.assertTrue({36, 37, 38}.issubset(values),
                        "registered comparison witnesses must cover below/equal/above literal")
        self.assertTrue(any(sum(x > 37 for x in bindings["items"]) !=
                            sum(x >= 37 for x in bindings["items"])
                            for _, bindings in selected),
                        "strict/non-strict artifact mutation needs a distinguishing call")

    def test_invalid_raw_input_returns_typed_failure(self):
        for raw in (b"x", {"value": float("nan")}, "\ud800"):
            with self.subTest(type=type(raw).__name__):
                result = ContractCodeGenerator().generate(raw)
                self.assertIsNone(result["code"])
                self.assertNotEqual(result["verdict"], "ANSWER")
                self.assertIn(result["status"], ("refused", "held"))


if __name__ == "__main__":
    unittest.main()
