"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { Toast } from "@/components/Toast";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Bot, Brain, Edit, FolderOpen, Plus, UserRound } from "lucide-react";
import { AgentProfile, MemberProjectMemory, ProjectSummary, TeamDetail, TeamMember, apiRequest } from "@/lib/api";

const teamTabs = [
  { key: "about", label: "About Team" },
  { key: "members", label: "Team Members" },
  { key: "projects", label: "Projects" },
] as const;
type TeamTab = (typeof teamTabs)[number]["key"];

type HumanChoice = { id: number; name: string; username: string; role: string };

export function TeamsClient({ teamId }: { teamId: string }) {
  const [activeTab, setActiveTab] = useState<TeamTab>("about");
  const tabButtons = useRef<Array<HTMLButtonElement | null>>([]);
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [humans, setHumans] = useState<HumanChoice[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [editingTeam, setEditingTeam] = useState<{ id: number; name: string; description: string } | null>(null);
  const [memberKind, setMemberKind] = useState("agents");
  const [memberId, setMemberId] = useState("");
  const [moveProjectId, setMoveProjectId] = useState("");
  const [includeMembers, setIncludeMembers] = useState(true);
  const [memoryAgent, setMemoryAgent] = useState<number | null>(null);
  const [memory, setMemory] = useState<MemberProjectMemory[] | null>(null);
  const [humanForm, setHumanForm] = useState({ name: "", username: "", email: "", role: "" });
  const loadVersion = useRef(0);

  useEffect(() => {
    const readTab = () => {
      const tab = window.location.hash.slice(1);
      setActiveTab(teamTabs.find((item) => item.key === tab)?.key ?? "about");
    };
    readTab();
    window.addEventListener("hashchange", readTab);
    return () => window.removeEventListener("hashchange", readTab);
  }, [teamId]);

  function selectTab(tab: TeamTab) {
    setActiveTab(tab);
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}#${tab}`);
  }

  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    setLoading(true);
    try {
      const [detail, coworkers, people, allProjects] = await Promise.all([
        apiRequest<TeamDetail>(`/teams/${teamId}`), apiRequest<AgentProfile[]>("/agents"),
        apiRequest<HumanChoice[]>("/teams/available-humans"), apiRequest<ProjectSummary[]>("/projects"),
      ]);
      if (version !== loadVersion.current) return;
      setAgents(coworkers); setHumans(people); setProjects(allProjects); setTeam(detail);
      setMemoryAgent((current) => detail?.ai_members.some((member) => member.id === current) ? current : null);
      setError(null);
    } catch (caught) {
      if (version === loadVersion.current) setError(caught instanceof Error ? caught.message : "Unable to load team details");
    } finally {
      if (version === loadVersion.current) setLoading(false);
    }
  }, [teamId]);

  useEffect(() => { setTeam(null); setEditingTeam(null); setMemoryAgent(null); setMemory(null); setNotice(""); setMemberId(""); setMoveProjectId(""); void load();
    return () => { loadVersion.current += 1; };
  }, [load]);

  useEffect(() => {
    if (!team || memoryAgent === null || activeTab !== "members") return;
    let current = true;
    const refresh = () => void apiRequest<MemberProjectMemory[]>(`/teams/${team.id}/members/agents/${memoryAgent}/memory`)
      .then((result) => { if (current) setMemory(result); })
      .catch((caught) => { if (current) setError(caught instanceof Error ? caught.message : "Unable to load member memory"); });
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => { current = false; window.clearInterval(timer); };
  }, [team?.id, memoryAgent, activeTab]);

  async function mutate(path: string, method: string, body?: unknown, message = "Saved.") {
    setBusy(true); setError(null); setNotice("");
    try {
      await apiRequest(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
      await load(); setNotice(message); setMemberId(""); setMoveProjectId("");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to save team"); }
    finally { setBusy(false); }
  }

  async function saveTeam(event: FormEvent) {
    event.preventDefault();
    if (!editingTeam || editingTeam.id !== team?.id || busy) return;
    setBusy(true); setError(null); setNotice("");
    try {
      const saved = await apiRequest<TeamDetail>(`/teams/${editingTeam.id}`, {
        method: "PUT", body: JSON.stringify({ name: editingTeam.name.trim(), description: editingTeam.description.trim() }),
      });
      setTeam(saved);
      setProjects((current) => current.map((project) => project.team_id === saved.id
        ? { ...project, team_name: saved.name } : project));
      setEditingTeam(null); setNotice("Team updated.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to update team"); }
    finally { setBusy(false); }
  }

  function renderMember(member: TeamMember, kind: "agents" | "humans") {
    if (!team) return null;
    const availableProjects = team.projects.filter((project) => !member.projects.some((item) => item.id === project.id));
    return <article className="projectMemberCard" key={`${kind}-${member.id}`}>
      <div className="projectMemberCardTop"><span className="agentCardAvatar">{kind === "agents" ? <Bot size={22} /> : <UserRound size={22} />}</span><span className="agentCardStatus">{kind === "agents" ? "AI coworker" : "Human"} · {member.status}</span></div>
      <div className="projectMemberIdentity"><h3>{member.name}</h3><span>{member.handle}</span></div>
      <span className="projectMemberRole">{member.role}</span><p>{member.description || "No additional details."}</p>
      <div className="teamMemberProjects" aria-label={`${member.name}'s projects`}>
        {member.projects.map((project) => <Link href={`/projects/${project.id}`} key={project.id}>{project.name} <small>· {project.delivery_stage}</small></Link>)}
        {member.projects.length === 0 && <span className="agentSectionCopy">No projects assigned yet.</span>}
      </div>
      <form className="teamInlineForm" onSubmit={(event) => {
        event.preventDefault(); const projectId = new FormData(event.currentTarget).get("project");
        if (projectId) void mutate(`/teams/${team.id}/projects/${projectId}/members`, "POST",
          kind === "agents" ? { agent_ids: [member.id] } : { human_ids: [member.id] }, "Member assigned to project.");
      }}>
        <select aria-label={`Assign ${member.name} to a project`} defaultValue="" disabled={busy || !availableProjects.length} key={member.projects.map((project) => project.id).join(",")} name="project" required>
          <option value="">{availableProjects.length ? "Choose project" : "No unassigned projects"}</option>
          {availableProjects.map((project) => <option value={project.id} key={project.id}>{project.name}</option>)}
        </select><button className="ghostButton" disabled={busy || !availableProjects.length} type="submit">Assign</button>
      </form>
      <div className="projectMemberActions">
        {kind === "agents" && <><Link className="ghostButton" href={`/agents/${member.id}/tasks`}>Tasks</Link><button className="ghostButton" disabled={busy} onClick={() => { setMemory(null); setMemoryAgent((current) => current === member.id ? null : member.id); }} type="button"><Brain size={15} /> Memory</button></>}
        <button className="rowActionLink dangerAction" disabled={busy || member.projects.length > 0} title={member.projects.length ? "Remove project assignments first using each project's Update Members page" : "Remove from this team"}
          onClick={() => void mutate(`/teams/${team.id}/members/${kind}/${member.id}`, "DELETE", undefined, "Member removed from team.")} type="button">Remove</button>
      </div>
    </article>;
  }

  const choices = memberKind === "agents" ? agents.filter((agent) => agent.status === "available" && !team?.ai_members.some((member) => member.id === agent.id))
    : humans.filter((human) => !team?.human_members.some((member) => member.id === human.id));

  return <section className="projectPage">
    <div className="projectPageHeader"><div><h1>{team?.name ?? "Team details"}</h1><span>{team?.description || "Manage this team's members and projects."}</span></div>
      <div className="projectHeaderActions">
        <Link className="ghostButton" href="/teams"><ArrowLeft size={16} /> All Teams</Link></div></div>
    {error && <p className="formError" role="alert">{error}</p>}{notice && <Toast message={notice} />}
    {loading && <LoadingSkeleton variant="details" label="Loading team details" count={4} />}
    {!loading && team && <>
      <div aria-label={`${team.name} sections`} className="teamTabs" role="tablist">
        {teamTabs.map((tab, index) => <button aria-controls={`team-${team.id}-panel-${tab.key}`} aria-selected={activeTab === tab.key}
          id={`team-${team.id}-tab-${tab.key}`} key={tab.key} onClick={() => selectTab(tab.key)}
          onKeyDown={(event) => {
            let next = index;
            if (event.key === "ArrowRight") next = (index + 1) % teamTabs.length;
            else if (event.key === "ArrowLeft") next = (index + teamTabs.length - 1) % teamTabs.length;
            else if (event.key === "Home") next = 0;
            else if (event.key === "End") next = teamTabs.length - 1;
            else return;
            event.preventDefault(); selectTab(teamTabs[next].key); tabButtons.current[next]?.focus();
          }} ref={(button) => { tabButtons.current[index] = button; }} role="tab" tabIndex={activeTab === tab.key ? 0 : -1} type="button">{tab.label}</button>)}
      </div>
      <div aria-labelledby={`team-${team.id}-tab-about`} className="teamTabPanel" hidden={activeTab !== "about"} id={`team-${team.id}-panel-about`} role="tabpanel" tabIndex={0}>
        <section className="detailPanel">
          <div className="projectMemberSummary"><h2>About Team</h2>
            <button className="ghostButton" disabled={busy} onClick={() => {
              setError(null); setNotice("");
              setEditingTeam({ id: team.id, name: team.name, description: team.description });
            }} type="button"><Edit size={16} /> Edit Team</button>
          </div>
          <dl className="teamAboutDetails"><div><dt>Team name</dt><dd>{team.name}</dd></div><div><dt>Description</dt><dd>{team.description || "No description added."}</dd></div></dl>
          <div className="projectMemberCounts"><span><UserRound size={15} /> {team.human_members.length} humans</span><span><Bot size={15} /> {team.ai_members.length} AI coworkers</span><span><FolderOpen size={15} /> {team.projects.length} projects</span></div>
        </section>
      {editingTeam?.id === team.id && <form aria-labelledby="team-edit-title" className="projectForm teamCreateForm" onSubmit={(event) => void saveTeam(event)}
        onKeyDown={(event) => { if (event.key === "Escape" && !busy) setEditingTeam(null); }}>
        <h2 id="team-edit-title">Edit team</h2>
        <label>Team name<input autoFocus disabled={busy} required minLength={2} maxLength={160} value={editingTeam.name}
          onChange={(event) => setEditingTeam({ ...editingTeam, name: event.target.value })} /></label>
        <label>Description<textarea disabled={busy} maxLength={2000} value={editingTeam.description}
          onChange={(event) => setEditingTeam({ ...editingTeam, description: event.target.value })} /></label>
        <div className="formActions"><button className="ghostButton" disabled={busy} onClick={() => setEditingTeam(null)} type="button">Cancel</button>
          <button className="projectButton" disabled={busy || editingTeam.name.trim().length < 2} type="submit">{busy ? "Saving..." : "Save Changes"}</button></div>
      </form>}
      </div>
      <div aria-labelledby={`team-${team.id}-tab-members`} className="teamTabPanel" hidden={activeTab !== "members"} id={`team-${team.id}-panel-members`} role="tabpanel" tabIndex={0}>
      <section className="detailPanel"><div className="projectMemberSummary"><h2>Team members</h2><div className="projectMemberCounts"><span><UserRound size={15} /> {team.human_members.length} humans</span><span><Bot size={15} /> {team.ai_members.length} AI coworkers</span></div></div>
        <form className="teamInlineForm teamAddMember" onSubmit={(event) => { event.preventDefault(); void mutate(`/teams/${team.id}/members`, "POST", memberKind === "agents" ? { agent_ids: [Number(memberId)] } : { human_ids: [Number(memberId)] }, "Member added to team."); }}>
          <label>Member type<select value={memberKind} onChange={(event) => { setMemberKind(event.target.value); setMemberId(""); }}><option value="agents">AI coworker</option><option value="humans">Human</option></select></label>
          <label>Available member<select required disabled={busy} value={memberId} onChange={(event) => setMemberId(event.target.value)}><option value="">Choose member</option>{choices.map((member) => <option value={member.id} key={member.id}>{member.name} · {member.role}</option>)}</select></label>
          <button className="projectButton" disabled={busy || !memberId} type="submit"><Plus size={16} /> Add Member</button>
          <Link className="secondaryLink" href="/agents">Create AI coworker</Link>
        </form>
        {memberKind === "humans" && <details className="teamHumanForm"><summary>Create a human member</summary><form className="projectForm" onSubmit={(event) => { event.preventDefault(); void mutate(`/teams/${team.id}/members/humans`, "POST", humanForm, "Human added to team."); }}>
          <div className="formGrid">{(["name", "username", "email", "role"] as const).map((field) => <label key={field}>{field.replace(/^./, (letter) => letter.toUpperCase())}<input required={field !== "email"} type={field === "email" ? "email" : "text"} value={humanForm[field]} onChange={(event) => setHumanForm((current) => ({ ...current, [field]: event.target.value }))} /></label>)}</div>
          <button className="projectButton" disabled={busy} type="submit">Create Human</button></form></details>}
        <div className="projectMemberGrid">{team.ai_members.map((member) => renderMember(member, "agents"))}{team.human_members.map((member) => renderMember(member, "humans"))}
          {!team.ai_members.length && !team.human_members.length && <div className="projectEmpty">No team members yet. Add an existing coworker or human above.</div>}</div>
      </section>
      {memoryAgent !== null && <section className="detailPanel" aria-live="polite"><div className="projectMemberSummary"><h2><Brain size={18} /> {team.ai_members.find((member) => member.id === memoryAgent)?.name} · Project memory</h2><button className="ghostButton" onClick={() => setMemoryAgent(null)} type="button">Close</button></div>
        <p className="agentSectionCopy">Project details and progress are saved separately for this coworker. Collaboration uses only the current project. Refreshes every ten seconds.</p>
        {!memory && <LoadingSkeleton variant="content" label="Loading memory" count={2} />}{memory?.length === 0 && <p>No assigned project memory yet.</p>}
        {memory?.map((item) => <article className="teamMemoryProject" key={item.id}><h3><Link href={`/projects/${item.id}`}>{item.name}</Link></h3><p>{item.description || "No description."}</p>
          <div className="chipRow"><span>{item.status}</span><span>{item.delivery_stage}</span><span>{item.priority}</span><span>{item.tasks.length} tasks</span></div>
          <dl className="teamMemoryFacts"><div><dt>Domain</dt><dd>{item.business_domain || "Not specified"}</dd></div><div><dt>Repository</dt><dd>{item.repository_url || "Not specified"}</dd></div><div><dt>Tech stack</dt><dd>{item.tech_stack.join(", ") || "Not specified"}</dd></div></dl>
          {item.tasks.map((task) => <div className="teamMemoryTask" key={task.id}><strong>#{task.id} {task.title}</strong><span>{task.status.replaceAll("_", " ")}{task.run_status ? ` · ${task.run_status}` : ""}{item.my_task_ids.includes(task.id) ? " · Participating coworker" : ""}</span><p>{task.latest_progress || "No progress recorded."}</p></div>)}</article>)}
      </section>}
      </div>
      <div aria-labelledby={`team-${team.id}-tab-projects`} className="teamTabPanel" hidden={activeTab !== "projects"} id={`team-${team.id}-panel-projects`} role="tabpanel" tabIndex={0}>
      <section className="detailPanel"><div className="projectMemberSummary"><h2><FolderOpen size={18} /> Projects under {team.name}</h2><Link className="projectButton" href={`/projects/new?team=${team.id}`}><Plus size={16} /> New Project</Link></div>
        <div className="teamProjectList">{team.projects.map((project) => <article className="teamProjectRow" key={project.id}><div><Link href={`/projects/${project.id}`}><strong>{project.name}</strong></Link><p>{project.description || "No description."}</p><span>{project.status} · {project.delivery_stage} · {project.ai_member_count + project.human_member_count} members</span></div><div className="rowActions"><Link className="ghostButton" href={`/projects/${project.id}/members`}>Members</Link><Link className="ghostButton" href={`/projects/${project.id}/collab`}>Collab</Link></div></article>)}</div>
        {team.projects.length === 0 && <p className="projectEmpty">No projects in this team yet.</p>}
        <details className="teamHumanForm"><summary>Move an existing project into this team</summary><form className="teamMoveForm" onSubmit={(event) => { event.preventDefault(); void mutate(`/teams/${team.id}/projects`, "POST", { project_id: Number(moveProjectId), include_existing_members: includeMembers }, "Project moved into team."); }}>
          <label>Project<select required value={moveProjectId} onChange={(event) => setMoveProjectId(event.target.value)}><option value="">Choose project</option>{projects.filter((project) => project.team_id !== team.id).map((project) => <option value={project.id} key={project.id}>{project.team_name} / {project.name}</option>)}</select></label>
          <label className="teamCheckbox"><input checked={includeMembers} onChange={(event) => setIncludeMembers(event.target.checked)} type="checkbox" /> Add this project&apos;s current members to the team</label>
          <p className="agentSectionCopy">The project will leave its current team. Its history, files, and member assignments are preserved.</p><button className="projectButton" disabled={busy || !moveProjectId} type="submit">Move Project</button>
        </form></details>
      </section>
      </div>
    </>}
  </section>;
}
