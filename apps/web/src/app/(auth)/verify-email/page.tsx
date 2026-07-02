"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";
import Link from "next/link";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { api, ApiError } from "@/lib/api";
import { useAppAuth } from "@/contexts/AuthContext";

type State = "verifying" | "success" | "error";

function VerifyEmailContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refresh } = useAppAuth();
  const [state, setState] = useState<State>("verifying");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    if (!token) {
      setState("error");
      setErrorMsg("Link inválido. Nenhum token encontrado.");
      return;
    }

    api.auth.verifyEmail(token)
      .then(async () => {
        await refresh();
        setState("success");
        setTimeout(() => router.push("/onboarding"), 3000);
      })
      .catch((err: unknown) => {
        setState("error");
        if (err instanceof ApiError && err.status === 400) {
          setErrorMsg("Este link é inválido ou já expirou. Solicite um novo link de verificação.");
        } else {
          setErrorMsg("Ocorreu um erro inesperado. Tente novamente.");
        }
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="w-full max-w-md bg-nb-surface border border-nb-border rounded-2xl p-8
                    space-y-6 shadow-lg text-center">

      {state === "verifying" && (
        <>
          <div className="flex justify-center">
            <Loader2 className="w-12 h-12 text-nb-primary animate-spin" />
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-bold text-nb-text">Verificando seu e-mail...</h1>
            <p className="text-sm text-nb-secondary">Aguarde um instante.</p>
          </div>
        </>
      )}

      {state === "success" && (
        <>
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-nb-success/10 border border-nb-success/20
                            flex items-center justify-center">
              <CheckCircle className="w-7 h-7 text-nb-success" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-bold text-nb-text">E-mail confirmado!</h1>
            <p className="text-sm text-nb-secondary leading-relaxed">
              Sua conta está verificada. Você será redirecionado em instantes.
            </p>
          </div>
          <Link
            href="/onboarding"
            className="inline-block w-full py-2.5 rounded-xl bg-nb-primary text-nb-bg
                       text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            Continuar
          </Link>
        </>
      )}

      {state === "error" && (
        <>
          <div className="flex justify-center">
            <div className="w-14 h-14 rounded-2xl bg-nb-danger/10 border border-nb-danger/20
                            flex items-center justify-center">
              <XCircle className="w-7 h-7 text-nb-danger" />
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-xl font-bold text-nb-text">Link inválido</h1>
            <p className="text-sm text-nb-secondary leading-relaxed">{errorMsg}</p>
          </div>
          <div className="space-y-3">
            <Link
              href="/verify-email-required"
              className="block w-full py-2.5 rounded-xl bg-nb-primary text-nb-bg
                         text-sm font-semibold hover:opacity-90 transition-opacity"
            >
              Reenviar e-mail de verificação
            </Link>
            <Link
              href="/sign-in"
              className="block w-full py-2.5 rounded-xl border border-nb-border
                         text-nb-secondary text-sm font-medium hover:text-nb-text transition-colors"
            >
              Voltar ao login
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-nb-bg p-6">
      <div className="flex items-center gap-2.5 mb-10">
        <WenzapIcon size={28} />
        <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
      </div>
      <Suspense
        fallback={
          <div className="w-full max-w-md bg-nb-surface border border-nb-border rounded-2xl p-8
                          flex items-center justify-center">
            <Loader2 className="w-10 h-10 text-nb-primary animate-spin" />
          </div>
        }
      >
        <VerifyEmailContent />
      </Suspense>
    </div>
  );
}
