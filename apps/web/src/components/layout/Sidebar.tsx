"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { APP_VERSION } from "@/lib/version";
import {
  LayoutDashboard,
  Bot,
  MessageSquare,
  Settings,
  TrendingUp,
  Zap,
  BookOpen,
  Package,
  Users,
} from "lucide-react";
import type { Subscription, Usage } from "@/lib/api";

function WenzapIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 270 270" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Chat bubble outline */}
      <path
        d="M 18,32 6,53 1,71 l -1,82 4,20 9,18 15,17 15,10 -5,26 1,7 4,5 4,2 h 9 l 60,-31 h 81 l 13,-3 24,-12 18,-18 8,-14 6,-19 1,-85 L 264,60 257,43 248,30 232,15 216,6 193,0 H 75 L 57,4 40,12 28,21 Z m 19,13 9,-9 9,-6 12,-5 10,-2 h 114 l 16,4 11,6 12,11 7,10 7,23 v 76 l -4,15 -8,14 -14,13 -17,8 -12,2 h -79 l -45,22 -1,-5 2,-7 V 204 L 46,193 36,183 27,168 24,158 23,81 27,62 Z"
        fill="#00E09A"
        fillRule="evenodd"
      />
      {/* W letter */}
      <path
        d="m 62,76 -2,4 v 6 l 27,73 9,6 h 11 l 8,-5 12,-31 6,-11 3,1 16,41 8,5 h 12 l 4,-2 7,-10 24,-67 -1,-8 -5,-5 -10,-1 -4,2 -4,6 -15,46 -2,3 h -2 l -18,-47 -8,-6 -11,1 -7,7 -15,43 -4,1 -17,-48 -3,-5 -5,-3 h -8 z"
        fill="#00E09A"
        fillRule="evenodd"
      />
    </svg>
  );
}

const nav = [
  { href: "/dashboard",               label: "Visão geral",  icon: LayoutDashboard },
  { href: "/dashboard/inbox",         label: "Inbox",        icon: MessageSquare },
  { href: "/dashboard/agents",        label: "Agentes",      icon: Bot },
  { href: "/dashboard/knowledge-bases", label: "Conhecimento", icon: BookOpen },
  { href: "/dashboard/catalog",        label: "Catálogo",     icon: Package  },
  { href: "/dashboard/contacts",       label: "Clientes",     icon: Users    },
  { href: "/dashboard/settings",       label: "Configurações", icon: Settings },
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
  const plan         = subscription?.plan;
  const creditsUsed  = usage?.ai_credits_used ?? 0;
  const creditsTotal = plan?.monthly_ai_credits ?? 1;
  const pct          = Math.min(100, Math.round((creditsUsed / creditsTotal) * 100));

  const barColor     = pct >= 90 ? "bg-nb-danger" : pct >= 70 ? "bg-nb-warning" : "bg-nb-primary";
  const isExhausted  = pct >= 100;
  const isWarning    = pct >= 70 && pct < 100;

  if (collapsed) {
    return (
      <div className="px-3 pb-4">
        <div
          title={plan ? `${plan.name} — ${pct}% de créditos usados` : "Sem plano ativo"}
          className={`flex items-center justify-center w-8 h-8 rounded-lg border cursor-default mx-auto ${
            isExhausted ? "bg-nb-danger/10 border-nb-danger/30" :
            isWarning   ? "bg-nb-warning/10 border-nb-warning/30" :
                          "bg-nb-primary-bg border-nb-primary/20"
          }`}
        >
          <Zap className={`w-4 h-4 ${isExhausted ? "text-nb-danger" : isWarning ? "text-nb-warning" : "text-nb-primary"}`} />
        </div>
      </div>
    );
  }

  return (
    <div className={`mx-3 mb-4 p-3 rounded-xl border ${
      isExhausted ? "bg-nb-danger/5 border-nb-danger/20" :
      isWarning   ? "bg-nb-warning/5 border-nb-warning/20" :
                    "bg-nb-elevated border-nb-border"
    }`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-nb-secondary truncate">
          {plan?.name ?? "Sem plano"}
        </span>
        <TrendingUp className="w-3.5 h-3.5 text-nb-muted flex-shrink-0" />
      </div>

      {plan && (
        <div className="mb-2">
          <div className="flex justify-between text-[10px] mb-1">
            <span className="text-nb-muted">Créditos IA</span>
            {isExhausted
              ? <span className="text-nb-danger font-semibold">Esgotado</span>
              : <span className="text-nb-muted">{creditsUsed.toLocaleString("pt-BR")} / {creditsTotal.toLocaleString("pt-BR")}</span>
            }
          </div>
          <div className="h-1 bg-nb-border rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
          </div>
          {isWarning && (
            <p className="text-[10px] text-nb-warning mt-1">Perto do limite de créditos.</p>
          )}
        </div>
      )}

      <Link
        href="/dashboard/plan"
        className={`mt-1 flex items-center justify-center gap-1 w-full py-1.5 rounded-lg text-xs font-medium transition-colors ${
          isExhausted
            ? "bg-nb-danger/10 text-nb-danger border border-nb-danger/20 hover:bg-nb-danger/20"
            : "bg-nb-primary-bg text-nb-primary-strong hover:bg-nb-primary/20"
        }`}
      >
        <Zap className="w-3 h-3" />
        {isExhausted ? "Créditos esgotados" : "Upgrade"}
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
            <WenzapIcon size={28} />
          </div>
        ) : (
          <div className="flex items-center gap-2.5 px-4">
            <WenzapIcon size={28} />
            <span className="font-bold text-sm tracking-tight text-nb-text">Wenzap</span>
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

      {/* Version */}
      {!collapsed && (
        <p className="pb-3 text-center text-[10px] text-nb-muted select-none">
          v{APP_VERSION}
        </p>
      )}
    </aside>
  );
}
