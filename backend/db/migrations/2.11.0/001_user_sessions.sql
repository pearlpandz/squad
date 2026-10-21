BEGIN;

CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    human_id INTEGER NOT NULL REFERENCES humans(id),
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expiry ON user_sessions(expires_at);

DELETE FROM admin_sessions;
UPDATE app_settings SET value = '2.11.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.11.0', 'Passwordless email and role sessions for all workspace users');
COMMIT;
