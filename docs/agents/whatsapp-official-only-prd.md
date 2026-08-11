# PRD — WhatsApp oficial (Meta) como único caminho pra novas conexões

**Status: 🟡 Em implementação.** Pedido do Lucas depois de confirmar (com print do painel da
Meta) que o App Review foi aprovado e a paridade de código Meta×Evolution foi fechada
(`meta-cloud-api-parity-prd.md`). Decisão: parar de oferecer a Evolution API (bridge não-oficial)
pra novas conexões, e desativar as que já existem até serem reconectadas oficialmente.

## Contexto

Achado ao investigar antes de mexer: o botão de conexão via Meta (`EmbeddedSignupButton.tsx`)
**já existia pronto no código — backend e frontend — mas nunca tinha sido montado em nenhuma
tela**. O único fluxo de conexão que o usuário via era o QR code da Evolution
(`EvolutionQRConnect.tsx`). Ou seja, "oferecer só o oficial" não era trocar um fluxo funcionando
por outro — era ligar, pela primeira vez, um componente órfão.

Os 2 canais WhatsApp ativos em produção hoje são ambos do próprio Lucas (workspaces
`lucas3couto` e `lucas3couto-1`/Acme Ltda, a conta demo) — nenhum cliente real afetado.

## Desenho

### 1. Novas conexões — só Meta

`ImplantarTab.tsx` → `WhatsAppConnectCard`: troca `EvolutionQRConnect` por
`EmbeddedSignupButton` (mesma assinatura de props, `{agentId, onSuccess}` — drop-in). Testado
via Playwright contra ambiente local: o botão "Conectar com Meta" aparece, o clique dispara a
chamada real de `POST /channels/whatsapp/embedded-signup/state` com sucesso, e só para no
carregamento do SDK real da Meta (que exige uma conta Meta de verdade, não automatizável). O
componente `EvolutionQRConnect` fica sem nenhum uso no frontend depois dessa troca — não removido
(pode voltar a ser útil), só desconectado da UI.

### 2. Canais Evolution já ativos — desabilitados + alertados

- `auto_reply_enabled` desligado em `config_json` dos 2 canais Evolution ativos — mesmo mecanismo
  que já existe pra "IA desligada" numa conversa, não é comportamento novo. O agente para de
  responder automático nesse canal; mensagens recebidas continuam sendo guardadas normalmente
  (nada se perde).
- Alerta criado em `agent_alerts` pra cada workspace afetado, orientando a reconectar via
  Integração oficial. Usa o banner que já existe no dashboard (`AgentAlertsWarning`), sem UI nova.

**Achado ao implementar**: `AgentAlert.conversation_id` era `NOT NULL` — o sistema de alertas foi
desenhado só pra "uma conversa específica falhou", não pra "seu canal foi desativado" (não há
conversa nenhuma associada). Coluna virou nullable (migration `079`), `notify_channel_disabled`
novo em `agent_alert_service.py` (aceita uma `error_message_user` específica, ao contrário de
`notify_agent_error` que tem a mensagem fixa em "instabilidade temporária" — não serve pra esse
caso). Corrigido de brinde: o router serializava `conversation_id` nulo como a string `"None"` em
vez de JSON `null`.

## Fora de escopo (deliberado)

- **Remover o código da Evolution API** — desligado da UI de novas conexões, mas o backend
  continua funcionando (canais existentes que ainda não foram migrados seguem operando até serem
  desabilitados/reconectados). Sem plano de remoção de código nesta rodada.
- **Migração automática dos canais Evolution existentes pra Meta** — o operador reconecta
  manualmente via Embedded Signup; não existe (nem devia existir) um script que troca o provider
  de um canal sem o dono re-autorizar a conta de verdade na Meta.
- **Reconexão automática/notificação por e-mail** — só o alerta no dashboard.

## Estado da implementação

Backend: migration `079` + `notify_channel_disabled` + fix de serialização, testados em
`tests/test_agent_alerts.py` (6 casos novos — não existia nenhum teste pra esse sistema antes).
Frontend: troca testada via Playwright contra ambiente local (não produção).
