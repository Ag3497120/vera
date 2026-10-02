"""Independent r3 public-boundary regressions; no generated source executes.

These fixtures are authored from documented contracts, not B80/sealed inputs.
The reviewer only wrote/read this file. Execution belongs to the parent's one
worker. A passing mocked control is evidence of gate consistency, not actual
OS isolation, public latency, descendant containment, or general synthesis.
"""
from copy import deepcopy
import builtins
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

from verantyx import contract_sandbox as sandbox
from verantyx.contract_budget import Budget
from verantyx.contract_codegen import ContractCodeGenerator, HOLD_REASONS
from verantyx.contract_ir import ContractError
from verantyx.contract_lower import lower
from verantyx.contract_plan import synthesize
from verantyx.contract_reader import read_requirements
from verantyx.contract_verify import interpret, select_witnesses, verify


RAW = ("Python function f(items); input items: Seq[Int[-10..10]], "
       "length 0..32; finally return sum")
DESCENDANT_SCOPE = ("owned new-session PGID; "
                    "process-fork denial observed by trusted probe")


def complete_cleanup(child_id):
    return {"child_id": child_id, "group_signalled": True,
            "leader_reaped": True, "group_absence_confirmed": True,
            "cleanup_error": None, "deadline_exceeded": False,
            "launches": 1, "output_bytes": 0, "output_reserved_bytes": 0}


class FakePipe:
    """No actual descriptor; set_blocking is mocked whenever this is used."""
    def __init__(self, number, close_error=None):
        self.number = number
        self.close_error = close_error
        self.closed = False
        self.close_attempts = 0

    def fileno(self):
        return self.number

    def close(self):
        self.close_attempts += 1
        if self.close_error is not None:
            raise self.close_error
        self.closed = True


class FakeProcess:
    def __init__(self, stdin_error=None):
        self.pid = 23003
        self.stdin = FakePipe(61001, stdin_error)
        self.stdout = FakePipe(61002)
        self.stderr = FakePipe(61003)
        self.returncode = 0

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode


class FakeSelector:
    def __init__(self, registration_error=None, close_error=None):
        self.registration_error = registration_error
        self.close_error = close_error
        self.close_attempts = 0

    def register(self, *args):
        if self.registration_error is not None:
            raise self.registration_error

    def get_map(self):
        return {}

    def close(self):
        self.close_attempts += 1
        if self.close_error is not None:
            raise self.close_error


class ContractR3IndependentReviewTests(unittest.TestCase):
    def setUp(self):
        # A deterministic clock only isolates the mocked gates from machine
        # load; its zero timings must never be called latency measurements.
        clock = patch("verantyx.contract_budget.time.monotonic", return_value=0.0)
        clock.start()
        self.addCleanup(clock.stop)
        no_launch = patch.object(sandbox.subprocess, "Popen",
                                 side_effect=AssertionError("review must not launch a real child"))
        no_launch.start()
        self.addCleanup(no_launch.stop)

    def objects(self):
        source, ledger, contract = read_requirements(RAW)
        plan = synthesize(contract)
        artifact = lower(contract, plan, Budget())
        return source, ledger, contract, plan, artifact

    def runner_mock(self, contract, artifact, change=None):
        selections = select_witnesses(contract, Budget())
        expected = [interpret(contract, bindings, Budget())
                    for _, bindings in selections]

        def run(profile, source, interface, cases, **hooks):
            self.assertEqual(profile, contract.profile)
            self.assertEqual(source, artifact.source)
            self.assertEqual(cases, [case for case, _ in selections])
            for _ in range(2):
                hooks["before_launch"]()
            for _ in cases:
                hooks["before_case"]()
            probe = complete_cleanup(23001)
            child = complete_cleanup(23002)
            result = {
                "status": "EXECUTED", "artifact_sha256": artifact.hash,
                "isolation": {
                    "verified": True, "fork_denied": True,
                    "descendant_scope": DESCENDANT_SCOPE,
                    "probe_cleanup": deepcopy(probe),
                    "checks": {name: True for name in (
                        "external_read", "external_write", "local_write",
                        "network", "unlisted_exec", "fork_denied")}},
                "stats": {"launches": 2, "cases": len(cases),
                          "cases_reserved": len(cases),
                          "cases_attempted": len(cases),
                          "cases_finished": len(cases), "unconfirmed_starts": 0,
                          "output_bytes": 0, "output_reserved_bytes": 0,
                          "children": [
                              {"child_id": 23001, "status": "EXECUTED",
                               "output_bytes": 0, "output_reserved_bytes": 0,
                               "cleanup": deepcopy(probe)},
                              {"child_id": 23002, "status": "EXECUTED",
                               "output_bytes": 0, "output_reserved_bytes": 0,
                               "cleanup": deepcopy(child)}]},
                "results": [
                    {"index": i, "status": "EXECUTED", "exit_code": 0,
                     "stdout": "", "stderr": "", "process_stderr": "",
                     "signature": "(items)", "signature_matches": True,
                     "mutation": {"unchanged": True}, "value": value,
                     "typed_value": {"type": "int", "value": value},
                     "process_group_reaped": True, "cleanup": deepcopy(child)}
                    for i, value in enumerate(expected)]}
            if change is not None:
                change(result)
            return result
        return run

    def test_complete_control_and_rehashed_comment_artifact_are_finite_only(self):
        source, ledger, contract, plan, artifact = self.objects()
        # The source SHA must be recomputed. This safe comment mutation is a
        # control demonstrating that subsequent rejection is cleanup-related.
        changed = replace(artifact, source=artifact.source + "\n# r3 review control\n")
        self.assertNotEqual(changed.hash, artifact.hash)
        with patch("verantyx.contract_verify.run_artifact",
                   side_effect=self.runner_mock(contract, changed)):
            result = verify(source, ledger, contract, plan, changed, Budget())
        self.assertEqual(result["status"], "finite_verified")
        self.assertFalse(result["universal_proof"])
        self.assertEqual(result["artifact_sha256"], changed.hash)

    def test_recomputed_hash_and_correct_values_do_not_replace_cleanup_evidence(self):
        source, ledger, contract, plan, artifact = self.objects()
        artifact = replace(artifact, source=artifact.source + "\n# r3 rehashed input\n")

        def no_probe_evidence(result):
            result["isolation"].pop("probe_cleanup")

        def group_still_present(result):
            result["stats"]["children"][1]["cleanup"]["group_absence_confirmed"] = False

        def group_probe_permission_denied(result):
            result["results"][0]["cleanup"]["cleanup_error"] = [
                {"stage": "group_probe", "type": "PermissionError",
                 "message": "presence/absence could not be observed"}]

        def missing_leader_evidence(result):
            result["stats"]["children"][1]["cleanup"].pop("leader_reaped")

        def expired_cleanup(result):
            result["results"][0]["cleanup"]["deadline_exceeded"] = True

        for name, change in (
            ("probe_missing", no_probe_evidence),
            ("owned_group_present", group_still_present),
            ("group_observation_denied", group_probe_permission_denied),
            ("leader_unknown", missing_leader_evidence),
            ("cleanup_deadline", expired_cleanup)):
            with self.subTest(evidence=name), patch(
                    "verantyx.contract_verify.run_artifact",
                    side_effect=self.runner_mock(contract, artifact, change)):
                with self.assertRaises(ContractError):
                    verify(source, ledger, contract, plan, artifact, Budget())

    def test_correct_values_do_not_replace_fork_scope_evidence(self):
        source, ledger, contract, plan, artifact = self.objects()

        def missing_fork(result):
            result["isolation"].pop("fork_denied")

        def observed_fork_allowed(result):
            result["isolation"]["checks"]["fork_denied"] = False

        def wrong_scope(result):
            result["isolation"]["descendant_scope"] = "leader wait only"

        for name, change in (("missing", missing_fork),
                             ("allowed", observed_fork_allowed),
                             ("unknown_scope", wrong_scope)):
            with self.subTest(fork=name), patch(
                    "verantyx.contract_verify.run_artifact",
                    side_effect=self.runner_mock(contract, artifact, change)):
                with self.assertRaises(ContractError):
                    verify(source, ledger, contract, plan, artifact, Budget())

    def public_spawn_mock(self, selector, process, constructor_error=None):
        def run(profile, source, interface, cases, **hooks):
            with patch.object(sandbox.subprocess, "Popen", return_value=process), \
                    patch.object(sandbox.selectors, "DefaultSelector",
                                 side_effect=constructor_error,
                                 return_value=selector), \
                    patch.object(sandbox.os, "set_blocking"), \
                    patch.object(sandbox, "_kill_group",
                                 return_value=complete_cleanup(process.pid)) as kill:
                self.kill = kill
                return sandbox._spawn(Path("/mock-contract-root"),
                                      Path("/mock-policy.sb"), [], b"", 200,
                                      1048576, None, hooks["before_launch"],
                                      deadline=hooks["deadline"])
        return run

    def test_selector_environment_errors_have_typed_public_failure_and_cleanup(self):
        for stage, error in (("register", ValueError("closed fake stream")),
                             ("register", KeyError("selector fake registration")),
                             ("construct", RuntimeError("selector fake constructor"))):
            with self.subTest(stage=stage, error=type(error).__name__):
                child = FakeProcess()
                selector = FakeSelector(registration_error=error if stage == "register" else None)
                runner = self.public_spawn_mock(selector, child,
                                                error if stage == "construct" else None)
                with patch("verantyx.contract_verify.run_artifact", side_effect=runner):
                    result = ContractCodeGenerator().generate(RAW)
                self.assertEqual(result["verdict"], "SANDBOX_UNAVAILABLE")
                self.assertEqual(result["status"], "held")
                self.assertIsNone(result["code"])
                self.assertEqual(result["budget"]["used"]["subprocesses"], 1)
                self.kill.assert_called_once()
                self.assertTrue(all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr)))
                execution = result["verification"]["execution"]
                self.assertEqual(execution["prior_status"], "SANDBOX_UNAVAILABLE")
                self.assertIn(type(error).__name__,
                              [event.get("type") for event in execution["trace"]])

    def test_selector_and_pipe_close_failures_preserve_remaining_closes_and_public_evidence(self):
        child = FakeProcess(stdin_error=OSError("fake stdin close failed"))
        selector = FakeSelector(close_error=RuntimeError("fake selector close failed"))
        with patch("verantyx.contract_verify.run_artifact",
                   side_effect=self.public_spawn_mock(selector, child)):
            result = ContractCodeGenerator().generate(RAW)
        self.assertEqual(result["verdict"], "EXECUTION_INCOMPLETE")
        self.assertEqual(result["status"], "held")
        self.assertIsNone(result["code"])
        self.kill.assert_called_once()
        self.assertEqual(selector.close_attempts, 1)
        self.assertEqual([pipe.close_attempts for pipe in (child.stdin, child.stdout, child.stderr)], [1, 1, 1])
        self.assertTrue(child.stdout.closed and child.stderr.closed)
        execution = result["verification"]["execution"]
        self.assertEqual(execution["prior_status"], "EXECUTED")
        self.assertFalse(execution["process_group_reaped"])
        self.assertEqual({e["stage"] for e in execution["cleanup"]["cleanup_error"]},
                         {"selector_close", "close_stdin"})

    def test_fork_capable_shell_is_held_before_launch(self):
        with patch.object(sandbox, "_spawn") as spawn:
            result = sandbox.run_artifact(
                "posix_numeric_stream_v1", "/usr/bin/awk '{print $1}'",
                {}, [{"stdin": "1\n", "argv": []}])
        self.assertEqual(result["status"], "DESCENDANT_ISOLATION_UNVERIFIED")
        self.assertIsNone(result["code"])
        self.assertEqual(result["stats"]["launches"], 0)
        spawn.assert_not_called()
        self.assertIn(result["status"], HOLD_REASONS)

    def test_child_return_cap_includes_successful_cleanup_and_close(self):
        child = FakeProcess()
        selector = FakeSelector()
        clock = [0.0]

        def slow_confirmed_cleanup(*args, **kwargs):
            # The process/group evidence can complete under the public 1000ms
            # deadline while the child entry-to-return time exceeds 200ms.
            clock[0] = 0.250
            return complete_cleanup(child.pid)

        with patch.object(sandbox.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(sandbox.subprocess, "Popen", return_value=child), \
                patch.object(sandbox.selectors, "DefaultSelector", return_value=selector), \
                patch.object(sandbox.os, "set_blocking"), \
                patch.object(sandbox, "_kill_group", side_effect=slow_confirmed_cleanup):
            result = sandbox._spawn(Path("/mock-contract-root"),
                                    Path("/mock-policy.sb"), [], b"", 200,
                                    1048576, None, deadline=1.0)
        self.assertNotEqual(result["status"], "EXECUTED",
                            "a completed cleanup cannot waive registered child return time")
        self.assertGreaterEqual(result["elapsed_ms"], 250)
        self.assertTrue(all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr)))

    def test_child_return_cap_is_checked_after_output_decode(self):
        child = FakeProcess()
        clock = [0.0]

        def slow_bytes(value):
            clock[0] = 0.250
            return builtins.bytes(value)

        with patch.object(sandbox.time, "monotonic", side_effect=lambda: clock[0]), \
                patch.object(sandbox.subprocess, "Popen", return_value=child), \
                patch.object(sandbox.selectors, "DefaultSelector", return_value=FakeSelector()), \
                patch.object(sandbox.os, "set_blocking"), \
                patch.object(sandbox, "_kill_group", return_value=complete_cleanup(child.pid)), \
                patch.object(sandbox, "bytes", side_effect=slow_bytes, create=True):
            result = sandbox._spawn(Path("/mock-contract-root"), Path("/mock-policy.sb"),
                                    [], b"", 200, 1048576, None, deadline=1.0)
        self.assertEqual(result["status"], "CHILD_TIMEOUT")
        self.assertTrue(result["cleanup"]["child_deadline_exceeded"])
        self.assertGreaterEqual(result["elapsed_ms"], 250)
        self.assertTrue(all(pipe.closed for pipe in (child.stdin, child.stdout, child.stderr)))


if __name__ == "__main__":
    unittest.main()
