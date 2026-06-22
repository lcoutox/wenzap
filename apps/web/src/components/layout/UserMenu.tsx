"use client";

import { UserButton } from "@clerk/nextjs";

export function UserMenu() {
  return (
    <div className="flex items-center gap-2">
      <UserButton afterSignOutUrl="/sign-in" />
    </div>
  );
}
