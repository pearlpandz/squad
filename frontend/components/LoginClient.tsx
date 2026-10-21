"use client";

import { useState, type FormEvent } from "react";
import { useAdminSession } from "@/components/AdminSession";

export function LoginClient() {
  const { signIn } = useAdminSession();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try { await signIn(email.trim(), role.trim()); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign in"); }
    finally { setBusy(false); }
  }
  return <main className="loginPage">
    <section aria-labelledby="login-heading" className="loginCard">
      <div className="loginBrand">SQUAD<span>.</span></div>
      <p className="loginEyebrow">YOUR AI COWORKER WORKSPACE</p>
      <h1 id="login-heading">Welcome to SQUAD</h1>
      <p>Enter your enterprise email and role to get started.</p>
      {error && <div className="formError" role="alert">{error}</div>}
      <form className="projectForm" onSubmit={(event) => void submit(event)}>
        <label htmlFor="login-email">Enterprise email<input id="login-email" type="email" autoComplete="username" placeholder="you@oracle.com" required maxLength={254} disabled={busy} value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label htmlFor="login-role">Role<input id="login-role" autoComplete="organization-title" placeholder="e.g. Business Analyst" required maxLength={80} disabled={busy} value={role} onChange={(event) => setRole(event.target.value)} /></label>
        <button className="projectButton" disabled={busy || !email.trim() || !role.trim()} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <p className="loginHint">Use your @oracle.com email. SQUAD administrators use admin@squad-oracle.com with role admin.</p>
    </section>
  </main>;
}
