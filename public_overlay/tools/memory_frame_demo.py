#!/usr/bin/env python3
"""Typed memory demo: today's real facts written with witnesses, then asked; closed-choice resolution with a live model."""
import json, os, sys, time, hashlib
sys.path.insert(0, '.')
from verantyx.memory_frame import CodexAsker, Memory, WriteRejected

ROOT = os.path.abspath('.'); LIVE = '--live' in sys.argv
store = '/tmp/memory_frame_demo.jsonl'
if os.path.exists(store): os.remove(store)
m = Memory(store, asker=CodexAsker() if LIVE else None)
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
def tif(path, needle): return {'kind': 'text_in_file', 'path': os.path.join(ROOT, path), 'needle': needle}
H = {'kind': 'testimony', 'by': 'human'}
R = 'verantyx/semantic_route.py'; D = 'docs/ROUND5A_STEREO_ROUTE_2026-10-02.md'; GOAL = 'docs/VERA_GOAL_AND_RESUME.md'
writes = [
 ('DECISION', 'human', None, dict(subject='実装担当', choice='gpt-6-luna最大')),
 ('DECISION', 'human', None, dict(subject='生成作業者', choice='gpt-6-luna低')),
 ('DECISION', 'human', None, dict(subject='Codexの役割', choice='手足')),
 ('FACT', 'claude', tif(GOAL, '独立したCodex'), dict(subject='封印評価', attribute='採点者', value='独立Codex')),
 ('INVARIANT', 'human', tif(GOAL, '同点は棄権'), dict(subject='同点', rule='棄権')),
 ('INVARIANT', 'claude', tif('tests/test_semantic_measure.py', 'test_no_dev_fixture_string_is_hardcoded'), dict(subject='devの文字列', rule='ソース記載禁止')),
 ('FACT', 'claude', {'kind': 'file_sha256', 'path': os.path.join(ROOT, 'results/phase2/run_measure06/answers.jsonl'), 'sha256': sha('results/phase2/run_measure06/answers.jsonl')}, dict(subject='公開dev80', attribute='正答数', value='17')),
 ('FACT', 'claude', {'kind': 'file_sha256', 'path': os.path.join(ROOT, 'results/phase2/run_measure06/answers.jsonl'), 'sha256': sha('results/phase2/run_measure06/answers.jsonl')}, dict(subject='公開dev80', attribute='誤答数', value='0')),
 ('FACT', 'claude', tif(R, 'ANCHOR_CAP = 128'), dict(subject='ルーター', attribute='鍵の上限', value='128')),
 ('FACT', 'claude', tif(R, 'EXPAND_CAP = 8'), dict(subject='ルーター', attribute='追跡の上限', value='8')),
 ('FACT', 'claude', tif(R, 'UNREAD_CAP = 1024'), dict(subject='ルーター', attribute='未読の上限', value='1024')),
 ('FACT', 'claude', tif(R, "EVIDENCE_UNREAD = 'all'"), dict(subject='ルーター', attribute='証拠文書の未読方針', value='all')),
 ('FACT', 'claude', tif(D, '0.77'), dict(subject='ルーター', attribute='4000文書の応答', value='0.77ms')),
 ('FACT', 'claude', tif(D, '110/110'), dict(subject='ルーター', attribute='16000文書の再現率', value='110/110')),
 ('FACT', 'claude', tif(D, '0/40'), dict(subject='平らな経路', attribute='300文書以上の正答', value='0/40')),
 ('FACT', 'claude', H, dict(subject='コーパス', attribute='KEPT件数', value='54251')),
 ('FACT', 'claude', H, dict(subject='コーパス', attribute='保留件数', value='3')),
 ('FACT', 'claude', H, dict(subject='コーパス', attribute='owner なし件数', value='82')),
 ('FACT', 'claude', H, dict(subject='split不明のコーパス', attribute='取込', value='HOLD')),
 ('TASK', 'claude', None, dict(subject='原本への適用', state='保留')),
 ('TASK', 'claude', None, dict(subject='適用検証', state='完了')),
 ('TASK', 'claude', None, dict(subject='結合のチューニング', state='進行中')),
 ('LESSON', 'claude', None, dict(situation='zshの引数展開', fix='明示引数')),
 ('LESSON', 'claude', None, dict(situation='f文字列', fix='式内の逆スラッシュ禁止')),
 ('LESSON', 'claude', None, dict(situation='macOSのtimeout', fix='python側の時間制限')),
 ('LESSON', 'claude', None, dict(situation='macOSのsed', fix='in-place用の空文字列引数')),
 ('QUESTION', 'claude', None, dict(subject='証拠文書の未読方針', question='allとmentionの人間の決定')),
]
t0 = time.perf_counter(); ok = rej = 0; rejected = []
for kind, author, w, slots in writes:
    try: m.write(kind, author, witness=w, **slots); ok += 1
    except WriteRejected as e: rej += 1; rejected.append((kind, slots, e.reason, e.hint))
print(f'written {ok}, rejected {rej} in {(time.perf_counter()-t0)*1000:.0f} ms'); [print('  REJECTED', r) for r in rejected]
qs = [(('実装担当',), 'DECISION', ['gpt-6-luna最大']), (('生成作業者',), 'DECISION', ['gpt-6-luna低']), (('Codexの役割',), 'DECISION', ['手足']),
      (('封印評価', '採点者'), 'FACT', ['独立Codex']), (('同点',), 'INVARIANT', ['棄権']), (('devの文字列',), 'INVARIANT', ['ソース記載禁止']), (('公開dev80', '正答数'), 'FACT', ['17']), (('公開dev80', '誤答数'), 'FACT', ['0']),
      (('ルーター', '鍵の上限'), 'FACT', ['128']), (('ルーター', '追跡の上限'), 'FACT', ['8']), (('ルーター', '未読の上限'), 'FACT', ['1024']),
      (('ルーター', '証拠文書の未読方針'), 'FACT', ['all']), (('ルーター', '4000文書の応答'), 'FACT', ['0.77ms']), (('ルーター', '16000文書の再現率'), 'FACT', ['110/110']),
      (('平らな経路', '300文書以上の正答'), 'FACT', ['0/40']), (('コーパス', 'KEPT件数'), 'FACT', ['54251']), (('コーパス', '保留件数'), 'FACT', ['3']),
      (('split不明のコーパス', '取込'), 'FACT', ['HOLD']), (('原本への適用',), 'TASK', ['保留']), (('適用検証',), 'TASK', ['完了']),
      (('zshの引数展開',), 'LESSON', ['明示引数']), (('f文字列',), 'LESSON', ['式内の逆スラッシュ禁止']), (('証拠文書の未読方針',), 'QUESTION', ['allとmentionの人間の決定'])]
unknown = ['Proの空き容量は？', 'ルーターの色は？', '誰が決勝戦に勝った？']
hit = 0; ms = []
for args, kind, gold in qs:
    q = args
    t = time.perf_counter(); a = m.ask_about(*args, kind=kind); ms.append((time.perf_counter()-t)*1000)
    good = a['verdict'] == 'ANSWER' and a['values'] == gold; hit += good
    if not good: print('  MISS', q, a['verdict'], a['values'], 'gold', gold, a.get('reason'))
print(f'typed memory: {hit}/{len(qs)} answered correctly with the record id cited; median {sorted(ms)[len(ms)//2]:.1f} ms per ask (each ask rebuilds the view)')
print('unknown questions abstain:', [m.ask(q)['verdict'] for q in unknown])
print('normalized slots recorded:', sum(1 for r in m.records.values() if r.get('normalized')), 'of', len(m.records))
print('witness states:', {k: sum(1 for v in m.verify().values() if v == k) for k in set(m.verify().values())})
if LIVE:
    for kind, state in (('TASK', 'ブロック中'), ('TASK', 'もうすぐ終わる')):
        try:
            r = m.write('TASK', 'claude', subject='結合試験' + str(len(m.records)), state=state); print('LIVE resolved', state, '->', r['slots']['state'])
        except WriteRejected as e: print('LIVE not adopted', state, '|', e.reason)
    for k, a in m.aliases.items(): print('  alias', k, a['status'], a['choice'], [x['picked'] for x in a['asks']])
