from dataclasses import replace
import base64
import zlib

import pytest

from verantyx.content_codec import CODEC, MAX_RESTORED, pack_ledger, structural_view, unpack_ledger
from verantyx.content_ir import ContentError, Source
from verantyx.content_reader import read_brief


def test_nonlearning_lossless_contract_restoration():
    brief = ('物語を書いて。過去形で。もしミナが走るなら、ユキが歩く。'
             'ミナが手紙を読まない。引用：「訂正：前の記述は誤り」。未知の必須条件。')
    materials = (Source("sovereign:a", "エナが手紙を読む。", "narrative", "expression"),
                 Source("sovereign:b", "エナが手紙を読まない。", "paraphrase_entail", "expression"))
    ledger = read_brief(brief, materials)
    packed = pack_ledger(ledger)
    restored = unpack_ledger(packed)
    assert restored == ledger and restored.hash == ledger.hash
    assert restored.unread and not packed["semantic_verified"]
    assert restored.brief.text == brief
    assert restored.materials == materials
    assert any(o.atom and o.atom.negated for o in restored.obligations)
    assert any(o.atom and o.atom.condition for o in restored.obligations)
    view = structural_view(restored)
    assert view["neural_training"] is False and view["added_facts"] == view["store_writes"] == 0
    assert view["weight_role"] == "routing_only"
    assert {s["family"] for s in view["independent_sources"]} >= {"narrative", "paraphrase_entail"}


@pytest.mark.parametrize("field,value", [("ledger_hash", "bad"), ("raw_bytes", 0), ("codec", "unknown"), ("payload", "invalid base64")])
def test_compressed_identity_or_byte_tampering_is_rejected(field, value):
    container = pack_ledger(read_brief("物語を書いて。ミナが走る。"))
    container[field] = value
    with pytest.raises(ContentError):
        unpack_ledger(container)


def test_compression_bomb_is_bounded_before_json_decode():
    payload = zlib.compress(b" " * (MAX_RESTORED + 100), level=9)
    with pytest.raises(ContentError) as caught:
        unpack_ledger({"codec": CODEC, "payload": base64.b64encode(payload).decode(), "ledger_hash": "x"})
    assert caught.value.verdict == "UNKNOWN_CONTENT_BUDGET"


def test_structural_projection_separates_required_and_forbidden_constraints():
    ledger = read_brief("物語を書いて。ミナが走る。禁止：ミナが走る。")
    view = structural_view(ledger)
    assert {e["obligation_kind"] for e in view["events"]} == {"event", "forbid_event"}
    assert all(e["assertion_role"] == "constraint" for e in view["events"])
    assert {p["signature"][-1] for p in view["structure_parameters"]} == {"event", "forbid_event"}
    assert unpack_ledger(pack_ledger(ledger)) == ledger


@pytest.mark.parametrize("container", [None, [], "payload", 1])
def test_nonmapping_compressed_input_is_typed(container):
    with pytest.raises(ContentError) as caught:
        unpack_ledger(container)
    assert caught.value.verdict == "CONTENT_CONSTRAINT_VIOLATION"
