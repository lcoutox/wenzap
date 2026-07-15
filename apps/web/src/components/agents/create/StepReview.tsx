"use client";

import type { KnowledgeBase, AiCatalog } from "@/lib/api";
import type { WizardState } from "./wizard-types";
import { CREATIVITY_TEMPERATURE } from "./wizard-types";
import type { AgentTemplate } from "./templates";

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
  selectedTemplate,
}: {
  state: WizardState;
  catalog: AiCatalog | null;
  kbs: KnowledgeBase[];
  selectedTemplate: AgentTemplate | null;
}) {
  function findModelDisplayName(): string | null {
    if (!catalog || !state.aiModelId) return null;
    for (const p of catalog.providers) {
      const m = p.models.find((m) => m.id === state.aiModelId);
      if (m) return m.display_name;
    }
    return null;
  }

  const kbMap: Record<string, string> = {};
  kbs.forEach((kb) => { kbMap[kb.id] = kb.name; });

  const modelDisplayName  = findModelDisplayName();
  const temperature       = CREATIVITY_TEMPERATURE[state.creativity];
  const selectedKbNames   = state.selectedKbIds.map((id) => kbMap[id] ?? id);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">Revisão</h2>
        <p className="text-sm text-nb-muted mt-1">
          Confira as configurações antes de criar o agente.
        </p>
      </div>

      <div className="bg-nb-elevated border border-nb-border rounded-2xl px-4 divide-y divide-nb-border">
        {selectedTemplate && (
          <Row
            label="Template"
            value={
              <span className="flex items-center gap-1.5">
                <span>{selectedTemplate.icon}</span>
                <span>{selectedTemplate.label}</span>
              </span>
            }
          />
        )}
        <Row label="Nome" value={state.name || <span className="text-nb-muted">—</span>} />
        <Row
          label="Objetivo"
          value={state.description || <span className="text-nb-muted">—</span>}
        />
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
        {selectedTemplate && selectedTemplate.id !== "blank" && state.guidedConfig.main_objective && (
          <Row label="Objetivo do agente" value={state.guidedConfig.main_objective} />
        )}
      </div>

      <p className="text-xs text-nb-muted px-1">
        As instruções de comportamento foram configuradas pelo template e podem ser ajustadas depois na aba Instruções.
      </p>
    </div>
  );
}
