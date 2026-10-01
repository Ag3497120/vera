"""Experimental raw -> ledger -> contract -> typed DAG -> checked code API.

Integrators must use this same gate for explicit contract mode and the normal
code intent route, and must not fall back to legacy ANSWER after refusal.
The implementation covers a finite grammar/profile subset, not arbitrary
program synthesis. Public successes are finite verified artifacts.
"""
from __future__ import annotations
import json
import hashlib
import time
from dataclasses import asdict
from .contract_budget import Budget
from .contract_ir import ContractError, VERSION, canonical, digest
from .contract_reader import is_code_request, read_requirements
from .contract_plan import MANIFEST, synthesize
from .contract_lower import lower
from .contract_verify import verify

LANGUAGES={"python_pure_v1":"python","node_commonjs_sync_v1":"javascript",
           "sqlite_select_v1":"sql","posix_numeric_stream_v1":"sh"}
HOLD_REASONS=frozenset(("SANDBOX_UNAVAILABLE","SANDBOX_BUSY","RESOURCE_LIMIT_UNAVAILABLE",
    "RUNTIME_UNAVAILABLE","DESCENDANT_ISOLATION_UNVERIFIED","REQUEST_TIMEOUT","EXECUTION_BUDGET","EXECUTION_INCOMPLETE",
    "TIMEOUT","CHILD_TIMEOUT","CANCELLED","INTERRUPTED","VERIFICATION_BUDGET","VERIFICATION_UNSUPPORTED"))


def _finalize(result, budget, phase):
    """Account for serialization on successful and unsuccessful public returns."""
    budget.check_time("return", phase+" before serialization")
    started=time.monotonic()
    serialized=canonical(result)
    budget.record_serialization(len(serialized.encode("utf-8")),
                                (time.monotonic()-started)*1000, phase)
    budget.check_time("return_serialization", phase+" after serialization")
    result["budget"]=budget.report()
    budget.check_time("return", phase+" final budget snapshot")
    return result


def _minimal_deadline_return(raw, budget, trace, error, source_hash=None):
    # A process can be descheduled past a deadline. Preserve that observation,
    # not an ANSWER or a falsely claimed hard real-time completion. No large
    # source/plan/execution payload is rebuilt after return-time exhaustion.
    result={"verdict":"REQUEST_TIMEOUT","status":"held","code":None,
            "text":"public return deadline exhausted",
            "source_hash":source_hash if source_hash is not None else hashlib.sha256(raw.encode("utf-8","surrogatepass")).hexdigest() if isinstance(raw,str) else None,
            "failure":{"code":"REQUEST_TIMEOUT","stage":error.stage,
                       "message":"public return deadline exhausted","details":budget.stop},
            "budget":budget.report(),"trace":trace}
    started=time.monotonic()
    serialized=canonical(result)
    budget.record_serialization(len(serialized.encode("utf-8")),
                                (time.monotonic()-started)*1000,"compact_timeout")
    result["budget"]=budget.report()
    result["budget"]["deadline_exceeded"] = time.monotonic() >= budget.deadline
    return result


class ContractCodeGenerator:
    def __init__(self,profile=None,*,limits=None,timeout_ms=1000):
        self.profile=profile
        self.limits=limits
        self.timeout_ms=timeout_ms
        self.manifest_sha256=digest(MANIFEST)

    def generate(self,raw,*,cancel=None):
        budget=Budget(limits=self.limits,timeout_ms=self.timeout_ms,cancel=cancel)
        return self._generate(raw,budget)

    def _generate(self,raw,budget):
        trace={"version":VERSION,"sovereign":"contract","registry_sha256":self.manifest_sha256,
               "origin":"raw","development_revision":"r3","stages":[],"legacy_fallback":False}
        source=ledger=contract=plan=artifact=None
        try:
            source,ledger,contract=read_requirements(raw,budget,profile=self.profile)
            trace["stages"].append({"stage":"reader","source_hash":source.hash,"ledger_hash":ledger.hash})
            plan=synthesize(contract,budget)
            trace["stages"].append({"stage":"synthesis","contract_hash":contract.hash,"plan_hash":plan.hash,
                "parts":[{"part":n.part,"law":n.law,"bound_inputs":n.inputs,"output":n.output} for n in plan.nodes]})
            artifact=lower(contract,plan,budget)
            trace["stages"].append({"stage":"lowering","artifact_sha256":artifact.hash})
            certificate=verify(source,ledger,contract,plan,artifact,budget)
            trace["stages"].append({"stage":"verification","status":certificate["status"]})
            result={"verdict":"ANSWER","status":"verified","language":LANGUAGES[contract.profile],
                "profile":contract.profile,"code":artifact.source,
                "text":"有限入力検証を通過したコードです。原文読解の独立採点・全入力の完全証明は未実施です。\n\n"+chr(96)*3+LANGUAGES[contract.profile]+"\n"+artifact.source+"\n"+chr(96)*3,
                "source":asdict(source),"ledger":asdict(ledger),"contract":asdict(contract),"plan":asdict(plan),
                "verification":certificate,"budget":budget.report(),"trace":trace}
            # Include serialization in the public deadline, and return the exact
            # artifact hash checked by the independent runner.
            budget.check("return","final artifact and certificate")
            return _finalize(result,budget,"success")
        except ContractError as error:
            result={"verdict":error.code,"status":"held" if error.code in HOLD_REASONS else "refused",
                "code":None,"text":error.message,"source_hash":source.hash if source else hashlib.sha256(raw.encode("utf-8","surrogatepass")).hexdigest() if isinstance(raw,str) else None,
                "failure":error.to_dict(),"budget":budget.report(),"trace":trace}
            if isinstance(error.details,dict) and "artifact_sha256" in error.details:
                result["verification"]=error.details
            if source is not None: result["source"]=asdict(source)
            if ledger is not None: result["ledger"]=asdict(ledger)
            if contract is not None: result["contract"]=asdict(contract)
            if plan is not None: result["plan"]=asdict(plan)
            # No syntax-only, partial, timeout, cancelled, or unsafe code is
            # exposed as an adoptable artifact.
            try:
                return _finalize(result,budget,"failure")
            except ContractError as deadline_error:
                return _minimal_deadline_return(raw,budget,trace,deadline_error,result.get("source_hash"))


def generate_code(raw,*,profile=None,cancel=None):
    # The convenience entry also charges fresh generator/manifest setup to
    # this ask, rather than starting its deadline after construction.
    budget=Budget(cancel=cancel)
    return ContractCodeGenerator(profile=profile)._generate(raw,budget)


__all__=["ContractCodeGenerator","generate_code","is_code_request"]
