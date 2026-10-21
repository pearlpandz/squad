"use client";

import { useState } from "react";
import Link from "next/link";
import { useAdminSession } from "@/components/AdminSession";

export function AdminSignInClient() {
  const { session, signOut } = useAdminSession();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function logout() {
    setBusy(true); setError(null);
    try { await signOut(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign out"); }
    finally { setBusy(false); }
  }
  return <section className="projectPage">
    <div className="projectPageHeader"><div><h1>{session.is_admin ? "Admin workspace" : "Your account"}</h1><span>{session.email} · {session.role}</span></div></div>
    <div className="adminSignInCard">
      {error && <div className="formError" role="alert">{error}</div>}
      <h2>Signed in as {session.email}</h2>
      <p>{session.is_admin ? "Manage shared agent templates for your SQUAD teams." : "Your enterprise workspace session is active."}</p>
      <div className="formActions">{session.is_admin && <Link className="projectButton" href="/templates">Open agent templates</Link>}<button className="ghostButton" disabled={busy} onClick={() => void logout()} type="button">{busy ? "Signing out…" : "Sign out"}</button></div>
    </div>
  </section>;
}
