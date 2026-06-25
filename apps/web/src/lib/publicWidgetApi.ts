/**
 * Public widget API client — no Clerk token, uses X-Session-Token header.
 * Called exclusively from the /embed/widget/[publicKey] route.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

// ── Types ─────────────────────────────────────────────────────────────────────

export type PublicWidgetConfig = {
  public_key: string;
  name: string;
  theme: "dark" | "light" | "auto";
  primary_color: string;
  position: "bottom-right" | "bottom-left";
  welcome_message: string;
  header_title: string;
  header_subtitle: string;
  placeholder: string;
  avatar_url: string | null;
  auto_open: boolean;
  auto_open_delay_seconds: number;
};

export type WidgetMessage = {
  id: string;
  direction: string;
  sender_type: string;
  content: string;
  created_at: string;
};

// ── Fetch helper ──────────────────────────────────────────────────────────────

async function widgetFetch<T>(
  path: string,
  options: RequestInit = {},
  sessionToken?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(sessionToken ? { "X-Session-Token": sessionToken } : {}),
    ...(options.headers as Record<string, string>),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err.detail as string) ?? "API error");
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// ── Public widget API ─────────────────────────────────────────────────────────

export const publicWidgetApi = {
  getConfig: (publicKey: string) =>
    widgetFetch<PublicWidgetConfig>(`/public/widgets/${publicKey}/config`),

  createOrResumeSession: (publicKey: string, sessionToken?: string) =>
    widgetFetch<{ session_token: string }>(
      `/public/widgets/${publicKey}/sessions`,
      {
        method: "POST",
        body: JSON.stringify({ session_token: sessionToken ?? null }),
      },
    ),

  sendMessage: (publicKey: string, sessionToken: string, content: string) =>
    widgetFetch<WidgetMessage>(
      `/public/widgets/${publicKey}/messages`,
      { method: "POST", body: JSON.stringify({ content }) },
      sessionToken,
    ),

  listMessages: (publicKey: string, sessionToken: string) =>
    widgetFetch<WidgetMessage[]>(
      `/public/widgets/${publicKey}/messages`,
      {},
      sessionToken,
    ),
};
