"""
Tests for whatsapp_webhook_parser.py — Phase 6.2-A.

Pure unit tests: no DB, no fixtures beyond inline dicts.

Covers:
  parse_inbound_text_messages
  - valid text payload extracted correctly
  - phone_number_id extracted from metadata
  - wamid, from_wa_id, timestamp, text_body parsed
  - contact profile_name extracted
  - contact missing → contact still returned with wa_id
  - multiple entries / changes → all messages extracted
  - non-text message type ignored
  - status update payload → empty list
  - payload with no messages key → empty list
  - empty payload → empty list
  - non-dict payload → empty list
  - None payload → empty list
  - message with empty body ignored
  - message missing id or from field ignored

  is_status_update
  - status-only payload returns True
  - message payload returns False
  - empty payload returns False
  - mixed (status + messages in same value) returns False
"""

from app.services.whatsapp_webhook_parser import (
    WhatsAppInboundMessage,
    is_status_update,
    parse_inbound_text_messages,
    parse_status_updates,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────


def _make_text_payload(
    phone_number_id: str = "1238906075969844",
    wa_id: str = "5537999999999",
    wamid: str = "wamid.ABC123",
    text_body: str = "Olá",
    profile_name: str = "Lucas",
    timestamp: str = "1710000000",
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556620073",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": profile_name},
                                    "wa_id": wa_id,
                                }
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": wamid,
                                    "timestamp": timestamp,
                                    "text": {"body": text_body},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _make_status_payload(wamid: str = "wamid.ABC123") -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "statuses": [
                                {
                                    "id": wamid,
                                    "status": "delivered",
                                    "timestamp": "1710000001",
                                    "recipient_id": "5537999999999",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


# ── parse_inbound_text_messages ────────────────────────────────────────────────


class TestParseInboundTextMessages:
    def test_valid_text_payload_returns_one_message(self):
        result = parse_inbound_text_messages(_make_text_payload())
        assert len(result) == 1

    def test_result_type_is_whatsapp_inbound_message(self):
        result = parse_inbound_text_messages(_make_text_payload())
        assert isinstance(result[0], WhatsAppInboundMessage)

    def test_phone_number_id_extracted(self):
        result = parse_inbound_text_messages(_make_text_payload(phone_number_id="PHONE_ID_999"))
        assert result[0].phone_number_id == "PHONE_ID_999"

    def test_wamid_extracted(self):
        result = parse_inbound_text_messages(_make_text_payload(wamid="wamid.XYZ789"))
        assert result[0].wamid == "wamid.XYZ789"

    def test_from_wa_id_extracted(self):
        result = parse_inbound_text_messages(_make_text_payload(wa_id="5511988887777"))
        assert result[0].from_wa_id == "5511988887777"

    def test_text_body_extracted(self):
        result = parse_inbound_text_messages(_make_text_payload(text_body="Preciso de ajuda"))
        assert result[0].text_body == "Preciso de ajuda"

    def test_timestamp_extracted_as_int(self):
        result = parse_inbound_text_messages(_make_text_payload(timestamp="1710000000"))
        assert result[0].timestamp == 1710000000

    def test_contact_profile_name_extracted(self):
        result = parse_inbound_text_messages(_make_text_payload(profile_name="Ana Silva"))
        assert result[0].contact is not None
        assert result[0].contact.profile_name == "Ana Silva"
        assert result[0].contact.wa_id == "5537999999999"

    def test_contact_missing_returns_contact_with_none_profile_name(self):
        """Payload without contacts block → contact object still created with wa_id."""
        payload = _make_text_payload()
        del payload["entry"][0]["changes"][0]["value"]["contacts"]
        result = parse_inbound_text_messages(payload)
        assert len(result) == 1
        assert result[0].contact is not None
        assert result[0].contact.wa_id == "5537999999999"
        assert result[0].contact.profile_name is None

    def test_multiple_entries_all_messages_extracted(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID_1"},
                                "messages": [
                                    {
                                        "from": "5511111111111",
                                        "id": "wamid.M1",
                                        "timestamp": "1710000001",
                                        "text": {"body": "Msg 1"},
                                        "type": "text",
                                    }
                                ],
                            },
                        }
                    ],
                },
                {
                    "id": "WABA_2",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID_2"},
                                "messages": [
                                    {
                                        "from": "5522222222222",
                                        "id": "wamid.M2",
                                        "timestamp": "1710000002",
                                        "text": {"body": "Msg 2"},
                                        "type": "text",
                                    }
                                ],
                            },
                        }
                    ],
                },
            ],
        }
        result = parse_inbound_text_messages(payload)
        assert len(result) == 2
        wamids = {r.wamid for r in result}
        assert wamids == {"wamid.M1", "wamid.M2"}

    def test_multiple_changes_all_messages_extracted(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID_1"},
                                "messages": [
                                    {
                                        "from": "5511111111111",
                                        "id": "wamid.C1",
                                        "timestamp": "1710000001",
                                        "text": {"body": "Change 1"},
                                        "type": "text",
                                    }
                                ],
                            },
                        },
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID_1"},
                                "messages": [
                                    {
                                        "from": "5511111111111",
                                        "id": "wamid.C2",
                                        "timestamp": "1710000002",
                                        "text": {"body": "Change 2"},
                                        "type": "text",
                                    }
                                ],
                            },
                        },
                    ],
                }
            ],
        }
        result = parse_inbound_text_messages(payload)
        assert len(result) == 2

    def test_non_text_message_ignored(self):
        payload = _make_text_payload()
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_audio_message_ignored(self):
        payload = _make_text_payload()
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "audio"
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_status_update_payload_returns_empty_list(self):
        result = parse_inbound_text_messages(_make_status_payload())
        assert result == []

    def test_payload_with_no_messages_key_returns_empty_list(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {"metadata": {"phone_number_id": "PID_1"}},
                        }
                    ]
                }
            ],
        }
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_empty_dict_returns_empty_list(self):
        result = parse_inbound_text_messages({})
        assert result == []

    def test_non_dict_payload_returns_empty_list(self):
        result = parse_inbound_text_messages("not a dict")  # type: ignore[arg-type]
        assert result == []

    def test_none_payload_returns_empty_list(self):
        result = parse_inbound_text_messages(None)  # type: ignore[arg-type]
        assert result == []

    def test_empty_text_body_ignored(self):
        payload = _make_text_payload()
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = ""
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_message_missing_id_ignored(self):
        payload = _make_text_payload()
        del payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_message_missing_from_ignored(self):
        payload = _make_text_payload()
        del payload["entry"][0]["changes"][0]["value"]["messages"][0]["from"]
        result = parse_inbound_text_messages(payload)
        assert result == []

    def test_non_messages_field_ignored(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "account_review_update",
                            "value": {"decision": "APPROVED"},
                        }
                    ]
                }
            ],
        }
        result = parse_inbound_text_messages(payload)
        assert result == []


# ── is_status_update ───────────────────────────────────────────────────────────


class TestIsStatusUpdate:
    def test_status_only_payload_returns_true(self):
        assert is_status_update(_make_status_payload()) is True

    def test_text_message_payload_returns_false(self):
        assert is_status_update(_make_text_payload()) is False

    def test_empty_dict_returns_false(self):
        assert is_status_update({}) is False

    def test_non_dict_returns_false(self):
        assert is_status_update("not a dict") is False  # type: ignore[arg-type]

    def test_mixed_status_and_messages_returns_false(self):
        """If value contains both statuses and messages, it is not a pure status update."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [{"id": "wamid.X", "status": "read"}],
                                "messages": [
                                    {
                                        "from": "5511111111111",
                                        "id": "wamid.Y",
                                        "type": "text",
                                        "text": {"body": "Hi"},
                                    }
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        assert is_status_update(payload) is False


# ── parse_status_updates ───────────────────────────────────────────────────────


def _make_status_update_payload(
    phone_number_id: str = "1238906075969844",
    wamid: str = "wamid.STATUS001",
    status: str = "delivered",
    timestamp: str = "1710000000",
    recipient_id: str = "5537999999999",
    conversation_id: str = "wamid-conv-001",
    conversation_origin_type: str = "service",
    billable: bool = True,
    pricing_model: str = "CBP",
    pricing_category: str = "service",
    errors: list | None = None,
) -> dict:
    status_obj: dict = {
        "id": wamid,
        "status": status,
        "timestamp": timestamp,
        "recipient_id": recipient_id,
        "conversation": {
            "id": conversation_id,
            "expiration_timestamp": "1710003600",
            "origin": {"type": conversation_origin_type},
        },
        "pricing": {
            "billable": billable,
            "pricing_model": pricing_model,
            "category": pricing_category,
        },
    }
    if errors is not None:
        status_obj["errors"] = errors
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_001",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556620073",
                                "phone_number_id": phone_number_id,
                            },
                            "statuses": [status_obj],
                        },
                    }
                ],
            }
        ],
    }


class TestParseStatusUpdates:
    def test_extracts_delivered_status(self):
        payload = _make_status_update_payload(status="delivered")
        result = parse_status_updates(payload)
        assert len(result) == 1
        upd = result[0]
        assert upd.wamid == "wamid.STATUS001"
        assert upd.status == "delivered"

    def test_extracts_read_status(self):
        payload = _make_status_update_payload(status="read", wamid="wamid.READ001")
        result = parse_status_updates(payload)
        assert result[0].status == "read"
        assert result[0].wamid == "wamid.READ001"

    def test_extracts_failed_status_with_errors(self):
        errors = [
            {
                "code": 130497,
                "title": "Business account is restricted",
                "message": "Business account is restricted from messaging users in this country.",
            }
        ]
        payload = _make_status_update_payload(status="failed", errors=errors)
        result = parse_status_updates(payload)
        upd = result[0]
        assert upd.status == "failed"
        assert upd.error_code == "130497"
        assert upd.error_title == "Business account is restricted"
        assert "restricted" in (upd.error_message or "")

    def test_extracts_pricing_fields(self):
        payload = _make_status_update_payload(
            billable=True, pricing_model="CBP", pricing_category="service"
        )
        upd = parse_status_updates(payload)[0]
        assert upd.billable is True
        assert upd.pricing_model == "CBP"
        assert upd.pricing_category == "service"

    def test_extracts_conversation_id(self):
        payload = _make_status_update_payload(conversation_id="wamid-conv-XYZ")
        upd = parse_status_updates(payload)[0]
        assert upd.conversation_id == "wamid-conv-XYZ"

    def test_extracts_conversation_origin_type(self):
        payload = _make_status_update_payload(conversation_origin_type="marketing")
        upd = parse_status_updates(payload)[0]
        assert upd.conversation_origin_type == "marketing"

    def test_extracts_phone_number_id(self):
        payload = _make_status_update_payload(phone_number_id="PID_SPECIAL_999")
        upd = parse_status_updates(payload)[0]
        assert upd.phone_number_id == "PID_SPECIAL_999"

    def test_extracts_timestamp_as_int(self):
        payload = _make_status_update_payload(timestamp="1710000000")
        upd = parse_status_updates(payload)[0]
        assert upd.timestamp == 1710000000

    def test_multiple_statuses_in_same_payload(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID"},
                                "statuses": [
                                    {"id": "wamid.A", "status": "delivered", "timestamp": "1"},
                                    {"id": "wamid.B", "status": "read", "timestamp": "2"},
                                    {"id": "wamid.C", "status": "sent", "timestamp": "3"},
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        result = parse_status_updates(payload)
        assert len(result) == 3
        wamids = {u.wamid for u in result}
        assert wamids == {"wamid.A", "wamid.B", "wamid.C"}

    def test_status_without_id_is_ignored(self):
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID"},
                                "statuses": [
                                    {"status": "delivered"},  # no id
                                    {"id": "wamid.VALID", "status": "read"},
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        result = parse_status_updates(payload)
        assert len(result) == 1
        assert result[0].wamid == "wamid.VALID"

    def test_payload_without_statuses_returns_empty(self):
        payload = _make_text_payload()
        assert parse_status_updates(payload) == []

    def test_payload_with_no_entry_returns_empty(self):
        assert parse_status_updates({"object": "whatsapp_business_account"}) == []

    def test_malformed_payload_returns_empty(self):
        assert parse_status_updates(None) == []  # type: ignore[arg-type]
        assert parse_status_updates("bad") == []  # type: ignore[arg-type]
        assert parse_status_updates([]) == []  # type: ignore[arg-type]

    def test_mixed_payload_with_messages_and_statuses_returns_statuses(self):
        """parse_status_updates should extract statuses even when messages are also present."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "metadata": {"phone_number_id": "PID"},
                                "messages": [
                                    {
                                        "from": "5511111111111",
                                        "id": "wamid.INBOUND",
                                        "type": "text",
                                        "text": {"body": "Oi"},
                                    }
                                ],
                                "statuses": [
                                    {"id": "wamid.OUTBOUND", "status": "delivered"}
                                ],
                            },
                        }
                    ]
                }
            ],
        }
        statuses = parse_status_updates(payload)
        assert len(statuses) == 1
        assert statuses[0].wamid == "wamid.OUTBOUND"

    def test_unknown_status_preserved_as_string(self):
        payload = _make_status_update_payload(status="processing")
        upd = parse_status_updates(payload)[0]
        assert upd.status == "processing"

    def test_error_code_converted_to_string(self):
        errors = [{"code": 130497, "title": "err title", "message": "err msg"}]
        payload = _make_status_update_payload(status="failed", errors=errors)
        upd = parse_status_updates(payload)[0]
        assert upd.error_code == "130497"
        assert isinstance(upd.error_code, str)

    def test_missing_optional_fields_are_none(self):
        """Status with only id and status — all optional fields should be None."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "statuses": [{"id": "wamid.MIN", "status": "sent"}],
                            },
                        }
                    ]
                }
            ],
        }
        upd = parse_status_updates(payload)[0]
        assert upd.phone_number_id is None
        assert upd.timestamp is None
        assert upd.recipient_id is None
        assert upd.conversation_id is None
        assert upd.pricing_category is None
        assert upd.error_code is None
