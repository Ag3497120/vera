"""Writes the hand-designed ledgers and the small corpus root of tests/observe/data (stdlib only: no verantyx import, no reader, no observer).

The ledger events are written by hand here, in the shape of docs/OBSERVATION.md P9 (seq, id, ts, kind, payload). A cell key is built with the
rule of P1 (a canonical JSON of the content), not by calling the code under test. `ts` is a fixed string (it is stored and never read).
The viewpoint inside a hand-written observation event is a short stand-in; `output_sha256` is 64 zeros: these two ledger lines were not made
by the observer, so they cannot be replayed (the replay tests use ledgers the entry wrote).
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
TS = '2026-10-03T00:00:00+00:00'


def key(pred, agent, patient, recipient, polarity='+', tense='past'):
    content = {'center': {'predicate': pred, 'polarity': polarity, 'tense': tense, 'modality': None, 'voice': 'active'},
               'arms': [{'role': 'agent', 'kind': 'FILLER', 'surfaces': [agent]},
                        {'role': 'patient', 'kind': 'FILLER', 'surfaces': [patient]},
                        {'role': 'recipient', 'kind': 'FILLER', 'surfaces': [recipient]}]}
    return 'cell:' + json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


A = key('貸す', '教授', '辞書', '学生')
B = key('貸す', '事務員', '辞書', '学生')
C = key('貸す', '犬', '辞書', '学生')
D = key('渡す', '車掌', '切符', '乗客')
FAKE_VP = {'anchor': {'type': 'AnchorText', 'kind': 'question', 'text': 'hand-written', 'lang': None, 'cross_index': None, 'reading_source': 'semantic_read'},
           'direction': [{'move': 'FACE_SWAP', 'role': 'agent'}], 'range': 1, 'state': {'kind': 'FLAT'}}


def utt(text):
    return ('utterance', {'text': text, 'anchor': 'question'})


def dec(k):
    return ('decision', {'decided_cell': k})


def obs(outcome, state_seq, observed=None, tie=None):
    p = {'viewpoint': FAKE_VP, 'outcome': outcome, 'state_seq': state_seq, 'output_sha256': '0' * 64}
    if observed is not None: p['observed_cell'] = observed
    if tie is not None: p['tie_cells'] = tie
    return ('observation', p)


LEDGERS = {
    'L01': [],                                                                                    # empty
    'L02': [utt('図書館の話をしよう'), obs('TIE', 0, tie=sorted([A, B, C]))],                        # one turn that ended in a TIE (no observed_cell)
    'L03': [dec(A), dec(A), dec(B)],                                                              # decisions: A twice, B once (an alternative exists)
    'L04': [utt('駅員は乗客に切符を渡した。'), obs('FOCUS', 0, observed=D)],                          # the same question asked before; one candidate only
    'L05': [utt('教授にも聞いてみて')],                                                            # another wording: contains a changed filler verbatim (stage ii-a)
    'L06': [utt('猫を飼いたいな')],                                                                # another wording: contains a NEIGHBOUR of a changed filler (stage ii-b)
    'L07': [dec(C)],                                                                              # a frame decision
    'L08': [dec(B), utt('別の話'), obs('FOCUS', 1, observed=B)],                                    # a decision and a past focus on the same cell (recency before decision)
    'L09': [dec(A), obs('FOCUS', 1, observed=A)],                                                 # L09 and L10 differ in ONE line: the observed cell of line 2
    'L10': [dec(A), obs('FOCUS', 1, observed=B)],
}


def write_ledgers():
    for name, events in LEDGERS.items():
        lines = []
        for i, (kind, payload) in enumerate(events, 1):
            lines.append(json.dumps({'seq': i, 'id': 'ev:%d' % i, 'ts': TS, 'kind': kind, 'payload': payload}, ensure_ascii=False, separators=(',', ':')))
        (DATA / 'ledgers' / (name + '.jsonl')).write_text(''.join(l + '\n' for l in lines), encoding='utf-8')


SRC = 'llm_authored:codex:pro-b00001'


def write_corpus():
    rows = [
        '事務員は学生に辞書を貸した。',            # a sentence that holds the cross B (attests it, by cross)
        '国語辞書は学生に人気がある。',            # contains 辞書 and 学生 but is another cross
        '辞書を引くのは大切だ。',
        '留学生は学生寮に住んでいる。',            # contains 学生 inside other words
        '叔母は縁側で団子を食べた。',              # contains 縁側 and 団子, another cross
        '団子の作り方を教えてください。',
        '祖父は畑で野菜を育てた。',
    ] + ['犬の話その%d。' % i for i in range(1, 206)]    # 205 rows that contain 犬: a search for 犬 fills the window of 200
    root = DATA / 'corpus_root' / 'out'
    root.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({'text': t, 'source': SRC, 'scene': 'テスト', 'sha': 's%03d' % i}, ensure_ascii=False) for i, t in enumerate(rows)]
    (root / 'sentences.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    write_ledgers()
    write_corpus()
    print('ledgers', len(LEDGERS), 'corpus rows written')
