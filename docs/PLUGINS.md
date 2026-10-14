# Plugins

Vera Harness has a small plugin registry, built on Python entry points (group `vera.plugins`). The built-in backends, gates, memory profiles and note kinds are registered the
same way (entry point `vera-builtin`), so a plugin of yours is not a second-class citizen. `vera plugins` lists what is installed.

プラグインは Python の entry points（グループ `vera.plugins`）で登録します。標準の部品も同じ仕組みで登録されます。`vera plugins` で一覧できます。

## What a plugin can and cannot do

The point of the harness is that the model's only output is a quote from the record. A plugin must not weaken that, so the kinds are shaped accordingly:

| kind | object | what it can do | what it cannot do |
|---|---|---|---|
| `backend` | factory `(model, base_url=None, *, client=None, api_key_env=None, tool_choice="required", temperature=None) -> Backend` | add a model driver (see `verantyx/harness/backends/base.py`: one request in, one Anthropic-shaped turn out) | bypass the driver: whatever it returns still goes through the same loom server and ledger; free text is dropped |
| `gate` | a *filter* `(question, answer, sources) -> None \| code` | refuse an answer the loom's gate already passed (the answer becomes 「分かりません」, reason `plugin_refused`, your code) | let through anything the loom's gate refused. A filter that raises, or returns something odd, refuses (fail closed) |
| `memory_profile` | `MemoryProfile(versions, answer_version, profile)` | select which of the loom's *own* versioned memory bundles `vera mem` runs | add a version the loom does not implement |
| `note_kind` | `NoteKind(annotate)` with `annotate(sentences) -> [{"sid", "text"}]` | read the committed memory sentences and show notes beside an answer | change an answer. Its notes are shown, never used |

The built-in gates (`evidence.v1` … `evidence.v6`) are `LoomGate` objects: choosing one is `--evidence v6` (the default), not a filter. A new *rule* inside the loom's gate
is research work on the loom itself, with a new held-out set, not a plugin.

## A minimal plugin

`examples/plugins/vera_example_plugin/` is a complete package: one gate filter (`no-contact-info`: withholds a phone number or an e-mail address) and one note kind (`undecided`).

```python
# vera_example_plugin.py
from verantyx.harness.plugins import NoteKind, Plugin

def no_contact_info(question, answer, sources):
    return "phone" if looks_like_a_phone_number(answer) else None      # None = let it through

def plugins():
    return [Plugin("gate", "no-contact-info", "0.1.0", no_contact_info, "withholds phone numbers"),
            Plugin("note_kind", "undecided", "0.1.0", NoteKind(undecided_notes), "points at open items")]
```

```toml
# pyproject.toml
[project.entry-points."vera.plugins"]
vera-example = "vera_example_plugin:plugins"
```

```
pip install ./examples/plugins/vera_example_plugin
vera plugins
vera ask --docs ./manuals --gate-filter no-contact-info "広報の電話番号は何ですか"
vera mem --store ./memory --note-kind undecided --ask "広報の担当は誰ですか"
```

The entry point may be a `Plugin`, an iterable of `Plugin`, or a callable returning them. Names are lower-case (`[a-z0-9][a-z0-9._-]*`), versions are short strings.
A plugin cannot replace another (a name that is taken is refused, so nothing can shadow `evidence.v6`). An import error or a malformed plugin is listed by
`vera plugins` on stderr and does not stop `vera`; asking for it by name fails with `unknown_plugin`.

## The ledger records which plugins ran

The first `harness_meta` row of a run (inside the hash chain) carries `plugins`: `[{"kind","name","version"}, ...]`, canonical JSON, sorted. It lists the backend, the evidence gate,
the memory profile, and every filter and note kind you selected. Memory session and answer runs carry it too.

`vera verify` and `vera replay` compare that list with what is installed:

* every declared plugin installed at the declared version: the normal chain and replay checks decide;
* a declared plugin that is not installed (`unknown_plugin:gate/no-contact-info`) or installed at another version (`plugin_version:gate/no-contact-info:0.1.0!=0.2.0`):
  `vera verify` reports `REPLAY_INPUTS_MISMATCH` with `replay.status` = **INPUTS**, `vera replay` reports `INPUTS` (exit 2). It never passes silently: the answer you were shown depended on code you
  do not have;
* a ledger that declares nothing (made before plugins existed) is not a mismatch;
* a tampered ledger is `TAMPERED` first: the chain is checked before anything else.

Bump your plugin's version whenever its behaviour changes; that is what makes an old run say INPUTS instead of looking reproduced.

## Tests

`tests/harness/test_plugins.py` and `tests/harness/test_example_plugin.py` show how to test a plugin offline: build a registry with `plugins.discover([fake_entry_point])`, install it with
`plugins.set_registry(...)`, and drive `runner.ask` / `runner.mem_ask` with a fake client.
