"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  CheckCircle2,
  Zap,
  Eye,
  Wrench,
  Code2,
  BrainCircuit,
  Lock,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AiProvider, AiModel } from "@/lib/api";

// ── Capability icons ──────────────────────────────────────────────────────────

type Capability = { label: string; icon: React.ElementType };

function modelCapabilities(model: AiModel): Capability[] {
  const caps: Capability[] = [];
  if (model.supports_vision)    caps.push({ label: "Visão",        icon: Eye });
  if (model.supports_tools)     caps.push({ label: "Ferramentas",  icon: Wrench });
  if (model.supports_code)      caps.push({ label: "Código",       icon: Code2 });
  if (model.supports_reasoning) caps.push({ label: "Raciocínio",   icon: BrainCircuit });
  return caps;
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
    <div className="flex items-start gap-4 p-4 rounded-xl bg-indigo-50/60 border border-indigo-100">
      <div className="w-9 h-9 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
        <Zap className="w-4 h-4 text-white" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <p className="text-sm font-semibold text-gray-900">{model.display_name}</p>
          {model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-indigo-50 text-indigo-700 border-indigo-200">
              Recomendado
            </span>
          )}
          {model.is_featured && !model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-purple-50 text-purple-700 border-purple-200">
              Destaque
            </span>
          )}
          <span className="text-xs text-gray-400 ml-auto">
            {model.credits_per_message} crédito{model.credits_per_message !== 1 ? "s" : ""}/msg
          </span>
        </div>
        <p className="text-xs text-gray-500 mb-2">{provider.name}</p>
        {capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {capabilities.map(({ label, icon: Icon }) => (
              <span
                key={label}
                className="inline-flex items-center gap-1 text-xs text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded-md"
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
        ${disabled ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:shadow-sm"}
        ${selected
          ? "border-indigo-500 bg-indigo-50/50 ring-1 ring-indigo-500"
          : "border-gray-200 bg-white hover:border-gray-300"
        }
      `}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-gray-900">{model.display_name}</span>
          {model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-indigo-50 text-indigo-700 border-indigo-200">
              Recomendado
            </span>
          )}
          {model.is_featured && !model.is_recommended && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full border bg-purple-50 text-purple-700 border-purple-200">
              Destaque
            </span>
          )}
        </div>
        {selected && !unavailable && (
          <CheckCircle2 className="w-4 h-4 text-indigo-600 flex-shrink-0 mt-0.5" />
        )}
        {unavailable && (
          <Lock className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
        )}
      </div>

      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-gray-400">{provider.name}</p>
        <p className="text-xs text-gray-400">
          {model.credits_per_message} crédito{model.credits_per_message !== 1 ? "s" : ""}/msg
        </p>
      </div>

      {model.description && (
        <p className="text-xs text-gray-500 mb-3 line-clamp-2">{model.description}</p>
      )}

      {unavailable && (
        <p className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1 mb-2">
          Requer plano {model.min_plan_code}
        </p>
      )}

      {capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {capabilities.map(({ label, icon: Icon }) => (
            <span
              key={label}
              className="inline-flex items-center gap-1 text-xs text-gray-500 bg-gray-50 border border-gray-100 px-2 py-0.5 rounded-md"
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
  const { getToken } = useAuth();
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track whether we've fired the initial default selection
  const didInit = useRef(false);

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const catalog = await api.aiModels.list(token);
        setProviders(catalog.providers);

        // If no model is selected yet, auto-select the default available one
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
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [getToken]);

  // Find the currently selected model + its provider
  const allModels = providers.flatMap((p) =>
    p.models.map((m) => ({ model: m, provider: p }))
  );
  const selected = allModels.find(({ model }) => model.id === aiModelId) ?? null;

  if (loading) {
    return (
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl border border-gray-200 bg-gray-50 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
        {error}
      </div>
    );
  }

  if (providers.length === 0 || allModels.length === 0) {
    return (
      <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-500 text-center">
        Nenhum modelo disponível para o seu plano atual.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Active model summary */}
      {selected && (
        <ActiveModelSummary model={selected.model} provider={selected.provider} />
      )}

      {/* Model grid — grouped by provider */}
      {providers.map((provider) => (
        <div key={provider.code}>
          {providers.length > 1 && (
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
              {provider.name}
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {provider.models.map((model) => (
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
  );
}
