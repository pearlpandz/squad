"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Plus } from "lucide-react";
import { TeamDetail, TeamSummary, apiRequest } from "@/lib/api";

function updatedDate(value: string) {
  const normalized = value.replace(" ", "T");
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toLocaleDateString();
}

export function TeamsListClient() {
  const router = useRouter();
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setTeams(await apiRequest<TeamSummary[]>("/teams")); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to load teams"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function createTeam(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(null);
    try {
      const saved = await apiRequest<TeamDetail>("/teams", {
        method: "POST", body: JSON.stringify({ name: name.trim(), description: description.trim() }),
      });
      router.push(`/teams/${saved.id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create team"); setSaving(false);
    }
  }

  return <section className="projectPage">
    <div className="projectPageHeader"><div><h1>Teams</h1><span>Open a team to view its details, members, and projects.</span></div>
      <div className="projectHeaderActions">
        <button className="projectButton" disabled={saving} onClick={() => setShowForm((current) => !current)} type="button"><Plus size={16} /> New Team</button></div></div>
    {error && <p className="formError" role="alert">{error}</p>}
    {showForm && <form className="projectForm teamCreateForm" onSubmit={(event) => void createTeam(event)}>
      <h2>Create team</h2>
      <label>Team name<input autoFocus disabled={saving} minLength={2} maxLength={160} required value={name} onChange={(event) => setName(event.target.value)} /></label>
      <label>Description<textarea disabled={saving} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></label>
      <div className="formActions"><button className="ghostButton" disabled={saving} onClick={() => { setShowForm(false); setName(""); setDescription(""); }} type="button">Cancel</button>
        <button className="projectButton" disabled={saving || name.trim().length < 2} type="submit">{saving ? "Creating..." : "Create Team"}</button></div>
    </form>}
    {loading && <LoadingSkeleton label="Loading teams" count={5} />}
    {!loading && !error && teams.length === 0 && <div className="projectEmpty">No teams yet. Create a team to get started.</div>}
    {!loading && teams.length > 0 && <div aria-label="Available teams" className="teamsTableScroll" role="region" tabIndex={0}>
      <table className="teamsTable"><caption className="teamsTableCaption">Available teams ({teams.length})</caption>
        <thead><tr><th scope="col">Team</th><th scope="col">Description</th><th scope="col">Humans</th><th scope="col">AI coworkers</th><th scope="col">Projects</th><th scope="col">Updated</th><th scope="col">Action</th></tr></thead>
        <tbody>{teams.map((team) => <tr key={team.id}>
          <th scope="row"><Link href={`/teams/${team.id}`}>{team.name}</Link></th>
          <td className="teamsTableDescription">{team.description || "No description added."}</td>
          <td>{team.human_member_count}</td><td>{team.ai_member_count}</td><td>{team.project_count}</td><td>{updatedDate(team.updated_at)}</td>
          <td><Link aria-label={`Open ${team.name}`} className="rowActionLink" href={`/teams/${team.id}`}>Open Team <ArrowRight size={15} /></Link></td>
        </tr>)}</tbody>
      </table>
    </div>}
  </section>;
}
