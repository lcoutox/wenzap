# Phase 3 — Agent Playground

## Objetivo

Implementar o endpoint de execução de agentes em modo de teste e a aba Chat funcional no Agent Workspace, permitindo que membros do workspace (owner/admin/member) testem agentes em tempo real antes de publicá-los em canais.

---

## O que foi implementado

### Backend

| Componente | Localização | Responsabilidade |
|---|---|---|
| LLM abstraction layer | `app/llm/` | Interface provider-agnóstica para chamadas LLM |
| Anthropic provider | `app/llm/providers/anthropic.py` | Implementação concreta via SDK Anthropic |
| Context builder | `app/services/agent_context_builder.py` | Monta o system prompt final para o LLM |
| Schemas | `app/schemas/agent_test.py` | `AgentTestRequest`, `AgentTestResponse`, `AgentTestModelInfo` |
| Service | `app/services/agent_test_service.py` | Orquestra validação → créditos → LLM → log |
| Endpoint | `POST /agents/{agent_id}/test` | Exposto em `app/routers/agents.py` |
| Migration | `alembic/versions/017_create_agent_test_runs.py` | Cria tabela `agent_test_runs` |
| Model | `app/models/agent_test_run.py` | Registro de execuções que chegaram ao provider |
| Config | `app/config.py` | Campo `anthropic_api_key: str = ""` |
| Dependência | `pyproject.toml` | `anthropic>=0.84,<1.0` |

### Frontend

| Componente | Localização | Responsabilidade |
|---|---|---|
| `AgentChat` | `components/agents/workspace/tabs/AgentChat.tsx` | Chat funcional com histórico local |
| Tipos | `lib/api.ts` | `AgentTestModelInfo`, `AgentTestResponse` |
| Método | `lib/api.ts` → `api.agents.test()` | Chama `POST /agents/{id}/test` |
| Page | `dashboard/agents/[id]/page.tsx` | Substituiu `ChatPlaceholder` por `AgentChat` |

---

## O que ficou fora de escopo (Phase 3)

- RAG / Knowledge Base no contexto do agente
- Streaming de resposta
- Múltiplos turnos de conversa persistidos no banco
- Providers além de Anthropic (OpenAI, Google, DeepSeek)
- Histórico de testes salvo por conversa
- Ferramentas (Tools) executadas pelo agente
- Channels, Inbox, Pipelines
- Moderação de conteúdo

---

## Anthropic como único runtime provider

Na Phase 3, todas as chamadas LLM são roteadas para o provider Anthropic, independentemente de qual provider está configurado no catálogo do modelo.

`app/llm/client.py` despacha sempre para `app/llm/providers/anthropic.py`. A abstração (`LLMRequest`/`LLMResponse`/`LLMProviderError`) está preparada para suportar outros providers sem alterar o service layer.

### Whitelist de modelos executáveis (Phase 3)

```python
ANTHROPIC_EXECUTABLE_MODELS = {
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
}
```

**Regra para modelos Nexbrain:** um modelo com `provider.code == "nexbrain"` é executável se e somente se seu `model_name` estiver na whitelist acima. Isso reflete que os modelos Nexbrain são wrappers sobre modelos Anthropic.

**Erro para providers não suportados:** qualquer provider cujo `code` não seja `"anthropic"` ou `"nexbrain"` retorna HTTP 400 com mensagem controlada. O LLM não é chamado.

---

## Consumo de créditos

### Quando créditos SÃO consumidos

- Somente após resposta bem-sucedida do LLM provider.
- O valor é `ai_model.credits_per_message`.
- O incremento e o log de execução são feitos na mesma transação `db.commit()` para garantir atomicidade.

### Quando créditos NÃO são consumidos

| Situação | Crédito consumido? |
|---|---|
| Agente `archived` | Não |
| `system_prompt` ausente ou vazio | Não |
| Modelo sem configuração (`agent_model_settings` ausente) | Não |
| Modelo inativo (`is_active=False`) | Não |
| Provider inativo | Não |
| Modelo fora do plano | Não |
| Modelo não executável (provider não suportado ou model_name fora da whitelist) | Não |
| `usage_counter` ausente para o período atual | Não |
| Créditos insuficientes | Não |
| **Erro do provider LLM** | **Não** |
| Viewer tentando testar | Não (bloqueado antes do service) |

### Validação de créditos

Antes de chamar o LLM:
```
usage_counters.ai_credits_used + credits_per_message <= plan.monthly_ai_credits
```

O incremento usa `UPDATE ... SET ai_credits_used = ai_credits_used + N WHERE ...` atômico, sem read-before-write, para segurança em requests concorrentes.

---

## Tabela `agent_test_runs`

### O que é salvo

| Campo | Tipo | Descrição |
|---|---|---|
| `workspace_id` | UUID | Isolamento multi-tenant |
| `agent_id` | UUID | Agente que foi testado |
| `user_id` | UUID | Usuário que disparou o teste |
| `ai_model_id` | UUID | Snapshot de referência ao modelo |
| `provider_code` | VARCHAR | Snapshot do code do provider (ex: `"anthropic"`) |
| `model_code` | VARCHAR | Snapshot do code do modelo (ex: `"nexbrain-prime"`) |
| `model_name` | VARCHAR | Snapshot do model_name enviado ao LLM (ex: `"claude-sonnet-4-6"`) |
| `credits_used` | INT | Créditos efetivamente consumidos (0 em erros) |
| `input_tokens` | INT | Tokens de entrada retornados pelo provider |
| `output_tokens` | INT | Tokens de saída retornados pelo provider |
| `duration_ms` | INT | Duração da chamada ao provider em ms |
| `status` | VARCHAR | `"success"` ou `"error"` |
| `error_message` | VARCHAR(500) | Mensagem sanitizada (somente em `status="error"`) |

### O que NÃO é salvo (privacidade)

- Mensagem do usuário (user prompt)
- Resposta completa do LLM
- System prompt montado
- Persona ou identidade do agente
- Qualquer dado pessoal do contato

**Justificativa:** evitar armazenamento desnecessário de dados potencialmente sensíveis dos clientes finais dos workspaces.

### Quando um registro NÃO é criado

Execuções bloqueadas **antes** de chegar ao provider LLM não geram `agent_test_runs`. Isso inclui todos os casos de validação listados na seção de créditos acima. A tabela registra apenas interações com o provider.

---

## Contexto enviado ao LLM (Phase 3)

`agent_context_builder.build_system_prompt()` monta o system prompt com:

1. Identidade: `"You are {agent.name}. {agent.description}"`
2. System prompt base (de `agent_prompt_settings.system_prompt`)
3. Persona (de `agent_prompt_settings.persona`), se preenchida

Sem RAG. Sem knowledge base context. Sem tool descriptions. Isso será adicionado nas fases 4+.

---

## Histórico de mensagens (frontend)

O histórico de chat é armazenado **apenas em memória local** (`useState`) no componente `AgentChat`. Ao navegar para outra aba ou recarregar a página, o histórico é limpo. Nenhuma mensagem é persistida no banco de dados.

---

## RBAC do endpoint

| Role | Pode testar? |
|---|---|
| owner | Sim |
| admin | Sim |
| member | Sim |
| viewer | Não (403) |
| membro inativo | Não (403, bloqueado pelas dependencies de auth) |

---

## Variáveis de ambiente necessárias

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Se ausente ou vazia, o endpoint retorna 503 com mensagem controlada. A key nunca é logada.

---

## Próximos passos sugeridos (Phase 4+)

- **Phase 4 — Knowledge Base no Playground:** integrar RAG no context builder; incluir chunks relevantes no system prompt baseado na mensagem do usuário
- **Phase 4 — Provider registry:** implementar routing por provider no `llm/client.py` para suportar OpenAI/Google sem alterar o service layer
- **Phase 4 — Histórico persistido:** criar tabela de sessões de playground com mensagens, linkadas ao `agent_test_runs`
- **Phase 5 — Streaming:** substituir request/response por SSE ou WebSocket no playground
- **Phase 5 — Tools no contexto:** incluir tool descriptions no system prompt; processar `tool_use` na resposta
- **Futuro — Versioned prompts:** salvar snapshot do system prompt efetivo em `agent_test_runs` com opt-in por workspace (feature flag)
- **Futuro — Rate limiting:** adicionar rate limit por workspace no endpoint de teste
