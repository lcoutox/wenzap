# Agent Model & Context Settings

## O que é Modelo

O modelo de IA define qual engine executa as respostas do agente. Cada modelo tem:

- Provedor (Anthropic, OpenAI, Google, Nexbrain)
- Capacidades (texto, imagem, raciocínio, ferramentas, código)
- Custo base em créditos por mensagem (`credits_per_message`)
- Plano mínimo exigido (`min_plan_code`)

O modelo é salvo em `agent_model_settings.ai_model_id` (fonte autoritativa).

## O que é Contexto do Agente

O contexto do agente define quanto conteúdo o agente consegue considerar antes de responder, incluindo:

- Instruções do agente (prompt)
- Histórico da conversa
- Base de conhecimento (RAG)
- Catálogo de produtos
- Dados do contato e variáveis
- Pipeline/etapa atual
- Resultados de ferramentas/API (futuro)

**Não é** apenas "memória da conversa" — é um orçamento geral de contexto que afeta todos os componentes.

## Por que contexto consome créditos

Contexto maior significa mais tokens enviados ao LLM por requisição. O custo é:

```
credits_por_resposta = credits_per_message (modelo) × credit_multiplier (tier)
```

## Tiers de Contexto

| Tier | Label | Caracteres | Multiplicador | Disponibilidade |
|------|-------|-----------|----------------|-----------------|
| `economical` | Econômico | 6.000 | 1× | Todos |
| `standard` | Padrão | 15.000 | 2× | Todos |
| `broad` | Amplo | 25.000 | 4× | Growth+ |
| `advanced` | Avançado | 35.000 | 8× | Growth+ |
| `maximum` | Máximo | 300.000 | 16× | Scale/Enterprise |

Exemplo com modelo base de 1 crédito:
- Econômico: 1 crédito/resposta
- Padrão: 2 créditos/resposta
- Amplo: 4 créditos/resposta
- Avançado: 8 créditos/resposta
- Máximo: 16 créditos/resposta

## Disponibilidade por Plano

| Plano | Tiers disponíveis |
|-------|-------------------|
| Starter | Econômico, Padrão |
| Growth | Econômico, Padrão, Amplo, Avançado |
| Scale | Todos |
| Enterprise | Todos |

Definido em `context_tier_service.py: CONTEXT_TIER_PLAN_MATRIX`.

## Como o Contexto Afeta os Componentes

O orçamento de caracteres é distribuído aos componentes em ordem de prioridade:

1. **Identidade + instruções do agente** — sempre incluídos
2. **RAG (base de conhecimento)** — limita `rag_max_chars` por tier
3. **Catálogo** — limita número de itens por tier
4. **Histórico da conversa** — limita número de mensagens por tier

### Limites por tier

| Tier | history_limit | rag_max_chars | catalog_limit |
|------|--------------|---------------|---------------|
| economical | 5 msgs | 3.000 chars | 1 item |
| standard | 20 msgs | 8.000 chars | 3 itens |
| broad | 40 msgs | 12.000 chars | 5 itens |
| advanced | 60 msgs | 18.000 chars | 8 itens |
| maximum | 500 msgs | 150.000 chars | 20 itens |

Definido em `context_tier_service.py: CONTEXT_TIER_CONFIG`.

## Armazenamento

- Campo: `agent_model_settings.context_window_tier` (VARCHAR 20, NOT NULL, default 'standard')
- Migration: `058_agent_context_tier.py`
- Novos agentes: `standard` (definido em `agent_service.py: create_agent`)
- Agentes existentes (backfill): `standard` (definido em `058_agent_context_tier.py`)

## Limitações Conhecidas

- A divisão interna do orçamento entre componentes usa limites pré-definidos por tier, não um algoritmo dinâmico proporcional.
- O catálogo tem `_MAX_LIMIT=20` no serviço — tiers acima de 20 itens não terão efeito adicional.
- Validação de preview no browser requer backend rodando localmente.
