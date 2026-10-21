import { AgentTasksClient } from "@/components/AgentTasksClient";

export default async function AgentTasksPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AgentTasksClient agentId={id} />;
}
