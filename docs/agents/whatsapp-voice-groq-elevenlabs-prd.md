# PRD — Áudio no WhatsApp (transcrição Groq + resposta em voz ElevenLabs)

**Status: 🟢 Implementado (backend + frontend). Falta smoke test com chaves reais e commit/push.**
Pedido do Lucas: analisar como o Chatvolt faz (`docs.chatvolt.ai/agent/transcriptions-with-groq`, `docs.chatvolt.ai/agent/elevenLabs-audios`) e desenhar pro Wenzap. Retoma e substitui o item 3 de
[novas-funcionalidades-chatvolt.md](../../../../nexbrain/negocios/wenzap/novas-funcionalidades-chatvolt.md)
(NexBrain, 2026-07-19) — aquela análise ficou desatualizada porque a fundação de mídia mudou desde
então (feature de imagem, 2026-07-20).

## Contexto e decisão de negócio

Groq e ElevenLabs vão ser **chaves trazidas pelo próprio cliente** (por workspace), não chaves
globais do Wenzap — decisão explícita do Lucas: mesmo a Groq sendo barata por chamada, em escala
com muitos clientes o custo agregado seria dele, não do cliente. ElevenLabs é ainda mais caro por
uso (cobra por caractere sintetizado). Ele vai orientar/dar suporte manual pros primeiros clientes
configurarem as chaves, com vídeo tutorial depois.

Isso é diferente do padrão hoje (Anthropic/OpenAI são chaves globais do `config.py`) — não existe
nenhum mecanismo de "cliente traz a própria chave de serviço terceiro" no código ainda. O único
precedente parecido é `ChannelCredential`/`resolve_channel_secret()`, mas isso é por **canal**
(token do WhatsApp), não por workspace, e `channel_id` é obrigatório no schema — não dá pra
reaproveitar direto, precisa de uma tabela irmã.

## Achado importante: o envio de mídia de saída está quebrado pra quem usa Evolution

Investigando como mandar áudio de volta, achei que **o único código de "mandar mídia" que existe
hoje (`catalog_media_delivery_service.py`, usado pelo Catálogo) está hardcoded pra API do Meta
Graph** (`_call_meta_image_api`, `_META_API_BASE = "https://graph.facebook.com/v21.0"`) — não passa
pelo dispatch por provider (`app/services/messaging/dispatch.py`) que o texto já usa corretamente.
Como **hoje só existe canal WhatsApp ativo via Evolution API** (Meta Cloud API aguarda aprovação),
isso significa que **o envio de imagem do Catálogo provavelmente nunca funcionou em produção** —
ele tenta resolver `phone_number_id`/token de acesso Meta em canais que são Evolution, e isso falha
silenciosamente (captura de exceção ampla no call site).

Como preciso construir o primeiro envio de mídia de verdade pela Evolution (pro áudio), aproveito
pra consertar isso — generalizando o envio de mídia pelo mesmo registro por provider que o texto já
usa, em vez de deixar duas gambiarras (uma pra imagem, outra pra áudio).

## Desenho

### 1. Credencial por workspace (`workspace_credentials`)

Nova tabela, irmã de `channel_credentials` mas sem `channel_id`:

```python
class WorkspaceCredential(Base):
    __tablename__ = "workspace_credentials"
    id: UUID (pk)
    workspace_id: UUID FK workspaces.id ondelete=CASCADE, NOT NULL
    provider: str(50)          # "groq" | "elevenlabs"
    encrypted_value: Text      # Fernet, mesmo encrypt_secret/decrypt_secret de crypto_service.py
    created_at / updated_at
    # unique(workspace_id, provider)
```

Serviço `workspace_credentials_service.py`: `set_workspace_credential(db, workspace_id, provider,
plain_value)` (upsert), `get_workspace_credential(db, workspace_id, provider) -> str | None`
(decripta), `has_workspace_credential(...) -> bool`, `delete_workspace_credential(...)`. Mesmo
princípio de segurança do `ChannelCredential`: nunca devolver a chave crua numa resposta de API —
só indicar `configured: bool`.

Rotas (`app/routers/workspaces.py`, novo grupo `/workspaces/current/integrations`):
- `GET /workspaces/current/integrations` → `{groq_configured: bool, elevenlabs_configured: bool}`
- `PUT /workspaces/current/integrations/{provider}` body `{api_key: str}` → salva (upsert)
- `DELETE /workspaces/current/integrations/{provider}` → remove

Sem migration de mais nada além dessa tabela nova.

### 2. Entrada — reconhecer `audioMessage` + transcrever com Groq

- `evolution_webhook_parser.py`: adicionar `_AUDIO_MESSAGE_TYPE = "audioMessage"`. Diferente de
  imagem (que exige caption OU ser aceita vazia), áudio **nunca tem corpo de texto** — sempre
  considerado válido independente de `text_body` vazio. `message_type` vira `"audio"`.
- `evolution_media_service.py`: generalizar `download_and_store_inbound_image` →
  `download_and_store_inbound_media(db, channel, storage, *, wamid, from_wa_id, expected_mime_prefix)`
  — mesmo endpoint `getBase64FromMediaMessage` (Evolution decodifica qualquer tipo de mídia da
  mesma forma), só muda o mime/extensão default. Mantém as duas funções antigas como wrappers finos
  pra não quebrar o único call site de imagem existente.
- Novo `groq_transcription_service.py`: `transcribe_audio(api_key: str, audio_bytes: bytes,
  filename: str) -> str | None`. `POST https://api.groq.com/openai/v1/audio/transcriptions`,
  `Authorization: Bearer {api_key}`, multipart `file`+`model=whisper-large-v3-turbo`+
  `response_format=text`, timeout generoso (áudio pode demorar mais que texto). Nunca lança —
  mesma convenção de "never raises" do resto do pipeline de mídia.
- `whatsapp_inbound_service.py`: quando `msg.message_type == "audio"`, baixa o áudio (igual
  imagem), e SE o workspace tiver chave Groq configurada, transcreve e usa **o texto transcrito
  como `content`** da mensagem (é isso que o agente vai ler — mesmo princípio do Chatvolt: a
  transcrição vira a mensagem do cliente). Guarda o áudio original via `media_url` +
  `content_type="audio"` (pro Inbox mostrar/tocar depois — exibição ainda não é escopo desta PRD,
  mesma pendência que já existia pra imagem). Se não tiver chave Groq configurada: salva mesmo
  assim com `content="[Áudio recebido — transcrição não configurada. Configure sua chave Groq em
  Configurações > Integrações.]"`, pra não travar a conversa nem inventar conteúdo.

### 3. Saída — sintetizar com ElevenLabs e enviar pela Evolution

- Novo `elevenlabs_voice_service.py`: `synthesize_speech(api_key: str, text: str, voice_id: str) ->
  bytes | None`. `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}`, header
  `xi-api-key`, body `{"text": text, "model_id": "eleven_multilingual_v2"}`. Nunca lança.
- **Conserta o roteamento de mídia** — em vez de generalizar só pra áudio e deixar o Catálogo
  quebrado, adiciono `deliver_media` no protocolo `OutboundProvider` (`messaging/base.py`), com
  implementação em `EvolutionOutboundProvider` (`_call_evolution_send_audio`, endpoint
  `POST {base_url}/message/sendWhatsAppAudio/{instance}`, payload `{"number", "audio": base64,
  "encoding": true}` — mesmo padrão de header/timeout/tratamento de erro do `_call_evolution_send_text`)
  e em `MetaOutboundProvider` (mantendo o que já funcionava pra Meta, movendo `_call_meta_image_api`
  pra lá). `catalog_media_delivery_service.py` passa a chamar `dispatch.get_outbound_provider(...).deliver_media(...)`
  em vez de `_call_meta_image_api` direto — resolve o bug de tabela.
- Trigger: **só quando a mensagem de entrada que originou a resposta foi áudio** — mesmo
  comportamento do Chatvolt ("mensagem de texto recebe resposta em texto, mensagem de voz recebe
  resposta em voz"). Evita responder em áudio pra quem escreveu texto, o que seria estranho.
- Condição completa pra tentar voz na resposta: agente com `voice_reply_enabled=True` E workspace
  com chave ElevenLabs configurada E mensagem-gatilho era áudio. Se qualquer uma faltar, cai pro
  comportamento atual (resposta em texto), nunca bloqueia a resposta.
- Fluxo em `conversation_agent_reply_service.py`: depois de entregar o texto (como já acontece),
  se as condições acima baterem, sintetiza, guarda via storage, e entrega como mensagem separada
  `content_type="audio"` (mesmo padrão de "duas mensagens" que o Catálogo já usa pra imagem depois
  do texto) — não substitui o texto (o texto continua sendo persistido/mostrado no Inbox e usado
  pela Auditoria), a voz é um adicional.

### 4. Configuração por agente

Duas colunas novas em `agent_prompt_settings` (mesmo lugar de `reply_delay_seconds`/
`response_style` — configuração de comportamento do agente, não uma "tool" chamada pelo modelo,
já que é automático por tipo de mensagem, não uma decisão do LLM):
- `voice_reply_enabled: bool default False`
- `elevenlabs_voice_id: str | None` (o operador cola o ID da voz escolhida no próprio painel da
  ElevenLabs — listar vozes disponíveis via API é melhoria futura, fora de escopo agora)

Exposto no mesmo endpoint de update do agente (`PATCH /agents/{id}`), mesmo padrão dos outros
campos de `agent_prompt_settings`.

## O que fica fora de escopo desta rodada (registrar, não esquecer)

- **Exibir/tocar áudio no Inbox** — mesma pendência que já existia pra imagem (`media_url` vira
  URL tocável). Precisa de endpoint de resolução de storage key → URL assinada pro frontend.
- **Seleção de voz via UI** (listar vozes da conta ElevenLabs do cliente) — por ora o operador cola
  o `voice_id` manualmente.
- **Meta Cloud API** — todo o trabalho é Evolution-only, mesma limitação que já existia pra imagem
  (Meta parser nem reconhece tipos não-texto ainda).
- **Playground/Web Widget** — áudio só no WhatsApp por Evolution, como a imagem.
- **Suporte real, não automatizado, pra ajudar cliente a conseguir a chave** — o Lucas vai fazer
  manualmente no início; o vídeo tutorial é responsabilidade dele, fora do código.

## Referências

- `docs.chatvolt.ai/agent/transcriptions-with-groq`, `docs.chatvolt.ai/agent/elevenLabs-audios`
- `app/services/channel_credentials_service.py` — padrão de credencial + `resolve_channel_secret`.
- `app/services/crypto_service.py` — `encrypt_secret`/`decrypt_secret` (Fernet), reaproveitado.
- `app/services/evolution_media_service.py`, `evolution_webhook_parser.py` — pipeline de mídia de
  entrada da imagem, generalizado aqui pra áudio.
- `app/services/messaging/dispatch.py`, `base.py`, `evolution_provider.py`, `meta_provider.py` —
  registro de provider por canal, estendido com `deliver_media`.
- `app/services/catalog_media_delivery_service.py` — bug do hardcode em Meta, corrigido aqui.
- `app/models/agent_prompt_settings.py` — onde `voice_reply_enabled`/`elevenlabs_voice_id` entram.

## Estado da implementação (2026-07-23)

### Backend — completo

Tudo descrito no desenho acima está implementado e testado:

- **Credencial por workspace**: modelo `WorkspaceCredential` (migration `077_workspace_credentials.py`),
  `workspace_credentials_service.py`, rotas `GET/PUT/DELETE /workspaces/current/integrations[/{provider}]`
  (RBAC: só owner/admin, mesmo padrão de `_require_integration_role`).
- **Entrada de áudio**: `evolution_webhook_parser.py` reconhece `audioMessage` (nunca exige corpo de
  texto), `evolution_media_service.py` generalizado pra `download_and_store_inbound_media(...,
  media_kind=)` com `download_and_store_inbound_image`/`download_and_store_inbound_audio` como wrappers
  finos, `groq_transcription_service.py` novo, `whatsapp_inbound_service.py` transcreve quando há
  chave Groq configurada ou grava placeholder explicativo quando não há.
- **Saída de voz**: `elevenlabs_voice_service.py` novo; `deliver_media`/`deliver_media_message`
  adicionados ao protocolo `OutboundProvider` e ao dispatch (`messaging/base.py`, `dispatch.py`,
  `evolution_provider.py` com `sendWhatsAppAudio`/`sendMedia`, `meta_provider.py` com o
  `_call_meta_image_api` movido pra lá); `_maybe_deliver_voice_reply(...)` em
  `conversation_agent_reply_service.py` dispara depois da entrega de texto (+ imagem de catálogo,
  se houver), só quando a mensagem-gatilho foi áudio E o agente tem `voice_reply_enabled=True` E
  `elevenlabs_voice_id` setado E o workspace tem chave ElevenLabs configurada — silencioso em
  qualquer falha (nunca derruba a resposta em texto já entregue).
- **Bug real encontrado e corrigido de graça**: o envio de mídia do Catálogo estava hardcoded pra
  Meta Graph API e nunca funcionou de fato em produção (único canal ativo é Evolution). Agora passa
  pelo mesmo dispatch por provider que o texto já usava — `catalog_media_delivery_service.py`
  reescrito, `_was_recently_sent` corrigido pra checar o novo formato de `metadata_json["delivery"]`.
- **Config por agente**: `voice_reply_enabled`/`elevenlabs_voice_id` em `agent_prompt_settings`
  (migration `078_agent_voice_reply_settings.py`), expostos em `AgentUpdate`/`AgentOut`
  (`app/schemas/agent.py`) e no fluxo de update (`agent_service.py`), mesmo padrão de
  `reply_delay_seconds`.

### Testes

Suíte completa: **2292 passed, 10 failed (pré-existentes, confirmados via `git stash` antes desta
sessão — 3 em `test_agent_test.py`, 5 em `test_ai_models.py`, 2 em
`test_conversation_follow_up_scheduler.py`), 2 skipped.** Zero regressões desta feature.

Novos arquivos de teste:
- `tests/test_workspace_credentials_service.py` — set/get/has/delete, upsert, isolamento por
  workspace, falha de decrypt não lança.
- `tests/test_elevenlabs_voice_service.py`, `tests/test_groq_transcription_service.py` — sucesso e
  todos os caminhos de falha (chave ausente, erro HTTP, erro de rede, resposta vazia).
- `tests/test_workspace_integrations.py` — rotas GET/PUT/DELETE, RBAC (member/viewer bloqueados,
  owner/admin liberados), nunca ecoa a chave em texto plano, valida provider/`api_key` vazio.
- `tests/test_voice_reply.py` — `_maybe_deliver_voice_reply` isolado: todos os caminhos de skip
  (sem prompt settings, toggle off, sem voice_id, sem chave ElevenLabs, síntese falha, storage
  falha) e o caminho de sucesso (mensagem `content_type="audio"` criada, storage e
  `deliver_media_message` chamados com os argumentos certos), incluindo falha de entrega não
  remover a mensagem já criada.
- `tests/test_agents.py` — round-trip de `voice_reply_enabled`/`elevenlabs_voice_id` via
  `PATCH /agents/{id}`, incluindo limpar `elevenlabs_voice_id` com `null`.
- Arquivos de teste já existentes atualizados nesta sessão (parser, inbound service, catalog
  delivery, evolution outbound) — ver commits.

**Honestidade**: nada disso foi smoke-testado contra as APIs reais da Groq, ElevenLabs ou Evolution
— só construído a partir da documentação pública de cada uma e testado com mocks. Antes do primeiro
cliente real usar a funcionalidade, vale um teste manual ponta a ponta com chaves reais.

### Frontend — completo

- **Integrações do workspace**: nova aba "Integrações" em `/dashboard/settings`
  (`IntegrationsSettingsSection.tsx`), com um card por provider (Groq, ElevenLabs) — mostra
  configurado/não configurado, permite colar/trocar/remover a chave (nunca ecoa a chave de volta,
  só o booleano `*_configured`), com link direto pro painel de cada provider pra pegar a chave.
  Novo namespace `api.workspace.integrations.{get,set,remove}` em `lib/api.ts`.
- **Config do agente**: nova seção "Resposta em áudio no WhatsApp" em `ConfigApresentacao.tsx` (aba
  Apresentação), com toggle `voice_reply_enabled` e campo de texto `elevenlabs_voice_id` (só
  aparece quando o toggle está ligado). Mostra um aviso com link direto pra
  `/dashboard/settings?tab=integrations` quando o workspace ainda não tem chave ElevenLabs
  cadastrada. `page.tsx` do agente carrega/salva os dois campos junto com o resto do form (mesmo
  fluxo de `reply_delay_seconds`).
- Verificado com `tsc --noEmit` e `next build` limpos (sem erros de tipo, build de produção passou).
  Não testado manualmente no navegador nesta sessão (sem UI test/click-through).

### Pendente

- **Smoke test manual** com chaves reais de Groq/ElevenLabs e um número WhatsApp via Evolution —
  nada foi testado contra as APIs de verdade ainda, só com mocks.
- **Commit/push**: todo este trabalho ainda está sem commit.
- Itens fora de escopo (tocar áudio no Inbox, seleção de voz via UI, Meta Cloud API, Playground/Web
  Widget) seguem deliberadamente não implementados — ver seção acima.
