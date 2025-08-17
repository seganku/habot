import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_entities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        channel_id TEXT NOT NULL,
        rule_type TEXT,
        from_state TEXT,
        to_state TEXT,
        operator TEXT,
        threshold TEXT,
        message TEXT,
        UNIQUE (channel_id, entity_id, from_state, to_state, operator, threshold)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entity_cache (
        entity_id TEXT PRIMARY KEY,
        friendly_name TEXT,
        icon TEXT,
        state TEXT,
        device_class TEXT
    )
    """)
    conn.commit()
    conn.close()

def is_watching(entity_id, channel_id, from_state, to_state, operator, threshold):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM watched_entities
        WHERE entity_id = ? AND channel_id = ?
              AND from_state IS ? AND to_state IS ?
              AND operator IS ? AND threshold IS ?
    """, (entity_id, channel_id, from_state, to_state, operator, threshold))
    result = cur.fetchone()
    conn.close()
    return result is not None

def add_watch(user_id, entity_id, channel_id, rule_type=None, from_state=None, to_state=None, operator=None, threshold=None, message=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO watched_entities (
            user_id, entity_id, channel_id,
            rule_type, from_state, to_state,
            operator, threshold, message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, entity_id, channel_id, rule_type, from_state, to_state, operator, threshold, message))
    conn.commit()
    conn.close()

def remove_watch(watch_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM watched_entities WHERE id = ?", (watch_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted > 0

def get_watched_entities(channel_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, entity_id, rule_type, from_state, to_state, operator, threshold, message
        FROM watched_entities WHERE channel_id = ?
    """, (channel_id,))
    results = cur.fetchall()
    conn.close()
    return results

def get_watchers(entity_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, channel_id,
               rule_type, from_state, to_state,
               operator, threshold, message
        FROM watched_entities WHERE entity_id = ?
    """, (entity_id,))
    results = cur.fetchall()
    conn.close()
    return results

def cache_entity_details(entity_id, friendly_name, icon, state, device_class):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO entity_cache (entity_id, friendly_name, icon, state, device_class)
        VALUES (?, ?, ?, ?, ?)
    """, (entity_id, friendly_name, icon, state, device_class))
    conn.commit()
    conn.close()

def get_cached_entity_details(entity_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT friendly_name, icon, state, device_class FROM entity_cache WHERE entity_id = ?
    """, (entity_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row
    return None

