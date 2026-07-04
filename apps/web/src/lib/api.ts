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
  catalog_items_limit: number;
  channels_limit: number;
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
  // Metered (reset monthly)
  ai_credits_used: number;
  conversations_count: number;
  messages_count: number;
  // Resource snapshots
  agents_count: number;
  knowledge_bases_count: number;
  catalog_items_count: number;
  channels_count: number;
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
export type ResponseStyle = "concise" | "balanced" | "detailed";
export type LanguageMode = "auto" | "pt" | "en" | "es";
export type InstructionsMode = "guided" | "advanced";
export type ContextTier = "economical" | "standard" | "broad" | "advanced" | "maximum";

export const CONTEXT_TIERS: {
  code: ContextTier;
  label: string;
  description: string;
  maxChars: number;
  creditMultiplier: number;
}[] = [
  { code: "economical", label: "Econômico",  description: "Menor custo. Ideal para conversas simples e respostas rápidas.",                            maxChars: 6_000,   creditMultiplier: 1  },
  { code: "standard",   label: "Padrão",     description: "Recomendado para a maioria dos agentes. Equilibra custo e contexto.",                       maxChars: 15_000,  creditMultiplier: 2  },
  { code: "broad",      label: "Amplo",      description: "Considera mais histórico e informações conectadas.",                                         maxChars: 25_000,  creditMultiplier: 4  },
  { code: "advanced",   label: "Avançado",   description: "Indicado para conversas longas, bases maiores e atendimentos mais complexos.",               maxChars: 35_000,  creditMultiplier: 8  },
  { code: "maximum",    label: "Máximo",     description: "Maior contexto disponível. Alto consumo de créditos.",                                       maxChars: 300_000, creditMultiplier: 16 },
];

export const CONTEXT_TIER_PLAN_LIMITS: Record<string, ContextTier[]> = {
  starter:    ["economical", "standard"],
  growth:     ["economical", "standard", "broad", "advanced"],
  scale:      ["economical", "standard", "broad", "advanced", "maximum"],
  enterprise: ["economical", "standard", "broad", "advanced", "maximum"],
};

export type GuidedRole =
  | "initial_support"
  | "consultive_sales"
  | "presales_qualification"
  | "customer_support"
  | "relationship_postsale"
  | "reception_triage"
  | "custom";

export type GuidedPosture =
  | "consultive"
  | "direct"
  | "educational"
  | "welcoming"
  | "technical";

export type GuidedInitiative = "only_respond" | "respond_suggest" | "drive_conversion";
export type GuidedWhenNoInfo = "ask_context" | "direct_to_team" | "knowledge_only";

export type GuidedDoItem =
  | "answer_company_questions"
  | "explain_products"
  | "qualify_leads"
  | "recommend_catalog"
  | "guide_next_step"
  | "ask_context"
  | "use_knowledge_base";

export type GuidedDontItem =
  | "no_fake_prices"
  | "no_fake_discounts"
  | "no_guarantee_results"
  | "no_fake_integrations"
  | "no_official_partner_claims"
  | "no_sensitive_data"
  | "no_out_of_scope";

export type GuidedConfig = {
  role?: GuidedRole | null;
  main_objective?: string | null;
  posture?: GuidedPosture | null;
  initiative?: GuidedInitiative | null;
  when_no_info?: GuidedWhenNoInfo | null;
  do_items?: GuidedDoItem[];
  custom_should_do?: string[];
  dont_items?: GuidedDontItem[];
  custom_should_not_do?: string[];
  extra_restrictions?: string | null;
  good_response_example?: string | null;
  bad_response_example?: string | null;
};

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
  catalog_enabled: boolean;
  response_style: ResponseStyle;
  language_mode: LanguageMode;
  knowledge_only: boolean;
  show_sources: boolean;
  knowledge_fallback: string | null;
  instructions_mode: InstructionsMode;
  guided_config: GuidedConfig | null;
  advanced_prompt: string | null;
  context_tier: ContextTier;
  reply_delay_seconds: number;
  avatar_url: string | null;
  avatar_mime_type: string | null;
  avatar_updated_at: string | null;
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
  response_style?: ResponseStyle;
  language_mode?: LanguageMode;
  knowledge_only?: boolean;
  show_sources?: boolean;
  instructions_mode?: InstructionsMode;
  guided_config?: GuidedConfig;
};

export type AgentUpdateInput = {
  name?: string;
  description?: string | null;
  system_prompt?: string | null;
  persona?: string | null;
  ai_model_id?: string;
  temperature?: number;
  catalog_enabled?: boolean;
  response_style?: ResponseStyle;
  language_mode?: LanguageMode;
  knowledge_only?: boolean;
  show_sources?: boolean;
  instructions_mode?: InstructionsMode;
  guided_config?: GuidedConfig | null;
  advanced_prompt?: string | null;
  context_tier?: ContextTier;
  reply_delay_seconds?: number;
  knowledge_fallback?: string | null;
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
  catalog_retrieval_attempted: boolean;
  catalog_items_count: number;
  catalog_items_used: CatalogRetrievalItem[];
  catalog_retrieval_method: string | null;
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
  name: string | null;
  email: string | null;
  phone: string | null;
  origin: string | null;
  last_seen_at: string | null;
  external_id: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type ContactListOut = {
  items: Contact[];
  total: number;
  limit: number;
  offset: number;
};

export type ContactCreateInput = {
  name?: string;
  email?: string;
  phone?: string;
  origin?: string;
  external_id?: string;
};

export type ContactUpdateInput = {
  name?: string;
  email?: string | null;
  phone?: string | null;
  origin?: string | null;
  external_id?: string | null;
};

export type ContactVariable = {
  id: string;
  contact_id: string;
  workspace_id: string;
  key: string;
  value: string;
  source: string | null;
  created_at: string;
  updated_at: string;
};

export type ContactVariableCreateInput = { key: string; value: string; source?: string };
export type ContactVariableUpdateInput = { value: string; source?: string };

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
  // Attribution (web_widget only, derived from Contact.metadata_json)
  source_page_url: string | null;
  source_page_title: string | null;
  source_referrer: string | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  last_seen_page_url: string | null;
  last_seen_page_title: string | null;
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

export type MessageDelivery = {
  channel?: string;
  provider?: string;
  status?: "queued" | "sending" | "sent" | "delivered" | "read" | "failed" | string;
  external_message_id?: string | null;
  error_type?: string | null;
  error_status?: number | null;
  error_message?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  read_at?: string | null;
  failed_at?: string | null;
};

export type CatalogRetrievalItem = {
  id?: string;
  name?: string;
  score?: number | null;
  semantic_score?: number | null;
  lexical_score?: number | null;
  retrieval_method?: string;
};

export type CatalogRetrieval = {
  query?: string;
  retrieval_method?: string;
  embedding_used?: boolean;
  items_considered?: CatalogRetrievalItem[];
};

export type CatalogMediaDelivery = {
  attempted?: boolean;
  sent?: boolean;
  item_id?: string;
  item_name?: string;
  media_id?: string;
  media_url?: string;
  caption?: string;
  reason?: string;
  error?: string;
  wamid?: string;
};

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
  metadata_json:
    | {
        delivery?: MessageDelivery;
        catalog_retrieval?: CatalogRetrieval;
        catalog_media_delivery?: CatalogMediaDelivery;
        [key: string]: unknown;
      }
    | null;
  created_at: string;
};

export type ConversationMessageCreateInput = {
  content: string;
  direction: MessageDirection;
  sender_type: MessageSenderType;
  sender_user_id?: string;
  agent_id?: string;
};

// ── Onboarding ────────────────────────────────────────────────────────────────

export type OnboardingProfile = {
  id: string;
  workspace_id: string;
  user_id: string;
  full_name: string;
  phone: string;
  main_objective: string;
  expected_monthly_conversations: string;
  ai_experience: string;
  company_name: string;
  company_industry: string;
  company_website: string | null;
  role: string;
  heard_from: string;
  contact_consent: boolean;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OnboardingStatus = {
  completed: boolean;
  profile: OnboardingProfile | null;
};

export type OnboardingSubmitInput = {
  full_name: string;
  phone: string;
  main_objective: string;
  expected_monthly_conversations: string;
  ai_experience: string;
  company_name: string;
  company_industry: string;
  company_website?: string | null;
  role: string;
  heard_from: string;
  contact_consent: boolean;
};

// ── Catalog ───────────────────────────────────────────────────────────────────

export type CatalogItemStatus = "draft" | "active" | "inactive" | "unavailable" | "archived";

export type CatalogCategory = {
  id: string;
  workspace_id: string;
  parent_id: string | null;
  name: string;
  slug: string | null;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type CatalogItem = {
  id: string;
  workspace_id: string;
  category_id: string | null;
  name: string;
  slug: string | null;
  short_description: string | null;
  description: string | null;
  price: number | null;
  currency: string;
  status: CatalogItemStatus;
  tags: string[];
  metadata_json: Record<string, unknown>;
  searchable_text: string | null;
  external_id: string | null;
  sku: string | null;
  stock_quantity: number | null;
  is_featured: boolean;
  created_at: string;
  updated_at: string;
  primary_media?: CatalogMedia | null;
};

export type CatalogCategoryCreateInput = {
  name: string;
  parent_id?: string | null;
  slug?: string;
  description?: string;
  sort_order?: number;
  is_active?: boolean;
};

export type CatalogCategoryUpdateInput = Partial<CatalogCategoryCreateInput>;

export type AgentCatalogScope = {
  catalog_enabled: boolean;
  category_scope: "all" | "selected";
  category_ids: string[];
};

export type AgentCatalogScopeUpdate = {
  catalog_enabled: boolean;
  category_scope: "all" | "selected";
  category_ids: string[];
};

export type CatalogItemCreateInput = {
  name: string;
  category_id?: string | null;
  slug?: string;
  short_description?: string;
  description?: string;
  price?: number | null;
  currency?: string;
  status?: CatalogItemStatus;
  tags?: string[];
  metadata_json?: Record<string, unknown>;
  external_id?: string;
  sku?: string;
  stock_quantity?: number | null;
  is_featured?: boolean;
};

export type CatalogItemUpdateInput = Partial<CatalogItemCreateInput>;

export type CatalogMediaFileType = "image" | "document" | "other";

export type CatalogMedia = {
  id: string;
  workspace_id: string;
  item_id: string;
  file_key: string;
  original_filename: string;
  display_name: string | null;
  mime_type: string;
  file_type: CatalogMediaFileType;
  size_bytes: number;
  sort_order: number;
  is_primary: boolean;
  alt_text: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  preview_url: string | null;
  download_url: string | null;
};

export type CatalogMediaUpdateInput = {
  display_name?: string | null;
  alt_text?: string | null;
  sort_order?: number;
  metadata_json?: Record<string, unknown>;
};

export type CatalogMediaReorderItem = {
  id: string;
  sort_order: number;
};

export type CatalogImportMapping = {
  name?: string;
  category?: string;
  description?: string;
  short_description?: string;
  price?: string;
  currency?: string;
  status?: string;
  tags?: string;
  sku?: string;
  external_id?: string;
  stock_quantity?: string;
  is_featured?: string;
  metadata?: Record<string, string>;
};

export type CatalogImportMode = "create_only" | "upsert_by_sku" | "upsert_by_external_id";

export type CatalogImportRowPreview = {
  row_number: number;
  values: Record<string, string>;
};

export type CatalogImportPreview = {
  filename: string;
  total_rows: number;
  columns: string[];
  rows_preview: CatalogImportRowPreview[];
  warnings: string[];
};

export type CatalogImportError = {
  row_number: number;
  field: string | null;
  message: string;
};

export type CatalogImportWarning = {
  row_number: number | null;
  message: string;
};

export type CatalogImportReport = {
  total_rows: number;
  created: number;
  updated: number;
  skipped: number;
  errors: CatalogImportError[];
  warnings: CatalogImportWarning[];
};

export type CatalogItemFilters = {
  q?: string;
  category_id?: string;
  status?: CatalogItemStatus;
  is_featured?: boolean;
  has_price?: boolean;
  tag?: string;
  limit?: number;
  offset?: number;
  include_primary_media?: boolean;
};

// ── Channels ──────────────────────────────────────────────────────────────────

export type ChannelStatus = "active" | "inactive" | "archived";

export type WebWidgetConfig = {
  theme: "dark" | "light" | "auto";
  primary_color: string;
  position: "bottom-right" | "bottom-left";
  welcome_message: string;
  header_title: string;
  header_subtitle: string;
  placeholder: string;
  auto_open: boolean;
  auto_open_delay_seconds: number;
  // Visitor identity / lead capture
  contact_capture_enabled: boolean;
  require_name: boolean;
  require_email: boolean;
  require_phone: boolean;
};

export type WhatsAppChannelConfig = {
  provider: "meta_cloud_api";
  onboarding_type: "manual" | "embedded_signup";
  waba_id: string;
  phone_number_id: string;
  display_phone_number?: string | null;
  business_id?: string | null;
  access_token_ref?: string | null;
  status?: "testing" | "active" | "disconnected";
  connected_at?: string | null;
  last_webhook_at?: string | null;
  auto_reply_enabled?: boolean;
};

type ChannelBase = {
  id: string;
  workspace_id: string;
  agent_id: string;
  name: string;
  public_key: string;
  status: ChannelStatus;
  allowed_origins: string[];
  created_at: string;
  updated_at: string;
};

export type WebWidgetChannel = ChannelBase & {
  channel_type: "web_widget";
  config: WebWidgetConfig;
};

export type WhatsAppChannel = ChannelBase & {
  channel_type: "whatsapp";
  config: WhatsAppChannelConfig;
};

export type Channel = WebWidgetChannel | WhatsAppChannel;

export type WebWidgetChannelCreateInput = {
  name: string;
  channel_type: "web_widget";
  agent_id: string;
  config?: Partial<WebWidgetConfig>;
  allowed_origins?: string[];
};

export type WhatsAppChannelCreateInput = {
  name: string;
  channel_type: "whatsapp";
  agent_id: string;
  config: {
    provider: "meta_cloud_api";
    onboarding_type: "manual";
    waba_id: string;
    phone_number_id: string;
    display_phone_number?: string;
    business_id?: string;
    access_token_ref: string;
    status: "testing" | "active";
  };
};

export type ChannelCreateInput = WebWidgetChannelCreateInput | WhatsAppChannelCreateInput;

export type ChannelUpdateInput = {
  name?: string;
  status?: "active" | "inactive";
  config?: Partial<WebWidgetConfig> | Partial<WhatsAppChannelConfig>;
  allowed_origins?: string[];
};

// ── First-party auth types ────────────────────────────────────────────────────

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  email_verified: boolean;
};

export type AuthWorkspace = {
  id: string;
  name: string;
  slug: string;
};

export type AuthMe = {
  user: AuthUser;
  workspace: AuthWorkspace;
};

export type SignupInput = {
  email: string;
  password: string;
  name?: string;
};

export type LoginInput = {
  email: string;
  password: string;
};

export type ForgotPasswordInput = {
  email: string;
};

export type ResetPasswordInput = {
  token: string;
  new_password: string;
};

// ── Pipelines ─────────────────────────────────────────────────────────────────

export type Pipeline = {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  is_active: boolean;
  show_inactive_conversations: boolean;
  created_at: string;
  updated_at: string;
};

export type PipelineListOut = Pipeline[];

export type PipelineCreateInput = {
  name: string;
  description?: string | null;
};

export type PipelineUpdateInput = {
  name?: string;
  description?: string | null;
  is_active?: boolean;
};

export type PipelineStage = {
  id: string;
  workspace_id: string;
  pipeline_id: string;
  name: string;
  description: string | null;
  position: number;
  assigned_agent_id: string | null;
  entry_condition: string | null;
  extra_prompt: string | null;
  is_required: boolean;
  is_removal_stage: boolean;
  request_contact_info: boolean;
  stay_limit_enabled: boolean;
  stay_limit_minutes: number | null;
  webhook_url: string | null;
  webhook_auth_header: string | null;
  created_at: string;
  updated_at: string;
};

export type PipelineStageCreateInput = {
  name: string;
  description?: string | null;
  position?: number;
  assigned_agent_id?: string | null;
  extra_prompt?: string | null;
  is_required?: boolean;
  is_removal_stage?: boolean;
  stay_limit_enabled?: boolean;
  stay_limit_minutes?: number | null;
  webhook_url?: string | null;
  webhook_auth_header?: string | null;
};

export type PipelineStageUpdateInput = Partial<PipelineStageCreateInput>;

export type PipelineEntry = {
  id: string;
  workspace_id: string;
  pipeline_id: string | null;
  stage_id: string | null;
  conversation_id: string;
  contact_id: string | null;
  assigned_agent_id: string | null;
  status: "active" | "inactive" | "removed";
  entered_stage_at: string | null;
  created_at: string;
  updated_at: string;
  // Denormalized
  contact_name: string | null;
  contact_phone: string | null;
  contact_email: string | null;
  conversation_status: string | null;
  conversation_channel_type: string | null;
  conversation_last_message_at: string | null;
};

export type AgentPipelineSettingsInput = {
  default_pipeline_id: string | null;
  default_pipeline_stage_id: string | null;
};

// ── Errors ────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Fetch helpers ─────────────────────────────────────────────────────────────

// All authenticated API calls use the wenzap_session cookie (HttpOnly).
// No Authorization header is sent — the cookie is transmitted automatically.
async function cookieFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, error.detail ?? "API error");
  }

  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

// ── API client ────────────────────────────────────────────────────────────────

export const api = {
  me: () => cookieFetch<UserMe>("/me"),
  auth: {
    me: () => cookieFetch<AuthMe>("/auth/me"),
    signup: (input: SignupInput) =>
      cookieFetch<AuthMe>("/auth/signup", { method: "POST", body: JSON.stringify(input) }),
    login: (input: LoginInput) =>
      cookieFetch<AuthMe>("/auth/login", { method: "POST", body: JSON.stringify(input) }),
    logout: () =>
      cookieFetch<void>("/auth/logout", { method: "POST" }),
    forgotPassword: (input: ForgotPasswordInput) =>
      cookieFetch<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    resetPassword: (input: ResetPasswordInput) =>
      cookieFetch<{ message: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    verifyEmail: (token: string) =>
      cookieFetch<{ message: string }>("/auth/verify-email", {
        method: "POST",
        body: JSON.stringify({ token }),
      }),
    resendVerificationEmail: () =>
      cookieFetch<{ message: string }>("/auth/resend-verification-email", {
        method: "POST",
        body: JSON.stringify({}),
      }),
  },
  workspace: {
    current: () => cookieFetch<UserMe["workspace"]>("/workspaces/current"),
    update: (data: { name?: string; slug?: string }) =>
      cookieFetch<UserMe["workspace"]>("/workspaces/current", {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },
  members: {
    list: () => cookieFetch<Member[]>("/workspaces/current/members"),
    updateRole: (memberId: string, role: MemberRole) =>
      cookieFetch<Member>(`/workspaces/current/members/${memberId}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
  },
  plans: {
    list: () => cookieFetch<Plan[]>("/plans"),
    current: () => cookieFetch<Subscription>("/workspaces/current/plan"),
    usage: () => cookieFetch<Usage>("/workspaces/current/usage"),
  },
  aiModels: {
    list: () => cookieFetch<AiCatalog>("/ai-models"),
  },
  contacts: {
    list: (params?: { q?: string; limit?: number; offset?: number }) => {
      const qs = new URLSearchParams();
      if (params?.q) qs.set("q", params.q);
      if (params?.limit != null) qs.set("limit", String(params.limit));
      if (params?.offset != null) qs.set("offset", String(params.offset));
      const q = qs.toString();
      return cookieFetch<ContactListOut>(q ? `/contacts?${q}` : "/contacts");
    },
    get: (contactId: string) => cookieFetch<Contact>(`/contacts/${contactId}`),
    create: (data: ContactCreateInput) =>
      cookieFetch<Contact>("/contacts", { method: "POST", body: JSON.stringify(data) }),
    update: (contactId: string, data: ContactUpdateInput) =>
      cookieFetch<Contact>(`/contacts/${contactId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    delete: (contactId: string) =>
      cookieFetch<void>(`/contacts/${contactId}`, { method: "DELETE" }),
    variables: {
      list: (contactId: string) =>
        cookieFetch<ContactVariable[]>(`/contacts/${contactId}/variables`),
      create: (contactId: string, data: ContactVariableCreateInput) =>
        cookieFetch<ContactVariable>(`/contacts/${contactId}/variables`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (contactId: string, variableId: string, data: ContactVariableUpdateInput) =>
        cookieFetch<ContactVariable>(`/contacts/${contactId}/variables/${variableId}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      delete: (contactId: string, variableId: string) =>
        cookieFetch<void>(`/contacts/${contactId}/variables/${variableId}`, {
          method: "DELETE",
        }),
    },
  },
  conversations: {
    list: (params?: { status?: string; contact_id?: string; skip?: number; limit?: number }) => {
      const qs = new URLSearchParams();
      if (params?.status) qs.set("status", params.status);
      if (params?.contact_id) qs.set("contact_id", params.contact_id);
      if (params?.skip != null) qs.set("skip", String(params.skip));
      if (params?.limit != null) qs.set("limit", String(params.limit));
      const q = qs.toString();
      return cookieFetch<Conversation[]>(q ? `/conversations?${q}` : "/conversations");
    },
    get: (conversationId: string) =>
      cookieFetch<Conversation>(`/conversations/${conversationId}`),
    create: (data: ConversationCreateInput) =>
      cookieFetch<Conversation>("/conversations", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (conversationId: string, data: ConversationUpdateInput) =>
      cookieFetch<Conversation>(`/conversations/${conversationId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    takeOver: (conversationId: string) =>
      cookieFetch<Conversation>(`/conversations/${conversationId}/take-over`, {
        method: "POST",
      }),
    returnToAI: (conversationId: string) =>
      cookieFetch<Conversation>(`/conversations/${conversationId}/return-to-ai`, {
        method: "POST",
      }),
    messages: {
      list: (conversationId: string, params?: { skip?: number; limit?: number }) => {
        const qs = new URLSearchParams();
        if (params?.skip != null) qs.set("skip", String(params.skip));
        if (params?.limit != null) qs.set("limit", String(params.limit));
        const q = qs.toString();
        return cookieFetch<ConversationMessage[]>(
          q
            ? `/conversations/${conversationId}/messages?${q}`
            : `/conversations/${conversationId}/messages`,
        );
      },
      create: (conversationId: string, data: ConversationMessageCreateInput) =>
        cookieFetch<ConversationMessage>(`/conversations/${conversationId}/messages`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      retryDelivery: (conversationId: string, messageId: string) =>
        cookieFetch<ConversationMessage>(
          `/conversations/${conversationId}/messages/${messageId}/retry-delivery`,
          { method: "POST" },
        ),
    },
  },
  channels: {
    list: (params?: { channel_type?: string; agent_id?: string; include_archived?: boolean }) => {
      const qs = new URLSearchParams();
      if (params?.channel_type) qs.set("channel_type", params.channel_type);
      if (params?.agent_id) qs.set("agent_id", params.agent_id);
      if (params?.include_archived) qs.set("include_archived", "true");
      const q = qs.toString();
      return cookieFetch<Channel[]>(q ? `/channels?${q}` : "/channels");
    },
    get: (id: string) => cookieFetch<Channel>(`/channels/${id}`),
    create: (data: ChannelCreateInput) =>
      cookieFetch<Channel>("/channels", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: ChannelUpdateInput) =>
      cookieFetch<Channel>(`/channels/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    archive: (id: string) =>
      cookieFetch<Channel>(`/channels/${id}/archive`, { method: "POST" }),
    whatsappEmbeddedSignup: {
      createState: (agentId: string, debugId?: string) =>
        cookieFetch<{ state: string; expires_in: number }>(
          "/channels/whatsapp/embedded-signup/state",
          {
            method: "POST",
            body: JSON.stringify({ agent_id: agentId }),
            headers: debugId ? { "X-Wenzap-Debug-Id": debugId } : {},
          },
        ),
      exchange: (
        payload: {
          code: string;
          state: string;
          waba_id: string;
          phone_number_id: string;
          business_id?: string | null;
        },
        debugId?: string,
      ) =>
        cookieFetch<Channel>(
          "/channels/whatsapp/embedded-signup/exchange",
          {
            method: "POST",
            body: JSON.stringify(payload),
            headers: debugId ? { "X-Wenzap-Debug-Id": debugId } : {},
          },
        ),
    },
  },
  onboarding: {
    get: () => cookieFetch<OnboardingStatus>("/onboarding"),
    status: () => cookieFetch<OnboardingStatus>("/onboarding"),
    submit: (data: OnboardingSubmitInput) =>
      cookieFetch<OnboardingStatus>("/onboarding", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },
  catalog: {
    categories: {
      list: (includeInactive?: boolean) =>
        cookieFetch<CatalogCategory[]>(
          includeInactive ? "/catalog/categories?include_inactive=true" : "/catalog/categories",
        ),
      get: (id: string) => cookieFetch<CatalogCategory>(`/catalog/categories/${id}`),
      create: (data: CatalogCategoryCreateInput) =>
        cookieFetch<CatalogCategory>("/catalog/categories", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: string, data: CatalogCategoryUpdateInput) =>
        cookieFetch<CatalogCategory>(`/catalog/categories/${id}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      delete: (id: string) =>
        cookieFetch<CatalogCategory>(`/catalog/categories/${id}`, { method: "DELETE" }),
    },
    items: {
      list: (filters?: CatalogItemFilters) => {
        const qs = new URLSearchParams();
        if (filters?.q) qs.set("q", filters.q);
        if (filters?.category_id) qs.set("category_id", filters.category_id);
        if (filters?.status) qs.set("status", filters.status);
        if (filters?.is_featured != null) qs.set("is_featured", String(filters.is_featured));
        if (filters?.has_price != null) qs.set("has_price", String(filters.has_price));
        if (filters?.tag) qs.set("tag", filters.tag);
        if (filters?.limit != null) qs.set("limit", String(filters.limit));
        if (filters?.offset != null) qs.set("offset", String(filters.offset));
        if (filters?.include_primary_media) qs.set("include_primary_media", "true");
        const q = qs.toString();
        return cookieFetch<CatalogItem[]>(q ? `/catalog/items?${q}` : "/catalog/items");
      },
      get: (id: string) => cookieFetch<CatalogItem>(`/catalog/items/${id}`),
      create: (data: CatalogItemCreateInput) =>
        cookieFetch<CatalogItem>("/catalog/items", {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (id: string, data: CatalogItemUpdateInput) =>
        cookieFetch<CatalogItem>(`/catalog/items/${id}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      archive: (id: string) =>
        cookieFetch<CatalogItem>(`/catalog/items/${id}`, { method: "DELETE" }),
    },
    media: {
      list: (itemId: string) =>
        cookieFetch<CatalogMedia[]>(`/catalog/items/${itemId}/media`),
      get: (itemId: string, mediaId: string) =>
        cookieFetch<CatalogMedia>(`/catalog/items/${itemId}/media/${mediaId}`),
      upload: async (itemId: string, formData: FormData): Promise<CatalogMedia> => {
        const res = await fetch(`${API_URL}/catalog/items/${itemId}/media`, {
          method: "POST",
          credentials: "include",
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new ApiError(res.status, err.detail ?? "API error");
        }
        return res.json() as Promise<CatalogMedia>;
      },
      update: (itemId: string, mediaId: string, data: CatalogMediaUpdateInput) =>
        cookieFetch<CatalogMedia>(`/catalog/items/${itemId}/media/${mediaId}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      delete: (itemId: string, mediaId: string) =>
        cookieFetch<void>(`/catalog/items/${itemId}/media/${mediaId}`, { method: "DELETE" }),
      setPrimary: (itemId: string, mediaId: string) =>
        cookieFetch<CatalogMedia>(`/catalog/items/${itemId}/media/${mediaId}/set-primary`, {
          method: "POST",
        }),
      reorder: (itemId: string, payload: CatalogMediaReorderItem[]) =>
        cookieFetch<CatalogMedia[]>(`/catalog/items/${itemId}/media/reorder`, {
          method: "POST",
          body: JSON.stringify(payload),
        }),
    },
    import: {
      preview: async (file: File): Promise<CatalogImportPreview> => {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`${API_URL}/catalog/import/preview`, {
          method: "POST",
          body: form,
          credentials: "include",
        });
        if (!res.ok) throw new Error(await res.text());
        return res.json() as Promise<CatalogImportPreview>;
      },
      commit: async (
        file: File,
        mapping: CatalogImportMapping,
        mode: CatalogImportMode,
      ): Promise<CatalogImportReport> => {
        const form = new FormData();
        form.append("file", file);
        form.append("mapping_json", JSON.stringify(mapping));
        form.append("mode", mode);
        const res = await fetch(`${API_URL}/catalog/import/commit`, {
          method: "POST",
          body: form,
          credentials: "include",
        });
        if (!res.ok) throw new Error(await res.text());
        return res.json() as Promise<CatalogImportReport>;
      },
    },
  },
  agents: {
    list: (status?: AgentStatus) =>
      cookieFetch<Agent[]>(status ? `/agents?status=${status}` : "/agents"),
    get: (id: string) => cookieFetch<Agent>(`/agents/${id}`),
    create: (data: AgentCreateInput) =>
      cookieFetch<Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: AgentUpdateInput) =>
      cookieFetch<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    updateStatus: (id: string, status: AgentStatus) =>
      cookieFetch<Agent>(`/agents/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    archive: (id: string) => cookieFetch<Agent>(`/agents/${id}`, { method: "DELETE" }),
    deletePermanently: (id: string) =>
      cookieFetch<void>(`/agents/${id}/permanent`, { method: "DELETE" }),
    uploadAvatar: async (id: string, file: File): Promise<Agent> => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/agents/${id}/avatar`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new ApiError(res.status, error.detail ?? "Upload error");
      }
      return res.json();
    },
    deleteAvatar: (id: string) =>
      cookieFetch<Agent>(`/agents/${id}/avatar`, { method: "DELETE" }),
    /**
     * Resolve the best avatar URL for an agent.
     * - If avatar_url is set (e.g. R2 public URL), use it directly.
     * - If the agent has an avatar but avatar_url is null (local storage),
     *   fall back to the API serve endpoint with credentials.
     */
    resolveAvatarUrl: (agent: Agent): string | null => {
      if (agent.avatar_url) return agent.avatar_url;
      if (agent.avatar_mime_type) return `${API_URL}/agents/${agent.id}/avatar/file`;
      return null;
    },
    test: (id: string, message: string, sessionId?: string) =>
      cookieFetch<AgentTestResponse>(`/agents/${id}/test`, {
        method: "POST",
        body: JSON.stringify({ message, ...(sessionId ? { session_id: sessionId } : {}) }),
      }),
    knowledgeBases: {
      list: (agentId: string) =>
        cookieFetch<AgentKnowledgeBase[]>(`/agents/${agentId}/knowledge-bases`),
      connect: (agentId: string, kbId: string) =>
        cookieFetch<AgentKnowledgeBase>(`/agents/${agentId}/knowledge-bases`, {
          method: "POST",
          body: JSON.stringify({ knowledge_base_id: kbId }),
        }),
      update: (agentId: string, kbId: string, data: { is_active: boolean }) =>
        cookieFetch<AgentKnowledgeBase>(`/agents/${agentId}/knowledge-bases/${kbId}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      disconnect: (agentId: string, kbId: string) =>
        cookieFetch<void>(`/agents/${agentId}/knowledge-bases/${kbId}`, { method: "DELETE" }),
    },
    playground: {
      listSessions: (agentId: string) =>
        cookieFetch<PlaygroundSession[]>(`/agents/${agentId}/playground/sessions`),
      createSession: (agentId: string) =>
        cookieFetch<PlaygroundSession>(`/agents/${agentId}/playground/sessions`, {
          method: "POST",
          body: JSON.stringify({}),
        }),
      getSession: (agentId: string, sessionId: string) =>
        cookieFetch<PlaygroundSessionWithMessages>(
          `/agents/${agentId}/playground/sessions/${sessionId}`,
        ),
      deleteSession: (agentId: string, sessionId: string) =>
        cookieFetch<void>(`/agents/${agentId}/playground/sessions/${sessionId}`, {
          method: "DELETE",
        }),
    },
    updatePipelineSettings: (id: string, data: AgentPipelineSettingsInput) =>
      cookieFetch<Agent>(`/agents/${id}/pipeline-settings`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    catalogScope: {
      get: (agentId: string) =>
        cookieFetch<AgentCatalogScope>(`/agents/${agentId}/tools/catalog`),
      update: (agentId: string, data: AgentCatalogScopeUpdate) =>
        cookieFetch<AgentCatalogScope>(`/agents/${agentId}/tools/catalog`, {
          method: "PUT",
          body: JSON.stringify(data),
        }),
    },
  },
  pipelines: {
    list: () => cookieFetch<PipelineListOut>("/pipelines"),
    get: (id: string) => cookieFetch<Pipeline>(`/pipelines/${id}`),
    create: (data: PipelineCreateInput) =>
      cookieFetch<Pipeline>("/pipelines", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: PipelineUpdateInput) =>
      cookieFetch<Pipeline>(`/pipelines/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => cookieFetch<void>(`/pipelines/${id}`, { method: "DELETE" }),
    stages: {
      list: (pipelineId: string) =>
        cookieFetch<PipelineStage[]>(`/pipelines/${pipelineId}/stages`),
      create: (pipelineId: string, data: PipelineStageCreateInput) =>
        cookieFetch<PipelineStage>(`/pipelines/${pipelineId}/stages`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      update: (pipelineId: string, stageId: string, data: PipelineStageUpdateInput) =>
        cookieFetch<PipelineStage>(`/pipelines/${pipelineId}/stages/${stageId}`, {
          method: "PATCH",
          body: JSON.stringify(data),
        }),
      delete: (pipelineId: string, stageId: string) =>
        cookieFetch<void>(`/pipelines/${pipelineId}/stages/${stageId}`, { method: "DELETE" }),
      reorder: (pipelineId: string, stages: { id: string; position: number }[]) =>
        cookieFetch<PipelineStage[]>(`/pipelines/${pipelineId}/stages/reorder`, {
          method: "POST",
          body: JSON.stringify({ stages }),
        }),
    },
    entries: {
      list: (pipelineId: string) =>
        cookieFetch<PipelineEntry[]>(`/pipelines/${pipelineId}/entries`),
      create: (pipelineId: string, data: { conversation_id: string; stage_id: string }) =>
        cookieFetch<PipelineEntry>(`/pipelines/${pipelineId}/entries`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      move: (pipelineId: string, entryId: string, stageId: string) =>
        cookieFetch<PipelineEntry>(`/pipelines/${pipelineId}/entries/${entryId}/move`, {
          method: "PATCH",
          body: JSON.stringify({ stage_id: stageId }),
        }),
      delete: (pipelineId: string, entryId: string) =>
        cookieFetch<void>(`/pipelines/${pipelineId}/entries/${entryId}`, { method: "DELETE" }),
    },
  },
  knowledgeBases: {
    list: () => cookieFetch<KnowledgeBase[]>("/knowledge-bases"),
    create: (data: KnowledgeBaseCreateInput) =>
      cookieFetch<KnowledgeBase>("/knowledge-bases", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    get: (kbId: string) => cookieFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`),
    update: (kbId: string, data: KnowledgeBaseUpdateInput) =>
      cookieFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    archive: (kbId: string) =>
      cookieFetch<KnowledgeBase>(`/knowledge-bases/${kbId}`, { method: "DELETE" }),
    sources: {
      list: (kbId: string) =>
        cookieFetch<KnowledgeSource[]>(`/knowledge-bases/${kbId}/sources`),
      create: (kbId: string, data: KnowledgeSourceCreateInput) =>
        cookieFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources`, {
          method: "POST",
          body: JSON.stringify(data),
        }),
      get: (kbId: string, sourceId: string) =>
        cookieFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources/${sourceId}`),
      archive: (kbId: string, sourceId: string) =>
        cookieFetch<KnowledgeSource>(`/knowledge-bases/${kbId}/sources/${sourceId}`, {
          method: "DELETE",
        }),
      reprocess: (kbId: string, sourceId: string) =>
        cookieFetch<KnowledgeSource>(
          `/knowledge-bases/${kbId}/sources/${sourceId}/reprocess`,
          { method: "POST" },
        ),
      upload: async (
        kbId: string,
        file: File,
        data?: { title?: string; source_category?: string },
      ): Promise<KnowledgeSource> => {
        const form = new FormData();
        form.append("file", file);
        if (data?.title?.trim()) form.append("title", data.title.trim());
        if (data?.source_category?.trim())
          form.append("source_category", data.source_category.trim());
        // Do NOT set Content-Type — browser sets multipart boundary automatically.
        const res = await fetch(`${API_URL}/knowledge-bases/${kbId}/sources/upload`, {
          method: "POST",
          credentials: "include",
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
