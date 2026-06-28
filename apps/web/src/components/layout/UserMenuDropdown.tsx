"use client";

import { useRef, useState, useEffect } from "react";
import { LogOut, ChevronDown, User } from "lucide-react";
import { useAppAuth } from "@/contexts/AuthContext";

export function UserMenuDropdown() {
  const { user, logout } = useAppAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const name = user?.name ?? "Usuário";
  const email = user?.email ?? "";
  const avatarUrl = user?.avatar_url;
  const initials = name.split(" ").slice(0, 2).map((n) => n[0]).join("").toUpperCase();

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-xl px-2 py-1.5 text-sm text-nb-secondary hover:bg-nb-elevated transition-colors"
      >
        {avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatarUrl} alt={name} className="w-7 h-7 rounded-full object-cover" />
        ) : (
          <div className="w-7 h-7 rounded-full bg-nb-primary flex items-center justify-center text-white text-xs font-bold">
            {initials || <User className="w-3.5 h-3.5" />}
          </div>
        )}
        <span className="hidden sm:block max-w-[120px] truncate font-medium">{name}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-nb-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 rounded-xl bg-nb-surface border border-nb-border shadow-xl z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-nb-border">
            <p className="text-sm font-medium text-nb-text truncate">{name}</p>
            <p className="text-xs text-nb-muted truncate mt-0.5">{email}</p>
          </div>
          <div className="py-1">
            <button
              onClick={() => void logout()}
              className="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-nb-muted hover:bg-nb-elevated hover:text-nb-secondary transition-colors"
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
