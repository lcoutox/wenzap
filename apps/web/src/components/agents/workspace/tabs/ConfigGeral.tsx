import { Coins, Cpu } from "lucide-react";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type { Agent, AiModel } from "@/lib/api";

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const disabledInput =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-nb-secondary">{label}</label>
      {children}
      {hint && <p className="text-xs text-nb-muted">{hint}</p>}
    </div>
  );
}

export function ConfigGeral({
  agent,
  activeModel,
  name,
  description,
  catalogEnabled,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onNameChange,
  onDescriptionChange,
  onCatalogEnabledChange,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  name: string;
  description: string;
  catalogEnabled: boolean;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onCatalogEnabledChange: (v: boolean) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection title="Identidade" description="Nome e descrição exibidos na plataforma.">
        <Field label="Nome *">
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            required
            maxLength={100}
            disabled={readonly}
            placeholder="Ex: Agente de Suporte"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
        <Field label="Objetivo do agente" hint="Diga o que este agente deve fazer.">
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            rows={2}
            disabled={readonly}
            placeholder="Ex: Qualificar leads interessados nos serviços da empresa"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection title="Status e modelo" description="Resumo do estado atual do agente.">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Status</p>
            <AgentStatusBadge status={agent.status} />
          </div>
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Criado em</p>
            <p className="text-sm text-nb-secondary">
              {new Date(agent.created_at).toLocaleDateString("pt-BR", {
                day: "2-digit", month: "short", year: "numeric",
              })}
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Modelo ativo</p>
            {activeModel ? (
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-nb-muted" />
                <span className="text-sm text-nb-secondary">{activeModel.display_name}</span>
              </div>
            ) : (
              <span className="text-sm font-mono text-nb-muted">{agent.model_name}</span>
            )}
          </div>
          {activeModel && activeModel.credits_per_message > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Custo por mensagem</p>
              <div className="flex items-center gap-1.5">
                <Coins className="w-4 h-4 text-nb-warning" />
                <span className="text-sm text-nb-warning font-medium">
                  {activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
          )}
        </div>
      </AgentFormSection>

      <AgentFormSection
        title="Recursos do agente"
        description="Defina quais fontes de informação este agente pode consultar."
      >
        <label className="flex items-start gap-4 cursor-pointer group">
          <button
            type="button"
            role="switch"
            aria-checked={catalogEnabled}
            disabled={readonly}
            onClick={() => !readonly && onCatalogEnabledChange(!catalogEnabled)}
            className={`relative mt-0.5 flex-shrink-0 w-10 h-6 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-nb-primary/40 ${
              catalogEnabled ? "bg-nb-primary" : "bg-nb-border-strong"
            } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
          >
            <span
              className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                catalogEnabled ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </button>
          <div>
            <p className="text-sm font-medium text-nb-secondary">
              Usar Catálogo nas respostas
            </p>
            <p className="text-xs text-nb-muted mt-0.5">
              Permite que este agente consulte itens cadastrados no Catálogo para recomendar
              produtos, serviços, planos ou ofertas durante o atendimento.
            </p>
          </div>
        </label>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
