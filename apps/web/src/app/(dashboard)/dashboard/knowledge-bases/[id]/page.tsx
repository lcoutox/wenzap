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
  faq_qa: "FAQ",
  txt: "TXT",
  markdown: "Markdown",
  pdf_simple: "PDF",
  csv_simple: "CSV",
};

const SOURCE_CATEGORIES = [
  "FAQ",
  "Catálogo de produtos",
  "Script de atendimento",
  "Política comercial",
  "Procedimento interno",
  "Onboarding",
  "Técnico",
  "Jurídico",
  "Preços",
  "Institucional",
  "Operações",
];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Status badges ─────────────────────────────────────────────────────────────

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",    cls: "bg-green-50 text-green-700 border-green-200" },
    inactive: { label: "Inativa",  cls: "bg-gray-50 text-gray-500 border-gray-200" },
    archived: { label: "Arquivada", cls: "bg-red-50 text-red-600 border-red-200" },
  };
  const s = map[status] ?? { label: status, cls: "bg-gray-50 text-gray-500 border-gray-200" };
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

function SourceStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    ready:      { label: "Pronta",         cls: "bg-green-50 text-green-700 border-green-200" },
    pending:    { label: "Pendente",       cls: "bg-amber-50 text-amber-700 border-amber-200" },
    processing: { label: "Processando…",  cls: "bg-blue-50 text-blue-700 border-blue-200" },
    failed:     { label: "Erro",          cls: "bg-red-50 text-red-600 border-red-200" },
    archived:   { label: "Arquivada",     cls: "bg-gray-50 text-gray-400 border-gray-200" },
  };
  const s = map[status] ?? { label: status, cls: "bg-gray-50 text-gray-500 border-gray-200" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── Edit KB Modal ─────────────────────────────────────────────────────────────

function EditKbModal({
  kb,
  onClose,
  onSave,
}: {
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
    setSaving(true);
    setError(null);
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Editar base</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Nome <span className="text-red-500">*</span>
            </label>
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Descrição <span className="text-gray-400">(opcional — deixe vazio para remover)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            />
          </div>
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Archive KB Confirm Modal ──────────────────────────────────────────────────

function ArchiveKbModal({
  onClose,
  onConfirm,
  loading,
}: {
  onClose: () => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-red-50 border border-red-200 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-red-500" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-gray-900 mb-1">Arquivar base de conhecimento</h2>
            <p className="text-xs text-gray-500">
              Arquivar esta base irá removê-la do fluxo principal e desativar conexões com
              agentes. Esta ação não pode ser desfeita pela interface.
            </p>
          </div>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60 transition-colors"
          >
            {loading ? "Arquivando..." : "Arquivar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Archive Source Confirm ────────────────────────────────────────────────────

function ArchiveSourceModal({
  source,
  onClose,
  onConfirm,
  loading,
}: {
  source: KnowledgeSource;
  onClose: () => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-sm mx-4 p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-2">Arquivar fonte</h2>
        <p className="text-xs text-gray-500 mb-5">
          Deseja arquivar &ldquo;{source.title}&rdquo;? A fonte será removida da listagem.
        </p>
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-60"
          >
            {loading ? "Arquivando..." : "Arquivar"}
          </button>
        </div>
      </div>
    </div>
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

function AddSourceModal({
  kbId,
  onClose,
  onCreated,
}: {
  kbId: string;
  onClose: () => void;
  onCreated: (source: KnowledgeSource) => void;
}) {
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

  function addPair() {
    setPairs((p) => [...p, { question: "", answer: "" }]);
  }

  function removePair(i: number) {
    setPairs((p) => p.filter((_, idx) => idx !== i));
  }

  function updatePair(i: number, field: keyof QaPair, value: string) {
    setPairs((p) => p.map((pair, idx) => (idx === i ? { ...pair, [field]: value } : pair)));
  }

  function handleTabChange(next: SourceTypeTab) {
    setTab(next);
    setError(null);
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
        if (e instanceof ApiError) {
          setError(UPLOAD_ERROR_MAP[e.status] ?? e.message ?? "Não foi possível enviar o arquivo. Tente novamente.");
        } else {
          setError("Não foi possível enviar o arquivo. Tente novamente.");
        }
      } finally {
        setSaving(false);
      }
      return;
    }

    if (!title.trim()) { setError("Título é obrigatório."); return; }

    if (tab === "manual_text") {
      if (!contentText.trim()) { setError("Conteúdo é obrigatório para texto manual."); return; }
    } else {
      const validPairs = pairs.filter((p) => p.question.trim() && p.answer.trim());
      if (validPairs.length === 0) {
        setError("Adicione pelo menos um par de pergunta e resposta válido.");
        return;
      }
    }

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
        const validPairs = pairs.filter((p) => p.question.trim() && p.answer.trim());
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
        if (e.status === 402) {
          setError("Limite de fontes atingido para esta base no seu plano.");
        } else if (e.status === 400 && e.message.toLowerCase().includes("excede")) {
          setError("O conteúdo excede o limite permitido no seu plano.");
        } else {
          setError(e.message);
        }
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 flex-shrink-0">
          <h2 className="text-base font-semibold text-gray-900">Adicionar fonte</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Type tabs */}
        <div className="flex border-b border-gray-100 flex-shrink-0 overflow-x-auto">
          {tabs.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => handleTabChange(id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                tab === id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>

        {/* Form */}
        <form id="add-source-form" onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto flex-1">

          {/* File upload tab */}
          {tab === "file" && (
            <>
              {/* File picker */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Arquivo <span className="text-red-500">*</span>
                </label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".txt,.md,.markdown,.pdf,.csv"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-gray-700 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-gray-300 file:text-xs file:font-medium file:text-gray-700 file:bg-white hover:file:bg-gray-50 cursor-pointer"
                />
                {file && (
                  <p className="mt-1 text-xs text-gray-500">
                    {file.name} · {formatBytes(file.size)}
                  </p>
                )}
              </div>

              {/* Title (optional for file) */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Título <span className="text-gray-400">(opcional)</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={300}
                  placeholder="Opcional — se vazio, usaremos o nome do arquivo"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Categoria <span className="text-gray-400">(opcional)</span>
                </label>
                <div className="relative">
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full appearance-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 pr-8"
                  >
                    <option value="">Selecione uma categoria</option>
                    {SOURCE_CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>

              {/* Help text */}
              <div className="rounded-lg bg-gray-50 border border-gray-200 px-3 py-2.5 space-y-1">
                <p className="text-xs text-gray-600">
                  Tipos aceitos: TXT, Markdown, PDF com texto selecionável e CSV com cabeçalho.
                </p>
                <p className="text-xs text-gray-500">
                  PDFs escaneados sem texto não são suportados nesta fase.
                </p>
                <p className="text-xs text-gray-500">
                  O tamanho máximo depende do seu plano.
                </p>
              </div>
            </>
          )}

          {/* Text / FAQ tabs share title + category */}
          {tab !== "file" && (
            <>
              {/* Title */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Título <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={300}
                  placeholder="Ex: Política de devolução"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              {/* Category */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Categoria <span className="text-gray-400">(opcional)</span>
                </label>
                <div className="relative">
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full appearance-none border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 pr-8"
                  >
                    <option value="">Selecione uma categoria</option>
                    {SOURCE_CATEGORIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
              </div>
            </>
          )}

          {/* Manual text */}
          {tab === "manual_text" && (
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Conteúdo <span className="text-red-500">*</span>
              </label>
              <textarea
                value={contentText}
                onChange={(e) => setContentText(e.target.value)}
                rows={8}
                maxLength={MAX_CHARS}
                placeholder="Cole ou escreva o conteúdo aqui..."
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
              />
              <div className="mt-1 text-right text-xs text-gray-400">
                {contentText.length.toLocaleString()} / {MAX_CHARS.toLocaleString()}
              </div>
            </div>
          )}

          {/* FAQ pairs */}
          {tab === "faq_qa" && (
            <div className="space-y-3">
              <label className="block text-xs font-medium text-gray-700">
                Pares de pergunta e resposta <span className="text-red-500">*</span>
              </label>
              {pairs.map((pair, i) => (
                <div key={i} className="border border-gray-200 rounded-lg p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-gray-500">Par #{i + 1}</span>
                    {pairs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removePair(i)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    value={pair.question}
                    onChange={(e) => updatePair(i, "question", e.target.value)}
                    placeholder="Pergunta"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <textarea
                    value={pair.answer}
                    onChange={(e) => updatePair(i, "answer", e.target.value)}
                    rows={2}
                    placeholder="Resposta"
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={addPair}
                className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-700 font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                Adicionar par
              </button>
            </div>
          )}

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </form>

        {/* Footer */}
        <div className="flex gap-3 px-6 py-4 border-t border-gray-100 flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 px-4 py-2 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
          >
            Cancelar
          </button>
          <button
            type="submit"
            form="add-source-form"
            disabled={saving}
            className="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60 transition-colors"
          >
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

function SourceCard({
  source,
  onArchive,
  onReprocess,
  canArchive: archive,
  canReprocess,
  reprocessing,
}: {
  source: KnowledgeSource;
  onArchive: (source: KnowledgeSource) => void;
  onReprocess: (source: KnowledgeSource) => void;
  canArchive: boolean;
  canReprocess: boolean;
  reprocessing: boolean;
}) {
  const category = (source.metadata_json as Record<string, unknown> | null)
    ?.source_category as string | undefined;

  const showReprocess =
    canReprocess && (source.status === "ready" || source.status === "failed");

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-gray-50 border border-gray-200 flex items-center justify-center flex-shrink-0">
        {source.status === "processing" ? (
          <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
        ) : source.source_type === "faq_qa" ? (
          <HelpCircle className="w-4 h-4 text-indigo-400" />
        ) : source.original_filename ? (
          <File className="w-4 h-4 text-gray-400" />
        ) : (
          <FileText className="w-4 h-4 text-gray-400" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-gray-900 truncate">{source.title}</span>
          <SourceStatusBadge status={source.status} />
          {source.status === "ready" && (
            <Check className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
          )}
        </div>
        <div className="flex items-center gap-3 mt-0.5 flex-wrap">
          <span className="text-xs text-gray-400">
            {source.original_filename
              ? `${SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type} · ${source.original_filename}${source.file_size_bytes ? ` · ${formatBytes(source.file_size_bytes)}` : ""}`
              : (SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type)}
          </span>
          {category && (
            <span className="text-xs text-indigo-500 bg-indigo-50 px-1.5 py-0.5 rounded">
              {category}
            </span>
          )}
          <span className="flex items-center gap-1 text-xs text-gray-400">
            <Calendar className="w-3 h-3" />
            {new Date(source.created_at).toLocaleDateString("pt-BR")}
          </span>
        </div>
        {source.status === "failed" && source.error_message && (
          <p className="mt-1 text-xs text-red-500">{source.error_message}</p>
        )}
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {showReprocess && (
          <button
            type="button"
            onClick={() => onReprocess(source)}
            disabled={reprocessing}
            title="Reprocessar fonte"
            className="p-1.5 text-gray-400 hover:text-indigo-500 disabled:opacity-40 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${reprocessing ? "animate-spin" : ""}`} />
          </button>
        )}
        {archive && (
          <button
            type="button"
            onClick={() => onArchive(source)}
            title="Arquivar fonte"
            className="p-1.5 text-gray-400 hover:text-red-500 transition-colors"
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

  // Modals
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
    setArchivingKb(true);
    setArchiveKbError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      await api.knowledgeBases.archive(token, kb.id);
      router.push("/dashboard/knowledge-bases");
    } catch (e) {
      setArchiveKbError(e instanceof Error ? e.message : "Erro ao arquivar base.");
      setArchivingKb(false);
      setShowArchiveKb(false);
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
    } catch {
      // Silently ignore; UI will reflect latest state on next refresh
    } finally {
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
    } catch {
      // keep modal open on error — user can retry or cancel
    } finally {
      setArchivingSource(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-28 bg-white rounded-xl border border-gray-200" />
        <div className="h-8 w-48 bg-gray-200 rounded" />
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-white rounded-xl border border-gray-200" />
          ))}
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">
        {loadError}
      </div>
    );
  }

  if (!kb) return null;

  const write = canWrite(role);
  const archive = canArchive(role);

  return (
    <>
      {showEdit && (
        <EditKbModal
          kb={kb}
          onClose={() => setShowEdit(false)}
          onSave={(updated) => { setKb(updated); setShowEdit(false); }}
        />
      )}
      {showArchiveKb && (
        <ArchiveKbModal
          onClose={() => setShowArchiveKb(false)}
          onConfirm={handleArchiveKb}
          loading={archivingKb}
        />
      )}
      {showAddSource && (
        <AddSourceModal
          kbId={kb.id}
          onClose={() => setShowAddSource(false)}
          onCreated={(source) => {
            setSources((prev) => [source, ...prev]);
            setShowAddSource(false);
          }}
        />
      )}
      {sourceToArchive && (
        <ArchiveSourceModal
          source={sourceToArchive}
          onClose={() => setSourceToArchive(null)}
          onConfirm={handleArchiveSource}
          loading={archivingSource}
        />
      )}

      {/* KB Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
            <BookOpen className="w-6 h-6 text-indigo-500" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-lg font-bold text-gray-900">{kb.name}</h1>
              <KbStatusBadge status={kb.status} />
            </div>
            {kb.description ? (
              <p className="mt-1 text-sm text-gray-500">{kb.description}</p>
            ) : (
              <p className="mt-1 text-sm text-gray-300 italic">Sem descrição</p>
            )}
            <p className="mt-2 text-xs text-gray-400">
              Criada em {new Date(kb.created_at).toLocaleDateString("pt-BR")}
            </p>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 flex-shrink-0">
            {write && (
              <button
                type="button"
                onClick={() => setShowEdit(true)}
                className="px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Editar
              </button>
            )}
            {archive && (
              <button
                type="button"
                onClick={() => setShowArchiveKb(true)}
                className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors"
              >
                Arquivar
              </button>
            )}
          </div>
        </div>

        {archiveKbError && (
          <p className="mt-3 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {archiveKbError}
          </p>
        )}
      </div>

      {/* Sources section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Fontes</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {sources.length === 0
                ? "Nenhuma fonte adicionada ainda."
                : `${sources.length} fonte${sources.length !== 1 ? "s" : ""}`}
            </p>
          </div>
          {write && (
            <button
              type="button"
              onClick={() => setShowAddSource(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Adicionar Fonte
            </button>
          )}
        </div>

        {sources.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center border border-dashed border-gray-200 rounded-xl">
            <FileText className="w-8 h-8 text-gray-300 mb-3" />
            <p className="text-sm text-gray-500 mb-1">Nenhuma fonte adicionada ainda.</p>
            <p className="text-xs text-gray-400">
              Adicione textos, FAQs e procedimentos para enriquecer esta base.
            </p>
            {write && (
              <button
                type="button"
                onClick={() => setShowAddSource(true)}
                className="mt-4 flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50"
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
