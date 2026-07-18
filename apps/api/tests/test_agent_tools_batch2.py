"""
Tests for the "Batch 2" agent tools (agent-tools-batch-2-prd.md):

- tool_type="capture_contact_data": /agents/{id}/tools/capture-contact-data
  (no plan gate) and execute_capture_contact_data_tool's upsert-into-
  ContactVariable behavior.
- tool_type="pipeline_action": /agents/{id}/tools/pipeline-action (gated on
  the "pipelines" feature key) and execute_pipeline_action_tool's find-or-
  create-then-move behavior via pipeline_service.
- tool_type="assign_operator": /agents/{id}/tools/assign-operator (no plan
  gate) and execute_assign_operator_tool's assign+notify+idempotent behavior,
  plus Conversation.assignment_reason's lifecycle (set here, cleared by
  return_to_ai — mirrors handoff_reason).
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.enums import MemberRole, MemberStatus
from app.models.contact import Contact
from app.models.contact_variable import ContactVariable
from app.models.conversation import Conversation
from app.models.pipeline import Pipeline
from app.models.pipeline_entry import PipelineEntry
from app.models.pipeline_stage import PipelineStage
from app.models.workspace_member import WorkspaceMember
from app.services.agent_tool_service import (
    build_tool_dispatch,
    build_tool_schema,
    execute_assign_operator_tool,
    execute_capture_contact_data_tool,
    execute_pipeline_action_tool,
)
from app.services.conversation_service import return_to_ai
from app.services.email_service import FakeEmailService, override_email_service, reset_email_service
from tests.test_agent_tools import _create_agent, _FakeTool, _http_tool_payload

# ── Shared fixtures/helpers ──────────────────────────────────────────────────


@pytest.fixture()
def fake_email():
    svc = FakeEmailService()
    override_email_service(svc)
    yield svc
    reset_email_service()


def _make_pipeline(db, workspace_id, name: str = "Vendas") -> Pipeline:
    p = Pipeline(workspace_id=workspace_id, name=name)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_stage(
    db, workspace_id, pipeline_id, name: str = "Novo", position: int = 0
) -> PipelineStage:
    s = PipelineStage(
        workspace_id=workspace_id, pipeline_id=pipeline_id, name=name, position=position
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_member(db, workspace, role=MemberRole.member):
    from tests.conftest import _make_user  # noqa: PLC0415

    email = f"member-{uuid.uuid4().hex[:8]}@test.com"
    user = _make_user(db, email, "Operador Teste")
    db.add(WorkspaceMember(
        workspace_id=workspace.id, user_id=user.id, role=role, status=MemberStatus.active,
    ))
    db.commit()
    return user


# ── capture_contact_data: CRUD (no plan gate) ───────────────────────────────


def _capture_payload(**overrides) -> dict:
    defaults = {
        "tool_type": "capture_contact_data",
        "name": "capturar_dados",
        "description": "Captura o e-mail e o nome do cliente quando informados.",
        "config": {
            "fields": [
                {"key": "email", "description": "E-mail do cliente"},
                {"key": "empresa", "description": ""},
            ]
        },
    }
    defaults.update(overrides)
    return defaults


def test_create_capture_contact_data_tool_succeeds_on_starter_plan(
    client_a, subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data", json=_capture_payload()
    )
    assert r.status_code == 201
    body = r.json()
    assert body["tool_type"] == "capture_contact_data"
    assert len(body["config"]["fields"]) == 2


def test_create_capture_contact_data_tool_rejects_wrong_tool_type(
    client_a, subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data", json=_http_tool_payload()
    )
    assert r.status_code == 400


def test_create_capture_contact_data_tool_rejects_empty_fields(
    client_a, subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data",
        json=_capture_payload(config={"fields": []}),
    )
    assert r.status_code == 422


def test_create_capture_contact_data_tool_rejects_duplicate_keys(
    client_a, subscription_a, ai_model
):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data",
        json=_capture_payload(config={"fields": [
            {"key": "email", "description": "a"}, {"key": "email", "description": "b"},
        ]}),
    )
    assert r.status_code == 400


def test_update_delete_capture_contact_data_tool(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    created = client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data", json=_capture_payload()
    ).json()

    r = client_a.patch(
        f"/agents/{agent_id}/tools/capture-contact-data/{created['id']}",
        json={"is_enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False

    r = client_a.delete(f"/agents/{agent_id}/tools/capture-contact-data/{created['id']}")
    assert r.status_code == 204
    assert client_a.get(f"/agents/{agent_id}/tools/http").json() == []


# ── capture_contact_data: service-level ─────────────────────────────────────


class _FakeCaptureTool(_FakeTool):
    def __init__(self, fields=None):
        super().__init__(
            tool_type="capture_contact_data", name="capturar_dados",
            description="Captura dados.",
            config={"fields": fields or [
                {"key": "email", "description": "E-mail do cliente"},
                {"key": "empresa", "description": ""},
            ]},
        )


def test_build_tool_schema_capture_contact_data():
    schema = build_tool_schema(_FakeCaptureTool())
    assert schema["name"] == "capturar_dados"
    props = schema["input_schema"]["properties"]
    assert set(props) == {"email", "empresa"}
    assert props["email"]["description"] == "E-mail do cliente"
    assert props["empresa"]["description"] == "Value for 'empresa'."
    assert "required" not in schema["input_schema"]  # every field optional


def test_execute_capture_contact_data_tool_simulation_mode_when_no_conversation():
    result = execute_capture_contact_data_tool(
        db=None, workspace_id=None, conversation=None, captured_fields={"email": "a@b.com"}
    )
    assert "Simulação" in result
    assert "email" in result


def test_execute_capture_contact_data_tool_upserts_contact_variables(db, workspace_a):
    contact = Contact(workspace_id=workspace_a.id, name="Cliente Teste", phone="+5511999999999")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_a.id, contact_id=contact.id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_capture_contact_data_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        captured_fields={"email": "cliente@teste.com"},
    )
    assert "sucesso" not in result.lower()  # doesn't claim generic "success" wording
    assert "email" in result

    var = db.scalar(select(ContactVariable).where(ContactVariable.contact_id == contact.id))
    assert var.key == "email"
    assert var.value == "cliente@teste.com"
    assert var.source == "ai"

    # Calling again with a new value for the same key updates in place (upsert,
    # not a 409 like create_variable) — no duplicate row.
    execute_capture_contact_data_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        captured_fields={"email": "novo@teste.com"},
    )
    rows = list(db.scalars(select(ContactVariable).where(ContactVariable.contact_id == contact.id)))
    assert len(rows) == 1
    assert rows[0].value == "novo@teste.com"


def test_execute_capture_contact_data_tool_no_contact_on_conversation(db, workspace_a):
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_capture_contact_data_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        captured_fields={"email": "a@b.com"},
    )
    assert "contato" in result.lower()
    assert db.scalar(select(ContactVariable)) is None


def test_execute_capture_contact_data_tool_no_fields_captured(db, workspace_a):
    contact = Contact(workspace_id=workspace_a.id, name="Cliente", phone="+5511999999999")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_a.id, contact_id=contact.id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_capture_contact_data_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv, captured_fields={}
    )
    assert "Nenhum" in result


def test_build_tool_dispatch_capture_contact_data_filters_blank_input():
    calls = []

    def _fake_execute(**kwargs):
        calls.append(kwargs)
        return "ok"

    with patch(
        "app.services.agent_tool_service.execute_capture_contact_data_tool", _fake_execute
    ):
        dispatch = build_tool_dispatch(
            [_FakeCaptureTool()], db="db-sentinel", workspace_id="ws-sentinel",
            conversation="conv-sentinel",
        )
        dispatch["capturar_dados"]({"email": "a@b.com", "empresa": "  ", "extra": None})

    assert calls == [{
        "db": "db-sentinel", "workspace_id": "ws-sentinel", "conversation": "conv-sentinel",
        "captured_fields": {"email": "a@b.com"},
    }]


# ── pipeline_action: CRUD (gated on "pipelines" feature key) ───────────────


def _pipeline_action_payload(pipeline_id: uuid.UUID, stage_id: uuid.UUID, **overrides) -> dict:
    defaults = {
        "tool_type": "pipeline_action",
        "name": "mover_para_qualificado",
        "description": "Move o card para a etapa Qualificado quando o lead confirma interesse.",
        "config": {"pipeline_id": str(pipeline_id), "stage_id": str(stage_id)},
    }
    defaults.update(overrides)
    return defaults


def test_create_pipeline_action_tool_succeeds_on_starter_plan(
    client_a, subscription_a, ai_model, db, workspace_a
):
    """pipelines is enabled on every plan tier today — only http_tools/follow_up
    are premium-gated (agent-tools-batch-2-prd.md)."""
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    agent_id = _create_agent(client_a, ai_model)

    r = client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(pipeline.id, stage.id),
    )
    assert r.status_code == 201
    assert r.json()["config"] == {"pipeline_id": str(pipeline.id), "stage_id": str(stage.id)}


def test_create_pipeline_action_tool_blocked_when_pipelines_feature_disabled(
    client_a, subscription_a, ai_model, db, workspace_a
):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    agent_id = _create_agent(client_a, ai_model)

    with patch("app.routers.agents.workspace_allows_feature", return_value=False):
        r = client_a.post(
            f"/agents/{agent_id}/tools/pipeline-action",
            json=_pipeline_action_payload(pipeline.id, stage.id),
        )
    assert r.status_code == 402


def test_create_pipeline_action_tool_rejects_wrong_tool_type(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(f"/agents/{agent_id}/tools/pipeline-action", json=_http_tool_payload())
    assert r.status_code == 400


def test_create_pipeline_action_tool_rejects_unknown_pipeline(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(uuid.uuid4(), uuid.uuid4()),
    )
    assert r.status_code == 400


def test_create_pipeline_action_tool_rejects_stage_from_other_pipeline(
    client_a, subscription_a, ai_model, db, workspace_a
):
    pipeline_1 = _make_pipeline(db, workspace_a.id, name="Vendas")
    pipeline_2 = _make_pipeline(db, workspace_a.id, name="Suporte")
    stage_of_2 = _make_stage(db, workspace_a.id, pipeline_2.id)
    agent_id = _create_agent(client_a, ai_model)

    r = client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(pipeline_1.id, stage_of_2.id),
    )
    assert r.status_code == 400


def test_create_pipeline_action_tool_rejects_pipeline_from_other_workspace(
    client_a, subscription_a, ai_model, db, workspace_b
):
    pipeline = _make_pipeline(db, workspace_b.id)
    stage = _make_stage(db, workspace_b.id, pipeline.id)
    agent_id = _create_agent(client_a, ai_model)

    r = client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(pipeline.id, stage.id),
    )
    assert r.status_code == 400


def test_update_delete_pipeline_action_tool(client_a, subscription_a, ai_model, db, workspace_a):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    agent_id = _create_agent(client_a, ai_model)
    created = client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(pipeline.id, stage.id),
    ).json()

    r = client_a.patch(
        f"/agents/{agent_id}/tools/pipeline-action/{created['id']}", json={"is_enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False

    r = client_a.delete(f"/agents/{agent_id}/tools/pipeline-action/{created['id']}")
    assert r.status_code == 204
    assert client_a.get(f"/agents/{agent_id}/tools/http").json() == []


# ── pipeline_action: service-level ──────────────────────────────────────────


class _FakePipelineActionTool(_FakeTool):
    def __init__(self, pipeline_id=None, stage_id=None):
        super().__init__(
            tool_type="pipeline_action", name="mover_para_qualificado",
            description="Move o card.",
            config={
                "pipeline_id": str(pipeline_id or uuid.uuid4()),
                "stage_id": str(stage_id or uuid.uuid4()),
            },
        )


def test_build_tool_schema_pipeline_action_has_no_input():
    schema = build_tool_schema(_FakePipelineActionTool())
    assert schema["input_schema"]["properties"] == {}
    assert "required" not in schema["input_schema"]


def test_execute_pipeline_action_tool_simulation_mode_when_no_conversation():
    result = execute_pipeline_action_tool(
        db=None, workspace_id=None, conversation=None,
        pipeline_id=uuid.uuid4(), stage_id=uuid.uuid4(),
    )
    assert "Simulação" in result


def test_execute_pipeline_action_tool_creates_entry_when_none_exists(db, workspace_a):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_pipeline_action_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        pipeline_id=pipeline.id, stage_id=stage.id,
    )
    assert "sucesso" in result.lower()

    entry = db.scalar(
        select(PipelineEntry).where(
            PipelineEntry.pipeline_id == pipeline.id, PipelineEntry.conversation_id == conv.id
        )
    )
    assert entry is not None
    assert entry.stage_id == stage.id


def test_execute_pipeline_action_tool_moves_existing_entry(db, workspace_a):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage_1 = _make_stage(db, workspace_a.id, pipeline.id, name="Novo", position=0)
    stage_2 = _make_stage(db, workspace_a.id, pipeline.id, name="Qualificado", position=1)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    entry = PipelineEntry(
        workspace_id=workspace_a.id, pipeline_id=pipeline.id, conversation_id=conv.id,
        stage_id=stage_1.id,
    )
    db.add(entry)
    db.commit()

    execute_pipeline_action_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        pipeline_id=pipeline.id, stage_id=stage_2.id,
    )

    db.refresh(entry)
    assert entry.stage_id == stage_2.id


def test_execute_pipeline_action_tool_is_a_no_op_when_already_in_target_stage(db, workspace_a):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    entry = PipelineEntry(
        workspace_id=workspace_a.id, pipeline_id=pipeline.id, conversation_id=conv.id,
        stage_id=stage.id,
    )
    db.add(entry)
    db.commit()

    result = execute_pipeline_action_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        pipeline_id=pipeline.id, stage_id=stage.id,
    )
    assert "já estava" in result.lower()


def test_build_tool_dispatch_pipeline_action_wires_context():
    calls = []

    def _fake_execute(**kwargs):
        calls.append(kwargs)
        return "ok"

    pipeline_id = uuid.uuid4()
    stage_id = uuid.uuid4()
    with patch("app.services.agent_tool_service.execute_pipeline_action_tool", _fake_execute):
        dispatch = build_tool_dispatch(
            [_FakePipelineActionTool(pipeline_id=pipeline_id, stage_id=stage_id)],
            db="db-sentinel", workspace_id="ws-sentinel", conversation="conv-sentinel",
        )
        dispatch["mover_para_qualificado"]({})

    assert calls == [{
        "db": "db-sentinel", "workspace_id": "ws-sentinel", "conversation": "conv-sentinel",
        "pipeline_id": pipeline_id, "stage_id": stage_id,
    }]


# ── assign_operator: CRUD (no plan gate) ────────────────────────────────────


def _assign_operator_payload(user_id: uuid.UUID, **overrides) -> dict:
    defaults = {
        "tool_type": "assign_operator",
        "name": "atribuir_financeiro",
        "description": "Atribui ao time financeiro quando o cliente pede reembolso.",
        "config": {"user_id": str(user_id)},
    }
    defaults.update(overrides)
    return defaults


def test_create_assign_operator_tool_succeeds_on_starter_plan(
    client_a, subscription_a, ai_model, db, workspace_a, user_a
):
    """subscription_a defaults to starter — assign_operator has no plan gate."""
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/assign-operator", json=_assign_operator_payload(user_a.id)
    )
    assert r.status_code == 201
    assert r.json()["config"] == {"user_id": str(user_a.id)}


def test_create_assign_operator_tool_rejects_wrong_tool_type(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(f"/agents/{agent_id}/tools/assign-operator", json=_http_tool_payload())
    assert r.status_code == 400


def test_create_assign_operator_tool_rejects_non_member(client_a, subscription_a, ai_model):
    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/assign-operator", json=_assign_operator_payload(uuid.uuid4())
    )
    assert r.status_code == 400


def test_create_assign_operator_tool_rejects_inactive_member(
    client_a, subscription_a, ai_model, db, workspace_a
):
    member = _make_member(db, workspace_a)
    ms = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_a.id, WorkspaceMember.user_id == member.id
        )
    )
    ms.status = MemberStatus.inactive
    db.commit()

    agent_id = _create_agent(client_a, ai_model)
    r = client_a.post(
        f"/agents/{agent_id}/tools/assign-operator", json=_assign_operator_payload(member.id)
    )
    assert r.status_code == 400


def test_update_delete_assign_operator_tool(client_a, subscription_a, ai_model, user_a):
    agent_id = _create_agent(client_a, ai_model)
    created = client_a.post(
        f"/agents/{agent_id}/tools/assign-operator", json=_assign_operator_payload(user_a.id)
    ).json()

    r = client_a.patch(
        f"/agents/{agent_id}/tools/assign-operator/{created['id']}", json={"is_enabled": False}
    )
    assert r.status_code == 200
    assert r.json()["is_enabled"] is False

    r = client_a.delete(f"/agents/{agent_id}/tools/assign-operator/{created['id']}")
    assert r.status_code == 204
    assert client_a.get(f"/agents/{agent_id}/tools/http").json() == []


# ── assign_operator: service-level ──────────────────────────────────────────


class _FakeAssignOperatorTool(_FakeTool):
    def __init__(self, user_id=None):
        super().__init__(
            tool_type="assign_operator", name="atribuir_financeiro",
            description="Atribui ao financeiro.", config={"user_id": str(user_id or uuid.uuid4())},
        )


def test_build_tool_schema_assign_operator():
    schema = build_tool_schema(_FakeAssignOperatorTool())
    assert schema["input_schema"]["required"] == ["reason"]
    assert "reason" in schema["input_schema"]["properties"]


def test_execute_assign_operator_tool_simulation_mode_when_no_conversation():
    result = execute_assign_operator_tool(
        db=None, workspace_id=None, conversation=None, user_id=None, reason="Pedido de reembolso.",
    )
    assert "Simulação" in result
    assert "reembolso" in result


def test_execute_assign_operator_tool_assigns_and_notifies(db, workspace_a, fake_email):
    operator = _make_member(db, workspace_a)
    contact = Contact(workspace_id=workspace_a.id, name="Cliente Teste", phone="+5511999999999")
    db.add(contact)
    db.flush()
    conv = Conversation(
        workspace_id=workspace_a.id, contact_id=contact.id,
        channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_assign_operator_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        user_id=operator.id, reason="Cliente pediu reembolso.",
    )

    assert "sucesso" in result.lower()
    assert conv.assigned_user_id == operator.id
    assert conv.ai_enabled is False
    assert conv.assignment_reason == "Cliente pediu reembolso."
    assert len(fake_email.sent) == 1
    assert operator.email in fake_email.sent[0]["to"]
    assert "Cliente Teste" in fake_email.sent[0]["html"]
    assert "Cliente pediu reembolso." in fake_email.sent[0]["html"]


def test_execute_assign_operator_tool_is_idempotent_once_assigned(db, workspace_a, fake_email):
    operator_1 = _make_member(db, workspace_a)
    operator_2 = _make_member(db, workspace_a)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
        assigned_user_id=operator_1.id,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_assign_operator_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        user_id=operator_2.id, reason="Segundo motivo.",
    )

    assert "já está atribuída" in result.lower()
    assert conv.assigned_user_id == operator_1.id
    assert conv.assignment_reason is None
    assert len(fake_email.sent) == 0


def test_execute_assign_operator_tool_member_no_longer_active(db, workspace_a, fake_email):
    operator = _make_member(db, workspace_a)
    ms = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_a.id, WorkspaceMember.user_id == operator.id
        )
    )
    ms.status = MemberStatus.inactive
    db.commit()

    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    result = execute_assign_operator_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        user_id=operator.id, reason="Motivo qualquer.",
    )

    assert "não está mais disponível" in result.lower()
    assert conv.assigned_user_id is None
    assert len(fake_email.sent) == 0


def test_execute_assign_operator_tool_notify_failure_does_not_raise(db, workspace_a, fake_email):
    operator = _make_member(db, workspace_a)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    with patch(
        "app.services.email_service.FakeEmailService.send", side_effect=RuntimeError("boom")
    ):
        result = execute_assign_operator_tool(
            db=db, workspace_id=workspace_a.id, conversation=conv,
            user_id=operator.id, reason="Motivo qualquer.",
        )

    assert conv.assigned_user_id == operator.id
    assert "sucesso" in result.lower()


def test_assignment_reason_cleared_by_return_to_ai(db, workspace_a):
    operator = _make_member(db, workspace_a)
    conv = Conversation(
        workspace_id=workspace_a.id, channel_type="internal", status="open", ai_enabled=True,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    execute_assign_operator_tool(
        db=db, workspace_id=workspace_a.id, conversation=conv,
        user_id=operator.id, reason="Motivo qualquer.",
    )
    assert conv.assignment_reason == "Motivo qualquer."

    return_to_ai(db, workspace_a.id, conv.id)
    db.refresh(conv)
    assert conv.assignment_reason is None
    assert conv.assigned_user_id is None
    assert conv.ai_enabled is True


def test_build_tool_dispatch_assign_operator_wires_context():
    calls = []

    def _fake_execute(**kwargs):
        calls.append(kwargs)
        return "ok"

    user_id = uuid.uuid4()
    with patch("app.services.agent_tool_service.execute_assign_operator_tool", _fake_execute):
        dispatch = build_tool_dispatch(
            [_FakeAssignOperatorTool(user_id=user_id)],
            db="db-sentinel", workspace_id="ws-sentinel", conversation="conv-sentinel",
        )
        dispatch["atribuir_financeiro"]({"reason": "Teste"})

    assert calls == [{
        "db": "db-sentinel", "workspace_id": "ws-sentinel", "conversation": "conv-sentinel",
        "user_id": user_id, "reason": "Teste",
    }]


# ── Cross-tool: list endpoint returns all 6 tool_types ──────────────────────


def test_list_tools_returns_all_six_types(
    client_a, scale_subscription_a, ai_model, db, workspace_a
):
    pipeline = _make_pipeline(db, workspace_a.id)
    stage = _make_stage(db, workspace_a.id, pipeline.id)
    operator = _make_member(db, workspace_a)
    agent_id = _create_agent(client_a, ai_model)

    from tests.test_agent_tools import _PUBLIC_DNS_PATCH  # noqa: PLC0415

    with _PUBLIC_DNS_PATCH:
        client_a.post(f"/agents/{agent_id}/tools/http", json=_http_tool_payload())
    client_a.post(
        f"/agents/{agent_id}/tools/request-human",
        json={
            "tool_type": "request_human", "name": "solicitar_humano",
            "description": "x", "config": {},
        },
    )
    client_a.post(
        f"/agents/{agent_id}/tools/mark-resolved",
        json={
            "tool_type": "mark_resolved", "name": "marcar_resolvido",
            "description": "x", "config": {},
        },
    )
    client_a.post(
        f"/agents/{agent_id}/tools/capture-contact-data", json=_capture_payload()
    )
    client_a.post(
        f"/agents/{agent_id}/tools/pipeline-action",
        json=_pipeline_action_payload(pipeline.id, stage.id),
    )
    client_a.post(
        f"/agents/{agent_id}/tools/assign-operator", json=_assign_operator_payload(operator.id)
    )

    tool_types = {t["tool_type"] for t in client_a.get(f"/agents/{agent_id}/tools/http").json()}
    assert tool_types == {
        "http_request", "request_human", "mark_resolved",
        "capture_contact_data", "pipeline_action", "assign_operator",
    }
