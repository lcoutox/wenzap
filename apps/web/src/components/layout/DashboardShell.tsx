"use client";

import { useState, useEffect, useCallback } from "react";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { UserMenuDropdown } from "./UserMenuDropdown";
import type { Subscription, Usage } from "@/lib/api";

const STORAGE_KEY = "nexbrain:sidebar-collapsed";

const BREADCRUMBS: Record<string, string> = {
  "/dashboard":          "Dashboard",
  "/dashboard/agents":   "Agentes",
  "/dashboard/members":  "Membros",
  "/dashboard/settings": "Configurações",
  "/dashboard/plan":     "Plano e uso",
};

function getBreadcrumb(pathname: string): string {
  // Exact match first
  if (BREADCRUMBS[pathname]) return BREADCRUMBS[pathname];
  // Prefix match for nested routes (e.g. /dashboard/agents/new)
  const match = Object.keys(BREADCRUMBS)
    .filter((k) => k !== "/dashboard" && pathname.startsWith(k))
    .sort((a, b) => b.length - a.length)[0];
  return match ? BREADCRUMBS[match] : "Dashboard";
}

export function DashboardShell({
  children,
  subscription,
  usage,
}: {
  children: React.ReactNode;
  subscription: Subscription | null;
  usage: Usage | null;
}) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Read localStorage after mount to avoid SSR mismatch
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored !== null) setCollapsed(stored === "true");
    } catch {}
    setMounted(true);
  }, []);

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEY, String(next));
      } catch {}
      return next;
    });
  }, []);

  // Avoid layout shift: render collapsed=false until mounted
  const effectiveCollapsed = mounted ? collapsed : false;

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar
        collapsed={effectiveCollapsed}
        subscription={subscription}
        usage={usage}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header — h-14 matches sidebar logo area */}
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 gap-4 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={toggle}
              className="p-1.5 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700 transition-colors"
              aria-label={effectiveCollapsed ? "Expandir sidebar" : "Colapsar sidebar"}
            >
              {effectiveCollapsed ? (
                <PanelLeftOpen className="w-4.5 h-4.5" />
              ) : (
                <PanelLeftClose className="w-4.5 h-4.5" />
              )}
            </button>
            <span className="text-sm font-semibold text-gray-700">
              {getBreadcrumb(pathname)}
            </span>
          </div>

          <UserMenuDropdown />
        </header>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
