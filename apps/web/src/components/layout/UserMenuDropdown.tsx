"use client";

import { useRef, useState, useEffect } from "react";
import { useClerk, useUser } from "@clerk/nextjs";
import { LogOut, ChevronDown, User } from "lucide-react";

export function UserMenuDropdown() {
  const { signOut } = useClerk();
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const name = user?.fullName ?? user?.firstName ?? "Usuário";
  const email = user?.primaryEmailAddress?.emailAddress ?? "";
  const avatarUrl = user?.imageUrl;

  const initials = name
    .split(" ")
    .slice(0, 2)
    .map((n) => n[0])
    .join("")
    .toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-gray-300 hover:bg-gray-800 transition-colors"
      >
        {/* Avatar */}
        {avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt={name} className="w-7 h-7 rounded-full object-cover" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">
            {initials || <User className="w-3.5 h-3.5" />}
          </div>
        )}
        <span className="hidden sm:block max-w-[120px] truncate font-medium">{name}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-gray-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 rounded-lg bg-gray-900 border border-gray-800 shadow-xl z-50 overflow-hidden">
          {/* User info */}
          <div className="px-4 py-3 border-b border-gray-800">
            <p className="text-sm font-medium text-gray-100 truncate">{name}</p>
            <p className="text-xs text-gray-500 truncate mt-0.5">{email}</p>
          </div>

          {/* Actions */}
          <div className="py-1">
            <button
              onClick={() => signOut({ redirectUrl: "/sign-in" })}
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-gray-400 hover:bg-gray-800 hover:text-gray-100 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
