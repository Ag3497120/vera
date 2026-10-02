"""Read typed memory while re-checking its witnesses.

Cached witness results may be at most ``cache_ttl`` seconds old. The cache is
also bounded by ``cache_size`` entries; set either value to zero to disable
caching or storage, respectively.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable, Optional

from . import memory_frame
from .memory_frame import Memory, WriteRejected


def _blank_text_needle(witness) -> bool:
    return (isinstance(witness, dict) and witness.get('kind') == 'text_in_file' and
            (not isinstance(witness.get('needle'), str) or not witness['needle'].strip()))


def _guard_core_memory() -> None:
    """Keep direct Memory reads and writes safe for blank text witnesses."""
    if getattr(memory_frame, '_blank_needle_guard_installed', False):
        return

    original_check = memory_frame.check_witness

    def check_witness(witness):
        if _blank_text_needle(witness):
            return 'STALE'
        return original_check(witness)

    memory_frame.check_witness = check_witness

    original_write = Memory.write

    def write(self, kind, author, witness=None, supersedes=None, **slots):
        if _blank_text_needle(witness):
            raise WriteRejected('text_in_file witness には空でない needle が必要です')
        return original_write(self, kind, author, witness=witness,
                              supersedes=supersedes, **slots)

    Memory.write = write

    original_ask = Memory.ask

    def ask(self, question, require_fresh=True):
        records = getattr(self, 'records', {})
        if not any(_blank_text_needle(record.get('witness')) for record in records.values()):
            return original_ask(self, question, require_fresh)
        view = Memory.__new__(Memory)
        view.records = {rid: record for rid, record in records.items()
                        if not _blank_text_needle(record.get('witness'))}
        view.superseded = getattr(self, 'superseded', {})
        return original_ask(view, question, require_fresh)

    Memory.ask = ask
    memory_frame._blank_needle_guard_installed = True


_guard_core_memory()


class RevalidatingMemory:
    """A read-only ask wrapper that omits stale records and labels witnesses.

    ``runner`` is used only for local ``git cat-file`` witness checks. The
    result adds ``witness_status`` (record id to FRESH / STALE / UNVERIFIABLE)
    and ``stale`` (all stale active record ids) to Memory's answer. Testimony
    is answerable, but its witness status is UNVERIFIABLE.
    """

    def __init__(self, memory: Memory, *, runner: Optional[Callable] = None,
                 cache_ttl: float = 1.0, cache_size: int = 256,
                 clock: Callable[[], float] = time.monotonic):
        if not math.isfinite(cache_ttl) or cache_ttl < 0:
            raise ValueError('cache_ttl must be a finite non-negative number')
        if not isinstance(cache_size, int) or cache_size < 0:
            raise ValueError('cache_size must be a non-negative integer')
        self.memory = memory
        self.runner = runner or subprocess.run
        self.cache_ttl = float(cache_ttl)
        self.cache_size = cache_size
        self.clock = clock
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._lock = threading.RLock()

    @staticmethod
    def _key(witness) -> str:
        return json.dumps(witness, ensure_ascii=False, sort_keys=True, default=str)

    def _check(self, witness) -> str:
        if not witness or not isinstance(witness, dict):
            return 'UNVERIFIABLE'
        kind = witness.get('kind')
        if kind == 'testimony':
            return 'UNVERIFIABLE'
        try:
            if kind == 'file_sha256':
                digest = hashlib.sha256(Path(witness['path']).expanduser().read_bytes()).hexdigest()
                return 'FRESH' if digest == witness.get('sha256') else 'STALE'
            if kind == 'text_in_file':
                needle = witness.get('needle')
                if not isinstance(needle, str) or not needle.strip():
                    return 'STALE'
                return ('FRESH' if needle in
                        Path(witness['path']).expanduser().read_text() else 'STALE')
            if kind == 'git_commit':
                result = self.runner(
                    ['git', '-C', str(Path(witness['repo']).expanduser()), 'cat-file', '-e',
                     str(witness['commit']) + '^{commit}'],
                    capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
                return 'FRESH' if result.returncode == 0 else 'STALE'
        except (OSError, KeyError, TypeError, ValueError):
            return 'STALE' if kind in ('file_sha256', 'text_in_file') else 'UNVERIFIABLE'
        except Exception:
            return 'UNVERIFIABLE'
        return 'UNVERIFIABLE'

    def _status(self, witness) -> str:
        key = self._key(witness)
        with self._lock:
            now = self.clock()
            cached = self._cache.get(key)
            if cached is not None:
                checked_at, status = cached
                if self.cache_ttl > 0 and now - checked_at < self.cache_ttl:
                    self._cache.move_to_end(key)
                    return status
                del self._cache[key]
            status = self._check(witness)
            if self.cache_size and self.cache_ttl:
                self._cache[key] = (self.clock(), status)
                self._cache.move_to_end(key)
                while len(self._cache) > self.cache_size:
                    self._cache.popitem(last=False)
            return status

    def _view(self):
        active = self.memory.active(require_fresh=False)
        statuses = {record['id']: self._status(record.get('witness')) for record in active}
        records = {record['id']: record for record in active
                   if statuses[record['id']] != 'STALE'}

        # Memory.ask only needs these two fields. The view shares record values
        # but has no path and cannot append events to the original log.
        view = Memory.__new__(Memory)
        view.records = records
        view.superseded = {}
        return view, statuses

    @staticmethod
    def _label(answer: dict, statuses: dict) -> dict:
        answer['witness_status'] = statuses
        answer['stale'] = [rid for rid, status in statuses.items() if status == 'STALE']
        return answer

    def ask(self, question: str, require_fresh: bool = True) -> dict:
        """Ask after validating active records; STALE records cannot support answers."""
        view, statuses = self._view()
        answer = Memory.ask(view, question, require_fresh=False)
        return self._label(answer, statuses)

    def ask_about(self, subject: str, attribute: Optional[str] = None,
                  kind: str = 'FACT', require_fresh: bool = True) -> dict:
        """Ask for a typed slot with the same normalization as ``Memory``."""
        view, statuses = self._view()
        answer = Memory.ask_about(view, subject, attribute, kind, require_fresh=False)
        return self._label(answer, statuses)
