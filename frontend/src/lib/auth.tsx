import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { get, hasToken, post, setToken, setUnauthorizedHandler } from "./api";

export type Role = "LEARNER" | "INSTRUCTOR" | "ACADEMIC_ADMIN" | "SUPPORT" | "PLATFORM_ADMIN";
export interface Me { app_user_id: string; email: string; role: Role; student_id: string | null; program_id: string | null }

interface AuthState { me: Me | null; loading: boolean; signIn: (email: string, password: string) => Promise<void>; signOut: () => void }
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(hasToken());
  const qc = useQueryClient();

  const signOut = useCallback(() => { setToken(null); setMe(null); qc.clear(); }, [qc]);
  useEffect(() => setUnauthorizedHandler(signOut), [signOut]);
  useEffect(() => {
    if (!hasToken()) return;
    get<Me>("/auth/me").then(setMe).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const res = await post<{ token: string }>("/auth/login", { email, password });
    setToken(res.token);
    setMe(await get<Me>("/auth/me"));
  }, []);

  const value = useMemo(() => ({ me, loading, signIn, signOut }), [me, loading, signIn, signOut]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

export const isStaff = (r: Role) => r !== "LEARNER";
export const seesMoney = (r: Role) => r !== "INSTRUCTOR";
