import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { UserMenu } from "@/components/layout/UserMenu";
import { api } from "@/lib/api";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { getToken } = await auth();
  const token = await getToken();

  if (!token) {
    redirect("/sign-in");
  }

  const me = await api.me(token).catch(() => null);

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-6">
          <span className="text-sm font-medium text-gray-600">
            {me?.workspace?.name ?? "Workspace"}
          </span>
          <UserMenu />
        </header>
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
