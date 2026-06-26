"""
Tests for Phase 6.1-A — WhatsAppChannelConfig schema and ChannelCreate/ChannelUpdate.

Covers:
  WhatsAppChannelConfig
  - valid minimal config accepted
  - provider invalid rejected
  - onboarding_type invalid rejected
  - phone_number_id required
  - waba_id required
  - access_token_ref accepted
  - extra fields rejected (extra="forbid")
  - status default is "testing"
  - status invalid rejected

  ChannelCreate
  - channel_type=whatsapp with valid config accepted
  - channel_type=instagram still rejected (not implemented)
  - channel_type=web_widget still accepted

  _parse_config_by_type
  - routes web_widget to WebWidgetConfig
  - routes whatsapp to WhatsAppChannelConfig
  - unknown type raises ValueError
"""

import pytest
from pydantic import ValidationError

from app.schemas.channel import (
    ChannelCreate,
    WhatsAppChannelConfig,
    _parse_config_by_type,
)

# ── WhatsAppChannelConfig ──────────────────────────────────────────────────────


class TestWhatsAppChannelConfig:
    def _minimal(self, **overrides) -> dict:
        return {
            "waba_id": "1247116994094076",
            "phone_number_id": "123456789",
            **overrides,
        }

    def test_minimal_valid_config_accepted(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.waba_id == "1247116994094076"
        assert cfg.phone_number_id == "123456789"
        assert cfg.provider == "meta_cloud_api"
        assert cfg.status == "testing"

    def test_provider_default_is_meta_cloud_api(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.provider == "meta_cloud_api"

    def test_provider_invalid_rejected(self):
        with pytest.raises(ValidationError, match="provider"):
            WhatsAppChannelConfig(**self._minimal(provider="z_api"))

    def test_onboarding_type_default_is_manual(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.onboarding_type == "manual"

    def test_onboarding_type_embedded_signup_accepted(self):
        cfg = WhatsAppChannelConfig(**self._minimal(onboarding_type="embedded_signup"))
        assert cfg.onboarding_type == "embedded_signup"

    def test_onboarding_type_invalid_rejected(self):
        with pytest.raises(ValidationError, match="onboarding_type"):
            WhatsAppChannelConfig(**self._minimal(onboarding_type="manual_signup"))

    def test_phone_number_id_required(self):
        data = self._minimal()
        del data["phone_number_id"]
        with pytest.raises(ValidationError, match="phone_number_id"):
            WhatsAppChannelConfig(**data)

    def test_waba_id_required(self):
        data = self._minimal()
        del data["waba_id"]
        with pytest.raises(ValidationError, match="waba_id"):
            WhatsAppChannelConfig(**data)

    def test_access_token_ref_accepted(self):
        cfg = WhatsAppChannelConfig(
            **self._minimal(access_token_ref="env:WHATSAPP_TEMP_ACCESS_TOKEN")
        )
        assert cfg.access_token_ref == "env:WHATSAPP_TEMP_ACCESS_TOKEN"

    def test_access_token_ref_none_by_default(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.access_token_ref is None

    def test_status_default_is_testing(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.status == "testing"

    def test_status_active_accepted(self):
        cfg = WhatsAppChannelConfig(**self._minimal(status="active"))
        assert cfg.status == "active"

    def test_status_disconnected_accepted(self):
        cfg = WhatsAppChannelConfig(**self._minimal(status="disconnected"))
        assert cfg.status == "disconnected"

    def test_status_invalid_rejected(self):
        with pytest.raises(ValidationError, match="status"):
            WhatsAppChannelConfig(**self._minimal(status="pending"))

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            WhatsAppChannelConfig(**self._minimal(unknown_field="foo"))

    def test_display_phone_number_optional(self):
        cfg = WhatsAppChannelConfig(**self._minimal(display_phone_number="+55 11 99999-9999"))
        assert cfg.display_phone_number == "+55 11 99999-9999"

    def test_business_id_optional(self):
        cfg = WhatsAppChannelConfig(**self._minimal(business_id="9876543210"))
        assert cfg.business_id == "9876543210"

    def test_connected_at_and_last_webhook_at_optional(self):
        cfg = WhatsAppChannelConfig(**self._minimal())
        assert cfg.connected_at is None
        assert cfg.last_webhook_at is None


# ── ChannelCreate ──────────────────────────────────────────────────────────────

class TestChannelCreateWithWhatsApp:
    def _minimal_whatsapp_create(self, agent_id=None) -> dict:
        import uuid
        return {
            "agent_id": str(agent_id or uuid.uuid4()),
            "channel_type": "whatsapp",
            "name": "WhatsApp Principal",
            "config": {
                "waba_id": "1247116994094076",
                "phone_number_id": "123456789",
            },
        }

    def test_channel_create_whatsapp_valid(self):
        import uuid
        data = self._minimal_whatsapp_create(agent_id=uuid.uuid4())
        create = ChannelCreate(**data)
        assert create.channel_type == "whatsapp"
        assert create.config["waba_id"] == "1247116994094076"
        assert create.config["phone_number_id"] == "123456789"

    def test_channel_create_whatsapp_missing_phone_number_id_rejected(self):
        import uuid
        data = {
            "agent_id": str(uuid.uuid4()),
            "channel_type": "whatsapp",
            "name": "WhatsApp",
            "config": {"waba_id": "1247116994094076"},
        }
        with pytest.raises(ValidationError, match="phone_number_id"):
            ChannelCreate(**data)

    def test_channel_create_instagram_still_rejected(self):
        import uuid
        with pytest.raises(ValidationError, match="not yet implemented"):
            ChannelCreate(
                agent_id=uuid.uuid4(),
                channel_type="instagram",
                name="Instagram",
                config={},
            )

    def test_channel_create_web_widget_still_accepted(self):
        import uuid
        create = ChannelCreate(
            agent_id=uuid.uuid4(),
            channel_type="web_widget",
            name="Widget",
            config={},
        )
        assert create.channel_type == "web_widget"


# ── _parse_config_by_type ──────────────────────────────────────────────────────

class TestParseConfigByType:
    def test_routes_web_widget(self):
        result = _parse_config_by_type("web_widget", {})
        assert "theme" in result
        assert "primary_color" in result

    def test_routes_whatsapp(self):
        result = _parse_config_by_type("whatsapp", {
            "waba_id": "1247116994094076",
            "phone_number_id": "123456789",
        })
        assert result["provider"] == "meta_cloud_api"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="not yet implemented"):
            _parse_config_by_type("instagram", {})
