"""The three W5-a H1 sentences through verantyx.semantic_read.read. Run once per tree (PYTHONPATH=<tree>)."""
import json
from verantyx import semantic_read

print("semantic_read loaded from:", semantic_read.__file__)
for text in ("尼僧が月報を発行した。", "複数の人物が会報を発行した。", "会社が試験機を公開した。"):
    out = semantic_read.read(text)
    c = (out.get("clauses") or [{}])[0]
    print(json.dumps({"text": text, "readable": out.get("readable"), "abstain": out.get("abstain"),
                      "predicate": c.get("predicate"), "roles": c.get("roles")}, ensure_ascii=False))
