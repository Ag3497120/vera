"""O6: the registration came before the data, in order; the registered section is the one that was hashed (or its changes are all logged).

    python tests/observe/check_prereg_order.py --prereg artifacts/w3-c/prereg.txt --frozen tests/observe/data/FROZEN.json --doc docs/OBSERVATION.md
Prints `prereg_before_data: ok`, `frozen_order: ok`, `frozen_files_unchanged: ok`, and `section_sha: unchanged` or `section_sha: changed, changes_logged: N`.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
FMT = '%Y-%m-%d %H:%M:%S %z'
ORDER = ['inputs', 'inputs_add1', 'expected', 'first_observation', 'disagreements', 'disagreements_o4', 'inputs_r2', 'expected_r2', 'first_observation_r2', 'disagreements_r2']


def section(doc_text):
    m = re.search(r'<!-- prereg:begin -->\n(.*?)<!-- prereg:end -->', doc_text, re.S)
    return m.group(1) if m else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--prereg', required=True)
    ap.add_argument('--frozen', required=True)
    ap.add_argument('--doc', required=True)
    args = ap.parse_args(argv)
    pre = {}
    for line in Path(args.prereg).read_text(encoding='utf-8').splitlines():
        m = re.match(r'(registered_at|recorded_at|sha256_first|sha256_after_logged_changes|logged_changes|change3_recorded_at|sha256_current|logged_changes_current): (\S+(?: \S+)*)', line)
        if m and m.group(1) not in pre: pre[m.group(1)] = m.group(2)
    registered = datetime.strptime(pre['registered_at'].split(' (')[0], FMT)
    frozen = json.loads(Path(args.frozen).read_text(encoding='utf-8'))['stages']
    ok = True
    first_data = min(datetime.strptime(v['date'], FMT) for v in frozen.values())
    before = registered < first_data
    print('prereg_before_data: %s (registered %s, first data %s)' % ('ok' if before else 'FAIL', registered, first_data))
    ok &= before
    dates = [(name, datetime.strptime(frozen[name]['date'], FMT)) for name in ORDER if name in frozen]
    in_order = all(dates[i][1] <= dates[i + 1][1] for i in range(len(dates) - 1))
    print('frozen_order: %s (%s)' % ('ok' if in_order else 'FAIL', ' < '.join('%s %s' % (n, d.strftime('%H:%M:%S')) for n, d in dates)))
    ok &= in_order
    changed_files = []
    for stage in frozen.values():
        for rel, sha in stage['files'].items():
            path = TREE / 'tests' / 'observe' / 'data' / rel
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha: changed_files.append(rel)
    print('frozen_files_unchanged: %s%s' % ('ok' if not changed_files else 'FAIL', '' if not changed_files else ' ' + ', '.join(changed_files)))
    ok &= not changed_files
    doc = Path(args.doc).read_text(encoding='utf-8')
    body = section(doc)
    sha = hashlib.sha256(body.encode('utf-8')).hexdigest() if body is not None else None
    log = doc.split('### 事前登録の変更記録', 1)[1] if '### 事前登録の変更記録' in doc else ''
    logged = len(re.findall(r'^\d+\. \d{4}-\d\d-\d\d ', log, re.M))
    # round 2 (docs change record 3): the section was changed AFTER the first observation. The change is dated, and everything made for the new rule came after it.
    if 'change3_recorded_at' in pre:
        change3 = datetime.strptime(pre['change3_recorded_at'].split(' (')[0], FMT)
        r2 = [(n, datetime.strptime(frozen[n]['date'], FMT)) for n in ('inputs_r2', 'expected_r2', 'first_observation_r2') if n in frozen]
        r2_ok = all(change3 < d for _n, d in r2) and all(r2[i][1] <= r2[i + 1][1] for i in range(len(r2) - 1)) and len(r2) >= 1
        print('change3_before_r2_data: %s (change 3 recorded %s; %s)' % ('ok' if r2_ok else 'FAIL', change3.strftime('%H:%M:%S'), ' < '.join('%s %s' % (n, d.strftime('%H:%M:%S')) for n, d in r2)))
        ok &= r2_ok
    if sha == pre.get('sha256_first'):
        print('section_sha: unchanged')
    elif sha in (pre.get('sha256_after_logged_changes'), pre.get('sha256_current')):
        n = int(pre.get('logged_changes_current' if sha == pre.get('sha256_current') else 'logged_changes', '0'))
        good = logged >= n >= 1
        print('section_sha: changed, changes_logged: %d (prereg.txt records %d change(s) of the section; the log has %d entries, one of them a clarification that left the section alone)' % (n if good else 0, n, logged))
        ok &= good
    else:
        print('section_sha: changed and not recorded in prereg.txt: FAIL')
        ok = False
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
