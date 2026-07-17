"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  BookOpen,
  Check,
  Clock,
  Globe,
  Hand,
  Info,
  Loader2,
  Minus,
  Pencil,
  Plus,
  Settings2,
  ShoppingBag,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  AgentCatalogScope,
  AgentKnowledgeBase,
  AgentTool,
  AgentToolCreateInput,
  CatalogCategory,
  HttpToolConfig,
  KnowledgeBase,
  MemberRole,
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
  editingTool: AgentTool | null;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [method, setMethod] = useState<HttpToolConfig["method"]>("GET");
  const [url, setUrl] = useState("");
  const [headersText, setHeadersText] = useState("{}");
  const [timeoutSeconds, setTimeoutSeconds] = useState(8);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    if (editingTool) {
      setName(editingTool.name);
      setDescription(editingTool.description);
      setMethod(editingTool.config.method);
      setUrl(editingTool.config.url);
      setHeadersText(JSON.stringify(editingTool.config.headers || {}, null, 2));
      setTimeoutSeconds(editingTool.config.timeout_seconds);
    } else {
      setName("");
      setDescription("");
      setMethod("GET");
      setUrl("");
      setHeadersText("{}");
      setTimeoutSeconds(8);
    }
    setError(null);
  }, [open, editingTool]);

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

    let headers: Record<string, string>;
    try {
      headers = headersText.trim() ? JSON.parse(headersText) : {};
    } catch {
      setError("Cabeçalhos devem ser um JSON válido, ex: {\"Authorization\": \"Bearer ...\"}.");
      return;
    }

    const config: HttpToolConfig = { method, url: url.trim(), headers, timeout_seconds: timeoutSeconds };

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
            Quando o agente deve usar (descrição curta)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Consulta um CEP e retorna o endereço correspondente."
            rows={2}
            className={inputCls}
          />
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
              className={inputCls}
            />
          </div>
        </div>
        <p className="text-xs text-nb-muted -mt-2">
          Use <code className="font-mono">{"{variavel}"}</code> na URL pra partes dinâmicas — o
          agente preenche na hora de chamar (ex: <code className="font-mono">{"{cep}"}</code>).
        </p>

        <div>
          <label className="block text-xs font-medium text-nb-secondary mb-1.5">
            Cabeçalhos fixos (JSON, opcional) — use pra token/API key da API, ex:{" "}
            <code className="font-mono">{"{\"Authorization\": \"Bearer ...\"}"}</code>
          </label>
          <textarea
            value={headersText}
            onChange={(e) => setHeadersText(e.target.value)}
            rows={3}
            className={`${inputCls} font-mono text-xs`}
          />
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
  const [tools, setTools] = useState<AgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingTool, setEditingTool] = useState<AgentTool | null>(null);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const writeAllowed = canWrite(role);

  function refresh() {
    setLoading(true);
    setLoadError(null);
    api.agents.httpTools
      .list(agentId)
      .then(setTools)
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar ferramentas."))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) refresh();
  }, [open, agentId]);

  async function handleToggle(tool: AgentTool) {
    setBusy((p) => ({ ...p, [tool.id]: true }));
    try {
      const updated = await api.agents.httpTools.update(agentId, tool.id, {
        is_enabled: !tool.is_enabled,
      });
      setTools((prev) => prev.map((t) => (t.id === tool.id ? updated : t)));
    } catch {
      // Toggle failure is surfaced by the row staying unchanged — low-stakes enough
      // to not need a dedicated error banner here.
    } finally {
      setBusy((p) => ({ ...p, [tool.id]: false }));
    }
  }

  async function handleDelete(tool: AgentTool) {
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

// ── Roadmap card ──────────────────────────────────────────────────────────────

function RoadmapCard({
  icon: Icon,
  name,
  description,
}: {
  icon: React.ElementType;
  name: string;
  description: string;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 opacity-55 flex items-start gap-3">
      <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-nb-muted" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-medium text-nb-secondary">{name}</h3>
          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full bg-nb-elevated border border-nb-border text-nb-muted">
            <Clock className="w-3 h-3" />
            Em breve
          </span>
        </div>
        <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">{description}</p>
      </div>
    </div>
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
  // KB state (for active tools display)
  const [kbList, setKbList] = useState<AgentKnowledgeBase[]>([]);
  const [kbLoading, setKbLoading] = useState(true);
  const [kbError, setKbError] = useState(false);
  const [kbModalOpen, setKbModalOpen] = useState(false);

  // Catalog state (for active tools display)
  const [catalogScope, setCatalogScope] = useState<AgentCatalogScope | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogModalOpen, setCatalogModalOpen] = useState(false);

  // HTTP Tools state (for active tools display)
  const [httpToolsList, setHttpToolsList] = useState<AgentTool[]>([]);
  const [httpToolsLoading, setHttpToolsLoading] = useState(true);
  const [httpToolsModalOpen, setHttpToolsModalOpen] = useState(false);

  useEffect(() => {
    api.agents.httpTools
      .list(agentId)
      .then(setHttpToolsList)
      .catch(() => setHttpToolsList([]))
      .finally(() => setHttpToolsLoading(false));
  }, [agentId]);

  function handleHttpToolsModalClose() {
    setHttpToolsModalOpen(false);
    setHttpToolsLoading(true);
    api.agents.httpTools
      .list(agentId)
      .then(setHttpToolsList)
      .catch(() => setHttpToolsList([]))
      .finally(() => setHttpToolsLoading(false));
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
  const enabledHttpTools = httpToolsList.filter((t) => t.is_enabled);
  const httpToolsActive = !httpToolsLoading && enabledHttpTools.length > 0;

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

          {/* Roadmap */}
          <RoadmapCard
            icon={Hand}
            name="Solicitar humano"
            description="Permite que o agente transfira o atendimento para um operador humano."
          />
          <RoadmapCard
            icon={Zap}
            name="Follow-up"
            description="Envie mensagens de acompanhamento automáticas após o atendimento."
          />
          <RoadmapCard
            icon={Check}
            name="Marcar como resolvido"
            description="Permita que o agente encerre conversas automaticamente quando resolvidas."
          />
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
    </div>
  );
}
