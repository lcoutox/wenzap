"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Bot,
  MessageSquare,
  Settings,
  TrendingUp,
  Zap,
  BookOpen,
} from "lucide-react";
import type { Subscription, Usage } from "@/lib/api";

const nav = [
  { href: "/dashboard",               label: "Visão geral",  icon: LayoutDashboard },
  { href: "/dashboard/inbox",         label: "Inbox",        icon: MessageSquare },
  { href: "/dashboard/agents",        label: "Agentes",      icon: Bot },
  { href: "/dashboard/knowledge-bases", label: "Conhecimento", icon: BookOpen },
  { href: "/dashboard/settings",      label: "Configurações", icon: Settings },
];

// ── Plan card ─────────────────────────────────────────────────────────────────

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
  const creditsUsed  = usage?.ai_credits_used ?? 0;
  const creditsTotal = plan?.monthly_ai_credits ?? 1;
  const pct = Math.min(100, Math.round((creditsUsed / creditsTotal) * 100));

  if (collapsed) {
    return (
      <div className="px-3 pb-4">
        <div
          title={plan ? `${plan.name} — ${pct}% de créditos usados` : "Sem plano ativo"}
          className="flex items-center justify-center w-8 h-8 rounded-lg bg-nb-primary-bg border border-nb-primary/20 cursor-default mx-auto"
        >
          <Zap className="w-4 h-4 text-nb-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-3 mb-4 p-3 rounded-xl bg-nb-elevated border border-nb-border">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-nb-secondary truncate">
          {plan?.name ?? "Sem plano"}
        </span>
        <TrendingUp className="w-3.5 h-3.5 text-nb-muted flex-shrink-0" />
      </div>

      {plan && (
        <div className="mb-2">
          <div className="flex justify-between text-[10px] text-nb-muted mb-1">
            <span>Créditos IA</span>
            <span>{creditsUsed.toLocaleString()} / {creditsTotal.toLocaleString()}</span>
          </div>
          <div className="h-1 bg-nb-border rounded-full overflow-hidden">
            <div
              className="h-full bg-nb-primary rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}

      <Link
        href="/dashboard/plan"
        className="mt-1 flex items-center justify-center gap-1 w-full py-1.5 rounded-lg text-xs font-medium bg-nb-primary-bg text-nb-primary-strong hover:bg-nb-primary/20 transition-colors"
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

  // Routes absorbed into Configurações (no longer in the nav array).
  const SETTINGS_SUBROUTES = ["/dashboard/members", "/dashboard/plan"];

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    if (href === "/dashboard/settings" && SETTINGS_SUBROUTES.some((r) => pathname.startsWith(r))) return true;
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={`
        flex flex-col h-screen bg-nb-surface border-r border-nb-border
        transition-all duration-200 overflow-hidden flex-shrink-0
        ${collapsed ? "w-14" : "w-56"}
      `}
    >
      {/* Brand mark */}
      <div className="h-14 flex items-center border-b border-nb-border flex-shrink-0 overflow-hidden">
        {collapsed ? (
          <div className="flex items-center justify-center w-14">
            <div className="w-7 h-7 rounded-lg bg-nb-primary flex items-center justify-center">
              <span className="text-white font-bold text-xs tracking-tight">N</span>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2.5 px-4">
            <div className="w-7 h-7 rounded-lg bg-nb-primary flex items-center justify-center flex-shrink-0">
              <span className="text-white font-bold text-xs tracking-tight">N</span>
            </div>
            <span className="font-bold text-sm tracking-tight text-nb-text">Nexbrain</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-0.5 px-2 overflow-y-auto">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`
                relative flex items-center gap-3 px-2 py-2 rounded-lg text-sm font-medium transition-colors
                ${collapsed ? "justify-center" : ""}
                ${active
                  ? "bg-nb-primary-bg text-nb-primary-strong"
                  : "text-nb-muted hover:bg-nb-elevated hover:text-nb-secondary"}
              `}
            >
              {/* Active indicator bar */}
              {active && !collapsed && (
                <span className="absolute left-0 inset-y-1.5 w-0.5 bg-nb-primary rounded-full" />
              )}
              <Icon className={`w-4 h-4 flex-shrink-0 ${active ? "text-nb-primary-strong" : ""}`} />
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
