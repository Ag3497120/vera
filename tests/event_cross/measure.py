"""E2 measurements over the frozen test sentences.

  measure.py --out events_all.jsonl --summary e2_summary.json [--classes e2_classes.json]
      events_all.jsonl : the output of `semantic_read --events` for every sentence, exactly as the entry prints it (one line each);
                         the ids are in the file given by --ids (same order)
      e2_summary.json  : counts by status, language, tag and topic; crosses, arms, arm ties, relations (by type); agreement verdicts and
                         reasons; abstain kinds and first reasons; the `explain` sentences
  measure.py --timing timing.json
      per-sentence time of read(), build_crosses() (stub lookup) and read_events(), 3 rounds over all sentences (the first round is dropped);
      only when the 1-minute load average is below 8 (else `{"skipped": "load", "load": ...}` is written)
"""
import argparse
import io
import json
import statistics
import subprocess
import sys
import time
from collections import Counter
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(TREE)); sys.path.insert(0, str(HERE))

import classify    # noqa: E402
from verantyx import event_cross as E    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402

LOAD_LIMIT = 8.0


def loadavg():
    out = subprocess.run(['/usr/sbin/sysctl', '-n', 'vm.loadavg'], capture_output=True, text=True).stdout.split()
    return [float(x) for x in out if x not in '{}']


def run_entry(text):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = SR.main(['--text=' + text, '--events'])
    return buf.getvalue(), code


def summarize(rows):
    """rows: [(lang, sentence, output object)]"""
    s = {'sentences': len(rows), 'by_lang': Counter(), 'status': Counter(), 'status_by_lang': {}, 'status_by_tag': {}, 'status_by_topic': {},
         'crosses': 0, 'arms': 0, 'arm_ties': 0, 'relations': 0, 'relation_types': Counter(), 'agreement': Counter(), 'not_checked_by_reason': Counter(),
         'abstain_kind': Counter(), 'abstain_first_reason': Counter(), 'roles': Counter(), 'explain': {}, 'clauses_per_sentence': Counter(),
         'error_outputs': 0}
    for lang, sent, out in rows:
        ev = out['events']
        s['by_lang'][lang] += 1; s['status'][ev['status']] += 1
        s['status_by_lang'].setdefault(lang, Counter())[ev['status']] += 1
        for t in sent['tags']: s['status_by_tag'].setdefault(t, Counter())[ev['status']] += 1
        s['status_by_topic'].setdefault(sent['topic'], Counter())[ev['status']] += 1
        s['crosses'] += ev['counts']['crosses']; s['arms'] += ev['counts']['arms']; s['arm_ties'] += ev['counts']['arm_ties']
        s['relations'] += len(ev['relations'])
        for r in ev['relations']: s['relation_types'][r['type']] += 1
        for k, v in ev['counts']['agreement'].items(): s['agreement'][k] += v
        for k, v in ev['counts']['not_checked_by_reason'].items(): s['not_checked_by_reason'][k] += v
        for cross in ev['crosses']:
            for role in cross['arms']: s['roles'][role] += 1
        if ev['abstain'] is not None:
            s['abstain_kind'][ev['abstain']['kind']] += 1
            s['abstain_first_reason'][ev['abstain']['reasons'][0].split(':')[0]] += 1
        s['clauses_per_sentence'][str(ev['counts']['crosses'])] += 1
        if 'error' in out: s['error_outputs'] += 1
    explain = [(lang, sent, out) for lang, sent, out in rows if 'explain' in sent['tags']]
    for lang in classify.LANGS:
        sub = [(sent, out) for l, sent, out in explain if l == lang]
        s['explain'][lang] = {'sentences': len(sub), 'crossed': sum(1 for _, o in sub if o['events']['status'] == 'CROSSED'),
                              'abstained': sum(1 for _, o in sub if o['events']['status'] == 'ABSTAINED'),
                              'crossed_ids': [x['id'] for x, o in sub if o['events']['status'] == 'CROSSED']}
    for k in ('by_lang', 'status', 'relation_types', 'agreement', 'not_checked_by_reason', 'abstain_kind', 'abstain_first_reason', 'roles', 'clauses_per_sentence'):
        s[k] = dict(sorted(s[k].items()))
    for k in ('status_by_lang', 'status_by_tag', 'status_by_topic'):
        s[k] = {a: dict(sorted(b.items())) for a, b in sorted(s[k].items())}
    return s


def timing(sentences):
    before = loadavg()
    if before[0] >= LOAD_LIMIT: return {'skipped': 'load', 'load': before, 'limit': LOAD_LIMIT}
    per = {'read': [], 'build_crosses_stub': [], 'read_events': []}
    for rnd in range(3):
        for text in sentences:
            t0 = time.perf_counter(); got = SR.read(text); t1 = time.perf_counter()
            E.build_crosses(got); t2 = time.perf_counter()
            E.read_events(text); t3 = time.perf_counter()
            if rnd > 0:
                per['read'].append(t1 - t0); per['build_crosses_stub'].append(t2 - t1); per['read_events'].append(t3 - t2)
    after = loadavg()
    out = {'sentences': len(sentences), 'rounds_kept': 2, 'load_before': before, 'load_after': after, 'unit': 'ms per sentence'}
    for k, v in per.items():
        out[k] = {'median': round(statistics.median(v) * 1000, 4), 'max': round(max(v) * 1000, 4), 'n': len(v)}
    if max(before[0], after[0]) >= LOAD_LIMIT: out['note'] = 'load rose to or above %s during the measurement' % LOAD_LIMIT
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out'); ap.add_argument('--ids'); ap.add_argument('--summary'); ap.add_argument('--timing')
    args = ap.parse_args(argv)
    sents = [(l, s) for l in classify.LANGS for s in classify.load_all('sentences', l)]
    if args.out:
        rows, lines = [], []
        for lang, sent in sents:
            text, code = run_entry(sent['text'])
            assert code == 0, sent['id']
            lines.append(text); rows.append((lang, sent, json.loads(text)))
        Path(args.out).write_text(''.join(lines), encoding='utf-8')
        if args.ids: Path(args.ids).write_text(''.join(s['id'] + '\n' for _, s in sents), encoding='utf-8')
        if args.summary:
            Path(args.summary).write_text(json.dumps(summarize(rows), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            print(Path(args.summary).read_text(encoding='utf-8'))
    if args.timing:
        res = timing([s['text'] for _, s in sents])
        Path(args.timing).write_text(json.dumps(res, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
