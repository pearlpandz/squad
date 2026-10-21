import { TeamsClient } from "@/components/TeamsClient";

export default async function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TeamsClient teamId={id} />;
}
