import { Loader2 } from "lucide-react";
import type { AiCatalog, AiModel } from "@/lib/api";
import type { CreativityLevel } from "./wizard-types";
import { CREATIVITY_TEMPERATURE } from "./wizard-types";

const CREATIVITY_OPTIONS: { id: CreativityLevel; label: string; value: number; description: string }[] = [
  {
    id: "precise",
    label: "Conservador",
    value: 0.2,
    description: "Respostas consistentes e previsíveis. Ideal para suporte e FAQ.",
  },
  {
    id: "balanced",
    label: "Equilibrado",
    value: 0.7,
    description: "Combina precisão com naturalidade. Bom para a maioria dos casos.",
  },
  {
    id: "creative",
    label: "Criativo",
    value: 1.0,
    description: "Respostas mais variadas e elaboradas. Útil para vendas e engajamento.",
  },
];

export function StepModel({
  catalog,
  loading,
  aiModelId,
  creativity,
  onModelChange,
  onCreativityChange,
  errors,
}: {
  catalog: AiCatalog | null;
  loading: boolean;
  aiModelId: string | null;
  creativity: CreativityLevel;
  onModelChange: (id: string) => void;
  onCreativityChange: (v: CreativityLevel) => void;
  errors: { aiModelId?: string };
}) {
  const allModels: AiModel[] = catalog
    ? catalog.providers.flatMap((p) => p.models)
    : [];

  const temperature = CREATIVITY_TEMPERATURE[creativity];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">Modelo e criatividade</h2>
        <p className="text-sm text-nb-muted mt-1">
          Escolha o nível de inteligência e custo do agente. Modelos mais avançados consomem mais
          créditos por mensagem.
        </p>
      </div>

      {/* Modelo */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-nb-secondary">
          Modelo de IA <span className="text-nb-danger">*</span>
        </p>

        {loading ? (
          <div className="flex items-center gap-2 text-sm text-nb-muted py-4">
            <Loader2 className="w-4 h-4 animate-spin" />
            Carregando modelos…
          </div>
        ) : allModels.length === 0 ? (
          <p className="text-sm text-nb-muted">Nenhum modelo disponível.</p>
        ) : (
          <div className="space-y-2">
            {allModels.map((model) => {
              const selected = aiModelId === model.id;
              return (
                <button
                  key={model.id}
                  type="button"
                  onClick={() => onModelChange(model.id)}
                  className={`w-full text-left flex items-center justify-between p-3.5 rounded-xl border transition-all ${
                    selected
                      ? "border-nb-primary bg-nb-primary-bg ring-1 ring-nb-primary/20"
                      : "border-nb-border bg-nb-elevated hover:bg-nb-panel"
                  }`}
                >
                  <div className="min-w-0">
                    <p className={`text-sm font-semibold ${selected ? "text-nb-primary-strong" : "text-nb-text"}`}>
                      {model.display_name}
                    </p>
                    {model.description && (
                      <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                        {model.description}
                      </p>
                    )}
                  </div>
                  {model.credits_per_message > 0 && (
                    <span className="flex-shrink-0 ml-3 text-xs font-medium text-nb-warning">
                      {model.credits_per_message} crédito{model.credits_per_message !== 1 ? "s" : ""}/msg
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {errors.aiModelId && (
          <p className="text-xs text-nb-danger">{errors.aiModelId}</p>
        )}
      </div>

      {/* Criatividade */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium text-nb-secondary">Criatividade</p>
          <p className="text-xs text-nb-muted mt-0.5">
            Valores baixos deixam o agente mais consistente. Valores altos deixam as respostas mais variadas e criativas.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {CREATIVITY_OPTIONS.map((opt) => {
            const selected = creativity === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => onCreativityChange(opt.id)}
                className={`text-left p-3.5 rounded-xl border transition-all ${
                  selected
                    ? "border-nb-primary bg-nb-primary-bg ring-1 ring-nb-primary/20"
                    : "border-nb-border bg-nb-elevated hover:bg-nb-panel"
                }`}
              >
                <div className="flex items-start justify-between gap-1 mb-1">
                  <p className={`text-sm font-semibold ${selected ? "text-nb-primary-strong" : "text-nb-text"}`}>
                    {opt.label}
                  </p>
                  <span className={`font-mono text-xs px-1.5 py-0.5 rounded-md border flex-shrink-0 ${
                    selected
                      ? "bg-nb-primary/10 border-nb-primary/30 text-nb-primary-strong"
                      : "bg-nb-bg border-nb-border text-nb-muted"
                  }`}>
                    {opt.value.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-nb-muted leading-relaxed">{opt.description}</p>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
