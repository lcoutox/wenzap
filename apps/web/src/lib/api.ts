const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Domain types ──────────────────────────────────────────────────────────────

export type MemberRole = "owner" | "admin" | "member" | "viewer";
export type MemberStatus = "active" | "inactive";
export type WorkspaceStatus = "active" | "suspended" | "deleted";
export type SubscriptionStatus = "active" | "canceled" | "past_due";

export type UserMe = {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: MemberRole;
  workspace: {
    id: string;
    name: string;
    slug: string;
    status: WorkspaceStatus;
  };
};

export type Member = {
  id: string;
  user_id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: MemberRole;
  status: MemberStatus;
};

export type Plan = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  monthly_price_cents: number;
  currency: string;
  agents_limit: number;
  knowledge_bases_limit: number;
  users_limit: number;
  pipelines_limit: number;
  integrations_limit: number;
  monthly_ai_credits: number;
  monthly_conversations: number;
};

export type Subscription = {
  plan: Plan;
  status: SubscriptionStatus;
  current_period_start: string;
  current_period_end: string;
};

export type Usage = {
  ai_credits_used: number;
  conversations_count: number;
  messages_count: number;
  period_start: string;
  period_end: string;
};

// ── AI Model Catalog ──────────────────────────────────────────────────────────

export type AiModel = {
  id: string;
  code: string;
  display_name: string;
  description: string | null;
  model_name: string;
  credits_per_message: number;
  min_plan_code: string;
  context_window_tokens: number | null;
  is_default: boolean;
  is_recommended: boolean;
  is_featured: boolean;
  available: boolean;
  supports_vision: boolean;
  supports_tools: boolean;
  supports_reasoning: boolean;
  supports_code: boolean;
};

export type AiProvider = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  models: AiModel[];
};

export type AiCatalog = {
  current_plan: string;
  providers: AiProvider[];
};

// ── Agents ────────────────────────────────────────────────────────────────────

export type AgentStatus = "draft" | "active" | "inactive" | "archived";

export type Agent = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: AgentStatus;
  system_prompt: string | null;
  persona: string | null;
  ai_model_id: string | null;
  model_name: string;
  temperature: number;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AgentCreateInput = {
  name: string;
  description?: string;
  system_prompt?: string;
  persona?: string;
  ai_model_id: string;
  temperature?: number;
};

export type AgentUpdateInput = {
  name?: string;
  description?: string | null;
  system_prompt?: string | null;
  persona?: string | null;
  ai_model_id?: string;
  temperature?: number;
};

export type AgentStatusUpdateInput = {
  status: AgentStatus;
};

export type AgentTestModelInfo = {
  display_name: string;
  provider: string;
  model_name: string;
};

export type AgentTestResponse = {
  reply: string;
  credits_used: number;
  input_tokens: number;
  output_tokens: number;
  duration_ms: number;
  model: AgentTestModelInfo;
};

// ── Errors ────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Fetch helper ──────────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail ?? "API error");
  }

  return res.json() as Promise<T>;
}

// ── API client ────────────────────────────────────────────────────────────────

export const api = {
  me: (token: string) => apiFetch<UserMe>("/me", token),
  workspace: {
    current: (token: string) => apiFetch<UserMe["workspace"]>("/workspaces/current", token),
    update: (token: string, data: { name?: string; slug?: string }) =>
      apiFetch<UserMe["workspace"]>("/workspaces/current", token, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
  members: {
    list: (token: string) => apiFetch<Member[]>("/workspaces/current/members", token),
    updateRole: (token: string, memberId: string, role: MemberRole) =>
      apiFetch<Member>(`/workspaces/current/members/${memberId}/role`, token, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
  },
  plans: {
    list: (token: string) => apiFetch<Plan[]>("/plans", token),
    current: (token: string) => apiFetch<Subscription>("/workspaces/current/plan", token),
    usage: (token: string) => apiFetch<Usage>("/workspaces/current/usage", token),
  },
  aiModels: {
    list: (token: string) => apiFetch<AiCatalog>("/ai-models", token),
  },
  agents: {
    list: (token: string, status?: AgentStatus) =>
      apiFetch<Agent[]>(status ? `/agents?status=${status}` : "/agents", token),
    get: (token: string, id: string) => apiFetch<Agent>(`/agents/${id}`, token),
    create: (token: string, data: AgentCreateInput) =>
      apiFetch<Agent>("/agents", token, { method: "POST", body: JSON.stringify(data) }),
    update: (token: string, id: string, data: AgentUpdateInput) =>
      apiFetch<Agent>(`/agents/${id}`, token, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    updateStatus: (token: string, id: string, status: AgentStatus) =>
      apiFetch<Agent>(`/agents/${id}/status`, token, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    archive: (token: string, id: string) =>
      apiFetch<Agent>(`/agents/${id}`, token, { method: "DELETE" }),
    test: (token: string, id: string, message: string) =>
      apiFetch<AgentTestResponse>(`/agents/${id}/test`, token, {
        method: "POST",
        body: JSON.stringify({ message }),
      }),
  },
};
