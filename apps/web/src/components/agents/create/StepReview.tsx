"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { KnowledgeBase, AiCatalog } from "@/lib/api";
import type { WizardState } from "./wizard-types";
import { ALL_RULES, CREATIVITY_TEMPERATURE } from "./wizard-types";
import { buildSystemPrompt } from "./buildSystemPrompt";

const AGENT_TYPE_LABELS: Record<string, string> = {
  support:     "Atendimento ao cliente",
  sales:       "Vendas / qualificação de leads",
  tech:        "Suporte técnico",
  scheduling:  "Agendamento",
  collections: "Cobrança / follow-up",
  blank:       "Do zero",
};

const CREATIVITY_LABELS: Record<string, string> = {
  precise:  "Mais preciso",
  balanced: "Equilibrado",
  creative: "Mais criativo",
};

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-4 py-2.5 border-b border-nb-border last:border-0">
      <span className="w-36 flex-shrink-0 text-xs font-semibold text-nb-muted uppercase tracking-wide">
        {label}
      </span>
      <span className="text-sm text-nb-secondary">{value}</span>
    </div>
  );
}

export function StepReview({
  state,
  catalog,
  kbs,
}: {
  state: WizardState;
  catalog: AiCatalog | null;
  kbs: KnowledgeBase[];
}) {
  function findModelDisplayName(): string | null {
    if (!catalog || !state.aiModelId) return null;
    for (const p of catalog.providers) {
      const m = p.models.find((m) => m.id === state.aiModelId);
      if (m) return m.display_name;
    }
    return null;
  }

  const modelDisplayName = findModelDisplayName();
  const kbNames: Record<string, string> = {};
  kbs.forEach((kb) => { kbNames[kb.id] = kb.name; });
  const [promptOpen, setPromptOpen] = useState(false);

  const systemPrompt = buildSystemPrompt(state);
  const temperature  = CREATIVITY_TEMPERATURE[state.creativity];

  const ruleLabels = state.rules
    .map((id) => ALL_RULES.find((r) => r.id === id)?.label)
    .filter(Boolean) as string[];

  const selectedKbNames = state.selectedKbIds.map(
    (id) => kbNames[id] ?? id
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">Revisão</h2>
        <p className="text-sm text-nb-muted mt-1">
          Confira as configurações antes de criar o agente.
        </p>
      </div>

      <div className="bg-nb-elevated border border-nb-border rounded-2xl px-4 divide-y divide-nb-border">
        {state.agentType && (
          <Row label="Tipo" value={AGENT_TYPE_LABELS[state.agentType]} />
        )}
        <Row label="Nome" value={state.name || <span className="text-nb-muted">—</span>} />
        <Row
          label="Objetivo"
          value={
            state.description || <span className="text-nb-muted">—</span>
          }
        />
        <Row
          label="Tom de voz"
          value={
            state.tones.length > 0
              ? state.tones.join(", ")
              : <span className="text-nb-muted">—</span>
          }
        />
        {ruleLabels.length > 0 && (
          <Row
            label="Regras"
            value={
              <ul className="space-y-0.5">
                {ruleLabels.map((r) => (
                  <li key={r} className="flex items-center gap-1.5">
                    <span className="w-1 h-1 rounded-full bg-nb-muted flex-shrink-0" />
                    {r}
                  </li>
                ))}
              </ul>
            }
          />
        )}
        <Row
          label="Modelo"
          value={modelDisplayName ?? <span className="text-nb-muted">—</span>}
        />
        <Row
          label="Criatividade"
          value={`${CREATIVITY_LABELS[state.creativity]} (${temperature.toFixed(1)})`}
        />
        <Row
          label="Conhecimento"
          value={
            selectedKbNames.length > 0
              ? selectedKbNames.join(", ")
              : <span className="text-nb-muted">Nenhuma base selecionada</span>
          }
        />
      </div>

      {/* Preview recolhível das instruções */}
      <div className="border border-nb-border rounded-2xl overflow-hidden">
        <button
          type="button"
          onClick={() => setPromptOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-nb-secondary hover:bg-nb-elevated transition-colors"
        >
          <span>Ver instruções que serão usadas pelo agente</span>
          {promptOpen ? (
            <ChevronUp className="w-4 h-4 text-nb-muted" />
          ) : (
            <ChevronDown className="w-4 h-4 text-nb-muted" />
          )}
        </button>
        {promptOpen && (
          <pre className="px-4 py-3 text-xs text-nb-muted font-mono whitespace-pre-wrap bg-nb-bg border-t border-nb-border leading-relaxed max-h-64 overflow-y-auto">
            {systemPrompt}
          </pre>
        )}
      </div>
    </div>
  );
}
