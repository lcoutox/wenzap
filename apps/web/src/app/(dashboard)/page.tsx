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
      <h1 className="text-2xl font-bold text-gray-900 mb-1">Dashboard</h1>
      <p className="text-gray-500 text-sm mb-8">
        Bem-vindo ao <strong>{me?.workspace?.name}</strong>
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Workspace</p>
          <p className="text-lg font-semibold text-gray-900">{me?.workspace?.name ?? "—"}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Usuário</p>
          <p className="text-lg font-semibold text-gray-900">{me?.name ?? "—"}</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Papel</p>
          <p className="text-lg font-semibold text-gray-900 capitalize">{me?.role ?? "—"}</p>
        </div>
      </div>
    </div>
  );
}
