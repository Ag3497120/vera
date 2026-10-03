"""W5-d2: sha256 of EVERY <!-- NAME:begin -->...<!-- NAME:end --> region (inner text, markers excluded), w5d-* included. Usage: region_sha_all.py <doc.md>..."""
import hashlib, re, sys
for p in sys.argv[1:]:
    t = open(p, encoding='utf-8').read()
    for m in re.finditer(r'<!-- ([\w-]+):begin -->(.*?)<!-- \1:end -->', t, re.S):
        print(p.split('/')[-1], m.group(1), hashlib.sha256(m.group(2).encode('utf-8')).hexdigest())
