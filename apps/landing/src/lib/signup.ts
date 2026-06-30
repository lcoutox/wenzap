"use client";

import { readUTMs } from "./tracking";

const APP_URL =
  process.env.NEXT_PUBLIC_APP_URL ?? "https://app.wenzap.com.br";

/**
 * Returns the signup URL with UTM parameters passed through as query params.
 * Call this client-side so localStorage UTMs are available.
 */
export function getAppSignupUrl(): string {
  const base = `${APP_URL}/sign-up`;
  if (typeof window === "undefined") return base;

  const utms = readUTMs();
  const params = new URLSearchParams(utms);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}
