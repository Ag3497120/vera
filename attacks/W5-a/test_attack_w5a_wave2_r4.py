"""Three preregistered K64 probes with new objects and sentence contexts."""
from __future__ import annotations

import subprocess
import types

from verantyx import semantic_read as current


CASES = (
    ('尼僧が月報を発行した。', '尼僧', '発行する', '月報'),
    ('複数の人物が会報を発行した。', '複数の人物', '発行する', '会報'),
    ('会社が試験機を公開した。', '会社', '公開する', '試験機'),
)


def _baseline_reader():
    source = subprocess.check_output(['git', 'show', '2732274^:verantyx/semantic_read.py'], text=True)
    module = types.ModuleType('verantyx._semantic_read_wave2_r4_baseline')
    module.__package__ = 'verantyx'
    exec(compile(source, 'git:2732274^/verantyx/semantic_read.py', 'exec'), module.__dict__)
    return module


def test_k64_preserves_positive_person_and_organization_evidence_on_new_sentences():
    old = _baseline_reader()
    hits = []
    baseline_misses = []
    current_misses = []
    for text, agent, predicate, patient in CASES:
        before = old.read(text)
        if not before['readable']:
            baseline_misses.append((text, before))
            continue
        clause = before['clauses'][0]
        if (clause['predicate'] != predicate or clause['roles'].get('agent') != agent
                or clause['roles'].get('patient') != patient):
            baseline_misses.append((text, clause))
            continue
        after = current.read(text)
        if not after['readable'] and after.get('abstain', {}).get('reasons') == ['AGENT_EVIDENCE_MISSING:' + agent]:
            hits.append((text, clause, after['abstain']))
        else:
            current_misses.append((text, after))
    assert not baseline_misses, {'gold_not_established_at_baseline': baseline_misses}
    assert not hits, {'K64_positive_evidence_over_abstentions': hits, 'current_misses': current_misses}

