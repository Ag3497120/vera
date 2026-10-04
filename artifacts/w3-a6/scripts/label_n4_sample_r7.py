#!/usr/bin/env python3
"""Freeze the human visual labels for the already frozen N4 claim sample."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
SOURCE = ART / "n4_claims_prefreeze.jsonl"
OUTPUT = ART / "n4_visual_labels_r7.jsonl"

# Labels are assigned from the word and generated claim only; no placement or
# role-frame confirmation fields are read by this script.
OVERRIDES = {
    ("印字する", "に", "goal"): ("疑わしい", "印字対象への到達点とも対象場所とも読め、通常の用法だけでは役割を固定しにくい。"),
    ("つぼむ", "が", "entity"): ("疑わしい", "植物のつぼみには合うが、申告型にはこの語の主語として疑わしいものも混じる。"),
    ("吸引する", "を", "patient"): ("疑わしい", "吸引物という役割は合うが、身体部位を含む型の一般性は明確でない。"),
    ("任せる", "に", "causee"): ("誤り", "任せるは使役形でなく、に句は委ね先であって実際に元の動作をする使役相手ではない。"),
    ("締結する", "と", "companion"): ("疑わしい", "契約相手は共同行為者より相手方として読むことが多い。"),
    ("売れる", "が", "agent"): ("誤り", "売れるの主語は通常売られる商品で、申告された人・組織の動作主ではない。"),
    ("売れる", "に", "source"): ("誤り", "売れるのに句は通常売り先・買い手で、起点や出どころではない。"),
    ("始末する", "を", "patient"): ("疑わしい", "始末するの対象には人も普通に来るが、申告型に人が含まれず意味の幅を捉えきれていない。"),
    ("取り合わせる", "と", "companion"): ("誤り", "申告型は人工物・飲食物で、規約のcompanion（共に行う人）に当たらない。"),
    ("抜け替わる", "が", "agent"): ("疑わしい", "毛や歯などが主語になる用法では人・動物そのものをagentとする型が合わない。"),
    ("内線する", "を", "patient"): ("疑わしい", "普通は相手に内線する形が中心で、を句の申告は定着した項か判然としない。"),
    ("感じ取れる", "が", "agent"): ("疑わしい", "感じ取られる内容がが句になる用法も普通で、知覚者の動作主だけに固定しにくい。"),
    ("沿う", "と", "companion"): ("誤り", "沿うのと句は規約の共に行う人を表す通常の項にならない。"),
    ("体操する", "を", "patient"): ("疑わしい", "体操をするという名詞＋する表現はあるが、述語の外部対象としてのpatientかは判然としない。"),
    ("礼する", "を", "patient"): ("疑わしい", "礼する自体の普通の格枠が限られ、申告された対象関係を確定しにくい。"),
    ("礼する", "に", "agent"): ("誤り", "礼するのに句は礼の相手であり、行為者ではない。"),
    ("とかす", "を", "patient"): ("疑わしい", "かな表記は溶かす・梳かすを区別せず、申告された型の幅が不確か。"),
    ("とかす", "に", "result"): ("疑わしい", "溶かすの結果先には合うが、同音異義の梳かすではこの枠にならない。"),
    ("食べ残す", "を", "patient"): ("疑わしい", "食べ物は合うが、人工物・情報・出来事まで通常の対象型とする根拠が弱い。"),
    ("考える", "に", "quotation"): ("誤り", "考えるの内容を示す格は通常と等で、に句を引用内容にする規約上の根拠がない。"),
    ("とかす", "が", "agent"): ("疑わしい", "溶かすでは行為者に合うが、かな表記が別の普通の用法も含む。"),
    ("揶揄する", "を", "patient"): ("疑わしい", "対象役割は合うが、動物・出来事までの型は一般的な対象として幅が広い。"),
    ("寄進する", "を", "patient"): ("疑わしい", "物品の対象は合うが、抽象概念を寄進物に含めるのは通常の用法から外れる。"),
    ("標識する", "を", "patient"): ("疑わしい", "標識対象は合うが、PLACEが直接の対象となる型は意味により揺れる。"),
}

rows = [json.loads(line) for line in SOURCE.read_text(encoding="utf-8").splitlines() if line.strip()]
output = []
used = set()
for row in rows:
    roles = []
    for particle, claims in (row.get("frame") or {}).items():
        for claim in claims:
            key = (row["word"], particle, claim["role"])
            label, note = OVERRIDES.get(key, ("正しい", "規約§2の役割と申告型に目視で明らかな衝突がない。"))
            used.add(key)
            roles.append({"particle": particle, **claim, "visual_label": label, "note": note})
    output.append({"rank": row["rank"], "word": row["word"], "availability": row["availability"], "roles": roles})

unknown = set(OVERRIDES) - used
if unknown:
    raise SystemExit("visual labels refer to absent claims: " + repr(sorted(unknown)))
OUTPUT.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in output), encoding="utf-8")
labels = [role["visual_label"] for row in output for role in row["roles"]]
print(json.dumps({
    "sample_words": len(output),
    "role_claims": len(labels),
    "correct": labels.count("正しい"),
    "suspicious": labels.count("疑わしい"),
    "obvious_errors": labels.count("誤り"),
    "abstained_words": sum(row["availability"] == "abstained" for row in output),
    "missing_words": sum(row["availability"] == "missing" for row in output),
    "labels_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
}, ensure_ascii=False, indent=2))
