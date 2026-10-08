"""Run the frozen corpus through the same entry called by `vera observe`."""
import json
import os
from collections import Counter
from pathlib import Path

from verantyx import observe as O

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'
RESULTS = ROOT / 'results'


def main():
    RESULTS.mkdir(exist_ok=True)
    mode = 'configured' if os.environ.get('VERA_PLACEMENT') else 'absent'
    questions = [json.loads(line) for line in (DATA / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if line]
    statuses = Counter()
    wrong = []
    out_path = RESULTS / f'{mode}.jsonl'
    with out_path.open('w', encoding='utf-8') as out_file:
        for index, q in enumerate(questions, 1):
            doc = DATA / 'docs' / (q['doc'] + '.jsonl')
            result = O.run_entry(anchor_text=q['text'], anchor_kind='question', lang=q['lang'],
                                 structure_path=str(doc), no_index=True)
            out = json.loads(result.stdout) if result.stdout else {'error': result.error}
            answer = out.get('answer', {})
            status = answer.get('status', 'NO_ANSWER')
            statuses[status] += 1
            row = {'id': q['id'], 'doc': q['doc'], 'text': q['text'], 'attack_axis': q['attack_axis'],
                   'exit_code': result.exit_code, 'status': status,
                   'fillers': [{'surface': f['surface'], 'evidence': [e['reading'] for e in f.get('evidence', [])],
                                'hole_type_check': f.get('hole_type_check')}
                               for f in answer.get('fillers', [])],
                   'excluded': answer.get('excluded', []), 'reasons': answer.get('reasons', []),
                   'question': answer.get('question'), 'error': result.error}
            out_file.write(json.dumps(row, ensure_ascii=False) + '\n')
            out_file.flush()
            truth = q.get('truth')
            if truth and status in ('FILLED', 'TIE'):
                got = {f['surface'] for f in row['fillers']}
                want = set(truth.get('fillers', []))
                evid = {rid for f in row['fillers'] for rid in f['evidence']}
                want_evid = set(truth.get('evidence', []))
                if got != want or evid != want_evid or truth['kind'] not in ('ONE', 'SPLIT'):
                    wrong.append({'id': q['id'], 'text': q['text'], 'truth': truth, 'actual': row})
            elif truth and truth['kind'] == 'NONE' and status not in ('NO_ATTESTED_CELL', 'QUESTION_NOT_READ', 'POLAR_QUESTION'):
                wrong.append({'id': q['id'], 'text': q['text'], 'truth': truth, 'actual': row})
            if index % 10 == 0:
                print(f'completed={index}/{len(questions)}', flush=True)
    summary = {'placement_mode': mode, 'questions': len(questions), 'status_counts': dict(sorted(statuses.items())),
               'explicit_truth_wrong': wrong, 'output': str(out_path.relative_to(ROOT))}
    summary_path = RESULTS / f'{mode}.summary.json'
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'explicit_truth_wrong'} | {'explicit_truth_wrong_count': len(wrong)}, ensure_ascii=False))
    for item in wrong:
        print(json.dumps(item, ensure_ascii=False))


if __name__ == '__main__':
    main()
