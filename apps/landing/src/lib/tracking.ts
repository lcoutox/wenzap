"use client";

const UTM_PARAMS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;
const STORAGE_KEY = "wenzap:landing_utms";

export function captureUTMs() {
  if (typeof window === "undefined") return;
  try {
    const params = new URLSearchParams(window.location.search);
    const existing = readUTMs();
    const captured: Record<string, string> = { ...existing };
    let changed = false;

    for (const key of UTM_PARAMS) {
      const val = params.get(key);
      if (val && !captured[key]) {
        captured[key] = val;
        changed = true;
      }
    }

    if (!captured.referrer && document.referrer) {
      captured.referrer = document.referrer;
      changed = true;
    }

    if (!captured.landing_path) {
      captured.landing_path = window.location.pathname + window.location.search;
      changed = true;
    }

    if (!captured.first_seen_at) {
      captured.first_seen_at = new Date().toISOString();
      changed = true;
    }

    if (changed) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(captured));
    }
  } catch {
    // Ignore storage errors (private browsing, etc.)
  }
}

export function readUTMs(): Record<string, string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function trackLandingEvent(eventName: string, properties?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  const utms = readUTMs();
  const payload = { event: eventName, ...utms, ...properties };
  if (process.env.NODE_ENV === "development") {
    console.info("[wenzap:track]", payload);
  }
  // Future: send to Plausible / PostHog / etc.
}
