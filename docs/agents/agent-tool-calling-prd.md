# PRD — Tool Calling para Agentes (infraestrutura de ações)

**Status: ✅ Implementado (2026-07-17)** — Fases 0 a 5 completas, testadas (2061 testes
passando no backend, build de produção do frontend limpo). Primeira tool real (HTTP genérico)
funcionando ponta a ponta no Inbox e no Playground, gated Scale+. Ver seção "Estado da
implementação" no fim deste documento.

## Contexto

Hoje o Wenzap **não tem nenhuma infraestrutura de LLM tool-calling**. Confirmado por auditoria completa do backend: `LLMRequest`/`LLMResponse` (`app/llm/schemas.py`) não têm nenhum campo relacionado a tools, e `grep` por `tools=`/`tool_use`/`input_schema` em todo `apps/api/app` não retorna nenhum uso real. As três capacidades que hoje *parecem* "ferramentas" pro usuário foram construídas deliberadamente para **evitar** essa complexidade:

- **Base de Conhecimento (RAG)** e **Catálogo**: pré-busca / injeção de contexto. O backend busca os chunks/itens relevantes *antes* de chamar o LLM e cola tudo como texto no system prompt (`conversation_context_builder.py`). O modelo nunca decide buscar.
- **Pipeline (`entry_condition`)**: chamada de classificação *separada*, depois que a resposta já foi gerada (`pipeline_auto_routing_service.py`) — o próprio código documenta isso como alternativa deliberada ao tool-calling, "the same trick FluxVolt itself uses".

Isso foi uma boa decisão até agora, mas trava o próximo passo: dar ao agente capacidade de **executar ações reais** (chamar uma API externa, agendar algo, etc.) durante o atendimento — o que exige o modelo decidindo, em tempo real, se e qual ferramenta usar. Esse é o padrão que concorrentes como o Chatvolt usam (confirmado na doc pública deles: *"Keep tool descriptions short and action-oriented so the LLM knows exactly when to use them"* — function-calling nativo, orientado por descrição de tool + prompt).

**Sinais de que isso já era esperado no produto**, achados durante a pesquisa:
- A aba **Ferramentas** no frontend (`ConfigFerramentas.tsx`) já existe, já mostra KB/Catálogo como "ferramentas ativas", e já tem cards **"Em breve"** pré-desenhados pra `HTTP Tools`, `Solicitar humano`, `Follow-up` e `Marcar como resolvido`.
- `docs/architecture/AGENT_MODULE_ARCHITECTURE.md` já propõe a tabela `agent_tools` (satélite 1:N, `tool_type` + `config JSONB`), listando `http_request` como exemplo, mas marcada para "Phase 6+" — este PRD é essa fase.
- `plan_features` já tem a feature key **`http_tools` seedada** (`False` em starter/growth, `True` em scale/enterprise) — a decisão de produto (automação = Scale+, mesma linha do Pipeline.2) já foi tomada, só falta a engenharia.
- `docs/architecture/AGENT_GUARDRAILS.md` já lista "Guardrails para Tools (confirmação antes de ação irreversível)" como item de fase futura ainda não implementado.

Ou seja: isto não é greenfield — é fechar uma lacuna já mapeada em três documentos diferentes.

## Objetivo

Dar ao Wenzap a capacidade de agentes executarem ações reais durante o atendimento (primeira ferramenta: HTTP genérico), com o modelo decidindo sozinho quando usar cada uma, e com fricção mínima de configuração pro usuário final — ele liga um toggle e escreve regras de negócio em português no prompt; não escreve JSON schema nem código.

## Não-objetivos (fora de escopo deste PRD)

- **Migrar KB/Catálogo para tool-calling de verdade.** Continuam como pré-busca — funcionam bem assim; virar tool é otimização futura separada (ganho: busca sob demanda em vez de sempre injetar; custo: reescrever dois fluxos que já funcionam). Não é pré-requisito para nada aqui.
- **Múltiplas integrações nativas** (Google Calendar, Drive, etc.). Este PRD entrega a infraestrutura + **uma** tool de referência (HTTP genérico) para provar o loop ponta a ponta. Integrações nativas específicas são PRDs futuros, priorizados por demanda real de cliente.
- **Multi-provider tool-calling** (OpenAI/Gemini). Só Anthropic — mesma decisão já vigente pro resto do produto ("Nexbrain" é wrapper de modelos Anthropic).
- **Confirmação humana antes de ação irreversível.** `AGENT_GUARDRAILS.md` já registra essa intenção como fase futura. Para uma tool HTTP genérica não dá para saber automaticamente se uma chamada é "irreversível" — fica para quando houver tools com semântica conhecida (ex: "cancelar pedido").

## Princípio: reaproveitar o que já existe, não redesenhar

- SSRF-safe `validate_webhook_url()` (`app/services/pipeline_webhook_service.py`) — função pura, sem side effects, reaproveitável como está.
- Gating por plano: `plan_features` + `workspace_allows_feature()` (`app/services/plan_feature_service.py`) — `http_tools` já seedado, só falta o call-site de runtime.
- Padrão de satélite 1:N com `config JSONB` (`agent_tools`) — já desenhado em `AGENT_MODULE_ARCHITECTURE.md`, seguir à risca em vez de inventar variação.
- UI da aba Ferramentas (`ConfigFerramentas.tsx`) — já existe, já tem o card "HTTP Tools" desenhado como placeholder; troca por card funcional reaproveitando o padrão de `KbConfigModal`/`CatalogConfigModal` (toggle + modal de config).

## Fase 0 ✅ — Corrigir bug de retry pré-existente (pré-requisito, sem dependências)

Achado durante a pesquisa deste PRD, não relacionado a tool-calling em si, mas relevante porque um loop de tool-calling multiplica os round-trips ao LLM (mais chance de erro transitório no meio do caminho): `LLMProviderError` (`app/llm/schemas.py`) não define `.auth_error` nem `.transient`, mas `conversation_agent_reply_service.py:300,303` lê essas propriedades sem `hasattr`/`getattr` guard dentro do loop de retry. Isso quebra com `AttributeError` em vez de decidir corretamente se deve tentar de novo — o retry automático descrito no código provavelmente está quebrado em produção hoje. Corrigir antes de empilhar mais lógica de retry em cima (a Fase 2 vai precisar de retry funcionando de verdade).

## Fase 1 ✅ — Extensão da camada de abstração LLM (provider-agnostic)

A camada `app/llm/` foi desenhada para trocar de provider sem tocar nos callers ("Adding a new provider means implementing a new function in providers/ that accepts LLMRequest and returns LLMResponse — nothing else changes") — a extensão de tools precisa respeitar esse contrato, não ser hardcoded no `anthropic.py` de um jeito que quebre essa promessa.

- `LLMMessage.content`: de `str` para `str | list[dict]` (suportar content blocks: texto, `tool_use`, `tool_result`).
- `LLMRequest`: novos campos `tools: list[dict] | None`, `tool_choice: dict | None`.
- `LLMResponse`: novos campos `stop_reason: str`, `content_blocks: list[dict]` — hoje `anthropic.py` pega só `response.content[0].text`, assumindo que o primeiro bloco é sempre texto. Isso quebra assim que a resposta vier com `tool_use` como único bloco (ou junto de texto). Precisa mapear todos os blocos, não só o primeiro.
- `anthropic.py`: passar `tools=`/`tool_choice=` para `client.messages.create(...)` quando presentes no `LLMRequest`. O SDK instalado (`anthropic>=0.84,<1.0`) já suporta isso nativamente — **sem upgrade de dependência necessário**.
- Retrocompatível: quem não passa `tools=` continua funcionando exatamente como hoje.

## Fase 2 ✅ — Executor de loop compartilhado (resolve duplicação reply/test)

Achado importante da pesquisa: `conversation_agent_reply_service.py` (produção — Inbox/WhatsApp) e `agent_test_service.py` (Playground) são **implementações paralelas duplicadas**, não compartilham código — cada uma tem sua própria cópia de `_increment_credits`, sua própria allowlist de modelos executáveis (uma inclui GPT, outra não), uma tem retry e a outra não. Se tool-calling for implementado direto em cada uma, a duplicação piora.

Criar um executor único (proposta: `app/services/agent_llm_executor.py`) que:
- Recebe o request inicial + lista de tools disponíveis para aquele agente.
- Roda o loop: chama o LLM → se `stop_reason == "tool_use"`, executa a tool correspondente, injeta o `tool_result` na conversa, chama de novo → repete até a resposta final ser texto puro.
- Limite de iterações (ex: 5) — trava de segurança contra loop consumindo crédito indefinidamente.
- Retorna: texto final + lista estruturada de todas as chamadas feitas no loop (nome da tool, input, output, tokens/duração de cada round-trip) — necessário para a Fase 3.

`conversation_agent_reply_service.py` e `agent_test_service.py` passam a chamar esse executor em vez de `llm_client.complete()` direto. Isso corrige a duplicação como efeito colateral positivo, não é escopo extra — é o único jeito de tool-calling funcionar igual nos dois lugares sem duplicar o loop também.

## Fase 3 ✅ — Modelo de dados: `agent_tools` + auditoria por chamada

- **`agent_tools`** — exatamente como já desenhada em `AGENT_MODULE_ARCHITECTURE.md`: satélite 1:N (não 1:1, um agente pode ter várias tools), `agent_id` + `workspace_id` (FKs, ambos — convenção já usada nos outros satélites 1:N do módulo, mesmo sendo `workspace_id` derivável via join, por isolamento de tenant), `tool_type VARCHAR(50)`, `is_enabled BOOLEAN default true`, `config JSONB`, `sort_order INTEGER default 0`, timestamps.
- **Tabela de auditoria por chamada** (nome a definir, ex: `agent_tool_calls`), satélite de `conversation_agent_runs`/`agent_test_runs`: `call_index`, `tool_type`, `input` (resumo/hash, não payload completo — mesma política de não persistir conteúdo sensível já usada em `agent_test_runs`), `output` (idem), `status`, `credits_used`, `input_tokens`, `output_tokens`, `duration_ms` daquela chamada específica. Sem isso, um loop de N chamadas fica com custo somado sem visibilidade de qual chamada gastou o quê — mesmo padrão já usado para auditar retrieval de RAG (`agent_test_run_retrieved_chunk`, satélite de `agent_test_run`).
- **Decisão de produto necessária, não só técnica**: crédito cobrado por chamada de LLM dentro do loop (cada round-trip conta) ou preço fixo por turno do usuário, independente de quantas tools rodaram? Recomendação: por chamada — mais justo e prevê contra um agente mal configurado "gastando de graça" fazendo várias chamadas de tool em sequência. A contabilidade agregada (`usage_counters.ai_credits_used`) já suporta isso hoje (é um contador aditivo puro); o que falta é o modelo de auditoria por chamada acima.

## Fase 4 ✅ — Primeira tool real: HTTP genérico

- `tool_type = "http_request"`, `config` guarda method, URL (ou template), headers, body template.
- Execução: reaproveita `validate_webhook_url()` para proteção SSRF (mesma validação, incluindo a re-checagem no momento do disparo contra DNS rebinding). Diferente do webhook do Pipeline (fire-and-forget, thread solta): aqui a chamada é **síncrona** — o resultado precisa voltar pro modelo antes da resposta final, então bloqueia o turno. Timeout mais curto que o do webhook (8s), sem retry automático ou no máximo 1 retry rápido — o usuário está esperando resposta.
- Gate: `workspace_allows_feature(db, workspace_id, "http_tools")` — feature key já seedada (Scale+), só falta o call-site.
- UI: trocar o `RoadmapCard` "HTTP Tools" (`ConfigFerramentas.tsx`, hoje "Em breve") por card funcional com toggle + modal de configuração (method/URL/headers/body), reaproveitando o padrão visual e de estado de `KbConfigModal`/`CatalogConfigModal` — não é tela nova, é o mesmo componente com conteúdo novo.

## Fase 5 ✅ — Guardrails mínimos para tool-calling

- Atualizar o bloco fixo de safety rules (`_NEXBRAIN_SAFETY_RULES` em `agent_context_builder.py`) — hoje instrui o modelo a **negar** ter ferramentas ("Do not claim to have access to tools... unless they have been explicitly provided in this context"; "External actions and integrations are not available in this phase"). Precisa virar condicional: só nega se o agente realmente não tiver tools ativas.
- Guardrail sobre o **resultado** de uma tool antes de voltar pro contexto do modelo — hoje o único guardrail de anti-injection (`detect_prompt_injection`) roda só na mensagem do cliente. Um resultado de tool (ex: resposta de uma API externa) é uma superfície de prompt injection que ainda não é coberta por nada. No mínimo truncar/sanitizar; idealmente rodar o mesmo regex de anti-injection também no resultado.
- Confirmação antes de ação irreversível: fora de escopo (ver Não-objetivos) — registrar aqui como próximo passo natural quando houver tools com semântica conhecida o suficiente para classificar risco.

## Migrations necessárias

A partir de `067` (última hoje: `066_pipeline_entry_stage_history.py`):
- Nova tabela `agent_tools`
- Nova tabela de auditoria por chamada (nome a definir na Fase 3)

## Feature flag / gating

`http_tools` já existe em `plan_features` (Scale+) — reaproveitar, não criar novo.

## Ordem de execução recomendada

Fase 0 é independente, pode rodar em paralelo ou antes de tudo. As demais são sequenciais e cada uma depende da anterior: **0 → 1 → 2 → 3 → 4 → 5**. Não dá para pular a Fase 2 (executor compartilhado) direto para a Fase 4 (tool HTTP) sem duplicar o loop entre reply e test — foi exatamente esse tipo de atalho que gerou a duplicação que já existe hoje entre os dois serviços.

## Critério de "pronto"

Um agente em plano Scale+ consegue ativar a tool HTTP pela aba Ferramentas, o modelo decide sozinho quando chamá-la durante uma conversa real — tanto no Inbox/WhatsApp quanto no Playground —, a chamada é executada com proteção SSRF, o resultado volta pro modelo e influencia a resposta final, créditos são contabilizados corretamente por chamada, e a UI mostra a tool como "Ativa" no mesmo padrão visual que KB/Catálogo já usam hoje.

## Referências

- `docs/architecture/AGENT_MODULE_ARCHITECTURE.md` — arquitetura de satélites do módulo de agentes, propõe `agent_tools`.
- `docs/architecture/AGENT_GUARDRAILS.md` — escopo atual de guardrails e o que fica para fases futuras (Tools/Webhooks explicitamente listados como não cobertos).
- `docs/agents/agent-module-refactor-prd.md` — seção "Ferramentas (aba principal)", desenho de UI já aprovado.
- `app/services/pipeline_webhook_service.py` — padrão de SSRF-safe outbound HTTP a reaproveitar.
- `app/services/plan_feature_service.py` — padrão de gating por plano a reaproveitar.

## Estado da implementação (2026-07-17)

**Backend, arquivos novos:**
- `app/services/agent_llm_executor.py` — executor de loop compartilhado (Fase 2), com retry + loop de tool-calling + guardrail de tool_result (Fase 5).
- `app/services/agent_tool_service.py` — CRUD, `build_tool_schema`, `build_tool_dispatch`, `execute_http_tool` (SSRF-safe, síncrono).
- `app/models/agent_tool.py`, `app/models/agent_tool_call.py` + migration `067_agent_tool_calling.py`.
- `app/schemas/agent_tool.py` — `AgentToolCreate`/`Update`/`Out`, `HttpToolConfig`.
- Testes novos: `test_llm_anthropic_provider.py`, `test_agent_llm_executor.py`, `test_agent_tools.py`, `test_agent_tool_calling_integration.py` (ponta a ponta, Inbox + Playground).

**Backend, arquivos modificados:**
- `app/llm/schemas.py` / `app/llm/providers/anthropic.py` — suporte a `tools=`/`tool_choice`, `stop_reason`, `content_blocks`; correção do bug de retry (`.auth_error`/`.transient` nunca existiam em `LLMProviderError`).
- `app/services/conversation_agent_reply_service.py` / `app/services/agent_test_service.py` — migrados pro executor compartilhado, tools conectadas via `plan_allows_feature(db, plan_code, "http_tools")` (reaproveita `plan_code` já resolvido, sem round-trip extra).
- `app/services/agent_context_builder.py` / `app/services/conversation_context_builder.py` — `has_tools` condicional no bloco fixo de safety rules.
- `app/services/pipeline_webhook_service.py` — mensagens de erro traduzidas pra pt-BR (achado durante o reaproveitamento de `validate_webhook_url`, fora do escopo original mas na mesma linha da auditoria de idioma já feita antes nesta sessão).
- `app/routers/agents.py` — endpoints `/{agent_id}/tools/http` (list/create/update/delete), gated 402 por `http_tools`.

**Frontend:**
- `apps/web/src/lib/api.ts` — tipos `AgentTool`/`HttpToolConfig`/inputs + `api.agents.httpTools.*`.
- `apps/web/src/components/agents/workspace/tabs/ConfigFerramentas.tsx` — card "Ferramentas HTTP" (ativo/disponível, mesmo padrão visual de KB/Catálogo) + modal de lista + modal de formulário (criar/editar), substituindo o `RoadmapCard` "Em breve".

**Verificação:** 2061 testes de backend passando (13 pré-existentes sem relação, já documentados em `negocios/wenzap/decisoes.md` no NexBrain), build de produção do frontend limpo (typecheck + lint). UI não testada visualmente em navegador (sem ferramenta de browser disponível na sessão de implementação) — recomenda-se um teste manual antes de considerar 100% validado.

**Backlog explicitamente fora deste PRD** (ver "Não-objetivos"): migrar KB/Catálogo pra tool-calling de verdade; integrações nativas (Calendar, Drive); multi-provider tool-calling; confirmação humana antes de ação irreversível.
