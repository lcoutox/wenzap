"use client";

import { useState } from "react";
import { Loader2, MessageCircle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { WhatsAppChannel } from "@/lib/api";
import { loadMetaSdk, runEmbeddedSignup } from "@/lib/metaEmbeddedSignup";

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

  const busy = step !== "idle" && step !== "done";

  async function handleConnect() {
    setError(null);
    setStep("loading_state");

    try {
      // 1. Get CSRF state from backend
      const { state } = await api.channels.whatsappEmbeddedSignup.createState(agentId);

      // 2. Load FB SDK
      setStep("loading_sdk");
      await loadMetaSdk();

      // 3. Launch Meta popup and capture authorization code
      setStep("waiting_meta");
      const { code } = await runEmbeddedSignup();

      // 4. Exchange with backend — WABA and phone number are auto-discovered
      //    from the token's granular_scopes (Facebook Login for Business flow)
      setStep("exchanging");
      const channel = await api.channels.whatsappEmbeddedSignup.exchange({ code, state });

      setStep("done");
      onSuccess(channel as WhatsAppChannel);
    } catch (e) {
      setStep("idle");
      if (e instanceof ApiError) {
        setError(
          "Não foi possível conectar o WhatsApp. Verifique sua conta Meta ou tente novamente.",
        );
      } else if (e instanceof Error) {
        setError(e.message);
      } else {
        setError("Erro inesperado. Tente novamente.");
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
        <p className="text-xs text-nb-danger leading-relaxed">{error}</p>
      )}
    </div>
  );
}
