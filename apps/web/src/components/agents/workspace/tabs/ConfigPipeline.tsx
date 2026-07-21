"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Pipeline, PipelineStage } from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

function Field({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-nb-secondary mb-1">{label}</label>
      {description && <p className="text-xs text-nb-muted mb-1.5">{description}</p>}
      {children}
    </div>
  );
}

export function ConfigPipeline({
  agentId,
  defaultPipelineId,
  defaultPipelineStageId,
  onSaved,
}: {
  agentId: string;
  defaultPipelineId: string | null;
  defaultPipelineStageId: string | null;
  onSaved?: () => void;
}) {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [selectedPipelineId, setSelectedPipelineId] = useState(defaultPipelineId ?? "");
  const [selectedStageId, setSelectedStageId] = useState(defaultPipelineStageId ?? "");
  const [loadingPipelines, setLoadingPipelines] = useState(true);
  const [loadingStages, setLoadingStages] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();

  // Load pipelines once
  useEffect(() => {
    api.pipelines.list()
      .then(setPipelines)
      .catch(() => {})
      .finally(() => setLoadingPipelines(false));
  }, []);

  // Load stages when pipeline selection changes
  useEffect(() => {
    if (!selectedPipelineId) { setStages([]); return; }
    setLoadingStages(true);
    api.pipelines.stages.list(selectedPipelineId)
      .then((s) => setStages(s.sort((a, b) => a.position - b.position)))
      .catch(() => setStages([]))
      .finally(() => setLoadingStages(false));
  }, [selectedPipelineId]);

  // Reset stage when pipeline changes
  function handlePipelineChange(id: string) {
    setSelectedPipelineId(id);
    setSelectedStageId("");
    setSuccess(false);
    setError(null);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      await api.agents.updatePipelineSettings(agentId, {
        default_pipeline_id: selectedPipelineId || null,
        default_pipeline_stage_id: selectedStageId || null,
      });
      setSuccess(true);
      onSaved?.();
      showToast("success", "Configuração de pipeline salva.");
      setTimeout(() => setSuccess(false), 3000);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Erro ao salvar configurações de pipeline.";
      setError(msg);
      showToast("error", msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div>
        <h3 className="text-sm font-semibold text-nb-text mb-1">Pipeline padrão</h3>
        <p className="text-xs text-nb-muted leading-relaxed">
          Quando uma nova conversa for criada por este agente, ela será automaticamente adicionada ao pipeline e etapa selecionados.
        </p>
      </div>

      {loadingPipelines ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-nb-muted" />
        </div>
      ) : pipelines.length === 0 ? (
        <div className="rounded-xl border border-dashed border-nb-border p-6 text-center">
          <p className="text-sm text-nb-secondary mb-1">Nenhum pipeline encontrado</p>
          <p className="text-xs text-nb-muted">
            Crie um pipeline em{" "}
            <a href="/dashboard/pipeline" className="text-nb-primary hover:underline">
              Pipeline
            </a>{" "}
            para configurar aqui.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Pipeline" description="Selecione o pipeline onde as conversas serão adicionadas automaticamente.">
            <select
              className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
              value={selectedPipelineId}
              onChange={(e) => handlePipelineChange(e.target.value)}
            >
              <option value="">Nenhum</option>
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </Field>

          {selectedPipelineId && (
            <Field label="Etapa inicial" description="Etapa em que a conversa será inserida ao entrar no pipeline.">
              {loadingStages ? (
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <Loader2 className="w-4 h-4 animate-spin text-nb-muted" />
                  <span className="text-xs text-nb-muted">Carregando etapas…</span>
                </div>
              ) : (
                <select
                  className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text focus:outline-none focus:border-nb-primary transition-colors"
                  value={selectedStageId}
                  onChange={(e) => { setSelectedStageId(e.target.value); setSuccess(false); setError(null); }}
                >
                  <option value="">Primeira etapa (padrão)</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              )}
            </Field>
          )}
        </div>
      )}

      {error && <p className="text-xs text-nb-danger">{error}</p>}
      {success && <p className="text-xs text-green-600">Configurações salvas com sucesso.</p>}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || loadingPipelines}
          className="px-4 py-2 text-xs font-medium text-white bg-nb-primary rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
        >
          {saving ? "Salvando…" : "Salvar"}
        </button>
      </div>
    </div>
  );
}
