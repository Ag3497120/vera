import json, hashlib, sys
import verantyx.semantic_read as SR, verantyx.semantic_reader as R
out = {}
for mod in (SR, R):
    for k, v in sorted(vars(mod).items()):
        if k.startswith('__'): continue
        if isinstance(v, (set, frozenset, tuple, list, dict)) and k.upper() == k.lstrip('_').upper() or (k.startswith('_') and k[1:].isupper()):
            try:
                if isinstance(v, dict): val = {str(a): str(b) for a, b in sorted(v.items(), key=lambda kv: str(kv[0])) if k != 'NOT_PRODUCED'}
                elif isinstance(v, (set, frozenset)): val = sorted(map(str, v))
                else: val = list(map(str, v))
            except Exception: continue
            out[mod.__name__ + '.' + k] = val
text = json.dumps(out, ensure_ascii=False, sort_keys=True)
print(len(out), hashlib.sha256(text.encode()).hexdigest(), file=sys.stderr)
print(text)
