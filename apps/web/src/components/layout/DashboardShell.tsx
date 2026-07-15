"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { UserMenuDropdown } from "./UserMenuDropdown";
import { NotificationBell } from "./notification-bell";
import { useAppAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";
import type { Subscription, Usage } from "@/lib/api";

const STORAGE_KEY = "wenzap:sidebar-collapsed";

const BREADCRUMBS: Record<string, string> = {
  "/dashboard":                 "Visão geral",
  "/dashboard/agents":          "Agentes",
  "/dashboard/inbox":           "Inbox",
  "/dashboard/knowledge-bases": "Conhecimento",
  "/dashboard/contacts":        "Clientes",
  "/dashboard/pipeline":        "Pipeline",
  "/dashboard/members":         "Membros",
  "/dashboard/settings":        "Configurações",
  "/dashboard/plan":            "Plano e uso",
};

function getBreadcrumb(pathname: string): string {
  if (BREADCRUMBS[pathname]) return BREADCRUMBS[pathname];
  const match = Object.keys(BREADCRUMBS)
    .filter((k) => k !== "/dashboard" && pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  return match ? BREADCRUMBS[match] : "Dashboard";
}

export function DashboardShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { isLoaded, isSignedIn, user } = useAppAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored !== null) setCollapsed(stored === "true");
    } catch {}
    setMounted(true);
  }, []);

  useEffect(() => {
    api.plans.current().then(setSubscription).catch(() => {});
    api.plans.usage().then(setUsage).catch(() => {});
  }, []);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
    } else if (user && !user.email_verified) {
      router.replace("/verify-email-required");
    }
  }, [isLoaded, isSignedIn, user, router]);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem(STORAGE_KEY, String(next)); } catch {}
      return next;
    });
  }, []);

  const effectiveCollapsed = mounted ? collapsed : false;

  if (isLoaded && (!isSignedIn || (user && !user.email_verified))) {
    return null;
  }

  return (
    <div className="h-screen overflow-hidden flex bg-nb-bg">
      <Sidebar collapsed={effectiveCollapsed} subscription={subscription} usage={usage} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Topbar — h-14, dark surface */}
        <header className="h-14 bg-nb-surface border-b border-nb-border flex items-center justify-between px-4 gap-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={toggle}
              className="p-1.5 rounded-md text-nb-muted hover:bg-nb-elevated hover:text-nb-secondary transition-colors"
              aria-label={effectiveCollapsed ? "Expandir sidebar" : "Colapsar sidebar"}
            >
              {effectiveCollapsed ? (
                <PanelLeftOpen className="w-4.5 h-4.5" />
              ) : (
                <PanelLeftClose className="w-4.5 h-4.5" />
              )}
            </button>
            <span className="text-sm font-semibold text-nb-secondary tracking-wide">
              {getBreadcrumb(pathname)}
            </span>
          </div>

          <div className="flex items-center gap-1">
            <NotificationBell />
            <UserMenuDropdown />
          </div>
        </header>

        {/* Content area */}
        <main className="flex-1 overflow-y-auto p-6 bg-nb-bg">{children}</main>
      </div>
    </div>
  );
}
