# PRD — Refatoração do Módulo de Agentes

## Contexto

Este documento consolida o plano de refatoração do módulo de agentes do Nexbrain, definido nas sessões de design com o produto. Serve como referência central para rastrear o que foi feito e o que ainda falta.

O problema raiz era que a configuração estava fragmentada: Instruções e Comportamento respondiam a mesma pergunta, Restrições de conhecimento ficavam num lugar separado das instruções, e o usuário não sabia qual tela realmente mandava no comportamento do agente.

---

## Princípio central aprovado

Cada aba deve responder uma pergunta diferente:

| Aba | Pergunta |
|---|---|
| **Comportamento** | Como o agente responde? |
| **Conhecimento** | De onde ele tira informação? |
| **Ferramentas** | O que ele pode usar? |
| **Modelo** | Qual IA executa? |
| **Pipeline** | Onde a conversa entra? |
| **Segurança** | Quais limites e proteções? |

---

## Estrutura aprovada das abas

### Abas principais do workspace do agente

```
Chat | Canais | Ferramentas | Configurações
```

A aba **Ferramentas** permanece fora de Configurações como aba principal (responde operacionalmente, não é configuração).

### Subabas dentro de Configurações

```
Geral → Comportamento → Conhecimento → Modelo → Pipeline → Segurança
```

---

## Hierarquia de conflitos aprovada

Quando houver conflito entre configurações, a ordem de precedência é:

1. Regras internas do Nexbrain (safety)
2. Limites do plano e ferramentas disponíveis
3. Configurações de conhecimento (`knowledge_only`)
4. Ferramentas ativas
5. Comportamento do agente (guiado compilado OU avançado)
6. Pipeline/etapa atual
7. Histórico e mensagem do usuário

Exemplos:
- Modo avançado diz "responda mesmo sem base" + `knowledge_only=true` → vence `knowledge_only`
- Pipeline extra prompt diz "ofereça desconto" + safety diz "não inventar descontos" → vence safety

---

## Detalhamento das abas

### Configurações → Geral

**Pergunta:** Quem é este agente dentro da minha operação?

**1. Identidade do agente**
- Nome do agente — visível internamente e, dependendo do canal, para o cliente
- Descrição interna — **não é prompt principal**. Helper text: *"Use uma descrição curta para identificar a função deste agente. As regras de comportamento ficam na aba Comportamento."*
- Avatar
- Status: Ativo / Inativo

**2. Identificadores** (somente leitura)
- ID do agente + botão "Copiar ID"
- Criado em
- Atualizado em

**3. Área de perigo** (visual separado, no final da página)
- **Arquivar agente** — remove das listas ativas, preserva histórico e configurações
- **Excluir permanentemente** — só permitido se não houver dependências (conversas, canais, logs). Exige confirmação digitando o nome do agente

**O que NÃO fica em Geral:** tom de voz, prompt, estilo, idioma, base de conhecimento, catálogo, pipeline, modelo, temperatura, canais.

---

### Configurações → Comportamento

**Pergunta:** Como este agente deve agir, responder e conduzir conversas?

Esta é a aba mais importante para a resposta do agente. Contém tudo que define como o agente responde — inclui instruções, estilo, idioma e tempo de resposta.

**Estrutura da aba:**

```
[Modo guiado] [Modo avançado]
```

Seguido de campos que se aplicam independente do modo:
- Tempo de resposta (`reply_delay_seconds`)
- Estilo de resposta (`response_style`)
- Idioma (`language_mode`)

#### Modo guiado — campos aprovados

O modo guiado gera por baixo um bloco de instruções estruturado. O usuário preenche campos simples; o sistema compila em prompt interno organizado.

**1. Papel e objetivo**
- **Função principal** (select): Atendimento inicial / Vendas consultivas / Pré-vendas e qualificação / Suporte ao cliente / Relacionamento / pós-venda / Recepção e triagem / Personalizado
- **Objetivo principal** (textarea curto): campo livre. Ex: "Qualificar interessados e explicar os planos."

**2. Estilo de conversa**
- **Postura do agente** (select): Consultivo / Direto / Educativo / Acolhedor / Técnico
- **Estilo de resposta** (select): Objetivo / Equilibrado / Detalhado
- **Idioma** (select): Automático / Português / Inglês / Espanhol
- **Nível de iniciativa** (select): Apenas responder / Responder e sugerir próximo passo / Conduzir ativamente para conversão

**3. Regras de atuação**

*O que o agente deve fazer* — checklist com opções sugeridas + campo `+ Adicionar regra personalizada`:
- Responder dúvidas sobre a empresa
- Explicar produtos, serviços ou planos cadastrados
- Qualificar interessados com perguntas simples
- Recomendar opções do Catálogo quando relevante
- Orientar o visitante para o próximo passo
- Pedir mais contexto quando a pergunta estiver vaga
- Usar a Base de Conhecimento antes de responder

*O que o agente não deve fazer* — checklist com opções sugeridas + campo `+ Adicionar restrição personalizada`:
- Não inventar preços, prazos ou políticas
- Não prometer descontos ou condições comerciais não informadas
- Não garantir resultados
- Não afirmar integrações que não estão disponíveis
- Não pedir dados sensíveis sem necessidade
- Não responder fora do escopo da empresa

**4. Quando não souber** (select): Dizer que não sabe e pedir mais contexto / Orientar a falar com a equipe / Responder apenas com o que estiver disponível, sem inventar

**5. Exemplos** (opcionais)
- Exemplo de boa resposta (textarea)
- Exemplo de resposta que deve evitar (textarea)

#### Modo avançado

Um único campo `Instruções avançadas do agente` (textarea livre).

Aviso obrigatório: *"No modo avançado, suas instruções substituem o modo guiado. As regras internas de segurança, conhecimento, ferramentas e limites da plataforma continuam sendo aplicadas."*

O modo avançado substitui o guiado, mas NÃO substitui: regras internas, ferramentas, base de conhecimento, catálogo, pipeline, modelo, segurança.

#### Estrutura do `guided_config` (JSONB)

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

`response_style`, `language_mode` e `reply_delay_seconds` ficam **fora** do `guided_config` — são campos de nível superior em `agent_prompt_settings`.

---

### Configurações → Conhecimento

**Pergunta:** De onde o agente pode tirar informação?

**Escopo:** regras de *uso* das fontes já conectadas. Não conecta/desconecta bases aqui — isso é na aba Ferramentas.

Campos:
- **Responder apenas com base de conhecimento** (`knowledge_only`) — restringe ao conhecimento conectado. Vence instruções do agente.
- **Mostrar fontes nas respostas** (`show_sources`)
- **Quando não encontrar resposta** (select): Dizer que não sabe e pedir contexto / Orientar a falar com a equipe / Responder com conhecimento geral, se permitido

Seção somente leitura **Fontes disponíveis para este agente** — mostra bases conectadas com link `[Gerenciar em Ferramentas]` que leva à aba Ferramentas.

**O que NÃO fica em Conhecimento:** conectar/desconectar bases, ativar catálogo, upload de documentos, criar base.

---

### Ferramentas (aba principal)

**Pergunta:** Quais capacidades operacionais este agente pode usar?

Cada ferramenta tem estados claros: Disponível / Ativa / Inativa / Bloqueada pelo plano / Em breve

Ferramentas atuais e futuras:
- Base de Conhecimento (conectar/remover bases)
- Catálogo de Produtos
- HTTP Tools (futuro)
- Webhooks (futuro)
- Integrações externas (futuro)

Cada ferramenta ativa deve ter botões `[Configurar]` e `[Desativar]`.

**Regra importante:** ferramenta liberada ≠ ferramenta ativa. O usuário deve ativar explicitamente.

---

### Configurações → Modelo

**Pergunta:** Qual modelo de IA executa este agente?

**Estrutura:**
```
Modelo de IA
Contexto do agente
Avançado (subaba)
```

#### Seleção de modelo

- Busca por nome
- Filtro por provedor (Todos / OpenAI / Anthropic / Google / ...)
- Filtro por capacidade (Texto / Imagem / Raciocínio / Alta velocidade / ...)
- Cards com: nome, provedor, descrição curta, capacidades reais (ícones), velocidade, custo relativo, disponível no plano atual

Capacidades possíveis nos cards: Texto / Imagem / Áudio / Raciocínio / Contexto longo / Baixo custo / Alta velocidade / Alta qualidade.

**Os ícones devem refletir capacidades reais configuradas no backend, não marketing.**

#### Contexto do agente (Tiers)

**Nome UI:** Contexto do agente

**Descrição:** *"Define quanto conteúdo o agente consegue considerar antes de responder, incluindo histórico da conversa, base de conhecimento, catálogo e instruções. Quanto maior o contexto, maior o consumo de créditos."*

O contexto é um **orçamento compartilhado** — inclui prompt, instruções, histórico, base de conhecimento, catálogo e ferramentas (confirmado pelo comportamento do Chatvolt).

| Tier | Caracteres | Multiplicador de créditos | Plano |
|---|---|---|---|
| **Econômico** | 6.000 | 0,5× | Free |
| **Padrão** | 15.000 | 1× | Free/Growth |
| **Amplo** | 25.000 | 2× | Growth |
| **Avançado** | 35.000 | 4× | Growth |
| **Máximo** | 300.000 | 8× | Scale+ |

Créditos consumidos = crédito base do modelo × multiplicador do tier.

#### Subaba Avançado

- **Temperatura** — Conservador (0.2) / Equilibrado (0.7) / Criativo (1.0) com valor numérico visível
- Futuramente: máximo de tokens, top-p

---

### Configurações → Pipeline

**Pergunta:** Quando este agente criar uma nova conversa, ela entra em qual pipeline?

Campos:
- Pipeline padrão (select)
- Etapa padrão (select — só exibe etapas do pipeline selecionado)

Regras: se pipeline vazio → sem entrada automática. Se pipeline selecionado → etapa obrigatória.

**O que NÃO fica aqui:** criar pipeline, criar etapa, editar prompt da etapa, webhook da etapa.

---

### Configurações → Segurança

**Pergunta:** Quais limites e proteções este agente deve respeitar?

**Status:** planejado para fase futura. A aba pode ficar oculta até a primeira feature real.

Itens previstos:
- Domínios permitidos do widget
- Limite de mensagens por visitante
- Blacklist/whitelist
- Limite de créditos por agente
- Regras anti-abuso
- Políticas de intervenção humana

---

## Status das fases de implementação

### ✅ Agent Behavior UX.1 — Instruções Guiadas vs Avançadas
**Commit:** `599e703`

- Modo Guiado com formulário estruturado (papel, objetivo, postura, iniciativa, regras, exemplos)
- Campos `custom_should_do` e `custom_should_not_do` para regras livres
- Modo Avançado com textarea livre
- Fallback: sem instrução configurada → bloco omitido do LLM

---

### ✅ Agent Config UX.2 — Consolidação de Comportamento e Conhecimento
**Commit:** `483bdee`

- Aba Comportamento consolidada: estilo de resposta, idioma, modo guiado/avançado
- Aba Conhecimento separada: `knowledge_only`, `show_sources`, link para ferramentas
- Separação clara das responsabilidades de cada aba
- Documentação: `docs/agents/agent-configuration-architecture.md`

---

### ✅ Agent Model UX.1 — Seleção de Modelo + Context Tiers
**Commit:** `622dcd2` | **Tag:** `Agent-Model-UX.1`

- Seleção de modelo com busca por nome + filtro por provedor e capacidade
- Context Tiers: Econômico / Padrão / Amplo / Avançado / Máximo
- Multiplicadores de crédito por tier visíveis na UI
- Tiers maiores bloqueados por plano
- Documentação: `docs/agents/model-and-context-settings.md`

---

### ✅ AI Reply UX.1 — Debounced Auto Reply
**Commit:** `151101a` | **Tag:** `AI-Reply-UX.1`

- Campo `reply_delay_seconds` em `agent_prompt_settings` (valores: 0, 3, 5, 8, 15)
- Novos agentes: default 5s. Existentes: 0 (preserva comportamento)
- Migration `059_agent_reply_delay_seconds.py`
- UI em Comportamento → Tempo de resposta (grid com 5 opções, "5s Recomendado")
- `auto_reply_scheduler.py`: thread daemon com validação por `trigger_message_id` no wakeup
- Aplicado em: Web Widget, WhatsApp inbound, Inbox. Não aplicado em: Playground
- Créditos consumidos apenas quando resposta gerada — jobs no-op não consomem
- 17 novos testes. 1948 passed, 2 skipped
- Documentação: `docs/agents/reply-delay-and-message-debounce.md`

---

### ✅ Agent Config UX.3 — Aba Geral bem acabada
**Commit:** `b5cce47` | **Tag:** `Agent-Config-UX.3`

- ID do agente com botão "Copiar ID" (feedback visual por 2s)
- `updated_at` ao lado de `created_at` (somente leitura)
- Status editável dentro da aba Geral (toggle Ativar/Desativar)
- Área de perigo: Arquivar (preserva histórico) + Excluir permanentemente (confirmação digitando o nome)
- Backend: `DELETE /agents/{id}/permanent` com verificação de dependências

---

### ✅ Agent Behavior UX.3 — Templates de Agente
**Commit:** `43acd1a` | **Tag:** `Agent-Behavior-UX.3`

- Galeria de 7 templates no wizard de criação: Suporte ao Cliente / Vendas e Qualificação / FAQ / Onboarding / Cobrança e Follow-up / Assistente Interno / Criar do zero
- Cada template pré-preenche `guided_config` completo
- Wizard simplificado de 6 para 5 steps (template → identidade → conhecimento → modelo → revisão)
- Backend `AgentCreate` agora aceita `instructions_mode` e `guided_config`
- Templates aplicados uma vez na criação — sem vínculo permanente

---

### ✅ Model UX.2 — Temperatura com preset + valor numérico
**Commit:** `6f8d7f4`

- Substituiu campo de texto por 3 cards visuais: Conservador (0.2) / Equilibrado (0.7) / Criativo (1.0)
- Valor numérico visível em badge `font-mono` em cada card
- Texto explicativo: "Valores baixos deixam o agente mais consistente. Valores altos deixam as respostas mais criativas, mas menos previsíveis."

---

### ✅ AI Reply UX.2 — Typing Indicator no Widget
**Commit:** `953e5a1`

- Indicador de "digitando" com três pontos animados (bounce) durante debounce e geração
- Keyframes `nb-typing-bounce` injetados via `<style>` no widget (inline styles, sem Tailwind)
- Substituiu spinner anterior

---

### ✅ Knowledge UX.1 — Fontes disponíveis e fallback de conhecimento
**Commit:** `bb4e327`

- Campo `knowledge_fallback` (ask_context | direct_to_team | knowledge_general) em `agent_prompt_settings`
- Migration `060_agent_knowledge_fallback.py`
- Aba Conhecimento agora lista bases conectadas com link para Ferramentas
- Seção "Quando não encontrar resposta" com 3 cards de seleção
- Blocos de instrução injetados no system prompt para `direct_to_team` e `knowledge_general`

---

### ⬜ Agent Behavior UX.2 — Refinamentos do Comportamento

**O que ainda falta vs o que está implementado:**
- ✅ Modo guiado com seções estruturadas
- ✅ `custom_should_do` e `custom_should_not_do`
- ✅ Estilo de resposta, idioma em Comportamento
- ✅ Tempo de resposta (reply_delay_seconds)
- ✅ Campo "Quando não souber" com UI própria (seção 4 do modo guiado)
- ⬜ Revisar copy de cada campo para explicar melhor o que faz

---

### ⬜ Configurações → Segurança (primeira feature)

**Objetivo:** Implementar a primeira feature real de segurança por agente — provavelmente domínios permitidos do widget ou limite de mensagens por visitante.

---

## Ordem de prioridade recomendada

| # | Fase | Status |
|---|---|---|
| 1 | AI Reply UX.1 | ✅ `AI-Reply-UX.1` |
| 2 | Agent Config UX.3 — Geral bem acabada | ✅ `Agent-Config-UX.3` |
| 3 | Agent Behavior UX.3 — Templates | ✅ `Agent-Behavior-UX.3` |
| 4 | Agent Behavior UX.2 — Refinamentos copy | ⬜ Baixa prioridade |
| 5 | Model UX.2 — Temperatura com preset | ✅ `6f8d7f4` |
| 6 | AI Reply UX.2 — Typing Indicator | ✅ `953e5a1` |
| 7 | Knowledge UX.1 — Fontes + fallback | ✅ `bb4e327` |
| 8 | Segurança — primeira feature | ⬜ Futuro |

---

## Referências de documentação

- `docs/agents/agent-configuration-architecture.md` — estrutura atual das abas e campos
- `docs/agents/guided-vs-advanced-instructions.md` — modo guiado vs avançado
- `docs/agents/model-and-context-settings.md` — modelo e tiers de contexto
- `docs/agents/reply-delay-and-message-debounce.md` — debounce de resposta
