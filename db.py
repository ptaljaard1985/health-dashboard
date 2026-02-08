"""
Shared SQLite database module for health tracking.

All scripts use this module to access the local health.db file.
"""

import os
import sqlite3


def get_db_path():
    """Return the path to health.db (same directory as this module)."""
    return os.path.join(os.path.dirname(__file__), 'health.db')


def get_connection():
    """Return a sqlite3.Connection with row_factory set."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise TEXT NOT NULL,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            garmin_activity_id TEXT UNIQUE,
            duration REAL,
            distance REAL,
            calories INTEGER,
            avg_heart_rate INTEGER,
            max_heart_rate INTEGER,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS weigh_ins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            weight_kg REAL NOT NULL
        );
    """)
    conn.commit()
    conn.close()
