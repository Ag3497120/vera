"""W10-f04 (docs/FUSION.md section 6, K280): `semantic_read.read_with_holes`, `observe.describe_holes`, `vera read [--holes]`.
Data-driven rows (tests/fusion/w10f04/holes.jsonl, frozen before the code) are read with the placement r8 (read only); the rest uses a small fake placement (no files)."""
import contextlib
import io
import json
import subprocess
from pathlib import Path

import pytest

from verantyx import cli, observe, semantic_read as S, semantic_reader as R
from verantyx.coarse_types import NOUN_TYPES

# Integration (auditor, 2026-10-04): r8 is a build artefact that only the Pro has; on a machine without it these tests are skipped as ENV_MISSING (the W5-e2/W3-b4 pattern), never failed.
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
DATA = Path(__file__).parent / 'fusion' / 'w10f04' / 'holes.jsonl'
BASE_COMMIT = '338809e'


def decided(t):
    return {'state': 'DECIDED', 'top': [t], 'origin': 'direct', 'estimate_basis': None, 'constructed': False, 'decided_by': ['seed']}


def multiple(*ts):
    return {'state': 'MULTIPLE', 'top': sorted(ts), 'origin': 'direct', 'estimate_basis': None, 'constructed': False, 'decided_by': ['seed']}


UNPLACED = {'state': 'UNPLACED', 'top': [], 'origin': None, 'estimate_basis': None, 'constructed': False}


class FakePlacement:
    id = 'fake-placement'

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def query(self, term):
        self.asked.append(term)
        return self.answers.get(term, UNPLACED)


def fake():
    return FakePlacement({'歩く': decided('P_MOVE'), '母': decided('PERSON'), '駅': decided('PLACE'), '図書館': multiple('GROUP_ORG', 'PLACE'), '客': multiple('GROUP_ORG', 'PERSON')})


def fake_two_holes():
    """r3: the fake world of the candidate tests. `ウサギが図書館へ歩いた。` has TWO holes: が:ウサギ (MULTIPLE [ANIMAL, PERSON]; every type of it reads `agent`, so a candidate decides the word only) and
    へ:図書館 (MULTIPLE [GROUP_ORG, PLACE]; GROUP_ORG is not read, so (a4) refuses a candidate there). One-hole sentences are never adopted (docs/FUSION.md section 6.6, J16)."""
    p = fake()
    p.answers = dict(p.answers, **{'ウサギ': multiple('ANIMAL', 'PERSON'), '犬': decided('ANIMAL'), '猫': decided('ANIMAL'), '兄': decided('PERSON'), '山': decided('PLACE')})
    return p


def test_noun_types_are_17():
    # Integration of W3-a6 (auditor, 2026-10-05): the ticket's "18" became true (RELATIVE_POSITION); the 17 are the frame types. Name kept.
    from verantyx.coarse_types import FRAME_NOUN_TYPES
    assert len(NOUN_TYPES) == 18 and len(FRAME_NOUN_TYPES) == 17 and 'RELATIVE_POSITION' not in FRAME_NOUN_TYPES


def test_a_hole_on_a_fake_placement():
    out = S.read_with_holes('母が図書館へ歩いた。', placement=fake())
    assert out['readable'] is False and out['abstain'] is not None            # the abstention is kept
    assert out['holes_status'] == 'HOLES_FOUND'
    (h,) = out['holes']
    assert (h['arm'], h['particle'], h['head'], h['expected_types'], h['role_candidates'], h['placement_state']) == ('goal', 'へ', '図書館', ['PLACE'], ['goal'], 'MULTIPLE')
    assert h['why'] == 'PLACEMENT_MULTIPLE:へ:図書館'
    assert out['partial']['roles'] == {'agent': '母', 'goal': {'hole': 0}}
    text = json.dumps(out['partial'], ensure_ascii=False)
    assert 'hole_probe' not in text and 'placement_direct:PLACE' not in text          # no type of the probe is in `partial`


def test_keys_are_appended_at_the_end_and_read_is_unchanged():
    p = fake()
    plain = S.read('母が図書館へ歩いた。', placement=p)
    out = S.read_with_holes('母が図書館へ歩いた。', placement=p)
    assert list(out)[:len(plain)] == list(plain) and list(out)[len(plain):] == ['holes_status', 'holes', 'partial']
    assert {k: out[k] for k in plain} == plain


def test_probe_does_not_change_the_default_read():
    p = fake()
    before = json.dumps(S.read('母が図書館へ歩いた。', placement=p), ensure_ascii=False)
    S.read_with_holes('母が図書館へ歩いた。', placement=p)
    assert json.dumps(S.read('母が図書館へ歩いた。', placement=p), ensure_ascii=False) == before
    if not Path(R8).exists(): pytest.skip('ENV_MISSING[coarse placement r8/run2]')
    b = json.dumps(S.read('母が荷物を港へ押した。', placement=R8), ensure_ascii=False)
    S.read_with_holes('母が荷物を港へ押した。', placement=R8)
    assert json.dumps(S.read('母が荷物を港へ押した。', placement=R8), ensure_ascii=False) == b


def test_statuses_without_a_hole():
    assert S.read_with_holes('母が駅へ歩いた。', placement=fake())['holes_status'] == 'READ'
    assert S.read_with_holes('母が図書館へ歩いた。', placement=None)['holes_status'] == 'NO_PLACEMENT'
    en = S.read_with_holes('The mother walked to the library.', placement=fake())
    assert en['holes_status'] == 'LANG_NOT_SUPPORTED' and en['holes'] == [] and en['partial'] is None
    with pytest.raises(S.ReadError):
        S.read_with_holes('', placement=fake())


def test_two_holes_and_the_limit():
    p = fake()
    out = S.read_with_holes('客が図書館へ歩いた。', placement=p)
    assert out['holes_status'] == 'HOLES_FOUND' and [h['head'] for h in out['holes']] == ['客', '図書館']
    assert [h['expected_types'] for h in out['holes']] == [['ANIMAL', 'GROUP_ORG', 'PERSON'], ['PLACE']]
    assert out['partial']['roles'] == {'agent': {'hole': 0}, 'goal': {'hole': 1}}
    assert S.read_with_holes('客が図書館へ歩いた。', placement=p, max_holes=1)['holes_status'] == 'HOLE_TOO_MANY'


def test_a_part_and_a_predicate_reason_are_not_holes():
    # the unread predicate: the abstention is not a filler's placement
    out = S.read_with_holes('母が図書館へ謎める。', placement=fake())
    assert out['holes'] == [] and out['holes_status'].startswith(('NOT_A_FILLER_CAUSE', 'HOLE_'))


def test_describe_holes_display():
    text = '母が図書館へ歩いた。'
    out = S.read_with_holes(text, placement=fake())
    d = observe.describe_holes(out, text)
    assert d['display'] == '母がＸへ歩いた。' and d['arms'][0]['expected_types'] == ['PLACE']
    assert observe.describe_holes(S.read_with_holes('母が駅へ歩いた。', placement=fake()), '母が駅へ歩いた。')['display'] is None
    two = S.read_with_holes('客が図書館へ歩いた。', placement=fake())
    assert observe.describe_holes(two, '客が図書館へ歩いた。')['display'] == 'Ｘ1がＸ2へ歩いた。'


def _rows():
    return [json.loads(l) for l in DATA.read_text(encoding='utf-8').splitlines()]


def test_frozen_rows_no_wrong_hole_and_expected_types_inside_the_table():
    if not Path(R8).exists(): pytest.skip('ENV_MISSING[coarse placement r8/run2]')       # the placement r8 is the reference of this ticket
    rows = _rows()
    assert sum(1 for r in rows if r['is_hole']) >= 30 and sum(1 for r in rows if not r['is_hole']) >= 30
    wrong, missed, outside, bad_status = [], [], [], []
    for r in rows:
        out = S.read_with_holes(r['text'], r.get('lang'), placement=R8 if r['placement'] == 'r8' else None)
        got = bool(out['holes'])
        if got and not r['is_hole']: wrong.append(r['id'])
        if r['is_hole'] and not got: missed.append(r['id'])
        if not out['holes_status'].startswith(r['expect_status']): bad_status.append((r['id'], out['holes_status']))
        exp = r.get('holes') or [{'particle': r.get('particle'), 'head': r.get('head'), 'table_types': r.get('table_types')}]
        for h, e in zip(out['holes'], exp):
            if not h['expected_types'] or not set(h['expected_types']) <= set(e['table_types']): outside.append(r['id'])
    assert (wrong, missed, outside, bad_status) == ([], [], [], [])


def _run(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(argv)
    return code, buf.getvalue()


SENTENCES = ['母が部屋で手紙を読んだ。', '母が図書館へ歩いた。', '兄が山田に催促した。', '客が庭へ走った。', '母が荷物を港へ押した。', '兄が窓口で名乗った。', '弟が役所へ走った。', '妹が本部へ歩いた。',
             '夫婦がホテルで名乗った。', '姉が神社で日程を断った。', '母がホテルで勝利を願った。', '客が校庭で遊んだ。', '実は、母が部屋で手紙を読んだ。', '兄が祖父の家へ走った。', '先生が学校で本を読んだ。',
             '兄が公園で犬を見た。', '母が荷物を後へ押した。', '家族が図書館へ走った。', '妹が東京に旅行した。', '弟が明日、本を読んだ。', 'abc def。', 'The mother walked to the library.']


@pytest.mark.parametrize('placement', [True, False])
def test_vera_read_without_holes_is_the_module_byte_for_byte(placement):
    class A:
        holes = False
        max_holes = 2
        lang = None
    for t in SENTENCES:
        a = A(); a.text = t; a.placement = R8 if placement else None
        argv = ['--text=' + t] + (['--placement=' + R8] if placement else [])
        code1, out1 = _run(S.main, argv)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code2 = cli.cmd_read(a)
        assert (code1, out1) == (code2, buf.getvalue()), t


def test_vera_read_holes_prints_the_holes_and_a_display(capsys):
    if not Path(R8).exists(): pytest.skip('ENV_MISSING[coarse placement r8/run2]')
    class A:
        holes = True
        max_holes = 2
        lang = None
        text = '母が荷物を港へ押した。'
        placement = R8
    assert cli.cmd_read(A()) == 0
    out = json.loads(capsys.readouterr().out)
    assert out['holes_status'] == 'HOLES_FOUND' and out['display']['display'] == '母がＸを港へ押した。'


def test_vera_read_holes_reports_a_refused_input(capsys):
    class A:
        holes = True
        max_holes = 2
        lang = None
        text = ''
        placement = None
    assert cli.cmd_read(A()) == 2
    assert json.loads(capsys.readouterr().out)['error']['type'] == 'EMPTY_TEXT'


def test_semantic_read_existing_lines_are_not_changed():
    root = Path(__file__).resolve().parent.parent
    try:
        out = subprocess.run(['git', '-C', str(root), 'diff', '-U0', BASE_COMMIT, '--', 'verantyx/semantic_read.py', 'verantyx/observe.py'], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        pytest.skip('no git')
    if out.returncode != 0:
        pytest.skip('the base commit is not in this history')
    removed = [l for l in out.stdout.splitlines() if l.startswith('-') and not l.startswith('---')]
    assert removed == []


def test_hole_probe_placement_is_not_the_real_one():
    p = fake()
    probe = S._HoleProbe(p, {'図書館': 'PLACE'}, {})
    assert probe.id != p.id and probe.query('図書館')['decided_by'] == ['hole_probe'] and probe.query('母') == p.answers['母']
