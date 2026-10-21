"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useEffect, useState } from "react";

import { ProjectForm } from "@/components/ProjectForm";
import { ProjectDetail, apiRequest } from "@/lib/api";

export function ProjectEditClient({ projectId }: { projectId: string }) {
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
    return <LoadingSkeleton fullPage variant="form" label="Loading project" count={5} />;
  }

  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div>
          <h1>{project.name}</h1>
          <span>Update project metadata, stack, and human members.</span>
        </div>
      </div>
      <ProjectForm mode="edit" project={project} />
    </section>
  );
}

