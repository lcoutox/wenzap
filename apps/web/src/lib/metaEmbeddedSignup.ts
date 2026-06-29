/**
 * Meta / Facebook JS SDK loader and WhatsApp Embedded Signup flow helpers.
 *
 * The SDK is loaded lazily — only when the user initiates the flow.
 * Multiple calls to loadMetaSdk() are safe; the script is injected once.
 *
 * Flow:
 *  1. FB.login() opens the Meta popup with extras.feature = "whatsapp_embedded_signup".
 *  2. The popup fires a WA_EMBEDDED_SIGNUP postMessage with waba_id + phone_number_id.
 *  3. The FB.login callback fires with authResponse.code.
 *  4. Both signals are required before resolving. A 10-second polling loop handles
 *     the race where code arrives before the postMessage.
 *
 * No redirect_uri is passed to FB.login or to the backend — the JS SDK handles
 * the popup redirect internally via xd_arbiter and it must not be overridden.
 */

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
        callback: (response: { authResponse?: { code?: string } | null; status: string }) => void,
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

const META_TRUSTED_ORIGINS = new Set([
  "https://www.facebook.com",
  "https://web.facebook.com",
  "https://facebook.com",
  "https://business.facebook.com",
]);

export interface EmbeddedSignupData {
  code: string;
  waba_id: string;
  phone_number_id: string;
  business_id?: string | null;
}

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
      window.FB!.init({
        appId,
        autoLogAppEvents: true,
        xfbml: false,
        version,
      });
      resolve();
    };

    if (document.getElementById("facebook-jssdk")) {
      return;
    }

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

/**
 * Run the WhatsApp Embedded Signup flow.
 *
 * Resolves with { code, waba_id, phone_number_id, business_id } when both the
 * authorization code and the WA_EMBEDDED_SIGNUP postMessage are received.
 * Rejects with a user-facing error message on cancellation or timeout.
 */
export function runEmbeddedSignup(): Promise<EmbeddedSignupData> {
  const configId = process.env.NEXT_PUBLIC_META_CONFIG_ID;
  if (!configId || !process.env.NEXT_PUBLIC_META_APP_ID) {
    return Promise.reject(
      new Error("A conexão com a Meta ainda não está configurada neste ambiente."),
    );
  }

  return new Promise<EmbeddedSignupData>((resolve, reject) => {
    let code: string | null = null;
    let wabaId: string | null = null;
    let phoneNumberId: string | null = null;
    let businessId: string | null = null;

    function onMessage(event: MessageEvent) {
      if (!META_TRUSTED_ORIGINS.has(event.origin)) return;
      try {
        const data =
          typeof event.data === "string" ? JSON.parse(event.data) : event.data;
        if (data?.type !== "WA_EMBEDDED_SIGNUP") return;

        if (data.event === "FINISH" && data.data) {
          wabaId = data.data.waba_id ?? null;
          phoneNumberId = data.data.phone_number_id ?? null;
          businessId = data.data.business_id ?? null;
        }
      } catch {
        // non-JSON message — ignore
      }
    }

    window.addEventListener("message", onMessage);

    const cleanup = () => window.removeEventListener("message", onMessage);

    window.FB!.login(
      (response) => {
        if (response.status !== "connected" || !response.authResponse) {
          cleanup();
          reject(new Error("Conexão cancelada. Tente novamente quando quiser."));
          return;
        }

        code = response.authResponse.code ?? null;
        if (!code) {
          cleanup();
          reject(new Error("Código de autorização não recebido da Meta. Tente novamente."));
          return;
        }

        // Poll up to 10 s for the WA_EMBEDDED_SIGNUP postMessage.
        // The postMessage may arrive slightly before or after the FB.login callback.
        const deadline = Date.now() + 10_000;
        function waitForSessionInfo() {
          if (wabaId && phoneNumberId) {
            cleanup();
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
            reject(
              new Error(
                "Não foi possível obter os dados do WhatsApp Business. Complete o fluxo da Meta e tente novamente.",
              ),
            );
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
