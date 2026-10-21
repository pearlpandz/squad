"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAdminSession } from "@/components/AdminSession";
import { AppHeader } from "@/components/AppHeader";
import { LoginClient } from "@/components/LoginClient";

export function WorkspaceGate({ children }: { children: ReactNode }) {
  const { session, loading } = useAdminSession();
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    if (!loading && !session.authenticated && pathname !== "/login") router.replace("/login");
    if (!loading && session.authenticated && pathname === "/login") router.replace("/projects");
  }, [loading, session.authenticated, pathname, router]);
  if (loading) return <main className="loginPage" role="status">Checking your session…</main>;
  if (!session.authenticated) return <LoginClient />;
  if (pathname === "/login") return <main className="loginPage" role="status">Opening your workspace…</main>;
  return <><AppHeader /><div className="pageContent" id="page-content" tabIndex={-1}>{children}</div></>;
}
