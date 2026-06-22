"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Member } from "@/lib/api";

const ROLE_LABELS: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  member: "Membro",
  viewer: "Visualizador",
};

export default function MembersPage() {
  const { getToken } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);

  useEffect(() => {
    getToken().then((token) => {
      if (token) api.members.list(token).then(setMembers);
    });
  }, [getToken]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Membros</h1>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Nome</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Email</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Papel</th>
              <th className="text-left px-4 py-3 text-gray-500 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {members.map((m) => (
              <tr key={m.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{m.name}</td>
                <td className="px-4 py-3 text-gray-500">{m.email}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">
                    {ROLE_LABELS[m.role] ?? m.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    m.status === "active"
                      ? "bg-green-50 text-green-700"
                      : "bg-gray-100 text-gray-500"
                  }`}>
                    {m.status === "active" ? "Ativo" : "Inativo"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {members.length === 0 && (
          <p className="text-center text-gray-400 py-8 text-sm">Nenhum membro encontrado.</p>
        )}
      </div>
    </div>
  );
}
