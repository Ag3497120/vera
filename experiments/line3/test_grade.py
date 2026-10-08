import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from grade import grade, classify


def test_correct():
    assert grade(classify('ANSWER'), '遊眠', '遊眠は日本の漫画家', '遊眠', '漫画家')[0] == 'correct'


def test_wrong_answerable_and_unanswerable():
    assert grade(classify('ANSWER'), '遊眠', '遊眠は歌手', '遊眠', '漫画家')[0] == 'wrong'
    assert grade(classify('SEEDED'), 'X', '何か', 'X', '')[0] == 'wrong'  # unanswerable answered


def test_abstain():
    assert grade(classify('UNKNOWN_NO_EVIDENCE'), '', '', '遊眠', '漫画家')[0] == 'abstain'
    assert grade(classify(None), '', '', '遊眠', '')[0] == 'abstain'
