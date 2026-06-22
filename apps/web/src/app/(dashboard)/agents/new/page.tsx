"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function NewAgentPage() {
  const { getToken } = useAuth();
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [persona, setPersona] = useState("");
  const [modelProvider, setModelProvider] = useState("anthropic");
  const [modelName, setModelName] = useState("claude-sonnet-4-6");
  const [temperature, setTemperature] = useState("0.7");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

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
        model_provider: modelProvider.trim(),
        model_name: modelName.trim(),
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
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Novo agente</h1>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg border border-gray-200 p-6 space-y-5">
        <Field label="Nome *">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
            placeholder="Ex: Agente de Suporte"
            className={inputClass}
          />
        </Field>

        <Field label="Descrição">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            placeholder="Descreva o propósito deste agente"
            className={inputClass}
          />
        </Field>

        <Field label="System prompt">
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            rows={5}
            maxLength={8000}
            placeholder="Instrução base para o agente. Necessário para ativar o agente."
            className={inputClass}
          />
        </Field>

        <Field label="Persona / Tom">
          <textarea
            value={persona}
            onChange={(e) => setPersona(e.target.value)}
            rows={2}
            maxLength={1000}
            placeholder="Ex: Comunicativo, empático, direto ao ponto"
            className={inputClass}
          />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Provider">
            <input
              type="text"
              value={modelProvider}
              onChange={(e) => setModelProvider(e.target.value)}
              maxLength={50}
              className={inputClass}
            />
          </Field>
          <Field label="Modelo">
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              maxLength={100}
              className={inputClass}
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
            className={inputClass}
          />
        </Field>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Salvando..." : "Criar agente"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/dashboard/agents")}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
          >
            Cancelar
          </button>
        </div>
      </form>
    </div>
  );
}

const inputClass =
  "w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
    </div>
  );
}
