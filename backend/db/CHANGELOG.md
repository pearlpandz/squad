# Database Changelog

## 2.11.0 - Workspace Sign-in

- Add expiring, revocable user sessions linked to human identities. Retire existing admin sessions. Oracle email and role entry is self-declared; only admin@squad-oracle.com with role admin receives template access.

## 2.10.0 - Administrator Access

- Store hashed opaque admin session tokens with expiry and credential-version checks. Persist per-client login attempt limits across backend workers. Existing teams, coworkers, templates, and projects are unchanged.

## 2.9.1 - Remove Sample Human Users

- Remove the seeded Sarah Chen and Muthu users. Transfer Muthu's memberships, attribution, and saved requester IDs to the existing Muthupandi Velmurugan identity; clear Sarah's attribution while retaining project, task, and chat history.
- Project creation, editing, and removal resolve Muthupandi Velmurugan's active user ID instead of using a fixed sample ID. Historical migrations remain unchanged; the new migration also removes the sample users on fresh initialization.

## 2.9.0 - Teams and Project Memory

- Add teams and reusable human/coworker rosters; each project belongs to one team. Preserve existing project/member IDs under Default Team.
- Enforce roster membership for project assignments, workspace ownership, and safe project moves. A coworker can participate in multiple projects with the same identity.
- Persist coworker project-memory snapshots independently by agent and project. Collaboration uses current-project context; team memory views show only projects in that team.

## 2.8.0 - Requirement Workflow Tasks

- Persist the current requirement task per discussion. Follow-ups, retries, explicit assignments, and coworker handoffs create execution runs under that task. A different BRD link or an explicitly changed BRD starts a new task; historical runs and artifacts stay in place.

## 2.7.0 - Persistent Session Context

- Store separate Try sessions and their complete messages for each coworker.
- Persist versioned, model-specific context summaries scoped by session, project, and coworker; retain all original messages.

## 2.6.0 - Background Agent Jobs

- Persist Try and Self Train job state and results; backend worker threads execute them outside the request.
- Interrupted jobs are marked failed on backend restart. Project task runs continue using their existing task and run history.

## 2.5.0 - Template Read Permissions

- Give the seeded Business Analyst template the standard coworker read capabilities when they have not been customized.

## 2.4.0 - Business Analyst Template Backfill

- Seed the Business Analyst template identity in the agent pool.
- Copy Silvy's approved, trained knowledge source files into template-owned storage and publish the shared graph. Keep her project memberships, tasks, chats, and individual experience with Silvy.
- Mark Silvy's existing source records as inherited from the template. Future template upgrades remain explicit.

## 2.3.0 - Portable Coworker Lessons

- Added per-coworker reusable lessons with optional source-project provenance. Self Train adds approved lessons to that coworker's graph and removes retired lessons.

## 2.2.0 - Published Agent Templates

- Added versioned template snapshots and references from independent coworkers to their originating template version.
- Each copy has separate sources, graph rows, tasks, and memory. Explicit upgrades replace inherited defaults while keeping individual work.
- Added a local workspace ownership foundation; customer separation remains per installation.

## 1.9.0 - Per-agent semantic retrieval

- Added local embeddings to graph chunks so Try can rank knowledge by meaning within the selected coworker's graph.
- Existing chunks receive embeddings on the next Self Train; unchanged embedded chunks are skipped.
- Updated the document chunk size for the local embedding model.
- Normalize merged words from PDF extraction before embedding; keep original passage text for answers.

## 1.8.0 - Document Parsing and Graph Chunks

- Restricted agent uploads to text, Markdown, PDF, legacy and modern Word, and legacy and modern PowerPoint files.
- Added parsed document chunks with page or slide provenance for agent graph retrieval.
- Updated application database version to `1.8.0`.

## 1.7.0 - Agent Owned Knowledge Graphs

- Added one persistent graph per AI coworker, with source nodes, concept nodes, and source-to-concept edges.
- Recorded source checksums and change history so Self Train updates only changed files, completed tasks, and project chat.
- Updated application database version to `1.7.0`.

## 1.6.0 - Remove Seeded Silvy

- Removed the original Silvy coworker fixture and its agent-owned source records on upgrade, without touching a later coworker created with the same name.
- Removed Silvy from the standalone seed data. Human-authored project chat is retained.
- Updated application database version to `1.6.0`.

## 1.5.0 - Independent AI Coworkers and Sources

- Added an internal agent pool so a coworker can be created before joining any project; project membership remains in `project_agents`.
- Added agent-owned source and index tables. Existing source records are copied without deleting project source rows or previous index data.
- Updated application database version to `1.5.0`.

## 1.4.0 - Silvy Source Paths

- Moved the two seeded Silvy Markdown paths into `knowledge/agents/silvy/` without deleting source records or indexed data.
- The existing source table still retains its project association; agent-only ownership requires a separate data-preserving schema migration.
- Updated application database version to `1.4.0`.

## 1.3.0 - Agent Knowledge Refresh

- Added per-agent, per-project knowledge nodes and indexed terms with source provenance.
- Agent onboarding can add approved documents and refresh knowledge from completed tasks, latest Codex run summaries, and project chat across active project assignments.
- Updated application database version to `1.3.0`.

## 1.2.0 - Reusable Members

- Added `humans.username` for human member onboarding.
- Added `agents.username` and `agents.agent_description` for reusable AI coworker identity.
- Added `project_agents` so one AI agent can participate in multiple projects.
- Backfilled existing agents into `project_agents`.
- Updated application database version to `1.2.0`.

## 1.1.0 - Projects Feature

- Added project metadata columns: `business_domain`, `repository_url`, `delivery_stage`, `priority`, `tech_stack_json`, `metadata_json`, `updated_by_human_id`, and `removed_at`.
- Added `project_members` to map human members to projects with role, status, and audit timestamps.
- Seeded project metadata and human memberships for the initial projects.
- Updated application database version to `1.1.0`.

## 1.0.0 - Zero Day

- Added SQLite schema for projects, humans, onboarded AI agents, agent roles, knowledge sources, model catalog, routing rules, conversation threads, messages, tasks, and Codex subprocess runs.
- Knowledge source files are not stored in the database. Only `knowledge_sources.relative_path` stores the file location relative to the project knowledge root.
- Added seed data for the first human users, Project Atlas, Silvy, Arun, QA-Sentinel, knowledge source placeholders, model catalog, routing rules, one thread, sample messages, one task, and one Codex run.
- Added `schema_migrations` table to record applied migration versions.

## Upgrade Rule

Every version upgrade must add a new folder under `backend/db/migrations/<version>/` with an ordered SQL script and a matching changelog entry here.
## 2.1.0 - Coworker Task Progress

- Record task assignment and operational progress events for coworker task views.
- Existing assigned tasks receive an initial assignment event.

## 2.0.0 - Coworker Read Tools

- Granted existing AI coworkers read access to public web search, Confluence, and Oracle connectors. Per-coworker permissions remain editable and can be revoked.
- New AI coworkers receive the same read permissions by default.
