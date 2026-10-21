export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export type ProjectSummary = {
  id: number;
  team_id: number;
  team_name: string;
  code: string;
  name: string;
  description: string | null;
  status: string;
  business_domain: string;
  delivery_stage: string;
  priority: string;
  tech_stack: string[];
  created_at: string;
  updated_at: string;
  created_by: string | null;
  updated_by: string | null;
  human_member_count: number;
  ai_member_count: number;
};

export type ProjectDetail = ProjectSummary & {
  repository_url: string;
  metadata: Record<string, unknown>;
  removed_at: string | null;
  human_members: Array<{
    id: number;
    display_name: string;
    username: string;
    email: string | null;
    role: string;
    member_role: string;
    status: string;
  }>;
  ai_members: Array<{
    id: number;
    name: string;
    username: string;
    handle: string;
    role: string;
    status: string;
    agent_description: string;
    knowledge_scope: string;
  }>;
};

export type ProjectPayload = {
  code: string;
  name: string;
  description: string;
  status: string;
  business_domain: string;
  repository_url: string;
  delivery_stage: string;
  priority: string;
  tech_stack: string[];
  metadata: Record<string, unknown>;
  human_member_ids: number[];
  created_by_human_id?: number;
  updated_by_human_id?: number;
};

export type ProjectCreatePayload = {
  team_id: number;
  name: string;
  status: string;
  delivery_stage: string;
  description: string;
  agent_member_ids: number[];
  created_by_human_id?: number;
};

export type TeamSummary = {
  id: number; name: string; description: string; created_at: string; updated_at: string;
  project_count: number; ai_member_count: number; human_member_count: number;
};

export type TeamMember = {
  id: number; name: string; username: string; handle: string; role: string; status: string; description: string;
  projects: Array<{ id: number; name: string; status: string; delivery_stage: string }>;
};

export type TeamDetail = {
  id: number; name: string; description: string; ai_members: TeamMember[]; human_members: TeamMember[];
  projects: ProjectSummary[];
};

export type MemberProjectMemory = {
  id: number; team_id: number; name: string; description: string | null; status: string;
  business_domain: string; repository_url: string; delivery_stage: string; priority: string;
  tech_stack: string[]; metadata: Record<string, unknown>; updated_at: string;
  progress: Record<string, number>; my_task_ids: number[];
  tasks: Array<{ id: number; title: string; status: string; run_status: string | null; latest_progress: string | null }>;
};

export type HumanMemberPayload = {
  name: string;
  username: string;
  email: string;
  role: string;
};

export type AiMemberPayload = {
  name: string;
  username: string;
  role: string;
  agent_description: string;
  knowledge_resources: File[];
};

export type AgentProfile = {
  id: number;
  name: string;
  username: string;
  handle: string;
  status: string;
  role: string;
  agent_description: string;
  knowledge_scope: string;
  client_id: number;
  is_template: number;
  template_agent_id: number | null;
  template_version: number | null;
  template_instructions: string;
  template_description: string;
  template_scope: string;
  published_version: number;
  role_instructions: string;
  tool_permissions: Array<"web_search" | "confluence_read" | "oracle_read">;
  knowledge_items: number;
  projects: Array<{ id: number; name: string }>;
  sources: Array<{
    id: number;
    project_id: number | null;
    project_name: string | null;
    title: string;
    source_type: string;
    relative_path: string;
    copy_path: string;
    file_available: boolean;
    approval_status: string;
    template_source_id: number | null;
    created_at: string;
  }>;
};

export type AgentTask = {
  id: number;
  project_id: number;
  project_name: string;
  title: string;
  prompt: string;
  status: string;
  kind: string;
  created_at: string;
  updated_at: string;
  run_id: number | null;
  process_status: string | null;
  started_at: string | null;
  finished_at: string | null;
  output_summary: string | null;
  events: Array<{ stage: string; detail: string; created_at: string }>;
  runs: Array<{ id: number; process_status: string; started_at: string | null; finished_at: string | null; output_summary: string | null; created_at: string }>;
  artifacts: Array<{ name: string; path: string }>;
};

export type AgentTrainingResult = {
  agent_id: number;
  project_count: number;
  knowledge_items: number;
  updated_items: number;
  status: "done" | "done_with_errors";
  outcomes: Record<"added" | "updated" | "unchanged" | "removed" | "empty" | "error", number>;
  details: Array<{
    project_id: number | null;
    project_name: string;
    source_kind: string;
    source_id: string;
    title: string;
    outcome: string;
    preview: string;
  }>;
  errors: string[];
  graph: { sources: number; concepts: number; edges: number } | null;
};

export type AgentJob = {
  id: number;
  agent_id: number;
  kind: "self_train" | "trial";
  status: "queued" | "running" | "completed" | "failed";
  request: { message?: string; session_id?: string; history?: Array<{ role: "user" | "assistant"; content: string }> };
  result: AgentTrainingResult | { answer: string; refused: boolean; sources: string[] } | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type AgentLesson = {
  id: number;
  title: string;
  content: string;
  source_project_id: number | null;
  source_project_name: string | null;
  approval_status: string;
  created_at: string;
  updated_at: string;
};

export type AgentKnowledgeIndex = {
  knowledge_items: number;
  graph_exists: boolean;
  last_trained_at: string | null;
  concept_count: number;
  edge_count: number;
  chunk_count: number;
  pending_additions: number;
  pending_removals: number;
  pending_items: Array<{
    source_key: string;
    title: string;
    source_kind: string;
    action: "added" | "updated" | "removed";
  }>;
  items: Array<{
    project_id: number | null;
    project_name: string;
    source_kind: string;
    source_id: string;
    title: string;
    updated_at: string;
  }>;
  history: Array<{
    source_key: string;
    project_name: string;
    source_kind: string;
    title: string;
    outcome: string;
    recorded_at: string;
  }>;
};

export type ChatMessage = {
  id: number;
  thread_id: number;
  sender_type: "human" | "agent" | "system";
  sender_human_id: number | null;
  sender_agent_id: number | null;
  sender_name: string;
  sender_role: string | null;
  sender_handle: string | null;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type ProjectChat = {
  cleanup_mode: boolean;
  active_coworkers: Array<{ agent_id: number; name: string; run_id: number; status: "queued" | "running" }>;
  thread: {
    id: number;
    project_id: number;
    title: string;
    status: string;
    created_at: string;
    updated_at: string;
  };
  messages: ChatMessage[];
};

const navigationPaths = new Set(["/teams", "/projects", "/agents"]);
const navigationCache = new Map<string, { data: unknown; expiresAt: number }>();
const navigationRequests = new Map<string, Promise<unknown>>();
const NAVIGATION_CACHE_MS = 15000;
let navigationGeneration = 0;
let activeMutations = 0;

export function invalidateNavigationData() {
  navigationGeneration += 1;
  navigationCache.clear();
  navigationRequests.clear();
}

export async function prefetchNavigationData(route: string) {
  const path = route === "/templates" ? "/agents/templates" : route;
  if (!navigationPaths.has(path)) return;
  try { await apiRequest(path); } catch { /* The destination displays fetch errors when opened. */ }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const mutation = !["GET", "HEAD"].includes((init?.method ?? "GET").toUpperCase());
  if (mutation) {
    activeMutations += 1;
    invalidateNavigationData();
    try { return await fetchApi<T>(path, init); }
    finally { activeMutations -= 1; invalidateNavigationData(); }
  }
  // Only browser-side directory reads share a short-lived result. Live chat,
  // jobs, permissions, details, and explicitly configured reads remain fresh.
  if (typeof window === "undefined" || init !== undefined || activeMutations > 0 || !navigationPaths.has(path)) {
    return fetchApi<T>(path, init);
  }
  const cached = navigationCache.get(path);
  if (cached && cached.expiresAt > Date.now()) return cached.data as T;
  const pending = navigationRequests.get(path);
  if (pending) return pending as Promise<T>;
  const generation = navigationGeneration;
  const request = fetchApi<T>(path).then((data) => {
    if (generation === navigationGeneration) navigationCache.set(path, { data, expiresAt: Date.now() + NAVIGATION_CACHE_MS });
    return data;
  }).finally(() => {
    if (navigationRequests.get(path) === request) navigationRequests.delete(path);
  });
  navigationRequests.set(path, request);
  return request;
}

async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    credentials: "include",
    ...init,
    headers: isFormData
      ? init?.headers
      : {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
  });

  if (!response.ok) {
    if ([401, 403].includes(response.status) && typeof window !== "undefined") window.dispatchEvent(new Event("collab-admin-expired"));
    const body = await response.text();
    let message = body || `Request failed with ${response.status}`;
    try {
      const parsed: unknown = JSON.parse(body);
      if (typeof parsed === "object" && parsed !== null && "detail" in parsed && typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      // Non-JSON responses already have a readable fallback above.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export async function projectActorHumanId(): Promise<number> {
  const session = await apiRequest<{ human_id: number | null }>("/admin/session");
  if (!session.human_id) throw new Error("Sign in before changing projects.");
  return session.human_id;
}

export function uploadRequest<T>(
  path: string,
  body: FormData,
  onProgress: (percent: number) => void,
  onUploadComplete: () => void,
): Promise<T> {
  invalidateNavigationData();
  return new Promise<T>((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.withCredentials = true;
    request.onloadend = () => invalidateNavigationData();
    request.open("POST", `${API_BASE_URL}${path}`);
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    request.upload.onload = () => {
      onProgress(100);
      onUploadComplete();
    };
    request.onload = () => {
      let response: unknown;
      try { response = JSON.parse(request.responseText); }
      catch { response = null; }
      if (request.status >= 200 && request.status < 300) {
        if (response === null) reject(new Error("Invalid upload response"));
        else resolve(response as T);
        return;
      }
      const detail = response && typeof response === "object" && "detail" in response ? response.detail : null;
      reject(new Error(typeof detail === "string" ? detail : request.responseText || `Upload failed with ${request.status}`));
    };
    request.onerror = () => reject(new Error("Upload failed. Check your connection and retry."));
    request.onabort = () => reject(new Error("Upload was cancelled."));
    request.send(body);
  });
}
