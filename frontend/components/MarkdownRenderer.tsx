"use client";

import { Children, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChatMentionText } from "@/components/ChatMentionText";
import type { ProjectDetail } from "@/lib/api";

export function MarkdownContent({ content, project, className = "" }: { content: string; project?: ProjectDetail; className?: string }) {
  function mentions(children: ReactNode) {
    return project ? Children.map(children, (child) => typeof child === "string"
      ? <ChatMentionText content={child} project={project} /> : child) : children;
  }
  const components: Components = {
    p: ({ children }) => <p>{mentions(children)}</p>,
    li: ({ children, className }) => <li className={className}>{mentions(children)}</li>,
    strong: ({ children }) => <strong>{mentions(children)}</strong>,
    em: ({ children }) => <em>{mentions(children)}</em>,
    del: ({ children }) => <del>{mentions(children)}</del>,
    h1: ({ children }) => <h1>{mentions(children)}</h1>,
    h2: ({ children }) => <h2>{mentions(children)}</h2>,
    h3: ({ children }) => <h3>{mentions(children)}</h3>,
    h4: ({ children }) => <h4>{mentions(children)}</h4>,
    h5: ({ children }) => <h5>{mentions(children)}</h5>,
    h6: ({ children }) => <h6>{mentions(children)}</h6>,
    th: ({ children, style }) => <th style={style}>{mentions(children)}</th>,
    td: ({ children, style }) => <td style={style}>{mentions(children)}</td>,
    table: ({ children }) => <div className="markdownTableScroll"><table>{children}</table></div>,
    a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    // Keep replies compact and avoid remote image requests from generated text.
    img: ({ alt }) => <span>{alt ? `[Image: ${alt}]` : "[Image]"}</span>,
  };
  return <div className={`markdownContent ${className}`.trim()}>
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components} skipHtml>{content}</ReactMarkdown>
  </div>;
}
