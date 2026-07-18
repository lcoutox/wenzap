# PRD — Tool "Marcar como resolvido"

**Status: ✅ Implementado (2026-07-18)** — quarta tool real, mesma infra de tool-calling do HTTP
Tool e Solicitar Humano (`agent_tools`, decisão do modelo no meio do turno — não é sweep como o
Follow-up). 2117 testes de backend passando, build de frontend limpo. Ver "Estado da
implementação" no fim.

## Contexto

Pesquisa competitiva: doc pública do Chatvolt (`docs.chatvolt.ai/agent/tools/mark-as-resolved-tool`)
— bem vaga, fala em "critérios predefinidos" e "configurações customizáveis" sem detalhar nada
de operação (não diz se a IA para de responder, se dá pra reabrir, se notifica alguém). Pouco a
copiar tecnicamente; desenho baseado no que o Wenzap já tem.

## Achado de arquitetura

Igual ao Solicitar Humano: o modelo decide **no meio de um turno** que o problema acabou e chama
a tool — mesmo padrão de `agent_tools`/`tool_type`, reaproveitando `build_tool_schema`/
`build_tool_dispatch`/o mesmo `Conversation` já passado por contexto. Zero infraestrutura nova
além de uma coluna.

**Achado de risco, não documentado pelo Chatvolt**: hoje não existe nenhuma reabertura automática
de conversa `resolved`. No widget (conversa presa a uma sessão), uma mensagem nova do cliente cai
numa conversa resolvida e a IA fica muda pra sempre até um humano notar. No WhatsApp o sistema já
"resolve" sozinho criando uma conversa nova. Sem corrigir isso, dar ao modelo o poder de marcar
resolvido sozinho aumenta a chance real desse buraco ser atingido (LLM errando que o problema
acabou não é incomum).

## Objetivo

O agente encerra a conversa sozinho quando o cliente confirma que o problema foi resolvido, com
um resumo curto visível no Inbox — e sem risco de travar silenciosamente o atendimento se o
cliente voltar a escrever.

## Não-objetivos

- **Reabrir automaticamente no canal WhatsApp.** Lá uma mensagem nova já gera conversa nova
  (comportamento pré-existente, equivalente a "abrir um novo ticket") — não é o mesmo buraco do
  widget, fica fora do escopo.
- **Fechar/mover `PipelineEntry` vinculada.** Hoje o acoplamento Pipeline↔Conversa é só numa
  direção (etapa empurra status pra conversa, não o contrário) — marcar resolvido não mexe em
  nenhum card de pipeline. Registrado como possível PRD futuro, não bloqueia este.
- **Gate de plano.** Mesma linha do Solicitar Humano — recurso básico de atendimento, não
  automação avançada.

## Design

### Config e input do modelo

`tool_type="mark_resolved"`, config vazio (`MarkResolvedToolConfig`, mesmo padrão do
`RequestHumanToolConfig` — toggle puro, `name`/`description` controlam o gatilho). Input
obrigatório: `resolution_summary` (string) — sem isso o campo fica vazio na prática e perde o
valor de "revisar o que a IA fechou sozinha sem reabrir cada uma".

### Execução

`execute_mark_resolved_tool()`, mesmo formato do `execute_request_human_tool`:
- Idempotente: se `conversation.status` já é `"resolved"`, não faz nada, devolve aviso pro
  modelo em vez de sobrescrever.
- Seta `conversation.status = "resolved"` + `conversation.resolution_summary` (coluna nova,
  paralela à `handoff_reason`) — **não mexe em `ai_enabled`/`assigned_user_id`**, mesmo efeito do
  dropdown manual "Resolvida" no Inbox hoje.
- Modo simulação no Playground (sem `conversation` real) — mesmo padrão do Solicitar Humano, sem
  side effects.

### Reabertura automática (fecha o risco encontrado)

Em `conversation_message_service.create_message`, no branch `sender_type="customer"`: se
`conversation.status == "resolved"`, volta pra `"open"` e limpa `resolution_summary` antes do
check de elegibilidade de auto-reply — a próxima mensagem do cliente já cai numa conversa aberta,
IA responde normalmente. Cobre widget + qualquer chamada autenticada de API (única função usada
por esses dois caminhos). Mesma limpeza de `resolution_summary` em `update_conversation`
(`conversation_service.py`) quando o status muda manualmente pra algo diferente de `resolved`.

## Migrations necessárias

Uma migration: `conversations.resolution_summary` (nullable, `String(500)`, mesmo formato de
`handoff_reason`).

## Critério de "pronto"

Um agente qualquer (sem gate de plano) liga "Marcar como resolvido", o modelo decide sozinho
durante uma conversa real quando o problema acabou, a conversa vira "Resolvida" com o resumo
visível no Inbox, e se o cliente voltar a escrever depois (no widget), a conversa reabre sozinha
e a IA volta a responder — sem intervenção manual.

## Referências

- `app/services/agent_tool_service.py` — `execute_request_human_tool`, template direto pra
  `execute_mark_resolved_tool`.
- `docs/agents/request-human-tool-prd.md` — mesma infra de tool-calling reaproveitada.
- Pesquisa competitiva: doc pública do Chatvolt
  (`docs.chatvolt.ai/agent/tools/mark-as-resolved-tool`).

## Estado da implementação (2026-07-18)

**Backend, arquivos novos:**
- `alembic/versions/071_conversation_resolution_summary.py` — coluna
  `conversations.resolution_summary`, sem tabela nova (reaproveita `agent_tools` por completo).

**Backend, arquivos modificados:**
- `app/models/conversation.py` / `app/schemas/conversation.py` — `resolution_summary`.
- `app/schemas/agent_tool.py` — `MarkResolvedToolConfig` (vazio, igual ao
  `RequestHumanToolConfig`); `tool_type` amplo pra incluir `"mark_resolved"`.
- `app/services/agent_tool_service.py` — `build_tool_schema`/`build_tool_dispatch` estendidos;
  `execute_mark_resolved_tool` (idempotente, modo simulação no Playground, não mexe em
  `ai_enabled`/`assigned_user_id`). **Achado durante a implementação**: `RequestHumanToolConfig`
  e `MarkResolvedToolConfig` são estruturalmente idênticos (ambos vazios), então a união do
  Pydantic pode resolver um `config={}` pra qualquer um dos dois indistintamente — corrigido
  trocando o `isinstance` único por checagem de pertencimento num tuple das duas classes vazias
  em `_validate_tool_config` (só o `HttpToolConfig`, que exige `url`, é distinguível de verdade).
- `app/services/conversation_message_service.py` — reabertura automática: mensagem de cliente
  numa conversa `resolved` volta pra `open` e limpa `resolution_summary`, antes do check de
  elegibilidade de auto-reply (a IA já responde na mesma mensagem que reabriu).
- `app/services/conversation_service.py` — `update_conversation` limpa `resolution_summary`
  quando o status muda manualmente pra algo diferente de `resolved`.
- `app/routers/agents.py` — rotas `/tools/mark-resolved` (create/update/delete), sem gate de
  plano, mesmo padrão do Solicitar Humano.
- **Nenhuma mudança necessária** em `conversation_agent_reply_service.py`/`agent_test_service.py`
  — `build_tool_dispatch` já era genérico o bastante (thread de `db`/`workspace_id`/
  `conversation` reaproveitado de quando o Solicitar Humano foi implementado).

**Frontend (`ConfigFerramentas.tsx`):**
- `RoadmapCard` "Marcar como resolvido" ("Em breve") virou card funcional + modal (toggle +
  descrição editável), mesmo padrão do Solicitar Humano, sem `PlanGateBadge`.
- Como essa era a última tool "Em breve" da aba, o componente `RoadmapCard` (e o ícone `Clock`
  que só ele usava) viraram código morto — removidos.
- `ConversationHeader.tsx` — `resolution_summary` exibido como linha secundária quando
  `status === "resolved"`, mesmo padrão visual do `handoff_reason`.
- `apps/web/src/lib/api.ts` — `MarkResolvedToolConfig`/`MarkResolvedAgentTool` types,
  `api.agents.markResolvedTool.*`, `Conversation.resolution_summary`.

**Testes novos**: seção `mark_resolved` espelhando `request_human` em `test_agent_tools.py`
(CRUD, schema, dispatch, execução idempotente/simulação — incluindo teste específico da
ambiguidade de union descrita acima), teste ponta a ponta em
`test_agent_tool_calling_integration.py` (loop completo via `generate_conversation_agent_reply`,
plano starter), testes de reabertura automática em `test_conversation_messages.py` (reabre só
com mensagem de cliente, não com nota interna) e de limpeza de `resolution_summary` em
`test_conversations.py`.

**Verificação:** 2117 testes de backend passando (mesmos 8 pré-existentes sem relação de
sempre), `tsc --noEmit` limpo, `next build` limpo. **Não testado visualmente em navegador nem em
produção** — sem ferramenta de automação de browser disponível na sessão.
