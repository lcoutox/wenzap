# PRD — WhatsApp Coexistência (Business App + Cloud API no mesmo número)

**Status: 🟡 Em implementação.** Pedido do Lucas depois de perguntar se o fluxo de Embedded
Signup que já validamos em produção (`whatsapp-official-only-prd.md`) é a mesma coisa que
"WhatsApp Coexistência" — não é. Coexistência é um modo separado: o número continua funcionando
no WhatsApp Business App do celular **e** na Cloud API ao mesmo tempo, com sincronização de
histórico e mensagens.

## Contexto

No fluxo que já temos (Embedded Signup padrão), conectar um número exige tirá-lo do WhatsApp
Business App — foi exatamente isso que aconteceu no teste em produção do Lucas: a Meta recusou
conectar até ele excluir a conta do app no celular primeiro. Coexistência existe pra evitar esse
tipo de tudo-ou-nada: o dono do negócio continua respondendo pelo celular dele, com a Wenzap
atuando em paralelo pela API, e as mensagens dos dois lados sincronizadas.

Pesquisei a documentação oficial da Meta antes de propor qualquer código (não trabalhar de
memória num assunto onde detalhe errado quebra produção). Achados confirmados direto na fonte:

- **Não exige nova aprovação da Meta.** Usa as mesmas permissões que já temos aprovadas
  (`whatsapp_business_messaging`, `whatsapp_business_management`). Só exige ser Solution Partner
  ou Tech Provider — já somos, é o que faz o Embedded Signup multi-tenant funcionar hoje.
- **Não é automático.** A Meta documenta: *"To verify that you have enabled the feature
  correctly, access your implementation of Embedded Signup. If the WABA selection screen has been
  replaced with a screen that gives you the option to connect your existing WhatsApp Business
  account, the feature is enabled."* Ou seja, existe uma configuração a ativar no App Dashboard
  da Meta (Facebook Login for Business) que não consegui localizar o nome exato do toggle na
  documentação pública — **o Lucas precisa achar e ativar essa opção manualmente**, e só vamos
  confirmar que está ativa vendo a tela mudar no popup de verdade.
- **Requisito de versão do app:** o WhatsApp Business App do cliente final precisa ser versão
  2.24.17 ou superior — fora do nosso controle, é do lado do cliente.
- **Throughput compartilhado:** número em coexistência tem limite fixo de 20 mensagens/segundo
  (app + API somados) — informativo, a Meta que aplica esse limite, não precisamos implementar
  nada.

## Desenho

### 1. Frontend — reconhecer o evento de coexistência

`FB.login()` continua igual (mesmo `config_id`, mesmo popup). A diferença aparece no
`postMessage` de retorno: em vez de `event: "FINISH"`, vem `event:
"FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING"` quando o usuário escolhe manter o app.

`metaEmbeddedSignup.ts`: `isFinish` passa a aceitar os dois valores de evento. Quando for o de
coexistência, `EmbeddedSignupData` carrega `is_coexistence: true`, propagado até o backend na
troca de código.

### 2. Backend — pular ou registrar o número, conforme o caso

**Achado de graça, corrigido junto:** o fluxo padrão (não-coexistência) nunca chamava `POST
/{phone_number_id}/register` — passo que a Meta documenta como necessário pra ativar o número na
Cloud API. Isso já tinha causado um bug real em produção nesta mesma sessão (número ficou em
`status: PENDING`, nenhuma mensagem chegava, até resolver sozinho ou por uma tentativa manual de
registro). Corrigido agora como parte desta PRD:

- **Fluxo padrão** (`is_coexistence=False`): depois de criar o canal, chama `/register` com um
  PIN de verificação em duas etapas gerado na hora (6 dígitos), best-effort — se falhar (ex:
  número já tem PIN de uma migração anterior, como vimos em produção), só loga, não desfaz a
  conexão. O PIN é guardado como `ChannelCredential` (`credential_type=
  "whatsapp_two_step_pin"`), criptografado, pra eventual necessidade futura.
- **Fluxo de coexistência** (`is_coexistence=True`): **não chama `/register`** — o número já está
  registrado (é a diferença central desse modo). Em vez disso, chama `POST
  /{phone_number_id}/smb_app_data` com `{"messaging_product": "whatsapp", "sync_type":
  "history"}`, best-effort, pra disparar a sincronização de histórico. **Prazo real da Meta: 24
  horas** a partir da conclusão do Embedded Signup pra isso ser disparado, senão o cliente precisa
  desconectar e refazer o fluxo inteiro — por isso essa chamada acontece imediatamente na troca de
  código, não em background.

`config_json.onboarding_type` grava `"embedded_signup_coexistence"` quando aplicável, e
`config_json.coexistence_enabled: true` — usado pela UI (item 5) e pra decidir a lógica de
handoff (item 4).

### 3. Webhook — três campos novos

Preciso assinar (a nível do App na Meta) três campos além de `messages`:

- **`history`** — mensagens antigas, em lotes (`phase`, `chunk_order`, `progress`). Se o
  histórico for recusado pelo dono do número, vem um erro (código `2593109`) em vez do payload —
  tratado como "sem histórico", segue o fluxo normal daí pra frente.
- **`smb_app_state_sync`** — contatos adicionados/removidos no WhatsApp do dono.
- **`smb_message_echoes`** — mensagens que o dono manda pelo próprio celular depois de conectado.

Inscrição feita direto via Graph API (`POST /{app-id}/subscriptions`), mesma técnica já usada
nesta sessão pra verificar o webhook via `GET /{app-id}/subscriptions` — sem depender de o Lucas
clicar checkbox no painel.

### 4. Serviço novo — `whatsapp_coexistence_service.py`

- **`process_history_sync`**: cada mensagem do lote vira `Contact` + `Conversation` +
  `ConversationMessage`, idempotente por `wamid` (mesmo padrão do inbound normal). Direção
  (`inbound`/`outbound`) decidida comparando o campo `from` da mensagem com o número do negócio.
  **Decisão deliberada**: conversas importadas do histórico **não** contam pra cota de "novas
  conversas" do plano (`plan_service.count_new_conversation`) — são conversas que já aconteceram
  antes da Wenzap existir, cobrar o cliente por isso seria injusto. Marcadas com
  `metadata_json.imported_from = "whatsapp_business_app_history"` pra rastreabilidade.
  `created_at` da mensagem preserva o timestamp original do WhatsApp, não o momento da importação.
  **Nunca dispara auto-reply** — são mensagens do passado.
- **`process_state_sync`**: `action=add` cria/atualiza `Contact` (mesmo padrão de
  `_get_or_create_contact`). `action=remove` só loga — **decisão deliberada de não apagar nada**:
  remover um `Contact` em cascata apagaria conversas e mensagens reais, um efeito destrutivo
  grande demais pra reagir a um evento de sincronização de agenda do celular do cliente.
- **`process_message_echo`**: mensagem enviada pelo dono via app vira `ConversationMessage`
  (`direction="outbound"`, `sender_type="human"`, `sender_user_id=None` — não é um usuário Wenzap,
  é o dono respondendo pelo celular). Reaproveita `_get_or_create_conversation` do fluxo normal
  (mesma cota/contagem de conversa nova que já existe hoje). **Consequência importante**: a
  conversa tem `ai_enabled` desligado (`handoff_reason: "Dono respondeu pelo WhatsApp Business
  App"`) — mesmo mecanismo que já existe pra handoff manual (`request_human`/"Assumir"), evita a
  IA responder por cima do que o dono acabou de responder pelo próprio celular.

### 5. UI — indicador de coexistência

`ImplantarTab.tsx`: dentro de "Detalhes técnicos" do card de WhatsApp, mostra "Modo: Coexistência"
quando `config.coexistence_enabled` é `true` (hoje só mostra "Conexão: Embedded Signup"). Sem UI
nova pra histórico/echoes nesta rodada — as mensagens aparecem no Inbox normal, como qualquer
mensagem de WhatsApp.

## Fora de escopo (deliberado)

- **Ativar a opção de coexistência no App Dashboard da Meta** — ação manual do Lucas, não
  encontrei API pra isso na documentação pública. Verificamos juntos vendo se a tela do popup
  muda quando ele testar com um número que já está no WhatsApp Business App.
- **UI dedicada de progresso de sincronização de histórico** (barra de progresso por
  `phase`/`chunk_order`/`progress`) — as mensagens aparecem no Inbox conforme chegam, sem indicador
  visual de "sincronizando". Fica pra depois se o volume justificar.
- **Suporte a tipos de mensagem além de texto no histórico importado** (imagem, áudio, documento
  antigos) — a doc da Meta não detalha o formato exato do campo de mídia dentro de `history`
  (só mostra `"<MESSAGE_TYPE>": { <MESSAGE_CONTENTS> }` genérico). Pra não arriscar quebrar ou
  perder mensagem, tipos não-texto no histórico entram como placeholder de texto (ex: "[mensagem
  de imagem — histórico]"), sem baixar mídia. Mensagens novas (chegando por `messages` normal)
  continuam com suporte completo a imagem/áudio, sem mudança.
- **Retomar automaticamente a IA depois de um echo** — fica desligada até alguém (humano) religar
  manualmente no Inbox, mesmo comportamento que handoff manual já tem hoje.

## Estado da implementação

**Backend**: parsers dos 3 campos novos (`whatsapp_webhook_parser.py`), serviço
`whatsapp_coexistence_service.py` (history import, contact sync, echo + pausa de IA), roteados em
`whatsapp_webhooks.py`. `is_coexistence` propagado pelo schema/router/serviço do Embedded Signup,
com `/register` (fluxo padrão) ou `/smb_app_data` (coexistência) disparados na troca de código.
App já inscrito nos 3 campos novos em produção via Graph API (`POST /{app-id}/subscriptions`),
confirmado com `GET` logo depois — `active: true`, os 13 campos (10 antigos + 3 novos) presentes.

**Frontend**: `metaEmbeddedSignup.ts` aceita `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING` e propaga
`is_coexistence` até o exchange. `ImplantarTab.tsx` mostra "Modo: Coexistência" nos Detalhes
técnicos quando aplicável. `tsc --noEmit` limpo.

**Testes**: 30 novos (25 em `test_whatsapp_coexistence.py` — parsers + serviço completo; 2 de
integração no router em `test_whatsapp_webhooks.py`; 3 no fluxo de Embedded Signup em
`test_whatsapp_embedded_signup.py` — coexistência pula `/register` e dispara `/smb_app_data`,
credencial de PIN é salva, falha de `/register` não derruba a criação do canal). Suite completa
sem regressão.

**Não testado / não pode ser testado sem uma conta real em coexistência**: o payload exato de
`history`/`smb_app_state_sync`/`smb_message_echoes` foi montado a partir dos exemplos da
documentação oficial da Meta, não de uma captura real — mesma ressalva já registrada pra todo o
resto do Embedded Signup. **Pendência real, não uma formalidade**: a opção de coexistência
precisa ser habilitada manualmente no App Dashboard da Meta (Facebook Login for Business →
configuração usada no nosso Embedded Signup) — não encontrei essa ação exposta via API. Só vamos
saber que está ativa testando com um número de verdade que já esteja no WhatsApp Business App e
vendo se a tela do popup muda pra oferecer a opção de manter o app.
