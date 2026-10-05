"""C1 の変種の一覧を表で出す。使い方: c1_variants.py <ツリー>。鍵の本体は出さない（漏れは「漏れ」とだけ書く）。"""
import importlib.util
import sys

T = sys.argv[1]
sys.path.insert(0, T)
import verantyx
assert verantyx.__file__.startswith(T), verantyx.__file__
from verantyx import ledger_events as L
assert L.__file__.startswith(T)
spec = importlib.util.spec_from_file_location("t7c_tests", T + "/tests/test_w16t7c_redact_variants.py")
M = importlib.util.module_from_spec(spec)
spec.loader.exec_module(M)

bad = 0
print("形\t名前\t件数\t漏れ\t冪等\t出力の先頭40字（印以外は秘密を含まない場合だけ）")
for form, name, text, secrets in M.VARIANTS:
    out, n = L.redact(text)
    leak = bool(M.leaks(out, secrets))
    idem = L.redact(out)[1] == 0
    head = "(漏れ。表示しない)" if leak else out[:40].replace("\n", "\\n")
    print(f"{form}\t{name}\t{n}\t{'漏れ' if leak else '無し'}\t{'冪等' if idem else '非冪等'}\t{head}")
    if leak or n < 1 or not idem:
        bad += 1
print(f"total {len(M.VARIANTS)} bad {bad}")
