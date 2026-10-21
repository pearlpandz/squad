CREATE TABLE IF NOT EXISTS task_workflows (
    thread_id INTEGER PRIMARY KEY REFERENCES conversation_threads(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    brd_key TEXT
);
