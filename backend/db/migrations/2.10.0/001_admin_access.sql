BEGIN;

CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    credential_version TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_login_attempts (
    client_address TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL DEFAULT 0,
    window_started_at INTEGER NOT NULL
);

UPDATE app_settings SET value = '2.10.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.10.0', 'Administrator sessions and sign-in attempt limits');

COMMIT;
