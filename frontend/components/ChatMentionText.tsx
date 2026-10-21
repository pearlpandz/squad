"use client";

import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Brain, UserRound } from "lucide-react";
import { ProjectDetail } from "@/lib/api";

type MentionMember = { handle: string; name: string; kind: string; role: string; description: string; status: string };

function Mention({ text, member }: { text: string; member: MentionMember }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number; above: boolean } | null>(null);
  function show() {
    const rect = trigger.current?.getBoundingClientRect();
    if (!rect) return;
    const above = window.innerHeight - rect.bottom < 190 && rect.top > 190;
    setPosition({ top: above ? rect.top - 8 : rect.bottom + 8,
      left: Math.max(12, Math.min(rect.left, window.innerWidth - Math.min(280, window.innerWidth - 24) - 12)), above });
  }
  useEffect(() => {
    if (!position) return;
    const hide = () => setPosition(null);
    window.addEventListener("scroll", hide, true);
    window.addEventListener("resize", hide);
    return () => { window.removeEventListener("scroll", hide, true); window.removeEventListener("resize", hide); };
  }, [position]);
  return <>
    <button aria-describedby={position ? id : undefined} className="chatMention" onBlur={() => setPosition(null)}
      onClick={show} onFocus={show} onMouseEnter={show} onMouseLeave={() => setPosition(null)}
      onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); setPosition(null); } }} ref={trigger} type="button">{text}</button>
    {position && createPortal(<span className="chatMentionTooltip" id={id} role="tooltip"
      style={{ top: position.top, left: position.left, transform: position.above ? "translateY(-100%)" : undefined }}>
      <span className="chatMentionIdentity"><span className="chatMentionAvatar">{member.kind === "AI agent" ? <Brain size={19} /> : <UserRound size={19} />}</span><span><strong>{member.name}</strong><span>{member.handle}</span></span></span>
      <span className="chatMentionRole">{member.kind} · {member.role.replace(/[_-]/g, " ")}</span>
      {member.description && <span className="chatMentionDescription">{member.description}</span>}
      <span className="chatMentionStatus">{member.status.replace(/[_-]/g, " ")}</span>
    </span>, document.body)}
  </>;
}

export function ChatMentionText({ content, project }: { content: string; project: ProjectDetail }) {
  const members: MentionMember[] = [
    ...project.ai_members.map((member) => ({ handle: member.handle, name: member.name, kind: "AI agent", role: member.role, description: member.agent_description, status: member.status })),
    ...project.human_members.map((member) => ({ handle: `@${member.display_name.replace(/\s+/g, "")}`, name: member.display_name, kind: "Human", role: member.role, description: "", status: member.status })),
  ];
  const lookup = new Map(members.map((member) => [member.handle.toLowerCase(), member]));
  const handles = [...lookup.keys()].filter(Boolean).sort((a, b) => b.length - a.length)
    .map((handle) => handle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!handles.length) return <>{content}</>;
  const pattern = new RegExp(`(?<![\\w@])(${handles.join("|")})(?![\\w])`, "gi");
  return <>{content.split(pattern).map((part, index) => {
    const member = lookup.get(part.toLowerCase());
    return member ? <Mention key={index} text={part} member={member} /> : part;
  })}</>;
}
