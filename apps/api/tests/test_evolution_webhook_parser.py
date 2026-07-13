"""Tests for evolution_webhook_parser.py.

The primary fixture (`_real_captured_payload`) is the exact payload captured
from a live Evolution v2.3.7 instance on 2026-07-13 (via a temporary
webhook.site receiver), trimmed only of the large irrelevant Signal-protocol
metadata blob inside messageContextInfo. See negocios/wenzap/plano-evolution-api.md.
"""

from app.services.evolution_webhook_parser import (
    extract_apikey,
    parse_inbound_text_messages,
)


def _real_captured_payload(
    text: str = "Boa noite",
    from_wa_id: str = "553784111441",
    wamid: str = "3EB0031990398D2F8A5B32",
    from_me: bool = False,
    apikey: str = "864FADF292E3-444D-81C8-AA438514F40D",
) -> dict:
    """Mirrors the real Evolution v2.3.7 messages.upsert payload, verbatim shape."""
    return {
        "event": "messages.upsert",
        "instance": "wenzap",
        "data": {
            "key": {
                "remoteJid": f"{from_wa_id}@s.whatsapp.net",
                "remoteJidAlt": f"{from_wa_id}@s.whatsapp.net",
                "fromMe": from_me,
                "id": wamid,
                "participant": "",
                "addressingMode": "lid",
            },
            "pushName": "Lucas Couto",
            "status": "DELIVERY_ACK",
            "message": {"conversation": text},
            "contextInfo": {"mentionedJid": [], "groupMentions": []},
            "messageType": "conversation",
            "messageTimestamp": 1783982199,
            "instanceId": "fb4d0815-2c2b-43e6-abbd-562dd169d2fe",
            "source": "web",
        },
        "destination": "https://webhook.site/aaf83b2f-2b07-4490-b06e-0e27318a080e",
        "date_time": "2026-07-13T19:36:39.884Z",
        "sender": "553784269679@s.whatsapp.net",
        "server_url": "https://evolution-api-production-397c.up.railway.app",
        "apikey": apikey,
    }


# ── real payload — happy path ────────────────────────────────────────────────


def test_real_payload_extracts_one_message():
    results = parse_inbound_text_messages(_real_captured_payload())
    assert len(results) == 1
    msg = results[0]
    assert msg.phone_number_id == "wenzap"  # instance name, this provider's routing key
    assert msg.wamid == "3EB0031990398D2F8A5B32"
    assert msg.from_wa_id == "553784111441"
    assert msg.text_body == "Boa noite"
    assert msg.timestamp == 1783982199
    assert msg.contact is not None
    assert msg.contact.wa_id == "553784111441"
    assert msg.contact.profile_name == "Lucas Couto"


def test_extract_apikey_from_real_payload():
    assert extract_apikey(_real_captured_payload()) == "864FADF292E3-444D-81C8-AA438514F40D"


# ── fromMe filtering — critical, discovered from the real payload ───────────


def test_from_me_true_is_skipped():
    """Evolution fires messages.upsert for our own outbound sends too — must skip."""
    results = parse_inbound_text_messages(_real_captured_payload(from_me=True))
    assert results == []


# ── malformed / edge cases — never raises ────────────────────────────────────


def test_non_dict_payload_returns_empty():
    assert parse_inbound_text_messages(None) == []
    assert parse_inbound_text_messages("not a dict") == []
    assert parse_inbound_text_messages([1, 2, 3]) == []


def test_wrong_event_returns_empty():
    payload = _real_captured_payload()
    payload["event"] = "connection.update"
    assert parse_inbound_text_messages(payload) == []


def test_missing_instance_returns_empty():
    payload = _real_captured_payload()
    del payload["instance"]
    assert parse_inbound_text_messages(payload) == []


def test_missing_data_returns_empty():
    payload = _real_captured_payload()
    payload["data"] = None
    assert parse_inbound_text_messages(payload) == []


def test_missing_key_id_returns_empty():
    payload = _real_captured_payload()
    del payload["data"]["key"]["id"]
    assert parse_inbound_text_messages(payload) == []


def test_missing_remote_jid_returns_empty():
    payload = _real_captured_payload()
    del payload["data"]["key"]["remoteJid"]
    assert parse_inbound_text_messages(payload) == []


def test_unsupported_message_type_is_skipped():
    payload = _real_captured_payload()
    payload["data"]["messageType"] = "imageMessage"
    payload["data"]["message"] = {"imageMessage": {"caption": "look"}}
    assert parse_inbound_text_messages(payload) == []


def test_empty_text_body_is_skipped():
    payload = _real_captured_payload()
    payload["data"]["message"] = {"conversation": ""}
    assert parse_inbound_text_messages(payload) == []


def test_extended_text_message_fallback():
    payload = _real_captured_payload()
    payload["data"]["messageType"] = "extendedTextMessage"
    payload["data"]["message"] = {"extendedTextMessage": {"text": "Respondendo algo"}}
    results = parse_inbound_text_messages(payload)
    assert len(results) == 1
    assert results[0].text_body == "Respondendo algo"


def test_batched_data_list_is_supported():
    """Defensive: if Evolution ever batches multiple upserts in one call."""
    single = _real_captured_payload()
    payload = {**single, "data": [single["data"], _real_captured_payload(wamid="MSG2").get("data")]}
    results = parse_inbound_text_messages(payload)
    assert len(results) == 2


def test_extract_apikey_missing_returns_none():
    payload = _real_captured_payload()
    del payload["apikey"]
    assert extract_apikey(payload) is None
