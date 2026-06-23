"use client";

import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Calendar, Plus, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeBase, MemberRole } from "@/lib/api";

// ── RBAC ─────────────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

// ── Status badge ──────────────────────────────────────────────────────────────

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",    cls: "bg-green-50 text-green-700 border-green-200" },
    inactive: { label: "Inativa",  cls: "bg-gray-50 text-gray-500 border-gray-200" },
    archived: { label: "Arquivada", cls: "bg-red-50 text-red-600 border-red-200" },
  };
  const s = map[status] ?? { label: status, cls: "bg-gray-50 text-gray-500 border-gray-200" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── KB Card ───────────────────────────────────────────────────────────────────

function KbCard({ kb }: { kb: KnowledgeBase }) {
  return (
    <div className="group bg-white rounded-xl border border-gray-200 hover:border-indigo-300 hover:shadow-md transition-all duration-150 flex flex-col">
      <div className="p-5 flex items-start gap-4">
        <div className="w-10 h-10 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-5 h-5 text-indigo-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-gray-900 truncate">{kb.name}</h3>
            <KbStatusBadge status={kb.status} />
          </div>
          {kb.description ? (
            <p className="mt-1 text-xs text-gray-500 line-clamp-2">{kb.description}</p>
          ) : (
            <p className="mt-1 text-xs text-gray-300 italic">Sem descrição</p>
          )}
        </div>
      </div>

      <div className="px-5 pb-4 mt-auto flex items-center justify-between border-t border-gray-50 pt-3">
        <span className="flex items-center gap-1 text-xs text-gray-400">
          <Calendar className="w-3 h-3" />
          {new Date(kb.created_at).toLocaleDateString("pt-BR")}
        </span>
        <Link
          href={`/dashboard/knowledge-bases/${kb.id}`}
          className="text-xs font-medium text-indigo-600 hover:text-indigo-800 transition-colors"
        >
          Ver detalhes →
        </Link>
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ canCreate }: { canCreate: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-indigo-50 border border-indigo-100 flex items-center justify-center mb-4">
        <BookOpen className="w-8 h-8 text-indigo-400" />
      </div>
      <h3 className="text-base font-semibold text-gray-900 mb-1">
        Nenhuma base de conhecimento ainda
      </h3>
      <p className="text-sm text-gray-500 max-w-xs mb-6">
        Crie uma base e adicione textos, FAQs e procedimentos para que seus agentes respondam com mais precisão.
      </p>
      {canCreate && (
        <div className="text-sm text-indigo-600 font-medium">
          ↑ Clique em &ldquo;Nova Base&rdquo; para começar
        </div>
      )}
    </div>
  );
}

// ── Modal Nova Base ───────────────────────────────────────────────────────────

function CreateKbModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (kb: KnowledgeBase) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { getToken } = useAuth();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true);
    setError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const kb = await api.knowledgeBases.create(token, {
        name: name.trim(),
        description: description.trim() || undefined,
      });
      onCreate(kb);
    } catch (e) {
      if (e instanceof ApiError && e.status === 402) {
        setError("Limite de bases de conhecimento atingido no seu plano.");
      } else {
        setError(e instanceof Error ? e.message : "Erro ao criar base.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-900">Nova base de conhecimento</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
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
              placeholder="Ex: FAQ de Atendimento"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Descrição <span className="text-gray-400">(opcional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Descreva o conteúdo desta base..."
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
              {saving ? "Criando..." : "Criar base"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function KnowledgeBasesPage() {
  const { getToken } = useAuth();
  const [kbs, setKbs] = useState<KnowledgeBase[]>([]);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [kbList, me] = await Promise.all([
          api.knowledgeBases.list(token),
          api.me(token),
        ]);
        setKbs(kbList);
        setRole(me.role);
      } catch (e) {
        setLoadError(e instanceof Error ? e.message : "Erro ao carregar bases de conhecimento.");
      } finally {
        setLoading(false);
      }
    });
  }, [getToken]);

  function handleCreated(kb: KnowledgeBase) {
    setKbs((prev) => [kb, ...prev]);
    setShowCreate(false);
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="flex items-center justify-between">
          <div className="h-8 w-56 bg-gray-200 rounded" />
          <div className="h-9 w-28 bg-gray-200 rounded-lg" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-36 bg-white rounded-xl border border-gray-200" />
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

  return (
    <>
      {showCreate && (
        <CreateKbModal
          onClose={() => setShowCreate(false)}
          onCreate={handleCreated}
        />
      )}

      {/* Page header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Bases de Conhecimento</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Organize informações que seus agentes poderão usar para responder com mais precisão.
          </p>
        </div>
        {canWrite(role) && (
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Nova Base
          </button>
        )}
      </div>

      {kbs.length === 0 ? (
        <EmptyState canCreate={canWrite(role)} />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {kbs.map((kb) => (
            <KbCard key={kb.id} kb={kb} />
          ))}
        </div>
      )}
    </>
  );
}
