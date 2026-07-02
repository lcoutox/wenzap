"use client";

import { useState } from "react";
import { Mail, CheckCircle, LogOut } from "lucide-react";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { useAppAuth } from "@/contexts/AuthContext";
import { api, ApiError } from "@/lib/api";

export default function VerifyEmailRequiredPage() {
  const { user, logout } = useAppAuth();
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  async function handleResend() {
    if (loading || sent) return;
    setLoading(true);
    setError("");
    try {
      await api.auth.resendVerificationEmail();
      setSent(true);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError("Muitas tentativas. Aguarde alguns minutos antes de reenviar.");
        } else {
          setError("Não foi possível enviar. Tente novamente.");
        }
      } else {
        setError("Erro inesperado. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-nb-bg p-6">
      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-10">
        <WenzapIcon size={28} />
        <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-nb-surface border border-nb-border rounded-2xl p-8 space-y-6 shadow-lg">

        {/* Icon */}
        <div className="flex justify-center">
          <div className="w-14 h-14 rounded-2xl bg-nb-primary-bg border border-nb-primary/20
                          flex items-center justify-center">
            <Mail className="w-7 h-7 text-nb-primary-strong" />
          </div>
        </div>

        {/* Heading */}
        <div className="text-center space-y-2">
          <h1 className="text-xl font-bold text-nb-text">Verifique seu e-mail</h1>
          <p className="text-sm text-nb-secondary leading-relaxed">
            Enviamos um link de confirmação para{" "}
            <span className="font-medium text-nb-text">{user?.email ?? "seu e-mail"}</span>.
            <br />
            Confirme para liberar o acesso ao Wenzap.
          </p>
        </div>

        {/* Success state */}
        {sent && (
          <div className="flex items-start gap-3 rounded-xl bg-nb-success/10 border border-nb-success/20
                          p-4 text-sm text-nb-success">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>E-mail reenviado. Verifique sua caixa de entrada (e o spam).</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <p className="text-xs text-nb-danger text-center">{error}</p>
        )}

        {/* Actions */}
        <div className="space-y-3">
          {!sent ? (
            <button
              type="button"
              onClick={handleResend}
              disabled={loading}
              className="w-full py-2.5 rounded-xl bg-nb-primary text-nb-bg text-sm font-semibold
                         hover:opacity-90 disabled:opacity-40 transition-opacity cursor-pointer"
            >
              {loading ? "Enviando..." : "Reenviar e-mail"}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setSent(false)}
              className="w-full py-2.5 rounded-xl border border-nb-border text-nb-secondary text-sm
                         font-medium hover:text-nb-text transition-colors cursor-pointer"
            >
              Reenviar novamente
            </button>
          )}

          <button
            type="button"
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl
                       border border-nb-border text-nb-secondary text-sm font-medium
                       hover:text-nb-text transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4" />
            Sair
          </button>
        </div>

        <p className="text-center text-xs text-nb-muted">
          Não recebeu? Verifique a pasta de spam ou aguarde alguns minutos.
        </p>
      </div>
    </div>
  );
}
