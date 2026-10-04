"""Fake placements for the type-agreement tests (the real coarse placement is not wired in yet): a dict from a word to a PlaceResult.

`MappingLookup` records every argument it is called with, so a test can show that the only thing passed is the word of the filler.
"""
from verantyx.event_cross import PlaceResult


def direct(*types):
    """A placement that the word itself carries: one type -> DECIDED, several -> MULTIPLE (an unordered set, written alphabetically)."""
    ts = tuple(sorted(types))
    return PlaceResult(state='DECIDED' if len(ts) == 1 else 'MULTIPLE', origin='direct', estimate_basis=None, types=ts, provenance={'fake': True})


def estimated(basis, *types):
    ts = tuple(sorted(types))
    return PlaceResult(state='DECIDED' if len(ts) == 1 else 'MULTIPLE', origin='estimated', estimate_basis=basis, types=ts,
                       provenance={'fake': True, 'constructed': True})


def bare(state):
    """UNPLACED / UNKNOWN / NO_PLACEMENT: no type, no origin."""
    return PlaceResult(state=state, origin=None, estimate_basis=None, types=(), provenance={'fake': True})


class MappingLookup:
    id = 'fake-mapping/1'

    def __init__(self, mapping, default=None):
        self.mapping = dict(mapping)
        self.default = default if default is not None else bare('UNKNOWN')
        self.calls = []        # every (args, kwargs) the lookup was called with

    def lookup(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.mapping.get(args[0], self.default)


class RawLookup:
    """Returns exactly what it is given (a broken answer, for the contract tests)."""
    id = 'fake-raw/1'

    def __init__(self, value):
        self.value = value

    def lookup(self, lemma):
        return self.value
