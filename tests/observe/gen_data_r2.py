"""Round 2 (docs change record 3): writes the two ledgers and the three viewpoints that exercise the rule "an utterance equal to the anchor sentence is not the
latest utterance of stage ii". Stdlib only: no verantyx import, no reader, no observer. Written BEFORE the observer ran under the new rule (FROZEN.json: inputs_r2).
"""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'
TS = '2026-10-03T00:00:00+00:00'
J01 = '司書は学生に辞書を貸した。'


def utt(text):
    return ('utterance', {'text': text, 'anchor': 'question'})


LEDGERS = {
    'L11': [utt('教授にも聞いてみて'), utt(J01)],     # the latest utterance IS the anchor sentence; the one before it is another wording that holds a changed filler
    'L12': [utt(J01)],                                # the only utterance is the anchor sentence
}


def main():
    for name, events in LEDGERS.items():
        lines = [json.dumps({'seq': i, 'id': 'ev:%d' % i, 'ts': TS, 'kind': k, 'payload': p}, ensure_ascii=False, separators=(',', ':')) + '\n' for i, (k, p) in enumerate(events, 1)]
        (DATA / 'ledgers' / (name + '.jsonl')).write_text(''.join(lines), encoding='utf-8')
    base = {'direction': 'FACE_SWAP:agent', 'range': None, 'structure': 'seeds_ja.jsonl', 'placement': 'placement.json', 'index': None, 'families': None, 'turns': 1}
    cases = [
        dict(case='LG11', anchor={'text': J01, 'kind': 'seed'}, ledger='L11', note='latest utterance equals the anchor sentence: the one before it counts', **base),
        dict(case='LG12', anchor={'record': 'J01'}, ledger='L11', note='anchor is a record: its sentence in the structure is the anchor sentence', **base),
        dict(case='LG13', anchor={'text': J01, 'kind': 'seed'}, ledger='L12', note='only utterance equals the anchor sentence: the same as an empty ledger on stage ii', **base),
    ]
    (DATA / 'viewpoints_r2.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False) + '\n' for c in cases), encoding='utf-8')


if __name__ == '__main__':
    main()
