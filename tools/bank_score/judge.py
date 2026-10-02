"""python -m tools.bank_score.judge: Vera を呼ばずに、判定部分だけを通す入口（W1-s2 T2）。

観測を **外から与える**: 問題の参考例（reference）・別解（alt_answers）・誤答例（wrong_answers）から作るか、
`--observations`（1 行 `{"id":..., "observation": {...}}` の JSONL）で渡す。作った観測は `observation.probe` に記録し、
採点は本体と同じ `score_observation` を通す。Vera も子プロセスも起動しない。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import schema
from .classify import CLASS_JA
from .cli import _inputs_meta, _row, _scored
from .report import build_summary, dumps, render_md, write_jsonl
from .score import score_observation
from .v2 import b1, b3

PROBES = ("reference", "alt_answers", "wrong_answers")
EXIT_OK, EXIT_INPUT = 0, 2


def _blank(state: str, **kw: object) -> dict:
    o = {"state": state, "status": None, "verdict": None, "kind": None, "door": None, "text": "", "values": None,
         "partial": False, "declared_constructed": False, "has_evidence": False, "label_override": False,
         "exit_code": None, "entry": "judge", "argv": [], "constructed": False}
    o.update(kw)
    return o


def _b3_obs(expect: dict, text: str, want: str) -> dict:
    """b3_state が want になる観測（型の欄だけを立てる）。"""
    if want == "refuse":
        return _blank("abstain", text=text)
    return _blank("answer", text=text, declared_constructed=(want == "created"), constructed=(want == "constructed"))


def build_probe_observations(bank: str, probe: str, raw: dict, case: dict) -> list[dict]:
    """問題 1 件から probe の観測（0 個以上）を作る。各観測に probe 名と index を記録する。"""
    e = raw["expect"]
    obs: list[dict] = []
    if bank == "B1":
        if probe != "reference":
            return []
        g = b1.gold_output(e)
        o = _blank("abstain", readable=False, clauses=[], relations=[]) if not e["readable"] else \
            _blank("answer", readable=True, clauses=g["clauses"], relations=g["relations"])
        obs.append(o)
    elif bank == "B2":
        beh = e["behavior"]
        state = "abstain" if beh == "abstain" else ("social" if beh == "social" else "answer")
        if probe == "reference":
            obs.append(_blank(state, text=e.get("reference", "")))
        elif probe == "alt_answers":
            for a in raw.get("alt_answers") or []:
                if isinstance(a, str):
                    obs.append(_blank(state, text=a))
        elif probe == "wrong_answers":
            for w in raw.get("wrong_answers") or []:
                if isinstance(w, dict) and isinstance(w.get("text"), str) and w.get("state") in ("answer", "abstain"):
                    obs.append(_blank(w["state"], text=w["text"]))
    elif bank == "B3":
        if probe != "reference":
            return []
        st = e["state"]
        want = st[0] if isinstance(st, list) else st
        obs.append(_b3_obs(e, e.get("reference", ""), want))
    else:  # B5
        if probe != "reference":
            return []
        if e["decision"] == "escalate":
            obs.append(_blank("abstain", decision="escalate", answer=None, answer_option_index=None, vocab_mapping=None))
        elif case.get("options"):
            i = e["answer_option_index"]
            obs.append(_blank("answer", decision="answer", answer=case["options"][i], answer_option_index=i,
                              vocab_mapping=None))
        else:
            obs.append(_blank("answer", decision="answer", answer=e.get("answer") or "", answer_option_index=None,
                              vocab_mapping=None))
    for i, o in enumerate(obs):
        o["probe"] = probe
        o["probe_index"] = i
    return obs


def _rule_names(row: dict, result: str) -> list[str]:
    return sorted(k for k, c in row["checks"].items() if c["result"] == result)


def _entry(row: dict) -> dict:
    return {"id": row["id"], "class": row["class"], "class_approx": row.get("class_approx"),
            "fail_rules": _rule_names(row, "FAIL"), "unjudged_rules": _rule_names(row, "UNJUDGED")}


def probes_block(rows: list[dict]) -> dict:
    """行（probe・side・class・class_approx・checks）だけから作る。publish 後の行からも同じ数が出る。"""
    out: dict = {}
    for probe in sorted({r.get("probe") for r in rows if r.get("probe")}):
        pr = [r for r in rows if r.get("probe") == probe]
        if probe == "reference" or probe == "observations":
            ans = [r for r in pr if r.get("side") == "answer"]
            ab = [r for r in pr if r.get("side") == "abstain"]
            strict = [r for r in ans if r["class"] == "correct"]
            approx_only = [r for r in ans if r["class"] != "correct" and r.get("class_approx") == "correct"]
            not_correct = [_entry(r) for r in ans if r.get("class_approx") != "correct"]
            out[probe] = {
                "answer_side_total": len(ans), "correct_strict": len(strict), "correct_approx_only": len(approx_only),
                "approx_only_ids": [r["id"] for r in approx_only],
                "not_correct": not_correct,
                "rate_strict": round(len(strict) / len(ans), 6) if ans else None,
                "rate_with_approx": round((len(strict) + len(approx_only)) / len(ans), 6) if ans else None,
                "abstain_side_total": len(ab),
                "abstain_side_correct": sum(1 for r in ab if r["class"] == "correct_abstain"),
                "abstain_side_not_correct": [_entry(r) for r in ab if r["class"] != "correct_abstain"],
            }
        elif probe == "alt_answers":
            ok = [r for r in pr if r["class"] in ("correct", "correct_abstain")]
            out[probe] = {"probes": len(pr), "correct": len(ok),
                          "not_correct": [{**_entry(r), "index": r.get("probe_index")} for r in pr
                                          if r["class"] not in ("correct", "correct_abstain")]}
        elif probe == "wrong_answers":
            out[probe] = {"probes": len(pr),
                          "passed_wrongly": [{"id": r["id"], "index": r.get("probe_index"), "class": r["class"]}
                                             for r in pr if r["class"] in ("correct", "correct_abstain")]}
    return out


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m tools.bank_score.judge",
                                 description="Vera を呼ばずに判定部分だけを通す（参考例・別解・誤答例・外から与えた観測）")
    ap.add_argument("--bank", required=True, choices=list(schema.BANKS))
    ap.add_argument("--profile", default="w1s", choices=list(schema.PROFILES))
    ap.add_argument("--items", required=True)
    ap.add_argument("--quarantine")
    ap.add_argument("--frames")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--probe", choices=list(PROBES))
    g.add_argument("--observations", help="1 行 {\"id\":..., \"observation\": {...}} の JSONL")
    ap.add_argument("--out", required=True)
    return ap


def run(args: argparse.Namespace) -> int:
    bank, profile = args.bank, args.profile
    frames = Path(args.frames) if args.frames else None
    if bank == "B5" and frames is None:
        print("入力の誤り: B5 には --frames が必要", file=sys.stderr)
        return EXIT_INPUT
    if bank != "B5" and frames is not None:
        print("入力の誤り: --frames は B5 だけが受け取る", file=sys.stderr)
        return EXIT_INPUT
    try:
        qinfo = schema.load_quarantine_info(args.quarantine)
        recs = schema.read_items(args.items, bank, frames, profile)
        given: dict[str, list[dict]] = {}
        if args.observations:
            for ln in Path(args.observations).read_text(encoding="utf-8").splitlines():
                if not ln.strip():
                    continue
                try:
                    o = json.loads(ln)
                except json.JSONDecodeError:
                    raise schema.InputError("observations に JSON でない行がある")
                if not (isinstance(o, dict) and isinstance(o.get("id"), str) and isinstance(o.get("observation"), dict)
                        and o["observation"].get("state") in ("answer", "abstain", "social")):
                    raise schema.InputError("observations の行は {id, observation:{state: answer|abstain|social, ...}}")
                given.setdefault(o["id"], []).append(o["observation"])
            unknown = sorted(set(given) - {r["id"] for r in recs})
            if unknown:
                raise schema.InputError(f"observations に items に無い id がある: {len(unknown)} 件")
    except schema.InputError as e:
        print(f"入力の誤り: {e}", file=sys.stderr)
        return EXIT_INPUT
    qset = set(qinfo["ids"])
    kept = [r for r in recs if r["id"] not in qset]
    quarantine = {"count": len(recs) - len(kept), "ids": sorted(r["id"] for r in recs if r["id"] in qset),
                  "not_in_items": sorted(qset - {r["id"] for r in recs})}
    if profile == "v2":
        quarantine["shape"] = qinfo["shape"]
    probe = args.probe or "observations"
    rows: list[dict] = []
    n_without = 0
    for rec in kept:
        if rec["errors"]:
            rows.append(_row(rec, bank, f"judge:{probe}", profile=profile, **{"class": "unscorable",
                                                                               "reason": "ITEM_INVALID",
                                                                               "reason_detail": rec["errors"],
                                                                               "probe": probe, "side": None}))
            continue
        if args.observations:
            obs_list = [dict(o, probe=probe, probe_index=i) for i, o in enumerate(given.get(rec["id"], []))]
            if not obs_list:
                n_without += 1
        else:
            obs_list = build_probe_observations(bank, probe, rec["raw"], rec["case"])
        for o in obs_list:
            o.setdefault("probe", probe)
            sc = score_observation(bank, rec["raw"], rec["case"], o, profile)
            row = _row(rec, bank, f"judge:{probe}", profile=profile, observation=o, probe=probe,
                       probe_index=o.get("probe_index"), side=sc["side"])
            rows.append(_scored(row, sc))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in ("results.jsonl", "summary.json", "summary.md", "run_meta.json"):
        p = out / name
        if p.exists():
            p.unlink()
    summary = build_summary(bank, rows, {}, quarantine, profile)
    summary["probes"] = probes_block(rows)
    meta = {"bank": bank, "profile": profile, "mode": "judge", "probe": probe,
            "note": "Vera も子プロセスも起動していない。観測は probe（参考例・別解・誤答例）か --observations から作った",
            "args": {"items": args.items, "quarantine": args.quarantine, "frames": args.frames,
                     "observations": args.observations},
            "quarantine": quarantine, "n_rows": len(rows), "items_without_observation": n_without}
    if profile == "v2":
        from .v2.b3_approx import fugashi_version
        meta.update(_inputs_meta(args, frames))
        meta["fugashi"] = fugashi_version()
    write_jsonl(out / "results.jsonl", rows)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                      encoding="utf-8")
    (out / "summary.md").write_text(render_md(summary) + "\n", encoding="utf-8")
    (out / "run_meta.json").write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=1) + "\n",
                                       encoding="utf-8")
    pb = summary["probes"].get(probe, {})
    print(f"judge {bank} profile={profile} probe={probe} rows={len(rows)} "
          + " ".join(f"{k}={v['count']}" for k, v in summary["classes"].items()))
    if "rate_with_approx" in pb:
        print(f"answer_side={pb['answer_side_total']} strict={pb['correct_strict']} approx_only={pb['correct_approx_only']} "
              f"rate_strict={pb['rate_strict']} rate_with_approx={pb['rate_with_approx']}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    return run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
