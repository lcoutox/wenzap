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

## Estado da implementação

Backend: endpoint (já genérico pra `image`/`audio` desde a primeira versão desta PRD) + fix do
placeholder, testados em `tests/test_message_media_url.py` (9 casos: 404 mensagem/conversa, 422
sem mídia, 200 imagem/áudio, 502 storage, RBAC viewer/não-membro — cobre os dois content_types).
2305 testes passando no total (10 falhas pré-existentes sem relação). Frontend: `tsc --noEmit` e
`next build` limpos pros dois componentes (áudio e imagem). Não testado manualmente no navegador
nesta sessão.
