"use client";

import { useAppAuth } from "@/contexts/AuthContext";

export default function DashboardPage() {
  const { user, workspace } = useAppAuth();

  return (
    <div>
      <h1 className="text-xl font-bold text-nb-text mb-0.5">Dashboard</h1>
      <p className="text-nb-muted text-sm mb-8">
        Bem-vindo ao{" "}
        <span className="text-nb-secondary font-medium">{workspace?.name}</span>
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">Workspace</p>
          <p className="text-lg font-semibold text-nb-text">{workspace?.name ?? "—"}</p>
        </div>
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">Usuário</p>
          <p className="text-lg font-semibold text-nb-text">{user?.name ?? "—"}</p>
        </div>
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">E-mail</p>
          <p className="text-lg font-semibold text-nb-text">{user?.email ?? "—"}</p>
        </div>
      </div>
    </div>
  );
}
