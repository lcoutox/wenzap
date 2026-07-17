import { AGENT_TEMPLATES } from "./templates";
import type { TemplateId } from "./templates";

export function StepTemplate({
  value,
  onChange,
}: {
  value: TemplateId | null;
  onChange: (id: TemplateId) => void;
}) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">
          Com qual template você quer começar?
        </h2>
        <p className="text-sm text-nb-muted mt-1">
          O template pré-configura as instruções do agente. Você pode ajustar tudo depois.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {AGENT_TEMPLATES.map((t) => {
          const selected = value === t.id;
          const isBlank = t.id === "blank";
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onChange(t.id)}
              className={`text-left flex items-start gap-3 p-4 rounded-xl border transition-all ${
                isBlank ? "sm:col-span-2" : ""
              } ${
                selected
                  ? "border-nb-primary bg-nb-primary-bg ring-1 ring-nb-primary/30"
                  : "border-nb-border bg-nb-elevated hover:border-nb-border-strong hover:bg-nb-panel"
              }`}
            >
              <div
                className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center text-lg transition-colors ${
                  selected ? "bg-nb-primary/10" : "bg-nb-panel border border-nb-border"
                }`}
              >
                {t.icon}
              </div>
              <div className="min-w-0">
                <p className={`text-sm font-semibold leading-snug ${selected ? "text-nb-primary-strong" : "text-nb-text"}`}>
                  {t.label}
                </p>
                <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">{t.tagline}</p>
                {isBlank && (
                  <p className="text-xs text-nb-warning mt-1 leading-relaxed">
                    {t.description} Você precisa escrever o prompt manualmente antes de ativar.
                  </p>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
