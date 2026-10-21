"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { AdminRequired, useAdminSession } from "@/components/AdminSession";

import { Toast } from "@/components/Toast";

import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MarkdownContent } from "@/components/MarkdownContent";
import { useRouter } from "next/navigation";
import { CheckCircle2, Copy, FileText, FileUp, RefreshCw, Send, Sparkles, Trash2 } from "lucide-react";

import { API_BASE_URL, AgentJob, AgentKnowledgeIndex, AgentProfile, AgentTrainingResult, apiRequest, uploadRequest } from "@/lib/api";
import { useNotificationSound } from "@/lib/useNotificationSound";

type Mode = "edit" | "train" | "try";
type TrialTurn = { role: "user" | "assistant"; content: string; refused?: boolean };
type TrialSession = { id: string; agent_id: number; messages: TrialTurn[] };
type ToolPermission = AgentProfile["tool_permissions"][number];
type ProfileForm = { name: string; role: string; agent_description: string; template_instructions: string; tool_permissions: ToolPermission[] };
const toolOptions: Array<{ value: ToolPermission; label: string }> = [
  { value: "web_search", label: "Public web search" },
  { value: "confluence_read", label: "Read Confluence" },
  { value: "oracle_read", label: "Read Oracle connectors" },
];

function formatUserDateTime(utcTimestamp: string): string {
  const normalized = utcTimestamp.trim().replace(" ", "T");
  const withTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`;
  return new Date(withTimezone).toLocaleString();
}

export function AgentActionClient({ agentId, mode }: { agentId: string; mode: Mode }) {
  const { session } = useAdminSession();
  const router = useRouter();
  const playNotification = useNotificationSound();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const workerRef = useRef<Worker | null>(null);
  const handledJobs = useRef<Set<number>>(new Set());
  const trialSessionId = useRef<string | null>(null);
  const [sessionReady, setSessionReady] = useState(false);
  const [agent, setAgent] = useState<AgentProfile | null>(null);
  const [form, setForm] = useState<ProfileForm>({ name: "", role: "", agent_description: "", template_instructions: "", tool_permissions: [] });
  const [files, setFiles] = useState<File[]>([]);
  const [index, setIndex] = useState<AgentKnowledgeIndex | null>(null);
  const [training, setTraining] = useState<AgentTrainingResult | null>(null);
  const [trialDraft, setTrialDraft] = useState("");
  const [trialMessages, setTrialMessages] = useState<TrialTurn[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [jobStatus, setJobStatus] = useState<AgentJob["status"] | null>(null);
  const [uploadState, setUploadState] = useState<{ phase: "uploading" | "processing"; percent: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setAgent(null);
    setIndex(null);
    setTraining(null);
    setTrialMessages([]);
    trialSessionId.current = null;
    setSessionReady(false);
    setTrialDraft("");
    setError(null);
    setNotice(null);
    const requests: [Promise<AgentProfile>, Promise<AgentKnowledgeIndex>?] = [apiRequest<AgentProfile>(`/agents/${agentId}`)];
    if (mode === "train") requests.push(apiRequest<AgentKnowledgeIndex>(`/agents/${agentId}/knowledge-index`));
    Promise.all(requests).then(([profile, knowledge]) => {
      if (!active) return;
      setAgent(profile);
      setForm({ name: profile.name, role: profile.role, agent_description: profile.agent_description, template_instructions: profile.template_instructions, tool_permissions: profile.tool_permissions });
      if (knowledge) setIndex(knowledge);
    }).catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to load coworker"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [agentId, mode, session.is_admin]);

  useEffect(() => {
    if (mode === "edit") return;
    const worker = new Worker("/agent-job-worker.js");
    workerRef.current = worker;
    let active = true;
    worker.onmessage = (event: MessageEvent<{ type: string; job?: AgentJob; message?: string }>) => {
      if (!active) return;
      if (event.data.type === "jobError") {
        setError(event.data.message || "Unable to follow agent job");
        setBusy(false); setJobStatus(null);
        return;
      }
      const job = event.data.job;
      if (event.data.type !== "job" || !job || job.kind !== (mode === "train" ? "self_train" : "trial")) return;
      if (job.kind === "trial" && job.request.session_id !== trialSessionId.current) return;
      setJobStatus(job.status);
      setBusy(job.status === "queued" || job.status === "running");
      if (job.kind === "trial" && job.request.message) {
        setTrialMessages((current) => current.length === 0
          ? [{ role: "user", content: job.request.message! }] : current);
      }
      if (job.status === "failed") {
        setError(job.error || "Agent job failed");
        return;
      }
      if (job.status !== "completed" || handledJobs.current.has(job.id)) return;
      handledJobs.current.add(job.id);
      if (job.kind === "self_train") {
        const result = job.result as AgentTrainingResult;
        setTraining(result);
        setNotice(result.errors.length ? "Done with errors. Review the details below." : "Done. Knowledge index updated.");
        void Promise.all([
          apiRequest<AgentProfile>(`/agents/${agentId}`),
          apiRequest<AgentKnowledgeIndex>(`/agents/${agentId}/knowledge-index`),
        ]).then(([profile, knowledge]) => { if (active) { setAgent(profile); setIndex(knowledge); } })
          .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to refresh knowledge status"); });
      } else {
        void apiRequest<TrialSession>(`/agents/${agentId}/trial-sessions/${trialSessionId.current}`)
          .then((session) => { if (active && session.id === trialSessionId.current) setTrialMessages(session.messages); })
          .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to restore session"); });
        playNotification();
      }
    };
    const kind = mode === "train" ? "self_train" : "trial";
    const restore = async () => {
      if (mode === "try") {
        const session = await apiRequest<TrialSession>(`/agents/${agentId}/trial-session`);
        if (!active) return;
        trialSessionId.current = session.id;
        setTrialMessages(session.messages);
        setSessionReady(true);
      }
      const job = await apiRequest<AgentJob | null>(`/agents/${agentId}/jobs/latest?kind=${kind}`);
      if (!active || !job) return;
      if (mode === "try" && job.request.session_id !== trialSessionId.current) return;
      if (mode === "try" && (job.status === "completed" || job.status === "failed")) return;
      if (mode === "train" && job.status === "completed") {
        setTraining(job.result as AgentTrainingResult);
        return;
      }
      worker.postMessage({ type: "resumeJob", baseUrl: API_BASE_URL, agentId, job });
    };
    void restore().catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to restore session"); });
    return () => { active = false; worker.terminate(); workerRef.current = null; handledJobs.current.clear(); };
  }, [agentId, mode, playNotification, session.is_admin]);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(null); setNotice(null);
    try {
      const updated = await apiRequest<AgentProfile>(`/agents/${agentId}`, { method: "PUT", body: JSON.stringify(form) });
      setAgent(updated);
      setNotice("Coworker profile updated.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update coworker");
    } finally { setBusy(false); }
  }

  async function upgradeTemplate() {
    if (!agent?.template_agent_id) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const updated = await apiRequest<AgentProfile>(`/agents/${agentId}/upgrade-template`, { method: "POST" });
      setAgent(updated);
      setNotice(`Template version ${updated.template_version} applied. Individual knowledge and memory were kept.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to upgrade template");
    } finally { setBusy(false); }
  }

  async function uploadKnowledge() {
    if (files.length === 0) return;
    setBusy(true); setError(null); setNotice(null); setUploadState({ phase: "uploading", percent: 0 });
    try {
      const body = new FormData();
      files.forEach((file) => body.append("files", file));
      const result = await uploadRequest<{ agent: AgentProfile }>(
        `/agents/${agentId}/knowledge`, body,
        (percent) => setUploadState((current) => current?.phase === "uploading" ? { phase: "uploading", percent } : current),
        () => setUploadState({ phase: "processing", percent: 100 }),
      );
      setAgent(result.agent);
      setFiles([]);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setNotice(`${files.length} resource${files.length === 1 ? "" : "s"} uploaded. Select Start Self Train to update the knowledge graph and embeddings.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to upload knowledge");
    } finally { setBusy(false); setUploadState(null); }
  }

  async function deleteAgent() {
    if (!agent || !window.confirm(`Permanently delete ${agent.name}, their knowledge, and their authored chat messages?`)) return;
    setBusy(true); setError(null);
    try {
      await apiRequest<{ detail: string }>(`/agents/${agentId}`, { method: "DELETE" });
      router.push(agent.is_template ? "/templates" : "/agents");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete coworker");
    } finally { setBusy(false); }
  }

  async function deleteKnowledge(source: AgentProfile["sources"][number]) {
    if (!window.confirm(`Delete ${source.title}? Select Start Self Train afterward to remove its graph knowledge and embeddings.`)) return;
    setBusy(true); setError(null); setNotice(null);
    try {
      const result = await apiRequest<{ detail: string; file_cleanup_error: string | null }>(
        `/agents/${agentId}/knowledge/${source.id}`, { method: "DELETE" },
      );
      setAgent(await apiRequest<AgentProfile>(`/agents/${agentId}`));
      setNotice(result.file_cleanup_error
        ? `Resource removed. Select Start Self Train to update knowledge. File cleanup failed: ${result.file_cleanup_error}`
        : `${source.title} removed. Select Start Self Train to update the graph and embeddings.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete knowledge resource");
    } finally { setBusy(false); }
  }

  function selfTrain() {
    if (busy || !index || !hasTrainingWork) return;
    setBusy(true); setError(null); setNotice(null); setTraining(null);
    setJobStatus("queued");
    workerRef.current?.postMessage({ type: "startJob", baseUrl: API_BASE_URL, agentId, kind: "self_train", request: {} });
  }

  function sendTrial(event: FormEvent) {
    event.preventDefault();
    if (!agent || !trialDraft.trim() || busy || !trialSessionId.current) return;
    const message = trialDraft.trim();
    setBusy(true); setError(null);
    setJobStatus("queued");
    workerRef.current?.postMessage({ type: "startJob", baseUrl: API_BASE_URL, agentId,
      kind: "trial", request: { message, session_id: trialSessionId.current } });
    setTrialMessages((current) => [...current, { role: "user", content: message }]);
    setTrialDraft("");
  }

  async function startNewTrial() {
    if (busy) return;
    setSessionReady(false);
    try {
      const session = await apiRequest<TrialSession>(`/agents/${agentId}/trial-sessions`, { method: "POST" });
      trialSessionId.current = session.id;
      setTrialMessages(session.messages);
      setTrialDraft("");
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to start a new chat");
    } finally { setSessionReady(true); }
  }

  async function copyPath(path: string) {
    try { await navigator.clipboard.writeText(path); setNotice("Source path copied."); }
    catch { setNotice("Unable to copy the source path."); }
  }

  const pendingItems = index?.pending_items ?? [];
  const hasTrainingWork = pendingItems.length > 0;
  const pendingDocuments = pendingItems.filter((item) => item.source_kind === "file" && item.action !== "removed");
  const pendingOther = pendingItems.filter((item) => item.source_kind !== "file" || item.action === "removed");

  const title = mode === "edit" ? "Edit" : mode === "train" ? "Self Train" : "Try";
  const description = mode === "edit" ? "Manage this coworker's profile, knowledge, and tools."
    : mode === "train" ? "Train this coworker on approved skills and documents."
    : "Chat with this coworker and explore its capabilities.";
  if (agent?.is_template && !session.is_admin) return <AdminRequired />;
  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div><h1>{title}{agent ? ` ${agent.name}` : " coworker"}</h1><span>{description}</span></div>
      </div>
      {agent && <nav aria-label="Coworker actions" className="agentActionNav">
        <Link href={`/agents/${agentId}/tasks`}>Tasks</Link>
        <Link aria-current={mode === "edit" ? "page" : undefined} href={`/agents/${agentId}/edit`}>Edit</Link>
        <Link aria-current={mode === "train" ? "page" : undefined} href={`/agents/${agentId}/train`}>Self Train</Link>
        <Link aria-current={mode === "try" ? "page" : undefined} href={`/agents/${agentId}/try`}>Try</Link>
      </nav>}
      {error && <Toast message={error} tone="error" />}
      {notice && <Toast message={notice} />}
      {(jobStatus === "queued" || jobStatus === "running") && <Toast message={`${jobStatus === "queued" ? "Queued" : "Running"}. You can leave this page and return to see the result.`} tone="info" />}
      {loading && <LoadingSkeleton variant={mode === "try" ? "chat" : "form"} label="Loading coworker" count={4} />}
      {!loading && !agent && !error && <div className="projectEmpty">Coworker not found.</div>}

      {agent && mode === "edit" && <div className="agentActionContent agentEditContent">
        <form className="projectForm" onSubmit={(event) => void saveProfile(event)}>
          <div className="agentSectionTitle"><strong>Profile</strong><span>{agent.handle}</span></div>
          <div className="formGrid"><label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label><label>Role<input required value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} /></label></div>
          <label>Agent description<textarea maxLength={300} value={form.agent_description} onChange={(event) => setForm({ ...form, agent_description: event.target.value })} /><span className="fieldHint">{form.agent_description.length}/300 characters</span></label>
          {Boolean(agent.is_template) && <label>Default instructions<textarea maxLength={12000} rows={8} value={form.template_instructions} onChange={(event) => setForm({ ...form, template_instructions: event.target.value })} /><span className="fieldHint">Changes publish when you select Start Self Train.</span></label>}
          {agent.template_agent_id && session.is_admin && <p className="agentSectionCopy">Created from template #{agent.template_agent_id}, version {agent.template_version}. Shared knowledge comes from the template; projects, tasks, and experience belong to this coworker.</p>}
          <div className="agentSectionTitle"><strong>Connected tools</strong></div>
          <p className="agentSectionCopy">Grant read-only access. Chat intent determines when each granted source is used.</p>
          <div className="formGrid">{toolOptions.map((option) => <label className="projectTeamChoice" key={option.value}><input checked={form.tool_permissions.includes(option.value)} onChange={(event) => setForm({ ...form, tool_permissions: event.target.checked ? [...form.tool_permissions, option.value] : form.tool_permissions.filter((item) => item !== option.value) })} type="checkbox" /><span>{option.label}</span></label>)}</div>
          <div className="formActions"><button className="projectButton" disabled={busy} type="submit">{busy ? "Saving..." : "Save Changes"}</button>{agent.template_agent_id && session.is_admin && <button className="ghostButton" disabled={busy} onClick={() => void upgradeTemplate()} type="button">Upgrade Template</button>}<button className="ghostButton agentDeleteButton" disabled={busy || agent.projects.length > 0} onClick={() => void deleteAgent()} type="button"><Trash2 size={16} /> Delete {agent.is_template ? "Template" : "Agent"}</button></div>
          {agent.projects.length > 0 && <p className="agentSectionCopy">Part of {agent.projects.map((project, index) => <span key={project.id}>{index > 0 ? ", " : ""}<Link href={`/projects/${project.id}/members`}>{project.name}</Link></span>)}. Remove the coworker from these projects before deleting it.</p>}
        </form>
        <section className="projectForm">
          <div className="agentSectionTitle"><strong>Knowledge resources</strong><span>{agent.sources.length} sources</span></div>
          <p className="agentSectionCopy">{agent.template_agent_id ? session.is_admin ? <>Add shared files in the <Link href={`/agents/${agent.template_agent_id}/edit`}>agent template</Link>, train it, then upgrade this coworker. Self Train here updates its project experience.</> : "Shared resources are managed by your SQUAD admin team. Self Train here updates this coworker's project experience." : "Add or remove resources here, then select Start Self Train to update this coworker's graph and embeddings."}</p>
          {!agent.template_agent_id && <><label>Files<input accept=".txt,.md,.doc,.docx,.pdf,.ppt,.pptx" disabled={busy} multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} ref={fileInputRef} type="file" /></label>
          <span className="fieldHint">TXT, MD, DOC, DOCX, PDF, PPT, and PPTX.</span>
          <span className="fieldHint">Maximum 50 MB per file.</span>
          {files.length > 0 && <p className="agentSectionCopy">{files.map((file) => file.name).join(", ")}</p>}
          <button className="projectButton" disabled={busy || files.length === 0} onClick={() => void uploadKnowledge()} type="button"><FileUp size={16} /> {busy && uploadState ? "Uploading..." : "Upload resources"}</button></>}
          {uploadState && <div aria-live="polite" className="agentUploadStatus" role="status">
            <strong>{uploadState.phase === "uploading" ? `Uploading files: ${uploadState.percent}%` : "Upload complete. Saving resources..."}</strong>
            {uploadState.phase === "uploading" && <div aria-label="File upload progress" aria-valuemax={100} aria-valuemin={0} aria-valuenow={uploadState.percent} className="agentUploadTrack" role="progressbar"><span style={{ width: `${uploadState.percent}%` }} /></div>}
          </div>}
          <div className="agentSourceList">{agent.sources.map((source) => <div className="agentResourceRow" key={source.id}><div><strong>{source.title}</strong><small>{source.template_source_id ? "Inherited template knowledge" : "Agent knowledge"} · {source.approval_status}</small></div><div className="agentResourceActions"><button aria-label={`Copy ${source.title} path`} className="iconLink" disabled={!source.copy_path} onClick={() => void copyPath(source.copy_path)} title="Copy source path" type="button"><Copy size={15} /></button>{source.approval_status === "approved" && !source.template_source_id && <button aria-label={`Delete ${source.title}`} className="iconLink agentDeleteButton" disabled={busy} onClick={() => void deleteKnowledge(source)} title="Delete knowledge resource" type="button"><Trash2 size={15} /></button>}</div></div>)}</div>
        </section>
      </div>}

      {agent && mode === "train" && <div className="agentActionContent agentTrainLayout">
        <div className="agentTrainMain">
          <section className="projectForm agentTrainQueue">
            <div className="agentTrainQueueHeader">
              <div className="agentSectionTitle"><strong>Ready to train</strong><span>{pendingItems.length > 0 ? `${pendingItems.length} pending` : "No pending changes"}</span></div>
              <button className="projectButton" disabled={busy || !index || !hasTrainingWork} onClick={() => void selfTrain()} type="button">{busy ? <RefreshCw size={16} /> : <Sparkles size={16} />}{busy ? "Training..." : "Start Self Train"}</button>
            </div>
            {pendingDocuments.length > 0 && <ul className="agentPendingList">{pendingDocuments.map((item) => <li key={item.source_key}><FileText aria-hidden="true" size={18} /><strong>{item.title}</strong><span>{item.action === "added" ? "Untrained" : "Update ready"}</span></li>)}</ul>}
            {pendingOther.length > 0 && <ul className="agentPendingList">{pendingOther.map((item) => <li key={item.source_key}><RefreshCw aria-hidden="true" size={16} /><strong>{item.title}</strong><span>{item.action === "removed" ? "Remove from graph" : "Update ready"}</span></li>)}</ul>}
            {index && !hasTrainingWork && <p className="agentTrainCurrent"><CheckCircle2 aria-hidden="true" size={18} />{index.items.length > 0 ? "Everything is up to date." : "Add knowledge resources to get started."}</p>}
            {!index && <LoadingSkeleton variant="content" label="Loading training status" count={2} />}
          </section>
          <section className="projectForm">
            <div className="agentSectionTitle"><strong>Included in the graph</strong><span>{index?.items.length ?? 0} sources</span></div>
            <div className="agentTrainingDetails">{index?.items.map((item) => <div key={`${item.project_id}-${item.source_kind}-${item.source_id}`}><strong>{item.title}</strong></div>)}{index?.items.length === 0 && <p className="agentSectionCopy">No sources trained yet.</p>}</div>
          </section>
        {training && (training.errors.length > 0 || training.details.some((item) => item.outcome === "error" || item.outcome === "empty")) && <section className="projectForm" aria-live="polite">
          <div className="agentSectionTitle"><strong>Failed to train</strong></div>
          {training.errors.length > 0 && <div className="formError" role="alert">{training.errors.map((message, position) => <p key={position}>{message}</p>)}</div>}
          <div className="agentTrainingDetails">{training.details.filter((item) => item.outcome === "error" || item.outcome === "empty").map((item, position) => <div key={`${item.project_id}-${item.source_kind}-${item.source_id}-${position}`}><strong>{item.title}</strong><span>{item.outcome === "empty" ? "No content available to train." : "Training failed."}</span></div>)}</div>
        </section>}
        </div>
        <aside className="projectForm agentGraphSummary" aria-label="Graph summary">
          <div className="agentSectionTitle"><strong>Graph summary</strong></div>
          <dl>
            <div className="agentGraphLastTrained"><dt>Last trained</dt><dd>{index?.last_trained_at ? formatUserDateTime(index.last_trained_at) : "Never"}</dd></div>
            <div><dt>Chunks</dt><dd>{(index?.chunk_count ?? 0).toLocaleString()}</dd></div>
            <div><dt>Concepts</dt><dd>{(index?.concept_count ?? 0).toLocaleString()}</dd></div>
            <div><dt>Links</dt><dd>{(index?.edge_count ?? 0).toLocaleString()}</dd></div>
          </dl>
        </aside>
      </div>}

      {agent && mode === "try" && <section className="projectForm agentTryPage">
        <div className="agentSectionTitle"><strong>Conversation</strong><button className="ghostButton" disabled={busy || !sessionReady} onClick={() => void startNewTrial()} type="button">New chat</button></div>
        <p className="agentSectionCopy">This chat uses {agent.name}&apos;s knowledge graph and granted read-only tools when your request calls for them. Start Self Train first.</p>
        <div aria-live="polite" className="agentTrialMessages">{trialMessages.length === 0 && <p className="agentSectionCopy">Ask a question within this coworker&apos;s responsibilities.</p>}{trialMessages.map((turn, index) => <div className={`agentTrialMessage ${turn.role}`} key={index}><strong>{turn.role === "user" ? "You" : agent.name}{turn.refused ? " · Outside scope" : ""}</strong>{turn.role === "assistant" ? <MarkdownContent content={turn.content} /> : <p>{turn.content}</p>}</div>)}{busy && <p className="agentSectionCopy">{agent.name} is responding...</p>}</div>
        <form className="agentTrialComposer" onSubmit={(event) => void sendTrial(event)}><textarea aria-label={`Message ${agent.name}`} maxLength={4000} onChange={(event) => setTrialDraft(event.target.value)} placeholder={`Ask ${agent.name} a question...`} value={trialDraft} /><button className="projectButton" disabled={busy || !sessionReady || !trialDraft.trim()} type="submit">{busy ? "Thinking..." : "Send"}<Send size={16} /></button></form>
      </section>}
    </section>
  );
}
