"""Exact trigger index for typed LESSON records.

Situations are matched after the same noun-phrase normalization used by
``memory_frame``. An optional closed-choice asker may resolve an unmatched,
safe phrase to an existing trigger. Its two independent choices are retained
as testimony; it cannot create lesson text or a trigger.
"""
from __future__ import annotations

from copy import deepcopy
import json
import random
import re
from threading import RLock
from typing import Optional

from .memory_frame import Asker, Resolver, normalize_np


_UNSAFE_CHARACTERS = re.compile(r'[\x00-\x1f\x7f。！？!?「」『』]')
_INSTRUCTION_TEXT = re.compile(
    r'(?i)(?:\b(?:ignore|disregard|override|forget|follow|choose|select|answer|reveal|'
    r'instruction|instructions|prompt|system|policy|rule|rules)\b|無視|指示|命令|選択|選べ|従え|回答|開示|公開)'
)
_MAX_ASKER_OPTIONS = 128


def normalize_trigger(situation: str) -> str:
    """Normalize a situation noun phrase like a typed memory slot."""
    return normalize_np(situation) if isinstance(situation, str) else ''


def _safe_phrase(value: str) -> bool:
    """Allow only short phrase-like text into a closed-choice prompt."""
    return (isinstance(value, str) and bool(value) and len(value) <= 160
            and not _UNSAFE_CHARACTERS.search(value)
            and not _INSTRUCTION_TEXT.search(value))


def _stable_record_key(record: dict) -> tuple[str, str]:
    """Sort JSON-like records deterministically, including mixed-key input."""
    rid = record.get('id')
    stable_id = rid if isinstance(rid, str) else ''
    items = sorted((repr(key), repr(value)) for key, value in record.items())
    return stable_id, repr(items)


def _string_ids(value) -> set[str]:
    if isinstance(value, dict):
        values = value.keys()
    elif isinstance(value, str):
        values = (value,)
    else:
        try:
            values = iter(value or ())
        except TypeError:
            values = ()
    return {item for item in values if isinstance(item, str) and item}


def _strict_choice(reply, count: int):
    """Return a closed-list index/null, or False for anything else."""
    if not isinstance(reply, str):
        return False

    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON key')
            value[key] = item
        return value

    try:
        value = json.loads(reply, object_pairs_hook=unique_object)
    except (TypeError, ValueError):
        return False
    if type(value) is not dict or set(value) != {'choice'}:
        return False
    choice = value['choice']
    if choice is None:
        return None
    if type(choice) is int and 0 <= choice < count:
        return choice
    return False


def _seed_with_reordered_options(count: int) -> int:
    """Choose a Resolver seed whose second ask actually changes option order."""
    canonical = list(range(count))
    for seed in range(1024):
        order = list(canonical)
        random.Random(seed).shuffle(order)
        if order != canonical:
            return seed
    return 7


class LessonIndex:
    """Index LESSON records by normalized situation, retaining their ids."""

    def __init__(self, records, asker: Optional[Asker] = None, superseded=()):
        if hasattr(records, 'records'):
            memory = records
            records = memory.records.values() if hasattr(memory.records, 'values') else memory.records
            inherited = _string_ids(getattr(memory, 'superseded', {}))
            inherited.update(_string_ids(superseded))
            superseded = inherited
        elif isinstance(records, dict):
            records = records.values()

        try:
            records = [record for record in records if isinstance(record, dict)]
        except TypeError:
            records = []
        dead = _string_ids(superseded)
        # A record's supersedes slot identifies the prior record even when
        # the index is built from a plain record collection.
        dead.update(record['supersedes'] for record in records
                    if isinstance(record.get('supersedes'), str) and record['supersedes'])

        self._by_trigger = {}
        self._by_id = {}
        self._resolver_safe = True
        self._asker = asker if callable(asker) else None
        self._testimonies = []
        self._resolved = {}
        self._resolve_lock = RLock()

        for record in sorted(records, key=_stable_record_key):
            if record.get('kind') != 'LESSON':
                continue
            rid = record.get('id')
            if not isinstance(rid, str) or not rid or rid in dead:
                continue
            slots = record.get('slots', {})
            situation = slots.get('situation') if isinstance(slots, dict) else None
            trigger = normalize_trigger(situation)
            if not _safe_phrase(trigger):
                # Do not put malformed or instruction-like candidate text in
                # an asker prompt. Exact valid records remain independently
                # queryable even if another row makes fallback unsafe.
                self._resolver_safe = False
                continue
            # Repeated ids represent one typed-memory row. The stable sort
            # makes the retained representation independent of input order.
            if rid in self._by_id:
                continue
            lesson = deepcopy(record)
            self._by_id[rid] = (trigger, lesson)
            self._by_trigger.setdefault(trigger, []).append(lesson)

        for lessons in self._by_trigger.values():
            lessons.sort(key=lambda record: record['id'])
        self.triggers = tuple(sorted(self._by_trigger))

    @property
    def testimonies(self) -> list[dict]:
        """Closed-choice resolution attempts, detached from the index."""
        return deepcopy(self._testimonies)

    def _resolve(self, query: str) -> Optional[str]:
        if (self._asker is None or not self._resolver_safe or not 2 <= len(self.triggers) <= _MAX_ASKER_OPTIONS
                or not _safe_phrase(query)):
            return None

        options = list(self.triggers)
        prompts = []
        raw_replies = []

        def recording_asker(prompt):
            prompts.append(prompt)
            reply = self._asker(prompt)
            raw_replies.append(reply)
            if (not isinstance(reply, str) or len(reply) > 200
                    or _strict_choice(reply, len(options)) is False):
                return ''
            return reply

        seed = _seed_with_reordered_options(len(options))
        try:
            raw_result = Resolver(recording_asker, seed=seed).resolve(
                query, options, 'LESSON trigger lookup')
        except Exception:
            asks = []
            for index, prompt in enumerate(prompts):
                reply = raw_replies[index] if index < len(raw_replies) else None
                asks.append({
                    'prompt': prompt,
                    'reply': reply[:200] if isinstance(reply, str) else None,
                    'reply_truncated': isinstance(reply, str) and len(reply) > 200,
                })
            self._testimonies.append({
                'kind': 'TESTIMONY',
                'witness': {'kind': 'testimony', 'source': 'closed-choice-asker'},
                'query': query,
                'options': options,
                'status': 'UNRESOLVED',
                'choice': None,
                'why': 'asker failure',
                'asks': asks,
            })
            return None

        raw_asks = raw_result.get('asks', [])
        valid = len(raw_asks) == 2 and len(prompts) == 2 and len(raw_replies) == 2
        picked = []
        asks = []
        for variant, raw_ask in enumerate(raw_asks):
            raw_reply = raw_replies[variant] if variant < len(raw_replies) else None
            order = raw_ask.get('order') if isinstance(raw_ask, dict) else None
            if (not isinstance(order, list) or len(order) != len(options)
                    or any(type(item) is not int for item in order)
                    or sorted(order) != list(range(len(options)))
                    or type(raw_ask.get('variant')) is not int
                    or raw_ask.get('variant') != variant):
                valid = False
                asks.append({'prompt': prompts[variant] if variant < len(prompts) else None,
                             'order': deepcopy(order), 'reply': raw_reply[:200] if isinstance(raw_reply, str) else None,
                             'reply_truncated': isinstance(raw_reply, str) and len(raw_reply) > 200,
                             'picked': False})
                continue
            choice = (False if not isinstance(raw_reply, str) or len(raw_reply) > 200
                      else _strict_choice(raw_reply, len(options)))
            real = False if choice is False else (None if choice is None else order[choice])
            picked.append(real)
            asks.append({
                'prompt': prompts[variant],
                'variant': variant,
                'order': list(order),
                'reply': raw_reply[:200] if isinstance(raw_reply, str) else None,
                'reply_truncated': isinstance(raw_reply, str) and len(raw_reply) > 200,
                'picked': real,
            })

        if (len(asks) != 2 or (len(options) > 1 and asks[0].get('order') == asks[1].get('order'))
                or len(picked) != 2 or any(choice is False for choice in picked)):
            valid = False

        choice = None
        if valid and picked[0] is None and picked[1] is None:
            status = 'NONE'
        elif valid and picked[0] == picked[1]:
            status = 'ADOPT'
            choice = options[picked[0]]
        else:
            status = 'UNRESOLVED'

        self._testimonies.append({
            'kind': 'TESTIMONY',
            'witness': {'kind': 'testimony', 'source': 'closed-choice-asker'},
            'query': query,
            'options': options,
            'status': status,
            'choice': choice,
            'asks': asks,
        })
        return choice

    def lessons_for(self, situation: str) -> list[dict]:
        """Return exact matches or an agreed closed-choice match; otherwise abstain."""
        trigger = normalize_trigger(situation)
        if not trigger:
            return []
        if trigger in self._by_trigger:
            return [deepcopy(record) for record in self._by_trigger[trigger]]

        with self._resolve_lock:
            if trigger not in self._resolved:
                self._resolved[trigger] = self._resolve(trigger)
            selected = self._resolved[trigger]
        if selected is None:
            return []
        return [deepcopy(record) for record in self._by_trigger.get(selected, ())]


def lessons_for(records, situation: str, asker: Optional[Asker] = None, superseded=(),
                testimony_sink: Optional[list[dict]] = None) -> list[dict]:
    """Convenience lookup; external resolution requires a place to retain its testimony."""
    index = LessonIndex(records, asker=asker if testimony_sink is not None else None,
                        superseded=superseded)
    result = index.lessons_for(situation)
    if testimony_sink is not None:
        testimony_sink.extend(index.testimonies)
    return result
