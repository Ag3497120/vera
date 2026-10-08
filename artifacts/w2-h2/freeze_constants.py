"""Print the time and the sha256 of the constant tables of verantyx/routing_from_text.py (canonical JSON, so the hash does not depend on
PYTHONHASHSEED).  Usage: freeze_constants.py   (stdout is artifacts/w2-h2/constants_frozen.txt)."""
import hashlib
import json
import subprocess

import verantyx.routing_from_text as m


def canon(value):
    if isinstance(value, dict):
        return [[canon(k), canon(v)] for k, v in sorted(value.items(), key=lambda kv: json.dumps(canon(kv[0]), ensure_ascii=False))]
    if isinstance(value, (set, frozenset)):
        return sorted(canon(v) for v in value)
    if isinstance(value, tuple):
        return [canon(v) for v in value]
    return value


blob = json.dumps([[name, canon(getattr(m, name))] for name in m.CONSTANT_NAMES], ensure_ascii=False, sort_keys=False)
print(subprocess.run(["date", "+%Y-%m-%d %H:%M:%S %z"], capture_output=True, text=True).stdout.strip())
print(hashlib.sha256(blob.encode("utf-8")).hexdigest())
print("sizes:", {name: len(getattr(m, name)) for name in m.CONSTANT_NAMES})
print(blob)
