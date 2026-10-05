#!/usr/bin/env python3
"""Write Codex testimony labels for every r10 claim in the registered 60-word N4 sample."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a7/current-r3"
CLAIMS = ART / "n4_claims_v3_prefreeze.jsonl"
CLAIMS_FREEZE = ART / "n4_claims_v3_prefreeze.sha256.json"
OLD_LABELS = ROOT / "artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl"
OUT = ART / "n4_visual_labels_v3.jsonl"

ERRORS = {
    ("取り合わせる", "と", "companion"): "物どうしの並列対象は、一緒に行う人という companion の役割に合わない。",
    ("抜け替わる", "に", "source"): "に は変化後の到達先を表し、起点 source ではない。",
    ("否決する", "に", "agent"): "能動形で否決する動作主は主語で表し、に agent は合わない。",
    ("差し出せる", "に", "goal"): "人・組織が受け手なら recipient であり、移動先 goal とは区別される。",
    ("同封する", "と", "companion"): "同封物どうしの並列で、一緒に行う人という companion には合わない。",
    ("負担する", "に", "recipient"): "負担を引き受ける人は通常主語で、に recipient とする根拠を確認できない。",
    ("考える", "に", "recipient"): "思考の受け手を表す用法をこの述語のに格から確認できない。",
    ("相殺する", "と", "companion"): "相殺する債権・債務の並列で、一緒に行う人という companion には合わない。",
}

DOUBTFUL = {
    ("総括する", "で", "instrument"): "で格が場所か手段かは文脈なしに区別しにくい。",
    ("感じ取れる", "が", "experiencer"): "知覚の経験者には見えるが、規約の experiencer 定義は間接受身に限られる。",
    ("解任する", "から", "source"): "組織を起点とする読みはあり得るが、文脈なしに agent との区別が難しい。",
    ("看る", "に", "place"): "に格が看護の場所か対象に近い役割かを標本だけで一意に読めない。",
    ("繰り上がる", "に", "goal"): "順位・時間の到達先として読める一方、result との境界が曖昧。",
    ("出版する", "から", "source"): "出版元を起点とする読みはあり得るが、動作主との区別が文脈依存。",
    ("乗り入れる", "が", "agent"): "人の動作主には合うが、型 ARTIFACT の主語には entity が合う可能性がある。",
    ("体操する", "を", "patient"): "体操という行為の目的語には見えるが、patient とする境界が曖昧。",
}


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    claims_bytes = CLAIMS.read_bytes()
    frozen = json.loads(CLAIMS_FREEZE.read_text(encoding="utf-8"))
    if hashlib.sha256(claims_bytes).hexdigest() != frozen["sha256"]:
        raise SystemExit("N4 claim input no longer matches its pre-label freeze")
    claims = [json.loads(line) for line in claims_bytes.decode("utf-8").splitlines() if line.strip()]
    old = {(row["word"], row["particle"], row["role"]): row["visual_label"]
           for row in jsonl(OLD_LABELS)}
    keys = [(row["word"], row["particle"], row["role"]) for row in claims]
    if len(keys) != len(set(keys)):
        raise SystemExit("duplicate N4 claim key")
    labels = []
    for claim in claims:
        key = (claim["word"], claim["particle"], claim["role"])
        if key in ERRORS:
            label, note = "誤り", ERRORS[key]
        elif key in DOUBTFUL:
            label, note = "疑わしい", DOUBTFUL[key]
        else:
            label = "正しい"
            note = "助詞と役割の組み合わせに明瞭な不整合を認めなかった。"
        labels.append({
            "word": claim["word"], "particle": claim["particle"], "role": claim["role"],
            "types": claim["types"], "confirmed": claim["confirmed"],
            "confirmed_types": claim["confirmed_types"], "backed_by": claim["backed_by"],
            "visual_label": label, "note": note,
            "previous_r9_label_reference_only": old.get(key),
            "evidence_type": "testimony", "reviewer": "Codex gpt-6-luna",
        })
    if set(ERRORS) - set(keys) or set(DOUBTFUL) - set(keys):
        raise SystemExit("a manual review decision does not match a frozen N4 claim")
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                              for row in labels), encoding="utf-8")
    print(json.dumps({"labels": len(labels), "confirmed_labels": sum(row["confirmed"] for row in labels),
                      "label_counts": {label: sum(row["visual_label"] == label for row in labels)
                                       for label in ("正しい", "疑わしい", "誤り", "UNCLASSIFIED")},
                      "evidence_type": "testimony"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
