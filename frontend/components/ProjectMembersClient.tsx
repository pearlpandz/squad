"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Bot, Plus, UserMinus, UserRound, X } from "lucide-react";

import { TeamDetail, TeamMember, ProjectDetail, apiRequest } from "@/lib/api";

type MemberType = "human" | "ai";


export function ProjectMembersClient({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [memberType, setMemberType] = useState<MemberType>("human");
  const [selectedHumanId, setSelectedHumanId] = useState("");
  const [humans, setHumans] = useState<TeamMember[]>([]);
  const [agents, setAgents] = useState<TeamMember[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadProject() {
    setError(null);
    try {
      const projectDetail = await apiRequest<ProjectDetail>(`/projects/${projectId}`);
      const team = await apiRequest<TeamDetail>(`/teams/${projectDetail.team_id}`);
      setProject(projectDetail);
      setAgents(team.ai_members);
      setHumans(team.human_members);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load members");
    }
  }

  useEffect(() => {
    void loadProject();
  }, [projectId]);

  function resetModal() {
    setMemberType("human");
    setSelectedHumanId("");
    setSelectedAgentId("");
    setShowModal(false);
    setSaving(false);
  }

  async function saveMember(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (!project) return;
      await apiRequest(`/teams/${project.team_id}/projects/${projectId}/members`, {
        method: "POST", body: JSON.stringify(memberType === "human"
          ? { human_ids: [Number(selectedHumanId)] } : { agent_ids: [Number(selectedAgentId)] }),
      });
      await loadProject();
      resetModal();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save member");
      setSaving(false);
    }
  }

  async function removeHuman(humanId: number) {
    const saved = await apiRequest<ProjectDetail>(`/projects/${projectId}/members/humans/${humanId}`, {
      method: "DELETE",
    });
    setProject(saved);
  }

  async function removeAi(agentId: number) {
    const saved = await apiRequest<ProjectDetail>(`/projects/${projectId}/members/agents/${agentId}`, {
      method: "DELETE",
    });
    setProject(saved);
  }

  if (error && !project) {
    return <section className="projectPage"><div className="formError">{error}</div></section>;
  }

  if (!project) {
    return <LoadingSkeleton fullPage variant="cards" label="Loading members" count={6} />;
  }

  const members = [
    ...project.human_members.map((member) => ({
      key: `human-${member.id}`, name: member.display_name, handle: `@${member.username}`,
      role: member.member_role, status: member.status, description: member.email || member.role,
      isAi: false, editUrl: null, remove: () => removeHuman(member.id),
    })),
    ...project.ai_members.map((member) => ({
      key: `ai-${member.id}`, name: member.name, handle: member.handle,
      role: member.role, status: member.status, description: member.agent_description || member.knowledge_scope,
      isAi: true, editUrl: `/agents/${member.id}/edit`, remove: () => removeAi(member.id),
    })),
  ];

  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div>
          <h1>{project.name}</h1>
          <span>Assign team members to this project or remove their project assignments.</span>
        </div>
        <div className="projectHeaderActions">
          <button className="projectButton" onClick={() => setShowModal(true)} type="button">
            <Plus size={16} />
            Add Member
          </button>
          <Link className="ghostButton" href={`/projects/${project.id}`}>
            <ArrowLeft size={16} />
            View Project
          </Link>
        </div>
      </div>

      {error && <div className="formError">{error}</div>}

      <section className="detailPanel" aria-labelledby="project-members-title">
        <div className="projectMemberSummary">
          <h2 id="project-members-title">Project members</h2>
          <div className="projectMemberCounts" role="status" aria-live="polite">
            <span><UserRound size={15} aria-hidden="true" /> {project.human_members.length} humans</span>
            <span><Bot size={15} aria-hidden="true" /> {project.ai_members.length} AI co-workers</span>
          </div>
        </div>
        <div className="projectMemberGrid">
          {members.map((member) => (
            <article className="projectMemberCard" key={member.key}>
              <div className="projectMemberCardTop">
                <span className="agentCardAvatar" aria-hidden="true">{member.isAi ? <Bot size={22} /> : <UserRound size={22} />}</span>
                <span className="agentCardStatus">{member.isAi ? "AI co-worker" : "Human"}</span>
              </div>
              <div className="projectMemberIdentity"><h3>{member.name}</h3><span>{member.handle}</span></div>
              <span className="projectMemberRole">{member.role} · {member.status}</span>
              <p>{member.description || "No additional details."}</p>
              <div className="projectMemberActions">
                {member.editUrl && <Link aria-label={`Edit ${member.name}`} className="ghostButton" href={member.editUrl}>Edit</Link>}
                <button
                  aria-label={`Remove ${member.name} from project`}
                  className="rowActionLink dangerAction"
                  onClick={() => void member.remove().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to remove member"))}
                  title="Remove from project only"
                  type="button"
                ><UserMinus size={16} aria-hidden="true" /> Remove</button>
              </div>
            </article>
          ))}
          {members.length === 0 && <div className="projectEmpty">No members yet. Add a human or AI co-worker to get started.</div>}
        </div>
      </section>

      {showModal && (
        <div className="modalBackdrop" role="presentation">
          <form className="memberModal projectForm" onSubmit={(event) => void saveMember(event)}>
            <div className="modalHeader">
              <div>
                <p className="projectEyebrow">Add Member</p>
                <h2>{memberType === "human" ? "Human member" : "Assign AI co-worker"}</h2>
              </div>
              <button className="iconLink" onClick={resetModal} type="button">
                <X size={16} />
              </button>
            </div>

            <div className="memberModalBody">
              <div className="radioGroup">
                <label><input checked={memberType === "human"} onChange={() => setMemberType("human")} type="radio" /> Human</label>
                <label><input checked={memberType === "ai"} onChange={() => setMemberType("ai")} type="radio" /> AI</label>
              </div>

              {memberType === "human" ? (
                <label>Team human member
                  <select required value={selectedHumanId} onChange={(event) => setSelectedHumanId(event.target.value)}>
                    <option value="">Choose a human</option>
                    {humans.filter((human) => !project.human_members.some((member) => member.id === human.id)).map((human) => <option value={human.id} key={human.id}>{human.name} · {human.role}</option>)}
                  </select>
                  <Link className="secondaryLink" href={`/teams/${project.team_id}`}>Manage team members</Link>
                </label>
              ) : (
                <div className="agentAssignmentChoice">
                  <label>Existing AI co-worker
                    <select onChange={(event) => setSelectedAgentId(event.target.value)} required value={selectedAgentId}>
                      <option value="">Select a co-worker</option>
                      {agents.filter((agent) => agent.status === "available" && !project.ai_members.some((member) => member.id === agent.id)).map((agent) => (
                        <option key={agent.id} value={agent.id}>{agent.name} · {agent.role}</option>
                      ))}
                    </select>
                  </label>
                  {selectedAgentId && <p>{agents.find((agent) => String(agent.id) === selectedAgentId)?.description || "No responsibility description added yet."}</p>}
                  <Link className="secondaryLink" href={`/teams/${project.team_id}`}>Add coworkers to the team</Link>
                </div>
              )}
            </div>

            <div className="formActions memberModalFooter">
              <button className="secondaryLink" onClick={resetModal} type="button">Cancel</button>
              <button className="projectButton" disabled={saving || (memberType === "ai" ? !selectedAgentId : !selectedHumanId)} type="submit">
                {saving ? "Saving" : memberType === "ai" ? "Assign Co-worker" : "Save Member"}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
