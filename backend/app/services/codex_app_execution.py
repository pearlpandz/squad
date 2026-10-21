"""Stream project turns, checkpoint their threads, and interrupt unresponsive work."""

import json
import os
import queue
import signal
import subprocess
import time
from pathlib import Path
from threading import Thread

from app.services.task_trace import record_trace


class InterruptedExecution(RuntimeError):
    pass


def _checkpoint(logs: Path, state: dict) -> None:
    temporary = logs / 'thread.json.pending'
    temporary.write_text(json.dumps(state), encoding='utf-8')
    os.replace(temporary, logs / 'thread.json')


def _stop(process):
    if process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True, timeout=10)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


class AppExecution:
    def __init__(self, command, environment, cwd, logs, run_name):
        self.logs = logs
        self.serial = 0
        self.pending = {}
        self.events = queue.Queue()
        self.raw = (logs / f'{run_name}.stdout.log').open('a', encoding='utf-8')
        self.err = (logs / f'{run_name}.stderr.log').open('a', encoding='utf-8')
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=self.err, text=True, encoding='utf-8', errors='replace', bufsize=1,
                cwd=cwd, env=environment, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0,
                start_new_session=os.name != 'nt')
        except Exception:
            self.raw.close()
            self.err.close()
            raise
        self.reader = Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                saved = event
                if 'reasoning' in str(event.get('method', '')).lower():
                    saved = {'method': event['method'], 'params': {'activity': 'reasoning progress'}}
                self.raw.write(json.dumps(saved, ensure_ascii=False) + '\n')
                self.raw.flush()
                self.events.put(event)
        finally:
            self.events.put(None)

    def send(self, message):
        self.process.stdin.write(json.dumps(message) + '\n')
        self.process.stdin.flush()

    def next(self, timeout=1):
        try:
            event = self.events.get(timeout=timeout)
        except queue.Empty:
            return {}
        if event is None:
            raise InterruptedExecution('Codex transport closed. Thread and staged deliverables are preserved.')
        if 'method' in event and 'id' in event:
            # Automatic review handles permitted approvals. Never grant an
            # unexpected client-side permission or external write ourselves.
            self.send({'id': event['id'], 'error': {'code': -32601,
                       'message': 'Interactive approval/input is unavailable in this background worker.'}})
            raise RuntimeError(f"Codex requires interactive action: {event['method']}. Check the execution log.")
        return event

    def request(self, method, params, timeout=30):
        self.serial += 1
        request_id = self.serial
        self.send({'id': request_id, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            event = self.next()
            if event.get('id') == request_id:
                if event.get('error'):
                    raise RuntimeError(f"Codex rejected {method}: {event['error']}")
                return event.get('result') or {}
            if event.get('method'):
                self.pending.setdefault('notifications', []).append(event)
        raise InterruptedExecution(f'Codex did not answer {method}. The saved thread can be resumed.')

    def close(self):
        try:
            self.process.stdin.close()
            self.process.wait(timeout=3)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        _stop(self.process)
        self.reader.join(timeout=3)
        if not self.reader.is_alive():
            self.raw.close()
        self.err.close()


def run_project_turn(command, environment, model, prompt, cwd: Path, roots: list[Path],
                     logs: Path, run_name: str, idle_seconds: int, total_seconds: int,
                     activity=None, checkpoint: Path | None = None) -> str:
    try:
        saved = json.loads(checkpoint.read_text(encoding='utf-8')) if checkpoint and checkpoint.exists() else {}
    except (OSError, ValueError):
        saved = {}
        record_trace(logs, 'checkpoint_unavailable', 'Thread metadata is unreadable; staged files remain available for a fresh turn.')
    thread_id = saved.get('thread_id')
    deadline = time.monotonic() + total_seconds
    policy = {'type': 'workspaceWrite', 'writableRoots': [str(root) for root in roots],
              'networkAccess': False}
    # A stale process must stop after two minutes; recovery is a manual retry.
    for attempt in range(1):
        client = AppExecution(command, environment, str(cwd), logs, run_name)
        turn_id = None
        try:
            client.request('initialize', {'clientInfo': {'name': 'multi-agent-team', 'version': '1'},
                                          'capabilities': {'experimentalApi': True}})
            client.send({'method': 'initialized', 'params': {}})
            settings = {'model': model, 'cwd': str(cwd), 'sandbox': 'workspace-write',
                        'approvalPolicy': 'on-request', 'approvalsReviewer': 'auto_review'}
            result = client.request('thread/resume' if thread_id else 'thread/start',
                                    {**settings, **({'threadId': thread_id} if thread_id else {'ephemeral': False})})
            thread_id = result['thread']['id']
            _checkpoint(logs, {'thread_id': thread_id})
            instruction = prompt
            result = client.request('turn/start', {'threadId': thread_id,
                'input': [{'type': 'text', 'text': instruction}], 'cwd': str(cwd),
                'approvalPolicy': 'on-request', 'approvalsReviewer': 'auto_review', 'sandboxPolicy': policy})
            turn_id = result['turn']['id']
            _checkpoint(logs, {'thread_id': thread_id, 'turn_id': turn_id})
            record_trace(logs, 'turn_started', f'Thread {thread_id}; turn {turn_id}; attempt {attempt + 1}')
            last_activity = last_report = time.monotonic()
            last_progress = 'Turn started; no model/tool activity received yet.'
            answer = ''
            while time.monotonic() < deadline:
                notifications = client.pending.get('notifications', [])
                event = notifications.pop(0) if notifications else client.next()
                method = event.get('method', '')
                params = event.get('params') or {}
                if params.get('threadId', thread_id) != thread_id or params.get('turnId', turn_id) != turn_id:
                    continue
                # Observe model/tool deltas, not file size, pings or thread-read responses.
                if method.startswith('item/') or method in {'turn/plan/updated', 'turn/diff/updated'}:
                    last_activity = time.monotonic()
                    item = params.get('item') or {}
                    last_progress = f"{method} ({item.get('type', 'streamed progress')})"
                    if method == 'item/completed' and item.get('type') == 'agentMessage':
                        last_progress += ': ' + item.get('text', '')[:500]
                    if activity and last_activity - last_report >= 5:
                        activity()
                        last_report = last_activity
                if method == 'item/completed':
                    item = params.get('item') or {}
                    if item.get('type') == 'agentMessage' and item.get('phase') != 'commentary':
                        answer = item.get('text', '')
                if method == 'turn/completed' and params.get('turn', {}).get('id') == turn_id:
                    turn = params['turn']
                    if turn.get('status') != 'completed':
                        raise RuntimeError(f"Codex turn {turn.get('status')}: {turn.get('error') or 'See execution logs'}")
                    if not answer:
                        raise RuntimeError('Codex completed without a final response. Staged files were not published.')
                    record_trace(logs, 'turn_completed', f'Turn {turn_id} completed successfully.')
                    return answer
                if time.monotonic() - last_activity >= idle_seconds:
                    raise InterruptedExecution(
                        f'No model/tool progress for {idle_seconds} seconds. Last activity: {last_progress}')
            raise RuntimeError(f'Project execution reached its {total_seconds}-second runtime cap. Originals and checkpoints are preserved.')
        except InterruptedExecution as exc:
            record_trace(logs, 'interrupted', str(exc))
            if turn_id:
                try:
                    client.request('turn/interrupt', {'threadId': thread_id, 'turnId': turn_id}, timeout=5)
                except (RuntimeError, OSError):
                    pass
            raise RuntimeError(
                f'Execution stopped: {exc} Original files and staged work are preserved. '
                'Review this run\'s execution logs. A manual retry can use the saved checkpoint '
                'if the original files are unchanged.') from exc
        finally:
            client.close()
