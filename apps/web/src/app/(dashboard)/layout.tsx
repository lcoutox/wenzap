import { DashboardShell } from "@/components/layout/DashboardShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <DashboardShell subscription={null} usage={null}>
      {children}
    </DashboardShell>
  );
}
