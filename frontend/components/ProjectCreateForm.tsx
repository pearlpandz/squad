"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot, Save } from "lucide-react";

import { TeamDetail, TeamMember, TeamSummary, ProjectCreatePayload, ProjectDetail, apiRequest, projectActorHumanId } from "@/lib/api";

const stages = ["discovery", "planning", "design", "execution", "testing", "release", "maintenance", "on-hold"];

export function ProjectCreateForm({ initialTeamId }: { initialTeamId?: string }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [status, setStatus] = useState("active");
  const [deliveryStage, setDeliveryStage] = useState("discovery");
  const [description, setDescription] = useState("");
  const [agents, setAgents] = useState<TeamMember[]>([]);
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [teamId, setTeamId] = useState(initialTeamId ?? "");
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [agentLoadFailed, setAgentLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let current = true;
    apiRequest<TeamSummary[]>("/teams")
      .then((list) => { if (current) { setTeams(list); setTeamId(initialTeamId ?? String(list[0]?.id ?? "")); if (!list.length) setLoadingAgents(false); } })
      .catch((caught) => {
        if (current) {
          setAgentLoadFailed(true); setLoadingAgents(false);
          setError(caught instanceof Error ? caught.message : "Unable to load teams");
        }
      });
    return () => { current = false; };
  }, [initialTeamId]);

  useEffect(() => {
    if (!teamId) return;
    let current = true;
    setLoadingAgents(true); setAgentLoadFailed(false); setSelectedIds([]); setAgents([]);
    apiRequest<TeamDetail>(`/teams/${teamId}`)
      .then((team) => { if (current) setAgents(team.ai_members.filter((agent) => agent.status === "available")); })
      .catch((caught) => { if (current) { setAgentLoadFailed(true); setError(caught instanceof Error ? caught.message : "Unable to load team members"); } })
      .finally(() => { if (current) setLoadingAgents(false); });
    return () => { current = false; };
  }, [teamId]);

  function toggleAgent(agentId: number) {
    setSelectedIds((current) => current.includes(agentId)
      ? current.filter((id) => id !== agentId) : [...current, agentId]);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    const payload: ProjectCreatePayload = {
      team_id: Number(teamId),
      name: name.trim(), status, delivery_stage: deliveryStage,
      description: description.trim(), agent_member_ids: selectedIds,
    };
    try {
      payload.created_by_human_id = await projectActorHumanId();
      const project = await apiRequest<ProjectDetail>("/projects", {
        method: "POST", body: JSON.stringify(payload),
      });
      router.push(`/projects/${project.id}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create project");
      setSaving(false);
    }
  }

  return (
    <form className="projectCreateForm" onSubmit={(event) => void submit(event)}>
      {error && <div className="formError" role="alert">{error}</div>}
      <section className="projectForm projectCreateSection">
        <div><p className="projectEyebrow">01 · Project Details</p><h2>Project details</h2></div>
        <div className="formGrid">
          <label>Team<select required value={teamId} onChange={(event) => setTeamId(event.target.value)}><option value="">Select team</option>{teams.map((team) => <option value={team.id} key={team.id}>{team.name}</option>)}</select></label>
          <label>Name<input autoFocus maxLength={160} minLength={2} onChange={(event) => setName(event.target.value)} required value={name} /></label>
          <label>Status<select onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="active">Active</option><option value="inactive">Inactive</option><option value="on-hold">On Hold</option>
          </select></label>
          <label>Delivery Stage<select onChange={(event) => setDeliveryStage(event.target.value)} value={deliveryStage}>
            {stages.map((stage) => <option key={stage} value={stage}>{stage.replace("-", " ").replace(/^./, (letter) => letter.toUpperCase())}</option>)}
          </select></label>
        </div>
        <label>Description<textarea onChange={(event) => setDescription(event.target.value)} value={description} /></label>
      </section>

      <section className="projectForm projectCreateSection">
        <div><p className="projectEyebrow">02 · Project Team</p><h2>AI coworkers</h2><span>Choose coworkers from the selected team.</span></div>
        {loadingAgents && <LoadingSkeleton label="Loading coworkers" count={3} />}
        {!loadingAgents && agents.length === 0 && (
          <div className="projectEmpty">No available team coworkers. <Link href={teamId ? `/teams/${teamId}` : "/teams"}>Add members to the team</Link> first.</div>
        )}
        <div className="projectTeamChoices">
          {agents.map((agent) => (
            <label className="projectTeamChoice" key={agent.id}>
              <input checked={selectedIds.includes(agent.id)} onChange={() => toggleAgent(agent.id)} type="checkbox" />
              <span className="projectTeamAvatar"><Bot size={19} /></span>
              <span><strong>{agent.name}</strong><small>{agent.handle} · {agent.role}</small><small>{agent.description || "No responsibility description yet."}</small></span>
            </label>
          ))}
        </div>
      </section>
      <div className="formActions">
        <Link className="secondaryLink" href="/projects">Cancel</Link>
        <button className="projectButton" disabled={saving || loadingAgents || agentLoadFailed || !teamId} type="submit">
          <Save size={16} />{saving ? "Creating..." : "Create Project"}
        </button>
      </div>
    </form>
  );
}
