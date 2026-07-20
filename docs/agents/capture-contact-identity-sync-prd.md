# PRD — Sincronizar dado capturado com os campos estruturados do Contato

**Status: ✅ Implementado (backend + frontend, 2026-07-20).** Achado ao vivo testando o agente Léo (widget da
landing) em 2026-07-20: o lead "André Veículos" teve nome, negócio, WhatsApp, dor e volume de
leads capturados pela tool "Capturar dados do cliente" — tudo salvo certinho em `ContactVariable`
(aba Variáveis do contato) — mas a lista de Contatos continuou mostrando ele como **"Visitante"**,
sem nome nem telefone nos campos estruturados. Achado registrado (fora deste repo) em
`negocios/wenzap/decisoes.md` no NexBrain — sessão de review do widget, 2026-07-20.

## Contexto

Essa PRD nasce de uma sessão de review ao vivo do agente de qualificação (Léo, widget da landing).
Nessa mesma sessão, dois outros achados já foram **implementados** (não fazem parte do escopo
desta PRD, citados aqui só pra contexto de quem ler depois):

- ✅ **Tom conversacional natural como baseline do core do prompt** — antes só existia pra
  WhatsApp (`_WHATSAPP_CHANNEL_RULES`); virou `_CORE_CONVERSATION_STYLE`, sempre injetado,
  independente de canal. `app/services/agent_context_builder.py`.
- ✅ **Indicador de "digitando" honesto no widget** — antes aparecia e sumia antes da resposta
  existir de fato (orçamento de poll menor que `reply_delay_seconds`). Agora o widget conhece o
  delay real do agente (`reply_delay_seconds` exposto em `PublicWidgetConfigOut`), só mostra
  "digitando" depois que ele passa, e o campo de mensagem não trava mais durante a espera (permite
  mensagem picada de verdade). `app/services/public_widget_service.py`,
  `apps/web/src/components/widget/WidgetEmbed.tsx`.

Fora de escopo de código, mas pendente como ação de configuração (não PRD): ajustar o prompt do
Léo pra evitar chamar a captura de dado duas vezes na mesma conversa, e reduzir o tom de "log de
sistema" da mensagem de confirmação final.

## Problema

`execute_capture_contact_data_tool` (`app/services/agent_tool_service.py:776-809`) só grava em
`ContactVariable` via `upsert_contact_variable` — nunca toca em `Contact.name`, `Contact.phone` ou
`Contact.email`. Como o Web Widget cria o contato com `name="Visitante"` por padrão quando não há
formulário de pré-captura (`public_widget_service.py:229`), e nada depois atualiza isso, um lead
totalmente qualificado pelo agente — nome, negócio, WhatsApp, tudo capturado — continua aparecendo
como "Visitante" na tela de Contatos e na lista do Inbox. A informação existe (aba Variáveis), mas
não onde o operador olha primeiro.

Não é uma decisão de produto — o PRD original que criou essa tool
(`docs/agents/agent-tools-batch-2-prd.md`) não menciona sincronizar com os campos estruturados em
nenhum momento. É lacuna, não escolha.

## Objetivo

Quando o operador configurar um campo de captura que representa a identidade do contato (nome,
telefone, e-mail), o agente — além de continuar salvando a variável, como já faz — também atualiza
o campo estruturado correspondente. O contato deixa de ficar "Visitante" assim que a IA descobre
quem é.

## Desenho

### Por que não inferir pelo nome da chave

A chave de cada campo capturado é texto livre escolhido pelo operador (`key: str` com regex
`^[a-zA-Z_][a-zA-Z0-9_]*$`, sem vocabulário fixo — `ContactDataField`,
`app/schemas/agent_tool.py:108-115`). Tentar adivinhar que `numero_whatsapp` "é" o telefone por
heurística de nome é frágil: quebra silenciosamente se o próximo operador chamar o campo de
`whatsapp_cliente`, `fone`, `contato_wpp`, etc. — e falha calada é pior que não sincronizar nada,
porque o operador nem sabe que devia esperar a sincronização. Mapeamento **explícito**, escolhido
pelo operador no momento em que configura o campo, é a única forma de saber a semântica com
certeza.

### Mapeamento explícito por campo

Novo campo opcional em `ContactDataField`:

```python
class ContactDataField(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    description: str = Field(default="", max_length=300)
    maps_to: Literal["name", "phone", "email"] | None = None
```

Validação em `CaptureContactDataToolConfig` (`model_validator`): no máximo um campo por valor de
`maps_to` — não faz sentido dois campos mapeados pra "nome" na mesma tool. Continua até 5 campos
no total (limite atual, inalterado).

### UI (`ContactFieldsEditor`, `ConfigFerramentas.tsx:2325-2386`)

Cada linha de campo ganha um terceiro controle (hoje só tem chave + descrição): um seletor
"Nenhum / Nome do contato / Telefone / E-mail", default "Nenhum" (comportamento atual, sem
mudança pra quem não usar). Placeholder/hint explicando: "Se marcado, esse dado também atualiza a
ficha do contato — não só a variável."

### Execução (`execute_capture_contact_data_tool`)

Hoje o executor recebe só `captured_fields: dict[str, str]` (o que o modelo efetivamente
preencheu naquele turno) — não tem acesso à config da tool pra saber qual chave mapeia pra quê.
Precisa passar o mapeamento adiante, no mesmo padrão já usado por `pipeline_action`/
`assign_operator`, que já recebem pedaços da config no momento do dispatch
(`_build_tool_dispatch`, `agent_tool_service.py:370-373`):

```python
elif tool.tool_type == "capture_contact_data":
    config = tool.config
    identity_map = {
        f["key"]: f["maps_to"] for f in config.get("fields", []) if f.get("maps_to")
    }
    dispatch[tool.name] = _make_capture_contact_data_executor(
        db=db, workspace_id=workspace_id, conversation=conversation,
        identity_map=identity_map,
    )
```

Dentro de `execute_capture_contact_data_tool`, depois do loop de `upsert_contact_variable` (que
não muda), para cada `key` capturada presente em `identity_map`:

```python
from app.services.contact_service import update_contact  # noqa: PLC0415
from app.schemas.contact import ContactUpdate  # noqa: PLC0415

field_name = identity_map[key]  # "name" | "phone" | "email"
try:
    update_contact(
        db, workspace_id, conversation.contact_id,
        ContactUpdate(**{field_name: value}),
    )
except HTTPException:
    # Conflito de dedup (telefone/e-mail já pertence a outro contato do
    # workspace) — a variável já foi salva acima; não interrompe a
    # conversa, só não sincroniza esse campo específico.
    pass
```

Reaproveita `update_contact` (`contact_service.py:219-250`) de propósito — já faz normalização de
telefone/e-mail e dedup contra outros contatos do workspace. O único cuidado é que `update_contact`
levanta `HTTPException(409)` em conflito de dedup; como o executor roda no meio do loop de
tool-calling (não numa request HTTP), isso precisa ser capturado ali mesmo — deixar vazar
quebraria o turno inteiro por causa de um campo secundário, quando o dado principal (a variável)
já foi salvo com sucesso.

Mensagem de retorno ajustada pra refletir os dois efeitos quando aplicável, ex.: `"Dados salvos no
contato: nome, negocio, numero_whatsapp, dor_relatada, volume_leads. Nome e telefone do contato
atualizados."` — só quando pelo menos um campo tinha `maps_to`.

### Gate

Sem gate de plano — mesma categoria da tool em si (já sem gate).

## Migrations necessárias

Nenhuma. `AgentTool.config` é JSONB — `maps_to` ausente em configs já existentes (como o do Léo)
é lido como `None` automaticamente, sem precisar de backfill nem default especial.

## Critério de "pronto"

Um agente com a tool "Capturar dados do cliente" configurada com um campo marcado como "Nome do
contato" e outro como "Telefone": ao capturar esses dados numa conversa real, o contato passa a
aparecer com nome e telefone reais na tela de Contatos e no Inbox — não mais "Visitante" — mesma
sessão em que a variável correspondente também aparece na aba Variáveis (comportamento atual,
preservado).

## Ação manual pendente (não faz parte do código desta PRD)

O contato do lead "André Veículos" (capturado antes desta correção existir) continua como
"Visitante" no banco — vale corrigir manualmente (`UPDATE contacts SET name=..., phone=...`) assim
que a feature entrar no ar, ou aproveitar e rodar antes como validação manual do fix.

## Referências

- `app/services/agent_tool_service.py:776-809` — `execute_capture_contact_data_tool`; `:370-373` —
  dispatch onde `pipeline_action`/`assign_operator` já mostravam o padrão de repassar pedaços da
  config pro executor.
- `app/schemas/agent_tool.py:108-129` — `ContactDataField`/`CaptureContactDataToolConfig`.
- `app/services/contact_service.py:219-250` — `update_contact` (reaproveitado sem alteração).
- `apps/web/src/components/agents/workspace/tabs/ConfigFerramentas.tsx:2325-2386` —
  `ContactFieldsEditor`, novo seletor `maps_to`.
- `docs/agents/agent-tools-batch-2-prd.md` — PRD original da tool, não cobria este caso.

## Estado da implementação

**Backend** — completo. Uma diferença do desenho original: a duplicidade de `maps_to` (dois campos
mapeados pro mesmo dado do contato) acabou implementada como checagem manual em
`agent_tool_service.py` (HTTP 400), **não** como `model_validator` no schema Pydantic — encontrei
que a checagem irmã já existente (chaves duplicadas) segue esse padrão no projeto (validação de
regra de negócio na camada de serviço, não no schema), e um `model_validator` teria devolvido 422
em vez de 400, inconsistente com o resto do arquivo. Sem migration (config já é JSONB). Testado:
4 casos novos em `tests/test_agent_tools_batch2.py` (rejeita `maps_to` duplicado, aceita
mapeamento, sincroniza nome+telefone preservando as variáveis, e conflito de dedup não derruba a
tool call) — suíte inteira do arquivo (42 casos) + `test_agent_tools.py` +
`test_agent_context_builder.py` rodando limpa (147 casos).

**Frontend** — completo. `ContactFieldsEditor` ganhou um `<select>` por campo ("Só salvar como
variável" / "Também atualizar nome/telefone/e-mail"), desabilitando opções já usadas por outro
campo da mesma tool. `handleSave` (`CaptureContactDataConfigModal`) agora propaga `maps_to` no
payload (antes descartava, só reconstruía `{key, description}`) e valida duplicidade no cliente
antes de salvar. `tsc --noEmit` limpo. Não testado clicando na UI real (sem ferramenta de browser
disponível nesta sessão) — só verificado via typecheck e pela suíte de testes de backend.

**Pendente, fora do código:** rodar o backfill manual do contato "André Veículos" (ver seção
acima) — ainda não feito.
