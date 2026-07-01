# Growth Plan Matrix — Billing/Plans.4

## Objetivo do Growth

> Free = testar o Wenzap.
> Growth = começar a operar atendimento e vendas com agentes de IA.

O Growth é o primeiro plano pago do Wenzap. Ele libera WhatsApp, mais agentes,
mais usuários e mais créditos de IA para que uma empresa possa operar de verdade.

---

## Limites

| Recurso                  | Free         | Growth        |
|--------------------------|--------------|---------------|
| Agentes                  | 1            | **3**         |
| Usuários                 | 1            | **5**         |
| Bases de conhecimento    | 1            | **5**         |
| Fontes por base (KB)     | 10           | **100**       |
| Caracteres por fonte     | 50.000       | **100.000**   |
| Tamanho máx. por arquivo | 5 MB         | **10 MB**     |
| Itens no Catálogo        | 50           | **500**       |
| Canais totais            | 1            | **5**         |
| Créditos IA/mês          | 200          | **7.500**     |
| Conversas/mês            | métrica      | métrica       |
| Preço                    | R$0/mês      | **R$297/mês** |

> Conversas/mês não são uma cota bloqueante em nenhum plano.
> Veja [free-plan-matrix.md](./free-plan-matrix.md#conversations--metric-only-plans3).

---

## Canais liberados

| Canal             | Free | Growth |
|-------------------|------|--------|
| Web Widget        | ✅   | ✅     |
| WhatsApp Business | ❌   | ✅     |
| Instagram         | ❌   | ❌ (futuro) |
| Telegram          | ❌   | ❌ (futuro) |
| Slack             | ❌   | ❌ (futuro) |

### Por que WhatsApp entra no Growth

WhatsApp Business Platform exige aprovação da Meta, número oficial e integração
via Cloud API. É um canal de produção — não faz sentido no plano gratuito.
O Growth é o momento em que a empresa já validou o agente e quer escalar para um
canal com maior volume e engajamento.

---

## Recursos liberados no Growth

| Recurso                 | Disponível |
|-------------------------|------------|
| Web Widget              | ✅         |
| WhatsApp Business       | ✅         |
| Base de Conhecimento    | ✅         |
| Catálogo de produtos    | ✅         |
| Inbox                   | ✅         |
| Playground              | ✅         |
| Pipelines               | ✅         |
| Múltiplas KBs           | ✅         |

---

## Recursos bloqueados no Growth (Scale+)

| Recurso                    | Mínimo  | Motivo                                               |
|----------------------------|---------|------------------------------------------------------|
| Remover "Powered by Wenzap"| Scale   | Branding como camada de retorno no Free/Growth        |
| HTTP Tools                 | Scale   | Aumenta superfície de ataque; requer uso qualificado  |
| Follow-up automático       | Scale   | Automações complexas; risco de spam se mal configuradas|
| Webhooks                   | Scale   | Integrações externas avançadas para clientes maiores  |
| Modelo de IA customizado   | Scale   | Custo alto; clientes avançados                        |
| Analytics avançado         | Scale   | Relatórios de volume; clientes em escala              |

### Por que HTTP Tools / Webhooks / Follow-up ficam para Scale

Essas ferramentas exigem configuração técnica avançada e têm potencial de abuso
(envio de spam, chamadas HTTP arbitrárias, automações sem supervisão).
Reservá-las para o Scale garante que apenas clientes com maior maturidade técnica
e operacional as utilizem.

---

## Migration

Arquivo: `apps/api/alembic/versions/049_update_growth_plan.py`

Atualiza o plano `growth` existente (sem deletar ou quebrar subscriptions existentes):

```sql
UPDATE plans SET
  monthly_price_cents  = 29700,
  agents_limit         = 3,
  users_limit          = 5,
  knowledge_bases_limit = 5,
  sources_per_kb_limit = 100,
  max_source_chars     = 100000,
  max_file_size_bytes  = 10485760,
  catalog_items_limit  = 500,
  channels_limit       = 5,
  monthly_ai_credits   = 7500,
  monthly_conversations = 0
WHERE code = 'growth';
```

---

## Feature Gates (backend)

Feature gates são armazenados na tabela `plan_features` (Billing/Plans.4).
Não existem mais dicts hardcoded — as permissões vêm do banco de dados.

Arquivo: `apps/api/app/services/plan_feature_service.py`

```python
plan_allows_feature(db, plan_code, feature_key) -> bool
plan_allows_channel_type(db, plan_code, channel_type) -> bool
workspace_allows_feature(db, workspace_id, feature_key) -> bool
check_channel_type_or_402(db, workspace_id, channel_type) -> None
```

Seed canônico: `apps/api/app/seeds/billing_plans.py`
Documentação: `docs/billing/feature-gates.md`

**Nota:** `remove_powered_by` é Enterprise-only (não Growth, não Scale).

---

## Upgrade

Nesta fase não há Stripe nem checkout automático.
O upgrade é manual: cliente solicita via e-mail ou contato com a equipe Wenzap.
A UI mostra o botão "Solicitar upgrade" que abre um modal com instruções de contato.

---

## Observações

- `monthly_conversations = 0` no Growth significa "sem uso como cota" (metric only).
- Os campos `sources_per_kb_limit`, `max_source_chars`, `max_file_size_bytes` existem
  no modelo `Plan` mas ainda não são enforçados nos endpoints de sources/KB. Ficarão
  para uma fase de enforcement futura.
- O campo `channels_limit` é enforçado por `channel_service.create_channel()`.
