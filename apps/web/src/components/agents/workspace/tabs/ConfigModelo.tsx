import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { ModelCardSelector } from "@/components/agents/ModelCardSelector";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

export function ConfigModelo({
  aiModelId,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onModelChange,
}: {
  aiModelId: string | null;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onModelChange: (modelId: string, modelName: string) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="Modelo de IA"
        description="Escolha o modelo que alimenta este agente. Modelos superiores consomem mais créditos por mensagem."
      >
        <ModelCardSelector
          aiModelId={aiModelId}
          disabled={readonly}
          onChange={onModelChange}
        />
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
