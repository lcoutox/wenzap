# PRD — Paridade da Meta Cloud API com a Evolution (áudio, imagem de entrada, webhook subscription)

**Status: 🟢 Implementado.** Pedido do Lucas depois que o App Review da Meta foi aprovado
(28/07/2026 — permissões `whatsapp_business_messaging`, `whatsapp_business_management`,
`public_profile`). O bloqueio que motivou usar Evolution API como ponte não-oficial está
resolvido; esta PRD fecha as lacunas de código que ficaram como consequência direta desse
bloqueio (documentadas explicitamente nos comentários do próprio código como "Meta channel isn't
in active production use yet, pending app approval").

## Contexto

Investigação prévia (read-only, sem mudar nada) mapeou o estado real:

- **Texto**: funciona nos dois sentidos via Meta (`whatsapp_webhook_parser.py` +
  `whatsapp_outbound_service.py`).
- **Imagem**: só funciona **saindo** (`MetaOutboundProvider.deliver_media`, via
  `_call_meta_image_api`). O parser de entrada (`whatsapp_webhook_parser.py:227`) ignora todo
  `type != "text"` — uma foto que um cliente manda pela Meta é descartada silenciosamente.
- **Áudio**: não funciona em nenhum sentido pela Meta. Comentário literal no código
  (`meta_provider.py:52-55`): "Audio replies are out of scope for Meta in this PRD slice... isn't
  a priority" — ou seja, a feature de voz (transcrição Groq + resposta ElevenLabs) que já está no
  ar só funciona no canal Evolution hoje.
- **Embedded Signup**: o fluxo de conectar a conta WhatsApp Business real de um cliente está
  completo e funcional (`whatsapp_embedded_signup_service.py` — troca OAuth, descoberta de WABA,
  criação de canal + credencial). Falta um passo: nunca chama
  `POST /{waba_id}/subscribed_apps`, que é o que diz pra Meta "manda os webhooks dessa conta pro
  meu app". Sem isso, mensagens de clientes conectados por esse fluxo podem não chegar
  automaticamente.

A Evolution já resolve os quatro pontos acima — esta PRD é só sobre fechar a paridade do lado
Meta, não sobre construir algo novo conceitualmente.

## Desenho

### 1. Entrada — reconhecer imagem e áudio vindos da Meta

- `whatsapp_webhook_parser.py`: `WhatsAppInboundMessage` ganha `media_id: str | None` e
  `media_mime_type: str | None` (novos campos opcionais, default `None` — não quebra nenhum
  call site existente). `_extract_text_messages` passa a tratar `type in ("image", "audio")`:
  extrai `message["image"]["id"]`/`message["image"].get("mime_type")` e
  `message["image"].get("caption", "")` como `text_body` (legenda vazia continua válido, mesmo
  princípio já usado pela Evolution); `message["audio"]["id"]`/`mime_type`, sempre válido
  independente de corpo (áudio nunca tem legenda). `message_type` vira `"image"`/`"audio"`.
  Mensagem sem o objeto de mídia correspondente (payload malformado) é ignorada, não quebra.

- Novo `meta_media_service.py` (paralelo ao `evolution_media_service.py`, mesma assinatura de
  retorno `(storage_key, mime_type) | None`): fluxo de 2 chamadas documentado pela Meta —
  `GET /{media_id}` com `Authorization: Bearer {token}` devolve uma URL de CDN válida por ~5min;
  `GET` nessa URL (mesmo Bearer) devolve os bytes. Token resolvido do
  `channel.config_json["access_token_ref"]` via `resolve_channel_secret` (mesmo padrão já usado
  em `meta_provider.py`/`whatsapp_outbound_service.py`). Nunca lança — mesma convenção do resto
  do pipeline de mídia.

- `whatsapp_inbound_service.py::_download_inbound_media`: passa a ramificar por
  `channel.config_json["provider"]` — `"evolution_api"` chama o serviço existente,
  `"meta_cloud_api"` chama o novo `meta_media_service.py` usando `msg.media_id`/`msg.media_mime_type`,
  qualquer outro valor continua sendo ignorado (log, não quebra). O resto do pipeline
  (transcrição, placeholder, persistência) já é agnóstico de provider — não muda.

### 2. Saída — áudio via Meta

- `meta_provider.py::MetaOutboundProvider.deliver_media`: aceita `content_type in ("image",
  "audio")` em vez de só `"image"`. Para áudio, novo `_call_meta_audio_api` — mesmo padrão de
  `_call_meta_image_api` (link-based, Meta busca a mídia numa URL assinada), corpo
  `{"type": "audio", "audio": {"link": audio_url}}` (Meta não suporta caption em áudio — parâmetro
  `caption` é ignorado pra esse tipo, mesmo princípio que a Evolution já segue). Formato MP3
  (`audio/mpeg`, o que a ElevenLabs gera) é um MIME type suportado pela Meta pra mensagem de
  áudio comum (não pro selo nativo de "nota de voz", que exige Ogg/Opus — fora de escopo, MP3
  ainda toca normalmente como anexo de áudio).

### 3. Embedded Signup — inscrever o app pros webhooks da WABA

- `whatsapp_embedded_signup_service.py::create_or_update_whatsapp_channel`: depois do commit do
  canal/credencial, chama `POST /{waba_id}/subscribed_apps` com o `long_lived_token` já obtido
  nesse mesmo fluxo (tem a permissão certa pra essa WABA). Sem corpo, só o Bearer token. Melhor
  esforço — nunca lança, só loga sucesso/falha (não deve travar a criação do canal, que já
  aconteceu; uma falha aqui vira um item de log pra investigar manualmente, não um erro pro
  usuário que acabou de conectar).

## Fora de escopo (deliberado)

- **Selo nativo de "nota de voz"** (waveform, exige Ogg/Opus) — MP3 funciona como áudio comum,
  suficiente pra essa rodada.
- **Publicar o app** (sair de "Não publicado" no painel da Meta) — ação manual do Lucas no painel,
  não é código.
- **Reagendamento/cancelamento via Cal.com** — gap não relacionado a esta PRD, já registrado em
  `negocios/wenzap/decisoes.md`.
- **Migrar o canal ativo hoje de Evolution pra Meta** — esta PRD só fecha paridade de código; a
  decisão de qual provider usar em produção é separada.

## Referências

- `app/services/whatsapp_webhook_parser.py`, `evolution_webhook_parser.py` — parser a estender e
  seu par já completo, usado como referência de shape.
- `app/services/evolution_media_service.py` — padrão de serviço de download de mídia a espelhar.
- `app/services/messaging/meta_provider.py`, `evolution_provider.py` — provider de saída a
  estender e seu par já completo.
- `app/services/whatsapp_embedded_signup_service.py` — fluxo de conexão de conta real, onde entra
  a chamada de `subscribed_apps`.
- Docs oficiais Meta consultados nesta sessão: `developers.facebook.com/docs/whatsapp/cloud-api/reference/media`
  (fluxo de download em 2 passos), `.../reference/messages` (payload de envio de áudio, aceita
  `link` igual imagem), `.../embedded-signup/webhooks` (`subscribed_apps`).

## Estado da implementação

Todos os 3 itens implementados:

1. **Entrada** — `whatsapp_webhook_parser.py` reconhece `image`/`audio` (media_id, mime_type,
   caption pra imagem), `meta_media_service.py` novo faz o download real (2 chamadas Graph API),
   `whatsapp_inbound_service.py` roteia por provider (`evolution_api` → serviço existente,
   `meta_cloud_api` → novo serviço). Pipeline de transcrição/persistência a jusante não mudou —
   já era agnóstico de provider.
2. **Saída** — `MetaOutboundProvider.deliver_media` aceita `image`/`audio`, novo
   `_call_meta_audio_api` (mesmo padrão link-based da imagem).
3. **Embedded Signup** — `_subscribe_app_to_waba` chamado depois da criação do canal/credencial,
   best-effort (nunca desfaz o canal já criado se falhar).

**Achado ao testar**: o envio de imagem via Meta (`MetaOutboundProvider.deliver_media`, já
existente antes desta PRD) **nunca teve nenhum teste** — confirmado por busca no repo inteiro.
Escrito `test_meta_provider.py` cobrindo os dois caminhos (imagem pré-existente + áudio novo),
fechando essa lacuna de cobertura junto.

Testes novos/atualizados: `test_whatsapp_webhook_parser.py` (+4 líquido — 2 casos antigos
"ignorado" trocados pra um tipo genuinamente não suportado, já que imagem/áudio agora são
reconhecidos; 6 casos novos), `test_meta_media_service.py` (9 casos novos), `test_meta_provider.py`
(8 casos novos, cobertura que não existia), `test_whatsapp_inbound_service.py` (teste de imagem
via Meta trocado de "skip" pra "baixa de verdade"; 1 caso novo de áudio via Meta), 
`test_whatsapp_embedded_signup.py` (+2, confirma a chamada de `subscribed_apps` e que uma falha
nela não desfaz o canal). Suite completa: 2364 passando, 11 falhas pré-existentes sem relação
(confirmadas via `git stash` contra a árvore limpa, incluindo uma nova falha de timing
(`test_updated_at_changes_on_second_post`) que também falha sem nenhuma mudança desta sessão).

⚠️ **Não smoke-testado contra a API real da Meta** — construído a partir da documentação oficial
consultada nesta sessão (`developers.facebook.com`), mesmo caveat do resto do pipeline de mídia
desta sessão. Antes de confiar em produção: testar manualmente mandar/receber áudio e imagem com
uma conta Meta real (o app está aprovado, mas ainda "Não publicado" — dá pra testar com número de
desenvolvedor sem precisar publicar).
