"""Stage deliverables and publish validated files without deleting saved originals."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from urllib.parse import quote

from app.services.task_trace import record_trace


def _files(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*')
            if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve())
            and not any(part.startswith('.') or part in {'node_modules', '__pycache__'}
                        for part in p.relative_to(root).parts)}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WorkspaceTransaction:
    def __init__(self, roots: list[Path], directory: Path, checkpoint: Path | None = None):
        self.directory = directory
        self.mapping = {root: directory / 'staging' / str(index) for index, root in enumerate(dict.fromkeys(roots))}
        self.initial: dict[str, dict[str, str]] = {}
        for index, (root, staged) in enumerate(self.mapping.items()):
            staged.mkdir(parents=True, exist_ok=True)
            backup = directory / 'backups' / str(index)
            files = _files(root)
            self.initial[str(root)] = {name: _digest(path) for name, path in files.items()}
            for name, path in files.items():
                for destination in (staged / name, backup / name):
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, destination)
        manifest = {'roots': [str(root) for root in self.mapping], 'initial': self.initial}
        self.resumable = False
        if checkpoint and (checkpoint / 'workspace.json').exists():
            try:
                old = json.loads((checkpoint / 'workspace.json').read_text(encoding='utf-8'))
            except (OSError, ValueError):
                old = {}
            if old == manifest:
                for index, staged in enumerate(self.mapping.values()):
                    previous = checkpoint / 'staging' / str(index)
                    if previous.is_dir():
                        for name, source in _files(previous).items():
                            target = staged / name
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(source, target)
                self.resumable = True
        temporary = directory / 'workspace.json.pending'
        temporary.write_text(json.dumps(manifest), encoding='utf-8')
        os.replace(temporary, directory / 'workspace.json')
        record_trace(directory, 'checkpoint', 'Original deliverables backed up; execution writes staging copies only.')

    def has_staged_changes(self) -> bool:
        """A resumable file snapshot alone is not evidence of execution progress."""
        for root, staged in self.mapping.items():
            current = {name: _digest(path) for name, path in _files(staged).items()}
            if current != self.initial[str(root)]:
                return True
        return False

    def rewrite(self, text: str, reverse: bool = False) -> str:
        for original, staged in sorted(self.mapping.items(), key=lambda item: len(str(item[0])), reverse=True):
            source, target = (staged, original) if reverse else (original, staged)
            text = text.replace(str(source), str(target)).replace(source.as_posix(), target.as_posix())
            text = text.replace(quote(source.as_posix(), safe='/:'), quote(target.as_posix(), safe='/:'))
        return text

    def publish(self) -> None:
        pending = []
        for root, staged in self.mapping.items():
            before = self.initial[str(root)]
            after = _files(staged)
            if set(before) - set(after):
                raise RuntimeError('The staged revision deleted an existing deliverable. Saved originals were preserved.')
            for name, source in after.items():
                target = root / name
                if name in before and _digest(source) == before[name]:
                    continue
                if (name in before and (not target.exists() or _digest(target) != before[name])) or (name not in before and target.exists()):
                    raise RuntimeError(f'File changed outside this run: {target}. Refusing to overwrite it.')
                if not source.stat().st_size:
                    raise RuntimeError(f'Empty staged deliverable: {name}. Saved originals were preserved.')
                if source.suffix.lower() in {'.html', '.htm'}:
                    text = source.read_text(encoding='utf-8-sig', errors='replace').lower()
                    if '<html' not in text or '</html>' not in text:
                        raise RuntimeError(f'Incomplete HTML deliverable: {name}. Saved originals were preserved.')
                pending.append((source, target))
        published = []
        try:
            for source, target in pending:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = target.with_name(f'.{target.name}.{uuid4().hex}.pending')
                try:
                    shutil.copy2(source, temporary)
                    os.replace(temporary, target)
                    published.append(target)
                finally:
                    temporary.unlink(missing_ok=True)
        except Exception:
            for target in reversed(published):
                for index, root in enumerate(self.mapping):
                    if target.is_relative_to(root):
                        backup = self.directory / 'backups' / str(index) / target.relative_to(root)
                        if backup.exists():
                            temporary = target.with_name(f'.{target.name}.{uuid4().hex}.restore')
                            shutil.copy2(backup, temporary)
                            os.replace(temporary, target)
                        else:
                            target.unlink(missing_ok=True)
                        break
            raise
        record_trace(self.directory, 'published', f'Atomically published {len(pending)} validated files; backups retained.')
