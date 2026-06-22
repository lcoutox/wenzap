"use client";

import { useAuth } from "@clerk/nextjs";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Bot } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Agent, AgentStatus, MemberRole } from "@/lib/api";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { AgentFormSection } from "@/components/agents/AgentFormSection";
import { ModelCardSelector } from "@/components/agents/ModelCardSelector";

// ── Permissions ───────────────────────────────────────────────────────────────

function canWrite(role: MemberRole | null) {
  return role === "owner" || role === "admin" || role === "member";
}
function canArchive(role: MemberRole | null) {
  return role === "owner" || role === "admin";
}

// ── Shared field components ───────────────────────────────────────────────────

const baseInput =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent";
const disabledInput =
  "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-400 bg-gray-50 cursor-not-allowed";

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
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

// ── Tab nav ───────────────────────────────────────────────────────────────────

type Tab = "prompt" | "model" | "advanced";
const TABS: { id: Tab; label: string }[] = [
  { id: "prompt",   label: "Prompt" },
  { id: "model",    label: "Modelo" },
  { id: "advanced", label: "Avançado" },
];

// ── Action button ─────────────────────────────────────────────────────────────

function ActionBtn({
  onClick,
  variant,
  children,
}: {
  onClick: () => void;
  variant: "primary" | "secondary" | "danger";
  children: React.ReactNode;
}) {
  const cls = {
    primary:   "bg-indigo-600 text-white hover:bg-indigo-700",
    secondary: "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50",
    danger:    "bg-white text-red-600 border border-red-200 hover:bg-red-50",
  }[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${cls}`}
    >
      {children}
    </button>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  // Remote state
  const [agent, setAgent] = useState<Agent | null>(null);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Form state (mirrors agent fields)
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [persona, setPersona] = useState("");
  const [aiModelId, setAiModelId] = useState<string | null>(null);
  const [temperature, setTemperature] = useState("0.7");

  // UI state
  const [activeTab, setActiveTab] = useState<Tab>("prompt");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  // ── Load ────────────────────────────────────────────────────────────────────
  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [agentData, me] = await Promise.all([
          api.agents.get(token, id),
          api.me(token),
        ]);
        setAgent(agentData);
        setRole(me.role);
        setName(agentData.name);
        setDescription(agentData.description ?? "");
        setSystemPrompt(agentData.system_prompt ?? "");
        setPersona(agentData.persona ?? "");
        setAiModelId(agentData.ai_model_id);
        setTemperature(String(agentData.temperature));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          router.push("/dashboard/agents");
        } else {
          setLoadError(e instanceof Error ? e.message : "Erro ao carregar agente.");
        }
      } finally {
        setLoading(false);
      }
    });
  }, [id, getToken, router]);

  // ── Save ────────────────────────────────────────────────────────────────────
  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!agent) return;
    setSaveError(null);
    setSaveSuccess(false);

    if (!aiModelId) { setSaveError("Selecione um modelo de IA."); return; }

    const tempNum = parseFloat(temperature);
    if (isNaN(tempNum) || tempNum < 0 || tempNum > 1) {
      setSaveError("Temperatura deve ser entre 0.0 e 1.0.");
      return;
    }

    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.agents.update(token, id, {
        name: name.trim(),
        description: description.trim() || null,
        system_prompt: systemPrompt.trim() || null,
        persona: persona.trim() || null,
        ai_model_id: aiModelId,
        temperature: tempNum,
      });
      setAgent(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  // ── Status actions ───────────────────────────────────────────────────────────
  async function changeStatus(newStatus: AgentStatus) {
    if (!agent) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.agents.updateStatus(token, id, newStatus);
      setAgent(updated);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Erro ao mudar status.");
    }
  }

  async function handleArchive() {
    if (!agent) return;
    setActionError(null);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.agents.archive(token, id);
      setAgent(updated);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Erro ao arquivar.");
    }
  }

  // ── Loading / error states ───────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-4 animate-pulse max-w-4xl">
        <div className="h-6 w-48 bg-gray-200 rounded" />
        <div className="h-10 w-72 bg-gray-200 rounded" />
        <div className="h-64 bg-gray-100 rounded-xl" />
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

  if (!agent) return null;

  const isArchived = agent.status === "archived";
  const write = canWrite(role);
  const archive = canArchive(role);
  const readonly = isArchived || !write;

  // ── Render ──────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-4xl space-y-6">

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1 text-sm text-gray-400">
        <Link href="/dashboard/agents" className="hover:text-gray-700 transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5" />
        <span className="text-gray-700 font-medium truncate max-w-xs">{agent.name}</span>
      </nav>

      {/* Agent header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-xl bg-indigo-50 border border-indigo-100 flex items-center justify-center flex-shrink-0">
            <Bot className="w-5 h-5 text-indigo-500" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900 truncate">{agent.name}</h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <AgentStatusBadge status={agent.status} />
              <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-md font-mono">
                {agent.model_name}
              </span>
            </div>
          </div>
        </div>

        {/* Status action buttons */}
        {!isArchived && (
          <div className="flex items-center gap-2 flex-wrap">
            {agent.status === "draft" && write && (
              <ActionBtn variant="primary" onClick={() => changeStatus("active")}>
                Ativar agente
              </ActionBtn>
            )}
            {agent.status === "active" && write && (
              <ActionBtn variant="secondary" onClick={() => changeStatus("inactive")}>
                Desativar
              </ActionBtn>
            )}
            {agent.status === "inactive" && write && (
              <ActionBtn variant="primary" onClick={() => changeStatus("active")}>
                Ativar
              </ActionBtn>
            )}
            {archive && (
              <ActionBtn variant="danger" onClick={handleArchive}>
                Arquivar
              </ActionBtn>
            )}
          </div>
        )}
      </div>

      {/* Action error */}
      {actionError && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
          {actionError}
        </div>
      )}

      {isArchived && (
        <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
          Este agente está arquivado e não pode ser editado.
        </div>
      )}

      {/* Tab nav */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-1 -mb-px">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? "border-indigo-600 text-indigo-600"
                  : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <form onSubmit={handleSave} className="space-y-5">

        {/* ── Prompt tab ── */}
        {activeTab === "prompt" && (
          <>
            <AgentFormSection
              title="Identidade"
              description="Nome e descrição exibidos na plataforma."
            >
              <Field label="Nome *">
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={100}
                  disabled={readonly}
                  placeholder="Ex: Agente de Suporte"
                  className={readonly ? disabledInput : baseInput}
                />
              </Field>
              <Field label="Descrição" hint="Visível na listagem de agentes.">
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={2}
                  disabled={readonly}
                  placeholder="Descreva o propósito deste agente"
                  className={readonly ? disabledInput : baseInput}
                />
              </Field>
            </AgentFormSection>

            <AgentFormSection
              title="System Prompt"
              description="Instrução base que define o comportamento do agente. Obrigatório para ativar."
            >
              <Field
                label="Prompt"
                hint={`${systemPrompt.length} / 8000 caracteres`}
              >
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  rows={8}
                  maxLength={8000}
                  disabled={readonly}
                  placeholder={readonly ? "" : "Você é um agente de suporte da empresa Acme..."}
                  className={readonly ? disabledInput : baseInput}
                />
              </Field>
            </AgentFormSection>

            <AgentFormSection
              title="Persona e Tom"
              description="Define a personalidade e o estilo de comunicação do agente."
            >
              <Field label="Persona" hint="Máximo de 1000 caracteres.">
                <textarea
                  value={persona}
                  onChange={(e) => setPersona(e.target.value)}
                  rows={3}
                  maxLength={1000}
                  disabled={readonly}
                  placeholder={readonly ? "" : "Comunicativo, empático, direto ao ponto"}
                  className={readonly ? disabledInput : baseInput}
                />
              </Field>
            </AgentFormSection>
          </>
        )}

        {/* ── Model tab ── */}
        {activeTab === "model" && (
          <AgentFormSection
            title="Modelo de IA"
            description="Escolha o modelo que alimenta este agente."
          >
            <ModelCardSelector
              aiModelId={aiModelId}
              disabled={readonly}
              onChange={(id) => setAiModelId(id)}
            />
          </AgentFormSection>
        )}

        {/* ── Advanced tab ── */}
        {activeTab === "advanced" && (
          <AgentFormSection
            title="Configurações avançadas"
            description="Ajustes de geração de texto e comportamento do modelo."
          >
            <Field
              label="Temperatura"
              hint="Controla a criatividade das respostas. 0 = mais preciso, 1 = mais criativo."
            >
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  value={temperature}
                  onChange={(e) => setTemperature(e.target.value)}
                  step="0.1"
                  min="0"
                  max="1"
                  disabled={readonly}
                  className="flex-1 accent-indigo-600"
                />
                <span className="w-10 text-sm font-mono text-center text-gray-700 bg-gray-100 rounded px-2 py-1">
                  {parseFloat(temperature).toFixed(1)}
                </span>
              </div>
            </Field>
          </AgentFormSection>
        )}

        {/* ── Save bar ── */}
        {write && !isArchived && activeTab !== "advanced" && (
          <div className="flex items-center gap-3">
            {saveError && (
              <p className="text-sm text-red-500 flex-1">{saveError}</p>
            )}
            {saveSuccess && (
              <p className="text-sm text-green-600 flex-1">Salvo com sucesso.</p>
            )}
            <button
              type="submit"
              disabled={saving}
              className="ml-auto px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar alterações"}
            </button>
          </div>
        )}

        {/* Save bar also on Advanced tab */}
        {write && !isArchived && activeTab === "advanced" && (
          <div className="flex items-center justify-end gap-3">
            {saveError && <p className="text-sm text-red-500">{saveError}</p>}
            {saveSuccess && <p className="text-sm text-green-600">Salvo com sucesso.</p>}
            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar alterações"}
            </button>
          </div>
        )}
      </form>
    </div>
  );
}
