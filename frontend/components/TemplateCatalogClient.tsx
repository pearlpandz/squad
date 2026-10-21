"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";
import { AdminRequired, useAdminSession } from "@/components/AdminSession";

import { Toast } from "@/components/Toast";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bot, Plus, X } from "lucide-react";

import { AgentProfile, apiRequest } from "@/lib/api";

type TemplateForm = {
  name: string; username: string; role: string; agent_description: string;
  template_instructions: string; tool_permissions: AgentProfile["tool_permissions"];
};
const blankTemplate: TemplateForm = {
  name: "Business Analyst", username: "business-analyst-template", role: "Business Analyst",
  agent_description: "Analyze business requirements and prepare functional design deliverables.",
  template_instructions: "Use the trained skills and sources to identify required inputs before starting. Ask for missing inputs, prepare the requested deliverable, validate it, and share generated artifact paths.",
  tool_permissions: ["web_search", "confluence_read", "oracle_read"],
};

export function TemplateCatalogClient() {
  const { session, loading } = useAdminSession();
  if (loading) return <LoadingSkeleton fullPage variant="cards" label="Checking administrator access" />;
  if (!session.is_admin) return <AdminRequired />;
  return <TemplateCatalog />;
}

function TemplateCatalog() {
  const router = useRouter();
  const [templates, setTemplates] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [copyFrom, setCopyFrom] = useState<AgentProfile | null>(null);
  const [form, setForm] = useState<TemplateForm>(blankTemplate);
  const [copyName, setCopyName] = useState("");
  const [copyUsername, setCopyUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function reload() {
    setTemplates(await apiRequest<AgentProfile[]>("/agents/templates"));
  }
  useEffect(() => {
    reload().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load templates"))
      .finally(() => setLoading(false));
  }, []);

  async function createTemplate(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const created = await apiRequest<AgentProfile>("/agents/templates", {
        method: "POST", body: JSON.stringify(form),
      });
      setShowCreate(false); setForm(blankTemplate);
      await reload();
      setNotice(`${created.name} created. Add its skills and documents, then Start Self Train to publish version 1.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create template");
    } finally { setBusy(false); }
  }

  async function createCopy(event: FormEvent) {
    event.preventDefault();
    if (!copyFrom) return;
    setBusy(true); setError(null);
    try {
      const created = await apiRequest<AgentProfile>(`/agents/templates/${copyFrom.id}/clone`, {
        method: "POST", body: JSON.stringify({ name: copyName, username: copyUsername }),
      });
      setCopyFrom(null); setCopyName(""); setCopyUsername("");
      router.push(`/agents/${created.id}/edit`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create coworker");
    } finally { setBusy(false); }
  }

  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div><h1>Agent templates</h1><span>Publish shared skills and knowledge, then create independent coworkers.</span></div>
        <div className="projectHeaderActions">
          
          <button className="projectButton" onClick={() => { setError(null); setShowCreate(true); }} type="button"><Plus size={16} /> Create Template</button>
        </div>
      </div>
      {error && !showCreate && !copyFrom && <div className="formError" role="alert">{error}</div>}
      {notice && <Toast message={notice} />}
      <div className="agentRoster">
        <div className="agentSectionTitle"><strong>Published and draft templates</strong><span>{templates.length}</span></div>
        <div className="agentCardGrid">
          {loading && <LoadingSkeleton variant="cards" label="Loading templates" count={6} />}
          {!loading && templates.length === 0 && <div className="projectEmpty">No templates yet. Create the Business Analyst template to begin.</div>}
          {templates.map((template) => (
            <article className="agentProfileCard" key={template.id}>
              <div className="agentCardTop"><span className="agentCardAvatar"><Bot size={23} /></span><span className="agentCardStatus">{template.published_version ? `Version ${template.published_version}` : "Draft"}</span></div>
              <div className="agentCardIdentity"><h2>{template.name}</h2><span>{template.role}</span></div>
              <p>{template.agent_description || "Add the work this template is designed to perform."}</p>
              <div className="agentCardMeta"><span>{template.sources.filter((source) => source.approval_status === "approved").length} shared resources</span></div>
              <div className="agentCardActions">
                <Link className="ghostButton" href={`/agents/${template.id}/edit`}>Edit</Link>
                <Link className="ghostButton" href={`/agents/${template.id}/train`}>Self Train</Link>
                <button className="projectButton" disabled={!template.published_version} onClick={() => { setError(null); setCopyFrom(template); }} type="button">Create Co-worker</button>
              </div>
            </article>
          ))}
        </div>
      </div>
      {showCreate && <div className="modalBackdrop" role="presentation"><form aria-label="Create agent template" aria-modal="true" className="memberModal projectForm" onSubmit={(event) => void createTemplate(event)} role="dialog">
        <div className="modalHeader"><div><p className="projectEyebrow">Template</p><h2>Create agent template</h2></div><button aria-label="Close" className="iconLink" onClick={() => setShowCreate(false)} type="button"><X size={16} /></button></div>
        <div className="memberModalBody">
          {error && <div className="formError" role="alert">{error}</div>}
          <div className="formGrid">
            <label>Name<input required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label>Template username<input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} /></label>
            <label>Role<input required value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value })} /></label>
          </div>
          <label>Description<textarea maxLength={300} value={form.agent_description} onChange={(event) => setForm({ ...form, agent_description: event.target.value })} /></label>
          <label>Default instructions<textarea required rows={6} value={form.template_instructions} onChange={(event) => setForm({ ...form, template_instructions: event.target.value })} /></label>
        </div>
        <div className="formActions memberModalFooter"><button className="secondaryLink" onClick={() => setShowCreate(false)} type="button">Cancel</button><button className="projectButton" disabled={busy} type="submit">{busy ? "Creating..." : "Create Template"}</button></div>
      </form></div>}
      {copyFrom && <div className="modalBackdrop" role="presentation"><form aria-label="Create coworker from template" aria-modal="true" className="memberModal projectForm" onSubmit={(event) => void createCopy(event)} role="dialog">
        <div className="modalHeader"><div><p className="projectEyebrow">{copyFrom.name} · Version {copyFrom.published_version}</p><h2>Create co-worker</h2></div><button aria-label="Close" className="iconLink" onClick={() => setCopyFrom(null)} type="button"><X size={16} /></button></div>
        <div className="memberModalBody">
          {error && <div className="formError" role="alert">{error}</div>}
          <p className="agentSectionCopy">This coworker inherits the published defaults and starts with its own memory. Assign projects after creation.</p>
          <div className="formGrid">
            <label>Name<input autoFocus required value={copyName} onChange={(event) => setCopyName(event.target.value)} /></label>
            <label>Username<input required value={copyUsername} onChange={(event) => setCopyUsername(event.target.value)} /></label>
          </div>
        </div>
        <div className="formActions memberModalFooter"><button className="secondaryLink" onClick={() => setCopyFrom(null)} type="button">Cancel</button><button className="projectButton" disabled={busy} type="submit">{busy ? "Creating..." : "Create Co-worker"}</button></div>
      </form></div>}
    </section>
  );
}
