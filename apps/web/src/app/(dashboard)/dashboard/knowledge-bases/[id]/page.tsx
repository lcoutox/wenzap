"use client";

import { useAuth } from "@clerk/nextjs";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Calendar,
  Check,
  ChevronDown,
  File,
  FileText,
  HelpCircle,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  KnowledgeBase,
  KnowledgeSource,
  KnowledgeSourceCreateInput,
  MemberRole,
  QaPair,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}
function canArchive(role: MemberRole | null) {
  return role === "owner" || role === "admin";
}

const SOURCE_TYPE_LABELS: Record<string, string> = {
  manual_text: "Texto manual",
  faq_qa:      "FAQ",
  txt:         "TXT",
  markdown:    "Markdown",
  pdf_simple:  "PDF",
  csv_simple:  "CSV",
};

const SOURCE_CATEGORIES = [
  "FAQ", "Catálogo de produtos", "Script de atendimento", "Política comercial",
  "Procedimento interno", "Onboarding", "Técnico", "Jurídico", "Preços",
  "Institucional", "Operações",
];

function formatBytes(bytes: number): string {
  if (bytes < 1024)             return `${bytes} B`;
  if (bytes < 1024 * 1024)      return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const inputCls  = "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";
const selectCls = "w-full appearance-none bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors pr-8";

// ── Status badges ─────────────────────────────────────────────────────────────

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",     cls: "bg-nb-success/10 text-nb-success border-nb-success/20" },
    inactive: { label: "Inativa",   cls: "bg-nb-elevated   text-nb-muted   border-nb-border"     },
    archived: { label: "Arquivada", cls: "bg-nb-danger/10  text-nb-danger  border-nb-danger/20"  },
  };
  const s = map[status] ?? { label: status, cls: "bg-nb-elevated text-nb-muted border-nb-border" };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

function SourceStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    ready:      { label: "Pronta",        cls: "bg-nb-success/10 text-nb-success border-nb-success/20" },
    pending:    { label: "Pendente",      cls: "bg-nb-warning/10 text-nb-warning border-nb-warning/20" },
    processing: { label: "Processando…", cls: "bg-nb-info/10    text-nb-info    border-nb-info/20"     },
    failed:     { label: "Erro",         cls: "bg-nb-danger/10  text-nb-danger  border-nb-danger/20"   },
    archived:   { label: "Arquivada",    cls: "bg-nb-elevated   text-nb-muted   border-nb-border"      },
  };
  const s = map[status] ?? { label: status, cls: "bg-nb-elevated text-nb-muted border-nb-border" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── Modal base ────────────────────────────────────────────────────────────────

function Modal({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {children}
    </div>
  );
}

// ── Edit KB Modal ─────────────────────────────────────────────────────────────

function EditKbModal({ kb, onClose, onSave }: {
  kb: KnowledgeBase;
  onClose: () => void;
  onSave: (updated: KnowledgeBase) => void;
}) {
  const [name, setName] = useState(kb.name);
  const [description, setDescription] = useState(kb.description ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { getToken } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { inputRef.current?.focus(); }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true); setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.knowledgeBases.update(token, kb.id, {
        name: name.trim(),
        description: description.trim() || null,
      });
      onSave(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal onClose={onClose}>
      <div className="bg-nb-surface rounded-[18px] border border-nb-border shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
          <h2 className="text-base font-semibold text-nb-text">Editar base</h2>
          <button type="button" onClick={onClose} className="text-nb-muted hover:text-nb-secondary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">
              Nome <span className="text-nb-danger">*</span>
            </label>
            <input ref={inputRef} type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} className={inputCls} />
          </div>
          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">
              Descrição <span className="text-nb-muted">(opcional — vazio para remover)</span>
            </label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={inputCls + " resize-none"} />
          </div>
          {error && <p className="text-xs text-nb-danger bg-nb-danger/10 border border-nb-danger/20 rounded-xl px-3 py-2">{error}</p>}
          <div className="flex gap-3 pt-1">
            <button type="button" onClick={onClose} className="flex-1 px-4 py-2 text-sm font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">Cancelar</button>
            <button type="submit" disabled={saving} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors">{saving ? "Salvando..." : "Salvar"}</button>
          </div>
        </form>
      </div>
    </Modal>
  );
}

// ── Archive KB Confirm ────────────────────────────────────────────────────────

function ArchiveKbModal({ onClose, onConfirm, loading }: { onClose: () => void; onConfirm: () => void; loading: boolean }) {
  return (
    <Modal onClose={onClose}>
      <div className="bg-nb-surface rounded-[18px] border border-nb-border shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-nb-danger/10 border border-nb-danger/20 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-nb-danger" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-nb-text mb-1">Arquivar base de conhecimento</h2>
            <p className="text-xs text-nb-muted">
              Arquivar esta base irá removê-la do fluxo principal e desativar conexões com agentes. Esta ação não pode ser desfeita pela interface.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <button type="button" onClick={onClose} className="flex-1 px-4 py-2 text-sm font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">Cancelar</button>
          <button type="button" onClick={onConfirm} disabled={loading} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-nb-danger rounded-xl hover:opacity-90 disabled:opacity-40 transition-colors">{loading ? "Arquivando..." : "Arquivar"}</button>
        </div>
      </div>
    </Modal>
  );
}

// ── Archive Source Confirm ────────────────────────────────────────────────────

function ArchiveSourceModal({ source, onClose, onConfirm, loading }: { source: KnowledgeSource; onClose: () => void; onConfirm: () => void; loading: boolean }) {
  return (
    <Modal onClose={onClose}>
      <div className="bg-nb-surface rounded-[18px] border border-nb-border shadow-2xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-sm font-semibold text-nb-text mb-2">Arquivar fonte</h2>
        <p className="text-xs text-nb-muted mb-5">
          Deseja arquivar &ldquo;{source.title}&rdquo;? A fonte será removida da listagem.
        </p>
        <div className="flex gap-3">
          <button type="button" onClick={onClose} className="flex-1 px-4 py-2 text-sm font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">Cancelar</button>
          <button type="button" onClick={onConfirm} disabled={loading} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-nb-danger rounded-xl hover:opacity-90 disabled:opacity-40 transition-colors">{loading ? "Arquivando..." : "Arquivar"}</button>
        </div>
      </div>
    </Modal>
  );
}

// ── Add Source Modal ──────────────────────────────────────────────────────────

type SourceTypeTab = "manual_text" | "faq_qa" | "file";

const UPLOAD_ERROR_MAP: Record<number, string> = {
  400: "Arquivo inválido ou tipo não suportado.",
  402: "Limite de fontes atingido para esta base no seu plano.",
  403: "Você não tem permissão para enviar arquivos.",
  404: "Base de conhecimento não encontrada.",
  413: "Arquivo acima do limite permitido para o seu plano.",
};

function AddSourceModal({ kbId, onClose, onCreated }: { kbId: string; onClose: () => void; onCreated: (source: KnowledgeSource) => void }) {
  const { getToken } = useAuth();
  const [tab, setTab] = useState<SourceTypeTab>("manual_text");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [contentText, setContentText] = useState("");
  const [pairs, setPairs] = useState<QaPair[]>([{ question: "", answer: "" }]);
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const MAX_CHARS = 50_000;

  function addPair() { setPairs((p) => [...p, { question: "", answer: "" }]); }
  function removePair(i: number) { setPairs((p) => p.filter((_, idx) => idx !== i)); }
  function updatePair(i: number, field: keyof QaPair, value: string) {
    setPairs((p) => p.map((pair, idx) => (idx === i ? { ...pair, [field]: value } : pair)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const token = await getToken();
    if (!token) { setError("Sessão expirada."); return; }

    if (tab === "file") {
      if (!file) { setError("Selecione um arquivo."); return; }
      setSaving(true);
      try {
        const source = await api.knowledgeBases.sources.upload(token, kbId, file, {
          title: title.trim() || undefined,
          source_category: category.trim() || undefined,
        });
        onCreated(source);
      } catch (e) {
        setError(e instanceof ApiError ? (UPLOAD_ERROR_MAP[e.status] ?? e.message ?? "Não foi possível enviar o arquivo.") : "Não foi possível enviar o arquivo.");
      } finally {
        setSaving(false);
      }
      return;
    }

    if (!title.trim()) { setError("Título é obrigatório."); return; }
    if (tab === "manual_text" && !contentText.trim()) { setError("Conteúdo é obrigatório para texto manual."); return; }
    const validPairs = pairs.filter((p) => p.question.trim() && p.answer.trim());
    if (tab === "faq_qa" && validPairs.length === 0) { setError("Adicione pelo menos um par de pergunta e resposta válido."); return; }

    setSaving(true);
    try {
      let payload: KnowledgeSourceCreateInput;
      if (tab === "manual_text") {
        payload = {
          source_type: "manual_text",
          title: title.trim(),
          content_text: contentText.trim(),
          metadata: category.trim() ? { source_category: category.trim() } : undefined,
        };
      } else {
        payload = {
          source_type: "faq_qa",
          title: title.trim(),
          metadata: {
            ...(category.trim() ? { source_category: category.trim() } : {}),
            qa_pairs: validPairs,
          },
        };
      }
      const source = await api.knowledgeBases.sources.create(token, kbId, payload);
      onCreated(source);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 402) setError("Limite de fontes atingido para esta base no seu plano.");
        else if (e.status === 400 && e.message.toLowerCase().includes("excede")) setError("O conteúdo excede o limite permitido no seu plano.");
        else setError(e.message);
      } else {
        setError(e instanceof Error ? e.message : "Erro ao criar fonte.");
      }
    } finally {
      setSaving(false);
    }
  }

  const tabs = [
    { id: "manual_text" as SourceTypeTab, label: "Texto manual",               icon: FileText },
    { id: "faq_qa"      as SourceTypeTab, label: "FAQ / Perguntas e respostas", icon: HelpCircle },
    { id: "file"        as SourceTypeTab, label: "Arquivo",                     icon: File },
  ] as const;

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-nb-surface rounded-[18px] border border-nb-border shadow-2xl w-full max-w-lg mx-4 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border flex-shrink-0">
          <h2 className="text-base font-semibold text-nb-text">Adicionar fonte</h2>
          <button type="button" onClick={onClose} className="text-nb-muted hover:text-nb-secondary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Type tabs */}
        <div className="flex border-b border-nb-border flex-shrink-0 overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => { setTab(id); setError(null); }}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === id
                  ? "border-nb-primary text-nb-primary-strong"
                  : "border-transparent text-nb-muted hover:text-nb-secondary"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Form */}
        <form id="add-source-form" onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">

          {/* File tab */}
          {tab === "file" && (
            <>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Arquivo <span className="text-nb-danger">*</span>
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.md,.markdown,.pdf,.csv"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-nb-secondary file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-nb-border file:text-xs file:font-medium file:text-nb-secondary file:bg-nb-elevated hover:file:bg-nb-soft cursor-pointer"
                />
                {file && (
                  <p className="mt-1 text-xs text-nb-muted">{file.name} · {formatBytes(file.size)}</p>
                )}
              </div>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Título <span className="text-nb-muted">(opcional)</span>
                </label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} placeholder="Opcional — se vazio, usaremos o nome do arquivo" className={inputCls} />
              </div>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Categoria <span className="text-nb-muted">(opcional)</span>
                </label>
                <div className="relative">
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectCls}>
                    <option value="">Selecione uma categoria</option>
                    {SOURCE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted pointer-events-none" />
                </div>
              </div>
              <div className="rounded-xl bg-nb-elevated border border-nb-border px-3 py-2.5 space-y-1">
                <p className="text-xs text-nb-secondary">Tipos aceitos: TXT, Markdown, PDF com texto selecionável e CSV com cabeçalho.</p>
                <p className="text-xs text-nb-muted">PDFs escaneados sem texto não são suportados nesta fase.</p>
                <p className="text-xs text-nb-muted">O tamanho máximo depende do seu plano.</p>
              </div>
            </>
          )}

          {/* Shared: title + category for text/faq */}
          {tab !== "file" && (
            <>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Título <span className="text-nb-danger">*</span>
                </label>
                <input type="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={300} placeholder="Ex: Política de devolução" className={inputCls} />
              </div>
              <div>
                <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Categoria <span className="text-nb-muted">(opcional)</span>
                </label>
                <div className="relative">
                  <select value={category} onChange={(e) => setCategory(e.target.value)} className={selectCls}>
                    <option value="">Selecione uma categoria</option>
                    {SOURCE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-nb-muted pointer-events-none" />
                </div>
              </div>
            </>
          )}

          {/* Manual text */}
          {tab === "manual_text" && (
            <div>
              <label className="block text-xs font-medium text-nb-secondary mb-1.5">
                Conteúdo <span className="text-nb-danger">*</span>
              </label>
              <textarea
                value={contentText}
                onChange={(e) => setContentText(e.target.value)}
                rows={8}
                maxLength={MAX_CHARS}
                placeholder="Cole ou escreva o conteúdo aqui..."
                className={inputCls + " resize-none"}
              />
              <div className="mt-1 text-right text-xs text-nb-muted">
                {contentText.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
              </div>
            </div>
          )}

          {/* FAQ pairs */}
          {tab === "faq_qa" && (
            <div className="space-y-3">
              <label className="block text-xs font-medium text-nb-secondary">
                Pares de pergunta e resposta <span className="text-nb-danger">*</span>
              </label>
              {pairs.map((pair, i) => (
                <div key={i} className="border border-nb-border rounded-xl p-3 space-y-2 bg-nb-elevated">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-nb-muted">Par #{i + 1}</span>
                    {pairs.length > 1 && (
                      <button type="button" onClick={() => removePair(i)} className="text-nb-muted hover:text-nb-danger transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  <input type="text" value={pair.question} onChange={(e) => updatePair(i, "question", e.target.value)} placeholder="Pergunta" className={inputCls} />
                  <textarea value={pair.answer} onChange={(e) => updatePair(i, "answer", e.target.value)} rows={2} placeholder="Resposta" className={inputCls + " resize-none"} />
                </div>
              ))}
              <button type="button" onClick={addPair} className="flex items-center gap-1.5 text-xs text-nb-primary hover:text-nb-primary-strong font-medium transition-colors">
                <Plus className="w-3.5 h-3.5" />
                Adicionar par
              </button>
            </div>
          )}

          {error && <p className="text-xs text-nb-danger bg-nb-danger/10 border border-nb-danger/20 rounded-xl px-3 py-2">{error}</p>}
        </form>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-nb-border flex-shrink-0">
          <button type="button" onClick={onClose} className="flex-1 px-4 py-2 text-sm font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">Cancelar</button>
          <button type="submit" form="add-source-form" disabled={saving} className="flex-1 px-4 py-2 text-sm font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors">
            {saving
              ? tab === "file" ? "Enviando..." : "Adicionando..."
              : tab === "file" ? "Enviar arquivo" : "Adicionar fonte"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Source Card ───────────────────────────────────────────────────────────────

function SourceCard({ source, onArchive, onReprocess, canArchive: archive, canReprocess, reprocessing }: {
  source: KnowledgeSource;
  onArchive: (source: KnowledgeSource) => void;
  onReprocess: (source: KnowledgeSource) => void;
  canArchive: boolean;
  canReprocess: boolean;
  reprocessing: boolean;
}) {
  const category = (source.metadata_json as Record<string, unknown> | null)?.source_category as string | undefined;
  const showReprocess = canReprocess && (source.status === "ready" || source.status === "failed");

  return (
    <div className="bg-nb-panel rounded-2xl border border-nb-border p-4 flex items-start gap-3 hover:border-nb-border-strong transition-colors">
      <div className="w-8 h-8 rounded-xl bg-nb-elevated border border-nb-border flex items-center justify-center flex-shrink-0">
        {source.status === "processing" ? (
          <Loader2 className="w-4 h-4 text-nb-info animate-spin" />
        ) : source.source_type === "faq_qa" ? (
          <HelpCircle className="w-4 h-4 text-nb-primary" />
        ) : source.original_filename ? (
          <File className="w-4 h-4 text-nb-muted" />
        ) : (
          <FileText className="w-4 h-4 text-nb-muted" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-nb-text truncate">{source.title}</span>
          <SourceStatusBadge status={source.status} />
          {source.status === "ready" && <Check className="w-3.5 h-3.5 text-nb-success flex-shrink-0" />}
        </div>
        <div className="flex items-center gap-3 mt-0.5 flex-wrap">
          <span className="text-xs text-nb-muted">
            {source.original_filename
              ? `${SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type} · ${source.original_filename}${source.file_size_bytes ? ` · ${formatBytes(source.file_size_bytes)}` : ""}`
              : (SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type)}
          </span>
          {category && (
            <span className="text-xs text-nb-primary-strong bg-nb-primary-bg px-1.5 py-0.5 rounded-lg border border-nb-primary/20">
              {category}
            </span>
          )}
          <span className="flex items-center gap-1 text-xs text-nb-muted">
            <Calendar className="w-3 h-3" />
            {new Date(source.created_at).toLocaleDateString("pt-BR")}
          </span>
        </div>
        {source.status === "failed" && source.error_message && (
          <p className="mt-1 text-xs text-nb-danger">{source.error_message}</p>
        )}
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {showReprocess && (
          <button
            type="button"
            onClick={() => onReprocess(source)}
            disabled={reprocessing}
            title="Reprocessar fonte"
            className="p-1.5 text-nb-muted hover:text-nb-primary disabled:opacity-40 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reprocessing ? "animate-spin" : ""}`} />
          </button>
        )}
        {archive && (
          <button
            type="button"
            onClick={() => onArchive(source)}
            title="Arquivar fonte"
            className="p-1.5 text-nb-muted hover:text-nb-danger transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function KnowledgeBaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [showEdit, setShowEdit] = useState(false);
  const [showArchiveKb, setShowArchiveKb] = useState(false);
  const [archivingKb, setArchivingKb] = useState(false);
  const [archiveKbError, setArchiveKbError] = useState<string | null>(null);
  const [showAddSource, setShowAddSource] = useState(false);
  const [sourceToArchive, setSourceToArchive] = useState<KnowledgeSource | null>(null);
  const [archivingSource, setArchivingSource] = useState(false);
  const [reprocessingSourceId, setReprocessingSourceId] = useState<string | null>(null);

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [kbData, sourcesList, me] = await Promise.all([
          api.knowledgeBases.get(token, id),
          api.knowledgeBases.sources.list(token, id),
          api.me(token),
        ]);
        setKb(kbData);
        setSources(sourcesList);
        setRole(me.role);
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          router.push("/dashboard/knowledge-bases");
        } else {
          setLoadError(e instanceof Error ? e.message : "Erro ao carregar base de conhecimento.");
        }
      } finally {
        setLoading(false);
      }
    });
  }, [id, getToken, router]);

  async function handleArchiveKb() {
    if (!kb) return;
    setArchivingKb(true); setArchiveKbError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      await api.knowledgeBases.archive(token, kb.id);
      router.push("/dashboard/knowledge-bases");
    } catch (e) {
      setArchiveKbError(e instanceof Error ? e.message : "Erro ao arquivar base.");
      setArchivingKb(false); setShowArchiveKb(false);
    }
  }

  async function handleReprocess(source: KnowledgeSource) {
    if (!kb || reprocessingSourceId) return;
    setReprocessingSourceId(source.id);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.knowledgeBases.sources.reprocess(token, kb.id, source.id);
      setSources((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch { /* ignore */ } finally {
      setReprocessingSourceId(null);
    }
  }

  async function handleArchiveSource() {
    if (!sourceToArchive || !kb) return;
    setArchivingSource(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      await api.knowledgeBases.sources.archive(token, kb.id, sourceToArchive.id);
      setSources((prev) => prev.filter((s) => s.id !== sourceToArchive.id));
      setSourceToArchive(null);
    } catch { /* keep modal open */ } finally {
      setArchivingSource(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-28 bg-nb-panel rounded-2xl border border-nb-border" />
        <div className="h-8 w-48 bg-nb-panel rounded-xl" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-16 bg-nb-panel rounded-2xl border border-nb-border" />)}
        </div>
      </div>
    );
  }

  if (loadError) {
    return <div className="p-4 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">{loadError}</div>;
  }

  if (!kb) return null;

  const write   = canWrite(role);
  const archive = canArchive(role);

  return (
    <>
      {showEdit && <EditKbModal kb={kb} onClose={() => setShowEdit(false)} onSave={(updated) => { setKb(updated); setShowEdit(false); }} />}
      {showArchiveKb && <ArchiveKbModal onClose={() => setShowArchiveKb(false)} onConfirm={handleArchiveKb} loading={archivingKb} />}
      {showAddSource && <AddSourceModal kbId={kb.id} onClose={() => setShowAddSource(false)} onCreated={(source) => { setSources((prev) => [source, ...prev]); setShowAddSource(false); }} />}
      {sourceToArchive && <ArchiveSourceModal source={sourceToArchive} onClose={() => setSourceToArchive(null)} onConfirm={handleArchiveSource} loading={archivingSource} />}

      {/* KB Header */}
      <div className="bg-nb-panel rounded-2xl border border-nb-border p-6 mb-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-6 h-6 text-nb-primary-strong" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-bold text-nb-text">{kb.name}</h1>
              <KbStatusBadge status={kb.status} />
            </div>
            {kb.description ? (
              <p className="mt-1 text-sm text-nb-muted">{kb.description}</p>
            ) : (
              <p className="mt-1 text-sm text-nb-muted/40 italic">Sem descrição</p>
            )}
            <p className="mt-2 text-xs text-nb-muted">
              Criada em {new Date(kb.created_at).toLocaleDateString("pt-BR")}
            </p>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {write && (
              <button type="button" onClick={() => setShowEdit(true)} className="px-3 py-1.5 text-xs font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors">
                Editar
              </button>
            )}
            {archive && (
              <button type="button" onClick={() => setShowArchiveKb(true)} className="px-3 py-1.5 text-xs font-medium text-nb-danger border border-nb-danger/20 rounded-xl hover:bg-nb-danger/10 transition-colors">
                Arquivar
              </button>
            )}
          </div>
        </div>

        {archiveKbError && (
          <p className="mt-3 text-xs text-nb-danger bg-nb-danger/10 border border-nb-danger/20 rounded-xl px-3 py-2">{archiveKbError}</p>
        )}
      </div>

      {/* Sources section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-nb-text">Fontes</h2>
            <p className="text-xs text-nb-muted mt-0.5">
              {sources.length === 0 ? "Nenhuma fonte adicionada ainda." : `${sources.length} fonte${sources.length !== 1 ? "s" : ""}`}
            </p>
          </div>
          {write && (
            <button
              type="button"
              onClick={() => setShowAddSource(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary-bg transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Adicionar Fonte
            </button>
          )}
        </div>

        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-nb-border rounded-2xl">
            <FileText className="w-8 h-8 text-nb-border-strong mb-3" />
            <p className="text-sm text-nb-secondary mb-1">Nenhuma fonte adicionada ainda.</p>
            <p className="text-xs text-nb-muted">Adicione textos, FAQs e procedimentos para enriquecer esta base.</p>
            {write && (
              <button
                type="button"
                onClick={() => setShowAddSource(true)}
                className="mt-4 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-nb-primary border border-nb-primary/20 rounded-xl hover:bg-nb-primary-bg transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                Adicionar primeira fonte
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {sources.map((source) => (
              <SourceCard
                key={source.id}
                source={source}
                canArchive={archive}
                canReprocess={write}
                reprocessing={reprocessingSourceId === source.id}
                onArchive={setSourceToArchive}
                onReprocess={handleReprocess}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
