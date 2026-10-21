"""Interactively configure the local admin credential without printing a password."""
import getpass
import os
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.admin import password_hash


def main() -> None:
    username = input("Admin username [collab-admin]: ").strip() or "collab-admin"
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{2,80}", username):
        raise SystemExit("Use 2-80 letters, numbers, dots, underscores, @ or hyphens.")
    password = getpass.getpass("Admin password (12-256 characters): ")
    if not 12 <= len(password) <= 256:
        raise SystemExit("Password must contain 12-256 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match; configuration was not changed.")
    env_path = Path(__file__).resolve().parents[1] / ".env"
    content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    values = {"ADMIN_USERNAME": username, "ADMIN_PASSWORD_HASH": password_hash(password)}
    for key, value in values.items():
        line = f"{key}='{value}'"
        if re.search(rf"^{key}=", content, flags=re.M):
            content = re.sub(rf"^{key}=.*$", lambda _: line, content, flags=re.M)
        else:
            content = content.rstrip() + "\n" + line + "\n"
    handle, temporary = tempfile.mkstemp(prefix=".admin-config-", dir=env_path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as output:
            output.write(content)
        os.replace(temporary, env_path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print("Admin configured. Restart the backend, then open /admin in SQUAD.")


if __name__ == "__main__":
    main()
