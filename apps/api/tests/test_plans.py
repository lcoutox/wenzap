from sqlalchemy.orm import Session

from app.models.plan import Plan


def test_list_plans(client_a, db: Session, plan: Plan):
    response = client_a.get("/plans")
    assert response.status_code == 200
    plans = response.json()
    assert len(plans) >= 1
    codes = [p["code"] for p in plans]
    assert plan.code in codes


def test_list_plans_returns_only_public_plans(client_a, db: Session, feature_matrix):
    """GET /plans must never expose scale or enterprise."""
    response = client_a.get("/plans")
    assert response.status_code == 200
    codes = [p["code"] for p in response.json()]
    assert "starter" in codes
    assert "growth" in codes
    assert "scale" not in codes
    assert "enterprise" not in codes


def test_list_plans_sorted_by_sort_order(client_a, db: Session, feature_matrix):
    response = client_a.get("/plans")
    assert response.status_code == 200
    codes = [p["code"] for p in response.json()]
    assert codes == ["starter", "growth"]


def test_plan_out_includes_visibility_fields(client_a, db: Session, plan: Plan):
    response = client_a.get("/plans")
    assert response.status_code == 200
    starter = next(p for p in response.json() if p["code"] == "starter")
    assert starter["is_public"] is True
    assert starter["sort_order"] == 10


def test_get_current_plan(client_a, subscription_a, plan: Plan):
    response = client_a.get("/workspaces/current/plan")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["plan"]["code"] == plan.code


def test_get_current_usage_zero(client_a, workspace_a, subscription_a):
    response = client_a.get("/workspaces/current/usage")
    assert response.status_code == 200
    data = response.json()
    assert data["ai_credits_used"] == 0
    assert data["conversations_count"] == 0
    assert data["messages_count"] == 0
