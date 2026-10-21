"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { apiRequest, invalidateNavigationData } from "@/lib/api";

type Session = { configured: boolean; authenticated: boolean; is_admin: boolean; username: string | null; email: string | null; role: string | null; human_id: number | null };
const guest: Session = { configured: true, authenticated: false, is_admin: false, username: null, email: null, role: null, human_id: null };
type AdminContextValue = {
  session: Session; loading: boolean;
  signIn: (email: string, role: string) => Promise<void>;
  signOut: () => Promise<void>;
};
const AdminContext = createContext<AdminContextValue | null>(null);

export function AdminSessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session>(guest);
  const [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const version = ++generation.current;
    try { const result = await apiRequest<Session>("/admin/session"); if (version === generation.current) { invalidateNavigationData(); setSession(result); } }
    catch { if (version === generation.current) setSession(guest); }
    finally { if (version === generation.current) setLoading(false); }
  }, []);
  useEffect(() => {
    void refresh();
    const onFocus = () => { if (document.visibilityState === "visible") void refresh(); };
    const onStorage = (event: StorageEvent) => { if (event.key === "collab-admin-change") { invalidateNavigationData(); void refresh(); } };
    window.addEventListener("focus", onFocus);
    window.addEventListener("storage", onStorage);
    window.addEventListener("collab-admin-expired", onFocus);
    document.addEventListener("visibilitychange", onFocus);
    const timer = window.setInterval(onFocus, 60000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("collab-admin-expired", onFocus);
      document.removeEventListener("visibilitychange", onFocus);
      window.clearInterval(timer);
    };
  }, [refresh]);

  function notifyChange() {
    invalidateNavigationData();
    try { window.localStorage.setItem("collab-admin-change", String(Date.now())); } catch { /* Session cookies still work when storage is unavailable. */ }
  }
  async function signIn(email: string, role: string) {
    const result = await apiRequest<Session>("/admin/login", { method: "POST", body: JSON.stringify({ email, role }) });
    generation.current += 1;
    notifyChange(); setSession(result); setLoading(false);
  }
  async function signOut() {
    await apiRequest("/admin/logout", { method: "POST" });
    generation.current += 1;
    notifyChange(); setSession(guest);
  }
  return <AdminContext.Provider value={{ session, loading, signIn, signOut }}>{children}</AdminContext.Provider>;
}

export function useAdminSession() {
  const value = useContext(AdminContext);
  if (!value) throw new Error("AdminSessionProvider is missing");
  return value;
}

export function AdminRequired() {
  return <section className="projectPage">
    <div className="projectPageHeader"><div><h1>Administrator access</h1><span>Agent templates are managed by the SQUAD admin team.</span></div></div>
    <Link className="projectButton" href="/admin">Admin sign-in</Link>
  </section>;
}
