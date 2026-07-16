"""update plan prices for Stripe launch

Revision ID: 064
Revises: 063
Create Date: 2026-07-16

007_seed_plans set placeholder launch prices (Growth R$99, Scale R$299,
Enterprise free). This migration sets the real prices used to configure
the matching Stripe Price objects (see STRIPE_PRICE_ID_* env vars).
"""

import sqlalchemy as sa
from alembic import op

revision = "064"
down_revision = "063"
branch_labels = None
depends_on = None

_PRICES_CENTS = {
    "starter": 0,
    "growth": 24_700,
    "scale": 58_700,
    "enterprise": 99_700,
}

_PREVIOUS_PRICES_CENTS = {
    "starter": 0,
    "growth": 9_900,
    "scale": 29_900,
    "enterprise": 0,
}


def upgrade() -> None:
    for code, cents in _PRICES_CENTS.items():
        op.execute(
            sa.text("UPDATE plans SET monthly_price_cents = :cents WHERE code = :code").bindparams(
                cents=cents, code=code
            )
        )


def downgrade() -> None:
    for code, cents in _PREVIOUS_PRICES_CENTS.items():
        op.execute(
            sa.text("UPDATE plans SET monthly_price_cents = :cents WHERE code = :code").bindparams(
                cents=cents, code=code
            )
        )
