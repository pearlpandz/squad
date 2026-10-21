"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { useAdminSession } from "@/components/AdminSession";

import { Toast } from "@/components/Toast";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { Bot, Copy, Plus, X } from "lucide-react";

import { AgentProfile, ProjectSummary, apiRequest } from "@/lib/api";

type ToolPermission = AgentProfile["tool_permissions"][number];
type CreateForm = { name: string; username: string; role: string; agent_description: string; project_id: string; template_id: string; tool_permissions: ToolPermission[] };
const blankForm: CreateForm = { name: "", username: "", role: "", agent_description: "", project_id: "", template_id: "", tool_permissions: ["web_search", "confluence_read", "oracle_read"] };
const toolOptions: Array<{ value: ToolPermission; label: string }> = [
  { value: "web_search", label: "Public web search" },
  { value: "confluence_read", label: "Read Confluence" },
  { value: "oracle_read", label: "Read Oracle connectors" },
];

export function AgentDirectoryClient() {
  const { session } = useAdminSession();
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [templates, setTemplates] = useState<AgentProfile[]>([]);
  const [form, setForm] = useState<CreateForm>(blankForm);
  const [sourceAgentId, setSourceAgentId] = useState<number | null>(null);
  const [projectAgentId, setProjectAgentId] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingOptions, setLoadingOptions] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sourceNotice, setSourceNotice] = useState<string | null>(null);
  const sourceAgent = agents.find((agent) => agent.id === sourceAgentId) ?? null;
  const projectAgent = agents.find((agent) => agent.id === projectAgentId) ?? null;

  async function reload() {
    setAgents(await apiRequest<AgentProfile[]>("/agents"));
  }

  useEffect(() => {
    if (!showCreate) return;
    let active = true;
    setLoadingOptions(true);
    Promise.all([apiRequest<ProjectSummary[]>("/projects"), session.is_admin ? apiRequest<AgentProfile[]>("/agents/templates") : Promise.resolve([])])
      .then(([projectList, templateList]) => {
        if (active) { setProjects(projectList); setTemplates(templateList); }
      })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to load creation options"); })
      .finally(() => { if (active) setLoadingOptions(false); });
    return () => { active = false; };
  }, [showCreate, session.is_admin]);

  useEffect(() => {
    if (!session.is_admin) {
      setTemplates([]);
      setForm((current) => ({ ...current, template_id: "" }));
    }
  }, [session.is_admin]);

  useEffect(() => {
    const requestedProject = new URLSearchParams(window.location.search).get("project") ?? "";
    if (requestedProject) {
      setForm({ ...blankForm, project_id: requestedProject });
      setShowCreate(true);
    }
    reload().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load coworkers"))
      .finally(() => setLoading(false));
  }, []);

  async function createAgent(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = form.template_id
        ? await apiRequest<AgentProfile>(`/agents/templates/${form.template_id}/clone`, {
          method: "POST", body: JSON.stringify({ name: form.name, username: form.username,
            project_id: form.project_id ? Number(form.project_id) : null }),
        })
        : await apiRequest<AgentProfile>("/agents", {
          method: "POST", body: JSON.stringify({ ...form, project_id: form.project_id ? Number(form.project_id) : null }),
        });
      await reload();
      setShowCreate(false);
      setForm(blankForm);
      setNotice(form.template_id ? `${saved.name} created from template version ${saved.template_version}.` : `${saved.name} created. Use Edit to add knowledge resources.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create coworker");
    } finally {
      setBusy(false);
    }
  }

  async function copySourcePath(path: string, title: string) {
    try {
      await navigator.clipboard.writeText(path);
      setSourceNotice(`${title} path copied.`);
    } catch {
      setSourceNotice("Unable to copy the source path.");
    }
  }

  return (
    <section className="projectPage coworkerDirectory">
      <div className="projectPageHeader">
        <div><h1>AI co-workers</h1><span>Review each coworker, then open its dedicated workspace.</span></div>
        <div className="projectHeaderActions">

          <button className="projectButton" onClick={() => { setForm(blankForm); setError(null); setShowCreate(true); }} type="button"><Plus size={16} /> Create AI Co-worker</button>
        </div>
      </div>
      {error && !showCreate && <div className="formError" role="alert">{error}</div>}
      {notice && <Toast message={notice} />}
      <div className="agentRoster">
        <div className="agentSectionTitle"><strong>Existing co-workers</strong><span>{agents.length}</span></div>
        <div className="agentCardGrid">
          {loading && <LoadingSkeleton variant="cards" label="Loading coworkers" count={6} />}
          {!loading && agents.length === 0 && <div className="projectEmpty">No AI co-workers yet.</div>}
          {agents.map((agent) => (
            <article className="agentProfileCard" key={agent.id}>
              <div className="agentCardTop"><span className="agentCardAvatar"><Bot size={23} /></span><span className="agentCardStatus">{agent.status}</span></div>
              <div className="agentCardIdentity"><h2>{agent.name}</h2><span>{agent.handle} · {agent.role}{agent.template_agent_id ? ` · Template v${agent.template_version}` : ""}</span></div>
              <p>{agent.agent_description || "No responsibility description added yet."}</p>
              <div className="agentCardMeta">
                <button className="agentSourceCount" onClick={() => setProjectAgentId(agent.id)} type="button">{agent.projects.length} projects</button>
                <button className="agentSourceCount" onClick={() => { setSourceAgentId(agent.id); setSourceNotice(null); }} type="button">{agent.sources.length} knowledge sources</button>
              </div>
              <div className="agentCardActions">
                <Link className="ghostButton" href={`/agents/${agent.id}/tasks`}>Tasks</Link>
                <Link className="ghostButton" href={`/agents/${agent.id}/edit`}>Edit</Link>
                <Link className="ghostButton" href={`/agents/${agent.id}/train`}>Self Train</Link>
                <Link className="projectButton" href={`/agents/${agent.id}/try`}>Try</Link>
              </div>
            </article>
          ))}
        </div>
      </div>

      {showCreate && (
        <div className="modalBackdrop" role="presentation">
          <form aria-label="Create AI co-worker" aria-modal="true" className="memberModal projectForm" onSubmit={(event) => void createAgent(event)} role="dialog">
            <div className="modalHeader"><div><p className="projectEyebrow">AI Co-worker</p><h2>Create AI co-worker</h2></div><button aria-label="Close" className="iconLink" onClick={() => setShowCreate(false)} type="button"><X size={16} /></button></div>
            <div className="memberModalBody">
              {error && <div className="formError" role="alert">{error}</div>}
              {loadingOptions && <LoadingSkeleton variant="form" label="Loading creation options" count={2} />}
              {session.is_admin && <label>Start from template<select value={form.template_id} onChange={(event) => setForm({ ...form, template_id: event.target.value })}><option value="">Custom coworker</option>{templates.filter((template) => template.published_version > 0).map((template) => <option key={template.id} value={template.id}>{template.name} · version {template.published_version}</option>)}</select></label>}
              <div className="formGrid">
                <label>Name<input autoFocus required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
                <label>Username<input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
                {!form.template_id && <label>Role<input required value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} /></label>}
                <label>First project (optional)<select value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })}><option value="">Assign later</option>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
              </div>
              {!form.template_id && <><label>Agent description<textarea maxLength={300} placeholder="What work should this coworker handle?" value={form.agent_description} onChange={(event) => setForm({ ...form, agent_description: event.target.value })} /><span className="fieldHint">{form.agent_description.length}/300 characters</span></label>
                <div className="agentSectionTitle"><strong>Connected tools</strong></div>
                <p className="agentSectionCopy">Select the read-only sources this coworker may use when a chat request calls for them.</p>
                <div className="formGrid">{toolOptions.map((option) => <label className="projectTeamChoice" key={option.value}><input checked={form.tool_permissions.includes(option.value)} onChange={(event) => setForm({ ...form, tool_permissions: event.target.checked ? [...form.tool_permissions, option.value] : form.tool_permissions.filter((item) => item !== option.value) })} type="checkbox" /><span>{option.label}</span></label>)}</div></>}
            </div>
            <div className="formActions memberModalFooter"><button className="secondaryLink" onClick={() => setShowCreate(false)} type="button">Cancel</button><button className="projectButton" disabled={busy || loading || loadingOptions} type="submit">{busy ? "Creating..." : "Create Agent"}</button></div>
          </form>
        </div>
      )}

      {projectAgent && (
        <div className="modalBackdrop" role="presentation">
          <div aria-label={`${projectAgent.name} projects`} aria-modal="true" className="memberModal projectForm agentSourcesModal" role="dialog">
            <div className="modalHeader"><div><p className="projectEyebrow">Projects</p><h2>{projectAgent.name} · {projectAgent.projects.length} projects</h2></div><button aria-label="Close project list" className="iconLink" onClick={() => setProjectAgentId(null)} type="button"><X size={16} /></button></div>
            <div className="memberModalBody agentSourcesBody">
              {projectAgent.projects.length === 0 && <div className="projectEmpty">This coworker is not assigned to a project yet.</div>}
              {projectAgent.projects.map((project) => <article className="agentSourceCard" key={project.id}><div className="agentSectionTitle"><strong>{project.name}</strong><Link className="secondaryLink" href={`/projects/${project.id}/members`}>View project</Link></div></article>)}
            </div>
            <div className="formActions memberModalFooter"><button className="secondaryLink" onClick={() => setProjectAgentId(null)} type="button">Close</button></div>
          </div>
        </div>
      )}

      {sourceAgent && (
        <div className="modalBackdrop" role="presentation">
          <div aria-label={`${sourceAgent.name} knowledge sources`} aria-modal="true" className="memberModal projectForm agentSourcesModal" role="dialog">
            <div className="modalHeader"><div><p className="projectEyebrow">Knowledge sources</p><h2>{sourceAgent.name} · {sourceAgent.sources.length} sources</h2></div><button aria-label="Close source list" className="iconLink" onClick={() => setSourceAgentId(null)} type="button"><X size={16} /></button></div>
            <div className="memberModalBody agentSourcesBody">
              {sourceNotice && <Toast message={sourceNotice} tone="info" />}
              {sourceAgent.sources.length === 0 && <div className="projectEmpty">No knowledge sources have been added yet.</div>}
              {sourceAgent.sources.map((source) => (
                <article className="agentSourceCard" key={source.id}>
                  <div className="agentSectionTitle"><strong>{source.title}</strong><span className="agentResourceActions"><span>{source.approval_status}</span><button aria-label={`Copy ${source.title} path`} className="iconLink" disabled={!source.copy_path} onClick={() => void copySourcePath(source.copy_path, source.title)} title="Copy source path" type="button"><Copy size={15} /></button></span></div>
                  <p className="agentSectionCopy">Agent knowledge · {source.source_type}{["file", "markdown"].includes(source.source_type) && !source.file_available ? " · file unavailable" : ""}</p>
                </article>
              ))}
            </div>
            <div className="formActions memberModalFooter"><button className="secondaryLink" onClick={() => setSourceAgentId(null)} type="button">Close</button></div>
          </div>
        </div>
      )}
    </section>
  );
}
