"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import {
  Download,
  Loader2,
  MessageSquare,
  MoreHorizontal,
  Pencil,
  Phone,
  Plus,
  Search,
  Trash2,
  User,
  Variable,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Contact, ContactVariable, MemberRole } from "@/lib/api";
import { PhoneInput } from "@/components/ui/PhoneInput";

// ── Helpers ───────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
}

function displayName(contact: Contact) {
  return contact.name || contact.email || contact.phone || "—";
}

// ── Modal base ────────────────────────────────────────────────────────────────

function Modal({
  open, onClose, title, children,
}: {
  open: boolean; onClose: () => void; title: string; children: React.ReactNode;
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
      <div className="w-full max-w-lg bg-nb-surface border border-nb-border rounded-2xl shadow-2xl flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between px-5 py-4 border-b border-nb-border shrink-0">
          <h2 className="text-sm font-semibold text-nb-text">{title}</h2>
          <button type="button" onClick={onClose} className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="overflow-y-auto flex-1 px-5 py-4">{children}</div>
      </div>
    </div>
  );
}

// ── Variables Tab ─────────────────────────────────────────────────────────────

function VariablesTab({ contactId, readonly }: { contactId: string; readonly: boolean }) {
  const [vars, setVars] = useState<ContactVariable[]>([]);
  const [loading, setLoading] = useState(true);
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editVal, setEditVal] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.contacts.variables.list(contactId);
      setVars(data);
    } catch { setError("Erro ao carregar variáveis."); }
    finally { setLoading(false); }
  }, [contactId]);

  useEffect(() => { load(); }, [load]);

  async function handleAdd() {
    if (!newKey.trim() || !newVal.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const v = await api.contacts.variables.create(contactId, { key: newKey.trim(), value: newVal.trim() });
      setVars((prev) => [...prev, v]);
      setNewKey(""); setNewVal("");
    } catch (e) {
      setError(e instanceof ApiError && e.status === 409
        ? `Já existe uma variável com a chave "${newKey}".`
        : "Erro ao criar variável.");
    } finally { setAdding(false); }
  }

  async function handleSaveEdit(id: string) {
    if (!editVal.trim()) return;
    setBusy((p) => ({ ...p, [id]: true }));
    try {
      const v = await api.contacts.variables.update(contactId, id, { value: editVal.trim() });
      setVars((prev) => prev.map((x) => x.id === id ? v : x));
      setEditingId(null);
    } catch { setError("Erro ao editar variável."); }
    finally { setBusy((p) => ({ ...p, [id]: false })); }
  }

  async function handleDelete(id: string) {
    setBusy((p) => ({ ...p, [id]: true }));
    try {
      await api.contacts.variables.delete(contactId, id);
      setVars((prev) => prev.filter((x) => x.id !== id));
    } catch { setError("Erro ao excluir variável."); }
    finally { setBusy((p) => ({ ...p, [id]: false })); }
  }

  if (loading) return <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-nb-muted" /></div>;

  return (
    <div className="space-y-4">
      <p className="text-xs text-nb-muted leading-relaxed">
        Variáveis ajudam os agentes de IA a personalizar respostas e segmentar clientes no futuro.
      </p>

      {error && <p className="text-xs text-nb-danger">{error}</p>}

      {/* Existing variables */}
      {vars.length === 0 ? (
        <div className="text-center py-8 border border-dashed border-nb-border rounded-xl">
          <Variable className="w-6 h-6 text-nb-muted mx-auto mb-2" />
          <p className="text-sm text-nb-secondary">Nenhuma variável ainda</p>
        </div>
      ) : (
        <div className="space-y-2">
          {vars.map((v) => (
            <div key={v.id} className="flex items-center gap-2 p-3 bg-nb-panel border border-nb-border rounded-xl">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-mono font-medium text-nb-primary truncate">{v.key}</p>
                {editingId === v.id ? (
                  <input
                    className="mt-1 w-full bg-nb-elevated border border-nb-border rounded-lg px-2 py-1 text-xs text-nb-text focus:outline-none focus:border-nb-primary"
                    value={editVal}
                    onChange={(e) => setEditVal(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSaveEdit(v.id)}
                    autoFocus
                  />
                ) : (
                  <p className="text-xs text-nb-secondary mt-0.5 truncate">{v.value}</p>
                )}
              </div>
              {!readonly && (
                busy[v.id] ? <Loader2 className="w-4 h-4 animate-spin text-nb-muted shrink-0" /> :
                editingId === v.id ? (
                  <div className="flex gap-1 shrink-0">
                    <button type="button" onClick={() => handleSaveEdit(v.id)} className="px-2 py-1 text-xs font-medium bg-nb-primary text-white rounded-lg">Salvar</button>
                    <button type="button" onClick={() => setEditingId(null)} className="px-2 py-1 text-xs text-nb-muted border border-nb-border rounded-lg">Cancelar</button>
                  </div>
                ) : (
                  <div className="flex gap-1 shrink-0">
                    <button type="button" onClick={() => { setEditingId(v.id); setEditVal(v.value); }} className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                    <button type="button" onClick={() => handleDelete(v.id)} className="p-1.5 rounded-lg hover:bg-nb-danger/10 text-nb-muted hover:text-nb-danger transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                  </div>
                )
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add new variable */}
      {!readonly && (
        <div className="space-y-2 pt-2 border-t border-nb-border">
          <p className="text-xs font-semibold text-nb-muted uppercase tracking-wide">Nova variável</p>
          <div className="flex gap-2">
            <input
              className="flex-1 bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-xs text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary"
              placeholder="chave"
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
            />
            <input
              className="flex-1 bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-xs text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary"
              placeholder="valor"
              value={newVal}
              onChange={(e) => setNewVal(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button
              type="button"
              onClick={handleAdd}
              disabled={adding || !newKey.trim() || !newVal.trim()}
              className="px-3 py-2 text-xs font-medium bg-nb-primary text-white rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Contact Form Modal ────────────────────────────────────────────────────────

function ContactModal({
  open,
  onClose,
  onSaved,
  initial,
  readonly,
  initialTab = "data",
}: {
  open: boolean;
  onClose: () => void;
  onSaved: (c: Contact) => void;
  initial?: Contact;
  readonly: boolean;
  initialTab?: "data" | "variables";
}) {
  const [tab, setTab] = useState<"data" | "variables">("data");
  const [name, setName] = useState(initial?.name ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [origin, setOrigin] = useState(initial?.origin ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) {
      setTab(initialTab);
      setName(initial?.name ?? "");
      setEmail(initial?.email ?? "");
      setPhone(initial?.phone ?? "");
      setOrigin(initial?.origin ?? "");
      setError("");
    }
  }, [open, initial, initialTab]);

  const isEdit = !!initial;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() && !email.trim() && !phone.trim()) {
      setError("Informe pelo menos nome, e-mail ou telefone.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = {
        name: name.trim() || undefined,
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        origin: origin.trim() || undefined,
      };
      const saved = isEdit
        ? await api.contacts.update(initial.id, payload)
        : await api.contacts.create(payload);
      onSaved(saved);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message || "E-mail ou telefone já cadastrado.");
      } else if (e instanceof ApiError && e.status === 422) {
        setError("Informe pelo menos nome, e-mail ou telefone.");
      } else {
        setError("Erro ao salvar contato.");
      }
    } finally {
      setSaving(false);
    }
  }

  const noContactId = !isEdit;

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Editar contato" : "Novo contato"}>
      {/* Tabs (only in edit mode) */}
      {isEdit && (
        <div className="flex gap-1 mb-4 p-1 bg-nb-elevated rounded-xl">
          {(["data", "variables"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`flex-1 py-1.5 text-xs font-medium rounded-lg transition-colors ${tab === t ? "bg-nb-surface text-nb-text shadow-sm" : "text-nb-muted hover:text-nb-secondary"}`}
            >
              {t === "data" ? "Dados do contato" : "Variáveis"}
            </button>
          ))}
        </div>
      )}

      {tab === "variables" && isEdit ? (
        <VariablesTab contactId={initial.id} readonly={readonly} />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <Field label="Nome">
            <input
              className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
              placeholder="Nome completo"
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={readonly}
            />
          </Field>
          <PhoneInput
            label="Telefone"
            value={phone}
            onChange={(val) => setPhone(val ?? "")}
            disabled={readonly}
          />
          <Field label="E-mail">
            <input
              type="email"
              className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
              placeholder="email@exemplo.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={readonly}
            />
          </Field>
          <Field label="Origem">
            <input
              className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
              placeholder="Ex: site, indicação, WhatsApp…"
              value={origin}
              onChange={(e) => setOrigin(e.target.value)}
              disabled={readonly}
            />
          </Field>

          {!phone.trim() && !email.trim() && !readonly && (
            <p className="text-xs text-nb-warning bg-nb-warning/10 border border-nb-warning/20 rounded-xl px-3 py-2">
              Contatos sem telefone ou e-mail não poderão ser usados em disparos futuros.
            </p>
          )}

          {error && <p className="text-xs text-nb-danger">{error}</p>}

          {!readonly && (
            <div className="flex justify-end gap-2 pt-1">
              <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
                Cancelar
              </button>
              <button type="submit" disabled={saving} className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors">
                {saving ? "Salvando…" : isEdit ? "Salvar" : "Criar contato"}
              </button>
            </div>
          )}
        </form>
      )}
    </Modal>
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

// ── Delete confirm ────────────────────────────────────────────────────────────

function DeleteModal({
  open, onClose, contact, onDeleted,
}: {
  open: boolean; onClose: () => void; contact: Contact | null; onDeleted: (id: string) => void;
}) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  async function handleDelete() {
    if (!contact) return;
    setDeleting(true);
    setError("");
    try {
      await api.contacts.delete(contact.id);
      onDeleted(contact.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError("Este contato possui conversas vinculadas e não pode ser excluído.");
      } else {
        setError("Erro ao excluir contato.");
      }
    } finally { setDeleting(false); }
  }

  return (
    <Modal open={open} onClose={onClose} title="Excluir contato">
      <div className="space-y-4">
        <p className="text-sm text-nb-secondary">
          Tem certeza que deseja excluir <strong className="text-nb-text">{contact ? displayName(contact) : ""}</strong>? Esta ação não pode ser desfeita.
        </p>
        {error && <p className="text-xs text-nb-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="px-4 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
            Cancelar
          </button>
          <button type="button" onClick={handleDelete} disabled={deleting} className="px-4 py-2 text-xs font-medium text-white bg-nb-danger rounded-xl hover:opacity-90 disabled:opacity-40 transition-opacity">
            {deleting ? "Excluindo…" : "Excluir"}
          </button>
        </div>
      </div>
    </Modal>
  );
}

// ── Row actions menu ──────────────────────────────────────────────────────────

function RowActions({
  contact,
  onEdit,
  onDelete,
  onViewConversations,
  onViewData,
}: {
  contact: Contact;
  onEdit: () => void;
  onDelete: () => void;
  onViewConversations: () => void;
  onViewData: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const MENU_WIDTH = 208; // px, matches w-52

  function toggle() {
    if (!open && btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      setPos({
        top: rect.bottom + 4,
        left: Math.max(8, rect.right - MENU_WIDTH),
      });
    }
    setOpen((v) => !v);
  }

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      const target = e.target as Node;
      if (!btnRef.current?.contains(target) && !menuRef.current?.contains(target)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        onClick={toggle}
        className="p-1.5 rounded-lg hover:bg-nb-elevated text-nb-muted hover:text-nb-secondary transition-colors"
      >
        <MoreHorizontal className="w-4 h-4" />
      </button>
      {/* Portal — the table wrapper uses overflow-hidden for its rounded
          corners, which would silently clip an absolutely-positioned menu
          (worst for the last row, whose menu has nowhere to open into). */}
      {open && pos && createPortal(
        <div
          ref={menuRef}
          style={{ position: "fixed", top: pos.top, left: pos.left, width: MENU_WIDTH }}
          className="z-50 bg-nb-surface border border-nb-border rounded-xl shadow-lg py-1"
        >
          <MenuItem icon={MessageSquare} label="Ver conversas" onClick={() => { setOpen(false); onViewConversations(); }} />
          {!!contact.variables_count && (
            <MenuItem
              icon={Variable}
              label={`Ver dados capturados (${contact.variables_count})`}
              onClick={() => { setOpen(false); onViewData(); }}
            />
          )}
          <MenuItem icon={Pencil} label="Editar" onClick={() => { setOpen(false); onEdit(); }} />
          <MenuItem icon={Trash2} label="Excluir" danger onClick={() => { setOpen(false); onDelete(); }} />
        </div>,
        document.body
      )}
    </>
  );
}

function MenuItem({ icon: Icon, label, onClick, danger = false }: { icon: React.ElementType; label: string; onClick: () => void; danger?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium transition-colors ${danger ? "text-nb-danger hover:bg-nb-danger/10" : "text-nb-secondary hover:bg-nb-elevated hover:text-nb-text"}`}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function Skeleton() {
  return (
    <div className="space-y-0">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3.5 border-b border-nb-border/60 animate-pulse">
          <div className="w-8 h-8 rounded-full bg-nb-elevated shrink-0" />
          <div className="flex-1 space-y-1.5">
            <div className="h-3 bg-nb-elevated rounded w-1/3" />
            <div className="h-2.5 bg-nb-elevated rounded w-1/4" />
          </div>
          <div className="h-3 bg-nb-elevated rounded w-20 hidden sm:block" />
          <div className="h-3 bg-nb-elevated rounded w-24 hidden md:block" />
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ContactsPage() {
  const router = useRouter();

  const [contacts, setContacts] = useState<Contact[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [userRole, setUserRole] = useState<MemberRole | null>(null);

  const [addOpen, setAddOpen] = useState(false);
  const [editContact, setEditContact] = useState<Contact | null>(null);
  const [editTab, setEditTab] = useState<"data" | "variables">("data");
  const [deleteContact, setDeleteContact] = useState<Contact | null>(null);

  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.me().then((me) => setUserRole(me.role)).catch(() => {});
  }, []);

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(search), 300);
  }, [search]);

  const load = useCallback(async (q: string) => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.contacts.list({ q: q || undefined, limit: 50 });
      setContacts(result.items);
      setTotal(result.total);
    } catch {
      setError("Erro ao carregar contatos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(debouncedSearch); }, [debouncedSearch, load]);

  function handleSaved(c: Contact) {
    setAddOpen(false);
    setEditContact(null);
    // Insert or update in list
    setContacts((prev) => {
      const exists = prev.find((x) => x.id === c.id);
      if (exists) return prev.map((x) => x.id === c.id ? c : x);
      return [c, ...prev];
    });
    setTotal((t) => editContact ? t : t + 1);
  }

  function handleDeleted(id: string) {
    setDeleteContact(null);
    setContacts((prev) => prev.filter((c) => c.id !== id));
    setTotal((t) => t - 1);
  }

  const write = canWrite(userRole);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg font-bold text-nb-text">Contatos</h1>
          <p className="text-sm text-nb-muted mt-0.5">
            Gerencie seus clientes, leads e histórico de conversas.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-nb-muted border border-nb-border rounded-xl opacity-50 cursor-not-allowed"
          >
            <Download className="w-3.5 h-3.5" />
            Importar CSV
            <span className="ml-1 px-1.5 py-0.5 text-xs font-medium rounded-full bg-nb-elevated border border-nb-border text-nb-muted">
              Em breve
            </span>
          </button>
          {write && (
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Adicionar contato
            </button>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted pointer-events-none" />
        <input
          className="w-full bg-nb-surface border border-nb-border rounded-xl pl-9 pr-4 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
          placeholder="Buscar por nome, e-mail ou telefone"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button type="button" onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-nb-muted hover:text-nb-secondary">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Count */}
      {!loading && !error && (
        <p className="text-xs text-nb-muted">
          {total === 0 ? "Nenhum contato encontrado." : `${total} contato${total !== 1 ? "s" : ""}`}
        </p>
      )}

      {/* Table */}
      <div className="bg-nb-surface border border-nb-border rounded-2xl overflow-hidden">
        {/* Table header */}
        <div className="hidden md:grid grid-cols-[2fr_1fr_1fr_1fr_1fr_40px] gap-4 px-4 py-3 border-b border-nb-border bg-nb-elevated/50">
          {["Nome", "Telefone", "E-mail", "Origem", "Criado em", ""].map((h) => (
            <span key={h} className="text-xs font-semibold text-nb-muted uppercase tracking-wide">{h}</span>
          ))}
        </div>

        {loading ? (
          <Skeleton />
        ) : error ? (
          <div className="px-4 py-12 text-center">
            <p className="text-sm text-nb-danger">{error}</p>
            <button type="button" onClick={() => load(debouncedSearch)} className="mt-3 text-xs text-nb-primary hover:underline">Tentar novamente</button>
          </div>
        ) : contacts.length === 0 ? (
          <div className="px-4 py-16 text-center">
            <User className="w-10 h-10 text-nb-muted mx-auto mb-3" />
            <p className="text-sm font-medium text-nb-secondary mb-1">
              {debouncedSearch ? "Nenhum contato encontrado." : "Nenhum contato ainda."}
            </p>
            <p className="text-xs text-nb-muted">
              {debouncedSearch ? "Tente outro termo de busca." : "Adicione seu primeiro contato."}
            </p>
            {!debouncedSearch && write && (
              <button type="button" onClick={() => setAddOpen(true)} className="mt-4 flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong transition-colors mx-auto">
                <Plus className="w-3.5 h-3.5" /> Adicionar contato
              </button>
            )}
          </div>
        ) : (
          <div>
            {contacts.map((c, i) => (
              <div
                key={c.id}
                className={`flex md:grid md:grid-cols-[2fr_1fr_1fr_1fr_1fr_40px] gap-4 items-center px-4 py-3.5 ${i < contacts.length - 1 ? "border-b border-nb-border/60" : ""} hover:bg-nb-elevated/30 transition-colors`}
              >
                {/* Name */}
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-full bg-nb-primary/10 border border-nb-primary/20 flex items-center justify-center shrink-0">
                    <span className="text-xs font-semibold text-nb-primary-strong">
                      {(c.name?.[0] ?? c.email?.[0] ?? "?").toUpperCase()}
                    </span>
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5">
                      <p className="text-sm font-medium text-nb-text truncate">{displayName(c)}</p>
                      {!!c.variables_count && (
                        <button
                          type="button"
                          onClick={() => { setEditTab("variables"); setEditContact(c); }}
                          title={`${c.variables_count} dado(s) capturado(s) pela IA`}
                          className="shrink-0 inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-nb-primary-bg text-nb-primary-strong hover:opacity-80 transition-opacity"
                        >
                          <Variable className="w-2.5 h-2.5" /> {c.variables_count}
                        </button>
                      )}
                    </div>
                    {/* mobile: show phone/email below name */}
                    <p className="md:hidden text-xs text-nb-muted truncate">{c.phone ?? c.email ?? ""}</p>
                  </div>
                </div>
                {/* Phone */}
                <p className="hidden md:flex items-center gap-1.5 text-sm text-nb-secondary truncate">
                  {c.phone ? <><Phone className="w-3.5 h-3.5 text-nb-muted shrink-0" />{c.phone}</> : <span className="text-nb-muted">—</span>}
                </p>
                {/* Email */}
                <p className="hidden md:block text-sm text-nb-secondary truncate">{c.email ?? <span className="text-nb-muted">—</span>}</p>
                {/* Origin */}
                <p className="hidden md:block text-sm text-nb-secondary truncate">{c.origin ?? <span className="text-nb-muted">—</span>}</p>
                {/* Created at */}
                <p className="hidden md:block text-sm text-nb-muted">{formatDate(c.created_at)}</p>
                {/* Actions */}
                <div className="shrink-0 ml-auto md:ml-0">
                  <RowActions
                    contact={c}
                    onEdit={() => { setEditTab("data"); setEditContact(c); }}
                    onDelete={() => setDeleteContact(c)}
                    onViewConversations={() => router.push(`/dashboard/inbox?contactId=${c.id}`)}
                    onViewData={() => { setEditTab("variables"); setEditContact(c); }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modals */}
      <ContactModal
        open={addOpen}
        onClose={() => setAddOpen(false)}
        onSaved={handleSaved}
        readonly={false}
      />
      <ContactModal
        open={!!editContact}
        onClose={() => setEditContact(null)}
        onSaved={handleSaved}
        initial={editContact ?? undefined}
        readonly={!write}
        initialTab={editTab}
      />
      <DeleteModal
        open={!!deleteContact}
        onClose={() => setDeleteContact(null)}
        contact={deleteContact}
        onDeleted={handleDeleted}
      />
    </div>
  );
}
