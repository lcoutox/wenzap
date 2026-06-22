import { Coins, Cpu } from "lucide-react";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type { Agent, AiModel } from "@/lib/api";

const baseInput =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent";
const disabledInput =
  "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-400 bg-gray-50 cursor-not-allowed";

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
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

export function ConfigGeral({
  agent,
  activeModel,
  name,
  description,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onNameChange,
  onDescriptionChange,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  name: string;
  description: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="Identidade"
        description="Nome e descrição exibidos na plataforma."
      >
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
        <Field label="Descrição" hint="Visível na listagem de agentes.">
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            rows={2}
            disabled={readonly}
            placeholder="Descreva o propósito deste agente"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection title="Status e modelo" description="Resumo do estado atual do agente.">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Status</p>
            <AgentStatusBadge status={agent.status} />
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Criado em</p>
            <p className="text-sm text-gray-700">
              {new Date(agent.created_at).toLocaleDateString("pt-BR", {
                day: "2-digit", month: "short", year: "numeric",
              })}
            </p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Modelo ativo</p>
            {activeModel ? (
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-700">{activeModel.display_name}</span>
              </div>
            ) : (
              <span className="text-sm font-mono text-gray-500">{agent.model_name}</span>
            )}
          </div>
          {activeModel && activeModel.credits_per_message > 0 && (
            <div className="space-y-1">
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Custo por mensagem</p>
              <div className="flex items-center gap-1.5">
                <Coins className="w-4 h-4 text-amber-500" />
                <span className="text-sm text-amber-600 font-medium">
                  {activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
          )}
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
