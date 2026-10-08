"""W16-t3b の特性の試験。コードの後に書いたもので、凍結データではない（凍結データは test_w16t3b_cases.py）。"""
from verantyx import decode_grammar as G
from verantyx import quote_check as QC


def _rec(tmp_path, docs):
    paths = []
    for name, body in docs.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body + "\n", encoding="utf-8")
        paths.append(str(p))
    return G.load_records(paths)


def _q(source, line, text):
    return {"source": source, "line": line, "text": text}


def test_r16_keeps_positions_elements_and_conflicts(tmp_path):
    """R16 は found・鍵だけを変える。pos（要素の found_in・conflicts）と印は変えない。"""
    rec = _rec(tmp_path, {"a.txt": "返却期限は14日だ。", "b.txt": "返却期限は21日だ。"})
    plain = QC.check("返却期限は14日だ。", [_q("a.txt", 1, "返却期限は14日だ。"), _q("b.txt", 1, "返却期限は21日だ。")], rec).to_dict()
    moved = QC.check("返却期限は14日だ。", [_q("docs/a.txt", 1, "返却期限は14日だ。"), _q("docs/b.txt", 1, "返却期限は21日だ。")], rec).to_dict()
    assert plain["verdict"] == moved["verdict"] == "conflict"
    assert plain["elements"] == moved["elements"] and plain["conflicts"] == moved["conflicts"]
    assert [x["found"] for x in plain["quotes"]] == ["exact", "exact"]
    assert [x["found"] for x in moved["quotes"]] == ["relocated", "relocated"]
    assert moved["quotes"][0]["relocated_to"] == ["a.txt:1"] and moved["quotes"][0]["source_claimed"] == "docs/a.txt" and moved["quotes"][0]["source_record"] == ["a.txt"]
    assert list(moved["quotes"][0]) == ["source", "line", "text", "relocated_to", "source_claimed", "source_record", "found"]


def test_r16_bare_filename_and_old_relocated_unchanged(tmp_path):
    rec = _rec(tmp_path, {"a.txt": "規程は毎年改定する。\n窓口は午前九時に開く。"})
    d = QC.check("規程は毎年改定する。", [_q("a.txt", 1, "規程は毎年改定する。"), _q("a.txt", 2, "規程は毎年改定する。")], rec).to_dict()
    assert d["quotes"][0]["found"] == "exact" and "source_claimed" not in d["quotes"][0]
    assert d["quotes"][1]["found"] == "relocated" and "source_claimed" not in d["quotes"][1]     # 指定行に無く他の行にある引用は従来の relocated


def test_new_rules_do_not_override_existing_reasons(tmp_path):
    """極性の違う答えは、役割・時制も違っても POLARITY_DIFFERS のまま（新しい段は anchored の直前）。"""
    rec = _rec(tmp_path, {"d.txt": "東京支店が京都支店を買収した。"})
    r = QC.check("京都支店が東京支店を買収しなかった。", [_q("d.txt", 1, "東京支店が京都支店を買収した。")], rec)
    assert r.verdict == "unanchored" and r.to_dict()["reason"] == "POLARITY_DIFFERS"


def test_attack_four_forms(tmp_path):
    rec = _rec(tmp_path, {"original.txt": "東京支店が京都支店を買収した。\n東京支店は開く。\n京都支店は閉店した。"})
    q = QC.check("京都支店が東京支店を買収した。", [_q("original.txt", 1, "東京支店が京都支店を買収した。")], rec).to_dict()
    assert q["verdict"] == "unanchored" and q["reason"].startswith("ROLE_PARTICLE_DIFFERS:")
    t = QC.check("東京支店は開いた。", [_q("original.txt", 2, "東京支店は開く。")], rec).to_dict()
    assert t["verdict"] == "unanchored" and t["reason"] == "TENSE_DIFFERS:開く"
    s = QC.check("東京支店は閉店した。", [_q("original.txt", 2, "東京支店は開く。"), _q("original.txt", 3, "京都支店は閉店した。")], rec).to_dict()
    assert s["verdict"] == "unanchored" and s["reason"] == "ANSWER_SPLIT_ACROSS_QUOTES"
    o = QC.check("東京支店は開く。", [_q("untrusted/original.txt", 2, "東京支店は開く。")], rec).to_dict()
    assert o["quotes"][0]["found"] == "relocated"


def test_particle_pair_ha_ga_mo_same_and_no_not_compared(tmp_path):
    rec = _rec(tmp_path, {"d.txt": "経理課が総務課の書類を預かった。"})
    r = QC.check("経理課は総務課の書類を預かった。", [_q("d.txt", 1, "経理課が総務課の書類を預かった。")], rec)
    assert r.verdict == "anchored"
    r = QC.check("経理課も総務課の書類を預かった。", [_q("d.txt", 1, "経理課が総務課の書類を預かった。")], rec)
    assert r.verdict == "anchored"
