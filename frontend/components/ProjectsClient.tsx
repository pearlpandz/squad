"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Bot, EllipsisVertical, FolderKanban, MessageSquare, Plus, Search, Trash2, Users, X } from "lucide-react";

import { ProjectSummary, apiRequest, projectActorHumanId } from "@/lib/api";

export function ProjectsClient() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [teamId, setTeamId] = useState("");
  const [search, setSearch] = useState("");
  const [removingId, setRemovingId] = useState<number | null>(null);
  const teams = Array.from(new Map(projects.map((project) => [project.team_id, project.team_name])));
  const query = search.trim().toLowerCase();
  const visibleProjects = projects.filter((project) => (!teamId || String(project.team_id) === teamId)
    && (!query || [project.name, project.description, project.team_name].some((value) => value?.toLowerCase().includes(query))));

  async function loadProjects() {
    setLoading(true);
    setError(null);
    try {
      setProjects(await apiRequest<ProjectSummary[]>("/projects"));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load projects");
    } finally {
      setLoading(false);
    }
  }

  async function removeProject(projectId: number) {
    if (removingId !== null) return;
    const project = projects.find((item) => item.id === projectId);
    if (!window.confirm(`Remove ${project?.name ?? "this project"}?`)) {
      return;
    }

    setError(null);
    setRemovingId(projectId);
    try {
      const actorId = await projectActorHumanId();
      await apiRequest(`/projects/${projectId}?updated_by_human_id=${actorId}`, { method: "DELETE" });
      await loadProjects();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to remove project");
    } finally {
      setRemovingId(null);
    }
  }

  useEffect(() => {
    void loadProjects();
  }, []);

  return (
    <section className="projectPage projectWorkspacePage">
      <div className="projectPageHeader">
        <div>
          <h1>Projects</h1>
          <span>A shared space for your team and AI coworkers.</span>
        </div>
        <div className="projectHeaderActions">

          <Link className="projectButton" href="/projects/new">
            <Plus size={16} />
            New Project
          </Link>
        </div>
      </div>

      {error && <div className="formError" role="alert">{error}</div>}
      {loading && <LoadingSkeleton variant="cards" label="Loading projects" count={4} />}

      {!loading && (
        <div className="workspaceToolbar">
          {teams.length > 1 && <label className="workspaceTeamFilter"><span className="skeletonStatus">Filter by team</span>
            <select value={teamId} onChange={(event) => setTeamId(event.target.value)}><option value="">All teams</option>{teams.map(([id, name]) => <option value={id} key={id}>{name}</option>)}</select>
          </label>}
          <div className="workspaceSearch">
            <Search size={16} aria-hidden="true" />
            <input aria-label="Search projects" placeholder="Search projects…" type="search" value={search} onChange={(event) => setSearch(event.target.value)} />
            {search && <button type="button" aria-label="Clear search" onClick={() => setSearch("")}><X size={14} aria-hidden="true" /></button>}
          </div>
          <span className="workspaceResultCount" role="status">{visibleProjects.length} {visibleProjects.length === 1 ? "project" : "projects"}</span>
        </div>
      )}
      {!loading && (
        <div className="workspaceProjectGrid">
          {visibleProjects.map((project) => <article className="workspaceProjectCard" key={project.id}>
            <div className="workspaceCardHeader">
              <span className="workspaceProjectIcon" aria-hidden="true"><FolderKanban size={18} /></span>
              <div className="workspaceProjectIdentity">
                <h2><Link href={`/projects/${project.id}/collab`}>{project.name}</Link></h2>
                <Link className="workspaceTeamLink" href={`/teams/${project.team_id}`}>{project.team_name}</Link>
              </div>
              <details className="workspaceProjectMenu" onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false;
              }} onKeyDown={(event) => {
                if (event.key === "Escape") { event.currentTarget.open = false; event.currentTarget.querySelector("summary")?.focus(); }
              }}>
                <summary aria-label={`Options for ${project.name}`}><EllipsisVertical size={16} aria-hidden="true" /></summary>
                <div className="workspaceProjectMenuItems">
                  <Link href={`/projects/${project.id}`}><ArrowUpRight size={14} aria-hidden="true" /> Project details</Link>
                  <Link href={`/projects/${project.id}/members`}><Users size={14} aria-hidden="true" /> Manage members</Link>
                  <button className="dangerAction" disabled={removingId !== null} type="button" onClick={(event) => {
                    event.currentTarget.closest("details")?.removeAttribute("open");
                    void removeProject(project.id);
                  }}><Trash2 size={14} aria-hidden="true" /> {removingId === project.id ? "Removing…" : "Remove project"}</button>
                </div>
              </details>
            </div>
            <p className="workspaceProjectDescription">{project.description || "Bring your team together and start the conversation."}</p>
            <div className="workspaceCardFooter">
              <div className="workspaceMemberCounts">
                <span><Users size={14} aria-hidden="true" /> {project.human_member_count} {project.human_member_count === 1 ? "person" : "people"}</span>
                <span><Bot size={14} aria-hidden="true" /> {project.ai_member_count} AI</span>
              </div>
              <Link className="workspaceOpenChat" href={`/projects/${project.id}/collab`} aria-label={`Open chat for ${project.name}`}>
                <MessageSquare size={15} aria-hidden="true" /> Open chat <ArrowUpRight size={14} aria-hidden="true" />
              </Link>
            </div>
          </article>)}
          {visibleProjects.length === 0 && !error && <div className="workspaceEmpty">
            <span className="workspaceProjectIcon" aria-hidden="true"><FolderKanban size={18} /></span>
            <h2>{projects.length === 0 ? "Your next project starts here" : "No matching projects"}</h2>
            <p>{projects.length === 0 ? "Create a project, bring in your coworkers, and start collaborating." : "Try a different name or choose another team."}</p>
            {projects.length === 0 ? <Link className="projectButton" href="/projects/new"><Plus size={15} /> Create project</Link>
              : <button className="ghostButton" type="button" onClick={() => { setSearch(""); setTeamId(""); }}>Clear filters</button>}
          </div>}
        </div>
      )}
    </section>
  );
}
