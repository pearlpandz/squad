"use client";

import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";

import { ProjectDetail, ProjectPayload, apiRequest, projectActorHumanId } from "@/lib/api";

type ProjectFormProps = {
  project?: ProjectDetail;
  mode: "create" | "edit";
};

const deliveryStages = [
  { value: "discovery", label: "Discovery" },
  { value: "planning", label: "Planning" },
  { value: "design", label: "Design" },
  { value: "execution", label: "Execution" },
  { value: "testing", label: "Testing" },
  { value: "release", label: "Release" },
  { value: "maintenance", label: "Maintenance" },
  { value: "on-hold", label: "On Hold" },
];

function toLines(values: string[]) {
  return values.join("\n");
}

function fromLines(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function metadataToText(metadata: Record<string, unknown>) {
  return Object.entries(metadata)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join("\n");
}

function metadataFromText(value: string) {
  return Object.fromEntries(
    value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const [key, ...rest] = line.split("=");
        return [key.trim(), rest.join("=").trim()];
      })
      .filter(([key]) => key),
  );
}

export function ProjectForm({ project, mode }: ProjectFormProps) {
  const router = useRouter();
  const initial = useMemo(
    () => ({
      code: project?.code ?? "",
      name: project?.name ?? "",
      description: project?.description ?? "",
      status: project?.status ?? "active",
      business_domain: project?.business_domain ?? "",
      repository_url: project?.repository_url ?? "",
      delivery_stage: project?.delivery_stage ?? "discovery",
      priority: project?.priority ?? "medium",
      tech_stack: toLines(project?.tech_stack ?? []),
      metadata: metadataToText(project?.metadata ?? {}),
      human_member_ids: (project?.human_members ?? []).map((member) => member.id).join(","),
    }),
    [project],
  );
  const [form, setForm] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    const payload: ProjectPayload = {
      code: form.code,
      name: form.name,
      description: form.description,
      status: form.status,
      business_domain: form.business_domain,
      repository_url: form.repository_url,
      delivery_stage: form.delivery_stage,
      priority: form.priority,
      tech_stack: fromLines(form.tech_stack),
      metadata: metadataFromText(form.metadata),
      human_member_ids: fromLines(form.human_member_ids).map(Number).filter(Boolean),
    };

    try {
      const actorId = await projectActorHumanId();
      if (mode === "create") payload.created_by_human_id = actorId;
      payload.updated_by_human_id = actorId;
      const saved = await apiRequest<ProjectDetail>(
        mode === "create" ? "/projects" : `/projects/${project?.id}`,
        {
          method: mode === "create" ? "POST" : "PUT",
          body: JSON.stringify(payload),
        },
      );
      router.push(`/projects/${saved.id}`);
      router.refresh();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save project");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="projectForm" onSubmit={submit}>
      {error && <div className="formError">{error}</div>}

      <div className="formGrid">
        <label>
          Name
          <input value={form.name} onChange={(event) => update("name", event.target.value)} required />
        </label>
        <label>
          Code
          <input value={form.code} onChange={(event) => update("code", event.target.value)} required />
        </label>
        <label>
          Status
          <select value={form.status} onChange={(event) => update("status", event.target.value)}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="on-hold">On Hold</option>
          </select>
        </label>
        <label>
          Priority
          <select value={form.priority} onChange={(event) => update("priority", event.target.value)}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </label>
        <label>
          Business Domain
          <input
            value={form.business_domain}
            onChange={(event) => update("business_domain", event.target.value)}
          />
        </label>
        <label>
          Delivery Stage
          <select value={form.delivery_stage} onChange={(event) => update("delivery_stage", event.target.value)}>
            {deliveryStages.map((stage) => (
              <option key={stage.value} value={stage.value}>
                {stage.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label>
        Description
        <textarea value={form.description} onChange={(event) => update("description", event.target.value)} />
      </label>

      <label>
        Repository URL
        <input value={form.repository_url} onChange={(event) => update("repository_url", event.target.value)} />
      </label>

      <div className="formGrid">
        <label>
          Tech Stack
          <textarea
            value={form.tech_stack}
            onChange={(event) => update("tech_stack", event.target.value)}
            placeholder="One per line or comma separated"
          />
        </label>
        <label>
          Metadata
          <textarea
            value={form.metadata}
            onChange={(event) => update("metadata", event.target.value)}
            placeholder="key=value"
          />
        </label>
      </div>

      <label>
        Human Member IDs
        <input
          value={form.human_member_ids}
          onChange={(event) => update("human_member_ids", event.target.value)}
          placeholder="Example: 1,2"
        />
      </label>

      <div className="formActions">
        <button className="secondaryLink" type="button" onClick={() => router.back()}>
          Cancel
        </button>
        <button className="projectButton" type="submit" disabled={saving}>
          <Save size={16} />
          {saving ? "Saving" : "Save Project"}
        </button>
      </div>
    </form>
  );
}
