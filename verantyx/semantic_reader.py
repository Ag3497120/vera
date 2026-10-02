"""A bounded, compositional Japanese reader for Round5-A.

Frame/Edge/Stage/Item readings are candidates. Their roles stay clause-local;
unknown constructions remain source-bound Unread records rather than slots.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from decimal import Decimal

from .frames import CONVERSE, canonical, read_all, _predicates
from .question import Stage
from .semantic_coord import chunk, coordination_ok, own_subject_phrase, phrase_bounded, topic_phrase, tag
from .semantic_names import is_past_aux, name_split_in, tokens_covering
from .semantic_ir import (Limit, Budget, Clause, Nominal, Obligation, Operator, Output,
                          Pattern, Plan, Quantity, Request, Role, Span, Test, Unread, Variable, View)
from .typed_edges import _base, _tagger, extract
from .verdict import COND, _clause_kind, read_records

_NUM = re.compile(r'([+-]?[0-9]+(?:\.[0-9]+)?)\s*([A-Za-z%]+|[一-鿿]+)')
_WH = re.compile(r'誰|だれ|何|どこ|いつ|どちら|いくつ')
# The copula だ is dropped, but not the past auxiliary だ after a 撥音便/イ音便 stem (呼んだ, 泳いだ).
_END = re.compile(r'(?:ですか|ますか|でしょうか|です|(?<![んい])だ|か)?[？?。！!]*$')
_MODAL_UNSUPPORTED = re.compile(r'もし|だったなら|はず|かもしれ|だろう|らしい|そう(?:だ|です|だった|でした)')
_COMPLEX = re.compile(r'すべて|全部|それぞれ|最後|最初|同時|前後|以前|以後|最新|現在|今日|昨日|今年|午前|午後|[0-9]+[年月日時]|ただし|以外|除[くき]|のみ|だけ|必ず')
_ROLE_WORDS = {'受取人': 'recipient', '受領者': 'recipient', '渡した人': 'agent',
               '作成者': 'agent', '起点': 'origin', '終点': 'recipient', '相手': 'recipient'}
_DOUBLE_NEGATION = re.compile(r'(?:ない|なく|ぬ)(?:わけ|こと|もの)(?:では|じゃ|は|も)|なくはない|ないとは限らない')
_NEGATIVE_ADJECTIVE = re.compile(r'(?:くない|くありません|くなかった|くありませんでした)[。！？?]*$')
_TIME_NOMINAL = re.compile(r'(?:[0-9０-９]+\s*)?(?:年|月|日|時|分|秒|曜日|頃|ごろ|午前|午後|朝|昼|夜)$')
_GOAL_PREDICATES = frozenset(('行く','来る','帰る','戻る','向かう','着く','入る','出る','進む','移る','渡る','送る','届ける'))
_LOCATION_PREDICATES = frozenset(('住む','滞在する','位置する','存在する'))
_MEANS_NOMINALS = frozenset(('車','電車','バス','飛行機','船','自転車','徒歩','手','指','箸','包丁','ペン','鉛筆','電話','メール','日本語','英語','道具','方法','手段'))
_PLACE_NOMINALS = frozenset(('学校','家','駅','公園','部屋','店','会社','図書館','病院','工場','東京','大阪','京都','日本','教室','庭','海','山'))


def _span(source, raw, start=0, end=None):
    end = len(raw) if end is None else end
    return Span(source, start, end, raw[start:end])


def _tokens(text):
    out = []; cursor = 0
    for word in _tagger()(text):
        at = text.find(word.surface, cursor)
        out.append((word, at, at + len(word.surface))); cursor = at + len(word.surface)
    return out


def _uncovered_nominals(tokens, covered):
    """Content omitted by a Frame must remain an explicit unread requirement."""
    for word, start, end in tokens:
        if word.feature.pos1 in ('名詞', '代名詞', '形容詞', '形状詞', '副詞', '接頭辞', '接尾辞'):
            if not any(left <= start and end <= right for left, right in covered):
                return True
    return False


def _predicate_coverage(tokens, ev, predicate):
    spans = [tokens[ev][1:]]
    # サ変 nouns belong to the parsed predicate, not to an omitted argument.
    if ev and _base(tokens[ev][0]) == 'する':
        noun = tokens[ev-1][0]
        if noun.feature.pos1 == '名詞' and _base(noun)+'する' == predicate:
            spans.append(tokens[ev-1][1:])
    return spans


def _event_time(words, predicate_index):
    # The candidate Frame stops at a compound verb's first independent verb.
    # Read the single clause's grammatical auxiliaries, including the compound
    # tail (e.g. 受け/取っ/た), instead of dropping its past tense.
    return 'past' if any(is_past_aux(w)
                         for w in words[predicate_index + 1:]) else 'nonpast'


def _case_phrase(text, tokens, particle_index, lower=0):
    """Return the source-bounded nominal phrase immediately before a case particle."""
    j = particle_index - 1
    while j >= 0 and tokens[j][2] > lower:
        word = tokens[j][0]
        pos = word.feature.pos1
        if pos in ('名詞','代名詞','形容詞','形状詞','接頭辞','接尾辞','数'):
            j -= 1; continue
        if pos == '助詞' and word.surface == 'の':
            j -= 1; continue
        break
    first = j + 1
    if first >= particle_index: return None
    start, end = tokens[first][1], tokens[particle_index - 1][2]
    phrase = text[start:end]
    return start, end, phrase


def _case_role(particle, phrase, predicate, *, quoted=False, person=False):
    """Map only morphologically or syntactically resolved cases; label the rest."""
    compact = phrase.replace(' ', '').replace('　', '')
    if particle == 'に':
        if _TIME_NOMINAL.search(compact): return 'time', 'case'
        if predicate in _GOAL_PREDICATES: return 'goal', 'case'
        if predicate in _LOCATION_PREDICATES: return 'location', 'case'
        return 'ambiguous', 'case:に:location|goal|time'
    if particle == 'で':
        head = compact.split('の')[-1]
        if head in _PLACE_NOMINALS or any(head.endswith(x) for x in ('学校','駅','公園','会社','図書館','病院','市','町','県','国','室')):
            return 'place', 'case'
        if head in _MEANS_NOMINALS or head.endswith('語'):
            return 'means', 'case'
        return 'ambiguous', 'case:で:place|means'
    if particle == 'と':
        if quoted: return 'quotation', 'case'
        if person: return 'companion', 'case'
        return 'ambiguous', 'case:と:companion|quotation'
    if particle == 'から':
        return ('time' if _TIME_NOMINAL.search(compact) else 'source'), 'case'
    if particle == 'まで': return 'limit', 'case'
    if particle == 'へ': return 'direction', 'case'
    return None, 'case'


def _case_roles(text, tokens, predicate_index, lower=0, existing=(), offset=0):
    """Read case adjuncts attached before this predicate and preserve ambiguity."""
    predicate = _base(tokens[predicate_index][0]) if predicate_index < len(tokens) else ''
    roles = []; issues = []
    existing_spans = set(); existing_terms = set()
    for item in existing:
        if hasattr(item, 'span'):
            existing_spans.add((item.span.start-offset, item.span.end-offset))
            existing_terms.add(str(item.term))
        elif isinstance(item, tuple) and len(item) == 2:
            existing_terms.add(str(item[1]))
    for ti, (word, start, end) in enumerate(tokens):
        if start < lower or ti >= predicate_index: continue
        if word.feature.pos1 != '助詞' or word.feature.pos2 != '格助詞' or word.surface not in ('に','で','と','から','まで','へ'):
            continue
        located = _case_phrase(text, tokens, ti, lower)
        if located is None: continue
        pstart, pend, phrase = located
        # A frame's recipient is already a better typed reading of this に phrase.
        if (pstart, pend) in existing_spans or phrase in existing_terms: continue
        # Wh-bearing phrases are variables in requests, not asserted case adjuncts.
        if _WH.search(phrase): continue
        quoted = word.surface == 'と' and text[:start].rstrip().endswith('」')
        if quoted:
            close = text.rfind('」', 0, start)
            opening = text.rfind('「', 0, close)
            if opening >= 0:
                pstart, pend = opening + 1, close
                phrase = text[pstart:pend]
        person = False
        if word.surface == 'と':
            prior = tokens[ti - 1][0] if ti else None
            person = bool(prior and (prior.feature.pos3 == '人名' or phrase.endswith('さん') or phrase.endswith('氏')))
        role, kind = _case_role(word.surface, phrase, predicate, quoted=quoted, person=person)
        if role is None: continue
        span = (pstart, pend)
        if span in existing_spans: continue
        roles.append((role, phrase, span, kind))
        if role == 'ambiguous': issues.append('ambiguous case role: '+word.surface)
    return roles, issues


def attribute(text):
    words = list(_tagger()(text))
    if len(words) == 2 and words[0].feature.pos1 == '形容詞' and words[1].surface == 'さ':
        return 'nominal:' + _base(words[0])
    return text


def quantity(text):
    m = _NUM.fullmatch(text.strip())
    if not m: return None
    value = Decimal(m[1])
    if len(value.as_tuple().digits) > 128: return None
    return Quantity(value, m[2])


def _sentences(raw):
    start = 0; quoted = 0
    for i, ch in enumerate(raw):
        if ch in '「『': quoted += 1
        elif ch in '」』': quoted = max(0, quoted - 1)
        if quoted == 0 and ch in '。！？\n':
            if raw[start:i+1].strip(): yield start, i+1
            start = i+1
    if raw[start:].strip(): yield start, len(raw)


def _piece(source, raw, start, end, sovereign, family):
    full = _span(source, raw, start, end)
    left = start + len(full.text) - len(full.text.lstrip()); right = end
    # A prefix can declare a hypothesis, correction, quotation or normative
    # scope. It is not transparent metadata. Until that scope has a typed
    # interpretation, retain it as unread instead of asserting the suffix.
    colon = raw.find(':', left, right)
    if colon < 0: colon = raw.find('：', left, right)
    if colon >= 0:
        # Keep a complete numeric colon-valued copula (e.g. a displayed
        # clock value) as literal text. A label ending in a digit is not that
        # grammar and receives no exception. Nothing before a colon is cut.
        numeric_value = re.fullmatch(
            r'\s*[^:：。！？\n]+[はが]\s*[0-9]+(?:[:：][0-9]+)+(?:です|である|だ|ではない|でない|じゃない)?[。！？?]*\s*',
            raw[left:right])
        if not numeric_value:
            return [], [Unread(full, 'uninterpreted colon scope')]
    while left < right and raw[left] in ' 、,': left += 1
    condition = []; guard_spans = []; unknown = []
    text = raw[left:right]
    if _COMPLEX.search(text): unknown.append('unsupported source quantifier/exception/time')
    cm = COND.match(text)
    if cm and cm.group(1).strip():
        guard = _span(source, raw, left, left + len(cm.group(1)))
        gc, gu = _piece(source, raw, guard.start, guard.end, sovereign, family)
        if len(gc) == 1 and not gu and not gc[0].conditions and not gc[0].unsupported:
            c = gc[0]
            condition.append(Pattern(c.predicate, tuple((r.name, r.term) for r in c.roles), c.polarity, c.modality, c.time))
            if c.modality != 'assert': unknown.append('unsupported antecedent modality')
        else: unknown.append('unsupported antecedent')
        guard_spans.append(guard); left += cm.end(); text = raw[left:right]
    body = _span(source, raw, left, right)
    tokens = _tokens(text); words = [t[0] for t in tokens]
    if text.rstrip().endswith(('?', '？')) or any(w.feature.pos1 == '助詞' and w.surface in ('か', 'かな', 'かしら', 'かい', 'かね', 'っけ') for w in words):
        return [], [Unread(full, 'interrogative source does not assert a fact')]
    if _DOUBLE_NEGATION.search(text):
        return [], [Unread(full, 'unsupported double negation')]
    if _NEGATIVE_ADJECTIVE.search(text):
        return [], [Unread(full, 'unsupported negative adjective')]
    if any('意志推量' in str(w.feature.cForm) for w in words):
        return [], [Unread(full, 'volitional source does not assert a fact')]
    # A duration (1時間) is not a clock-time scope: judge the other complex-scope words on the text without it.
    plain = re.sub(r'[0-9]+(?:\.[0-9]+)?(?:時間|分|秒)', '', text)
    if not condition and not _COMPLEX.search(plain) and all(u == 'unsupported source quantifier/exception/time' for u in unknown):
        from .semantic_measure import read_measure_sentence
        measured = read_measure_sentence(source, raw, start, left, right, sovereign, family)
        if measured is not None: return measured, []
    edges = extract(text); frames = read_all(text); records = read_records(text, 'record')
    predicates = _predicates(words)
    result = []
    # Noun copulas (including explicit nominal fragments) are relational facts.
    m = re.fullmatch(r'\s*(.+?)[はが]\s*(.*?)[。！？?]*\s*', text)
    if m and not frames and m[2] and not _WH.search(m[2]):
        lhs, raw_value = m[1], m[2]
        suffix = re.search(r'(ではなかった|でなかった|じゃなかった|ではない|でない|じゃない|でした|だった|である|です|だ)$', raw_value)
        copula = suffix[1] if suffix else ''
        value = raw_value[:suffix.start()] if suffix else raw_value
        value = value.rstrip()
        if not value:
            return [], [Unread(full, 'unsupported empty copula value')]
        parts = lhs.split('の'); entity = 'の'.join(parts[:-1]) if len(parts)>1 else lhs
        attr = parts[-1] if len(parts)>1 else ''
        entity_at = left + text.index(entity); value_at = left + m.start(2)
        roles = [Role('entity', entity, _span(source, raw, entity_at, entity_at+len(entity)))]
        if attr:
            at = left + m.start(1) + len(lhs) - len(attr)
            roles.append(Role('attribute', attribute(attr), _span(source, raw, at, at+len(attr)), 'nominal'))
        q = quantity(value)
        if _NUM.fullmatch(value.strip()) and q is None: unknown.append('quantity outside exact contract')
        if entity in ('彼','彼女','それ','これ','あれ') or value in ('彼','彼女','それ','これ','あれ'):
            unknown.append('unresolved anaphora')
        roles.append(Role('value', q or value, _span(source, raw, value_at, value_at+len(value)), 'quantity' if q else 'literal'))
        pol = '-' if copula in ('ではなかった','でなかった','じゃなかった','ではない','でない','じゃない') else '+'
        before = raw[:value_at]; quoted = before.count('「')>before.count('」')
        mod = 'quote' if quoted else ('hedge' if _MODAL_UNSUPPORTED.search(text) else 'assert')
        ident = hashlib.sha256(f'{source}:{start}:{end}:copula'.encode()).hexdigest()[:24]
        result.append(Clause(ident, Variable('event_'+ident, 'event'), 'property' if attr else 'identity',
            _span(source, raw, value_at, value_at+len(value)), tuple(roles), full, body,
            polarity=pol, modality=mod, time='past' if copula in ('ではなかった','でなかった','じゃなかった','でした','だった') else '', conditions=tuple(condition), condition_spans=tuple(guard_spans),
            rule='copula', sovereign=sovereign, family=family, unsupported=tuple(unknown)))
    elif frames:
        if len(frames) != len(predicates): unknown.append('predicate/frame alignment')
        tagged = tag([w for w, _, _ in tokens], [s0 for _, s0, _ in tokens])
        coordinated = (len(frames) > 1 and len(frames) == len(predicates)
                       and _clause_kind(text, 'record', False) == 'fact'
                       and coordination_ok(tagged, [p0 for p0, _ in predicates]))
        if len(frames) > 1 and not coordinated: unknown.append('multiple predicates need explicit clause scope')
        for index, frame in enumerate(frames):
            if index >= len(predicates): break
            ev, surface_pred = predicates[index]; word, pstart, pend = tokens[ev]
            roles = []; descriptors = []; issues = list(unknown)
            previous = predicates[index-1][0] if index else -1
            chunk_start = tokens[previous][2] if previous >= 0 else 0
            for role in ('agent','patient','recipient'):
                value = getattr(frame, role)
                if not value: continue
                at = text.rfind(value, chunk_start, pstart)
                if at < 0:
                    at = text.find(value, 0, pstart)
                    if at >= 0 and at < chunk_start:       # the phrase belongs to an earlier clause: a borrowed role
                        pidx = [p0 for p0, _ in predicates]
                        topic = topic_phrase(tagged, pidx) if coordinated else None
                        c_first, c_last = chunk(tagged, pidx, index) if coordinated else (0, 0)
                        if not (coordinated and role == 'agent' and index > 0 and topic == (at, at + len(value))
                                and not own_subject_phrase(tagged, c_first, c_last)):
                            issues.append('unlicensed role borrowing'); continue
                if at < 0:
                    issues.append('unlocated '+role); continue
                if value in ('彼','彼女','それ','これ','あれ') or '彼の' in value:
                    issues.append('unresolved anaphora')
                split = name_split_in(tokens_covering([(w.surface, w.feature.pos1, w.feature.pos2, a0, a1) for w, a0, a1 in tokens], at, at+len(value)), value)
                if split:      # an appositive descriptor (技師ユン) names the person; keep it covered, not as the value
                    desc, head = split
                    roles.append(Role(role, canonical(head), _span(source, raw, left+at+len(desc), left+at+len(value)), 'frame'))
                    descriptors.append((at, at+len(desc)))
                else:
                    roles.append(Role(role, canonical(value), _span(source, raw, left+at, left+at+len(value)), 'frame'))
            # Case adjuncts stay attached to this predicate and retain their exact source span.
            case_roles, case_issues = _case_roles(text, tokens, ev, chunk_start, roles, left)
            issues.extend(case_issues)
            for role, term, (at, end_at), kind in case_roles:
                roles.append(Role(role, term, _span(source, raw, left+at, left+end_at), kind))
                if term in ('彼','彼女','それ','これ','あれ') or '彼の' in term:
                    issues.append('unresolved anaphora')
            covered = [(r.span.start-left, r.span.end-left) for r in roles] + descriptors + _predicate_coverage(tokens, ev, surface_pred)
            own_tokens = tokens
            if coordinated:        # the other clauses of a coordinated sentence are read as their own clauses
                own_first, own_last = chunk(tagged, [p0 for p0, _ in predicates], index)
                own_tokens = tokens[own_first:own_last + 1]
            if _uncovered_nominals(own_tokens, covered): issues.append('unrepresented source content')
            for r in roles:
                if r.name not in ('agent','patient','recipient','origin','source','location','goal','time','place','means','companion','quotation','limit','direction','ambiguous'): continue
                lo_, hi_ = r.span.start - left, r.span.end - left
                for d0, d1 in descriptors:
                    if d1 == lo_: lo_ = d0
                if not phrase_bounded(tagged, lo_, hi_): issues.append('unrepresented source content'); break
            if len({r.name for r in roles}) != len(roles): issues.append('duplicate role in clause')   # two で-phrases: not representable
            if frame.ambiguous: issues.append('ambiguous frame role')
            mod = _clause_kind(text, 'record', frame.negated)
            mod = 'assert' if mod == 'fact' else mod
            clause_edges = [e for e in edges if e.ev == ev]
            if any(e.mod in ('quote','hedge','simile') for e in clause_edges): mod = clause_edges[0].mod
            if _MODAL_UNSUPPORTED.search(text): mod = 'hedge'
            before = raw[:left+pstart]
            if before.count('「')>before.count('」'): mod = 'quote'
            pol = '-' if frame.negated and mod not in ('prohibition','obligation') else '+'
            ident = hashlib.sha256(f'{source}:{start}:{end}:{index}'.encode()).hexdigest()[:24]
            result.append(Clause(ident, Variable('event_'+ident,'event'),frame.predicate,
                _span(source,raw,left+pstart,left+pend),tuple(roles),full,body,polarity=pol,
                modality=mod,time=_event_time(words,ev),conditions=tuple(condition),
                condition_spans=tuple(guard_spans),rule='frame',sovereign=sovereign,family=family,
                unsupported=tuple(issues)))
    if not result:
        return [], [Unread(full,'unsupported clause grammar')]
    return result, []


def document_view(documents, *, sovereigns=None, family='document'):
    started = time.perf_counter(); sources = dict(documents); clauses = []; unread = []
    from .bot import _INJECTED
    for source, raw in sources.items():
        sovereign = (sovereigns or {}).get(source, family)
        for start, end in _sentences(raw):
            if _INJECTED.search(raw[start:end]):
                unread.append(Unread(_span(source,raw,start,end),'document instruction excluded')); continue
            cs, us = _piece(source,raw,start,end,sovereign,family)
            if re.match(r'\s*ただし',raw[start:end]):
                if clauses and clauses[-1].span.source == source:
                    base = clauses[-1]
                    if cs and cs[0].conditions:
                        clauses[-1] = replace(base,exceptions=cs[0].conditions,exception_spans=cs[0].condition_spans)
                        cs = [replace(c,exception_of=base.id) for c in cs]
                    else:
                        clauses[-1] = replace(base,unsupported=(*base.unsupported,'unsupported explicit exception'))
                        cs = [replace(c,unsupported=(*c.unsupported,'unsupported explicit exception'),exception_of=base.id) for c in cs]
                else: us.append(Unread(_span(source,raw,start,end),'exception has no source rule'))
            clauses.extend(cs); unread.extend(us)
    return View(sources,tuple(clauses),tuple(unread),(time.perf_counter()-started)*1000)


class Builder:
    def __init__(self,text):
        self.text=text; self.nodes=[]; self.obligations=[]; self.outputs=[]; self.roots=[]; self.number=0

    def variable(self,sort='entity'):
        self.number+=1; return Variable('v'+str(self.number),sort)

    def obligation(self,node,kind,span,detail=''):
        ident='o'+str(len(self.obligations))
        self.obligations.append(Obligation(ident,span,kind,node,detail)); return ident

    def bind(self,pattern,span,target=None,relation=''):
        ident='n'+str(len(self.nodes)); ids=[self.obligation(ident,'relation',span,pattern.predicate)]
        for name,term in pattern.roles: ids.append(self.obligation(ident,'role',span,name))
        for kind,detail in (('polarity',pattern.polarity),('modality',pattern.modality)):
            ids.append(self.obligation(ident,kind,span,detail))
        if pattern.time:ids.append(self.obligation(ident,'time',span,pattern.time))
        if pattern.event is not None:ids.append(self.obligation(ident,'event',span))
        self.nodes.append(Operator(ident,'Bind',pattern=pattern,target=target,relation=relation,obligations=tuple(ids),span=span))
        current=ident
        for op in ('ApplyCondition','Except'):
            next_id='n'+str(len(self.nodes)); self.nodes.append(Operator(next_id,op,inputs=(current,))); current=next_id
        self.roots.append(current); return current

    def path(self,phrase,span,sort='value'):
        parts=phrase.split('の')
        if any(not p for p in parts): raise ValueError('empty nominal path')
        subject=parts[0]
        if len(parts)==1:
            value=self.variable(sort); self.bind(Pattern('identity',(('entity',subject),('value',value))),span); return value
        for i,attr in enumerate(parts[1:]):
            value=self.variable(sort if i==len(parts)-2 else 'entity')
            self.bind(Pattern('property',(('entity',subject),('attribute',attribute(attr)),('value',value))),span)
            subject=value
        return subject

    def finish(self):
        if not self.roots or not self.outputs: raise ValueError('no answer obligations')
        current=self.roots[0]
        for root in self.roots[1:]:
            ident='n'+str(len(self.nodes)); self.nodes.append(Operator(ident,'Join',inputs=(current,root))); current=ident
        return current

    def project(self,current):
        ident='n'+str(len(self.nodes)); outputs=[]; ids=[]
        for label,term,span,unit in self.outputs:
            oid=self.obligation(ident,'output',span,label); ids.append(oid); outputs.append(Output(label,term,oid,unit,span))
        self.nodes.append(Operator(ident,'Project',inputs=(current,),outputs=tuple(outputs),obligations=tuple(ids)))
        return Plan(tuple(self.nodes),ident)


def _property_question(fragment,b,span):
    cleaned=_END.sub('',fragment).strip()
    m=re.fullmatch(r'(.+?)(?:は|が)(?:誰|だれ|何|どこ|いつ)([A-Za-z一-鿿]*)',cleaned)
    if m:
        phrase=m[1]; unit=m[2]; value=b.path(phrase,span,'quantity' if unit else 'value')
        b.outputs.append((phrase,value,span,unit)); return True
    if cleaned.endswith('は'):
        phrase=cleaned[:-1]
        if read_all(phrase): return False
        if phrase in _ROLE_WORDS:
            value=b.variable(); b.bind(Pattern('*',((_ROLE_WORDS[phrase],value),)),span)
        elif 'の' in phrase:
            value=b.path(phrase,span)
        else:
            subject=b.variable(); value=b.variable('value')
            b.bind(Pattern('property',(('entity',subject),('attribute',attribute(phrase)),('value',value))),span)
        b.outputs.append((phrase,value,span,'')); return True
    return False


def _event_question(fragment,b,span):
    cleaned=_END.sub('',fragment).strip()
    # A relative head names the missing event role, and becomes a bound variable.
    relative=re.fullmatch(r'(.+?)(人|もの|物|箱|鍵|資料)(?:は)?',cleaned)
    # Cleft question ("Xを呼んだのは？"): the omitted head asks for the role the clause leaves open.
    cleft=None if relative else re.fullmatch(r'(.+?)の(?:は|が)(?:誰|だれ|何)?',cleaned)
    if cleft: relative=re.fullmatch(r'(.+?)(もの)',cleft[1]+'もの')
    core=relative[1] if relative else cleaned
    frames=read_all(core); positioned=_tokens(core); tokens=[w for w,_,_ in positioned]; preds=_predicates(tokens)
    if len(frames)!=1 or len(preds)!=1: return False
    f=frames[0]; original=preds[0][1]
    if any('意志推量' in str(w.feature.cForm) for w in tokens): return False
    if f.ambiguous: return False
    if any(w.feature.pos1 == '副詞' for w in tokens): return False
    roles=[]; outputs=[]; covered=[]
    for role in ('agent','patient','recipient'):
        term=getattr(f,role)
        if term and not _WH.search(term):
            roles.append((role,canonical(term)))
            at = core.rfind(term, 0, positioned[preds[0][0]][1])
            if at >= 0: covered.append((at, at+len(term)))
    case_roles, case_issues = _case_roles(core, positioned, preds[0][0], existing=roles)
    if case_issues: return False
    for role, term, (at, end_at), _kind in case_roles:
        if any(k==role for k,_ in roles):return False
        roles.append((role,term)); covered.append((at,end_at))
    passive=bool(re.search(r'(?:れ|られ)(?:た|る|ます)',core))
    handled_wh=set()
    for m in re.finditer(r'(誰|だれ|何時|いつ|何|どこ)(によって|が|は|を|に|へ|で|から|まで|と)',core):
        handled_wh.add(m.start())
        covered.append((m.start(),m.end()))
        wh, particle = m[1], m[2]
        if particle == 'によって':
            role='agent'
        elif particle in ('が','は'):
            role='patient' if passive else 'agent'
        elif particle == 'を': role='patient'
        elif particle == 'に':
            if wh in ('いつ','何時'): role='time'
            elif wh in ('誰','だれ'): role='agent' if passive else 'recipient'
            elif wh == 'どこ':
                if original in _GOAL_PREDICATES: role='goal'
                elif original in _LOCATION_PREDICATES or original in ('いる','ある'): role='location'
                else: return False
            else: return False
        elif particle == 'へ': role='direction'
        elif particle == 'で':
            if wh == 'どこ': role='place'
            else: return False
        elif particle == 'から': role='time' if wh in ('いつ','何時') else 'source'
        elif particle == 'まで': role='limit'
        elif particle == 'と':
            if wh in ('誰','だれ'): role='companion'
            elif original in ('言う','話す','述べる'): role='quotation'
            else: return False
        if original in CONVERSE and particle != 'によって':
            role={'agent':'recipient','recipient':'agent','origin':'agent','source':'agent'}.get(role,role)
        if any(k==role for k,_ in roles): return False
        value=b.variable(); roles.append((role,value)); outputs.append((role,value))
    if any(m.start() not in handled_wh for m in _WH.finditer(core)):return False
    covered.extend(_predicate_coverage(positioned, preds[0][0], original))
    if _uncovered_nominals(positioned, covered): return False
    if relative:
        head=relative[2]
        if original in CONVERSE: role='recipient'
        elif not f.agent: role='agent'
        elif not f.patient: role='patient'
        else: return False
        if any(k==role for k,_ in roles): return False
        value=b.variable(); roles.append((role,value if head in ('人','もの','物') else Nominal(head,value)))
        outputs.append((role,value))
    # Noun objects in abbreviated relative questions are head restrictions (not for a cleft: the noun is the entity itself).
    if relative and not cleft:
        roles=[(k,Nominal(v,b.variable()) if isinstance(v,str) and k=='patient' else v) for k,v in roles]
    mod='normative' if re.search(r'てよい|てもよい|可能|できる|られる',core) else 'assert'
    if not outputs and re.search(r'(?:の|は|が|を|に)$',cleaned): return False   # a particle-final fragment is not a yes/no question
    if outputs:
        b.bind(Pattern(f.predicate,tuple(roles),'-' if f.negated else '+',mod,_event_time(tokens,preds[0][0])),span)
        b.outputs.extend((label,value,span,'') for label,value in outputs)
    else:
        value=b.variable('value'); b.bind(Pattern(f.predicate,tuple(roles),'*',mod,_event_time(tokens,preds[0][0])),span,value,'whether-negative' if f.negated else 'whether')
        b.outputs.append(('可否',value,span,''))
    return True


def read_request(text,budget=Budget()):
    from .stage_split import split
    raw=text; full=_span('question',raw)
    sr=split(raw); stages=tuple(Stage(s['condition'],s['head'],s['fragment'],tuple(s['span'])) for s in sr.get('stages',()))
    try:
        if not raw.strip(): raise ValueError('empty request')
        from .question import _is_generation, _ACTION
        if _is_generation(raw) or _ACTION.search(raw):
            raise ValueError('generation/action speech act is unsupported in semantic QA')
        if _COMPLEX.search(raw) or _MODAL_UNSUPPORTED.search(raw): raise ValueError('unsupported mandatory scope/quantifier/time')
        if COND.match(raw): raise ValueError('unsupported question antecedent')
        b=Builder(raw)
        cleaned=raw.strip()
        # Explicit arithmetic over named nominal paths. Operands are dependency
        # nodes, never values harvested from nearby sentences.
        am=re.fullmatch(r'(.+?)(?:の合計|の差)(?:は|を)(?:何|いくつ)([A-Za-z一-鿿]*)(?:ですか)?[？?。]*',cleaned)
        cmp=re.fullmatch(r'(.+?)は(.+?)より(大きい|小さい|多い|少ない)(?:ですか|か)[？?。]*',cleaned)
        filt=re.fullmatch(r'(.+?)が([+-]?[0-9]+(?:\.[0-9]+)?\s*[^\s0-9]+?)(以上|以下)の(?:もの|物)は[？?。]*',cleaned)
        from .semantic_measure import read_measure_request
        from .semantic_wh import read_role_list_question
        measure_plan=read_measure_request(raw,b,full) or read_role_list_question(raw,b,full)
        if measure_plan is not None:
            plan=measure_plan
        elif filt:
            q=quantity(filt[2])
            if q is None: raise ValueError('unread filter quantity')
            entity=b.variable(); value=b.variable('quantity')
            current=b.bind(Pattern('property',(('entity',entity),('attribute',attribute(filt[1])),('value',value))),full)
            ident='n'+str(len(b.nodes)); oid=b.obligation(ident,'filter',full,'inclusive quantity threshold')
            b.nodes.append(Operator(ident,'Filter',inputs=(current,),tests=(Test(value,'>=' if filt[3]=='以上' else '<=',q),),obligations=(oid,)))
            b.outputs.append(('対象',entity,full,'')); plan=b.project(ident)
        elif am or cmp:
            phrases=am[1].split('と') if am else [cmp[1],cmp[2]]
            if len(phrases)!=2: raise ValueError('arithmetic requires two explicit operands')
            terms=tuple(b.path(p,full,'quantity') for p in phrases)
            current=b.finish() if b.outputs else b.roots[0]
            for root in b.roots[1:]:
                ident='n'+str(len(b.nodes)); b.nodes.append(Operator(ident,'Join',inputs=(current,root))); current=ident
            ident='n'+str(len(b.nodes)); result=b.variable('quantity' if am else 'value')
            op='Sum' if am and 'の合計' in cleaned else ('Difference' if am else 'Compare')
            oid=b.obligation(ident,'operation',full,op)
            b.nodes.append(Operator(ident,op,inputs=(current,),terms=terms,target=result,unit=am[2] if am else '',
                                   relation=('>' if cmp[3] in ('大きい','多い') else '<') if cmp else '',
                                   absolute=op=='Difference',obligations=(oid,)))
            # absolute is a Difference field, and is false for Sum.
            b.outputs.append(('計算結果' if am else '比較結果',result,full,am[2] if am else '')); plan=b.project(ident)
        else:
            fragments=re.split(r'[、,]|と(?=[^。?？]*?の)',cleaned)
            for fragment in fragments:
                if not fragment.strip(): raise ValueError('empty conjunct')
                at=raw.find(fragment); span=_span('question',raw,at,at+len(fragment))
                if not _property_question(fragment,b,span) and not _event_question(fragment,b,span):
                    raise ValueError('unsupported request grammar')
            plan=b.project(b.finish())
        from .semantic_validate import request_shape
        request=Request(raw,(plan,),tuple(b.obligations),(full,),stages=stages,rules=('frame/edge/stage candidates','nominal-path','role-wh','relational-plan'))
        request_shape(request,plan,budget)
        return request
    except (ValueError, KeyError, IndexError) as exc:
        return Request(raw,(),(),(),(Unread(full,str(exc)),),stages,('typed unread',))
    except Limit as exc:     # a path/plan deeper than the budget is a typed unread request, never an exception out of ask
        return Request(raw,(),(),(),(Unread(full,'request plan exceeds budget: '+str(exc)),),stages,('typed unread',))
