"use client";

import { useEffect, useState } from "react";
import { api, AgentKnowledgeBase } from "@/lib/api";
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

type KnowledgeFallback = "ask_context" | "direct_to_team" | "knowledge_general";

const FALLBACK_OPTIONS: { value: KnowledgeFallback; label: string; description: string }[] = [
  {
    value: "ask_context",
    label: "Pedir mais contexto",
    description: "O agente pede mais detalhes ao usuário antes de responder.",
  },
  {
    value: "direct_to_team",
    label: "Encaminhar para equipe",
    description: "O agente avisa que não encontrou a informação e oferece transferência para um humano.",
  },
  {
    value: "knowledge_general",
    label: "Usar conhecimento geral",
    description: "O agente responde com conhecimento geral, deixando claro que a resposta não veio da base.",
  },
];

export function ConfigConhecimento({
  agentId,
  knowledgeOnly,
  showSources,
  knowledgeFallback,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onKnowledgeOnlyChange,
  onShowSourcesChange,
  onKnowledgeFallbackChange,
  onSwitchToTools,
}: {
  agentId: string;
  knowledgeOnly: boolean;
  showSources: boolean;
  knowledgeFallback: KnowledgeFallback | null;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onKnowledgeOnlyChange: (v: boolean) => void;
  onShowSourcesChange: (v: boolean) => void;
  onKnowledgeFallbackChange: (v: KnowledgeFallback) => void;
  onSwitchToTools: () => void;
}) {
  const [connectedKbs, setConnectedKbs] = useState<AgentKnowledgeBase[]>([]);
  const [loadingKbs, setLoadingKbs] = useState(true);

  useEffect(() => {
    setLoadingKbs(true);
    api.agents.knowledgeBases
      .list(agentId)
      .then(setConnectedKbs)
      .catch(() => setConnectedKbs([]))
      .finally(() => setLoadingKbs(false));
  }, [agentId]);

  const effectiveFallback: KnowledgeFallback = knowledgeFallback ?? "ask_context";

  return (
    <div className="space-y-6">
      <AgentFormSection
        title="Fontes disponíveis"
        description="Bases de conhecimento conectadas a este agente."
      >
        {loadingKbs ? (
          <div className="text-xs text-nb-muted">Carregando fontes...</div>
        ) : connectedKbs.length === 0 ? (
          <div className="p-3 bg-nb-elevated border border-nb-border rounded-xl text-sm text-nb-muted">
            Nenhuma base de conhecimento conectada.{" "}
            <button
              type="button"
              onClick={onSwitchToTools}
              className="text-nb-primary underline hover:no-underline"
            >
              Gerenciar em Ferramentas
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {connectedKbs.map((kb) => (
              <div
                key={kb.id}
                className="flex items-center justify-between px-3 py-2 bg-nb-elevated border border-nb-border rounded-xl"
              >
                <span className="text-sm text-nb-secondary font-medium">{kb.knowledge_base_name}</span>
              </div>
            ))}
            <button
              type="button"
              onClick={onSwitchToTools}
              className="text-xs text-nb-primary underline hover:no-underline mt-1"
            >
              Gerenciar em Ferramentas
            </button>
          </div>
        )}
      </AgentFormSection>

      <AgentFormSection
        title="Uso do conhecimento"
        description="Controla como o agente usa as fontes conectadas ao responder."
      >
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <Toggle checked={knowledgeOnly} onChange={onKnowledgeOnlyChange} disabled={readonly} />
            <div>
              <p className="text-sm font-medium text-nb-secondary">
                Responder apenas com base de conhecimento
              </p>
              <p className="text-xs text-nb-muted mt-0.5">
                Quando ativado, o agente evita responder fora das informações conectadas.
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
                O agente pode mencionar as fontes usadas nas respostas, quando disponíveis.
              </p>
            </div>
          </div>
        </div>
      </AgentFormSection>

      <AgentFormSection
        title="Quando não encontrar resposta"
        description="O que o agente deve fazer quando a base de conhecimento não tiver informação suficiente."
      >
        <div className="space-y-2">
          {FALLBACK_OPTIONS.map((opt) => {
            const selected = effectiveFallback === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                disabled={readonly}
                onClick={() => !readonly && onKnowledgeFallbackChange(opt.value)}
                className={`w-full text-left px-4 py-3 rounded-xl border transition-colors ${
                  selected
                    ? "border-nb-primary bg-nb-primary/5"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <p className={`text-sm font-medium ${selected ? "text-nb-primary" : "text-nb-secondary"}`}>
                  {opt.label}
                </p>
                <p className="text-xs text-nb-muted mt-0.5">{opt.description}</p>
              </button>
            );
          })}
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
