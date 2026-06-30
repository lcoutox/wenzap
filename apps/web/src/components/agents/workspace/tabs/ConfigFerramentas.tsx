"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Clock,
  Globe,
  Hand,
  ShoppingBag,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentCatalogScope, AgentKnowledgeBase, CatalogCategory, MemberRole } from "@/lib/api";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

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

// ── Category picker modal ─────────────────────────────────────────────────────

function CategoryPickerModal({
  categories,
  selectedIds,
  onClose,
  onSave,
}: {
  categories: CatalogCategory[];
  selectedIds: string[];
  onClose: () => void;
  onSave: (ids: string[]) => void;
}) {
  const [draft, setDraft] = useState<Set<string>>(new Set(selectedIds));

  const toggle = (id: string) =>
    setDraft((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-nb-panel rounded-2xl border border-nb-border shadow-xl flex flex-col max-h-[80vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-nb-border shrink-0">
          <div>
            <h3 className="text-sm font-bold text-nb-text">Categorias do Catálogo</h3>
            <p className="text-xs text-nb-muted mt-0.5">
              Selecione quais categorias este agente pode consultar.
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated transition-colors text-nb-muted"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-2 min-h-0">
          {categories.length === 0 ? (
            <p className="text-sm text-nb-muted text-center py-6">
              Nenhuma categoria cadastrada.
            </p>
          ) : (
            categories.map((cat) => (
              <label
                key={cat.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border cursor-pointer transition-colors ${
                  draft.has(cat.id)
                    ? "border-nb-primary bg-nb-primary/5"
                    : "border-nb-border bg-nb-elevated hover:bg-nb-border/30"
                }`}
              >
                <input
                  type="checkbox"
                  checked={draft.has(cat.id)}
                  onChange={() => toggle(cat.id)}
                  className="accent-nb-primary"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-nb-text truncate">{cat.name}</p>
                  {cat.description && (
                    <p className="text-xs text-nb-muted truncate">{cat.description}</p>
                  )}
                </div>
              </label>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 p-4 border-t border-nb-border shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-nb-border text-sm text-nb-text hover:bg-nb-elevated transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={() => { onSave(Array.from(draft)); onClose(); }}
            className="px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
          >
            Salvar seleção
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Tool cards ────────────────────────────────────────────────────────────────

function SoonToolCard({
  icon: Icon,
  name,
  description,
}: {
  icon: React.ElementType;
  name: string;
  description: string;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 opacity-55">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
          <Icon className="w-5 h-5 text-nb-muted" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-secondary">{name}</h3>
            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-nb-elevated border border-nb-border text-nb-muted">
              Em breve
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-1 leading-relaxed">{description}</p>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigFerramentas({
  agentId,
  readonly,
  saving,
  saveError,
  saveSuccess,
  role: _role,
}: {
  agentId: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  role: MemberRole | null;
}) {
  // Knowledge Base state
  const [kbList, setKbList] = useState<AgentKnowledgeBase[]>([]);
  const [kbLoading, setKbLoading] = useState(true);
  const [kbError, setKbError] = useState(false);

  useEffect(() => {
    api.agents.knowledgeBases.list(agentId)
      .then((data) => setKbList(data.filter((kb) => kb.is_active)))
      .catch(() => setKbError(true))
      .finally(() => setKbLoading(false));
  }, [agentId]);

  // Catalog scope state
  const [scope, setScope] = useState<AgentCatalogScope>({
    catalog_enabled: true,
    category_scope: "all",
    category_ids: [],
  });
  const [categories, setCategories] = useState<CatalogCategory[]>([]);
  const [loadingScope, setLoadingScope] = useState(true);
  const [scopeError, setScopeError] = useState<string | null>(null);
  const [scopeSaving, setScopeSaving] = useState(false);
  const [scopeSaveError, setScopeSaveError] = useState<string | null>(null);
  const [scopeSaveSuccess, setScopeSaveSuccess] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    Promise.all([
      api.agents.catalogScope.get(agentId),
      api.catalog.categories.list(false),
    ])
      .then(([s, cats]) => {
        setScope(s);
        setCategories(cats);
      })
      .catch(() => setScopeError("Erro ao carregar ferramentas."))
      .finally(() => setLoadingScope(false));
  }, [agentId]);

  const saveScope = async (next: AgentCatalogScope) => {
    setScopeSaving(true);
    setScopeSaveError(null);
    try {
      const saved = await api.agents.catalogScope.update(agentId, {
        catalog_enabled: next.catalog_enabled,
        category_scope: next.category_scope,
        category_ids: next.category_ids,
      });
      setScope(saved);
      setScopeSaveSuccess(true);
      setTimeout(() => setScopeSaveSuccess(false), 3000);
    } catch {
      setScopeSaveError("Erro ao salvar configuração do Catálogo.");
    } finally {
      setScopeSaving(false);
    }
  };

  const handleToggleCatalog = (enabled: boolean) => {
    const next = { ...scope, catalog_enabled: enabled };
    setScope(next);
    saveScope(next);
  };

  const handleScopeChange = (s: "all" | "selected") => {
    const next: AgentCatalogScope = {
      ...scope,
      category_scope: s,
      category_ids: s === "all" ? [] : scope.category_ids,
    };
    setScope(next);
    saveScope(next);
  };

  const handleCategorySave = (ids: string[]) => {
    const next: AgentCatalogScope = {
      ...scope,
      category_scope: ids.length > 0 ? "selected" : "all",
      category_ids: ids,
    };
    setScope(next);
    saveScope(next);
  };

  const selectedCategoryNames = scope.category_ids
    .map((id) => categories.find((c) => c.id === id)?.name)
    .filter(Boolean);

  if (loadingScope) {
    return (
      <div className="space-y-4">
        {[1, 2].map((i) => (
          <div key={i} className="h-40 rounded-2xl bg-nb-elevated animate-pulse" />
        ))}
      </div>
    );
  }

  if (scopeError) {
    return <p className="text-sm text-nb-danger">{scopeError}</p>;
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

      {/* Active tools */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">
          Ferramentas disponíveis
        </p>
        <div className="flex flex-col gap-4">

          {/* ── Knowledge Base ── */}
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
                <BookOpen className="w-5 h-5 text-nb-primary-strong" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-nb-text">Base de Conhecimento</h3>
                  {kbLoading ? (
                    <span className="w-16 h-4 rounded-full bg-nb-elevated animate-pulse inline-block" />
                  ) : kbError ? (
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-danger/10 text-nb-danger border-nb-danger/20">
                      Erro
                    </span>
                  ) : kbList.length > 0 ? (
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-success/10 text-nb-success border-nb-success/20">
                      Conectada
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-xs font-medium rounded-full border bg-nb-elevated text-nb-muted border-nb-border">
                      Sem bases
                    </span>
                  )}
                </div>
                <p className="text-xs text-nb-muted mt-1 leading-relaxed">
                  Permite que o agente consulte documentos, perguntas frequentes e informações da
                  empresa para responder com mais precisão.
                </p>
              </div>
            </div>

            {/* Connected bases summary */}
            {!kbLoading && !kbError && kbList.length > 0 && (
              <div className="border-t border-nb-border pt-3 flex flex-col gap-2">
                <p className="text-xs font-semibold text-nb-text">
                  {kbList.length === 1 ? "1 base conectada" : `${kbList.length} bases conectadas`}
                </p>
                <ul className="flex flex-col gap-1">
                  {kbList.map((kb) => (
                    <li key={kb.id} className="flex items-center gap-2 text-xs text-nb-muted">
                      <span className="w-1.5 h-1.5 rounded-full bg-nb-success shrink-0" />
                      {kb.knowledge_base_name}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Empty state */}
            {!kbLoading && !kbError && kbList.length === 0 && (
              <div className="border-t border-nb-border pt-3">
                <p className="text-xs text-nb-muted leading-relaxed">
                  Nenhuma base conectada. Conecte documentos, FAQs e informações da empresa para que
                  o agente responda com mais precisão.
                </p>
              </div>
            )}

            {/* Error state */}
            {!kbLoading && kbError && (
              <div className="border-t border-nb-border pt-3">
                <p className="text-xs text-nb-danger">
                  Não foi possível carregar as bases conectadas.
                </p>
              </div>
            )}

            <div className="border-t border-nb-border pt-3">
              <Link
                href={`/dashboard/agents/${agentId}?tab=knowledge`}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
              >
                {!kbLoading && !kbError && kbList.length === 0
                  ? "Conectar base"
                  : "Gerenciar conhecimento"}
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          {/* ── Catalog ── */}
          <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 flex flex-col gap-4">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
                <ShoppingBag className="w-5 h-5 text-nb-primary-strong" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-sm font-semibold text-nb-text">Catálogo</h3>
                  <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${
                    scope.catalog_enabled
                      ? "bg-nb-success/10 text-nb-success border-nb-success/20"
                      : "bg-nb-elevated text-nb-muted border-nb-border"
                  }`}>
                    {scope.catalog_enabled ? "Ativo" : "Inativo"}
                  </span>
                </div>
                <p className="text-xs text-nb-muted mt-1 leading-relaxed">
                  Permite que o agente consulte produtos, serviços, planos e ofertas cadastradas para
                  recomendar opções durante o atendimento.
                </p>
              </div>
              <div className="shrink-0 mt-0.5">
                <Toggle
                  checked={scope.catalog_enabled}
                  disabled={readonly || scopeSaving}
                  onChange={handleToggleCatalog}
                />
              </div>
            </div>

            {/* Scope selector — only when enabled */}
            {scope.catalog_enabled && (
              <div className="border-t border-nb-border pt-4 flex flex-col gap-3">
                <p className="text-xs font-semibold text-nb-text">Escopo do Catálogo</p>
                <div className="flex flex-col gap-2">
                  {(["all", "selected"] as const).map((opt) => (
                    <label
                      key={opt}
                      className={`flex items-center gap-3 px-3 py-2.5 rounded-xl border cursor-pointer transition-colors ${
                        scope.category_scope === opt
                          ? "border-nb-primary bg-nb-primary/5"
                          : "border-nb-border bg-nb-elevated hover:bg-nb-border/30"
                      } ${readonly || scopeSaving ? "pointer-events-none opacity-60" : ""}`}
                    >
                      <input
                        type="radio"
                        checked={scope.category_scope === opt}
                        onChange={() => handleScopeChange(opt)}
                        disabled={readonly || scopeSaving}
                        className="accent-nb-primary"
                      />
                      <span className="text-sm text-nb-text">
                        {opt === "all" ? "Todo o Catálogo" : "Categorias selecionadas"}
                      </span>
                    </label>
                  ))}
                </div>

                {/* Category summary / picker */}
                {scope.category_scope === "selected" && (
                  <div className="flex flex-col gap-2 mt-1">
                    {categories.length === 0 ? (
                      <p className="text-xs text-nb-muted">
                        Nenhuma categoria cadastrada.{" "}
                        <Link
                          href="/dashboard/catalog"
                          className="text-nb-primary hover:underline"
                        >
                          Gerenciar Catálogo
                        </Link>
                      </p>
                    ) : (
                      <>
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                          <p className="text-xs text-nb-muted">
                            {scope.category_ids.length === 0
                              ? "Nenhuma categoria selecionada"
                              : selectedCategoryNames.length <= 3
                              ? selectedCategoryNames.join(", ")
                              : `${selectedCategoryNames.slice(0, 3).join(", ")} +${selectedCategoryNames.length - 3}`}
                          </p>
                          {!readonly && (
                            <button
                              type="button"
                              onClick={() => setPickerOpen(true)}
                              className="text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors shrink-0"
                            >
                              {scope.category_ids.length === 0 ? "Selecionar categorias" : "Alterar categorias"}
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Save error / success for scope changes */}
                {scopeSaveError && (
                  <p className="text-xs text-nb-danger">{scopeSaveError}</p>
                )}
                {scopeSaveSuccess && (
                  <p className="text-xs text-nb-success">Configuração salva.</p>
                )}
              </div>
            )}

            <div className="border-t border-nb-border pt-3 flex items-center justify-between flex-wrap gap-3">
              <p className="text-xs text-nb-muted max-w-xs">
                Quando ativado, o agente pode consultar itens ativos do Catálogo quando identificar
                uma intenção comercial.
              </p>
              <Link
                href="/dashboard/catalog"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors shrink-0"
              >
                Gerenciar Catálogo
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* SaveBar for parent form (knowledge base etc) */}
      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}

      {/* Roadmap */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">Em breve</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <SoonToolCard
            icon={Globe}
            name="HTTP Tools"
            description="Permite que o agente consulte sistemas externos e execute ações via API durante o atendimento."
          />
          <SoonToolCard
            icon={Hand}
            name="Solicitar humano"
            description="Permite que o agente chame um atendente quando a conversa precisar de intervenção humana."
          />
          <SoonToolCard
            icon={Clock}
            name="Follow-up"
            description="Permite que o agente acompanhe oportunidades e retome conversas automaticamente."
          />
          <SoonToolCard
            icon={CheckCircle2}
            name="Marcar como resolvido"
            description="Permite que o agente finalize conversas quando o atendimento estiver concluído."
          />
        </div>
      </div>

      {/* Category picker modal */}
      {pickerOpen && (
        <CategoryPickerModal
          categories={categories}
          selectedIds={scope.category_ids}
          onClose={() => setPickerOpen(false)}
          onSave={handleCategorySave}
        />
      )}
    </div>
  );
}
