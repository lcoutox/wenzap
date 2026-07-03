"use client";

import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { ModelCardSelector } from "@/components/agents/ModelCardSelector";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import { CONTEXT_TIERS, CONTEXT_TIER_PLAN_LIMITS } from "@/lib/api";
import type { ContextTier } from "@/lib/api";

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

export function ConfigModelo({
  aiModelId,
  temperature,
  contextTier,
  planCode,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onModelChange,
  onTemperatureChange,
  onContextTierChange,
}: {
  aiModelId: string | null;
  temperature: string;
  contextTier: ContextTier;
  planCode: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onModelChange: (modelId: string, modelName: string) => void;
  onTemperatureChange: (v: string) => void;
  onContextTierChange: (tier: ContextTier) => void;
}) {
  return (
    <div className="space-y-5">
      {/* Seção 1 — Modelo de IA */}
      <AgentFormSection
        title="Modelo de IA"
        description="Escolha o modelo que executa este agente. Modelos mais avançados consomem mais créditos por mensagem."
      >
        <ModelCardSelector
          aiModelId={aiModelId}
          disabled={readonly}
          onChange={onModelChange}
        />
      </AgentFormSection>

      {/* Seção 2 — Contexto do agente */}
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

      {/* Seção 3 — Avançado */}
      <AgentFormSection
        title="Avançado"
        description="Configurações avançadas de geração de texto."
      >
        <div className="space-y-3">
          <label className="block text-sm text-nb-secondary">
            Criatividade
            <span className="text-nb-muted ml-1 text-xs">
              (valores mais baixos = respostas mais precisas)
            </span>
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              value={temperature}
              onChange={(e) => onTemperatureChange(e.target.value)}
              step="0.1"
              min="0"
              max="1"
              disabled={readonly}
              className="flex-1 accent-nb-primary disabled:opacity-50"
            />
            <span className="w-10 text-sm font-mono text-center text-nb-secondary bg-nb-elevated border border-nb-border rounded-lg px-2 py-1">
              {parseFloat(temperature).toFixed(1)}
            </span>
          </div>
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
