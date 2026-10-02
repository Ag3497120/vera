"""Typed project memory: write-time typing, witnesses, askability, and closed-choice term resolution.

Why: prose notes are not askable (181 notes of a real session: 25% of their clauses were supported, 6/6 questions
abstained). A record is accepted only if (1) its kind and slots are complete, (2) it carries a witness that can be
re-checked (or is explicitly testimony), and (3) its canonical sentence round-trips through the semantic reader, i.e.
Vera can actually answer a question from it. Nothing is deleted; a record is superseded by another one.

Out-of-frame words are never guessed and never invented by a model. `Resolver` shows an LLM the CLOSED list of
canonical expressions and asks which one the word is closest to (or none). The answer must be an index in range.
Two independent asks (different order and wording) must name the same expression before an alias is adopted; the
adoption is stored with its provenance as testimony, not as a fact. The model cannot add a canonical term.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Callable, Optional

from .semantic_reader import document_view

KINDS = {
    #  kind        slots (in order)               attribute used in the canonical sentence
    'FACT':      (('subject', 'attribute', 'value'), None),
    'DECISION':  (('subject', 'choice'), '決定'),
    'INVARIANT': (('subject', 'rule'), '規則'),
    'TASK':      (('subject', 'state'), '状態'),
    'LESSON':    (('situation', 'fix'), '対処'),
    'QUESTION':  (('subject', 'question'), '未解決'),
}
KIND_ALIASES = {'FACT': ('事実', '測定', '結果'), 'DECISION': ('決定', '方針', '判断', '決め'),
                'INVARIANT': ('不変条件', '守る線', '制約', '原則'), 'TASK': ('作業', 'タスク', '進捗'),
                'LESSON': ('教訓', '失敗', '注意'), 'QUESTION': ('質問', '未解決', '要確認')}
STATES = ('未着手', '進行中', '完了', '停止', '保留')
NEEDS_WITNESS = ('FACT', 'INVARIANT')
_BAD = re.compile(r'[。！？!?\n\r「」『』]')
_NO_NOUN_PARTICLE = re.compile(r'[はがのをにでと]')


def normalize_np(text: str) -> str:
    """A bare compound noun: case particles and the genitive の between nouns are dropped (未読の上限 -> 未読上限).

    The semantic reader splits `AのBはC` at the last の and a question `AのBは？` at the first one, so a stored
    noun phrase must not contain one. The original form is kept in the record (`normalized`).
    """
    return _NO_NOUN_PARTICLE.sub('', text.strip())


def _normalize_np_in_frame(text: str) -> str:
    """Normalize case particles while keeping a script-internal lexical の intact."""
    chars = list(text.strip())
    lexical_no = set()
    for i in range(1, len(chars) - 1):
        if chars[i] != 'の': continue
        left, right = unicodedata.name(chars[i - 1], ''), unicodedata.name(chars[i + 1], '')
        if ('HIRAGANA' in left and 'HIRAGANA' in right) or ('KATAKANA' in left and 'KATAKANA' in right):
            lexical_no.add(i)
    return ''.join(char for i, char in enumerate(chars) if char not in 'はがのをにでと' or i in lexical_no)


class WriteRejected(Exception):
    def __init__(self, reason: str, hint: str = ''):
        super().__init__(reason); self.reason, self.hint = reason, hint


# ------------------------------------------------------------------ witnesses
def _sha(path: str) -> Optional[str]:
    try: return hashlib.sha256(Path(path).expanduser().read_bytes()).hexdigest()
    except (OSError, TypeError, ValueError): return None


def _file_hash_shape_ok(w: dict) -> bool:
    """The one rule for a well-formed file-hash witness: a non-blank path and a 64-hex-digit sha256.

    `check_witness` (UNVERIFIABLE vs. readable) and `Memory._witness_supports` (shape only: the content was
    already read by the freshness check) both use it, so the rule is written once.
    """
    path, expected = w.get('path'), w.get('sha256')
    return (isinstance(path, (str, Path)) and bool(str(path).strip()) and
            isinstance(expected, str) and re.fullmatch(r'[0-9a-fA-F]{64}', expected) is not None)


def check_witness(w: Optional[dict]) -> str:
    """FRESH / STALE / UNVERIFIABLE / TESTIMONY for a witness dict."""
    if not isinstance(w, dict): return 'UNVERIFIABLE'
    kind = w.get('kind')
    if kind == 'testimony': return 'TESTIMONY'
    if kind in ('file_sha256', 'file_hash'):
        if not _file_hash_shape_ok(w): return 'UNVERIFIABLE'
        now = _sha(w['path']); return 'STALE' if now is None else ('FRESH' if now == w['sha256'].lower() else 'STALE')
    if kind == 'text_in_file':
        path, needle = w.get('path'), w.get('needle')
        if (not isinstance(path, (str, Path)) or not str(path).strip() or
                not isinstance(needle, str) or not needle.strip()): return 'UNVERIFIABLE'
        try: return 'FRESH' if needle in Path(path).expanduser().read_text(encoding='utf-8') else 'STALE'
        except (OSError, TypeError, ValueError, UnicodeError): return 'STALE'
    if kind == 'git_commit':
        repo, commit = w.get('repo'), w.get('commit')
        if (not isinstance(repo, (str, Path)) or not str(repo).strip() or
                not isinstance(commit, str) or not commit.strip()): return 'UNVERIFIABLE'
        try:
            r = subprocess.run(['git', '-C', str(Path(repo).expanduser()), 'cat-file', '-e', commit + '^{commit}'],
                               capture_output=True)
            return 'FRESH' if r.returncode == 0 else 'STALE'
        except (OSError, TypeError, ValueError): return 'UNVERIFIABLE'
    if kind in ('command_result', 'command_exit'):
        command, result = w.get('command'), w.get('exit_code', w.get('result'))
        expected = w.get('expected_exit', 0)
        command_ok = (isinstance(command, str) and bool(command.strip()) or
                      isinstance(command, (list, tuple)) and bool(command) and
                      all(isinstance(part, str) and part for part in command))
        if (not command_ok or type(result) is not int or type(expected) is not int):
            return 'UNVERIFIABLE'
        return 'FRESH' if result == expected else 'STALE'
    return 'UNVERIFIABLE'


def witness_class(witness: Optional[dict]) -> str:
    """Return the stable provenance class attached to an answer's supporting record."""
    if not isinstance(witness, dict): return 'constructed'
    kind = witness.get('kind')
    if kind in ('file_sha256', 'file_hash'): return 'file_hash'
    if kind == 'text_in_file': return 'text_in_file'
    if kind == 'git_commit': return 'git_commit'
    if kind in ('command_result', 'command_exit'): return 'command_result'
    if kind == 'testimony': return 'testimony'
    # Unknown or explicitly constructed sources are never promoted to evidence.
    return 'constructed'


def _claims_constructed_source(witness: Optional[dict]) -> bool:
    """Recognize explicit generated-output markers so they cannot be relabeled as evidence."""
    if not isinstance(witness, dict): return False
    if witness.get('kind') in ('constructed', 'generated'): return True
    if witness.get('constructed') is True or witness.get('generated') is True: return True
    for key in ('source', 'origin', 'provenance', 'output_kind', 'source_kind'):
        value = witness.get(key)
        if isinstance(value, str) and re.search(r'\b(?:constructed|generated)\b|生成', value.casefold()):
            return True
    if witness.get('generated_by') or witness.get('constructed_by'):
        return True
    return False


# ------------------------------------------------------------------ closed-choice resolution
Asker = Callable[[str], str]


class CodexAsker:
    """Closed-choice question to a model through the Codex CLI (read-only, no tools, standard tier)."""
    def __init__(self, model='gpt-6-luna', effort='low',
                 codex='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex', timeout=240):
        self.model, self.effort, self.codex, self.timeout = model, effort, codex, timeout

    def __call__(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'last.txt'
            subprocess.run([self.codex, 'exec', '--ignore-user-config', '-m', self.model, '-c',
                            f'model_reasoning_effort="{self.effort}"', '-c', 'service_tier="default"',
                            '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-C', tmp,
                            '-o', str(out), prompt], capture_output=True, text=True, timeout=self.timeout,
                           stdin=subprocess.DEVNULL)
            return out.read_text() if out.exists() else ''


def parse_choice(reply: str, n: int):
    """Index in [0, n) or None for 'none of them'; anything else is invalid (returns False)."""
    def unique_object(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj: raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj

    try: data = json.loads(reply, object_pairs_hook=unique_object)
    except (TypeError, ValueError): return False
    if not isinstance(data, dict) or set(data) != {'choice'}: return False
    choice = data['choice']
    if choice is None: return None
    if type(choice) is not int: return False
    return choice if 0 <= choice < n else False


class Resolver:
    """Which canonical expression is this out-of-frame word closest to? Two independent closed asks must agree."""
    def __init__(self, asker: Asker, seed: int = 7):
        self.asker, self.rng = asker, random.Random(seed)

    def _prompt(self, word, context, options, variant):
        def escape(value):
            out = []
            for char in str(value):
                category = unicodedata.category(char)
                if char == '\\': out.append('\\\\')
                elif char in '「」' or category in ('Cc', 'Cf', 'Zl', 'Zp'):
                    out.append(f'\\u{ord(char):04x}')
                else: out.append(char)
            return ''.join(out)

        safe_options = [escape(o) for o in options]
        lines = '\n'.join(f'{i}: {o}' for i, o in enumerate(safe_options))
        head = ('次の語は、下の候補のどれに意味が最も近いですか。' if variant == 0 else
                '候補の中から、次の語を最も自然に言い換えられるものを1つだけ選んでください。どれも合わなければ null。')
        shown_word, shown_context = escape(word), escape(context)
        return (f'{head}\n語: 「{shown_word}」\n使われた場面: {shown_context}\n候補:\n{lines}\n'
                f'答えは次のJSONだけを出力してください（説明は不要）: {{"choice": 番号 または null}}\n'
                f'候補以外を選んだり、新しい表現を作ったりしてはいけません。')

    def resolve(self, word, options, context=''):
        """-> dict(status ADOPT|NONE|UNRESOLVED, choice, asks). The caller stores it as testimony."""
        options = list(options); asks = []
        for variant in (0, 1):
            order = list(range(len(options)))
            if variant == 1: self.rng.shuffle(order)
            shown = [options[i] for i in order]
            reply = self.asker(self._prompt(word, context, shown, variant))
            picked = parse_choice(reply, len(shown))
            real = False if picked is False else (None if picked is None else order[picked])
            asks.append({'variant': variant, 'order': order, 'reply': (reply or '')[:200], 'picked': real})
        a, b = asks[0]['picked'], asks[1]['picked']
        if a is False or b is False: return {'status': 'UNRESOLVED', 'why': 'invalid answer', 'choice': None, 'asks': asks}
        if a is None and b is None: return {'status': 'NONE', 'choice': None, 'asks': asks}
        if a == b: return {'status': 'ADOPT', 'choice': options[a], 'asks': asks}
        return {'status': 'UNRESOLVED', 'why': 'the two asks disagree', 'choice': None, 'asks': asks}


# ------------------------------------------------------------------ the store
class Memory:
    """Append-only typed memory. `path` is a JSONL event log (write / supersede / alias)."""

    def __init__(self, path: str, asker: Optional[Asker] = None, now: Callable[[], str] = lambda: time.strftime('%Y-%m-%dT%H:%M:%S')):
        self.path = Path(path); self.now = now
        self.resolver = Resolver(asker) if asker else None
        self.records: dict[str, dict] = {}; self.superseded: dict[str, str] = {}; self.aliases: dict[tuple, dict] = {}
        self._view = None
        if self.path.exists():
            for line in self.path.read_text().splitlines():
                if line.strip(): self._apply(json.loads(line))

    # ---- log
    def _supersede_state(self) -> tuple[list[dict], dict[str, list[dict]]]:
        """The supersede accounting state: (every supersede event read with how it was settled, events waiting
        for their replacement record by record id). Created here on first use, not in __init__, so a Memory that
        was built without __init__ (a view with only `records`/`superseded`, or a subclass such as
        project_frame._ExchangeMemory) works in write/_apply and supersede_accounting."""
        d = self.__dict__
        return d.setdefault('_supersede_log', []), d.setdefault('_waiting', {})

    def _apply(self, ev):
        log, waiting = self._supersede_state()
        if ev['op'] == 'write':
            self.records[ev['record']['id']] = ev['record']
            for entry in waiting.pop(ev['record']['id'], ()): self._settle_supersede(entry)
        elif ev['op'] in ('supersede', 'pending_supersede'):
            # A supersede event is operative only when its replacement record carries the matching `supersedes`
            # pointer (the same rule memory_merge uses). The event may come before the record: it then waits.
            entry = {'id': ev['id'], 'by': ev['by'], 'op': ev['op'], 'state': 'waiting_for_record',
                     'reason': 'REPLACEMENT_NOT_PRESENT'}
            log.append(entry)
            if ev['by'] in self.records: self._settle_supersede(entry)
            else: waiting.setdefault(ev['by'], []).append(entry)
        elif ev['op'] == 'alias': self.aliases[(ev['scope'], ev['word'])] = ev
        self._view = None

    def _settle_supersede(self, entry):
        """The replacement record is present: apply the event only if its pointer names the target."""
        pointer = self.records[entry['by']].get('supersedes')
        ids = pointer if isinstance(pointer, (list, tuple)) else (pointer,)
        if pointer is None or pointer == '' or (isinstance(pointer, (list, tuple)) and not pointer):
            entry['state'], entry['reason'] = 'nonoperative', 'REPLACEMENT_POINTER_ABSENT'
        elif any(not isinstance(i, str) or not i for i in ids):
            entry['state'], entry['reason'] = 'nonoperative', 'REPLACEMENT_POINTER_INVALID'
        elif entry['id'] in ids:
            self.superseded[entry['id']] = entry['by']
            entry['state'], entry['reason'] = 'applied', 'REPLACEMENT_POINTER_MATCHES'
        else:
            entry['state'], entry['reason'] = 'nonoperative', 'REPLACEMENT_POINTER_MISMATCH'

    def supersede_accounting(self) -> dict:
        """How many supersede events were applied, kept without effect, or are waiting for their record.

        Nothing is dropped silently: an event whose replacement record does not point back at its target stays
        in the log, is not applied, and is listed here with a typed reason. Works on a Memory that only has
        `records` and `superseded` (nothing logged: all counts 0).
        """
        log = self._supersede_state()[0]
        view = lambda state: [{k: e[k] for k in ('id', 'by', 'op', 'reason')} for e in log if e['state'] == state]
        nonoperative, waiting = view('nonoperative'), view('waiting_for_record')
        applied = sum(e['state'] == 'applied' for e in log)
        return {'applied': applied, 'nonoperative': nonoperative, 'waiting_for_record': waiting,
                'counts': {'applied': applied, 'nonoperative': len(nonoperative),
                           'waiting_for_record': len(waiting), 'events': len(log)}}

    def _append(self, ev):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as f: f.write(json.dumps(ev, ensure_ascii=False) + '\n')
        self._apply(ev)

    # ---- term resolution (closed choice)
    def _alias(self, scope, word, options, context):
        if word in options: return word
        hit = self.aliases.get((scope, word))
        if hit: return hit['choice']
        if self.resolver is None: raise WriteRejected(f'「{word}」は枠にない語です（{scope}）', '候補: ' + ' / '.join(options))
        res = self.resolver.resolve(word, options, context)
        self._append({'op': 'alias', 'scope': scope, 'word': word, 'choice': res['choice'], 'status': res['status'],
                      'asks': res['asks'], 'by': 'llm-closed-choice', 'support': 'testimony', 'ts': self.now()})
        if res['status'] != 'ADOPT':
            raise WriteRejected(f'「{word}」を枠の語に対応づけられません（{res["status"]}）', '候補: ' + ' / '.join(options))
        return res['choice']

    def normalize_kind(self, kind):
        if kind in KINDS: return kind
        flat = {a: k for k, al in KIND_ALIASES.items() for a in al}
        if kind in flat: return flat[kind]
        options = list(KINDS)
        return self._alias('kind', kind, options, '記録の種類')

    # ---- write
    @staticmethod
    def sentence(kind, slots):
        names, attr = KINDS[kind]
        if kind == 'FACT': return f"{slots['subject']}の{slots['attribute']}は{slots['value']}である。"
        return f"{slots[names[0]]}の{_normalize_np_in_frame(attr)}は{slots[names[1]]}である。"

    @staticmethod
    def askable(sentence, slots, kind):
        """Round trip: the reader must recover the complete typed case frame."""
        view = document_view({'r': sentence})
        names, attr = KINDS[kind]
        expected = {
            'entity': slots[names[0]],
            'attribute': slots['attribute'] if kind == 'FACT' else _normalize_np_in_frame(attr),
            'value': slots[names[-1]],
        }
        for c in view.clauses:
            if c.unsupported or c.predicate != 'property' or c.polarity != '+' or c.modality != 'assert': continue
            if c.conditions or c.exceptions or c.exception_of: continue
            roles = {r.name: r.term for r in c.roles}
            if all(str(roles.get(name)) == value for name, value in expected.items()): return True
        return False

    def write(self, kind, author, witness=None, supersedes=None, **slots):
        kind = self.normalize_kind(kind)
        names, attr = KINDS[kind]
        if set(slots) != set(names):
            raise WriteRejected(f'{kind} の項目は {list(names)} です（{sorted(slots)} が渡されました）')
        if supersedes is not None:
            if not isinstance(supersedes, str) or not supersedes or supersedes not in self.records:
                raise WriteRejected(f'置き換え対象 {supersedes} がありません')
            if supersedes in self.superseded:
                raise WriteRejected(f'置き換え対象 {supersedes} は既に置き換えられています')
        if witness is not None and not isinstance(witness, dict):
            raise WriteRejected('witness の形式が不明です')
        slots = {k: str(v).strip() for k, v in slots.items()}
        for k, v in slots.items():
            if not v: raise WriteRejected(f'項目 {k} が空です')
            if _BAD.search(v): raise WriteRejected(f'項目 {k} に文の区切りや括弧が含まれています', '短い名詞句にしてください')
        normalized = {}
        for k in names[:-1]:        # the entity / attribute slots are bare compound nouns
            n = _normalize_np_in_frame(slots[k])
            if n != slots[k]: normalized[k] = slots[k]; slots[k] = n
            if not n: raise WriteRejected(f'項目 {k} が助詞だけです')
        if kind == 'TASK':
            slots['state'] = self._alias('TASK.state', slots['state'], list(STATES), f'タスク「{slots["subject"]}」の状態')
        if kind in NEEDS_WITNESS and not witness:
            raise WriteRejected(f'{kind} には確かめ方（witness）が必要です',
                                "witness={'kind': 'file_hash'|'text_in_file'|'git_commit'|'command_result'|'testimony'|'constructed', ...}")
        if witness and witness.get('kind') not in ('file_sha256', 'file_hash', 'git_commit', 'text_in_file',
                                                    'command_result', 'command_exit', 'testimony', 'constructed'):
            raise WriteRejected('witness の種類が不明です')
        if kind in ('FACT', 'DECISION', 'INVARIANT') and _claims_constructed_source(witness) and witness_class(witness) != 'constructed':
            raise WriteRejected(f'{kind} の生成物は constructed witness として記録してください')
        sentence = self.sentence(kind, slots)
        if not self.askable(sentence, slots, kind):
            raise WriteRejected('この記録は Vera が引ける文として読めません',
                                f'値は名詞句にしてください（動詞で終わる節は引けません）: {sentence}')
        ts = self.now()
        identity = json.dumps([kind, slots, author, ts, witness, supersedes], ensure_ascii=False, sort_keys=True)
        rid = hashlib.sha256(identity.encode()).hexdigest()[:12]
        record = {'id': rid, 'kind': kind, 'slots': slots, 'author': author, 'ts': ts, 'witness': witness,
                  'sentence': sentence, 'supersedes': supersedes, 'normalized': normalized}
        if rid in self.records:
            return self.records[rid]
        self._append({'op': 'write', 'record': record})
        if supersedes:
            self._append({'op': 'supersede', 'id': supersedes, 'by': rid, 'ts': self.now()})
        return record

    # ---- read
    def active(self, require_fresh=False):
        out = []
        for rid, r in self.records.items():
            if rid in self.superseded: continue
            if require_fresh and check_witness(r.get('witness')) == 'STALE': continue
            out.append(r)
        return out

    def verify(self):
        return {rid: check_witness(r.get('witness')) for rid, r in self.records.items() if rid not in self.superseded}

    def ask_about(self, subject, attribute=None, kind='FACT', require_fresh=True):
        """Ask for a slot with the same noun normalization as the writer: `ask_about('ルーター', '未読の上限')`."""
        attr = KINDS[kind][1] or _normalize_np_in_frame(attribute)
        return self.ask(f'{_normalize_np_in_frame(subject)}の{attr}は？', require_fresh)

    @staticmethod
    def _witness_supports(record, status=None):
        """Does the witness support this record's claim?

        `status` is the result of ONE `check_witness` call the caller already made for this very question. When it
        is given the evidence is not read a second time (a status and a support decision from two separate reads
        could disagree); when it is None the check is made here, once, as before.
        """
        witness = record.get('witness')
        if witness is None: return True
        if not isinstance(witness, dict): return False
        kind = witness.get('kind')
        if kind == 'testimony': return True
        if kind == 'constructed': return True
        if kind in ('file_sha256', 'file_hash'):
            # The freshness read (when there is one) already hashed the file; here only the shape matters.
            # Same rule as check_witness: a well-formed witness is never UNVERIFIABLE.
            return _file_hash_shape_ok(witness)
        if kind in ('git_commit', 'command_result', 'command_exit'):
            # git_commit is not shape-only: UNVERIFIABLE also means git could not start.
            if status is None: status = check_witness(witness)
            return status != 'UNVERIFIABLE'
        if kind != 'text_in_file': return False
        try:
            if status == 'FRESH':
                # check_witness read the file and found the (non-blank) needle in it.
                evidence = witness['needle']
            else:
                source = Path(witness['path']).expanduser().read_text(encoding='utf-8')
                evidence = witness['needle']
                if not isinstance(evidence, str) or not evidence or evidence not in source: return False
            names, attr = KINDS[record['kind']]
            expected = {
                'entity': record['slots'][names[0]],
                'attribute': record['slots']['attribute'] if record['kind'] == 'FACT' else _normalize_np_in_frame(attr),
                'value': record['slots'][names[-1]],
            }
            for clause in document_view({'witness': evidence}).clauses:
                if clause.unsupported or clause.predicate != 'property' or clause.polarity != '+' or clause.modality != 'assert':
                    continue
                if clause.conditions or clause.exceptions or clause.exception_of: continue
                roles = {role.name: role.term for role in clause.roles}
                if all(str(roles.get(name)) == value for name, value in expected.items()): return True
            return False
        except (KeyError, OSError, TypeError, ValueError, UnicodeError):
            return False

    def ask(self, question, require_fresh=True, evidence_only=False):
        from .one import Vera
        # One check_witness call per record per question: its status both excludes STALE records and tells
        # _witness_supports what was already read. active(False) + the check below is active(True) with the
        # status kept instead of thrown away.
        candidates = []
        for r in self.active(False):
            status = check_witness(r.get('witness')) if require_fresh else None
            if status == 'STALE': continue
            if self._witness_supports(r, status=status) and not (
                    evidence_only and witness_class(r.get('witness')) in ('testimony', 'constructed')):
                candidates.append(r)
        docs = {f"rec:{r['id']}": r['sentence'] for r in candidates}
        if not docs:
            return {'verdict': 'UNKNOWN_NO_EVIDENCE', 'values': [], 'records': [], 'witness_classes': {}}
        v = Vera.from_texts(docs, mode='semantic')
        try:
            a = v.ask(question)
            numeric = re.sub(r'はいくつですか([?？])\s*$', r'は何ですか\1', question)
            if numeric != question and a.get('verdict') != 'ANSWER': a = v.ask(numeric)
        finally: v.close()
        ids = [s['source'].split(':', 1)[1] for s in a.get('sources', [])]
        by_id = {r['id']: r for r in candidates}
        classes = {rid: witness_class(by_id[rid].get('witness')) for rid in ids if rid in by_id}
        return {'verdict': a['verdict'], 'values': a.get('values', []), 'records': ids,
                'witness_classes': classes, 'reason': a.get('reason')}
