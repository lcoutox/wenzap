import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useUnreadAlertsCount() {
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCount = async () => {
      try {
        const response = await api.agentAlerts.listUnread();
        setCount(response.length);
      } catch {
        // Silent fail
      } finally {
        setLoading(false);
      }
    };

    fetchCount();
    // Refetch every 30s
    const interval = setInterval(fetchCount, 30000);

    return () => clearInterval(interval);
  }, []);

  return { count, loading };
}
