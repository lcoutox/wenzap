# Seed de Planos — Billing/Plans.4.1

## Para que serve

O seed popula ou atualiza planos e feature gates em qualquer ambiente de forma idempotente.

**Diferença entre migration e seed:**

| | Migration | Seed |
|---|---|---|
| Propósito | Evolui schema e dados em produção incremental | Sincroniza o estado canônico de planos/features |
| Quando roda | Uma vez por migration, em ordem | A qualquer momento, quantas vezes precisar |
| Idempotente | Por design (não reexecuta) | Sim — cria o que falta, atualiza o que existe |
| Onde usar | Produção, CI/CD via `alembic upgrade head` | Local, staging, reset de banco, Railway initial |

As migrations continuam sendo necessárias para produção já existente.
O seed é complementar para ambientes novos ou resetados.

---

## Quando rodar

- Ambiente local recém-criado
- Staging após reset de banco
- Railway (prod) na inicialização inicial
- Após mudar a matriz de features sem criar nova migration
- Qualquer ambiente onde `alembic upgrade head` não seja suficiente

---

## Comando

```bash
cd apps/api && uv run python scripts/seed_billing_plans.py
```

Saída esperada:

```
Billing plans seed completed.
```

---

## O que cria/atualiza

### Planos (`plans`)

| code | name | Preço | Status limites |
|---|---|---|---|
| starter | Free | R$0/mês | Aprovado |
| growth | Growth | R$297/mês | Aprovado |
| scale | Scale | R$299/mês | **Provisório** — aguarda fase Scale |
| enterprise | Enterprise | Negociado | Placeholder com valores altos |

> Scale e Enterprise terão fases dedicadas para definição comercial definitiva.

### Feature gates (`plan_features`)

88 linhas (4 planos × 22 feature keys). Ver matriz completa em `docs/billing/feature-gates.md`.

---

## Idempotência

O seed usa get-or-create + update:

1. Busca a linha existente.
2. Se não existe: cria.
3. Se existe: atualiza para o valor canônico.

Rodar 1 vez, 2 vezes ou 10 vezes produz o mesmo estado final.
Nunca deleta linhas existentes.

---

## Relação com migrations

```
alembic upgrade head   → aplica schema + seed mínimo de migrations
seed_billing_plans.py  → sincroniza com a matriz canônica atual
```

A migration `050_create_plan_features.py` ainda é necessária e continua intacta.
O seed não a substitui — é complementar.

---

## Arquitetura

```
apps/api/app/seeds/billing_plans.py   — função pura seed_billing_plans(db: Session)
apps/api/scripts/seed_billing_plans.py — CLI runner que chama a função
```

A função `seed_billing_plans(db)` é testável diretamente:

```python
from app.seeds.billing_plans import seed_billing_plans
seed_billing_plans(db)
db.commit()
```

---

## Histórico de mudanças relevantes no seed

| Fase       | Mudança                                  | Motivo                                                   |
|------------|------------------------------------------|----------------------------------------------------------|
| Pipeline.1 | `starter: pipelines` `False` → `True`   | Uso manual de pipeline liberado no Free; automações avançadas continuam fora do escopo do starter. Ver `docs/pipeline/conversation-pipeline-foundation.md`. |

---

## Feature key classification

| Classificação | Keys |
|---|---|
| implemented / gated | `web_widget`, `api`, `whatsapp` |
| implemented / not yet gated | `knowledge_base`, `catalog`, `inbox`, `playground`, `multiple_knowledge_bases`, `remove_powered_by` |
| implemented / gated (Free=manual, Growth=automações) | `pipelines` |
| roadmap | `instagram`, `telegram`, `slack`, `http_tools`, `follow_up`, `webhooks`, `custom_model`, `analytics`, `external_integrations`, `premium_models` |
| suspect / compatibility | `whatsapp_channel`, `api_access` (legado do dict hardcoded anterior) |
