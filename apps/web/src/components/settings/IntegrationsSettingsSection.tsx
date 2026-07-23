"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { IntegrationProvider, WorkspaceIntegrations } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

type ProviderConfig = {
  provider: IntegrationProvider;
  name: string;
  description: string;
  keyPlaceholder: string;
  helpUrl: string;
  helpLabel: string;
};

const PROVIDERS: ProviderConfig[] = [
  {
    provider: "groq",
    name: "Groq",
    description: "Transcreve os áudios recebidos no WhatsApp para texto, para o agente entender e responder.",
    keyPlaceholder: "gsk_...",
    helpUrl: "https://console.groq.com/keys",
    helpLabel: "Pegar chave no console da Groq",
  },
  {
    provider: "elevenlabs",
    name: "ElevenLabs",
    description: "Permite que o agente responda em áudio quando o cliente manda uma mensagem de voz.",
    keyPlaceholder: "sk_...",
    helpUrl: "https://elevenlabs.io/app/settings/api-keys",
    helpLabel: "Pegar chave na ElevenLabs",
  },
];

function ProviderCard({
  config,
  configured,
  onChanged,
}: {
  config: ProviderConfig;
  configured: boolean;
  onChanged: () => void;
}) {
  const { showToast } = useToast();
  const [editing, setEditing] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);

  async function handleSave() {
    if (!apiKey.trim()) return;
    setSaving(true);
    try {
      await api.workspace.integrations.set(config.provider, apiKey.trim());
      showToast("success", `Chave da ${config.name} salva com sucesso.`);
      setApiKey("");
      setEditing(false);
      onChanged();
    } catch (err: unknown) {
      showToast("error", err instanceof ApiError ? err.message : "Erro ao salvar a chave.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setRemoving(true);
    try {
      await api.workspace.integrations.remove(config.provider);
      showToast("success", `Chave da ${config.name} removida.`);
      onChanged();
    } catch (err: unknown) {
      showToast("error", err instanceof ApiError ? err.message : "Erro ao remover a chave.");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <div className="bg-nb-panel border border-nb-border rounded-2xl p-5 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-nb-text">{config.name}</h3>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-lg text-[11px] font-medium border ${
                configured
                  ? "bg-nb-success/10 text-nb-success border-nb-success/20"
                  : "bg-nb-elevated text-nb-muted border-nb-border"
              }`}
            >
              {configured ? "Configurado" : "Não configurado"}
            </span>
          </div>
          <p className="text-xs text-nb-muted mt-1 max-w-md">{config.description}</p>
        </div>
      </div>

      {editing ? (
        <div className="space-y-2 pt-1">
          <input
            type="password"
            autoFocus
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={config.keyPlaceholder}
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
          />
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !apiKey.trim()}
              className="px-3 py-1.5 bg-nb-primary text-white text-xs font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar chave"}
            </button>
            <button
              type="button"
              onClick={() => { setEditing(false); setApiKey(""); }}
              className="px-3 py-1.5 text-xs font-medium text-nb-muted hover:text-nb-secondary transition-colors"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3 pt-1">
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="px-3 py-1.5 bg-nb-elevated border border-nb-border text-xs font-medium text-nb-text rounded-xl hover:border-nb-border-strong transition-colors"
          >
            {configured ? "Trocar chave" : "Adicionar chave"}
          </button>
          {configured && (
            <button
              type="button"
              onClick={handleRemove}
              disabled={removing}
              className="px-3 py-1.5 text-xs font-medium text-nb-danger hover:text-nb-danger/80 disabled:opacity-40 transition-colors"
            >
              {removing ? "Removendo..." : "Remover"}
            </button>
          )}
          <a
            href={config.helpUrl}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-xs text-nb-muted hover:text-nb-secondary transition-colors underline underline-offset-2"
          >
            {config.helpLabel}
          </a>
        </div>
      )}
    </div>
  );
}

export function IntegrationsSettingsSection() {
  const [integrations, setIntegrations] = useState<WorkspaceIntegrations | null>(null);

  function reload() {
    api.workspace.integrations.get().then(setIntegrations).catch(() => {});
  }

  useEffect(() => {
    reload();
  }, []);

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-nb-text">Integrações de áudio no WhatsApp</h2>
        <p className="text-xs text-nb-muted mt-0.5 max-w-lg">
          Cadastre suas próprias chaves da Groq e da ElevenLabs para habilitar transcrição e
          resposta em áudio nas conversas do WhatsApp. As chaves são usadas só pelo seu workspace —
          o Wenzap nunca vê nem armazena o texto em claro depois de salvo.
        </p>
      </div>

      {integrations && (
        <div className="grid gap-4">
          {PROVIDERS.map((config) => (
            <ProviderCard
              key={config.provider}
              config={config}
              configured={
                config.provider === "groq"
                  ? integrations.groq_configured
                  : integrations.elevenlabs_configured
              }
              onChanged={reload}
            />
          ))}
        </div>
      )}
    </div>
  );
}
