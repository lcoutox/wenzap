"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useDraggable, useDroppable } from "@dnd-kit/core";
import {
  BarChart3,
  ChevronDown,
  Clock,
  Globe,
  GripVertical,
  KanbanSquare,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Phone,
  Plus,
  Smartphone,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  Agent,
  Member,
  Pipeline,
  PipelineEntry,
  PipelineMetrics,
  PipelineStage,
} from "@/lib/api";

const CONVERSATION_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "open", label: "Aberta" },
  { value: "pending", label: "Pendente" },
  { value: "resolved", label: "Resolvida" },
  { value: "archived", label: "Arquivada" },
];

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
  members,
  nextPosition,
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (s: PipelineStage) => void;
  pipelineId: string;
  initial?: PipelineStage;
  agents: Agent[];
  members: Member[];
  nextPosition: number;
}) {
  const isEdit = !!initial;
  const [tab, setTab] = useState<StageTab>("basico");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isRequired, setIsRequired] = useState(false);
  const [isRemoval, setIsRemoval] = useState(false);
  const [extraPrompt, setExtraPrompt] = useState("");
  const [entryCondition, setEntryCondition] = useState("");
  const [assignedAgentId, setAssignedAgentId] = useState("");
  const [requestContactInfo, setRequestContactInfo] = useState(false);
  const [stayLimitEnabled, setStayLimitEnabled] = useState(false);
  const [stayLimitMinutes, setStayLimitMinutes] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookAuthHeader, setWebhookAuthHeader] = useState("");
  const [onEnterStatus, setOnEnterStatus] = useState("");
  const [onEnterAssignedUserId, setOnEnterAssignedUserId] = useState("");
  const [onEnterAiEnabled, setOnEnterAiEnabled] = useState(""); // "" | "true" | "false"
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
      setEntryCondition(initial?.entry_condition ?? "");
      setAssignedAgentId(initial?.assigned_agent_id ?? "");
      setRequestContactInfo(initial?.request_contact_info ?? false);
      setStayLimitEnabled(initial?.stay_limit_enabled ?? false);
      setStayLimitMinutes(initial?.stay_limit_minutes?.toString() ?? "");
      setWebhookUrl(initial?.webhook_url ?? "");
      setOnEnterStatus(initial?.on_enter_conversation_status ?? "");
      setOnEnterAssignedUserId(initial?.on_enter_assigned_user_id ?? "");
      setOnEnterAiEnabled(
        initial?.on_enter_ai_enabled === true
          ? "true"
          : initial?.on_enter_ai_enabled === false
          ? "false"
          : ""
      );
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
      entry_condition: entryCondition.trim() || null,
      assigned_agent_id: assignedAgentId || null,
      request_contact_info: requestContactInfo,
      stay_limit_enabled: stayLimitEnabled,
      stay_limit_minutes: stayLimitEnabled && stayLimitMinutes ? parseInt(stayLimitMinutes) : null,
      webhook_url: webhookUrl.trim() || null,
      webhook_auth_header: webhookAuthHeader.trim() || null,
      on_enter_conversation_status: onEnterStatus || null,
      on_enter_assigned_user_id: onEnterAssignedUserId || null,
      on_enter_ai_enabled: onEnterAiEnabled === "" ? null : onEnterAiEnabled === "true",
    };
    try {
      const saved = isEdit
        ? await api.pipelines.stages.update(pipelineId, initial!.id, payload)
        : await api.pipelines.stages.create(pipelineId, { ...payload, position: nextPosition });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Erro ao salvar etapa.");
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
            <Field label="Condição de entrada automática (opcional, requer plano Scale+)">
              <textarea
                rows={3}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors resize-none"
                placeholder="Ex: Cliente confirmou interesse em comprar"
                value={entryCondition}
                onChange={(e) => setEntryCondition(e.target.value)}
              />
              <p className="text-[11px] text-nb-muted mt-1.5">
                Descrita em linguagem natural. A IA avalia a conversa a cada mensagem e move
                automaticamente pra esta etapa quando a condição for satisfeita.
              </p>
            </Field>
            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-nb-border accent-nb-primary mt-0.5"
                checked={requestContactInfo}
                onChange={(e) => setRequestContactInfo(e.target.checked)}
              />
              <span className="text-xs text-nb-secondary">
                Pedir dados de contato faltantes (nome, e-mail, telefone) nesta etapa
              </span>
            </label>
          </div>
        )}

        {tab === "avancado" && (
          <div className="space-y-4">
            <div className="rounded-lg bg-nb-elevated border border-nb-border px-3 py-2">
              <p className="text-[11px] text-nb-muted">
                Limite de permanência, webhook e ações de entrada só disparam em workspaces no
                plano <strong>Scale</strong> ou superior. No plano atual esses campos ficam
                salvos mas não são executados.
              </p>
            </div>
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

            <div className="pt-2 border-t border-nb-border">
              <p className="text-xs font-medium text-nb-secondary mb-3">Ao entrar nesta etapa</p>
              <div className="space-y-3">
                <Field label="Mudar status da conversa">
                  <select
                    className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                    value={onEnterStatus}
                    onChange={(e) => setOnEnterStatus(e.target.value)}
                  >
                    <option value="">Não alterar</option>
                    {CONVERSATION_STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Atribuir a um operador">
                  <select
                    className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                    value={onEnterAssignedUserId}
                    onChange={(e) => setOnEnterAssignedUserId(e.target.value)}
                  >
                    <option value="">Não alterar</option>
                    {members.map((m) => (
                      <option key={m.user_id} value={m.user_id}>{m.name}</option>
                    ))}
                  </select>
                </Field>
                <Field label="IA neste agente">
                  <select
                    className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                    value={onEnterAiEnabled}
                    onChange={(e) => setOnEnterAiEnabled(e.target.value)}
                  >
                    <option value="">Não alterar</option>
                    <option value="true">Ligar IA</option>
                    <option value="false">Desligar IA (passar pra humano)</option>
                  </select>
                </Field>
              </div>
            </div>
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

  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: entry.id,
    data: { entry },
  });
  const dragStyle = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`, zIndex: 40 }
    : undefined;

  return (
    <>
      <div
        ref={setNodeRef}
        style={dragStyle}
        {...listeners}
        {...attributes}
        className={`group relative bg-nb-surface border border-nb-border rounded-xl p-3 hover:border-nb-primary/30 hover:shadow-sm transition-all cursor-grab active:cursor-grabbing ${isDragging ? "opacity-50" : ""}`}
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

  const { setNodeRef: setDroppableRef, isOver } = useDroppable({
    id: stage.id,
    data: { stageId: stage.id },
  });
  const {
    attributes: sortAttrs,
    listeners: sortListeners,
    setNodeRef: setSortableRef,
    transform: sortTransform,
    transition: sortTransition,
    isDragging: isColumnDragging,
  } = useSortable({ id: stage.id, data: { type: "stage" } });
  const columnStyle = {
    transform: CSS.Transform.toString(sortTransform),
    transition: sortTransition,
  };

  return (
    <div
      ref={setSortableRef}
      style={columnStyle}
      className={`flex-shrink-0 w-72 flex flex-col bg-nb-panel border rounded-2xl overflow-hidden transition-colors ${isColumnDragging ? "opacity-50" : ""} ${isOver ? "border-nb-primary/50" : "border-nb-border"}`}
    >
      {/* Column header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-nb-border bg-nb-elevated/50">
        <div className="flex items-center gap-1.5 min-w-0">
          <span
            {...sortAttrs}
            {...sortListeners}
            className="cursor-grab active:cursor-grabbing text-nb-muted hover:text-nb-secondary shrink-0"
          >
            <GripVertical className="w-3.5 h-3.5" />
          </span>
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
      <div ref={setDroppableRef} className="flex-1 overflow-y-auto p-2 space-y-2 min-h-[120px]">
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
  const [members, setMembers] = useState<Member[]>([]);
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null);
  const [metricsOpen, setMetricsOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingBoard, setLoadingBoard] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Mobile: show one stage at a time
  const [mobileStageIdx, setMobileStageIdx] = useState(0);

  // Modals
  const [createPipelineOpen, setCreatePipelineOpen] = useState(false);
  const [stageModalOpen, setStageModalOpen] = useState(false);
  const [editingStage, setEditingStage] = useState<PipelineStage | undefined>(undefined);

  // Load pipelines, agents and members on mount
  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const [pList, aList, mList] = await Promise.all([
          api.pipelines.list(),
          api.agents.list(),
          api.members.list(),
        ]);
        setPipelines(pList);
        setAgents(aList);
        setMembers(mList);
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
    setMetrics(null);
    setMetricsOpen(false);
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

  async function toggleMetrics() {
    if (metricsOpen) { setMetricsOpen(false); return; }
    setMetricsOpen(true);
    if (!metrics && selectedPipelineId) {
      try {
        setMetrics(await api.pipelines.metrics(selectedPipelineId));
      } catch {
        setMetricsOpen(false);
      }
    }
  }

  function handleEntryMoved(updated: PipelineEntry) {
    setEntries((prev) => prev.map((e) => e.id === updated.id ? updated : e));
  }

  function handleEntryRemoved(id: string) {
    setEntries((prev) => prev.filter((e) => e.id !== id));
  }

  const dndSensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  );

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || !selectedPipelineId) return;

    const activeStageIds = new Set(stages.map((s) => s.id));
    const isColumnDrag = activeStageIds.has(active.id as string);

    if (isColumnDrag) {
      // Reordering stage columns.
      if (active.id === over.id) return;
      const ordered = [...sortedStages];
      const fromIdx = ordered.findIndex((s) => s.id === active.id);
      const toIdx = ordered.findIndex((s) => s.id === over.id);
      if (fromIdx === -1 || toIdx === -1) return;
      const [moved] = ordered.splice(fromIdx, 1);
      ordered.splice(toIdx, 0, moved);
      const reindexed = ordered.map((s, i) => ({ ...s, position: i }));
      setStages(reindexed);
      try {
        await api.pipelines.stages.reorder(
          selectedPipelineId,
          reindexed.map((s, i) => ({ id: s.id, position: i }))
        );
      } catch {
        setError("Erro ao reordenar etapas.");
        loadBoard(selectedPipelineId);
      }
      return;
    }

    // Dragging a card onto a column.
    const entry = entries.find((e) => e.id === active.id);
    const targetStageId = over.id as string;
    if (!entry || entry.stage_id === targetStageId || !activeStageIds.has(targetStageId)) return;

    const previous = entry;
    setEntries((prev) =>
      prev.map((e) => (e.id === entry.id ? { ...e, stage_id: targetStageId } : e))
    );
    try {
      const updated = await api.pipelines.entries.move(selectedPipelineId, entry.id, targetStageId);
      handleEntryMoved(updated);
    } catch {
      setEntries((prev) => prev.map((e) => (e.id === entry.id ? previous : e)));
      setError("Erro ao mover conversa.");
    }
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
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleMetrics}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-xl border transition-colors ${metricsOpen ? "bg-nb-primary/10 border-nb-primary/30 text-nb-primary-strong" : "bg-nb-surface border-nb-border text-nb-secondary hover:bg-nb-elevated"}`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            Métricas
          </button>
          <button
            type="button"
            onClick={() => setCreatePipelineOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Novo Pipeline
          </button>
        </div>
      </div>

      {/* Metrics panel */}
      {metricsOpen && (
        <div className="shrink-0 bg-nb-panel border border-nb-border rounded-2xl p-4">
          {metrics === null ? (
            <div className="flex items-center gap-2 text-xs text-nb-muted">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> Carregando métricas…
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-6 flex-wrap text-xs">
                <div>
                  <span className="text-nb-muted">Total de conversas: </span>
                  <span className="font-semibold text-nb-text">{metrics.total_entries}</span>
                </div>
                <div>
                  <span className="text-nb-muted">Chegaram na última etapa: </span>
                  <span className="font-semibold text-nb-text">{metrics.entries_reached_last_stage}</span>
                </div>
                <div>
                  <span className="text-nb-muted">Taxa de conversão: </span>
                  <span className="font-semibold text-nb-text">
                    {metrics.conversion_rate !== null ? `${Math.round(metrics.conversion_rate * 100)}%` : "—"}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {metrics.stage_metrics.map((m) => (
                  <div key={m.stage_id} className="bg-nb-elevated border border-nb-border rounded-xl p-2.5">
                    <p className="text-[11px] font-medium text-nb-text truncate">{m.stage_name}</p>
                    <p className="text-[10px] text-nb-muted mt-0.5">
                      {m.avg_minutes_in_stage !== null
                        ? `${Math.round(m.avg_minutes_in_stage)} min em média`
                        : "sem dados de tempo"}
                    </p>
                    <p className="text-[10px] text-nb-muted">{m.entries_passed_through} passaram</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

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
          {/* Desktop: horizontal scroll, drag-and-drop enabled */}
          <DndContext
            sensors={dndSensors}
            collisionDetection={closestCenter}
            onDragEnd={handleDragEnd}
          >
            <div className="hidden md:flex gap-4 overflow-x-auto pb-4 flex-1 items-start">
              <SortableContext
                items={sortedStages.map((s) => s.id)}
                strategy={horizontalListSortingStrategy}
              >
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
              </SortableContext>
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
          </DndContext>

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
            members={members}
            nextPosition={stages.length}
          />
        </>
      )}
    </div>
  );
}
