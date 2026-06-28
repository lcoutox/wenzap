"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import type { AuthUser, AuthWorkspace, LoginInput, SignupInput } from "@/lib/api";

type AuthState = {
  user: AuthUser | null;
  workspace: AuthWorkspace | null;
  isLoaded: boolean;
  isSignedIn: boolean;
};

type AuthContextValue = AuthState & {
  refresh: () => Promise<void>;
  login: (input: LoginInput) => Promise<void>;
  signup: (input: SignupInput) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    workspace: null,
    isLoaded: false,
    isSignedIn: false,
  });

  const refresh = useCallback(async () => {
    try {
      const me = await api.auth.me();
      setState({
        user: me.user,
        workspace: me.workspace,
        isLoaded: true,
        isSignedIn: true,
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setState({ user: null, workspace: null, isLoaded: true, isSignedIn: false });
      } else {
        // Unexpected error — mark loaded but unauthenticated; don't crash the app.
        setState({ user: null, workspace: null, isLoaded: true, isSignedIn: false });
      }
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(
    async (input: LoginInput) => {
      const me = await api.auth.login(input);
      setState({ user: me.user, workspace: me.workspace, isLoaded: true, isSignedIn: true });
    },
    [],
  );

  const signup = useCallback(
    async (input: SignupInput) => {
      const me = await api.auth.signup(input);
      setState({ user: me.user, workspace: me.workspace, isLoaded: true, isSignedIn: true });
    },
    [],
  );

  const logout = useCallback(async () => {
    await api.auth.logout();
    setState({ user: null, workspace: null, isLoaded: true, isSignedIn: false });
    router.push("/sign-in");
  }, [router]);

  return (
    <AuthContext.Provider value={{ ...state, refresh, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAppAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAppAuth must be used inside <AuthProvider>");
  return ctx;
}

export function useCurrentUser(): AuthUser | null {
  return useAppAuth().user;
}
