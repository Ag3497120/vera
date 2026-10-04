"""Compare the independent review's frozen direction/place pairs using only POS gate inputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys


TREE = Path(__file__).resolve().parents[3]
INPUT = Path("/private/tmp/w5f_review_r1/holdout.r1.jsonl")
EXPECTED_SHA256 = "aea0fb3f6b8158dc8884851e019bd538ee7f2c0305f4e2808c40c26dc6732617"
sys.path.insert(0, str(TREE))

from verantyx import semantic_reader as R


raw = INPUT.read_bytes()
digest = hashlib.sha256(raw).hexdigest()
if digest != EXPECTED_SHA256:
    raise SystemExit(f"HOLDOUT_HASH_MISMATCH {digest}")
rows = {row["id"]: row for row in
        (json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip())}
same_pos = same_shape = narrow_hits = wide_direction_hits = wide_place_hits = 0
for number in range(1, 33):
    direction = rows[f"F2_A{number:02d}"]
    place = rows[f"F2_R{number:02d}"]
    case = next(p for p in ("で", "へ", "から", "に") if p in direction["text"])

    def head_and_gate(row):
        toks = R._tokens(row["text"])
        pi = next(i for i, token in enumerate(toks)
                  if token[0].surface == case and token[0].feature.pos1 == "助詞")
        head = toks[pi - 1]
        role = SimpleNamespace(span=SimpleNamespace(start=head[1], end=head[2]))
        name = {"で": "place", "へ": "goal", "から": "source", "に": "place"}[case]
        gate = R.typed_relational_filler_ja(toks, {"roles": [(name, role)]})
        feature = head[0].feature
        signature = (feature.pos1, feature.pos2, feature.pos3)
        normalized = row["text"].replace(head[0].surface, "<FILLER>", 1)
        return signature, normalized, gate

    direction_pos, direction_shape, direction_gate = head_and_gate(direction)
    place_pos, place_shape, place_gate = head_and_gate(place)
    same_pos += direction_pos == place_pos
    same_shape += direction_shape == place_shape
    narrow_hits += direction_gate is not None
    wide_direction_hits += direction_pos == ("名詞", "普通名詞", "一般")
    wide_place_hits += place_pos == ("名詞", "普通名詞", "一般")
    print(direction["id"], direction_pos, direction_gate, "|",
          place["id"], place_pos, place_gate,
          "| normalized_equal", direction_shape == place_shape)
print("SUMMARY", {"input_sha256": digest, "pairs": 32,
                  "same_pos_triplet": same_pos, "same_syntax_after_filler_mask": same_shape,
                  "current_gate_direction_hits": narrow_hits,
                  "general_noun_directions": wide_direction_hits,
                  "general_noun_place_controls": wide_place_hits})
