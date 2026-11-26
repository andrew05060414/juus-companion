from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate
from openapi_spec_validator.readers import read_from_filename

from juus_server.bubbles import bind_message_fields, parse_bubbles


@pytest.fixture(scope="module")
def document():
    path = Path(__file__).resolve().parents[1] / "docs" / "openapi-draft.yaml"
    return read_from_filename(str(path))


def test_openapi_draft_is_valid(document):
    spec, base_uri = document
    validate(spec, base_uri=base_uri)


@pytest.fixture
def contract(document):
    spec, _ = document

    def validator(schema):
        if isinstance(schema, str):
            schema = {"$ref": f"#/components/schemas/{schema}"}
        return Draft202012Validator(
            {**schema, "components": spec["components"]},
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )

    return validator


def response(document, path, method, status):
    op = document[0]["paths"][path][method]
    return op["responses"][status]["content"]["application/json"]["schema"]


NOW = "2026-01-01T00:00:00Z"


@pytest.fixture
def message():
    return dict(
        id="msg-1",
        conversation_id="chat-1",
        sender_id="char-1",
        role="assistant",
        origin="single",
        turn_id="turn-1",
        bubble_index=0,
        type="text",
        content="Hi",
        created_at=NOW,
    )


def test_bubble_adapter_rows_are_valid_messages(contract, message):
    bubbles = parse_bubbles(
        "<bubble>Hi</bubble><bubble>[语音: v]</bubble><bubble>[表情: s]</bubble>",
        voice_candidates={"v": "hello"},
        sticker_candidates={"s": "cloud"},
    ).bubbles
    rows = bind_message_fields(
        bubbles,
        turn_id="turn-1",
        bubble_index=0,
        types={"text": "text", "voice": "voice", "sticker": "sticker"},
    )
    assert len(rows) == 3
    messages = contract("Message")
    for row in rows:
        messages.validate(message | row)
    assert not messages.is_valid(message | {"media_id": "v"})
    for kind in ("voice", "sticker"):
        for fields in ({}, {"media_id": None}, {"media_id": ""}):
            assert not messages.is_valid(message | {"type": kind} | fields)


def test_history_has_a_reusable_cursor_exactly_on_nonempty_pages(contract, document, message):
    path = "/v1/conversations/{conversation_id}/messages"
    page = contract(response(document, path, "get", "200"))
    page.validate({"messages": [], "next_cursor": None})
    page.validate({"messages": [message], "next_cursor": "after-1"})
    for items, cursor in (([], "after-1"), ([message], None), ([message], "")):
        assert not page.is_valid({"messages": items, "next_cursor": cursor})


def test_sync_and_ack_have_distinct_states(contract, document, message):
    path = "/v1/devices/{device_id}/deliveries"
    page = contract(response(document, path, "get", "200"))
    ack = contract(response(document, path + "/{delivery_id}/ack", "put", "200"))
    queued = dict(
        id="d", device_id="dev", message_id=message["id"], status="queued", created_at=NOW
    )
    acknowledged = queued | {"status": "acknowledged", "acknowledged_at": NOW}

    def batch(row):
        return {
            "items": [{"change_type": "append", "delivery": row, "message": message}],
            "next_cursor": None,
        }

    page.validate(batch(queued))
    ack.validate(acknowledged)
    assert not page.is_valid(batch(acknowledged))
    assert not page.is_valid(batch(queued | {"acknowledged_at": None}))
    assert not ack.is_valid(queued)
    assert not ack.is_valid(queued | {"status": "acknowledged"})


@pytest.mark.parametrize(("index", "cursor"), [(0, "more"), (1, None)])
def test_each_single_item_replacement_page_carries_tombstones(
    contract, document, message, index, cursor
):
    page = contract(response(document, "/v1/devices/{device_id}/deliveries", "get", "200"))
    msg = message | {"id": f"new-{index}", "bubble_index": index}
    row = dict(
        id=f"d-{index}", device_id="dev", message_id=msg["id"], status="queued", created_at=NOW
    )
    item = {"change_type": "replace", "delivery": row, "message": msg}

    def batch(fields):
        return {"items": [item | fields], "next_cursor": cursor}

    page.validate(batch({"replaced_message_ids": ["old-1", "old-2"]}))
    assert not page.is_valid(batch({}))
    assert not page.is_valid(batch({"replaced_message_ids": []}))
    assert not page.is_valid(batch({"change_type": "append", "replaced_message_ids": ["old-1"]}))


def test_successful_regeneration_replaces_at_least_one_bubble(contract, document, message):
    path = "/v1/conversations/{conversation_id}/turns/{turn_id}/regenerate"
    regenerated = contract(response(document, path, "post", "200"))
    result = {"messages": [message], "replaced_message_ids": ["old"]}
    regenerated.validate(result)
    assert not regenerated.is_valid(result | {"messages": []})
    assert not regenerated.is_valid(result | {"replaced_message_ids": []})


def test_registry_review_is_versioned_and_private(contract):
    overlay = contract("CharacterRegistryOverlay")
    key = {"character_id": "char-1", "persona_version": "version-1"}
    overlay.validate(key)
    for flag in (None, True):
        overlay.validate(key | {"appearance_minor": flag})
    adult = key | {
        "appearance_minor": False,
        "reviewed_by": "reviewer",
        "reviewed_at": NOW,
        "basis": "review",
    }
    overlay.validate(adult)
    for field in ("persona_version", "reviewed_by", "reviewed_at", "basis"):
        assert not overlay.is_valid({k: v for k, v in adult.items() if k != field})
    public = {
        "id": key["character_id"],
        "persona_version": key["persona_version"],
        "display_name": "Cloud",
    }
    contract("Character").validate(public)
    assert not contract("Character").is_valid(public | {"reviewed_by": "reviewer"})


def test_push_fallback_is_not_a_delivery_ack(contract):
    attempt = contract("PushAttempt")
    first = dict(id="a", delivery_id="d", channel="fcm", attempted_at=NOW, outcome="failed")
    attempt.validate(first)
    attempt.validate(first | {"id": "b", "channel": "ntfy", "outcome": "accepted"})
    assert not attempt.is_valid(first | {"outcome": "acknowledged"})
    wake = contract("PushWakeup")
    wake.validate({"message_id": "msg-1"})
    assert not wake.is_valid({"message_id": "msg-1", "content": "private"})


def test_security_contracts_are_visible_to_clients(document):
    spec, _ = document
    assert spec["security"] == [{"DeviceBearer": []}]
    for path in spec["paths"].values():
        for method, op in path.items():
            if method == "parameters":
                continue
            expected = {
                "registerDevice": "EnrollmentBearer",
                "listPromptTraces": "InternalBearer",
                "runProactiveTick": "InternalBearer",
            }.get(op["operationId"], "DeviceBearer")
            assert op.get("security", spec["security"]) == [{expected: []}]
            assert {"401", "403"} <= op["responses"].keys()
