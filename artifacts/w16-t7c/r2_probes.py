"""第 2 ラウンドの追加の探り（レビュー R1）。使い方: r2_probes.py <ツリー>。鍵の本体は出さない。"""
import base64, sys
sys.path.insert(0, sys.argv[1])
import verantyx.ledger_events as L
assert L.__file__.startswith(sys.argv[1])
SK = "s" + "k-" + "qrstuvwxyzABCDEF"
e = base64.b64encode(SK.encode()).decode()
def leak(out):
    return any(w in out for s in (SK, e) for w in {s[i:i + 8] for i in range(len(s) - 7)})
cases = [("id_ + b64", "id_" + e), ("x- + b64", "x-" + e),
         ("URL path + b64", "https://h.example/download/" + e),
         ("b64 + 後ろに - と文字", e + "-tail"),
         ("b64 を 8 字で改行して折り返し（限界）", "\n".join(e[i:i + 8] for i in range(0, len(e), 8))),
         ("URL ?x= + b64", "https://h.example/dl?x=" + e),
         ("key: + b64", "key:" + e)]
for name, t in cases:
    out, n = L.redact(t)
    print(f"{name}: n={n} {'漏れ' if leak(out) else '漏れ無し'}")
