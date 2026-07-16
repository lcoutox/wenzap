"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Subscription } from "@/lib/api";
import { PlanUsageSettingsSection } from "@/components/settings/PlanUsageSettingsSection";
import { PlansSection } from "@/components/plan/PlansSection";

// After a successful Stripe Checkout, the webhook that activates the
// subscription can land a beat after the redirect back. Poll briefly so the
// page reflects the new plan without the admin manually refreshing.
const CHECKOUT_POLL_ATTEMPTS = 5;
const CHECKOUT_POLL_INTERVAL_MS = 1500;

function CheckoutStatusBanner({ upgraded }: { upgraded: boolean }) {
  const searchParams = useSearchParams();
  const checkout = searchParams.get("checkout");
  const [polling, setPolling] = useState(checkout === "success" && !upgraded);

  useEffect(() => {
    if (checkout === "success" && upgraded) setPolling(false);
  }, [checkout, upgraded]);

  if (checkout === "success") {
    return (
      <div className="rounded-xl border border-nb-success bg-nb-success/5 p-4 flex items-start gap-3">
        {polling ? (
          <Loader2 className="w-5 h-5 text-nb-success flex-shrink-0 mt-0.5 animate-spin" />
        ) : (
          <CheckCircle className="w-5 h-5 text-nb-success flex-shrink-0 mt-0.5" />
        )}
        <p className="text-sm text-nb-text">
          {polling
            ? "Pagamento confirmado — ativando seu novo plano..."
            : "Pagamento confirmado! Seu plano foi atualizado."}
        </p>
      </div>
    );
  }

  if (checkout === "cancelled") {
    return (
      <div className="rounded-xl border border-nb-border bg-nb-elevated/30 p-4">
        <p className="text-sm text-nb-secondary">Checkout cancelado — nenhuma cobrança foi feita.</p>
      </div>
    );
  }

  return null;
}

export default function PlanPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const attemptsRef = useRef(0);

  const fetchSubscription = useCallback(async () => {
    const sub = await api.plans.current().catch(() => null);
    if (sub) setSubscription(sub);
    return sub;
  }, []);

  useEffect(() => {
    fetchSubscription();
  }, [fetchSubscription]);

  // Poll a few times only when we land back from a successful checkout and
  // the plan hasn't updated yet (webhook still in flight).
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (new URLSearchParams(window.location.search).get("checkout") !== "success") return;
    if (subscription && subscription.plan.code !== "starter") return;
    if (attemptsRef.current >= CHECKOUT_POLL_ATTEMPTS) return;

    const timer = setTimeout(async () => {
      attemptsRef.current += 1;
      await fetchSubscription();
    }, CHECKOUT_POLL_INTERVAL_MS);
    return () => clearTimeout(timer);
  }, [subscription, fetchSubscription]);

  const upgraded = !!subscription && subscription.plan.code !== "starter";

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-xl font-bold text-nb-text">Plano e uso</h1>
        <p className="text-sm text-nb-muted mt-0.5">Seu plano atual, consumo do período e opções de upgrade.</p>
      </div>

      <Suspense>
        <CheckoutStatusBanner upgraded={upgraded} />
      </Suspense>

      <PlanUsageSettingsSection />

      <div className="border-t border-nb-border" />

      <PlansSection subscription={subscription} />
    </div>
  );
}
