"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Eye, EyeOff } from "lucide-react";
import { AuthLeftPanel } from "@/components/auth/AuthLeftPanel";
import { WenzapIcon } from "@/components/auth/WenzapIcon";
import { authErrorMessage } from "@/components/auth/authErrors";
import { useAppAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

export default function SignInPage() {
  const { login } = useAppAuth();
  const router = useRouter();

  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;
    setError("");

    if (!email.trim() || !password) {
      setError("Preencha e-mail e senha.");
      return;
    }

    setLoading(true);
    try {
      await login({ email: email.trim(), password });

      // Check onboarding status to decide where to redirect.
      try {
        const onboarding = await api.onboarding.status();
        router.push(onboarding.completed ? "/dashboard" : "/onboarding");
      } catch {
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(authErrorMessage(err));
    } finally {
      setLoading(false);
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
              <label htmlFor="password" className="block text-xs font-medium text-nb-secondary mb-1.5">
                Senha
              </label>
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

            {error && (
              <p role="alert" aria-live="polite" className="text-nb-danger text-xs">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
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
