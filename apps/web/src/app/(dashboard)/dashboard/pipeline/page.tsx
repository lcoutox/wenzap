"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  Clock,
  Globe,
  KanbanSquare,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Phone,
  Plus,
  Smartphone,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  Agent,
  Pipeline,
  PipelineEntry,
  PipelineStage,
} from "@/lib/api";

// ── Helpers ────────────────────────────────────────────────────────────────────

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return "Agora";
  if (diffMins < 60) return `${diffMins}m`;
  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h`;
  return `${Math.floor(diffHrs / 24)}d`;
}

function channelIcon(type: string | null) {
  if (type === "whatsapp") return <Smartphone className="w-3 h-3 text-green-500" />;
  if (type === "web_widget") return <Globe className="w-3 h-3 text-nb-primary" />;
  return <MessageSquare className="w-3 h-3 text-nb-muted" />;
}

function statusBadge(status: string | null) {
  const map: Record<string, string> = {
    open: "bg-green-500/10 text-green-600 border-green-500/20",
    pending: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    resolved: "bg-nb-muted/10 text-nb-muted border-nb-border",
    archived: "bg-nb-elevated text-nb-muted border-nb-border",
  };
  const cls = map[status ?? ""] ?? "bg-nb-elevated text-nb-muted border-nb-border";
  const label: Record<string, string> = { open: "Aberta", pending: "Pendente", resolved: "Resolvida", archived: "Arquivada" };
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium border ${cls}`}>
      {label[status ?? ""] ?? status ?? "—"}
    </span>
  );
}

// ── Modal base ────────────────────────────────────────────────────────────────

function Modal({
  open,
  onClose,
  title,
  children,
  maxWidth = "max-w-lg",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  maxWidth?: string;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={(e) => e.target === overlayRef.current && onClose()}
    >
      <div className={`w-full ${maxWidth} bg-nb-surface border border-nb-border rounded-2xl shadow-2xl flex flex-col max-h-[90vh]`}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border shrink-0">
          <h2 className="text-sm font-semibold text-nb-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-nb-secondary mb-1.5">{label}</label>
      {children}
    </div>
  );
}

// ── CreatePipelineModal ────────────────────────────────────────────────────────

function CreatePipelineModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: (p: Pipeline) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) { setName(""); setDescription(""); setError(""); }
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true);
    setError("");
    try {
      const p = await api.pipelines.create({ name: name.trim(), description: description.trim() || null });
      onCreated(p);
    } catch {
      setError("Erro ao criar pipeline.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Novo Pipeline">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field label="Nome">
          <input
            autoFocus
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
            placeholder="Ex: Qualificação de leads"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Descrição (opcional)">
          <textarea
            rows={2}
            className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors resize-none"
            placeholder="Descreva o objetivo deste pipeline…"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        {error && <p className="text-xs text-nb-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" disabled={saving} className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors">
            {saving ? "Criando…" : "Criar Pipeline"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── StageModal ────────────────────────────────────────────────────────────────

type StageTab = "basico" | "ia" | "avancado";

function StageModal({
  open,
  onClose,
  onSaved,
  pipelineId,
  initial,
  agents,
  nextPosition,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (s: PipelineStage) => void;
  pipelineId: string;
  initial?: PipelineStage;
  agents: Agent[];
  nextPosition: number;
}) {
  const isEdit = !!initial;
  const [tab, setTab] = useState<StageTab>("basico");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isRequired, setIsRequired] = useState(false);
  const [isRemoval, setIsRemoval] = useState(false);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [assignedAgentId, setAssignedAgentId] = useState("");
  const [stayLimitEnabled, setStayLimitEnabled] = useState(false);
  const [stayLimitMinutes, setStayLimitMinutes] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookAuthHeader, setWebhookAuthHeader] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setTab("basico");
      setName(initial?.name ?? "");
      setDescription(initial?.description ?? "");
      setIsRequired(initial?.is_required ?? false);
      setIsRemoval(initial?.is_removal_stage ?? false);
      setExtraPrompt(initial?.extra_prompt ?? "");
      setAssignedAgentId(initial?.assigned_agent_id ?? "");
      setStayLimitEnabled(initial?.stay_limit_enabled ?? false);
      setStayLimitMinutes(initial?.stay_limit_minutes?.toString() ?? "");
      setWebhookUrl(initial?.webhook_url ?? "");
      setWebhookAuthHeader(initial?.webhook_auth_header ?? "");
      setError("");
    }
  }, [open, initial]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Nome é obrigatório."); setTab("basico"); return; }
    setSaving(true);
    setError("");
    const payload = {
      name: name.trim(),
      description: description.trim() || null,
      is_required: isRequired,
      is_removal_stage: isRemoval,
      extra_prompt: extraPrompt.trim() || null,
      assigned_agent_id: assignedAgentId || null,
      stay_limit_enabled: stayLimitEnabled,
      stay_limit_minutes: stayLimitEnabled && stayLimitMinutes ? parseInt(stayLimitMinutes) : null,
      webhook_url: webhookUrl.trim() || null,
      webhook_auth_header: webhookAuthHeader.trim() || null,
    };
    try {
      const saved = isEdit
        ? await api.pipelines.stages.update(pipelineId, initial!.id, payload)
        : await api.pipelines.stages.create(pipelineId, { ...payload, position: nextPosition });
      onSaved(saved);
    } catch {
      setError("Erro ao salvar etapa.");
    } finally {
      setSaving(false);
    }
  }

  const TABS: { id: StageTab; label: string }[] = [
    { id: "basico", label: "Básico" },
    { id: "ia", label: "IA" },
    { id: "avancado", label: "Avançado" },
  ];

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Editar Etapa" : "Nova Etapa"}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Tabs */}
        <div className="flex gap-1 p-1 bg-nb-elevated rounded-xl">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${tab === t.id ? "bg-nb-surface text-nb-text shadow-sm" : "text-nb-muted hover:text-nb-secondary"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "basico" && (
          <div className="space-y-4">
            <Field label="Nome">
              <input
                autoFocus
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
                placeholder="Ex: Qualificação inicial"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </Field>
            <Field label="Descrição (opcional)">
              <textarea
                rows={2}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors resize-none"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </Field>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-nb-border accent-nb-primary"
                  checked={isRequired}
                  onChange={(e) => setIsRequired(e.target.checked)}
                />
                <span className="text-xs text-nb-secondary">Etapa obrigatória</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  className="w-4 h-4 rounded border-nb-border accent-nb-primary"
                  checked={isRemoval}
                  onChange={(e) => setIsRemoval(e.target.checked)}
                />
                <span className="text-xs text-nb-secondary">Etapa de saída</span>
              </label>
            </div>
          </div>
        )}

        {tab === "ia" && (
          <div className="space-y-4">
            <Field label="Prompt adicional desta etapa">
              <textarea
                rows={5}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors resize-none font-mono"
                placeholder="Instrução extra que o agente deve seguir nesta etapa…"
                value={extraPrompt}
                onChange={(e) => setExtraPrompt(e.target.value)}
              />
            </Field>
            <Field label="Agente responsável (opcional)">
              <select
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                value={assignedAgentId}
                onChange={(e) => setAssignedAgentId(e.target.value)}
              >
                <option value="">Nenhum (usar padrão)</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </Field>
          </div>
        )}

        {tab === "avancado" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-nb-secondary">Limite de permanência</p>
                <p className="text-xs text-nb-muted mt-0.5">Mover automaticamente após X minutos</p>
              </div>
              <button
                type="button"
                onClick={() => setStayLimitEnabled((v) => !v)}
                className={`relative w-9 h-5 rounded-full transition-colors ${stayLimitEnabled ? "bg-nb-primary" : "bg-nb-border"}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${stayLimitEnabled ? "translate-x-4" : ""}`} />
              </button>
            </div>
            {stayLimitEnabled && (
              <Field label="Minutos">
                <input
                  type="number"
                  min={1}
                  className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                  placeholder="Ex: 60"
                  value={stayLimitMinutes}
                  onChange={(e) => setStayLimitMinutes(e.target.value)}
                />
              </Field>
            )}
            <Field label="Webhook URL (opcional)">
              <input
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
                placeholder="https://…"
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
              />
            </Field>
            <Field label="Webhook Auth Header (opcional)">
              <input
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
                placeholder="Bearer …"
                value={webhookAuthHeader}
                onChange={(e) => setWebhookAuthHeader(e.target.value)}
              />
            </Field>
          </div>
        )}

        {error && <p className="text-xs text-nb-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
            Cancelar
          </button>
          <button type="submit" disabled={saving} className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors">
            {saving ? "Salvando…" : isEdit ? "Salvar" : "Criar Etapa"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

// ── MoveEntryModal ────────────────────────────────────────────────────────────

function MoveEntryModal({
  open,
  onClose,
  onMoved,
  pipelineId,
  entryId,
  stages,
  currentStageId,
}: {
  open: boolean;
  onClose: () => void;
  onMoved: (entry: PipelineEntry) => void;
  pipelineId: string;
  entryId: string;
  stages: PipelineStage[];
  currentStageId: string | null;
}) {
  const [targetStageId, setTargetStageId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) { setTargetStageId(""); setError(""); }
  }, [open]);

  async function handleMove() {
    if (!targetStageId) { setError("Selecione uma etapa."); return; }
    setSaving(true);
    setError("");
    try {
      const entry = await api.pipelines.entries.move(pipelineId, entryId, targetStageId);
      onMoved(entry);
    } catch {
      setError("Erro ao mover conversa.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Mover para…">
      <div className="space-y-4">
        <div className="space-y-2">
          {stages
            .filter((s) => s.id !== currentStageId)
            .map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setTargetStageId(s.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl border text-left transition-colors ${targetStageId === s.id ? "border-nb-primary bg-nb-primary/5 text-nb-primary-strong" : "border-nb-border hover:bg-nb-elevated text-nb-secondary"}`}
              >
                <div className={`w-2 h-2 rounded-full shrink-0 ${targetStageId === s.id ? "bg-nb-primary" : "bg-nb-border"}`} />
                <span className="text-sm font-medium">{s.name}</span>
              </button>
            ))}
        </div>
        {error && <p className="text-xs text-nb-danger">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleMove}
            disabled={saving || !targetStageId}
            className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
          >
            {saving ? "Movendo…" : "Mover"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Entry card ────────────────────────────────────────────────────────────────

function EntryCard({
  entry,
  stages,
  pipelineId,
  onMoved,
  onRemoved,
}: {
  entry: PipelineEntry;
  stages: PipelineStage[];
  pipelineId: string;
  onMoved: (e: PipelineEntry) => void;
  onRemoved: (id: string) => void;
}) {
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [moveOpen, setMoveOpen] = useState(false);
  const [removing, setRemoving] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenuOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  async function handleRemove() {
    setMenuOpen(false);
    setRemoving(true);
    try {
      await api.pipelines.entries.delete(pipelineId, entry.id);
      onRemoved(entry.id);
    } catch {
      setRemoving(false);
    }
  }

  const contactLabel = entry.contact_name ?? "Contato desconhecido";
  const contactSub = entry.contact_phone ?? entry.contact_email ?? null;

  return (
    <>
      <div
        className="group relative bg-nb-surface border border-nb-border rounded-xl p-3 hover:border-nb-primary/30 hover:shadow-sm transition-all cursor-pointer"
        onClick={() => router.push(`/dashboard/inbox?conversationId=${entry.conversation_id}`)}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="min-w-0">
            <p className="text-xs font-semibold text-nb-text truncate">{contactLabel}</p>
            {contactSub && (
              <p className="text-[10px] text-nb-muted flex items-center gap-1 mt-0.5 truncate">
                <Phone className="w-2.5 h-2.5 shrink-0" />
                {contactSub}
              </p>
            )}
          </div>
          <div ref={menuRef} className="relative shrink-0" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="p-1 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary opacity-0 group-hover:opacity-100 transition-all"
              disabled={removing}
            >
              {removing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <MoreHorizontal className="w-3.5 h-3.5" />}
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-7 z-30 w-44 bg-nb-surface border border-nb-border rounded-xl shadow-lg py-1">
                <button
                  type="button"
                  onClick={() => { setMenuOpen(false); setMoveOpen(true); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-nb-secondary hover:bg-nb-elevated hover:text-nb-text transition-colors"
                >
                  <KanbanSquare className="w-3.5 h-3.5" />
                  Mover para…
                </button>
                <button
                  type="button"
                  onClick={handleRemove}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-nb-danger hover:bg-nb-danger/10 transition-colors"
                >
                  <X className="w-3.5 h-3.5" />
                  Remover do pipeline
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            {channelIcon(entry.conversation_channel_type)}
            {statusBadge(entry.conversation_status)}
          </div>
          <span className="flex items-center gap-1 text-[10px] text-nb-muted">
            <Clock className="w-2.5 h-2.5" />
            {timeAgo(entry.entered_stage_at ?? entry.created_at)}
          </span>
        </div>
      </div>

      <MoveEntryModal
        open={moveOpen}
        onClose={() => setMoveOpen(false)}
        onMoved={(e) => { setMoveOpen(false); onMoved(e); }}
        pipelineId={pipelineId}
        entryId={entry.id}
        stages={stages}
        currentStageId={entry.stage_id}
      />
    </>
  );
}

// ── Kanban column ─────────────────────────────────────────────────────────────

function KanbanColumn({
  stage,
  entries,
  stages,
  pipelineId,
  onEditStage,
  onMoved,
  onRemoved,
}: {
  stage: PipelineStage;
  entries: PipelineEntry[];
  stages: PipelineStage[];
  pipelineId: string;
  onEditStage: (s: PipelineStage) => void;
  onMoved: (e: PipelineEntry) => void;
  onRemoved: (id: string) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const close = (e: MouseEvent) => !menuRef.current?.contains(e.target as Node) && setMenuOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menuOpen]);

  return (
    <div className="flex-shrink-0 w-72 flex flex-col bg-nb-panel border border-nb-border rounded-2xl overflow-hidden">
      {/* Column header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-nb-border bg-nb-elevated/50">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold text-nb-text truncate">{stage.name}</span>
          <span className="shrink-0 px-1.5 py-0.5 text-[10px] font-medium bg-nb-elevated border border-nb-border text-nb-muted rounded-full">
            {entries.length}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((v) => !v)}
              className="p-1 rounded-lg hover:bg-nb-border text-nb-muted hover:text-nb-secondary transition-colors"
            >
              <MoreHorizontal className="w-3.5 h-3.5" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-7 z-30 w-36 bg-nb-surface border border-nb-border rounded-xl shadow-lg py-1">
                <button
                  type="button"
                  onClick={() => { setMenuOpen(false); onEditStage(stage); }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium text-nb-secondary hover:bg-nb-elevated hover:text-nb-text transition-colors"
                >
                  Editar etapa
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Cards */}
      <div className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[120px]">
        {entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center">
            <MessageSquare className="w-6 h-6 text-nb-muted mb-2" />
            <p className="text-xs text-nb-muted">Nenhuma conversa</p>
          </div>
        ) : (
          entries.map((e) => (
            <EntryCard
              key={e.id}
              entry={e}
              stages={stages}
              pipelineId={pipelineId}
              onMoved={onMoved}
              onRemoved={onRemoved}
            />
          ))
        )}
      </div>
    </div>
  );
}

// ── PipelineSelector ──────────────────────────────────────────────────────────

function PipelineSelector({
  pipelines,
  selectedId,
  onSelect,
}: {
  pipelines: Pipeline[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const selected = pipelines.find((p) => p.id === selectedId);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 bg-nb-surface border border-nb-border rounded-xl text-sm font-medium text-nb-text hover:bg-nb-elevated transition-colors"
      >
        <KanbanSquare className="w-4 h-4 text-nb-primary" />
        <span className="truncate max-w-48">{selected?.name ?? "Selecionar pipeline"}</span>
        <ChevronDown className="w-4 h-4 text-nb-muted shrink-0" />
      </button>
      {open && (
        <div className="absolute left-0 top-10 z-20 w-72 bg-nb-surface border border-nb-border rounded-xl shadow-lg py-1">
          {pipelines.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => { setOpen(false); onSelect(p.id); }}
              className={`w-full flex items-center gap-2 px-3 py-2.5 text-xs font-medium transition-colors ${p.id === selectedId ? "text-nb-primary-strong bg-nb-primary/5" : "text-nb-secondary hover:bg-nb-elevated hover:text-nb-text"}`}
            >
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${p.id === selectedId ? "bg-nb-primary" : "bg-nb-border"}`} />
              {p.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PipelinePage() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState<string | null>(null);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [entries, setEntries] = useState<PipelineEntry[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mobile: show one stage at a time
  const [mobileStageIdx, setMobileStageIdx] = useState(0);

  // Modals
  const [createPipelineOpen, setCreatePipelineOpen] = useState(false);
  const [stageModalOpen, setStageModalOpen] = useState(false);
  const [editingStage, setEditingStage] = useState<PipelineStage | undefined>(undefined);

  // Load pipelines and agents on mount
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const [pList, aList] = await Promise.all([
          api.pipelines.list(),
          api.agents.list(),
        ]);
        setPipelines(pList);
        setAgents(aList);
        if (pList.length > 0) setSelectedPipelineId(pList[0].id);
      } catch {
        setError("Erro ao carregar pipelines.");
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  // Load board when selected pipeline changes
  const loadBoard = useCallback(async (pipelineId: string) => {
    setLoadingBoard(true);
    try {
      const [sList, eList] = await Promise.all([
        api.pipelines.stages.list(pipelineId),
        api.pipelines.entries.list(pipelineId),
      ]);
      setStages(sList.sort((a, b) => a.position - b.position));
      setEntries(eList);
      setMobileStageIdx(0);
    } catch {
      setError("Erro ao carregar quadro.");
    } finally {
      setLoadingBoard(false);
    }
  }, []);

  useEffect(() => {
    if (selectedPipelineId) loadBoard(selectedPipelineId);
  }, [selectedPipelineId, loadBoard]);

  function handleEntryMoved(updated: PipelineEntry) {
    setEntries((prev) => prev.map((e) => e.id === updated.id ? updated : e));
  }

  function handleEntryRemoved(id: string) {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }

  function handleStageSaved(stage: PipelineStage) {
    setStageModalOpen(false);
    setEditingStage(undefined);
    setStages((prev) => {
      const exists = prev.find((s) => s.id === stage.id);
      if (exists) return prev.map((s) => s.id === stage.id ? stage : s).sort((a, b) => a.position - b.position);
      return [...prev, stage].sort((a, b) => a.position - b.position);
    });
  }

  function openEditStage(stage: PipelineStage) {
    setEditingStage(stage);
    setStageModalOpen(true);
  }

  function openNewStage() {
    setEditingStage(undefined);
    setStageModalOpen(true);
  }

  const sortedStages = [...stages].sort((a, b) => a.position - b.position);
  const mobileStage = sortedStages[mobileStageIdx] ?? null;
  const mobileEntries = mobileStage ? entries.filter((e) => e.stage_id === mobileStage.id) : [];

  // ── Render ──

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-nb-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <p className="text-sm text-nb-danger">{error}</p>
        <button type="button" onClick={() => window.location.reload()} className="text-xs text-nb-primary hover:underline">
          Recarregar
        </button>
      </div>
    );
  }

  // Empty state — no pipelines
  if (pipelines.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center">
          <KanbanSquare className="w-8 h-8 text-nb-primary" />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold text-nb-text mb-1">Nenhum pipeline criado</p>
          <p className="text-xs text-nb-muted">Crie seu primeiro pipeline para organizar conversas por etapas</p>
        </div>
        <button
          type="button"
          onClick={() => setCreatePipelineOpen(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors"
        >
          <Plus className="w-4 h-4" />
          Criar Pipeline
        </button>
        <CreatePipelineModal
          open={createPipelineOpen}
          onClose={() => setCreatePipelineOpen(false)}
          onCreated={(p) => { setPipelines([p]); setSelectedPipelineId(p.id); setCreatePipelineOpen(false); }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap shrink-0">
        <div className="flex items-center gap-3">
          <PipelineSelector
            pipelines={pipelines}
            selectedId={selectedPipelineId ?? ""}
            onSelect={setSelectedPipelineId}
          />
        </div>
        <button
          type="button"
          onClick={() => setCreatePipelineOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          Novo Pipeline
        </button>
      </div>

      {/* Mobile stage selector */}
      {stages.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-1 md:hidden shrink-0">
          {sortedStages.map((s, i) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setMobileStageIdx(i)}
              className={`shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${mobileStageIdx === i ? "bg-nb-primary text-white border-nb-primary" : "bg-nb-surface text-nb-muted border-nb-border hover:bg-nb-elevated"}`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}

      {/* Board */}
      {loadingBoard ? (
        <div className="flex items-center justify-center h-48">
          <Loader2 className="w-5 h-5 animate-spin text-nb-muted" />
        </div>
      ) : selectedPipelineId ? (
        <>
          {/* Desktop: horizontal scroll */}
          <div className="hidden md:flex gap-4 overflow-x-auto pb-4 flex-1 items-start">
            {sortedStages.map((stage) => (
              <KanbanColumn
                key={stage.id}
                stage={stage}
                entries={entries.filter((e) => e.stage_id === stage.id)}
                stages={sortedStages}
                pipelineId={selectedPipelineId}
                onEditStage={openEditStage}
                onMoved={handleEntryMoved}
                onRemoved={handleEntryRemoved}
              />
            ))}
            {/* Add stage button */}
            <div className="flex-shrink-0 w-72">
              <button
                type="button"
                onClick={openNewStage}
                className="w-full flex items-center justify-center gap-2 py-4 border-2 border-dashed border-nb-border rounded-2xl text-sm text-nb-muted hover:border-nb-primary/40 hover:text-nb-primary hover:bg-nb-primary/5 transition-all"
              >
                <Plus className="w-4 h-4" />
                Nova Etapa
              </button>
            </div>
          </div>

          {/* Mobile: single column */}
          <div className="md:hidden flex-1">
            {mobileStage ? (
              <KanbanColumn
                stage={mobileStage}
                entries={mobileEntries}
                stages={sortedStages}
                pipelineId={selectedPipelineId}
                onEditStage={openEditStage}
                onMoved={handleEntryMoved}
                onRemoved={handleEntryRemoved}
              />
            ) : (
              <div className="flex flex-col items-center justify-center h-48 gap-3">
                <p className="text-sm text-nb-muted">Nenhuma etapa criada</p>
                <button type="button" onClick={openNewStage} className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl">
                  <Plus className="w-3.5 h-3.5" /> Nova Etapa
                </button>
              </div>
            )}
          </div>
        </>
      ) : null}

      {/* Modals */}
      <CreatePipelineModal
        open={createPipelineOpen}
        onClose={() => setCreatePipelineOpen(false)}
        onCreated={(p) => {
          setPipelines((prev) => [...prev, p]);
          setSelectedPipelineId(p.id);
          setCreatePipelineOpen(false);
        }}
      />

      {selectedPipelineId && (
        <>
          <StageModal
            open={stageModalOpen}
            onClose={() => { setStageModalOpen(false); setEditingStage(undefined); }}
            onSaved={handleStageSaved}
            pipelineId={selectedPipelineId}
            initial={editingStage}
            agents={agents}
            nextPosition={stages.length}
          />
        </>
      )}
    </div>
  );
}
