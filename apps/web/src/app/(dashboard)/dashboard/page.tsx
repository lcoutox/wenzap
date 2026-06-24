import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";

export default async function DashboardPage() {
  const { getToken } = await auth();
  const token = await getToken();

  if (!token) redirect("/sign-in");

  const me = await api.me(token).catch(() => null);

  return (
    <div>
      <h1 className="text-xl font-bold text-nb-text mb-0.5">Dashboard</h1>
      <p className="text-nb-muted text-sm mb-8">
        Bem-vindo ao <span className="text-nb-secondary font-medium">{me?.workspace?.name}</span>
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">Workspace</p>
          <p className="text-lg font-semibold text-nb-text">{me?.workspace?.name ?? "—"}</p>
        </div>
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">Usuário</p>
          <p className="text-lg font-semibold text-nb-text">{me?.name ?? "—"}</p>
        </div>
        <div className="bg-nb-panel rounded-2xl border border-nb-border p-5 hover:border-nb-border-strong transition-colors">
          <p className="text-[10px] font-semibold text-nb-muted uppercase tracking-widest mb-2">Papel</p>
          <p className="text-lg font-semibold text-nb-text capitalize">{me?.role ?? "—"}</p>
        </div>
      </div>
    </div>
  );
}
