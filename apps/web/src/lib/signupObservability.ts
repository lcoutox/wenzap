/**
 * Observability helpers for the WhatsApp Embedded Signup flow.
 *
 * Sentry is NOT a dependency of the frontend yet. This module tries to load
 * it dynamically; when unavailable it falls back to console.error so the
 * instrumentation works without a hard runtime dependency.
 *
 * To install Sentry later: `pnpm add @sentry/nextjs` and run the Sentry wizard.
 */

// ── Types ─────────────────────────────────────────────────────────────────────

export interface SignupErrorContext {
  step: string;
  debugId: string;
  hasCode?: boolean;
  hasSessionInfo?: boolean;
  lastMessageOrigin?: string | null;
  lastMessageShape?: Record<string, unknown> | null;
  metaAppIdPresent?: boolean;
  metaConfigIdPresent?: boolean;
  graphVersion?: string;
}

// ── Debug mode ────────────────────────────────────────────────────────────────

export function isDebugMode(): boolean {
  return (
    process.env.NEXT_PUBLIC_DEBUG_META_SIGNUP === "true" ||
    process.env.NODE_ENV === "development"
  );
}

// ── Structured logger ─────────────────────────────────────────────────────────

export function logSignup(event: string, data: Record<string, unknown> = {}): void {
  if (!isDebugMode()) return;
  console.debug(`[WA-Signup] ${event}`, data);
}

// ── Sentry capture ────────────────────────────────────────────────────────────

type SentryLike = {
  captureException: (
    err: unknown,
    opts: { tags: Record<string, string>; extra: Record<string, unknown> },
  ) => void;
};

function getSentry(): SentryLike | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const mod = require("@sentry/nextjs");
    if (typeof mod?.captureException === "function") return mod as SentryLike;
  } catch {
    // not installed
  }
  return null;
}

export function captureSignupError(error: Error, ctx: SignupErrorContext): void {
  // Always log to console (visible in Railway/Vercel build logs and DevTools)
  console.error(
    `[WA-Signup] error step=${ctx.step} debugId=${ctx.debugId}: ${error.message}`,
  );

  const sentry = getSentry();
  if (sentry) {
    sentry.captureException(error, {
      tags: {
        feature: "whatsapp_embedded_signup",
        step: ctx.step,
      },
      extra: {
        debugId: ctx.debugId,
        hasCode: ctx.hasCode ?? false,
        hasSessionInfo: ctx.hasSessionInfo ?? false,
        lastMessageOrigin: ctx.lastMessageOrigin ?? null,
        lastMessageShape: ctx.lastMessageShape ?? null,
        metaAppIdPresent: ctx.metaAppIdPresent ?? false,
        metaConfigIdPresent: ctx.metaConfigIdPresent ?? false,
        graphVersion: ctx.graphVersion ?? "unknown",
      },
    });
  }
}
