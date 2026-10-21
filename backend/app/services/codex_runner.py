import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import tomllib
from contextlib import nullcontext
from collections.abc import Iterable
from collections.abc import Callable
from pathlib import Path
from threading import Thread
from uuid import uuid4

from app.services.agent_tools import ToolPlan
from app.db.session import project_root
from app.core.runtime import runtime_project_root
from app.services.task_trace import record_trace
from app.services.workspace_transaction import WorkspaceTransaction
from app.services.codex_app_execution import run_project_turn


def _codex_executable() -> str:
    candidates = ("codex.exe", "codex.cmd") if os.name == "nt" else ("codex",)
    for candidate in candidates:
        executable = shutil.which(candidate)
        if executable:
            return executable
    raise RuntimeError("Codex CLI executable was not found on the backend PATH")


def build_codex_exec_command(model: str) -> list[str]:
    return [_codex_executable(), "exec", "--model", model, "--json", "-"]


def _read_only_cli_environment() -> dict[str, str]:
    environment = os.environ.copy()
    # The desktop parent injects a private app-tools pipe that a nested CLI cannot load.
    environment.pop("CODEX_APP_TOOLS_PIPE_PATH", None)
    return environment


def run_codex_task(model: str, prompt: str) -> Iterable[dict]:
    process = subprocess.Popen(
        build_codex_exec_command(model),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def send_prompt() -> None:
        if process.stdin is None:
            return
        try:
            process.stdin.write(prompt)
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()

    Thread(target=send_prompt, daemon=True).start()

    if process.stdout is None:
        return

    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            yield {"type": "log", "message": line}


def run_codex_trial(model: str, prompt: str, tool_plan: ToolPlan | None = None,
                    timeout_seconds: int = 120, tool_events: list[str] | None = None,
                    diagnostics: list[str] | None = None,
                    output_directory: Path | None = None,
                    trace_directory: Path | None = None,
                    idle_timeout_seconds: int | None = None,
                    total_timeout_seconds: int | None = None,
                    activity: Callable[[], None] | None = None,
                    additional_write_directories: list[Path] | None = None) -> str:
    """Run a bounded turn, optionally enforcing inactivity and total runtime separately."""
    if not 1 <= timeout_seconds <= 120:
        raise ValueError("Codex timeout must be between 1 and 120 seconds")
    if idle_timeout_seconds is not None and not 1 <= idle_timeout_seconds <= 120:
        raise ValueError("Codex inactivity timeout must be between 1 and 120 seconds")
    if total_timeout_seconds is not None and not 1 <= total_timeout_seconds <= 1800:
        raise ValueError("Codex total timeout must be between 1 and 1800 seconds")
    plan = tool_plan or ToolPlan()
    writable = output_directory is not None
    write_directories = []
    for directory in additional_write_directories or []:
        directory = directory.resolve()
        if not writable or not directory.is_relative_to((project_root() / ".runtime/projects").resolve()):
            raise ValueError("Additional write roots require a project workspace and must stay under .runtime/projects")
        directory.mkdir(parents=True, exist_ok=True)
        if directory not in write_directories:
            write_directories.append(directory)
    if output_directory is not None:
        output_directory = output_directory.resolve()
        if not output_directory.is_relative_to((project_root() / ".runtime" / "projects").resolve()):
            raise ValueError("Codex outputs must stay under .runtime/projects")
        output_directory.mkdir(parents=True, exist_ok=True)
    runtime_directory = runtime_project_root()
    if output_directory is not None:
        projects_root = (project_root() / ".runtime/projects").resolve()
        runtime_directory = projects_root / output_directory.relative_to(projects_root).parts[0]
    temporary_root = runtime_directory / "tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    logs_root = trace_directory or runtime_directory / "logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    run_name = f"codex-{uuid4().hex}"
    work_context = nullcontext(str(output_directory)) if writable else tempfile.TemporaryDirectory(prefix="coworker-trial-", dir=temporary_root)
    with work_context as work_dir, tempfile.TemporaryDirectory(prefix="coworker-answer-", dir=temporary_root) as answer_dir:
        answer_path = Path(answer_dir) / "answer.txt"
        executable = _codex_executable()
        environment = _read_only_cli_environment()
        environment.update({"TMP": str(temporary_root), "TEMP": str(temporary_root), "TMPDIR": str(temporary_root)})
        command = [executable,
                   "-c", "apps._default.enabled=false",
                   "-c", "apps._default.destructive_enabled=false",
                   "-c", "apps._default.default_tools_approval_mode=\"writes\"",
                   "-c", f"features.shell_tool={'true' if writable else 'false'}",
                   "-c", "approval_policy=\"on-request\""]
        if writable:
            # Headless exec cannot prompt a human; use the CLI's approval reviewer.
            command.append("--approve-for-me")
        if plan.web_search:
            command.append("--search")
        else:
            command.extend(["-c", "web_search=\"disabled\""])
        if plan.apps:
            for app in plan.apps:
                if not app.id.replace("-", "_").replace("_", "").isalnum():
                    raise RuntimeError("Unsafe app id in Codex catalog")
                command.extend(["-c", f"apps.{app.id}.enabled=true",
                                "-c", f"apps.{app.id}.destructive_enabled=false"])
                for tool_name in app.tools:
                    command.extend(["-c", f"apps.{app.id}.tools.{json.dumps(tool_name)}.enabled=true"])
                for tool_name in app.blocked_tools:
                    command.extend(["-c", f"apps.{app.id}.tools.{json.dumps(tool_name)}.enabled=false"])
        command.extend(["exec", "--model", model, "--json", "--sandbox", "workspace-write" if writable else "read-only",
                        "--skip-git-repo-check", "--ephemeral"])
        for directory in write_directories:
            if directory != output_directory:
                command.extend(["--add-dir", str(directory)])
        command.append("--ignore-user-config")
        command.extend(["-C", work_dir, "--output-last-message", str(answer_path), "-"])
        if plan.apps:
            prompt = " ".join(f"${app.slug}" for app in plan.apps) + "\n" + prompt
        if writable:
            # Check actual backend filesystem access without modifying a deliverable.
            for directory in dict.fromkeys([output_directory, *write_directories]):
                try:
                    with tempfile.TemporaryFile(dir=directory) as probe:
                        probe.write(b"workspace access check")
                        probe.flush()
                except OSError as exc:
                    record_trace(logs_root, "workspace_error", f"Write access failed: {directory}: {exc}")
                    raise RuntimeError(f"Task workspace is not writable: {directory}: {exc}") from exc
            writable_roots = "\n".join(str(path) for path in dict.fromkeys([output_directory, *write_directories]))
            record_trace(logs_root, "workspace", f"Requested sandbox: workspace-write; backend write checks passed. Writable task folders:\n{writable_roots}")
            prompt = (
                "Local file policy: You can create and update requested deliverables in your working "
                f"directory: {work_dir}, and these explicitly writable coworker task folders:\n{writable_roots}\n"
                "Keep all output files inside these folders. "
                "Use local file tools to produce the requested format and verify each file exists before "
                "reporting its absolute local path. Read existing deliverables here for revisions. "
                "You may read explicitly supplied reference files. These task folders passed a backend write check; "
                "attempt the requested file save using an enabled file tool before reporting a permission blocker. "
                "Do not infer current permissions from historical chat or earlier read-only statements. "
                "If saving is rejected, report the exact tool error and path; do not claim a read-only workspace without evidence. "
                "Do not change the application source, database, or external records. "
                "If a tool is rejected by policy, do not retry equivalent commands to bypass it. "
                "Use an already permitted operation if available; otherwise report the exact blocker. "
                "Create the complete requested deliverable before reporting success; a title-only file is incomplete. "
                "Use the Redwood theme for frontend/UI deliverables. Architecture and flow diagrams "
                "must use draw.io format. Do not write test cases unless requested.\n\n" + prompt
            )
        record_trace(logs_root, "launch", f"Model: {model}; timeout: {timeout_seconds}s; workspace: {work_dir}")
        if idle_timeout_seconds is not None:
            record_trace(logs_root, "limits", f"Inactivity: {idle_timeout_seconds}s; total: {total_timeout_seconds or timeout_seconds}s")
        if trace_directory is not None:
            (logs_root / f"{run_name}.input.log").write_text(prompt, encoding="utf-8")
        if writable:
            previous = None
            if trace_directory and trace_directory.name.startswith('run-') and trace_directory.parent.name.startswith('task-'):
                from app.db.session import get_connection
                with get_connection() as connection:
                    row = connection.execute(
                        'SELECT id, process_status, command_json FROM codex_runs WHERE task_id = ? AND id < ? ORDER BY id DESC LIMIT 1',
                        (int(trace_directory.parent.name[5:]), int(trace_directory.name[4:])),
                    ).fetchone()
                    current = connection.execute('SELECT command_json FROM codex_runs WHERE id = ?',
                                                 (int(trace_directory.name[4:]),)).fetchone()
                same_agent = bool(row and current and
                                  json.loads(row['command_json']).get('agent_id') ==
                                  json.loads(current['command_json']).get('agent_id'))
                if row and row['process_status'] == 'failed' and same_agent:
                    previous = trace_directory.parent / f"run-{row['id']}"
            transaction = WorkspaceTransaction(list(dict.fromkeys([output_directory, *write_directories])), logs_root, previous)
            staged_roots = list(transaction.mapping.values())
            staged_prompt = transaction.rewrite(prompt) + (
                '\n\nExecution safety: These paths are staged copies. Never delete a saved file before '
                'its replacement is complete. Write complete revisions using temporary files and atomic '
                'replacement. The backend publishes validated files only after a successful turn. '
                'For a long deliverable, write it incrementally: each tool call should write at most '
                'one section or about 600 words, then inspect the saved section before continuing. '
                'Do not generate the entire document in one large tool argument. Build a temporary '
                'replacement in the staging directory, append sections with small commands, and '
                'verify the complete result before replacing the staged deliverable. '
                'Give brief progress updates after saving sections, not instead of saving work. '
                'Original deliverables outside the staging roots are read-only references.'
            )
            (logs_root / f'{run_name}.input.log').write_text(staged_prompt, encoding='utf-8')
            prefix = command[:command.index('exec')]
            prefix = [value for value in prefix if value not in {'--approve-for-me', '--search'}]
            prefix.extend(['-c', 'web_search="live"' if plan.web_search else 'web_search="disabled"'])
            # app-server has no --ignore-user-config flag. Disable every user MCP
            # server explicitly while retaining managed policy and CLI sign-in.
            config_path = Path(environment.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'config.toml'
            if config_path.exists():
                configured = tomllib.loads(config_path.read_text(encoding='utf-8'))
                for server in configured.get('mcp_servers', {}):
                    if not all(character.isalnum() or character in '_-' for character in server):
                        raise RuntimeError('Unsupported MCP configuration name; cannot safely isolate project tools.')
                    prefix.extend(['-c', f'mcp_servers.{server}.enabled=false'])
                selected_apps = {app.id for app in plan.apps}
                for app in configured.get('apps', {}):
                    if app != '_default' and app not in selected_apps:
                        if not all(character.isalnum() or character in '_-' for character in app):
                            raise RuntimeError('Unsupported app configuration name; cannot safely isolate project tools.')
                        prefix.extend(['-c', f'apps.{app}.enabled=false'])
            record_trace(logs_root, 'transport', 'Project execution uses app-server model/tool deltas, persistent thread checkpoints, and isolated staging.')
            resume_checkpoint = None
            if previous and transaction.resumable:
                if transaction.has_staged_changes():
                    resume_checkpoint = previous / 'thread.json'
                    record_trace(logs_root, 'recovery_mode', 'Resuming saved thread with staged file progress.')
                else:
                    record_trace(logs_root, 'recovery_mode',
                                 'Previous run made no staged file changes. Starting a fresh thread with '
                                 'current task context and preserved files instead of replaying the stalled thread.')
            answer = run_project_turn(prefix + ['app-server'], environment, model, staged_prompt,
                                      transaction.mapping[output_directory], staged_roots, logs_root, run_name,
                                      idle_timeout_seconds or 120, total_timeout_seconds or 900, activity,
                                      resume_checkpoint)
            transaction.publish()
            return transaction.rewrite(answer, reverse=True)
        try:
            # Redirect directly to files so polling can read output while the CLI is running.
            with (logs_root / f"{run_name}.stdout.log").open("w", encoding="utf-8") as stdout_file, \
                    (logs_root / f"{run_name}.stderr.log").open("w", encoding="utf-8") as stderr_file:
                return _execute_trial(command, environment, work_dir, prompt, timeout_seconds,
                                      logs_root, run_name, answer_path, stdout_file, stderr_file,
                                      tool_events, diagnostics, idle_timeout_seconds,
                                      total_timeout_seconds, activity)
        except FileNotFoundError as exc:
            record_trace(logs_root, "failed", str(exc))
            raise RuntimeError("Codex CLI executable disappeared from the backend PATH") from exc


def _execute_trial(command, environment, work_dir, prompt, timeout_seconds, logs_root,
                   run_name, answer_path, stdout_file, stderr_file, tool_events, diagnostics,
                   idle_timeout_seconds=None, total_timeout_seconds=None, activity=None) -> str:
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE, stdout=stdout_file, stderr=stderr_file,
        text=True, encoding="utf-8", errors="replace",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
        env=environment,
        cwd=work_dir,
    )
    stop_reason = ""
    try:
        if idle_timeout_seconds is None:
            process.communicate(input=prompt, timeout=timeout_seconds)
        else:
            started = last_activity = last_report = time.monotonic()
            output_size = 0
            first = True
            while True:
                try:
                    process.communicate(input=prompt if first else None, timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    first = False
                    now = time.monotonic()
                    size = (logs_root / f"{run_name}.stdout.log").stat().st_size
                    if size != output_size:
                        output_size = size
                        last_activity = now
                        if activity is not None and now - last_report >= 5:
                            activity()
                            last_report = now
                    if now - started >= (total_timeout_seconds or timeout_seconds):
                        stop_reason = f"Codex execution reached its {total_timeout_seconds or timeout_seconds}-second total runtime limit."
                        raise
                    if now - last_activity >= idle_timeout_seconds:
                        stop_reason = f"Codex execution stalled: no new execution output for {idle_timeout_seconds} seconds."
                        raise
    except subprocess.TimeoutExpired as exc:
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                               capture_output=True, timeout=10, check=False)
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        detail = stop_reason or f"Codex execution stopped after its {timeout_seconds}-second execution budget expired."
        stderr = (logs_root / f"{run_name}.stderr.log").read_text(encoding="utf-8", errors="replace")
        if "blocked by policy" in stderr.lower():
            detail += " A tool command was rejected by policy; review stderr for the exact command."
        detail += " Review this run's execution logs for the last activity."
        record_trace(logs_root, "timeout", detail)
        raise RuntimeError(detail) from exc
    record_trace(logs_root, "exit", f"CLI exit code: {process.returncode}")
    stdout = (logs_root / f"{run_name}.stdout.log").read_text(encoding="utf-8", errors="replace")
    stderr = (logs_root / f"{run_name}.stderr.log").read_text(encoding="utf-8", errors="replace")
    answer_from_file = answer_path.read_text(encoding="utf-8").strip() if answer_path.exists() else ""

    answer = answer_from_file
    error = ""
    if diagnostics is not None:
        diagnostics.append(stderr[-1200:])
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                answer = item.get("text", "")
            elif tool_events is not None:
                tool_events.append(f"{item.get('type', 'unknown')}:{item.get('tool', item.get('name', ''))}")
            if diagnostics is not None and item.get("type") == "error":
                diagnostics.append(str(item.get("message", ""))[:500])
            if diagnostics is not None and item.get("type") == "command_execution" and item.get("exit_code") != 0:
                diagnostics.append(str(item.get("aggregated_output", ""))[-1200:])
        elif event.get("type") == "turn.failed":
            failure = event.get("error") or {}
            error = failure.get("message", "") if isinstance(failure, dict) else str(failure)
    if process.returncode != 0 or not answer:
        raise RuntimeError(error or "Codex trial failed; check CLI login and model access")
    return answer
