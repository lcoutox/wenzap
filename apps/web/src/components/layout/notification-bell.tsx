"use client";

import { useState, useRef, useEffect } from "react";
import { Bell, X } from "lucide-react";
import { useUnreadAlertsCount } from "@/hooks/use-unread-alerts-count";
import { api } from "@/lib/api";
import type { AgentAlert } from "@/lib/api";

export function NotificationBell() {
  const { count: unreadCount } = useUnreadAlertsCount();
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState<AgentAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const fetchAlerts = async () => {
    setLoading(true);
    try {
      const response = await api.agentAlerts.listUnread();
      setAlerts(response);
    } catch {
      // Silent fail
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchAlerts();
    }
  }, [open]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  const handleDismiss = async (alertId: string) => {
    try {
      await api.agentAlerts.markAsRead(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch {
      // Ignore
    }
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-1.5 rounded-md text-nb-muted hover:bg-nb-elevated hover:text-nb-secondary transition-colors"
        aria-label="Notificações"
      >
        <Bell className="w-4.5 h-4.5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex items-center justify-center w-5 h-5 rounded-full bg-nb-danger text-white text-xs font-bold">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 mt-2 w-80 rounded-xl border border-nb-border bg-nb-panel shadow-lg overflow-hidden z-50">
          <div className="p-3 border-b border-nb-border">
            <h3 className="text-sm font-semibold text-nb-text">Alertas de agentes</h3>
          </div>

          <div className="max-h-96 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-xs text-nb-muted">
                Carregando...
              </div>
            ) : alerts.length === 0 ? (
              <div className="p-4 text-center text-xs text-nb-muted">
                Sem alertas
              </div>
            ) : (
              alerts.map((alert) => (
                <div
                  key={alert.id}
                  className="p-3 border-b border-nb-border/30 last:border-0 hover:bg-nb-elevated/30 transition-colors"
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-nb-text">
                        Agente indisponível
                      </p>
                      <p className="text-xs text-nb-muted mt-0.5 leading-relaxed">
                        {alert.error_message_user}
                      </p>
                      <p className="text-xs text-nb-muted/60 mt-1">
                        {new Date(alert.created_at).toLocaleString("pt-BR")}
                      </p>
                    </div>
                    <button
                      onClick={() => handleDismiss(alert.id)}
                      className="flex-shrink-0 text-nb-muted hover:text-nb-text transition-colors p-0.5"
                      aria-label="Descartar"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
