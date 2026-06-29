/**
 * Meta / Facebook JS SDK loader and WhatsApp Embedded Signup flow helpers.
 *
 * The SDK is loaded lazily — only when the user initiates the flow.
 * Multiple calls to loadMetaSdk() are safe; the script is injected once.
 *
 * This implementation targets the "Facebook Login for Business" flow, where
 * the popup returns only an authorization code. waba_id and phone_number_id
 * are NOT available via postMessage in this flow — the backend discovers them
 * from the token's granular_scopes after code exchange.
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
        options: { config_id: string; response_type: string; override_default_response_type: boolean; redirect_uri?: string },
      ) => void;
    };
    fbAsyncInit?: () => void;
  }
}

export interface EmbeddedSignupData {
  code: string;
  redirect_uri: string;
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
 * Run the Facebook Login for Business flow and return the authorization code.
 *
 * The backend will use this code to:
 *  1. Exchange it for a user access token
 *  2. Discover the WABA and phone number from the token's granular_scopes
 *  3. Create the WhatsApp channel
 */
export function runEmbeddedSignup(): Promise<EmbeddedSignupData> {
  const configId = process.env.NEXT_PUBLIC_META_CONFIG_ID;
  if (!configId || !process.env.NEXT_PUBLIC_META_APP_ID) {
    return Promise.reject(
      new Error("A conexão com a Meta ainda não está configurada neste ambiente."),
    );
  }

  return new Promise<EmbeddedSignupData>((resolve, reject) => {
    // The redirect_uri passed to FB.login must match exactly what the backend
    // sends to Meta during code exchange. We use the origin root so it can be
    // registered as a valid OAuth redirect URI in the Facebook app settings.
    const redirect_uri = window.location.origin + "/";

    window.FB!.login(
      (response) => {
        if (response.status !== "connected" || !response.authResponse) {
          reject(new Error("Conexão cancelada. Tente novamente quando quiser."));
          return;
        }

        const code = response.authResponse.code ?? null;
        if (!code) {
          reject(new Error("Código de autorização não recebido da Meta. Tente novamente."));
          return;
        }

        resolve({ code, redirect_uri });
      },
      {
        config_id: configId,
        response_type: "code",
        override_default_response_type: true,
        redirect_uri,
      } as Parameters<NonNullable<typeof window.FB>["login"]>[1],
    );
  });
}
