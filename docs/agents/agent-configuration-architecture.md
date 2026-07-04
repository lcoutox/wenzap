# Agent Configuration Architecture

## Abas principais do agente

O workspace do agente tem 4 abas principais:

| Aba | Pergunta que responde |
|---|---|
| **Chat** | Como este agente está conversando agora? |
| **Canais** | Onde este agente está publicado? |
| **Ferramentas** | Quais capacidades e bases de conhecimento estão conectadas? |
| **Configurações** | Como este agente é configurado? |

## Subabas de Configurações

Dentro de Configurações, a navegação é:

```
Geral → Comportamento → Conhecimento → Modelo → Pipeline
```

### Geral
**Pergunta:** Quem é este agente?

Contém:
- Nome do agente
- Descrição interna (identificação operacional, não comportamento)
- Avatar
- ID do agente (referência)
- Área de perigo (arquivar)

Não contém: prompt, tom, estilo, conhecimento, modelo, pipeline.

### Comportamento
**Pergunta:** Como este agente conversa?

Contém:
- **Tempo de resposta** (`reply_delay_seconds`): 0 / 3 / 5 / 8 / 15 segundos — debounce antes de gerar resposta automática. Ver `docs/agents/reply-delay-and-message-debounce.md`.
- **Estilo de resposta** (`response_style`): objetivo / equilibrado / detalhado
- **Idioma** (`language_mode`): automático / pt / en / es
- **Modo de configuração**: Guiado ou Avançado
  - **Guiado** (`guided_config`): seções estruturadas
    1. Papel e objetivo (função principal + objetivo)
    2. Estilo de conversa (postura + iniciativa)
    3. Regras de atuação (deve fazer / não deve fazer — enums + customizadas)
    4. Quando não souber
    5. Exemplos (boa resposta / resposta a evitar)
  - **Avançado** (`advanced_prompt`): textarea livre

Não contém: knowledge_only, show_sources, modelo, ferramentas.

### Conhecimento
**Pergunta:** De onde o agente pode tirar informação?

Contém:
- **Responder apenas com base** (`knowledge_only`): restringe ao conhecimento conectado
- **Mostrar fontes** (`show_sources`): cita fontes nas respostas
- Link orientando para a aba Ferramentas (conectar/remover bases)

Não conecta/desconecta bases aqui — isso é na aba Ferramentas.

### Ferramentas
**Pergunta:** Quais capacidades o agente pode usar?

Contém:
- Bases de conhecimento (conectar/remover)
- Catálogo de produtos
- Ações (futuro)
- Integrações (futuro)

### Modelo
**Pergunta:** Qual IA executa este agente?

Contém:
- Seleção de modelo de IA
- Temperatura

### Pipeline
**Pergunta:** Onde novas conversas entram?

Contém:
- Pipeline padrão para novas conversas
- Stage padrão

### Segurança
**Pergunta:** Quais limites e proteções se aplicam?

Status: planejado para fase futura.

## Hierarquia de prompt

O prompt final enviado ao LLM é composto nesta ordem:

1. **Identity anchor** — nome + descrição do agente
2. **Operator instructions** — bloco gerado por `build_agent_instructions_block()`:
   - Modo `advanced` → usa `advanced_prompt` (fallback: `system_prompt` legado)
   - Modo `guided` → compila `guided_config` (fallback: `system_prompt` legado)
   - Retorna `None` se nada configurado (bloco omitido)
3. **Response style** — baseado em `response_style`
4. **Language mode** — baseado em `language_mode`
5. **Knowledge restriction** — se `knowledge_only=True`
6. **RAG context** — base de conhecimento recuperada (se disponível)
7. **Show sources** — se `show_sources=True` e RAG presente
8. **Catalog context** — catálogo de produtos (se disponível)
9. **Channel rules** — ex: WhatsApp (plain text only)
10. **Pipeline extra_prompt** — instruções da stage ativa (se configurado)
11. **Nexbrain safety rules** — sempre último, imutável

`response_style`, `language_mode`, `knowledge_only`, `show_sources` são **sempre aplicados** independente do modo de instruções (guided ou advanced).

## Campos do guided_config

```json
{
  "role": "consultive_sales | customer_support | ...",
  "main_objective": "string (max 500)",
  "posture": "consultive | direct | educational | welcoming | technical",
  "initiative": "only_respond | respond_suggest | drive_conversion",
  "when_no_info": "ask_context | direct_to_team | knowledge_only",
  "do_items": ["answer_company_questions", "qualify_leads", ...],
  "custom_should_do": ["string livre..."],
  "dont_items": ["no_fake_prices", "no_guarantee_results", ...],
  "custom_should_not_do": ["string livre..."],
  "extra_restrictions": "string (max 1000)",
  "good_response_example": "string (max 2000)",
  "bad_response_example": "string (max 2000)"
}
```

`response_style` e `language_mode` ficam **fora** do `guided_config` — são campos de nível superior em `agent_prompt_settings`.
