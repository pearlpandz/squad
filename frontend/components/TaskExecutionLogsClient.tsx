"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MarkdownContent } from "@/components/MarkdownContent";
import { ArrowLeft, Download } from "lucide-react";
import { API_BASE_URL, AgentTask, apiRequest } from "@/lib/api";

type TaskTrace = { directory: string; recovery: string; has_cli_logs: boolean; files: Array<{ name: string; path: string | null; content: string; truncated: boolean }> };

function readableLog(content: string): string {
  return content.split("\n").map((line) => {
    try {
      const event = JSON.parse(line);
      if (event.stage) return `[${event.time}] ${event.stage.toUpperCase()}\n${event.detail}`;
      const item = event.item;
      if (item?.type === "command_execution") return `${event.type}: COMMAND ${item.status ?? ""}\n${item.command}\nExit code: ${item.exit_code ?? "pending"}\n${item.aggregated_output ?? ""}`;
      if (item?.type === "agent_message") return `${event.type}: AGENT UPDATE\n${item.text}`;
      return JSON.stringify(event, null, 2);
    } catch { return line; }
  }).join("\n");
}

export function TaskExecutionLogsClient({ agentId, taskId, requestedRun }: { agentId: string; taskId: string; requestedRun?: string }) {
  const [task, setTask] = useState<AgentTask | null>(null);
  const [runId, setRunId] = useState(requestedRun ?? "");
  const [trace, setTrace] = useState<TaskTrace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadVersion = useRef(0);
  useEffect(() => { setRunId(requestedRun ?? ""); setTrace(null); }, [requestedRun]);
  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    const result = await apiRequest<AgentTask>(`/agents/${agentId}/tasks/${taskId}`);
    if (version !== loadVersion.current) return;
    setTask(result);
    const selected = runId || String(result.runs[0]?.id ?? "");
    if (!selected || !result.runs.some((run) => String(run.id) === selected)) throw new Error("Run not found for this task.");
    if (!runId) setRunId(selected);
    const logs = await apiRequest<TaskTrace>(`/agents/${agentId}/tasks/${taskId}/runs/${selected}/trace`);
    if (version !== loadVersion.current) return;
    setTrace(logs);
    setError(null);
  }, [agentId, taskId, runId]);
  const refresh = useCallback(() => { void load().catch((caught) => setError(caught instanceof Error ? caught.message : "Unable to load execution logs")); }, [load]);
  useEffect(() => { refresh(); return () => { loadVersion.current += 1; }; }, [refresh]);
  const run = task?.runs.find((item) => String(item.id) === runId);
  const active = run?.process_status === "running" || run?.process_status === "queued";
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(refresh, 5000);
    return () => window.clearInterval(timer);
  }, [active, refresh]);
  return <section className="projectPage">
    <div className="projectPageHeader"><div><h1>Execution logs</h1><span>Inspect execution progress and saved output for task #{taskId}.</span></div>
      <div className="projectHeaderActions"><Link className="ghostButton" href={`/agents/${agentId}/tasks`}><ArrowLeft size={16} /> Tasks</Link>{task && <Link className="ghostButton" href={`/projects/${task.project_id}/collab`}>Back to chat</Link>}</div>
    </div>
    {error && <p className="formError" role="alert">{error}</p>}
    {task && <section className="projectForm agentRunTrace">
      <label className="agentTaskFilter">Execution run<select value={runId} onChange={(event) => { setTrace(null); setRunId(event.target.value); }}>{task.runs.map((item) => <option key={item.id} value={item.id}>Run #{item.id} · {item.process_status}</option>)}</select></label>
      {run?.output_summary && <MarkdownContent className={run.process_status === "failed" ? "formError" : "agentSectionCopy"} content={run.output_summary} />}
      {active && <p className="agentSectionCopy">Logs refresh every five seconds while this run is active.</p>}
      {!trace && !error && <LoadingSkeleton variant="content" label="Loading execution logs" count={4} />}
      {trace && <><p className="agentTracePath">Log folder: {trace.directory}</p>
        {trace.recovery && <p className="agentSectionCopy">{trace.recovery}</p>}
        {!trace.has_cli_logs && <p className="agentSectionCopy">{active ? "Waiting for CLI output. Received input and recorded progress appear below." : "Received input and saved progress are shown below. No uniquely matching CLI log is available for this run."}</p>}
        <div className="executionConsoleHeader"><strong>Execution console</strong><span>{active ? "LIVE · Refreshes every 5 seconds" : "Recorded execution"}</span></div>
        <pre aria-label="Execution console" className="executionConsole">{trace.files.filter((file) => !file.name.endsWith(".input.log")).map((file) => `===== ${file.name} ${file.truncated ? "(last 256 KB; download for all entries)" : ""} =====\n${readableLog(file.content) || "No output."}`).join("\n\n")}</pre>
        {trace.files.map((file) => <section className="executionLogFile" key={file.name}>
          <div className="agentSectionTitle"><strong>{file.name}</strong><a className="ghostButton" href={`${API_BASE_URL}/agents/${agentId}/tasks/${taskId}/runs/${runId}/trace/download?name=${encodeURIComponent(file.name)}`}><Download size={16} /> Download full log</a></div>
          {file.path && <p className="agentTracePath">{file.path}</p>}{file.truncated && <p className="agentSectionCopy">Preview shows the last 256 KB. Download the full log for all entries.</p>}
          <details><summary>View raw log</summary><pre className="executionConsole executionConsoleRaw">{file.content || "No output yet."}</pre></details>
        </section>)}</>}
    </section>}
  </section>;
}
