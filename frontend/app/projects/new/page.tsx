import { ProjectCreateForm } from "@/components/ProjectCreateForm";

export default async function NewProjectPage({ searchParams }: { searchParams: Promise<{ team?: string }> }) {
  const { team } = await searchParams;
  return (
    <section className="projectPage">
      <div className="projectPageHeader">
        <div>
          <h1>Create project</h1>
          <span>Add the project details and choose AI coworkers for its team.</span>
        </div>
      </div>
      <ProjectCreateForm initialTeamId={team} />
    </section>
  );
}
