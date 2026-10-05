"""W16-t6 / T6-3 (K603): 10-02〜10-05 の実報告（impl.r*.md、自由文）に V・a・b を掛ける。規則は docs/ATTEST.md 第 7 節。
使い方: python run_replay.py <出力ディレクトリ> [--freeze]   （--freeze は manifest.json が無いときだけ作る。あれば読むだけ。新しい報告は入れない）
他の wt/* は開かない（tree はこの作業ツリー、解決できないものは EVIDENCE_NOT_IN_TREE）。"""
import datetime
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
RI = Path("/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl")
LO = datetime.datetime(2026, 10, 2, 0, 0, 0).timestamp()
HI = datetime.datetime(2026, 10, 5, 23, 59, 59).timestamp()


def freeze(out):
    reports = []
    for p in sorted(RI.glob("*/impl.r*.md")):
        if p.parent.name.startswith("W16-"):
            continue
        mt = p.stat().st_mtime
        if not (LO <= mt <= HI):
            continue
        reports.append({"path": str(p), "dir": p.parent.name, "mtime": datetime.datetime.fromtimestamp(mt).astimezone().isoformat(timespec="seconds"),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    m = {"frozen_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "root": str(RI),
         "rule": "impl.r*.md, mtime in [2026-10-02 00:00, 2026-10-05 23:59:59] local, directory name not starting with W16-; .bak directories included; date evidence is mtime (not under git)",
         "reports": reports}
    (out / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def tsv(s):
    return str(s).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def main(out, do_freeze):
    sys.path.insert(0, str(TREE))
    from verantyx import attest
    out = Path(out)
    if do_freeze and not (out / "manifest.json").exists():
        freeze(out)
    man = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    cache = {}
    rows, changed_since = [], []
    for r in man["reports"]:
        data = Path(r["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != r["sha256"]:
            changed_since.append(r["path"])
        res = attest.run_attest(data.decode("utf-8", "replace"), str(TREE), extractors=("V", "a", "b"), partial=True,
                                search_dirs=["artifacts/" + r["dir"].lower()], history=True, report_path=r["dir"] + "/" + Path(r["path"]).name, cache=cache)
        for ex, e in res["extractors"].items():
            for c in e["claims"]:
                rows.append({"report": res["report"]["path"], "extractor": ex, **{k: c[k] for k in ("claim_id", "line", "kind", "text", "mark", "reason", "facts")}})
    (out / "results.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    lab = ["\t".join(["report", "line", "claim_text", "extractor", "mark", "reason", "evidence_path", "evidence_sha256", "claimed", "actual", "label"])]
    mm = [lab[0].replace("\tlabel", "\tfact")]
    for x in rows:
        deciding = next((f for f in x["facts"] if f["mark"] == x["mark"]), x["facts"][0] if x["facts"] else None)
        ev = (deciding or {}).get("evidence") or {}
        cells = [x["report"], x["line"], x["text"], x["extractor"], x["mark"], x["reason"], ev.get("path", ""), ev.get("sha256", ""),
                 json.dumps(deciding["claimed"], ensure_ascii=False) if deciding else "", json.dumps(deciding["actual"], ensure_ascii=False) if deciding else ""]
        lab.append("\t".join(tsv(c) for c in cells + [""]))
        for f in x["facts"]:
            if f["mark"] == "MISMATCH":
                e2 = f.get("evidence") or {}
                mm.append("\t".join(tsv(c) for c in [x["report"], x["line"], x["text"], x["extractor"], f["mark"], f["reason"], e2.get("path", ""), e2.get("sha256", ""),
                                                     json.dumps(f["claimed"], ensure_ascii=False), json.dumps(f["actual"], ensure_ascii=False), f["fact"]]))
    (out / "labels.tsv").write_text("\n".join(lab) + "\n", encoding="utf-8")
    (out / "mismatches.tsv").write_text("\n".join(mm) + "\n", encoding="utf-8")
    L = ["T6-3 再生: 対象の報告 %d 本（manifest.json。凍結 %s）。凍結後に変わった報告: %d 本" % (len(man["reports"]), man["frozen_at"], len(changed_since)), ""]
    for ex in ("V", "a", "b"):
        xs = [x for x in rows if x["extractor"] == ex]
        marks = Counter(x["mark"] for x in xs)
        facts = [f for x in xs for f in x["facts"]]
        fm = Counter(f["mark"] for f in facts)
        n = len(xs)
        L.append("[%s] 申告 %d 件（申告のある報告 %d 本）: 記録 %d / 証言 %d / 食い違い %d" % (ex, n, len({x["report"] for x in xs}), marks["RECORD"], marks["TESTIMONY"], marks["MISMATCH"]))
        L.append("    照合できた申告の割合 =（記録+食い違い）/全数 = %s" % ("%d/%d = %.4f" % (marks["RECORD"] + marks["MISMATCH"], n, (marks["RECORD"] + marks["MISMATCH"]) / n) if n else "n/a（申告 0 件）"))
        nf = len(facts)
        L.append("    事実 %d 件: 記録 %d / 証言 %d / 食い違い %d。照合できた事実の割合 = %s" % (nf, fm["RECORD"], fm["TESTIMONY"], fm["MISMATCH"],
                 "%d/%d = %.4f" % (fm["RECORD"] + fm["MISMATCH"], nf, (fm["RECORD"] + fm["MISMATCH"]) / nf) if nf else "n/a"))
        L.append("    申告の理由の内訳: " + ", ".join("%s:%s=%d" % (m, r, c) for (m, r), c in sorted(Counter((x["mark"], x["reason"]) for x in xs).items())))
        L.append("    事実の理由の内訳: " + ", ".join("%s:%s=%d" % (m, r, c) for (m, r), c in sorted(Counter((f["mark"], f["reason"]) for f in facts).items())))
        L.append("    種類: " + ", ".join("%s=%d" % (k, c) for k, c in sorted(Counter(x["kind"] for x in xs).items())))
        mf = [f for f in facts if f["mark"] == "MISMATCH" and f["fact"].startswith("file_sha:")]
        if mf:
            L.append("    file_sha の食い違い %d 件の申告 sha の桁数: %s（40 桁は git の sha1 の可能性）" % (len(mf), dict(Counter(len(str(f["claimed"]).rstrip(".")) for f in mf))))
        L.append("")
    L.append("labels.tsv: %d 申告 + 見出し、label 列は空（正解ラベルはオーナーが付ける）。mismatches.tsv: 食い違いの事実 %d 件。" % (len(rows), len(mm) - 1))
    (out / "summary.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1], "--freeze" in sys.argv)
