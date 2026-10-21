import { ProjectMembersClient } from "@/components/ProjectMembersClient";

export default async function ProjectMembersPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectMembersClient projectId={id} />;
}
