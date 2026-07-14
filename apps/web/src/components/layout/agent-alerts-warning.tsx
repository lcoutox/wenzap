"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";
import { api } from "@/lib/api";

interface AgentAlert {
  id: string;
  agent_id: string;
  conversation_id: string;
  error_code: string;
  error_message_user: string;
  is_read: boolean;
  created_at: string;
}

export function AgentAlertsWarning() {
  const [alerts, setAlerts] = useState<AgentAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const response = await api.agentAlerts.listUnread();
        setAlerts(response);
      } catch {
        // Silent fail — alerts are nice-to-have, not critical
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading || !visible || alerts.length === 0) {
    return null;
  }

  const handleClose = () => setVisible(false);

  const handleDismiss = async (alertId: string) => {
    try {
      await api.agentAlerts.markAsRead(alertId);
      setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    } catch {
      // Ignore error
    }
  };

  return (
    <div className="flex flex-col gap-2">
      {alerts.slice(0, 3).map((alert) => (
        <div
          key={alert.id}
          className="flex items-start gap-3 p-3.5 rounded-xl border border-nb-danger/30 bg-nb-danger/5"
        >
          <AlertTriangle className="w-4 h-4 text-nb-danger flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-nb-text">Agente indisponível</p>
            <p className="text-xs text-nb-muted mt-0.5">{alert.error_message_user}</p>
          </div>
          <button
            onClick={() => handleDismiss(alert.id)}
            className="flex-shrink-0 text-nb-muted hover:text-nb-text transition-colors"
            aria-label="Fechar alerta"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      ))}
      {alerts.length > 3 && (
        <p className="text-xs text-nb-muted text-center">
          +{alerts.length - 3} agentes com problemas
        </p>
      )}
    </div>
  );
}
