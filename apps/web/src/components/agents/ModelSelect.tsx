"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AiProvider } from "@/lib/api";

interface ModelSelectProps {
  aiModelId: string | null;
  disabled?: boolean;
  onChange: (modelId: string, modelName: string) => void;
}

export function ModelSelect({ aiModelId, disabled = false, onChange }: ModelSelectProps) {
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    api.aiModels.list()
      .then((catalog) => setProviders(catalog.providers))
      .catch(() => setCatalogError("Não foi possível carregar os modelos disponíveis."));
  }, []);

  const allModels = providers.flatMap((p) => p.models);

  if (catalogError) {
    return (
      <div className="p-3 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {catalogError}
      </div>
    );
  }

  if (providers.length === 0) {
    return <div className="h-9 bg-nb-elevated rounded-xl animate-pulse" />;
  }

  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-nb-secondary">Modelo</label>
      <select
        value={aiModelId ?? ""}
        disabled={disabled}
        onChange={(e) => {
          const model = allModels.find((m) => m.id === e.target.value);
          if (model) onChange(model.id, model.model_name);
        }}
        className={`w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        {allModels.map((m) => (
          <option key={m.id} value={m.id} disabled={!m.available}>
            {m.display_name}
            {m.is_default ? " (padrão)" : ""}
            {!m.available ? " — requer plano " + m.min_plan_code : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
