"""Bounded, read-only access to independently stored composition materials.

This adapter supplies source records, never answers or transferable truth
labels. A consumer must read their roles, scope and fiction status and verify
its own construction. Existing family answers and scores are not called.
"""
from __future__ import annotations

import json
import pickle
import sqlite3
import time
from pathlib import Path

from . import conduct_tree
from .family_library import FORMAT, _norm, _terms
from .lang import ja_content_runs


class MaterialSource:
    families = ('paraphrase_entail', 'narrative')

    def __init__(self, root: str | Path, *, immutable: bool = False):
        if type(immutable) is not bool:
            raise ValueError('immutable must be a boolean for an already frozen material index')
        self.root = Path(root)
        self.immutable = immutable
        self._routes = {}

    def candidates(self, family: str, text: str, *, limit: int = 64) -> dict:
        if family not in self.families:
            raise ValueError('unsupported material family')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('material query must be nonempty text')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 256:
            raise ValueError('material candidate limit must be between 1 and 256')
        started = time.perf_counter()
        trace = {'part': 'material_source.MaterialSource', 'family': family,
                 'read_only': True, 'immutable': self.immutable, 'candidate_limit': limit, 'queries': 0,
                 'selection_is_evidence': False, 'consumer_verification_required': True}

        def result(verdict, rows=(), reason=''):
            return {'kind': 'materials', 'verdict': verdict, 'family': family,
                    'records': list(rows), 'reason': reason, 'verified': False,
                    'trace': [dict(trace, elapsed_ms=(time.perf_counter()-started)*1000)]}

        if len(text) > 4096:
            return result('UNKNOWN_BUDGET', reason='material query length')
        directory = self.root / family
        database = directory / 'family.db'
        if not database.is_file():
            return result('UNKNOWN_SOURCE_ASSET', reason='material family is not built')
        # immutable=1 ignores journals. It is an explicit assertion by the
        # caller that this is a pinned, checkpointed release, never a live DB.
        # Refuse an obvious incomplete checkpoint instead of reading old pages.
        if self.immutable:
            try:
                pending = [suffix for suffix in ('-wal', '-journal')
                           if (journal := Path(str(database)+suffix)).exists() and journal.stat().st_size]
            except OSError:
                return result('UNKNOWN_SOURCE_ASSET', reason='material journal state is unavailable')
            if pending:
                return result('UNKNOWN_SOURCE_ASSET', reason='immutable material index requires a checkpointed database')
        tokens = _terms(text)
        if len(tokens) > 64:
            return result('UNKNOWN_BUDGET', reason='material query tokens')
        connection = None
        try:
            uri = database.resolve().as_uri()+'?mode=ro'+('&immutable=1' if self.immutable else '')
            connection = sqlite3.connect(uri, uri=True)
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            trace['queries'] += 1
            ids = [r[0] for r in connection.execute(
                'SELECT DISTINCT rid FROM variants WHERE norm=? LIMIT ?', (_norm(text), limit+1))]
            trace['path'] = 'exact_surface'
            if not ids:
                route_path = directory / 'route.pkl'
                if not route_path.is_file():
                    return result('UNKNOWN_NO_ROUTE', reason='material routing asset is missing')
                stamp = (route_path.stat().st_mtime_ns, route_path.stat().st_size)
                cached = self._routes.get(family)
                if cached is None or cached[0] != stamp:
                    with route_path.open('rb') as stream:
                        version, root = pickle.load(stream)
                    if version != FORMAT:
                        return result('UNKNOWN_SOURCE_ASSET', reason='unsupported material route format')
                    self._routes[family] = (stamp, root)
                else:
                    root = cached[1]
                runs = ja_content_runs(text)
                anchor = next((r for r in runs if len(r) >= 2), None)
                route = conduct_tree.descend(root, sorted(set(tokens) | set(runs)), anchor=anchor) if root else {'verdict': 'UNKNOWN_NO_ROUTE'}
                trace.update(path='conduct', route=route)
                if route.get('verdict') != 'ROUTED' or not tokens:
                    return result('UNKNOWN_NO_ROUTE', reason='no unambiguous material leaf')
                marks = ','.join('?' for _ in tokens)
                trace['queries'] += 1
                ids = [r[0] for r in connection.execute(
                    f'SELECT DISTINCT rid FROM terms WHERE leaf=? AND token IN ({marks}) LIMIT ?',
                    (route['leaf'], *tokens, limit+1))]
            if len(ids) > limit:
                return result('UNKNOWN_BUDGET', reason='material candidate overflow; no prefix returned')
            if not ids:
                return result('UNKNOWN_NO_EVIDENCE', reason='no matching material record')
            marks = ','.join('?' for _ in ids)
            trace['queries'] += 1
            records = []
            for row in connection.execute(f'SELECT id,source,sha,payload FROM records WHERE id IN ({marks}) ORDER BY id', ids):
                if len(row['payload'].encode('utf-8')) > 65536:
                    return result('UNKNOWN_BUDGET', reason='material record byte limit')
                payload = json.loads(row['payload'])
                if (not isinstance(payload, dict) or payload.get('family') != family or payload.get('split') != 'train'
                        or payload.get('source') != row['source'] or payload.get('sha') != row['sha']):
                    return result('UNKNOWN_SOURCE_ASSET', reason='material provenance does not match stored row')
                records.append({'family': family, 'row_id': row['id'], 'source': row['source'],
                                'sha': row['sha'], 'payload': payload,
                                'role': 'structural_material' if family == 'paraphrase_entail' else 'fiction_material',
                                'verified': False})
            trace['rows'] = len(records)
            return result('MATERIALS', records)
        except (sqlite3.DatabaseError, ValueError, TypeError, OSError, EOFError, pickle.UnpicklingError) as exc:
            return result('UNKNOWN_SOURCE_ASSET', reason=type(exc).__name__)
        finally:
            if connection is not None: connection.close()
