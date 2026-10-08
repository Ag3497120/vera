"""W16-t7c K720〜K722: 全角・パーセント・base64 に変形した鍵の伏せ。鍵はすべて連結・符号化で作る（完成形・符号化した列をソースに置かない）。"""
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verantyx import ledger_events as L  # noqa: E402

BODY = "abcdefghijklmnop"
SK = "s" + "k-" + BODY
AKIA = "AK" + "IA" + "ZZZZYYYYXXXXWWWW"
GHP = "gh" + "p_" + "MnOp" * 6
ZB = "z" * 30
HUNTER = "hunter2hunter2"
PWQ = "pass" + "word=" + "hu?nter2hunter2"      # '?' が 3k+2 番目: base64 に '/'（urlsafe では '_'）が出る
PW = "pass" + "word=" + HUNTER


def fw(s):
    """ASCII 可視文字を全角に、空白を U+3000 に。"""
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else ("　" if c == " " else c) for c in s)


def pct_all(s):
    return "".join("%%%02X" % ord(c) for c in s)


def b64(s):
    return base64.b64encode(s.encode()).decode()


def _variants():
    v = []
    # (形, 名前, 入力, 入力に現れる秘密の列の一覧)
    def add(form, name, text, secrets):
        v.append((form, name, text, secrets))

    add("fullwidth", "fw_prefix_only", "ヘッダは " + fw("sk-") + BODY + " です", [SK, fw("sk-") + BODY])
    add("fullwidth", "fw_all", "ヘッダは " + fw(SK) + " です", [SK, fw(SK)])
    add("fullwidth", "fw_japanese_nogap", "鍵は" + fw(SK) + "です", [SK, fw(SK)])
    add("fullwidth", "fw_quoted", 'curl -H "x: ' + fw(SK) + '"', [SK, fw(SK)])
    add("fullwidth", "fw_akia", "ヘッダは " + fw(AKIA) + " です", [AKIA, fw(AKIA)])
    add("fullwidth", "fw_ghp", "ヘッダは " + fw(GHP) + " です", [GHP, fw(GHP)])
    add("fullwidth", "fw_fe63_dash", "ヘッダは sk﹣" + BODY + " です", [SK, "sk﹣" + BODY])
    add("fullwidth", "fw_bearer_window", "ヘッダは " + fw("Bearer ") + ZB + " です", [ZB, fw("Bearer ") + ZB])
    add("fullwidth", "fw_password", "ヘッダは " + fw("pass" + "word=" + HUNTER) + " です", [HUNTER, fw("pass" + "word=" + HUNTER)])

    add("percent", "pct_dash", "ヘッダは sk%2D" + BODY + " です", [SK, "sk%2D" + BODY])
    add("percent", "pct_dash_lower", "ヘッダは sk%2d" + BODY + " です", [SK, "sk%2d" + BODY])
    add("percent", "pct_all", "ヘッダは " + pct_all(SK) + " です", [SK, pct_all(SK)])
    add("percent", "pct_double", "ヘッダは sk%252D" + BODY + " です", [SK, "sk%252D" + BODY])
    add("percent", "pct_url_query", "see https://h.example/?x=sk%2D" + BODY + "&y=1", [SK, "sk%2D" + BODY])
    add("percent", "pct_bearer_space", "ヘッダは Bearer%20" + ZB + " です", [ZB, "Bearer%20" + ZB])
    add("percent", "pct_akia", "ヘッダは %41KIA" + "ZZZZYYYYXXXXWWWW" + " です", [AKIA, "%41KIA" + "ZZZZYYYYXXXXWWWW"])
    add("percent", "pct_bearer_plus", "ヘッダは Bearer+" + ZB + " です", [ZB, "Bearer+" + ZB])

    e = b64(SK)
    add("base64", "b64_padded", "ヘッダは " + e + " です", [SK, e])
    add("base64", "b64_unpadded", "ヘッダは " + e.rstrip("=") + " です", [SK, e.rstrip("=")])
    u = base64.urlsafe_b64encode(PWQ.encode()).decode()
    assert ("_" in u or "-" in u) and u != b64(PWQ)
    add("base64", "b64_urlsafe", "ヘッダは " + u + " です", [PWQ, u])
    e = b64(PW)
    add("base64", "b64_password", "ヘッダは " + e + " です", [HUNTER, PW, e])
    e = b64("user:" + SK)
    add("base64", "b64_basic_auth", "Authorization: Basic " + e, [SK, e])
    e = b64(SK)
    add("base64", "b64_in_token", "ヘッダは x=" + e + " です", [SK, e])
    e = b64(AKIA)
    add("base64", "b64_akia", "ヘッダは " + e + " です", [AKIA, e])
    # 第 2 ラウンドで追加（レビュー R1。厳しくする方向の追加）。base64 の前に base64 の文字（`_` `-` `/`）が接する形。
    e = b64(SK)
    add("base64", "b64_prefix_underscore", "ヘッダは id_" + e + " です", [SK, e])
    add("base64", "b64_prefix_hyphen", "ヘッダは x-" + e + " です", [SK, e])
    add("base64", "b64_url_path", "see https://h.example/download/" + e + " now", [SK, e])
    # 第 3 ラウンドで追加（レビュー r2 の R4・R5。厳しくする方向の追加）
    D = b64(json.dumps({"api_key": SK, "メモ": "設定の説明です。" * 20}, ensure_ascii=False))
    assert sum(D.count(c) for c in "/+") >= 16
    add("base64", "b64_ja_json_prefix_underscore", "ヘッダは id_" + D + " です", [SK, D])
    add("base64", "b64_ja_json_url_path", "see https://h.example/download/" + D + " now", [SK, D])
    add("base64", "b64_ja_json_prefix_hyphen", "ヘッダは x-" + D + " です", [SK, D])
    e = b64(SK)
    add("base64", "b64_alnum_prefix1", "ヘッダは a" + e + " です", [SK, e])
    add("base64", "b64_alnum_prefix3", "ヘッダは abc" + e + " です", [SK, e])
    add("base64", "b64_alnum_prefix4", "ヘッダは abcd" + e + " です", [SK, e])
    add("base64", "b64_alnum_suffix", "ヘッダは " + e.rstrip("=") + "xyz です", [SK, e.rstrip("=")])
    add("base64", "b64_alnum_both", "ヘッダは Q" + e.rstrip("=") + "zz です", [SK, e.rstrip("=")])
    # 第 4 ラウンドで追加（レビュー r3 の R7。厳しくする方向の追加）。`+/` を含む base64 の後ろに `-` `_` が接する形（逆向きも）。
    # 鍵は JSON の先頭側にあり、`D` には `/+` が多い（鍵が最後の `+/` より前にある）。
    j = json.dumps({"api_key": SK, "メモ": "設定の説明です。" * 20}, ensure_ascii=False)
    D2 = base64.b64encode(j.encode()).decode().rstrip("=")
    DU = base64.urlsafe_b64encode(j.encode()).decode().rstrip("=")
    assert sum(D2.count(c) for c in "/+") >= 16 and sum(DU.count(c) for c in "-_") >= 16
    add("base64", "b64_ja_json_suffix_hyphen", "ヘッダは " + D2 + "-v2 です", [SK, D2])
    add("base64", "b64_ja_json_suffix_underscore", "ヘッダは " + D2 + "_tail です", [SK, D2])
    add("base64", "b64_ja_json_both_hyphen", "ヘッダは x-" + D2 + "-y です", [SK, D2])
    add("base64", "b64_ja_json_name_backup", "ヘッダは name-" + D2 + "-backup です", [SK, D2])
    add("base64", "b64_ja_json_urlsafe_suffix_plus", "ヘッダは " + DU + "+v2 です", [SK, DU])
    add("base64", "b64_ja_json_urlsafe_suffix_slash", "ヘッダは " + DU + "/x です", [SK, DU])
    return v


VARIANTS = _variants()


def windows(s, k=8):
    return {s[i:i + k] for i in range(max(0, len(s) - k + 1))}


def leaks(out, secrets):
    return [w for s in secrets for w in windows(s) if w in out]


def test_variant_counts():
    for form in ("fullwidth", "percent", "base64"):
        assert sum(1 for x in VARIANTS if x[0] == form) >= 5


@pytest.mark.parametrize("form,name,text,secrets", VARIANTS, ids=[x[1] for x in VARIANTS])
def test_c1_variant_redacted(form, name, text, secrets):
    out, n = L.redact(text)
    assert n >= 1, "伏せの件数 0"
    assert leaks(out, secrets) == [], "漏れ"
    assert out != "[REDACTED:unbounded]"
    assert L.redact(out)[1] == 0, "冪等でない"
    assert L.redact(out)[0] == out


def test_marker_names_are_one_of_three():
    out, _ = L.redact("ヘッダは " + fw(SK) + " です")
    assert out == "ヘッダは [REDACTED:sk:nfkc] です"
    out, _ = L.redact("ヘッダは sk%2D" + BODY + " です")
    assert out == "ヘッダは [REDACTED:sk:pct] です"
    out, _ = L.redact("ヘッダは " + b64(SK) + " です")
    assert out == "ヘッダは [REDACTED:sk:b64] です"


def test_marker_safety():
    for t, _rx, _g in L.REDACT_PATTERNS:
        for var in ("nfkc", "pct", "b64"):
            m = "[REDACTED:%s:%s]" % (t, var)
            assert L.redact(m) == (m, 0), m
            assert L.redact("x " + m + " y")[1] == 0, m
            assert L.redact('"' + m + '"')[1] == 0, m
            assert L.redact(m + " " + m)[1] == 0, m
            assert L.redact("pass" + "word=" + m)[1] == 0, m


def test_window_across_tokens():
    for text, sec in (("ヘッダは " + fw("Bearer") + "　" + ZB, [ZB]),
                      ("ヘッダは " + fw("pass" + "word") + "： " + HUNTER, [HUNTER])):
        out, n = L.redact(text)
        assert n >= 1 and leaks(out, sec) == []


def test_marker_adjacent_to_variant_key():
    out, n = L.redact("[REDACTED:sk]" + fw(SK))
    assert n >= 1 and leaks(out, [SK, fw(SK)]) == []
    assert L.redact(out)[1] == 0


def test_k722_nonsecret_unchanged():
    cases = [
        "普通の文。キー無し。", "Bear" + "er token を使う", "新しい " + "token:" + "\n" + "abcdefg" + " を試して",
        "ＡＢＣ全角の文", "https://example.com/?q=%E3%81%82", b64("hello world hello world"),
        "ヘッダは " + b64("hello world hello world") + " です", "日本語のあとに ｈｅｌｌｏ ｗｏｒｌｄ", "100%25 完了", "",
    ]
    for s in cases:
        assert L.redact(s) == (s, 0), s


def test_k721_split_key_is_not_detected_and_is_disclosed():
    # 2 つの欄に分けた鍵は検出しない（K721）。docs/RECORDER.md の「残る限界」に開示してある。
    a, b = "s" + "k-", BODY
    s = json.dumps({"a": a, "b": b})
    assert L.redact(s)[1] == 0
    assert "K721" in (ROOT / "docs" / "RECORDER.md").read_text(encoding="utf-8")


# ---- 経路: UserPromptSubmit の hook ----
def _env(**kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def _hook_prompt(tmp_path, prompt):
    r = subprocess.run([sys.executable, "-m", "verantyx.cli", "hooks", "print", "--claude-code"], capture_output=True, text=True,
                       env=_env(), cwd=str(tmp_path))
    cmd = json.loads(r.stdout)["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(tmp_path)),
                       input=json.dumps({"prompt": prompt}), cwd=str(tmp_path))
    assert p.returncode == 0, p.stderr
    d = tmp_path / ".vera" / "ledger"
    rs = [json.loads(x) for x in (d / "events.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
    return d, rs


def _all_bytes(d):
    return b"".join(p.read_bytes() for p in Path(d).rglob("*") if p.is_file())


@pytest.mark.parametrize("name", ["fw_all", "b64_padded", "pct_dash"])
def test_hook_route_variant_not_in_ledger(tmp_path, name):
    form, _n, text, secrets = next(x for x in VARIANTS if x[1] == name)
    d, rs = _hook_prompt(tmp_path, text)
    assert len(rs) == 1 and rs[0]["data"]["redactions"] >= 1
    b = _all_bytes(d)
    assert b
    for s in secrets:
        for rep in (s.encode("utf-8"), json.dumps(s)[1:-1].encode("utf-8")):
            assert rep not in b, name
        assert leaks(b.decode("utf-8", "replace") + json.dumps(b.decode("utf-8", "replace")), [s]) == []
