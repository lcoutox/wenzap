# Tech Debt

Registro de dívidas técnicas conhecidas. Cada entrada descreve o comportamento atual, o problema e a solução futura sugerida.

---

## TD — Persistir metadados RAG no histórico do Playground

**Status:** aberto  
**Fase de origem:** Phase 4.3 — RAG no Agent Playground  
**Data de registro:** 2026-06-23

### Comportamento atual

O badge "Conhecimento usado · N trechos" aparece apenas no turno atual, logo após o envio de uma mensagem. Ele depende de `lastRunMeta` (state React efêmero em `AgentChat.tsx`). Ao recarregar a página ou trocar de sessão, `loadSession` zera `lastRunMeta=null` e o histórico de mensagens é recarregado do servidor sem metadados de RAG — o badge não reaparece.

### Causa

`PlaygroundMessage` (retornado por `GET /agents/{id}/playground/sessions/{session_id}`) não carrega `rag_used` nem `retrieved_chunks_count`. Essas informações existem em `agent_test_runs` (coluna `rag_used`, `retrieved_chunks_count`), mas o endpoint não faz o join.

### Impacto

Baixo. O RAG funciona corretamente; apenas a indicação visual no histórico é perdida após reload.

### Solução futura

Enriquecer `GET /agents/{id}/playground/sessions/{session_id}` para retornar metadados do `agent_test_run` associado à cada assistant message. Campos candidatos:

- `rag_used`
- `retrieved_chunks_count`
- `credits_used`
- `duration_ms`
- `model`
- metadados de fontes usadas (fase futura, quando houver painel de fontes)

**Backend:** `PlaygroundMessageOut` schema ganha campos opcionais; o endpoint faz LEFT JOIN com `agent_test_runs` via `agent_test_run_id` já presente em `AgentPlaygroundMessage`.

**Frontend:** `PlaygroundMessage` type em `api.ts` ganha `rag_used?: boolean` e `retrieved_chunks_count?: number`; `AgentChat.tsx` exibe o badge no histórico com base nesses campos, sem depender de `lastRunMeta`.

---

## TD — Reprocess de fontes de arquivo não re-extrai do arquivo original

**Status:** aberto  
**Fase de origem:** Phase 4.4 — File Upload para Knowledge Sources  
**Data de registro:** 2026-06-23

### Comportamento atual

`POST /knowledge-bases/{kb_id}/sources/{source_id}/reprocess` (em `knowledge_source_service.py`) usa `content_text` já armazenado na `KnowledgeSource`. Para fontes do tipo `manual_text` e `faq_qa` isso é correto. Para fontes de arquivo (`txt`, `markdown`, `pdf_simple`, `csv_simple`), no entanto, o arquivo original está salvo no storage (campo `storage_key`), mas o reprocess **não** o re-extrai — usa apenas o texto já extraído previamente.

### Impacto

Médio. Se a extração original falhou (`status=failed`) e o usuário quer re-tentar, `reprocess` reaproveita `content_text=None` e a indexação falha novamente com "No content could be extracted". O arquivo original está preservado mas nunca é lido no reprocess atual.

### Solução futura

Em `reprocess_source` (ou numa versão futura do serviço): detectar que a source tem `storage_key` e `status=failed` + `content_text=None`; buscar o arquivo do storage provider; re-extrair com o extractor correspondente ao `source_type`; atualizar `content_text`; re-indexar.

Campos necessários já existem: `storage_key`, `storage_provider`, `source_type`. A factory de extractors e o `get_storage_provider()` estão prontos. O trabalho é conectar os pontos em `reprocess_source`.

---

## TD — Evitar contato órfão em criação de conversa inline

**Status:** aberto  
**Fase de origem:** Phase 5.1 — Conversation Core  
**Data de registro:** 2026-06-23

### Comportamento atual

`create_conversation` com `contact_name` chama `create_contact` (em `contact_service.py`), que executa `db.commit()` antes de a conversa ser criada. Se a criação da conversa falhar após esse ponto (ex.: violação de constraint na tabela `conversations`), o contato será persistido sem nenhuma conversa associada — um contato órfão.

### Impacto

Baixo no MVP, porque ainda não há UI nem canal externo usando esse fluxo em produção. Em uso normal a conversa sempre é criada com sucesso após o contato. O contato órfão não causa erros visíveis, apenas dado desnecessário no banco.

### Solução futura

Refatorar `create_contact` para aceitar um modo transacional onde executa apenas `db.flush()` (sem `db.commit()`), deixando o commit para o caller. Opções:

1. Adicionar parâmetro `commit: bool = True` em `create_contact` — simples mas expõe detalhe transacional.
2. Criar helper interno `_create_contact_in_transaction(db, workspace_id, data) -> Contact` que só faz `flush()`, usado por `create_conversation`; o `create_contact` público continua fazendo `commit()`.
3. Usar `savepoint` para rollback parcial se a conversa falhar — mais robusto mas mais complexo.
