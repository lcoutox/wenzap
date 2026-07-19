"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Globe,
  Hand,
  Info,
  Kanban,
  Loader2,
  Minus,
  Pencil,
  Play,
  Plus,
  Settings2,
  ShoppingBag,
  Sparkles,
  Trash2,
  UserCheck,
  X,
  Zap,
} from "lucide-react";
import CodeMirror from "@uiw/react-codemirror";
import { json as cmJson, jsonParseLinter } from "@codemirror/lang-json";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { linter, lintGutter } from "@codemirror/lint";
import { indentWithTab } from "@codemirror/commands";
import { EditorView, keymap } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { api, ApiError } from "@/lib/api";
import type {
  AgentCatalogScope,
  AgentFollowUpSettings,
  AgentKnowledgeBase,
  AgentTool,
  AgentToolCreateInput,
  AssignOperatorAgentTool,
  CaptureContactDataAgentTool,
  CatalogCategory,
  ContactDataField,
  HttpAgentTool,
  HttpToolConfig,
  HttpToolParam,
  HttpToolTestResult,
  KnowledgeBase,
  MarkResolvedAgentTool,
  Member,
  MemberRole,
  Pipeline,
  PipelineActionAgentTool,
  PipelineStage,
  RequestHumanAgentTool,
} from "@/lib/api";
import { inputCls } from "@/components/agents/workspace/AgentHeader";
import { PlanGateBadge } from "@/components/plan/PlanGateBadge";
import { minPlanLabel, planAllowsFeature } from "@/lib/plan";

// ── Helpers ───────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

// ── Toggle ────────────────────────────────────────────────────────────────────

function Toggle({
  checked,
  disabled,
  onChange,
}: {
  checked: boolean;
  disabled?: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative flex-shrink-0 w-10 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-nb-primary/40 ${
        checked ? "bg-nb-primary" : "bg-nb-border-strong"
      } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
          checked ? "translate-x-4" : "translate-x-0"
        }`}
      />
    </button>
  );
}

// ── Modal wrapper ─────────────────────────────────────────────────────────────

function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className="w-full max-w-lg bg-nb-surface border border-nb-border rounded-2xl shadow-2xl flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border shrink-0">
          <h2 className="text-sm font-semibold text-nb-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

// ── KB Configure Modal ────────────────────────────────────────────────────────

function KbConfigModal({
  open,
  onClose,
  agentId,
  role,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  role: MemberRole | null;
}) {
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [connections, setConnections] = useState<AgentKnowledgeBase[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [actionErrors, setActionErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setLoadError(null);
    Promise.all([api.knowledgeBases.list(), api.agents.knowledgeBases.list(agentId)])
      .then(([allKbs, agentKbs]) => {
        setKbs(allKbs);
        setConnections(agentKbs);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar bases."))
      .finally(() => setLoading(false));
  }, [open, agentId]);

  function getConnection(kbId: string) {
    return connections.find((c) => c.knowledge_base_id === kbId);
  }

  async function handleConnect(kbId: string) {
    setBusy((p) => ({ ...p, [kbId]: true }));
    setActionErrors((p) => ({ ...p, [kbId]: "" }));
    try {
      const conn = await api.agents.knowledgeBases.connect(agentId, kbId);
      setConnections((prev) => {
        const existing = prev.find((c) => c.knowledge_base_id === kbId);
        if (existing) return prev.map((c) => (c.knowledge_base_id === kbId ? conn : c));
        return [...prev, conn];
      });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const refreshed = await api.agents.knowledgeBases.list(agentId).catch(() => null);
        if (refreshed) setConnections(refreshed);
      } else {
        setActionErrors((p) => ({ ...p, [kbId]: e instanceof Error ? e.message : "Erro ao conectar." }));
      }
    } finally {
      setBusy((p) => ({ ...p, [kbId]: false }));
    }
  }

  async function handleDisconnect(kbId: string) {
    setBusy((p) => ({ ...p, [kbId]: true }));
    setActionErrors((p) => ({ ...p, [kbId]: "" }));
    try {
      await api.agents.knowledgeBases.disconnect(agentId, kbId);
      setConnections((prev) => prev.filter((c) => c.knowledge_base_id !== kbId));
    } catch (e) {
      setActionErrors((p) => ({ ...p, [kbId]: e instanceof Error ? e.message : "Erro ao desconectar." }));
    } finally {
      setBusy((p) => ({ ...p, [kbId]: false }));
    }
  }

  const writeAllowed = canWrite(role);

  return (
    <Modal open={open} onClose={onClose} title="Configurar Base de Conhecimento">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          Selecione quais bases este agente pode consultar ao responder clientes.
        </p>

        <div className="flex items-start gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/20">
          <Info className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
          <p className="text-xs text-nb-warning">
            As bases conectadas são usadas automaticamente pelo agente via RAG.
          </p>
        </div>

        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-nb-elevated rounded-xl animate-pulse" />
            ))}
          </div>
        ) : loadError ? (
          <p className="text-sm text-nb-danger">{loadError}</p>
        ) : kbs.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center border border-dashed border-nb-border rounded-xl">
            <BookOpen className="w-8 h-8 text-nb-muted mb-2" />
            <p className="text-sm font-medium text-nb-secondary mb-1">Nenhuma base criada ainda.</p>
            <p className="text-xs text-nb-muted mb-4">
              Crie uma em{" "}
              <Link href="/dashboard/knowledge-bases" className="text-nb-primary hover:underline">
                Conhecimento
              </Link>
              .
            </p>
            <Link
              href="/dashboard/knowledge-bases"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-nb-primary text-white text-xs font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Criar base de conhecimento
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {kbs.map((kb) => {
              const conn = getConnection(kb.id);
              const connected = !!conn && conn.is_active;
              const isBusy = busy[kb.id] ?? false;
              const err = actionErrors[kb.id];

              return (
                <div
                  key={kb.id}
                  className="flex items-center gap-3 p-3.5 bg-nb-panel rounded-xl border border-nb-border hover:border-nb-border-strong transition-colors"
                >
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      connected
                        ? "bg-nb-primary/10 border border-nb-primary/20"
                        : "bg-nb-elevated border border-nb-border"
                    }`}
                  >
                    <BookOpen className={`w-4 h-4 ${connected ? "text-nb-primary-strong" : "text-nb-muted"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-nb-text truncate">{kb.name}</span>
                      {connected && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-medium bg-nb-success/10 text-nb-success border border-nb-success/20">
                          <Check className="w-3 h-3" />
                          Conectada
                        </span>
                      )}
                    </div>
                    {kb.description && (
                      <p className="text-xs text-nb-muted truncate mt-0.5">{kb.description}</p>
                    )}
                    {err && <p className="text-xs text-nb-danger mt-0.5">{err}</p>}
                  </div>
                  {writeAllowed && (
                    isBusy ? (
                      <Loader2 className="w-4 h-4 text-nb-muted animate-spin flex-shrink-0" />
                    ) : connected ? (
                      <button
                        type="button"
                        onClick={() => handleDisconnect(kb.id)}
                        className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-nb-muted border border-nb-border rounded-lg hover:bg-nb-danger/10 hover:text-nb-danger hover:border-nb-danger/20 transition-colors"
                      >
                        <Minus className="w-3.5 h-3.5" />
                        Desconectar
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleConnect(kb.id)}
                        className="flex-shrink-0 flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-lg hover:bg-nb-primary/10 transition-colors"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        Conectar
                      </button>
                    )
                  )}
                </div>
              );
            })}
          </div>
        )}

        {kbs.length > 0 && (
          <div className="flex justify-end pt-1">
            <Link
              href="/dashboard/knowledge-bases"
              className="text-xs text-nb-primary hover:underline"
            >
              Gerenciar bases de conhecimento →
            </Link>
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Catalog Configure Modal ───────────────────────────────────────────────────

function CategoryPickerModal({
  open,
  onClose,
  categories,
  selectedIds,
  onSave,
}: {
  open: boolean;
  onClose: () => void;
  categories: CatalogCategory[];
  selectedIds: string[];
  onSave: (ids: string[]) => void;
}) {
  const [draft, setDraft] = useState<string[]>(selectedIds);

  useEffect(() => {
    if (open) setDraft(selectedIds);
  }, [open, selectedIds]);

  function toggle(id: string) {
    setDraft((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  return (
    <Modal open={open} onClose={onClose} title="Selecionar categorias">
      <div className="space-y-3">
        {categories.length === 0 ? (
          <p className="text-sm text-nb-muted py-6 text-center">
            Nenhuma categoria encontrada no catálogo.
          </p>
        ) : (
          <div className="space-y-1">
            {categories.map((cat) => {
              const checked = draft.includes(cat.id);
              return (
                <label
                  key={cat.id}
                  className="flex items-center gap-3 p-3 rounded-xl border border-nb-border hover:border-nb-border-strong cursor-pointer transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(cat.id)}
                    className="w-4 h-4 accent-nb-primary"
                  />
                  <span className="text-sm text-nb-text">{cat.name}</span>
                </label>
              );
            })}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2 border-t border-nb-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => { onSave(draft); onClose(); }}
            className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors"
          >
            Salvar seleção
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CatalogConfigModal({
  open,
  onClose,
  agentId,
  readonly,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  readonly: boolean;
}) {
  const [scope, setScope] = useState<AgentCatalogScope>({
    catalog_enabled: true,
    category_scope: "all",
    category_ids: [],
  });
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    setError(null);
    Promise.all([api.agents.catalogScope.get(agentId), api.catalog.categories.list(false)])
      .then(([s, cats]) => { setScope(s); setCategories(cats); })
      .catch(() => setError("Erro ao carregar configuração do Catálogo."))
      .finally(() => setLoading(false));
  }, [open, agentId]);

  async function saveScope(next: AgentCatalogScope) {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await api.agents.catalogScope.update(agentId, {
        catalog_enabled: next.catalog_enabled,
        category_scope: next.category_scope,
        category_ids: next.category_ids,
      });
      setScope(saved);
    } catch {
      setSaveError("Erro ao salvar configuração do Catálogo.");
    } finally {
      setSaving(false);
    }
  }

  function handleToggle(enabled: boolean) {
    const next = { ...scope, catalog_enabled: enabled };
    setScope(next);
    saveScope(next);
  }

  function handleScopeChange(s: "all" | "selected") {
    const next: AgentCatalogScope = {
      ...scope,
      category_scope: s,
      category_ids: s === "all" ? [] : scope.category_ids,
    };
    setScope(next);
    saveScope(next);
  }

  function handleCategorySave(ids: string[]) {
    const next: AgentCatalogScope = {
      ...scope,
      category_scope: ids.length > 0 ? "selected" : "all",
      category_ids: ids,
    };
    setScope(next);
    saveScope(next);
  }

  const selectedNames = scope.category_ids
    .map((id) => categories.find((c) => c.id === id)?.name)
    .filter(Boolean);

  // Render category picker modal inside the main modal flow
  if (pickerOpen) {
    return (
      <CategoryPickerModal
        open={true}
        onClose={() => setPickerOpen(false)}
        categories={categories}
        selectedIds={scope.category_ids}
        onSave={handleCategorySave}
      />
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="Configurar Catálogo">
      <div className="space-y-5">
        {loading ? (
          <div className="space-y-3">
            {[1, 2].map((i) => <div key={i} className="h-12 bg-nb-elevated rounded-xl animate-pulse" />)}
          </div>
        ) : error ? (
          <p className="text-sm text-nb-danger">{error}</p>
        ) : (
          <>
            {/* Enable toggle */}
            <div className="flex items-center justify-between p-4 bg-nb-panel border border-nb-border rounded-xl">
              <div>
                <p className="text-sm font-medium text-nb-text">Usar Catálogo nas respostas</p>
                <p className="text-xs text-nb-muted mt-0.5">
                  Permite que o agente consulte produtos e serviços cadastrados.
                </p>
              </div>
              <Toggle
                checked={scope.catalog_enabled}
                disabled={readonly || saving}
                onChange={handleToggle}
              />
            </div>

            {scope.catalog_enabled && (
              <div className="space-y-3">
                <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">
                  Escopo do Catálogo
                </p>

                {(["all", "selected"] as const).map((opt) => (
                  <label
                    key={opt}
                    className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition-colors ${
                      scope.category_scope === opt
                        ? "border-nb-primary/40 bg-nb-primary/5"
                        : "border-nb-border hover:border-nb-border-strong"
                    }`}
                  >
                    <input
                      type="radio"
                      name="catalog-scope"
                      checked={scope.category_scope === opt}
                      onChange={() => !readonly && !saving && handleScopeChange(opt)}
                      disabled={readonly || saving}
                      className="mt-0.5 accent-nb-primary"
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-nb-text">
                        {opt === "all" ? "Todo o Catálogo" : "Categorias selecionadas"}
                      </p>
                      <p className="text-xs text-nb-muted mt-0.5">
                        {opt === "all"
                          ? "O agente consulta todos os itens do catálogo."
                          : "Restrinja o agente a categorias específicas."}
                      </p>
                    </div>
                  </label>
                ))}

                {scope.category_scope === "selected" && (
                  <div className="pt-1 space-y-2">
                    <button
                      type="button"
                      disabled={readonly || saving}
                      onClick={() => setPickerOpen(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      Selecionar categorias
                    </button>
                    {selectedNames.length > 0 && (
                      <ul className="flex flex-col gap-1">
                        {selectedNames.map((name) => (
                          <li key={name} className="flex items-center gap-2 text-xs text-nb-muted">
                            <span className="w-1.5 h-1.5 rounded-full bg-nb-primary shrink-0" />
                            {name}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            )}

            {saveError && <p className="text-xs text-nb-danger">{saveError}</p>}
            {saving && (
              <div className="flex items-center gap-2 text-xs text-nb-muted">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Salvando…
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

// ── HTTP Tool form modal (create/edit) ──────────────────────────────────────────

const NAME_PATTERN = /^[a-zA-Z0-9_]+$/;
const URL_PLACEHOLDER_RE = /\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g;

function extractPathVars(url: string): string[] {
  const found = new Set<string>();
  for (const m of url.matchAll(URL_PLACEHOLDER_RE)) found.add(m[1]);
  return Array.from(found);
}

type HttpToolTemplate = {
  label: string;
  name: string;
  description: string;
  url: string;
  pathParamDescriptions: Record<string, string>;
  method?: HttpToolConfig["method"];
  headers?: Record<string, string>;
  queryParams?: HttpToolParam[];
  // Contract JSON text (same shape the "JSON" body mode reads/writes) — kept
  // as a literal string here so applyTemplate() doesn't need to know about
  // the field-tree types.
  bodyJsonText?: string;
};

const HTTP_TOOL_TEMPLATES: HttpToolTemplate[] = [
  {
    label: "ViaCEP — consultar endereço por CEP",
    name: "consultar_cep",
    description: "Consulta um CEP e retorna o endereço correspondente (rua, bairro, cidade, UF).",
    url: "https://viacep.com.br/ws/{cep}/json/",
    pathParamDescriptions: { cep: "CEP no formato 00000000 (só números, sem traço)." },
  },
  {
    label: "ReceitaWS — consultar CNPJ",
    name: "consultar_cnpj",
    description: "Consulta um CNPJ e retorna dados cadastrais da empresa (razão social, situação, endereço).",
    url: "https://receitaws.com.br/v1/cnpj/{cnpj}",
    pathParamDescriptions: { cnpj: "CNPJ só com números, sem pontuação." },
  },
  {
    label: "Cal.com — agendar visita/reunião",
    name: "agendar_visita",
    description:
      "Aciona quando o cliente confirmar um dia e horário específicos pra agendar uma visita/reunião. " +
      "Antes de chamar, sempre pergunte e confirme o nome completo e o e-mail do cliente.",
    url: "https://api.cal.com/v2/bookings",
    method: "POST",
    pathParamDescriptions: {},
    headers: {
      Authorization: "Bearer <sua-api-key-da-cal.com>",
      "cal-api-version": "2026-02-25",
    },
    bodyJsonText: JSON.stringify(
      {
        eventTypeId: {
          type: "number", isUserProvided: false, value: 0,
          description: "Substitua pelo ID do seu Tipo de Evento na Cal.com (Event Types → copie o ID na URL).",
        },
        start: {
          type: "string", isUserProvided: true,
          description:
            "Data/hora de início da visita em UTC, formato ISO 8601 (ex: 2026-07-25T17:00:00Z). " +
            "Se o cliente informar horário de Brasília, converta somando 3 horas antes de preencher.",
        },
        attendee: {
          type: "object",
          properties: {
            name: { type: "string", isUserProvided: true, description: "Nome completo do cliente" },
            email: { type: "string", isUserProvided: true, description: "E-mail do cliente" },
            timeZone: { type: "string", isUserProvided: false, value: "America/Sao_Paulo" },
          },
        },
      },
      null,
      2
    ),
  },
  {
    label: "Cal.com — verificar horários disponíveis",
    name: "verificar_horarios_calcom",
    description:
      "Aciona quando o cliente perguntar sobre disponibilidade de horários pra visita/reunião, " +
      "antes de confirmar um dia e horário específicos.",
    url: "https://api.cal.com/v2/slots?username=<seu-username-cal.com>&eventTypeSlug=<slug-do-evento>&timeZone=America/Sao_Paulo",
    method: "GET",
    pathParamDescriptions: {},
    headers: {
      Authorization: "Bearer <sua-api-key-da-cal.com>",
      "cal-api-version": "2024-09-04",
    },
    queryParams: [
      {
        name: "start", required: true,
        description: "Início do intervalo de busca, ISO 8601 em UTC (ex: 2026-07-25 ou 2026-07-25T00:00:00Z).",
      },
      {
        name: "end", required: true,
        description: "Fim do intervalo de busca, ISO 8601 em UTC (ex: 2026-08-01).",
      },
    ],
  },
];

// ── Headers editor (key/value rows, replaces the old raw-JSON textarea) ────────

function HeadersEditor({
  rows,
  onChange,
}: {
  rows: { key: string; value: string }[];
  onChange: (rows: { key: string; value: string }[]) => void;
}) {
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex gap-2">
          <input
            type="text"
            value={row.key}
            onChange={(e) => onChange(rows.map((r, j) => (j === i ? { ...r, key: e.target.value } : r)))}
            placeholder="Authorization"
            className={`${inputCls} font-mono text-xs`}
          />
          <input
            type="text"
            value={row.value}
            onChange={(e) => onChange(rows.map((r, j) => (j === i ? { ...r, value: e.target.value } : r)))}
            placeholder="Bearer ..."
            className={`${inputCls} font-mono text-xs`}
          />
          <button
            type="button"
            onClick={() => onChange(rows.filter((_, j) => j !== i))}
            className="flex-shrink-0 p-2 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...rows, { key: "", value: "" }])}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:underline"
      >
        <Plus className="w-3.5 h-3.5" /> Add Header
      </button>
    </div>
  );
}

// ── Query params editor (structured — name/descrição/obrigatório/valor de teste) ─

function QueryParamsEditor({
  params,
  onChange,
  testValues,
  onTestValueChange,
}: {
  params: HttpToolParam[];
  onChange: (params: HttpToolParam[]) => void;
  testValues: Record<string, string>;
  onTestValueChange: (name: string, value: string) => void;
}) {
  return (
    <div className="space-y-2">
      {params.map((p, i) => (
        <div key={i} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
          <div className="flex gap-2">
            <input
              type="text"
              value={p.name}
              onChange={(e) => onChange(params.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
              placeholder="formato"
              className={`${inputCls} font-mono text-xs`}
            />
            <label className="flex items-center gap-1.5 flex-shrink-0 text-xs text-nb-muted whitespace-nowrap px-1">
              <input
                type="checkbox"
                checked={p.required}
                onChange={(e) => onChange(params.map((x, j) => (j === i ? { ...x, required: e.target.checked } : x)))}
                className="accent-nb-primary"
              />
              Obrigatório
            </label>
            <button
              type="button"
              onClick={() => onChange(params.filter((_, j) => j !== i))}
              className="flex-shrink-0 p-2 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
          <input
            type="text"
            value={p.description}
            onChange={(e) => onChange(params.map((x, j) => (j === i ? { ...x, description: e.target.value } : x)))}
            placeholder="Descrição pro agente entender pra que serve (ex: json ou xml)"
            className={`${inputCls} text-xs`}
          />
          {p.name.trim() && (
            <input
              type="text"
              value={testValues[p.name] || ""}
              onChange={(e) => onTestValueChange(p.name, e.target.value)}
              placeholder="Valor de teste (usado só no botão Validar Configuração)"
              className={`${inputCls} text-xs`}
            />
          )}
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...params, { name: "", description: "", required: false }])}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:underline"
      >
        <Plus className="w-3.5 h-3.5" /> Add Parâmetro de Query
      </button>
    </div>
  );
}

// ── Body (JSON) code editor — syntax highlighting, Tab-to-indent, live lint ────

const cmTheme = EditorView.theme({
  "&": {
    backgroundColor: "var(--color-nb-panel)",
    color: "var(--color-nb-text)",
    fontSize: "12px",
  },
  ".cm-content": { fontFamily: "var(--font-mono, ui-monospace, monospace)", padding: "8px 0" },
  ".cm-gutters": {
    backgroundColor: "var(--color-nb-panel)",
    color: "var(--color-nb-muted)",
    border: "none",
  },
  "&.cm-focused": { outline: "none" },
  ".cm-activeLine": { backgroundColor: "transparent" },
  ".cm-activeLineGutter": { backgroundColor: "transparent" },
});

const jsonHighlightStyle = HighlightStyle.define([
  { tag: tags.propertyName, color: "var(--color-nb-primary)" },
  { tag: tags.string, color: "var(--color-nb-success)" },
  { tag: tags.number, color: "#F59E0B" },
  { tag: [tags.bool, tags.null], color: "#8B5CF6" },
  { tag: [tags.brace, tags.squareBracket, tags.punctuation], color: "var(--color-nb-muted)" },
]);

function JsonBodyEditor({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className="rounded-xl overflow-hidden border border-nb-border">
      <CodeMirror
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        theme={cmTheme}
        basicSetup={{ lineNumbers: true, foldGutter: false, highlightActiveLine: false }}
        extensions={[
          cmJson(),
          syntaxHighlighting(jsonHighlightStyle),
          linter(jsonParseLinter()),
          lintGutter(),
          keymap.of([indentWithTab]),
        ]}
        minHeight="90px"
        maxHeight="320px"
      />
    </div>
  );
}

// ── Body — contract JSON (type/isUserProvided/value/description per field) ─────
//
// The user edits a self-describing contract, not the literal HTTP body — no
// {placeholder} syntax to learn or get wrong. "Formulário" and "JSON" are two
// views of the same field tree; body_template (the literal JSON actually sent
// to the API, still the backend's contract) is derived from that tree at
// save/test time. Nothing changes server-side.

type BodyFieldType = "string" | "number" | "boolean" | "null" | "object";

type BodyFieldNode = {
  key: string;
  type: BodyFieldType;
  isUserProvided: boolean; // meaningless for type "object" / "null"
  value: string;           // raw text, used for string/number when fixed
  boolValue: boolean;      // used for boolean when fixed
  description: string;
  children: BodyFieldNode[]; // used for type "object"
};

// "Valor de teste" (used only by "Validar Configuração") is intentionally NOT
// part of this tree — it lives in the modal's bodyTestValues state, keyed by
// field key, same pattern as pathTestValues/queryTestValues. Keeping it out
// of the tree means it survives a JSON <-> Formulário mode switch for free.
function emptyBodyField(): BodyFieldNode {
  return {
    key: "", type: "string", isUserProvided: true, value: "", boolValue: true,
    description: "", children: [],
  };
}

const BODY_FIELD_TYPE_LABELS: Record<BodyFieldType, string> = {
  string: "Texto",
  number: "Número",
  boolean: "Verdadeiro/falso",
  null: "Nulo",
  object: "Objeto aninhado",
};

// ── tree -> literal body_template (what actually gets sent to the API) ─────────

function serializeBodyNode(node: BodyFieldNode, indent: number): string {
  const pad = "  ".repeat(indent);
  const key = JSON.stringify(node.key);
  if (node.type === "object") {
    const inner = node.children.map((c) => serializeBodyNode(c, indent + 1)).join(",\n");
    return `${pad}${key}: {\n${inner}\n${pad}}`;
  }
  if (node.isUserProvided) {
    return `${pad}${key}: ${JSON.stringify(`{${node.key.trim() || "valor"}}`)}`;
  }
  switch (node.type) {
    case "string":
      return `${pad}${key}: ${JSON.stringify(node.value)}`;
    case "number": {
      const n = Number(node.value);
      return `${pad}${key}: ${node.value.trim() !== "" && Number.isFinite(n) ? n : 0}`;
    }
    case "boolean":
      return `${pad}${key}: ${node.boolValue ? "true" : "false"}`;
    case "null":
      return `${pad}${key}: null`;
  }
}

function buildBodyTemplateFromFields(fields: BodyFieldNode[]): string {
  if (fields.length === 0) return "";
  const inner = fields.map((f) => serializeBodyNode(f, 1)).join(",\n");
  return `{\n${inner}\n}`;
}

function collectVariablesFromFields(
  fields: BodyFieldNode[]
): { key: string; description: string }[] {
  const out: { key: string; description: string }[] = [];
  const seen = new Set<string>();
  function walk(nodes: BodyFieldNode[]) {
    for (const n of nodes) {
      if (n.type === "object") {
        walk(n.children);
      } else if (n.isUserProvided && n.key.trim() && !seen.has(n.key.trim())) {
        seen.add(n.key.trim());
        out.push({ key: n.key.trim(), description: n.description });
      }
    }
  }
  walk(fields);
  return out;
}

// ── tree <-> contract JSON (what the user reads/writes in "JSON" mode) ─────────
//
// { "start": { "type": "string", "isUserProvided": true, "description": "..." },
//   "attendee": { "type": "object", "properties": { "email": {...} } } }

function fieldToContractValue(node: BodyFieldNode): unknown {
  if (node.type === "object") {
    const properties: Record<string, unknown> = {};
    node.children.forEach((c) => { properties[c.key] = fieldToContractValue(c); });
    return { type: "object", properties };
  }
  const entry: Record<string, unknown> = { type: node.type, isUserProvided: node.isUserProvided };
  if (!node.isUserProvided) {
    if (node.type === "boolean") entry.value = node.boolValue;
    else if (node.type === "number") {
      const n = Number(node.value);
      entry.value = node.value.trim() !== "" && Number.isFinite(n) ? n : 0;
    } else if (node.type === "string") entry.value = node.value;
  }
  if (node.description.trim()) entry.description = node.description;
  return entry;
}

function serializeFieldsToContractJson(fields: BodyFieldNode[]): string {
  if (fields.length === 0) return "";
  const obj: Record<string, unknown> = {};
  fields.forEach((f) => { obj[f.key] = fieldToContractValue(f); });
  return JSON.stringify(obj, null, 2);
}

function contractValueToField(key: string, entry: unknown): BodyFieldNode | null {
  if (typeof entry !== "object" || entry === null || Array.isArray(entry)) return null;
  const e = entry as Record<string, unknown>;
  if (e.type === "object") {
    if (typeof e.properties !== "object" || e.properties === null || Array.isArray(e.properties)) return null;
    const children: BodyFieldNode[] = [];
    for (const [k, v] of Object.entries(e.properties as Record<string, unknown>)) {
      const child = contractValueToField(k, v);
      if (!child) return null;
      children.push(child);
    }
    return { ...emptyBodyField(), key, type: "object", children };
  }
  if (e.type !== "string" && e.type !== "number" && e.type !== "boolean" && e.type !== "null") return null;
  const isUserProvided = e.isUserProvided === true;
  const description = typeof e.description === "string" ? e.description : "";
  const node: BodyFieldNode = { ...emptyBodyField(), key, type: e.type, isUserProvided, description };
  if (!isUserProvided) {
    if (e.type === "boolean") node.boolValue = e.value === true;
    else if (e.type === "number") node.value = typeof e.value === "number" ? String(e.value) : "0";
    else if (e.type === "string") node.value = typeof e.value === "string" ? e.value : "";
  }
  return node;
}

// Returns null when the text isn't a valid contract (bad JSON, contains a
// list, isn't a top-level object) — caller keeps the user in JSON mode and
// shows why, instead of losing/mangling what they wrote.
function parseContractJsonToFields(jsonText: string): BodyFieldNode[] | null {
  const trimmed = jsonText.trim();
  if (!trimmed) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return null;
  }
  // Tolerate a single-element array wrapper (`[{...}]`) — the shape some
  // other tools (and content pasted from them) use for the same contract.
  if (Array.isArray(parsed) && parsed.length === 1 && typeof parsed[0] === "object" && parsed[0] !== null && !Array.isArray(parsed[0])) {
    parsed = parsed[0];
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
  const fields: BodyFieldNode[] = [];
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    const node = contractValueToField(k, v);
    if (!node) return null;
    fields.push(node);
  }
  return fields;
}

// ── legacy migration: old body_template ("{start}" placeholders inside the
// literal JSON) -> field tree, run once when a previously-saved tool is
// opened, so it shows the new contract instead of erroring on load. ──────────

const LEGACY_VARIABLE_VALUE_RE = /^\{([a-zA-Z_][a-zA-Z0-9_]*)\}$/;

// Same intent as the backend's _URL_PLACEHOLDER_RE substitution — tolerates
// the exact bug pattern (`"start": {start}` instead of `"start": "{start}"`)
// some hand-typed legacy templates have.
function normalizeUnquotedPlaceholders(raw: string): string {
  return raw.replace(/(?<!")\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!")/g, '"{$1}"');
}

function legacyValueToField(
  key: string,
  value: unknown,
  descriptions: Record<string, string>
): BodyFieldNode | null {
  if (Array.isArray(value)) return null;
  if (value === null) return { ...emptyBodyField(), key, type: "null", isUserProvided: false };
  if (typeof value === "object") {
    const children: BodyFieldNode[] = [];
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const child = legacyValueToField(k, v, descriptions);
      if (!child) return null;
      children.push(child);
    }
    return { ...emptyBodyField(), key, type: "object", children };
  }
  if (typeof value === "string") {
    const m = value.match(LEGACY_VARIABLE_VALUE_RE);
    if (m) {
      const varName = m[1];
      return {
        ...emptyBodyField(), key, type: "string", isUserProvided: true,
        description: descriptions[varName] || "",
      };
    }
    return { ...emptyBodyField(), key, type: "string", isUserProvided: false, value };
  }
  if (typeof value === "number") {
    return { ...emptyBodyField(), key, type: "number", isUserProvided: false, value: String(value) };
  }
  if (typeof value === "boolean") {
    return { ...emptyBodyField(), key, type: "boolean", isUserProvided: false, boolValue: value };
  }
  return null;
}

function parseLegacyBodyTemplateToFields(
  template: string,
  descriptions: Record<string, string>
): BodyFieldNode[] | null {
  const trimmed = template.trim();
  if (!trimmed) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    try {
      parsed = JSON.parse(normalizeUnquotedPlaceholders(trimmed));
    } catch {
      return null;
    }
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) return null;
  const fields: BodyFieldNode[] = [];
  for (const [k, v] of Object.entries(parsed as Record<string, unknown>)) {
    const node = legacyValueToField(k, v, descriptions);
    if (!node) return null;
    fields.push(node);
  }
  return fields;
}

// ── Formulário — clickable view of the same field tree ─────────────────────────

function BodyFormEditor({
  fields,
  onChange,
  testValues,
  onTestValueChange,
  depth = 0,
}: {
  fields: BodyFieldNode[];
  onChange: (fields: BodyFieldNode[]) => void;
  testValues: Record<string, string>;
  onTestValueChange: (key: string, value: string) => void;
  depth?: number;
}) {
  function updateField(i: number, patch: Partial<BodyFieldNode>) {
    onChange(fields.map((f, j) => (j === i ? { ...f, ...patch } : f)));
  }
  function removeField(i: number) {
    onChange(fields.filter((_, j) => j !== i));
  }

  return (
    <div className={depth > 0 ? "pl-3 border-l-2 border-nb-border space-y-2" : "space-y-2"}>
      {fields.map((f, i) => (
        <div key={i} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
          <div className="flex gap-2">
            <input
              type="text"
              value={f.key}
              onChange={(e) => updateField(i, { key: e.target.value })}
              placeholder="chave"
              className={`${inputCls} font-mono text-xs`}
            />
            <select
              value={f.type}
              onChange={(e) => updateField(i, { type: e.target.value as BodyFieldType })}
              className={`${inputCls} text-xs w-auto flex-shrink-0`}
            >
              {(Object.keys(BODY_FIELD_TYPE_LABELS) as BodyFieldType[]).map((t) => (
                <option key={t} value={t}>{BODY_FIELD_TYPE_LABELS[t]}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => removeField(i)}
              className="flex-shrink-0 p-2 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>

          {f.type !== "object" && f.type !== "null" && (
            <label className="flex items-center gap-1.5 text-xs text-nb-muted">
              <input
                type="checkbox"
                checked={f.isUserProvided}
                onChange={(e) => updateField(i, { isUserProvided: e.target.checked })}
                className="accent-nb-primary"
              />
              Preenchido pelo agente
            </label>
          )}

          {f.type === "object" ? (
            <BodyFormEditor
              fields={f.children}
              onChange={(children) => updateField(i, { children })}
              testValues={testValues}
              onTestValueChange={onTestValueChange}
              depth={depth + 1}
            />
          ) : f.isUserProvided ? (
            <>
              <input
                type="text"
                value={f.description}
                onChange={(e) => updateField(i, { description: e.target.value })}
                placeholder="Descrição pro agente entender o que preencher aqui (opcional)"
                className={`${inputCls} text-xs`}
              />
              {f.key.trim() && (
                <input
                  type="text"
                  value={testValues[f.key.trim()] || ""}
                  onChange={(e) => onTestValueChange(f.key.trim(), e.target.value)}
                  placeholder="Valor de teste (usado só no botão Validar Configuração)"
                  className={`${inputCls} text-xs`}
                />
              )}
            </>
          ) : (
            <>
              {f.type === "string" && (
                <input
                  type="text"
                  value={f.value}
                  onChange={(e) => updateField(i, { value: e.target.value })}
                  placeholder="Valor"
                  className={`${inputCls} text-xs`}
                />
              )}
              {f.type === "number" && (
                <input
                  type="text"
                  inputMode="decimal"
                  value={f.value}
                  onChange={(e) => updateField(i, { value: e.target.value })}
                  placeholder="Valor numérico"
                  className={`${inputCls} text-xs`}
                />
              )}
              {f.type === "boolean" && (
                <label className="flex items-center gap-1.5 text-xs text-nb-muted">
                  <input
                    type="checkbox"
                    checked={f.boolValue}
                    onChange={(e) => updateField(i, { boolValue: e.target.checked })}
                    className="accent-nb-primary"
                  />
                  {f.boolValue ? "true" : "false"}
                </label>
              )}
            </>
          )}
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...fields, emptyBodyField()])}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:underline"
      >
        <Plus className="w-3.5 h-3.5" /> Add campo
      </button>
    </div>
  );
}

function HttpToolFormModal({
  open,
  onClose,
  agentId,
  editingTool,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  editingTool: HttpAgentTool | null;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [method, setMethod] = useState<HttpToolConfig["method"]>("GET");
  const [url, setUrl] = useState("");
  const [headerRows, setHeaderRows] = useState<{ key: string; value: string }[]>([]);
  const [pathDescriptions, setPathDescriptions] = useState<Record<string, string>>({});
  const [pathTestValues, setPathTestValues] = useState<Record<string, string>>({});
  const [queryParams, setQueryParams] = useState<HttpToolParam[]>([]);
  const [queryTestValues, setQueryTestValues] = useState<Record<string, string>>({});
  // Body — "JSON" mode is free text (bodyJsonText) validated at mode-switch /
  // save / test time; "Formulário" mode is a live, always-valid field tree
  // (bodyFields). bodyTestValues is ephemeral (never persisted), keyed by
  // field key, shared by both modes so it survives switching between them.
  const [bodyJsonText, setBodyJsonText] = useState("");
  const [bodyFields, setBodyFields] = useState<BodyFieldNode[]>([]);
  const [bodyMode, setBodyMode] = useState<"json" | "form">("json");
  const [bodyTestValues, setBodyTestValues] = useState<Record<string, string>>({});
  const [bodyFormError, setBodyFormError] = useState<string | null>(null);
  const [timeoutSeconds, setTimeoutSeconds] = useState(8);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<HttpToolTestResult | null>(null);

  const pathVars = extractPathVars(url);
  const bodyAllowed = method === "POST" || method === "PUT" || method === "PATCH";
  // Resolved fields for whichever mode is active — null only means "JSON
  // mode has invalid text right now" (Formulário is always structurally valid).
  const resolvedBodyFields = bodyMode === "form" ? bodyFields : parseContractJsonToFields(bodyJsonText);
  const bodyVars = resolvedBodyFields ? collectVariablesFromFields(resolvedBodyFields) : [];

  useEffect(() => {
    if (!open) return;
    if (editingTool) {
      setName(editingTool.name);
      setDescription(editingTool.description);
      setMethod(editingTool.config.method);
      setUrl(editingTool.config.url);
      setHeaderRows(Object.entries(editingTool.config.headers || {}).map(([key, value]) => ({ key, value })));
      setPathDescriptions(editingTool.config.path_param_descriptions || {});
      setQueryParams(editingTool.config.query_params || []);

      const legacyFields = parseLegacyBodyTemplateToFields(
        editingTool.config.body_template || "",
        editingTool.config.body_param_descriptions || {}
      );
      const fields = legacyFields ?? [];
      setBodyFields(fields);
      setBodyJsonText(serializeFieldsToContractJson(fields));
      setBodyFormError(
        legacyFields === null && (editingTool.config.body_template || "").trim()
          ? "Não consegui converter automaticamente o body salvo pro contrato novo (ex: contém uma lista/array). Reconfigure abaixo."
          : null
      );
    } else {
      setName("");
      setDescription("");
      setMethod("GET");
      setUrl("");
      setHeaderRows([]);
      setPathDescriptions({});
      setQueryParams([]);
      setBodyFields([]);
      setBodyJsonText("");
      setBodyFormError(null);
    }
    setTimeoutSeconds(editingTool?.config.timeout_seconds ?? 8);
    setPathTestValues({});
    setQueryTestValues({});
    setBodyTestValues({});
    setBodyMode("json");
    setTemplatePickerOpen(false);
    setError(null);
    setTestResult(null);
  }, [open, editingTool]);

  function applyTemplate(t: HttpToolTemplate) {
    setName(t.name);
    setDescription(t.description);
    setMethod(t.method || "GET");
    setUrl(t.url);
    setPathDescriptions(t.pathParamDescriptions);
    setQueryParams(t.queryParams || []);
    setHeaderRows(Object.entries(t.headers || {}).map(([key, value]) => ({ key, value })));
    setBodyFields([]);
    setBodyJsonText(t.bodyJsonText || "");
    setBodyMode("json");
    setBodyFormError(null);
    setTestResult(null);
  }

  function switchToBodyFormMode() {
    const fields = parseContractJsonToFields(bodyJsonText);
    if (fields === null) {
      setBodyFormError("O JSON do body está inválido. Corrija antes de trocar pro Formulário.");
      return;
    }
    setBodyFields(fields);
    setBodyFormError(null);
    setBodyMode("form");
  }

  function switchToBodyJsonMode() {
    setBodyJsonText(serializeFieldsToContractJson(bodyFields));
    setBodyFormError(null);
    setBodyMode("json");
  }

  function formatBodyJsonText() {
    const fields = parseContractJsonToFields(bodyJsonText);
    if (fields === null) {
      setError("Não foi possível formatar: o JSON do body está inválido.");
      return;
    }
    setBodyJsonText(serializeFieldsToContractJson(fields));
    setError(null);
  }

  // Body must be valid before we can build a config from it — null only
  // happens in JSON mode with broken text (Formulário is always valid).
  function validateBody(): string | null {
    if (bodyAllowed && bodyMode === "json" && resolvedBodyFields === null) {
      return "O JSON do body está inválido. Corrija antes de continuar.";
    }
    return null;
  }

  function buildConfig(): HttpToolConfig {
    const headers: Record<string, string> = {};
    headerRows.forEach(({ key, value }) => { if (key.trim()) headers[key.trim()] = value; });
    const fields = bodyAllowed ? resolvedBodyFields || [] : [];
    const bodyTemplateStr = buildBodyTemplateFromFields(fields);
    const bodyDescriptions: Record<string, string> = {};
    collectVariablesFromFields(fields).forEach((v) => { bodyDescriptions[v.key] = v.description; });
    return {
      method,
      url: url.trim(),
      headers,
      timeout_seconds: timeoutSeconds,
      path_param_descriptions: pathDescriptions,
      query_params: queryParams.filter((p) => p.name.trim()),
      body_template: bodyTemplateStr.trim() ? bodyTemplateStr.trim() : null,
      body_param_descriptions: bodyDescriptions,
    };
  }

  async function handleTest() {
    setTestResult(null);
    if (!url.trim()) {
      setError("Informe a URL antes de validar.");
      return;
    }
    const bodyError = validateBody();
    if (bodyError) {
      setError(bodyError);
      return;
    }
    setError(null);
    setTesting(true);
    try {
      const sampleQuery: Record<string, string> = {};
      queryParams.forEach((p) => {
        const v = queryTestValues[p.name];
        if (p.name.trim() && v) sampleQuery[p.name] = v;
      });
      const result = await api.agents.httpTools.test(agentId, buildConfig(), {
        ...pathTestValues,
        ...(bodyAllowed ? bodyTestValues : {}),
        query_params: sampleQuery,
      });
      setTestResult(result);
    } catch (e) {
      setTestResult({
        ok: false, status_code: null, body: null,
        error: e instanceof ApiError ? e.message : "Erro ao validar configuração.",
      });
    } finally {
      setTesting(false);
    }
  }

  async function handleSave() {
    setError(null);

    if (!NAME_PATTERN.test(name)) {
      setError("O nome deve conter apenas letras, números e underline (ex: consultar_cep).");
      return;
    }
    if (!description.trim()) {
      setError("Descreva quando o agente deve usar essa ferramenta.");
      return;
    }
    if (!url.trim()) {
      setError("Informe a URL da API.");
      return;
    }
    const bodyError = validateBody();
    if (bodyError) {
      setError(bodyError);
      return;
    }

    const config = buildConfig();

    setSaving(true);
    try {
      if (editingTool) {
        await api.agents.httpTools.update(agentId, editingTool.id, {
          name, description, config,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "http_request", name, description, config,
        };
        await api.agents.httpTools.create(agentId, payload);
      }
      onSaved();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={editingTool ? "Editar ferramenta HTTP" : "Nova ferramenta HTTP"}>
      <div className="space-y-4">
        {!editingTool && (
          <div>
            <button
              type="button"
              onClick={() => setTemplatePickerOpen((v) => !v)}
              className="w-full flex items-center justify-between px-3 py-2.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5" /> Usar um modelo pronto
              </span>
              {templatePickerOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {templatePickerOpen && (
              <div className="mt-2 space-y-1 border border-nb-border rounded-xl p-1.5">
                {HTTP_TOOL_TEMPLATES.map((t) => (
                  <div
                    key={t.name}
                    className="flex items-center justify-between gap-2 p-2 rounded-lg hover:bg-nb-elevated transition-colors"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-nb-text truncate">{t.label}</p>
                      <p className="text-[11px] text-nb-muted truncate">{t.description}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => { applyTemplate(t); setTemplatePickerOpen(false); }}
                      className="flex-shrink-0 px-2.5 py-1 text-xs font-semibold text-white bg-nb-primary rounded-lg hover:opacity-90 transition-opacity"
                    >
                      Usar
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Nome (identificador, sem espaços)
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="consultar_cep"
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Descrição | Gatilho — quando o agente deve usar
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Consulta um CEP e retorna o endereço correspondente."
            rows={2}
            className={inputCls}
          />
          <p className="text-xs text-nb-muted mt-1">
            A descrição é essencial pra guiar o agente — é ela que ajuda o modelo a decidir quando
            chamar essa ferramenta.
          </p>
        </div>

        <div className="grid grid-cols-[110px_1fr] gap-2">
          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">Método</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as HttpToolConfig["method"])}
              className={inputCls}
            >
              {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://api.exemplo.com/cep/{cep}"
              className={`${inputCls} font-mono text-xs`}
            />
          </div>
        </div>
        <p className="text-xs text-nb-muted -mt-2">
          Use <code className="font-mono">{"{variavel}"}</code> na URL pra partes dinâmicas — cada
          uma vira uma linha em "Path" abaixo.
        </p>

        {/* Path — derivado da URL, uma linha por {variavel} detectada */}
        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">Path</label>
          {pathVars.length === 0 ? (
            <p className="text-xs text-nb-muted">
              Nenhuma variável detectada — escreva <code className="font-mono">{"{nome}"}</code>{" "}
              na URL acima pra criar uma.
            </p>
          ) : (
            <div className="space-y-2">
              {pathVars.map((v) => (
                <div key={v} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
                  <span className="text-xs font-mono font-medium text-nb-text">{`{${v}}`}</span>
                  <input
                    type="text"
                    value={pathDescriptions[v] || ""}
                    onChange={(e) => setPathDescriptions((p) => ({ ...p, [v]: e.target.value }))}
                    placeholder={`Descrição pro agente entender o que é "${v}" (opcional)`}
                    className={`${inputCls} text-xs`}
                  />
                  <input
                    type="text"
                    value={pathTestValues[v] || ""}
                    onChange={(e) => setPathTestValues((p) => ({ ...p, [v]: e.target.value }))}
                    placeholder="Valor de teste (usado só no botão Validar Configuração)"
                    className={`${inputCls} text-xs`}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Query */}
        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">Query</label>
          <QueryParamsEditor
            params={queryParams}
            onChange={setQueryParams}
            testValues={queryTestValues}
            onTestValueChange={(n, v) => setQueryTestValues((p) => ({ ...p, [n]: v }))}
          />
        </div>

        {/* Body — só faz sentido pra métodos que enviam corpo */}
        {bodyAllowed && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-medium text-nb-secondary">Body</label>
              <div className="inline-flex rounded-lg border border-nb-border p-0.5 bg-nb-bg">
                <button
                  type="button"
                  onClick={() => { if (bodyMode !== "json") switchToBodyJsonMode(); }}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                    bodyMode === "json" ? "bg-nb-primary text-nb-bg font-semibold" : "text-nb-muted"
                  }`}
                >
                  JSON
                </button>
                <button
                  type="button"
                  onClick={() => { if (bodyMode !== "form") switchToBodyFormMode(); }}
                  className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                    bodyMode === "form" ? "bg-nb-primary text-nb-bg font-semibold" : "text-nb-muted"
                  }`}
                >
                  Formulário
                </button>
              </div>
            </div>

            {bodyFormError && (
              <p className="text-xs text-nb-danger mb-1.5">{bodyFormError}</p>
            )}

            {bodyMode === "json" ? (
              <>
                <div className="flex justify-end mb-1">
                  <button
                    type="button"
                    onClick={formatBodyJsonText}
                    className="text-xs font-medium text-nb-primary hover:underline"
                  >
                    Formatar JSON
                  </button>
                </div>
                <JsonBodyEditor
                  value={bodyJsonText}
                  onChange={setBodyJsonText}
                  placeholder={
                    '{\n  "start": { "type": "string", "isUserProvided": true, "description": "Data/hora em UTC" },\n' +
                    '  "attendee": { "type": "object", "properties": {\n' +
                    '    "email": { "type": "string", "isUserProvided": true, "description": "E-mail do cliente" },\n' +
                    '    "timeZone": { "type": "string", "isUserProvided": false, "value": "America/Sao_Paulo" }\n' +
                    '  } }\n}'
                  }
                />
                <p className="text-xs text-nb-muted mt-1">
                  Descreva o contrato do body, campo por campo: <code className="font-mono">type</code> (string/number/boolean/null/object),{" "}
                  <code className="font-mono">isUserProvided</code> (se o agente preenche em tempo real),{" "}
                  <code className="font-mono">value</code> (valor fixo, quando não é preenchido pelo agente) e{" "}
                  <code className="font-mono">description</code>. Campos do tipo objeto usam{" "}
                  <code className="font-mono">properties</code> pra aninhar. Deixe em branco pra o agente montar o corpo sozinho (menos confiável).
                </p>
                {bodyVars.length > 0 && (
                  <div className="space-y-2 mt-2">
                    {bodyVars.map((v) => (
                      <div key={v.key} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
                        <span className="text-xs font-mono font-medium text-nb-text">{v.key}</span>
                        <input
                          type="text"
                          value={bodyTestValues[v.key] || ""}
                          onChange={(e) => setBodyTestValues((p) => ({ ...p, [v.key]: e.target.value }))}
                          placeholder="Valor de teste (usado só no botão Validar Configuração)"
                          className={`${inputCls} text-xs`}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <BodyFormEditor
                  fields={bodyFields}
                  onChange={setBodyFields}
                  testValues={bodyTestValues}
                  onTestValueChange={(key, value) => setBodyTestValues((p) => ({ ...p, [key]: value }))}
                />
                <p className="text-xs text-nb-muted mt-2">
                  Campos marcados como &ldquo;Preenchido pelo agente&rdquo; ficam de fora do valor fixo — o agente
                  informa em tempo real. Objetos aninhados criam sub-campos dentro do mesmo campo.
                </p>
              </>
            )}
          </div>
        )}

        {/* Headers */}
        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Headers — use pra token/API key da API (ex: Authorization)
          </label>
          <HeadersEditor rows={headerRows} onChange={setHeaderRows} />
        </div>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Timeout (segundos)
          </label>
          <input
            type="number"
            min={1}
            max={15}
            value={timeoutSeconds}
            onChange={(e) => setTimeoutSeconds(Number(e.target.value))}
            className={inputCls}
          />
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <button
          type="button"
          onClick={handleTest}
          disabled={testing}
          className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 text-xs font-semibold text-white bg-nb-success rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          {testing ? "Validando…" : "Validar Configuração"}
        </button>

        {testResult && (
          <div className={`p-3 rounded-xl border text-xs space-y-1 ${
            testResult.ok
              ? "bg-nb-success/10 border-nb-success/20 text-nb-success"
              : "bg-nb-danger/10 border-nb-danger/20 text-nb-danger"
          }`}>
            {testResult.ok ? (
              <>
                <p className="font-medium">Chamada respondeu com status {testResult.status_code}.</p>
                {testResult.body && (
                  <p className="font-mono text-nb-muted break-all line-clamp-3">{testResult.body}</p>
                )}
              </>
            ) : (
              <p className="font-medium">Falhou: {testResult.error}</p>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-nb-border">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
          >
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── HTTP Tools list modal ─────────────────────────────────────────────────────

function HttpToolsListModal({
  open,
  onClose,
  agentId,
  role,
  gated,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  role: MemberRole | null;
  gated: boolean;
}) {
  const [tools, setTools] = useState<HttpAgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<HttpAgentTool | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const writeAllowed = canWrite(role);

  function refresh() {
    setLoading(true);
    setLoadError(null);
    api.agents.httpTools
      .list(agentId)
      .then((all) => setTools(all.filter((t): t is HttpAgentTool => t.tool_type === "http_request")))
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar ferramentas."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) refresh();
  }, [open, agentId]);

  async function handleToggle(tool: HttpAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      const updated = await api.agents.httpTools.update(agentId, tool.id, {
        is_enabled: !tool.is_enabled,
      });
      setTools((prev) => prev.map((t) => (t.id === tool.id ? (updated as HttpAgentTool) : t)));
    } catch {
      // Toggle failure is surfaced by the row staying unchanged — low-stakes enough
      // to not need a dedicated error banner here.
    } finally {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  async function handleDelete(tool: HttpAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      await api.agents.httpTools.delete(agentId, tool.id);
      setTools((prev) => prev.filter((t) => t.id !== tool.id));
    } catch {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  if (formOpen) {
    return (
      <HttpToolFormModal
        open={true}
        onClose={() => { setFormOpen(false); setEditingTool(null); }}
        agentId={agentId}
        editingTool={editingTool}
        onSaved={refresh}
      />
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="Ferramentas HTTP">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente decide sozinho quando chamar cada ferramenta durante a conversa,
          com base na descrição que você escrever.
        </p>

        {gated && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/20">
            <Info className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
            <p className="text-xs text-nb-warning">
              Ferramentas HTTP não estão disponíveis no seu plano atual. Ferramentas já
              configuradas continuam aqui, mas não serão usadas pelo agente até o upgrade.
            </p>
          </div>
        )}

        {loading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => <div key={i} className="h-16 bg-nb-elevated rounded-xl animate-pulse" />)}
          </div>
        ) : loadError ? (
          <p className="text-sm text-nb-danger">{loadError}</p>
        ) : tools.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center border border-dashed border-nb-border rounded-xl">
            <Globe className="w-8 h-8 text-nb-muted mb-2" />
            <p className="text-sm font-medium text-nb-secondary mb-1">Nenhuma ferramenta HTTP ainda.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-start gap-3 p-3.5 bg-nb-panel rounded-xl border border-nb-border"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-medium text-nb-text font-mono">{tool.name}</span>
                    <span className="px-1.5 py-0.5 text-xs font-medium rounded-full bg-nb-elevated border border-nb-border text-nb-muted">
                      {tool.config.method}
                    </span>
                  </div>
                  <p className="text-xs text-nb-muted mt-0.5 truncate">{tool.description}</p>
                  <p className="text-xs text-nb-muted mt-0.5 truncate font-mono">{tool.config.url}</p>
                </div>
                {writeAllowed && (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {busy[tool.id] ? (
                      <Loader2 className="w-4 h-4 text-nb-muted animate-spin" />
                    ) : (
                      <>
                        <Toggle checked={tool.is_enabled} onChange={() => handleToggle(tool)} />
                        <button
                          type="button"
                          onClick={() => { setEditingTool(tool); setFormOpen(true); }}
                          className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(tool)}
                          className="p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {writeAllowed && !gated && (
          <button
            type="button"
            onClick={() => { setEditingTool(null); setFormOpen(true); }}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Nova ferramenta HTTP
          </button>
        )}
      </div>
    </Modal>
  );
}

// ── Request-human config modal ──────────────────────────────────────────────────

const DEFAULT_REQUEST_HUMAN_DESCRIPTION =
  "Aciona quando o cliente pedir para falar com um atendente, reclamar de forma " +
  "clara, pedir reembolso/cancelamento, ou perguntar algo que você não consegue " +
  "responder com segurança.";

function RequestHumanConfigModal({
  open,
  onClose,
  agentId,
  tool,
  readonly,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  tool: RequestHumanAgentTool | null;
  readonly: boolean;
}) {
  const [description, setDescription] = useState(DEFAULT_REQUEST_HUMAN_DESCRIPTION);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDescription(tool?.description || DEFAULT_REQUEST_HUMAN_DESCRIPTION);
    setError(null);
  }, [open, tool]);

  async function handleSave() {
    if (!description.trim()) {
      setError("Descreva quando o agente deve transferir para um humano.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (tool) {
        await api.agents.requestHumanTool.update(agentId, tool.id, {
          description: description.trim(),
          is_enabled: true,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "request_human",
          name: "solicitar_humano",
          description: description.trim(),
          config: {},
        };
        await api.agents.requestHumanTool.create(agentId, payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable() {
    if (!tool) return;
    setSaving(true);
    setError(null);
    try {
      await api.agents.requestHumanTool.update(agentId, tool.id, { is_enabled: false });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao desativar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Solicitar humano">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente decide sozinho quando transferir o atendimento para um humano, com base na
          descrição abaixo. A conversa fica com a IA pausada até alguém assumir, e a equipe
          recebe um e-mail avisando.
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Quando o agente deve transferir
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            disabled={readonly}
            className={inputCls}
          />
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {tool?.is_enabled ? (
            <button
              type="button"
              onClick={handleDisable}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando…" : tool ? "Salvar" : "Ativar"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Mark-resolved config modal ──────────────────────────────────────────────────

const DEFAULT_MARK_RESOLVED_DESCRIPTION =
  "Aciona quando o cliente confirma que seu problema foi resolvido, agradece e " +
  "encerra a conversa, ou a conversa chega a uma conclusão natural sem nada " +
  "pendente.";

function MarkResolvedConfigModal({
  open,
  onClose,
  agentId,
  tool,
  readonly,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  tool: MarkResolvedAgentTool | null;
  readonly: boolean;
}) {
  const [description, setDescription] = useState(DEFAULT_MARK_RESOLVED_DESCRIPTION);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDescription(tool?.description || DEFAULT_MARK_RESOLVED_DESCRIPTION);
    setError(null);
  }, [open, tool]);

  async function handleSave() {
    if (!description.trim()) {
      setError("Descreva quando o agente deve marcar a conversa como resolvida.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (tool) {
        await api.agents.markResolvedTool.update(agentId, tool.id, {
          description: description.trim(),
          is_enabled: true,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "mark_resolved",
          name: "marcar_resolvido",
          description: description.trim(),
          config: {},
        };
        await api.agents.markResolvedTool.create(agentId, payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable() {
    if (!tool) return;
    setSaving(true);
    setError(null);
    try {
      await api.agents.markResolvedTool.update(agentId, tool.id, { is_enabled: false });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao desativar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Marcar como resolvido">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente decide sozinho quando o atendimento chegou ao fim, com base na descrição
          abaixo. A conversa vira "Resolvida" com um resumo visível no Inbox — se o cliente
          escrever de novo, a conversa reabre e a IA volta a responder normalmente.
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Quando o agente deve marcar como resolvida
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            disabled={readonly}
            className={inputCls}
          />
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {tool?.is_enabled ? (
            <button
              type="button"
              onClick={handleDisable}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando…" : tool ? "Salvar" : "Ativar"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Capture-contact-data config modal ───────────────────────────────────────────

const DEFAULT_CAPTURE_CONTACT_DATA_DESCRIPTION =
  "Aciona sempre que o cliente informar espontaneamente um dos dados configurados " +
  "abaixo durante a conversa.";

function ContactFieldsEditor({
  fields,
  onChange,
  readonly,
}: {
  fields: ContactDataField[];
  onChange: (fields: ContactDataField[]) => void;
  readonly: boolean;
}) {
  return (
    <div className="space-y-3">
      {fields.map((field, i) => (
        <div key={i} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={field.key}
              disabled={readonly}
              onChange={(e) =>
                onChange(fields.map((f, j) => (
                  j === i ? { ...f, key: e.target.value.replace(/[^a-zA-Z0-9_]/g, "_") } : f
                )))
              }
              placeholder="chave_do_dado (ex: email)"
              className={`${inputCls} font-mono text-xs`}
            />
            {!readonly && (
              <button
                type="button"
                onClick={() => onChange(fields.filter((_, j) => j !== i))}
                className="flex-shrink-0 p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <input
            type="text"
            value={field.description}
            disabled={readonly}
            onChange={(e) =>
              onChange(fields.map((f, j) => (
                j === i ? { ...f, description: e.target.value } : f
              )))
            }
            placeholder="O que é esse dado, pro agente reconhecer (opcional)"
            className={`${inputCls} text-xs`}
          />
        </div>
      ))}
      {!readonly && fields.length < 5 && (
        <button
          type="button"
          onClick={() => onChange([...fields, { key: "", description: "" }])}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:underline"
        >
          <Plus className="w-3.5 h-3.5" /> Add dado
        </button>
      )}
    </div>
  );
}

function CaptureContactDataConfigModal({
  open,
  onClose,
  agentId,
  tool,
  readonly,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  tool: CaptureContactDataAgentTool | null;
  readonly: boolean;
}) {
  const [description, setDescription] = useState(DEFAULT_CAPTURE_CONTACT_DATA_DESCRIPTION);
  const [fields, setFields] = useState<ContactDataField[]>([{ key: "", description: "" }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDescription(tool?.description || DEFAULT_CAPTURE_CONTACT_DATA_DESCRIPTION);
    setFields(tool?.config.fields.length ? tool.config.fields : [{ key: "", description: "" }]);
    setError(null);
  }, [open, tool]);

  async function handleSave() {
    if (!description.trim()) {
      setError("Descreva quando o agente deve capturar dados do cliente.");
      return;
    }
    const cleanFields = fields
      .map((f) => ({ key: f.key.trim(), description: f.description.trim() }))
      .filter((f) => f.key.length > 0);
    if (cleanFields.length === 0) {
      setError("Adicione pelo menos um dado para o agente capturar.");
      return;
    }
    const keys = cleanFields.map((f) => f.key);
    if (new Set(keys).size !== keys.length) {
      setError("As chaves dos dados devem ser únicas.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (tool) {
        await api.agents.captureContactDataTool.update(agentId, tool.id, {
          description: description.trim(),
          config: { fields: cleanFields },
          is_enabled: true,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "capture_contact_data",
          name: "capturar_dados_contato",
          description: description.trim(),
          config: { fields: cleanFields },
        };
        await api.agents.captureContactDataTool.create(agentId, payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable() {
    if (!tool) return;
    setSaving(true);
    setError(null);
    try {
      await api.agents.captureContactDataTool.update(agentId, tool.id, { is_enabled: false });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao desativar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Capturar dados do cliente">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente identifica e salva automaticamente os dados abaixo assim que o cliente os
          informar na conversa — ficam disponíveis na ficha do contato, na aba Variáveis.
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Quando o agente deve capturar
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            disabled={readonly}
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Dados a capturar
          </label>
          <ContactFieldsEditor fields={fields} onChange={setFields} readonly={readonly} />
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {tool?.is_enabled ? (
            <button
              type="button"
              onClick={handleDisable}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando…" : tool ? "Salvar" : "Ativar"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Pipeline-action config modal ────────────────────────────────────────────────

const DEFAULT_PIPELINE_ACTION_DESCRIPTION =
  "Aciona quando a conversa avança para esta etapa do funil, com base no que o " +
  "cliente disse.";

function PipelineActionConfigModal({
  open,
  onClose,
  agentId,
  tool,
  readonly,
  gated,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  tool: PipelineActionAgentTool | null;
  readonly: boolean;
  gated: boolean;
}) {
  const [description, setDescription] = useState(DEFAULT_PIPELINE_ACTION_DESCRIPTION);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [pipelineId, setPipelineId] = useState("");
  const [stageId, setStageId] = useState("");
  const [loadingPipelines, setLoadingPipelines] = useState(true);
  const [loadingStages, setLoadingStages] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDescription(tool?.description || DEFAULT_PIPELINE_ACTION_DESCRIPTION);
    setPipelineId(tool?.config.pipeline_id || "");
    setStageId(tool?.config.stage_id || "");
    setError(null);
    setLoadingPipelines(true);
    api.pipelines
      .list()
      .then(setPipelines)
      .catch(() => setPipelines([]))
      .finally(() => setLoadingPipelines(false));
  }, [open, tool]);

  useEffect(() => {
    if (!pipelineId) {
      setStages([]);
      return;
    }
    setLoadingStages(true);
    api.pipelines.stages
      .list(pipelineId)
      .then(setStages)
      .catch(() => setStages([]))
      .finally(() => setLoadingStages(false));
  }, [pipelineId]);

  async function handleSave() {
    if (!description.trim()) {
      setError("Descreva quando o agente deve mover o card.");
      return;
    }
    if (!pipelineId || !stageId) {
      setError("Selecione o pipeline e a etapa de destino.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (tool) {
        await api.agents.pipelineActionTool.update(agentId, tool.id, {
          description: description.trim(),
          config: { pipeline_id: pipelineId, stage_id: stageId },
          is_enabled: true,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "pipeline_action",
          name: "mover_card_pipeline",
          description: description.trim(),
          config: { pipeline_id: pipelineId, stage_id: stageId },
        };
        await api.agents.pipelineActionTool.create(agentId, payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable() {
    if (!tool) return;
    setSaving(true);
    setError(null);
    try {
      await api.agents.pipelineActionTool.update(agentId, tool.id, { is_enabled: false });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao desativar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Mover card no pipeline">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente move o card desta conversa para a etapa escolhida abaixo, com base na
          descrição. Para o agente escolher entre etapas diferentes, crie uma ferramenta para
          cada destino.
        </p>

        {gated ? (
          <div className="flex items-center gap-2 p-3 bg-nb-elevated rounded-xl border border-nb-border">
            <PlanGateBadge label={minPlanLabel("pipelines")} variant="premium" size="xs" />
            <p className="text-xs text-nb-muted">Disponível nos planos superiores.</p>
          </div>
        ) : (
          <>
            <div>
              <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                Quando o agente deve mover o card
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                disabled={readonly}
                className={inputCls}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Pipeline
                </label>
                <select
                  value={pipelineId}
                  disabled={readonly || loadingPipelines}
                  onChange={(e) => {
                    setPipelineId(e.target.value);
                    setStageId("");
                  }}
                  className={inputCls}
                >
                  <option value="">Selecione…</option>
                  {pipelines.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Etapa de destino
                </label>
                <select
                  value={stageId}
                  disabled={readonly || !pipelineId || loadingStages}
                  onChange={(e) => setStageId(e.target.value)}
                  className={inputCls}
                >
                  <option value="">Selecione…</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
          </>
        )}

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {tool?.is_enabled ? (
            <button
              type="button"
              onClick={handleDisable}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            {!gated && (
              <button
                type="button"
                onClick={handleSave}
                disabled={saving || readonly}
                className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
              >
                {saving ? "Salvando…" : tool ? "Salvar" : "Ativar"}
              </button>
            )}
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Assign-operator config modal ────────────────────────────────────────────────

const DEFAULT_ASSIGN_OPERATOR_DESCRIPTION =
  "Aciona quando o cliente precisa falar especificamente com este operador, com " +
  "base no assunto tratado na conversa.";

function AssignOperatorConfigModal({
  open,
  onClose,
  agentId,
  tool,
  readonly,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  tool: AssignOperatorAgentTool | null;
  readonly: boolean;
}) {
  const [description, setDescription] = useState(DEFAULT_ASSIGN_OPERATOR_DESCRIPTION);
  const [members, setMembers] = useState<Member[]>([]);
  const [userId, setUserId] = useState("");
  const [loadingMembers, setLoadingMembers] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setDescription(tool?.description || DEFAULT_ASSIGN_OPERATOR_DESCRIPTION);
    setUserId(tool?.config.user_id || "");
    setError(null);
    setLoadingMembers(true);
    api.members
      .list()
      .then((data) => setMembers(data.filter((m) => m.status === "active")))
      .catch(() => setMembers([]))
      .finally(() => setLoadingMembers(false));
  }, [open, tool]);

  async function handleSave() {
    if (!description.trim()) {
      setError("Descreva quando o agente deve atribuir a este operador.");
      return;
    }
    if (!userId) {
      setError("Selecione o operador responsável.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (tool) {
        await api.agents.assignOperatorTool.update(agentId, tool.id, {
          description: description.trim(),
          config: { user_id: userId },
          is_enabled: true,
        });
      } else {
        const payload: AgentToolCreateInput = {
          tool_type: "assign_operator",
          name: "atribuir_operador",
          description: description.trim(),
          config: { user_id: userId },
        };
        await api.agents.assignOperatorTool.create(agentId, payload);
      }
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable() {
    if (!tool) return;
    setSaving(true);
    setError(null);
    try {
      await api.agents.assignOperatorTool.update(agentId, tool.id, { is_enabled: false });
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao desativar ferramenta.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Atribuir a um operador">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente atribui o atendimento a este operador específico e pausa as respostas
          automáticas — a equipe recebe um e-mail avisando. Para o agente escolher entre
          operadores diferentes, crie uma ferramenta para cada um.
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Quando o agente deve atribuir
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            disabled={readonly}
            className={inputCls}
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Operador responsável
          </label>
          <select
            value={userId}
            disabled={readonly || loadingMembers}
            onChange={(e) => setUserId(e.target.value)}
            className={inputCls}
          >
            <option value="">Selecione…</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>{m.name || m.email}</option>
            ))}
          </select>
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {tool?.is_enabled ? (
            <button
              type="button"
              onClick={handleDisable}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando…" : tool ? "Salvar" : "Ativar"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Pipeline-action list modal ──────────────────────────────────────────────────
//
// Unlike Solicitar Humano/Marcar Resolvido/Capturar Dado (one instance per
// agent), an agent can want to move cards to several different destination
// stages — each needs its own instance (fixed pipeline+stage+trigger
// description). Same "list + form" pattern as HttpToolsListModal, reusing
// PipelineActionConfigModal unchanged as the create/edit form.

function PipelineActionListModal({
  open,
  onClose,
  agentId,
  role,
  gated,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  role: MemberRole | null;
  gated: boolean;
}) {
  const [tools, setTools] = useState<PipelineActionAgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<PipelineActionAgentTool | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const writeAllowed = canWrite(role);

  function refresh() {
    setLoading(true);
    setLoadError(null);
    api.agents.httpTools
      .list(agentId)
      .then((all) =>
        setTools(all.filter((t): t is PipelineActionAgentTool => t.tool_type === "pipeline_action"))
      )
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar regras."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) refresh();
  }, [open, agentId]);

  async function handleToggle(tool: PipelineActionAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      const updated = await api.agents.pipelineActionTool.update(agentId, tool.id, {
        is_enabled: !tool.is_enabled,
      });
      setTools((prev) => prev.map((t) => (t.id === tool.id ? (updated as PipelineActionAgentTool) : t)));
    } catch {
      // Toggle failure is surfaced by the row staying unchanged — same as HttpToolsListModal.
    } finally {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  async function handleDelete(tool: PipelineActionAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      await api.agents.pipelineActionTool.delete(agentId, tool.id);
      setTools((prev) => prev.filter((t) => t.id !== tool.id));
    } catch {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  if (formOpen) {
    return (
      <PipelineActionConfigModal
        open={true}
        onClose={() => { setFormOpen(false); setEditingTool(null); refresh(); }}
        agentId={agentId}
        tool={editingTool}
        readonly={!writeAllowed}
        gated={gated}
      />
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="Mover card no pipeline">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente decide sozinho quando mover o card, com base na descrição de cada regra. Crie
          uma regra por etapa de destino — cada uma pode apontar pra um pipeline/etapa diferente.
        </p>

        {gated && (
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/20">
            <Info className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
            <p className="text-xs text-nb-warning">
              Mover card no pipeline não está disponível no seu plano atual. Regras já
              configuradas continuam aqui, mas não serão usadas pelo agente até o upgrade.
            </p>
          </div>
        )}

        {loading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => <div key={i} className="h-16 bg-nb-elevated rounded-xl animate-pulse" />)}
          </div>
        ) : loadError ? (
          <p className="text-sm text-nb-danger">{loadError}</p>
        ) : tools.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center border border-dashed border-nb-border rounded-xl">
            <Kanban className="w-8 h-8 text-nb-muted mb-2" />
            <p className="text-sm font-medium text-nb-secondary mb-1">Nenhuma regra ainda.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-start gap-3 p-3.5 bg-nb-panel rounded-xl border border-nb-border"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-nb-text font-mono">{tool.name}</span>
                  <p className="text-xs text-nb-muted mt-0.5 truncate">{tool.description}</p>
                </div>
                {writeAllowed && (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {busy[tool.id] ? (
                      <Loader2 className="w-4 h-4 text-nb-muted animate-spin" />
                    ) : (
                      <>
                        <Toggle checked={tool.is_enabled} onChange={() => handleToggle(tool)} />
                        <button
                          type="button"
                          onClick={() => { setEditingTool(tool); setFormOpen(true); }}
                          className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(tool)}
                          className="p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {writeAllowed && !gated && (
          <button
            type="button"
            onClick={() => { setEditingTool(null); setFormOpen(true); }}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Nova regra
          </button>
        )}
      </div>
    </Modal>
  );
}

// ── Assign-operator list modal ──────────────────────────────────────────────────
//
// Same "one instance per destination" rationale as PipelineActionListModal —
// a distinct operator per instance (e.g. "atribuir_financeiro",
// "atribuir_juridico"). Reuses AssignOperatorConfigModal unchanged as the
// create/edit form. No plan gate (assign_operator is ungated).

function AssignOperatorListModal({
  open,
  onClose,
  agentId,
  role,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  role: MemberRole | null;
}) {
  const [tools, setTools] = useState<AssignOperatorAgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<AssignOperatorAgentTool | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const writeAllowed = canWrite(role);

  function refresh() {
    setLoading(true);
    setLoadError(null);
    api.agents.httpTools
      .list(agentId)
      .then((all) =>
        setTools(all.filter((t): t is AssignOperatorAgentTool => t.tool_type === "assign_operator"))
      )
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar operadores."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) refresh();
  }, [open, agentId]);

  async function handleToggle(tool: AssignOperatorAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      const updated = await api.agents.assignOperatorTool.update(agentId, tool.id, {
        is_enabled: !tool.is_enabled,
      });
      setTools((prev) => prev.map((t) => (t.id === tool.id ? (updated as AssignOperatorAgentTool) : t)));
    } catch {
      // Toggle failure is surfaced by the row staying unchanged — same as HttpToolsListModal.
    } finally {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  async function handleDelete(tool: AssignOperatorAgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      await api.agents.assignOperatorTool.delete(agentId, tool.id);
      setTools((prev) => prev.filter((t) => t.id !== tool.id));
    } catch {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  if (formOpen) {
    return (
      <AssignOperatorConfigModal
        open={true}
        onClose={() => { setFormOpen(false); setEditingTool(null); refresh(); }}
        agentId={agentId}
        tool={editingTool}
        readonly={!writeAllowed}
      />
    );
  }

  return (
    <Modal open={open} onClose={onClose} title="Atribuir a um operador">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          O agente decide sozinho a quem atribuir, com base na descrição de cada regra. Crie uma
          regra por operador — cada uma aponta pra uma pessoa fixa do time.
        </p>

        {loading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => <div key={i} className="h-16 bg-nb-elevated rounded-xl animate-pulse" />)}
          </div>
        ) : loadError ? (
          <p className="text-sm text-nb-danger">{loadError}</p>
        ) : tools.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center border border-dashed border-nb-border rounded-xl">
            <UserCheck className="w-8 h-8 text-nb-muted mb-2" />
            <p className="text-sm font-medium text-nb-secondary mb-1">Nenhum operador ainda.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {tools.map((tool) => (
              <div
                key={tool.id}
                className="flex items-start gap-3 p-3.5 bg-nb-panel rounded-xl border border-nb-border"
              >
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-nb-text font-mono">{tool.name}</span>
                  <p className="text-xs text-nb-muted mt-0.5 truncate">{tool.description}</p>
                </div>
                {writeAllowed && (
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    {busy[tool.id] ? (
                      <Loader2 className="w-4 h-4 text-nb-muted animate-spin" />
                    ) : (
                      <>
                        <Toggle checked={tool.is_enabled} onChange={() => handleToggle(tool)} />
                        <button
                          type="button"
                          onClick={() => { setEditingTool(tool); setFormOpen(true); }}
                          className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(tool)}
                          className="p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {writeAllowed && (
          <button
            type="button"
            onClick={() => { setEditingTool(null); setFormOpen(true); }}
            className="w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Novo operador
          </button>
        )}
      </div>
    </Modal>
  );
}

// ── Follow-up config modal ──────────────────────────────────────────────────────

type FollowUpStepDraft = {
  delay_hours: number;
  // "" means no per-step instruction — falls back to the general one (or none).
  custom_instructions: string;
};

function FollowUpStepsEditor({
  steps,
  onChange,
  readonly,
}: {
  steps: FollowUpStepDraft[];
  onChange: (steps: FollowUpStepDraft[]) => void;
  readonly: boolean;
}) {
  return (
    <div className="space-y-3">
      {steps.map((step, i) => (
        <div key={i} className="p-2.5 bg-nb-panel rounded-xl border border-nb-border space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-xs text-nb-muted w-20 flex-shrink-0">
              Follow-up #{i + 1}
            </span>
            <input
              type="number"
              min={1}
              max={500}
              value={step.delay_hours}
              disabled={readonly}
              onChange={(e) =>
                onChange(steps.map((s, j) => (
                  j === i ? { ...s, delay_hours: Number(e.target.value) } : s
                )))
              }
              className={`${inputCls} w-24`}
            />
            <span className="text-xs text-nb-muted">horas de silêncio</span>
            {!readonly && (
              <button
                type="button"
                onClick={() => onChange(steps.filter((_, j) => j !== i))}
                className="ml-auto p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <input
            type="text"
            value={step.custom_instructions}
            disabled={readonly}
            onChange={(e) =>
              onChange(steps.map((s, j) => (
                j === i ? { ...s, custom_instructions: e.target.value } : s
              )))
            }
            placeholder="Instrução específica deste degrau (opcional — sem ela, usa só a geral abaixo)"
            className={`${inputCls} text-xs`}
          />
        </div>
      ))}
      {!readonly && steps.length < 5 && (
        <button
          type="button"
          onClick={() => onChange([
            ...steps,
            { delay_hours: (steps[steps.length - 1]?.delay_hours ?? 0) + 6, custom_instructions: "" },
          ])}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:underline"
        >
          <Plus className="w-3.5 h-3.5" /> Add degrau
        </button>
      )}
    </div>
  );
}

function FollowUpConfigModal({
  open,
  onClose,
  agentId,
  settings,
  readonly,
  onSaved,
}: {
  open: boolean;
  onClose: () => void;
  agentId: string;
  settings: AgentFollowUpSettings | null;
  readonly: boolean;
  onSaved: (updated: AgentFollowUpSettings) => void;
}) {
  const [customInstructions, setCustomInstructions] = useState("");
  const [steps, setSteps] = useState<FollowUpStepDraft[]>([
    { delay_hours: 6, custom_instructions: "" },
    { delay_hours: 24, custom_instructions: "" },
    { delay_hours: 72, custom_instructions: "" },
  ]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setCustomInstructions(settings?.custom_instructions || "");
    setSteps(
      settings && settings.steps.length > 0
        ? settings.steps.map((s) => ({
            delay_hours: s.delay_hours,
            custom_instructions: s.custom_instructions || "",
          }))
        : [
            { delay_hours: 6, custom_instructions: "" },
            { delay_hours: 24, custom_instructions: "" },
            { delay_hours: 72, custom_instructions: "" },
          ]
    );
    setError(null);
  }, [open, settings]);

  async function handleSave(nextEnabled: boolean) {
    setError(null);
    const hours = steps.map((s) => s.delay_hours);
    if (nextEnabled) {
      const sorted = [...hours].sort((a, b) => a - b);
      if (hours.some((h, i) => h !== sorted[i]) || new Set(hours).size !== hours.length) {
        setError("Os prazos dos degraus devem ser crescentes e sem repetição (ex: 6, 24, 72).");
        return;
      }
      if (steps.length === 0) {
        setError("Configure ao menos um degrau para ativar.");
        return;
      }
    }
    setSaving(true);
    try {
      const updated = await api.agents.followUp.update(agentId, {
        is_enabled: nextEnabled,
        custom_instructions: customInstructions.trim() || null,
        steps: steps.map((s) => ({
          delay_hours: s.delay_hours,
          custom_instructions: s.custom_instructions.trim() || null,
        })),
      });
      onSaved(updated);
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Erro ao salvar follow-up.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Follow-up automático">
      <div className="space-y-4">
        <p className="text-xs text-nb-muted leading-relaxed">
          Quando o cliente para de responder, o agente manda mensagens de reengajamento nos
          prazos configurados abaixo. Para de mandar sozinho assim que o cliente responder.
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Degraus (prazos crescentes desde a última mensagem do cliente)
          </label>
          <FollowUpStepsEditor steps={steps} onChange={setSteps} readonly={readonly} />
        </div>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Instrução geral de tom (opcional, vale para todos os degraus)
          </label>
          <textarea
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value)}
            placeholder="Ex: Nunca seja insistente, sempre deixe a porta aberta pro cliente voltar."
            rows={3}
            disabled={readonly}
            className={inputCls}
          />
          <p className="text-xs text-nb-muted mt-1">
            A IA já sabe qual degrau é e há quanto tempo o cliente está em silêncio — esse campo
            e o de cada degrau acima são só pra guiar o tom/conteúdo quando você quiser.
          </p>
        </div>

        {error && <p className="text-xs text-nb-danger">{error}</p>}

        <div className="flex justify-between gap-2 pt-2 border-t border-nb-border">
          {settings?.is_enabled ? (
            <button
              type="button"
              onClick={() => handleSave(false)}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors disabled:opacity-50"
            >
              Desativar
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => handleSave(true)}
              disabled={saving || readonly}
              className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors disabled:opacity-50"
            >
              {saving ? "Salvando…" : settings?.is_enabled ? "Salvar" : "Ativar"}
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigFerramentas({
  agentId,
  readonly,
  role,
  planCode,
}: {
  agentId: string;
  readonly: boolean;
  role: MemberRole | null;
  planCode: string | null;
}) {
  const httpToolsGated = planCode !== null && !planAllowsFeature(planCode, "http_tools");
  const followUpGated = planCode !== null && !planAllowsFeature(planCode, "follow_up");
  const pipelinesGated = planCode !== null && !planAllowsFeature(planCode, "pipelines");
  // KB state (for active tools display)
  const [kbList, setKbList] = useState<AgentKnowledgeBase[]>([]);
  const [kbLoading, setKbLoading] = useState(true);
  const [kbError, setKbError] = useState(false);
  const [kbModalOpen, setKbModalOpen] = useState(false);

  // Catalog state (for active tools display)
  const [catalogScope, setCatalogScope] = useState<AgentCatalogScope | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogModalOpen, setCatalogModalOpen] = useState(false);

  // Agent Tools state — one list call covers every tool_type (http_request,
  // request_human, mark_resolved); the sections below derive their own slice from it.
  const [httpToolsList, setHttpToolsList] = useState<AgentTool[]>([]);
  const [httpToolsLoading, setHttpToolsLoading] = useState(true);
  const [httpToolsModalOpen, setHttpToolsModalOpen] = useState(false);
  const [requestHumanModalOpen, setRequestHumanModalOpen] = useState(false);
  const [markResolvedModalOpen, setMarkResolvedModalOpen] = useState(false);
  const [captureContactDataModalOpen, setCaptureContactDataModalOpen] = useState(false);
  const [pipelineActionModalOpen, setPipelineActionModalOpen] = useState(false);
  const [assignOperatorModalOpen, setAssignOperatorModalOpen] = useState(false);

  // Follow-up state
  const [followUpSettings, setFollowUpSettings] = useState<AgentFollowUpSettings | null>(null);
  const [followUpLoading, setFollowUpLoading] = useState(true);
  const [followUpModalOpen, setFollowUpModalOpen] = useState(false);

  useEffect(() => {
    api.agents.followUp
      .get(agentId)
      .then(setFollowUpSettings)
      .catch(() => setFollowUpSettings(null))
      .finally(() => setFollowUpLoading(false));
  }, [agentId]);

  function refreshAgentTools() {
    setHttpToolsLoading(true);
    return api.agents.httpTools
      .list(agentId)
      .then(setHttpToolsList)
      .catch(() => setHttpToolsList([]))
      .finally(() => setHttpToolsLoading(false));
  }

  useEffect(() => {
    refreshAgentTools();
  }, [agentId]);

  function handleHttpToolsModalClose() {
    setHttpToolsModalOpen(false);
    refreshAgentTools();
  }

  function handleRequestHumanModalClose() {
    setRequestHumanModalOpen(false);
    refreshAgentTools();
  }

  function handleMarkResolvedModalClose() {
    setMarkResolvedModalOpen(false);
    refreshAgentTools();
  }

  function handleCaptureContactDataModalClose() {
    setCaptureContactDataModalOpen(false);
    refreshAgentTools();
  }

  function handlePipelineActionModalClose() {
    setPipelineActionModalOpen(false);
    refreshAgentTools();
  }

  function handleAssignOperatorModalClose() {
    setAssignOperatorModalOpen(false);
    refreshAgentTools();
  }

  useEffect(() => {
    api.agents.knowledgeBases
      .list(agentId)
      .then((data) => setKbList(data.filter((kb) => kb.is_active)))
      .catch(() => setKbError(true))
      .finally(() => setKbLoading(false));
  }, [agentId]);

  useEffect(() => {
    api.agents.catalogScope
      .get(agentId)
      .then(setCatalogScope)
      .catch(() => setCatalogScope(null))
      .finally(() => setCatalogLoading(false));
  }, [agentId]);

  // Refresh KB list after modal closes
  function handleKbModalClose() {
    setKbModalOpen(false);
    setKbLoading(true);
    api.agents.knowledgeBases
      .list(agentId)
      .then((data) => setKbList(data.filter((kb) => kb.is_active)))
      .catch(() => setKbError(true))
      .finally(() => setKbLoading(false));
  }

  // Refresh catalog scope after modal closes
  function handleCatalogModalClose() {
    setCatalogModalOpen(false);
    api.agents.catalogScope
      .get(agentId)
      .then(setCatalogScope)
      .catch(() => {});
  }

  const kbActive = !kbLoading && !kbError && kbList.length > 0;
  const catalogActive = !catalogLoading && catalogScope?.catalog_enabled === true;
  const enabledHttpTools = httpToolsList.filter(
    (t): t is HttpAgentTool => t.tool_type === "http_request" && t.is_enabled
  );
  const httpToolsActive = !httpToolsLoading && enabledHttpTools.length > 0;

  const requestHumanTool = httpToolsList.find(
    (t): t is RequestHumanAgentTool => t.tool_type === "request_human"
  );
  const requestHumanActive = !httpToolsLoading && requestHumanTool?.is_enabled === true;

  const markResolvedTool = httpToolsList.find(
    (t): t is MarkResolvedAgentTool => t.tool_type === "mark_resolved"
  );
  const markResolvedActive = !httpToolsLoading && markResolvedTool?.is_enabled === true;

  const captureContactDataTool = httpToolsList.find(
    (t): t is CaptureContactDataAgentTool => t.tool_type === "capture_contact_data"
  );
  const captureContactDataActive =
    !httpToolsLoading && captureContactDataTool?.is_enabled === true;

  // Unlike request_human/mark_resolved/capture_contact_data (one instance per
  // agent), pipeline_action and assign_operator support multiple instances —
  // one per destination stage / target operator, same pattern as HTTP tools.
  const pipelineActionTools = httpToolsList.filter(
    (t): t is PipelineActionAgentTool => t.tool_type === "pipeline_action"
  );
  const enabledPipelineActionTools = pipelineActionTools.filter((t) => t.is_enabled);
  const pipelineActionActive = !httpToolsLoading && enabledPipelineActionTools.length > 0;

  const assignOperatorTools = httpToolsList.filter(
    (t): t is AssignOperatorAgentTool => t.tool_type === "assign_operator"
  );
  const enabledAssignOperatorTools = assignOperatorTools.filter((t) => t.is_enabled);
  const assignOperatorActive = !httpToolsLoading && enabledAssignOperatorTools.length > 0;

  const followUpActive = !followUpLoading && followUpSettings?.is_enabled === true;

  const activeTools: React.ReactNode[] = [];

  if (kbActive) {
    activeTools.push(
      <div key="kb" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Base de Conhecimento</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">
            {kbList.length === 1 ? "1 base conectada" : `${kbList.length} bases conectadas`}
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {kbList.map((kb) => (
              <li key={kb.id} className="flex items-center gap-2 text-xs text-nb-muted">
                <span className="w-1.5 h-1.5 rounded-full bg-nb-success shrink-0" />
                {kb.knowledge_base_name}
              </li>
            ))}
          </ul>
        </div>
        <button
          type="button"
          onClick={() => setKbModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (catalogActive && catalogScope) {
    const scopeLabel =
      catalogScope.category_scope === "all"
        ? "Todo o Catálogo"
        : `${catalogScope.category_ids.length} ${
            catalogScope.category_ids.length === 1 ? "categoria selecionada" : "categorias selecionadas"
          }`;

    activeTools.push(
      <div key="catalog" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <ShoppingBag className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Catálogo</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativo
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">Escopo: {scopeLabel}</p>
        </div>
        <button
          type="button"
          onClick={() => setCatalogModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (httpToolsActive) {
    activeTools.push(
      <div key="http-tools" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Globe className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Ferramentas HTTP</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">
            {enabledHttpTools.length === 1
              ? "1 ferramenta configurada"
              : `${enabledHttpTools.length} ferramentas configuradas`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setHttpToolsModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (requestHumanActive) {
    activeTools.push(
      <div key="request-human" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Hand className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Solicitar humano</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5 line-clamp-1">
            {requestHumanTool?.description}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setRequestHumanModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (markResolvedActive) {
    activeTools.push(
      <div key="mark-resolved" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Check className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Marcar como resolvido</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5 line-clamp-1">
            {markResolvedTool?.description}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setMarkResolvedModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (captureContactDataActive) {
    activeTools.push(
      <div key="capture-contact-data" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <ClipboardList className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Capturar dados do cliente</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">
            {captureContactDataTool?.config.fields.length === 1
              ? "1 dado configurado"
              : `${captureContactDataTool?.config.fields.length ?? 0} dados configurados`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setCaptureContactDataModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (pipelineActionActive) {
    activeTools.push(
      <div key="pipeline-action" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Kanban className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Mover card no pipeline</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">
            {enabledPipelineActionTools.length === 1
              ? "1 regra configurada"
              : `${enabledPipelineActionTools.length} regras configuradas`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setPipelineActionModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (assignOperatorActive) {
    activeTools.push(
      <div key="assign-operator" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <UserCheck className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Atribuir a um operador</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">
            {enabledAssignOperatorTools.length === 1
              ? "1 operador configurado"
              : `${enabledAssignOperatorTools.length} operadores configurados`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setAssignOperatorModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  if (followUpActive) {
    const stepsLabel = followUpSettings
      ? followUpSettings.steps.map((s) => `${s.delay_hours}h`).join(" → ")
      : "";
    activeTools.push(
      <div key="follow-up" className="bg-nb-panel rounded-2xl border border-nb-primary/20 p-4 flex items-start gap-4">
        <div className="w-9 h-9 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <Zap className="w-4 h-4 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text">Follow-up</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
              Ativa
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-0.5">{stepsLabel}</p>
        </div>
        <button
          type="button"
          onClick={() => setFollowUpModalOpen(true)}
          className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
        >
          <Settings2 className="w-3.5 h-3.5" />
          Configurar
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="text-base font-semibold text-nb-text">Ferramentas</h2>
        <p className="text-sm text-nb-muted mt-1 max-w-xl">
          Dê capacidades operacionais ao seu agente para consultar informações, usar o Catálogo e
          executar ações durante o atendimento.
        </p>
      </div>

      {/* ── Ferramentas ativas ──────────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">
            Ferramentas ativas
          </p>
          {activeTools.length > 0 && (
            <span className="px-2 py-0.5 text-xs font-semibold rounded-full bg-nb-primary/10 text-nb-primary border border-nb-primary/20">
              {activeTools.length}
            </span>
          )}
        </div>

        {kbLoading || catalogLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-20 rounded-2xl bg-nb-elevated animate-pulse" />
            ))}
          </div>
        ) : activeTools.length > 0 ? (
          <div className="flex flex-col gap-3">{activeTools}</div>
        ) : (
          <div className="flex flex-col items-center py-10 text-center border border-dashed border-nb-border rounded-2xl">
            <Zap className="w-8 h-8 text-nb-muted mb-2" />
            <p className="text-sm font-medium text-nb-secondary mb-1">Nenhuma ferramenta ativa.</p>
            <p className="text-xs text-nb-muted">
              Adicione uma ferramenta para dar novas capacidades operacionais ao agente.
            </p>
          </div>
        )}
      </div>

      {/* ── Ferramentas disponíveis ─────────────────────────────────────────── */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">
          Ferramentas disponíveis
        </p>
        <div className="flex flex-col gap-3">

          {/* Knowledge Base — só mostra se não está ativo */}
          {!kbActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <BookOpen className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Base de Conhecimento</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Permite que o agente consulte documentos, perguntas frequentes e informações da empresa
                para responder com mais precisão.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly}
              onClick={() => setKbModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {kbActive ? (
                <><Settings2 className="w-3.5 h-3.5" /> Configurar</>
              ) : (
                <><Plus className="w-3.5 h-3.5" /> Adicionar</>
              )}
            </button>
          </div>}

          {/* Catalog — só mostra se não está ativo */}
          {!catalogActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <ShoppingBag className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Catálogo</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Permite que o agente consulte produtos, serviços, planos e ofertas cadastradas para
                recomendar opções durante o atendimento.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || catalogLoading}
              onClick={() => setCatalogModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {catalogActive ? (
                <><Settings2 className="w-3.5 h-3.5" /> Configurar</>
              ) : (
                <><Plus className="w-3.5 h-3.5" /> Adicionar</>
              )}
            </button>
          </div>}

          {/* HTTP Tools — só mostra se não está ativo */}
          {!httpToolsActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <Globe className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold text-nb-text">Ferramentas HTTP</h3>
                {httpToolsGated && (
                  <PlanGateBadge label={minPlanLabel("http_tools")} variant="premium" size="xs" />
                )}
              </div>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                {httpToolsGated
                  ? "Disponível nos planos superiores. Faça upgrade para dar ao agente a capacidade de chamar APIs externas."
                  : "Execute chamadas HTTP para APIs externas durante o atendimento — o agente decide sozinho quando usar cada uma."}
              </p>
            </div>
            {!httpToolsGated && (
              <button
                type="button"
                disabled={readonly || httpToolsLoading}
                onClick={() => setHttpToolsModalOpen(true)}
                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="w-3.5 h-3.5" /> Adicionar
              </button>
            )}
          </div>}

          {/* Solicitar humano — só mostra se não está ativo */}
          {!requestHumanActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <Hand className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Solicitar humano</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Permite que o agente transfira o atendimento para um operador humano quando
                decidir que é necessário — disponível em todos os planos.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || httpToolsLoading}
              onClick={() => setRequestHumanModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" /> Adicionar
            </button>
          </div>}

          {/* Follow-up — só mostra se não está ativo */}
          {!followUpActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <Zap className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold text-nb-text">Follow-up</h3>
                {followUpGated && (
                  <PlanGateBadge label={minPlanLabel("follow_up")} variant="premium" size="xs" />
                )}
              </div>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                {followUpGated
                  ? "Disponível nos planos superiores. Faça upgrade para reengajar clientes automaticamente após silêncio."
                  : "Envie mensagens de acompanhamento automáticas quando o cliente parar de responder."}
              </p>
            </div>
            {!followUpGated && (
              <button
                type="button"
                disabled={readonly || followUpLoading}
                onClick={() => setFollowUpModalOpen(true)}
                className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Plus className="w-3.5 h-3.5" /> Adicionar
              </button>
            )}
          </div>}

          {/* Marcar como resolvido — só mostra se não está ativo */}
          {!markResolvedActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <Check className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Marcar como resolvido</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Permita que o agente encerre conversas automaticamente quando resolvidas —
                disponível em todos os planos.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || httpToolsLoading}
              onClick={() => setMarkResolvedModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" /> Adicionar
            </button>
          </div>}

          {/* Capturar dados do cliente — só mostra se não está ativo */}
          {!captureContactDataActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <ClipboardList className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Capturar dados do cliente</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Salva automaticamente dados como e-mail, empresa ou CPF assim que o cliente os
                informa na conversa — disponível em todos os planos.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || httpToolsLoading}
              onClick={() => setCaptureContactDataModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" /> Adicionar
            </button>
          </div>}

          {/* Mover card no pipeline — só mostra se não está ativo */}
          {!pipelineActionActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <Kanban className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-sm font-semibold text-nb-text">Mover card no pipeline</h3>
                {pipelinesGated && (
                  <PlanGateBadge label={minPlanLabel("pipelines")} variant="premium" size="xs" />
                )}
              </div>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                {pipelinesGated
                  ? "Disponível nos planos superiores. Faça upgrade para dar ao agente a capacidade de mover cards no pipeline."
                  : "Move o card desta conversa para uma etapa do pipeline quando o agente decidir que é hora."}
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || httpToolsLoading}
              onClick={() => setPipelineActionModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" /> Adicionar
            </button>
          </div>}

          {/* Atribuir a um operador — só mostra se não está ativo */}
          {!assignOperatorActive && <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-4">
            <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
              <UserCheck className="w-4 h-4 text-nb-muted" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="text-sm font-semibold text-nb-text">Atribuir a um operador</h3>
              <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                Atribui o atendimento a um membro específico da equipe e pausa as respostas
                automáticas — disponível em todos os planos.
              </p>
            </div>
            <button
              type="button"
              disabled={readonly || httpToolsLoading}
              onClick={() => setAssignOperatorModalOpen(true)}
              className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="w-3.5 h-3.5" /> Adicionar
            </button>
          </div>}
        </div>
      </div>

      {/* Modals */}
      <KbConfigModal
        open={kbModalOpen}
        onClose={handleKbModalClose}
        agentId={agentId}
        role={role}
      />
      <CatalogConfigModal
        open={catalogModalOpen}
        onClose={handleCatalogModalClose}
        agentId={agentId}
        readonly={readonly}
      />
      <HttpToolsListModal
        open={httpToolsModalOpen}
        onClose={handleHttpToolsModalClose}
        agentId={agentId}
        role={role}
        gated={httpToolsGated}
      />
      <RequestHumanConfigModal
        open={requestHumanModalOpen}
        onClose={handleRequestHumanModalClose}
        agentId={agentId}
        tool={requestHumanTool ?? null}
        readonly={readonly}
      />
      <MarkResolvedConfigModal
        open={markResolvedModalOpen}
        onClose={handleMarkResolvedModalClose}
        agentId={agentId}
        tool={markResolvedTool ?? null}
        readonly={readonly}
      />
      <CaptureContactDataConfigModal
        open={captureContactDataModalOpen}
        onClose={handleCaptureContactDataModalClose}
        agentId={agentId}
        tool={captureContactDataTool ?? null}
        readonly={readonly}
      />
      <PipelineActionListModal
        open={pipelineActionModalOpen}
        onClose={handlePipelineActionModalClose}
        agentId={agentId}
        role={role}
        gated={pipelinesGated}
      />
      <AssignOperatorListModal
        open={assignOperatorModalOpen}
        onClose={handleAssignOperatorModalClose}
        agentId={agentId}
        role={role}
      />
      <FollowUpConfigModal
        open={followUpModalOpen}
        onClose={() => setFollowUpModalOpen(false)}
        agentId={agentId}
        settings={followUpSettings}
        readonly={readonly}
        onSaved={setFollowUpSettings}
      />
    </div>
  );
}
