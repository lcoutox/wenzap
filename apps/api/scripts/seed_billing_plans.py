#!/usr/bin/env python3
"""
Seed script to create default billing plans in the database.

Usage:
    python scripts/seed_billing_plans.py
"""

import os
import sys
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models.plan import Plan

DATABASE_URL = os.getenv("DATABASE_URL")

def seed_plans():
    """Create default billing plans."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check if plans already exist
        existing = session.query(Plan).count()
        if existing > 0:
            print(f"✓ Plans already exist ({existing} plans found), skipping seed")
            return

        plans = [
            Plan(
                id=uuid.uuid4(),
                code="starter",
                name="Starter",
                description="Para começar com IA",
                monthly_price_cents=0,  # Free
                features=[
                    "Até 1 agente",
                    "Base de conhecimento limitada",
                    "Canal: Widget Web",
                    "100 mensagens/mês",
                    "Suporte comunitário",
                ],
                is_active=True,
            ),
            Plan(
                id=uuid.uuid4(),
                code="growth",
                name="Growth",
                description="Para empresas em crescimento",
                monthly_price_cents=29700,  # R$ 297.00
                features=[
                    "Até 10 agentes",
                    "Base de conhecimento ilimitada",
                    "Canais: Widget Web, WhatsApp, API",
                    "10.000 mensagens/mês",
                    "Suporte prioritário via email",
                    "Acesso a integrações",
                ],
                is_active=True,
            ),
            Plan(
                id=uuid.uuid4(),
                code="scale",
                name="Scale",
                description="Para operações em escala",
                monthly_price_cents=99700,  # R$ 997.00
                features=[
                    "Agentes ilimitados",
                    "Base de conhecimento ilimitada",
                    "Todos os canais",
                    "100.000 mensagens/mês",
                    "Suporte prioritário 24/7",
                    "Acesso a todas as integrações",
                    "API custom",
                    "SLA garantido",
                ],
                is_active=True,
            ),
        ]

        for plan in plans:
            session.add(plan)
            print(f"✓ Created plan: {plan.name} ({plan.code}) - R${plan.monthly_price_cents/100:.2f}")

        session.commit()
        print("\n✅ Billing plans seeded successfully")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding plans: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    seed_plans()
