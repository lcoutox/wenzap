# PRD — Tocar áudio/imagem no Inbox + transcrição

**Status: 🟢 Implementado (áudio e imagem).** Pedido do Lucas depois de testar a resposta em voz
do WhatsApp em produção: "Quando via whatsapp é enviado audio por parte do bot e do lead, os
audios não aparecem no inbox." Retoma o item explicitamente deixado fora de escopo em
[whatsapp-voice-groq-elevenlabs-prd.md](whatsapp-voice-groq-elevenlabs-prd.md) ("Exibir/tocar áudio
no Inbox"). Estendido pra imagem no mesmo dia, a pedido explícito ("Pode implementar a de imagem
também") — a lacuna era idêntica e o endpoint já tinha sido construído de forma genérica.

## Achado

`MessageBubble.tsx` nunca teve nenhuma lógica baseada em `content_type` — toda mensagem (texto,
imagem, áudio) renderizava só `msg.content` como texto puro. Pra áudio isso significava:
mensagem do cliente mostrava a transcrição sem indicar que veio de voz; mensagem do bot mostrava
literalmente o placeholder fixo `"[Mensagem de voz]"`, sem player nenhum — visualmente parecia bug.
Pra imagem (só inbound — mensagem enviada pelo cliente pelo WhatsApp; imagem de catálogo já tinha
seu próprio card) mostrava só a legenda ou o placeholder `"[Imagem]"`, sem a foto nenhuma.

Também não existia nenhum endpoint que resolvesse `ConversationMessage.media_url` (uma chave de
storage, não uma URL navegável) pra algo que o navegador consiga tocar/exibir.

## Desenho

### Backend

- `conversation_message_service.resolve_message_media_url(db, workspace_id, conversation_id,
  message_id) -> str` — carrega a mensagem (404 se não existir/não for do workspace), 422 se
  `content_type` não for `image`/`audio` ou não tiver `media_url`, resolve via
  `storage.generate_presigned_url(...)` (502 se o storage falhar). Gera uma URL nova a cada
  chamada — não cacheia, já que URL assinada expira.
- Rota `GET /conversations/{conversation_id}/messages/{message_id}/media-url` → `{"url": str}`.
  Mesmo nível de acesso de leitura de mensagens (`_READ_ROLES` — owner/admin/member/viewer).
- Corrigido de brinde: a mensagem de voz de saída do agente
  (`_try_deliver_voice_reply` em `conversation_agent_reply_service.py`) tinha `content` fixo em
  `"[Mensagem de voz]"` — trocado pro texto real que foi sintetizado, pra transcrição do lado do
  bot também funcionar.

### Frontend

- `api.conversations.messages.getMediaUrl(conversationId, messageId)` novo em `lib/api.ts`.
- `AudioMessageContent` novo em `MessageBubble.tsx` — busca a URL assinada ao montar (loading →
  player nativo `<audio controls>` ou aviso de indisponível), com "Ver transcrição" recolhível
  abaixo (mesmo padrão visual do `CatalogRetrievalBadge` já existente no arquivo). Usado tanto em
  `InboundBubble` (áudio do cliente) quanto `OutboundBubble` (áudio do agente), disparado quando
  `msg.content_type === "audio"`.
- Estilos usam opacidade sobre a cor de texto herdada (`opacity-70`/`opacity-90` em vez de tokens
  `nb-*` fixos), porque o mesmo componente aparece tanto no bubble claro do cliente
  (`bg-nb-elevated text-nb-text`) quanto no bubble colorido do agente (`text-white`).
- `ImageMessageContent` novo — mesmo padrão de busca de URL, renderiza um card autocontido
  (`aspect-square`, `object-cover`, com a legenda abaixo se houver e for diferente do placeholder
  `"[Imagem]"`) igual ao `CatalogMediaMessageCard` já existente, e **substitui** o bubble com
  padding em vez de ficar aninhado nele (uma foto com padding de texto ao redor fica estranho) —
  mesmo tratamento condicional que `catalogMedia` já recebia em `OutboundBubble`. Usado em
  `InboundBubble` e `OutboundBubble` quando `msg.content_type === "image"`.

## Fora de escopo (deliberado)

- **Player/viewer customizado** — usa o `<audio controls>` nativo do navegador e um `<img>` simples
  (sem lightbox/zoom). Aceitável pro MVP.
- **Preview local (dev)** — `generate_presigned_url` do `LocalStorageProvider` retorna um caminho
  `file://`, que o navegador não toca/exibe. Só funciona de verdade em produção (R2). Mesma
  limitação pré-existente de outras features de mídia.

## Correção (2026-07-28): imagem de catálogo nunca aparecia no Inbox

Achado real do Lucas ao testar em produção: a imagem que o agente manda quando recomenda um item
do catálogo aparecia sempre como "Prévia indisponível" + "Falha ao enviar imagem do Catálogo",
mesmo quando a entrega tinha funcionado. Causa raiz: o `CatalogMediaMessageCard` (card específico
pra imagem de catálogo, anterior a esta PRD) lia dois campos que `catalog_media_delivery_service.py`
nunca preenchia direito:
- `delivery.media_url` — nunca foi setado nessa chave de metadata; a imagem não tinha de onde
  carregar.
- `delivery.sent` — inicializado `False` na criação da mensagem e **nunca atualizado pra `True`**
  no caminho de sucesso (o sucesso real é gravado em `metadata_json.delivery.status`, uma chave
  diferente, pelo `OutboundProvider` que entregou). Resultado: toda imagem de catálogo, entregue ou
  não, sempre mostrava o badge de falha.

Corrigido **removendo** o card especial em vez de consertá-lo — ele duplicava (mal) o que o
`ImageMessageContent` genérico (desta mesma PRD) e o `DeliveryBadge` já existente já faziam
corretamente:
- `OutboundBubble` agora usa `ImageMessageContent` pra qualquer `content_type === "image"`,
  catálogo incluso — sem ramo especial. Resolve a URL de verdade via
  `GET .../media-url` (a mesma rota, já genérica) em vez de depender de um campo nunca preenchido.
- `DeliveryBadge` (já renderizado pra toda mensagem outbound) mostra "Não entregue" + botão de
  reenviar quando `metadata_json.delivery.status === "failed"` — a chave que o provider realmente
  atualiza. Ganho extra: catálogo agora tem retry, que o card antigo nunca teve.
- `catalog_media_delivery_service.py` simplificado: `content` da mensagem vira só a legenda (sem o
  wrapper `"[Imagem: ...]"`), `metadata_json.catalog_media_delivery` guarda só `item_id`/`media_id`
  (usado pelo antispam `_was_recently_sent`) — o resto (`sent`, `attempted`, `reason`, `media_url`)
  era campo morto que nada lia corretamente. `_record_delivery_failure` (fallback pra quando
  `deliver_media_message` levanta uma exceção inesperada, já que providers não deveriam levantar)
  agora grava em `metadata_json.delivery` também, não só num campo que a UI não olha mais.
- `CatalogMediaMessageCard`, `getCatalogMediaDelivery` e o tipo `CatalogMediaDelivery` removidos —
  código morto depois da consolidação.

Testado: `test_catalog_media_delivery.py` atualizado (verifica `metadata_json.delivery.status`
em vez do campo antigo). `tsc --noEmit` e `next build` limpos.

## Estado da implementação

Backend: endpoint (já genérico pra `image`/`audio` desde a primeira versão desta PRD) + fix do
placeholder + consolidação da imagem de catálogo, testados em `tests/test_message_media_url.py`
(9 casos) e `tests/test_catalog_media_delivery.py`. 2340 testes passando no total (10 falhas
pré-existentes sem relação). Frontend: `tsc --noEmit` e `next build` limpos pros três componentes
(áudio, imagem genérica, imagem de catálogo consolidada). Não testado manualmente no navegador
nesta sessão.
