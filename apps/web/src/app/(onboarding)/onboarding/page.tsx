"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAppAuth } from "@/contexts/AuthContext";
import { OnboardingFlow } from "@/components/onboarding/OnboardingFlow";

export default function OnboardingPage() {
  const { isLoaded, isSignedIn } = useAppAuth();
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }

    void api.onboarding.status()
      .then((status) => {
        if (status.completed) router.replace("/dashboard");
        else setChecking(false);
      })
      .catch(() => setChecking(false));
  }, [isLoaded, isSignedIn, router]);

  if (checking) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="w-6 h-6 rounded-full border-2 border-nb-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  return <OnboardingFlow />;
}
