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
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Configurações do workspace</h1>

      {workspace && (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Nome</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Slug</label>
            <input
              type="text"
              value={workspace.slug}
              readOnly
              className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm bg-gray-50 text-gray-500 cursor-not-allowed"
            />
          </div>
          {message && (
            <p className="text-sm text-green-600">{message}</p>
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </form>
      )}
    </div>
  );
}
