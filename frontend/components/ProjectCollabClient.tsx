"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Brain, EllipsisVertical, Hash, Paperclip, Pencil, Plus, Send, Slash, Trash2, TriangleAlert, UserRound, X } from "lucide-react";

import { API_BASE_URL, ChatMessage, ProjectChat, ProjectDetail, apiRequest } from "@/lib/api";
import { useAdminSession } from "@/components/AdminSession";
import { useNotificationSound } from "@/lib/useNotificationSound";
import { ChatMentionText } from "@/components/ChatMentionText";
import { MarkdownContent } from "@/components/MarkdownContent";

type OutgoingMessage = ChatMessage & { deliveryStatus: "sending" | "sent" | "failed" };
type ComposerSuggestion = { name: string; username: string; value: string; kind: "human" | "agent" | "command" | "channel" };

export function ProjectCollabClient({ projectId }: { projectId: string }) {
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const { session } = useAdminSession();
  const currentHumanId = session.human_id;
  const [chat, setChat] = useState<ProjectChat | null>(null);
  const [draft, setDraft] = useState("");
  const [composerCursor, setComposerCursor] = useState(0);
  const [suggestionSelection, setSuggestionSelection] = useState({ context: "", index: 0, dismissed: false });
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [editingMessage, setEditingMessage] = useState<{ id: number; content: string } | null>(null);
  const [deletingMessage, setDeletingMessage] = useState<number | null>(null);
  const [savingMessage, setSavingMessage] = useState<number | null>(null);
  const [outgoingMessages, setOutgoingMessages] = useState<OutgoingMessage[]>([]);
  const sendingRef = useRef(false);
  const messagesRef = useRef<HTMLElement>(null);
  const localMessageId = useRef(0);
  const playNotification = useNotificationSound();
  const seenReplies = useRef<{ threadId: number; ids: Set<number> } | null>(null);
  const chatLoaded = useRef(false);
  const displayedMessages = [
    ...(chat?.messages ?? []).filter((message) => !message.metadata.deleted_at && !(message.metadata.source === "project-agent" && message.metadata.status === "working")),
    ...outgoingMessages.filter((outgoing) => outgoing.deliveryStatus !== "failed" && !chat?.messages.some((message) =>
      message.id === outgoing.id || message.metadata.client_message_id === outgoing.metadata.client_message_id)),
  ];
  const lastMessageId = displayedMessages.at(-1)?.id;
  const typingCoworkers = (chat?.active_coworkers ?? []).filter((coworker) => coworker.status === "running");
  const typingNames = typingCoworkers.map((coworker) => coworker.name).join(", ");
  const waitingNames = (chat?.active_coworkers ?? []).filter((coworker) => coworker.status === "queued").map((coworker) => coworker.name).join(", ");
  const composerSuggestions = getComposerSuggestions(draft.slice(0, composerCursor), [
    ...(project?.human_members ?? []).filter((member) => member.id !== currentHumanId).map((member) => ({
      name: member.display_name, username: member.username,
      value: `@${member.display_name.replace(/\s+/g, "")}`, kind: "human" as const,
    })),
    ...(project?.ai_members ?? []).map((member) => ({ name: member.name, username: member.username, value: member.handle, kind: "agent" as const })),
  ]);
  const suggestionContext = `${composerCursor}:${draft}`;
  const suggestionsOpen = composerSuggestions.length > 0 && !(suggestionSelection.context === suggestionContext && suggestionSelection.dismissed);
  const activeSuggestion = suggestionSelection.context === suggestionContext ? Math.min(suggestionSelection.index, composerSuggestions.length - 1) : 0;

  useEffect(() => {
    const container = messagesRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  }, [lastMessageId, displayedMessages.length, typingNames, waitingNames]);

  useEffect(() => {
    if (!chat) return;
    const replies = chat.messages.filter((message) => message.sender_type === "agent" && message.metadata.status !== "working");
    const previous = seenReplies.current;
    if (!previous || previous.threadId !== chat.thread.id) {
      seenReplies.current = { threadId: chat.thread.id, ids: new Set(replies.map((message) => message.id)) };
      return;
    }
    let count = 0;
    for (const reply of replies) {
      if (!previous.ids.has(reply.id)) {
        previous.ids.add(reply.id);
        count += 1;
      }
    }
    if (count > 0) playNotification(count);
  }, [chat, playNotification]);

  useEffect(() => {
    let active = true;
    chatLoaded.current = false;
    seenReplies.current = null;
    setChat(null);
    setProject(null);
    setOutgoingMessages([]);
    setEditingMessage(null);
    setDeletingMessage(null);
    Promise.all([
      apiRequest<ProjectDetail>(`/projects/${projectId}`),
      apiRequest<ProjectChat>(`/projects/${projectId}/chat`),
    ])
      .then(([projectResponse, chatResponse]) => {
        if (!active) return;
        setProject(projectResponse);
        setChat(chatResponse);
        chatLoaded.current = true;
      })
      .catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : "Unable to load chat"); });
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    const worker = new Worker("/agent-job-worker.js");
    worker.onmessage = (event: MessageEvent<{ type: string; chat?: ProjectChat }>) => {
      if (active && chatLoaded.current && event.data.type === "chat" && event.data.chat) {
        setChat(event.data.chat);
      }
    };
    worker.postMessage({ type: "pollChat", url: `${API_BASE_URL}/projects/${projectId}/chat` });
    return () => { active = false; worker.postMessage({ type: "stopChat" }); worker.terminate(); };
  }, [projectId]);

  async function sendMessage() {
    const textContent = draft.trim();
    const attachmentSummary = attachments.map((file) => file.name).join(", ");
    const content = textContent || (attachmentSummary ? `Attached files: ${attachmentSummary}` : "");
    if (!content || sendingRef.current || !chat || !project) {
      return;
    }
    if (attachments.length > 0 && project?.ai_members.some((member) => content.includes(member.handle))) {
      setError("Chat attachments are not available to coworkers. Upload the file to the coworker or its agent template, then select Start Self Train.");
      return;
    }

    sendingRef.current = true;
    setSending(true);
    setError(null);
    let sender: ProjectDetail["human_members"][number];
    try {
      // Membership can change on Update Members while this chat remains open.
      const latestProject = await apiRequest<ProjectDetail>(`/projects/${projectId}`);
      const activeSender = latestProject.human_members.find((member) => member.id === currentHumanId && member.status !== "removed");
      if (!activeSender) throw new Error("Join this project as a human member before sending a message.");
      sender = activeSender;
      setProject(latestProject);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to verify project membership");
      sendingRef.current = false;
      setSending(false);
      return;
    }

    const originalDraft = draft;
    const sentAttachments = attachments;
    const clientMessageId = crypto.randomUUID();
    const metadata = {
      source: "collab-ui",
      client_message_id: clientMessageId,
      attachments: sentAttachments.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type || "application/octet-stream",
      })),
      tokens: parseComposerTokens(content),
    };
    const optimisticMessage: OutgoingMessage = {
      id: --localMessageId.current,
      thread_id: chat.thread.id,
      sender_type: "human",
      sender_human_id: sender.id,
      sender_agent_id: null,
      sender_name: sender.display_name,
      sender_role: sender.role,
      sender_handle: null,
      content,
      metadata,
      created_at: new Date().toISOString(),
      deliveryStatus: "sending",
    };
    setOutgoingMessages((current) => [...current, optimisticMessage]);
    setDraft("");
    setAttachments([]);
    try {
      const message = await apiRequest<ChatMessage>(`/projects/${projectId}/chat/messages`, {
        method: "POST",
        body: JSON.stringify({
          content,
          sender_human_id: optimisticMessage.sender_human_id,
          metadata,
        }),
      });
      setOutgoingMessages((current) => current.map((entry) => entry.metadata.client_message_id === clientMessageId
        ? { ...message, deliveryStatus: "sent" } : entry));
      setChat((current) => current && !current.messages.some((entry) => entry.id === message.id)
        ? { ...current, messages: [...current.messages, message] } : current);
      void apiRequest<ProjectChat>(`/projects/${projectId}/chat`).then(setChat).catch(() => {});
    } catch (caught) {
      // A lost response does not prove the write failed. Reconcile by request ID
      // before restoring the draft, so a saved message is not offered for resend.
      try {
        const refreshed = await apiRequest<ProjectChat>(`/projects/${projectId}/chat`);
        setChat(refreshed);
        if (refreshed.messages.some((entry) => entry.metadata.client_message_id === clientMessageId)) {
          setOutgoingMessages((current) => current.filter((entry) => entry.metadata.client_message_id !== clientMessageId));
          return;
        }
      } catch {
        // Keep the original send error when the recovery read also fails.
      }
      setOutgoingMessages((current) => current.filter((entry) => entry.metadata.client_message_id !== clientMessageId));
      setDraft((current) => current || originalDraft);
      setAttachments((current) => current.length > 0 ? current : sentAttachments);
      setError(caught instanceof Error ? caught.message : "Unable to send message");
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  function renderMessageActions(message: ChatMessage) {
    const canEdit = message.sender_type === "human" && message.sender_human_id === currentHumanId;
    if (message.id <= 0 || message.metadata.deleted_at || (!canEdit && !chat?.cleanup_mode)) return null;
    return (
      <details className="chatMessageMenu" onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false;
      }}>
        <summary aria-label={`Actions for ${message.sender_name}'s message`}><EllipsisVertical size={16} aria-hidden="true" /></summary>
        <div className="chatMessageMenuItems">
          {canEdit && <button type="button" onClick={(event) => {
            event.currentTarget.closest("details")?.removeAttribute("open");
            setDeletingMessage(null); setEditingMessage({ id: message.id, content: message.content });
          }}><Pencil size={14} aria-hidden="true" /> Edit</button>}
          <button className="dangerAction" type="button" onClick={(event) => {
            event.currentTarget.closest("details")?.removeAttribute("open");
            setEditingMessage(null); setDeletingMessage(message.id);
          }}><Trash2 size={14} aria-hidden="true" /> Delete</button>
        </div>
      </details>
    );
  }

  function renderDeleteConfirmation(messageId: number) {
    if (deletingMessage !== messageId) return null;
    return (
      <div className="chatDeleteConfirmation" role="group" aria-label="Confirm message deletion">
        <span>Permanently delete this message?</span>
        <button className="ghostButton" disabled={savingMessage !== null} onClick={() => setDeletingMessage(null)} type="button">Cancel</button>
        <button className="ghostButton dangerAction" disabled={savingMessage !== null} onClick={() => void changeMessage(messageId)} type="button">{savingMessage === messageId ? "Deleting…" : "Delete"}</button>
      </div>
    );
  }

  async function changeMessage(messageId: number, content?: string) {
    if (currentHumanId === null || savingMessage !== null) return;
    setSavingMessage(messageId);
    setError(null);
    try {
      const updated = await apiRequest<ChatMessage | { deleted_message_id: number }>(`/projects/${projectId}/chat/messages/${messageId}`, {
        method: content === undefined ? "DELETE" : "PATCH",
        body: JSON.stringify({ sender_human_id: currentHumanId, ...(content === undefined ? {} : { content }) }),
      });
      setChat((current) => current && { ...current, messages: "deleted_message_id" in updated
        ? current.messages.filter((message) => message.id !== updated.deleted_message_id)
        : current.messages.map((message) => message.id === updated.id ? updated : message) });
      setOutgoingMessages((current) => current.filter((message) => message.id !== messageId));
      setEditingMessage(null);
      setDeletingMessage(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to update message");
    } finally {
      setSavingMessage(null);
    }
  }

  function insertComposerToken(value: string) {
    const input = composerRef.current;
    const start = input?.selectionStart ?? draft.length;
    const end = input?.selectionEnd ?? start;
    const prefix = draft.slice(0, start);
    const trailingMatch = prefix.match(/(\S+)$/);
    const replaceStart = trailingMatch?.[0]?.startsWith(value[0]) ? start - trailingMatch[0].length : start;
    const before = draft.slice(0, replaceStart);
    const spacer = before && !/\s$/.test(before) ? " " : "";
    const inserted = `${before}${spacer}${value}${value.length === 1 ? "" : " "}`;
    setSuggestionSelection({ context: "", index: 0, dismissed: false });
    setDraft(inserted + draft.slice(end));
    setComposerCursor(inserted.length);
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(inserted.length, inserted.length);
    });
  }

  function removeAttachment(index: number) {
    setAttachments((current) => current.filter((_, currentIndex) => currentIndex !== index));
  }

  if (error && (!project || !chat)) {
    return <section className="projectPage"><div className="formError">{error}</div></section>;
  }

  if (!project || !chat) {
    return <LoadingSkeleton fullPage variant="chat" label="Loading chat" count={4} />;
  }

  return (
    <section className="chatPage">
      <main className="chatWorkspace">
        {error && <div className="formError" role="alert">{error}</div>}
        <div className="chatThreadHeader">
          <h1>{project.name}</h1>
          <Link className="teamProjectOwner" href={`/teams/${project.team_id}`}>{project.team_name}</Link>
        </div>

        <section className="chatMessages" ref={messagesRef}>
          {displayedMessages.map((message) => (
            message.sender_type === "agent" || message.sender_type === "system" ? (
              <article className={`agentMessage${message.metadata.status === "failed" ? " failedMessage" : ""}`} key={message.id}>
                <div className="agentAvatarWrap">
                  <div className="agentAvatar">
                    <Brain size={24} />
                  </div>
                  <span />
                </div>

                <div className="agentContent">
                  <div className="agentTitleRow">
                    <div className="agentTitle">
                      <strong>{message.sender_name}</strong>
                      <span className="agentBadge">{message.sender_type === "system" ? "ROUTER" : "AI AGENT"}</span>
                      {message.metadata.status === "failed" && <span className="chatFailureBadge"><TriangleAlert size={14} aria-hidden="true" /> Task failed</span>}
                      <span className="modelBadge">{message.sender_handle ?? "built in"}</span>
                    </div>
                    <time>{localChatTime(message.created_at)}</time>
                    {renderMessageActions(message)}
                  </div>
                  {renderDeleteConfirmation(message.id)}

                  <section className="analysisCard"><MarkdownContent className="projectAgentReply" content={message.content} project={project} /></section>
                  {message.metadata.status === "failed" && message.sender_agent_id !== null && typeof message.metadata.task_id === "number" && (
                    <Link className="chatExecutionLink" href={`/agents/${message.sender_agent_id}/tasks/${message.metadata.task_id}/logs${typeof message.metadata.run_id === "number" ? `?run=${message.metadata.run_id}` : ""}`}>View execution logs</Link>
                  )}
                </div>
              </article>
            ) : (
              <article className={`humanMessage ${message.sender_human_id === currentHumanId ? "ownMessage" : "otherMessage"}`} key={message.id}>
                <div className="chatAvatar"><UserRound size={18} /></div>
                <div className="messageBody">
                  <div className="messageMeta">
                    <strong>{message.sender_human_id === currentHumanId ? "You" : message.sender_name}</strong>
                    <span>{message.sender_role ?? "human"}</span>
                    <time>{localChatTime(message.created_at)}</time>
                    {!!message.metadata.edited_at && !message.metadata.deleted_at && <span className="chatMessageEdited">Edited</span>}
                    {renderMessageActions(message)}
                  </div>
                  {editingMessage?.id === message.id ? (
                    <form className="chatMessageEditor" onSubmit={(event) => { event.preventDefault(); void changeMessage(message.id, editingMessage.content); }}>
                      <textarea aria-label="Edit your message" autoFocus maxLength={8000} rows={3} value={editingMessage.content}
                        onChange={(event) => setEditingMessage({ id: message.id, content: event.target.value })}
                        onKeyDown={(event) => { if (event.key === "Escape" && savingMessage === null) setEditingMessage(null); }} />
                      <div><button className="ghostButton" disabled={savingMessage !== null} onClick={() => setEditingMessage(null)} type="button">Cancel</button>
                        <button className="projectButton" disabled={savingMessage !== null || !editingMessage.content.trim()} type="submit">{savingMessage === message.id ? "Saving…" : "Save"}</button></div>
                    </form>
                    ) : <p><ChatMentionText content={message.content} project={project} /></p>}
                  {renderDeleteConfirmation(message.id)}
                  {"deliveryStatus" in message && message.deliveryStatus !== "sent" && (
                    <span className="agentWorkStatus" role="status">
                      {message.deliveryStatus === "failed" ? "Send failed — check before resending" : "Sending..."}
                    </span>
                  )}
                </div>
              </article>
            )
          ))}
          {typingNames && (
            <div className="chatTypingIndicator" role="status" aria-live="polite" aria-atomic="true">
              <span className="chatTypingDots" aria-hidden="true"><i /><i /><i /></span>
              <span>{typingNames} {typingCoworkers.length === 1 ? "is" : "are"} typing…</span>
            </div>
          )}
          {waitingNames && <div className="chatTypingIndicator" role="status">{waitingNames} — waiting for a turn</div>}
          {displayedMessages.length === 0 && (
            <div className="projectEmpty">
              No messages yet. Start the project conversation below.
            </div>
          )}
        </section>

        <footer className="chatComposerWrap">
          <div className="composer">
            <ComposerInterpreter
              suggestions={suggestionsOpen ? composerSuggestions : []}
              activeIndex={activeSuggestion}
              onHighlight={(index) => setSuggestionSelection({ context: suggestionContext, index, dismissed: false })}
              onInsert={insertComposerToken}
            />
            <textarea
              className="chatInput"
              ref={composerRef}
              rows={3}
              aria-label="Message the project team"
              aria-autocomplete="list"
              aria-expanded={suggestionsOpen}
              aria-controls={suggestionsOpen ? "composer-suggestions" : undefined}
              aria-activedescendant={suggestionsOpen ? `composer-suggestion-${activeSuggestion}` : undefined}
              onBlur={() => setSuggestionSelection({ context: suggestionContext, index: activeSuggestion, dismissed: true })}
              onChange={(event) => { setDraft(event.target.value); setComposerCursor(event.target.selectionStart); }}
              onSelect={(event) => setComposerCursor(event.currentTarget.selectionStart)}
              onKeyDown={(event) => {
                if (event.nativeEvent.isComposing) return;
                if (suggestionsOpen && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
                  event.preventDefault();
                  const direction = event.key === "ArrowDown" ? 1 : -1;
                  setSuggestionSelection({ context: suggestionContext, index: (activeSuggestion + direction + composerSuggestions.length) % composerSuggestions.length, dismissed: false });
                  return;
                }
                if (suggestionsOpen && event.key === "Escape") {
                  event.preventDefault();
                  setSuggestionSelection({ context: suggestionContext, index: activeSuggestion, dismissed: true });
                  return;
                }
                if (suggestionsOpen && event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  insertComposerToken(composerSuggestions[activeSuggestion].value);
                  return;
                }
                if (event.key === "Tab" && !event.shiftKey && !event.ctrlKey && !event.altKey && !event.metaKey
                    && event.currentTarget.selectionStart === event.currentTarget.selectionEnd && suggestionsOpen) {
                  event.preventDefault();
                  insertComposerToken(composerSuggestions[activeSuggestion].value);
                  return;
                }
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage();
                }
              }}
              placeholder="Message the project team or @mention an AI co-worker... (Type / for commands)"
              value={draft}
            />
            {attachments.length > 0 && (
              <div className="attachmentTray">
                {attachments.map((file, index) => (
                  <span key={`${file.name}-${file.size}`}>
                    <Paperclip size={14} />
                    {file.name}
                    <button aria-label={`Remove ${file.name}`} onClick={() => removeAttachment(index)} type="button">
                      <X size={13} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="composerActions">
              <div className="composerTools">
                <ComposerAttachmentMenu onFiles={(files) => setAttachments((current) => [...current, ...files])} />
              </div>
              <button disabled={sending || (!draft.trim() && attachments.length === 0)} onClick={() => void sendMessage()} type="button">
                {sending ? "Sending" : "Send"}
                <Send size={21} />
              </button>
            </div>
          </div>
          <div className="composerHint">
            <span>Use <strong>@agent</strong> for a direct request or <strong>/discuss @agent1 @agent2</strong> for a team discussion.</span>
            <span>↑ ↓ to select • Tab / Return to autocomplete • Return to send • Shift + Return for new line</span>
          </div>
        </footer>
      </main>
    </section>
  );
}

function ComposerAttachmentMenu({ onFiles }: { onFiles: (files: File[]) => void }) {
  const menuRef = useRef<HTMLDetailsElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function closeOutside(event: PointerEvent) {
      if (event.target instanceof Node && !menuRef.current?.contains(event.target) && menuRef.current) {
        menuRef.current.open = false;
      }
    }
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);

  return (
    <div className="composerAttachmentControl">
      <details className="composerAttachmentMenu" ref={menuRef}
        onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false; }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            event.preventDefault();
            event.currentTarget.open = false;
            event.currentTarget.querySelector("summary")?.focus();
          }
        }}>
        <summary aria-label="Add to message" aria-controls="composer-attachment-options"><Plus size={20} aria-hidden="true" /></summary>
        <div className="composerAttachmentOptions" id="composer-attachment-options" role="group" aria-label="Add to message">
          <button type="button" onClick={() => {
            if (menuRef.current) menuRef.current.open = false;
            menuRef.current?.querySelector("summary")?.focus();
            fileRef.current?.click();
          }}>
            <Paperclip size={20} aria-hidden="true" />
            <span><strong>Add photos &amp; files</strong><small>Choose from your computer</small></span>
          </button>
        </div>
      </details>
      <input hidden ref={fileRef} aria-label="Add photos and files" multiple type="file" onChange={(event) => {
        onFiles(Array.from(event.target.files ?? []));
        event.target.value = "";
      }} />
    </div>
  );
}

function ComposerInterpreter({
  suggestions,
  activeIndex,
  onHighlight,
  onInsert,
}: {
  suggestions: ComposerSuggestion[];
  activeIndex: number;
  onHighlight: (index: number) => void;
  onInsert: (value: string) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, suggestions.length]);
  if (suggestions.length === 0) return null;

  return (
    <div className="composerInterpreter" id="composer-suggestions" role="listbox" aria-label="Message suggestions" ref={listRef}>
      {suggestions.map((suggestion, index) => (
        <button key={suggestion.value} id={`composer-suggestion-${index}`} role="option" aria-selected={index === activeIndex}
          tabIndex={-1} onMouseDown={(event) => event.preventDefault()} onMouseEnter={() => onHighlight(index)}
          onClick={() => onInsert(suggestion.value)} type="button">
          <span className="composerSuggestionAvatar" aria-hidden="true">
            {suggestion.kind === "human" ? <UserRound /> : suggestion.kind === "agent" ? <Brain /> : suggestion.kind === "command" ? <Slash /> : <Hash />}
          </span>
          <span className="composerSuggestionName">{suggestion.name}</span>
          <span className="composerSuggestionUsername">{suggestion.username}</span>
        </button>
      ))}
    </div>
  );
}

function getComposerSuggestions(prefix: string, members: ComposerSuggestion[]): ComposerSuggestion[] {
  const token = prefix.match(/(?:^|\s)([@/#][^\s]*)$/)?.[1]?.toLowerCase();
  if (!token) return [];
  const options = token.startsWith("@") ? members : (
    token.startsWith("/") ? ["/assign", "/discuss", "/decision", "/status", "/ask-human"]
      : ["#requirements", "#architecture", "#testing", "#release"]
  ).map((value): ComposerSuggestion => ({ name: value.slice(1).replace(/-/g, " "), username: value, value, kind: token.startsWith("/") ? "command" : "channel" }));
  const query = token.slice(1);
  return options.filter((option) => option.value.toLowerCase().startsWith(token) || option.username.toLowerCase().startsWith(query) || option.name.toLowerCase().includes(query));
}

function localChatTime(value: string) {
  // SQLite timestamps are UTC but omit the offset. ISO client timestamps retain theirs.
  const normalized = value.trim().replace(" ", "T");
  const timestamp = /(?:z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`;
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString("en-US", {
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}

function parseComposerTokens(content: string) {
  return {
    mentions: content.match(/@\S+/g) ?? [],
    commands: content.match(/\/\S+/g) ?? [],
    channels: content.match(/#\S+/g) ?? [],
  };
}
