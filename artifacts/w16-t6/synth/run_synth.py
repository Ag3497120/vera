"""W16-t6 / T6-1: 合成 40 件を実体化して V・a・b に掛け、t6_1_synth.json と t6_1_synth.txt を書く。
使い方: python run_synth.py <作業ディレクトリ(tmp)> <出力ディレクトリ(artifacts/w16-t6)>"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("synth_lib", HERE / "synth_lib.py")
sl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sl)


def compact(res):
    out = {}
    for ex, e in res["extractors"].items():
        out[ex] = {"counts": e["counts"], "offform": e["offform"],
                   "claims": [{"claim_id": c["claim_id"], "kind": c["kind"], "line": c["line"], "mark": c["mark"], "reason": c["reason"],
                               "facts": [{k: f[k] for k in ("fact", "mark", "reason", "claimed", "actual")} for f in c["facts"]]} for c in e["claims"]]}
    return out


def summary_text(m, ok, n):
    jp = [("detected", "検出（偽→食い違い）"), ("missed", "見逃し（偽→記録）"), ("abstain_false", "偽→証言（棄権）"), ("false_positive", "誤検出（正→食い違い）"),
          ("insufficient", "裏づけ不足（正→証言）"), ("not_extracted", "未抽出"), ("extra", "余剰"), ("exact", "期待と完全一致")]
    lines = ["T6-1 合成 %d 件（凍結の sha256 検査: %s）" % (n, "OK" if ok else "NG")]
    for ex in ("V", "a", "b"):
        x = m[ex]
        lines.append("")
        lines.append("[%s] 対象 %d 件・事実 %d（偽 %d / 正 %d / 判定不能設計 %d）" % (ex, x["cases"], x["facts"], x["false_facts"], x["true_facts"], x["unknown_facts"]))
        for k, label in jp:
            lines.append("  %s: %d" % (label, x[k]))
        lines.append("  検出率: %s" % ("%.4f" % x["detection_rate"] if x["detection_rate"] is not None else "n/a"))
        if ex in ("V", "a"):
            lines.append("  申告単位の見逃し: %d / 申告単位の誤検出: %d / 申告の並びの不一致: %d" % (x["claim_missed"], x["claim_false_positive"], x["claim_alignment_errors"]))
        if ex == "V":
            lines.append("  形外れの行 期待 %d / 実際 %d" % (x["offform_expected"], x["offform_actual"]))
        for mm in x["mismatched_expectations"]:
            lines.append("  期待と不一致: %s" % json.dumps(mm, ensure_ascii=False))
    return "\n".join(lines) + "\n"


def main(work, out):
    sys.path.insert(0, str(HERE.parents[2]))
    from verantyx import attest
    ok, bad = sl.freeze_ok()
    cases, expected, results, metrics = sl.run_all(attest, work)
    doc = {"freeze_ok": ok, "metrics": metrics, "cases": [{"id": c["id"], "group": c["group"], "note": c["note"], "extractors": compact(results[c["id"]])} for c in cases]}
    Path(out, "t6_1_synth.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    Path(out, "t6_1_synth.txt").write_text(summary_text(metrics, ok, len(cases)), encoding="utf-8")
    print(summary_text(metrics, ok, len(cases)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
