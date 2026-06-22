"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { api } from "@/lib/api";
import type { AiProvider } from "@/lib/api";

interface ModelSelectProps {
  aiModelId: string | null;
  disabled?: boolean;
  onChange: (modelId: string, modelName: string) => void;
}

const selectClass = (disabled: boolean) =>
  `w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white
   focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent
   ${disabled ? "bg-gray-50 text-gray-400 cursor-not-allowed" : ""}`;

export function ModelSelect({
  aiModelId,
  disabled = false,
  onChange,
}: ModelSelectProps) {
  const { getToken } = useAuth();
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [catalogError, setCatalogError] = useState<string | null>(null);

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const catalog = await api.aiModels.list(token);
        setProviders(catalog.providers);
      } catch {
        setCatalogError("Não foi possível carregar os modelos disponíveis.");
      }
    });
  }, [getToken]);

  const allModels = providers.flatMap((p) => p.models);

  if (catalogError) {
    return (
      <div className="p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
        {catalogError}
      </div>
    );
  }

  if (providers.length === 0) {
    return <div className="h-9 bg-gray-100 rounded-md animate-pulse" />;
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">Modelo</label>
      <select
        value={aiModelId ?? ""}
        disabled={disabled}
        onChange={(e) => {
          const model = allModels.find((m) => m.id === e.target.value);
          if (model) onChange(model.id, model.model_name);
        }}
        className={selectClass(disabled)}
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
