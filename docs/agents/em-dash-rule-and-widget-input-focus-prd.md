# PRD — Regra contra travessão no core do prompt + foco do input após enviar

**Status: ✅ Implementado (2026-07-20).** Dois achados do mesmo review ao vivo do agente Léo
(widget da landing) que gerou o [[capture-contact-identity-sync-prd.md]] — pequenos o suficiente
pra não precisarem de desenho longo, mas registrados como PRD a pedido do Lucas.

## 1. Travessão (—) em excesso nas respostas do agente

### Problema
O Léo (e por extensão qualquer agente da plataforma) usa "—" com frequência muito acima do que
uma pessoa real digita numa conversa de texto. É um tique conhecido de modelos Anthropic/OpenAI em
geração de texto solto, mas quebra o objetivo do próprio `_CORE_CONVERSATION_STYLE`
(`agent_context_builder.py:78-81`, adicionado nesta mesma sessão) de soar como conversa humana
normal — ninguém manda "vou verificar isso — te aviso em breve" no WhatsApp.

### Correção
Uma linha a mais no bloco de core já existente, sem criar bloco novo — é a mesma categoria de
regra (estilo de escrita, sempre aplicada, independente de canal/response_style):

```python
_CORE_CONVERSATION_STYLE = """\
Conversation style (baseline — always applies): write like a real person having a normal text \
conversation. Natural and warm, not like a script, a form, or a corporate template. This is the \
default regardless of channel or the response length settings below. Avoid overusing em dashes \
(—) — most people don't write with them in everyday messages. Prefer a period, a comma, or simply \
starting a new sentence instead."""
```

Sem gate, sem migration, sem mudança de schema — é texto de prompt.

## 2. Foco do campo de mensagem some depois de apertar Enter

### Problema
`handleSend` (`WidgetEmbed.tsx`) seta `sending=true` de forma síncrona assim que o envio começa,
e o `<textarea>` tem `disabled={sending || !!initError}`. Navegador tira o foco automaticamente de
qualquer elemento que vira `disabled` — então apertar Enter manda a mensagem e imediatamente
derruba o foco do campo, mesmo `sending` voltando pra `false` uns instantes depois (assim que o
POST resolve). Resultado: quem manda mensagem picada de propósito (o comportamento que a correção
de indicador de digitando desta mesma sessão passou a suportar de verdade) precisa clicar de novo
no campo antes de continuar digitando — trava exatamente o fluxo que a outra correção destravou.

### Correção
`setSending(false)` só atualiza o estado — o React ainda precisa re-renderizar pra tirar o
`disabled` do DOM antes de `.focus()` funcionar (chamar `.focus()` num elemento ainda `disabled`
não faz nada). Por isso a devolução de foco entra num `useEffect` reagindo à transição de
`sending`, que roda depois do commit/re-render, não inline logo após `setSending(false)`:

```tsx
// O lock de envio é breve (só o POST) — assim que libera, devolve o foco pro
// campo, pra apertar Enter não derrubar o foco no meio de uma mensagem picada.
useEffect(() => {
  if (!sending && open) inputRef.current?.focus();
}, [sending, open]);
```

## Referências

- `apps/api/app/services/agent_context_builder.py:78-81` — `_CORE_CONVERSATION_STYLE`.
- `apps/web/src/components/widget/WidgetEmbed.tsx` — `handleSend`, `<textarea disabled={sending...}>`,
  efeito existente "Focus input when chat opens" (padrão já usado, replicado aqui pra outro gatilho).

## Estado da implementação

Ambos aplicados. Sem teste automatizado novo — a regra de travessão é conteúdo de prompt (não dá
pra asserir output de LLM em teste unitário determinístico) e o foco de input é comportamento de
DOM/browser que os testes desta suíte não cobrem (sem Testing Library configurado pro widget). Não
testado clicando na UI real (sem ferramenta de browser disponível nesta sessão) — só verificado via
`tsc --noEmit` e leitura do fluxo de estado.
