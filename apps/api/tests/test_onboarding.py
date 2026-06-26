"""
Tests for onboarding endpoints — Phase Growth.1-A.

GET  /onboarding
POST /onboarding

Uses real DB session via conftest fixtures.
Auth is overridden via _make_client / client_a / client_b.

Covers:
  GET
  - new workspace returns completed=false, profile=null
  - after POST returns completed=true with profile
  - unauthenticated returns 401

  POST
  - creates onboarding profile
  - sets completed_at
  - second POST updates without duplicating
  - body cannot inject workspace_id (ignored/forbidden)
  - body cannot inject user_id (ignored/forbidden)
  - workspace isolation: user_b cannot read user_a's profile

  Validations
  - full_name empty → 422
  - full_name too short → 422
  - phone too short → 422
  - company_name empty → 422
  - invalid main_objective enum → 422
  - invalid company_industry enum → 422
  - invalid company_website → 422
  - contact_consent=false is allowed

  Persistence
  - workspace_id unique (no duplicates)
  - user_id saved correctly
  - updated_at changes on second POST
  - completed_at preserved on second POST
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_onboarding_profile import WorkspaceOnboardingProfile
from tests.conftest import _make_client

URL = "/onboarding"


# ── Payload factory ────────────────────────────────────────────────────────────

def _valid_payload(**overrides) -> dict:
    base = {
        "full_name": "Lucas Couto",
        "phone": "5537999999999",
        "main_objective": "customer_support",
        "expected_monthly_conversations": "100_to_500",
        "ai_experience": "tested_tools",
        "company_name": "Nexbrain Ltda",
        "company_industry": "saas_tech",
        "company_website": "https://nexbrain.ai",
        "role": "owner_founder",
        "heard_from": "google",
        "contact_consent": True,
    }
    base.update(overrides)
    return base


# ── GET /onboarding ────────────────────────────────────────────────────────────

class TestGetOnboarding:
    def test_new_workspace_returns_incomplete(
        self, client_a: TestClient
    ):
        resp = client_a.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed"] is False
        assert body["profile"] is None

    def test_after_post_returns_completed(
        self, client_a: TestClient
    ):
        client_a.post(URL, json=_valid_payload())
        resp = client_a.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed"] is True
        assert body["profile"] is not None
        assert body["profile"]["full_name"] == "Lucas Couto"

    def test_unauthenticated_returns_401(
        self, unauthenticated_client: TestClient
    ):
        resp = unauthenticated_client.get(URL)
        assert resp.status_code == 401


# ── POST /onboarding ───────────────────────────────────────────────────────────

class TestPostOnboarding:
    def test_creates_profile(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        resp = client_a.post(URL, json=_valid_payload())
        assert resp.status_code == 200
        body = resp.json()
        assert body["completed"] is True
        assert body["profile"]["company_name"] == "Nexbrain Ltda"

        profile = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        assert profile is not None

    def test_sets_completed_at(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        client_a.post(URL, json=_valid_payload())
        profile = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        assert profile is not None
        assert profile.completed_at is not None

    def test_second_post_updates_without_duplicating(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        client_a.post(URL, json=_valid_payload(full_name="First Name"))
        client_a.post(URL, json=_valid_payload(full_name="Updated Name"))

        profiles = list(
            db.scalars(
                select(WorkspaceOnboardingProfile).where(
                    WorkspaceOnboardingProfile.workspace_id == workspace_a.id
                )
            ).all()
        )
        assert len(profiles) == 1
        assert profiles[0].full_name == "Updated Name"

    def test_second_post_preserves_completed_at(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        client_a.post(URL, json=_valid_payload())
        profile_first = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        first_completed_at = profile_first.completed_at

        client_a.post(URL, json=_valid_payload(full_name="New Name"))
        db.refresh(profile_first)

        assert profile_first.completed_at == first_completed_at

    def test_user_id_saved_correctly(
        self, db: Session, client_a: TestClient, user_a: User, workspace_a: Workspace
    ):
        client_a.post(URL, json=_valid_payload())
        profile = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        assert profile.user_id == user_a.id

    def test_cannot_inject_workspace_id_in_body(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        fake_workspace_id = str(uuid.uuid4())
        payload = _valid_payload()
        payload["workspace_id"] = fake_workspace_id

        resp = client_a.post(URL, json=payload)
        # Either 422 (extra fields forbidden) or 200 (field ignored)
        # Either way, the saved workspace_id must be workspace_a.id
        if resp.status_code == 200:
            body = resp.json()
            assert body["profile"]["workspace_id"] == str(workspace_a.id)

    def test_cannot_inject_user_id_in_body(
        self, db: Session, client_a: TestClient, user_a: User, workspace_a: Workspace
    ):
        fake_user_id = str(uuid.uuid4())
        payload = _valid_payload()
        payload["user_id"] = fake_user_id

        resp = client_a.post(URL, json=payload)
        if resp.status_code == 200:
            body = resp.json()
            assert body["profile"]["user_id"] == str(user_a.id)

    def test_unauthenticated_returns_401(
        self, unauthenticated_client: TestClient
    ):
        resp = unauthenticated_client.post(URL, json=_valid_payload())
        assert resp.status_code == 401

    def test_updated_at_changes_on_second_post(
        self, db: Session, client_a: TestClient, workspace_a: Workspace
    ):
        client_a.post(URL, json=_valid_payload())
        profile = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        first_updated_at = profile.updated_at

        client_a.post(URL, json=_valid_payload(full_name="Changed"))
        db.refresh(profile)

        assert profile.updated_at >= first_updated_at


# ── Workspace isolation ────────────────────────────────────────────────────────

class TestOnboardingIsolation:
    def test_workspace_b_cannot_read_workspace_a_profile(
        self,
        db: Session,
        user_a: User,
        user_b: User,
        workspace_a: Workspace,
        workspace_b: Workspace,
    ):
        # Use clients sequentially to avoid dependency override conflict.
        with _make_client(db, user_a, workspace_a) as client_a:
            client_a.post(URL, json=_valid_payload())

        with _make_client(db, user_b, workspace_b) as client_b:
            resp_b = client_b.get(URL)

        assert resp_b.status_code == 200
        assert resp_b.json()["completed"] is False
        assert resp_b.json()["profile"] is None

    def test_workspace_b_post_does_not_affect_workspace_a(
        self,
        db: Session,
        user_a: User,
        user_b: User,
        workspace_a: Workspace,
        workspace_b: Workspace,
    ):
        with _make_client(db, user_a, workspace_a) as client_a:
            client_a.post(URL, json=_valid_payload(full_name="User A Name"))

        with _make_client(db, user_b, workspace_b) as client_b:
            client_b.post(URL, json=_valid_payload(full_name="User B Name"))

        profile_a = db.scalar(
            select(WorkspaceOnboardingProfile).where(
                WorkspaceOnboardingProfile.workspace_id == workspace_a.id
            )
        )
        assert profile_a.full_name == "User A Name"


# ── Validations ────────────────────────────────────────────────────────────────

class TestOnboardingValidations:
    def test_full_name_empty_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(full_name=""))
        assert resp.status_code == 422

    def test_full_name_too_short_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(full_name="A"))
        assert resp.status_code == 422

    def test_phone_too_short_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(phone="1234567"))
        assert resp.status_code == 422

    def test_phone_empty_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(phone=""))
        assert resp.status_code == 422

    def test_company_name_empty_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(company_name=""))
        assert resp.status_code == 422

    def test_company_name_too_short_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(company_name="X"))
        assert resp.status_code == 422

    def test_invalid_main_objective_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(main_objective="invalid_value"))
        assert resp.status_code == 422

    def test_invalid_company_industry_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(company_industry="unknown_industry"))
        assert resp.status_code == 422

    def test_invalid_ai_experience_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(ai_experience="expert"))
        assert resp.status_code == 422

    def test_invalid_role_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(role="janitor"))
        assert resp.status_code == 422

    def test_invalid_heard_from_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(heard_from="tiktok"))
        assert resp.status_code == 422

    def test_invalid_website_url_returns_422(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(company_website="not-a-url"))
        assert resp.status_code == 422

    def test_website_none_is_allowed(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(company_website=None))
        assert resp.status_code == 200

    def test_contact_consent_false_is_allowed(self, client_a: TestClient):
        resp = client_a.post(URL, json=_valid_payload(contact_consent=False))
        assert resp.status_code == 200
        assert resp.json()["profile"]["contact_consent"] is False

    def test_all_enum_values_accepted(self, client_a: TestClient):
        """Smoke test a representative set of valid enum values."""
        combos = [
            ("sales_qualification", "up_to_100", "never_used", "clinic_health",
             "sales", "instagram"),
            ("technical_support", "500_to_2000", "using_in_production", "ecommerce",
             "developer_it", "referral"),
            ("other", "2000_plus", "tested_tools", "other", "other", "other"),
        ]
        for obj, conv, exp, ind, role, heard in combos:
            resp = client_a.post(URL, json=_valid_payload(
                main_objective=obj,
                expected_monthly_conversations=conv,
                ai_experience=exp,
                company_industry=ind,
                role=role,
                heard_from=heard,
            ))
            combo_id = f"{obj},{conv},{exp},{ind},{role},{heard}"
            assert resp.status_code == 200, f"Failed for combo: {combo_id}"
