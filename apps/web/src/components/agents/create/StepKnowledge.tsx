import { Loader2, BookOpen } from "lucide-react";
import type { KnowledgeBase } from "@/lib/api";

export function StepKnowledge({
  kbs,
  loading,
  selectedKbIds,
  onSelectionChange,
}: {
  kbs: KnowledgeBase[];
  loading: boolean;
  selectedKbIds: string[];
  onSelectionChange: (ids: string[]) => void;
}) {

  function toggle(id: string) {
    if (selectedKbIds.includes(id)) {
      onSelectionChange(selectedKbIds.filter((x) => x !== id));
    } else {
      onSelectionChange([...selectedKbIds, id]);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">
          Quais informações o agente deve usar?
        </h2>
        <p className="text-sm text-nb-muted mt-1">
          Conecte bases de conhecimento para o agente usar como referência. Você pode pular e configurar depois.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-nb-muted py-6">
          <Loader2 className="w-4 h-4 animate-spin" />
          Carregando bases de conhecimento…
        </div>
      ) : kbs.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-10 text-center">
          <div className="w-12 h-12 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
            <BookOpen className="w-6 h-6 text-nb-muted" />
          </div>
          <p className="text-sm font-medium text-nb-secondary">
            Você ainda não tem bases de conhecimento.
          </p>
          <p className="text-xs text-nb-muted max-w-xs">
            Crie o agente agora e conecte uma base depois, na aba Conhecimento.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {kbs.map((kb) => {
            const selected = selectedKbIds.includes(kb.id);
            return (
              <label
                key={kb.id}
                className={`flex items-center gap-3 p-3.5 rounded-xl border cursor-pointer transition-all ${
                  selected
                    ? "border-nb-primary bg-nb-primary-bg"
                    : "border-nb-border bg-nb-elevated hover:bg-nb-panel"
                }`}
              >
                <div
                  className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center border transition-all ${
                    selected ? "bg-nb-primary border-nb-primary" : "border-nb-border-strong"
                  }`}
                >
                  {selected && (
                    <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={selected}
                  onChange={() => toggle(kb.id)}
                />
                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-medium ${selected ? "text-nb-primary-strong" : "text-nb-text"}`}>
                    {kb.name}
                  </p>
                  {kb.description && (
                    <p className="text-xs text-nb-muted truncate">{kb.description}</p>
                  )}
                </div>
                <span className="text-xs text-nb-muted flex-shrink-0">
                  {kb.status === "active" ? "Ativa" : kb.status}
                </span>
              </label>
            );
          })}
          {selectedKbIds.length > 0 && (
            <p className="text-xs text-nb-muted pt-1">
              {selectedKbIds.length}{" "}
              {selectedKbIds.length === 1 ? "base selecionada" : "bases selecionadas"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
