# 2026-08-18 – Claude Opus 4.6: refactored with context managers, logging, and error handling
import sqlite3
import os
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("HARNESSFOAM_DB_PATH", ".harnessfoam/harnessfoam.db")

def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(DB_PATH, timeout=10)

def init_db():
    """Initialize the database tables."""
    with _get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                case_id TEXT PRIMARY KEY,
                case_dir TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                state_json TEXT
            )
        ''')
        conn.commit()
    logger.info("Database initialized at %s", DB_PATH)

def create_run(case_id: str, case_dir: str, prompt: str, initial_state: Dict[str, Any]):
    """Record a new simulation run."""
    try:
        state_str = json.dumps(initial_state, default=str)
    except (TypeError, ValueError) as e:
        logger.warning("Failed to serialize initial state for %s: %s", case_id, e)
        state_str = "{}"
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO runs (case_id, case_dir, prompt, status, state_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (case_id, case_dir, prompt, initial_state.get('status', 'PENDING'), state_str))
        conn.commit()

def update_run_state(case_id: str, state_update: Dict[str, Any]):
    """Merge updates into a run's state JSON."""
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT state_json FROM runs WHERE case_id = ?', (case_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Run {case_id} not found")

        try:
            current_state = json.loads(row[0]) if row[0] else {}
        except json.JSONDecodeError:
            logger.warning("Corrupt state JSON for run %s, resetting", case_id)
            current_state = {}

        current_state.update(state_update)
        status = current_state.get('status', 'RUNNING')

        try:
            state_str = json.dumps(current_state, default=str)
        except (TypeError, ValueError) as e:
            logger.warning("Failed to serialize updated state for %s: %s", case_id, e)
            state_str = json.dumps({"status": status, "error": str(e)})

        cursor.execute('''
            UPDATE runs
            SET status = ?, state_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE case_id = ?
        ''', (status, state_str, case_id))
        conn.commit()

def get_run(case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a run's state."""
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT state_json FROM runs WHERE case_id = ?', (case_id,))
        row = cursor.fetchone()
    if row and row[0]:
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            logger.warning("Corrupt state JSON for run %s", case_id)
            return None
    return None

def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent runs."""
    with _get_conn() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT case_id, case_dir, prompt, status, created_at, updated_at 
            FROM runs 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]
