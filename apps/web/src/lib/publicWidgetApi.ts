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
  contact_capture_enabled: boolean;
  require_name: boolean;
  require_email: boolean;
  require_phone: boolean;
};

export type WidgetSessionResult = {
  session_token: string;
  contact_captured: boolean;
};

export type WidgetMessage = {
  id: string;
  direction: string;
  sender_type: string;
  content: string;
  created_at: string;
};

export type ContactCaptureData = {
  name?: string;
  email?: string;
  phone?: string;
};

export type WidgetPageContext = {
  page_url?: string | null;
  page_title?: string | null;
  referrer?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_term?: string | null;
  utm_content?: string | null;
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

  createOrResumeSession: (
    publicKey: string,
    sessionToken?: string,
    pageContext?: WidgetPageContext,
  ) =>
    widgetFetch<WidgetSessionResult>(
      `/public/widgets/${publicKey}/sessions`,
      {
        method: "POST",
        body: JSON.stringify({
          session_token: sessionToken ?? null,
          page_context: pageContext ?? null,
        }),
      },
    ),

  updateContact: (publicKey: string, sessionToken: string, data: ContactCaptureData) =>
    widgetFetch<void>(
      `/public/widgets/${publicKey}/session/contact`,
      { method: "PATCH", body: JSON.stringify(data) },
      sessionToken,
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
