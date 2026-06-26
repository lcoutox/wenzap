"use client";

import { useSignUp } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { AuthLeftPanel } from "@/components/auth/AuthLeftPanel";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { clerkErrorMessage, isClerkError } from "@/components/auth/clerkErrors";

type Step = "register" | "verify";

// ── Google OAuth button ───────────────────────────────────────────────────────

function GoogleButton({ onClick, loading }: { onClick: () => void; loading: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-xl bg-nb-elevated border border-nb-border text-nb-secondary text-sm font-medium hover:bg-nb-soft hover:text-nb-text transition-colors disabled:opacity-40 cursor-pointer"
    >
      <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
        <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
        <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
        <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
        <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 6.29C4.672 4.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
      </svg>
      Continuar com Google
    </button>
  );
}

// ── Sign-up form ──────────────────────────────────────────────────────────────

export default function SignUpPage() {
  const { signUp, setActive, isLoaded } = useSignUp();
  const router = useRouter();

  const [step, setStep]         = useState<Step>("register");
  const [name, setName]         = useState("");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode]         = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const afterUrl = process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL ?? "/dashboard";

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoaded || loading) return;
    setError("");
    setLoading(true);

    try {
      const result = await signUp.create({
        firstName: name.trim() || undefined,
        emailAddress: email,
        password,
      });

      if (result.status === "complete") {
        await setActive({ session: result.createdSessionId });
        router.push(afterUrl);
      } else if (result.status === "missing_requirements") {
        await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
        setStep("verify");
      } else {
        setError("Não foi possível criar a conta. Tente novamente.");
      }
    } catch (err: unknown) {
      if (isClerkError(err)) {
        setError(clerkErrorMessage(err.errors));
      } else {
        setError("Não foi possível criar a conta. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoaded || loading) return;
    setError("");
    setLoading(true);

    try {
      const result = await signUp.attemptEmailAddressVerification({ code });

      if (result.status === "complete") {
        await setActive({ session: result.createdSessionId });
        router.push(afterUrl);
      } else {
        setError("Verificação incompleta. Tente novamente.");
      }
    } catch (err: unknown) {
      if (isClerkError(err)) {
        setError(clerkErrorMessage(err.errors));
      } else {
        setError("Código inválido ou expirado.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (!isLoaded || loading) return;
    setError("");
    try {
      await signUp.prepareEmailAddressVerification({ strategy: "email_code" });
    } catch {
      setError("Não foi possível reenviar o código.");
    }
  }

  async function handleGoogle() {
    if (!isLoaded || loading) return;
    setError("");
    try {
      await signUp.authenticateWithRedirect({
        strategy: "oauth_google",
        redirectUrl: "/sso-callback",
        redirectUrlComplete: afterUrl,
      });
    } catch (err: unknown) {
      if (isClerkError(err)) {
        setError(clerkErrorMessage(err.errors));
      } else {
        setError("Login com Google indisponível no momento.");
      }
    }
  }

  // ── Verify step ────────────────────────────────────────────────────────────

  if (step === "verify") {
    return (
      <div className="min-h-screen flex bg-nb-bg">
        <AuthLeftPanel />

        <div className="flex-1 flex flex-col items-center justify-center p-8">
          <div className="flex lg:hidden items-center gap-2.5 mb-8">
            <WenzapIcon size={28} />
            <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
          </div>

          <div className="w-full max-w-sm">
            <div className="mb-8">
              <h2 className="text-2xl font-bold text-nb-text">Verifique seu e-mail</h2>
              <p className="text-nb-muted text-sm mt-1">
                Digite o código enviado para <span className="text-nb-secondary font-medium">{email}</span>.
              </p>
            </div>

            <form onSubmit={handleVerify} noValidate className="space-y-4">
              <div>
                <label htmlFor="code" className="block text-xs font-medium text-nb-secondary mb-1.5">
                  Código de verificação
                </label>
                <input
                  id="code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="000000"
                  maxLength={6}
                  className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted text-center tracking-[0.4em] focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
                />
              </div>

              {error && (
                <p role="alert" aria-live="polite" className="text-nb-danger text-xs">
                  {error}
                </p>
              )}

              <button
                type="submit"
                disabled={loading || !isLoaded || code.length < 6}
                className="w-full py-2.5 rounded-xl bg-nb-primary text-nb-bg text-sm font-semibold hover:opacity-90 disabled:opacity-40 transition-opacity cursor-pointer"
              >
                {loading ? "Verificando..." : "Verificar"}
              </button>
            </form>

            <p className="mt-4 text-center text-xs text-nb-muted">
              Não recebeu o código?{" "}
              <button
                type="button"
                onClick={handleResend}
                className="text-nb-primary hover:text-nb-primary-strong transition-colors font-medium cursor-pointer"
              >
                Reenviar
              </button>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ── Register step ──────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen flex bg-nb-bg">
      <AuthLeftPanel />

      <div className="flex-1 flex flex-col items-center justify-center p-8">
        <div className="flex lg:hidden items-center gap-2.5 mb-8">
          <WenzapIcon size={28} />
          <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-nb-text">Crie sua conta no Wenzap</h2>
            <p className="text-nb-muted text-sm mt-1">Comece a operar agentes inteligentes.</p>
          </div>

          <GoogleButton onClick={handleGoogle} loading={loading} />

          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-nb-border" />
            <span className="text-nb-muted text-xs">ou</span>
            <div className="flex-1 h-px bg-nb-border" />
          </div>

          <form onSubmit={handleRegister} noValidate className="space-y-4">
            <div>
              <label htmlFor="name" className="block text-xs font-medium text-nb-secondary mb-1.5">
                Nome <span className="text-nb-muted font-normal">(opcional)</span>
              </label>
              <input
                id="name"
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Seu nome"
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
              />
            </div>

            <div>
              <label htmlFor="email" className="block text-xs font-medium text-nb-secondary mb-1.5">
                E-mail
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="seu@email.com"
                className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-xs font-medium text-nb-secondary mb-1.5">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mínimo 8 caracteres"
                  className="w-full bg-nb-elevated border border-nb-border rounded-xl px-3 py-2.5 pr-10 text-sm text-nb-text placeholder:text-nb-muted focus:outline-none focus:border-nb-primary focus:ring-1 focus:ring-nb-primary/30 transition-colors"
                />
                <button
                  type="button"
                  tabIndex={-1}
                  onClick={() => setShowPwd((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-nb-muted hover:text-nb-secondary transition-colors cursor-pointer"
                  aria-label={showPwd ? "Ocultar senha" : "Mostrar senha"}
                >
                  {showPwd ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {error && (
              <p role="alert" aria-live="polite" className="text-nb-danger text-xs">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !isLoaded}
              className="w-full py-2.5 rounded-xl bg-nb-primary text-nb-bg text-sm font-semibold hover:opacity-90 disabled:opacity-40 transition-opacity cursor-pointer"
            >
              {loading ? "Criando conta..." : "Criar conta"}
            </button>
          </form>

          <p className="mt-6 text-center text-xs text-nb-muted">
            Já tem uma conta?{" "}
            <Link href="/sign-in" className="text-nb-primary hover:text-nb-primary-strong transition-colors font-medium">
              Entrar
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
