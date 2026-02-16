"""
SQLite database management for sync state tracking.
Handles schema creation and CRUD operations for sync state.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


class SyncDatabase:
    """SQLite database for managing sync state and history."""
    
    DB_PATH = Path(__file__).parent / 'sync_state.db'
    
    def __init__(self):
        self.db_path = self.DB_PATH
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize database and create tables if they don't exist."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        cursor = self.conn.cursor()
        
        # Create tables
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS sync_state (
                id INTEGER PRIMARY KEY,
                last_synced_at TIMESTAMP,
                watermark_timestamp TEXT,
                sync_date_range TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS toggle_entries (
                id INTEGER PRIMARY KEY,
                toggle_id INTEGER UNIQUE NOT NULL,
                start_time TEXT NOT NULL,
                duration INTEGER NOT NULL,
                description TEXT,
                project_name TEXT NOT NULL,
                tags TEXT,
                local_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS worklog_map (
                id INTEGER PRIMARY KEY,
                toggle_id INTEGER NOT NULL UNIQUE,
                jira_worklog_id TEXT,
                jira_issue_key TEXT NOT NULL,
                synced_at TIMESTAMP,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (toggle_id) REFERENCES toggle_entries(toggle_id)
            );
            
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY,
                sync_run_id TEXT NOT NULL,
                sync_date TIMESTAMP,
                entries_attempted INTEGER,
                entries_synced INTEGER,
                entries_skipped INTEGER,
                entries_failed INTEGER,
                error_details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS issue_validation_cache (
                id INTEGER PRIMARY KEY,
                issue_key TEXT UNIQUE NOT NULL,
                is_valid INTEGER NOT NULL,
                last_checked_at TIMESTAMP,
                error_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_toggle_entries_toggle_id 
                ON toggle_entries(toggle_id);
            CREATE INDEX IF NOT EXISTS idx_worklog_map_toggle_id 
                ON worklog_map(toggle_id);
            CREATE INDEX IF NOT EXISTS idx_worklog_map_issue_key 
                ON worklog_map(jira_issue_key);
            CREATE INDEX IF NOT EXISTS idx_issue_validation_cache_issue_key 
                ON issue_validation_cache(issue_key);
        """)
        
        self.conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    # Sync State Methods
    def get_last_watermark(self):
        """Get the last synced watermark timestamp."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT watermark_timestamp FROM sync_state ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        return row['watermark_timestamp'] if row else None
    
    def set_watermark(self, watermark):
        """Update the watermark timestamp after successful sync."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO sync_state (id, watermark_timestamp, last_synced_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
        ''', (watermark,))
        self.conn.commit()
    
    # Toggle Entry Methods
    def save_toggle_entry(self, entry_data):
        """Save a Toggle entry to the database."""
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO toggle_entries 
                (toggle_id, start_time, duration, description, project_name, tags, local_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry_data['id'],
                entry_data['start'],
                entry_data['duration'],
                entry_data.get('description'),
                entry_data['project_name'],
                json.dumps(entry_data.get('tags', [])),
                entry_data['hash'],
            ))
            self.conn.commit()
        except sqlite3.IntegrityError as e:
            print(f"Error saving toggle entry {entry_data['id']}: {e}")
    
    def get_toggle_entry(self, toggle_id):
        """Get a Toggle entry by ID."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM toggle_entries WHERE toggle_id = ?', (toggle_id,))
        return cursor.fetchone()
    
    def get_all_toggle_entries(self):
        """Get all Toggle entries."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM toggle_entries')
        return cursor.fetchall()
    
    # Worklog Map Methods
    def save_worklog_mapping(self, toggle_id, jira_worklog_id, jira_issue_key, status='synced'):
        """Save mapping between Toggle entry and Jira worklog."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO worklog_map 
            (toggle_id, jira_worklog_id, jira_issue_key, synced_at, status)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (toggle_id, jira_worklog_id, jira_issue_key, status))
        self.conn.commit()
    
    def get_worklog_mapping(self, toggle_id):
        """Get worklog mapping for a Toggle entry."""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM worklog_map WHERE toggle_id = ?', (toggle_id,))
        return cursor.fetchone()
    
    def get_worklog_by_issue_and_date(self, issue_key, start_date, end_date):
        """Check if worklog exists in Jira for issue and date range."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM worklog_map 
            WHERE jira_issue_key = ? AND status = 'synced'
        ''', (issue_key,))
        return cursor.fetchone()
    
    # Issue Validation Cache Methods
    def check_issue_cache(self, issue_key):
        """Check if issue validation is cached and still valid (1 hour)."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM issue_validation_cache 
            WHERE issue_key = ? 
            AND datetime(last_checked_at) > datetime('now', '-1 hour')
        ''', (issue_key,))
        return cursor.fetchone()
    
    def cache_issue_validation(self, issue_key, is_valid, error_reason=None):
        """Cache issue validation result."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO issue_validation_cache 
            (issue_key, is_valid, last_checked_at, error_reason)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?)
        ''', (issue_key, 1 if is_valid else 0, error_reason))
        self.conn.commit()
    
    def clear_issue_cache(self):
        """Clear all issue validation cache entries."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM issue_validation_cache')
        self.conn.commit()
    
    # Sync History Methods
    def log_sync_run(self, sync_run_id, attempted, synced, skipped, failed, errors=None):
        """Log a sync run to history."""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO sync_history 
            (sync_run_id, sync_date, entries_attempted, entries_synced, entries_skipped, entries_failed, error_details)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        ''', (sync_run_id, attempted, synced, skipped, failed, json.dumps(errors) if errors else None))
        self.conn.commit()
    
    def get_sync_history(self, limit=10):
        """Get recent sync history."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM sync_history ORDER BY sync_date DESC LIMIT ?
        ''', (limit,))
        return cursor.fetchall()


def get_db():
    """Get database instance."""
    return SyncDatabase()
