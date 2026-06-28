"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Member } from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  owner:  "Owner",
  admin:  "Admin",
  member: "Membro",
  viewer: "Visualizador",
};

const ROLE_CLS: Record<string, string> = {
  owner:  "bg-nb-primary-bg text-nb-primary-strong border-nb-primary/20",
  admin:  "bg-nb-info/10     text-nb-info            border-nb-info/20",
  member: "bg-nb-elevated    text-nb-secondary       border-nb-border",
  viewer: "bg-nb-elevated    text-nb-muted           border-nb-border",
};

export function MembersSettingsSection() {
  const [members, setMembers] = useState<Member[]>([]);

  useEffect(() => {
    api.members.list().then(setMembers).catch(() => {});
  }, []);

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-nb-text">Membros do workspace</h2>
        <p className="text-xs text-nb-muted mt-0.5">Gerencie os membros e papéis de acesso.</p>
      </div>

      <div className="bg-nb-panel rounded-2xl border border-nb-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-nb-elevated border-b border-nb-border">
            <tr>
              <th className="text-left px-4 py-3 text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Nome</th>
              <th className="text-left px-4 py-3 text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Email</th>
              <th className="text-left px-4 py-3 text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Papel</th>
              <th className="text-left px-4 py-3 text-[10px] font-semibold text-nb-muted uppercase tracking-widest">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-nb-border">
            {members.map((m) => (
              <tr key={m.id} className="hover:bg-nb-elevated/50 transition-colors">
                <td className="px-4 py-3 font-medium text-nb-text">{m.name}</td>
                <td className="px-4 py-3 text-nb-muted">{m.email}</td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium border ${ROLE_CLS[m.role] ?? "bg-nb-elevated text-nb-muted border-nb-border"}`}>
                    {ROLE_LABELS[m.role] ?? m.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-xs font-medium border ${
                    m.status === "active"
                      ? "bg-nb-success/10 text-nb-success border-nb-success/20"
                      : "bg-nb-elevated   text-nb-muted   border-nb-border"
                  }`}>
                    {m.status === "active" ? "Ativo" : "Inativo"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {members.length === 0 && (
          <p className="text-center text-nb-muted py-8 text-sm">Nenhum membro encontrado.</p>
        )}
      </div>
    </div>
  );
}
