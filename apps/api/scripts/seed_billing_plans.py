#!/usr/bin/env python
"""
CLI runner for billing plan seed.

Usage:
    cd apps/api && uv run python scripts/seed_billing_plans.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal
from app.seeds.billing_plans import seed_billing_plans


def main() -> None:
    db = SessionLocal()
    try:
        seed_billing_plans(db)
        db.commit()
        print("Billing plans seed completed.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
