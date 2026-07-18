# PRD — Lote 2 de tools: Captura de dado, Ação de Pipeline, Atribuir a operador

**Status: ✅ Implementado (backend + frontend, 2026-07-18)** — três tools novas, mesma infra de
`agent_tools` já usada pelo HTTP Tool/Solicitar Humano/Marcar Resolvido (decisão do modelo no
meio do turno). Nenhuma é um sweep como o Follow-up. Falta rodar a migration em produção e fazer
o bump/deploy (aguardando "bump"/"Sim" do Lucas).

## Contexto

Depois de implementar as 4 primeiras tools, perguntei ao Lucas o que achava que ainda faltava
pra dar conta de "todo tipo de agente". Concordamos em 3 gaps, nesta ordem de prioridade:

1. **Capturar dado estruturado do cliente** — hoje o agente só conversa em texto solto, nenhum
   dado vira informação utilizável depois.
2. **Criar/mover card no Pipeline** — o Pipeline já existe como funcionalidade, mas o agente não
   alimenta o funil sozinho.
3. **Atribuir a um operador específico** — o Solicitar Humano só pausa a IA sem dono; às vezes o
   operador quer que vá direto pra uma pessoa certa.

Deliberadamente fora de escopo (confirmado na conversa): integrações nativas (Calendar, Sheets,
CRM externo) — o HTTP Tool genérico já cobre isso, sem sinal de demanda real que justifique tool
nativa por integração.

## 1. Capturar dado do cliente (`tool_type="capture_contact_data"`)

### Achado que mudou o desenho
Investigação encontrou que já existe uma tabela pronta pra isso — `ContactVariable`
(`contact_id`, `key`, `value`, `source`, com `UniqueConstraint(contact_id, key)`), com CRUD
completo já exposto na página de Contatos (`VariablesTab`). Reaproveitar essa tabela em vez de
criar `metadata_json`/coluna nova elimina praticamente todo o trabalho de UI de exibição — os
dados capturados pela IA aparecem na mesma aba "Variáveis" que já existe, só com
`source="ai"` os diferenciando dos criados manualmente.

### Config
`fields: list[{key, description}]` — o operador lista quais dados quer que o agente tente
capturar (ex: `key="cpf", description="CPF do cliente, só números"`), 1 a 5 campos. Cada campo
vira uma propriedade **opcional** no `input_schema` (o modelo só preenche o que conseguiu extrair
naquela mensagem — nenhum campo é obrigatório, a tool pode ser chamada várias vezes ao longo da
conversa conforme o cliente for informando cada dado).

### Execução
Sem idempotência especial — é upsert por natureza (`ContactVariable` já tem constraint única por
chave). `upsert_contact_variable()` novo em `contact_service.py` (não existia — hoje só create
com 409 em duplicata, ou update por id). Se `conversation.contact_id` for nulo, devolve aviso sem
salvar nada.

### Gate
Sem gate de plano — mesma categoria de capacidade básica de atendimento que Solicitar Humano.

## 2. Ação de Pipeline (`tool_type="pipeline_action"`)

### Desenho
Diferente de deixar o modelo escolher entre vários pipelines/etapas por nome (arriscado — o
Wenzap pode ter vários pipelines), o operador configura **uma etapa-alvo fixa** por instância da
tool (`pipeline_id` + `stage_id`). Se quiser que o agente decida entre destinos diferentes (ex:
"qualificado" vs "perdido"), cria duas instâncias da tool, cada uma com sua própria descrição de
gatilho — o mesmo truque já usado hoje pra múltiplas ferramentas HTTP num agente.

### Config
`pipeline_id`, `stage_id` — validados na criação/edição (pertencem ao workspace e a etapa
pertence ao pipeline). `input_schema` do modelo fica **vazio** (zero propriedades) — é um toggle
puro de "quando", o "o quê" já está fixado pelo operador.

### Execução
Reaproveita `pipeline_service.create_entry`/`move_entry` sem nenhuma mudança nessas funções —
busca se já existe `PipelineEntry` para `(pipeline_id, conversation_id)`; se sim, chama
`move_entry`; se não, `create_entry`. `apply_stage_entry_effects` já dispara automações
(`on_enter_*`, webhook) de graça se o workspace tiver `pipeline_automations` habilitado — não
precisa de nenhuma lógica nova pra isso.

### Gate
`"pipelines"` (Growth+) — mesma feature que já gate a existência do Pipeline em si. Não faz
sentido essa tool existir num plano que nem tem Pipeline.

## 3. Atribuir a operador (`tool_type="assign_operator"`)

### Achado de conflito, corrigido no desenho
Cheguei a cogitar reaproveitar `Conversation.handoff_reason` (já existe, usado pelo Solicitar
Humano) pro motivo dessa tool também — mas achei um conflito real: a linha do Inbox que mostra
`handoff_reason` só aparece quando **ninguém está atribuído** (`!isHumanAssigned`), porque foi
desenhada especificamente pro estado "limbo" do Solicitar Humano. Como Atribuir a Operador
sempre define um `assigned_user_id`, um `handoff_reason` reaproveitado nunca apareceria na tela —
e pior, se as duas tools rodassem em sequência (Solicitar Humano primeiro, depois alguém assume
manualmente), o campo ficaria com um motivo desatualizado sem forma de saber que é stale. Coluna
nova (`assignment_reason`) resolve isso de forma limpa, mesmo padrão de `handoff_reason`/
`resolution_summary`.

### Config
`user_id` — um membro específico do workspace, validado como membro ativo na criação/edição da
tool (reaproveitando o mesmo padrão de `_require_active_member` já usado no take-over manual).
Se o operador quiser que o agente escolha entre pessoas diferentes, mesma solução do Pipeline:
uma instância de tool por pessoa, cada uma com sua própria descrição de gatilho.

### Execução
Igual ao Solicitar Humano: seta `assigned_user_id` + `ai_enabled=False` + `assignment_reason`
(campo obrigatório do modelo) — mesmo efeito de um humano clicar "Assumir", só que decidido pelo
agente e já direcionado pra pessoa certa. Idempotente: se a conversa já tem alguém atribuído, não
sobrescreve, só avisa o modelo. Notificação por e-mail best-effort, mas dessa vez **só pro
operador designado**, não pra todos os owner/admin (diferente do Solicitar Humano, que não sabe
quem vai pegar).

### Gate
Sem gate de plano — mesma categoria do Solicitar Humano.

## Migrations necessárias

Uma migration: `conversations.assignment_reason` (nullable, `String(500)`). Nenhuma tabela nova
— captura de dado reaproveita `contact_variables`, ação de pipeline reaproveita `pipeline_entries`.

## Critério de "pronto"

Um agente com as 3 tools ativas: captura CPF/pedido do cliente durante a conversa (aparece na
aba Variáveis do contato), move o card do lead pra "Qualificado" quando o cliente demonstra
interesse real, e atribui pro vendedor certo quando o cliente pede um humano específico — tudo
sem intervenção manual, com auditoria visível no Inbox/Contato pra cada ação.

## Referências

- `app/services/agent_tool_service.py` — `execute_request_human_tool`/`execute_mark_resolved_tool`,
  template direto pras 3 execuções novas.
- `app/services/pipeline_service.py` — `create_entry`/`move_entry`, reaproveitados sem alteração.
- `app/services/contact_service.py` — `create_variable`, template pro novo `upsert_contact_variable`.

## Estado da implementação

**Backend** — completo, testado (`tests/test_agent_tools_batch2.py`, 38 casos + 1 teste de
loop completo em `test_agent_tool_calling_integration.py`), suite inteira rodando limpa (só as
mesmas falhas pré-existentes de sempre, sem relação com este trabalho). Migration `072` já
aplicada no banco local; falta rodar em produção.

- Rotas: `POST/PATCH/DELETE /agents/{id}/tools/capture-contact-data`,
  `/pipeline-action`, `/assign-operator` — mesmo padrão kebab-case das tools anteriores.
  `pipeline-action` tem gate `_check_pipelines_feature` (feature `"pipelines"`); as outras duas
  são ungated.
- Bug real encontrado e corrigido durante a implementação: `create_agent_tool`/`update_agent_tool`
  faziam `data.config.model_dump()` sem `mode="json"` — para os dois configs novos com campo
  `UUID` (`PipelineActionToolConfig`, `AssignOperatorToolConfig`), isso deixava objetos `UUID` no
  dict, que quebravam a serialização JSON da coluna JSONB ao commitar. Corrigido para
  `model_dump(mode="json")` nos dois call sites.
- Falha de teste nova e não relacionada, encontrada ao rodar a suite: `test_conversation_follow_up_scheduler.py::test_sweep_skips_before_delay_elapsed`
  passou a falhar porque hardcoda `_NOW = datetime(2026, 7, 18, 12, 0, 0)` e o serviço usa o
  relógio real (`datetime.now()`) — o teste ficou "no limite" e virou flaky quando a data real do
  sandbox chegou em 2026-07-18. Não é bug de produção, é teste mal desenhado (deveria usar
  freezegun ou algo assim). Não corrigido agora (fora do escopo deste lote) — fica registrado
  como pendência.

**Frontend** — completo, `tsc --noEmit` e `next build` limpos. `api.ts` com os 3 tipos de config +
CRUD; `ConfigFerramentas.tsx` com 3 modais novos (`CaptureContactDataConfigModal` com editor
dinâmico de campos tipo `ContactFieldsEditor`, `PipelineActionConfigModal` com dropdowns de
pipeline/etapa, `AssignOperatorConfigModal` com dropdown de membro) e os cards ativo/disponível
de cada um; `ConversationHeader.tsx` com a linha de `assignment_reason` (visível só quando há
humano atribuído — distinta da linha de `handoff_reason`, que só aparece no limbo pré-atribuição).
Não testado clicando na UI real (sem ferramenta de browser disponível nesta sessão) — só
verificado via typecheck/build limpos e pela suite de testes de backend.
