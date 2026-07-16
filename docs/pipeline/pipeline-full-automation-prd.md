# PRD — Pipeline 100% Funcional (Pipeline.2)

**Status: ✅ Implementado (2026-07-16)** — Fases 0-6 completas (backend + frontend + testes).
Ver `docs/pipeline/conversation-pipeline-foundation.md` pro estado final documentado por tabela/endpoint.
Backlog fora deste PRD (templates de pipeline, API pública de criação de conversa, tags,
notificação SMS) segue como itens futuros no ROADMAP.md.

## Contexto

Pipeline.1 (`conversation-pipeline-foundation.md`) entregou o esqueleto: pipelines, etapas, cards (entries), board Kanban, `extra_prompt` injetado no agente, e atribuição automática de conversa nova ao pipeline/etapa padrão do agente. Isso está sólido e em produção.

O problema: a etapa "Avançado" do formulário de etapa (`webhook_url`, `stay_limit_minutes`, `entry_condition`, `is_removal_stage`, `request_contact_info`) salva dados que **nunca são executados**. O cliente configura um webhook, acha que está funcionando, e nada dispara. Isso foi decisão consciente do Pipeline.1 ("salvo, não executado nesta fase") mas nunca foi comunicado na UI — ao contrário da aba Ferramentas do agente, que marca claramente "Em breve" nos itens não prontos.

Auditoria comparativa contra o FluxVolt (Chatvolt), produto que inspirou o desenho deste módulo, confirmou que o schema foi copiado quase campo por campo (`entry_condition`, `extra_prompt`, `is_removal_stage`, `request_contact_info`, `stay_limit_minutes` ≈ "Auto Next Step", `webhook_url`) mas apenas o CRUD foi construído — nenhuma camada de execução. O FluxVolt implementa todos esses campos de verdade: `entry_condition` é avaliada automaticamente a cada mensagem para decidir se a conversa deve mudar de etapa; webhooks disparam de verdade no evento `STEP_ENTERED`; "Auto Next Step" move a conversa sozinha após X minutos na etapa. Nem o FluxVolt tem o agente movendo cards via tool-calling autônomo — a automação deles é o **sistema avaliando uma condição a cada mensagem**, não o LLM decidindo via function call. Isso importa porque significa que dá para alcançar paridade sem construir infraestrutura de tool-calling.

## Objetivo

Fazer o módulo de Pipeline funcionar de ponta a ponta: todo campo que hoje é salvo e ignorado passa a ter efeito real, ou é removido/marcado como não disponível até ser construído. Nenhum campo "fantasma" deve continuar existindo na UI depois deste PRD.

## Não-objetivos (fora de escopo)

- Tool-calling/function-calling genérico para agentes (LLM decidindo ações via structured output) — mencionado no PRODUCT_VISION como visão de longo prazo, mas não é necessário para paridade com FluxVolt neste módulo, e é um projeto à parte, maior que Pipeline.
- Notificação SMS (Z-Api) — o Wenzap não tem provedor de SMS integrado hoje; replicar essa feature específica do FluxVolt exigiria contratar/integrar um provedor novo, sem relação com o problema central (campos inertes). Fica de fora até haver demanda real de cliente.
- Templates de pipeline (duplicar um pipeline pronto) e API pública de criação de conversa — valem a pena, mas não fazem parte do problema "campo salvo e ignorado"; ficam como backlog no final deste documento.

## Princípio: automação é Growth+, ação manual continua Free

Mantém a decisão já tomada em Pipeline.1: tudo que é automação (webhook, entry_condition, stay_limit, ações automáticas de etapa) é gated pela feature `pipeline_automations` (nova flag) restrita a planos pagos. CRUD manual continua disponível no Free. Isso também limita custo de infra (LLM calls extras, disparo de webhook) a workspaces pagantes.

---

## Fase 0 — Honestidade de UI + fix de bug (pré-requisito, sem dependências)

**Por quê primeiro:** custo quase zero, resolve a pior parte do problema (cliente configurando algo que não funciona) imediatamente, sem esperar as fases seguintes.

**O que fazer:**
1. No formulário de etapa (`StageModal`, aba Avançado), adicionar badge "Em breve" nos campos que ainda não têm execução no momento do deploy desta fase (todos, inicialmente) — mesmo padrão visual já usado em `ConfigFerramentas.tsx`. Conforme cada fase seguinte for implementada, o badge correspondente é removido.
2. Corrigir o bug encontrado na auditoria: `Plan.pipelines_limit` nunca é checado em `pipeline_service.create_pipeline` — hoje um workspace Free pode criar pipelines ilimitados apesar do limite documentado. Adicionar a checagem (padrão idêntico ao já usado para outros limites de plano, ex. `agents_limit`).

**Arquivos:**
- `apps/web/src/app/(dashboard)/dashboard/pipeline/page.tsx` (StageModal, aba Avançado)
- `apps/api/app/services/pipeline_service.py` (`create_pipeline`)

**Testes:** caso de teste novo em `test_pipelines.py` — criar pipeline além do `pipelines_limit` do plano retorna 402.

---

## Fase 1 — Webhook de etapa (dispatch real)

**O que resolve:** `webhook_url` / `webhook_auth_header` passam a disparar de verdade quando um card entra numa etapa.

**Design:**
- Novo serviço `pipeline_webhook_service.py`, seguindo o mesmo padrão de `whatsapp_outbound_service.py` (httpx síncrono, timeout curto, tratamento de `TimeoutException`/`HTTPStatusError`/`RequestError`).
- Disparo em thread daemon fire-and-forget (mesmo padrão de `auto_reply_scheduler.py`) para não bloquear a resposta HTTP do endpoint que moveu o card — webhook de terceiro pode ser lento ou estar fora do ar.
- Payload mínimo: `event=STAGE_ENTERED`, `pipeline_id`, `stage_id`, `stage_name`, `entry_id`, `conversation_id`, `contact_id` (+ nome/telefone se disponíveis), `previous_stage_id`, `timestamp`.
- Header de autenticação: se `webhook_auth_header` estiver preenchido, enviar como `Authorization: <valor>`.
- **Segurança — validação de SSRF obrigatória antes do disparo**: `webhook_url` é fornecido pelo cliente; resolver o hostname e rejeitar (não salvar, ou não disparar) IPs privados/loopback/link-local (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`, IPv6 equivalentes) para impedir que um workspace use o campo para atingir infraestrutura interna do Wenzap. Validar tanto na gravação (`update_stage`) quanto, defensivamente, antes de cada disparo (DNS rebinding).
- Retry: 1 retentativa após falha, sem fila persistente nesta fase (nível de esforço equivalente ao resto do MVP). Se falhar as 2 tentativas, registrar em log estruturado — não há tabela de auditoria dedicada nesta fase (ver Fase 5 para histórico).
- Disparo acontece em todo caminho que muda `stage_id` de uma entry: `move_entry` (manual), e os pontos das Fases 2/3/4 que também movem entries.

**Arquivos:**
- Novo: `apps/api/app/services/pipeline_webhook_service.py`
- Modificado: `apps/api/app/services/pipeline_service.py` (`move_entry` chama o dispatch)
- Modificado: `apps/web/.../page.tsx` (remover badge "Em breve" de Webhook)

**Testes:** mock de `httpx.post`; caso de sucesso (payload correto, header correto), caso de timeout (não derruba a request principal), caso de URL apontando para IP privado (rejeitada).

---

## Fase 2 — `entry_condition` avaliada automaticamente

**O que resolve:** o diferencial real do FluxVolt. Uma conversa muda de etapa sozinha quando o conteúdo da conversa bate com a condição configurada — sem precisar de tool-calling formal.

**Design:**
- Hook point: `conversation_agent_reply_service.py`, logo após uma mensagem inbound ser processada (mesmo lugar que já resolve o `extra_prompt` da etapa atual via `conversation_context_builder`).
- Se a entry ativa da conversa está num pipeline que tem **outras etapas** com `entry_condition` não vazio, fazer **uma chamada LLM adicional, curta e barata** (prompt de classificação, não geração): lista as etapas candidatas com nome + `entry_condition`, mais as últimas N mensagens da conversa, pergunta "esta conversa deve mover para alguma dessas etapas? Se sim, qual?". Resposta estruturada simples (JSON com `should_move: bool`, `target_stage_id: str | null`), via `response_format`/prompt engineering — não requer tool-calling, é só mais uma chamada de completion com saída controlada.
- Usar um modelo barato/rápido para essa classificação (não o modelo configurado do agente) para não inflar custo — decisão a validar com o Lucas: pode ser um modelo fixo de baixo custo (ex. Haiku) independente do modelo escolhido pelo cliente para o agente principal.
- Se `should_move=true`, mover a entry (mesma função `move_entry`, disparando o webhook da Fase 1 automaticamente) e opcionalmente injetar a `entry_message` da nova etapa (ver Fase 4) como próxima mensagem do agente.
- Gate: só roda se o workspace tem `pipeline_automations` habilitada (Growth+) — evita custo de LLM extra em workspaces Free.
- Guarda contra loop: não avaliar novamente a mesma condição na mesma etapa mais de 1x por mensagem inbound (idempotência natural, já que só roda no fluxo de resposta).

**Arquivos:**
- Novo: `apps/api/app/services/pipeline_auto_routing_service.py`
- Modificado: `apps/api/app/services/conversation_agent_reply_service.py` (chama o novo serviço antes/depois de gerar a resposta)
- Modificado: `apps/web/.../page.tsx` (remover badge "Em breve" de Entry Condition)

**Testes:** mock do LLM de classificação; caso condição bate → entry move + webhook dispara; caso não bate → nada muda; caso workspace sem `pipeline_automations` → não avalia (zero chamadas LLM extras).

---

## Fase 3 — Auto-avanço por tempo (`stay_limit`)

**O que resolve:** "Auto Next Step" do FluxVolt — conversa parada numa etapa por X minutos avança sozinha.

**Por que é a fase mais cara estruturalmente:** não existe scheduler genérico no projeto (`auto_reply_scheduler.py` é uma thread por conversa com sleep de segundos — inadequado para um limite medido em minutos/horas: a thread morre em todo redeploy do Railway, perdendo o agendamento silenciosamente). Isso também bloqueia "Follow-up automático pós-conversa" do roadmap geral — vale construir pensando em reuso.

**Design:**
- Scheduler novo: **sweep periódico** em vez de uma thread por entry. Um loop em background (iniciado no lifespan do FastAPI, mesmo processo) que a cada N minutos (ex. 1 min) roda:
  ```sql
  SELECT * FROM pipeline_entries
  WHERE status = 'active'
    AND stage_id IN (SELECT id FROM pipeline_stages WHERE stay_limit_enabled = true)
    AND entered_stage_at + (stay_limit_minutes || ' minutes')::interval <= now()
  ```
- Para cada entry encontrada, mover para a **próxima etapa por `position`** dentro do mesmo pipeline (se não houver próxima etapa, não faz nada — é a última).
- **Segurança contra corrida em múltiplas réplicas**: mover via `UPDATE pipeline_entries SET stage_id = :next, entered_stage_at = now() WHERE id = :id AND stage_id = :original_stage_id` (compare-and-swap). Se outra réplica já moveu a entry entre o SELECT e o UPDATE, a cláusula `WHERE stage_id = :original_stage_id` falha silenciosamente (0 rows), sem duplo disparo. Evita depender de lock distribuído.
- Gate: `pipeline_automations` (Growth+), mesmo critério da Fase 2.
- Reaproveitar o dispatch de webhook da Fase 1 quando a auto-move acontecer.

**Arquivos:**
- Novo: `apps/api/app/services/pipeline_stay_limit_scheduler.py`
- Modificado: `apps/api/app/main.py` (registrar o loop no lifespan, ao lado da inicialização existente)
- Modificado: `apps/web/.../page.tsx` (remover badge "Em breve" de Stay Limit)

**Testes:** teste de integração com `entered_stage_at` manipulado no passado, roda uma iteração do sweep manualmente (função extraída e testável, não só o loop infinito), confirma a entry moveu e o compare-and-swap não duplica quando chamado 2x seguidas na mesma entry já movida.

**Nota para o Lucas:** esse scheduler em processo único funciona bem em 1 réplica (é o cenário atual de produção, confirmado). Se o Wenzap escalar para múltiplas réplicas da API, precisa migrar para Celery Beat ou cron externo — o compare-and-swap já deixa isso seguro de fazer depois, sem re-arquitetura.

---

## Fase 4 — Ações automáticas de etapa

**O que resolve:** `is_removal_stage`, `request_contact_info`, e o equivalente ao "Default Conversation Settings" do FluxVolt (status/assignee/IA ligada-desligada ao entrar na etapa) — mais barato do que parecia, porque `Conversation.status`, `Conversation.assigned_user_id` e `Conversation.ai_enabled` **já existem** no modelo, só faltava algo escrever neles.

**Design:**
- Estender `PipelineStage` com campos opcionais de ação de entrada: `on_enter_conversation_status` (nullable), `on_enter_assigned_user_id` (nullable FK), `on_enter_ai_enabled` (nullable bool — `null` = não mexe).
- `is_removal_stage`: ao mover uma entry para uma etapa com essa flag, setar `entry.status = "inactive"` automaticamente (consistente com "Inactive Conversations" do FluxVolt — a conversa some do board ativo mas fica acessível no histórico).
- `request_contact_info`: em vez de construir um fluxo de coleta estruturada (exigiria tool-calling, fora de escopo), reaproveitar o mecanismo de `extra_prompt` já existente — quando a flag está ativa e o contato não tem nome/e-mail/telefone preenchidos, injetar automaticamente uma instrução adicional no system prompt pedindo esses dados. Mais barato, reaproveita infraestrutura, não precisa de UI nova.
- Todas as ações de entrada disparam no mesmo ponto (`move_entry`, e os pontos automáticos das Fases 2/3), depois do webhook.

**Arquivos:**
- Migration nova (ver seção de Migrations)
- Modificado: `apps/api/app/models/pipeline_stage.py`, `schemas/pipeline.py`, `pipeline_service.py` (`move_entry` executa as ações)
- Modificado: `conversation_context_builder.py` (injeção condicional de pedido de contato)
- Modificado: `apps/web/.../page.tsx` (novos campos na aba Avançado; remover badges "Em breve" de Removal Stage e Request Contact Info)

**Testes:** entry entra em etapa de remoção → status vira inactive; etapa com `on_enter_ai_enabled=false` → conversa passa a `ai_enabled=False`; `request_contact_info` injeta a instrução só quando faltam dados do contato.

---

## Fase 5 — Histórico de etapa + métricas

**O que resolve:** duas lacunas da auditoria que dependem da mesma peça de infraestrutura: card sem histórico (mover sobrescreve `stage_id` sem deixar rastro) e "Métricas por etapa (tempo médio, conversão)" do roadmap, que hoje é impossível de calcular porque não existe onde consultar tempo em etapas anteriores.

**Design:**
- Nova tabela `pipeline_entry_stage_history`: `id`, `entry_id` (FK), `stage_id` (FK, nullable — etapa pode ser deletada depois), `stage_name_snapshot` (texto, preserva o nome mesmo se a etapa for renomeada/excluída depois), `entered_at`, `exited_at` (nullable — null enquanto está na etapa atual), `moved_by` (`manual` / `entry_condition` / `stay_limit` / `initial`).
- Toda movimentação de entry (todas as fases anteriores) grava uma linha: fecha o `exited_at` da linha anterior, abre uma nova.
- Endpoint novo: `GET /pipelines/{id}/metrics` — tempo médio por etapa (média de `exited_at - entered_at` das linhas fechadas), taxa de conversão simples (entries que chegaram na última etapa do pipeline ÷ total de entries criadas).
- Card detail (ao clicar num card no board) passa a exibir a linha do tempo de etapas percorridas — pequena adição de UI, não precisa de tela nova.

**Arquivos:**
- Migration nova + `apps/api/app/models/pipeline_entry_stage_history.py`
- Modificado: `pipeline_service.py` (grava histórico em toda movimentação)
- Novo endpoint em `pipelines.py` + `PipelineMetricsOut` em `schemas/pipeline.py`
- Frontend: seção de métricas na tela de pipeline (gráfico simples ou tabela, sem exigir biblioteca de charts nova se já houver uma no projeto — confirmar antes de adicionar dependência)

**Testes:** histórico grava corretamente em cada tipo de movimentação (manual/condition/stay_limit); métricas calculam certo com dados fixture.

---

## Fase 6 — Drag-and-drop

**O que resolve:** paridade de UX com FluxVolt — mover card e reordenar etapa por arrastar, não só por modal de clique.

**Design:**
- Adicionar `@dnd-kit/core` + `@dnd-kit/sortable` (não há biblioteca de D&D no projeto hoje — confirmado). Preferência a `@dnd-kit` sobre `react-beautiful-dnd` (não mantida) por ser ativamente mantida e acessível (suporte a teclado).
- Cards: arrastar entre colunas chama o mesmo endpoint `move` já existente (`POST .../entries/{id}/move`) — nenhuma mudança de backend.
- Etapas: arrastar para reordenar chama o endpoint `reorder` já existente (`POST .../stages/reorder`) — também sem mudança de backend.
- Puramente frontend, sem dependência das fases anteriores — pode ser feita em paralelo a qualquer uma delas.

**Arquivos:**
- `apps/web/package.json` (nova dependência)
- `apps/web/src/app/(dashboard)/dashboard/pipeline/page.tsx` (reescrever `KanbanColumn`/`EntryCard` com sensores de drag)

**Testes:** cobertura de frontend é mais fraca no projeto hoje; no mínimo, teste manual documentado no PR + smoke test de que o endpoint é chamado corretamente ao soltar.

---

## Backlog (fora do escopo imediato, registrar mas não bloquear "100% funcional")

- Templates de pipeline (duplicar um pipeline existente como ponto de partida)
- API pública de criação de conversa em etapa específica (equivalente ao "Flux CRM Templates API")
- Mensagem automática de entrada na etapa (`entry_message`) — pequena, pode entrar como parte da Fase 4 se o esforço permitir
- Tags/labels em cards e atribuição a operador humano além de `assigned_user_id` (avaliar se `assigned_user_id` já resolve o caso de uso antes de construir um sistema de tags novo)
- Notificação SMS — fora de escopo por falta de provedor (ver Não-objetivos)

---

## Migrations necessárias (a partir de 065)

| Fase | Migration | Conteúdo |
|---|---|---|
| 4 | `065_pipeline_stage_entry_actions.py` | `on_enter_conversation_status`, `on_enter_assigned_user_id`, `on_enter_ai_enabled` em `pipeline_stages` |
| 5 | `066_pipeline_entry_stage_history.py` | Nova tabela `pipeline_entry_stage_history` |

(Fases 0, 1, 2, 3, 6 não exigem migration — usam campos já existentes ou são puramente comportamentais/frontend.)

## Feature flag nova

`pipeline_automations` (booleana, por plano) — Free: `false`. Growth/Scale/Enterprise: `true`. Controla Fases 2, 3 e as ações automáticas da Fase 4 (não controla Fase 1/webhook, que é manual-triggered então pode ficar disponível no Free assim como o resto do CRUD manual — a decidir com o Lucas se webhook deve ser Free ou Growth+; a recomendação é Growth+ para manter a mesma linha de "manual=Free, automação=pago", já que webhook é uma forma de automação externa).

## Ordem de execução recomendada

Fase 0 → Fase 1 → Fase 4 (ações de etapa, barata, reaproveita campos existentes de `Conversation`) → Fase 2 (entry_condition) → Fase 5 (histórico/métricas) → Fase 3 (stay_limit, mais cara em infra) → Fase 6 (drag-and-drop, pode entrar em paralelo a qualquer momento).

## Critério de "pronto"

O módulo é considerado 100% funcional quando: nenhum campo do formulário de etapa é apenas decorativo; toda automação testada tem teste automatizado cobrindo o caminho feliz e pelo menos um caminho de falha; `docs/pipeline/conversation-pipeline-foundation.md` é atualizado para remover a seção "O que ficou para fase futura" (ou reduzi-la só ao que estiver genuinamente no Backlog acima).
