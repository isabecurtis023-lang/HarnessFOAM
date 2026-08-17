import sqlite3
import os
import json
from typing import Dict, Any, List, Optional
from pathlib import Path

DB_PATH = os.environ.get("HARNESSFOAM_DB_PATH", ".harnessfoam/harnessfoam.db")

def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    """Initialize the database tables."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('''
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
    conn.close()

def create_run(case_id: str, case_dir: str, prompt: str, initial_state: Dict[str, Any]):
    """Record a new simulation run."""
    conn = _get_conn()
    cursor = conn.cursor()
    state_str = json.dumps(initial_state)
    cursor.execute('''
        INSERT INTO runs (case_id, case_dir, prompt, status, state_json)
        VALUES (?, ?, ?, ?, ?)
    ''', (case_id, case_dir, prompt, initial_state.get('status', 'PENDING'), state_str))
    conn.commit()
    conn.close()

def update_run_state(case_id: str, state_update: Dict[str, Any]):
    """Merge updates into a run's state JSON."""
    conn = _get_conn()
    cursor = conn.cursor()
    
    # Get current state
    cursor.execute('SELECT state_json FROM runs WHERE case_id = ?', (case_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Run {case_id} not found")
        
    current_state = json.loads(row[0]) if row[0] else {}
    current_state.update(state_update)
    
    status = current_state.get('status', 'RUNNING')
    state_str = json.dumps(current_state)
    
    cursor.execute('''
        UPDATE runs
        SET status = ?, state_json = ?, updated_at = CURRENT_TIMESTAMP
        WHERE case_id = ?
    ''', (status, state_str, case_id))
    
    conn.commit()
    conn.close()

def get_run(case_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve a run's state."""
    conn = _get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT state_json FROM runs WHERE case_id = ?', (case_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0]:
        return json.loads(row[0])
    return None

def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
    """List recent runs."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT case_id, case_dir, prompt, status, created_at, updated_at 
        FROM runs 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
