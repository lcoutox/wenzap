"use client";

import { MembersSettingsSection } from "@/components/settings/MembersSettingsSection";

export default function MembersPage() {
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-bold text-nb-text">Membros</h1>
        <p className="text-sm text-nb-muted mt-0.5">Gerencie os membros do seu workspace.</p>
      </div>
      <MembersSettingsSection />
    </div>
  );
}
