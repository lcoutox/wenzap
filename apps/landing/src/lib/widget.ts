"use client";

declare global {
  interface Window {
    WenzapWidget?: { open: () => void };
  }
}

export function openWenzapWidget() {
  if (typeof window === "undefined") return;

  const MAX_ATTEMPTS = 20;
  const DELAY_MS = 150;
  let attempts = 0;

  const tryOpen = () => {
    if (window.WenzapWidget?.open) {
      window.WenzapWidget.open();
      return;
    }
    attempts += 1;
    if (attempts < MAX_ATTEMPTS) {
      window.setTimeout(tryOpen, DELAY_MS);
    }
  };

  tryOpen();
}
