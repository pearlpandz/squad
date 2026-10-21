"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Edit, MessageSquare, UserPlus, Users } from "lucide-react";

import { ProjectDetail, apiRequest } from "@/lib/api";

export function ProjectDetailsClient({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<ProjectDetail>(`/projects/${projectId}`)
      .then(setProject)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load project"));
  }, [projectId]);

  if (error) {
    return <section className="projectPage"><div className="formError">{error}</div></section>;
  }

  if (!project) {
    return <LoadingSkeleton fullPage variant="details" label="Loading project" count={4} />;
  }

  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div>
          <h1>{project.name}</h1>
          <span>{project.description || "No description added."}</span>
        </div>
        <div className="projectHeaderActions">
          <Link className="ghostButton" href={`/projects/${project.id}/collab`}>
            <MessageSquare size={16} />
            Collab
          </Link>
          <Link className="ghostButton" href={`/projects/${project.id}/members`}>
            <UserPlus size={16} />
            Update Members
          </Link>
          <Link className="projectButton" href={`/projects/${project.id}/edit`}>
            <Edit size={16} />
            Edit Project
          </Link>
        </div>
      </div>

      <div className="detailGrid">
        <section className="detailPanel">
          <h2>About</h2>
          <dl>
            <div><dt>Status</dt><dd>{project.status}</dd></div>
            <div><dt>Business Domain</dt><dd>{project.business_domain || "-"}</dd></div>
            <div><dt>Delivery Stage</dt><dd>{project.delivery_stage}</dd></div>
            <div><dt>Priority</dt><dd>{project.priority}</dd></div>
            <div><dt>Repository</dt><dd>{project.repository_url || "-"}</dd></div>
          </dl>
        </section>

        <section className="detailPanel">
          <h2>Metadata</h2>
          <dl>
            <div><dt>Created At</dt><dd>{project.created_at}</dd></div>
            <div><dt>Created By</dt><dd>{project.created_by || "-"}</dd></div>
            <div><dt>Updated At</dt><dd>{project.updated_at}</dd></div>
            <div><dt>Updated By</dt><dd>{project.updated_by || "-"}</dd></div>
            <div><dt>Removed At</dt><dd>{project.removed_at || "-"}</dd></div>
          </dl>
        </section>
      </div>

      <section className="detailPanel">
        <h2>Tech Stack</h2>
        <div className="chipRow roomy">
          {project.tech_stack.map((item) => <span key={item}>{item}</span>)}
          {project.tech_stack.length === 0 && <span>Not captured</span>}
        </div>
      </section>

      <div className="detailGrid">
        <section className="detailPanel">
          <h2><Users size={16} /> Human Members</h2>
          <div className="memberList">
            {project.human_members.map((member) => (
              <div className="memberItem" key={member.id}>
                <strong>{member.display_name}</strong>
                <span>{member.member_role} - {member.status}</span>
                <p>{member.email || member.role}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="detailPanel">
          <h2>AI Members</h2>
          <div className="memberList">
            {project.ai_members.map((member) => (
              <div className="memberItem" key={member.id}>
                <strong>{member.name} <em>{member.handle}</em></strong>
                <span>{member.role} - {member.status}</span>
                <p>{member.knowledge_scope}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="detailPanel">
        <h2>Custom Metadata</h2>
        <pre className="metadataPre">{JSON.stringify(project.metadata, null, 2)}</pre>
      </section>
    </section>
  );
}
