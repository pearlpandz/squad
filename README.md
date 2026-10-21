# SQUAD.

Autonomous multi-agent team skeleton.

Agent replies in project chat, Try Coworker, task run history, and execution summaries render Markdown in the Redwood theme, including headings, emphasis, lists, read-only checkboxes, tables, links, and code blocks. Project chat mentions retain their member tooltips. Saved Markdown artifacts, editable message source, and raw execution logs remain available in their original format.

The shared Redwood left sidebar provides Teams, Projects, AI Co-workers, and Agent Templates after sign-in, with icons and an active section indicator. Light mode uses a white page background and a softly tinted sidebar. A small chevron toggle floats across the sidebar border. The sidebar starts collapsed and remembers the expanded/collapsed preference. Theme controls live in the sidebar; desktop pages use the full viewport height. On mobile, the menu button opens a navigation drawer that closes on selection, Escape, or an outside click, keeps keyboard focus inside while open, and returns focus when closed. Page headers retain contextual actions instead of repeating global navigation links.

Teams own projects and maintain reusable human and AI coworker rosters. `/teams` lists available teams in a table with member counts, project counts, and update dates. Click a team name or Open Team to visit `/teams/<id>`; All Teams returns to the list. New Team is available on the list screen. Each team details screen has three tabs: About Team for its name, description, and member/project counts; Team Members for its roster, assignments, and coworker memory; and Projects for its projects, New Project, and Move Project. The selected tab stays in the URL so refresh preserves it. Use Edit Team in About Team to update its name (2–160 characters) and description (up to 2,000 characters), then Save Changes; Cancel discards the draft. Add existing coworkers or humans to a team, then assign each member to any number of its projects. Project creation and member pickers use the selected team's roster. A coworker can belong to more than one team while keeping one identity, trained knowledge, and individual memory. Removing a member from a team requires removing their active project assignments first.

Each coworker retains project details and recorded task progress in separate `agent_project_memory` snapshots. The Memory action shows that coworker's projects within the selected team and refreshes every ten seconds. Snapshots refresh when viewed, before collaboration, and after a task run. Full messages, runs, and artifacts remain in their existing project storage. Collaboration receives only its current project's snapshot and conversation context; other-project task passages are excluded. Recorded completion states describe execution status and do not establish artifact approval.

Schema migration `2.9.0` moves existing projects and members into Default Team without changing their IDs, files, or conversation history. New teams can take over an existing project; the Move Project form can enroll its current members in the destination team while preserving their assignments. Run the normal backend initialization/startup to apply the migration.

Migration `2.9.1` removes the original Sarah Chen and Muthu sample users. Muthu's memberships and attribution references transfer to the existing Muthupandi Velmurugan user; Sarah's attribution references are cleared. Project and chat history are retained. Project forms resolve Muthupandi Velmurugan's active user ID instead of using the sample user's fixed ID; human members are managed through the team roster.

A task covers one requirement from BRD input through artifact generation. Questions, retries, revisions, explicit assignments, and coworker handoffs remain execution runs within that task, including after an artifact is produced. A different BRD-labelled link or an explicit statement that the BRD changed starts a new task. Repeated links and supporting documents keep the existing task. Changes made externally at the same URL must be stated in chat; routing does not fetch document versions. Historical tasks and files are preserved. Participating coworkers retain access to task history and logs after a handoff.

## Stack

- Frontend: Next.js
- Backend: Python, FastAPI, LangChain
- Runtime pattern: backend orchestrates AI coworkers and can launch Codex CLI subprocesses with a selected model.

## Local Setup

### Workspace sign-in

The first screen is `/login`, with enterprise email and role fields and no password. Employees must use an exact `@oracle.com` email domain; the reserved administrator is `admin@squad-oracle.com` with role `admin`. Other roles are descriptive and do not grant administrator privileges. Shared template access remains enforced by the API.

All workspace screens, including direct URLs, require a signed-in session. Until the session is checked, only the session loading screen is rendered; unsigned users see login. Use **Logout** in the sidebar (also available when collapsed and on mobile) to revoke the session and return to `/login`. Back navigation cannot reopen workspace screens while signed out.

Email entry is self-declared and does not verify mailbox ownership. Anyone who knows the reserved admin email can enter as admin; verified enterprise authentication requires a future SSO or email verification integration.

The API creates an eight-hour HttpOnly cookie session with a hashed token in SQLite. Logout revokes it; expiry returns to login. All workspace APIs require a session. Sign-in resolves or creates a human identity by email, and project attribution and chat actions use that session identity. Existing team/project membership is still required for chat. Set `ADMIN_COOKIE_SECURE=true` for HTTPS and use the same site for frontend and API (for local use, `localhost` for both). Restart the backend to apply migration `2.11.0`; previous admin sessions are invalidated. The old password setup command is no longer required.

### Backend

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
$env:PYTHONPATH='backend'; python backend\scripts\init_db.py
uvicorn app.main:app --reload --app-dir backend
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

For normal daily use, run `npm run build` once and `npm start` to use the optimized production frontend. Development mode compiles routes on demand, so first visits can take longer.

## Implemented Features

### 1. Projects

- Backend CRUD endpoints:
  - `GET /api/projects`
  - `POST /api/projects`
  - `GET /api/projects/{project_id}`
  - `PUT /api/projects/{project_id}`
  - `DELETE /api/projects/{project_id}`
- Backend chat endpoints:
  - `GET /api/projects/{project_id}/chat`
  - `POST /api/projects/{project_id}/chat/messages`
- Coworker task endpoints:
  - `GET /api/agents/{agent_id}/tasks`
  - `GET /api/agents/{agent_id}/tasks/{task_id}`
- Frontend pages:
  - `/`
  - `/projects`
  - `/projects/new`
  - `/projects/[id]`
  - `/projects/[id]/edit`
  - `/projects/[id]/collab`
  - `/projects/[id]/members`
- Project navigation starts from `/`; `/projects` shows the same Redwood project cards. Search by project name, description, or team and filter by team. Cards show the project, team, description, and people/AI counts with Open chat as the main action. Project details, member management, and confirmed removal are in each card's options menu; status, stage, priority, domain, and stack labels are omitted from this overview.
- Collab opens a backend-synced project chat interface with a compact header, right-aligned `View Project` action, scrollable messages, a bottom-pinned composer, `/` commands, clean `@` member mentions, `#` channels, and file attachment selection. Mention one assigned AI coworker to request a scoped answer; `/assign @coworker task` records an assigned task and its Codex run. Both execute in the background, with progress and the final reply visible in chat.
- Project details include about, tech stack, human members, AI members, audit metadata, and custom metadata.
- New AI coworker replies play a notification chime in the open project chat and Try Coworker pages after a click or keypress enables browser audio. Existing chat history and repeated polls stay silent. Project chat continues polling in background tabs; browser throttling or suspension may delay notifications. Sound requires the relevant page to remain open and the tab/device to be unmuted.
- Running coworkers appear as a transient typing indicator and queued coworkers appear as waiting in project chat, using persisted execution state so it survives page refreshes and clears after completion or failure. Assignment and working acknowledgments are not posted as messages; only results and failures enter the conversation. Older acknowledgment messages are hidden in the chat UI while their stored history remains intact.
- Once a coworker owns the discussion, requests routed to that same coworker produce no Task Router bubble, including queued follow-ups and new work for the same coworker. The router announces initial assignments and handoffs to a different coworker; clarification/blocking questions remain visible when needed. Task status replies come from the coworker. Routing decisions remain in execution logs even when the chat routing note is suppressed.
- Sending a project chat message immediately shows it in the conversation, clears the composer, and scrolls to the latest message while the server processes the request. A client message identifier prevents duplicate bubbles during polling. Failed sends show a delivery warning and restore the submitted draft when the composer is empty.
- Project chat displays the current sender's messages on the right in green Redwood bubbles, with other humans, coworkers, and the Task Router on the left in bordered cards matching the agent styling. The current sender follows the composer identity (the project's first human member).
- Typing `@`, `/`, or `#` opens a scrollable Redwood suggestion list with an avatar/icon, display name, and username or token. Mentions match names and usernames, excluding the current sender. Use arrow keys to select, Tab or Enter to insert, and Escape to dismiss. The composer toolbar shows a `+` menu and Send control. The menu's Add photos & files action opens the computer file picker; selected files appear in the attachment tray. Click outside or press Escape to close the menu. Chat attachments retain the existing metadata-only behavior and are not available to coworkers for document processing.
- Failed agent replies have a light red background and border, plus a warning icon and `Task failed` label in both themes.
- Known project-member @mentions in chat show a compact Redwood profile tooltip on hover or keyboard focus, with name, human/AI type, role, description when available, and status. Unknown mentions stay plain text; Escape dismisses the tooltip.
- Project members can be updated from a dedicated page using one `Add Member` popup with a Human/AI radio choice. The AI choice assigns an existing coworker without changing its global profile. The `/agents` page provides AI coworker creation, profile updates, document uploads, self-training, and deletion. An agent assigned to any project cannot be deleted; the page names those projects and links to their member pages for removal. Deletion permanently removes the agent row, its owned knowledge, and its authored chat messages. Project tasks remain but become unassigned. Member removal is labeled `Remove from Project` and removes only the project assignment.
- AI co-workers are reusable across projects through `project_agents`.
- Project creation asks only for name, status, delivery stage, description, and existing AI coworkers. The backend generates a unique project code, adds the creator to the human membership needed for chat, and assigns the selected coworkers in the same database transaction. Project editing retains the existing advanced fields.
- Shared application header stays visible across pages; page content uses the full available width below the header.
- Header branding uses the `SQUAD.` wordmark with 2px letter spacing and an `S.` mark in the collapsed sidebar.
- Shared Redwood sizing keeps navigation, headings, action icons, buttons, cards, forms, and tables compact. Mobile navigation retains larger touch targets.
- Page headers show only a title and short description, without a separate category label or breadcrumb above the title. Loading skeleton headers follow the same two-line layout.
- Loading routes and page data use shared Redwood skeletons shaped for lists, cards, details, forms, chat, and text content. Decorative placeholders are hidden from screen readers, loading status is announced, and animation stops when reduced motion is preferred.
- Menu hover, keyboard focus, and touch warm destination routes and directory data; background warming starts after a short delay and skips slow/data-saving connections. The teams, projects, and coworkers directory endpoints share in-flight requests and reuse browser-memory results for up to 15 seconds. Writes, uploads, and returning to the tab invalidate these results; templates, chat, task progress, and detail reads remain uncached. Template routes are prefetched only for signed-in admins. Route transitions show a Redwood loading placeholder. Coworker creation options and the Markdown renderer load only when needed.
- Frontend defaults to a polished light Redwood theme and includes a header toggle for dark theme.
- Local Next.js development indicator is disabled so product screens stay clean during review.
- Project list fetches are uncached, and removed projects stay hidden after refresh.
- Database version `1.2.0` adds reusable project AI members and member profile fields.

## Initial Shape

- `backend/app/agents`: predefined AI coworker profiles.
- `backend/app/services/knowledge_documents.py`: parses approved document formats and splits pages, slides, and text into graph chunks.
- `backend/app/services/agent_training.py`: maintains one agent-owned knowledge graph from approved files, completed task summaries, and chat messages.
- `backend/db`: SQLite DDL, seed DML, migration scripts, and database changelog.
- `backend/scripts/init_db.py`: applies zero-day migration and creates the local SQLite database.
- `backend/app/services/model_router.py`: task complexity and model selection placeholder.
- `backend/app/services/codex_runner.py`: Codex CLI subprocess wrapper. On Windows it resolves `codex.exe` or `codex.cmd` from the backend PATH and sends prompts through stdin.
- `frontend/app`: Next.js Redwood-themed product team console.

## Database

Current database version: `2.1.0`.

- SQLite file: `.runtime/multi-agent-team.db` at the repository root. Startup relocates an existing legacy database with SQLite backup, verifies its integrity, and archives the old file under `.runtime/projects/_system/backups/` before using the runtime database. Existing legacy `.env` paths also resolve to the runtime database; custom database overrides remain supported.
- DDL: `backend/db/schema.sql`
- Seed DML: `backend/db/seed.sql`
- Zero-day migration: `backend/db/migrations/1.0.0/001_zero_day.sql`
- Projects migration: `backend/db/migrations/1.1.0/001_projects_feature.sql`
- Reusable project members migration: `backend/db/migrations/1.2.0/001_reusable_project_members.sql`
- Agent knowledge index migration: `backend/db/migrations/1.3.0/001_agent_knowledge_graph.sql`
- Agent source paths migration: `backend/db/migrations/1.4.0/001_agent_source_paths.sql`
- Independent agent sources migration: `backend/db/migrations/1.5.0/001_agent_owned_sources.sql`
- Seeded Silvy removal migration: `backend/db/migrations/1.6.0/001_remove_seeded_silvy.sql`
- Agent owned graph migration: `backend/db/migrations/1.7.0/001_agent_owned_knowledge_graph.sql`
- Graph chunks migration: `backend/db/migrations/1.8.0/001_agent_graph_chunks.sql`
- Semantic embeddings migration: `backend/db/migrations/1.9.0/001_agent_graph_embeddings.sql`
- Coworker read tools migration: `backend/db/migrations/2.0.0/001_coworker_read_tools.sql`
- Task progress migration: `backend/db/migrations/2.1.0/001_task_events.sql`
- Changelog: `backend/db/CHANGELOG.md`

Uploaded knowledge sources stay under `.runtime/projects/project-<id>/knowledge/<agent-username>/`. The database stores their relative paths. Startup relocates legacy files and updates the source paths while preserving file content and trained graph data.

Active source records belong to the coworker. Uploads made from a project use that project folder. Global coworker uploads use the existing Agent pool project folder, since coworkers can belong to multiple projects. Unreferenced uploaded files are removed on resource or coworker deletion. The original Silvy fixture and its example documents have been removed; a newly created coworker starts with no knowledge sources.

The AI Co-workers page lists existing coworkers as cards, with separate Edit, Self Train, and Try pages. Edit lets a user upload multiple TXT, MD, DOC, DOCX, PDF, PPT, or PPTX resources (up to 50 MB each), copy a source path, or remove a resource. Upload and removal change the resource list immediately but leave the agent graph and embeddings unchanged until the user selects Start Self Train. The Self Train page shows pending added and removed resources; training parses approved files and linked project work, updates only changed graph sources, and removes graph nodes and vectors for deleted resources. Try uses only the selected coworker's trained graph and excludes deleted resources even while training is pending. Image-only PDFs require OCR, which is not included. The Codex CLI trial runs read-only and stops after two minutes.

The Business Analyst template is seeded automatically. On an installation with trained Silvy sources, startup copies those approved files into the template, publishes the shared graph, and marks Silvy's copies as inherited. Silvy retains her project memberships, tasks, chats, and individual experience. New coworkers receive their own graph and project assignments. Shared files are managed on the template; cloned coworkers receive read-only inherited copies and train their own project, task, chat, and portable-lesson experience.

The Agent Templates page creates and manages a reusable Business Analyst or other role template. Add default instructions and approved skill or document files, then select Start Self Train to publish a version. A trained `SKILL.md` is included as instructions in relevant coworker turns. Creating a coworker from a published template copies its trained source graph and pins the template version; Silvy and Jack receive separate agent IDs, graphs, project memberships, tasks, and personal knowledge. A later template publication does not silently change existing coworkers. Each coworker can explicitly upgrade its inherited defaults while keeping individual knowledge and work. The Self Train page also lets a coworker save approved portable lessons with source-project provenance; those lessons enter only that coworker's graph after Self Train and can be used across its projects. Raw project task experience remains project tagged and is retrieved from another project only when the requesting human belongs to that project. Try uses only global coworker sources and portable lessons, without project context. This installation uses one local workspace and its logged-in Codex CLI; no customer selection is exposed.

Try and Self Train now create persisted agent jobs and return immediately. Separate backend worker threads run each coworker; work for one coworker is serialized while different coworkers can run concurrently. The browser uses a Web Worker to submit and follow Try and Self Train jobs and to poll project chat, so navigation does not stop backend work. If the backend restarts mid-job, its job is marked failed and can be started again. Project assignments and follow-ups continue to use their task and Codex run records.

Try conversations now have persistent session IDs and retain every user and assistant message across refreshes. New chat starts a separate session for the same coworker. Short retries such as "retry now" reuse the last substantive user question from the stored session before knowledge retrieval and tool selection. Legacy API callers can supply history to seed a new session; the browser sends only its session ID. Each session belongs to one coworker.

Try treats factual questions grounded in approved knowledge as within scope. Self Train embeds each graph chunk locally as a 384-dimensional vector with `sentence-transformers/all-MiniLM-L6-v2`; Try embeds the question, finds similar chunks only in that coworker's graph by cosine similarity, and reranks the candidates with `cross-encoder/ms-marco-MiniLM-L6-v2` before sending passages to Codex. PDF words merged during extraction are split for retrieval, while the original passage remains available to the answering model. The local models need no API key and run on the backend CPU. Prepare both model caches once before Self Train or chat on a new machine, for example with `hf download sentence-transformers/all-MiniLM-L6-v2 --cache-dir .runtime/projects/_system/cache/models` and `hf download cross-encoder/ms-marco-MiniLM-L6-v2 --cache-dir .runtime/projects/_system/cache/models`. Startup reuses already installed model caches by copying the required models into this runtime cache. Inference reads the runtime cache; the original shared library cache remains available for other applications. Runtime inference loads cached models offline to avoid stalled network checks. Existing agents must run Self Train once after migration 1.9.0 to add embeddings. Subsequent Self Train runs skip unchanged embedded chunks. No keyword fallback is used. Source details are retained by the API but are not shown in the trial chat.

Project chat uses the same agent-owned graph, prioritizing global agent resources and trained work from the current project. An assigned coworker must be active in that project and have run Self Train. Saved task inputs, earlier results, and task files are working memory for immediate follow-ups in that project, without another Self Train. Trained task experience from another project can also be retrieved when the requesting human belongs to that project; it is labeled with its source project and used only for reusable methods, not as current-project requirements. Cross-project retrieval requires Self Train and never includes another project's raw chat or uploaded files. The backend uses the logged-in Codex CLI with a workspace-write sandbox rooted at `.runtime/projects/project-<id>/tasks/task-<id>/`; execution stops after two minutes without observable model/tool progress, with one bounded checkpoint recovery attempt. Requested files persist there across follow-ups, and the coworker reports their absolute local paths. Application source and the database are outside the task workspace. Project turns use the CLI automatic approval reviewer so permitted local writes can run without a human approval prompt in headless mode. The `/assign` result is persisted in `tasks` and `codex_runs`, then shown in chat. Training remains manual, so newly assigned project work enters the graph on the next Start Self Train. A built-in Task Router reviews untagged human messages in the background using local cached sentence-transformer embeddings, coworker roles/scopes, existing tasks, and the latest 20 messages from the current discussion. Short replies, corrections, supplied inputs, and retries continue the relevant task without an @mention; clear new work is assigned by role. Discussion task IDs resolve similar task matches, and explicit new-topic requests are separated from ongoing work. Ambiguous or unavailable classifications ask for clarification instead of silently ignoring actionable requests. Explicit @mentions and task numbers remain optional overrides. Routing makes no external LLM call and needs no project membership. Follow-ups to a running task wait for that run to finish.

Coworker Create and Edit include read permissions for public web search, Confluence, and Oracle connectors. Both Try and project chat select permitted tools from the current message and relevant recent links; a task-time lookup does not add content to the agent graph. Public web uses Codex CLI live search. Confluence and Oracle apps are discovered from the logged-in Codex CLI, including each app's canonical slug and enabled read-only tool list. The backend ignores the user's MCP configuration for coworker turns, enables local file tools for project work and disables public web unless routed, enables only the selected apps, and disables their other tools. Project work uses the task workspace-write sandbox; Try and internal classification remain read-only. Try turns keep the two-minute deadline. Project tasks allow active execution beyond two minutes, interrupt after 120 seconds without streamed model/tool progress, and have a total execution runtime cap of 900 seconds by default (`PROJECT_RUN_MAX_SECONDS`, allowed range 120–1800). If the logged-in account lacks connector access, the coworker reports that access is unavailable. Existing active coworkers receive these read permissions through migration 2.0.0; Edit can change them.

Coworker cards show Projects and Knowledge sources as two list popups. The card has one user-facing knowledge count: uploaded sources. The former knowledge-items count referred to trained graph entries, which can also include completed tasks and project chat; those inputs are shown within the Knowledge sources section on Self Train, without a separate knowledge-items editor.

The Tasks page shows each coworker's queue, run timeline, result, and generated-file state. It refreshes while work is active. In project chat, task status questions return that coworker's recorded work in the current project; Try returns work across projects. Generated files and their absolute local paths are listed from the task workspace. Files are grouped under each project in the root `.runtime/projects/` directory; a task subfolder keeps assignments separate and lets follow-ups revise existing files. Try has no project workspace and remains read-only.

Failed project-chat replies and each task's run history have a **View execution logs** link to a separate Redwood page at `/agents/<agent-id>/tasks/<task-id>/logs?run=<run-id>`. New replies link to their exact execution run; the page also has a run selector and links back to chat and Tasks. The viewer refreshes every five seconds while a run is queued or running and shows lifecycle events, raw Codex JSON events (including tool commands, outputs, and errors), stderr, and absolute log paths. Logs are written during execution under `.runtime/projects/project-<id>/logs/task-<id>/run-<id>/`, separately from deliverables, and survive success, failure, and timeout. Each file preview shows its last 256 KB, with **Download full log** for the complete file. Older runs retain their existing progress and results; their UUID-named project logs were not linked to run IDs. Historical CLI cutoffs such as 109 seconds came from a two-minute wall-clock budget shared with preparation. Project execution now uses app-server model/tool deltas with a separate inactivity watchdog and total runtime cap, so preparation no longer subtracts from its execution window. Actual streamed activity refreshes task timestamps so chat polling does not mark a healthy long-running task as stale. Missing progress for 120 seconds stops execution safely, retains a thread checkpoint, and reports the last model/tool activity without automatically retrying; a manual retry reuses staged file progress if original file hashes still match. When the prior run saved no file changes, retry starts a fresh Codex thread with the current task context rather than extending the stalled thread. Long document revisions are instructed to save one section (about 600 words) per tool call before assembling and validating the final replacement. Policy-rejected commands remain rejected and are reported in the trace.

The execution page has a black console with white text, a received-input/run overview, recorded task progress, readable CLI command/output events, and the result or failure. Existing UUID logs are recovered only when exactly one log pair uniquely matches this project's run completion time within two seconds; the page labels this timestamp-based recovery. Ambiguous or absent logs are never assigned to a run. New runs additionally record routing inputs, selected trained sources, context scope and preparation, selected connectors, and the full CLI prompt in a downloadable input log. Older runs show their saved inputs and available logs; missing historical steps cannot be reconstructed.

Do not commit the generated SQLite runtime database or uploaded knowledge files. `.runtime/` is ignored in `.gitignore`; only DDL, DML, migrations, and changelog files should be pushed.

## Runtime file storage

All application files outside SQLite stay in the repository root `.runtime/projects/` tree. Project deliverables use `project-<id>/tasks/task-<id>/`, uploaded sources use `project-<id>/knowledge/`, and Codex logs and temporary execution files use the owning project's `logs/` and `tmp/` folders. Project-independent operations, backend logs, database backups, model caches, and preserved unreferenced legacy files use the reserved `_system/` folder. Temporary directories are removed after each completed or stopped turn. The shared SQLite database remains `.runtime/multi-agent-team.db`. Application source, dependencies, and Codex account configuration are not project data.

## Session context and compaction

Try and Project Collab load complete stored session history instead of fixed 10-message or 6-message windows. Project context is captured up to the request being executed, includes full saved results for the assigned coworker, and remains scoped to its project and collaboration thread. Shared project chat remains shared; private Try sessions and other-project personal memory are not imported.

The context service reads the selected model's locally cached context-window metadata, applies its effective-window percentage, and reserves space for CLI instructions, retrieved evidence, and the final answer. `CONTEXT_WINDOW_TOKENS` can override the model window; without metadata it uses a conservative 64,000-token fallback. Token budgeting uses UTF-8 bytes as a conservative upper bound, so it can compact earlier than a tokenizer-based count would. The defaults reserve 24,000 tokens for the CLI harness and 8,192 for the response; configure `CONTEXT_HARNESS_RESERVE_TOKENS`, `CONTEXT_RESPONSE_RESERVE_TOKENS`, and `CONTEXT_SUMMARY_TOKENS` to tune these reserves. No tokenizer download or network call is required for budgeting.

When history exceeds the available budget, older messages are summarized into versioned `context_compactions` records scoped by session, coworker, and model. Summaries retain requirements, decisions and reversals, constraints, unresolved questions, source references and artifact paths. Recent messages stay verbatim. Relevant original older messages are recalled within a reserved budget; every original message remains stored and available through the existing project chat API or the coworker's `GET /api/agents/{id}/trial-sessions/{session_id}` endpoint. Summaries are context, not trained knowledge or approval decisions. Checksums invalidate summaries when their source prefix changes. Failed or oversized compaction never deletes history or silently sends a truncated prompt: it returns an explicit retry error. Try preparation, compaction, and final generation share one two-minute turn deadline. Project preparation/compaction has a two-minute budget; final CLI execution uses its own 120-second inactivity watchdog and configurable total runtime cap.

Project session context uses the request message's actual collaboration thread (or the latest thread when no request boundary is supplied), preserving full stored history for generation even when older empty threads exist. The router's recent discussion window is only a classification input and does not truncate stored chat or coworker working memory.

Document revisions resolve a uniquely matching existing deliverable when an older router created an empty follow-up task. Coworker prompts include an inventory of their current/earlier task files in the same project discussion, approved trained template text, and trained `instructions.md` as well as `SKILL.md`. All task folders belonging to that coworker in the current project have editable staging copies within the app-server workspace-write policy. Original deliverables remain outside the model write roots during execution. Backend write probes validate filesystem access before execution and record the writable roots in the trace. The coworker must attempt the requested save before reporting a permission blocker and include the exact error/path if rejected. Shared templates, application source, the database, and other coworkers' task folders are not added as write roots. Ambiguous existing deliverables require a task choice, rather than guessing or asking the user to upload everything again.

Project turns also include an explicit inventory of source URLs already supplied by humans in the current discussion, with message IDs. These references, approved templates, and actual task files take precedence over older coworker messages asking for those inputs. A retry, including an operational preface such as "workspace access updated, please retry", resolves to that coworker's latest substantive user work request, skipping earlier retries and input-only messages. Supplied URLs are references to retrieve, not proof of document contents; genuine source-access failures must name the unavailable input instead of repeating the whole intake checklist.

Project turns use persistent Codex app-server threads instead of watching `codex exec` stdout file size. Model text, tool output, file/plan changes, and reasoning-progress events refresh the inactivity clock; raw reasoning text is not exposed by the execution monitor. Turns must explicitly complete successfully before staged files are published. Existing deliverables are backed up; deleting a staged original, empty files, incomplete HTML, or conflicting external edits prevent publication. Each changed file is replaced atomically, with backup restoration if publication fails. Thread metadata, original file hashes, staged drafts, and backups are kept with run logs so interrupted work can resume safely. Managed approval policy and read-only external-app restrictions remain enforced.

Projects with exactly one available coworker route requests to that coworker automatically, without asking who should handle them. Social-only messages remain silent, and ambiguous deliverables can still require a task choice.

In project chat, Tab completes the first visible mention, command, or channel suggestion at the cursor. Shift+Tab and Tab without a matching suggestion retain normal keyboard navigation.

Update Members displays humans and AI coworkers together in one responsive Redwood card grid, with separate human/coworker counts and member actions on each card.

For a direct request, its first coworker mention is the recipient; later mentions remain references unless the message explicitly invites a team discussion. For example, @sylvie can review a story prepared by @leo without routing a second execution to Leo. This also applies to /assign.

Group discussion: use `/discuss @sylvie @leo Review this story together`, start with `@sylvie and @leo`, or explicitly invite both mentioned coworkers to discuss. `/discuss` without mentions invites all available project coworkers. Each invitation queues one persisted turn per participant, in mention order, under the same requirement task. Later speakers receive earlier replies and failures from that invitation, without including human messages sent after the invitation. The human can send a follow-up to start another bounded round with the same team; mentioning one coworker switches to a direct request. Simple thanks/acknowledgments do not start another round. Each run retains its own trace and failure status. An agent handoff never reuses another agent's Codex checkpoint. Backend restart recovery for queued project turns remains subject to the existing stale-run handling; this is not an unlimited autonomous conversation.

Coworker execution loads complete approved `SKILL.md`, `instructions.md`, and `boundaries.md` text together. Policies exceeding the safe context budget produce an explicit error rather than being silently truncated. Teammate feedback can guide revisions of existing artifacts within the recipient's role; conditional refusal fragments retrieved as knowledge do not replace the full approved policy.

Your saved human chat messages have a vertical three-dot menu for Edit and Delete. Edits are marked; Delete asks for confirmation and permanently removes the message row, including its edit revisions; no placeholder remains. The backend checks the message owner and active project membership. Messages with queued/running executions cannot be changed until those executions finish. Edits do not rerun completed work. While a message exists, its edit revisions stay in internal audit metadata; completed execution logs remain intact after chat deletion; revision content is not returned in normal chat responses. Deleted messages are excluded from future conversation, routing, shared-input, and team-invitation recall.

Temporary chat cleanup is controlled by `CHAT_CLEANUP_MODE` in `backend/.env` (default false). While true, active human project members can hard-delete any message in that project, including agent/router replies and other humans' messages; editing remains owner-only and active-execution protections remain. The chat response exposes the switch to show/hide Delete menus. Set it to false and reload the backend to restore owner-only deletion. Cleanup is temporarily enabled locally until the user requests disabling it.
