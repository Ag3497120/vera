"""W1-a5 (docs/READING_SOUNDNESS.md section 10G): what a test that compares the entry with the base commit byte for byte may still say about a sentence W1-a5 changed.
`touched(text)`: the decision of W1-a5 for the sentence is not `not_triggered`. `documented(base_out, out)`: `out` differs from `base_out` in one of the registered ways only (K210):
the aspect rule corrected the polarity and the tense of a read output; an aspect gate refused a read output (one reason, ASPECT_*); one reason of W1-a5 stands behind the reasons of the
base (the kind is the base's); or the base abstained and the output is one clause that carries `quantifiers` or `flags`. Nothing is weakened: a sentence W1-a5 does not touch is compared
byte for byte as before; a touched sentence must be one of the four kinds."""
from verantyx import semantic_reader as R


def touched(text, placement=None):
    # Integration (auditor, 2026-10-04): the sample lists of earlier tickets hold English sentences; W1-a5 is Japanese-only, so a text whose
    # script is not Japanese is never touched (the explain of the Japanese path raises LANG_MISMATCH on it).
    try:
        return R.w1a5_explain_ja(text, placement)['path'] != 'not_triggered'
    except Exception as e:
        if 'LANG_MISMATCH' in str(e): return False
        raise


def documented(base_out, out):
    if base_out['readable'] and out['readable']:
        a, b = base_out['clauses'], out['clauses']
        return len(a) == len(b) == 1 and {k: v for k, v in a[0].items() if k not in ('polarity', 'tense')} == {k: v for k, v in b[0].items() if k not in ('polarity', 'tense')}
    if base_out['readable']:
        return len(out['abstain']['reasons']) == 1 and out['abstain']['reasons'][0].startswith('ASPECT_')
    if not out['readable']:
        return out['abstain']['kind'] == base_out['abstain']['kind'] and out['abstain']['reasons'][:-1] == base_out['abstain']['reasons']
    return len(out['clauses']) == 1 and ('quantifiers' in out['clauses'][0] or 'flags' in out['clauses'][0])
