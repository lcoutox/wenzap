"""
Cliente HTTP para a Meta Graph API (WhatsApp Cloud API).
Isolado como adaptador provisório para App Review da Meta.
Token nunca é logado nem retornado ao frontend.
"""

import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://graph.facebook.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.meta_review_access_token}",
        "Content-Type": "application/json",
    }


def _api_url(path: str) -> str:
    return f"{_BASE_URL}/{settings.meta_graph_api_version}/{path}"


class MetaApiError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Meta API error [{code}]: {message}")


def _raise_for_meta_error(data: dict) -> None:
    if "error" in data:
        err = data["error"]
        raise MetaApiError(
            code=str(err.get("code", "unknown")),
            message=err.get("message", "Unknown Meta API error"),
        )


def send_text_message(to: str, body: str) -> dict[str, Any]:
    """Envia mensagem de texto via Cloud API. Retorna resposta normalizada."""
    url = _api_url(f"{settings.meta_review_phone_number_id}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=_headers())

    data = resp.json()
    _raise_for_meta_error(data)

    messages = data.get("messages", [{}])
    return {
        "message_id": messages[0].get("id") if messages else None,
        "raw": data,
    }


def create_message_template(
    name: str,
    language: str,
    category: str,
    body: str,
) -> dict[str, Any]:
    """
    Cria template de mensagem na Meta.
    Usa corpo sem variáveis para evitar rejeição por falta de exemplos.
    Se o corpo contiver {{N}}, o chamador é responsável por incluir examples.
    """
    url = _api_url(f"{settings.meta_review_waba_id}/message_templates")
    payload = {
        "name": name,
        "language": language,
        "category": category,
        "components": [
            {
                "type": "BODY",
                "text": body,
            }
        ],
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.post(url, json=payload, headers=_headers())

    data = resp.json()
    _raise_for_meta_error(data)
    return data
