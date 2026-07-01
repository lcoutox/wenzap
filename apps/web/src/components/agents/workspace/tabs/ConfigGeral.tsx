"use client";

import { useRef, useState } from "react";
import { Coins, Cpu, Bot, Upload, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type { Agent, AiModel } from "@/lib/api";

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const disabledInput =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

const ACCEPTED = "image/jpeg,image/png,image/webp";
const MAX_MB = 5;

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-nb-secondary">{label}</label>
      {children}
      {hint && <p className="text-xs text-nb-muted">{hint}</p>}
    </div>
  );
}

// ── Avatar uploader ────────────────────────────────────────────────────────────

function AvatarUploader({
  agent,
  readonly,
  onAvatarChange,
}: {
  agent: Agent;
  readonly: boolean;
  onAvatarChange: (updated: Agent) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setError(null);
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`Imagem deve ter no máximo ${MAX_MB} MB.`);
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Formato inválido. Use JPEG, PNG ou WebP.");
      return;
    }
    setUploading(true);
    try {
      const updated = await api.agents.uploadAvatar(agent.id, file);
      onAvatarChange(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao enviar avatar.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function handleDelete() {
    setError(null);
    setUploading(true);
    try {
      const updated = await api.agents.deleteAvatar(agent.id);
      onAvatarChange(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao remover avatar.");
    } finally {
      setUploading(false);
    }
  }

  const hasAvatar = !!agent.avatar_url;

  return (
    <div className="flex items-center gap-5">
      {/* Preview */}
      <div className="relative flex-shrink-0">
        <div className="w-16 h-16 rounded-2xl overflow-hidden border border-nb-border bg-nb-primary-bg flex items-center justify-center">
          {hasAvatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={agent.avatar_url!}
              alt={agent.name}
              className="w-full h-full object-cover"
            />
          ) : (
            <Bot className="w-7 h-7 text-nb-primary-strong" />
          )}
        </div>
        {uploading && (
          <div className="absolute inset-0 rounded-2xl bg-nb-bg/70 flex items-center justify-center">
            <div className="w-4 h-4 border-2 border-nb-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          {!readonly && (
            <button
              type="button"
              disabled={uploading}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-border bg-nb-elevated hover:bg-nb-soft text-nb-secondary hover:text-nb-text transition-colors disabled:opacity-50"
            >
              <Upload className="w-3.5 h-3.5" />
              {hasAvatar ? "Alterar avatar" : "Enviar avatar"}
            </button>
          )}
          {hasAvatar && !readonly && (
            <button
              type="button"
              disabled={uploading}
              onClick={handleDelete}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-danger/20 bg-nb-danger/5 hover:bg-nb-danger/10 text-nb-danger transition-colors disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Remover
            </button>
          )}
        </div>
        <p className="text-xs text-nb-muted">JPEG, PNG ou WebP · máx. {MAX_MB} MB</p>
        {error && <p className="text-xs text-nb-danger">{error}</p>}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
      />
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export function ConfigGeral({
  agent,
  activeModel,
  name,
  description,
  readonly,
  saving,
  saveError,
  saveSuccess,
  onNameChange,
  onDescriptionChange,
  onAvatarChange,
}: {
  agent: Agent;
  activeModel: AiModel | null;
  name: string;
  description: string;
  readonly: boolean;
  saving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  onNameChange: (v: string) => void;
  onDescriptionChange: (v: string) => void;
  onAvatarChange?: (updated: Agent) => void;
}) {
  return (
    <div className="space-y-5">
      {/* Avatar */}
      <AgentFormSection
        title="Avatar do agente"
        description="Imagem exibida no painel e na lista de agentes."
      >
        <AvatarUploader
          agent={agent}
          readonly={readonly}
          onAvatarChange={onAvatarChange ?? (() => {})}
        />
      </AgentFormSection>

      <AgentFormSection title="Identidade" description="Nome e descrição exibidos na plataforma.">
        <Field label="Nome *">
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            required
            maxLength={100}
            disabled={readonly}
            placeholder="Ex: Agente de Suporte"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
        <Field label="Objetivo do agente" hint="Diga o que este agente deve fazer.">
          <textarea
            value={description}
            onChange={(e) => onDescriptionChange(e.target.value)}
            rows={2}
            disabled={readonly}
            placeholder="Ex: Qualificar leads interessados nos serviços da empresa"
            className={readonly ? disabledInput : baseInput}
          />
        </Field>
      </AgentFormSection>

      <AgentFormSection title="Status e modelo" description="Resumo do estado atual do agente.">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Status</p>
            <AgentStatusBadge status={agent.status} />
          </div>
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Criado em</p>
            <p className="text-sm text-nb-secondary">
              {new Date(agent.created_at).toLocaleDateString("pt-BR", {
                day: "2-digit", month: "short", year: "numeric",
              })}
            </p>
          </div>
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Modelo ativo</p>
            {activeModel ? (
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-nb-muted" />
                <span className="text-sm text-nb-secondary">{activeModel.display_name}</span>
              </div>
            ) : (
              <span className="text-sm font-mono text-nb-muted">{agent.model_name}</span>
            )}
          </div>
          {activeModel && activeModel.credits_per_message > 0 && (
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Custo por mensagem</p>
              <div className="flex items-center gap-1.5">
                <Coins className="w-4 h-4 text-nb-warning" />
                <span className="text-sm text-nb-warning font-medium">
                  {activeModel.credits_per_message} crédito{activeModel.credits_per_message !== 1 ? "s" : ""}
                </span>
              </div>
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
