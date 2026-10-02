"""Read-only adapter to existing conductive and predicate/term postings.

Retrieval proposes original rows. Legacy SlotFrame qualification/ANSWER is
never used. Context questions are metadata, not asserted supporting facts.
"""
from __future__ import annotations

import time

from . import conduct_tree
from .answer_slots import nouns
from .evidence_library import EvidenceLibrary
from .semantic_ir import Budget, Limit, Variable
from .semantic_reader import document_view


class Retriever:
    families = ('general_qa', 'local', 'pro', 'jawiki')

    def __init__(self, root):
        started = time.perf_counter(); self.root = root; self.libraries = {}
        for family in self.families:
            directory = root / family / 'evidence'
            if (directory / 'evidence.db').is_file():
                library = EvidenceLibrary(directory, family)
                library.con.execute('PRAGMA query_only=ON')
                self.libraries[family] = library
        self.initialization_ms = (time.perf_counter()-started)*1000

    def close(self):
        for library in self.libraries.values(): library.close()
        self.libraries.clear()

    def retrieve(self, request, budget=Budget()):
        started = time.perf_counter(); views = []; trace = []; provenance = {}; total = 0
        predicates = {n.pattern.predicate for p in request.plans for n in p.nodes if n.pattern and n.pattern.predicate != '*'}
        anchors = {term for p in request.plans for n in p.nodes if n.pattern for role, term in n.pattern.roles
                   if role != 'attribute' and isinstance(term, str) and term}
        depth = max((p.depth() for p in request.plans), default=0)
        for family, library in self.libraries.items():
            library._refresh(); con = library.con; ids = set(); rows = {}; queries = 0; seen = set(); routes = []
            pending = set(anchors)
            def add(sql, params):
                nonlocal queries, total
                queries += 1
                if queries > budget.steps: raise Limit('retrieval queries')
                found = con.execute(sql, (*params, budget.candidates+1)).fetchall()
                if len(found) > budget.candidates: raise Limit('retrieval candidates')
                for item in found:
                    rid = item[0]
                    if rid not in ids:
                        ids.add(rid); total += 1
                        if total > budget.candidates: raise Limit('retrieval candidates')
            con.execute('BEGIN')
            try:
                for _ in range(depth):
                    current = pending-seen
                    if not current: break
                    seen.update(current); pending = set()
                    for anchor in current:
                        tokens = set((anchor, *nouns(anchor)))
                        route = conduct_tree.descend(library.root, list(tokens), anchor=anchor) if library.root else {'verdict': 'UNKNOWN_NO_ROUTE'}
                        routes.append({'anchor': anchor, **route})
                        if route.get('verdict') == 'ROUTED':
                            add('SELECT id FROM rows WHERE leaf=? AND subject=? LIMIT ?', (route['leaf'], anchor))
                        for token in tokens:
                            add('SELECT rid FROM terms WHERE token=? LIMIT ?', (token,))
                        for predicate in predicates:
                            add('SELECT rid FROM frames WHERE predicate=? AND subject=? LIMIT ?', (predicate, anchor))
                    missing = ids-rows.keys()
                    if missing:
                        marks = ','.join('?' for _ in missing)
                        queries += 1
                        for row in con.execute(f'SELECT * FROM rows WHERE id IN ({marks})', tuple(missing)):
                            rows[row['id']] = dict(row)
                        # Expand the next nominal dependency by grounded entity
                        # values, still only for recall and within the same DB.
                        dv = document_view({f'{family}:row:{rid}': row['text'] for rid,row in rows.items()}, family=family)
                        for c in dv.clauses:
                            if c.predicate == 'property':
                                pending.update(r.term for r in c.roles if r.name == 'value' and isinstance(r.term,str))
                texts = {}; sovereigns = {}
                for rid,row in rows.items():
                    key = f'{family}:row:{rid}'; texts[key] = row['text']
                    sovereigns[key] = family + ':' + row['independent']
                    provenance[key] = {'source': row['source'], 'row_id': rid, 'independent': row['independent']}
                views.append(document_view(texts, sovereigns=sovereigns, family=family))
                trace.append({'part': 'semantic_retrieve.Retriever', 'status': 'ran', 'family': family,
                              'rows': len(rows), 'queries': queries, 'candidate_limit': budget.candidates,
                              'routes': routes, 'context_is_evidence': False, 'read_only': True})
            except Limit as exc:
                exc.trace = [*trace, {'part':'semantic_retrieve.Retriever','status':'abstained','family':family,
                                     'rows_seen':len(ids),'queries':queries,'total_rows_seen':total,
                                     'candidate_limit':budget.candidates,'reason':str(exc),'read_only':True,
                                     'retrieval_ms':(time.perf_counter()-started)*1000,
                                     'index_initialization_ms':self.initialization_ms}]
                raise
            finally:
                con.rollback()
        trace.append({'part': 'semantic_retrieve.total', 'status': 'ran', 'rows': total,
                      'retrieval_ms': (time.perf_counter()-started)*1000, 'index_initialization_ms': self.initialization_ms})
        return views, trace, provenance
