"""Developer-only P2 measurement over the spent sealed1 question prompts."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from verantyx.intent_frames import parse
from verantyx.question import read


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path.home() / "Projects" / "vera-ja-sealed1")
    args = parser.parse_args()

    rows = [item for path in sorted(args.data.glob("doc_*.json"))
            for item in json.loads(path.read_text(encoding="utf-8"))["questions"]]
    prompts = [item["prompt"] for path in sorted(args.data.glob("ab_*.json"))
               for item in json.loads(path.read_text(encoding="utf-8"))["items"]]
    labels = Counter(item["kind"] for item in rows)
    predictions = [(item["kind"], read(item["q"]).kind.value) for item in rows]
    compatible = [(gold, predicted) for gold, predicted in predictions
                  if gold not in ("unanswerable", "injection")]
    before_misfires = sum(parse(prompt).get("verdict") == "INTENT" for prompt in prompts)
    after_misfires = sum(read(prompt).intent_op.value.verdict == "INTENT" for prompt in prompts)
    print(json.dumps({
        "document_questions": len(rows),
        "kind_labels": dict(sorted(labels.items())),
        "before_typed_kind_predictions": 0,
        "after_raw_exact": sum(gold == predicted for gold, predicted in predictions),
        "after_compatible_exact": sum(gold == predicted for gold, predicted in compatible),
        "compatible_total": len(compatible),
        "per_kind": {kind: {
            "correct": sum(gold == predicted == kind for gold, predicted in predictions),
            "total": count,
        } for kind, count in sorted(labels.items())},
        "ability_prompts": len(prompts),
        "before_operation_misfires": before_misfires,
        "after_operation_misfires": after_misfires,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
