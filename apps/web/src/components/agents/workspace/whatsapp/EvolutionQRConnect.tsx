"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle, Loader2, QrCode, RefreshCcw, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Channel, WhatsAppChannel } from "@/lib/api";

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 3 * 60 * 1000; // QR codes expire; stop polling after 3 minutes

type FlowState =
  | { step: "idle" }
  | { step: "loading" }
  | { step: "qr"; channel: Channel; qrcodeBase64: string }
  | { step: "connected"; channel: Channel }
  | { step: "error"; message: string };

/**
 * "Connect via QR Code" flow for the Evolution API bridge provider.
 *
 * Bridge WhatsApp connection used until Meta approves the app for
 * multi-tenant self-serve Embedded Signup — see negocios/wenzap/plano-evolution-api.md.
 */
export function EvolutionQRConnect({
  agentId,
  onSuccess,
}: {
  agentId: string;
  onSuccess: (ch: WhatsAppChannel) => void;
}) {
  const [open, setOpen] = useState(false);
  const [flow, setFlow] = useState<FlowState>({ step: "idle" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timeoutRef.current) { clearTimeout(timeoutRef.current); timeoutRef.current = null; }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const startPolling = useCallback((channelId: string, channel: Channel, qrcodeBase64: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const { state } = await api.channels.whatsappEvolution.status(channelId);
        if (state === "open") {
          stopPolling();
          setFlow({ step: "connected", channel });
          onSuccess(channel as WhatsAppChannel);
        }
      } catch {
        // Transient polling errors are ignored — the interval keeps retrying
        // until the timeout below gives up.
      }
    }, POLL_INTERVAL_MS);

    timeoutRef.current = setTimeout(() => {
      stopPolling();
      setFlow((prev) =>
        prev.step === "qr"
          ? { step: "error", message: "O QR Code expirou. Gere um novo para tentar novamente." }
          : prev,
      );
    }, POLL_TIMEOUT_MS);
    // Keep referencing the latest QR while polling.
    void qrcodeBase64;
  }, [onSuccess, stopPolling]);

  async function handleStart() {
    setOpen(true);
    setFlow({ step: "loading" });
    try {
      const { channel, qrcode_base64 } = await api.channels.whatsappEvolution.connect(agentId);
      if (!qrcode_base64) {
        setFlow({ step: "error", message: "Não foi possível gerar o QR Code. Tente novamente." });
        return;
      }
      setFlow({ step: "qr", channel, qrcodeBase64: qrcode_base64 });
      startPolling(channel.id, channel, qrcode_base64);
    } catch (e) {
      setFlow({
        step: "error",
        message: e instanceof ApiError ? e.message : "Erro ao iniciar a conexão via QR Code.",
      });
    }
  }

  function handleClose() {
    stopPolling();
    setOpen(false);
    setFlow({ step: "idle" });
  }

  return (
    <>
      <button
        type="button"
        onClick={handleStart}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:border-nb-border-strong hover:text-nb-text transition-colors"
      >
        <QrCode className="w-4 h-4" />
        Conectar via QR Code
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 backdrop-blur-sm p-4">
          <div className="relative w-full max-w-sm bg-nb-surface border border-nb-border rounded-2xl shadow-xl my-8">
            <div className="flex items-center justify-between px-6 py-4 border-b border-nb-border">
              <div className="flex items-center gap-2.5">
                <QrCode className="w-4 h-4 text-nb-primary" />
                <h2 className="text-base font-semibold text-nb-text">Conectar via QR Code</h2>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="p-1.5 rounded-lg text-nb-muted hover:text-nb-secondary hover:bg-nb-elevated transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="px-6 py-6 flex flex-col items-center text-center gap-4">
              {flow.step === "loading" && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <Loader2 className="w-6 h-6 text-nb-primary animate-spin" />
                  <p className="text-sm text-nb-muted">Gerando QR Code...</p>
                </div>
              )}

              {flow.step === "qr" && (
                <>
                  <div className="w-56 h-56 rounded-xl overflow-hidden border border-nb-border bg-white p-2">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={flow.qrcodeBase64}
                      alt="QR Code para conectar o WhatsApp"
                      className="w-full h-full object-contain"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <p className="text-sm font-medium text-nb-secondary">
                      Escaneie com o WhatsApp
                    </p>
                    <p className="text-xs text-nb-muted leading-relaxed max-w-[240px]">
                      No celular: WhatsApp → Configurações → Aparelhos conectados → Conectar
                      aparelho.
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 text-xs text-nb-muted">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Aguardando conexão...
                  </div>
                </>
              )}

              {flow.step === "connected" && (
                <div className="flex flex-col items-center gap-3 py-8">
                  <CheckCircle className="w-10 h-10 text-nb-success" />
                  <p className="text-sm font-medium text-nb-text">WhatsApp conectado!</p>
                </div>
              )}

              {flow.step === "error" && (
                <div className="flex flex-col items-center gap-3 py-6">
                  <p className="text-sm text-nb-danger">{flow.message}</p>
                  <button
                    type="button"
                    onClick={handleStart}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-nb-elevated border border-nb-border text-nb-secondary hover:text-nb-text transition-colors"
                  >
                    <RefreshCcw className="w-3.5 h-3.5" />
                    Gerar novo QR Code
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
