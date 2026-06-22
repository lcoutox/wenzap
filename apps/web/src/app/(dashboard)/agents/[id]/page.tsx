"use client";

import { useAuth } from "@clerk/nextjs";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Agent, AgentStatus, MemberRole } from "@/lib/api";

const STATUS_LABELS: Record<AgentStatus, string> = {
  draft: "Rascunho",
  active: "Ativo",
  inactive: "Inativo",
  archived: "Arquivado",
};

const STATUS_COLORS: Record<AgentStatus, string> = {
  draft: "bg-gray-100 text-gray-600",
  active: "bg-green-50 text-green-700",
  inactive: "bg-yellow-50 text-yellow-700",
  archived: "bg-red-50 text-red-500",
};

function canWrite(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

function canArchive(role: MemberRole | null): boolean {
  return role === "owner" || role === "admin";
}

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  const [agent, setAgent] = useState<Agent | null>(null);
  const [role, setRole] = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [persona, setPersona] = useState("");
  const [modelProvider, setModelProvider] = useState("");
  const [modelName, setModelName] = useState("");
  const [temperature, setTemperature] = useState("");

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
        // Populate form
        setName(agentData.name);
        setDescription(agentData.description ?? "");
        setSystemPrompt(agentData.system_prompt ?? "");
        setPersona(agentData.persona ?? "");
        setModelProvider(agentData.model_provider);
        setModelName(agentData.model_name);
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

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!agent) return;
    setFormError(null);

    const tempNum = parseFloat(temperature);
    if (isNaN(tempNum) || tempNum < 0 || tempNum > 1) {
      setFormError("Temperatura deve ser entre 0.0 e 1.0.");
      return;
    }

    setSaving(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sessão expirada.");
      const updated = await api.agents.update(token, id, {
        name: name.trim(),
        description: description.trim() || undefined,
        system_prompt: systemPrompt.trim() || undefined,
        persona: persona.trim() || undefined,
        model_provider: modelProvider.trim(),
        model_name: modelName.trim(),
        temperature: tempNum,
      });
      setAgent(updated);
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(newStatus: AgentStatus) {
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

  if (loading) {
    return <p className="text-sm text-gray-400">Carregando agente...</p>;
  }

  if (loadError) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
        {loadError}
      </div>
    );
  }

  if (!agent) return null;

  const isArchived = agent.status === "archived";
  const write = canWrite(role);
  const archive = canArchive(role);

  return (
    <div className="max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{agent.name}</h1>
          <span className={`inline-flex items-center mt-1 px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[agent.status]}`}>
            {STATUS_LABELS[agent.status]}
          </span>
        </div>

        {/* Status action buttons */}
        {!isArchived && (
          <div className="flex gap-2">
            {agent.status === "draft" && write && (
              <ActionButton onClick={() => handleStatusChange("active")} variant="primary">
                Ativar
              </ActionButton>
            )}
            {agent.status === "active" && write && (
              <ActionButton onClick={() => handleStatusChange("inactive")} variant="secondary">
                Desativar
              </ActionButton>
            )}
            {agent.status === "inactive" && write && (
              <ActionButton onClick={() => handleStatusChange("active")} variant="primary">
                Ativar
              </ActionButton>
            )}
            {archive && (
              <ActionButton onClick={handleArchive} variant="danger">
                Arquivar
              </ActionButton>
            )}
          </div>
        )}
      </div>

      {actionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-600">
          {actionError}
        </div>
      )}

      <form onSubmit={handleSave} className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
        <Field label="Nome *">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
            disabled={isArchived || !write}
            className={inputClass(isArchived || !write)}
          />
        </Field>

        <Field label="Descrição">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            disabled={isArchived || !write}
            className={inputClass(isArchived || !write)}
          />
        </Field>

        <Field label="System prompt">
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={5}
            maxLength={8000}
            disabled={isArchived || !write}
            placeholder={isArchived ? "" : "Necessário para ativar o agente."}
            className={inputClass(isArchived || !write)}
          />
        </Field>

        <Field label="Persona / Tom">
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            rows={2}
            maxLength={1000}
            disabled={isArchived || !write}
            className={inputClass(isArchived || !write)}
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Provider">
            <input
              type="text"
              value={modelProvider}
              onChange={(e) => setModelProvider(e.target.value)}
              maxLength={50}
              disabled={isArchived || !write}
              className={inputClass(isArchived || !write)}
            />
          </Field>
          <Field label="Modelo">
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              maxLength={100}
              disabled={isArchived || !write}
              className={inputClass(isArchived || !write)}
            />
          </Field>
        </div>

        <Field label="Temperatura (0.0 – 1.0)">
          <input
            type="number"
            value={temperature}
            onChange={(e) => setTemperature(e.target.value)}
            step="0.1"
            min="0"
            max="1"
            disabled={isArchived || !write}
            className={inputClass(isArchived || !write)}
          />
        </Field>

        {formError && <p className="text-sm text-red-500">{formError}</p>}

        {write && !isArchived && (
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
            <button
              type="button"
              onClick={() => router.push("/dashboard/agents")}
              className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              Voltar
            </button>
          </div>
        )}

        {isArchived && (
          <p className="text-sm text-gray-400 pt-2">Este agente está arquivado e não pode ser editado.</p>
        )}
      </form>
    </div>
  );
}

function inputClass(disabled: boolean) {
  return `w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
    disabled ? "bg-gray-50 text-gray-400 cursor-not-allowed" : ""
  }`;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
    </div>
  );
}

function ActionButton({
  onClick,
  variant,
  children,
}: {
  onClick: () => void;
  variant: "primary" | "secondary" | "danger";
  children: React.ReactNode;
}) {
  const colors = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "bg-gray-100 text-gray-700 hover:bg-gray-200",
    danger: "bg-red-50 text-red-600 hover:bg-red-100",
  };
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${colors[variant]}`}
    >
      {children}
    </button>
  );
}
