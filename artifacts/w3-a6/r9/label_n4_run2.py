#!/usr/bin/env python3
"""Expand the manual, pre-check visual decisions into a keyed N4 table."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
INPUT = ROOT / "artifacts/w3-a6/r9/n4_claims_run2_prefreeze.jsonl"
OUTPUT = ROOT / "artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl"

# These judgments were made from the predicate, particle, role and declared
# noun types only, before exposing any run2 distribution checks.
DECISIONS = {
    ("つぼむ", "が", "entity"): ("疑わしい", "entity は適合するが、型に通常の語義と結びつきにくい ARTIFACT も混在する。"),
    ("つぼむ", "を", "patient"): ("誤り", "通常の『つぼむ』は花などが閉じる自動詞で、を格の対象を取らない。"),
    ("総括する", "に", "standard"): ("誤り", "規約の standard は比較基準で、総括するの普通の意味に比較項がない。"),
    ("吸引する", "に", "goal"): ("疑わしい", "到達点の読みはありうるが、PERSON を goal とする普通の用法は判然としない。"),
    ("締結する", "で", "time"): ("疑わしい", "期間を表す読みはありうるが、締結するに普通伴う時の格かは曖昧。"),
    ("内線する", "を", "patient"): ("疑わしい", "『内線をする』は可能だが、内線するのを格が独立した対象として取るか不明。"),
    ("怒る", "に", "cause"): ("疑わしい", "に格は怒りの向け先にも原因にも読め、役割を一意に見分けにくい。"),
    ("取り合わせる", "と", "companion"): ("誤り", "と格は通常、組み合わせる対象を列挙し、共同行為者を表さない。"),
    ("繰り上がる", "に", "goal"): ("疑わしい", "順位などの移行先にも読める一方、変化の結果 result との境界が曖昧。"),
    ("否決する", "に", "cause"): ("疑わしい", "に格の原因用法は排除できないが、能動の否決するに普通伴う格か不明。"),
    ("解任する", "から", "source"): ("疑わしい", "役職・所属から外す起点の読みはありうるが、申告型 GROUP_ORG との適合が曖昧。"),
    ("相殺する", "と", "companion"): ("疑わしい", "相殺する対象の並列には読めるが、companion は一緒に行う人を定義する。"),
    ("沿う", "と", "companion"): ("疑わしい", "沿うに同行者を加える読みはありうるが、普通の語義での結びつきが弱い。"),
    ("沿う", "に", "goal"): ("疑わしい", "に格は沿う基準・経路を示し、到達点 goal とは異なる可能性がある。"),
    ("計上する", "で", "cause"): ("疑わしい", "原因の句が付く余地はあるが、計上するに普通伴う原因格か不明。"),
    ("体操する", "を", "patient"): ("疑わしい", "EVENT_ACT は自然だが、BODY_PART が体操するの直接対象となるか曖昧。"),
    ("負担する", "に", "recipient"): ("誤り", "普通は費用などを負担する。受け手を取るなら『負担を負わせる』等の別構文。"),
    ("変速する", "を", "patient"): ("疑わしい", "変速機を変速する読みは可能だが、普通の『変速する』は自動詞的にも使う。"),
    ("とかす", "に", "goal"): ("疑わしい", "溶かす用法で溶媒・結果のどちらにも読め、goal と断定しにくい。"),
    ("暮らす", "から", "source"): ("疑わしい", "起点の句は成立しうるが、暮らすに普通伴う格か語義が一定しない。"),
    ("捻る", "に", "goal"): ("疑わしい", "に格の接触先・到達先はありうるが、捻るの普通の項か曖昧。"),
    ("感じ取れる", "が", "experiencer"): ("誤り", "規約の experiencer は間接受身の影響を受ける人で、知覚他動詞の主語ではない。"),
    ("考える", "に", "recipient"): ("誤り", "考えるの普通の枠に情報の受取人はなく、に格の人を recipient とする根拠がない。"),
}

rows = [json.loads(line) for line in INPUT.read_text(encoding="utf-8").splitlines() if line.strip()]
out = []
seen = set()
for row in rows:
    for claim in row["claims"]:
        key = (row["word"], claim["particle"], claim["role"])
        if key in seen:
            raise SystemExit(f"duplicate role claim: {key}")
        seen.add(key)
        label, note = DECISIONS.get(key, ("正しい", ""))
        out.append({"word": row["word"], **claim, "visual_label": label, "note": note})
unknown = set(DECISIONS) - seen
if unknown:
    raise SystemExit(f"manual decision keys not present in frozen claims: {sorted(unknown)}")
OUTPUT.write_text(
    "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in out),
    encoding="utf-8",
)
print(json.dumps({"visual_role_rows": len(out), "precheck_only": True,
                  "labels": {label: sum(item["visual_label"] == label for item in out)
                             for label in ("正しい", "疑わしい", "誤り")},
                  "output": str(OUTPUT)}, ensure_ascii=False, indent=2))
