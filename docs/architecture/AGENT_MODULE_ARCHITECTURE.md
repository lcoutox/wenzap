# Agent Module Architecture

**Status:** Proposal — awaiting approval before any implementation  
**Phase context:** After Phase 2.2 (AI Model Catalog). Before Phase 3 (Playground).  
**Last updated:** 2026-06-22

---

## 1. Visão arquitetural

Um `Agent` no Nexbrain não é apenas um cadastro. É um workspace operacional — uma entidade viva que recebe mensagens, executa ações, consome créditos, se conecta a canais e pode ser supervisionada por humanos.

A tela de agente no produto final terá seções distintas:

```
Agent Workspace
├── Chat           — testar o agente (Playground)
├── Implantar      — canais, widget, API key
└── Configurações
    ├── Geral      — nome, descrição, status
    ├── Prompt     — system prompt, persona, estilo
    ├── Modelo     — provider, temperatura, contexto
    ├── Ferramentas — knowledge base, ações, webhooks
    ├── Segurança  — domínios, rate limit, moderação
    ├── Webhooks   — outbound events
    └── Avançado   — JSON mode, idioma, timeout, markdown
```

Cada uma dessas seções tem ciclo de vida, frequência de edição e escopo de dados distintos. Colocar tudo em `agents` cria uma tabela que nunca para de crescer e que mistura responsabilidades irreconciliáveis.

A proposta central é: **`agents` deve permanecer pequena, estável e focada na identidade e status do agente**. As configurações de cada dimensão devem morar em tabelas satélites ligadas por `agent_id`.

---

## 2. Estado atual

### Tabela `agents`

```
id                  UUID PK
workspace_id        UUID FK → workspaces (CASCADE)
name                VARCHAR(255)
description         TEXT nullable
status              VARCHAR(50)  -- draft | active | inactive | archived
system_prompt       TEXT nullable
persona             TEXT nullable
ai_model_id         UUID FK → ai_models (SET NULL) nullable
model_name          VARCHAR(200) -- snapshot do model_name no momento da seleção
temperature         NUMERIC(3,2) default 0.70
created_by_user_id  UUID FK → users (SET NULL) nullable
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

### Tabela `ai_model_providers`

```
id, code, name, description, logo_url, is_active, created_at, updated_at
```

### Tabela `ai_models`

```
id, provider_id, code, display_name, description, model_name,
credits_per_message, min_plan_code, context_window_tokens,
is_default, is_recommended, is_featured, is_active, sort_order,
supports_vision, supports_tools, supports_reasoning, supports_code,
created_at, updated_at
```

### O que já funciona bem

- Tenant isolation: `workspace_id` em todos os recursos, sempre resolvido via auth context.
- RBAC: owner/admin/member/viewer aplicado no router.
- Status lifecycle: draft → active → inactive → archived com validações.
- Plan limits: agentes bloqueados por `agents_limit` no plano.
- AI Model catalog: `ai_model_id` referencia catálogo; `model_name` como snapshot para calls LLM.
- Créditos por modelo: `credits_per_message` + `min_plan_code` por modelo.

### Lacunas atuais

- `system_prompt`, `persona` e `temperature` dentro de `agents` — campos de configuração misturados com campos de identidade.
- Nenhuma entidade para canais, ferramentas, webhooks ou segurança.
- Nenhum histórico de prompts ou versioning.
- `model_name` como snapshot simples, sem rastreio de mudanças.

---

## 3. Problema que queremos evitar

### Tabela gigante

Se cada nova feature de configuração for um campo em `agents`, em 12 meses a tabela terá 40+ colunas. Isso dificulta leitura, indexação seletiva, migrations parciais e raciocínio sobre o que uma linha representa.

Exemplo de crescimento descontrolado:

```
agents
  id, workspace_id, name, description, status, ...
  system_prompt, persona, response_style, language_mode,
  ai_model_id, model_name, temperature, context_window_tier,
  widget_enabled, public_slug, public_page_enabled,
  kb_id_1, kb_id_2, kb_id_3,
  webhook_url, webhook_secret, webhook_events,
  allowed_domains, rate_limit_per_minute, moderation_enabled,
  json_mode, markdown_output, auto_language, ignore_images,
  inactivity_timeout, inactivity_message, timezone, ...
```

Isso não é hiperbólico — é o caminho natural se não houver disciplina arquitetural.

### Acoplamento entre dimensões independentes

Prompt, modelo, segurança e canais têm frequências de edição diferentes, owners diferentes (prompt = operador; security = admin) e requisitos de versionamento diferentes. Misturá-los em uma tabela gera um `PATCH /agents/{id}` que pode mudar qualquer coisa, sem rastreabilidade.

### Dificuldade de versionar configurações

Prompt versioning (guardar histórico de prompts anteriores) é uma feature que vai existir no Nexbrain. Ela é impossível de implementar de forma limpa se o prompt viver diretamente em `agents`.

### Migrations brutas no futuro

Adicionar `NOT NULL` columns a uma tabela com 100k linhas exige backfill. É muito mais seguro adicionar esses campos em tabelas novas com `DEFAULT` ou `nullable` e backfill incremental.

### Dificuldade de autorizar granularmente

No futuro, um `member` poderá editar o prompt mas não as configurações de segurança ou webhooks. Isso é difícil de impor se tudo está no mesmo recurso `PATCH /agents/{id}`.

---

## 4. Proposta de entidades futuras

### `agent_prompt_settings`

**Propósito:** Separar toda a configuração de geração de texto da identidade do agente.

```
agent_id            UUID FK → agents (CASCADE) PK
system_prompt       TEXT nullable
persona             TEXT nullable
response_style      VARCHAR(50) nullable  -- concise | detailed | conversational
language_mode       VARCHAR(20) nullable  -- auto | pt | en | es
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

**Por que separar:** `system_prompt` e `persona` são os campos mais editados do produto. Vão ganhar versioning, diff visual e templates. Manter em `agents` torna isso mais difícil. A relação é 1:1 com o agente.

**Migração:** criar tabela, backfill com dados atuais de `agents`, manter leitura transparente no service.

---

### `agent_model_settings`

**Propósito:** Configurações de geração de resposta pelo modelo.

```
agent_id                UUID FK → agents (CASCADE) PK
ai_model_id             UUID FK → ai_models (SET NULL) nullable
model_name              VARCHAR(200)  -- snapshot
temperature             NUMERIC(3,2) default 0.70
max_tokens              INTEGER nullable
context_window_policy   VARCHAR(20) default 'auto'  -- auto | fixed | summarize
created_at              TIMESTAMPTZ
updated_at              TIMESTAMPTZ
```

**Por que separar:** Temperatura e modelo são configurações técnicas que merecem histórico e validação de plano. Separar permite, no futuro, logs de "modelo alterado de X para Y em DD/MM" sem poluir o audit log geral do agente. A relação é 1:1.

**Sobre `ai_model_id` atual em `agents`:** recomendamos mover para `agent_model_settings` quando essa tabela for criada. Enquanto isso, manter em `agents` com `model_name` como snapshot.

---

### `agent_security_settings`

**Propósito:** Controles de acesso, moderação e visibilidade do agente.

```
agent_id                    UUID FK → agents (CASCADE) PK
public_access_enabled       BOOLEAN default false
include_sources_enabled     BOOLEAN default false
allowed_domains_enabled     BOOLEAN default false
allowed_domains             TEXT[] nullable
rate_limit_per_minute       INTEGER nullable
moderation_enabled          BOOLEAN default false
moderation_message          TEXT nullable
feedback_logging_enabled    BOOLEAN default true
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
```

**Por que separar:** Configurações de segurança têm owner diferente (admin/owner) e frequência de edição diferente. São requisitos de compliance e auditoria que merecem tabela própria. Relação 1:1.

**Quando criar:** Phase 5+ (Widget/Deploy). Não criar antes de precisar.

---

### `agent_deployment_settings`

**Propósito:** Configurações de onde e como o agente é publicado.

```
agent_id            UUID FK → agents (CASCADE) PK
public_slug         VARCHAR(100) unique nullable
widget_enabled      BOOLEAN default false
public_page_enabled BOOLEAN default false
api_access_enabled  BOOLEAN default false
created_at          TIMESTAMPTZ
updated_at          TIMESTAMPTZ
```

**Por que separar:** Deploy é uma dimensão completamente diferente de identidade ou prompt. Um agente pode existir sem estar implantado. Separar permite a tela "Implantar" ter endpoints específicos sem misturar com configurações de prompt. Relação 1:1.

**Quando criar:** Phase 5 (Widget/Deploy).

---

### `agent_channels`

**Propósito:** Canais de comunicação onde o agente está ativo.

```
id              UUID PK
agent_id        UUID FK → agents (CASCADE)
workspace_id    UUID FK → workspaces (CASCADE)  -- tenant safety
channel_type    VARCHAR(50)  -- website | whatsapp | instagram | telegram | slack | api
is_enabled      BOOLEAN default false
config          JSONB nullable  -- credenciais e config específica do canal
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**Por que separar:** Um agente pode ter 0 ou N canais. Relação 1:N obrigatória. Cada canal tem configuração própria (token de WhatsApp, webhook de Instagram etc.). JSONB por canal evita proliferação de tabelas por canal.

**Quando criar:** Phase 5 (Widget) + Phase 6 (Channels).

---

### `agent_tools`

**Propósito:** Ferramentas que o agente pode usar ao responder.

```
id              UUID PK
agent_id        UUID FK → agents (CASCADE)
workspace_id    UUID FK → workspaces (CASCADE)
tool_type       VARCHAR(50)  -- knowledge_base | http_request | human_handoff | mark_resolved | follow_up
is_enabled      BOOLEAN default true
config          JSONB nullable
sort_order      INTEGER default 0
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**Por que separar:** Um agente terá múltiplas ferramentas. A lista de ferramentas disponíveis vai crescer. É uma relação 1:N natural. `config` em JSONB por ferramenta evita explosion de colunas.

**Quando criar:** Phase 4 (Knowledge Base) para a tool `knowledge_base`. Demais tools em Phase 6+.

---

### `agent_webhooks`

**Propósito:** Webhooks de saída configurados por agente.

```
id              UUID PK
agent_id        UUID FK → agents (CASCADE)
workspace_id    UUID FK → workspaces (CASCADE)
name            VARCHAR(100)
url             VARCHAR(2000)
secret          VARCHAR(255) nullable  -- armazenar encriptado
event_types     TEXT[]  -- conversation.started | message.received | lead.qualified | etc.
http_method     VARCHAR(10) default 'POST'
headers         JSONB nullable
is_enabled      BOOLEAN default true
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

**Por que separar:** 1:N com o agente. Cada webhook tem URL, segredo, eventos e headers próprios. Separar permite validar assinatura por webhook. Relação estruturalmente diferente de tools.

**Quando criar:** Phase 6 (Webhooks/Integrations).

---

### `agent_advanced_settings`

**Propósito:** Configurações de comportamento avançado do agente.

```
agent_id                    UUID FK → agents (CASCADE) PK
markdown_output_enabled     BOOLEAN default true
json_mode_enabled           BOOLEAN default false
auto_language_detection     BOOLEAN default true
ignore_images               BOOLEAN default false
inactivity_timeout_seconds  INTEGER nullable
inactivity_message          TEXT nullable
timezone                    VARCHAR(50) nullable
conversation_summary_mode   VARCHAR(20) default 'disabled'  -- disabled | auto | on_close
created_at                  TIMESTAMPTZ
updated_at                  TIMESTAMPTZ
```

**Por que separar:** Configurações de comportamento em runtime que não são prompt nem modelo. Relação 1:1. Podem crescer muito sem impactar a tabela de agentes.

**Quando criar:** Junto com Phase 3 (Playground) ou Phase 5 (Deploy), quando essas configs passarem a ter efeito real.

---

## 5. O que criar agora vs depois

### Criar agora — Phase 2.4

**`agent_prompt_settings`** — Recomendado criar agora.

- `system_prompt` e `persona` são os campos mais editados do produto.
- Já existem em `agents`. A migração é trivial: criar tabela, backfill, atualizar service.
- Libera `agents` de campos de texto longos que crescerão (response_style, language_mode etc.).
- Prepara o terreno para prompt versioning na Phase 3.

**`agent_model_settings`** — Recomendado criar agora.

- `ai_model_id`, `model_name` e `temperature` já existem em `agents`.
- A separação em tabela própria permite adicionar `max_tokens`, `context_window_policy` sem alterar `agents`.
- Migração trivial: backfill 1:1.
- Valida o padrão de settings satélite antes de ir para entidades mais complexas.

### Deixar para fases futuras

| Entidade                   | Fase sugerida  | Justificativa                                        |
|----------------------------|----------------|------------------------------------------------------|
| `agent_security_settings`  | Phase 5        | Sem canal publicado, segurança não tem efeito real   |
| `agent_deployment_settings`| Phase 5        | Depende de Widget e geração de public_slug           |
| `agent_channels`           | Phase 5–6      | Depende de integrações de canal                      |
| `agent_tools`              | Phase 4 (KB)   | `knowledge_base` tool pode vir antes das demais      |
| `agent_webhooks`           | Phase 6        | Depende de sistema de eventos e assinatura           |
| `agent_advanced_settings`  | Phase 3–5      | Criar quando os campos tiverem efeito no runtime     |

**Regra:** Não criar tabela antes de ter pelo menos uma feature real que escreva ou leia dados nela.

---

## 6. Migração recomendada

Para `agent_prompt_settings` e `agent_model_settings`, a migração segura segue este padrão:

```
Passo 1: Criar nova tabela com FK → agents
Passo 2: INSERT INTO agent_prompt_settings (agent_id, system_prompt, persona)
         SELECT id, system_prompt, persona FROM agents
Passo 3: Atualizar AgentService para ler e escrever na nova tabela
Passo 4: AgentOut ainda inclui os campos (JOIN transparente no service)
Passo 5: PATCH /agents/{id} continua funcionando (service faz UPDATE na tabela certa)
Passo 6: [Fase posterior] DROP COLUMN system_prompt, persona FROM agents
         (somente depois de confirmar que nenhum código lê diretamente)
```

**Compatibilidade de API durante migração:**

- `GET /agents/{id}` e `PATCH /agents/{id}` continuam com o mesmo contrato externo.
- O service absorve a complexidade de JOIN internamente.
- Frontend não precisa saber da separação das tabelas.

**Testes que devem continuar passando após a migração:**

- Tenant isolation: `workspace_id` em `agent_prompt_settings` não é necessário (FK via agent já garante), mas o service deve sempre buscar o agente com `workspace_id` antes de acessar settings.
- RBAC: aplicado no router antes de chamar o service. Não muda.
- Status validation: continua em `agents.status`. Não muda.

---

## 7. API e frontend

O frontend deve continuar enxergando um objeto `Agent` enriquecido. A separação de tabelas é um detalhe de implementação do backend.

### Visão futura dos endpoints

```
GET  /agents/{id}
     → retorna Agent + prompt_settings + model_settings (JOIN no service)

PATCH /agents/{id}
     → atualiza campos de identidade (name, description)

PATCH /agents/{id}/prompt-settings
     → atualiza system_prompt, persona, response_style

PATCH /agents/{id}/model-settings
     → atualiza ai_model_id, temperature

PATCH /agents/{id}/advanced-settings
     → atualiza markdown, json_mode, timezone, etc.

GET  /agents/{id}/tools
POST /agents/{id}/tools
PATCH /agents/{id}/tools/{tool_id}

GET  /agents/{id}/channels
POST /agents/{id}/channels/{channel_type}/enable

GET  /agents/{id}/webhooks
POST /agents/{id}/webhooks
```

### Princípio de composição no service

```python
def get_agent(db, workspace_id, agent_id) -> AgentOut:
    agent = _get_agent_or_404(db, workspace_id, agent_id)
    prompt = _get_or_init_prompt_settings(db, agent.id)
    model  = _get_or_init_model_settings(db, agent.id)
    return AgentOut.from_agent_and_settings(agent, prompt, model)
```

O frontend recebe um único objeto. A complexidade é encapsulada no service.

---

## 8. Roadmap técnico sugerido

### Phase 2.4 — Agent Architecture Preparation
- Criar `agent_prompt_settings` com backfill de `agents`
- Criar `agent_model_settings` com backfill de `agents`
- Atualizar `AgentService` para usar as novas tabelas
- Manter contrato de API idêntico (zero breaking change)
- Atualizar `AgentOut` para compor dados das três tabelas
- Testes: verificar tenant isolation e RBAC inalterados

### Phase 3 — Agent Playground (Chat)
- Interface de chat para testar o agente
- Integração real com LLM usando `model_name` do `agent_model_settings`
- `conversation` e `message` entities
- Logs de uso de créditos por mensagem

### Phase 4 — Knowledge Base
- Entidades `knowledge_bases`, `sources`
- Tool `knowledge_base` em `agent_tools`
- RAG pipeline básico

### Phase 5 — Widget e Deploy
- `agent_deployment_settings` (public_slug, widget_enabled)
- `agent_security_settings` (allowed_domains, rate_limit)
- `agent_channels` — início com `website`
- Website chat widget (JS embed)

### Phase 6 — Tools, Webhooks e Integrations
- `agent_tools`: http_request, human_handoff, mark_resolved
- `agent_webhooks`: outbound events com assinatura
- `agent_channels`: WhatsApp, Instagram, Telegram
- Integration catalog

---

## 9. Riscos

| Risco | Severidade | Mitigação |
|-------|-----------|-----------|
| **Overengineering** — criar tabelas sem uso real | Alta | Regra: não criar antes de ter feature real que use |
| **Migrations prematuras** — mover campos antes da hora | Média | Fazer backfill incremental, manter compatibilidade |
| **JSON config excessivo** — tudo em JSONB sem estrutura | Média | JSONB apenas para config específica de canal/tool |
| **Granularidade demais** — settings 1:1 como tabelas separadas em excesso | Média | Só separar quando houver justificativa real (versioning, RBAC diferente, crescimento esperado) |
| **Quebrar API antes da hora** — mudar contrato enquanto frontend depende dele | Alta | Service como camada de abstração; frontend recebe sempre o mesmo `AgentOut` |
| **Falta de versionamento** — prompt sem histórico | Baixa (hoje) | `agent_prompt_settings` já prepara para isso; versioning pode ser adicionado depois |
| **Dificuldade de testes** — mais tabelas = mais fixtures | Baixa | Factory functions em `conftest.py` absorvem a complexidade |
| **Criar entidades sem uso real** — tabelas vazias em produção | Alta | Ver regra de overengineering acima |

---

## 10. Recomendação final

### Criar agora (Phase 2.4)

**`agent_prompt_settings`** — Sim. Backfill trivial de `system_prompt` e `persona`. Libera `agents` dos campos de texto mais instáveis. Prepara para versioning e templates de prompt.

**`agent_model_settings`** — Sim. Move `ai_model_id`, `model_name` e `temperature` para tabela específica. Permite adicionar `max_tokens` e `context_window_policy` sem encostar em `agents`. Valida o padrão de satellite tables.

### Não criar agora

Todas as demais entidades (`agent_security_settings`, `agent_deployment_settings`, `agent_channels`, `agent_tools`, `agent_webhooks`, `agent_advanced_settings`) devem esperar as fases que as tornam necessárias.

### Sobre `ai_model_id` em `agents`

Mover para `agent_model_settings` junto com `temperature`. Em `agents` fica apenas `model_name` como snapshot de emergência (para o caso de JOIN falhar). Ao estabilizar `agent_model_settings`, o snapshot em `agents` pode ser removido.

### Sobre `system_prompt` e `persona` em `agents`

Mover para `agent_prompt_settings` na Phase 2.4. Enquanto isso, manter em `agents`. Não remover os campos de `agents` na mesma migration do backfill — dar pelo menos uma fase de estabilização antes de fazer o DROP.

### Menor passo seguro antes da Phase 3

Criar `agent_prompt_settings` e `agent_model_settings` com backfill. Atualizar o service para compor dados das três tabelas. Manter o contrato de API idêntico. Zero breaking change para o frontend. `agents` fica com: `id, workspace_id, name, description, status, created_by_user_id, created_at, updated_at`.

Esse é o núcleo estável da entidade Agent — e deve permanecer assim.
