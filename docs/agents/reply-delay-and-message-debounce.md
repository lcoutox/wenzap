# Reply Delay & Message Debounce

## O que é

O **Tempo de resposta** (reply delay) é uma configuração de comportamento do agente que define quantos segundos ele aguarda após a última mensagem do cliente antes de gerar uma resposta automática.

## Por que existe

Usuários frequentemente enviam mensagens em partes, especialmente em WhatsApp e widgets de site:

```
12:00:00 cliente: Oi
12:00:02 cliente: queria saber os planos
12:00:04 cliente: minha empresa é uma clínica
```

Sem debounce, o agente responderia à primeira mensagem "Oi" antes do cliente terminar de escrever, gerando respostas fragmentadas e má experiência.

Com debounce de 5 segundos, o agente aguarda e responde uma única vez às três mensagens juntas.

## Onde configurar

**Configurações → Comportamento → Tempo de resposta**

Opções disponíveis:

| Valor | Label | Observação |
|-------|-------|------------|
| 0 | Imediato | Comportamento legado — responde na hora |
| 3 | 3 segundos | — |
| 5 | 5 segundos | **Recomendado** |
| 8 | 8 segundos | — |
| 15 | 15 segundos | Para conversas mais lentas |

## Comportamento padrão

- **Novos agentes:** `reply_delay_seconds = 5` (configurado na criação via `agent_service.create_agent`)
- **Agentes existentes (migration 059):** `reply_delay_seconds = 0` (preserva comportamento anterior)

## Como funciona tecnicamente

### Fluxo com debounce

```
cliente envia mensagem
→ API salva mensagem (commit imediato)
→ API lê reply_delay_seconds do agente
→ delay=0: reply gerado sincronamente (mesmo request)
→ delay>0: thread daemon iniciada → HTTP retorna imediatamente
             thread dorme N segundos
             thread acorda e verifica se a mensagem ainda é a mais recente
             se sim: gera resposta
             se não: encerra sem fazer nada
```

### Invalidação de jobs antigos

Não existe cancelamento de threads. Em vez disso, usa-se o ID da última mensagem como verificação:

1. Thread recebe `trigger_message_id` (ID da mensagem que disparou o agendamento).
2. Ao acordar, a thread consulta a mensagem inbound customer mais recente da conversa.
3. Se `latest_message.id != trigger_message_id`, a thread encerra sem gerar resposta.
4. Uma thread para cada mensagem — apenas a última thread gera resposta.

### Onde é aplicado

| Fluxo | Aplica debounce? |
|-------|-----------------|
| Web Widget inbound | ✅ Sim |
| WhatsApp inbound | ✅ Sim |
| Inbox (mensagem via API autenticada) | ✅ Sim |
| Playground (teste manual) | ❌ Não — usa `agent_test_service`, desacoplado |

### Armazenamento

- Campo: `agent_prompt_settings.reply_delay_seconds` (`INTEGER NOT NULL DEFAULT 0`)
- Migration: `059_agent_reply_delay_seconds.py`
- Pertence a `agent_prompt_settings` porque é configuração de comportamento do agente, não do canal.

## Proteção de créditos

Créditos são consumidos **apenas quando a resposta é de fato gerada** (dentro de `generate_conversation_agent_reply`, somente em caso de sucesso LLM).

Threads no-op (invalidadas por mensagem mais recente) encerram antes de chamar `generate_conversation_agent_reply` → **nenhum crédito consumido**.

Exemplo: cliente envia 3 mensagens em 5 segundos com delay=5s:
- Thread 1 acorda, vê que não é a mais recente → no-op
- Thread 2 acorda, vê que não é a mais recente → no-op
- Thread 3 acorda, é a mais recente → gera resposta → 1 consumo de crédito

## Limitações conhecidas

1. **Threads daemon:** não persistem após reinício do servidor. Se o processo reiniciar durante o período de debounce, a resposta não é gerada. Solução futura: migrar para Celery.
2. **Mesma sessão:** múltiplos pods/workers não compartilham threads — em produção com múltiplos workers, cada worker agenda sua própria thread. O mecanismo de validação por `trigger_message_id` garante que apenas uma thread produz resposta, mas pode haver pequenas janelas de duplicidade em ambientes muito concorrentes. Solução futura: Celery com lock Redis.
3. **delay=0:** mantém comportamento síncrono (HTTP aguarda LLM). Aceito na spec; futuro: mover para background mesmo com delay=0.
4. **Sem UI de fila:** não há visualização de mensagens aguardando resposta na interface.
