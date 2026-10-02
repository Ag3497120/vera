"""Exact trigger index for typed LESSON records.

Known situations are matched after the same noun-phrase normalization used by
``memory_frame``. An unmatched situation can be sent to its closed-choice
resolver; only an agreed choice from the existing trigger vocabulary is used.
Lesson text is never included in that choice prompt.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Optional

from .memory_frame import Asker, Resolver, normalize_np


def normalize_trigger(situation: str) -> str:
    """Normalize a situation noun phrase like a typed memory slot."""
    return normalize_np(situation) if isinstance(situation, str) else ''


class LessonIndex:
    """Index LESSON records by normalized situation, retaining their ids."""

    def __init__(self, records, asker: Optional[Asker] = None, superseded=()):
        if hasattr(records, 'records'):
            memory = records
            records = memory.records.values()
            inherited = set(getattr(memory, 'superseded', {}))
            if isinstance(superseded, dict):
                inherited.update(superseded)
            elif isinstance(superseded, str):
                inherited.add(superseded)
            else:
                inherited.update(superseded or ())
            superseded = inherited
        elif isinstance(records, dict):
            records = records.values()

        records = [r for r in records if isinstance(r, dict)]
        if isinstance(superseded, dict):
            dead = set(superseded)
        elif isinstance(superseded, str):
            dead = {superseded}
        else:
            dead = set(superseded or ())
        # A record's supersedes slot is also enough to identify the old record
        # when the index is built from a plain record collection.
        dead.update(r['supersedes'] for r in records if r.get('supersedes'))

        self.resolver = Resolver(asker) if asker is not None else None
        self._by_trigger = {}
        self._by_id = {}
        # Sorting before insertion makes a repeated id deterministic too.
        ordered = sorted(records,
                         key=lambda r: (str(r.get('id', '')), repr(sorted(r.items(), key=lambda p: p[0]))))
        for record in ordered:
            if record.get('kind') != 'LESSON':
                continue
            rid = record.get('id')
            slots = record.get('slots', {})
            situation = slots.get('situation') if isinstance(slots, dict) else None
            trigger = normalize_trigger(situation)
            if not rid or not trigger or rid in dead:
                continue
            # Duplicate ids are one record in typed memory. Keep the first
            # stable representation instead of returning it more than once.
            if rid in self._by_id:
                continue
            lesson = deepcopy(record)
            self._by_id[rid] = (trigger, lesson)
            self._by_trigger.setdefault(trigger, []).append(lesson)

        for lessons in self._by_trigger.values():
            lessons.sort(key=lambda r: str(r['id']))
        self.triggers = tuple(sorted(self._by_trigger))

    def lessons_for(self, situation: str) -> list[dict]:
        """Return lessons for an exact normalized trigger, or an agreed choice.

        If there is no exact trigger, the injected asker is offered only the
        trigger vocabulary. With no asker, a disagreement, a tie/none, or an
        invalid answer, the method abstains with an empty list.
        """
        trigger = normalize_trigger(situation)
        if not trigger:
            return []
        if trigger in self._by_trigger:
            return list(self._by_trigger[trigger])
        if self.resolver is None or not self.triggers:
            return []
        resolution = self.resolver.resolve(trigger, self.triggers, context='LESSON の状況 trigger')
        if resolution['status'] != 'ADOPT':
            return []
        return list(self._by_trigger.get(resolution['choice'], ()))


def lessons_for(records, situation: str, asker: Optional[Asker] = None, superseded=()) -> list[dict]:
    """Convenience lookup over typed LESSON records or a ``Memory`` instance."""
    return LessonIndex(records, asker=asker, superseded=superseded).lessons_for(situation)
