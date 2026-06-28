import type { ToneOption } from "./wizard-types";
import { ALL_RULES } from "./wizard-types";

const ALL_TONES: ToneOption[] = [
  "Profissional",
  "Simpático",
  "Direto ao ponto",
  "Consultivo",
  "Descontraído",
  "Técnico",
];

const baseTextarea =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

export function StepBehavior({
  tones,
  rules,
  avoidText,
  additionalInstructions,
  onTonesChange,
  onRulesChange,
  onAvoidTextChange,
  onAdditionalInstructionsChange,
  errors,
}: {
  tones: ToneOption[];
  rules: string[];
  avoidText: string;
  additionalInstructions: string;
  onTonesChange: (v: ToneOption[]) => void;
  onRulesChange: (v: string[]) => void;
  onAvoidTextChange: (v: string) => void;
  onAdditionalInstructionsChange: (v: string) => void;
  errors: { tones?: string };
}) {
  function toggleTone(tone: ToneOption) {
    if (tones.includes(tone)) {
      onTonesChange(tones.filter((t) => t !== tone));
    } else {
      onTonesChange([...tones, tone]);
    }
  }

  function toggleRule(id: string) {
    if (rules.includes(id)) {
      onRulesChange(rules.filter((r) => r !== id));
    } else {
      onRulesChange([...rules, id]);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-nb-text">Comportamento</h2>
        <p className="text-sm text-nb-muted mt-1">
          Defina como o agente deve agir e se comunicar.
        </p>
      </div>

      {/* Tom de voz */}
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium text-nb-secondary">
            Tom de voz <span className="text-nb-danger">*</span>
          </p>
          <p className="text-xs text-nb-muted mt-0.5">
            Selecione um ou mais estilos de comunicação.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {ALL_TONES.map((tone) => {
            const selected = tones.includes(tone);
            return (
              <button
                key={tone}
                type="button"
                onClick={() => toggleTone(tone)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
                  selected
                    ? "bg-nb-primary border-nb-primary text-white"
                    : "bg-nb-elevated border-nb-border text-nb-secondary hover:border-nb-border-strong"
                }`}
              >
                {tone}
              </button>
            );
          })}
        </div>
        {errors.tones && (
          <p className="text-xs text-nb-danger">{errors.tones}</p>
        )}
      </div>

      {/* Regras principais */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-nb-secondary">Regras principais</p>
        <div className="space-y-2">
          {ALL_RULES.map((rule) => {
            const checked = rules.includes(rule.id);
            return (
              <label
                key={rule.id}
                className="flex items-center gap-3 p-3 rounded-xl border border-nb-border bg-nb-elevated hover:bg-nb-panel cursor-pointer transition-colors"
              >
                <div
                  className={`w-4 h-4 rounded flex-shrink-0 flex items-center justify-center border transition-all ${
                    checked
                      ? "bg-nb-primary border-nb-primary"
                      : "border-nb-border-strong bg-transparent"
                  }`}
                >
                  {checked && (
                    <svg className="w-2.5 h-2.5 text-white" fill="none" stroke="currentColor" strokeWidth={3} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </div>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={checked}
                  onChange={() => toggleRule(rule.id)}
                />
                <span className="text-sm text-nb-secondary">{rule.label}</span>
              </label>
            );
          })}
        </div>
      </div>

      {/* O que evitar */}
      <div className="space-y-1.5">
        <label className="block text-sm font-medium text-nb-secondary">
          O que o agente deve evitar{" "}
          <span className="font-normal text-nb-muted">(opcional)</span>
        </label>
        <textarea
          value={avoidText}
          onChange={(e) => onAvoidTextChange(e.target.value)}
          rows={3}
          placeholder="Ex: Não prometer descontos, não confirmar prazos sem consultar a equipe, não inventar informações."
          className={baseTextarea}
        />
      </div>

      {/* Instruções adicionais */}
      <div className="space-y-1.5">
        <label className="block text-sm font-medium text-nb-secondary">
          Instruções adicionais{" "}
          <span className="font-normal text-nb-muted">(opcional)</span>
        </label>
        <textarea
          value={additionalInstructions}
          onChange={(e) => onAdditionalInstructionsChange(e.target.value)}
          rows={3}
          placeholder="Ex: Sempre pergunte nome e telefone antes de encaminhar para o time comercial."
          className={baseTextarea}
        />
      </div>
    </div>
  );
}
