/**
 * Meta / Facebook JS SDK loader and WhatsApp Embedded Signup flow helpers.
 *
 * Flow:
 *  1. FB.login() opens the Meta popup with extras.feature = "whatsapp_embedded_signup".
 *  2. The popup fires a WA_EMBEDDED_SIGNUP postMessage with waba_id + phone_number_id.
 *  3. The FB.login callback fires with authResponse.code.
 *  4. Both signals are required. A 10-second polling loop handles the race.
 *
 * No redirect_uri is passed — the JS SDK handles the popup via xd_arbiter internally.
 */

import { captureSignupError, isDebugMode, logSignup } from "./signupObservability";

declare global {
  interface Window {
    FB?: {
      init: (options: {
        appId: string;
        autoLogAppEvents: boolean;
        xfbml: boolean;
        version: string;
      }) => void;
      login: (
        callback: (response: {
          authResponse?: { code?: string } | null;
          status: string;
        }) => void,
        options: {
          config_id: string;
          response_type: string;
          override_default_response_type: boolean;
          extras?: Record<string, unknown>;
        },
      ) => void;
    };
    fbAsyncInit?: () => void;
  }
}

// ── Trusted origins ───────────────────────────────────────────────────────────
// staticxx.facebook.com hosts the xd_arbiter used by the JS SDK popup.
// business.facebook.com is used by the Business Manager flow.

const META_TRUSTED_ORIGINS = new Set([
  "https://www.facebook.com",
  "https://web.facebook.com",
  "https://facebook.com",
  "https://business.facebook.com",
  "https://staticxx.facebook.com",
]);

// ── Types ─────────────────────────────────────────────────────────────────────

export interface EmbeddedSignupData {
  code: string;
  waba_id: string;
  phone_number_id: string;
  business_id?: string | null;
}

export interface ParsedEmbeddedSignupMessage {
  type?: string;
  event?: string;
  waba_id?: string;
  phone_number_id?: string;
  business_id?: string;
}

// ── postMessage parser ────────────────────────────────────────────────────────

/**
 * Parse a postMessage event into a structured WA_EMBEDDED_SIGNUP payload.
 *
 * Handles all observed formats:
 *   1. event.data is an object
 *   2. event.data is a JSON string
 *   3. event.data is a URL-encoded / querystring string
 *
 * Also handles field name variations (snake_case vs camelCase).
 * Returns null when the message is not a WA_EMBEDDED_SIGNUP message.
 */
export function parseEmbeddedSignupMessage(
  event: MessageEvent,
): ParsedEmbeddedSignupMessage | null {
  let raw: unknown;

  if (event.data !== null && typeof event.data === "object") {
    raw = event.data;
  } else if (typeof event.data === "string") {
    // Try JSON first
    try {
      raw = JSON.parse(event.data);
    } catch {
      // Try URL-encoded / querystring fallback
      try {
        const params = new URLSearchParams(event.data);
        if (params.has("type") || params.has("waba_id") || params.has("wabaId")) {
          const obj: Record<string, string> = {};
          params.forEach((v, k) => {
            obj[k] = v;
          });
          raw = obj;
        }
      } catch {
        // unparseable — ignore
      }
    }
  }

  if (!raw || typeof raw !== "object") return null;

  const msg = raw as Record<string, unknown>;

  // Must carry the WA_EMBEDDED_SIGNUP type marker (or waba_id directly as flat fallback)
  const isWASignup =
    msg["type"] === "WA_EMBEDDED_SIGNUP" ||
    (msg["type"] == null && ("waba_id" in msg || "wabaId" in msg));
  if (!isWASignup) return null;

  const result: ParsedEmbeddedSignupMessage = {
    type: msg["type"] != null ? String(msg["type"]) : "WA_EMBEDDED_SIGNUP",
    event: msg["event"] != null ? String(msg["event"]) : undefined,
  };

  // WABA data: may be nested under "data" or at the top level
  const inner =
    msg["data"] != null && typeof msg["data"] === "object"
      ? (msg["data"] as Record<string, unknown>)
      : msg;

  // Accept snake_case (waba_id) and camelCase (wabaId) variants
  const wabaId = inner["waba_id"] ?? inner["wabaId"];
  const phoneNumberId = inner["phone_number_id"] ?? inner["phoneNumberId"];
  const businessId = inner["business_id"] ?? inner["businessId"];

  if (wabaId != null) result.waba_id = String(wabaId);
  if (phoneNumberId != null) result.phone_number_id = String(phoneNumberId);
  if (businessId != null) result.business_id = String(businessId);

  return result;
}

/** Safe shape descriptor for a postMessage — never logs raw values. */
function messageShape(event: MessageEvent): Record<string, unknown> {
  const keys =
    event.data !== null && typeof event.data === "object"
      ? Object.keys(event.data as object)
      : typeof event.data === "string"
        ? ["<string>"]
        : ["<unknown>"];

  const parsed = parseEmbeddedSignupMessage(event);
  return {
    origin: event.origin,
    dataType: typeof event.data,
    keys,
    type: parsed?.type ?? null,
    event: parsed?.event ?? null,
    hasWabaId: parsed?.waba_id != null,
    hasPhoneNumberId: parsed?.phone_number_id != null,
    hasBusinessId: parsed?.business_id != null,
  };
}

// ── SDK loader ────────────────────────────────────────────────────────────────

let sdkLoadPromise: Promise<void> | null = null;

export function loadMetaSdk(): Promise<void> {
  if (sdkLoadPromise) return sdkLoadPromise;

  sdkLoadPromise = new Promise<void>((resolve, reject) => {
    if (typeof window === "undefined") {
      reject(new Error("loadMetaSdk must run in the browser"));
      return;
    }
    if (window.FB) {
      resolve();
      return;
    }

    const appId = process.env.NEXT_PUBLIC_META_APP_ID;
    const version = process.env.NEXT_PUBLIC_META_GRAPH_API_VERSION ?? "v25.0";

    if (!appId) {
      reject(new Error("NEXT_PUBLIC_META_APP_ID is not configured"));
      return;
    }

    window.fbAsyncInit = () => {
      window.FB!.init({ appId, autoLogAppEvents: true, xfbml: false, version });
      resolve();
    };

    if (document.getElementById("facebook-jssdk")) return;

    const script = document.createElement("script");
    script.id = "facebook-jssdk";
    script.src = "https://connect.facebook.net/en_US/sdk.js";
    script.async = true;
    script.defer = true;
    script.onerror = () => reject(new Error("Failed to load Meta SDK"));
    document.head.appendChild(script);
  });

  return sdkLoadPromise;
}

// ── Main signup flow ──────────────────────────────────────────────────────────

/**
 * Run the WhatsApp Embedded Signup flow.
 *
 * Resolves with { code, waba_id, phone_number_id, business_id } when both
 * the authorization code and the WA_EMBEDDED_SIGNUP postMessage are received.
 * Rejects with a user-facing error message on failure, and captures to Sentry.
 */
export function runEmbeddedSignup(debugId: string): Promise<EmbeddedSignupData> {
  const configId = process.env.NEXT_PUBLIC_META_CONFIG_ID;
  const appId = process.env.NEXT_PUBLIC_META_APP_ID;
  const graphVersion = process.env.NEXT_PUBLIC_META_GRAPH_API_VERSION ?? "v25.0";

  logSignup("embedded_signup.fb.login.start", { debugId, configId: !!configId, appId: !!appId });

  if (!configId || !appId) {
    const err = new Error("A conexão com a Meta ainda não está configurada neste ambiente.");
    captureSignupError(err, {
      step: "config_check",
      debugId,
      metaAppIdPresent: !!appId,
      metaConfigIdPresent: !!configId,
      graphVersion,
    });
    return Promise.reject(err);
  }

  return new Promise<EmbeddedSignupData>((resolve, reject) => {
    let code: string | null = null;
    let wabaId: string | null = null;
    let phoneNumberId: string | null = null;
    let businessId: string | null = null;
    let lastMessageOrigin: string | null = null;
    let lastMessageShape: Record<string, unknown> | null = null;

    function onMessage(event: MessageEvent) {
      // Log ALL postMessages (shape only, no raw values) for diagnostics
      const isMeta =
        typeof event.origin === "string" &&
        (event.origin.includes("facebook.com") || event.origin.includes("meta.com"));

      if (isMeta) {
        const shape = messageShape(event);
        lastMessageOrigin = event.origin;
        lastMessageShape = shape;
        logSignup("embedded_signup.message.received", { debugId, ...shape });
      }

      if (!META_TRUSTED_ORIGINS.has(event.origin)) {
        if (isMeta) {
          logSignup("embedded_signup.message.ignored_origin", {
            debugId,
            origin: event.origin,
            note: "origin not in trusted set — add if this is a legitimate Meta domain",
          });
        }
        return;
      }

      const parsed = parseEmbeddedSignupMessage(event);

      if (!parsed) {
        if (isMeta) {
          logSignup("embedded_signup.message.parse_failed", {
            debugId,
            origin: event.origin,
            dataType: typeof event.data,
          });
        }
        return;
      }

      logSignup("embedded_signup.message.parsed", {
        debugId,
        type: parsed.type,
        event: parsed.event,
        hasWabaId: parsed.waba_id != null,
        hasPhoneNumberId: parsed.phone_number_id != null,
        hasBusinessId: parsed.business_id != null,
      });

      // Accept FINISH or any message carrying waba_id (some SDK versions omit event field)
      const isFinish =
        parsed.event === "FINISH" ||
        (parsed.event == null && parsed.waba_id != null);

      if (isFinish && parsed.waba_id && parsed.phone_number_id) {
        wabaId = parsed.waba_id;
        phoneNumberId = parsed.phone_number_id;
        businessId = parsed.business_id ?? null;
        logSignup("embedded_signup.session_info.received", {
          debugId,
          waba_id: wabaId,
          phone_number_id: phoneNumberId,
          has_business_id: businessId != null,
        });
      }
    }

    window.addEventListener("message", onMessage);
    const cleanup = () => window.removeEventListener("message", onMessage);

    window.FB!.login(
      (response) => {
        logSignup("embedded_signup.fb.login.callback", {
          debugId,
          status: response.status,
          hasAuthResponse: response.authResponse != null,
        });

        if (response.status !== "connected" || !response.authResponse) {
          cleanup();
          const err = new Error("Conexão cancelada. Tente novamente quando quiser.");
          captureSignupError(err, {
            step: "fb_login_cancelled",
            debugId,
            hasCode: false,
            hasSessionInfo: false,
            lastMessageOrigin,
            lastMessageShape,
            metaAppIdPresent: !!appId,
            metaConfigIdPresent: !!configId,
            graphVersion,
          });
          reject(err);
          return;
        }

        code = response.authResponse.code ?? null;

        if (!code) {
          cleanup();
          logSignup("embedded_signup.fb.login.no_code", { debugId });
          const err = new Error(
            "Autorização recebida da Meta, mas o código estava ausente. Tente novamente.",
          );
          captureSignupError(err, {
            step: "fb_login_no_code",
            debugId,
            hasCode: false,
            hasSessionInfo: false,
            lastMessageOrigin,
            lastMessageShape,
            metaAppIdPresent: !!appId,
            metaConfigIdPresent: !!configId,
            graphVersion,
          });
          reject(err);
          return;
        }

        // Mask code in logs — first 8 chars only
        logSignup("embedded_signup.fb.login.callback", {
          debugId,
          codePrefix: `${code.slice(0, 8)}…`,
          status: "code_received",
        });

        // Poll up to 10 s for the WA_EMBEDDED_SIGNUP postMessage.
        const deadline = Date.now() + 10_000;

        function waitForSessionInfo() {
          if (wabaId && phoneNumberId) {
            cleanup();
            logSignup("embedded_signup.ready_for_exchange", {
              debugId,
              waba_id: wabaId,
              phone_number_id: phoneNumberId,
            });
            resolve({
              code: code!,
              waba_id: wabaId,
              phone_number_id: phoneNumberId,
              business_id: businessId,
            });
            return;
          }

          if (Date.now() >= deadline) {
            cleanup();
            logSignup("embedded_signup.timeout_waiting_for_data", {
              debugId,
              hasCode: true,
              hasWabaId: wabaId != null,
              hasPhoneNumberId: phoneNumberId != null,
              lastMessageOrigin,
              lastMessageShape,
            });

            let message: string;
            if (isDebugMode()) {
              // Detailed message in debug mode for the developer
              message =
                `A Meta autorizou o login (code recebido), mas não retornou os dados do número WhatsApp ` +
                `(WA_EMBEDDED_SIGNUP). ` +
                `lastOrigin=${lastMessageOrigin ?? "nenhuma mensagem"} ` +
                `debugId=${debugId}`;
            } else {
              message =
                "A Meta autorizou o login, mas não retornou os dados do número do WhatsApp. " +
                "Verifique se a configuração usada é de WhatsApp Embedded Signup.";
            }

            const err = new Error(message);
            captureSignupError(err, {
              step: "timeout_waiting_session_info",
              debugId,
              hasCode: true,
              hasSessionInfo: false,
              lastMessageOrigin,
              lastMessageShape,
              metaAppIdPresent: !!appId,
              metaConfigIdPresent: !!configId,
              graphVersion,
            });
            reject(err);
            return;
          }

          setTimeout(waitForSessionInfo, 50);
        }

        waitForSessionInfo();
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        extras: {
          feature: "whatsapp_embedded_signup",
          sessionInfoVersion: 2,
        },
      },
    );
  });
}
