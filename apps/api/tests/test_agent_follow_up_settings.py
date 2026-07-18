"""
Tests for AgentFollowUpSettings CRUD (follow-up-tool-prd.md):
GET/PUT /agents/{id}/follow-up, plan gating (only when turning ON), and
step validation (strictly increasing delay_hours).
"""

import uuid


def _agent_payload(ai_model_id: uuid.UUID, **kwargs) -> dict:
    defaults = {
        "name": "Agente com Follow-up",
        "system_prompt": "You are a helpful agent.",
        "ai_model_id": str(ai_model_id),
        "temperature": 0.7,
    }
    defaults.update(kwargs)
    return defaults


def _create_agent(client, ai_model, name: str = "Agente com Follow-up") -> str:
    r = client.post("/agents", json=_agent_payload(ai_model.id, name=name))
    assert r.status_code == 201
    return r.json()["id"]


def _enable_payload(**overrides) -> dict:
    defaults = {
        "is_enabled": True,
        "custom_instructions": None,
        "steps": [{"delay_hours": 6}, {"delay_hours": 24}, {"delay_hours": 72}],
    }
    defaults.update(overrides)
    return defaults


def test_get_follow_up_settings_defaults_disabled(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.get(f"/agents/{agent_id}/follow-up")
    assert r.status_code == 200
    body = r.json()
    assert body["is_enabled"] is False
    assert body["steps"] == []


def test_enable_follow_up_requires_scale_plan(client_a, subscription_a, ai_model):
    """subscription_a defaults to starter — follow_up is Scale+."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(f"/agents/{agent_id}/follow-up", json=_enable_payload())
    assert r.status_code == 402


def test_disable_follow_up_works_without_scale_plan(client_a, subscription_a, ai_model):
    """Always allowed to turn OFF / edit while off, even on starter."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json={"is_enabled": False, "custom_instructions": "Seja gentil.", "steps": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["is_enabled"] is False
    assert body["custom_instructions"] == "Seja gentil."


def test_enable_follow_up_succeeds_on_scale_plan(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(f"/agents/{agent_id}/follow-up", json=_enable_payload())
    assert r.status_code == 200
    body = r.json()
    assert body["is_enabled"] is True
    assert body["steps"] == [
        {"step_order": 0, "delay_hours": 6, "custom_instructions": None},
        {"step_order": 1, "delay_hours": 24, "custom_instructions": None},
        {"step_order": 2, "delay_hours": 72, "custom_instructions": None},
    ]


def test_enable_without_steps_rejected(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json={"is_enabled": True, "custom_instructions": None, "steps": []},
    )
    assert r.status_code == 422


def test_steps_must_be_strictly_increasing(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json=_enable_payload(steps=[{"delay_hours": 24}, {"delay_hours": 6}]),
    )
    assert r.status_code == 422


def test_steps_reject_duplicates(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json=_enable_payload(steps=[{"delay_hours": 6}, {"delay_hours": 6}]),
    )
    assert r.status_code == 422


def test_steps_max_five(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    steps = [{"delay_hours": h} for h in (1, 2, 3, 4, 5, 6)]
    r = client_a.put(f"/agents/{agent_id}/follow-up", json=_enable_payload(steps=steps))
    assert r.status_code == 422


def test_update_replaces_step_list_fully(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    client_a.put(f"/agents/{agent_id}/follow-up", json=_enable_payload())

    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json=_enable_payload(steps=[{"delay_hours": 12}]),
    )
    assert r.status_code == 200
    assert r.json()["steps"] == [
        {"step_order": 0, "delay_hours": 12, "custom_instructions": None}
    ]


def test_step_custom_instructions_persisted(client_a, scale_subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.put(
        f"/agents/{agent_id}/follow-up",
        json=_enable_payload(steps=[
            {"delay_hours": 6, "custom_instructions": None},
            {"delay_hours": 24, "custom_instructions": "Ofereça um cupom de 10% de desconto."},
        ]),
    )
    assert r.status_code == 200
    steps = r.json()["steps"]
    assert steps[0]["custom_instructions"] is None
    assert steps[1]["custom_instructions"] == "Ofereça um cupom de 10% de desconto."

    # GET reflects the same persisted values.
    r2 = client_a.get(f"/agents/{agent_id}/follow-up")
    assert r2.json()["steps"][1]["custom_instructions"] == "Ofereça um cupom de 10% de desconto."


def test_follow_up_settings_isolated_per_agent(client_a, scale_subscription_a, ai_model):
    agent_id_1 = _create_agent(client_a, ai_model)
    agent_id_2 = _create_agent(client_a, ai_model, name="Outro agente")
    client_a.put(f"/agents/{agent_id_1}/follow-up", json=_enable_payload())

    r = client_a.get(f"/agents/{agent_id_2}/follow-up")
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False
    assert r.json()["steps"] == []
