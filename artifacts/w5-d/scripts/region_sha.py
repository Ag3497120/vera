"""W5-d: sha256 of every <!-- NAME:begin -->...<!-- NAME:end --> region (inner text, markers excluded) in the given docs.
Regions whose name starts with 'w5d-' are skipped (they are this ticket's own). Usage: region_sha.py <doc.md>... """
import hashlib, re, sys
for p in sys.argv[1:]:
    t = open(p, encoding='utf-8').read()
    for m in re.finditer(r'<!-- ([\w-]+):begin -->(.*?)<!-- \1:end -->', t, re.S):
        if m.group(1).startswith('w5d-'): continue
        print(p.split('/')[-1], m.group(1), hashlib.sha256(m.group(2).encode('utf-8')).hexdigest())
