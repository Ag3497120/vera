"""追加の探り（R6: 台本つき）。使い方: extra_probes.py <ツリー>。鍵の完成形・符号化した列は出力しない。出すのは 名前: n=件数 漏れ|漏れ無し (冪等|冪等でない) だけ。"""
import base64, json, sys, unicodedata
TREE = sys.argv[1]
sys.path.insert(0, TREE)
import verantyx.ledger_events as L
assert L.__file__.startswith(TREE)
print(L.__file__)

SK = "s" + "k-" + "qrstuvwxyzABCDEF"
ZB = "Zq8Lm3Vt7Hs2Wk9Rp4Nc6Xb"
def b64(s): return base64.b64encode(s.encode()).decode()
def fw(s): return "".join(chr(ord(c) + 0xFEE0) if "!" <= c <= "~" else c for c in s)
def pct_all(s): return "".join("%%%02X" % ord(c) for c in s)
def windows(s): return {s[i:i + 8] for i in range(len(s) - 7)}

# 印の安全性
bad = []
for nm, _r, _g in L.REDACT_PATTERNS:
    for v in ("nfkc", "pct", "b64"):
        m = f"[REDACTED:{nm}:{v}]"
        for t in (m, "x " + m + " y", '"' + m + '"', m + " " + m):
            if L.redact(t)[1]:
                bad.append(t)
print("markers ok" if not bad else bad)

def run(name, text, secrets):
    out, n = L.redact(text)
    leak = any(w in out for s in secrets for w in windows(s))
    out2, n2 = L.redact(out)
    idem = (out2 == out and n2 == 0)
    print(f"{name}: n={n} {'漏れ' if leak else '漏れ無し'} {'冪等' if idem else '冪等でない'}")

e = b64(SK)
# --- 旧 12 項目（変形の合成・限界の開示を含む。結果は docs 15.4 の記述と対応）
run("fw quoted + %20", 'curl -H "x: ' + fw("sk-") + "%20" + SK[3:] + '"', [SK, SK[3:]])
run("b64 after colon", "key: " + e, [SK, e])
run("b64 after colon nospace", "key:" + e, [SK, e])
run("Bearer %20 fw", fw("Bearer") + "%20" + ZB, [ZB])
run("fw Bearer U+3000 + pct body", fw("Bearer") + "　%7A" + ZB[1:], [ZB])
run("marker adjacent fw", "[REDACTED:sk:nfkc] " + fw(SK), [SK, fw(SK)])
run("split in two tokens (K721)", "sk- " + SK[3:], [SK[3:]])
run("U+2010 dash (known limit)", "sk‐" + SK[3:], [SK])
run("U+200B zero width (known limit)", "sk-​" + SK[3:], [SK])
run("hex (known limit)", SK.encode().hex(), [SK, SK.encode().hex()])
run("b64 of fullwidth (compose, limit)", b64(fw(SK)), [b64(fw(SK)), fw(SK)])
run("pct of b64 (compose)", e.replace("=", "%3D") + "%0A", [SK, e.rstrip("=")])

# --- R4: 日本語を含む JSON の base64（`/+` が多い）に前置
for k in (5, 20, 40):
    D = b64(json.dumps({"api_key": SK, "メモ": "設定の説明です。" * k}, ensure_ascii=False))
    seps = sum(D.count(c) for c in "/+")
    for pre in ("id_", "https://h.example/f/", "x-"):
        run(f"R4 k={k} seps={seps} prefix={pre}", pre + D, [SK, D])

# --- R5: 英数字が base64 の前後に区切り無しで接する形
for pre in ("a", "ab", "abc", "abcd", "abcde"):
    run(f"R5 prefix={pre}", pre + e, [SK, e])
run("R5 suffix=xyz (no =)", e.rstrip("=") + "xyz", [SK, e.rstrip("=")])
run("R5 suffix=x (no =)", e.rstrip("=") + "x", [SK, e.rstrip("=")])
run("R5 both Q..zz", "Q" + e.rstrip("=") + "zz", [SK, e.rstrip("=")])

# --- 追加の探り 7 件
D = b64(json.dumps({"api_key": SK, "メモ": "設定の説明です。" * 20}, ensure_ascii=False))
run("id_abc + b64", "id_abc" + e, [SK, e])
run("x-ab + b64", "x-ab" + e, [SK, e])
run("a_ x20 + JSON b64", "a_" * 20 + D, [SK, D])
run("a/ x20 + JSON b64", "a/" * 20 + D, [SK, D])
run("id_ + JSON b64 + xyz", "id_" + D.rstrip("=") + "xyz", [SK, D.rstrip("=")])
run("URL path 17 segments + JSON b64", "https://h.example/" + "/".join("seg%d" % i for i in range(17)) + "/" + D, [SK, D])
run("b64 + _tail", e + "_tail", [SK, e])

# --- R7（第 4 ラウンド）: `+/` を含む base64 の後ろに `-_` が接する形（逆向きも）。鍵は JSON の先頭側。対照: 鍵が末尾側。
j = json.dumps({"api_key": SK, "メモ": "設定の説明です。" * 20}, ensure_ascii=False)
D2 = base64.b64encode(j.encode()).decode().rstrip("=")
DU = base64.urlsafe_b64encode(j.encode()).decode().rstrip("=")
print("R7 seps", sum(D2.count(c) for c in "/+"), sum(DU.count(c) for c in "-_"))
run("R7 D + -v2", D2 + "-v2", [SK, D2])
run("R7 D + _tail", D2 + "_tail", [SK, D2])
run("R7 D + _x", D2 + "_x", [SK, D2])
run("R7 D + -", D2 + "-", [SK, D2])
run("R7 DU + /tail", DU + "/tail", [SK, DU])
run("R7 DU + +v2", DU + "+v2", [SK, DU])
run("R7 DU + /x", DU + "/x", [SK, DU])
run("R7 DU + +", DU + "+", [SK, DU])
run("R7 id_ + D + _v2", "id_" + D2 + "_v2", [SK, D2])
run("R7 x- + D + -y", "x-" + D2 + "-y", [SK, D2])
run("R7 name- + D + -backup", "name-" + D2 + "-backup", [SK, D2])
j2 = json.dumps({"メモ": "設定の説明です。" * 20, "api_key": SK}, ensure_ascii=False)
D3 = base64.b64encode(j2.encode()).decode().rstrip("=")
run("R7 control: key at end, D + -v2", D3 + "-v2", [SK, D3])
run("R7 b64(SK) + -v2 (no +/ in body)", e.rstrip("=") + "-v2", [SK, e.rstrip("=")])
# レビュー r3 の任意 2: 前置 5〜8 字の英数字に区切りが混ざる形、b64 の連続部分が 1 トークンに 2 つある形
for pre in ("abcde", "abcdefgh", "ab-cd", "ab_cdef"):
    run("optional prefix=" + pre, pre + e, [SK, e])
run("two b64 runs in 1 token (key in 2nd)", "x=" + b64("hello world, not secret") + "&y=" + e, [SK, e])
run("two b64 runs in 1 token (. sep, key in 2nd)", b64("hello world, not secret") + "." + e, [SK, e])

# --- 開示済みの限界: 改行で折り返した base64
run("b64 folded every 8 chars (known limit)", "\n".join(e[i:i + 8] for i in range(0, len(e), 8)), [SK, e])
