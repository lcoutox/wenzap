# Conversation Pipeline Foundation — Pipeline.1

## O que é

Pipeline é um quadro Kanban para organizar conversas por etapas dentro de um workspace.

Permite que equipes acompanhem o progresso de conversas ao longo de um fluxo definido —
ex: Novo Lead → Qualificação → Proposta → Fechado.

Pipelines organizam **conversas**, não contatos. Um contato pode ter várias conversas em
diferentes pipelines.

---

## Conceitos

| Termo         | Definição                                                             |
|---------------|-----------------------------------------------------------------------|
| Pipeline      | Quadro com etapas. Um workspace pode ter múltiplos pipelines.         |
| Stage (Etapa) | Coluna dentro de um pipeline, com posição e configurações opcionais.  |
| Entry         | Associação de uma conversa a um pipeline/etapa. Uma conversa pode ter no máximo uma entry por pipeline. |

---

## Escopo desta fase

### O que foi implementado

- Criação e edição de pipelines e etapas via UI e API
- Board Kanban com colunas por etapa
- Adicionar conversas manualmente ao pipeline
- Mover conversas entre etapas manualmente
- Configurar pipeline/etapa padrão por agente → novas conversas criadas por esse agente entram automaticamente na etapa configurada
- `extra_prompt` por etapa injetado no context builder do agente quando a conversa está ativa naquela etapa
- Suporte a campos avançados de etapa salvos no banco (webhook_url, stay_limit, etc.) — **não executados nesta fase**

### Pipeline.2 (2026-07-16) — automação completa

Todos os itens que ficaram "salvo, não executado" em Pipeline.1 agora funcionam de verdade.
Ver PRD completo em `docs/pipeline/pipeline-full-automation-prd.md`.

- ✅ Webhook de etapa dispara de verdade (`STAGE_ENTERED`, com proteção contra SSRF)
- ✅ `entry_condition` avaliada automaticamente por IA a cada mensagem — move a conversa sozinha
  quando a condição descrita em linguagem natural é satisfeita (sem tool-calling — é uma chamada
  de classificação separada, mesmo truque que o FluxVolt usa)
- ✅ `stay_limit` — auto-avanço por tempo de permanência via sweep periódico (não uma thread por
  entry — ver seção "Scheduler" abaixo)
- ✅ Ações automáticas ao entrar na etapa: mudar status da conversa, atribuir a um operador,
  ligar/desligar a IA (`on_enter_conversation_status`/`on_enter_assigned_user_id`/`on_enter_ai_enabled`)
- ✅ `is_removal_stage` marca a entry como `inactive` de verdade (efeito manual, disponível em
  qualquer plano — não é "automação")
- ✅ `request_contact_info` injeta pedido de dados faltantes no prompt do agente
- ✅ Histórico de etapas por entry (`pipeline_entry_stage_history`) + métricas (tempo médio por
  etapa, taxa de conversão) — `GET /pipelines/{id}/metrics`
- ✅ Drag-and-drop de cards entre etapas e de etapas para reordenar (`@dnd-kit`)
- ✅ Bug corrigido: `pipelines_limit` do plano agora é aplicado (`create_pipeline` retornava 201
  ilimitadamente antes)

### O que ainda fica pra depois (backlog, não é mais "campo fantasma")

- Templates de pipeline (duplicar um pipeline existente)
- API pública de criação de conversa em etapa específica
- Tags/labels em cards
- Notificação SMS (sem provedor integrado hoje)

---

## Scheduler do stay_limit

Não é uma thread por entry (um `stay_limit` é medido em minutos/horas — uma thread dormindo
morreria silenciosamente em todo redeploy do Railway). É um **sweep periódico** (a cada 60s,
iniciado no lifespan do FastAPI em `main.py`) que varre entries elegíveis e move via
compare-and-swap (`UPDATE ... WHERE stage_id = <etapa lida>`) — seguro mesmo se o app escalar
para múltiplas réplicas sem lock distribuído, porque uma segunda réplica que tente mover a mesma
entry simplesmente casa 0 linhas e não faz nada.

MVP-adequado para o deploy atual (réplica única). Se escalar, migrar para Celery Beat/cron
externo — o compare-and-swap já deixa essa migração seguro de fazer depois.

---

## Pipeline no plano Free (starter)

A partir de Pipeline.1, o plano Free inclui acesso a pipelines manuais.

### O que o Free pode fazer

- Criar pipelines (respeitando `pipelines_limit` do plano)
- Criar etapas
- Adicionar conversas manualmente ao pipeline
- Mover conversas manualmente entre etapas (clique ou drag-and-drop)
- Configurar pipeline padrão no agente (se dentro do limite `pipelines_limit`)
- Usar `extra_prompt` por etapa
- Marcar etapa como etapa de saída (`is_removal_stage`) — efeito manual, não é automação

### O que o Free **não** inclui (feature `pipeline_automations`, Scale+)

- Execução de webhooks de etapa
- Movimentação automática por condição (`entry_condition`) ou tempo (`stay_limit`)
- Ações automáticas ao entrar na etapa (status/assignee/IA)
- Analytics/métricas de pipeline (`GET /pipelines/{id}/metrics` — endpoint não é gated pela
  feature, mas fica pouco útil sem automação; avaliar se deve virar Growth+ separadamente)

A distinção continua: **ação manual = Free**, **automação = Scale+**.

Esta decisão foi tomada em Pipeline.1 ao mudar `("starter", "pipelines", False)` para `True` no seed,
e mantida em Pipeline.2 via a feature `pipeline_automations` (`False` em starter/growth, `True` em
scale/enterprise). O intent é incentivar adoção no Free/Growth com as funcionalidades manuais, sem
liberar automações que aumentam custo de infra (chamadas de IA extras, disparo de webhook) e suporte.

---

## Tabelas

### `pipelines`

| Coluna                       | Tipo         | Descrição                              |
|------------------------------|--------------|----------------------------------------|
| id                           | UUID PK      |                                        |
| workspace_id                 | UUID FK      | Isolamento de tenant                   |
| name                         | VARCHAR(255) |                                        |
| description                  | TEXT         | Opcional                               |
| is_active                    | BOOLEAN      | Soft-delete via flag                   |
| show_inactive_conversations  | BOOLEAN      | Exibir conversas closed no board       |
| created_at / updated_at      | TIMESTAMPTZ  |                                        |

### `pipeline_stages`

| Coluna               | Tipo         | Descrição                                        |
|----------------------|--------------|--------------------------------------------------|
| id                   | UUID PK      |                                                  |
| workspace_id         | UUID FK      |                                                  |
| pipeline_id          | UUID FK      |                                                  |
| name                 | VARCHAR(255) |                                                  |
| description          | TEXT         |                                                  |
| position             | INTEGER      | Ordem das colunas no board                       |
| assigned_agent_id    | UUID FK      | Agente padrão desta etapa (opcional)             |
| entry_condition      | TEXT         | Condição em linguagem natural — avaliada por IA a cada mensagem (Pipeline.2, Scale+) |
| extra_prompt         | TEXT         | Texto injetado no system prompt quando conversa está nesta etapa |
| is_required          | BOOLEAN      |                                                  |
| is_removal_stage     | BOOLEAN      | Etapa de saída — marca a entry como `inactive` ao entrar (qualquer plano) |
| request_contact_info | BOOLEAN      | Injeta pedido de dados de contato faltantes no prompt (qualquer plano) |
| stay_limit_enabled   | BOOLEAN      | Auto-avanço por tempo de permanência (Pipeline.2, Scale+) |
| stay_limit_minutes   | INTEGER      |                                                  |
| webhook_url          | VARCHAR(1000)| Dispara `STAGE_ENTERED` ao entrar na etapa (Pipeline.2, Scale+, validado contra SSRF) |
| webhook_auth_header  | VARCHAR(500) | Enviado como header `Authorization` no disparo   |
| on_enter_conversation_status | VARCHAR(32) | Muda `Conversation.status` ao entrar (Pipeline.2, Scale+, opcional) |
| on_enter_assigned_user_id    | UUID FK     | Atribui a conversa a um operador ao entrar (Pipeline.2, Scale+, opcional) |
| on_enter_ai_enabled          | BOOLEAN     | Liga/desliga a IA da conversa ao entrar (Pipeline.2, Scale+, opcional) |

### `pipeline_entries`

| Coluna              | Tipo        | Descrição                                      |
|---------------------|-------------|------------------------------------------------|
| id                  | UUID PK     |                                                |
| workspace_id        | UUID FK     |                                                |
| pipeline_id         | UUID FK     |                                                |
| stage_id            | UUID FK     |                                                |
| conversation_id     | UUID FK     | UNIQUE com pipeline_id (1 entry por conversa/pipeline) |
| contact_id          | UUID FK     | Desnormalizado para exibição no board          |
| assigned_agent_id   | UUID FK     |                                                |
| status              | VARCHAR(32) | `active` / `inactive` / `removed`             |
| entered_stage_at    | TIMESTAMPTZ | Timestamp da última movimentação de etapa      |

### `pipeline_entry_stage_history` (Pipeline.2)

Uma linha por etapa que a entry passou. `exited_at` é `NULL` enquanto a entry está na etapa
(a linha "atual"). Alimenta o endpoint de histórico e as métricas.

| Coluna               | Tipo         | Descrição                                        |
|----------------------|--------------|--------------------------------------------------|
| id                   | UUID PK      |                                                  |
| workspace_id         | UUID FK      |                                                  |
| entry_id             | UUID FK      | `pipeline_entries.id`, cascade delete            |
| stage_id             | UUID FK      | `pipeline_stages.id`, `SET NULL` se a etapa for excluída |
| stage_name_snapshot  | VARCHAR(255) | Preserva o nome mesmo se a etapa for renomeada/excluída depois |
| entered_at           | TIMESTAMPTZ  |                                                  |
| exited_at            | TIMESTAMPTZ  | `NULL` enquanto ativa nesta etapa                |
| moved_by             | VARCHAR(32)  | `initial` / `manual` / `entry_condition` / `stay_limit` |

---

## Mudanças em tabelas existentes

### `agents`

Adicionados em Migration 056:

| Coluna                   | Tipo    | Descrição                                         |
|--------------------------|---------|---------------------------------------------------|
| default_pipeline_id      | UUID FK | Pipeline onde novas conversas deste agente entram |
| default_pipeline_stage_id| UUID FK | Etapa inicial dentro do pipeline acima            |

---

## Fluxo de criação automática de entry

Quando uma conversa é criada em qualquer um dos 3 fluxos (widget, WhatsApp, manual),
`ensure_conversation_pipeline_entry` é chamado após o flush:

```
conversation criada
  → agent.default_pipeline_id definido?
    → sim → cria PipelineEntry(pipeline_id, stage_id, conversation_id, contact_id)
    → não → noop
```

A função usa `db.flush()`, não `db.commit()`, para participar da mesma transação.

---

## extra_prompt por etapa

Em `conversation_context_builder.build_conversation_context()`, antes de retornar:

1. Busca `PipelineEntry` ativo da conversa
2. Se existe entry com `stage_id`, busca o `PipelineStage`
3. Se `stage.extra_prompt` não é vazio, concatena ao system prompt:

```
## INSTRUÇÕES DESTA ETAPA

{extra_prompt}
```

Isso permite que cada etapa do pipeline instrua o agente de forma diferente —
ex: etapa "Qualificação" pode ter prompt focado em qualificar interesse, enquanto
"Proposta" tem prompt focado em apresentar o produto.

No mesmo ponto, se `stage.request_contact_info` estiver ativo e o contato ainda não tiver
nome/e-mail/telefone preenchidos, uma segunda instrução é concatenada (`## COLETA DE DADOS`)
pedindo ao agente que colete o que falta — reaproveita o mesmo mecanismo de injeção em vez de
um fluxo de coleta estruturada separado (Pipeline.2).

---

## Endpoints da API

```
GET    /pipelines
POST   /pipelines
GET    /pipelines/{pipeline_id}
PATCH  /pipelines/{pipeline_id}
DELETE /pipelines/{pipeline_id}                       (soft: is_active=False)

GET    /pipelines/{pipeline_id}/stages
POST   /pipelines/{pipeline_id}/stages
PATCH  /pipelines/{pipeline_id}/stages/{stage_id}
DELETE /pipelines/{pipeline_id}/stages/{stage_id}
POST   /pipelines/{pipeline_id}/stages/reorder

GET    /pipelines/{pipeline_id}/entries
POST   /pipelines/{pipeline_id}/entries
PATCH  /pipelines/{pipeline_id}/entries/{entry_id}/move
DELETE /pipelines/{pipeline_id}/entries/{entry_id}    (soft: status=removed)
GET    /pipelines/{pipeline_id}/entries/{entry_id}/history   (Pipeline.2)

GET    /pipelines/{pipeline_id}/metrics                      (Pipeline.2)

PATCH  /agents/{agent_id}/pipeline-settings
```

Todos os endpoints retornam 402 se o workspace não tem a feature `pipelines` habilitada.
Automações (webhook, entry_condition, stay_limit, ações de entrada) exigem também a feature
`pipeline_automations` — sem ela, o efeito automático é ignorado silenciosamente (não retorna erro,
já que o CRUD de configuração continua disponível em qualquer plano).

---

## Migrations

| Revisão | Arquivo                                    | Descrição                                |
|---------|---------------------------------------------|------------------------------------------|
| 055     | `055_pipeline_foundation.py`                | Cria pipelines, pipeline_stages, pipeline_entries |
| 056     | `056_agent_default_pipeline.py`             | Adiciona default_pipeline_id/stage_id em agents |
| 065     | `065_pipeline_stage_entry_actions.py`       | Adiciona on_enter_conversation_status/assigned_user_id/ai_enabled em pipeline_stages |
| 066     | `066_pipeline_entry_stage_history.py`       | Cria pipeline_entry_stage_history |
