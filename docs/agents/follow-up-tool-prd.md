# PRD — Follow-up automático (reengajamento por silêncio)

**Status: ✅ Implementado (2026-07-18)** — terceiro item da aba Ferramentas a sair de
"Em breve" nesta leva (depois de HTTP Tool e Solicitar Humano), mas **arquiteturalmente
diferente dos dois**: não é uma tool que o modelo decide chamar no meio de um turno, é uma
varredura em background que decide iniciar um turno novo quando não há nenhuma mensagem
disparando isso. 2101 testes de backend passando (28 novos, incluindo o adendo de instrução por
degrau), build de frontend limpo. Ver
"Estado da implementação" no fim.

## Contexto

Pesquisa competitiva: doc pública do Chatvolt
(`docs.chatvolt.ai/agent/tools/follow-up-messages-tool`). O deles é zero-config — prazo fixo por
canal (WhatsApp/Telegram 16h, Web 4h), sem cancelamento documentado, sem limite de envios, 2
créditos fixos por follow-up, "pré-configurado, sem configuração adicional necessária".

Decisões de produto tomadas com o Lucas antes deste PRD (2026-07-17/18):
1. **Prazo configurável por agente**, não fixo por canal como o Chatvolt.
2. **Múltiplos follow-ups com prazos crescentes** (ex: 6h, 24h, 72h), não só um.
3. **IA gera o texto sozinha**, com um campo opcional de instrução/tom pro operador guiar.

## Achado de arquitetura (o que muda o desenho)

A infra de tool-calling que acabamos de construir (`agent_tools`, `agent_llm_executor.py`) é
estritamente para o **modelo decidir usar algo no meio de um turno já em andamento** — existe
`tool_use` porque existe uma chamada ao LLM rolando. Follow-up é o oposto: não há mensagem nova
disparando nada, é o **backend** que decide iniciar um turno depois de um período de silêncio.
Não existe `tool_use` pra emitir. Forçar isso em `agent_tools` seria um encaixe errado.

O padrão certo já existe no código: o **sweep scheduler do Pipeline.2**
(`app/services/pipeline_stay_limit_scheduler.py`) — uma thread daemon única, dorme, varre o
banco periodicamente procurando linhas que passaram de um prazo, e age. Mesmo princípio de
design (recalcula o estado a cada passada em vez de "lembrar" um agendamento — se a condição
não bate mais, simplesmente não age; não precisa de lógica de cancelamento).

## Objetivo

Quando o cliente para de responder, o agente manda uma ou mais mensagens de reengajamento em
prazos crescentes configurados pelo operador, sem que isso dependa de nenhuma mensagem nova
chegando — e para sozinho de mandar mais se o cliente responder.

## Não-objetivos

- **Múltiplos replicas / distributed lock de verdade.** Mesma limitação já aceita no scheduler
  do Pipeline.2 — single-replica hoje, e o design (constraint única no banco) já deixa migrar
  pra multi-replica seguro depois, sem redesenhar o guard.
- **Web push pra conversas de widget fechado.** O follow-up ainda é gerado e salvo na thread pra
  conversas de `web_widget`, mas só é **entregue** de verdade (ping ativo) em conversas de
  WhatsApp — não existe canal de push pro navegador do cliente hoje.
- **Editar o texto gerado antes de enviar.** Sai direto, igual a uma resposta normal do agente —
  mesma filosofia de "o agente decide e age" já usada nas outras duas tools.

## Design

### Âncora do prazo: `Conversation.last_customer_message_at` (coluna nova)

Não dá pra usar `last_message_at` puro — cada follow-up enviado atualiza esse campo, e prazos
crescentes (6h, 24h, 72h) precisam ser contados a partir de **quando o cliente escreveu por
último**, não da nossa própria última mensagem. Coluna nova, populada só quando
`sender_type="customer"`, nos três pontos onde mensagem inbound de cliente é criada
(`conversation_message_service.create_message`, `whatsapp_inbound_service._create_message_idempotent`
— o widget público já passa pelo primeiro). Conversas existentes ficam com o campo `NULL` até a
próxima mensagem do cliente — sem backfill, sem risco de disparar uma onda de follow-up em
conversas antigas no deploy.

### Configuração — dois satélites novos, mesmo padrão do módulo

- **`agent_follow_up_settings`** (1:1 por agente): `is_enabled`, `custom_instructions` (opcional,
  instrução **geral**, aplicada a todos os degraus — o prompt já informa ao modelo qual follow-up
  é e quanto tempo passou, então ele varia o tom sozinho mesmo sem nenhuma instrução específica).
- **`agent_follow_up_steps`** (1:N, ordenado): `step_order` + `delay_hours` + `custom_instructions`
  (opcional, ver adendo abaixo). Editado como lista na UI (adicionar/remover degrau); salvo como
  replace completo da lista a cada PUT (mesma simplicidade do "reorder stages" do Pipeline).
  Validação: horas estritamente crescentes entre degraus, 1 a 5 degraus, 1–500h por degrau.
- Endpoint dedicado `GET`/`PUT /agents/{agent_id}/follow-up`, no padrão do
  `AgentCatalogScope` (não embutido no `PATCH /agents/{id}` geral como
  model/prompt settings).

### Auditoria + trava de concorrência: `conversation_follow_ups`

Cada envio vira uma linha: `conversation_id`, `step_order`, **`silence_anchor`** (cópia do
`last_customer_message_at` no momento do envio — não o valor atual, que pode já ter mudado),
`conversation_message_id`, `sent_at`. **Constraint única em
`(conversation_id, step_order, silence_anchor)`** — é isso que garante que o mesmo degrau nunca
é mandado duas vezes pro mesmo período de silêncio, mesmo sob concorrência (dois processos
tentando inserir a mesma claim colidem no banco, um perde). Contar quantos degraus já foram
mandados *para o período de silêncio atual* é só `WHERE conversation_id = ? AND silence_anchor =
last_customer_message_at` — se o cliente responde, `last_customer_message_at` muda, a contagem
zera sozinha, nenhum follow-up antigo "conta" mais. Isso também é o cancelamento: não existe
lógica explícita de cancelar, o próximo sweep simplesmente não encontra mais a condição.

### Sweep — mesmo padrão do Pipeline.2, thread separada

`app/services/conversation_follow_up_scheduler.py`, intervalo de 5 min (não precisa da
granularidade de 60s do stay_limit — aqui a unidade é hora). A cada passada: acha conversas
elegíveis (`ai_enabled=True`, sem humano atribuído, canal WhatsApp/Web Widget,
`last_customer_message_at` não nulo), verifica gate de plano (`workspace_allows_feature(db,
workspace_id, "follow_up")` — **já seedado**, Scale+/Enterprise, sem migration de billing
necessária), verifica se o agente tem follow-up ligado e configurado, calcula quantos degraus já
foram mandados nesse período de silêncio, e se o próximo degrau já venceu, tenta a claim.

**Fluxo "claim-then-generate":** insere a linha de auditoria primeiro (a claim), tenta
`db.flush()` — se colidir com a constraint única (`IntegrityError`), outro processo já pegou
esse degrau, desiste sem gastar chamada de LLM. Se a claim passar, gera o conteúdo (reaproveitando
`run_agent_turn`/`build_system_prompt`, sem tools anexadas) e só confirma a transação inteira
(mensagem + créditos + claim) se tudo der certo — se faltar crédito ou o LLM falhar, `rollback()`
desfaz a claim também, e o degrau pode ser tentado de novo no próximo sweep.

### Geração de conteúdo

Reaproveita quase tudo do fluxo de resposta normal: `build_system_prompt` (identidade/persona do
agente, sem RAG/catálogo — não há pergunta nova do cliente pra buscar contexto), histórico
recente formatado (mesmo `SENDER_LABELS` já usado em `conversation_context_builder.py`). O que
muda é só a instrução final, que passa a ser algo como *"O cliente está em silêncio há N horas.
Esta é a mensagem de follow-up #K de M. Escreva uma mensagem curta e natural pra reengajar, sem
soar como cobrança."* — mais a instrução customizada do operador, se houver.

Créditos: cobrados pela **mesma tabela de créditos por modelo** já usada nas respostas normais
(`calculate_credits`), não um valor fixo tipo o "2 créditos" do Chatvolt — mais justo, escala
com o modelo escolhido pelo agente.

## Adendo (2026-07-18) — instrução opcional por degrau

Pergunta do Lucas depois do primeiro deploy: dá pra dar uma instrução diferente pra cada degrau,
não só uma geral pra todos? Faz sentido pra sequências onde os degraus não são só "o mesmo
lembrete com tom mais forte", mas mudam de estratégia mesmo — ex: degrau 1 é um "oi, ainda aí?",
degrau 3 já oferece um cupom de desconto específico. O campo único de `custom_instructions` (na
Fase 1) não cobre bem esse caso.

**Design**: novo campo opcional `custom_instructions` direto em `agent_follow_up_steps` (uma
coluna, sem tabela nova). Continua opcional — se o operador deixar em branco, o degrau usa só a
instrução geral (ou nenhuma), mantendo a simplicidade de configuração de hoje pra quem não
precisa de controle fino. Quando preenchido, as duas instruções (geral + do degrau) são
combinadas no prompt do follow-up, rotuladas separadamente, pra deixar claro pro modelo qual é
orientação de tom permanente e qual é específica daquele degrau — não uma substitui a outra.

Sem mudança na trava de concorrência (`conversation_follow_ups`), no gate de plano, nem no
sweep — só o texto passado pra `_build_follow_up_instruction` muda.

## Migrations necessárias

Migration `069`: `conversations.last_customer_message_at` (nullable) +
`agent_follow_up_settings` + `agent_follow_up_steps` + `conversation_follow_ups`.
Migration `070` (adendo): `agent_follow_up_steps.custom_instructions` (nullable).

## Feature flag / gating

`follow_up` já existe em `plan_features` (Scale+/Enterprise) desde antes deste PRD — só falta o
call-site no scheduler e no endpoint de update (gate só quando `is_enabled=True`, mesmo padrão
de "sempre pode desligar/editar mesmo sem o plano" já usado no HTTP Tool).

## Critério de "pronto"

Um agente em plano Scale+ liga follow-up, configura 2–3 degraus com prazos crescentes, o cliente
para de responder no WhatsApp, e as mensagens chegam nos horários certos — param de chegar se o
cliente responder antes, créditos são contabilizados corretamente, e nada disso depende de
nenhuma mensagem nova disparando o processo.

## Referências

- `app/services/pipeline_stay_limit_scheduler.py` — padrão de sweep reaproveitado.
- `app/services/conversation_context_builder.py` — formatação de histórico/`build_system_prompt`
  reaproveitados.
- `app/services/conversation_agent_reply_service.py` — padrão de checagem/consumo de créditos.
- Pesquisa competitiva: doc pública do Chatvolt
  (`docs.chatvolt.ai/agent/tools/follow-up-messages-tool`).

## Estado da implementação (2026-07-18)

**Backend, arquivos novos:**
- `alembic/versions/069_conversation_follow_up.py` — `conversations.last_customer_message_at`
  + `agent_follow_up_settings` + `agent_follow_up_steps` + `conversation_follow_ups`.
- `app/models/agent_follow_up_settings.py`, `app/models/agent_follow_up_step.py`,
  `app/models/conversation_follow_up.py`.
- `app/schemas/agent_follow_up.py` — validação de degraus crescentes (1–5, 1–500h cada) no
  `model_validator`.
- `app/services/agent_follow_up_service.py` — CRUD get-or-create + replace-completo de degraus.
- `app/services/conversation_follow_up_service.py` — geração (reaproveita `build_system_prompt`/
  `run_agent_turn`) + envio + créditos, tudo numa transação só.
- `app/services/conversation_follow_up_scheduler.py` — sweep de 5 em 5 min, claim-then-generate
  via constraint única no banco.
- Testes novos: `tests/test_agent_follow_up_settings.py` (CRUD + gate de plano + validação),
  `tests/test_conversation_follow_up_scheduler.py` (elegibilidade, degraus múltiplos, reset por
  resposta do cliente, trava de concorrência).

**Backend, arquivos modificados:**
- `app/models/conversation.py` — `last_customer_message_at`.
- `app/services/conversation_message_service.py` / `app/services/whatsapp_inbound_service.py` —
  populam `last_customer_message_at` nos dois pontos reais de mensagem inbound de cliente (o
  widget público passa pelo primeiro, não precisou de mudança própria).
- `app/routers/agents.py` — `GET`/`PUT /agents/{id}/follow-up`, gate de plano só quando
  `is_enabled=True` (mesmo padrão do HTTP Tool: sempre dá pra desligar/editar sem o plano).
- `app/main.py` — registra a nova sweep no `lifespan`, junto com a do Pipeline.2.

**Achado colateral (não corrigido, fora de escopo):** o padrão `Model.__new__(Model)` +
atribuição de atributos, usado como stub de fallback em `conversation_context_builder.py`
(`_load_prompt_settings`) e `agent_test_service.py` (`_get_prompt_settings`) pra agentes sem
`AgentPromptSettings`, está **quebrado** — `AttributeError` porque `__new__` nunca inicializa
`_sa_instance_state` do SQLAlchemy (reproduzido isoladamente). Só afeta agentes criados antes da
tabela satélite existir, provavelmente dormant em produção hoje (nenhum agente novo cai nesse
caminho). Meu código evita o padrão (usa `SimpleNamespace`), mas os outros dois pontos continuam
com o bug latente — vale um follow-up dedicado depois.

**Frontend (`ConfigFerramentas.tsx`):**
- `RoadmapCard` "Follow-up" ("Em breve") virou card funcional + modal (toggle, editor de degraus
  com "+ Add degrau"/remover, campo de instrução opcional), com `PlanGateBadge` (Scale+, mesmo
  padrão do HTTP Tool).
- `apps/web/src/lib/api.ts` — `AgentFollowUpSettings`/`AgentFollowUpStep` types,
  `api.agents.followUp.get/update`.

**Verificação:** 2095 testes de backend passando na entrega principal (mesmos 8 pré-existentes sem relação de
sempre), `tsc --noEmit` limpo, `next build` limpo. **Não testado visualmente em navegador nem em
produção** — sem ferramenta de automação de browser na sessão, e o sweep em si só é observável
esperando horas reais passarem; roteiro de teste manual documentado no NexBrain.

## Estado da implementação do adendo (2026-07-18)

- `alembic/versions/070_agent_follow_up_step_instructions.py` — coluna
  `agent_follow_up_steps.custom_instructions` (nullable, sem mudança nas outras tabelas).
- `app/models/agent_follow_up_step.py` / `app/schemas/agent_follow_up.py` — campo novo em
  `AgentFollowUpStepInput`/`Out`.
- `app/services/conversation_follow_up_service.py` — `_build_follow_up_instruction` agora recebe
  `general_instructions`/`step_instructions` separados, combina os dois no prompt (rotulados,
  nenhum substitui o outro).
- `app/services/conversation_follow_up_scheduler.py` — passa `next_step.custom_instructions`
  pra `generate_and_send_follow_up`.
- Testes novos: `tests/test_conversation_follow_up_service.py` (4 casos — nenhuma/geral/degrau/
  ambas as instruções), mais 1 teste de persistência em `test_agent_follow_up_settings.py` e 1
  ponta a ponta em `test_conversation_follow_up_scheduler.py` confirmando que as duas instruções
  chegam combinadas no prompt real enviado ao LLM. 2101 testes de backend passando no total (28
  novos desde o `v0.3.9`), `tsc`/`next build` limpos.
- Frontend: editor de degraus (`FollowUpStepsEditor`) ganhou um campo de texto por linha,
  opcional; campo geral existente renomeado pra deixar claro que vale pra todos os degraus.
