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

### O que ficou para fase futura

- Execução de webhooks ao mover conversa de etapa
- Movimentação automática por condição de entrada (`entry_condition`)
- Automação por tempo de permanência (`stay_limit`)
- Disparos/follow-up automático ao entrar/sair de etapa
- Campanhas vinculadas a pipeline
- Relatórios e analytics de pipeline
- Drag-and-drop de cards

---

## Pipeline no plano Free (starter)

A partir de Pipeline.1, o plano Free inclui acesso a pipelines manuais.

### O que o Free pode fazer

- Criar pipelines
- Criar etapas
- Adicionar conversas manualmente ao pipeline
- Mover conversas manualmente entre etapas
- Configurar pipeline padrão no agente (se dentro do limite `pipelines_limit`)
- Usar `extra_prompt` por etapa

### O que o Free **não** inclui

- Execução de webhooks de etapa (campo salvo, mas não executado)
- Movimentação automática por condição ou tempo
- Automações de follow-up vinculadas a pipeline
- Analytics de pipeline (fase futura, Growth+)

A distinção é: **ação manual = Free**, **automação = Growth+**.

Esta decisão foi tomada em Pipeline.1 ao mudar `("starter", "pipelines", False)` para `True` no seed.
O intent é incentivar adoção no Free com as funcionalidades manuais, sem liberar automações que aumentam custo de infra e suporte.

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
| entry_condition      | TEXT         | Condição futura para entrada automática          |
| extra_prompt         | TEXT         | Texto injetado no system prompt quando conversa está nesta etapa |
| is_required          | BOOLEAN      |                                                  |
| is_removal_stage     | BOOLEAN      | Etapa de saída do pipeline                       |
| request_contact_info | BOOLEAN      |                                                  |
| stay_limit_enabled   | BOOLEAN      | Futura automação por tempo                       |
| stay_limit_minutes   | INTEGER      |                                                  |
| webhook_url          | VARCHAR(1000)| Salvo, não executado nesta fase                  |
| webhook_auth_header  | VARCHAR(500) | Salvo, não executado nesta fase                  |

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

PATCH  /agents/{agent_id}/pipeline-settings
```

Todos os endpoints retornam 402 se o workspace não tem a feature `pipelines` habilitada.

---

## Migrations

| Revisão | Arquivo                           | Descrição                                |
|---------|-----------------------------------|------------------------------------------|
| 055     | `055_pipeline_foundation.py`      | Cria pipelines, pipeline_stages, pipeline_entries |
| 056     | `056_agent_default_pipeline.py`   | Adiciona default_pipeline_id/stage_id em agents |
