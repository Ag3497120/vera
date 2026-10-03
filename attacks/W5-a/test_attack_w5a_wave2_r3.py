"""K64 over-abstention regression probes, preregistered in PRE_REGISTRATION_R3.md."""
from __future__ import annotations

import subprocess
import types

from verantyx import semantic_read as current


CASES = (
    ('尼僧が古い箱を閉めた。', '尼僧', '閉める', '古い箱'),
    ('複数の人物が回答書を発行した。', '複数の人物', '発行する', '回答書'),
    ('尼僧が案内図を描いた。', '尼僧', '描く', '案内図'),
    ('会社が試作品を公開した。', '会社', '公開する', '試作品'),
    ('複数の人物が別々の名を名乗った。', '複数の人物', '名乗る', '別々の名'),
)


def _baseline_reader():
    source = subprocess.check_output(['git', 'show', '2732274^:verantyx/semantic_read.py'], text=True)
    module = types.ModuleType('verantyx._semantic_read_wave1_baseline')
    module.__package__ = 'verantyx'
    exec(compile(source, 'git:2732274^/verantyx/semantic_read.py', 'exec'), module.__dict__)
    return module


def test_k64_does_not_turn_clear_human_or_organization_agents_into_abstentions():
    old = _baseline_reader()
    regressions = []
    other = []
    for text, agent, predicate, patient in CASES:
        before = old.read(text)
        assert before['readable'] is True, ('baseline did not establish the frozen gold', text, before)
        c = before['clauses'][0]
        assert c['predicate'] == predicate and c['roles'].get('agent') == agent and c['roles'].get('patient') == patient, (text, c)
        after = current.read(text)
        if (not after['readable'] and after.get('abstain', {}).get('reasons') == ['AGENT_EVIDENCE_MISSING:' + agent]):
            regressions.append((text, c, after['abstain']))
        else:
            other.append((text, after))
    assert not regressions, {'K64_positive_semantic_evidence_over_abstentions': regressions, 'other_results': other}

