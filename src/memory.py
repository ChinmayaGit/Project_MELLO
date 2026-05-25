import sqlite3
import json
from datetime import datetime
import os

from .vector_memory import VectorMemory

class MemorySystem:
    def __init__(self, db_path="mello_memory.db", vector_db_path="mello_vector_db"):
        self.db_path = db_path
        self.vector_db = VectorMemory(vector_db_path)
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
            row_id = cursor.lastrowid
            conn.commit()
            
            # Sync to Vector DB for semantic search
            self.vector_db.add_event(
                event_id=row_id,
                text=description,
                metadata={"type": event_type, "meta": json.dumps(metadata) if metadata else ""}
            )
            return row_id

    def semantic_search(self, query, limit=5):
        """Returns relevant events using vector search"""
        return self.vector_db.search(query, n_results=limit)

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

    def search_episodic_memory(self, query="", limit=50, offset=0):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if query:
                cursor.execute(
                    "SELECT * FROM episodic_memory WHERE description LIKE ? OR event_type LIKE ? "
                    "ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (f"%{query}%", f"%{query}%", limit, offset)
                )
            else:
                cursor.execute(
                    "SELECT * FROM episodic_memory ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            return cursor.fetchall()

    def count_episodic_memory(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM episodic_memory")
            return cursor.fetchone()[0]

    def delete_episodic_memory(self, memory_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM episodic_memory WHERE id = ?", (memory_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_episodic_memory(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM episodic_memory")
            conn.commit()

if __name__ == "__main__":
    # Test Memory System
    memory = MemorySystem("test_mello.db")
    memory.add_episodic_memory("test_event", "System initialized")
    memory.update_semantic_memory("preferred_style", "snake_case")
    print("Semantic Memory:", memory.get_semantic_memory("preferred_style"))
    print("Episodic Memory:", memory.query_episodic_memory())
