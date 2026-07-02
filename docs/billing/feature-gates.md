# Feature Gates — Billing/Plans.4

## Por que feature gates foram migrados para banco

Antes desta fase, as permissões de recursos eram controladas por dicionários hardcoded
em `plan_feature_service.py`:

```python
_FEATURE_MIN_PLAN = { "whatsapp_channel": "growth", "remove_powered_by": "scale", ... }
_PLAN_CHANNEL_TYPES = { "starter": {"web_widget", "api"}, ... }
```

Problemas do modelo anterior:

1. Alterar permissões exigia deploy de código.
2. Não era possível diferenciar comportamento por workspace sem refatoração grande.
3. O padrão não escalava para `workspace_entitlements` ou overrides administrativos.
4. Feature keys ficavam espalhadas sem centralização.

A migração para banco permite:

- Alterar a matriz de permissões sem deploy.
- Preparar a base para workspace-level entitlements (fase futura).
- Auditabilidade (quem mudou, quando, qual feature).

---

## Tabela `plan_features`

```sql
CREATE TABLE plan_features (
    id          UUID PRIMARY KEY,
    plan_code   VARCHAR NOT NULL,
    feature_key VARCHAR NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL,
    UNIQUE (plan_code, feature_key)
);
```

**Campos:**

| Campo       | Tipo    | Descrição                                   |
|-------------|---------|---------------------------------------------|
| id          | UUID    | PK                                          |
| plan_code   | string  | Código do plano (e.g. "starter", "growth")  |
| feature_key | string  | Chave da feature (ver abaixo)               |
| enabled     | boolean | true = liberado, false = bloqueado          |
| created_at  | datetime| Data de criação da linha                    |

**Nota:** `plan_code` possui FK referenciando `plans.code` (UNIQUE) com `ON DELETE CASCADE`.
A FK garante integridade referencial sem acoplamento ao `plans.id` interno.

---

## Feature keys

Constante centralizada em `plan_feature_service.py`:

```python
FEATURE_KEYS = frozenset([
    # Tipos de canal
    "web_widget", "api", "whatsapp", "instagram", "telegram", "slack",
    # Recursos gerais
    "knowledge_base", "catalog", "inbox", "playground",
    "pipelines", "multiple_knowledge_bases", "whatsapp_channel", "api_access",
    "http_tools", "follow_up", "webhooks", "custom_model",
    "analytics", "external_integrations", "remove_powered_by", "premium_models",
])
```

---

## Matriz de features por plano

| Feature                  | starter | growth | scale | enterprise |
|--------------------------|:-------:|:------:|:-----:|:----------:|
| web_widget               | ✅      | ✅     | ✅    | ✅         |
| api                      | ✅      | ✅     | ✅    | ✅         |
| knowledge_base           | ✅      | ✅     | ✅    | ✅         |
| inbox                    | ✅      | ✅     | ✅    | ✅         |
| playground               | ✅      | ✅     | ✅    | ✅         |
| whatsapp                 | ❌      | ✅     | ✅    | ✅         |
| whatsapp_channel         | ❌      | ✅     | ✅    | ✅         |
| catalog                  | ✅      | ✅     | ✅    | ✅         |
| pipelines                | ✅      | ✅     | ✅    | ✅         |
| multiple_knowledge_bases | ❌      | ✅     | ✅    | ✅         |
| api_access               | ❌      | ✅     | ✅    | ✅         |
| instagram                | ❌      | ❌     | ✅    | ✅         |
| telegram                 | ❌      | ❌     | ✅    | ✅         |
| http_tools               | ❌      | ❌     | ✅    | ✅         |
| follow_up                | ❌      | ❌     | ✅    | ✅         |
| webhooks                 | ❌      | ❌     | ✅    | ✅         |
| custom_model             | ❌      | ❌     | ✅    | ✅         |
| analytics                | ❌      | ❌     | ✅    | ✅         |
| external_integrations    | ❌      | ❌     | ✅    | ✅         |
| premium_models           | ❌      | ❌     | ✅    | ✅         |
| remove_powered_by        | ❌      | ❌     | ❌    | ✅         |
| slack                    | ❌      | ❌     | ❌    | ✅         |

---

## Regra default deny

Se uma linha não existe em `plan_features`:

- `plan_allows_feature(db, plan_code, feature_key)` → **`False`**
- `plan_allows_channel_type(db, plan_code, channel_type)` → **`False`**

Se o workspace não tem subscription ativa, `get_workspace_plan_code` retorna `"starter"`.
Como `starter` tem features explicitamente configuradas, o comportamento é previsível.

**Ausência de configuração = bloqueado.** Nunca `True` por ausência.

---

## Diferença entre limites numéricos e features booleanas

| Tipo            | Onde fica    | Exemplo                  | Enforcement           |
|-----------------|-------------|--------------------------|----------------------|
| Limite numérico | `plans`     | `agents_limit = 3`        | `check_agents_limit` |
| Feature booleana| `plan_features` | `whatsapp = true/false` | `plan_allows_feature` |

Limites numéricos controlam **quantidades** (ex: quantos agentes, KBs, canais).
Features booleanas controlam **acesso** (ex: pode usar WhatsApp ou não).

---

## Por que ainda não há `workspace_entitlements`

`workspace_entitlements` permitiria sobrescrever o comportamento padrão do plano
por workspace — ex: liberar `remove_powered_by` para um workspace específico no plano Growth.

Essa funcionalidade foi intencionalmente adiada porque:

1. Exige backoffice administrativo para gerenciar overrides.
2. Aumenta a complexidade do serviço de gates.
3. Não é necessária na fase atual (MVP com dois planos públicos).

Quando implementado, `workspace_entitlements` terá prioridade sobre `plan_features`.

---

## API — exposição de features

Nesta fase, as features não são expostas via API para o frontend.

O frontend (`apps/web/src/lib/plan.ts`) mantém lógica hardcoded apenas para fins de
**display** (mostrar/ocultar elementos de UI). O **enforcement real** sempre ocorre no backend.

Em fase futura, considerar endpoint:

```json
GET /me/subscription
{
  "plan": { "code": "starter", "name": "Free" },
  "features": { "web_widget": true, "whatsapp": false }
}
```

---

## Funções do serviço

Arquivo: `apps/api/app/services/plan_feature_service.py`

```python
plan_allows_feature(db, plan_code, feature_key) -> bool
plan_allows_channel_type(db, plan_code, channel_type) -> bool
workspace_allows_feature(db, workspace_id, feature_key) -> bool
workspace_allows_channel_type(db, workspace_id, channel_type) -> bool
check_channel_type_or_402(db, workspace_id, channel_type) -> None  # raises 402
check_users_limit(db, workspace_id) -> None  # raises 402
get_workspace_plan_code(db, workspace_id) -> str
```

---

## Escopo de features com acesso parcial por plano

Algumas features estão habilitadas no Free (`starter`) mas com escopo limitado.
A gate booleana libera o acesso; a distinção de escopo é documental e de UI —
automações avançadas não são executadas no backend nesta fase.

### `pipelines` — Free inclui uso manual; automações ficam para Growth+

O plano Free pode:
- criar pipelines e etapas
- adicionar conversas manualmente
- mover conversas entre etapas manualmente
- configurar pipeline padrão no agente

O plano Free **não inclui**:
- execução de webhooks de etapa
- movimentação automática por condição de entrada
- automação por tempo de permanência (stay_limit)
- follow-up automático ao entrar/sair de etapa

Essa distinção foi estabelecida em Pipeline.1.
Ver: `docs/pipeline/conversation-pipeline-foundation.md`

---

## O que fica para fase futura

- `workspace_entitlements` — overrides por workspace
- Backoffice para gerenciar `plan_features` e entitlements sem deploy
- Exposição de features via API para o frontend
- Cache de feature gates (redis ou in-memory com TTL) para reduzir round-trips
- Audit log de mudanças em `plan_features`
- `limit_value` e `metadata_json` na tabela (campos opcionais para futuras gates complexas)
