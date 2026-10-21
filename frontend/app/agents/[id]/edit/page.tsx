import { AgentActionClient } from "@/components/AgentActionClient";

export default async function EditAgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AgentActionClient agentId={id} mode="edit" />;
}
