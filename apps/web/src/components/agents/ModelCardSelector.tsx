"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Zap,
  Eye,
  Wrench,
  Code2,
  BrainCircuit,
  Lock,
  Search,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AiProvider, AiModel } from "@/lib/api";

// ── Capability icons ──────────────────────────────────────────────────────────

type Capability = { key: string; label: string; icon: React.ElementType };

function modelCapabilities(model: AiModel): Capability[] {
  const caps: Capability[] = [];
  if (model.supports_vision)    caps.push({ key: "vision",    label: "Visão",       icon: Eye });
  if (model.supports_tools)     caps.push({ key: "tools",     label: "Ferramentas", icon: Wrench });
  if (model.supports_code)      caps.push({ key: "code",      label: "Código",      icon: Code2 });
  if (model.supports_reasoning) caps.push({ key: "reasoning", label: "Raciocínio",  icon: BrainCircuit });
  return caps;
}

// ── Filter bar ────────────────────────────────────────────────────────────────

type FilterChipProps = {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
};

function FilterChip({ active, onClick, children }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors
        ${active
          ? "bg-nb-primary text-white border border-nb-primary"
          : "bg-nb-elevated border border-nb-border text-nb-muted hover:text-nb-secondary hover:border-nb-border-strong"}
      `}
    >
      {children}
    </button>
  );
}

// ── Active model summary ──────────────────────────────────────────────────────

function ActiveModelSummary({
  model,
  provider,
}: {
  model: AiModel | null;
  provider: AiProvider | null;
}) {
  if (!model || !provider) return null;
  const capabilities = modelCapabilities(model);

  return (
    <div className="flex items-start gap-4 p-4 rounded-xl bg-nb-primary-bg border border-nb-primary/20">
      <div className="w-9 h-9 rounded-xl bg-nb-primary flex items-center justify-center flex-shrink-0">
        <Zap className="w-4 h-4 text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <p className="text-sm font-semibold text-nb-text">{model.display_name}</p>
          {model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-nb-primary-bg text-nb-primary-strong border-nb-primary/20">
              Recomendado
            </span>
          )}
          {model.is_featured && !model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-nb-elevated text-nb-secondary border-nb-border">
              Destaque
            </span>
          )}
          <span className="text-xs text-nb-muted ml-auto">
            {model.credits_per_message} crédito{model.credits_per_message !== 1 ? "s" : ""}/msg
          </span>
        </div>
        <p className="text-xs text-nb-muted mb-2">{provider.name}</p>
        {capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {capabilities.map(({ key, label, icon: Icon }) => (
              <span
                key={key}
                className="inline-flex items-center gap-1 text-xs text-nb-primary-strong bg-nb-primary-bg px-2 py-0.5 rounded-lg"
              >
                <Icon className="w-3 h-3" />
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Model card ────────────────────────────────────────────────────────────────

function ModelCard({
  model,
  provider,
  selected,
  globalDisabled,
  onSelect,
}: {
  model: AiModel;
  provider: AiProvider;
  selected: boolean;
  globalDisabled: boolean;
  onSelect: () => void;
}) {
  const unavailable = !model.available;
  const disabled = globalDisabled || unavailable;
  const capabilities = modelCapabilities(model);

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onSelect}
      className={`
        w-full text-left rounded-xl border p-4 transition-all duration-150
        ${disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-nb-border-strong"}
        ${selected
          ? "border-nb-primary bg-nb-primary-bg/50 ring-1 ring-nb-primary/40"
          : "border-nb-border bg-nb-elevated"}
      `}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-nb-text">{model.display_name}</span>
          {model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-nb-primary-bg text-nb-primary-strong border-nb-primary/20">
              Recomendado
            </span>
          )}
          {model.is_featured && !model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-nb-elevated text-nb-secondary border-nb-border">
              Destaque
            </span>
          )}
        </div>
        {selected && !unavailable && (
          <CheckCircle2 className="w-4 h-4 text-nb-primary flex-shrink-0 mt-0.5" />
        )}
        {unavailable && (
          <Lock className="w-4 h-4 text-nb-muted flex-shrink-0 mt-0.5" />
        )}
      </div>

      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-nb-muted">{provider.name}</p>
        <p className="text-xs text-nb-muted">
          {model.credits_per_message} crédito{model.credits_per_message !== 1 ? "s" : ""}/msg
        </p>
      </div>

      {model.description && (
        <p className="text-xs text-nb-muted mb-3 line-clamp-2">{model.description}</p>
      )}

      {unavailable && (
        <p className="text-xs text-nb-warning bg-nb-warning/10 rounded-lg px-2 py-1 mb-2 border border-nb-warning/20">
          Requer plano {model.min_plan_code}
        </p>
      )}

      {capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {capabilities.map(({ key, label, icon: Icon }) => (
            <span
              key={key}
              className="inline-flex items-center gap-1 text-xs text-nb-muted bg-nb-soft border border-nb-border px-2 py-0.5 rounded-lg"
            >
              <Icon className="w-3 h-3" />
              {label}
            </span>
          ))}
        </div>
      )}
    </button>
  );
}

// ── Capability filter options (only real fields) ───────────────────────────────

const CAPABILITY_FILTERS: { key: string; label: string }[] = [
  { key: "vision",    label: "Visão" },
  { key: "reasoning", label: "Raciocínio" },
  { key: "tools",     label: "Ferramentas" },
  { key: "code",      label: "Código" },
];

function modelHasCapability(model: AiModel, capKey: string): boolean {
  if (capKey === "vision")    return model.supports_vision;
  if (capKey === "reasoning") return model.supports_reasoning;
  if (capKey === "tools")     return model.supports_tools;
  if (capKey === "code")      return model.supports_code;
  return false;
}

// ── Main component ────────────────────────────────────────────────────────────

interface ModelCardSelectorProps {
  aiModelId: string | null;
  disabled?: boolean;
  onChange: (modelId: string, modelName: string) => void;
}

export function ModelCardSelector({
  aiModelId,
  disabled = false,
  onChange,
}: ModelCardSelectorProps) {
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState<string | null>(null);
  const didInit                 = useRef(false);

  // Filter state
  const [search, setSearch]             = useState("");
  const [providerFilter, setProviderFilter] = useState<string | null>(null);
  const [capFilter, setCapFilter]       = useState<string | null>(null);
  const [onlyAvailable, setOnlyAvailable] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const catalog = await api.aiModels.list();
        setProviders(catalog.providers);
        if (!aiModelId && !didInit.current) {
          didInit.current = true;
          const allModels = catalog.providers.flatMap((p) => p.models);
          const pick =
            allModels.find((m) => m.is_default && m.available) ??
            allModels.find((m) => m.available) ??
            null;
          if (pick) onChange(pick.id, pick.model_name);
        }
      } catch {
        setError("Não foi possível carregar os modelos disponíveis.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const allPairs = providers.flatMap((p) => p.models.map((m) => ({ model: m, provider: p })));
  const selected = allPairs.find(({ model }) => model.id === aiModelId) ?? null;

  // Apply filters
  const query = search.trim().toLowerCase();
  const filtered = allPairs.filter(({ model, provider }) => {
    if (query && !model.display_name.toLowerCase().includes(query) &&
        !provider.name.toLowerCase().includes(query) &&
        !(model.description ?? "").toLowerCase().includes(query)) return false;
    if (providerFilter && provider.code !== providerFilter) return false;
    if (capFilter && !modelHasCapability(model, capFilter)) return false;
    if (onlyAvailable && !model.available) return false;
    return true;
  });

  const hasActiveFilter = !!query || !!providerFilter || !!capFilter || onlyAvailable;

  function clearFilters() {
    setSearch("");
    setProviderFilter(null);
    setCapFilter(null);
    setOnlyAvailable(false);
  }

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl border border-nb-border bg-nb-elevated animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {error}
      </div>
    );
  }

  if (providers.length === 0 || allPairs.length === 0) {
    return (
      <div className="p-4 bg-nb-elevated border border-nb-border rounded-xl text-sm text-nb-muted text-center">
        Nenhum modelo disponível para o seu plano atual.
      </div>
    );
  }

  // Group filtered results by provider
  const filteredByProvider = providers
    .map((p) => ({
      provider: p,
      models: filtered.filter(({ provider }) => provider.code === p.code).map(({ model }) => model),
    }))
    .filter(({ models }) => models.length > 0);

  return (
    <div className="space-y-4">
      {/* Active model summary */}
      {selected && (
        <ActiveModelSummary model={selected.model} provider={selected.provider} />
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Buscar modelo..."
          disabled={disabled}
          className="w-full pl-9 pr-9 py-2 text-sm bg-nb-panel border border-nb-border rounded-xl text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary disabled:opacity-50"
        />
        {search && (
          <button
            type="button"
            onClick={() => setSearch("")}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-nb-muted hover:text-nb-secondary"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {/* Provider filters */}
        {providers.map((p) => (
          <FilterChip
            key={p.code}
            active={providerFilter === p.code}
            onClick={() => setProviderFilter(providerFilter === p.code ? null : p.code)}
          >
            {p.name}
          </FilterChip>
        ))}

        {/* Capability filters — only show if any model has that capability */}
        {CAPABILITY_FILTERS.filter(({ key }) =>
          allPairs.some(({ model }) => modelHasCapability(model, key))
        ).map(({ key, label }) => (
          <FilterChip
            key={key}
            active={capFilter === key}
            onClick={() => setCapFilter(capFilter === key ? null : key)}
          >
            {label}
          </FilterChip>
        ))}

        {/* Disponível no plano */}
        <FilterChip
          active={onlyAvailable}
          onClick={() => setOnlyAvailable(!onlyAvailable)}
        >
          Disponível no plano
        </FilterChip>

        {/* Clear all */}
        {hasActiveFilter && (
          <button
            type="button"
            onClick={clearFilters}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-nb-muted hover:text-nb-secondary flex items-center gap-1"
          >
            <X className="w-3 h-3" />
            Limpar
          </button>
        )}
      </div>

      {/* Results */}
      {filteredByProvider.length === 0 ? (
        <div className="p-4 bg-nb-elevated border border-nb-border rounded-xl text-sm text-nb-muted text-center">
          Nenhum modelo encontrado para os filtros aplicados.
        </div>
      ) : (
        <div className="space-y-5">
          {filteredByProvider.map(({ provider, models }) => (
            <div key={provider.code}>
              {filteredByProvider.length > 1 && (
                <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">
                  {provider.name}
                </p>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {models.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    provider={provider}
                    selected={model.id === aiModelId}
                    globalDisabled={disabled}
                    onSelect={() => onChange(model.id, model.model_name)}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
