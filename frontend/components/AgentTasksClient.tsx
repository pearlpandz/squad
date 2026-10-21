"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { MarkdownContent } from "@/components/MarkdownContent";

import { AgentProfile, AgentTask, apiRequest } from "@/lib/api";

function localTime(value: string | null): string {
  if (!value) return "Not started";
  const normalized = value.trim().replace(" ", "T");
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`).toLocaleString();
}

export function AgentTasksClient({ agentId }: { agentId: string }) {
  const [agent, setAgent] = useState<AgentProfile | null>(null);
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try {
      const [profile, rows] = await Promise.all([
        apiRequest<AgentProfile>(`/agents/${agentId}`),
        apiRequest<AgentTask[]>(`/agents/${agentId}/tasks`),
      ]);
      setAgent(profile);
      setTasks(rows);
      setSelectedId((current) => current !== null && rows.some((row) => row.id === current) ? current : rows[0]?.id ?? null);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load tasks");
    } finally { setLoading(false); }
  }, [agentId]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!tasks.some((task) => task.status === "queued" || task.status === "in_progress")) return;
    const timer = window.setInterval(() => void load(), 5000);
    return () => window.clearInterval(timer);
  }, [tasks, load]);

  const visible = tasks.filter((task) => filter === "all" || task.status === filter);
  const selected = tasks.find((task) => task.id === selectedId) ?? null;
  const active = tasks.filter((task) => task.status === "queued" || task.status === "in_progress").length;

  return <section className="projectPage">
    <div className="projectPageHeader">
      <div><h1>{agent ? `${agent.name}'s tasks` : "Coworker tasks"}</h1><span>Track assigned work, progress, and previous results.</span></div>
      
    </div>
    {agent && <nav aria-label="Coworker actions" className="agentActionNav"><Link aria-current="page" href={`/agents/${agentId}/tasks`}>Tasks</Link><Link href={`/agents/${agentId}/edit`}>Edit</Link><Link href={`/agents/${agentId}/train`}>Self Train</Link><Link href={`/agents/${agentId}/try`}>Try</Link></nav>}
    {error && <div className="formError" role="alert">{error}</div>}
    {loading && <LoadingSkeleton label="Loading tasks" count={5} />}
    {!loading && <div className="agentTasksLayout">
      <section className="projectForm agentTasksList"><div className="agentSectionTitle"><strong>Task queue and history</strong><span>{active} active · {visible.length} shown</span></div><label className="agentTaskFilter">Status<select onChange={(event) => { const next = event.target.value; setFilter(next); setSelectedId(tasks.find((task) => next === "all" || task.status === next)?.id ?? null); }} value={filter}><option value="all">All</option><option value="queued">Queued</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="failed">Failed</option></select></label>
        {visible.length === 0 && <p className="agentSectionCopy">No tasks in this view.</p>}
        {visible.map((task) => <button aria-pressed={selectedId === task.id} className="agentTaskCard" key={task.id} onClick={() => setSelectedId(task.id)} type="button"><span className="agentTaskCardTop"><strong>#{task.id} {task.title}</strong><em>{task.status.replace("_", " ")}</em></span><span>{task.project_name} Â· {task.kind === "assignment" ? "Assigned task" : "Chat request"}</span><small>{localTime(task.created_at)}</small></button>)}
      </section>
      <section className="projectForm agentTaskDetail">
        {!selected ? <p className="agentSectionCopy">Select a task to see its runs.</p> : <>
          <div className="agentSectionTitle"><strong>Task #{selected.id}</strong><span>{selected.status.replace("_", " ")}</span></div>
          <h2>{selected.title}</h2>
          <p className="agentSectionCopy">Project: <Link href={`/projects/${selected.project_id}/collab`}>{selected.project_name}</Link></p>
          <p className="agentSectionCopy">Assigned {localTime(selected.created_at)} Â· Latest run {localTime(selected.started_at)}</p>
          <div className="agentTaskBlock"><strong>Request</strong><p>{selected.prompt}</p></div>
          <div className="agentTaskBlock"><strong>Run progress</strong><ol>{selected.events.map((event, index) => <li key={`${event.created_at}-${index}`}><strong>{event.stage.replace("_", " ")}</strong><span>{event.detail} Â· {localTime(event.created_at)}</span></li>)}</ol></div>
          <div className="agentTaskBlock"><strong>Run history</strong>{selected.runs.map((run) => <article className="agentTaskRun" key={run.id}><strong>Run #{run.id} Â· {run.process_status.replace("_", " ")}</strong><small>{localTime(run.started_at || run.created_at)} Â· {run.finished_at ? `Finished ${localTime(run.finished_at)}` : "Pending"}</small><MarkdownContent content={run.output_summary || "Waiting for the coworker response."} /><Link className="ghostButton" href={`/agents/${agentId}/tasks/${selected.id}/logs?run=${run.id}`}>View execution logs</Link></article>)}</div>
          <div className="agentTaskBlock"><strong>Generated files</strong>{selected.artifacts.length ? selected.artifacts.map((artifact) => <p key={artifact.path}>{artifact.name} Â· {artifact.path}</p>) : <p>No files generated for this task yet. Its response is saved in project chat.</p>}</div>
        </>}
      </section>
    </div>}
  </section>;
}
