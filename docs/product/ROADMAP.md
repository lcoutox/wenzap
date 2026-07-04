# Roadmap — Nexbrain

Este documento é a **fonte de verdade** para novas funcionalidades. Antes de implementar qualquer feature, ela deve estar registrada aqui com status e contexto suficiente para guiar o desenvolvimento.

---

## Como usar este documento

- **Novo item:** adicione na seção correta com status `⬜ Planejado` antes de implementar.
- **Em andamento:** mude para `🔵 Em progresso` ao iniciar.
- **Concluído:** mude para `✅ Feito` com commit/tag de referência.
- **Descartado:** mude para `🚫 Descartado` com motivo.
- **Postergado:** mude para `⏸ Adiado` com motivo.

Cada item deve ter: o que é, por que existe, o que está fora do escopo, e critério de "feito".

---

## Status atual do produto

O Nexbrain está na fase de MVP avançado. As fundações técnicas (multi-tenant, auth, billing, agentes, knowledge base, widget, inbox, pipeline, contatos) estão implementadas. O foco atual é polimento das configurações de agentes e preparação para os primeiros clientes reais.

---

## Módulos e status

### 1. Workspace e Usuários

| Item | Status | Ref |
|---|---|---|
| Workspace multi-tenant + autenticação | ✅ Feito | Phase 1 |
| Convite de membros e RBAC | ✅ Feito | Phase 1 |
| Planos e limites de uso | ✅ Feito | Plans.1–5 |
| Verificação de e-mail | ✅ Feito | Auth.6 |
| Upgrade de plano (self-serve) | ⬜ Planejado | — |
| Configurações avançadas do workspace (logo, timezone) | ⬜ Planejado | — |

---

### 2. Agentes

#### 2.1 Criação e configuração

| Item | Status | Ref |
|---|---|---|
| Criação de agente com wizard | ✅ Feito | Phase 2 |
| Galeria de templates no wizard | ✅ Feito | `43acd1a` |
| Aba Geral (ID, status, área de perigo) | ✅ Feito | `b5cce47` |
| Aba Comportamento — modo guiado e avançado | ✅ Feito | `599e703` |
| Aba Comportamento — estilo, idioma, tempo de resposta | ✅ Feito | `483bdee` + `151101a` |
| Aba Conhecimento — knowledge_only, show_sources, fallback | ✅ Feito | `bb4e327` |
| Aba Conhecimento — lista de fontes conectadas | ✅ Feito | `bb4e327` |
| Aba Modelo — seleção de modelo + context tiers | ✅ Feito | `622dcd2` |
| Aba Modelo — temperatura com presets visuais | ✅ Feito | `6f8d7f4` |
| Aba Pipeline — pipeline e etapa padrão | ✅ Feito | Pipeline.1 |
| Aba Segurança — domínios permitidos do widget | ⬜ Planejado | — |
| Aba Segurança — limite de mensagens por visitante | ⬜ Planejado | — |

#### 2.2 Playground

| Item | Status | Ref |
|---|---|---|
| Chat de teste (playground) | ✅ Feito | Phase 3 |
| Sessões persistentes no playground | ✅ Feito | Phase 3.1 |
| Guardrails (anti-injection, rate limit) | ✅ Feito | Phase 3.2 |

#### 2.3 Resposta automática

| Item | Status | Ref |
|---|---|---|
| Auto-reply com debounce configurável | ✅ Feito | `151101a` |
| Typing indicator no widget | ✅ Feito | `953e5a1` |
| Auto-reply no WhatsApp | ✅ Feito | `151101a` |

---

### 3. Base de Conhecimento

| Item | Status | Ref |
|---|---|---|
| Criação de base de conhecimento | ✅ Feito | Phase 4.1 |
| Upload de arquivos + embeddings + RAG | ✅ Feito | Phase 4.1 |
| Múltiplas bases por agente | ✅ Feito | — |
| Catálogo de produtos | ✅ Feito | — |
| Fonte via URL (scraping) | ⬜ Planejado | — |
| Fonte via Q&A estruturado | ⬜ Planejado | — |
| Atualização automática de fontes | ⬜ Planejado | — |
| Revisão e curadoria de chunks | ⬜ Planejado | — |

---

### 4. Canais

| Item | Status | Ref |
|---|---|---|
| Widget de site | ✅ Feito | Phase 5.4 |
| WhatsApp (inbound + auto-reply) | ✅ Feito | — |
| Instagram | ⬜ Planejado | — |
| Telegram | ⬜ Planejado | — |
| E-mail | ⬜ Planejado | — |
| API pública (canal programático) | ⬜ Planejado | — |

---

### 5. Inbox e Conversas

| Item | Status | Ref |
|---|---|---|
| Inbox central com lista de conversas | ✅ Feito | Phase 5 |
| Envio de mensagens como humano | ✅ Feito | — |
| Resposta automática pelo agente | ✅ Feito | — |
| Assumir conversa (human handoff) | ✅ Feito | — |
| Filtros e busca no inbox | ⬜ Planejado | — |
| Atribuição de conversa a operador | ⬜ Planejado | — |
| Tags em conversas | ⬜ Planejado | — |
| Notas internas em conversas | ⬜ Planejado | — |
| Resumo automático da conversa (AI) | ⬜ Planejado | — |

---

### 6. Contatos

| Item | Status | Ref |
|---|---|---|
| Base de contatos | ✅ Feito | Clientes.1 |
| Normalização de telefone (E.164) | ✅ Feito | Clientes.1.1 |
| Importação de contatos (CSV) | ⬜ Planejado | — |
| Campos customizados por contato | ⬜ Planejado | — |
| Histórico de conversas por contato | ⬜ Planejado | — |
| Score/qualificação de contato | ⬜ Planejado | — |

---

### 7. Pipeline

| Item | Status | Ref |
|---|---|---|
| Pipeline com etapas e cards | ✅ Feito | Pipeline.1 |
| Enviar conversa para pipeline (inbox) | ✅ Feito | `73c3651` |
| Extra prompt por etapa | ✅ Feito | — |
| Múltiplos pipelines por workspace | ✅ Feito | — |
| Automações por etapa (mover, notificar) | ⬜ Planejado | — |
| Templates de pipeline | ⬜ Planejado | — |
| Métricas por etapa (tempo médio, conversão) | ⬜ Planejado | — |

---

### 8. Ferramentas e Actions

| Item | Status | Ref |
|---|---|---|
| Ativação de base de conhecimento por agente | ✅ Feito | — |
| Ativação de catálogo por agente | ✅ Feito | — |
| HTTP Tool (agente chama webhook externo) | ⬜ Planejado | — |
| Criação de card no pipeline (action) | ⬜ Planejado | — |
| Criação de contato (action) | ⬜ Planejado | — |
| Envio de e-mail (action) | ⬜ Planejado | — |
| Transferência para humano (action estruturada) | ⬜ Planejado | — |

---

### 9. Automações

| Item | Status | Ref |
|---|---|---|
| Regras de automação (trigger → action) | ⬜ Planejado | — |
| Automação por tag de conversa | ⬜ Planejado | — |
| Automação por etapa de pipeline | ⬜ Planejado | — |
| Agendamento de mensagem | ⬜ Planejado | — |

---

### 10. Integrações

| Item | Status | Ref |
|---|---|---|
| Arquitetura de integrações modulares | ⬜ Planejado | — |
| CRM externo (ex: HubSpot) | ⬜ Planejado | — |
| Calendário (ex: Google Calendar) | ⬜ Planejado | — |
| E-commerce (ex: Shopify) | ⬜ Planejado | — |
| Zapier / Make (via webhook) | ⬜ Planejado | — |

---

### 11. Analytics

| Item | Status | Ref |
|---|---|---|
| Uso de créditos por workspace | ✅ Feito | Plans.3 |
| Dashboard de conversas e mensagens | ⬜ Planejado | — |
| Performance por agente | ⬜ Planejado | — |
| Taxa de handoff humano | ⬜ Planejado | — |
| Análise de base de conhecimento (queries sem resposta) | ⬜ Planejado | — |

---

### 12. Billing

| Item | Status | Ref |
|---|---|---|
| Planos Free e Growth | ✅ Feito | Plans.1–5 |
| Feature gates por plano | ✅ Feito | Plans.4 |
| Prompts de upgrade na UI | ✅ Feito | Plans.2 |
| Cobrança real (Stripe) | ⬜ Planejado | — |
| Portal de faturamento (self-serve) | ⬜ Planejado | — |
| Plano Scale | ⬜ Planejado | — |

---

### 13. API Pública e Developer Tools

| Item | Status | Ref |
|---|---|---|
| API REST autenticada | ✅ Feito | (interna) |
| API pública com API keys | ⬜ Planejado | — |
| Webhooks de saída | ⬜ Planejado | — |
| Documentação pública (OpenAPI/Swagger) | ⬜ Planejado | — |
| SDK JavaScript | ⬜ Planejado | — |

---

## Próximos itens a implementar (backlog ativo)

Esta seção lista o que deve ser feito nos próximos ciclos, em ordem de prioridade. Atualizar sempre que um item for iniciado ou concluído.

| Prioridade | Item | Módulo | Notas |
|---|---|---|---|
| 1 | Fonte via URL (scraping) | Base de Conhecimento | Reduz fricção no onboarding |
| 2 | Filtros e busca no inbox | Inbox | Necessário assim que volume crescer |
| 3 | Cobrança real (Stripe) | Billing | Pré-requisito para monetização |
| 4 | HTTP Tool (agente chama webhook) | Ferramentas | Abre casos de uso operacionais |
| 5 | Resumo automático de conversa | Inbox | Alto valor, baixo esforço |
| 6 | Atribuição de conversa a operador | Inbox | Necessário para equipes |
| 7 | Instagram como canal | Canais | Alta demanda esperada |
| 8 | Aba Segurança — domínios do widget | Agentes | Proteção básica para clientes em produção |

---

## Itens descartados ou adiados

| Item | Status | Motivo |
|---|---|---|
| Aba Segurança — implementação completa | ⏸ Adiado | Baixa urgência no MVP; adicionar quando houver casos reais de abuso |
| Agent Behavior UX.2 — revisão de copy | ⏸ Adiado | Baixa prioridade; UX funciona bem |

---

## Referências

- `docs/product/PRODUCT_VISION.md` — visão e posicionamento
- `docs/product/PRODUCT_MODULES.md` — detalhamento de módulos
- `docs/agents/agent-module-refactor-prd.md` — PRD detalhado do módulo de agentes
- `docs/architecture/ARCHITECTURE_PRINCIPLES.md` — princípios de arquitetura
- `docs/billing/` — feature gates e planos
