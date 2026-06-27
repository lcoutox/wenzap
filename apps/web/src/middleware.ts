import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/sso-callback(.*)",
  "/onboarding(.*)",
  "/embed(.*)",
]);

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    const authObj = await auth();
    // Clerk marks sessions as "pending" when there are unresolved tasks
    // (e.g. choose-organization). Since we do not use Clerk Organizations,
    // treat any pending session that has a valid userId as authenticated.
    if (authObj.userId && authObj.sessionStatus === "pending") {
      return;
    }
    await auth.protect();
  }
});

export const config = {
  matcher: ["/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)", "/(api|trpc)(.*)"],
};
