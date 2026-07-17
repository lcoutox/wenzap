"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AiCatalog } from "@/lib/api";

export default function AdvancedCreatePage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [aiModelId, setAiModelId] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [catalog, setCatalog] = useState<AiCatalog | null>(null);
  const [catalogLoad, setCatalogLoad] = useState(false);
  const catalogFetched = useRef(false);

  useEffect(() => {
    if (!catalogFetched.current) {
      catalogFetched.current = true;
      setCatalogLoad(true);
      api.aiModels.list().then(setCatalog).catch(() => {}).finally(() => setCatalogLoad(false));
    }
  }, []);

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!name.trim()) e.name = "Informe o nome do agente.";
    if (!aiModelId) e.aiModelId = "Selecione um modelo de IA.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleCreate() {
    if (!validate()) return;

    setGlobalError(null);
    setSaving(true);

    try {
      const agent = await api.agents.create({
        name: name.trim(),
        description: description.trim() || undefined,
        ai_model_id: aiModelId!,
        temperature: 0.7,
        instructions_mode: "advanced",
      });

      router.push(`/dashboard/agents/${agent.id}?tab=settings&configTab=instrucoes`);
    } catch (e) {
      setGlobalError(e instanceof Error ? e.message : "Erro ao criar agente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl space-y-6 pb-24">
      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <Link href="/dashboard/agents/new" className="hover:text-nb-secondary transition-colors">
          Novo agente
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium">Avançado</span>
      </nav>

      <div className="space-y-3">
        <h1 className="text-2xl font-semibold text-nb-text">Criar agente avançado</h1>
        <p className="text-sm text-nb-muted">
          Configure o essencial agora. Você poderá customizar as instruções em detalhes depois.
        </p>
      </div>

      <div className="bg-nb-panel border border-nb-border rounded-2xl p-6 space-y-6">
        {/* Name */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-nb-text">Nome do agente</label>
          <input
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setErrors((prev) => ({ ...prev, name: "" }));
            }}
            placeholder="Ex: Suporte Técnico, Vendedor de Premium..."
            className="w-full px-4 py-2.5 bg-nb-elevated border border-nb-border rounded-lg text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary transition-colors"
          />
          {errors.name && <p className="text-xs text-nb-danger">{errors.name}</p>}
        </div>

        {/* Description */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-nb-text">Descrição (opcional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Descreva o propósito e escopo deste agente..."
            rows={3}
            className="w-full px-4 py-2.5 bg-nb-elevated border border-nb-border rounded-lg text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary transition-colors resize-none"
          />
        </div>

        {/* AI Model */}
        <div className="space-y-2">
          <label className="text-sm font-semibold text-nb-text">Modelo de IA</label>
          {catalogLoad ? (
            <div className="flex items-center gap-2 text-sm text-nb-muted py-2.5">
              <Loader2 className="w-4 h-4 animate-spin" />
              Carregando modelos...
            </div>
          ) : catalog ? (
            <select
              value={aiModelId || ""}
              onChange={(e) => {
                setAiModelId(e.target.value || null);
                setErrors((prev) => ({ ...prev, aiModelId: "" }));
              }}
              className="w-full px-4 py-2.5 bg-nb-elevated border border-nb-border rounded-lg text-nb-text focus:outline-none focus:border-nb-primary transition-colors cursor-pointer"
            >
              <option value="">Selecione um modelo...</option>
              {catalog.providers.map((provider) =>
                provider.models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {provider.name} — {model.display_name}
                  </option>
                ))
              )}
            </select>
          ) : (
            <p className="text-sm text-nb-danger">Erro ao carregar modelos</p>
          )}
          {errors.aiModelId && <p className="text-xs text-nb-danger">{errors.aiModelId}</p>}
        </div>
      </div>

      {globalError && (
        <p className="text-sm text-nb-danger px-1">{globalError}</p>
      )}

      <div className="flex items-center justify-between">
        <Link
          href="/dashboard/agents/new"
          className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
        >
          Voltar
        </Link>

        <button
          type="button"
          onClick={handleCreate}
          disabled={saving}
          className="flex items-center gap-2 px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-50 transition-colors"
        >
          {saving && <Loader2 className="w-4 h-4 animate-spin" />}
          {saving ? "Criando..." : "Criar agente"}
        </button>
      </div>
    </div>
  );
}
