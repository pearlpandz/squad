import { ProjectCollabClient } from "@/components/ProjectCollabClient";

export default async function ProjectCollabPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectCollabClient projectId={id} />;
}
