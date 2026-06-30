"use client";

import { useEffect } from "react";
import { captureUTMs, trackLandingEvent } from "@/lib/tracking";

export function LandingTracker() {
  useEffect(() => {
    captureUTMs();
    trackLandingEvent("lp_view");
  }, []);

  return null;
}
