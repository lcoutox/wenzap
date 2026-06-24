"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { UserMe } from "@/lib/api";

export default function SettingsPage() {
  const { getToken } = useAuth();
  const [workspace, setWorkspace] = useState<UserMe["workspace"] | null>(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getToken().then((token) => {
      if (token) api.me(token).then((me) => {
        setWorkspace(me.workspace);
        setName(me.workspace.name);
      });
    });
  }, [getToken]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const token = await getToken();
      if (!token) return;
      const updated = await api.workspace.update(token, { name });
      setWorkspace(updated);
      setMessage("Salvo com sucesso.");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-lg">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-nb-text">Configurações do workspace</h1>
        <p className="text-sm text-nb-muted mt-0.5">Gerencie as informações do seu workspace.</p>
      </div>

      {workspace && (
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-6">
          <form onSubmit={handleSave} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-nb-secondary mb-1.5">Nome</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-nb-secondary mb-1.5">Slug</label>
              <input
                type="text"
                value={workspace.slug}
                readOnly
                className="w-full bg-nb-bg border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-muted cursor-not-allowed"
              />
            </div>
            {message && (
              <p className={`text-sm ${message.includes("sucesso") ? "text-nb-success" : "text-nb-danger"}`}>
                {message}
              </p>
            )}
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-2 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
