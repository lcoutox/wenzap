"use client";

import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

function Toggle({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`
        relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer items-center rounded-full
        transition-colors duration-200 focus:outline-none
        ${checked ? "bg-nb-primary" : "bg-nb-border-strong"}
        ${disabled ? "opacity-50 cursor-not-allowed" : ""}
      `}
    >
      <span
        className={`
          pointer-events-none inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow
          transition duration-200
          ${checked ? "translate-x-[18px]" : "translate-x-[3px]"}
        `}
      />
    </button>
  );
}

export function ConfigConhecimento({
  knowledgeOnly,
  showSources,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onKnowledgeOnlyChange,
  onShowSourcesChange,
}: {
  knowledgeOnly: boolean;
  showSources: boolean;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onKnowledgeOnlyChange: (v: boolean) => void;
  onShowSourcesChange: (v: boolean) => void;
}) {
  return (
    <div className="space-y-6">
      <AgentFormSection
        title="Uso do conhecimento"
        description="Estas configurações controlam como o agente usa as fontes conectadas. Para conectar ou remover bases de conhecimento, use a aba Ferramentas."
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <Toggle checked={knowledgeOnly} onChange={onKnowledgeOnlyChange} disabled={readonly} />
            <div>
              <p className="text-sm font-medium text-nb-secondary">
                Responder apenas com base de conhecimento
              </p>
              <p className="text-xs text-nb-muted mt-0.5">
                Quando ativado, o agente evita responder fora das informações conectadas e oferece ajuda humana quando não souber.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <Toggle checked={showSources} onChange={onShowSourcesChange} disabled={readonly} />
            <div>
              <p className="text-sm font-medium text-nb-secondary">
                Mostrar fontes nas respostas
              </p>
              <p className="text-xs text-nb-muted mt-0.5">
                Quando ativado, o agente pode mencionar as fontes usadas nas respostas, quando disponíveis.
              </p>
            </div>
          </div>
        </div>
      </AgentFormSection>

      <AgentFormSection
        title="Bases de conhecimento e catálogo"
        description="Conecte e gerencie fontes de informação na aba Ferramentas."
      >
        <div className="p-3 bg-nb-elevated border border-nb-border rounded-xl text-sm text-nb-muted">
          As bases de conhecimento e o catálogo de produtos são configurados na aba{" "}
          <span className="text-nb-secondary font-medium">Ferramentas</span>.
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
