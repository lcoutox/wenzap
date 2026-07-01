"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Subscription } from "@/lib/api";
import { PlanUsageSettingsSection } from "@/components/settings/PlanUsageSettingsSection";
import { PlansSection } from "@/components/plan/PlansSection";

export default function PlanPage() {
  const [subscription, setSubscription] = useState<Subscription | null>(null);

  useEffect(() => {
    api.plans.current().then(setSubscription).catch(() => {});
  }, []);

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-xl font-bold text-nb-text">Plano e uso</h1>
        <p className="text-sm text-nb-muted mt-0.5">Seu plano atual, consumo do período e opções de upgrade.</p>
      </div>

      <PlanUsageSettingsSection />

      <div className="border-t border-nb-border" />

      <PlansSection subscription={subscription} />
    </div>
  );
}
