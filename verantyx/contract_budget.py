"""Per-request counters; retries and phase re-entry share the same account."""
from __future__ import annotations
from dataclasses import dataclass
import time
from typing import Callable, Optional
from .contract_ir import ContractError

LIMITS = {"requirements": 32, "symbols": 64, "scopes": 8, "reader": 2048,
          "readings": 16, "synthesis": 8192, "live_states": 128, "plans": 32,
          "nodes": 8, "depth": 8, "proof": 256, "lowering": 512,
          "artifacts": 4, "artifact_bytes": 65536, "verifier": 4096,
          "dynamic_artifacts": 2, "witnesses": 12, "syntax": 4,
          "subprocesses": 28, "child_output_bytes": 1048576}

# Work may stop before the public deadline to leave time for child cleanup and
# both success/failure serialization. This reduces available work, never raises
# the registered 1000 ms deadline or the 200 ms child bound.
RETURN_RESERVE_MS = 50


class Budget:
    def __init__(self, *, limits: Optional[dict] = None, timeout_ms: float = 1000,
                 cancel: Optional[Callable[[], bool]] = None):
        self.limits = dict(LIMITS)
        if limits:
            for key, value in limits.items():
                if key not in self.limits or type(value) is not int or not 0 <= value <= self.limits[key]:
                    raise ValueError("budget overrides can only reduce registered limits")
                self.limits[key] = value
        if not 0 <= timeout_ms <= 1000:
            raise ValueError("deadline cannot exceed registered 1000ms")
        self.used = {key: 0 for key in self.limits}
        self.started = time.monotonic()
        self.deadline = self.started + timeout_ms / 1000
        self.return_reserve_ms = min(RETURN_RESERVE_MS, timeout_ms)
        self.work_deadline = self.deadline - self.return_reserve_ms / 1000
        self.cancel = cancel
        self.stop = None
        self.output_reserved = {}
        self.output_actual = {}
        self.serialization = {"calls": 0, "bytes": 0, "elapsed_ms": 0.0, "phases": []}

    def cancelled(self) -> bool:
        if self.cancel is None: return False
        if hasattr(self.cancel, "is_set"): return bool(self.cancel.is_set())
        return bool(self.cancel()) if callable(self.cancel) else bool(self.cancel)

    def stop_execution(self, code: str, location: str, details=None) -> None:
        record = {"phase": "execution", "location": location, "code": code}
        if details is not None: record["details"] = details
        if self.stop is None: self.stop = record

    def check_time(self, phase: str, location: str = "") -> None:
        """Hard public-deadline gate also used after cancellation/refusal."""
        if time.monotonic() >= self.deadline:
            previous = self.stop
            self.stop = {"phase": phase, "location": location, "code": "REQUEST_TIMEOUT"}
            if previous is not None: self.stop["prior_stop"] = previous
            raise ContractError("REQUEST_TIMEOUT", phase, "public return deadline exhausted", self.stop)

    def check(self, phase: str, location: str = "") -> None:
        code = "INTERRUPTED" if self.cancelled() else "REQUEST_TIMEOUT" if time.monotonic() >= self.work_deadline else ""
        if code:
            self.stop = {"phase": phase, "location": location, "code": code,
                         "return_reserve_ms": self.return_reserve_ms,
                         "deadline_scope": "work_with_public_return_reserve"}
            raise ContractError(code, phase, "request stopped", self.stop)

    def charge(self, key: str, cost: int = 1, location: str = "") -> None:
        self.check(key, location)
        if type(cost) is not int or cost < 0:
            raise ValueError("nonnegative integer cost required")
        following = self.used[key] + cost
        if following > self.limits[key]:
            self.stop = {"phase": key, "location": location, "used": self.used[key],
                         "next_cost": cost, "limit": self.limits[key]}
            code = "READING_BUDGET" if key in ("reader", "readings") else "SYNTHESIS_BUDGET" if key in ("synthesis", "live_states", "plans", "nodes", "depth", "proof") else "VERIFICATION_BUDGET"
            raise ContractError(code, key, "registered budget exhausted", self.stop)
        self.used[key] = following

    def capacity(self, key: str, size: int, location: str = "") -> None:
        """Record peak live resources without resetting accumulated work."""
        if size > self.used[key]:
            self.charge(key, size - self.used[key], location)
        else:
            self.check(key, location)

    def remaining_ms(self) -> float:
        self.check("execution")
        return max(0.0, (self.work_deadline - time.monotonic()) * 1000)

    def charge_output(self, cost: int, child_id: int) -> None:
        """Precharge one child's next bounded pipe read, never all children."""
        self.check("child_output_bytes", "pipe read before I/O")
        if type(cost) is not int or cost < 0 or type(child_id) is not int:
            raise ValueError("child id and output byte cost must be integers")
        current = self.output_reserved.get(child_id, 0)
        following = current + cost
        limit = self.limits["child_output_bytes"]
        if following > limit:
            self.stop = {"phase": "child_output_bytes", "location": "pipe read before I/O",
                         "code": "OUTPUT_LIMIT", "child_id": child_id,
                         "used": current, "next_cost": cost, "limit": limit}
            raise ContractError("OUTPUT_LIMIT", "child_output_bytes", "child output read exceeds registered byte cap", self.stop)
        self.output_reserved[child_id] = following
        self.used["child_output_bytes"] = max(self.used["child_output_bytes"], following)

    def record_output(self, cost: int, child_id: int) -> None:
        """Record actual receive bytes separately from pre-read reservations."""
        if type(cost) is not int or cost < 0 or type(child_id) is not int:
            raise ValueError("child id and output byte cost must be integers")
        following = self.output_actual.get(child_id, 0) + cost
        if following > self.output_reserved.get(child_id, 0):
            self.stop_execution("VERIFICATION_FAILED", "unreserved output receive", {"child_id": child_id, "actual_bytes": following})
            raise ContractError("VERIFICATION_FAILED", "child_output_bytes", "pipe receive was not precharged", self.stop)
        self.output_actual[child_id] = following

    def record_serialization(self, byte_count: int, elapsed_ms: float, phase: str) -> None:
        self.serialization["calls"] += 1
        self.serialization["bytes"] += byte_count
        self.serialization["elapsed_ms"] += elapsed_ms
        self.serialization["phases"].append(phase)

    def report(self) -> dict:
        logical = sum(self.used[k] for k in ("reader", "synthesis", "lowering", "verifier"))
        return {"used": dict(self.used), "limits": dict(self.limits), "logical_work": logical,
                "elapsed_ms": (time.monotonic() - self.started) * 1000, "stop": self.stop,
                "resource_usage": {"child_output_bytes": {
                    "limit_scope": "per_child_stdout_plus_stderr",
                    "used_counter_scope": "peak_precharged_child_bytes",
                    "reserved_total": sum(self.output_reserved.values()),
                    "reserved_by_child": dict(self.output_reserved),
                    "actual_total": sum(self.output_actual.values()),
                    "actual_by_child": dict(self.output_actual),
                    "peak_actual_bytes": max(self.output_actual.values(), default=0)},
                    "serialization": {**self.serialization,
                                      "phases": list(self.serialization["phases"])}}}
