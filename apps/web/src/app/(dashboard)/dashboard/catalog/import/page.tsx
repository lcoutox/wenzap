"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileSpreadsheet,
  Upload,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  CatalogImportMapping,
  CatalogImportMode,
  CatalogImportPreview,
  CatalogImportReport,
} from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

type Step = "upload" | "mapping" | "result";

const MAPPABLE_FIELDS: { key: keyof Omit<CatalogImportMapping, "metadata">; label: string; required?: boolean }[] = [
  { key: "name",             label: "Nome",             required: true },
  { key: "category",         label: "Categoria" },
  { key: "description",      label: "Descrição" },
  { key: "short_description",label: "Descrição curta" },
  { key: "price",            label: "Preço" },
  { key: "currency",         label: "Moeda" },
  { key: "status",           label: "Status" },
  { key: "tags",             label: "Tags" },
  { key: "sku",              label: "SKU" },
  { key: "external_id",      label: "ID Externo" },
  { key: "stock_quantity",   label: "Estoque" },
  { key: "is_featured",      label: "Destaque" },
];

const MODE_LABELS: Record<CatalogImportMode, string> = {
  create_only:          "Criar apenas novos itens",
  upsert_by_sku:        "Criar ou atualizar por SKU",
  upsert_by_external_id:"Criar ou atualizar por ID Externo",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function CatalogImportPage() {
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CatalogImportPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<CatalogImportMode>("create_only");
  const [report, setReport] = useState<CatalogImportReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorsExpanded, setErrorsExpanded] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Drag & drop ──────────────────────────────────────────────────────────────

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFile = async (f: File) => {
    setError(null);
    setFile(f);
    setLoading(true);
    try {
      const result = await api.catalog.import.preview(f);
      setPreview(result);
      setStep("mapping");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao processar arquivo.");
      setFile(null);
    } finally {
      setLoading(false);
    }
  };

  // ── Commit ───────────────────────────────────────────────────────────────────

  const handleCommit = async () => {
    if (!file) return;
    setError(null);
    setLoading(true);
    try {
      const builtMapping: CatalogImportMapping = {};
      for (const f of MAPPABLE_FIELDS) {
        const col = mapping[f.key];
        if (col) (builtMapping as Record<string, string>)[f.key] = col;
      }
      const result = await api.catalog.import.commit(file, builtMapping, mode);
      setReport(result);
      setStep("result");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao importar.");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setStep("upload");
    setFile(null);
    setPreview(null);
    setMapping({});
    setMode("create_only");
    setReport(null);
    setError(null);
  };

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/dashboard/catalog"
          className="p-1.5 rounded-lg hover:bg-nb-elevated transition-colors text-nb-muted hover:text-nb-text"
        >
          <ArrowLeft className="w-4 h-4" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-nb-text">Importar itens</h1>
          <p className="mt-0.5 text-sm text-nb-muted">
            Importe produtos do catálogo em lote via CSV ou XLSX.
          </p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 text-sm">
        {(["upload", "mapping", "result"] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            {i > 0 && <div className="w-8 h-px bg-nb-border" />}
            <span
              className={`px-2.5 py-1 rounded-full font-medium ${
                step === s
                  ? "bg-nb-primary text-white"
                  : step === "result" || (step === "mapping" && i === 0)
                  ? "bg-nb-elevated text-nb-muted"
                  : "text-nb-muted"
              }`}
            >
              {i + 1}. {s === "upload" ? "Arquivo" : s === "mapping" ? "Mapeamento" : "Resultado"}
            </span>
          </div>
        ))}
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ── Step: upload ── */}
      {step === "upload" && (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-4 p-12 rounded-2xl border-2 border-dashed border-nb-border bg-nb-elevated cursor-pointer hover:border-nb-primary/50 transition-colors"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFile(f);
            }}
          />
          {loading ? (
            <div className="w-8 h-8 border-2 border-nb-primary border-t-transparent rounded-full animate-spin" />
          ) : (
            <>
              <div className="p-4 rounded-2xl bg-nb-base border border-nb-border">
                <FileSpreadsheet className="w-8 h-8 text-nb-muted" />
              </div>
              <div className="text-center">
                <p className="font-medium text-nb-text">
                  Arraste um arquivo ou clique para selecionar
                </p>
                <p className="mt-1 text-sm text-nb-muted">CSV ou XLSX — máximo 5 MB, 2.000 linhas</p>
              </div>
              <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium">
                <Upload className="w-4 h-4" />
                Selecionar arquivo
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Step: mapping ── */}
      {step === "mapping" && preview && (
        <div className="flex flex-col gap-5">
          {/* File info */}
          <div className="flex items-center gap-3 p-4 rounded-xl bg-nb-elevated border border-nb-border">
            <FileSpreadsheet className="w-5 h-5 text-nb-muted shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-nb-text truncate">{preview.filename}</p>
              <p className="text-xs text-nb-muted">{preview.total_rows} linhas detectadas</p>
            </div>
            <button
              onClick={handleReset}
              className="ml-auto text-xs text-nb-muted hover:text-nb-text underline shrink-0"
            >
              Trocar arquivo
            </button>
          </div>

          {/* Warnings */}
          {preview.warnings.length > 0 && (
            <div className="flex flex-col gap-1.5 p-3 rounded-xl bg-amber-50 border border-amber-200">
              {preview.warnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-700">{w}</p>
              ))}
            </div>
          )}

          {/* Column mapping */}
          <div className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold text-nb-text">Mapeamento de colunas</h2>
            <p className="text-xs text-nb-muted -mt-1">
              Selecione qual coluna do arquivo corresponde a cada campo do catálogo.
            </p>
            <div className="grid grid-cols-2 gap-3">
              {MAPPABLE_FIELDS.map((f) => (
                <div key={f.key} className="flex flex-col gap-1">
                  <label className="text-xs font-medium text-nb-muted">
                    {f.label}
                    {f.required && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  <select
                    value={mapping[f.key] ?? ""}
                    onChange={(e) =>
                      setMapping((prev) => ({ ...prev, [f.key]: e.target.value }))
                    }
                    className="px-3 py-2 rounded-xl bg-nb-base border border-nb-border text-sm text-nb-text focus:outline-none focus:ring-1 focus:ring-nb-primary"
                  >
                    <option value="">— não mapear —</option>
                    {preview.columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {/* Mode */}
          <div className="flex flex-col gap-2">
            <h2 className="text-sm font-semibold text-nb-text">Modo de importação</h2>
            <div className="flex flex-col gap-2">
              {(Object.entries(MODE_LABELS) as [CatalogImportMode, string][]).map(([m, label]) => (
                <label
                  key={m}
                  className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                    mode === m
                      ? "border-nb-primary bg-nb-primary/5"
                      : "border-nb-border bg-nb-elevated hover:bg-nb-border/30"
                  }`}
                >
                  <input
                    type="radio"
                    value={m}
                    checked={mode === m}
                    onChange={() => setMode(m)}
                    className="accent-nb-primary"
                  />
                  <span className="text-sm text-nb-text">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-xl border border-nb-border text-sm text-nb-text hover:bg-nb-elevated transition-colors"
            >
              Cancelar
            </button>
            <button
              onClick={handleCommit}
              disabled={loading || !mapping["name"]}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading && (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )}
              Importar
            </button>
          </div>
        </div>
      )}

      {/* ── Step: result ── */}
      {step === "result" && report && (
        <div className="flex flex-col gap-5">
          {/* Summary cards */}
          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "Criados", value: report.created, color: "text-green-600" },
              { label: "Atualizados", value: report.updated, color: "text-blue-600" },
              { label: "Ignorados", value: report.skipped, color: "text-amber-600" },
            ].map((s) => (
              <div
                key={s.label}
                className="flex flex-col items-center gap-1 p-4 rounded-xl bg-nb-elevated border border-nb-border"
              >
                <span className={`text-2xl font-bold ${s.color}`}>{s.value}</span>
                <span className="text-xs text-nb-muted">{s.label}</span>
              </div>
            ))}
          </div>

          {/* Success / partial */}
          {report.errors.length === 0 ? (
            <div className="flex items-center gap-3 p-4 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              Importação concluída com sucesso.
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <button
                onClick={() => setErrorsExpanded((v) => !v)}
                className="flex items-center justify-between p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm font-medium"
              >
                <span className="flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {report.errors.length} erro(s) encontrado(s)
                </span>
                {errorsExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {errorsExpanded && (
                <div className="flex flex-col gap-1 max-h-64 overflow-y-auto rounded-xl border border-nb-border bg-nb-elevated p-3">
                  {report.errors.map((e, i) => (
                    <div key={i} className="text-xs text-nb-text py-1 border-b border-nb-border last:border-0">
                      <span className="text-nb-muted">Linha {e.row_number}</span>
                      {e.field && <span className="mx-1 text-nb-muted">· {e.field}</span>}
                      <span className="ml-1">{e.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Warnings */}
          {report.warnings.length > 0 && (
            <div className="flex flex-col gap-1 p-3 rounded-xl bg-amber-50 border border-amber-200">
              {report.warnings.map((w, i) => (
                <p key={i} className="text-xs text-amber-700">{w.message}</p>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              onClick={handleReset}
              className="px-4 py-2 rounded-xl border border-nb-border text-sm text-nb-text hover:bg-nb-elevated transition-colors"
            >
              Nova importação
            </button>
            <Link
              href="/dashboard/catalog"
              className="px-4 py-2 rounded-xl bg-nb-primary text-white text-sm font-medium hover:bg-nb-primary-strong transition-colors"
            >
              Ver catálogo
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
