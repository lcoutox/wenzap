# Phase 3.1 — Playground Sessions

## Objetivo

Persistir as conversas de teste do Agent Playground no banco de dados, permitindo que membros do workspace:

- Consultem histórico de testes anteriores
- Continuem uma conversa de teste existente
- Criem novas sessões de teste
- Excluam sessões antigas
- Comparem respostas entre execuções diferentes

Phase 3.1 não altera o comportamento do LLM nem dos créditos. É exclusivamente persistência e UI de histórico.

---

## O que foi implementado

### Backend

| Componente | Localização | Responsabilidade |
|---|---|---|
| Model `AgentPlaygroundSession` | `app/models/agent_playground_session.py` | Sessão de playground (grupo de mensagens) |
| Model `AgentPlaygroundMessage` | `app/models/agent_playground_message.py` | Mensagem individual dentro de uma sessão |
| Migration 018 | `alembic/versions/018_create_playground_sessions.py` | Cria `agent_playground_sessions` |
| Migration 019 | `alembic/versions/019_create_playground_messages.py` | Cria `agent_playground_messages` |
| Schemas | `app/schemas/playground.py` | `PlaygroundMessageOut`, `PlaygroundSessionOut`, `PlaygroundSessionWithMessages` |
| Schema atualizado | `app/schemas/agent_test.py` | `AgentTestRequest` agora aceita `session_id?: UUID`; `AgentTestResponse` retorna `session_id: UUID` |
| `playground_service.py` | `app/services/playground_service.py` | CRUD de sessões e mensagens |
| `agent_test_service.py` | `app/services/agent_test_service.py` | Integrado com sessions (Iteration 3) |
| Endpoints de sessions | `app/routers/agents.py` | 4 novos endpoints (listar, criar, obter, deletar) |

### Frontend

| Componente | Localização | Responsabilidade |
|---|---|---|
| Tipos | `apps/web/src/lib/api.ts` | `PlaygroundMessage`, `PlaygroundSession`, `PlaygroundSessionWithMessages` |
| Métodos | `apps/web/src/lib/api.ts` → `api.agents.playground.*` | CRUD de sessões |
| `AgentChat` | `apps/web/src/components/agents/workspace/tabs/AgentChat.tsx` | Refatorado para usar sessions persistentes |
| `PlaygroundSidebar` | `apps/web/src/components/agents/workspace/tabs/PlaygroundSidebar.tsx` | Lista lateral de sessões |

---

## Diferença entre Playground Sessions e Conversas Reais

| Dimensão | Playground Sessions | Conversas reais (futuro) |
|---|---|---|
| Origem | Iniciadas por membros do workspace para testar agentes | Iniciadas por contatos externos via canais (Widget, WhatsApp, etc.) |
| Tabelas | `agent_playground_sessions`, `agent_playground_messages` | `conversations`, `messages` (futuro — Inbox) |
| Isolamento | Por workspace + agent | Por workspace + channel |
| RBAC | Apenas owner/admin/member | Depende do canal |
| Visibilidade | Apenas interna (não aparece no Inbox) | Aparece no Inbox |
| Créditos | Consome créditos de teste | Consome créditos de produção |
| Relação com runs | `agent_playground_messages.agent_test_run_id` → `agent_test_runs` | Futuro: `messages.llm_run_id` |
| Contexto | Sem RAG, sem Knowledge Base, sem Tools na Phase 3.x | Com RAG, KB, Tools nas fases futuras |

**Playground Sessions nunca aparecem no Inbox e nunca são enviadas para canais reais.**

---

## Tabelas criadas

### `agent_playground_sessions`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID PK | Identificador único |
| `workspace_id` | UUID FK → `workspaces.id` (CASCADE) | Isolamento multi-tenant |
| `agent_id` | UUID FK → `agents.id` (CASCADE) | Agente ao qual pertence |
| `user_id` | UUID FK → `users.id` (SET NULL) | Quem criou (nullable: SET NULL se user for removido) |
| `title` | VARCHAR(200) | Título da sessão. Default: `"Nova conversa"`. Atualizado para a primeira mensagem do usuário. |
| `created_at` | TIMESTAMPTZ | Criação |
| `updated_at` | TIMESTAMPTZ | Última atividade (atualizado em cada nova mensagem) |

**Índices:**
- `workspace_id` (simples)
- `agent_id` (simples)
- `created_at DESC`
- `(workspace_id, agent_id, updated_at DESC)` — índice composto para a query de listagem

### `agent_playground_messages`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | UUID PK | Identificador único |
| `session_id` | UUID FK → `agent_playground_sessions.id` (CASCADE) | Sessão pai |
| `role` | VARCHAR(20) | `"user"` ou `"assistant"` |
| `content` | TEXT | Conteúdo da mensagem |
| `agent_test_run_id` | UUID FK → `agent_test_runs.id` (SET NULL) | Referência ao run que gerou esta resposta (NULL para mensagens de usuário) |
| `created_at` | TIMESTAMPTZ | Criação |

**Índices:**
- `session_id` (simples)
- `(session_id, created_at)` — para busca ordenada de mensagens de uma sessão

---

## Endpoints criados

Todos requerem role `owner | admin | member`. Viewer → 403.

| Método | Path | Descrição |
|---|---|---|
| `GET` | `/agents/{agent_id}/playground/sessions` | Lista sessões ordenadas por `updated_at DESC` |
| `POST` | `/agents/{agent_id}/playground/sessions` | Cria nova sessão com título `"Nova conversa"` |
| `GET` | `/agents/{agent_id}/playground/sessions/{session_id}` | Retorna sessão com lista de mensagens |
| `DELETE` | `/agents/{agent_id}/playground/sessions/{session_id}` | Deleta sessão (CASCADE deleta mensagens) |

### Endpoint `/test` atualizado

`POST /agents/{agent_id}/test` agora aceita `session_id` opcional no body:

```json
{ "message": "Olá!", "session_id": "uuid-opcional" }
```

E a response agora sempre retorna `session_id`:

```json
{
  "reply": "...",
  "credits_used": 1,
  "input_tokens": 10,
  "output_tokens": 20,
  "duration_ms": 800,
  "model": { "display_name": "...", "provider": "...", "model_name": "..." },
  "session_id": "uuid-da-sessao"
}
```

---

## Comportamento do `session_id` no `/test`

### Quando `session_id` é omitido

- Uma nova sessão é criada automaticamente antes de chamar o LLM.
- O `session_id` da nova sessão é retornado na response.
- O cliente deve usar este `session_id` para continuar a mesma conversa nas chamadas seguintes.

### Quando `session_id` é fornecido

- A sessão é validada: deve pertencer ao mesmo `workspace_id` e `agent_id` do request.
- Se não encontrada ou de outro tenant → `404 Not Found`.
- A mensagem do usuário é adicionada à sessão existente.
- Se a sessão ainda tinha título `"Nova conversa"`, ele é atualizado com os primeiros 80 chars da mensagem.

---

## Quando sessão NÃO é criada

Nenhuma sessão, mensagem ou run é criado se o request falhar **antes** da chamada ao LLM. Isso inclui:

| Situação | HTTP | Sessão criada? |
|---|---|---|
| Agente `archived` | 400 | Não |
| `system_prompt` ausente ou vazio | 400 | Não |
| Sem configuração de modelo | 400 | Não |
| Modelo inativo | 404 | Não |
| Provider inativo | 400 | Não |
| Modelo fora do plano | 402 | Não |
| Modelo não executável (whitelist) | 400 | Não |
| Créditos insuficientes | 402 | Não |
| `session_id` inválido / de outro tenant | 404 | Não |
| Viewer tentando testar | 403 (no router) | Não |

---

## Regra de persistência de user message

A mensagem do usuário é persistida **imediatamente após** a criação/resolução da sessão, **antes** de chamar o LLM.

Isso garante que:
- Se o LLM retornar erro (timeout, rate limit, etc.), a pergunta do usuário fica registrada.
- O histórico mostra o que o usuário perguntou, mesmo sem resposta do agente.

`agent_playground_messages.agent_test_run_id` é sempre `NULL` para mensagens de usuário.

---

## Regra de persistência de assistant message

A mensagem do assistente **só é salva em caso de sucesso do LLM**. Nunca é criada em caso de erro do provider.

Quando criada:
- `role = "assistant"`
- `content = llm_response.content`
- `agent_test_run_id = run.id` — referência ao `agent_test_runs` que registrou a execução

---

## Relação com `agent_test_runs`

`agent_test_runs` continua sendo a tabela de auditoria de execuções que chegaram ao provider LLM. Phase 3.1 não altera seu contrato.

A relação é:

```
agent_playground_messages (assistant) → agent_test_run_id → agent_test_runs
```

Um `agent_test_run` pode ter no máximo uma `agent_playground_message` assistante associada. Se o run falhou (status=error), nenhuma mensagem assistante é criada, mas o run ainda é registrado.

---

## Regra de erro do provider

Quando o LLM retorna erro (`LLMProviderError`):

1. Sessão e user message já estão persistidas (flush anterior).
2. Um `agent_test_run` com `status="error"` e `credits_used=0` é inserido.
3. `touch_session` é chamado para atualizar `updated_at`.
4. O DB é commitado (sessão + user msg + run de erro = atômico).
5. Nenhuma mensagem assistante é criada.
6. Nenhum crédito é consumido.
7. HTTP 503 é retornado ao cliente.

---

## Regra de créditos insuficientes

Verificação de créditos acontece **antes** de qualquer escrita no banco. Se insuficiente:
- Nenhuma sessão é criada (nem auto-criada).
- Nenhuma mensagem é criada.
- Nenhum run é registrado.
- HTTP 402 é retornado.

---

## Atomicidade

A fase de sucesso (após retorno do LLM) é atômica:

```
db.flush()  ← persiste sessão + user message (antes do LLM)
↓
LLM call
↓ (sucesso)
_increment_credits()      ←┐
_log_run(status=success)   ├── mesmo db.commit()
db.flush()  ← get run.id   │
save_assistant_message()  ←┘
touch_session()
db.commit()
```

Se qualquer parte falhar após o LLM (ex: crash no servidor), créditos, run e assistant message ficam ausentes. Esta é uma inconsistência conhecida aceitável — nenhum dado é corrompido, apenas incompleto.

---

## RBAC

| Role | Endpoints de sessions | `/test` com sessions |
|---|---|---|
| owner | ✅ | ✅ |
| admin | ✅ | ✅ |
| member | ✅ | ✅ |
| viewer | ❌ 403 | ❌ 403 |

Viewers não podem listar, criar, obter, deletar sessões nem enviar mensagens de teste.

---

## Tenant isolation

Toda query de sessão filtra por `(workspace_id, agent_id)` — nunca apenas por `session_id`.

Consequência: um `session_id` de outro workspace ou de outro agente retorna **404**, não 403. Isso não revela se a sessão existe, apenas que não pertence ao contexto do request.

---

## O que ficou fora de escopo (Phase 3.1)

- RAG / Knowledge Base no contexto do agente
- Streaming de resposta
- Múltiplos turnos de conversa multi-agente
- Providers além de Anthropic (OpenAI, Google, DeepSeek)
- Edição manual de título da sessão
- Paginação de sessões
- Paginação de mensagens
- Busca em histórico
- Exportação de histórico
- Compartilhamento de sessão
- Run metadata (créditos, duração, modelo) retornado em `PlaygroundMessageOut` — só disponível na response do `/test` ao vivo

---

## Limitações conhecidas

| Limitação | Impacto | Referência TECH_DEBT |
|---|---|---|
| `PlaygroundMessageOut` não retorna run metadata | Metadados (créditos, duração, modelo) somem ao recarregar a página | TD-005 |
| Sem paginação de sessões | Workspaces com muitas sessões retornam tudo em uma lista | TD-006 |
| Sem paginação de mensagens | Sessões longas carregam todas as mensagens de uma vez | TD-007 |
| Sem edição manual de título | Usuário não pode renomear sessões | TD-008 |
| Sem limite de sessões por agente/workspace | Espaço em disco pode crescer indefinidamente | TD-009 |
| Sem busca em histórico | Não é possível buscar por conteúdo de mensagens | TD-010 |
