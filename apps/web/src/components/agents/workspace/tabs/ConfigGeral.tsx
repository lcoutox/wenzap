"use client";

import { useRef, useState } from "react";
import { Coins, Cpu, Bot, Upload, Trash2, Copy, Check, AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { SaveBar } from "@/components/agents/workspace/SaveBar";
import type { Agent, AgentStatus, AiModel } from "@/lib/api";

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

  const avatarUrl = api.agents.resolveAvatarUrl(agent);
  const hasAvatar = !!avatarUrl;

  return (
    <div className="flex items-center gap-5">
      <div className="relative flex-shrink-0">
        <div className="w-16 h-16 rounded-2xl overflow-hidden border border-nb-border bg-nb-primary-bg flex items-center justify-center">
          {hasAvatar ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={avatarUrl} alt={agent.name} className="w-full h-full object-cover" />
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

// ── Copy ID button ─────────────────────────────────────────────────────────────

function CopyIdButton({ id }: { id: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="flex items-center gap-2">
      <span className="font-mono text-xs text-nb-muted bg-nb-bg border border-nb-border rounded-lg px-2.5 py-1.5 select-all flex-1 truncate">
        {id}
      </span>
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-lg border border-nb-border bg-nb-elevated hover:bg-nb-soft text-nb-secondary transition-colors flex-shrink-0"
      >
        {copied ? (
          <>
            <Check className="w-3.5 h-3.5 text-nb-success" />
            Copiado
          </>
        ) : (
          <>
            <Copy className="w-3.5 h-3.5" />
            Copiar
          </>
        )}
      </button>
    </div>
  );
}

// ── Status control ─────────────────────────────────────────────────────────────

function StatusControl({
  agent,
  readonly,
  onChangeStatus,
}: {
  agent: Agent;
  readonly: boolean;
  onChangeStatus: (status: AgentStatus) => void;
}) {
  const isArchived = agent.status === "archived";

  if (isArchived) {
    return (
      <div className="flex items-center gap-3">
        <AgentStatusBadge status={agent.status} />
        <span className="text-xs text-nb-muted">Agente arquivado — restaure pela lista de agentes.</span>
      </div>
    );
  }

  const isActive = agent.status === "active";

  return (
    <div className="flex items-center gap-3">
      <AgentStatusBadge status={agent.status} />
      {!readonly && (
        <button
          type="button"
          onClick={() => onChangeStatus(isActive ? "inactive" : "active")}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-border bg-nb-elevated hover:bg-nb-soft text-nb-secondary hover:text-nb-text transition-colors"
        >
          {isActive ? "Desativar" : "Ativar"}
        </button>
      )}
    </div>
  );
}

// ── Danger zone ────────────────────────────────────────────────────────────────

function DangerZone({
  agent,
  onArchive,
  onDeletePermanently,
}: {
  agent: Agent;
  onArchive: () => void;
  onDeletePermanently: () => void;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmName, setConfirmName] = useState("");
  const [archiving, setArchiving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const isArchived = agent.status === "archived";
  const nameMatch = confirmName.trim() === agent.name.trim();

  async function handleArchive() {
    setArchiving(true);
    try {
      await onArchive();
    } finally {
      setArchiving(false);
    }
  }

  async function handleDelete() {
    if (!nameMatch) return;
    setDeleting(true);
    try {
      await onDeletePermanently();
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="rounded-2xl border border-nb-danger/30 bg-nb-danger/5 overflow-hidden">
      <div className="px-5 py-4 border-b border-nb-danger/20">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-nb-danger" />
          <h3 className="text-sm font-semibold text-nb-danger">Área de perigo</h3>
        </div>
      </div>

      <div className="divide-y divide-nb-danger/10">
        {/* Archive */}
        {!isArchived && (
          <div className="px-5 py-4 flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-nb-text">Arquivar agente</p>
              <p className="text-xs text-nb-muted mt-0.5">
                Remove da lista de agentes ativos. O histórico de conversas e configurações são preservados.
              </p>
            </div>
            <button
              type="button"
              disabled={archiving}
              onClick={handleArchive}
              className="flex-shrink-0 inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-danger/30 bg-nb-elevated hover:bg-nb-danger/10 text-nb-danger transition-colors disabled:opacity-50"
            >
              {archiving ? "Arquivando…" : "Arquivar"}
            </button>
          </div>
        )}

        {/* Permanent delete */}
        <div className="px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-nb-text">Excluir permanentemente</p>
              <p className="text-xs text-nb-muted mt-0.5">
                Apaga o agente e todas as configurações. Não é possível desfazer. Bloqueado se houver conversas ou canais ativos.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm((v) => !v)}
              className="flex-shrink-0 inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-danger/40 bg-nb-danger/10 hover:bg-nb-danger/20 text-nb-danger transition-colors"
            >
              Excluir
            </button>
          </div>

          {showDeleteConfirm && (
            <div className="mt-4 space-y-3 p-4 bg-nb-bg rounded-xl border border-nb-danger/20">
              <p className="text-xs text-nb-secondary">
                Para confirmar, digite o nome do agente:{" "}
                <span className="font-semibold text-nb-text">{agent.name}</span>
              </p>
              <input
                type="text"
                value={confirmName}
                onChange={(e) => setConfirmName(e.target.value)}
                placeholder={agent.name}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-danger focus:ring-1 focus:ring-nb-danger/30 transition-colors"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={!nameMatch || deleting}
                  onClick={handleDelete}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-xl bg-nb-danger text-white hover:bg-nb-danger/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {deleting ? "Excluindo…" : "Confirmar exclusão"}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowDeleteConfirm(false); setConfirmName(""); }}
                  className="inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-xl border border-nb-border bg-nb-elevated hover:bg-nb-soft text-nb-secondary transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
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
  onChangeStatus,
  onArchive,
  onDeletePermanently,
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
  onChangeStatus?: (status: AgentStatus) => void;
  onArchive?: () => void;
  onDeletePermanently?: () => void;
}) {
  const isArchived = agent.status === "archived";

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

      {/* Identidade */}
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
        <Field
          label="Objetivo do agente"
          hint="Descrição interna para identificar a função deste agente. As regras de comportamento ficam na aba Instruções."
        >
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

      {/* Status e identificadores */}
      <AgentFormSection title="Status e identificadores" description="Informações do agente na plataforma.">
        <div className="space-y-4">
          {/* Status */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Status</p>
            <StatusControl
              agent={agent}
              readonly={!onChangeStatus || isArchived}
              onChangeStatus={onChangeStatus ?? (() => {})}
            />
          </div>

          {/* ID */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">ID do agente</p>
            <CopyIdButton id={agent.id} />
          </div>

          {/* Datas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Criado em</p>
              <p className="text-sm text-nb-secondary">
                {new Date(agent.created_at).toLocaleDateString("pt-BR", {
                  day: "2-digit", month: "short", year: "numeric",
                })}
              </p>
            </div>
            <div className="space-y-1.5">
              <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Atualizado em</p>
              <p className="text-sm text-nb-secondary">
                {new Date(agent.updated_at).toLocaleDateString("pt-BR", {
                  day: "2-digit", month: "short", year: "numeric",
                })}
              </p>
            </div>
          </div>

          {/* Modelo ativo */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Modelo ativo</p>
            <div className="flex items-center gap-2">
              <Cpu className="w-4 h-4 text-nb-muted" />
              {activeModel ? (
                <span className="text-sm text-nb-secondary">{activeModel.display_name}</span>
              ) : (
                <span className="text-sm font-mono text-nb-muted">{agent.model_name}</span>
              )}
              {activeModel && activeModel.credits_per_message > 0 && (
                <div className="flex items-center gap-1 ml-2">
                  <Coins className="w-3.5 h-3.5 text-nb-warning" />
                  <span className="text-xs text-nb-warning font-medium">
                    {activeModel.credits_per_message} créd/msg
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </AgentFormSection>

      {!readonly && (
        <SaveBar saving={saving} saveError={saveError} saveSuccess={saveSuccess} />
      )}

      {/* Área de perigo */}
      {onArchive && onDeletePermanently && (
        <DangerZone
          agent={agent}
          onArchive={onArchive}
          onDeletePermanently={onDeletePermanently}
        />
      )}
    </div>
  );
}
