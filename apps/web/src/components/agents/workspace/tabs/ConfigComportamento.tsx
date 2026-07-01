"use client";

import type { LanguageMode, ResponseStyle } from "@/lib/api";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";

// ── Response style cards ───────────────────────────────────────────────────────

const RESPONSE_STYLE_OPTIONS: {
  value: ResponseStyle;
  label: string;
  description: string;
}[] = [
  {
    value: "concise",
    label: "Objetivo",
    description:
      "Respostas curtas e diretas. Ideal para widget, WhatsApp e atendimento rápido.",
  },
  {
    value: "balanced",
    label: "Equilibrado",
    description:
      "Respostas claras, com contexto suficiente, sem excesso de detalhe.",
  },
  {
    value: "detailed",
    label: "Detalhado",
    description:
      "Respostas mais completas para explicações e suporte aprofundado.",
  },
];

// ── Language mode options ─────────────────────────────────────────────────────

const LANGUAGE_OPTIONS: { value: LanguageMode; label: string }[] = [
  { value: "auto",  label: "Automático — responde no idioma do usuário" },
  { value: "pt",    label: "Português (Brasil)" },
  { value: "en",    label: "Inglês" },
  { value: "es",    label: "Espanhol" },
];

// ── Toggle component ──────────────────────────────────────────────────────────

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

// ── Main component ────────────────────────────────────────────────────────────

export function ConfigComportamento({
  responseStyle,
  languageMode,
  knowledgeOnly,
  showSources,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onResponseStyleChange,
  onLanguageModeChange,
  onKnowledgeOnlyChange,
  onShowSourcesChange,
}: {
  responseStyle: ResponseStyle;
  languageMode: LanguageMode;
  knowledgeOnly: boolean;
  showSources: boolean;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onResponseStyleChange: (v: ResponseStyle) => void;
  onLanguageModeChange: (v: LanguageMode) => void;
  onKnowledgeOnlyChange: (v: boolean) => void;
  onShowSourcesChange: (v: boolean) => void;
}) {
  return (
    <div className="space-y-6">
      {/* Estilo de resposta */}
      <AgentFormSection
        title="Estilo de resposta"
        description="Define o tamanho e a profundidade das respostas geradas pelo agente."
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {RESPONSE_STYLE_OPTIONS.map(({ value, label, description }) => {
            const active = responseStyle === value;
            return (
              <button
                key={value}
                type="button"
                disabled={readonly}
                onClick={() => !readonly && onResponseStyleChange(value)}
                className={`
                  text-left rounded-xl border p-4 transition-colors
                  ${active
                    ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"}
                  ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
                `}
              >
                <p className={`text-sm font-semibold mb-1 ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>
                  {label}
                </p>
                <p className="text-xs text-nb-muted leading-relaxed">{description}</p>
              </button>
            );
          })}
        </div>
      </AgentFormSection>

      {/* Idioma */}
      <AgentFormSection
        title="Idioma"
        description="Define em qual idioma o agente responde, independente do idioma da pergunta."
      >
        <div className="space-y-1.5">
          <select
            value={languageMode}
            disabled={readonly}
            onChange={(e) => onLanguageModeChange(e.target.value as LanguageMode)}
            className={`
              w-full rounded-xl border px-3 py-2 text-sm transition-colors
              focus:outline-none focus:ring-1 focus:ring-nb-primary/30
              ${readonly
                ? "bg-nb-bg border-nb-border text-nb-muted cursor-not-allowed"
                : "bg-nb-elevated border-nb-border text-nb-text focus:border-nb-primary"}
            `}
          >
            {LANGUAGE_OPTIONS.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </AgentFormSection>

      {/* Restrições de conhecimento */}
      <AgentFormSection
        title="Restrições de conhecimento"
        description="Controla se o agente pode responder fora das fontes conectadas."
      >
        <div className="space-y-4">
          {/* knowledge_only */}
          <div className="flex items-start gap-3">
            <Toggle
              checked={knowledgeOnly}
              onChange={onKnowledgeOnlyChange}
              disabled={readonly}
            />
            <div>
              <p className="text-sm font-medium text-nb-secondary">
                Responder apenas com base de conhecimento
              </p>
              <p className="text-xs text-nb-muted mt-0.5">
                Quando ativado, o agente evita responder fora das informações conectadas
                e oferece ajuda humana quando não souber.
              </p>
            </div>
          </div>

          {/* show_sources */}
          <div className="flex items-start gap-3">
            <Toggle
              checked={showSources}
              onChange={onShowSourcesChange}
              disabled={readonly}
            />
            <div>
              <p className="text-sm font-medium text-nb-secondary">
                Mostrar fontes nas respostas
              </p>
              <p className="text-xs text-nb-muted mt-0.5">
                Quando ativado, o agente pode mencionar as fontes usadas nas respostas,
                quando disponíveis.
              </p>
            </div>
          </div>
        </div>
      </AgentFormSection>

      <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
    </div>
  );
}
