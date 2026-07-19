# PRD — Retrieval robusto do Catálogo (2 camadas)

**Status: ✅ Implementado (2026-07-19)** — detalhes de execução (testes, migration, frontend) em
[catalogo-retrieval-robusto.md](../../../nexbrain/negocios/wenzap/catalogo-retrieval-robusto.md)
no NexBrain.

## Contexto

Testando o roteiro da imobiliária fictícia ([teste-imobiliaria.md](../../../nexbrain/negocios/wenzap/teste-imobiliaria.md)
no NexBrain), o agente "esqueceu" um apartamento que tinha acabado de mencionar e inventou que ele
"não estava mais no catálogo" — os scores de relevância da busca híbrida ficaram entre 0,005 e
0,055 (numa escala onde 1.0 seria match perfeito), tão baixos e ruidosos que o item nem veio nos
top-3 daquela vez.

O Lucas sugeriu trocar de banco vetorial (Qdrant) — investigação descartou essa hipótese: pgvector
e Qdrant calculam a mesma distância de cosseno sobre os mesmos embeddings, a matemática não muda.
O problema real está em 3 lugares específicos do motor de busca (detalhados abaixo), nenhum deles
resolvido trocando de banco.

Pedido explícito do Lucas: **não um patch pro caso da imobiliária, uma solução que cubra o
espectro inteiro de cliente** — do pequeno com poucos itens mal descritos até o hard user com
catálogo grande e bem estruturado.

## Desenho: 2 camadas que se adaptam ao tamanho real do catálogo

### Camada 1 — Catálogo pequeno: injeta tudo, sem retrieval

Quando o catálogo ativo (respeitando o escopo de categoria do agente) cabe inteiro dentro de um
orçamento de caracteres, o agente recebe **todos os itens**, sempre — sem ranking, sem risco de
"esquecer" um item. Ainda fica atrás do gate de intenção comercial já existente
(`should_retrieve_catalog`) — só passa a listar tudo em vez de rankear top-K quando decide buscar.

- Orçamento: soma de `len(nome) + len(descrição_curta) + ~80 chars de overhead de formatação` de
  todos os itens ativos no escopo. `_FULL_CATALOG_CHAR_BUDGET = 6000` (~1500 tokens) — cobre
  confortavelmente 15-20 itens típicos, cai pra Camada 2 automaticamente se ultrapassar (seja por
  ter muitos itens ou por ter descrições longas).
- `retrieval_method="full_catalog"` no item retornado (novo valor, os demais ficam iguais).

### Camada 2 — Catálogo grande: retrieval de verdade, mas robusto

Três melhorias no motor, nenhuma delas dependente de trocar de banco vetorial:

1. **Full-text search nativo do Postgres** (`to_tsvector`/`ts_rank`, configuração `portuguese`,
   índice GIN por expressão sobre `searchable_text`) no lugar do `ILIKE` contando termo por termo.
   Mais robusto a variação de escrita, e ganha ranking de relevância de verdade (`ts_rank`) em vez
   de uma contagem crua de termos batidos.
2. **Reciprocal Rank Fusion (RRF)** no lugar da soma ponderada fixa (`0.7×semântico + 0.3×léxico`).
   RRF combina os *rankings* de cada método (`score = Σ 1/(k + rank)`, k=60, padrão da literatura)
   em vez dos scores brutos — não depende de calibrar pesos fixos que quebram com catálogos de
   perfis diferentes (poucos itens vs. muitos, descrição rica vs. pobre).
3. **Threshold de confiança + sinal explícito pro modelo.** Um candidato só entra no resultado
   final se passar em pelo menos um destes dois critérios: similaridade semântica ≥ 0,15, OU teve
   match léxico de verdade (apareceu no full-text search, que só retorna match real, não "quase
   parecido"). Se a busca teve candidatos mas **nenhum** passou nesse crivo, o agente recebe um
   bloco explícito avisando que a busca foi inconclusiva — nunca mais um "top-3 fraco" silencioso
   sendo apresentado como se fosse confiável. Distingue esse caso de "genuinamente não achou nada"
   (aí não teve candidato nenhum, comportamento atual se mantém — sem bloco, sem hedge desnecessário).
4. **Índice HNSW no pgvector** (`vector_cosine_ops`) — hoje a busca semântica é sequential scan
   (nenhum índice ANN existe). Não muda corretude em catálogo pequeno, mas é gargalo real em
   catálogo grande — adicionado já que estamos mexendo nessa área.

## O que NÃO muda

- `retrieve_catalog_items()` mantém a mesma assinatura pública (`list[CatalogRetrievalItem]`) —
  os ~14 call sites em testes existentes continuam funcionando sem alteração. A lógica de
  confiança/hedge fica numa função interna nova (`_retrieve_catalog_items_full`), usada só por
  `retrieve_catalog_context` (o único ponto de entrada real usado em produção).
- `build_embedding_text()`/`build_searchable_text()` — já constroem texto rico (nome, categoria,
  descrição, preço, tags, SKU, atributos), não precisam mudar.
- O gate de intenção comercial (`should_retrieve_catalog`, baseado em palavra-chave) — fora de
  escopo desta PRD.

## Migrations necessárias

Uma migration, só índices (sem mudança de schema/dado, rápida e segura):
- Índice GIN por expressão: `to_tsvector('portuguese', coalesce(searchable_text, ''))`.
- Índice HNSW: `catalog_items.embedding` com `vector_cosine_ops`.

## Critério de "pronto"

Catálogo de 5 itens (como o da imobiliária) nunca mais "esquece" um item já mencionado — o agente
sempre vê o catálogo inteiro. Catálogo grande com descrições fracas ainda encontra o item certo
mais confiavelmente (FTS + RRF + threshold), e quando a busca é genuinamente inconclusiva o
agente sabe disso em vez de inventar.
