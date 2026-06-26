"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { OnboardingFlow } from "@/components/onboarding/OnboardingFlow";

export default function OnboardingPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      router.replace("/sign-in");
      return;
    }

    void (async () => {
      const t = await getToken();
      if (!t) {
        router.replace("/sign-in");
        return;
      }
      try {
        const status = await api.onboarding.get(t);
        if (status.completed) {
          router.replace("/dashboard");
          return;
        }
      } catch {
        // If check fails, show the form anyway — backend will handle duplicates.
      }
      setToken(t);
      setChecking(false);
    })();
  }, [isLoaded, isSignedIn, getToken, router]);

  if (checking || !token) {
    return (
      <div className="flex-1 flex items-center justify-center min-h-screen">
        <div className="w-6 h-6 rounded-full border-2 border-nb-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  return <OnboardingFlow token={token} />;
}
