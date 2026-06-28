"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronRight, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { AiCatalog, KnowledgeBase } from "@/lib/api";

import {
  INITIAL_WIZARD_STATE,
  CREATIVITY_TEMPERATURE,
  AGENT_TYPE_DEFAULTS,
} from "@/components/agents/create/wizard-types";
import type {
  WizardState,
  AgentTypeId,
  ToneOption,
  CreativityLevel,
} from "@/components/agents/create/wizard-types";
import { buildSystemPrompt, buildPersona } from "@/components/agents/create/buildSystemPrompt";
import { WizardProgress } from "@/components/agents/create/WizardProgress";
import { StepAgentType }  from "@/components/agents/create/StepAgentType";
import { StepIdentity }   from "@/components/agents/create/StepIdentity";
import { StepBehavior }   from "@/components/agents/create/StepBehavior";
import { StepKnowledge }  from "@/components/agents/create/StepKnowledge";
import { StepModel }      from "@/components/agents/create/StepModel";
import { StepReview }     from "@/components/agents/create/StepReview";

const TOTAL_STEPS = 6;

export default function NewAgentPage() {
  const router = useRouter();

  const [step,        setStep]        = useState(1);
  const [state,       setState]       = useState<WizardState>(INITIAL_WIZARD_STATE);
  const [errors,      setErrors]      = useState<Record<string, string>>({});
  const [saving,      setSaving]      = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Shared data fetched once — passed to steps that need them
  const [catalog,     setCatalog]     = useState<AiCatalog | null>(null);
  const [kbs,         setKbs]         = useState<KnowledgeBase[]>([]);
  const [catalogLoad, setCatalogLoad] = useState(false);
  const [kbsLoad,     setKbsLoad]     = useState(false);

  // Fetch catalog when reaching step 5
  useEffect(() => {
    if (step === 5 && !catalog && !catalogLoad) {
      setCatalogLoad(true);
      api.aiModels.list().then(setCatalog).catch(() => {}).finally(() => setCatalogLoad(false));
    }
  }, [step, catalog, catalogLoad]);

  // Fetch KBs when reaching step 4
  useEffect(() => {
    if (step === 4 && kbs.length === 0 && !kbsLoad) {
      setKbsLoad(true);
      api.knowledgeBases.list().then(setKbs).catch(() => {}).finally(() => setKbsLoad(false));
    }
  }, [step, kbs.length, kbsLoad]);

  function update(patch: Partial<WizardState>) {
    setState((prev) => ({ ...prev, ...patch }));
  }

  function handleAgentTypeChange(type: AgentTypeId) {
    const defaults = AGENT_TYPE_DEFAULTS[type];
    setState((prev) => ({
      ...prev,
      agentType:   type,
      description: prev.description || defaults.descriptionHint,
      tones:       prev.tones.length > 0 ? prev.tones : (defaults.tones as ToneOption[]),
      rules:       prev.rules.length > 0 ? prev.rules : defaults.rules,
    }));
  }

  // ── Validation ────────────────────────────────────────────────────────────

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (step === 1 && !state.agentType)           e.agentType   = "Selecione um tipo de agente.";
    if (step === 2 && !state.name.trim())          e.name        = "Informe o nome do agente.";
    if (step === 2 && !state.description.trim())   e.description = "Informe o objetivo do agente.";
    if (step === 3 && state.tones.length === 0)    e.tones       = "Selecione ao menos um tom de voz.";
    if (step === 5 && !state.aiModelId)            e.aiModelId   = "Selecione um modelo de IA.";
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

    const systemPrompt = buildSystemPrompt(state);
    const persona      = buildPersona(state.tones);
    const temperature  = CREATIVITY_TEMPERATURE[state.creativity];

    try {
      const agent = await api.agents.create({
        name:          state.name.trim(),
        description:   state.description.trim() || undefined,
        system_prompt: systemPrompt || undefined,
        persona:       persona || undefined,
        ai_model_id:   state.aiModelId!,
        temperature,
      });

      if (state.selectedKbIds.length > 0) {
        await Promise.allSettled(
          state.selectedKbIds.map((kbId) =>
            api.agents.knowledgeBases.connect(agent.id, kbId)
          )
        );
      }

      router.push(`/dashboard/agents/${agent.id}`);
    } catch (e) {
      setGlobalError(e instanceof Error ? e.message : "Erro ao criar agente.");
    } finally {
      setSaving(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="max-w-2xl space-y-6 pb-24">

      <nav className="flex items-center gap-1 text-sm text-nb-muted">
        <Link href="/dashboard/agents" className="hover:text-nb-secondary transition-colors">
          Agentes
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-nb-border-strong" />
        <span className="text-nb-secondary font-medium">Novo agente</span>
      </nav>

      <WizardProgress current={step} />

      <div className="bg-nb-panel border border-nb-border rounded-2xl p-6">
        {step === 1 && (
          <StepAgentType
            value={state.agentType}
            onChange={handleAgentTypeChange}
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
          <StepBehavior
            tones={state.tones}
            rules={state.rules}
            avoidText={state.avoidText}
            additionalInstructions={state.additionalInstructions}
            onTonesChange={(v) => update({ tones: v })}
            onRulesChange={(v) => update({ rules: v })}
            onAvoidTextChange={(v) => update({ avoidText: v })}
            onAdditionalInstructionsChange={(v) => update({ additionalInstructions: v })}
            errors={errors}
          />
        )}
        {step === 4 && (
          <StepKnowledge
            kbs={kbs}
            loading={kbsLoad}
            selectedKbIds={state.selectedKbIds}
            onSelectionChange={(v) => update({ selectedKbIds: v })}
          />
        )}
        {step === 5 && (
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
        {step === 6 && (
          <StepReview
            state={state}
            catalog={catalog}
            kbs={kbs}
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
          {step === 4 && (
            <button
              type="button"
              onClick={() => { setErrors({}); setStep(5); }}
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
