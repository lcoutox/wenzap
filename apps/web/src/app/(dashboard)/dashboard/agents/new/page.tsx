"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { ChevronRight, Bot } from "lucide-react";
import { api } from "@/lib/api";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { ModelCardSelector } from "@/components/agents/ModelCardSelector";

const baseInput =
  "w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors";

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-nb-secondary">{label}</label>
      {children}
      {hint && <p className="text-xs text-nb-muted">{hint}</p>}
    </div>
  );
}

export default function NewAgentPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  const [name,         setName]         = useState("");
  const [description,  setDescription]  = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [persona,      setPersona]      = useState("");
  const [aiModelId,    setAiModelId]    = useState<string | null>(null);
  const [temperature,  setTemperature]  = useState("0.7");
  const [error,        setError]        = useState<string | null>(null);
  const [saving,       setSaving]       = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!aiModelId) { setError("Selecione um modelo de IA."); return; }

    const tempNum = parseFloat(temperature);
    if (isNaN(tempNum) || tempNum < 0 || tempNum > 1) {
      setError("Temperatura deve ser entre 0.0 e 1.0.");
      return;
    }

    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const agent = await api.agents.create(token, {
        name: name.trim(),
        description: description.trim() || undefined,
        system_prompt: systemPrompt.trim() || undefined,
        persona: persona.trim() || undefined,
        ai_model_id: aiModelId,
        temperature: tempNum,
      });
      router.push(`/dashboard/agents/${agent.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao criar agente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl space-y-6">

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium">Novo agente</span>
      </nav>

      {/* Page header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-nb-primary-bg border border-nb-primary/20 flex items-center justify-center">
          <Bot className="w-5 h-5 text-nb-primary-strong" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-nb-text">Novo agente</h1>
          <p className="text-sm text-nb-muted">Configure a identidade, o prompt e o modelo do agente.</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">

        <AgentFormSection title="Informações básicas" description="Nome e descrição exibidos na plataforma.">
          <Field label="Nome *">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
              placeholder="Ex: Agente de Suporte"
              className={baseInput}
            />
          </Field>
          <Field label="Descrição" hint="Visível na listagem de agentes.">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Descreva o propósito deste agente"
              className={baseInput}
            />
          </Field>
        </AgentFormSection>

        <AgentFormSection title="Prompt inicial" description="Instrução base e persona do agente.">
          <Field label="System prompt" hint={`${systemPrompt.length} / 8000 caracteres — obrigatório para ativar o agente.`}>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={7}
              maxLength={8000}
              placeholder="Você é um agente de suporte da empresa Acme. Responda de forma..."
              className={baseInput}
            />
          </Field>
          <Field label="Persona / Tom" hint="Máximo de 1000 caracteres.">
            <textarea
              value={persona}
              onChange={(e) => setPersona(e.target.value)}
              rows={2}
              maxLength={1000}
              placeholder="Comunicativo, empático, direto ao ponto"
              className={baseInput}
            />
          </Field>
          <Field label="Temperatura" hint="Controla a criatividade. 0 = mais preciso, 1 = mais criativo.">
            <div className="flex items-center gap-4">
              <input
                type="range"
                value={temperature}
                onChange={(e) => setTemperature(e.target.value)}
                step="0.1"
                min="0"
                max="1"
                className="flex-1 accent-nb-primary"
              />
              <span className="w-10 text-sm font-mono text-center text-nb-secondary bg-nb-elevated border border-nb-border rounded-lg px-2 py-1">
                {parseFloat(temperature).toFixed(1)}
              </span>
            </div>
          </Field>
        </AgentFormSection>

        <AgentFormSection title="Modelo do agente" description="Escolha o modelo de IA que alimentará este agente.">
          <ModelCardSelector
            aiModelId={aiModelId}
            onChange={(id) => setAiModelId(id)}
          />
        </AgentFormSection>

        {error && (
          <p className="text-sm text-nb-danger">{error}</p>
        )}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={saving || !aiModelId}
            className="px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
          >
            {saving ? "Criando..." : "Criar agente"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard/agents")}
            className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}
