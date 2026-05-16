import sqlite3
import json
from datetime import datetime
import os

class MemorySystem:
    def __init__(self, db_path="mello_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Episodic Memory: Searchable logs of actions/events
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    event_type TEXT,
                    description TEXT,
                    metadata TEXT
                )
            ''')
            # Semantic Memory: Long-term patterns and preferences
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()

    def add_episodic_memory(self, event_type, description, metadata=None):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO episodic_memory (event_type, description, metadata) VALUES (?, ?, ?)",
                (event_type, description, json.dumps(metadata) if metadata else None)
            )
            conn.commit()

    def update_semantic_memory(self, key, value):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO semantic_memory (key, value, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, json.dumps(value) if isinstance(value, (dict, list)) else str(value))
            )
            conn.commit()

    def get_semantic_memory(self, key):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM semantic_memory WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except json.JSONDecodeError:
                    return row[0]
            return None

    def query_episodic_memory(self, limit=10):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM episodic_memory ORDER BY timestamp DESC LIMIT ?", (limit,))
            return cursor.fetchall()

if __name__ == "__main__":
    # Test Memory System
    memory = MemorySystem("test_mello.db")
    memory.add_episodic_memory("test_event", "System initialized")
    memory.update_semantic_memory("preferred_style", "snake_case")
    print("Semantic Memory:", memory.get_semantic_memory("preferred_style"))
    print("Episodic Memory:", memory.query_episodic_memory())
