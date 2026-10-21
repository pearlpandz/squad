import { ProjectDetailsClient } from "@/components/ProjectDetailsClient";

export default async function ProjectDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectDetailsClient projectId={id} />;
}

