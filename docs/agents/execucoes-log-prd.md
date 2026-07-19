# PRD — Tela de Execuções (log de agente pro dono do workspace)

**Status: ✅ Implementado (2026-07-19)**

## Contexto

Testando o agendamento da imobiliária fictícia, o agente respondeu ao cliente "um corretor vai
entrar em contato" em vez de "confirmado" — internamente, a chamada `agendar_visita` tinha
retornado 400 da Cal.com. A correção anterior (Sentry + `ToolCallFailedError`, ver
`decisoes.md` no NexBrain) já garante que **o Lucas** (dono do SaaS) vê isso no Sentry. Mas o
dono real do workspace (o cliente do Wenzap, ex: dono da imobiliária) não tinha nenhuma forma de
ver isso — só descobriria se um cliente reclamasse.

Comparação com o Chatvolt (concorrente direto, doc pública consultada): não têm nada documentado
nessa linha — a página "Debug" deles é só um checklist genérico de troubleshooting. Isso não é
recuperar terreno, é ficar à frente.

Referência de categoria: Zapier (Zap History), Make.com (Execution History) e n8n (Executions)
— todos têm uma tela dedicada e workspace-wide de histórico de execução, filtrável por status,
não um indicador escondido dentro de cada item individual.

## Desenho

**Correção de dado, pré-requisito:** `conversation_agent_runs.status` só refletia se o turno do
LLM em si travou — uma tool que falhou dentro de um turno que completou normalmente (o caso real)
ainda gravava `status="success"`. Adicionado `had_tool_error: bool`, calculado a partir de
`AgentTurnResult.calls[].tool_calls[].status` no fim do turno (migration 075).

**Tela `/dashboard/logs` ("Execuções")** — lista todo `ConversationAgentRun` do workspace, mais
recente primeiro: data, contato, agente, ferramentas chamadas, status (OK / tool falhou / falhou
/ outro). Filtros: só falhas (`had_error`), agente, nome da ferramenta, conversa específica.
Clicar numa linha abre o detalhe: cada tool call (nome, input, output, status) + link direto pra
conversa real no Inbox.

**Indicador no Inbox** — badge discreto "⚠ Falha detectada" no cabeçalho da conversa, só aparece
quando essa conversa teve pelo menos uma execução com falha real. Clique leva direto pra
`/dashboard/logs?conversation_id=X`, já filtrado.

## Backend

- `alembic/versions/075_conversation_agent_run_had_tool_error.py` — coluna nova, sem dado a
  migrar (default `false`).
- `conversation_agent_reply_service.py` — computa `had_tool_error` antes de salvar o run de
  sucesso, a partir do resultado já existente de `run_agent_turn`.
- `agent_run_service.py` (novo) — só leitura: `list_agent_runs` (filtros + paginação, join com
  `Contact`/`Agent`, nomes de tool via bulk-fetch de `agent_tool_calls` — sem N+1) e
  `get_agent_run_detail` (uma execução completa, tool calls achatadas).
- `routers/agent_runs.py` (novo) — `GET /agent-runs`, `GET /agent-runs/{id}`, mesmo padrão de
  role-check (viewer+) que `conversations.py`.

## O que não muda

Nenhum endpoint de escrita novo — é 100% leitura do que `conversation_agent_reply_service.py` e
`agent_llm_executor.py` já gravam. `agent_alerts` (sininho de falha da própria Anthropic) e o
Sentry continuam existindo, sem sobreposição — servem propósitos diferentes (alerta imediato vs.
histórico navegável).

## Testes

16 testes novos: `test_agent_run_service.py` (9, filtros/paginação/isolamento direto no service),
`test_agent_runs_api.py` (6, camada HTTP: auth, serialização, 404, isolamento por workspace),
`test_conversation_agent_reply_service.py` (1, `had_tool_error` de ponta a ponta com uma tool
HTTP real falhando). Suite completa limpa (só as 10 falhas pré-existentes conhecidas).
