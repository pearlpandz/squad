import { ProjectEditClient } from "@/components/ProjectEditClient";

export default async function EditProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ProjectEditClient projectId={id} />;
}
