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
  session_id: string;
  rag_used: boolean;
  retrieved_chunks_count: number;
};

// ── Playground Sessions ───────────────────────────────────────────────────────

export type PlaygroundMessage = {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  agent_test_run_id: string | null;
  created_at: string;
};

export type PlaygroundSession = {
  id: string;
  workspace_id: string;
  agent_id: string;
  user_id: string | null;
  title: string;
  created_at: string;
  updated_at: string;
};

export type PlaygroundSessionWithMessages = PlaygroundSession & {
  messages: PlaygroundMessage[];
};

// ── Knowledge Bases ───────────────────────────────────────────────────────────

export type KnowledgeBaseStatus = "active" | "inactive" | "archived";

export type KnowledgeBase = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: KnowledgeBaseStatus;
  created_by_user_id: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBaseCreateInput = {
  name: string;
  description?: string;
};

export type KnowledgeBaseUpdateInput = {
  name?: string;
  description?: string | null;
};

export type KnowledgeSourceStatus = "pending" | "processing" | "ready" | "failed" | "archived";
export type KnowledgeSourceType =
  | "manual_text"
  | "faq_qa"
  | "txt"
  | "markdown"
  | "pdf_simple"
  | "csv_simple";

export type KnowledgeSource = {
  id: string;
  workspace_id: string;
  knowledge_base_id: string;
  source_type: KnowledgeSourceType;
  title: string;
  content_text: string | null;
  status: KnowledgeSourceStatus;
  metadata_json: Record<string, unknown> | null;
  error_message: string | null;
  created_by_user_id: string | null;
  processed_at: string | null;
  created_at: string;
  updated_at: string;
  // File upload fields (null for manual_text / faq_qa sources)
  original_filename: string | null;
  mime_type: string | null;
  file_size_bytes: number | null;
  storage_provider: string | null;
  storage_key: string | null;
  content_hash: string | null;
};

export type QaPair = {
  question: string;
  answer: string;
};

export type KnowledgeSourceCreateInput = {
  source_type: KnowledgeSourceType;
  title: string;
  content_text?: string;
  metadata?: {
    source_category?: string;
    qa_pairs?: QaPair[];
  };
};

export type AgentKnowledgeBase = {
  id: string;
  workspace_id: string;
  agent_id: string;
  knowledge_base_id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  knowledge_base_name: string;
  knowledge_base_status: string;
};

// ── Inbox — Contacts ─────────────────────────────────────────────────────────

export type Contact = {
  id: string;
  workspace_id: string;
  name: string;
  email: string | null;
  phone: string | null;
  external_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ContactCreateInput = {
  name: string;
  email?: string;
  phone?: string;
  external_id?: string;
};

export type ContactUpdateInput = {
  name?: string;
  email?: string | null;
  phone?: string | null;
  external_id?: string | null;
};

// ── Inbox — Conversations ─────────────────────────────────────────────────────

export type ConversationStatus = "open" | "pending" | "resolved" | "archived";

export type ChannelType =
  | "internal"
  | "web_widget"
  | "whatsapp"
  | "instagram"
  | "email"
  | "api";

export type Conversation = {
  id: string;
  workspace_id: string;
  contact_id: string | null;
  contact_name: string | null;
  agent_id: string | null;
  assigned_user_id: string | null;
  channel_type: ChannelType;
  channel_external_id: string | null;
  status: ConversationStatus;
  ai_enabled: boolean;
  last_message_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ConversationCreateInput = {
  contact_id?: string;
  contact_name?: string;
  agent_id?: string;
  channel_type?: ChannelType;
  channel_external_id?: string;
  ai_enabled?: boolean;
};

export type ConversationUpdateInput = {
  status?: ConversationStatus;
  agent_id?: string | null;
  assigned_user_id?: string | null;
  ai_enabled?: boolean;
};

// ── Inbox — Messages ──────────────────────────────────────────────────────────

export type MessageDirection = "inbound" | "outbound" | "internal";
export type MessageSenderType = "customer" | "human" | "agent" | "system";

export type ConversationMessage = {
  id: string;
  workspace_id: string;
  conversation_id: string;
  direction: MessageDirection;
  sender_type: MessageSenderType;
  sender_user_id: string | null;
  agent_id: string | null;
  content: string;
  content_type: string;
  external_message_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
};

export type ConversationMessageCreateInput = {
  content: string;
  direction: MessageDirection;
  sender_type: MessageSenderType;
  sender_user_id?: string;
  agent_id?: string;
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

  // Handle 204 No Content (e.g. DELETE responses)
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
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
  contacts: {
    list: (token: string, params?: { skip?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.skip != null) qs.set("skip", String(params.skip));
      if (params?.limit != null) qs.set("limit", String(params.limit));
      const q = qs.toString();
      return apiFetch<Contact[]>(q ? `/contacts?${q}` : "/contacts", token);
    },
    get: (token: string, contactId: string) =>
      apiFetch<Contact>(`/contacts/${contactId}`, token),
    create: (token: string, data: ContactCreateInput) =>
      apiFetch<Contact>("/contacts", token, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (token: string, contactId: string, data: ContactUpdateInput) =>
      apiFetch<Contact>(`/contacts/${contactId}`, token, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
  conversations: {
    list: (token: string, params?: { status?: string; skip?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      if (params?.skip != null) qs.set("skip", String(params.skip));
      if (params?.limit != null) qs.set("limit", String(params.limit));
      const q = qs.toString();
      return apiFetch<Conversation[]>(q ? `/conversations?${q}` : "/conversations", token);
    },
    get: (token: string, conversationId: string) =>
      apiFetch<Conversation>(`/conversations/${conversationId}`, token),
    create: (token: string, data: ConversationCreateInput) =>
      apiFetch<Conversation>("/conversations", token, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (token: string, conversationId: string, data: ConversationUpdateInput) =>
      apiFetch<Conversation>(`/conversations/${conversationId}`, token, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    messages: {
      list: (
        token: string,
        conversationId: string,
        params?: { skip?: number; limit?: number },
      ) => {
        const qs = new URLSearchParams();
        if (params?.skip != null) qs.set("skip", String(params.skip));
        if (params?.limit != null) qs.set("limit", String(params.limit));
        const q = qs.toString();
        return apiFetch<ConversationMessage[]>(
          q
            ? `/conversations/${conversationId}/messages?${q}`
            : `/conversations/${conversationId}/messages`,
          token,
        );
      },
      create: (
        token: string,
        conversationId: string,
        data: ConversationMessageCreateInput,
      ) =>
        apiFetch<ConversationMessage>(
          `/conversations/${conversationId}/messages`,
          token,
          { method: "POST", body: JSON.stringify(data) },
        ),
    },
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
    test: (token: string, id: string, message: string, sessionId?: string) =>
      apiFetch<AgentTestResponse>(`/agents/${id}/test`, token, {
        method: "POST",
        body: JSON.stringify({ message, ...(sessionId ? { session_id: sessionId } : {}) }),
      }),
    knowledgeBases: {
      list: (token: string, agentId: string) =>
        apiFetch<AgentKnowledgeBase[]>(`/agents/${agentId}/knowledge-bases`, token),
      connect: (token: string, agentId: string, kbId: string) =>
        apiFetch<AgentKnowledgeBase>(`/agents/${agentId}/knowledge-bases`, token, {
          method: "POST",
          body: JSON.stringify({ knowledge_base_id: kbId }),
        }),
      update: (token: string, agentId: string, kbId: string, data: { is_active: boolean }) =>
        apiFetch<AgentKnowledgeBase>(`/agents/${agentId}/knowledge-bases/${kbId}`, token, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      disconnect: (token: string, agentId: string, kbId: string) =>
        apiFetch<void>(`/agents/${agentId}/knowledge-bases/${kbId}`, token, {
          method: "DELETE",
        }),
    },
    playground: {
      listSessions: (token: string, agentId: string) =>
        apiFetch<PlaygroundSession[]>(`/agents/${agentId}/playground/sessions`, token),
      createSession: (token: string, agentId: string) =>
        apiFetch<PlaygroundSession>(`/agents/${agentId}/playground/sessions`, token, {
          method: "POST",
          body: JSON.stringify({}),
        }),
      getSession: (token: string, agentId: string, sessionId: string) =>
        apiFetch<PlaygroundSessionWithMessages>(
          `/agents/${agentId}/playground/sessions/${sessionId}`,
          token,
        ),
      deleteSession: (token: string, agentId: string, sessionId: string) =>
        apiFetch<void>(`/agents/${agentId}/playground/sessions/${sessionId}`, token, {
          method: "DELETE",
        }),
    },
  },
  knowledgeBases: {
    list: (token: string) => apiFetch<KnowledgeBase[]>("/knowledge-bases", token),
    create: (token: string, data: KnowledgeBaseCreateInput) =>
      apiFetch<KnowledgeBase>("/knowledge-bases", token, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    get: (token: string, kbId: string) =>
      apiFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`, token),
    update: (token: string, kbId: string, data: KnowledgeBaseUpdateInput) =>
      apiFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`, token, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    archive: (token: string, kbId: string) =>
      apiFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`, token, { method: "DELETE" }),
    sources: {
      list: (token: string, kbId: string) =>
        apiFetch<KnowledgeSource[]>(`/knowledge-bases/${kbId}/sources`, token),
      create: (token: string, kbId: string, data: KnowledgeSourceCreateInput) =>
        apiFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources`, token, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      get: (token: string, kbId: string, sourceId: string) =>
        apiFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources/${sourceId}`, token),
      archive: (token: string, kbId: string, sourceId: string) =>
        apiFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources/${sourceId}`, token, {
          method: "DELETE",
        }),
      reprocess: (token: string, kbId: string, sourceId: string) =>
        apiFetch<KnowledgeSource>(
          `/knowledge-bases/${kbId}/sources/${sourceId}/reprocess`,
          token,
          { method: "POST" },
        ),
      upload: async (
        token: string,
        kbId: string,
        file: File,
        data?: { title?: string; source_category?: string },
      ): Promise<KnowledgeSource> => {
        const form = new FormData();
        form.append("file", file);
        if (data?.title?.trim()) form.append("title", data.title.trim());
        if (data?.source_category?.trim())
          form.append("source_category", data.source_category.trim());
        // Do NOT set Content-Type — browser must set the multipart boundary automatically.
        const res = await fetch(`${API_URL}/knowledge-bases/${kbId}/sources/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: form,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new ApiError(res.status, err.detail ?? "API error");
        }
        return res.json() as Promise<KnowledgeSource>;
      },
    },
  },
};
