# PRD — Tool "Solicitar humano" (handoff estruturado)

**Status: ✅ Implementado (2026-07-17)** — segunda tool real do sistema de tool-calling
(`docs/agents/agent-tool-calling-prd.md`), sem gate de plano. 2081 testes de backend passando
(13 novos desta feature), build de frontend limpo. Ver seção "Estado da implementação" no fim.

## Contexto

A aba Ferramentas (`ConfigFerramentas.tsx`) já tinha "Solicitar humano" desenhado como
`RoadmapCard` ("Em breve") desde antes do tool-calling existir. Agora que a infraestrutura de
tool-calling está pronta e provada em produção (HTTP genérico), essa é a tool natural a
implementar em seguida — não precisa de nenhuma peça de infraestrutura nova, só um novo
`tool_type` + a lógica de handoff que já existe parcialmente no produto (`Conversation.ai_enabled`
+ `assigned_user_id`, `take_over_conversation()`/`return_to_ai()`, badges "IA ativa"/"IA
pausada"/"Atendimento humano" no Inbox).

**Pesquisa competitiva** (Chatvolt, via doc pública): a "Request Human Tool" deles é um toggle
puro, zero parâmetros de configuração — o modelo decide sozinho quando chamar, orientado só pela
descrição da tool. A notificação de quem deveria atender é responsabilidade do cliente
(integração com o sistema genérico de Agent Webhooks deles, sem evento dedicado de handoff).

## Objetivo

Permitir que o agente, durante uma conversa, decida pausar a IA e sinalizar que aquele
atendimento precisa de um humano — sem o operador escrever nenhum JSON, só uma descrição em
português de quando isso deve acontecer (mesmo modelo mental já usado no HTTP Tool). Diferencial
sobre o Chatvolt: **notificação nativa por e-mail** para quem deveria atender, em vez de exigir
que o cliente monte sua própria integração de webhook — decisão que segue a
[[feedback pré-existente]] de o público do Wenzap (PME menos técnica) precisar de "funciona sem
configurar nada extra".

## Não-objetivos

- **Atribuir a conversa a um operador específico.** O handoff deixa a conversa "IA pausada" e
  sem dono (`assigned_user_id = None`) — igual ao estado que já existe hoje quando ninguém
  clicou "Assumir" ainda. Roteamento automático para o operador certo é um problema diferente
  (existe como item futuro separado no roadmap: "Atribuição de conversa a operador").
- **Confirmação humana antes de disparar.** O modelo decide e executa direto, como qualquer
  outra tool — não há "pedir permissão" no meio.
- **Notificação por outros canais (Slack, push).** Só e-mail nesta fase — mesma decisão que
  `agent_alert_service.py` já tinha como TODO não implementado; aqui vira o primeiro canal de
  notificação de fato implementado no produto, mas só o canal e-mail.
- **Multi-provider.** Só Anthropic, mesma decisão do PRD de tool-calling.

## Gate de plano

**Sem gate — disponível em todos os planos**, decisão de produto (confirmada com o Lucas
2026-07-17). Diferente do HTTP Tool (Scale+, tratado como "automação avançada"), handoff para
humano é tratado como recurso básico de atendimento — mesma categoria que assumir conversa/Inbox,
que também não são gated hoje. Não precisa de nova linha em `plan_features`; o call-site
simplesmente não chama `plan_allows_feature`/`workspace_allows_feature` para este `tool_type`.

## Design

### Modelo de dados — reaproveita `agent_tools`

Novo `tool_type = "request_human"` na tabela já existente (`app/models/agent_tool.py`), sem
migration de tabela nova. `config` fica **vazio** (`RequestHumanToolConfig`, sem campos) — o
único input do operador é `name`/`description` (colunas genéricas já existentes), que
determinam quando o modelo aciona a tool. Isso é deliberado: reduz a configuração ao mínimo
(como o Chatvolt), mas ainda dá controle real ao operador via linguagem natural na descrição
(ex: "aciona quando o cliente pedir reembolso, reclamar de forma clara, ou perguntar algo fora
do que você sabe responder").

Nova migration (`068`): coluna `Conversation.handoff_reason: str | None` — motivo capturado do
modelo no momento do handoff (parâmetro `reason` do tool call), exibido no Inbox pro operador
não precisar reler a conversa inteira pra entender o contexto. Limpo (`None`) quando a conversa
volta pra IA (`return_to_ai()`), já que deixa de ser relevante.

### Input schema exposto ao modelo

```json
{
  "type": "object",
  "properties": {
    "reason": {
      "type": "string",
      "description": "Motivo pelo qual o atendimento está sendo transferido para um humano."
    }
  },
  "required": ["reason"]
}
```

`reason` obrigatório — sem ele a auditoria/notificação/Inbox perdem o principal valor da feature
(saber *por quê* sem reler tudo).

### Execução (`execute_request_human_tool`)

Diferente do HTTP Tool (`execute_http_tool`, puramente funcional — recebe `config`+`input`, sem
estado externo), esta tool precisa de contexto de conversa (`db`, `workspace_id`, `conversation`)
que o HTTP Tool nunca precisou. `build_tool_dispatch()` ganha esse contexto como parâmetros
opcionais, passados pelos dois call-sites (`conversation_agent_reply_service.py`,
`agent_test_service.py`):

- **No Inbox/WhatsApp** (`conversation` real disponível): se `conversation.ai_enabled` ainda for
  `True` (não foi chamada antes nesse mesmo turno — proteção contra chamada duplicada no loop de
  até 5 iterações), seta `ai_enabled = False`, grava `handoff_reason`, dispara e-mail best-effort
  (nunca derruba o turno se falhar — mesmo padrão de `agent_alert_service.notify_agent_error`) e
  devolve pro modelo uma confirmação curta pra ele formular a resposta final ao cliente. Se já
  tinha sido chamada antes no mesmo turno, devolve aviso de que já foi transferido, sem duplicar
  notificação.
- **No Playground** (sem `conversation` real — é uma sessão de teste, não existe linha em
  `conversations`): executa em **modo simulação** — não muta nada, não manda e-mail, só devolve
  um texto indicando o que aconteceria numa conversa real. Evita que testar o agente no
  Playground dispare e-mails de handoff pra equipe toda hora.

### Notificação por e-mail

Destinatários: membros ativos do workspace com role `owner`/`admin` (novo helper,
`_get_workspace_notify_recipients`, reaproveitando o mesmo join de `member_service.list_members`
filtrado por role/status). Template novo em `email_templates.py`
(`handoff_requested_email_html`/`_text`), mesmo padrão visual dos templates existentes (card
escuro, verde `#00E09A`), com nome do agente, nome do contato (se houver), o `reason` capturado e
um link direto pra conversa no Inbox (`{app_url}/dashboard/inbox?conversation={id}`).

### UI (`ConfigFerramentas.tsx`)

Troca o `RoadmapCard` "Solicitar humano" ("Em breve") por um card funcional, mais simples que o
de HTTP Tools — sem lista de múltiplas instâncias (só faz sentido ter **uma** por agente): toggle
liga/desliga direto no card + descrição editável num modal leve (nome fixo `solicitar_humano`,
não editável — não há por quê o operador escolher outro nome pra uma tool com semântica fixa).
Sem `PlanGateBadge` (sem gate de plano).

Inbox (`ConversationHeader.tsx`): o badge "IA pausada" (estado hoje sem contexto nenhum) ganha
uma linha secundária mostrando `conversation.handoff_reason` quando presente — só aparece nesse
estado porque é exatamente o que uma conversa pausada por essa tool produz (diferente do
"Atendimento humano", que é quando alguém já clicou "Assumir" manualmente).

## Critério de "pronto"

Um agente qualquer (qualquer plano) consegue ligar "Solicitar humano" na aba Ferramentas,
escrever quando deve acionar, e o modelo decide sozinho durante uma conversa real (Inbox/WhatsApp)
quando transferir — a conversa vira "IA pausada" com o motivo visível no header, um e-mail chega
pro owner/admin do workspace, e o Playground simula o comportamento sem side effects reais.

## Referências

- `docs/agents/agent-tool-calling-prd.md` — infraestrutura reaproveitada (executor, `agent_tools`,
  guardrails).
- `app/services/conversation_service.py` — `take_over_conversation`/`return_to_ai`, mecânica de
  `ai_enabled`/`assigned_user_id` já existente, reaproveitada sem mudança de contrato.
- `app/services/email_service.py`/`email_templates.py` — infraestrutura de e-mail transacional
  (Resend) já existente, primeiro uso fora do fluxo de auth.
- Pesquisa competitiva: doc pública do Chatvolt (`docs.chatvolt.ai/agent/tools/request-human-tool`).

## Estado da implementação (2026-07-17)

**Backend, arquivos novos:**
- `alembic/versions/068_conversation_handoff_reason.py` — coluna `conversations.handoff_reason`.
- Testes: seção nova em `tests/test_agent_tools.py` (CRUD via `/tools/request-human`, gate
  cruzado tool_type↔rota, `build_tool_schema`, `execute_request_human_tool` simulação/real/
  idempotência/falha de notificação) + teste de integração ponta a ponta em
  `tests/test_agent_tool_calling_integration.py` (loop completo via
  `generate_conversation_agent_reply`, plano starter — confirma ausência de gate).

**Backend, arquivos modificados:**
- `app/models/agent_tool.py` (sem mudança de schema — só novo `tool_type` na coluna existente),
  `app/models/conversation.py` (`handoff_reason`).
- `app/schemas/agent_tool.py` — `RequestHumanToolConfig` (vazio, `extra="forbid"`), união
  `HttpToolConfig | RequestHumanToolConfig`, `tool_type` amplo pra `Literal["http_request",
  "request_human"]`.
- `app/services/agent_tool_service.py` — `build_tool_schema`/`build_tool_dispatch` estendidos;
  `execute_request_human_tool` (modo simulação no Playground, idempotente dentro do mesmo turno,
  notificação best-effort nunca derruba o turno); `_get_workspace_notify_recipients` (owner/admin
  ativos); `_validate_tool_config` agora valida `isinstance` além do `tool_type`.
- `app/services/email_templates.py` — `handoff_requested_email_html`/`_text`, mesmo padrão visual
  dos templates existentes.
- `app/services/conversation_service.py` — expõe `handoff_reason`, limpo em `return_to_ai()`.
- `app/schemas/conversation.py` — `ConversationOut.handoff_reason`.
- `app/routers/agents.py` — rotas `/tools/request-human` (create/update/delete, sem gate de
  plano) + `_require_tool_type()` (impede criar `http_request` via `/tools/request-human` e
  vice-versa — sem isso, a rota sem gate poderia ser usada pra burlar o 402 do `http_tools`).
- `app/services/conversation_agent_reply_service.py` / `app/services/agent_test_service.py` —
  `enabled_tools` agora é buscado sempre (não só quando `http_tools` está liberado); filtragem por
  `tool_type` decide quem é usável; `build_tool_dispatch` recebe `db`/`workspace_id`/`conversation`
  no fluxo de produção (ausentes no Playground → modo simulação automático).

**Frontend:**
- `apps/web/src/lib/api.ts` — `AgentTool` virou union discriminada por `tool_type`
  (`HttpAgentTool`/`RequestHumanAgentTool`), `RequestHumanToolConfig`, `api.agents.
  requestHumanTool.*`; `Conversation.handoff_reason`.
- `apps/web/src/components/agents/workspace/tabs/ConfigFerramentas.tsx` — `RoadmapCard`
  "Solicitar humano" ("Em breve") virou card funcional (toggle + descrição editável num modal
  único, sem lista — só faz sentido uma instância por agente), sem `PlanGateBadge` (sem gate).
  HTTP Tools filtrado corretamente por `tool_type` agora que a lista compartilhada retorna os
  dois tipos.
- `apps/web/src/components/inbox/ConversationHeader.tsx` — `handoff_reason` exibido como linha
  secundária só no estado "IA pausada" sem humano atribuído (o estado que essa tool produz,
  distinto de "Assumir" manual).

**Verificação:** 2081 testes de backend passando (mesmos 8 pré-existentes sem relação de sempre —
5 em `test_ai_models.py`, 3 em `test_agent_test.py`, confirmado via `git stash` que já falhavam
antes desta feature), `tsc --noEmit` limpo, `next build` limpo.
