from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

MOSCOW_TZ = timezone(timedelta(hours=3))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def to_moscow_display(value: str | None) -> str:
    if not value:
        return "—"

    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_msk = dt.astimezone(MOSCOW_TZ)
        return dt_msk.strftime("%d.%m.%Y %H:%M:%S") + " МСК"
    except Exception:
        return value


class AnalyticsService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    is_bot INTEGER NOT NULL DEFAULT 0,
                    language_code TEXT,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    last_step TEXT,
                    current_step_updated_at TEXT,
                    start_count INTEGER NOT NULL DEFAULT 0,
                    bot_blocked INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    step TEXT,
                    payload_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS nurture_state (
                    user_id INTEGER PRIMARY KEY,
                    context_type TEXT,
                    context_id TEXT,
                    last_activity_at TEXT NOT NULL,
                    payment_reached INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS nurture_sent (
                    user_id INTEGER NOT NULL,
                    reminder_code TEXT NOT NULL,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, reminder_code),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                """
            )

            columns = {row[1] for row in cursor.execute("PRAGMA table_info(users)")}
            if "bot_blocked" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN bot_blocked INTEGER NOT NULL DEFAULT 0")

            cursor.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id);
                CREATE INDEX IF NOT EXISTS idx_events_step ON events(step);
                CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
                CREATE INDEX IF NOT EXISTS idx_users_last_step ON users(last_step);
                CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen);
                CREATE INDEX IF NOT EXISTS idx_users_blocked ON users(bot_blocked);
                CREATE INDEX IF NOT EXISTS idx_nurture_last_activity ON nurture_state(last_activity_at);
                """
            )

            self._conn.commit()

    def identify_user(self, user: Any) -> None:
        now = utc_now_iso()
        user_id = int(user.id)
        username = getattr(user, "username", None)
        first_name = getattr(user, "first_name", None)
        last_name = getattr(user, "last_name", None)
        is_bot = 1 if getattr(user, "is_bot", False) else 0
        language_code = getattr(user, "language_code", None)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO users (
                    user_id, username, first_name, last_name, is_bot,
                    language_code, first_seen, last_seen, bot_blocked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    is_bot = excluded.is_bot,
                    language_code = excluded.language_code,
                    last_seen = excluded.last_seen,
                    bot_blocked = 0
                """,
                (user_id, username, first_name, last_name, is_bot, language_code, now, now),
            )
            self._conn.commit()

    def mark_user_blocked(self, user_id: int, blocked: bool = True) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE users SET bot_blocked = ? WHERE user_id = ?",
                (1 if blocked else 0, user_id),
            )
            self._conn.commit()

    def track_event(
        self,
        user: Any,
        event_type: str,
        step: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.identify_user(user)
        now = utc_now_iso()
        user_id = int(user.id)
        payload_json = json.dumps(payload, ensure_ascii=False) if payload else None

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO events (user_id, event_type, step, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, event_type, step, payload_json, now),
            )

            if step:
                self._conn.execute(
                    """
                    UPDATE users
                    SET last_step = ?, current_step_updated_at = ?, last_seen = ?, bot_blocked = 0
                    WHERE user_id = ?
                    """,
                    (step, now, now, user_id),
                )

            if event_type == "start_command":
                self._conn.execute(
                    "UPDATE users SET start_count = start_count + 1 WHERE user_id = ?",
                    (user_id,),
                )

            self._conn.commit()

    def track_step(self, user: Any, step: str, payload: dict[str, Any] | None = None) -> None:
        self.track_event(user=user, event_type="step", step=step, payload=payload)

    def set_nurture_context(
        self,
        user: Any,
        context_type: str,
        context_id: str | None = None,
        payment_reached: bool = False,
    ) -> None:
        self.identify_user(user)
        user_id = int(user.id)
        now = utc_now_iso()

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO nurture_state (user_id, context_type, context_id, last_activity_at, payment_reached)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    context_type = excluded.context_type,
                    context_id = excluded.context_id,
                    last_activity_at = excluded.last_activity_at,
                    payment_reached = excluded.payment_reached
                """,
                (user_id, context_type, context_id, now, 1 if payment_reached else 0),
            )
            self._conn.commit()

    def restart_nurture_cycle(self, user: Any) -> None:
        self.identify_user(user)
        user_id = int(user.id)
        with self._lock:
            self._conn.execute("DELETE FROM nurture_sent WHERE user_id = ?", (user_id,))
            self._conn.execute("DELETE FROM nurture_state WHERE user_id = ?", (user_id,))
            self._conn.commit()

    def mark_nurture_sent(self, user_id: int, reminder_code: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO nurture_sent (user_id, reminder_code, sent_at)
                VALUES (?, ?, ?)
                """,
                (user_id, reminder_code, utc_now_iso()),
            )
            self._conn.commit()

    def get_sent_reminder_codes(self, user_id: int) -> set[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT reminder_code FROM nurture_sent WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        return {row["reminder_code"] for row in rows}

    def reset_nurture(self, user_ref: str) -> bool:
        user_row = self._resolve_user_row(user_ref)
        if not user_row:
            return False

        user_id = user_row["user_id"]
        now = utc_now_iso()
        with self._lock:
            self._conn.execute("DELETE FROM nurture_sent WHERE user_id = ?", (user_id,))
            self._conn.execute(
                """
                UPDATE nurture_state
                SET last_activity_at = ?, payment_reached = 0
                WHERE user_id = ?
                """,
                (now, user_id),
            )
            self._conn.commit()
        return True

    def get_due_nurture_reminders(self, reminders: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        now = utc_now()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT s.user_id, s.context_type, s.context_id, s.last_activity_at, s.payment_reached,
                       u.username, u.first_name
                FROM nurture_state s
                JOIN users u ON u.user_id = s.user_id
                WHERE s.payment_reached = 0
                ORDER BY s.last_activity_at ASC
                """
            ).fetchall()

        due_items: list[dict[str, Any]] = []
        for row in rows:
            user_id = row["user_id"]
            last_activity = datetime.fromisoformat(row["last_activity_at"])
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            sent_codes = self.get_sent_reminder_codes(user_id)
            for reminder in reminders:
                if reminder["code"] in sent_codes:
                    continue
                if now >= last_activity + timedelta(hours=reminder["hours"]):
                    due_items.append(
                        {
                            "user_id": user_id,
                            "username": row["username"],
                            "first_name": row["first_name"],
                            "context_type": row["context_type"],
                            "context_id": row["context_id"],
                            "reminder": reminder,
                        }
                    )
                    break
        return due_items

    def get_summary(self) -> dict[str, Any]:
        now = utc_now()
        today_start = now.astimezone(MOSCOW_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start.astimezone(timezone.utc)
        active_since = now - timedelta(hours=24)

        with self._lock:
            total_users = self._conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            users_today = self._conn.execute(
                "SELECT COUNT(*) FROM users WHERE first_seen >= ?",
                (today_start_utc.isoformat(timespec="seconds"),),
            ).fetchone()[0]
            active_24h = self._conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_seen >= ?",
                (active_since.isoformat(timespec="seconds"),),
            ).fetchone()[0]
            inactive_users = self._conn.execute(
                "SELECT COUNT(*) FROM users WHERE bot_blocked = 1"
            ).fetchone()[0]
            active_users = total_users - inactive_users
            total_events = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            total_starts = self._conn.execute(
                "SELECT COALESCE(SUM(start_count), 0) FROM users"
            ).fetchone()[0]
            stop_rows = self._conn.execute(
                """
                SELECT COALESCE(last_step, 'unknown') AS step, COUNT(*) AS cnt
                FROM users
                GROUP BY COALESCE(last_step, 'unknown')
                ORDER BY cnt DESC, step ASC
                LIMIT 10
                """
            ).fetchall()

        return {
            "total_users": total_users,
            "users_today": users_today,
            "active_24h": active_24h,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "total_events": total_events,
            "total_starts": total_starts,
            "top_stops": [(row["step"], row["cnt"]) for row in stop_rows],
        }

    def get_funnel(self) -> list[tuple[str, int]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT step, COUNT(DISTINCT user_id) AS cnt
                FROM events
                WHERE step IS NOT NULL
                GROUP BY step
                ORDER BY cnt DESC, step ASC
                """
            ).fetchall()
        return [(row["step"], row["cnt"]) for row in rows]

    def get_recent_users(self, limit: int = 20) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 10000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT user_id, username, first_name, last_name, first_seen, last_seen, last_step, start_count, bot_blocked
                FROM users
                ORDER BY last_seen DESC
                LIMIT ?
                """,
                (safe_limit,),
            ).fetchall()

        users = [dict(row) for row in rows]
        for user in users:
            user["first_seen"] = to_moscow_display(user.get("first_seen"))
            user["last_seen"] = to_moscow_display(user.get("last_seen"))
        return users

    def get_all_users(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT user_id, username, first_name, last_name, first_seen, last_seen, last_step, start_count, bot_blocked
                FROM users
                ORDER BY last_seen DESC
                """
            ).fetchall()

        users = [dict(row) for row in rows]
        for user in users:
            user["first_seen"] = to_moscow_display(user.get("first_seen"))
            user["last_seen"] = to_moscow_display(user.get("last_seen"))
        return users

    def _resolve_user_row(self, user_ref: str) -> sqlite3.Row | None:
        value = user_ref.strip()
        query = """
            SELECT user_id, username, first_name, last_name, language_code,
                   first_seen, last_seen, last_step, current_step_updated_at, start_count, bot_blocked
            FROM users
            WHERE user_id = ?
        """
        params: tuple[Any, ...]
        if value.isdigit():
            params = (int(value),)
        else:
            query = query.replace("WHERE user_id = ?", "WHERE LOWER(COALESCE(username, '')) = ?")
            params = (value.lstrip("@").lower(),)

        with self._lock:
            return self._conn.execute(query, params).fetchone()

    def get_user_details(self, user_ref: str, event_limit: int = 25) -> dict[str, Any] | None:
        user_row = self._resolve_user_row(user_ref)
        if not user_row:
            return None

        with self._lock:
            event_rows = self._conn.execute(
                """
                SELECT id, event_type, step, payload_json, created_at
                FROM events
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_row["user_id"], max(1, min(event_limit, 100))),
            ).fetchall()

        user_data = dict(user_row)
        user_data["first_seen"] = to_moscow_display(user_data.get("first_seen"))
        user_data["last_seen"] = to_moscow_display(user_data.get("last_seen"))
        user_data["current_step_updated_at"] = to_moscow_display(user_data.get("current_step_updated_at"))

        events_data = [dict(row) for row in event_rows]
        for event in events_data:
            event["created_at"] = to_moscow_display(event.get("created_at"))

        return {
            "user": user_data,
            "events": events_data,
        }

    def find_users_by_refs(self, refs: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
        normalized_refs: list[str] = []
        id_refs: list[int] = []
        username_refs: list[str] = []

        for ref in refs:
            token = ref.strip()
            if not token:
                continue
            normalized_refs.append(token)
            if token.isdigit():
                id_refs.append(int(token))
            else:
                username_refs.append(token.lstrip("@").lower())

        if not normalized_refs:
            return [], []

        clauses: list[str] = []
        params: list[Any] = []

        if id_refs:
            placeholders = ",".join("?" for _ in id_refs)
            clauses.append(f"user_id IN ({placeholders})")
            params.extend(id_refs)

        if username_refs:
            placeholders = ",".join("?" for _ in username_refs)
            clauses.append(f"LOWER(COALESCE(username, '')) IN ({placeholders})")
            params.extend(username_refs)

        query = f'''
            SELECT user_id, username, first_name, last_name, first_seen, last_seen, last_step, start_count, bot_blocked
            FROM users
            WHERE {" OR ".join(clauses)}
        '''

        with self._lock:
            rows = self._conn.execute(query, params).fetchall()

        users = [dict(row) for row in rows]
        by_id = {str(user["user_id"]): user for user in users}
        by_username = {
            (user["username"] or "").lower(): user
            for user in users
            if user.get("username")
        }

        found_users: list[dict[str, Any]] = []
        unresolved: list[str] = []
        seen_user_ids: set[int] = set()

        for ref in normalized_refs:
            user: dict[str, Any] | None = None
            if ref.isdigit():
                user = by_id.get(ref)
            else:
                user = by_username.get(ref.lstrip("@").lower())

            if user is None:
                unresolved.append(ref)
                continue

            if user["user_id"] not in seen_user_ids:
                found_users.append(user)
                seen_user_ids.add(user["user_id"])

        return found_users, unresolved

    def get_users_by_step(self, step: str, limit: int = 1000) -> list[dict[str, Any]]:
        safe_limit = max(1, min(limit, 10000))
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.last_name, u.first_seen, u.last_seen, u.last_step, u.start_count, u.bot_blocked
                FROM users u
                JOIN events e ON e.user_id = u.user_id
                WHERE e.step = ?
                ORDER BY u.last_seen DESC
                LIMIT ?
                """,
                (step, safe_limit),
            ).fetchall()

        users = [dict(row) for row in rows]
        for user in users:
            user["first_seen"] = to_moscow_display(user.get("first_seen"))
            user["last_seen"] = to_moscow_display(user.get("last_seen"))
        return users

    def export_users_csv(self, export_dir: Path) -> Path:
        export_dir.mkdir(parents=True, exist_ok=True)
        file_path = export_dir / f"users_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
        rows = self.get_all_users()
        with file_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "user_id",
                    "username",
                    "first_name",
                    "last_name",
                    "first_seen",
                    "last_seen",
                    "last_step",
                    "start_count",
                    "bot_blocked",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)
        return file_path

    def export_events_csv(self, export_dir: Path, limit: int = 100000) -> Path:
        export_dir.mkdir(parents=True, exist_ok=True)
        file_path = export_dir / f"events_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, user_id, event_type, step, payload_json, created_at
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(limit, 500000)),),
            ).fetchall()

        events = [dict(row) for row in rows]
        for event in events:
            event["created_at"] = to_moscow_display(event.get("created_at"))

        with file_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["id", "user_id", "event_type", "step", "payload_json", "created_at"],
            )
            writer.writeheader()
            writer.writerows(events)
        return file_path

