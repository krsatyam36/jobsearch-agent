import sqlite3
from datetime import datetime
from pathlib import Path

from config.settings import DATABASE_PATH


class JobDatabase:
    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self._conn = None

    def connect(self):
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                posted_minutes_ago INTEGER,
                time_bucket TEXT,
                linkedin_url TEXT,
                description TEXT,
                is_relevant_fit INTEGER,
                requires_edge_hardware INTEGER,
                hardware_mentioned TEXT,
                requires_robotics_stack INTEGER,
                protocols_mentioned TEXT,
                years_experience_required INTEGER,
                remote_policy TEXT,
                match_score INTEGER,
                red_flags TEXT,
                llm_raw_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.commit()

    def exists(self, job_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None

    def insert(self, job: dict):
        self._conn.execute("""
            INSERT OR IGNORE INTO jobs (
                job_id, title, company, location, posted_minutes_ago,
                time_bucket, linkedin_url, description,
                is_relevant_fit, requires_edge_hardware, hardware_mentioned,
                requires_robotics_stack, protocols_mentioned,
                years_experience_required, remote_policy,
                match_score, red_flags, llm_raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["job_id"],
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("posted_minutes_ago"),
            job.get("time_bucket"),
            job.get("linkedin_url"),
            job.get("description"),
            int(job.get("is_relevant_fit", False)),
            int(job.get("requires_edge_hardware", False)),
            job.get("hardware_mentioned", ""),
            int(job.get("requires_robotics_stack", False)),
            job.get("protocols_mentioned", ""),
            job.get("years_experience_required"),
            job.get("remote_policy"),
            job.get("match_score"),
            job.get("red_flags", ""),
            job.get("llm_raw_json", ""),
        ))
        self._conn.commit()

    def get_all(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_new_since(self, timestamp: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE created_at >= ? ORDER BY created_at DESC",
            (timestamp,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        if self._conn:
            self._conn.close()
