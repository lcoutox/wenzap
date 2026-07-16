import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const AUTH_COOKIE = "wenzap_session";

// Set SIGNUP_ENABLED=false to block self-serve account creation (e.g. before
// public launch, or during a production testing window). Existing sessions
// are unaffected — this only gates the /sign-up route.
const SIGNUP_ENABLED = process.env.SIGNUP_ENABLED !== "false";

const PUBLIC_PREFIXES = [
  "/sign-in",
  "/sign-up",
  "/embed",
  "/public",
  "/widget",
  // Verification pages: public so anyone with the link can confirm.
  // Authenticated users must NOT be redirected to /dashboard from these.
  "/verify-email",
  "/verify-email-required",
];

const PROTECTED_PREFIXES = [
  "/dashboard",
  "/onboarding",
];

function isPublic(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/") || pathname.startsWith(p + "?"));
}

function isProtected(pathname: string): boolean {
  return PROTECTED_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasSession = req.cookies.has(AUTH_COOKIE);

  if (isProtected(pathname) && !hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/sign-in";
    url.searchParams.set("redirect_url", pathname);
    return NextResponse.redirect(url);
  }

  if (!SIGNUP_ENABLED && pathname.startsWith("/sign-up") && !hasSession) {
    const url = req.nextUrl.clone();
    url.pathname = "/sign-in";
    url.search = "";
    return NextResponse.redirect(url);
  }

  // Some public routes must be accessible to authenticated users too:
  // /embed — would render dashboard in iframe instead of chat UI.
  // /verify-email* — user may be authenticated but not yet verified.
  if (
    isPublic(pathname) &&
    hasSession &&
    !pathname.startsWith("/embed") &&
    !pathname.startsWith("/verify-email")
  ) {
    const url = req.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|woff2?|ttf)).*)",
  ],
};
