"use client";

import { useSignIn, useClerk } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { AuthLeftPanel } from "@/components/auth/AuthLeftPanel";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { clerkErrorMessage, isClerkError } from "@/components/auth/clerkErrors";

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

// ── Sign-in form ──────────────────────────────────────────────────────────────

export default function SignInPage() {
  const { signIn, setActive, isLoaded } = useSignIn();
  const { client, setActive: clerkSetActive } = useClerk();
  const router = useRouter();

  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  // Clerk redirects here as /sign-in/tasks?redirect_url=... (or #tasks/...)
  // when a pending session has a choose-organization task.
  // Pass organization: null to signal "no org" and activate the session.
  // The middleware also lets pending sessions with a valid userId through,
  // so the user reaches the dashboard even if setActive doesn't resolve the task.
  useEffect(() => {
    if (!client || typeof window === "undefined") return;
    const { pathname, hash, search } = window.location;
    const isClerksTaskRoute =
      pathname.includes("/tasks") ||
      hash.includes("choose-organization") ||
      search.includes("choose-organization");
    if (!isClerksTaskRoute) return;
    const pending = client.sessions.find((s) => s.status === "pending");
    if (!pending) return;
    void clerkSetActive({ session: pending.id, organization: null }).then(() =>
      router.replace("/dashboard"),
    );
  }, [client, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isLoaded || loading) return;
    setError("");
    setLoading(true);

    try {
      const result = await signIn.create({ identifier: email, password });

      if (result.status === "complete") {
        await setActive({ session: result.createdSessionId });
        router.push(process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL ?? "/dashboard");
      } else {
        setError("Não foi possível entrar. Tente novamente.");
      }
    } catch (err: unknown) {
      if (isClerkError(err)) {
        setError(clerkErrorMessage(err.errors));
      } else {
        setError("Não foi possível entrar. Tente novamente.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    if (!isLoaded || loading) return;
    setError("");
    try {
      await signIn.authenticateWithRedirect({
        strategy: "oauth_google",
        redirectUrl: "/sso-callback",
        redirectUrlComplete: process.env.NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL ?? "/dashboard",
      });
    } catch (err: unknown) {
      if (isClerkError(err)) {
        setError(clerkErrorMessage(err.errors));
      } else {
        setError("Login com Google indisponível no momento.");
      }
    }
  }

  return (
    <div className="min-h-screen flex bg-nb-bg">
      <AuthLeftPanel />

      {/* Right panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Mobile logo */}
        <div className="flex lg:hidden items-center gap-2.5 mb-8">
          <WenzapIcon size={28} />
          <span className="text-nb-text font-bold text-lg tracking-tight">Wenzap</span>
        </div>

        <div className="w-full max-w-sm">
          {/* Header */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-nb-text">Entre no Wenzap</h2>
            <p className="text-nb-muted text-sm mt-1">Acesse sua conta para continuar.</p>
          </div>

          {/* Google */}
          <GoogleButton onClick={handleGoogle} loading={loading} />

          {/* Divider */}
          <div className="flex items-center gap-3 my-5">
            <div className="flex-1 h-px bg-nb-border" />
            <span className="text-nb-muted text-xs">ou</span>
            <div className="flex-1 h-px bg-nb-border" />
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
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
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="password" className="block text-xs font-medium text-nb-secondary">
                  Senha
                </label>
              </div>
              <div className="relative">
                <input
                  id="password"
                  type={showPwd ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
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

            {/* Error */}
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
              {loading ? "Entrando..." : "Entrar"}
            </button>
          </form>

          {/* Sign-up link */}
          <p className="mt-6 text-center text-xs text-nb-muted">
            Não tem uma conta?{" "}
            <Link href="/sign-up" className="text-nb-primary hover:text-nb-primary-strong transition-colors font-medium">
              Criar conta
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
