"""Tests for the outbound messaging dispatcher (provider abstraction — Slice 1).

The dispatcher routes an outbound message to the provider configured on its
channel (channel.config_json["provider"]), defaulting to Meta. These are pure
unit tests over the routing logic; the Meta path is patched at
`whatsapp_outbound_service.deliver_human_message` (module attribute), which is
how the existing suite already intercepts delivery.
"""

from unittest.mock import MagicMock, patch

from app.services.messaging.dispatch import (
    DEFAULT_PROVIDER_KEY,
    _resolve_provider_key,
    deliver_outbound_message,
)

_META_DELIVER = "app.services.whatsapp_outbound_service.deliver_human_message"


def _conv(channel_id=None):
    conv = MagicMock()
    conv.channel_id = channel_id
    return conv


def test_resolve_defaults_to_meta_without_channel():
    db = MagicMock()
    assert _resolve_provider_key(db, _conv(channel_id=None)) == DEFAULT_PROVIDER_KEY
    db.get.assert_not_called()


def test_resolve_reads_provider_from_channel_config():
    db = MagicMock()
    channel = MagicMock()
    channel.config_json = {"provider": "evolution_api"}
    db.get.return_value = channel
    assert _resolve_provider_key(db, _conv(channel_id=1)) == "evolution_api"


def test_resolve_defaults_when_channel_has_no_provider():
    db = MagicMock()
    channel = MagicMock()
    channel.config_json = {}
    db.get.return_value = channel
    assert _resolve_provider_key(db, _conv(channel_id=1)) == DEFAULT_PROVIDER_KEY


def test_dispatch_routes_to_meta_by_default():
    db = MagicMock()
    message = MagicMock()
    conversation = _conv(channel_id=None)
    with patch(_META_DELIVER) as meta_deliver:
        deliver_outbound_message(db, message, conversation)
    meta_deliver.assert_called_once_with(db, message, conversation)


def test_dispatch_unknown_provider_falls_back_to_meta():
    db = MagicMock()
    channel = MagicMock()
    channel.config_json = {"provider": "not_a_real_provider"}
    db.get.return_value = channel
    message = MagicMock()
    conversation = _conv(channel_id=99)
    with patch(_META_DELIVER) as meta_deliver:
        deliver_outbound_message(db, message, conversation)
    meta_deliver.assert_called_once_with(db, message, conversation)
