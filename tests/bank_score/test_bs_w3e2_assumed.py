"""W3-e2 (K335): the classes of the assumed reading (a home-made sample; NOT an answer key of any bank)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.bank_score.v2 import assumed as A

FIX = ROOT / 'tests' / 'bank_score' / 'fixtures' / 'W3E2_assumed' / 'items.jsonl'


def test_the_three_classes_and_none_for_a_strict_reading(tmp_path):
    summ = A.run([str(FIX)], None, str(tmp_path))
    rows = [json.loads(l) for l in (tmp_path / 'rows.jsonl').read_text(encoding='utf-8').splitlines()]
    cls = {r['id']: r['assumed_class'] for r in rows}
    assert cls['W3E2-A01'] is None
    assert cls['W3E2-A02'] == cls['W3E2-A03'] == cls['W3E2-A04'] == 'assumed_correct'
    assert cls['W3E2-A05'] == cls['W3E2-A06'] == 'assumed_wrong'
    assert cls['W3E2-A07'] == cls['W3E2-A08'] == cls['W3E2-A09'] == 'assumed_abstain'
    assert summ['assumed_correct'] == 3 and summ['assumed_wrong'] == 2 and summ['assumed_abstain'] == 3 and summ['strict_read'] == 1
    assert summ['assumed_wrong_rate'] == 0.4 and summ['rate_denominator'] == 5 and summ['over_a_tenth'] is True
    assert json.loads((tmp_path / 'summary.json').read_text(encoding='utf-8')) == summ


def test_the_rate_has_no_denominator_without_a_reading():
    assert A.summarize([{'assumed_class': 'assumed_abstain'}])['assumed_wrong_rate'] is None
    assert A.summarize([{'assumed_class': None}])['strict_read'] == 1


def test_the_existing_modules_are_untouched():
    import subprocess
    out = subprocess.run(['git', '-C', str(ROOT), 'diff', 'bfb17b8', '--', 'tools/bank_score/v2/score.py', 'tools/bank_score/v2/b1.py', 'tools/bank_score/classify.py',
                          'tools/bank_score/score.py', 'tools/bank_score/adapters.py'], capture_output=True, text=True, check=True).stdout
    assert out == ''
