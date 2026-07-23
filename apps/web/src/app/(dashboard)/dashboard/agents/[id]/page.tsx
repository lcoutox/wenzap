"use client";

import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import type {
  Agent,
  AgentStatus,
  AiCatalog,
  AiModel,
  ContextTier,
  GuidedConfig,
  InstructionsMode,
  LanguageMode,
  MemberRole,
  ResponseStyle,
} from "@/lib/api";

import { AgentHeader } from "@/components/agents/workspace/AgentHeader";
import { AgentWorkspaceTabs } from "@/components/agents/workspace/AgentWorkspaceTabs";
import type { WorkspaceTab } from "@/components/agents/workspace/AgentWorkspaceTabs";
import { ConfigTabs } from "@/components/agents/workspace/ConfigTabs";
import type { ConfigTab } from "@/components/agents/workspace/ConfigTabs";

import { AgentChat }            from "@/components/agents/workspace/tabs/AgentChat";
import { ImplantarTab }          from "@/components/agents/workspace/tabs/ImplantarTab";
import { ConfigGeral }           from "@/components/agents/workspace/tabs/ConfigGeral";
import { ConfigApresentacao }    from "@/components/agents/workspace/tabs/ConfigApresentacao";
import { ConfigComportamento }   from "@/components/agents/workspace/tabs/ConfigComportamento";
import { ConfigConhecimento }    from "@/components/agents/workspace/tabs/ConfigConhecimento";
import { ConfigModelo }          from "@/components/agents/workspace/tabs/ConfigModelo";
import { ConfigAvancado }        from "@/components/agents/workspace/tabs/ConfigAvancado";
import { ConfigFerramentas }     from "@/components/agents/workspace/tabs/ConfigFerramentas";
import { ConfigPipeline }        from "@/components/agents/workspace/tabs/ConfigPipeline";

// ── Helpers ───────────────────────────────────────────────────────────────────

function findActiveModel(catalog: AiCatalog | null, aiModelId: string | null): AiModel | null {
  if (!catalog || !aiModelId) return null;
  for (const provider of catalog.providers) {
    const m = provider.models.find((m) => m.id === aiModelId);
    if (m) return m;
  }
  return null;
}

// Models executable for playground testing (backend + frontend support)
const EXECUTABLE_MODEL_NAMES = new Set([
  // Anthropic Claude
  "claude-haiku-4-5",
  "claude-sonnet-4-6",
  "claude-opus-4-8",
  // OpenAI GPT
  "gpt-4o-mini",
  "gpt-4o",
]);

function isModelExecutable(catalog: AiCatalog | null, activeModel: AiModel | null): boolean {
  if (!catalog || !activeModel) return false;
  for (const provider of catalog.providers) {
    const found = provider.models.find((m) => m.id === activeModel.id);
    if (found) {
      return (
        (provider.code === "anthropic" || provider.code === "openai" || provider.code === "nexbrain") &&
        EXECUTABLE_MODEL_NAMES.has(activeModel.model_name)
      );
    }
  }
  return false;
}

// ── Tab deep-link helpers ─────────────────────────────────────────────────────

const VALID_WORKSPACE_TABS: WorkspaceTab[] = ["chat", "deploy", "tools", "settings"];

function parseWorkspaceTab(value: string | null): WorkspaceTab | null {
  if (!value) return null;
  // Legacy deep-link: ?tab=knowledge → tools
  if (value === "knowledge") return "tools";
  if ((VALID_WORKSPACE_TABS as string[]).includes(value)) return value as WorkspaceTab;
  return null;
}

const VALID_CONFIG_TABS: ConfigTab[] = ["geral", "apresentacao", "instrucoes", "conhecimento", "modelo", "avancado", "pipeline"];

function parseConfigTab(value: string | null): ConfigTab | null {
  if (!value) return null;
  if ((VALID_CONFIG_TABS as string[]).includes(value)) return value as ConfigTab;
  return null;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const router   = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { showToast } = useToast();

  // Remote state
  const [agent,    setAgent]   = useState<Agent | null>(null);
  const [catalog,  setCatalog] = useState<AiCatalog | null>(null);
  const [role,     setRole]    = useState<MemberRole | null>(null);
  const [planCode, setPlanCode] = useState<string>("starter");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Form fields
  const [name,         setName]         = useState("");
  const [description,  setDescription]  = useState("");
  const [aiModelId,    setAiModelId]    = useState<string | null>(null);
  const [temperature,  setTemperature]  = useState("0.7");
  const [catalogEnabled, setCatalogEnabled] = useState(true);
  const [responseStyle,  setResponseStyle]  = useState<ResponseStyle>("balanced");
  const [languageMode,   setLanguageMode]   = useState<LanguageMode>("auto");
  const [knowledgeOnly,  setKnowledgeOnly]  = useState(false);
  const [showSources,    setShowSources]    = useState(false);
  const [instructionsMode, setInstructionsMode] = useState<InstructionsMode>("guided");
  const [guidedConfig, setGuidedConfig] = useState<GuidedConfig>({});
  const [advancedPrompt, setAdvancedPrompt] = useState("");
  const [contextTier, setContextTier] = useState<ContextTier>("standard");
  const [replyDelaySeconds, setReplyDelaySeconds] = useState<number>(5);
  const [knowledgeFallback, setKnowledgeFallback] = useState<"ask_context" | "direct_to_team" | "knowledge_general" | null>(null);
  const [voiceReplyEnabled, setVoiceReplyEnabled] = useState(false);
  const [elevenlabsVoiceId, setElevenlabsVoiceId] = useState("");

  // UI state — initialise from ?tab= query param, fallback to "chat"
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>(
    () => parseWorkspaceTab(searchParams.get("tab")) ?? "chat"
  );
  const [configTab,    setConfigTab]    = useState<ConfigTab>(
    () => parseConfigTab(searchParams.get("configTab")) ?? "geral"
  );
  const [saving,       setSaving]       = useState(false);
  const [saveError,    setSaveError]    = useState<string | null>(null);
  const [saveSuccess,  setSaveSuccess]  = useState(false);
  const [actionError,  setActionError]  = useState<string | null>(null);

  // ── Tab navigation ────────────────────────────────────────────────────────────

  // Sync URL → state (handles back/forward and in-page links like "Gerenciar conhecimento")
  const tabParam = searchParams.get("tab");
  useEffect(() => {
    const next = parseWorkspaceTab(tabParam) ?? "chat";
    setWorkspaceTab((current) => (current === next ? current : next));
  }, [tabParam]);

  const handleTabChange = (tab: WorkspaceTab) => {
    setWorkspaceTab(tab);
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tab);
    router.replace(`${pathname}?${params.toString()}`, { scroll: false });
  };

  // ── Load ─────────────────────────────────────────────────────────────────────
  useEffect(() => {
    (async () => {
      try {
        const [agentData, me, catalogData] = await Promise.all([
          api.agents.get(id),
          api.me(),
          api.aiModels.list(),
        ]);
        setAgent(agentData);
        setRole(me.role);
        setCatalog(catalogData);
        setPlanCode(catalogData.current_plan);
        setName(agentData.name);
        setDescription(agentData.description ?? "");
        setAiModelId(agentData.ai_model_id);
        setTemperature(String(agentData.temperature));
        setCatalogEnabled(agentData.catalog_enabled);
        setResponseStyle(agentData.response_style);
        setLanguageMode(agentData.language_mode);
        setKnowledgeOnly(agentData.knowledge_only);
        setShowSources(agentData.show_sources);
        setInstructionsMode(agentData.instructions_mode ?? "guided");
        setGuidedConfig(agentData.guided_config ?? {});
        setAdvancedPrompt(agentData.advanced_prompt ?? "");
        setContextTier(agentData.context_tier ?? "standard");
        setReplyDelaySeconds(agentData.reply_delay_seconds ?? 5);
        setKnowledgeFallback((agentData.knowledge_fallback as "ask_context" | "direct_to_team" | "knowledge_general" | null) ?? null);
        setVoiceReplyEnabled(agentData.voice_reply_enabled ?? false);
        setElevenlabsVoiceId(agentData.elevenlabs_voice_id ?? "");
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) {
          router.push("/dashboard/agents");
        } else {
          setLoadError(e instanceof Error ? e.message : "Erro ao carregar agente.");
        }
      } finally {
        setLoading(false);
      }
    })();
  }, [id, router]);

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
      const updated = await api.agents.update(id, {
        name: name.trim(),
        description: description.trim() || null,
        ai_model_id: aiModelId,
        temperature: tempNum,
        catalog_enabled: catalogEnabled,
        response_style: responseStyle,
        language_mode: languageMode,
        knowledge_only: knowledgeOnly,
        show_sources: showSources,
        instructions_mode: instructionsMode,
        guided_config: instructionsMode === "guided" ? guidedConfig : undefined,
        advanced_prompt:
          instructionsMode === "advanced" ? advancedPrompt.trim() || null : undefined,
        context_tier: contextTier,
        reply_delay_seconds: replyDelaySeconds,
        knowledge_fallback: knowledgeFallback,
        voice_reply_enabled: voiceReplyEnabled,
        elevenlabs_voice_id: elevenlabsVoiceId.trim() || null,
      });
      setAgent(updated);
      setSaveSuccess(true);
      showToast("success", "Configuração do agente salva.");
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao salvar.";
      setSaveError(msg);
      showToast("error", msg);
    } finally {
      setSaving(false);
    }
  }

  // ── Status actions ────────────────────────────────────────────────────────────
  async function changeStatus(newStatus: AgentStatus) {
    if (!agent) return;
    setActionError(null);
    try {
      const updated = await api.agents.updateStatus(id, newStatus);
      setAgent(updated);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Erro ao mudar status.";
      // Activation blocked by missing prompt/behavior config — take the user
      // straight to where it's fixed instead of leaving them stuck on Chat.
      if (message.startsWith("Configure o prompt avançado") || message.startsWith("Configure o comportamento")) {
        handleTabChange("settings");
        setConfigTab("instrucoes");
      }
      setActionError(message);
    }
  }

  async function handleArchive() {
    if (!agent) return;
    setActionError(null);
    try {
      const updated = await api.agents.archive(id);
      setAgent(updated);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Erro ao arquivar.");
    }
  }

  async function handleDeletePermanently() {
    if (!agent) return;
    setActionError(null);
    try {
      await api.agents.deletePermanently(id);
      router.push("/dashboard/agents");
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Erro ao excluir agente.");
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

  // Config tabs that have real save functionality (pipeline has its own save button)
  const isSaveable = ["geral", "instrucoes", "conhecimento", "modelo", "avancado"].includes(configTab);

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
      <AgentWorkspaceTabs active={workspaceTab} onChange={handleTabChange} />

      {/* Tab content */}
      <div className="p-6 flex-1">

        {/* ── Chat ── */}
        {workspaceTab === "chat" && (
          <AgentChat
            agent={agent}
            activeModel={activeModel}
            modelExecutable={modelExecutable}
            role={role}
          />
        )}

        {/* ── Implantar ── */}
        {workspaceTab === "deploy" && (
          <ImplantarTab agentId={id} role={role} />
        )}

        {/* ── Ferramentas ── */}
        {workspaceTab === "tools" && (
          <div className="max-w-4xl">
            <ConfigFerramentas
              agentId={id}
              readonly={readonly}
              role={role}
              planCode={planCode}
            />
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
                  onAvatarChange={setAgent}
                  onChangeStatus={changeStatus}
                  onArchive={handleArchive}
                  onDeletePermanently={handleDeletePermanently}
                />
              )}

              {configTab === "apresentacao" && (
                <ConfigApresentacao
                  responseStyle={responseStyle}
                  languageMode={languageMode}
                  replyDelaySeconds={replyDelaySeconds}
                  voiceReplyEnabled={voiceReplyEnabled}
                  elevenlabsVoiceId={elevenlabsVoiceId}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onResponseStyleChange={setResponseStyle}
                  onLanguageModeChange={setLanguageMode}
                  onReplyDelaySecondsChange={setReplyDelaySeconds}
                  onVoiceReplyEnabledChange={setVoiceReplyEnabled}
                  onElevenlabsVoiceIdChange={setElevenlabsVoiceId}
                />
              )}

              {configTab === "instrucoes" && (
                <ConfigComportamento
                  instructionsMode={instructionsMode}
                  guidedConfig={guidedConfig}
                  advancedPrompt={advancedPrompt}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onInstructionsModeChange={setInstructionsMode}
                  onGuidedConfigChange={setGuidedConfig}
                  onAdvancedPromptChange={setAdvancedPrompt}
                />
              )}

              {configTab === "conhecimento" && (
                <ConfigConhecimento
                  agentId={id}
                  knowledgeOnly={knowledgeOnly}
                  showSources={showSources}
                  knowledgeFallback={knowledgeFallback}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onKnowledgeOnlyChange={setKnowledgeOnly}
                  onShowSourcesChange={setShowSources}
                  onKnowledgeFallbackChange={setKnowledgeFallback}
                  onSwitchToTools={() => handleTabChange("tools")}
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
                  contextTier={contextTier}
                  planCode={planCode}
                  readonly={readonly}
                  saving={saving}
                  saveError={saveError}
                  saveSuccess={saveSuccess}
                  onTemperatureChange={setTemperature}
                  onContextTierChange={setContextTier}
                />
              )}
            </form>

            {configTab === "pipeline" && (
              <ConfigPipeline
                agentId={id}
                defaultPipelineId={null}
                defaultPipelineStageId={null}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
