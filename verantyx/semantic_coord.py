"""Plain coordination of predicates inside one sentence (te-form / renyō chains), Round5-A.

Licensed only for ``clause1(て|連用)、clause2 …`` chains: every non-final predicate is a 連用 form
followed by nothing but an optional て/で and an optional 、. Adversative が, causal ので/から,
conditional ば/たら/と and everything else are NOT coordination here and keep the old refusal.

Topic scope: an agent that is marked by the topic は in the first clause is shared by a later clause
only if that clause has no は/が phrase of its own. The sidecar reports exactly this as an
unpermitted INTERCLAUSE_BORROW; this module is the typed rule that licenses it.

Tokens are ``(surface, pos1, pos2, cform, start, end)`` of the sentence itself.
"""
from __future__ import annotations

from unicodedata import category


def tag(words, positions):
    return [(w.surface, w.feature.pos1, w.feature.pos2, str(w.feature.cForm), at, at + len(w.surface))
            for w, at in zip(words, positions)]


def _tail_end(tagged, p):
    """Index after the predicate token and its optional て/で and 、; None when something else follows."""
    k = p + 1
    if k < len(tagged) and tagged[k][0] in ('て', 'で') and tagged[k][1] == '助詞': k += 1
    if k < len(tagged) and tagged[k][0] == '、' and tagged[k][1] == '補助記号': k += 1
    return k


def coordination_ok(tagged, pred_idx):
    """True for a chain of >= 2 predicates joined only by te/renyō coordination."""
    if len(pred_idx) < 2: return False
    if any(type(p) is not int or p < 0 or p >= len(tagged) for p in pred_idx): return False
    shared_topic = topic_phrase(tagged, pred_idx) is not None
    for a, b in zip(pred_idx, pred_idx[1:]):
        if a >= b: return False
        if not tagged[a][3].startswith('連用'): return False
        k = _tail_end(tagged, a)
        if k > b: return False
        # A later clause needs a nominal phrase unless the first clause supplies a topic.
        body = tagged[k:b]
        if any((t[1] == '接続詞') or (t[1] == '助詞' and t[2] == '接続助詞' and t[0] not in ('て', 'で')) for t in body):
            return False
        # the separator must really be te / comma: a bare renyō needs the 、
        gap = ''.join(t[0] for t in tagged[a + 1:k])
        if gap not in ('、', 'て', 'て、', 'で', 'で、'): return False
        has_nominal = any(t[1] in ('名詞', '接尾辞', '代名詞') for t in body)
        if not shared_topic and not has_nominal and gap != '、': return False
    return True


def chunk(tagged, pred_idx, i):
    """(first token index, predicate token index) of clause i's own tokens."""
    first = 0 if i == 0 else _tail_end(tagged, pred_idx[i - 1])
    return first, pred_idx[i]


def own_subject_phrase(tagged, first, last):
    """True when the chunk has its own は/が marked phrase."""
    return any(t[1] == '助詞' and t[0] in ('は', 'が') and t[2] in ('係助詞', '格助詞') for t in tagged[first:last])


def topic_phrase(tagged, pred_idx):
    """(start, end) character span of the first clause's は-marked noun phrase, or None."""
    first, last = chunk(tagged, pred_idx, 0)
    for k in range(first, last):
        t = tagged[k]
        if t[1] == '助詞' and t[0] == 'は' and t[2] == '係助詞':
            j = k
            while j > first and tagged[j - 1][1] in ('名詞', '接尾辞', '代名詞'): j -= 1
            return (tagged[j][4], tagged[k - 1][5]) if j < k else None
    return None


_RIGHT_OK = ('助詞', '助動詞', '動詞', '接続詞', '形容詞')


def _punctuation(token):
    """Real punctuation only: format-only marks and letter-like symbols are not boundaries."""
    surface = token[0]
    return (token[1] == '補助記号' and bool(surface)
            and all(category(ch)[0] in ('P', 'S') for ch in surface))


def phrase_bounded(tagged, start, end):
    """A role phrase must start after a particle/punctuation (or at the chunk start) and end before a particle,
    punctuation or the predicate. A tagger that cuts one word (クククル -> クク + クル, ノシカル -> ノシ + カル)
    leaves a stray neighbour, and the phrase would then answer only a fragment of the written name."""
    if start >= end: return False
    first = next((i for i, t in enumerate(tagged) if t[4] == start), None)
    last = next((i for i, t in enumerate(tagged) if t[5] == end), None)
    if first is None or last is None or first > last: return False
    if any(tagged[i][5] != tagged[i + 1][4] for i in range(first, last)): return False
    if first and (tagged[first - 1][5] != start
                  or not (tagged[first - 1][1] == '助詞' or _punctuation(tagged[first - 1]))): return False
    if last + 1 < len(tagged):
        right = tagged[last + 1]
        if right[4] != end or not (right[1] in _RIGHT_OK or _punctuation(right)): return False
    return True
