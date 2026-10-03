"""Write the frozen, hand-authored W3-c2 attack documents and questions."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'

DOCS = {
    'JA01': [
        '校長は生徒に地図を渡した。', '先生は生徒に地図を渡した。', '生徒は校長に地図を渡した。',
        '校長は生徒に地図を渡さなかった。', '校長は生徒に薬を渡した。',
        '校長は駅で生徒に地図を渡した。', '先生は地図を渡した。',
    ],
    'JA02': [
        '花子は本を読んだ。', '先生は本を読んだ。', '花子は新聞を読んだ。',
        '花子は本を読まなかった。', '花子は昨日本を読んだ。',
        '花子は毎日本を読んだ。', '生徒は本を読んでいる。',
    ],
    'JA03': [
        '母は料理を作った。', '父は料理を作った。', '母は弁当を作った。',
        '母は料理を作らなかった。', '母は台所で料理を作った。',
        '母は三つの料理を作った。', '母は料理を作り始めた。',
    ],
    'JA04': [
        '医師は患者に薬を送った。', '看護師は患者に薬を送った。', '患者は医師に薬を送った。',
        '医師は患者に薬を送らなかった。', '医師は患者に手紙を送った。',
        '医師は病院で患者に薬を送った。', '看護師は患者に薬を送る。',
    ],
    'JA05': [
        '生徒は先生に褒められた。', '太郎は次郎に叱られた。', '母は子に本を読ませた。',
        '先生は生徒に本を読ませた。', '母は子に薬を飲ませた。',
        '子は本を読んだ。', '先生は生徒に本を読んだ。',
    ],
    'JA06': [
        '校長は地図を渡した。', '校長が地図を渡した。', '地図は校長が渡した。',
        '先生は本を読んだ。', '先生が本を読んだ。', '生徒は先生に本を渡した。',
        '校長は生徒に地図を渡した。',
    ],
    'JA07': [
        '花子は駅で友達に手紙を渡した。', '先生は教室で生徒に本を渡した。',
        '母は台所で父に弁当を渡した。', '生徒は駅で先生に地図を渡した。',
        '先生は公園で生徒に本を渡した。', '母は父に薬を渡さなかった。',
        '花子は友達に手紙を渡す。',
    ],
    'EN08': [
        'The girl wrote a letter.', 'The girl wrote a note.', 'The boy wrote a letter.',
        'The girl did not write a letter.', 'The girl sent a letter to a student.',
        'The girl writes a report.', 'A letter was sent to the girl by the boy.',
    ],
    'EN09': [
        'The nurse helped a patient.', 'The doctor helped a patient.', 'The nurse helped a student.',
        'The patient helped a nurse.', 'The nurse did not help a patient.',
        'The nurse treated a patient.', 'The nurse gave a book to a student.',
    ],
    'EN10': [
        'The girl read a book.', 'The girl read a novel.', 'The girl read a report.',
        'The boy read a book.', 'The girl sent a letter to the student.',
        'The girl was given a book.', 'The girl did not read a book.',
    ],
}

QUESTIONS = {
    'JA01': [
        ('誰が生徒に地図を渡した？', 'agent/tie'), ('誰が校長に地図を渡した？', 'agent/role-swap'),
        ('校長は生徒に何を渡した？', 'patient/tie'), ('誰が生徒に薬を渡した？', 'patient-filter'),
        ('誰が生徒に地図を渡さなかった？', 'polarity'), ('誰が駅で生徒に地図を渡した？', 'place'),
        ('校長は駅で生徒に何を渡した？', 'place/patient'), ('校長は誰に地図を渡した？', 'recipient-hole'),
        ('昨日誰が生徒に地図を渡した？', 'time-adverb'), ('何人が生徒に地図を渡した？', 'quantity'),
        ('誰が生徒に手紙を渡した？', 'no-match'), ('誰が何を生徒に渡した？', 'multiple-wh'),
    ],
    'JA02': [
        ('花子は何を読んだ？', 'patient/tie'), ('誰が本を読んだ？', 'agent'),
        ('誰が本を読まなかった？', 'polarity'), ('花子は何を読まなかった？', 'polarity/patient'),
        ('昨日花子は何を読んだ？', 'time-adverb'), ('毎日花子は何を読んだ？', 'frequency'),
        ('花子はどの本を読んだ？', 'which-n'), ('先生は何を読んだ？', 'patient'),
        ('花子は新聞を読んだ？', 'polar'), ('誰が新聞を読んだ？', 'agent/patient-swap'),
        ('花子は何を読んでいる？', 'aspect'), ('誰が本を読み始めた？', 'aspect/agent'),
    ],
    'JA03': [
        ('母は何を作った？', 'patient/tie'), ('誰が料理を作った？', 'agent/tie'),
        ('誰が弁当を作った？', 'agent'), ('母は何を作らなかった？', 'polarity'),
        ('母は台所で何を作った？', 'place'), ('昨日母は何を作った？', 'time-adverb'),
        ('母は三つの料理を作った？', 'quantity/polar'), ('母は何個作った？', 'quantity-wh'),
        ('母はどの料理を作った？', 'which-n'), ('父は何を作った？', 'patient'),
        ('母は何を作り始めた？', 'aspect'), ('誰が料理を作らなかった？', 'polarity/agent'),
    ],
    'JA04': [
        ('誰が患者に薬を送った？', 'agent/tie'), ('誰が医師に薬を送った？', 'role-swap'),
        ('医師は患者に何を送った？', 'patient/tie'), ('誰が患者に手紙を送った？', 'patient-filter'),
        ('誰が患者に薬を送らなかった？', 'polarity'), ('誰が病院で患者に薬を送った？', 'place'),
        ('医師はどこで患者に薬を送った？', 'place-hole'), ('医師は誰に薬を送った？', 'recipient-hole'),
        ('誰が昨日患者に薬を送った？', 'time-adverb'), ('看護師は患者に何を送る？', 'tense'),
        ('誰が患者に本を送った？', 'no-match'), ('誰が何を患者に送った？', 'multiple-wh'),
    ],
    'JA05': [
        ('誰が先生に褒められた？', 'passive'), ('誰が次郎に叱られた？', 'passive'),
        ('母は子に何を読ませた？', 'causative'), ('誰が生徒に本を読ませた？', 'causative'),
        ('誰が本を読んだ？', 'active-vs-causative'), ('誰が薬を飲まされた？', 'passive-causative'),
        ('母は何を子に読ませた？', 'role-swap'), ('誰が母に本を読ませた？', 'causative-agent'),
        ('先生は生徒に本を読んだ？', 'argument-structure'), ('誰が先生に褒めた？', 'voice-inversion'),
        ('どの生徒が先生に褒められた？', 'which-n/passive'), ('誰が先生に褒められなかった？', 'negative-passive'),
    ],
    'JA06': [
        ('誰が地図を渡した？', 'topic/agent'), ('校長は何を渡した？', 'topic/patient'),
        ('地図は誰が渡した？', 'topic-focus'), ('誰が本を読んだ？', 'topic/agent-read'),
        ('先生は何を読んだ？', 'topic/patient-read'), ('校長が地図を渡した？', 'case-particle'),
        ('誰が先生に本を渡した？', 'subject-object'), ('先生は誰に本を渡した？', 'recipient-hole'),
        ('誰は地図を渡した？', 'wa-topic'), ('何は校長が渡した？', 'wa-topic/object'),
        ('校長は生徒に地図を渡さなかった？', 'negative-polar'), ('誰が昨日地図を渡した？', 'time-adverb'),
    ],
    'JA07': [
        ('誰が駅で友達に手紙を渡した？', 'agent/place'), ('誰が教室で生徒に本を渡した？', 'agent/place'),
        ('母は台所で何を渡した？', 'place/patient'), ('誰が駅で先生に地図を渡した？', 'agent/place'),
        ('先生はどこで生徒に本を渡した？', 'place-hole'), ('母は父に何を渡さなかった？', 'negative/patient'),
        ('誰が友達に手紙を渡す？', 'tense'), ('誰が駅で友達に本を渡した？', 'no-match'),
        ('母は誰に薬を渡した？', 'no-match/recipient'), ('いつ花子は友達に手紙を渡した？', 'time-hole'),
        ('誰が何を友達に渡した？', 'multiple-wh'), ('花子は駅で何を渡した？', 'topic/place'),
    ],
    'EN08': [
        ('Who did the girl write?', 'stranded-preposition/object-hole'), ('What did the girl write?', 'patient/tie'),
        ('Who did the girl write to?', 'stranded-preposition/to'), ('Who did the girl send a letter to?', 'stranded-preposition/recipient'),
        ('Which letter did the girl write?', 'which-n'), ('Who writes a report?', 'does/subject'),
        ('Who did the boy write?', 'did/object-hole'), ('Does the girl write a report?', 'does/polar'),
        ('Was a letter written by the girl?', 'was/passive'), ('What did the boy write?', 'patient'),
        ('Who did the girl send?', 'did/recipient-vs-patient'), ('Who did the girl write a report for?', 'preposition/for'),
    ],
    'EN09': [
        ('Who did the nurse help?', 'did/person'), ('Who does the nurse help?', 'does/person'),
        ('Who was helped by the nurse?', 'was/passive'), ('Who did the patient help?', 'did/role-swap'),
        ('Did the nurse help a patient?', 'polar'), ('Who did the nurse not help?', 'negation'),
        ('What did the nurse treat?', 'type-mismatch'), ('Which patient did the nurse help?', 'which-n'),
        ('Who did the nurse give a book to?', 'preposition/recipient'), ('Who did the nurse help yesterday?', 'time-adverb'),
        ('Who helped a student?', 'subject-wh'), ('Who did the nurse help?', 'tie-repeat'),
    ],
    'EN10': [
        ('Which book did the girl read?', 'which-n'), ('What did the girl read?', 'patient/tie'),
        ('Which novel did the girl read?', 'which-n/restrictor'), ('Who did the girl send a letter to?', 'stranded-preposition'),
        ('Who did the girl send the letter?', 'did/object-vs-recipient'), ('Who was given a book?', 'was/passive'),
        ('Did the girl read a book?', 'polar'), ('Who did the boy read?', 'did/person-hole'),
        ('What did the boy read?', 'patient'), ('Who did the girl read to?', 'stranded-preposition/to'),
        ('Who did not read a book?', 'negation/subject'), ('What did the girl not read?', 'negation/patient'),
    ],
}

TRUTH = {
    # Hand-set reference classifications for unambiguous probes, derived from the sentences above.
    'EN08-01': {'kind': 'NONE', 'fillers': [], 'evidence': []},
    'EN08-04': {'kind': 'ONE', 'fillers': ['student'], 'evidence': ['EN08-S05']},
    'JA01-01': {'kind': 'SPLIT', 'fillers': ['校長', '先生'], 'evidence': ['JA01-S01', 'JA01-S02']},
    'JA01-05': {'kind': 'ONE', 'fillers': ['校長'], 'evidence': ['JA01-S04']},
}


def main():
    docs_dir = DATA / 'docs'
    docs_dir.mkdir(parents=True, exist_ok=True)
    for doc_id, sentences in DOCS.items():
        rows = [{'id': f'{doc_id}-S{i:02d}', 'text': text,
                 'lang': 'ja' if doc_id.startswith('JA') else 'en'}
                for i, text in enumerate(sentences, 1)]
        (docs_dir / f'{doc_id}.jsonl').write_text(
            ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    questions = []
    for doc_id, items in QUESTIONS.items():
        lang = 'ja' if doc_id.startswith('JA') else 'en'
        for i, (text, axis) in enumerate(items, 1):
            qid = f'{doc_id}-{i:02d}'
            q = {'id': qid, 'doc': doc_id, 'lang': lang, 'text': text, 'attack_axis': axis}
            if qid in TRUTH:
                q['truth'] = TRUTH[qid]
            questions.append(q)
    assert len(questions) >= 100
    (DATA / 'questions.jsonl').write_text(
        ''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in questions), encoding='utf-8')
    typed = {
        'lemmas': {
            'letter': {'state': 'DECIDED', 'origin': 'direct', 'types': ['ARTIFACT']},
            'note': {'state': 'DECIDED', 'origin': 'direct', 'types': ['ARTIFACT']},
            'girl': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']},
            'student': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']},
        },
        'neighbors': {},
    }
    (DATA / 'direct-types.json').write_text(json.dumps(typed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'documents={len(DOCS)} sentences={sum(map(len, DOCS.values()))} questions={len(questions)}')


if __name__ == '__main__':
    main()
