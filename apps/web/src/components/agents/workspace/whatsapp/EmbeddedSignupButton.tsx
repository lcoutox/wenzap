"use client";

import { useState } from "react";
import { Loader2, MessageCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { WhatsAppChannel } from "@/lib/api";
import { loadMetaSdk, runEmbeddedSignup } from "@/lib/metaEmbeddedSignup";
import { captureSignupError, logSignup } from "@/lib/signupObservability";

interface Props {
  agentId: string;
  onSuccess: (channel: WhatsAppChannel) => void;
}

type Step =
  | "idle"
  | "loading_state"
  | "loading_sdk"
  | "waiting_meta"
  | "exchanging"
  | "done";

const STEP_LABELS: Record<Step, string> = {
  idle: "Conectar com Meta",
  loading_state: "Preparando...",
  loading_sdk: "Carregando SDK...",
  waiting_meta: "Aguardando Meta...",
  exchanging: "Conectando canal...",
  done: "Conectado!",
};

export function EmbeddedSignupButton({ agentId, onSuccess }: Props) {
  const [step, setStep] = useState<Step>("idle");
  const [error, setError] = useState<string | null>(null);
  const [debugId, setDebugId] = useState<string | null>(null);

  const busy = step !== "idle" && step !== "done";

  async function handleConnect() {
    setError(null);

    // Generate a correlation id for this attempt — logged frontend + backend
    const attemptDebugId = crypto.randomUUID();
    setDebugId(attemptDebugId);

    logSignup("embedded_signup.start", { debugId: attemptDebugId, agentId });
    setStep("loading_state");

    try {
      // 1. Get CSRF state from backend
      logSignup("embedded_signup.state.request", { debugId: attemptDebugId });
      const { state } = await api.channels.whatsappEmbeddedSignup.createState(
        agentId,
        attemptDebugId,
      );
      logSignup("embedded_signup.state.success", { debugId: attemptDebugId });

      // 2. Load FB SDK
      logSignup("embedded_signup.sdk.load.start", { debugId: attemptDebugId });
      setStep("loading_sdk");
      await loadMetaSdk();
      logSignup("embedded_signup.sdk.load.success", { debugId: attemptDebugId });

      // 3. Launch Meta popup — waits for code + WA_EMBEDDED_SIGNUP postMessage
      setStep("waiting_meta");
      const { code, waba_id, phone_number_id, business_id } =
        await runEmbeddedSignup(attemptDebugId);

      // 4. Exchange with backend
      logSignup("embedded_signup.exchange.start", {
        debugId: attemptDebugId,
        waba_id,
        phone_number_id,
      });
      setStep("exchanging");
      const channel = await api.channels.whatsappEmbeddedSignup.exchange(
        { code, state, waba_id, phone_number_id, business_id },
        attemptDebugId,
      );

      logSignup("embedded_signup.exchange.success", {
        debugId: attemptDebugId,
        channelId: (channel as { id?: string }).id,
      });

      setStep("done");
      onSuccess(channel as WhatsAppChannel);
    } catch (e) {
      setStep("idle");

      if (e instanceof ApiError) {
        const msg =
          "Não foi possível concluir a conexão com a Meta. Tente novamente ou fale com o suporte Wenzap.";
        setError(msg);
        logSignup("embedded_signup.exchange.failed", {
          debugId: attemptDebugId,
          status: e.status,
          detail: e.message,
        });
        captureSignupError(new Error(msg), {
          step: "exchange_api_error",
          debugId: attemptDebugId,
          hasCode: true,
          hasSessionInfo: true,
          metaAppIdPresent: !!process.env.NEXT_PUBLIC_META_APP_ID,
          metaConfigIdPresent: !!process.env.NEXT_PUBLIC_META_CONFIG_ID,
        });
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("A conexão foi cancelada ou não foi concluída.");
      }
    }
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={handleConnect}
        disabled={busy}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-[#25D366]/10 border border-[#25D366]/20 text-[#25D366] text-sm font-medium hover:bg-[#25D366]/20 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {busy ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <MessageCircle className="w-4 h-4" />
        )}
        {STEP_LABELS[step]}
      </button>

      {error && (
        <div className="space-y-1">
          <p className="text-xs text-nb-danger leading-relaxed">{error}</p>
          {debugId && (
            <p className="text-[10px] text-nb-muted font-mono select-all">
              Diagnóstico: {debugId}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
