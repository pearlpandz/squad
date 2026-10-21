"use client";

import { LoadingSkeleton } from "@/components/LoadingSkeleton";

import dynamic from "next/dynamic";

// Keep the Markdown parser out of edit, training, and empty chat screens until
// a reply or task summary actually needs to be rendered.
export const MarkdownContent = dynamic(
  () => import("@/components/MarkdownRenderer").then((module) => module.MarkdownContent),
  { loading: () => <LoadingSkeleton variant="content" label="Loading content" count={1} /> },
);
