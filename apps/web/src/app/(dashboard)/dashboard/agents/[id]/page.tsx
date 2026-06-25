"use client";

import { useAuth } from "@clerk/nextjs";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Agent, AgentStatus, AiCatalog, AiModel, MemberRole } from "@/lib/api";

import { AgentHeader } from "@/components/agents/workspace/AgentHeader";
import { AgentWorkspaceTabs } from "@/components/agents/workspace/AgentWorkspaceTabs";
import type { WorkspaceTab } from "@/components/agents/workspace/AgentWorkspaceTabs";
import { ConfigTabs } from "@/components/agents/workspace/ConfigTabs";
import type { ConfigTab } from "@/components/agents/workspace/ConfigTabs";

import { AgentChat }           from "@/components/agents/workspace/tabs/AgentChat";
import { ImplantarTab } from "@/components/agents/workspace/tabs/ImplantarTab";
import { ConfigGeral }          from "@/components/agents/workspace/tabs/ConfigGeral";
import { ConfigPrompt }         from "@/components/agents/workspace/tabs/ConfigPrompt";
import { ConfigModelo }         from "@/components/agents/workspace/tabs/ConfigModelo";
import { ConfigAvancado }       from "@/components/agents/workspace/tabs/ConfigAvancado";
import { ConfigFerramentas }    from "@/components/agents/workspace/tabs/ConfigFerramentas";
import { ConfigSeguranca }      from "@/components/agents/workspace/tabs/ConfigSeguranca";
import { ConfigWebhooks }       from "@/components/agents/workspace/tabs/ConfigWebhooks";
import { ConfigConhecimento }   from "@/components/agents/workspace/tabs/ConfigConhecimento";

// ── Helpers ───────────────────────────────────────────────────────────────────

function findActiveModel(catalog: AiCatalog | null, aiModelId: string | null): AiModel | null {
  if (!catalog || !aiModelId) return null;
  for (const provider of catalog.providers) {
    const m = provider.models.find((m) => m.id === aiModelId);
    if (m) return m;
  }
  return null;
}

// Phase 3: models executable via Anthropic SDK
const EXECUTABLE_MODEL_NAMES = new Set([
  "claude-haiku-4-5",
  "claude-sonnet-4-6",
  "claude-opus-4-8",
]);

function isModelExecutable(catalog: AiCatalog | null, activeModel: AiModel | null): boolean {
  if (!catalog || !activeModel) return false;
  for (const provider of catalog.providers) {
    const found = provider.models.find((m) => m.id === activeModel.id);
    if (found) {
      return (
        (provider.code === "anthropic" || provider.code === "nexbrain") &&
        EXECUTABLE_MODEL_NAMES.has(activeModel.model_name)
      );
    }
  }
  return false;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const { getToken } = useAuth();
  const router = useRouter();

  // Remote state
  const [agent,   setAgent]   = useState<Agent | null>(null);
  const [catalog, setCatalog] = useState<AiCatalog | null>(null);
  const [role,    setRole]    = useState<MemberRole | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Form fields
  const [name,         setName]         = useState("");
  const [description,  setDescription]  = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [persona,      setPersona]      = useState("");
  const [aiModelId,    setAiModelId]    = useState<string | null>(null);
  const [temperature,  setTemperature]  = useState("0.7");

  // UI state
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("settings");
  const [configTab,    setConfigTab]    = useState<ConfigTab>("geral");
  const [saving,       setSaving]       = useState(false);
  const [saveError,    setSaveError]    = useState<string | null>(null);
  const [saveSuccess,  setSaveSuccess]  = useState(false);
  const [actionError,  setActionError]  = useState<string | null>(null);

  // ── Load ─────────────────────────────────────────────────────────────────────
  useEffect(() => {
    getToken().then(async (token) => {
      if (!token) return;
      try {
        const [agentData, me, catalogData] = await Promise.all([
          api.agents.get(token, id),
          api.me(token),
          api.aiModels.list(token),
        ]);
        setAgent(agentData);
        setRole(me.role);
        setCatalog(catalogData);
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

  // ── Save ──────────────────────────────────────────────────────────────────────
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

  // ── Status actions ────────────────────────────────────────────────────────────
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

  // ── Loading / error states ────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="h-32 bg-nb-panel rounded-2xl border border-nb-border" />
        <div className="h-10 w-80 bg-nb-panel rounded-xl" />
        <div className="h-96 bg-nb-panel rounded-2xl border border-nb-border" />
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

  if (!agent) return null;

  const activeModel     = findActiveModel(catalog, aiModelId);
  const modelExecutable = isModelExecutable(catalog, activeModel);
  const isArchived      = agent.status === "archived";
  const canWrite    = role === "owner" || role === "admin" || role === "member";
  const readonly    = isArchived || !canWrite;

  // Config tabs that have real save functionality
  const isSaveable = ["geral", "prompt", "modelo", "avancado"].includes(configTab);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-0 -m-6">
      {/* Sticky header */}
      <AgentHeader
        agent={agent}
        activeModel={activeModel}
        role={role}
        actionError={actionError}
        onChangeStatus={changeStatus}
        onArchive={handleArchive}
      />

      {/* Main workspace tabs */}
      <AgentWorkspaceTabs active={workspaceTab} onChange={setWorkspaceTab} />

      {/* Tab content */}
      <div className="p-6 flex-1">

        {/* ── Chat ── */}
        {workspaceTab === "chat" && (
          <AgentChat
            agent={agent}
            activeModel={activeModel}
            modelExecutable={modelExecutable}
            role={role}
            getToken={getToken}
          />
        )}

        {/* ── Implantar ── */}
        {workspaceTab === "deploy" && (
          <ImplantarTab agentId={id} role={role} getToken={getToken} />
        )}

        {/* ── Conhecimento ── */}
        {workspaceTab === "knowledge" && (
          <div className="max-w-3xl">
            <ConfigConhecimento agentId={id} role={role} getToken={getToken} />
          </div>
        )}

        {/* ── Configurações ── */}
        {workspaceTab === "settings" && (
          <div className="max-w-3xl space-y-5">
            <ConfigTabs active={configTab} onChange={setConfigTab} />

            <form onSubmit={isSaveable ? handleSave : (e) => e.preventDefault()}>
              {configTab === "geral" && (
                <ConfigGeral
                  agent={agent}
                  activeModel={activeModel}
                  name={name}
                  description={description}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onNameChange={setName}
                  onDescriptionChange={setDescription}
                />
              )}

              {configTab === "prompt" && (
                <ConfigPrompt
                  systemPrompt={systemPrompt}
                  persona={persona}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onSystemPromptChange={setSystemPrompt}
                  onPersonaChange={setPersona}
                />
              )}

              {configTab === "modelo" && (
                <ConfigModelo
                  aiModelId={aiModelId}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onModelChange={(modelId) => setAiModelId(modelId)}
                />
              )}

              {configTab === "avancado" && (
                <ConfigAvancado
                  temperature={temperature}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onTemperatureChange={setTemperature}
                />
              )}

              {configTab === "ferramentas" && <ConfigFerramentas />}
              {configTab === "seguranca"   && <ConfigSeguranca />}
              {configTab === "webhooks"    && <ConfigWebhooks />}
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
