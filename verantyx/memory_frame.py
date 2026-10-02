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


class WriteRejected(Exception):
    def __init__(self, reason: str, hint: str = ''):
        super().__init__(reason); self.reason, self.hint = reason, hint


# ------------------------------------------------------------------ witnesses
def _sha(path: str) -> Optional[str]:
    try: return hashlib.sha256(Path(path).expanduser().read_bytes()).hexdigest()
    except OSError: return None


def check_witness(w: Optional[dict]) -> str:
    """FRESH / STALE / UNVERIFIABLE / TESTIMONY for a witness dict."""
    if not w: return 'UNVERIFIABLE'
    kind = w.get('kind')
    if kind == 'testimony': return 'TESTIMONY'
    if kind == 'file_sha256':
        now = _sha(w['path']); return 'STALE' if now is None else ('FRESH' if now == w['sha256'] else 'STALE')
    if kind == 'text_in_file':
        try: return 'FRESH' if w['needle'] in Path(w['path']).expanduser().read_text() else 'STALE'
        except OSError: return 'STALE'
    if kind == 'git_commit':
        r = subprocess.run(['git', '-C', str(Path(w['repo']).expanduser()), 'cat-file', '-e', w['commit'] + '^{commit}'],
                           capture_output=True)
        return 'FRESH' if r.returncode == 0 else 'STALE'
    return 'UNVERIFIABLE'


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
    m = re.search(r'"choice"\s*:\s*(null|-?\d+)', reply or '')
    if not m: return False
    if m[1] == 'null': return None
    i = int(m[1])
    return i if 0 <= i < n else False


class Resolver:
    """Which canonical expression is this out-of-frame word closest to? Two independent closed asks must agree."""
    def __init__(self, asker: Asker, seed: int = 7):
        self.asker, self.rng = asker, random.Random(seed)

    def _prompt(self, word, context, options, variant):
        lines = '\n'.join(f'{i}: {o}' for i, o in enumerate(options))
        head = ('次の語は、下の候補のどれに意味が最も近いですか。' if variant == 0 else
                '候補の中から、次の語を最も自然に言い換えられるものを1つだけ選んでください。どれも合わなければ null。')
        return (f'{head}\n語: 「{word}」\n使われた場面: {context}\n候補:\n{lines}\n'
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
    def _apply(self, ev):
        if ev['op'] == 'write': self.records[ev['record']['id']] = ev['record']
        elif ev['op'] == 'supersede': self.superseded[ev['id']] = ev['by']
        elif ev['op'] == 'alias': self.aliases[(ev['scope'], ev['word'])] = ev
        self._view = None

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
        return f"{slots[names[0]]}の{attr}は{slots[names[1]]}である。"

    @staticmethod
    def askable(sentence, slots, kind):
        """Round trip: the semantic reader must read the sentence into one supported property clause with these values."""
        view = document_view({'r': sentence})
        for c in view.clauses:
            if c.unsupported or c.predicate != 'property': continue
            roles = {r.name: r.term for r in c.roles}
            names, attr = KINDS[kind]
            value = slots[names[-1]]
            if str(roles.get('value')) == value or (hasattr(roles.get('value'), 'amount') and str(roles['value']) == value): return True
        return False

    def write(self, kind, author, witness=None, supersedes=None, **slots):
        kind = self.normalize_kind(kind)
        names, attr = KINDS[kind]
        if set(slots) != set(names):
            raise WriteRejected(f'{kind} の項目は {list(names)} です（{sorted(slots)} が渡されました）')
        slots = {k: str(v).strip() for k, v in slots.items()}
        for k, v in slots.items():
            if not v: raise WriteRejected(f'項目 {k} が空です')
            if _BAD.search(v): raise WriteRejected(f'項目 {k} に文の区切りや括弧が含まれています', '短い名詞句にしてください')
        normalized = {}
        for k in names[:-1]:        # the entity / attribute slots are bare compound nouns
            n = normalize_np(slots[k])
            if n != slots[k]: normalized[k] = slots[k]; slots[k] = n
            if not n: raise WriteRejected(f'項目 {k} が助詞だけです')
        if kind == 'TASK':
            slots['state'] = self._alias('TASK.state', slots['state'], list(STATES), f'タスク「{slots["subject"]}」の状態')
        if kind in NEEDS_WITNESS and not witness:
            raise WriteRejected(f'{kind} には確かめ方（witness）が必要です', "witness={'kind': 'file_sha256'|'git_commit'|'text_in_file'|'testimony', ...}")
        if witness and witness.get('kind') not in ('file_sha256', 'git_commit', 'text_in_file', 'testimony'):
            raise WriteRejected('witness の種類が不明です')
        sentence = self.sentence(kind, slots)
        if not self.askable(sentence, slots, kind):
            raise WriteRejected('この記録は Vera が引ける文として読めません',
                                f'値は名詞句にしてください（動詞で終わる節は引けません）: {sentence}')
        rid = hashlib.sha256(json.dumps([kind, slots, author, self.now()], ensure_ascii=False).encode()).hexdigest()[:12]
        record = {'id': rid, 'kind': kind, 'slots': slots, 'author': author, 'ts': self.now(), 'witness': witness,
                  'sentence': sentence, 'supersedes': supersedes, 'normalized': normalized}
        self._append({'op': 'write', 'record': record})
        if supersedes:
            if supersedes not in self.records: raise WriteRejected(f'置き換え対象 {supersedes} がありません')
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
        attr = KINDS[kind][1] or normalize_np(attribute)
        return self.ask(f'{normalize_np(subject)}の{attr}は？', require_fresh)

    def ask(self, question, require_fresh=True):
        from .one import Vera
        docs = {f"rec:{r['id']}": r['sentence'] for r in self.active(require_fresh)}
        if not docs: return {'verdict': 'UNKNOWN_NO_EVIDENCE', 'values': [], 'records': []}
        v = Vera.from_texts(docs, mode='semantic')
        try: a = v.ask(question)
        finally: v.close()
        ids = [s['source'].split(':', 1)[1] for s in a.get('sources', [])]
        return {'verdict': a['verdict'], 'values': a.get('values', []), 'records': ids, 'reason': a.get('reason')}
