"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import type { UserMe } from "@/lib/api";
import { MembersSettingsSection } from "@/components/settings/MembersSettingsSection";
import { PlanUsageSettingsSection } from "@/components/settings/PlanUsageSettingsSection";
import { IntegrationsSettingsSection } from "@/components/settings/IntegrationsSettingsSection";

type Tab = "general" | "members" | "plan" | "integrations";

const TABS: { id: Tab; label: string }[] = [
  { id: "general",      label: "Geral"         },
  { id: "members",      label: "Membros"       },
  { id: "plan",         label: "Plano e uso"   },
  { id: "integrations", label: "Integrações"   },
];

function parseTab(raw: string | null): Tab {
  if (raw === "members" || raw === "plan" || raw === "integrations") return raw;
  return "general";
}

// ── Tab: Geral ────────────────────────────────────────────────────────────────

function TabGeral() {
  const [workspace, setWorkspace] = useState<UserMe["workspace"] | null>(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.me().then((me) => {
      setWorkspace(me.workspace);
      setName(me.workspace.name);
    }).catch(() => {});
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMessage("");
    try {
      const updated = await api.workspace.update({ name });
      setWorkspace(updated);
      setMessage("Salvo com sucesso.");
    } catch (err: unknown) {
      setMessage(err instanceof Error ? err.message : "Erro ao salvar.");
    } finally {
      setSaving(false);
    }
  }

  if (!workspace) {
    return <div className="h-32 flex items-center justify-center text-sm text-nb-muted">Carregando...</div>;
  }

  return (
    <div className="max-w-md space-y-6">
      <div>
        <h2 className="text-sm font-semibold text-nb-text">Informações do workspace</h2>
        <p className="text-xs text-nb-muted mt-0.5">Nome e identificador do seu workspace no Wenzap.</p>
      </div>

      <div className="bg-nb-panel border border-nb-border rounded-2xl divide-y divide-nb-border">
        <form onSubmit={handleSave}>
          <div className="p-5 space-y-4">
            <div>
              <label className="block text-xs font-medium text-nb-secondary mb-1.5">Nome do workspace</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
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
              <p className="text-[11px] text-nb-muted mt-1">O slug não pode ser alterado.</p>
            </div>
          </div>

          <div className="px-5 py-3 bg-nb-elevated/60 rounded-b-2xl flex items-center justify-between gap-3">
            {message ? (
              <p className={`text-xs ${message.includes("sucesso") ? "text-nb-success" : "text-nb-danger"}`}>
                {message}
              </p>
            ) : (
              <span />
            )}
            <button
              type="submit"
              disabled={saving}
              className="px-4 py-1.5 bg-nb-primary text-white text-sm font-medium rounded-xl hover:bg-nb-primary-strong disabled:opacity-40 transition-colors"
            >
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

function SettingsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTab = parseTab(searchParams.get("tab"));

  function setTab(tab: Tab) {
    const params = new URLSearchParams(searchParams.toString());
    if (tab === "general") {
      params.delete("tab");
    } else {
      params.set("tab", tab);
    }
    router.replace(`/dashboard/settings?${params.toString()}`, { scroll: false });
  }

  return (
    <>
      {/* Tabs */}
      <div className="border-b border-nb-border">
        <nav className="flex gap-0 -mb-px">
          {TABS.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`
                px-4 py-2.5 text-sm font-medium border-b-2 transition-colors
                ${activeTab === id
                  ? "border-nb-primary text-nb-primary-strong"
                  : "border-transparent text-nb-muted hover:text-nb-secondary hover:border-nb-border-strong"}
              `}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab content */}
      <div className="pt-6">
        {activeTab === "general"      && <TabGeral />}
        {activeTab === "members"      && <MembersSettingsSection />}
        {activeTab === "plan"         && <PlanUsageSettingsSection />}
        {activeTab === "integrations" && <IntegrationsSettingsSection />}
      </div>
    </>
  );
}

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-nb-text">Configurações</h1>
        <p className="text-sm text-nb-muted mt-0.5">Gerencie o workspace, membros e plano da conta.</p>
      </div>

      <Suspense>
        <SettingsContent />
      </Suspense>
    </div>
  );
}
