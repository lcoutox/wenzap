/**
 * Client-side feature gate helpers.
 * Mirrors plan_feature_service.py on the backend.
 * Unknown plan codes are treated as unrestricted (custom/test plans).
 */

const PLAN_TIER: Record<string, number> = {
  starter: 1,
  growth: 2,
  scale: 3,
  enterprise: 4,
};

const PLAN_CHANNEL_TYPES: Record<string, Set<string>> = {
  starter:    new Set(["web_widget", "api"]),
  growth:     new Set(["web_widget", "api", "whatsapp"]),
  scale:      new Set(["web_widget", "api", "whatsapp", "instagram", "telegram"]),
  enterprise: new Set(["web_widget", "api", "whatsapp", "instagram", "telegram", "slack"]),
};

const FEATURE_MIN_PLAN: Record<string, string> = {
  // Growth+
  whatsapp_channel:         "growth",
  pipelines:                "growth",
  integrations:             "growth",
  multiple_knowledge_bases: "growth",
  api_access:               "growth",
  // Scale+ (internal plan — show generic label in UI)
  http_tools:               "scale",
  follow_up:                "scale",
  webhooks:                 "scale",
  custom_model:             "scale",
  analytics:                "scale",
  // Enterprise-only (internal plan — show generic label in UI)
  remove_powered_by:        "enterprise",
};

export type LimitState = "normal" | "warning" | "danger" | "exceeded";

/** Returns visual state for a usage bar. 0-limit means unlimited → always normal. */
export function getLimitState(used: number, limit: number): LimitState {
  if (limit <= 0) return "normal";
  const pct = used / limit;
  if (pct >= 1)   return "exceeded";
  if (pct >= 0.9) return "danger";
  if (pct >= 0.7) return "warning";
  return "normal";
}

/** Returns percentage (0–100), capped at 100. */
export function limitPct(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

/** Returns true if another resource can be created within the limit. */
export function canCreateResource(used: number, limit: number): boolean {
  if (limit <= 0) return true;
  return used < limit;
}

export function planTier(planCode: string): number {
  return PLAN_TIER[planCode] ?? 1;
}

export function planAllowsChannelType(planCode: string, channelType: string): boolean {
  const allowed = PLAN_CHANNEL_TYPES[planCode];
  if (!allowed) return true; // unknown plan = unrestricted
  return allowed.has(channelType);
}

export function planAllowsFeature(planCode: string, feature: string): boolean {
  const minPlan = FEATURE_MIN_PLAN[feature];
  if (!minPlan) return true;
  return planTier(planCode) >= planTier(minPlan);
}

/** Returns true when an HTTP response status indicates a plan limit error. */
export function isPlanLimitError(status: number): boolean {
  return status === 402;
}

/** Human-readable plan name label. */
export function planLabel(planCode: string): string {
  const map: Record<string, string> = {
    starter:    "Free",
    growth:     "Growth",
    scale:      "Scale",
    enterprise: "Enterprise",
  };
  return map[planCode] ?? planCode;
}

/** Minimum plan name for a feature.
 *  Scale and Enterprise are internal plans — return a generic label instead. */
export function minPlanLabel(feature: string): string {
  const minPlan = FEATURE_MIN_PLAN[feature];
  if (!minPlan) return "";
  if (minPlan === "scale" || minPlan === "enterprise") return "Planos superiores";
  return planLabel(minPlan);
}
