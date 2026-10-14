"""The example plugin of examples/plugins/ works through the registry exactly as docs/PLUGINS.md says."""
import importlib.util
import os

import pytest

from verantyx.harness import plugins as pl
from verantyx.harness import runner as rn
from verantyx.harness.backends import make_backend

from fakes import FakeOpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def example():
    spec = importlib.util.spec_from_file_location("vera_example_plugin", os.path.join(ROOT, "examples", "plugins", "vera_example_plugin", "vera_example_plugin.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class EP:
        name, value = "vera-example", "vera_example_plugin:plugins"
        load = staticmethod(lambda: mod.plugins)
    pl.set_registry(pl.discover([EP]))
    yield mod
    pl.set_registry(None)


def test_the_filter_refuses_contact_details_only(example):
    f = example.no_contact_info
    assert f("q", "03-1234-5678", []) == "phone" and f("q", "0312345678", []) == "phone" and f("q", "2024年", []) is None and f("q", "a.b@example.com", []) == "email" and f("q", "山本", []) is None


def test_the_filter_withholds_a_phone_number_from_a_memory_answer(example, tmp_path):
    store = str(tmp_path / "store")
    story = [[("tool", "write", {"text": "広報の電話番号は0312345678"}), ("tool", "report", {"contradictions": []})]]
    assert rn.mem_say(store, ["広報の電話番号は0312345678"], make_backend("openai", "m", client=FakeOpenAI(story))).committed
    ask = [[("tool", "recall", {"question": "広報の電話番号は何ですか"})], [("tool", "weave_span", {"sid": 0, "tier": "WORD", "first": "0312345678", "last": "0312345678"})], [("tool", "emit", {})]]
    plain = rn.mem_ask(store, "広報の電話番号は何ですか", make_backend("openai", "m", client=FakeOpenAI(ask)))
    filtered = rn.mem_ask(store, "広報の電話番号は何ですか", make_backend("openai", "m", client=FakeOpenAI(ask)), gate_filters=["no-contact-info"])
    assert plain.status == "answered" and plain.text == "0312345678"
    assert filtered.status == "refused" and filtered.reason == "plugin_refused" and filtered.detail["plugin"]["code"] == "phone" and filtered.text is None


def test_the_note_kind_points_at_open_sentences(example):
    rows = [{"sent": "広報の担当は山本"}, {"sent": "会場は未定"}]
    assert example.undecided(rows) == [{"sid": 1, "text": "まだ決まっていない: 会場は未定"}]
