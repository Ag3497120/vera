"""Predicate-elided role questions for Round5-A (e.g. a question made only of wh-words with case particles, or only of role nouns).

The question names only event roles. It becomes one wildcard Bind whose roles are
the asked roles; nothing about the predicate is guessed. A document with several
events that carry all asked roles stays ambiguous and abstains.
"""
from __future__ import annotations

import re

from .semantic_ir import Pattern

_WH = r'(?:誰|だれ|何|なに|どこ)'
_CASE_ROLE = {'が': 'agent', 'は': 'agent', 'を': 'patient', 'に': 'recipient', 'へ': 'recipient',
              'で': 'location', 'から': 'origin'}
_ROLE_NOUN = {'物': 'patient', '起点': 'origin', '終点': 'recipient', '受取人': 'recipient',
              '渡した人': 'agent', '送り主': 'agent'}


def read_role_list_question(raw, b, full):
    """Return a plan for a role-only question, or None when raw is another shape."""
    text = raw.strip()
    m = re.fullmatch(r'((?:' + _WH + r'(?:が|は|を|に|へ|で|から))+)(?:ですか)?[？?。]*', text)
    roles = []
    if m:
        for part in re.finditer('(' + _WH + r')(が|は|を|に|へ|で|から)', m[1]):
            roles.append((part[0], _CASE_ROLE[part[2]]))
    else:
        m = re.fullmatch(r'((?:' + '|'.join(map(re.escape, _ROLE_NOUN)) + r')(?:、(?:' + '|'.join(map(re.escape, _ROLE_NOUN))
                         + r'))*)は[？?。]*', text)
        if not m: return None
        roles = [(noun, _ROLE_NOUN[noun]) for noun in m[1].split('、')]
    names = [role for _, role in roles]
    if len(names) < 2 or len(set(names)) != len(names): return None
    variables = [(label, role, b.variable()) for label, role in roles]
    b.bind(Pattern('*', tuple((role, v) for _, role, v in variables)), full)
    for label, role, v in variables:
        b.outputs.append((label, v, full, ''))
    return b.project(b.roots[0])
