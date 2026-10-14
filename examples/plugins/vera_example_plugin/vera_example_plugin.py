"""A minimal Vera Harness plugin: one gate filter and one note kind.

    pip install ./examples/plugins/vera_example_plugin      (into the same environment as vera-harness)
    vera plugins                                            (both are listed)
    vera ask --docs ./manuals --gate-filter no-contact-info "広報の連絡先は何ですか"
    vera mem --store ./memory --note-kind undecided --ask "…"

The gate filter runs on an answer the loom's gate has ALREADY passed (a verbatim quote of the record) and can only refuse it: here, an answer that looks like a phone number or an
e-mail address is withheld (「分かりません」, reason plugin_refused, code phone / email).  The note kind reads the remembered sentences and points at the ones that say something is
still open; its notes are shown beside an answer and never change it.  Both are recorded, with their versions, in the ledger of every run that uses them.
"""
import re

from verantyx.harness.plugins import NoteKind, Plugin

VERSION = "0.1.0"
_PHONE = re.compile(r"\d{2,4}[-ー－]\d{2,4}[-ー－]\d{3,4}|\b0\d{9,10}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_OPEN = ("未定", "検討中", "要確認", "調整中")


def no_contact_info(question, answer, sources):
    """(question, answer, sources) -> None to let the answer through, or a short code to refuse it."""
    if _PHONE.search(answer):
        return "phone"
    if _EMAIL.search(answer):
        return "email"
    return None


def undecided(sentences):
    """sentences: the committed memory rows ({"sent": ..., "turn": ..., ...}) -> [{"sid", "text"}]."""
    return [{"sid": i, "text": "まだ決まっていない: " + r["sent"]} for i, r in enumerate(sentences) if any(w in r.get("sent", "") for w in _OPEN)]


def plugins():
    """The entry point (group `vera.plugins`) returns the plugins this package provides."""
    return [
        Plugin("gate", "no-contact-info", VERSION, no_contact_info, "withholds an answer that looks like a phone number or an e-mail address"),
        Plugin("note_kind", "undecided", VERSION, NoteKind(undecided), "points at remembered sentences that say something is still open"),
    ]
