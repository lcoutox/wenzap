"use client";

import { useEffect, useState, useCallback } from "react";
import {
  AlertTriangle,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Code2,
  Copy,
  Globe,
  Loader2,
  Plus,
  Power,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Channel, ChannelCreateInput, ChannelUpdateInput, MemberRole, WebWidgetConfig } from "@/lib/api";

// ── Permissions ───────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin";
}

// ── Design helpers ────────────────────────────────────────────────────────────

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

const disabledInput =
  "w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed";

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

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Channel["status"] }) {
  const map: Record<Channel["status"], { label: string; cls: string }> = {
    active:   { label: "Ativo",     cls: "bg-nb-success/10 text-nb-success border-nb-success/20" },
    inactive: { label: "Inativo",   cls: "bg-nb-elevated text-nb-muted border-nb-border" },
    archived: { label: "Arquivado", cls: "bg-nb-danger/10 text-nb-danger border-nb-danger/20" },
  };
  const s = map[status];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── Script helpers ────────────────────────────────────────────────────────────

function getScriptBaseUrl(): string {
  if (typeof window !== "undefined") return window.location.origin;
  return process.env.NEXT_PUBLIC_APP_URL ?? "";
}

function buildScript(publicKey: string): string {
  const base = getScriptBaseUrl();
  return `<script\n  src="${base}/widget.js"\n  data-widget-key="${publicKey}"\n></script>`;
}

// ── CopyButton ────────────────────────────────────────────────────────────────

function CopyButton({ text, label = "Copiar" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    if (!navigator?.clipboard) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text transition-colors"
    >
      {copied ? (
        <>
          <Check className="w-3.5 h-3.5 text-nb-success" />
          Copiado
        </>
      ) : (
        <>
          <Copy className="w-3.5 h-3.5" />
          {label}
        </>
      )}
    </button>
  );
}

// ── Origins warning ───────────────────────────────────────────────────────────

function OriginsWarning() {
  return (
    <div className="flex gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/30">
      <AlertTriangle className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
      <p className="text-xs text-nb-warning leading-relaxed">
        Sem domínios permitidos definidos — este widget poderá ser carregado de qualquer origem.
        Recomendado apenas para testes.
      </p>
    </div>
  );
}

// ── Widget form default values ────────────────────────────────────────────────

const DEFAULT_CONFIG: WebWidgetConfig = {
  theme: "dark",
  primary_color: "#7167F0",
  position: "bottom-right",
  welcome_message: "Olá! Como posso ajudar?",
  header_title: "Atendimento",
  header_subtitle: "Resposta em segundos",
  placeholder: "Digite sua mensagem...",
  avatar_url: null,
  auto_open: false,
  auto_open_delay_seconds: 3,
  contact_capture_enabled: false,
  require_name: false,
  require_email: false,
  require_phone: false,
};

// ── Validation ────────────────────────────────────────────────────────────────

function validateHexColor(v: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(v);
}

function parseOrigins(raw: string): string[] {
  return raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

// ── Widget form state ─────────────────────────────────────────────────────────

type FormState = {
  name: string;
  theme: WebWidgetConfig["theme"];
  primary_color: string;
  position: WebWidgetConfig["position"];
  welcome_message: string;
  header_title: string;
  header_subtitle: string;
  placeholder: string;
  avatar_url: string;
  auto_open: boolean;
  auto_open_delay_seconds: number;
  allowed_origins_raw: string;
  // Visitor identity / lead capture
  contact_capture_enabled: boolean;
  require_name: boolean;
  require_email: boolean;
  require_phone: boolean;
};

function channelToForm(ch?: Channel): FormState {
  const cfg = ch?.config ?? DEFAULT_CONFIG;
  return {
    name: ch?.name ?? "",
    theme: cfg.theme,
    primary_color: cfg.primary_color,
    position: cfg.position,
    welcome_message: cfg.welcome_message,
    header_title: cfg.header_title,
    header_subtitle: cfg.header_subtitle,
    placeholder: cfg.placeholder,
    avatar_url: cfg.avatar_url ?? "",
    auto_open: cfg.auto_open,
    auto_open_delay_seconds: cfg.auto_open_delay_seconds,
    allowed_origins_raw: (ch?.allowed_origins ?? []).join("\n"),
    contact_capture_enabled: cfg.contact_capture_enabled ?? false,
    require_name: cfg.require_name ?? false,
    require_email: cfg.require_email ?? false,
    require_phone: cfg.require_phone ?? false,
  };
}

function formToPayload(
  f: FormState,
  agentId: string,
  isCreate: boolean,
): ChannelCreateInput | ChannelUpdateInput {
  const config: Partial<WebWidgetConfig> = {
    theme: f.theme,
    primary_color: f.primary_color,
    position: f.position,
    welcome_message: f.welcome_message,
    header_title: f.header_title,
    header_subtitle: f.header_subtitle,
    placeholder: f.placeholder,
    avatar_url: f.avatar_url.trim() || null,
    auto_open: f.auto_open,
    auto_open_delay_seconds: f.auto_open_delay_seconds,
    contact_capture_enabled: f.contact_capture_enabled,
    require_name: f.require_name,
    require_email: f.require_email,
    require_phone: f.require_phone,
  };
  const allowed_origins = parseOrigins(f.allowed_origins_raw);

  if (isCreate) {
    return {
      name: f.name.trim(),
      channel_type: "web_widget",
      agent_id: agentId,
      config,
      allowed_origins,
    } satisfies ChannelCreateInput;
  }
  return { name: f.name.trim(), config, allowed_origins } satisfies ChannelUpdateInput;
}

// ── Widget form ───────────────────────────────────────────────────────────────

function WidgetForm({
  initial,
  onSave,
  onCancel,
  saving,
  saveError,
}: {
  initial: FormState;
  onSave: (f: FormState) => void;
  onCancel: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const [validationError, setValidationError] = useState<string | null>(null);

  function set<K extends keyof FormState>(key: K, val: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) {
      setValidationError("O nome do widget é obrigatório.");
      return;
    }
    if (!validateHexColor(form.primary_color)) {
      setValidationError("Cor primária deve estar no formato #RRGGBB (ex: #7167F0).");
      return;
    }
    if (form.auto_open_delay_seconds < 0 || form.auto_open_delay_seconds > 60) {
      setValidationError("O delay de auto-open deve ser entre 0 e 60 segundos.");
      return;
    }
    setValidationError(null);
    onSave(form);
  }

  const origins = parseOrigins(form.allowed_origins_raw);

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Name */}
      <Field label="Nome do widget *">
        <input
          type="text"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          maxLength={100}
          placeholder="Ex: Widget do Site Principal"
          className={baseInput}
        />
      </Field>

      {/* Header */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Título do header">
          <input
            type="text"
            value={form.header_title}
            onChange={(e) => set("header_title", e.target.value)}
            maxLength={60}
            placeholder="Atendimento"
            className={baseInput}
          />
        </Field>
        <Field label="Subtítulo do header">
          <input
            type="text"
            value={form.header_subtitle}
            onChange={(e) => set("header_subtitle", e.target.value)}
            maxLength={80}
            placeholder="Resposta em segundos"
            className={baseInput}
          />
        </Field>
      </div>

      {/* Welcome + placeholder */}
      <Field label="Mensagem de boas-vindas">
        <input
          type="text"
          value={form.welcome_message}
          onChange={(e) => set("welcome_message", e.target.value)}
          maxLength={200}
          placeholder="Olá! Como posso ajudar?"
          className={baseInput}
        />
      </Field>
      <Field label="Placeholder do input">
        <input
          type="text"
          value={form.placeholder}
          onChange={(e) => set("placeholder", e.target.value)}
          maxLength={80}
          placeholder="Digite sua mensagem..."
          className={baseInput}
        />
      </Field>

      {/* Theme + position */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Tema">
          <select
            value={form.theme}
            onChange={(e) => set("theme", e.target.value as WebWidgetConfig["theme"])}
            className={baseInput}
          >
            <option value="dark">Escuro</option>
            <option value="light">Claro</option>
            <option value="auto">Automático (sistema)</option>
          </select>
        </Field>
        <Field label="Posição">
          <select
            value={form.position}
            onChange={(e) => set("position", e.target.value as WebWidgetConfig["position"])}
            className={baseInput}
          >
            <option value="bottom-right">Inferior direito</option>
            <option value="bottom-left">Inferior esquerdo</option>
          </select>
        </Field>
      </div>

      {/* Primary color */}
      <Field label="Cor primária" hint="Formato hexadecimal: #RRGGBB">
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={form.primary_color}
            onChange={(e) => set("primary_color", e.target.value)}
            className="w-9 h-9 rounded-lg border border-nb-border bg-nb-elevated cursor-pointer flex-shrink-0"
          />
          <input
            type="text"
            value={form.primary_color}
            onChange={(e) => set("primary_color", e.target.value)}
            maxLength={7}
            placeholder="#7167F0"
            className={baseInput}
          />
        </div>
      </Field>

      {/* Auto-open */}
      <div className="flex items-start gap-4">
        <div className="flex items-center gap-2 pt-0.5">
          <input
            type="checkbox"
            id="auto_open"
            checked={form.auto_open}
            onChange={(e) => set("auto_open", e.target.checked)}
            className="w-4 h-4 rounded accent-nb-primary"
          />
          <label htmlFor="auto_open" className="text-sm font-medium text-nb-secondary cursor-pointer">
            Abrir automaticamente
          </label>
        </div>
        {form.auto_open && (
          <Field label="Delay (segundos)" hint="Entre 0 e 60">
            <input
              type="number"
              value={form.auto_open_delay_seconds}
              onChange={(e) => set("auto_open_delay_seconds", Number(e.target.value))}
              min={0}
              max={60}
              className={`${baseInput} w-28`}
            />
          </Field>
        )}
      </div>

      {/* Avatar URL */}
      <Field label="URL do avatar" hint="Opcional. Imagem exibida no header do widget.">
        <input
          type="url"
          value={form.avatar_url}
          onChange={(e) => set("avatar_url", e.target.value)}
          placeholder="https://exemplo.com/avatar.png"
          className={baseInput}
        />
      </Field>

      {/* Contact capture */}
      <div className="flex flex-col gap-3 p-4 rounded-xl border border-nb-border/60 bg-nb-elevated/30">
        <p className="text-xs font-semibold text-nb-secondary uppercase tracking-wide">Coleta de dados do visitante</p>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            id="contact_capture_enabled"
            checked={form.contact_capture_enabled}
            onChange={(e) => {
              set("contact_capture_enabled", e.target.checked);
              if (!e.target.checked) {
                set("require_name", false);
                set("require_email", false);
                set("require_phone", false);
              }
            }}
            className="w-4 h-4 accent-nb-primary"
          />
          <span className="text-sm text-nb-secondary">Exigir dados antes de iniciar o chat</span>
        </label>
        {form.contact_capture_enabled && (
          <div className="flex flex-col gap-2 pl-7">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-nb-secondary">
              <input
                type="checkbox"
                checked={form.require_name}
                onChange={(e) => set("require_name", e.target.checked)}
                className="w-4 h-4 accent-nb-primary"
              />
              Nome
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm text-nb-secondary">
              <input
                type="checkbox"
                checked={form.require_email}
                onChange={(e) => set("require_email", e.target.checked)}
                className="w-4 h-4 accent-nb-primary"
              />
              E-mail
            </label>
            <label className="flex items-center gap-2 cursor-pointer text-sm text-nb-secondary">
              <input
                type="checkbox"
                checked={form.require_phone}
                onChange={(e) => set("require_phone", e.target.checked)}
                className="w-4 h-4 accent-nb-primary"
              />
              Telefone
            </label>
          </div>
        )}
      </div>

      {/* Allowed origins */}
      <Field
        label="Domínios permitidos"
        hint="Um domínio por linha. Inclua o protocolo: https://meusite.com.br"
      >
        <textarea
          value={form.allowed_origins_raw}
          onChange={(e) => set("allowed_origins_raw", e.target.value)}
          rows={4}
          placeholder={"https://meusite.com.br\nhttps://www.meusite.com.br\nhttp://localhost:3000"}
          className={baseInput}
        />
        {origins.length === 0 && <OriginsWarning />}
      </Field>

      {/* Errors */}
      {(validationError ?? saveError) && (
        <div className="flex gap-2 p-3 rounded-xl bg-nb-danger/10 border border-nb-danger/30">
          <AlertTriangle className="w-4 h-4 text-nb-danger flex-shrink-0 mt-0.5" />
          <p className="text-xs text-nb-danger">{validationError ?? saveError}</p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3 pt-1">
        <button
          type="submit"
          disabled={saving}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong disabled:opacity-60 transition-colors"
        >
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Salvar
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="px-4 py-2 rounded-xl text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ── Script panel ──────────────────────────────────────────────────────────────

function ScriptPanel({ publicKey }: { publicKey: string }) {
  const [open, setOpen] = useState(false);
  const script = buildScript(publicKey);

  return (
    <div className="border border-nb-border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 bg-nb-elevated hover:bg-nb-soft transition-colors text-sm"
      >
        <div className="flex items-center gap-2 text-nb-secondary font-medium">
          <Code2 className="w-4 h-4 text-nb-muted" />
          Script de instalação
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-nb-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-nb-muted" />
        )}
      </button>

      {open && (
        <div className="bg-nb-bg border-t border-nb-border p-4 space-y-3">
          <p className="text-xs text-nb-muted">
            Cole este script no <code className="font-mono bg-nb-elevated px-1 rounded">&lt;head&gt;</code> ou antes do fechamento do{" "}
            <code className="font-mono bg-nb-elevated px-1 rounded">&lt;/body&gt;</code> do seu site.
            O embed público será publicado na próxima etapa.
          </p>
          <pre className="bg-nb-panel border border-nb-border rounded-xl p-3 text-xs font-mono text-nb-secondary overflow-x-auto whitespace-pre">
            {script}
          </pre>
          <CopyButton text={script} label="Copiar script" />
        </div>
      )}
    </div>
  );
}

// ── Widget card ───────────────────────────────────────────────────────────────

function WidgetCard({
  channel,
  canEdit,
  onEdit,
  onToggleStatus,
  onArchive,
  busy,
}: {
  channel: Channel;
  canEdit: boolean;
  onEdit: (ch: Channel) => void;
  onToggleStatus: (ch: Channel) => void;
  onArchive: (ch: Channel) => void;
  busy: boolean;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4 hover:border-nb-border-strong transition-colors">
      {/* Top row */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
            <Globe className="w-4.5 h-4.5 text-nb-muted" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-nb-text truncate">{channel.name}</p>
            <p className="text-xs font-mono text-nb-muted truncate mt-0.5">{channel.public_key}</p>
          </div>
        </div>
        <StatusBadge status={channel.status} />
      </div>

      {/* Meta row */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Tema</p>
          <p className="text-nb-secondary capitalize">{channel.config?.theme ?? "—"}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Posição</p>
          <p className="text-nb-secondary">{channel.config?.position ?? "—"}</p>
        </div>
        <div className="col-span-2">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Domínios</p>
          {channel.allowed_origins.length === 0 ? (
            <span className="inline-flex items-center gap-1 text-nb-warning">
              <AlertTriangle className="w-3 h-3" />
              Qualquer origem (sem restrição)
            </span>
          ) : (
            <p className="text-nb-secondary truncate">{channel.allowed_origins.join(", ")}</p>
          )}
        </div>
      </div>

      {/* Script */}
      <ScriptPanel publicKey={channel.public_key} />

      {/* Actions */}
      {canEdit && (
        <div className="flex items-center gap-2 pt-1 border-t border-nb-border">
          <button
            type="button"
            onClick={() => onEdit(channel)}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text hover:border-nb-border-strong transition-colors"
          >
            Editar
          </button>
          <button
            type="button"
            onClick={() => onToggleStatus(channel)}
            disabled={busy}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text hover:border-nb-border-strong disabled:opacity-50 transition-colors"
          >
            {busy ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Power className="w-3 h-3" />
            )}
            {channel.status === "active" ? "Inativar" : "Ativar"}
          </button>
          <button
            type="button"
            onClick={() => onArchive(channel)}
            disabled={busy}
            className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-nb-danger/70 hover:text-nb-danger hover:bg-nb-danger/10 border border-transparent hover:border-nb-danger/20 disabled:opacity-50 transition-colors"
          >
            {busy ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Trash2 className="w-3 h-3" />
            )}
            Arquivar
          </button>
        </div>
      )}
    </div>
  );
}

// ── Widget form modal ─────────────────────────────────────────────────────────

function WidgetFormModal({
  title,
  initial,
  onSave,
  onClose,
  saving,
  saveError,
}: {
  title: string;
  initial: FormState;
  onSave: (f: FormState) => void;
  onClose: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-xl bg-nb-surface border border-nb-border rounded-2xl shadow-xl my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
          <h2 className="text-base font-semibold text-nb-text">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1.5 rounded-lg text-nb-muted hover:text-nb-secondary hover:bg-nb-elevated transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        {/* Body */}
        <div className="px-6 py-5">
          <WidgetForm
            initial={initial}
            onSave={onSave}
            onCancel={onClose}
            saving={saving}
            saveError={saveError}
          />
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ImplantarTab({
  agentId,
  role,
  getToken,
}: {
  agentId: string;
  role: MemberRole | null;
  getToken: () => Promise<string | null>;
}) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Modal state
  const [modal, setModal] = useState<"create" | { edit: Channel } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Per-card busy state (toggle/archive)
  const [busyId, setBusyId] = useState<string | null>(null);

  // Success feedback
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const writable = canWrite(role);

  // ── Load ────────────────────────────────────────────────────────────────────

  const loadChannels = useCallback(async () => {
    const token = await getToken();
    if (!token) return;
    try {
      const data = await api.channels.list(token, {
        channel_type: "web_widget",
        agent_id: agentId,
      });
      setChannels(data);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Erro ao carregar widgets.");
    } finally {
      setLoading(false);
    }
  }, [agentId, getToken]);

  useEffect(() => { loadChannels(); }, [loadChannels]);

  function showSuccess(msg: string) {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  }

  // ── Create ──────────────────────────────────────────────────────────────────

  async function handleCreate(f: FormState) {
    const token = await getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await api.channels.create(token, formToPayload(f, agentId, true) as import("@/lib/api").ChannelCreateInput);
      setChannels((prev) => [created, ...prev]);
      setModal(null);
      showSuccess("Widget criado com sucesso.");
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erro ao criar widget.");
    } finally {
      setSaving(false);
    }
  }

  // ── Edit ────────────────────────────────────────────────────────────────────

  async function handleEdit(ch: Channel, f: FormState) {
    const token = await getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await api.channels.update(token, ch.id, formToPayload(f, agentId, false) as import("@/lib/api").ChannelUpdateInput);
      setChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setModal(null);
      showSuccess("Widget atualizado.");
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erro ao salvar widget.");
    } finally {
      setSaving(false);
    }
  }

  // ── Toggle status ────────────────────────────────────────────────────────────

  async function handleToggleStatus(ch: Channel) {
    const token = await getToken();
    if (!token) return;
    setBusyId(ch.id);
    try {
      const newStatus = ch.status === "active" ? "inactive" : "active";
      const updated = await api.channels.update(token, ch.id, { status: newStatus });
      setChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Erro ao alterar status.");
    } finally {
      setBusyId(null);
    }
  }

  // ── Archive ──────────────────────────────────────────────────────────────────

  async function handleArchive(ch: Channel) {
    if (!confirm(`Arquivar "${ch.name}"? Esta ação não pode ser desfeita facilmente.`)) return;
    const token = await getToken();
    if (!token) return;
    setBusyId(ch.id);
    try {
      await api.channels.archive(token, ch.id);
      setChannels((prev) => prev.filter((c) => c.id !== ch.id));
      showSuccess("Widget arquivado.");
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Erro ao arquivar widget.");
    } finally {
      setBusyId(null);
    }
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-nb-text">Implantar agente</h2>
            <p className="text-sm text-nb-muted mt-1">
              Conecte este agente a canais externos. Comece com um Web Widget para instalar no seu site.
            </p>
          </div>
          {writable && (
            <button
              type="button"
              onClick={() => { setSaveError(null); setModal("create"); }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong transition-colors flex-shrink-0"
            >
              <Plus className="w-4 h-4" />
              Novo Web Widget
            </button>
          )}
        </div>

        {/* Success toast */}
        {successMsg && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-nb-success/10 border border-nb-success/30 text-nb-success text-sm">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            {successMsg}
          </div>
        )}

        {/* Error */}
        {loadError && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-nb-danger/10 border border-nb-danger/30 text-nb-danger text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {loadError}
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex items-center gap-2 text-nb-muted py-8 justify-center">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Carregando widgets...</span>
          </div>
        )}

        {/* Empty state */}
        {!loading && !loadError && channels.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-4 bg-nb-panel rounded-2xl border border-nb-border border-dashed">
            <div className="w-12 h-12 rounded-2xl bg-nb-elevated border border-nb-border flex items-center justify-center">
              <Globe className="w-6 h-6 text-nb-muted" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-nb-secondary">Nenhum Web Widget criado ainda</p>
              <p className="text-xs text-nb-muted mt-1">
                Crie um widget para instalar este agente no seu site.
              </p>
            </div>
            {writable && (
              <button
                type="button"
                onClick={() => { setSaveError(null); setModal("create"); }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong transition-colors"
              >
                <Plus className="w-4 h-4" />
                Criar primeiro widget
              </button>
            )}
          </div>
        )}

        {/* Widget cards */}
        {!loading && channels.length > 0 && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {channels.map((ch) => (
              <WidgetCard
                key={ch.id}
                channel={ch}
                canEdit={writable}
                onEdit={(c) => { setSaveError(null); setModal({ edit: c }); }}
                onToggleStatus={handleToggleStatus}
                onArchive={handleArchive}
                busy={busyId === ch.id}
              />
            ))}
          </div>
        )}

        {/* Other channels preview */}
        <div className="pt-4 border-t border-nb-border">
          <p className="text-xs text-nb-muted mb-3 font-medium uppercase tracking-widest">Próximos canais</p>
          <div className="flex flex-wrap gap-2">
            {["WhatsApp", "Instagram", "Telegram", "Slack", "API"].map((name) => (
              <span
                key={name}
                className="px-3 py-1 rounded-full text-xs font-medium bg-nb-elevated border border-nb-border text-nb-muted"
              >
                {name} · Em breve
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Modal */}
      {modal === "create" && (
        <WidgetFormModal
          title="Novo Web Widget"
          initial={channelToForm()}
          onSave={handleCreate}
          onClose={() => setModal(null)}
          saving={saving}
          saveError={saveError}
        />
      )}
      {modal !== null && modal !== "create" && (
        <WidgetFormModal
          title="Editar Web Widget"
          initial={channelToForm(modal.edit)}
          onSave={(f) => handleEdit(modal.edit, f)}
          onClose={() => setModal(null)}
          saving={saving}
          saveError={saveError}
        />
      )}
    </>
  );
}
