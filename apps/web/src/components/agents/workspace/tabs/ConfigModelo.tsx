import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { ModelCardSelector } from "@/components/agents/ModelCardSelector";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

export function ConfigModelo({
  aiModelId,
  temperature,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onModelChange,
  onTemperatureChange,
}: {
  aiModelId: string | null;
  temperature: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onModelChange: (modelId: string, modelName: string) => void;
  onTemperatureChange: (v: string) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="Modelo de IA"
        description="Escolha o nível de inteligência e custo do agente. Modelos mais avançados consomem mais créditos por mensagem."
      >
        <ModelCardSelector
          aiModelId={aiModelId}
          disabled={readonly}
          onChange={onModelChange}
        />
      </AgentFormSection>

      <AgentFormSection
        title="Criatividade"
        description="Valores mais baixos deixam o agente mais preciso. Valores mais altos deixam as respostas mais variadas."
      >
        <div className="flex items-center gap-4">
          <input
            type="range"
            value={temperature}
            onChange={(e) => onTemperatureChange(e.target.value)}
            step="0.1"
            min="0"
            max="1"
            disabled={readonly}
            className="flex-1 accent-nb-primary disabled:opacity-50"
          />
          <span className="w-10 text-sm font-mono text-center text-nb-secondary bg-nb-elevated border border-nb-border rounded-lg px-2 py-1">
            {parseFloat(temperature).toFixed(1)}
          </span>
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
