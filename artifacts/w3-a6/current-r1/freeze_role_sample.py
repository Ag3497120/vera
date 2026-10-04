import hashlib
import json
import random
from pathlib import Path

needs = Path("artifacts/w3-a6/current-r1/needs_role.jsonl")
out = Path("artifacts/w3-a6/current-r1/role_sample_words.jsonl")
words = sorted({json.loads(line)["word"] for line in needs.read_text(encoding="utf-8").splitlines() if line})
sample = random.Random(20261004).sample(words, 60)
text = "".join(json.dumps({"rank": i, "word": word}, ensure_ascii=False) + "\n"
               for i, word in enumerate(sample, 1))
out.write_text(text, encoding="utf-8")
print(json.dumps({"population": len(words), "sample": len(sample), "seed": 20261004,
                  "rule": "sample(sorted(unique(needs_role.words)), 60)",
                  "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}, ensure_ascii=False))
