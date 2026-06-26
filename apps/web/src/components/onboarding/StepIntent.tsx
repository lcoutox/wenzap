"use client";

import type { OnboardingFormData } from "./OnboardingFlow";

type Props = {
  data: OnboardingFormData;
  onChange: (fields: Partial<OnboardingFormData>) => void;
  errors: Partial<Record<keyof OnboardingFormData, string>>;
};

const OBJECTIVES = [
  { value: "customer_support", label: "Atendimento ao cliente" },
  { value: "sales_qualification", label: "Vendas / qualificação de leads" },
  { value: "technical_support", label: "Suporte técnico" },
  { value: "scheduling", label: "Agendamento" },
  { value: "collections_followup", label: "Cobrança / follow-up" },
  { value: "other", label: "Outro" },
];

const VOLUMES = [
  { value: "up_to_100", label: "Até 100 conversas/mês" },
  { value: "100_to_500", label: "100 a 500 conversas/mês" },
  { value: "500_to_2000", label: "500 a 2.000 conversas/mês" },
  { value: "2000_plus", label: "Mais de 2.000 conversas/mês" },
];

const AI_EXPERIENCE = [
  { value: "never_used", label: "Nunca usei" },
  { value: "tested_tools", label: "Já testei algumas ferramentas" },
  { value: "using_in_production", label: "Já uso em operação" },
];

function OptionGroup({
  label,
  options,
  value,
  onChange,
  error,
  name,
}: {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  error?: string;
  name: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium text-nb-secondary mb-2">
        {label} <span className="text-nb-danger">*</span>
      </p>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            aria-pressed={value === opt.value}
            className={`px-3 py-2 rounded-xl text-sm font-medium border transition-colors cursor-pointer
              ${value === opt.value
                ? "bg-nb-primary-bg border-nb-primary text-nb-primary"
                : "bg-nb-elevated border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text"
              }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      {error && <p role="alert" className="text-nb-danger text-xs mt-1">{error}</p>}
    </div>
  );
}

export function StepIntent({ data, onChange, errors }: Props) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-nb-text">Como você pretende usar o Wenzap?</h2>
        <p className="text-nb-muted text-sm mt-1">
          Isso nos ajuda a adaptar sua jornada inicial.
        </p>
      </div>

      <div className="space-y-6">
        <OptionGroup
          name="main_objective"
          label="Principal objetivo"
          options={OBJECTIVES}
          value={data.main_objective}
          onChange={(v) => onChange({ main_objective: v })}
          error={errors.main_objective}
        />

        <OptionGroup
          name="expected_monthly_conversations"
          label="Volume mensal esperado de conversas"
          options={VOLUMES}
          value={data.expected_monthly_conversations}
          onChange={(v) => onChange({ expected_monthly_conversations: v })}
          error={errors.expected_monthly_conversations}
        />

        <OptionGroup
          name="ai_experience"
          label="Experiência com agentes de IA"
          options={AI_EXPERIENCE}
          value={data.ai_experience}
          onChange={(v) => onChange({ ai_experience: v })}
          error={errors.ai_experience}
        />
      </div>
    </div>
  );
}
