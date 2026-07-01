"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { BookOpen, Calendar, Plus, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { KnowledgeBase, MemberRole, Plan, Usage } from "@/lib/api";
import { canCreateResource } from "@/lib/plan";
import { LimitReachedBanner } from "@/components/plan/UpgradePrompt";

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}

function KbStatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    active:   { label: "Ativa",     cls: "bg-nb-success/10 text-nb-success border-nb-success/20" },
    inactive: { label: "Inativa",   cls: "bg-nb-elevated   text-nb-muted   border-nb-border"     },
    archived: { label: "Arquivada", cls: "bg-nb-danger/10  text-nb-danger  border-nb-danger/20"  },
  };
  const s = map[status] ?? { label: status, cls: "bg-nb-elevated text-nb-muted border-nb-border" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${s.cls}`}>
      {s.label}
    </span>
  );
}

function KbCard({ kb }: { kb: KnowledgeBase }) {
  return (
    <div className="group bg-nb-panel rounded-2xl border border-nb-border hover:border-nb-border-strong transition-all duration-150 flex flex-col">
      <div className="p-5 flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center flex-shrink-0">
          <BookOpen className="w-5 h-5 text-nb-primary-strong" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-nb-text truncate">{kb.name}</h3>
            <KbStatusBadge status={kb.status} />
          </div>
          {kb.description ? (
            <p className="mt-1 text-xs text-nb-muted line-clamp-2">{kb.description}</p>
          ) : (
            <p className="mt-1 text-xs text-nb-muted/40 italic">Sem descrição</p>
          )}
        </div>
      </div>
      <div className="px-5 pb-4 mt-auto flex items-center justify-between border-t border-nb-border pt-3">
        <span className="flex items-center gap-1 text-xs text-nb-muted">
          <Calendar className="w-3 h-3" />
          {new Date(kb.created_at).toLocaleDateString("pt-BR")}
        </span>
        <Link
          href={`/dashboard/knowledge-bases/${kb.id}`}
          className="text-xs font-medium text-nb-primary hover:text-nb-primary-strong transition-colors"
        >
          Ver detalhes →
        </Link>
      </div>
    </div>
  );
}

function EmptyState({ canCreate }: { canCreate: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <div className="w-16 h-16 rounded-2xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center mb-4">
        <BookOpen className="w-8 h-8 text-nb-primary" />
      </div>
      <h3 className="text-base font-semibold text-nb-text mb-1">
        Nenhuma base de conhecimento ainda
      </h3>
      <p className="text-sm text-nb-muted max-w-xs mb-6">
        Crie uma base e adicione textos, FAQs e procedimentos para que seus agentes respondam com mais precisão.
      </p>
      {canCreate && (
        <p className="text-sm text-nb-primary font-medium">
          ↑ Clique em &ldquo;Nova Base&rdquo; para começar
        </p>
      )}
    </div>
  );
}

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
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    function onKey(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true);
    setError(null);
    try {
      const kb = await api.knowledgeBases.create({
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

  const inputCls = "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-nb-surface rounded-[18px] border border-nb-border shadow-2xl w-full max-w-md mx-4">
        <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
          <h2 className="text-base font-semibold text-nb-text">Nova base de conhecimento</h2>
          <button type="button" onClick={onClose} className="text-nb-muted hover:text-nb-secondary transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">
              Nome <span className="text-nb-danger">*</span>
            </label>
            <input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={200}
              placeholder="Ex: FAQ de Atendimento"
              className={inputCls}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-nb-secondary mb-1.5">
              Descrição <span className="text-nb-muted">(opcional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Descreva o conteúdo desta base..."
              className={inputCls + " resize-none"}
            />
          </div>

          {error && (
            <p className="text-xs text-nb-danger bg-nb-danger/10 border border-nb-danger/20 rounded-xl px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 text-sm font-medium text-nb-secondary border border-nb-border rounded-xl hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-4 py-2 text-sm font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {saving ? "Criando..." : "Criar base"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function KnowledgeBasesPage() {
  const [kbs,      setKbs]      = useState<KnowledgeBase[]>([]);
  const [role,     setRole]     = useState<MemberRole | null>(null);
  const [plan,     setPlan]     = useState<Plan | null>(null);
  const [usage,    setUsage]    = useState<Usage | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    Promise.all([
      api.knowledgeBases.list(),
      api.me(),
      api.plans.current().catch(() => null),
      api.plans.usage().catch(() => null),
    ])
      .then(([kbList, me, sub, usageData]) => {
        setKbs(kbList);
        setRole(me.role);
        setPlan(sub?.plan ?? null);
        setUsage(usageData);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Erro ao carregar bases de conhecimento."))
      .finally(() => setLoading(false));
  }, []);

  function handleCreated(kb: KnowledgeBase) {
    setKbs((prev) => [kb, ...prev]);
    setShowCreate(false);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-56 bg-nb-panel rounded-xl animate-pulse" />
          <div className="h-9 w-28 bg-nb-panel rounded-xl animate-pulse" />
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-36 bg-nb-panel rounded-2xl border border-nb-border animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="p-4 bg-nb-danger/10 border border-nb-danger/20 rounded-xl text-sm text-nb-danger">
        {loadError}
      </div>
    );
  }

  const kbsUsed  = usage?.knowledge_bases_count ?? kbs.length;
  const kbsLimit = plan?.knowledge_bases_limit ?? 0;
  const atLimit  = kbsLimit > 0 && !canCreateResource(kbsUsed, kbsLimit);

  return (
    <>
      {showCreate && (
        <CreateKbModal onClose={() => setShowCreate(false)} onCreate={handleCreated} />
      )}

      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-xl font-bold text-nb-text">Bases de Conhecimento</h1>
          <p className="text-sm text-nb-muted mt-0.5">
            Organize informações que seus agentes poderão usar para responder com mais precisão.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {plan && kbsLimit > 0 && (
            <span className={`text-sm font-medium ${atLimit ? "text-nb-danger" : "text-nb-muted"}`}>
              {kbsUsed} / {kbsLimit} {kbsLimit !== 1 ? "bases" : "base"}
            </span>
          )}
          {canWrite(role) && (
            atLimit ? (
              <span
                title="Limite de bases de conhecimento atingido no seu plano."
                className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-nb-elevated border border-nb-border text-nb-muted text-sm font-medium rounded-xl cursor-not-allowed opacity-60"
              >
                <Plus className="w-4 h-4" />
                Nova Base
              </span>
            ) : (
              <button
                type="button"
                onClick={() => setShowCreate(true)}
                className="flex-shrink-0 flex items-center gap-2 px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
              >
                <Plus className="w-4 h-4" />
                Nova Base
              </button>
            )
          )}
        </div>
      </div>

      {atLimit && (
        <LimitReachedBanner resource="bases de conhecimento" className="mb-6" />
      )}

      {kbs.length === 0 ? (
        <EmptyState canCreate={canWrite(role) && !atLimit} />
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
