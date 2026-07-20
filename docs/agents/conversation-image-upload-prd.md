# PRD — Recebimento e interpretação de imagem na conversa

**Status: ✅ Implementado (2026-07-20)** — escopo: WhatsApp via Evolution API (único canal ativo
hoje) → storage → Anthropic vision, gated por `supports_vision`. Meta Cloud API e Web Widget
ficaram fora desta leva (ver "Estado da implementação"). 2237 testes de backend passando (10
pré-existentes sem relação, confirmados contra o `main` antes desta mudança), zero regressão.
Ver "Estado da implementação" no fim.

## Contexto

Pergunta de produto: o Wenzap consegue hoje receber uma imagem do cliente (WhatsApp ou Web
Widget) e ter o agente de IA interpretando ela? Resposta, confirmada em código: não, em nenhum
ponto do pipeline.

Pesquisa competitiva: doc pública do Chatvolt
(`docs.chatvolt.ai/agent/conversation-file-upload`). Eles enviam a imagem direto pro modelo de
visão do LLM ("vision compatible model like GPT-4-Turbo or Claude 3") — sem OCR, sem extração de
texto intermediária. Formatos aceitos: imagens (PNG/JPEG/GIF/WebP) e documentos (CSV/TXT/
Markdown/JSON/DOCX/XLSX/PPTX/PDF). Formato não suportado é simplesmente ignorado pela IA, sem
erro. Arquivo fica restrito à conversa onde foi enviado, com um dropdown pra reutilizar dentro da
mesma conversa. A doc não detalha nada de webhook, storage ou a integração específica com
WhatsApp.

Esse gap já tinha sido mapeado antes, com escopo mais amplo (documento, áudio) em
`negocios/wenzap/novas-funcionalidades-chatvolt.md` (NexBrain), seção "Upload de arquivo na
conversa". Este PRD cobre só a fatia de **imagem/visão** — é a peça que responde diretamente à
pergunta de produto e é tecnicamente autocontida (visão nativa do modelo, sem pipeline de
extração de texto de documento).

## Achado de arquitetura (o que existe hoje, e por que não funciona)

Três pontos quebram a cadeia, de ponta a ponta:

1. **Ingestão descarta a mensagem.** `app/services/evolution_webhook_parser.py` —
   `_TEXT_MESSAGE_TYPES = {"conversation", "extendedTextMessage"}`; qualquer outro `messageType`
   (imagem, documento, áudio) é explicitamente pulado com log "skipping unsupported messageType"
   (linhas ~95-101). `app/services/whatsapp_webhook_parser.py` (caminho Meta Cloud API) nem tem
   função de extração de mídia — só texto.
2. **Storage não tem onde guardar.** `app/models/conversation_message.py` já tem a coluna
   `content_type`, com um comentário no próprio modelo antecipando isso: *"future types (image,
   file, audio, system_event) should not require a migration"* — mas `whatsapp_inbound_service.py`
   grava `content_type="text"` fixo (linha ~272) pra toda mensagem inbound. Não existe coluna de
   URL/referência de mídia no modelo.
3. **LLM nunca monta bloco de imagem.** `app/llm/schemas.py` — `LLMMessage.content: str |
   list[dict]`; a forma de lista já existe, mas só é usada pra `tool_use`/`tool_result` (visão
   nativa da Anthropic usa um content block de tipo diferente, nunca construído em lugar nenhum
   do código). `app/llm/providers/anthropic.py` repassa as mensagens direto, sem nenhuma
   montagem de bloco de imagem.

Achado colateral, direto ao ponto da pergunta original do Lucas ("precisa de modelo compatível ou
qualquer um funciona"): **já existe uma flag de capacidade por modelo** — `ai_models.supports_vision`
(boolean, seedado com mistura real: Claude Opus e toda a linha OpenAI/Google têm `true`; Claude
Haiku e Sonnet têm `false` no catálogo atual). Hoje essa flag é **só metadado pra UI** do seletor
de modelo (`ai_model_service.get_catalog()` repassa pro card, nada mais) — não existe nenhuma
validação no pipeline de execução que impeça um agente com modelo sem visão de "receber" uma
imagem sem saber o que fazer com ela. O próprio PRD de refactor do módulo de agente já antecipa a
intenção certa: *"os ícones devem refletir capacidades reais configuradas no backend, não
marketing"* (`agent-module-refactor-prd.md`).

## Objetivo

Cliente manda uma imagem (WhatsApp ou Web Widget), ela é baixada e guardada vinculada à
conversa, e se o agente estiver configurado com um modelo `supports_vision=true`, a imagem é
enviada como conteúdo de visão pro LLM — que responde considerando o que viu, não só o texto que
acompanhou (se houver).

## Não-objetivos

- **Documentos (PDF/DOCX/XLSX/etc) e áudio.** Fatia maior já mapeada em
  `novas-funcionalidades-chatvolt.md`; caminho técnico diferente (extração de texto/transcrição,
  não visão nativa) e não bloqueia este PRD. Fica pra um PRD próprio.
- **OCR ou pré-processamento de imagem.** Igual ao Chatvolt — visão nativa do modelo é a
  interpretação, sem etapa intermediária de extrair texto da imagem antes.
- **Múltiplas imagens no mesmo turno / álbum.** V1 cobre uma imagem por mensagem — é o caso comum
  do WhatsApp (cada foto chega como uma mensagem separada de qualquer forma).
- **Dropdown de reutilizar imagem já enviada na conversa** (o "conversation files dropdown" do
  Chatvolt). Recurso de UI de conveniência, não bloqueia a funcionalidade central; pode virar
  iteração futura se algum operador sentir falta.
- **Envio de imagem pelo operador humano no Inbox.** Escopo é imagem *do cliente pro agente
  interpretar*; operador já pode escrever texto no Inbox hoje, mandar imagem manualmente é
  ortogonal a este PRD.

## Design

### Ingestão — parar de descartar, baixar a mídia

**WhatsApp via Evolution API** (canal ativo hoje): `evolution_webhook_parser.py` precisa
reconhecer `messageType` de imagem (Evolution normalmente entrega either um base64 direto no
payload do webhook, ou uma referência que exige uma chamada separada à API da própria instância
Evolution pra baixar o binário — **verificar qual dos dois na implementação**, não confirmado
nesta pesquisa). Sem essa confirmação de formato de payload, o esforço de ingestão não pode ser
estimado com precisão.

**WhatsApp via Meta Cloud API** (caminho oficial, ainda bloqueado por aprovação Meta — ver
`decisoes.md` no NexBrain): mensagem de imagem chega com um `media_id`; é necessário um GET à
Graph API (`/v25.0/{media_id}`) pra obter uma URL de download temporária, e então baixar o
binário dessa URL — padrão documentado da Meta, sem ambiguidade.

**Web Widget**: já tem alguma forma de upload pro cliente anexar arquivo na conversa? Se não,
esse é escopo adicional (endpoint de upload novo), não só "parser aceitar tipo de mensagem" — a
menos que o widget já tenha isso implementado noutro fluxo (catálogo/KB usam upload de arquivo;
verificar se dá pra reaproveitar o mesmo endpoint/storage).

### Storage

Nova coluna em `conversation_messages` (nome proposto: `media_url`) + `content_type` passa a
receber valores reais (`"image"` em vez de sempre `"text"`) nos pontos identificados
(`whatsapp_inbound_service.py`, e o caminho do widget se aplicável). Upload do binário baixado via
`StorageProvider` (abstração já existente no projeto — local/S3, sem código novo de storage,
só o call-site de baixar do WhatsApp/Meta e subir por ela).

Limite de tamanho/formato: restringir na ingestão a formatos que a Anthropic aceita como visão
(JPEG/PNG/GIF/WebP) — arquivo fora disso é tratado como o Chatvolt trata ("ignorado", ver seção
seguinte).

### LLM — bloco de imagem + checagem de capacidade

`app/llm/schemas.py` ganha um tipo de content block de imagem (par com o que já existe pra
tool_use); `app/llm/providers/anthropic.py` monta esse bloco (base64 ou URL, a decidir conforme o
que a API da Anthropic aceitar mais direto vindo do storage escolhido) só quando o modelo do
agente tem `supports_vision=true`.

**Comportamento quando o modelo do agente NÃO tem visão** (decisão de produto ainda em aberto,
ver seção seguinte) — proposta: a imagem ainda é recebida, baixada e guardada na conversa (visível
no Inbox pro humano ver), mas **não é enviada como bloco de visão pro LLM**; em vez disso, o
prompt do turno recebe uma nota textual tipo *"o cliente enviou uma imagem que este agente não
consegue interpretar (modelo sem suporte a visão)"*, pra o agente poder reagir com contexto
(ex: pedir pra descrever, ou avisar que vai chamar um humano) em vez de responder como se nada
tivesse chegado. Alternativa mais simples (igual ao Chatvolt): ignorar silenciosamente. A
diferença de UX é real — vale decidir com o Lucas antes de implementar (ver "Decisões
pendentes").

### Playground

Mesma paridade de sempre com os outros PRDs de tool: o Playground deveria permitir simular envio
de imagem também, senão fica sem cobertura de teste manual pra essa funcionalidade central.

## Migrations necessárias

Uma migration: `conversation_messages.media_url` (nullable, `String`), sem tabela nova — reusa
`content_type` já existente.

## Feature flag / gating

Proposta: **sem gate de plano dedicado.** O custo diferencial já é carregado pelo próprio modelo
escolhido (`credits_per_message` por `ai_model`, e modelos com visão tendem a already ser os mais
caros/avançados do catálogo, ex. Claude Opus vs Haiku/Sonnet) — mesmo mecanismo que já resolve
"funcionalidade avançada custa mais" sem precisar duplicar em `plan_features`. Se o Lucas quiser
mesmo assim reservar recebimento de imagem pra Scale+/Enterprise independente do modelo, é um gate
adicional simples de encaixar (mesmo padrão do HTTP Tool/Follow-up).

## Decisões pendentes (confirmar antes de implementar)

1. **Formato de payload de mídia da Evolution API** — base64 direto no webhook ou referência que
   exige chamada separada? Define o esforço real de ingestão do canal ativo hoje.
2. **Web Widget já tem upload de arquivo do cliente pro agente, ou é escopo novo?**
3. **Comportamento com modelo sem visão**: ignorar silenciosamente (Chatvolt) vs. avisar o agente
   via nota textual no prompt (proposta acima) vs. bloquear o agente de ficar em canal com imagem
   habilitada se o modelo não suporta.
4. **Gate de plano**: nenhum (proposta) ou reservar pra Scale+/Enterprise independente do modelo.
5. **Tamanho máximo de arquivo aceito** — a doc do Chatvolt não menciona limite; a Anthropic tem
   limites documentados próprios que valem checar na implementação (não levantados com precisão
   nesta pesquisa).

## Critério de "pronto"

Um cliente manda uma foto pelo WhatsApp (canal Evolution API) pra um agente configurado com um
modelo `supports_vision=true` (ex: Claude Opus), e o agente responde considerando o conteúdo
visual da imagem — visível no Inbox como uma mensagem com mídia anexada, não só texto. Testado
também com um modelo sem visão, confirmando que o comportamento definido na "Decisão pendente #3"
acontece de fato, em vez de a imagem simplesmente desaparecer sem explicação nem pro cliente nem
pro operador.

## Referências

- `app/services/evolution_webhook_parser.py`, `app/services/whatsapp_webhook_parser.py` — pontos
  de ingestão que hoje descartam mídia.
- `app/models/conversation_message.py` — comentário antecipando `content_type` de imagem/arquivo.
- `app/services/whatsapp_inbound_service.py` — grava `content_type="text"` fixo.
- `app/llm/schemas.py`, `app/llm/providers/anthropic.py` — onde entra o content block de imagem.
- `app/models/ai_model.py`, `app/services/ai_model_service.py` — `supports_vision` já existe,
  hoje só exposto pra UI, sem enforcement.
- `docs/agents/agent-module-refactor-prd.md` — intenção original da flag de capacidade por
  modelo.
- Pesquisa competitiva: doc pública do Chatvolt
  (`docs.chatvolt.ai/agent/conversation-file-upload`).
- `negocios/wenzap/novas-funcionalidades-chatvolt.md` (NexBrain) — mapeamento original do gap,
  escopo mais amplo (documento/áudio).

## Decisões pendentes — como foram resolvidas nesta implementação

1. **Formato de payload de mídia da Evolution API** — resolvido usando o endpoint documentado
   `POST /chat/getBase64FromMediaMessage/{instance}` (decodifica a mídia do lado da Evolution,
   sem esta base ter que lidar com a criptografia do Baileys). **⚠️ Não testado contra uma
   instância real** — mesmo status de incerteza que `_call_evolution_send_text` já tinha antes
   deste PRD (ver `evolution_provider.py`). Precisa do mesmo tipo de smoke test real que a Slice 3
   do `plano-evolution-api.md` fez pra texto, mandando uma foto de verdade pro número conectado.
2. **Web Widget** — fora de escopo nesta leva. Não foi verificado se já existe upload de arquivo
   do cliente pro agente ali; a implementação cobre só WhatsApp via Evolution API.
3. **Comportamento com modelo sem visão** — implementado a proposta do PRD: a imagem é recebida e
   guardada normalmente, mas se `supports_vision=False` (ou se a imagem não puder ser recarregada
   do storage), o turno vira texto puro com uma nota anexada avisando o agente que uma imagem
   chegou e não pôde ser interpretada — em vez de ignorar silenciosamente como o Chatvolt.
4. **Gate de plano** — nenhum implementado, conforme proposto (custo diferencial já vem do
   `credits_per_message` do modelo escolhido).
5. **Tamanho máximo de arquivo** — não implementado limite explícito nesta leva. Fica como
   melhoria futura se necessário.

## Estado da implementação (2026-07-20)

**Backend, arquivos novos:**
- `alembic/versions/076_conversation_message_media_url.py` — `conversation_messages.media_url`
  (nullable, sem tabela nova).
- `app/services/evolution_media_service.py` — `download_and_store_inbound_image()`: chama o
  endpoint `getBase64FromMediaMessage` da Evolution, decodifica o base64, sobe pro
  `StorageProvider` configurado. Nunca levanta exceção (mesma filosofia do resto do pipeline
  inbound) — qualquer falha vira `None` e a mensagem ainda é persistida sem `media_url`.

**Backend, arquivos modificados:**
- `app/models/conversation_message.py` — coluna `media_url` (chave de storage, não URL pública
  direta — resolvida via `StorageProvider` no momento da leitura).
- `app/services/whatsapp_webhook_parser.py` — `WhatsAppInboundMessage.message_type: str = "text"`
  (default preserva 100% de compatibilidade com o parser da Meta, que nunca emite `"image"` ainda).
- `app/services/evolution_webhook_parser.py` — reconhece `messageType == "imageMessage"`
  (`_IMAGE_MESSAGE_TYPE`); extrai `caption` como `text_body`; **não** descarta imagem sem legenda
  (diferente do comportamento de mensagem de texto vazia).
- `app/services/whatsapp_inbound_service.py` — `_create_message_idempotent` agora recebe
  `channel` e grava `content_type="image"` + `media_url` quando aplicável. Imagem sem legenda vira
  `content="[Imagem]"` (nunca string vazia — `conversation_context_builder._fetch_history` exclui
  `content == ""` do histórico, o que faria a imagem desaparecer silenciosamente do contexto do
  LLM). `_download_inbound_media()` só aciona o download quando `channel.config_json.provider ==
  "evolution_api"` — canal Meta seria um no-op defensivo (parser da Meta não emite imagem ainda).
- `app/services/conversation_agent_reply_service.py` — monta o content block de imagem
  (`{"type": "image", "source": {"type": "base64", ...}}`) quando `trigger_message.content_type
  == "image"` e `model.supports_vision`; busca os bytes de volta via `StorageProvider.get_file`.
  Fallback textual (ver decisão #3) quando o modelo não suporta visão ou a leitura do storage
  falha. Usa `getattr` defensivo em `content_type`/`media_url` do trigger message — alguns testes
  já existentes passam um `SimpleNamespace` mockado no lugar de `ConversationMessage` real, sem
  todos os campos setados.
- `negocios/wenzap/novas-funcionalidades-chatvolt.md` (NexBrain) — linkado de volta pra este PRD.

**Testes novos:**
- `tests/test_evolution_media_service.py` — 9 casos (sucesso, mime_type default, base_url/
  instance_name/api_key faltando, falha HTTP, resposta sem base64, base64 inválido, falha de
  upload no storage).
- `tests/test_evolution_webhook_parser.py` — 3 casos novos (imagem com legenda, imagem sem
  legenda não é descartada, texto continua com `message_type="text"` por default); 1 teste
  existente corrigido (`test_unsupported_message_type_is_skipped` usava `imageMessage` como
  exemplo de tipo não suportado — não é mais verdade, trocado por `audioMessage`).
- `tests/test_whatsapp_inbound_service.py` — 4 casos novos (`TestImageMessage`): download e
  storage bem-sucedidos, legenda vazia vira `"[Imagem]"`, falha de download não impede a
  persistência da mensagem, canal Meta pula o download (guarda defensiva).
- `tests/test_conversation_agent_reply_service.py` — 4 casos novos (`TestImageTrigger`): modelo
  com visão monta o content block corretamente, modelo sem visão cai no fallback textual, falha
  de storage cai no fallback textual, gatilho de texto puro seguem funcionando sem qualquer efeito
  colateral (regressão).

**Verificação:** 2237 testes de backend passando (10 pré-existentes sem relação — confirmados
contra o `main` antes desta mudança via `git stash`, mesmos 10 falham lá também), `ruff check` e
`ruff format` limpos nos arquivos tocados. **Achado durante a implementação**: uma regressão real
foi pega e corrigida — `test_whatsapp_agent_outbound.py` passa um `SimpleNamespace` mockado como
`trigger_message` sem `content_type` setado; acesso direto ao atributo quebrava com
`AttributeError`. Corrigido com `getattr(..., None)` defensivo, sem mudar comportamento pra
`ConversationMessage` real (que sempre tem a coluna).

**Não testado:**
- **End-to-end contra a Evolution API real.** O endpoint `getBase64FromMediaMessage` foi
  implementado a partir da documentação pública da Evolution, mas nunca validado contra a
  instância `wenzap` de verdade — precisa do mesmo tipo de smoke test manual que a Slice 3 do
  `plano-evolution-api.md` fez pra texto (mandar uma foto real pro número conectado e conferir
  formato de request/response).
- **Frontend/Inbox.** A imagem é guardada (chave de storage), mas não construí nenhum endpoint
  novo pra resolver isso numa URL exibível — o Inbox hoje não vai renderizar a imagem visualmente.
  Fora do escopo pedido (recebimento + interpretação pelo agente), mas é o próximo passo natural.
- **Playground.** Não dá pra simular envio de imagem no Playground ainda — só funciona no fluxo
  real de conversa via WhatsApp.
- **Web Widget e Meta Cloud API.** Nenhum dos dois ganhou capacidade de mandar imagem nesta leva
  (ver "Decisões pendentes" #1/#2 acima).
