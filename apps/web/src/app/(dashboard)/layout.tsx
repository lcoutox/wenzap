import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";
import { DashboardShell } from "@/components/layout/DashboardShell";
import { api } from "@/lib/api";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { getToken } = await auth();
  const token = await getToken();

  if (!token) redirect("/sign-in");

  const [subscription, usage] = await Promise.allSettled([
    api.plans.current(token),
    api.plans.usage(token),
  ]);

  return (
    <DashboardShell
      subscription={subscription.status === "fulfilled" ? subscription.value : null}
      usage={usage.status === "fulfilled" ? usage.value : null}
    >
      {children}
    </DashboardShell>
  );
}
