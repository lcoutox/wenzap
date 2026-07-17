# PRD — Melhorias de UX no HTTP Tool (config estruturada + validação)

**Status: ✅ Implementado (2026-07-17)** — melhoria incremental sobre a Fase 4 do
`docs/agents/agent-tool-calling-prd.md`. Sem migration (tudo no `config JSONB` já existente),
100% retrocompatível com tools HTTP já criadas. 2091 testes de backend passando (17 novos),
build de frontend limpo. Ver "Estado da implementação" no fim.

## Contexto

O Lucas comparou o formulário de configuração do HTTP Tool do Chatvolt (concorrente direto) com
o do Wenzap e achou o deles mais intuitivo. Print anexado do modal deles mostra:

- Botão de **templates** ("Modelos de Ferramentas HTTP") e um de **preenchimento por IA**
  (marcado "Premium").
- Campo **Nome** e **Descrição | Gatilho** (com tooltip explicando que a descrição orienta o
  modelo — igual ao que já fazemos).
- **URL**, **Método**.
- Seções **Path**, **Query** e **Headers**, cada uma com um botão "+ Add ..." que adiciona uma
  linha estruturada (nome, e presumivelmente descrição) — não texto livre.
- Botão verde **"Validar Configuração"** no rodapé — testa a chamada antes de salvar.

Comparado ao nosso `HttpToolFormModal` atual (`ConfigFerramentas.tsx`), os gaps reais são:

1. **Path variables** só existem implicitamente — o operador digita `{cep}` dentro do texto da
   URL e temos que confiar que ele lembra a sintaxe. Não dá pra escrever uma descrição melhor
   que a genérica "Value for 'cep', used in the request URL." que o backend gera sozinho.
2. **Query params não têm nenhuma estrutura** — hoje o modelo recebe um `query_params: object`
   genérico e sem documentação nenhuma sobre quais chaves existem. O operador não consegue dizer
   ao modelo "esse endpoint aceita `formato` (json/xml)".
3. **Headers são um textarea de JSON cru** — um dos motivos mais comuns de erro de usuário
   (JSON malformado), quando é só uma lista de pares chave/valor (token de API, Content-Type).
4. **Não existe validação antes de salvar.** Hoje o único jeito de saber se a config funciona é
   salvar, ativar o agente, mandar uma mensagem que dispare a tool e torcer. Qualquer engano
   (URL errada, header faltando) só aparece depois, em produção.

## Objetivo

Fechar os 4 gaps acima — sem tocar na tabela `agent_tools` (é tudo dentro do `config` JSONB já
existente) e **mantendo compatibilidade total com toda tool HTTP já criada** (nenhuma migration).

## Não-objetivos (fora de escopo desta rodada)

- **Preenchimento automático por IA** (o botão "Premium" do Chatvolt). Exige uma chamada de LLM
  pra transformar linguagem natural em config estruturada — custo e complexidade reais, sem sinal
  de demanda ainda. Backlog explícito.
- **Galeria de templates completa.** Incluímos 2 templates prontos focados no mercado BR (ViaCEP,
  ReceitaWS/CNPJ) como prova de conceito de baixo custo — uma galeria maior/editável é
  otimização futura.
- **Estruturar o Body** (POST/PUT/PATCH) do mesmo jeito que Query. O print do concorrente não
  mostra essa seção (cortada ou inexistente pro método GET selecionado) e o Body de uma tool HTTP
  tende a ser mais heterogêneo/aninhado que query params simples — mesmo padrão dá pra aplicar
  depois se virar dor real.

## Design

### 1. Path variables com descrição customizável

Continuam **inferidas da URL** via regex (`{nome}`) — não vira uma lista separada que pode
dessincronizar do texto da URL, que é a fonte real da verdade. O que muda: novo campo opcional em
`HttpToolConfig`, `path_param_descriptions: dict[str, str]` (nome → descrição), populado pela UI
conforme o operador digita a URL (cada `{var}` detectado vira uma linha com um campo de descrição
editável). `build_tool_schema` usa essa descrição quando existe; cai no texto genérico atual
quando não (tools já existentes, sem esse campo, continuam funcionando idênticas a hoje).

### 2. Query params estruturados

Novo campo opcional em `HttpToolConfig`: `query_params: list[HttpToolParam]`, onde
`HttpToolParam = {name, description, required}`. Quando a lista não está vazia,
`build_tool_schema` gera um `input_schema.properties.query_params` com propriedades nomeadas e
descritas (schema aninhado, Anthropic tool-calling suporta objeto com `properties`/`required`
aninhados) em vez do objeto genérico de hoje. **Contrato de execução não muda** —
`execute_http_tool` já lê `input_.get("query_params") or {}` como um dict solto; a estrutura só
melhora o que o modelo *vê*, não como a chamada é montada. Tools sem `query_params` configurado
continuam com o comportamento livre de hoje (schema genérico) — zero regressão.

### 3. Headers como editor chave/valor

Puramente frontend — o `config.headers` já é (e continua sendo) `dict[str, str]` no backend, sem
mudança de schema. Só troca o textarea de JSON por linhas "+ Add Header" (nome + valor), erro de
JSON malformado deixa de existir por construção.

### 4. "Validar Configuração" — testar antes de salvar

Novo endpoint `POST /agents/{agent_id}/tools/http/test`: recebe um `HttpToolConfig` (rascunho,
**ainda não precisa existir como `AgentTool` salvo**) + `sample_input` (valores de teste que o
operador preenche nas linhas de Path/Query enquanto configura), executa via
`execute_http_tool()` — mesma função já testada exaustivamente (SSRF-safe, templating de URL) —
e devolve `{ok, status_code, body, error}` em vez de deixar uma exceção estourar. Mesmo gate de
plano/role do `create` (`_check_http_tools_feature` + `_WRITE_ROLES`), já que exercita a mesma
capacidade (chamada HTTP saindo da nossa infra).

### 5. Templates prontos (baixo custo, alto valor pro mercado BR)

Botão "Usar um modelo" no formulário, puramente frontend (array hardcoded, sem tabela nem
endpoint novo): **ViaCEP** (`GET https://viacep.com.br/ws/{cep}/json/`) e **ReceitaWS/CNPJ**
(`GET https://receitaws.com.br/v1/cnpj/{cnpj}`) — preenche nome/descrição/URL/path descriptions,
o operador ajusta e salva. Dá pra crescer a lista depois sem tocar em backend.

## Migrations necessárias

**Nenhuma.** Tudo cabe no `config JSONB` já existente; campos novos são opcionais com default
vazio, então tools HTTP já salvas continuam funcionando sem qualquer alteração de dado.

## Critério de "pronto"

O operador consegue configurar uma tool HTTP inteira (path/query/headers) via UI estruturada, sem
escrever JSON à mão; consegue clicar "Validar Configuração" e ver o resultado real da chamada
antes de salvar; tools HTTP criadas antes desta mudança continuam funcionando sem qualquer ajuste
manual.

## Referências

- `docs/agents/agent-tool-calling-prd.md` — Fase 4, HTTP Tool original.
- Print do Chatvolt (`app.chatvolt.ai/.../tools`), 2026-07-17 — referência de UX comparada.
- `app/services/agent_tool_service.py` — `execute_http_tool`/`build_tool_schema`, reaproveitados
  sem mudança de contrato de execução.

## Estado da implementação (2026-07-17)

**Backend:**
- `app/schemas/agent_tool.py` — `HttpToolParam` (name/description/required), `HttpToolConfig`
  ganhou `path_param_descriptions: dict[str,str]` e `query_params: list[HttpToolParam]`, ambos
  com default vazio; `HttpToolTestRequest`/`HttpToolTestResponse` novos.
- `app/services/agent_tool_service.py` — `build_tool_schema` usa a descrição customizada de path
  var quando existe (cai no texto genérico quando não); gera schema aninhado nomeado pra
  `query_params` quando a lista estruturada não está vazia (cai no objeto genérico quando vazia —
  zero regressão pra tools antigas). `validate_http_tool_config()` nova — roda
  `execute_http_tool` contra um config rascunho e devolve `{ok, status_code, body, error}` em vez
  de deixar a exceção estourar (nome deliberadamente sem prefixo `test_` — colidiria com a
  coleta de testes do pytest se importado num arquivo de teste).
- `app/routers/agents.py` — `POST /agents/{id}/tools/http/test`, mesmo gate de role/plano do
  `create`.
- Testes novos em `tests/test_agent_tools.py`: backward-compat sem os campos novos, descrição
  customizada de path var, query params estruturados (schema + execução inalterada), o endpoint
  de validação (sucesso, falha reportada como dado não como exceção, URL privada rejeitada, gate
  de plano), criação via API com `query_params`.

**Frontend (`ConfigFerramentas.tsx`):**
- `HeadersEditor` — linhas chave/valor, substitui o textarea de JSON cru.
- `QueryParamsEditor` — linhas nome/descrição/obrigatório/valor de teste, cada linha adicionável/
  removível.
- Seção **Path** — derivada ao vivo da URL (`{variavel}` via regex), uma linha por variável
  detectada com descrição editável + valor de teste (o nome não é editável — vem da própria URL,
  fonte única da verdade, evita dessincronia).
- Botão **"Validar Configuração"** — monta o config rascunho + os valores de teste preenchidos,
  chama `POST /tools/http/test`, mostra status/corpo ou erro inline, sem precisar salvar antes.
- 2 templates prontos (ViaCEP, ReceitaWS/CNPJ) via botão "Usar um modelo pronto".
- `apps/web/src/lib/api.ts` — `HttpToolParam`, `HttpToolTestResult`,
  `api.agents.httpTools.test()`.

**Verificação:** 2091 testes de backend passando (mesmos 8 pré-existentes sem relação de sempre),
`tsc --noEmit` limpo, `next build` limpo. **Não testado visualmente num navegador** (sem
ferramenta de automação de browser disponível nesta sessão) — recomendo um passe manual antes de
considerar 100% fechado, igual foi feito com o HTTP Tool original.
