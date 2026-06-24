import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

function PlaceholderToggle({ label, description }: { label: string; description: string }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-nb-border last:border-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-nb-muted">{label}</p>
        <p className="text-xs text-nb-muted/60 mt-0.5">{description}</p>
      </div>
      <div className="flex-shrink-0 flex items-center gap-2">
        <span className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-nb-elevated text-nb-muted border border-nb-border leading-none tracking-wide">
          EM BREVE
        </span>
        <div className="w-9 h-5 rounded-full bg-nb-border cursor-not-allowed opacity-40" />
      </div>
    </div>
  );
}

export function ConfigAvancado({
  temperature,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onTemperatureChange,
}: {
  temperature: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onTemperatureChange: (v: string) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="Geração de texto"
        description="Configurações que afetam como o modelo gera respostas."
      >
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-nb-secondary">
            Temperatura
          </label>
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
          <p className="text-xs text-nb-muted">
            Controla a criatividade das respostas. 0 = mais preciso, 1 = mais criativo.
          </p>
        </div>
      </AgentFormSection>

      <AgentFormSection
        title="Comportamento"
        description="Configurações de runtime. Disponíveis nas próximas fases."
      >
        <PlaceholderToggle label="Saída em Markdown" description="Formatar respostas com markdown." />
        <PlaceholderToggle label="Modo JSON" description="Forçar o modelo a retornar apenas JSON estruturado." />
        <PlaceholderToggle label="Detecção automática de idioma" description="Responder no idioma da mensagem recebida." />
        <PlaceholderToggle label="Ignorar imagens" description="Não processar imagens enviadas pelo usuário." />
      </AgentFormSection>

      <AgentFormSection
        title="Inatividade"
        description="Configurações de timeout e mensagens automáticas. Disponíveis na Phase 5."
      >
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <label className="text-sm font-medium text-nb-muted flex-1">
              Timeout de inatividade
            </label>
            <input
              type="number"
              disabled
              placeholder="ex: 30"
              className="w-24 bg-nb-bg border border-nb-border rounded-xl px-3 py-1.5 text-sm text-nb-muted cursor-not-allowed"
            />
            <span className="text-sm text-nb-muted">minutos</span>
            <span className="px-1.5 py-0.5 text-[9px] font-bold rounded bg-nb-elevated text-nb-muted border border-nb-border leading-none tracking-wide">
              EM BREVE
            </span>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-nb-muted">Mensagem de inatividade</label>
            <input
              type="text"
              disabled
              placeholder="ex: Ainda está por aí? Posso ajudar com mais alguma coisa?"
              className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed"
            />
          </div>
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
