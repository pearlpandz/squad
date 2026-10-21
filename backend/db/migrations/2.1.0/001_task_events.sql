CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_task_events_task ON task_events(task_id, id);

INSERT INTO task_events (task_id, stage, detail, created_at)
SELECT id, 'assigned', 'Task assigned to coworker.', created_at FROM tasks
WHERE assigned_agent_id IS NOT NULL;

UPDATE app_settings SET value = '2.1.0', updated_at = datetime('now') WHERE key = 'app.version';
INSERT OR IGNORE INTO schema_migrations (version, description)
VALUES ('2.1.0', 'Record coworker task progress events');
