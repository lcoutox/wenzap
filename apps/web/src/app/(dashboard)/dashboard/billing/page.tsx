"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle } from "lucide-react";

function SuccessAlert() {
  const searchParams = useSearchParams();
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("success") === "true") {
      setSuccess("Pagamento realizado com sucesso! Seu plano foi atualizado.");
      const timer = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [searchParams]);

  if (!success) return null;

  return (
    <div className="rounded-xl border border-nb-success bg-nb-success/5 p-4 flex gap-3">
      <CheckCircle className="w-5 h-5 text-nb-success flex-shrink-0 mt-0.5" />
      <p className="text-sm text-nb-text">{success}</p>
    </div>
  );
}

export default function BillingPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-nb-text">Faturamento</h1>
        <p className="text-sm text-nb-muted mt-0.5">Gerencie sua assinatura e método de pagamento</p>
      </div>

      <Suspense>
        <SuccessAlert />
      </Suspense>

      {/* Info Section */}
      <div className="rounded-xl border border-nb-border bg-nb-surface p-6 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-nb-text">Checkout Automático em Desenvolvimento</h2>
          <p className="text-sm text-nb-secondary mt-2 leading-relaxed">
            O sistema de faturamento com Stripe está sendo configurado em produção. Para solicitar um upgrade ou contratar Wenzap para sua empresa, entre em contato com nosso time.
          </p>
        </div>

        <div className="rounded-lg border border-nb-border bg-nb-elevated p-4 space-y-3">
          <p className="text-xs font-semibold text-nb-secondary uppercase tracking-wide">Formas de contato</p>
          <p className="text-sm text-nb-text">
            📧{" "}
            <a href="mailto:growth@wenzap.com.br" className="text-nb-primary hover:underline">
              growth@wenzap.com.br
            </a>
          </p>
          <p className="text-xs text-nb-muted">
            Resposta em até 1 dia útil.
          </p>
        </div>
      </div>

      {/* Plans Grid (informativo) */}
      <div>
        <h2 className="text-base font-semibold text-nb-text mb-4">Planos Disponíveis</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { name: "Starter", price: "R$ 0", desc: "Para começar com IA", features: ["Até 1 agente", "100 msgs/mês"] },
            { name: "Growth", price: "R$ 247", desc: "Para empresas", features: ["Até 10 agentes", "10.000 msgs/mês"] },
            { name: "Scale", price: "R$ 587", desc: "Para operações em escala", features: ["Agentes ilimitados", "100.000 msgs/mês"] },
          ].map((plan) => (
            <div key={plan.name} className="rounded-xl border border-nb-border bg-nb-surface p-4">
              <div className="mb-3">
                <h3 className="text-sm font-semibold text-nb-text">{plan.name}</h3>
                <p className="text-xs text-nb-muted mt-0.5">{plan.desc}</p>
              </div>
              <div className="mb-4">
                <span className="text-2xl font-bold text-nb-text">{plan.price}</span>
                <span className="text-xs text-nb-muted">/mês</span>
              </div>
              <ul className="space-y-1.5">
                {plan.features.map((f) => (
                  <li key={f} className="text-xs text-nb-secondary flex items-start gap-2">
                    <span className="text-nb-success">✓</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
