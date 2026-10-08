"""Independent, static/mocked r2 regressions; no artifact/OS execution.

Only the development-r2 copy is in scope. These fixtures are reviewer-authored,
not B80/sealed inputs. The parent runs this file in its single test worker.
The mutable clock is a deadline oracle, never a public latency measurement.
"""
import ast
import builtins
import hashlib
import json
import symtable
import unittest
from unittest.mock import patch

from verantyx.contract_budget import Budget
from verantyx.contract_codegen import ContractCodeGenerator
from verantyx.contract_ir import ContractError
from verantyx.contract_reader import is_code_request, read_requirements
from verantyx.contract_plan import synthesize
from verantyx.contract_lower import lower
from verantyx.contract_verify import verify
from verantyx import contract_codegen as codegen
from verantyx import contract_sandbox as sandbox


PY_RAW = ("Python function total(items); input items: Seq[Int[-3..3]], "
          "length 0..8; finally return sum; do not mutate input")
SQL_RAW = ("SQLite query inputs rows columns total; table rows: "
           "Relation[Record{ord:Int[1..32], x:Int[-3..3]}], length 0..8, "
           "ordinal ord; finally return sum rows.x")
OS_CHECKS = {name: True for name in ("external_read", "external_write",
                                    "local_write", "network", "unlisted_exec")}


class ContractRevisionTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        clock = patch("verantyx.contract_budget.time.monotonic", side_effect=lambda: self.now)
        clock.start()
        self.addCleanup(clock.stop)
        # A missing mock must fail rather than silently starting an OS worker.
        launches = patch("verantyx.contract_sandbox.subprocess.Popen",
                         side_effect=AssertionError("revision review must not launch artifacts"))
        launches.start()
        self.addCleanup(launches.stop)

    def objects(self):
        source, ledger, contract = read_requirements(PY_RAW)
        plan = synthesize(contract)
        artifact = lower(contract, plan, Budget())
        return source, ledger, contract, plan, artifact

    def output_usage(self, budget):
        return budget.report()["resource_usage"]["child_output_bytes"]

    @staticmethod
    def child_value(values, child_id):
        # Python report and its JSON serialization may use different key types.
        return values.get(child_id, values.get(str(child_id)))

    def test_explicit_sqlite_generation_header_reaches_code_router(self):
        self.assertTrue(is_code_request(SQL_RAW))
        source, ledger, contract = read_requirements(SQL_RAW)
        self.assertEqual(contract.profile, "sqlite_select_v1")
        self.assertEqual(contract.interface.columns, ("total",))
        self.assertFalse(ledger.unknown)
        self.assertTrue(all(span.valid(source.raw) for req in ledger.requirements for span in req.spans))
        for name in ("what", "how", "why"):
            with self.subTest(column=name):
                renamed = SQL_RAW.replace("columns total", "columns " + name)
                self.assertTrue(is_code_request(renamed), "an allowed alias is not a question cue")
        renamed = SQL_RAW.replace("columns total", "columns what").replace("x:", "how:").replace("rows.x", "rows.how")
        budget = Budget()
        _, _, renamed_contract = read_requirements(renamed, budget)
        self.assertEqual(renamed_contract.interface.columns, ("what",))
        self.assertEqual(renamed_contract.goals[0].config["field"], "how")
        self.assertEqual(budget.used["subprocesses"], 0)
        self.assertEqual(budget.used["witnesses"], 0)

    def test_sql_explanations_and_quoted_headers_are_not_generation(self):
        self.assertFalse(is_code_request("Explain how SQLite SELECT queries work"))
        self.assertFalse(is_code_request("SQLite queryとは何ですか"))
        self.assertFalse(is_code_request("引用:「" + SQL_RAW + "」"))
        self.assertFalse(is_code_request(SQL_RAW + "; Explain this query"))

    def test_output_limit_is_per_child_and_actual_bytes_are_separate(self):
        budget = Budget(limits={"child_output_bytes": 9})
        stdout, stderr = "あ".encode("utf-8"), b"err\n"
        self.assertEqual(len(stdout), 3)  # Bytes, not one decoded character.
        budget.charge_output(len(stdout) + 2, 0)
        budget.record_output(len(stdout), 0)  # A short read is three actual bytes.
        budget.charge_output(len(stderr), 0)
        budget.record_output(len(stderr), 0)  # stdout+stderr share one child cap.
        budget.charge_output(9, 1)
        budget.record_output(9, 1)
        usage = self.output_usage(budget)
        self.assertEqual(usage["reserved_total"], 18)
        self.assertEqual(usage["actual_total"], 16)
        self.assertEqual(self.child_value(usage["reserved_by_child"], 0), 9)
        self.assertEqual(self.child_value(usage["actual_by_child"], 0), 7)
        self.assertEqual(self.child_value(usage["actual_by_child"], 1), 9)
        self.assertEqual(usage["peak_actual_bytes"], 9)
        self.assertEqual(budget.used["child_output_bytes"], 9)
        with self.assertRaises(ContractError):
            budget.charge_output(1, 1)
        # The refused read must add neither reservation nor received bytes.
        after = self.output_usage(budget)
        self.assertEqual(after["reserved_total"], 18)
        self.assertEqual(after["actual_total"], 16)

    def test_probe_only_failure_does_not_count_reserved_witnesses(self):
        objects = self.objects()
        budget = Budget()
        seen = []

        def probe_only(profile, source, interface, cases, **kwargs):
            self.assertEqual(len(cases), 12)
            seen.append((kwargs["deadline"], kwargs["cleanup_reserve_ms"]))
            kwargs["before_launch"]()
            kwargs["before_output"](8, 0)
            kwargs["after_output"](6, 0)
            return {"status": "SANDBOX_UNAVAILABLE", "artifact_sha256": objects[-1].hash,
                    "isolation": {"verified": False}, "results": [],
                    "stats": {"launches": 1, "cases_reserved": 0, "cases_attempted": 0,
                              "cases_finished": 0, "cases": 0, "output_bytes": 6}}

        with patch("verantyx.contract_verify.run_artifact", side_effect=probe_only) as runner:
            with self.assertRaises(ContractError) as caught:
                verify(*objects, budget)
        self.assertEqual(caught.exception.code, "SANDBOX_UNAVAILABLE")
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(budget.used["subprocesses"], 1)
        self.assertEqual(budget.used["witnesses"], 0)
        self.assertEqual(self.output_usage(budget)["actual_total"], 6)
        self.assertEqual(seen, [(budget.deadline, 50)])

    def test_two_started_calls_do_not_become_twelve_executed_calls(self):
        objects = self.objects()
        budget = Budget()

        def partial_batch(profile, source, interface, cases, **kwargs):
            kwargs["before_launch"]()  # OS probe
            kwargs["before_launch"]()  # One batch child, not twelve children.
            for index in range(2):
                kwargs["before_case"]()
                kwargs["before_output"](5, 1)
                kwargs["after_output"](4, 1)
            return {"status": "ARTIFACT_ERROR", "artifact_sha256": objects[-1].hash,
                    "isolation": {"verified": True, "checks": OS_CHECKS},
                    "results": [{"index": 0, "status": "EXECUTED"},
                                {"index": 1, "status": "ARTIFACT_ERROR"}],
                    "stats": {"launches": 2, "cases_reserved": 2, "cases_attempted": 2,
                              "cases_finished": 2, "cases": 2, "output_bytes": 8,
                              "unconfirmed_starts": 0}}

        with patch("verantyx.contract_verify.run_artifact", side_effect=partial_batch) as runner:
            with self.assertRaises(ContractError) as caught:
                verify(*objects, budget)
        self.assertEqual(caught.exception.code, "ARTIFACT_ERROR")
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(budget.used["subprocesses"], 2)
        self.assertEqual(budget.used["witnesses"], 2)
        self.assertEqual(self.output_usage(budget)["reserved_total"], 10)
        self.assertEqual(self.output_usage(budget)["actual_total"], 8)
        self.assertEqual(caught.exception.details["execution"]["stats"]["cases_attempted"], 2)

    def test_public_deadline_and_external_cancel_have_distinct_stop_reasons(self):
        for elapsed, external, expected in ((1.01, False, "REQUEST_TIMEOUT"),
                                             (0.10, True, "INTERRUPTED")):
            with self.subTest(expected=expected):
                self.now = 0.0
                cancelled = [False]

                def halted(profile, source, interface, cases, **kwargs):
                    kwargs["before_launch"]()
                    self.now = elapsed
                    cancelled[0] = external
                    # The transport's external-cancel predicate must remain
                    # false at a public timeout; deadline is a separate input.
                    self.assertEqual(bool(kwargs["cancel"]()), external)
                    self.assertEqual(kwargs["deadline"], 1.0)
                    return {"status": expected, "artifact_sha256":
                            hashlib.sha256(source.encode()).hexdigest(),
                            "isolation": {"verified": False}, "results": [],
                            "stats": {"launches": 1, "cases_reserved": 0,
                                      "cases_attempted": 0, "cases_finished": 0,
                                      "cases": 0, "output_bytes": 0,
                                      "output_reserved_bytes": 0, "unconfirmed_starts": 0}}

                with patch("verantyx.contract_verify.run_artifact", side_effect=halted) as runner:
                    result = ContractCodeGenerator().generate(PY_RAW, cancel=lambda: cancelled[0])
                self.assertEqual(runner.call_count, 1)
                self.assertEqual(result["verdict"], expected)
                self.assertEqual(result["status"], "held")
                self.assertIsNone(result["code"])
                self.assertEqual(result["failure"]["code"], expected)
                self.assertEqual(result["budget"]["stop"]["code"], expected)

    def test_child_timeout_is_recorded_before_public_deadline(self):
        def timed_out(profile, source, interface, cases, **kwargs):
            kwargs["before_launch"]()
            self.now = 0.20
            return {"status": "CHILD_TIMEOUT", "artifact_sha256":
                    hashlib.sha256(source.encode()).hexdigest(),
                    "isolation": {"verified": False}, "results": [],
                    "stats": {"launches": 1, "cases_reserved": 0, "cases_attempted": 0,
                              "cases_finished": 0, "cases": 0, "output_bytes": 0,
                              "output_reserved_bytes": 0, "unconfirmed_starts": 0}}
        with patch("verantyx.contract_verify.run_artifact", side_effect=timed_out):
            result = ContractCodeGenerator().generate(PY_RAW)
        self.assertEqual(result["verdict"], "CHILD_TIMEOUT")
        self.assertEqual(result["status"], "held")
        self.assertEqual(result["budget"]["stop"]["code"], "CHILD_TIMEOUT")
        self.assertIsNone(result["code"])

    def test_failure_serialization_deadline_replaces_stale_refusal(self):
        calls = []
        byte_counts = []
        real_canonical = codegen.canonical

        def serialization(value):
            if isinstance(value, dict) and "failure" in value:
                calls.append(value.get("verdict"))
                if value.get("verdict") == "REQUIREMENT_UNREAD":
                    self.now = 1.01
            serialized = real_canonical(value)
            if isinstance(value, dict) and "failure" in value:
                byte_counts.append(len(serialized.encode("utf-8")))
            return serialized

        failure = ContractError("REQUIREMENT_UNREAD", "reader", "static mock refusal")
        with patch("verantyx.contract_codegen.read_requirements", side_effect=failure), \
                patch("verantyx.contract_codegen.canonical", side_effect=serialization):
            result = ContractCodeGenerator().generate(PY_RAW)
        self.assertIn("REQUIREMENT_UNREAD", calls, "the refusal must also pass serialization accounting")
        self.assertEqual(result["verdict"], "REQUEST_TIMEOUT")
        self.assertEqual(result["failure"]["code"], "REQUEST_TIMEOUT")
        self.assertEqual(result["status"], "held")
        self.assertIsNone(result["code"])
        self.assertEqual(result["budget"]["stop"]["code"], "REQUEST_TIMEOUT")
        self.assertIn("serialization", json.dumps(result["budget"]["stop"]).lower())
        self.assertIn("return_serialization", json.dumps(result))
        self.assertLessEqual(len(calls), 3, "deadline failure must not recurse into unlimited serialization retries")
        usage = result["budget"]["resource_usage"]["serialization"]
        self.assertEqual(usage["calls"], len(calls))
        self.assertEqual(usage["bytes"], sum(byte_counts))
        self.assertGreaterEqual(usage["elapsed_ms"], 1000)
        self.assertIs(result["budget"]["deadline_exceeded"], True)

    def test_failure_serialization_checks_time_even_when_cancelled(self):
        calls = []
        real_canonical = codegen.canonical

        def serialization(value):
            if isinstance(value, dict) and "failure" in value:
                calls.append(value.get("verdict"))
            return real_canonical(value)

        with patch("verantyx.contract_codegen.canonical", side_effect=serialization):
            result = ContractCodeGenerator().generate(PY_RAW, cancel=lambda: True)
        self.assertEqual(result["verdict"], "INTERRUPTED")
        self.assertEqual(result["failure"]["code"], "INTERRUPTED")
        self.assertEqual(result["budget"]["stop"]["code"], "INTERRUPTED")
        self.assertGreaterEqual(len(calls), 1, "external cancellation must not skip failure serialization")
        self.assertEqual(result["budget"]["resource_usage"]["serialization"]["calls"], len(calls))
        self.assertGreater(result["budget"]["resource_usage"]["serialization"]["bytes"], 0)
        self.assertIsNone(result["code"])

    def test_trusted_batch_observer_has_no_unbound_runtime_names(self):
        # Parse trusted runner source as data. Never exec the runner/artifact.
        for profile in ("python_pure_v1", "sqlite_select_v1"):
            with self.subTest(profile=profile):
                program = sandbox._batch_program(profile)
                ast.parse(program)
                module = symtable.symtable(program, "<trusted-batch-review>", "exec")
                observer = next(child for child in module.get_children() if child.get_name() == "observe")
                self.assertTrue(observer.lookup("source").is_parameter())
                scopes = [observer]
                while scopes:
                    scope = scopes.pop()
                    scopes.extend(scope.get_children())
                    for name in scope.get_identifiers():
                        symbol = scope.lookup(name)
                        if not (symbol.is_global() and symbol.is_referenced()):
                            continue
                        if name in vars(builtins):
                            continue
                        try:
                            declared = module.lookup(name)
                        except KeyError:
                            self.fail("trusted runner reads unbound global " + name)
                        self.assertTrue(declared.is_imported() or declared.is_assigned(),
                                        "trusted runner reads unbound global " + name)
                if profile == "python_pure_v1":
                    self.assertTrue(observer.lookup("namespace").is_local())
                    self.assertTrue(observer.lookup("builtins_template").is_parameter())
                else:
                    self.assertTrue(observer.lookup("connection").is_local())

    def test_batch_permit_reservation_is_not_an_observed_start(self):
        permissions = []
        protocol = sandbox._BatchProtocol(12, before_case=lambda: permissions.append("permit"))
        frame = lambda **value: (json.dumps(value) + "\n").encode()
        permit = protocol.feed(frame(event="ready", index=0))
        self.assertEqual(json.loads(permit), {"permit": 0})
        self.assertEqual(permissions, ["permit"])
        self.assertEqual(protocol.stats()["cases_reserved"], 1)
        self.assertEqual(protocol.stats()["cases_attempted"], 0)
        self.assertEqual(protocol.stats()["cases_finished"], 0)
        self.assertEqual(protocol.stats()["cases"], 0)
        self.assertEqual(protocol.stats()["unconfirmed_starts"], 1)
        protocol.feed(frame(event="started", index=0))
        self.assertEqual(protocol.stats()["cases"], 1)
        self.assertEqual(protocol.stats()["cases_finished"], 0)
        self.assertEqual(protocol.stats()["unconfirmed_starts"], 0)
        protocol.feed(frame(event="result", index=0, result={"status": "ARTIFACT_ERROR"}))
        self.assertEqual(protocol.stats()["cases_finished"], 1)
        self.assertEqual(protocol.stats()["cases"], 1)


if __name__ == "__main__":
    unittest.main()
