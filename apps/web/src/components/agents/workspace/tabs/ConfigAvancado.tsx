import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import { CONTEXT_TIERS, CONTEXT_TIER_PLAN_LIMITS } from "@/lib/api";
import type { ContextTier } from "@/lib/api";

const TEMPERATURE_PRESETS = [
  {
    id: "conservative",
    label: "Conservador",
    value: 0.2,
    description: "Respostas consistentes e previsíveis. Ideal para suporte e FAQ.",
  },
  {
    id: "balanced",
    label: "Equilibrado",
    value: 0.7,
    description: "Combina precisão com naturalidade. Bom para a maioria dos casos.",
  },
  {
    id: "creative",
    label: "Criativo",
    value: 1.0,
    description: "Respostas mais variadas e elaboradas. Útil para vendas e engajamento.",
  },
];

function formatChars(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(0)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function ContextTierCard({
  tier,
  selected,
  disabled,
  planCode,
  onClick,
}: {
  tier: typeof CONTEXT_TIERS[number];
  selected: boolean;
  disabled: boolean;
  planCode: string;
  onClick: () => void;
}) {
  const allowed = (CONTEXT_TIER_PLAN_LIMITS[planCode] ?? CONTEXT_TIER_PLAN_LIMITS["starter"]).includes(tier.code);
  const locked = !allowed;

  return (
    <button
      type="button"
      disabled={disabled || locked}
      onClick={onClick}
      className={`
        relative flex flex-col gap-1.5 rounded-xl border p-3 text-left transition-all
        ${selected
          ? "border-nb-primary bg-nb-primary/5 shadow-sm"
          : "border-nb-border bg-nb-panel hover:border-nb-border-strong"}
        ${(disabled || locked) ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <span className={`text-sm font-semibold ${selected ? "text-nb-primary-strong" : "text-nb-primary-text"}`}>
          {tier.label}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          {locked && (
            <span className="text-[10px] font-medium bg-nb-elevated border border-nb-border text-nb-muted px-1.5 py-0.5 rounded-md">
              Plano superior
            </span>
          )}
          {selected && !locked && (
            <span className="text-[10px] font-medium bg-nb-primary text-white px-1.5 py-0.5 rounded-md">
              Selecionado
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-nb-muted">
        <span>{formatChars(tier.maxChars)} caracteres</span>
        <span>·</span>
        <span>{tier.creditMultiplier}× créditos</span>
      </div>

      <p className="text-xs text-nb-muted leading-relaxed">
        {tier.description}
      </p>
    </button>
  );
}

export function ConfigAvancado({
  temperature,
  contextTier,
  planCode,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onTemperatureChange,
  onContextTierChange,
}: {
  temperature: string;
  contextTier: ContextTier;
  planCode: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onTemperatureChange: (v: string) => void;
  onContextTierChange: (tier: ContextTier) => void;
}) {
  return (
    <div className="space-y-5">
      <AgentFormSection
        title="Contexto do agente"
        description="Define quanto conteúdo o agente consegue considerar antes de responder, incluindo instruções, histórico da conversa, base de conhecimento, catálogo e dados de ferramentas. Quanto maior o contexto, maior o consumo de créditos."
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {CONTEXT_TIERS.map((tier) => (
            <ContextTierCard
              key={tier.code}
              tier={tier}
              selected={contextTier === tier.code}
              disabled={readonly}
              planCode={planCode}
              onClick={() => onContextTierChange(tier.code)}
            />
          ))}
        </div>
      </AgentFormSection>

      <AgentFormSection
        title="Temperatura"
        description="Valores baixos deixam o agente mais consistente. Valores altos deixam as respostas mais variadas e criativas, mas menos previsíveis."
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {TEMPERATURE_PRESETS.map((preset) => {
            const selected = parseFloat(temperature).toFixed(1) === preset.value.toFixed(1);
            return (
              <button
                key={preset.id}
                type="button"
                disabled={readonly}
                onClick={() => onTemperatureChange(String(preset.value))}
                className={`text-left rounded-xl border p-3.5 transition-all ${
                  selected
                    ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <div className="flex items-start justify-between gap-1 mb-1">
                  <p className={`text-sm font-semibold ${selected ? "text-nb-primary-strong" : "text-nb-text"}`}>
                    {preset.label}
                  </p>
                  <span className={`font-mono text-xs px-1.5 py-0.5 rounded-md border flex-shrink-0 ${
                    selected
                      ? "bg-nb-primary/10 border-nb-primary/30 text-nb-primary-strong"
                      : "bg-nb-bg border-nb-border text-nb-muted"
                  }`}>
                    {preset.value.toFixed(1)}
                  </span>
                </div>
                <p className="text-xs text-nb-muted leading-relaxed">{preset.description}</p>
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
