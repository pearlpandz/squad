// Browser worker for agent-job requests and status polling.
let chatTimer = null;
let chatFetching = false;

async function readJson(response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return body;
}

async function followJob(baseUrl, agentId, job) {
  self.postMessage({ type: "job", job });
  while (job.status === "queued" || job.status === "running") {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    job = await readJson(await fetch(`${baseUrl}/agents/${agentId}/jobs/${job.id}`, { credentials: "include" }));
    self.postMessage({ type: "job", job });
  }
}

self.onmessage = async (event) => {
  const message = event.data;
  if (message.type === "startJob" || message.type === "resumeJob") {
    try {
      const job = message.type === "startJob"
        ? await readJson(await fetch(`${message.baseUrl}/agents/${message.agentId}/${message.kind === "self_train" ? "self-train" : "try"}`, {
            method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(message.request || {}),
          }))
        : message.job;
      await followJob(message.baseUrl, message.agentId, job);
    } catch (error) {
      self.postMessage({ type: "jobError", message: error instanceof Error ? error.message : "Agent job failed" });
    }
  }
  if (message.type === "pollChat") {
    if (chatTimer) clearInterval(chatTimer);
    const refresh = async () => {
      if (chatFetching) return;
      chatFetching = true;
      try {
        const chat = await readJson(await fetch(message.url, { credentials: "include" }));
        self.postMessage({ type: "chat", chat });
      } catch (error) {
        self.postMessage({ type: "chatError", message: error instanceof Error ? error.message : "Chat refresh failed" });
      } finally { chatFetching = false; }
    };
    chatTimer = setInterval(refresh, 3000);
  }
  if (message.type === "stopChat" && chatTimer) {
    clearInterval(chatTimer);
    chatTimer = null;
  }
};
