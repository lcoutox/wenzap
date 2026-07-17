"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AiCatalog, KnowledgeBase } from "@/lib/api";

import {
  INITIAL_WIZARD_STATE,
  CREATIVITY_TEMPERATURE,
} from "@/components/agents/create/wizard-types";
import type { WizardState, CreativityLevel } from "@/components/agents/create/wizard-types";
import { AGENT_TEMPLATES } from "@/components/agents/create/templates";
import type { TemplateId } from "@/components/agents/create/templates";
import { WizardProgress }  from "@/components/agents/create/WizardProgress";
import { StepTemplate }    from "@/components/agents/create/StepTemplate";
import { StepIdentity }    from "@/components/agents/create/StepIdentity";
import { StepKnowledge }   from "@/components/agents/create/StepKnowledge";
import { StepModel }       from "@/components/agents/create/StepModel";
import { StepReview }      from "@/components/agents/create/StepReview";
import { StepSuccess }     from "@/components/agents/create/StepSuccess";

const TOTAL_STEPS = 5;

export default function NewAgentPage() {
  const router = useRouter();

  const [step,        setStep]        = useState(1);
  const [state,       setState]       = useState<WizardState>(INITIAL_WIZARD_STATE);
  const [errors,      setErrors]      = useState<Record<string, string>>({});
  const [saving,      setSaving]      = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const [createdAgentId,   setCreatedAgentId]   = useState<string | null>(null);
  const [connectedKbNames, setConnectedKbNames] = useState<string[]>([]);
  const [kbWarning,        setKbWarning]        = useState(false);

  const [catalog,     setCatalog]     = useState<AiCatalog | null>(null);
  const [kbs,         setKbs]         = useState<KnowledgeBase[]>([]);
  const [catalogLoad, setCatalogLoad] = useState(false);
  const [kbsLoad,     setKbsLoad]     = useState(false);
  const catalogFetched = useRef(false);
  const kbsFetched     = useRef(false);

  useEffect(() => {
    if (step === 4 && !catalogFetched.current) {
      catalogFetched.current = true;
      setCatalogLoad(true);
      api.aiModels.list().then(setCatalog).catch(() => {}).finally(() => setCatalogLoad(false));
    }
  }, [step]);

  useEffect(() => {
    if (step === 3 && !kbsFetched.current) {
      kbsFetched.current = true;
      setKbsLoad(true);
      api.knowledgeBases.list().then(setKbs).catch(() => {}).finally(() => setKbsLoad(false));
    }
  }, [step]);

  function update(patch: Partial<WizardState>) {
    setState((prev) => ({ ...prev, ...patch }));
  }

  function handleTemplateChange(id: TemplateId) {
    const template = AGENT_TEMPLATES.find((t) => t.id === id)!;
    setState((prev) => ({
      ...prev,
      templateId: id,
      guidedConfig: template.guidedConfig,
      // Pre-fill name hint from template if user hasn't typed yet
      name: prev.name,
    }));
  }

  // ── Validation ────────────────────────────────────────────────────────────

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (step === 1 && !state.templateId)         e.templateId  = "Selecione um template para continuar.";
    if (step === 2 && !state.name.trim())         e.name        = "Informe o nome do agente.";
    if (step === 4 && !state.aiModelId)           e.aiModelId   = "Selecione um modelo de IA.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  function handleNext() {
    if (!validate()) return;
    setStep((s) => Math.min(s + 1, TOTAL_STEPS));
  }

  function handleBack() {
    setErrors({});
    setStep((s) => Math.max(s - 1, 1));
  }

  // ── Submit ──────────────────────────────────────────────────────────────────

  async function handleCreate() {
    setGlobalError(null);
    setSaving(true);

    const temperature = CREATIVITY_TEMPERATURE[state.creativity];
    const isBlank     = state.templateId === "blank";

    try {
      const agent = await api.agents.create({
        name:             state.name.trim(),
        description:      state.description.trim() || undefined,
        ai_model_id:      state.aiModelId!,
        temperature,
        instructions_mode: isBlank ? "advanced" : "guided",
        guided_config:    isBlank ? undefined : state.guidedConfig,
      });

      let hasKbFailure = false;
      const successfulKbNames: string[] = [];
      if (state.selectedKbIds.length > 0) {
        const kbMap: Record<string, string> = {};
        kbs.forEach((kb) => { kbMap[kb.id] = kb.name; });

        const results = await Promise.allSettled(
          state.selectedKbIds.map((kbId) =>
            api.agents.knowledgeBases.connect(agent.id, kbId)
          )
        );
        results.forEach((r, i) => {
          if (r.status === "fulfilled") {
            successfulKbNames.push(kbMap[state.selectedKbIds[i]] ?? state.selectedKbIds[i]);
          } else {
            hasKbFailure = true;
          }
        });
      }

      setConnectedKbNames(successfulKbNames);
      setKbWarning(hasKbFailure);
      setCreatedAgentId(agent.id);
    } catch (e) {
      setGlobalError(e instanceof Error ? e.message : "Erro ao criar agente.");
    } finally {
      setSaving(false);
    }
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  function findModelDisplayName(): string | null {
    if (!catalog || !state.aiModelId) return null;
    for (const p of catalog.providers) {
      const m = p.models.find((m) => m.id === state.aiModelId);
      if (m) return m.display_name;
    }
    return null;
  }

  const selectedTemplate = AGENT_TEMPLATES.find((t) => t.id === state.templateId) ?? null;

  // ── Success screen ───────────────────────────────────────────────────────────

  if (createdAgentId) {
    return (
      <div className="max-w-2xl space-y-6 pb-24">
        <nav className="flex items-center gap-1 text-sm text-nb-muted">
          <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
            Agentes
          </Link>
          <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
          <span className="text-nb-secondary font-medium">Novo agente</span>
        </nav>
        <div className="bg-nb-panel border border-nb-border rounded-2xl p-6">
          <StepSuccess
            agentId={createdAgentId}
            agentName={state.name}
            description={state.description}
            modelDisplayName={findModelDisplayName()}
            connectedKbNames={connectedKbNames}
            kbWarning={kbWarning}
            agentType={null}
            needsPromptSetup={state.templateId === "blank"}
          />
        </div>
      </div>
    );
  }

  // ── Wizard ───────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl space-y-6 pb-24">
      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium">Novo agente</span>
      </nav>

      <WizardProgress current={step} total={TOTAL_STEPS} />

      <div className="bg-nb-panel border border-nb-border rounded-2xl p-6">
        {step === 1 && (
          <StepTemplate
            value={state.templateId}
            onChange={handleTemplateChange}
          />
        )}
        {step === 2 && (
          <StepIdentity
            name={state.name}
            description={state.description}
            onNameChange={(v) => update({ name: v })}
            onDescriptionChange={(v) => update({ description: v })}
            errors={errors}
          />
        )}
        {step === 3 && (
          <StepKnowledge
            kbs={kbs}
            loading={kbsLoad}
            selectedKbIds={state.selectedKbIds}
            onSelectionChange={(v) => update({ selectedKbIds: v })}
          />
        )}
        {step === 4 && (
          <StepModel
            catalog={catalog}
            loading={catalogLoad}
            aiModelId={state.aiModelId}
            creativity={state.creativity}
            onModelChange={(id) => update({ aiModelId: id })}
            onCreativityChange={(v: CreativityLevel) => update({ creativity: v })}
            errors={errors}
          />
        )}
        {step === 5 && (
          <StepReview
            state={state}
            catalog={catalog}
            kbs={kbs}
            selectedTemplate={selectedTemplate}
          />
        )}
      </div>

      {globalError && (
        <p className="text-sm text-nb-danger px-1">{globalError}</p>
      )}

      <div className="flex items-center justify-between">
        <div>
          {step > 1 ? (
            <button
              type="button"
              onClick={handleBack}
              disabled={saving}
              className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors disabled:opacity-40"
            >
              Voltar
            </button>
          ) : (
            <Link
              href="/dashboard/agents"
              className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
            >
              Cancelar
            </Link>
          )}
        </div>

        <div className="flex items-center gap-3">
          {step === 3 && (
            <button
              type="button"
              onClick={() => { setErrors({}); setStep(4); }}
              className="px-4 py-2 text-sm font-medium text-nb-muted hover:text-nb-secondary transition-colors"
            >
              Pular
            </button>
          )}

          {step < TOTAL_STEPS ? (
            <button
              type="button"
              onClick={handleNext}
              className="px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong transition-colors"
            >
              Continuar
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCreate}
              disabled={saving}
              className="flex items-center gap-2 px-5 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-50 transition-colors"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {saving ? "Criando agente…" : "Criar agente"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
