"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  Users,
  Settings,
  CreditCard,
  TrendingUp,
  Zap,
} from "lucide-react";
import type { Subscription, Usage } from "@/lib/api";

const nav = [
  { href: "/dashboard",          label: "Dashboard",      icon: LayoutDashboard },
  { href: "/dashboard/agents",   label: "Agentes",        icon: Bot },
  { href: "/dashboard/members",  label: "Membros",        icon: Users },
  { href: "/dashboard/settings", label: "Configurações",  icon: Settings },
  { href: "/dashboard/plan",     label: "Plano e uso",    icon: CreditCard },
];

// ── Plan card ────────────────────────────────────────────────────────────────

function PlanCard({
  collapsed,
  subscription,
  usage,
}: {
  collapsed: boolean;
  subscription: Subscription | null;
  usage: Usage | null;
}) {
  const plan = subscription?.plan;
  const creditsUsed = usage?.ai_credits_used ?? 0;
  const creditsTotal = plan?.monthly_ai_credits ?? 1;
  const pct = Math.min(100, Math.round((creditsUsed / creditsTotal) * 100));

  if (collapsed) {
    return (
      <div className="px-3 pb-4">
        <div
          title={plan ? `${plan.name} — ${pct}% de créditos usados` : "Sem plano ativo"}
          className="flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-600/10 border border-indigo-500/20 cursor-default mx-auto"
        >
          <Zap className="w-4 h-4 text-indigo-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-3 mb-4 p-3 rounded-lg bg-gray-800/60 border border-gray-700/60">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-300">
          {plan?.name ?? "Sem plano"}
        </span>
        <TrendingUp className="w-3.5 h-3.5 text-gray-500" />
      </div>

      {plan && (
        <>
          <div className="mb-1.5">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Créditos IA</span>
              <span>{creditsUsed.toLocaleString()} / {creditsTotal.toLocaleString()}</span>
            </div>
            <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-500 rounded-full transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        </>
      )}

      <Link
        href="/dashboard/plan"
        className="mt-2 flex items-center justify-center gap-1 w-full py-1.5 rounded text-xs font-medium bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 transition-colors"
      >
        <Zap className="w-3 h-3" />
        Upgrade
      </Link>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export function Sidebar({
  collapsed,
  subscription,
  usage,
}: {
  collapsed: boolean;
  subscription: Subscription | null;
  usage: Usage | null;
}) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(href);

  return (
    <aside
      className={`
        flex flex-col min-h-screen bg-gray-900 border-r border-gray-800 transition-all duration-200
        ${collapsed ? "w-14" : "w-56"}
      `}
    >
      {/* Logo — same height as header (h-14) */}
      <div className="h-14 flex items-center border-b border-gray-800 flex-shrink-0 overflow-hidden">
        {collapsed ? (
          <div className="flex items-center justify-center w-14">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold text-xs">N</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-4">
            <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-xs">N</span>
            </div>
            <span className="font-bold text-base tracking-tight text-white">Nexbrain</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`
                flex items-center gap-3 px-2 py-2 rounded-md text-sm font-medium transition-colors
                ${collapsed ? "justify-center" : ""}
                ${
                  active
                    ? "bg-indigo-600/15 text-indigo-400"
                    : "text-gray-400 hover:bg-gray-800 hover:text-gray-100"
                }
              `}
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Plan card */}
      <PlanCard collapsed={collapsed} subscription={subscription} usage={usage} />
    </aside>
  );
}
