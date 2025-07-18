"""
JARVIS — memory service.

A thin, dependency-free SQLite layer. Every call opens and closes its own
connection, which keeps it safe under Flask's threaded dev server and under
gunicorn workers without any global connection juggling.

Tables: tasks, events, notes, reminders, preferences, conversations.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    priority     TEXT    NOT NULL DEFAULT 'normal',
    due_date     TEXT,
    completed    INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    event_time  TEXT,
    location    TEXT,
    notes       TEXT,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    content     TEXT    NOT NULL DEFAULT '',
    tags        TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message     TEXT    NOT NULL,
    remind_at   TEXT,
    done        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_completed  ON tasks(completed);
CREATE INDEX IF NOT EXISTS idx_events_time      ON events(event_time);
CREATE INDEX IF NOT EXISTS idx_conv_created     ON conversations(created_at);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MemoryService:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    # ------------------------------------------------------------------ core
    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _rows(cursor) -> list:
        return [dict(row) for row in cursor.fetchall()]

    # ----------------------------------------------------------------- tasks
    def add_task(self, title, priority="normal", due_date=None) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tasks (title, priority, due_date, created_at) "
                "VALUES (?, ?, ?, ?)",
                (title.strip(), priority, due_date, _now()),
            )
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_task(self, task_id) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_tasks(self, include_completed=False, limit=100) -> list:
        query = "SELECT * FROM tasks"
        if not include_completed:
            query += " WHERE completed = 0"
        query += (
            " ORDER BY completed ASC,"
            " CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,"
            " id DESC LIMIT ?"
        )
        with self._conn() as conn:
            return self._rows(conn.execute(query, (limit,)))

    def complete_task(self, task_id) -> dict | None:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE tasks SET completed = 1, completed_at = ? WHERE id = ?",
                (_now(), task_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            return dict(row) if row else None

    def complete_task_by_title(self, fragment) -> dict | None:
        """Match the newest open task whose title contains the fragment."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM tasks WHERE completed = 0 AND title LIKE ? "
                "ORDER BY id DESC LIMIT 1",
                (f"%{fragment.strip()}%",),
            ).fetchone()
        return self.complete_task(row["id"]) if row else None

    def update_task(self, task_id, **fields) -> dict | None:
        allowed = {"title", "priority", "due_date", "completed"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_task(task_id)
        clause = ", ".join(f"{k} = ?" for k in updates)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE tasks SET {clause} WHERE id = ?",
                (*updates.values(), task_id),
            )
        return self.get_task(task_id)

    def delete_task(self, task_id) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    # ---------------------------------------------------------------- events
    def add_event(self, title, event_time=None, location=None, notes=None) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO events (title, event_time, location, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (title.strip(), event_time, location, notes, _now()),
            )
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_event(self, event_id) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_events(self, limit=100) -> list:
        with self._conn() as conn:
            return self._rows(
                conn.execute(
                    "SELECT * FROM events ORDER BY "
                    "CASE WHEN event_time IS NULL THEN 1 ELSE 0 END, "
                    "event_time ASC, id DESC LIMIT ?",
                    (limit,),
                )
            )

    def delete_event(self, event_id) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            return cur.rowcount > 0

    # ----------------------------------------------------------------- notes
    def add_note(self, title, content="", tags="") -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO notes (title, content, tags, created_at) "
                "VALUES (?, ?, ?, ?)",
                (title.strip(), content, tags, _now()),
            )
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)

    def get_note(self, note_id) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = ?", (note_id,)
            ).fetchone()
            return dict(row) if row else None

    def list_notes(self, limit=100) -> list:
        with self._conn() as conn:
            return self._rows(
                conn.execute(
                    "SELECT * FROM notes ORDER BY id DESC LIMIT ?", (limit,)
                )
            )

    def search_notes(self, term, limit=25) -> list:
        with self._conn() as conn:
            return self._rows(
                conn.execute(
                    "SELECT * FROM notes WHERE title LIKE ? OR content LIKE ? "
                    "OR tags LIKE ? ORDER BY id DESC LIMIT ?",
                    (f"%{term}%", f"%{term}%", f"%{term}%", limit),
                )
            )

    def update_note(self, note_id, **fields) -> dict | None:
        allowed = {"title", "content", "tags"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get_note(note_id)
        updates["updated_at"] = _now()
        clause = ", ".join(f"{k} = ?" for k in updates)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE notes SET {clause} WHERE id = ?",
                (*updates.values(), note_id),
            )
        return self.get_note(note_id)

    def delete_note(self, note_id) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
            return cur.rowcount > 0

    # ------------------------------------------------------------- reminders
    def add_reminder(self, message, remind_at=None) -> dict:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reminders (message, remind_at, created_at) "
                "VALUES (?, ?, ?)",
                (message.strip(), remind_at, _now()),
            )
            row = conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,)
            ).fetchone()
            return dict(row)

    def list_reminders(self, include_done=False, limit=100) -> list:
        query = "SELECT * FROM reminders"
        if not include_done:
            query += " WHERE done = 0"
        query += " ORDER BY id DESC LIMIT ?"
        with self._conn() as conn:
            return self._rows(conn.execute(query, (limit,)))

    def complete_reminder(self, reminder_id) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,)
            )
            return cur.rowcount > 0

    def delete_reminder(self, reminder_id) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            return cur.rowcount > 0

    # ----------------------------------------------------------- preferences
    def set_preference(self, key, value) -> dict:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
                "updated_at = excluded.updated_at",
                (key, str(value), _now()),
            )
        return {"key": key, "value": str(value)}

    def get_preference(self, key, default=None):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM preferences WHERE key = ?", (key,)
            ).fetchone()
            return row["value"] if row else default

    def all_preferences(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value FROM preferences").fetchall()
            return {r["key"]: r["value"] for r in rows}

    def delete_preference(self, key) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM preferences WHERE key = ?", (key,))
            return cur.rowcount > 0

    # ---------------------------------------------------------- conversation
    def save_message(self, role, content) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations (role, content, created_at) "
                "VALUES (?, ?, ?)",
                (role, content, _now()),
            )

    def recent_messages(self, limit=10) -> list:
        """Returns oldest-first, ready to feed straight into the model."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversations "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def clear_conversation(self) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM conversations")
            return cur.rowcount

    # ----------------------------------------------------------------- stats
    def stats(self) -> dict:
        with self._conn() as conn:
            def one(sql):
                return conn.execute(sql).fetchone()[0]

            return {
                "tasks_open": one("SELECT COUNT(*) FROM tasks WHERE completed = 0"),
                "tasks_done": one("SELECT COUNT(*) FROM tasks WHERE completed = 1"),
                "events": one("SELECT COUNT(*) FROM events"),
                "notes": one("SELECT COUNT(*) FROM notes"),
                "reminders_open": one(
                    "SELECT COUNT(*) FROM reminders WHERE done = 0"
                ),
                "messages": one("SELECT COUNT(*) FROM conversations"),
                "db_size_kb": round(
                    os.path.getsize(self.db_path) / 1024, 1
                )
                if os.path.exists(self.db_path)
                else 0,
            }

    def context_for_ai(self) -> str:
        """A compact snapshot of memory injected into the system prompt."""
        tasks = self.list_tasks(limit=8)
        events = self.list_events(limit=5)
        prefs = self.all_preferences()

        lines = []
        if tasks:
            listed = "; ".join(
                f"#{t['id']} {t['title']}"
                + (f" [{t['priority']}]" if t["priority"] != "normal" else "")
                for t in tasks
            )
            lines.append(f"Open tasks: {listed}")
        if events:
            listed = "; ".join(
                f"{e['title']}" + (f" at {e['event_time']}" if e["event_time"] else "")
                for e in events
            )
            lines.append(f"Upcoming events: {listed}")
        if prefs:
            listed = ", ".join(f"{k}={v}" for k, v in prefs.items())
            lines.append(f"Known preferences: {listed}")
        return "\n".join(lines) if lines else "No stored tasks, events or preferences yet."
