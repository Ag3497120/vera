"""Typed memory: write-time gates, witnesses, supersession, conflicts, closed-choice term resolution."""
import json
import hashlib

import pytest

from verantyx.memory_frame import Memory, Resolver, WriteRejected, check_witness, parse_choice

T = '2026-10-02T10:00:00'


def mem(tmp_path, asker=None):
    return Memory(str(tmp_path / 'mem.jsonl'), asker=asker, now=lambda: T)


W = {'kind': 'testimony', 'by': 'human'}


def test_typed_fact_is_askable_with_its_record_id(tmp_path):
    m = mem(tmp_path)
    r = m.write('FACT', 'claude', witness=W, subject='封印評価', attribute='採点者', value='独立Codex')
    a = m.ask('封印評価の採点者は？')
    assert (a['verdict'], a['values'], a['records']) == ('ANSWER', ['独立Codex'], [r['id']])


@pytest.mark.parametrize('slots', [
    dict(subject='封印評価', attribute='採点者'),                                  # missing slot
    dict(subject='封印評価', attribute='採点者', value=''),                        # empty
    dict(subject='封印評価', attribute='採点者', value='独立Codex。次に進む'),      # sentence-like value
    dict(subject='封印評価', attribute='採点者', value='独立Codexに渡さない'),        # a clause (verb phrase) is not an askable value
])
def test_malformed_records_are_rejected_with_a_reason(tmp_path, slots):
    with pytest.raises(WriteRejected):
        mem(tmp_path).write('FACT', 'claude', witness=W, **slots)


def test_prose_is_not_memory(tmp_path):
    with pytest.raises(WriteRejected):
        mem(tmp_path).write('FACT', 'claude', witness=W, subject='今日の作業', attribute='内容',
                            value='ルーターを調整してテストを回してから報告した')


def test_fact_and_invariant_need_a_witness_but_decision_does_not(tmp_path):
    m = mem(tmp_path)
    with pytest.raises(WriteRejected): m.write('FACT', 'claude', subject='封印評価', attribute='採点者', value='独立Codex')
    with pytest.raises(WriteRejected): m.write('INVARIANT', 'claude', subject='回答', rule='誤答ゼロ')
    m.write('DECISION', 'human', subject='実装担当', choice='gpt-6-luna最大')


def test_supersede_keeps_history_and_answers_with_the_new_value(tmp_path):
    m = mem(tmp_path)
    old = m.write('FACT', 'claude', witness=W, subject='封印評価', attribute='採点者', value='Claude')
    new = m.write('FACT', 'claude', witness=W, supersedes=old['id'], subject='封印評価', attribute='採点者', value='独立Codex')
    assert m.ask('封印評価の採点者は？')['values'] == ['独立Codex']
    assert old['id'] in m.records and old['id'] in m.superseded                    # nothing deleted
    assert Memory(str(tmp_path / 'mem.jsonl'), now=lambda: T).ask('封印評価の採点者は？')['values'] == ['独立Codex']   # reload


def test_two_active_records_that_disagree_are_a_typed_conflict_not_a_pick(tmp_path):
    m = mem(tmp_path)
    m.write('FACT', 'claude', witness=W, subject='封印評価', attribute='採点者', value='Claude')
    m.write('FACT', 'codex', witness=W, subject='封印評価', attribute='採点者', value='独立Codex')
    a = m.ask('封印評価の採点者は？')
    assert a['verdict'] != 'ANSWER'


def test_stale_witness_drops_a_record_from_answers(tmp_path):
    f = tmp_path / 'x.txt'; f.write_text('abc')
    w = {'kind': 'file_sha256', 'path': str(f), 'sha256': hashlib.sha256(b'abc').hexdigest()}
    m = mem(tmp_path)
    m.write('FACT', 'claude', witness=w, subject='設定ファイル', attribute='内容', value='abc')
    assert m.ask('設定ファイルの内容は？')['values'] == ['abc'] and list(m.verify().values()) == ['FRESH']
    f.write_text('changed')
    assert list(m.verify().values()) == ['STALE']
    assert m.ask('設定ファイルの内容は？')['verdict'] != 'ANSWER'                  # stale evidence is not served
    assert m.ask('設定ファイルの内容は？', require_fresh=False)['values'] == ['abc']  # but it is still there


def test_witness_kinds(tmp_path):
    f = tmp_path / 'y.txt'; f.write_text('needle here')
    assert check_witness({'kind': 'text_in_file', 'path': str(f), 'needle': 'needle'}) == 'FRESH'
    assert check_witness({'kind': 'text_in_file', 'path': str(f), 'needle': 'gone'}) == 'STALE'
    assert check_witness({'kind': 'git_commit', 'repo': str(tmp_path), 'commit': '0' * 40}) == 'STALE'
    assert check_witness(None) == 'UNVERIFIABLE' and check_witness(W) == 'TESTIMONY'


# ---- closed-choice resolution of out-of-frame words
class Scripted:
    def __init__(self, *replies): self.replies = list(replies); self.prompts = []
    def __call__(self, prompt): self.prompts.append(prompt); return self.replies.pop(0)


def choose(prompt_options, text):
    """Reply naming the option whose text equals `text` in the shown order."""
    shown = [l.split(': ', 1)[1] for l in prompt_options.split('候補:\n', 1)[1].split('\n答えは')[0].split('\n')]
    return json.dumps({'choice': shown.index(text)})


class Smart:
    """A model that maps ブロック中 -> 停止 regardless of the order shown."""
    def __init__(self, target): self.target, self.calls = target, 0
    def __call__(self, prompt): self.calls += 1; return choose(prompt, self.target)


def test_out_of_frame_state_is_adopted_only_when_two_independent_asks_agree(tmp_path):
    asker = Smart('停止'); m = mem(tmp_path, asker)
    r = m.write('TASK', 'claude', subject='適用検証', state='ブロック中')
    assert r['slots']['state'] == '停止' and asker.calls == 2
    again = m.write('TASK', 'claude', subject='結合試験', state='ブロック中')          # alias reused, no new asks
    assert again['slots']['state'] == '停止' and asker.calls == 2
    assert m.aliases[('TASK.state', 'ブロック中')]['support'] == 'testimony'            # stored as testimony, with the asks
    assert m.ask('適用検証の状態は？')['values'] == ['停止']


def test_disagreeing_asks_leave_the_word_unresolved(tmp_path):
    flip = Scripted(json.dumps({'choice': 0}), json.dumps({'choice': 0}))        # same INDEX but the order was shuffled: different words
    m = mem(tmp_path, flip)
    with pytest.raises(WriteRejected): m.write('TASK', 'claude', subject='適用検証', state='ブロック中')


@pytest.mark.parametrize('reply', ['停止です', '{"choice": 99}', '{"choice": "停止"}', '', '{"choice": -1}'])
def test_invalid_model_answers_never_become_aliases(tmp_path, reply):
    m = mem(tmp_path, Scripted(reply, reply))
    with pytest.raises(WriteRejected): m.write('TASK', 'claude', subject='適用検証', state='ブロック中')
    assert not [a for a in m.aliases.values() if a['status'] == 'ADOPT']


def test_none_of_them_is_a_valid_answer_and_adopts_nothing(tmp_path):
    m = mem(tmp_path, Scripted('{"choice": null}', '{"choice": null}'))
    with pytest.raises(WriteRejected): m.write('TASK', 'claude', subject='適用検証', state='ブロック中')


def test_the_model_cannot_add_a_canonical_term():
    r = Resolver(Scripted('{"choice": 0}', '{"choice": 0}')); res = r.resolve('ブロック中', ['完了', '停止'])
    assert res['choice'] in ('完了', '停止') or res['status'] != 'ADOPT'
    assert parse_choice('{"choice": 5}', 2) is False


def test_kind_aliases_and_unknown_kinds(tmp_path):
    m = mem(tmp_path)
    assert m.write('方針', 'human', subject='実装担当', choice='gpt-6-luna最大')['kind'] == 'DECISION'
    with pytest.raises(WriteRejected): m.write('ぜんぜん別の種類', 'human', subject='a', choice='b')   # no asker: refused, not guessed


def test_many_records_stay_answerable_through_the_leaf_router(tmp_path):
    m = mem(tmp_path)
    for i in range(40): m.write('FACT', 'claude', witness=W, subject=f'項目{i}', attribute='値', value=f'数{i}番')
    assert m.ask('項目17の値は？')['values'] == ['数17番']


def test_compound_nouns_are_normalized_and_the_original_is_kept(tmp_path):
    m = mem(tmp_path)
    r = m.write('FACT', 'claude', witness=W, subject='ルーター', attribute='未読の上限', value='1024')
    assert r['slots']['attribute'] == '未読上限' and r['normalized'] == {'attribute': '未読の上限'}
    assert m.ask_about('ルーター', '未読の上限')['values'] == ['1024']


def test_rejection_explains_how_to_fix_it(tmp_path):
    with pytest.raises(WriteRejected) as e:
        mem(tmp_path).write('LESSON', 'claude', situation='f文字列', fix='式に逆スラッシュを入れない')
    assert '名詞句' in e.value.hint
