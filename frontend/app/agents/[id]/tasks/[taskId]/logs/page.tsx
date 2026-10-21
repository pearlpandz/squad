import { TaskExecutionLogsClient } from "@/components/TaskExecutionLogsClient";

export default async function TaskExecutionLogsPage({ params, searchParams }: {
  params: Promise<{ id: string; taskId: string }>;
  searchParams: Promise<{ run?: string }>;
}) {
  const { id, taskId } = await params;
  const { run } = await searchParams;
  return <TaskExecutionLogsClient agentId={id} taskId={taskId} requestedRun={run} />;
}
