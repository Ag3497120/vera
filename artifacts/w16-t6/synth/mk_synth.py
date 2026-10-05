"""W16-t6: 合成の報告 40 件の生成器（実装 `verantyx/attest.py` を書く前に書いて凍結する。attest.py を import しない）。

出力: cases.jsonl（件ごとの fixture・報告・台帳・フラグ）と expected.jsonl（申告ごと・事実ごとの期待の印と理由と truth）。
fixture は JSON の中に文字列として持つ（`test_*.py` 等の名前のファイルを artifacts に置かない）。実体化はテスト／測定側で tmp に行う。
期待は構成から決める（実装の出力を写さない）。台帳の連鎖は docs/ATTEST.md の仮定の規則で自前に計算する。
"""
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

OUT = Path(__file__).resolve().parent


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mk_test(n_pass, n_fail=0):
    body = ["# synthetic fixture test"]
    for i in range(n_pass):
        body.append("def test_k%d():\n    assert %d + 1 == %d\n" % (i, i, i + 1))
    for i in range(n_fail):
        body.append("def test_f%d():\n    assert 1 == 2\n" % i)
    return "\n".join(body) + "\n"


def ledger_rows(events):
    """events: [(kind, data)] -> rows chained by the assumed rule of docs/ATTEST.md."""
    rows, prev = [], None
    for i, (kind, data) in enumerate(events):
        row = {"ts": "2026-10-05T22:%02d:00+09:00" % i, "kind": kind, "actor": "synth", "data": data, "prev": prev}
        body = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        row["sha"] = hashlib.sha256(body.encode("utf-8")).hexdigest()
        prev = row["sha"]
        rows.append(row)
    return rows


class Case:
    def __init__(self, cid, group, note, rerun=False, ledger=None, base=False, has_json=True, fullwidth=True):
        self.id, self.group, self.note = cid, group, note
        self.files, self.git_base = {"pytest.ini": ""}, None
        self.rerun, self.ledger_events, self.base, self.has_json, self.fw = rerun, ledger, base, has_json, fullwidth
        self.vlines, self.claims_json, self.exp_claims, self.offform = [], [], [], 0
        self.pre = "# 実装報告 %s\n\n本文。作業の説明（この文には申告は含まれない。3 つの節に分けた）。\n\n" % cid
        self.extra_tail = ""
        self.free_only = False
        self.ledger_cmds = {}

    # ---- helpers
    def _p(self, s):
        return s.replace("(", "（").replace(")", "）") if self.fw else s

    def exit_mode(self):
        return "ledger" if self.ledger_events is not None else ("rerun" if self.rerun else "none")

    # ---- claim builders. each appends the V line, the JSON claim(s) and the expected facts
    def acceptance(self, cid, cmd, claimed_exit, actual_exit, out=None, out_content=None, claimed_sha=None, allowed=True):
        mode = self.exit_mode()
        facts = []
        if not allowed and self.rerun:
            facts.append({"sig": "exit:" + cmd, "truth": "unknown", "mark": "TESTIMONY", "reason": "COMMAND_NOT_ALLOWED"})
        elif mode == "none":
            facts.append({"sig": "exit:" + cmd, "truth": "unknown", "mark": "TESTIMONY", "reason": "NO_EVENT"})
        elif claimed_exit == actual_exit:
            facts.append({"sig": "exit:" + cmd, "truth": "true", "mark": "RECORD", "reason": "MATCH"})
        else:
            facts.append({"sig": "exit:" + cmd, "truth": "false", "mark": "MISMATCH", "reason": "EXIT_CODE_DIFFERS"})
        line = "- 受入 %s: `%s` を実行し、終了コード %d" % (cid, cmd, claimed_exit)
        jc = {"kind": "acceptance", "id": cid, "command": cmd, "exit_code": claimed_exit}
        if out is not None:
            self.files[out] = out_content
            true_sha = sha(out_content)
            cs = claimed_sha if claimed_sha is not None else true_sha
            line += "、出力 " + out + self._p("(sha256 %s)" % cs)
            jc["output"] = {"path": out, "sha256": cs}
            facts.append(self._sha_fact(out, cs, true_sha))
        self.vlines.append(line + "。")
        self.claims_json.append(jc)
        self.exp_claims.append({"kind": "acceptance", "facts": facts})

    @staticmethod
    def _sha_fact(path, claimed, true_sha):
        sig = "file_sha:" + path
        if len(claimed.rstrip(".…")) < 12:
            return {"sig": sig, "truth": "unknown", "mark": "TESTIMONY", "reason": "SHA_TOO_SHORT"}
        if true_sha.startswith(claimed.rstrip(".…")):
            return {"sig": sig, "truth": "true", "mark": "RECORD", "reason": "MATCH"}
        return {"sig": sig, "truth": "false", "mark": "MISMATCH", "reason": "SHA_DIFFERS"}

    def changed(self, items):
        """items: [(path, claimed_sha or None (=true), final_content, base_content or None)]"""
        parts, jfiles = [], []
        for path, claimed, final, basec in items:
            self.files[path] = final
            if basec is not None:
                self.git_base = self.git_base or {"pytest.ini": ""}
                self.git_base[path] = basec
            true_sha = sha(final)
            cs = claimed if claimed is not None else true_sha
            parts.append(path + self._p("(sha256 %s)" % cs))
            jfiles.append({"path": path, "sha256": cs})
            if self.base:
                if basec is not None and basec == final:
                    cf = {"sig": "changed:" + path, "truth": "false", "mark": "MISMATCH", "reason": "NOT_CHANGED_SINCE_BASE"}
                else:
                    cf = {"sig": "changed:" + path, "truth": "true", "mark": "RECORD", "reason": "MATCH"}
            else:
                cf = {"sig": "changed:" + path, "truth": "unknown", "mark": "TESTIMONY", "reason": "NO_BASE"}
            self.exp_claims.append({"kind": "changed", "facts": [self._sha_fact(path, cs, true_sha), cf]})
        self.vlines.append("- 変更: " + "、".join(parts) + "。")
        self.claims_json.append({"kind": "changed", "files": jfiles})

    def tests_added(self, path, claimed_n, real_pass=0, real_fail=0, exist=True):
        mode = self.exit_mode()
        facts = []
        if exist:
            self.files[path] = mk_test(real_pass, real_fail)
            facts.append({"sig": "test_exists:" + path, "truth": "true", "mark": "RECORD", "reason": "MATCH"})
            if claimed_n == real_pass + real_fail:
                facts.append({"sig": "test_count:" + path, "truth": "true", "mark": "RECORD", "reason": "MATCH"})
            else:
                facts.append({"sig": "test_count:" + path, "truth": "false", "mark": "MISMATCH", "reason": "COUNT_DIFFERS"})
            if mode == "none":
                facts.append({"sig": "test_passed:" + path, "truth": "unknown", "mark": "TESTIMONY", "reason": "NO_EVENT"})
            elif real_fail == 0:
                facts.append({"sig": "test_passed:" + path, "truth": "true", "mark": "RECORD", "reason": "MATCH"})
            else:
                facts.append({"sig": "test_passed:" + path, "truth": "false", "mark": "MISMATCH", "reason": "EXIT_CODE_DIFFERS"})
        else:
            facts.append({"sig": "test_exists:" + path, "truth": "false", "mark": "MISMATCH", "reason": "TEST_NOT_FOUND"})
        self.vlines.append("- 追加したテスト: %s の %d 件が通った。" % (path, claimed_n))
        self.claims_json.append({"kind": "tests_added", "path": path, "count": claimed_n, "passed": True})
        self.exp_claims.append({"kind": "tests_added", "facts": facts})

    def number(self, cid, text, path, content, present):
        self.files[path] = content
        if present:
            f = {"sig": "number:%s@%s" % (unicodedata.normalize("NFKC", text), path), "truth": "true", "mark": "RECORD", "reason": "MATCH"}
        else:
            f = {"sig": "number:%s@%s" % (unicodedata.normalize("NFKC", text), path), "truth": "false", "mark": "MISMATCH", "reason": "NUMBER_NOT_IN_OUTPUT"}
        self.vlines.append("- 数値 %s: 「%s」は %s にある。" % (cid, text, path))
        self.claims_json.append({"kind": "number", "id": cid, "text": text, "path": path})
        self.exp_claims.append({"kind": "number", "facts": [f]})

    def raw_claim(self, vline, jclaim, claim_expected):
        self.vlines.append(vline)
        if jclaim is not None:
            self.claims_json.append(jclaim)
        if claim_expected is not None:
            self.exp_claims.append(claim_expected)

    def build(self):
        if self.free_only:
            report = self.pre + self.extra_tail
        else:
            report = self.pre + "完了:\n" + "\n".join(self.vlines) + "\n"
            if self.has_json:
                report += "\n```json\n" + json.dumps({"attest": 1, "claims": self.claims_json}, ensure_ascii=False, indent=1) + "\n```\n"
            report += self.extra_tail
        led = ledger_rows(self.ledger_events) if self.ledger_events is not None else None
        case = {"id": self.id, "group": self.group, "note": self.note, "files": self.files, "git_base": self.git_base, "ledger": led,
                "flags": {"rerun": self.rerun, "base": "HEAD" if self.base else None}, "report": report, "has_json": self.has_json and not self.free_only}
        exp = {"id": self.id, "claims": self.exp_claims, "offform": self.offform}
        return case, exp


def main():
    cases = []

    def new(cid, group, note, **kw):
        c = Case(cid, group, note, fullwidth=(len(cases) % 2 == 0), **kw)
        cases.append(c)
        return c

    OUTTXT = "結果: 12 passed, 3 skipped\n経過 1.5 秒\n行数 1,234\n精度 0.95\n"
    # ---- A: true claims only (13)
    c = new("S01", "A", "acceptance rerun, exit 0, output sha", rerun=True)
    c.files["tests/test_a.py"] = mk_test(3); c.acceptance("T1-1", "pytest -q tests/test_a.py", 0, 0, "out/t1.txt", OUTTXT)
    c = new("S02", "A", "acceptance rerun, python -m form with -x", rerun=True)
    c.files["tests/test_b.py"] = mk_test(2); c.acceptance("T1-2", "python -m pytest -q -x tests/test_b.py", 0, 0, "out/t2.txt", "2 passed\n")
    c = new("S03", "A", "acceptance rerun, node id", rerun=True)
    c.files["tests/test_c.py"] = mk_test(3); c.acceptance("T1-3", "python3 -m pytest -q tests/test_c.py::test_k1", 0, 0)
    c = new("S04", "A", "acceptance rerun, failing test, exit 1 claimed and true", rerun=True)
    c.files["tests/test_f.py"] = mk_test(1, 1); c.acceptance("T1-4", "pytest -q tests/test_f.py", 1, 1, "out/t4.txt", "1 failed, 1 passed\n")
    c = new("S05", "A", "acceptance by ledger, exit 0", ledger=[("note", {"text": "start"}), ("test_run", {"cmd": "python -m pytest -q tests/test_a.py", "exit_code": 0})])
    c.acceptance("T2-1", "python -m pytest -q tests/test_a.py", 0, 0, "out/t5.txt", "3 passed\n")
    c = new("S06", "A", "acceptance by ledger, exit 2 (process_exit, returncode)", ledger=[("process_exit", {"argv": ["python", "-m", "verantyx.tool", "run"], "returncode": 2})])
    c.acceptance("T2-2", "python -m verantyx.tool run", 2, 2)
    c = new("S07", "A", "changed one file vs base", base=True)
    c.changed([("pkg/a.py", None, "def a():\n    return 2\n", "def a():\n    return 1\n")])
    c = new("S08", "A", "changed two files, one new", base=True)
    c.changed([("pkg/b.py", None, "B = 2\n", "B = 1\n"), ("pkg/new.py", None, "N = 1\n", None)])
    c = new("S09", "A", "tests_added rerun", rerun=True)
    c.tests_added("tests/test_d.py", 4, real_pass=4)
    c = new("S10", "A", "tests_added by ledger", ledger=[("test_run", {"cmd": "pytest -q tests/test_e.py", "exit_code": 0})])
    c.tests_added("tests/test_e.py", 2, real_pass=2)
    c = new("S11", "A", "number with thousands comma")
    c.number("T3-1", "1,234 行を処理", "out/m.txt", OUTTXT, True)
    c = new("S12", "A", "number fullwidth and decimal")
    c.number("T3-2", "精度 0.95、３ 件を除外", "out/m2.txt", OUTTXT, True)
    c = new("S13", "A", "full mixed, all true", rerun=True, base=True)
    c.files["tests/test_g.py"] = mk_test(5)
    c.acceptance("T4-1", "pytest -q tests/test_g.py", 0, 0, "out/g.txt", OUTTXT)
    c.changed([("pkg/g.py", None, "G = 2\n", "G = 1\n")])
    c.tests_added("tests/test_g.py", 5, real_pass=5)
    c.number("T4-2", "12 passed", "out/g.txt", OUTTXT, True)
    # ---- B: false claims (21)
    wrong = sha("not the file")
    c = new("S14", "B", "fake: output sha differs", rerun=True)
    c.files["tests/test_a.py"] = mk_test(1); c.acceptance("T5-1", "pytest -q tests/test_a.py", 0, 0, "out/x.txt", "ok 1\n", claimed_sha=wrong)
    c = new("S15", "B", "fake: output sha differs by one hex digit", rerun=True)
    c.files["tests/test_a.py"] = mk_test(1)
    real = sha("ok 2\n"); alt = real[:-1] + ("0" if real[-1] != "0" else "1")
    c.acceptance("T5-2", "pytest -q tests/test_a.py", 0, 0, "out/y.txt", "ok 2\n", claimed_sha=alt)
    c = new("S16", "B", "fake: changed sha differs", base=True)
    c.changed([("pkg/c.py", wrong, "C = 2\n", "C = 1\n")])
    c = new("S17", "B", "fake: changed sha is the base content's sha", base=True)
    c.changed([("pkg/d.py", sha("D = 1\n"), "D = 2\n", "D = 1\n")])
    c = new("S18", "B", "fake: count too large (rerun)", rerun=True); c.tests_added("tests/test_h.py", 7, real_pass=5)
    c = new("S19", "B", "fake: count too small (ledger)", ledger=[("test_run", {"cmd": "pytest -q tests/test_i.py", "exit_code": 0})]); c.tests_added("tests/test_i.py", 1, real_pass=4)
    c = new("S20", "B", "fake: count off by one (rerun)", rerun=True); c.tests_added("tests/test_j.py", 3, real_pass=2)
    c = new("S21", "B", "fake: count (no event source)"); c.tests_added("tests/test_k.py", 10, real_pass=9)
    c = new("S22", "B", "fake: test file does not exist (rerun)", rerun=True); c.tests_added("tests/test_ghost1.py", 6, exist=False)
    c = new("S23", "B", "fake: test file does not exist (no event)"); c.tests_added("tests/test_ghost2.py", 2, exist=False)
    c = new("S24", "B", "fake: test file does not exist, but a similar file exists", rerun=True)
    c.files["tests/test_real.py"] = mk_test(2); c.tests_added("tests/test_reel.py", 2, exist=False)
    c = new("S25", "B", "fake: test claimed outside tests/ name, absent", ledger=[("test_run", {"cmd": "pytest -q tests/test_ghost4.py", "exit_code": 0})])
    c.tests_added("tests/sub/test_ghost4.py", 3, exist=False)
    c = new("S26", "B", "fake: exit 0 claimed, ledger says 1", ledger=[("test_run", {"cmd": "python -m pytest -q tests/test_a.py", "exit_code": 1})])
    c.acceptance("T6-1", "python -m pytest -q tests/test_a.py", 0, 1)
    c = new("S27", "B", "fake: exit 0 claimed, ledger says 2", ledger=[("note", {"text": "x"}), ("process_exit", {"cmd": "python -m verantyx.tool run", "exit_code": 2})])
    c.acceptance("T6-2", "python -m verantyx.tool run", 0, 2)
    c = new("S28", "B", "fake: exit 0 claimed, rerun fails (exit 1)", rerun=True)
    c.files["tests/test_f.py"] = mk_test(1, 1); c.acceptance("T6-3", "pytest -q tests/test_f.py", 0, 1)
    c = new("S29", "B", "fake: exit 1 claimed, rerun passes (exit 0)", rerun=True)
    c.files["tests/test_a.py"] = mk_test(2); c.acceptance("T6-4", "pytest -q tests/test_a.py", 1, 0)
    c = new("S30", "B", "fake: number absent", ); c.number("T7-1", "98 件を処理", "out/n1.txt", OUTTXT, False)
    c = new("S31", "B", "fake: 12 claimed, file has 120 only"); c.number("T7-2", "12 件", "out/n2.txt", "total 120 rows\n", False)
    c = new("S32", "B", "fake: 0 claimed, file has 0.95 only"); c.number("T7-3", "失敗 0 件", "out/n3.txt", "精度 0.95\n", False)
    c = new("S33", "B", "fake: decimal fabricated"); c.number("T7-4", "経過 3.5 秒", "out/n4.txt", OUTTXT, False)
    c = new("S34", "B", "mixed: true acceptance, fake changed sha, fake count, true number", rerun=True, base=True)
    c.files["tests/test_m.py"] = mk_test(3)
    c.acceptance("T8-1", "pytest -q tests/test_m.py", 0, 0, "out/m.txt", "3 passed\n")
    c.changed([("pkg/m.py", wrong, "M = 2\n", "M = 1\n")])
    c.tests_added("tests/test_m.py", 4, real_pass=3)
    c.number("T8-2", "3 passed", "out/m.txt", "3 passed\n", True)
    # ---- C: unverifiable by design (6)
    c = new("S35", "C", "off-form bullet (V only), plus one good ledger claim", ledger=[("test_run", {"cmd": "pytest -q tests/test_a.py", "exit_code": 0})], has_json=False)
    c.acceptance("T9-1", "pytest -q tests/test_a.py", 0, 0)
    c.vlines.append("- すべて完了しました。問題はありません"); c.offform = 1
    c = new("S36", "C", "paths outside the tree", base=True)
    c.raw_claim("- 変更: /etc/hosts" + c._p("(sha256 %s)" % sha("x")) + "。", {"kind": "changed", "files": [{"path": "/etc/hosts", "sha256": sha("x")}]},
                {"kind": "changed", "facts": [{"sig": "file_sha:/etc/hosts", "truth": "unknown", "mark": "TESTIMONY", "reason": "PATH_OUTSIDE_TREE"},
                                              {"sig": "changed:/etc/hosts", "truth": "unknown", "mark": "TESTIMONY", "reason": "PATH_OUTSIDE_TREE"}]})
    c.raw_claim("- 受入 T9-2: `pytest -q tests/test_a.py` を実行し、終了コード 0、出力 ../outside.txt" + c._p("(sha256 %s)" % sha("y")) + "。",
                {"kind": "acceptance", "id": "T9-2", "command": "pytest -q tests/test_a.py", "exit_code": 0, "output": {"path": "../outside.txt", "sha256": sha("y")}},
                {"kind": "acceptance", "facts": [{"sig": "exit:pytest -q tests/test_a.py", "truth": "unknown", "mark": "TESTIMONY", "reason": "NO_EVENT"},
                                                 {"sig": "file_sha:../outside.txt", "truth": "unknown", "mark": "TESTIMONY", "reason": "PATH_OUTSIDE_TREE"}]})
    c = new("S37", "C", "abbreviated sha (the ticket's own example form)", rerun=True)
    c.files["tests/test_a.py"] = mk_test(1); c.acceptance("T9-3", "pytest -q tests/test_a.py", 0, 0, "out/short.txt", "ok\n", claimed_sha="1a2b...")
    c = new("S38", "C", "no event source: exit and passed stay testimony")
    c.acceptance("T9-4", "pytest -q tests/test_a.py", 0, 0); c.tests_added("tests/test_n.py", 2, real_pass=2)
    c = new("S39", "C", "no completion section at all", has_json=False)
    c.free_only = True; c.extra_tail = "テストはすべて通りました。完了です。出力は out/z.txt にあります。\n"
    c = new("S40", "C", "rerun refuses commands outside the allowed forms", rerun=True)
    c.acceptance("T9-5", 'bash -c "echo hi"', 0, 0, allowed=False)
    c.acceptance("T9-6", "pytest -q tests/test_a.py; rm -rf /", 0, 0, allowed=False)

    built = [x.build() for x in cases]
    with open(OUT / "cases.jsonl", "w", encoding="utf-8") as f:
        for case, _ in built:
            f.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT / "expected.jsonl", "w", encoding="utf-8") as f:
        for _, exp in built:
            f.write(json.dumps(exp, ensure_ascii=False, sort_keys=True) + "\n")
    print("cases", len(built), file=sys.stderr)


if __name__ == "__main__":
    main()
