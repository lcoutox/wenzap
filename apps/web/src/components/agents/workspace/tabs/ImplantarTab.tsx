"use client";

import { useEffect, useState, useCallback, useRef } from "react";
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
  MessageCircle,
  Plus,
  Power,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  WebWidgetChannel,
  WhatsAppChannel,
  WebWidgetChannelCreateInput,
  WhatsAppChannelCreateInput,
  ChannelUpdateInput,
  MemberRole,
  WebWidgetConfig,
} from "@/lib/api";

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

function StatusBadge({ status }: { status: "active" | "inactive" | "archived" }) {
  const map = {
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
        <><Check className="w-3.5 h-3.5 text-nb-success" />Copiado</>
      ) : (
        <><Copy className="w-3.5 h-3.5" />{label}</>
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

// ── Widget form ───────────────────────────────────────────────────────────────

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

type WidgetFormState = {
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
  contact_capture_enabled: boolean;
  require_name: boolean;
  require_email: boolean;
  require_phone: boolean;
};

function channelToWidgetForm(ch?: WebWidgetChannel): WidgetFormState {
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

function validateHexColor(v: string): boolean {
  return /^#[0-9A-Fa-f]{6}$/.test(v);
}

function parseOrigins(raw: string): string[] {
  return raw.split("\n").map((l) => l.trim()).filter(Boolean);
}

function widgetFormToPayload(
  f: WidgetFormState,
  agentId: string,
  isCreate: boolean,
): WebWidgetChannelCreateInput | ChannelUpdateInput {
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
    return { name: f.name.trim(), channel_type: "web_widget", agent_id: agentId, config, allowed_origins };
  }
  return { name: f.name.trim(), config, allowed_origins };
}

function WidgetForm({
  initial,
  onSave,
  onCancel,
  saving,
  saveError,
}: {
  initial: WidgetFormState;
  onSave: (f: WidgetFormState) => void;
  onCancel: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  const [form, setForm] = useState<WidgetFormState>(initial);
  const [validationError, setValidationError] = useState<string | null>(null);

  function set<K extends keyof WidgetFormState>(key: K, val: WidgetFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) { setValidationError("O nome do widget é obrigatório."); return; }
    if (!validateHexColor(form.primary_color)) { setValidationError("Cor primária deve estar no formato #RRGGBB (ex: #7167F0)."); return; }
    if (form.auto_open_delay_seconds < 0 || form.auto_open_delay_seconds > 60) { setValidationError("O delay de auto-open deve ser entre 0 e 60 segundos."); return; }
    setValidationError(null);
    onSave(form);
  }

  const origins = parseOrigins(form.allowed_origins_raw);

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <Field label="Nome do widget *">
        <input type="text" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={100} placeholder="Ex: Widget do Site Principal" className={baseInput} />
      </Field>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Título do header">
          <input type="text" value={form.header_title} onChange={(e) => set("header_title", e.target.value)} maxLength={60} placeholder="Atendimento" className={baseInput} />
        </Field>
        <Field label="Subtítulo do header">
          <input type="text" value={form.header_subtitle} onChange={(e) => set("header_subtitle", e.target.value)} maxLength={80} placeholder="Resposta em segundos" className={baseInput} />
        </Field>
      </div>
      <Field label="Mensagem de boas-vindas">
        <input type="text" value={form.welcome_message} onChange={(e) => set("welcome_message", e.target.value)} maxLength={200} placeholder="Olá! Como posso ajudar?" className={baseInput} />
      </Field>
      <Field label="Placeholder do input">
        <input type="text" value={form.placeholder} onChange={(e) => set("placeholder", e.target.value)} maxLength={80} placeholder="Digite sua mensagem..." className={baseInput} />
      </Field>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Tema">
          <select value={form.theme} onChange={(e) => set("theme", e.target.value as WebWidgetConfig["theme"])} className={baseInput}>
            <option value="dark">Escuro</option>
            <option value="light">Claro</option>
            <option value="auto">Automático (sistema)</option>
          </select>
        </Field>
        <Field label="Posição">
          <select value={form.position} onChange={(e) => set("position", e.target.value as WebWidgetConfig["position"])} className={baseInput}>
            <option value="bottom-right">Inferior direito</option>
            <option value="bottom-left">Inferior esquerdo</option>
          </select>
        </Field>
      </div>
      <Field label="Cor primária" hint="Formato hexadecimal: #RRGGBB">
        <div className="flex items-center gap-2">
          <input type="color" value={form.primary_color} onChange={(e) => set("primary_color", e.target.value)} className="w-9 h-9 rounded-lg border border-nb-border bg-nb-elevated cursor-pointer flex-shrink-0" />
          <input type="text" value={form.primary_color} onChange={(e) => set("primary_color", e.target.value)} maxLength={7} placeholder="#7167F0" className={baseInput} />
        </div>
      </Field>
      <div className="flex items-start gap-4">
        <div className="flex items-center gap-2 pt-0.5">
          <input type="checkbox" id="auto_open" checked={form.auto_open} onChange={(e) => set("auto_open", e.target.checked)} className="w-4 h-4 rounded accent-nb-primary" />
          <label htmlFor="auto_open" className="text-sm font-medium text-nb-secondary cursor-pointer">Abrir automaticamente</label>
        </div>
        {form.auto_open && (
          <Field label="Delay (segundos)" hint="Entre 0 e 60">
            <input type="number" value={form.auto_open_delay_seconds} onChange={(e) => set("auto_open_delay_seconds", Number(e.target.value))} min={0} max={60} className={`${baseInput} w-28`} />
          </Field>
        )}
      </div>
      <Field label="URL do avatar" hint="Opcional. Imagem exibida no header do widget.">
        <input type="url" value={form.avatar_url} onChange={(e) => set("avatar_url", e.target.value)} placeholder="https://exemplo.com/avatar.png" className={baseInput} />
      </Field>
      <div className="flex flex-col gap-3 p-4 rounded-xl border border-nb-border/60 bg-nb-elevated/30">
        <p className="text-xs font-semibold text-nb-secondary uppercase tracking-wide">Coleta de dados do visitante</p>
        <label className="flex items-center gap-3 cursor-pointer">
          <input type="checkbox" checked={form.contact_capture_enabled} onChange={(e) => { set("contact_capture_enabled", e.target.checked); if (!e.target.checked) { set("require_name", false); set("require_email", false); set("require_phone", false); } }} className="w-4 h-4 accent-nb-primary" />
          <span className="text-sm text-nb-secondary">Exigir dados antes de iniciar o chat</span>
        </label>
        {form.contact_capture_enabled && (
          <div className="flex flex-col gap-2 pl-7">
            {(["require_name", "require_email", "require_phone"] as const).map((k) => (
              <label key={k} className="flex items-center gap-2 cursor-pointer text-sm text-nb-secondary">
                <input type="checkbox" checked={form[k]} onChange={(e) => set(k, e.target.checked)} className="w-4 h-4 accent-nb-primary" />
                {k === "require_name" ? "Nome" : k === "require_email" ? "E-mail" : "Telefone"}
              </label>
            ))}
          </div>
        )}
      </div>
      <Field label="Domínios permitidos" hint="Um domínio por linha. Inclua o protocolo: https://meusite.com.br">
        <textarea value={form.allowed_origins_raw} onChange={(e) => set("allowed_origins_raw", e.target.value)} rows={4} placeholder={"https://meusite.com.br\nhttps://www.meusite.com.br\nhttp://localhost:3000"} className={baseInput} />
        {origins.length === 0 && <OriginsWarning />}
      </Field>
      {(validationError ?? saveError) && (
        <div className="flex gap-2 p-3 rounded-xl bg-nb-danger/10 border border-nb-danger/30">
          <AlertTriangle className="w-4 h-4 text-nb-danger flex-shrink-0 mt-0.5" />
          <p className="text-xs text-nb-danger">{validationError ?? saveError}</p>
        </div>
      )}
      <div className="flex items-center gap-3 pt-1">
        <button type="submit" disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong disabled:opacity-60 transition-colors">
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Salvar
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className="px-4 py-2 rounded-xl text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors">Cancelar</button>
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
      <button type="button" onClick={() => setOpen((v) => !v)} className="w-full flex items-center justify-between px-4 py-3 bg-nb-elevated hover:bg-nb-soft transition-colors text-sm">
        <div className="flex items-center gap-2 text-nb-secondary font-medium">
          <Code2 className="w-4 h-4 text-nb-muted" />
          Script de instalação
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-nb-muted" /> : <ChevronDown className="w-4 h-4 text-nb-muted" />}
      </button>
      {open && (
        <div className="bg-nb-bg border-t border-nb-border p-4 space-y-3">
          <p className="text-xs text-nb-muted">
            Cole este script no <code className="font-mono bg-nb-elevated px-1 rounded">&lt;head&gt;</code> ou antes do fechamento do{" "}
            <code className="font-mono bg-nb-elevated px-1 rounded">&lt;/body&gt;</code> do seu site.
          </p>
          <pre className="bg-nb-panel border border-nb-border rounded-xl p-3 text-xs font-mono text-nb-secondary overflow-x-auto whitespace-pre">{script}</pre>
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
  channel: WebWidgetChannel;
  canEdit: boolean;
  onEdit: (ch: WebWidgetChannel) => void;
  onToggleStatus: (ch: WebWidgetChannel) => void;
  onArchive: (ch: WebWidgetChannel) => void;
  busy: boolean;
}) {
  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4 hover:border-nb-border-strong transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
            <Globe className="w-4 h-4 text-nb-muted" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-nb-text truncate">{channel.name}</p>
            <p className="text-xs font-mono text-nb-muted truncate mt-0.5">{channel.public_key}</p>
          </div>
        </div>
        <StatusBadge status={channel.status} />
      </div>
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
            <span className="inline-flex items-center gap-1 text-nb-warning"><AlertTriangle className="w-3 h-3" />Qualquer origem (sem restrição)</span>
          ) : (
            <p className="text-nb-secondary truncate">{channel.allowed_origins.join(", ")}</p>
          )}
        </div>
      </div>
      <ScriptPanel publicKey={channel.public_key} />
      {canEdit && (
        <div className="flex items-center gap-2 pt-1 border-t border-nb-border">
          <button type="button" onClick={() => onEdit(channel)} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text hover:border-nb-border-strong transition-colors">Editar</button>
          <button type="button" onClick={() => onToggleStatus(channel)} disabled={busy} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text hover:border-nb-border-strong disabled:opacity-50 transition-colors">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Power className="w-3 h-3" />}
            {channel.status === "active" ? "Inativar" : "Ativar"}
          </button>
          <button type="button" onClick={() => onArchive(channel)} disabled={busy} className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-nb-danger/70 hover:text-nb-danger hover:bg-nb-danger/10 border border-transparent hover:border-nb-danger/20 disabled:opacity-50 transition-colors">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
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
  initial: WidgetFormState;
  onSave: (f: WidgetFormState) => void;
  onClose: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-xl bg-nb-surface border border-nb-border rounded-2xl shadow-xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
          <h2 className="text-base font-semibold text-nb-text">{title}</h2>
          <button type="button" onClick={onClose} disabled={saving} className="p-1.5 rounded-lg text-nb-muted hover:text-nb-secondary hover:bg-nb-elevated transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-5">
          <WidgetForm initial={initial} onSave={onSave} onCancel={onClose} saving={saving} saveError={saveError} />
        </div>
      </div>
    </div>
  );
}

// ── WhatsApp icon ─────────────────────────────────────────────────────────────

function WhatsAppIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} xmlns="http://www.w3.org/2000/svg" fill="currentColor">
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
    </svg>
  );
}

// ── WhatsApp form ─────────────────────────────────────────────────────────────

type WaFormState = {
  name: string;
  display_phone_number: string;
  phone_number_id: string;
  waba_id: string;
  business_id: string;
  token_env_var: string;
  status: "testing" | "active";
};

const INITIAL_WA_FORM: WaFormState = {
  name: "WhatsApp",
  display_phone_number: "",
  phone_number_id: "",
  waba_id: "",
  business_id: "",
  token_env_var: "WHATSAPP_ACCESS_TOKEN",
  status: "testing",
};

const TOKEN_LOOKS_REAL_RE = /^EAAG|^EAA/;

function WhatsAppForm({
  onSave,
  onCancel,
  saving,
  saveError,
}: {
  onSave: (f: WaFormState) => void;
  onCancel: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  const [form, setForm] = useState<WaFormState>(INITIAL_WA_FORM);
  const [errors, setErrors] = useState<Partial<Record<keyof WaFormState, string>>>({});

  function set<K extends keyof WaFormState>(key: K, val: WaFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: val }));
    setErrors((prev) => { const n = { ...prev }; delete n[key]; return n; });
  }

  function validate(): boolean {
    const e: Partial<Record<keyof WaFormState, string>> = {};
    if (!form.name.trim())            e.name            = "Nome obrigatório.";
    if (!form.phone_number_id.trim()) e.phone_number_id = "Phone Number ID obrigatório.";
    else if (!/^\d{5,}$/.test(form.phone_number_id.trim())) e.phone_number_id = "Phone Number ID deve conter apenas dígitos (mínimo 5).";
    if (!form.waba_id.trim())         e.waba_id         = "WABA ID obrigatório.";
    else if (!/^\d{5,}$/.test(form.waba_id.trim()))         e.waba_id         = "WABA ID deve conter apenas dígitos (mínimo 5).";
    if (!form.token_env_var.trim())   e.token_env_var   = "Nome da variável de ambiente obrigatório.";
    else {
      const raw = form.token_env_var.trim();
      const normalized = raw.startsWith("env:") ? raw.slice(4) : raw;
      if (TOKEN_LOOKS_REAL_RE.test(normalized) || normalized.length > 80) {
        e.token_env_var = "Não cole o token real. Crie uma variável de ambiente no Railway e informe apenas o nome dela.";
      }
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (validate()) onSave(form);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Security notice */}
      <div className="flex gap-2.5 p-3 rounded-xl bg-nb-warning/10 border border-nb-warning/30">
        <AlertTriangle className="w-4 h-4 text-nb-warning flex-shrink-0 mt-0.5" />
        <p className="text-xs text-nb-warning leading-relaxed">
          Por segurança, cole apenas o nome da variável de ambiente do token. Não cole o token real aqui.
        </p>
      </div>

      <Field label="Nome do canal *">
        <input type="text" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={100} placeholder="Ex: WhatsApp Atendimento" className={errors.name ? baseInput + " border-nb-danger" : baseInput} />
        {errors.name && <p className="text-xs text-nb-danger">{errors.name}</p>}
      </Field>

      <Field label="Número de exibição" hint="Visual e informativo — ex: +55 37 99999-9999">
        <input type="text" value={form.display_phone_number} onChange={(e) => set("display_phone_number", e.target.value)} placeholder="Ex: +55 37 99999-9999" className={baseInput} />
      </Field>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Phone Number ID *" hint="ID do número no Meta Cloud API. Usado para rotear mensagens recebidas.">
          <input type="text" value={form.phone_number_id} onChange={(e) => set("phone_number_id", e.target.value.replace(/\D/g, ""))} placeholder="Ex: 123456789012345" className={errors.phone_number_id ? baseInput + " border-nb-danger" : baseInput} />
          {errors.phone_number_id && <p className="text-xs text-nb-danger">{errors.phone_number_id}</p>}
        </Field>
        <Field label="WABA ID *" hint="ID da conta WhatsApp Business na Meta.">
          <input type="text" value={form.waba_id} onChange={(e) => set("waba_id", e.target.value.replace(/\D/g, ""))} placeholder="Ex: 123456789012345" className={errors.waba_id ? baseInput + " border-nb-danger" : baseInput} />
          {errors.waba_id && <p className="text-xs text-nb-danger">{errors.waba_id}</p>}
        </Field>
      </div>

      <Field label="Business ID" hint="Opcional. ID do Business Manager na Meta.">
        <input type="text" value={form.business_id} onChange={(e) => set("business_id", e.target.value.replace(/\D/g, ""))} placeholder="Ex: 123456789012345" className={baseInput} />
      </Field>

      <Field label="Variável de ambiente do token *" hint="Informe o nome da variável configurada no Railway. O token não será salvo no banco.">
        <input type="text" value={form.token_env_var} onChange={(e) => set("token_env_var", e.target.value)} placeholder="WHATSAPP_ACCESS_TOKEN" className={errors.token_env_var ? baseInput + " border-nb-danger" : baseInput} />
        {errors.token_env_var && <p className="text-xs text-nb-danger">{errors.token_env_var}</p>}
      </Field>

      <Field label="Status inicial" hint='Use "testing" enquanto valida o número. Troque para "active" quando estiver pronto.'>
        <select value={form.status} onChange={(e) => set("status", e.target.value as WaFormState["status"])} className={baseInput}>
          <option value="testing">testing — Em validação</option>
          <option value="active">active — Pronto para uso</option>
        </select>
      </Field>

      {saveError && (
        <div className="flex gap-2 p-3 rounded-xl bg-nb-danger/10 border border-nb-danger/30">
          <AlertTriangle className="w-4 h-4 text-nb-danger flex-shrink-0 mt-0.5" />
          <p className="text-xs text-nb-danger">{saveError}</p>
        </div>
      )}

      <div className="flex items-center gap-3 pt-1">
        <button type="submit" disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong disabled:opacity-60 transition-colors">
          {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
          Salvar canal
        </button>
        <button type="button" onClick={onCancel} disabled={saving} className="px-4 py-2 rounded-xl text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors">Cancelar</button>
      </div>
    </form>
  );
}

// ── WhatsApp channel card ─────────────────────────────────────────────────────

function WhatsAppCard({
  channel,
  canEdit,
  onArchive,
  busy,
}: {
  channel: WhatsAppChannel;
  canEdit: boolean;
  onArchive: (ch: WhatsAppChannel) => void;
  busy: boolean;
}) {
  const cfg = channel.config;
  const waStatus = cfg.status ?? "—";
  const statusColor = waStatus === "active" ? "text-nb-success" : waStatus === "disconnected" ? "text-nb-danger" : "text-nb-warning";

  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4 hover:border-nb-border-strong transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-[#25D366]/10 border border-[#25D366]/20 flex items-center justify-center flex-shrink-0">
            <WhatsAppIcon className="w-4 h-4 text-[#25D366]" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-nb-text truncate">{channel.name}</p>
            <p className="text-xs text-nb-muted mt-0.5">{cfg.display_phone_number || "Sem número de exibição"}</p>
          </div>
        </div>
        <StatusBadge status={channel.status} />
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Phone Number ID</p>
          <p className="text-nb-secondary font-mono">{cfg.phone_number_id}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">WABA ID</p>
          <p className="text-nb-secondary font-mono">{cfg.waba_id}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Status Meta</p>
          <p className={`font-medium ${statusColor}`}>{waStatus}</p>
        </div>
        <div>
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Token</p>
          <p className="text-nb-secondary font-mono truncate">{cfg.access_token_ref ?? "—"}</p>
        </div>
        {cfg.last_webhook_at && (
          <div className="col-span-2">
            <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-1">Último webhook</p>
            <p className="text-nb-secondary">{new Date(cfg.last_webhook_at).toLocaleString("pt-BR")}</p>
          </div>
        )}
      </div>

      {canEdit && (
        <div className="flex items-center gap-2 pt-1 border-t border-nb-border">
          <button type="button" onClick={() => onArchive(channel)} disabled={busy} className="ml-auto inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-nb-danger/70 hover:text-nb-danger hover:bg-nb-danger/10 border border-transparent hover:border-nb-danger/20 disabled:opacity-50 transition-colors">
            {busy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
            Desconectar
          </button>
        </div>
      )}
    </div>
  );
}

// ── WhatsApp modal ────────────────────────────────────────────────────────────

function WhatsAppFormModal({
  onSave,
  onClose,
  saving,
  saveError,
}: {
  onSave: (f: WaFormState) => void;
  onClose: () => void;
  saving: boolean;
  saveError: string | null;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-xl bg-nb-surface border border-nb-border rounded-2xl shadow-xl my-8">
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
          <div className="flex items-center gap-2.5">
            <WhatsAppIcon className="w-4 h-4 text-[#25D366]" />
            <h2 className="text-base font-semibold text-nb-text">Conectar WhatsApp</h2>
          </div>
          <button type="button" onClick={onClose} disabled={saving} className="p-1.5 rounded-lg text-nb-muted hover:text-nb-secondary hover:bg-nb-elevated transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="px-6 py-5">
          <p className="text-sm text-nb-muted mb-5">
            Conecte um número WhatsApp Business usando os dados do Meta Cloud API. Configuração manual.
          </p>
          <WhatsAppForm onSave={onSave} onCancel={onClose} saving={saving} saveError={saveError} />
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function ImplantarTab({
  agentId,
  role,
}: {
  agentId: string;
  role: MemberRole | null;
}) {
  const [widgetChannels, setWidgetChannels] = useState<WebWidgetChannel[]>([]);
  const [waChannels,     setWaChannels]     = useState<WhatsAppChannel[]>([]);
  const [loading,        setLoading]        = useState(true);
  const [loadError,      setLoadError]      = useState<string | null>(null);
  const fetchedRef = useRef(false);

  // Modal state
  const [widgetModal, setWidgetModal] = useState<"create" | { edit: WebWidgetChannel } | null>(null);
  const [waModal,     setWaModal]     = useState(false);
  const [saving,      setSaving]      = useState(false);
  const [saveError,   setSaveError]   = useState<string | null>(null);

  // Per-card busy
  const [busyId, setBusyId] = useState<string | null>(null);

  // Success feedback
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const writable = canWrite(role);

  // ── Load ──────────────────────────────────────────────────────────────────

  const loadChannels = useCallback(async () => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    try {
      const data = await api.channels.list({ agent_id: agentId });
      setWidgetChannels(data.filter((c): c is WebWidgetChannel => c.channel_type === "web_widget"));
      setWaChannels(data.filter((c): c is WhatsAppChannel => c.channel_type === "whatsapp"));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Erro ao carregar canais.");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => { loadChannels(); }, [loadChannels]);

  function showSuccess(msg: string) {
    setSuccessMsg(msg);
    setTimeout(() => setSuccessMsg(null), 3000);
  }

  // ── Widget CRUD ───────────────────────────────────────────────────────────

  async function handleWidgetCreate(f: WidgetFormState) {
    setSaving(true); setSaveError(null);
    try {
      const created = await api.channels.create(widgetFormToPayload(f, agentId, true) as WebWidgetChannelCreateInput);
      setWidgetChannels((prev) => [created as WebWidgetChannel, ...prev]);
      setWidgetModal(null);
      showSuccess("Widget criado com sucesso.");
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erro ao criar widget.");
    } finally { setSaving(false); }
  }

  async function handleWidgetEdit(ch: WebWidgetChannel, f: WidgetFormState) {
    setSaving(true); setSaveError(null);
    try {
      const updated = await api.channels.update(ch.id, widgetFormToPayload(f, agentId, false));
      setWidgetChannels((prev) => prev.map((c) => (c.id === updated.id ? updated as WebWidgetChannel : c)));
      setWidgetModal(null);
      showSuccess("Widget atualizado.");
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erro ao salvar widget.");
    } finally { setSaving(false); }
  }

  async function handleWidgetToggleStatus(ch: WebWidgetChannel) {
    setBusyId(ch.id);
    try {
      const newStatus = ch.status === "active" ? "inactive" : "active";
      const updated = await api.channels.update(ch.id, { status: newStatus });
      setWidgetChannels((prev) => prev.map((c) => (c.id === updated.id ? updated as WebWidgetChannel : c)));
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Erro ao alterar status.");
    } finally { setBusyId(null); }
  }

  async function handleWidgetArchive(ch: WebWidgetChannel) {
    if (!confirm(`Arquivar "${ch.name}"?`)) return;
    setBusyId(ch.id);
    try {
      await api.channels.archive(ch.id);
      setWidgetChannels((prev) => prev.filter((c) => c.id !== ch.id));
      showSuccess("Widget arquivado.");
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Erro ao arquivar widget.");
    } finally { setBusyId(null); }
  }

  // ── WhatsApp CRUD ─────────────────────────────────────────────────────────

  async function handleWaCreate(f: WaFormState) {
    setSaving(true); setSaveError(null);
    const rawVar = f.token_env_var.trim();
    const varName = rawVar.startsWith("env:") ? rawVar.slice(4) : rawVar;
    const payload: WhatsAppChannelCreateInput = {
      name: f.name.trim(),
      channel_type: "whatsapp",
      agent_id: agentId,
      config: {
        provider: "meta_cloud_api",
        onboarding_type: "manual",
        waba_id: f.waba_id.trim(),
        phone_number_id: f.phone_number_id.trim(),
        display_phone_number: f.display_phone_number.trim() || undefined,
        business_id: f.business_id.trim() || undefined,
        access_token_ref: `env:${varName}`,
        status: f.status,
      },
    };
    try {
      const created = await api.channels.create(payload);
      setWaChannels((prev) => [created as WhatsAppChannel, ...prev]);
      setWaModal(false);
      showSuccess("Canal WhatsApp conectado com sucesso.");
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Erro ao criar canal WhatsApp.");
    } finally { setSaving(false); }
  }

  async function handleWaArchive(ch: WhatsAppChannel) {
    if (!confirm(`Desconectar "${ch.name}"? O canal deixará de receber mensagens.`)) return;
    setBusyId(ch.id);
    try {
      await api.channels.archive(ch.id);
      setWaChannels((prev) => prev.filter((c) => c.id !== ch.id));
      showSuccess("Canal WhatsApp desconectado.");
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : "Erro ao desconectar canal.");
    } finally { setBusyId(null); }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-base font-semibold text-nb-text">Implantar agente</h2>
          <p className="text-sm text-nb-muted mt-1">
            Conecte este agente a canais externos. Comece com um Web Widget para instalar no seu site.
          </p>
        </div>

        {/* Feedback */}
        {successMsg && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-nb-success/10 border border-nb-success/30 text-nb-success text-sm">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />{successMsg}
          </div>
        )}
        {loadError && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-nb-danger/10 border border-nb-danger/30 text-nb-danger text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />{loadError}
          </div>
        )}
        {loading && (
          <div className="flex items-center gap-2 text-nb-muted py-8 justify-center">
            <Loader2 className="w-5 h-5 animate-spin" />
            <span className="text-sm">Carregando canais...</span>
          </div>
        )}

        {!loading && (
          <>
            {/* ── Web Widget section ── */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-nb-muted" />
                  <h3 className="text-sm font-semibold text-nb-secondary">Web Widget</h3>
                </div>
                {writable && (
                  <button type="button" onClick={() => { setSaveError(null); setWidgetModal("create"); }} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text transition-colors">
                    <Plus className="w-3.5 h-3.5" />Novo widget
                  </button>
                )}
              </div>

              {widgetChannels.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 gap-3 bg-nb-panel rounded-2xl border border-nb-border border-dashed">
                  <div className="w-10 h-10 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center">
                    <Globe className="w-5 h-5 text-nb-muted" />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-medium text-nb-secondary">Nenhum widget criado ainda</p>
                    <p className="text-xs text-nb-muted mt-0.5">Crie um widget para instalar este agente no seu site.</p>
                  </div>
                  {writable && (
                    <button type="button" onClick={() => { setSaveError(null); setWidgetModal("create"); }} className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-nb-primary text-white hover:bg-nb-primary-strong transition-colors">
                      <Plus className="w-4 h-4" />Criar primeiro widget
                    </button>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {widgetChannels.map((ch) => (
                    <WidgetCard key={ch.id} channel={ch} canEdit={writable} onEdit={(c) => { setSaveError(null); setWidgetModal({ edit: c }); }} onToggleStatus={handleWidgetToggleStatus} onArchive={handleWidgetArchive} busy={busyId === ch.id} />
                  ))}
                </div>
              )}
            </div>

            {/* ── WhatsApp section ── */}
            <div className="space-y-4 pt-4 border-t border-nb-border">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <WhatsAppIcon className="w-4 h-4 text-[#25D366]" />
                  <h3 className="text-sm font-semibold text-nb-secondary">WhatsApp</h3>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-nb-elevated border border-nb-border text-nb-muted uppercase tracking-wide">Manual</span>
                </div>
                {writable && waChannels.length === 0 && (
                  <button type="button" onClick={() => { setSaveError(null); setWaModal(true); }} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text transition-colors">
                    <Plus className="w-3.5 h-3.5" />Conectar número
                  </button>
                )}
              </div>

              {waChannels.length === 0 ? (
                <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-[#25D366]/10 border border-[#25D366]/20 flex items-center justify-center flex-shrink-0">
                      <WhatsAppIcon className="w-4 h-4 text-[#25D366]" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-nb-text">WhatsApp Business</p>
                      <p className="text-xs text-nb-muted mt-0.5">Meta Cloud API · Configuração manual</p>
                    </div>
                  </div>
                  <p className="text-sm text-nb-muted leading-relaxed">
                    Conecte este agente a um número oficial do WhatsApp Business. Use os dados do Meta Cloud API para configurar o canal.
                  </p>
                  {writable ? (
                    <button type="button" onClick={() => { setSaveError(null); setWaModal(true); }} className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#25D366]/10 border border-[#25D366]/20 text-[#25D366] text-sm font-medium hover:bg-[#25D366]/20 transition-colors">
                      <MessageCircle className="w-4 h-4" />
                      Conectar WhatsApp
                    </button>
                  ) : (
                    <p className="text-xs text-nb-muted">Apenas administradores podem conectar canais.</p>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {waChannels.map((ch) => (
                    <WhatsAppCard key={ch.id} channel={ch} canEdit={writable} onArchive={handleWaArchive} busy={busyId === ch.id} />
                  ))}
                </div>
              )}
            </div>

            {/* ── Outros canais (em breve) ── */}
            <div className="pt-4 border-t border-nb-border">
              <p className="text-xs text-nb-muted font-medium uppercase tracking-widest mb-3">Outros canais</p>
              <div className="flex flex-wrap gap-2">
                {["Instagram", "Telegram", "Slack", "API"].map((name) => (
                  <span key={name} className="px-3 py-1 rounded-full text-xs font-medium bg-nb-elevated border border-nb-border text-nb-muted">
                    {name} · Em breve
                  </span>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Widget modals */}
      {widgetModal === "create" && (
        <WidgetFormModal title="Novo Web Widget" initial={channelToWidgetForm()} onSave={handleWidgetCreate} onClose={() => setWidgetModal(null)} saving={saving} saveError={saveError} />
      )}
      {widgetModal !== null && widgetModal !== "create" && (
        <WidgetFormModal title="Editar Web Widget" initial={channelToWidgetForm(widgetModal.edit)} onSave={(f) => handleWidgetEdit(widgetModal.edit, f)} onClose={() => setWidgetModal(null)} saving={saving} saveError={saveError} />
      )}

      {/* WhatsApp modal */}
      {waModal && (
        <WhatsAppFormModal onSave={handleWaCreate} onClose={() => setWaModal(false)} saving={saving} saveError={saveError} />
      )}
    </>
  );
}
