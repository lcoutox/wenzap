"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import { api } from "@/lib/api";
import type { ResponseStyle, LanguageMode } from "@/lib/api";

const RESPONSE_STYLE_OPTIONS: { value: ResponseStyle; label: string; description: string }[] = [
  { value: "concise",  label: "Objetivo",    description: "Respostas curtas e diretas. Ideal para widget e WhatsApp." },
  { value: "balanced", label: "Equilibrado", description: "Respostas claras com contexto suficiente, sem excesso de detalhe." },
  { value: "detailed", label: "Detalhado",   description: "Respostas mais completas para suporte aprofundado." },
];

const LANGUAGE_OPTIONS: { value: LanguageMode; label: string }[] = [
  { value: "auto", label: "Automático — responde no idioma do usuário" },
  { value: "pt",   label: "Português (Brasil)" },
  { value: "en",   label: "Inglês" },
  { value: "es",   label: "Espanhol" },
];

const REPLY_DELAY_OPTIONS: { value: number; label: string; recommended?: boolean }[] = [
  { value: 0,  label: "Imediato" },
  { value: 3,  label: "3 segundos" },
  { value: 5,  label: "5 segundos", recommended: true },
  { value: 8,  label: "8 segundos" },
  { value: 15, label: "15 segundos" },
];

const baseSelect =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const disabledSelect =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

export function ConfigApresentacao({
  responseStyle,
  languageMode,
  replyDelaySeconds,
  voiceReplyEnabled,
  elevenlabsVoiceId,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onResponseStyleChange,
  onLanguageModeChange,
  onReplyDelaySecondsChange,
  onVoiceReplyEnabledChange,
  onElevenlabsVoiceIdChange,
}: {
  responseStyle: ResponseStyle;
  languageMode: LanguageMode;
  replyDelaySeconds: number;
  voiceReplyEnabled: boolean;
  elevenlabsVoiceId: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onResponseStyleChange: (v: ResponseStyle) => void;
  onLanguageModeChange: (v: LanguageMode) => void;
  onReplyDelaySecondsChange: (v: number) => void;
  onVoiceReplyEnabledChange: (v: boolean) => void;
  onElevenlabsVoiceIdChange: (v: string) => void;
}) {
  const [elevenlabsConfigured, setElevenlabsConfigured] = useState<boolean | null>(null);

  useEffect(() => {
    api.workspace.integrations.get()
      .then((r) => setElevenlabsConfigured(r.elevenlabs_configured))
      .catch(() => setElevenlabsConfigured(null));
  }, []);

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
                className={`text-left rounded-xl border p-4 transition-colors ${
                  active
                    ? "border-nb-primary bg-nb-primary/5 ring-1 ring-nb-primary/30"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"
                } ${readonly ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
              >
                <p className={`text-sm font-semibold mb-1 ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>{label}</p>
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
        <select
          value={languageMode}
          disabled={readonly}
          onChange={(e) => onLanguageModeChange(e.target.value as LanguageMode)}
          className={readonly ? disabledSelect : baseSelect}
        >
          {LANGUAGE_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </AgentFormSection>

      {/* Tempo de resposta */}
      <AgentFormSection
        title="Tempo de resposta"
        description="O agente espera alguns segundos após a última mensagem do cliente antes de responder. Isso evita respostas quebradas quando o cliente envia várias mensagens seguidas."
      >
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          {REPLY_DELAY_OPTIONS.map(({ value, label, recommended }) => {
            const active = replyDelaySeconds === value;
            return (
              <button
                key={value}
                type="button"
                disabled={readonly}
                onClick={() => !readonly && onReplyDelaySecondsChange(value)}
                className={`
                  relative text-left rounded-xl border p-3 transition-all text-sm
                  ${readonly ? "cursor-not-allowed opacity-60" : "cursor-pointer"}
                  ${active
                    ? "border-nb-primary bg-nb-primary-bg/50 ring-1 ring-nb-primary/40"
                    : "border-nb-border bg-nb-elevated hover:border-nb-border-strong"}
                `}
              >
                <span className={`font-medium ${active ? "text-nb-primary-strong" : "text-nb-text"}`}>
                  {label}
                </span>
                {recommended && (
                  <span className="block text-[10px] text-nb-primary mt-0.5">Recomendado</span>
                )}
              </button>
            );
          })}
        </div>
        {replyDelaySeconds === 0 && (
          <p className="text-xs text-nb-muted mt-2">
            Pode responder mais rápido, mas pode gerar respostas antes do cliente terminar de digitar.
          </p>
        )}
      </AgentFormSection>

      {/* Resposta em áudio */}
      <AgentFormSection
        title="Resposta em áudio no WhatsApp"
        description="Quando o cliente manda uma mensagem de voz, o agente pode responder também em áudio, além do texto."
      >
        <div className="space-y-3">
          <label className={`flex items-center gap-3 ${readonly ? "cursor-not-allowed opacity-60" : "cursor-pointer"}`}>
            <input
              type="checkbox"
              checked={voiceReplyEnabled}
              disabled={readonly}
              onChange={(e) => onVoiceReplyEnabledChange(e.target.checked)}
              className="h-4 w-4 rounded border-nb-border accent-nb-primary"
            />
            <span className="text-sm text-nb-text">Responder em áudio quando o cliente enviar áudio</span>
          </label>

          {voiceReplyEnabled && (
            <div className="pl-7 space-y-2">
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  ID da voz na ElevenLabs
                </label>
                <input
                  type="text"
                  value={elevenlabsVoiceId}
                  disabled={readonly}
                  onChange={(e) => onElevenlabsVoiceIdChange(e.target.value)}
                  placeholder="Ex: 21m00Tcm4TlvDq8ikWAM"
                  className={readonly ? disabledSelect : baseSelect}
                />
                <p className="text-[11px] text-nb-muted mt-1">
                  Copie o ID da voz escolhida no painel da ElevenLabs (Voices → sua voz → Voice ID).
                </p>
              </div>

              {elevenlabsConfigured === false && (
                <p className="text-xs text-nb-danger">
                  Você ainda não cadastrou sua chave da ElevenLabs — sem ela, a resposta em áudio
                  não vai funcionar.{" "}
                  <Link href="/dashboard/settings?tab=integrations" className="underline underline-offset-2">
                    Cadastrar chave
                  </Link>
                </p>
              )}
            </div>
          )}
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}
    </div>
  );
}
