"""Red-team assertions for the W3-c2 question path. Expected to fail on a reproduced bad fill."""
import json
from pathlib import Path

from verantyx import observe as O

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data'


def _question(qid):
    return next(json.loads(line) for line in (DATA / 'questions.jsonl').read_text(encoding='utf-8').splitlines()
                if json.loads(line)['id'] == qid)


def _run(qid, placement_path=None):
    q = _question(qid)
    doc = DATA / 'docs' / (q['doc'] + '.jsonl')
    result = O.run_entry(anchor_text=q['text'], anchor_kind='question', lang=q['lang'],
                         structure_path=str(doc), no_index=True, placement_path=placement_path)
    assert result.stdout, result.error
    return json.loads(result.stdout)


def test_person_question_does_not_fill_with_artifacts_without_placement():
    out = _run('EN08-01')
    answer = out['answer']
    got = [(f['surface'], f['hole_type_check']) for f in answer['fillers']]
    assert answer['status'] not in ('FILLED', 'TIE') and not answer['fillers'], (
        'the documents say only that the girl wrote artifacts, not which person she wrote to; '
        f"expected abstention for frozen truth NONE, got status={answer['status']}, fillers={got!r}, "
        f"question={answer['question']!r}, reasons={answer['reasons']!r}"
    )


def test_direct_artifact_type_excludes_person_hole():
    out = _run('EN08-01', DATA / 'direct-types.json')
    answer = out['answer']
    assert answer['status'] == 'TYPE_EXCLUDED_ALL', (
        f"direct ARTIFACT evidence should exclude PERSON hole candidates; status={answer['status']}, "
        f"fillers={answer['fillers']!r}, excluded={answer['excluded']!r}"
    )
    assert {e['reason'] for e in answer['excluded']} == {'HOLE_TYPE_DISAGREE'}


def test_tied_agent_witnesses_remain_a_tie():
    answer = _run('JA01-01')['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'TIE' and got == {'校長', '先生'}, (
        f"expected both matching witnesses, got status={answer['status']}, fillers={got!r}"
    )


def test_negative_question_does_not_match_affirmative_crosses():
    answer = _run('JA01-05')['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'FILLED' and got == {'校長'}, (
        f"expected the sole negative witness JA01-S04, got status={answer['status']}, fillers={got!r}"
    )
