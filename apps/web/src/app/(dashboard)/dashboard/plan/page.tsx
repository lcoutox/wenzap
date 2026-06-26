"use client";

import { PlanUsageSettingsSection } from "@/components/settings/PlanUsageSettingsSection";

export default function PlanPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-nb-text">Plano e uso</h1>
        <p className="text-sm text-nb-muted mt-0.5">Seu plano atual e consumo do período.</p>
      </div>
      <PlanUsageSettingsSection />
    </div>
  );
}
