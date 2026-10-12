#!/usr/bin/env python3
"""Mechanical validation of the AUDITED bank 4 (bank4.tsv, adversarial unanswerable items) and its loom task file.

Run from anywhere: python3 check_bank4.py  -> writes check.txt next to itself.
Inputs: bank4.tsv here, ../data/S300_fulllead.jsonl (articles), ../bank2/data/fulllead_sents.jsonl (the same corpus split on 「。」),
../loom/tasks_unans_adv.jsonl.  Reads nothing else (no Vera code, no hidden bank).

ERROR rules
  corpus     the sentence file is the lossless 0-based 「。」 split of the article file (concatenation per title equals text; source = title#i)
  rows       header (bank3 columns); ids ADV-nnn unique and increasing; kind in the four kinds; corpus fulllead; gold empty;
             audit in {valid, fixed}; question ends with 。 and contains no negation (ない / ません / 以外 / 除く)
  evidence   every id resolves (0-based); at most two ids, one article; at least one cited sentence contains the subject verbatim
  subject    occurs verbatim in the question
  notes      a) b) c) present; the c) distractor occurs verbatim in the corpus (INFO if it also occurs in the question)
  kinds      >= 8 per kind
  tasks      4 rows per item (record_only, constructed_allowed, free_text control, no_tools); task_id bank4/ADV-nnn.<mode>;
             text = question without its final 「。」; no gold key; schema keys of tasks_bank2.jsonl (+ control)
INFO: per kind counts, audit counts, subjects/articles used, articles shared with bank2/bank3.
"""
import csv, hashlib, json, os, re, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
L3 = os.path.dirname(HERE)
ART = os.path.join(L3, 'data', 'S300_fulllead.jsonl')
SENTS = os.path.join(L3, 'bank2', 'data', 'fulllead_sents.jsonl')
BANK = os.path.join(HERE, 'bank4.tsv')
TASKS = os.path.join(L3, 'loom', 'tasks_unans_adv.jsonl')
KINDS = ('near-fact', 'same-slot', 'numeric', 'entity-swap')
COLS = ['#id', 'kind', 'corpus', 'subject', 'question', 'gold', 'evidence', 'notes', 'audit']
NEG = re.compile(r'ない|ません|以外|除く')

out, errs = [], []
def err(m): errs.append(m)
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

arts = [json.loads(l) for l in open(ART, encoding='utf-8')]
sents = [json.loads(l) for l in open(SENTS, encoding='utf-8')]
by = {}
for s in sents: by.setdefault(s['title'], []).append(s['sent'])
for a in arts:
    if ''.join(by.get(a['title'], [])) != a['text']: err('corpus: sentence split differs from article %s' % a['title'])
for s in sents:
    t, i = s['source'].rsplit('#', 1)
    if t != s['title'] or by[t][int(i)] != s['sent']: err('corpus: bad source %s' % s['source'])
blob = '\n'.join(a['title'] + '\n' + a['text'] for a in arts)
out.append('corpus: %d articles, %d sentences; S300_fulllead.jsonl %s; fulllead_sents.jsonl %s' % (len(arts), len(sents), sha(ART), sha(SENTS)))

lines = open(BANK, encoding='utf-8').read().splitlines()
if lines[0].split('\t') != COLS: err('header %r' % lines[0])
rows = [dict(zip(COLS, l.split('\t'))) for l in lines[1:]]
ids = [r['#id'] for r in rows]
if len(set(ids)) != len(ids) or ids != sorted(ids) or not all(re.fullmatch(r'ADV-\d{3}', i) for i in ids): err('ids not unique/ordered ADV-nnn')
for r in rows:
    i, q, subj = r['#id'], r['question'], r['subject']
    if len(r) != len(COLS): err('%s: column count' % i)
    if r['kind'] not in KINDS: err('%s: kind %s' % (i, r['kind']))
    if r['corpus'] != 'fulllead': err('%s: corpus' % i)
    if r['gold'] != '': err('%s: gold not empty' % i)
    if r['audit'] not in ('valid', 'fixed'): err('%s: audit %s' % (i, r['audit']))
    if not q.endswith('。'): err('%s: question does not end with 。' % i)
    if NEG.search(q): err('%s: negation in question' % i)
    if subj not in q: err('%s: subject %r not in question' % (i, subj))
    ev = r['evidence'].split(';')
    titles = {e.rsplit('#', 1)[0] for e in ev}
    if len(ev) > 2 or len(titles) != 1: err('%s: evidence %s' % (i, r['evidence']))
    got = []
    for e in ev:
        t, k = e.rsplit('#', 1)
        try: got.append(by[t][int(k)])
        except (KeyError, IndexError, ValueError): err('%s: evidence %s does not resolve' % (i, e))
    if got and not any(subj in s for s in got): err('%s: no cited sentence contains the subject' % i)
    m = re.fullmatch(r'a\) .+; b\) .+; c\) (.+)', r['notes'])
    if not m: err('%s: notes not a)/b)/c)' % i); continue
    c = m.group(1)
    if c not in blob: err('%s: c) %r not in corpus' % (i, c))
    if c in q: out.append('INFO %s: c) %r also occurs in the question' % (i, c))
kc = Counter(r['kind'] for r in rows)
for k in KINDS:
    if kc[k] < 8: err('kind %s has %d < 8' % (k, kc[k]))
out.append('rows: %d; kinds: %s' % (len(rows), ', '.join('%s=%d' % (k, kc[k]) for k in KINDS)))
ac = Counter((r['kind'], r['audit']) for r in rows)
out.append('audit: ' + ', '.join('%s %d valid / %d fixed' % (k, ac[(k, 'valid')], ac[(k, 'fixed')]) for k in KINDS))
arts_used = Counter(r['evidence'].split(';')[0].rsplit('#', 1)[0] for r in rows)
out.append('INFO articles used: %d; shared by >1 item: %s' % (len(arts_used), {t: n for t, n in arts_used.items() if n > 1}))
for name, p in (('bank2', os.path.join(L3, 'bank2', 'bank2.tsv')), ('bank3', os.path.join(L3, 'bank3', 'bank3.tsv'))):
    if os.path.exists(p):
        other = set()
        for l in open(p, encoding='utf-8').read().splitlines()[1:]:
            f = l.split('\t')
            for e in f[6].split(';'): other.add(e.rsplit('#', 1)[0])
        out.append('INFO articles also cited by %s: %d (%s)' % (name, len(set(arts_used) & other), ', '.join(sorted(set(arts_used) & other))))

T = [json.loads(l) for l in open(TASKS, encoding='utf-8')]
KEYS = {'bank2_id', 'base', 'corpus', 'lang', 'mode', 'task_id', 'text', 'tiers'}
want = {}
for r in rows:
    txt = r['question'][:-1]
    for lab, mode, ctl in (('record_only', 'record_only', None), ('constructed_allowed', 'constructed_allowed', None),
                           ('free_text', 'record_only', 'free_text'), ('no_tools', 'no_tools', 'no_tools')):
        want['bank4/%s.%s' % (r['#id'], lab)] = (r['#id'], mode, ctl, txt)
seen = set()
for d in T:
    tid = d.get('task_id')
    if tid not in want or tid in seen: err('tasks: unexpected/duplicate %s' % tid); continue
    seen.add(tid)
    bid, mode, ctl, txt = want[tid]
    if set(d) - {'control'} != KEYS or 'gold' in d: err('tasks: keys %s' % tid)
    if (d['bank2_id'], d['base'], d['mode'], d.get('control'), d['text']) != (bid, bid, mode, ctl, txt): err('tasks: fields %s' % tid)
    if d['corpus'] != 'experiments/line3/bank2/data/fulllead_sents.jsonl' or d['lang'] != 'prose' or d['tiers'] != ['RUN', 'WORD', 'CHAR']: err('tasks: corpus/lang/tiers %s' % tid)
if seen != set(want): err('tasks: missing %d rows' % len(set(want) - seen))
out.append('tasks: %d rows (%d items x 4 modes); %s' % (len(T), len(rows), sha(TASKS)))
out.append('bank4.tsv sha256 %s' % sha(BANK))
out.append('ERRORS: %d' % len(errs))
out += ['- ' + e for e in errs]
open(os.path.join(HERE, 'check.txt'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('\n'.join(out))
sys.exit(1 if errs else 0)
