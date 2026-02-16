"""
Validation utilities for issue keys, project names, and conflict detection.
"""

import re
import hashlib
import logging
import math
from datetime import datetime

logger = logging.getLogger(__name__)


class Validator:
    """Validator for issue keys and time entry data."""
    
    # Regex pattern for Jira issue key (e.g., PROJ-123, ABC-456)
    ISSUE_KEY_PATTERN = re.compile(r'^([A-Z][A-Z0-9]*-\d+)')
    
    @staticmethod
    def extract_issue_key(project_name):
        """
        Extract Jira issue key from Toggle project name.
        
        Args:
            project_name: Toggle project name (e.g., 'VCGCC-65 Implement feature')
        
        Returns:
            Tuple of (issue_key, success) where issue_key is str or None
        """
        if not project_name:
            return None, False
        
        match = Validator.ISSUE_KEY_PATTERN.match(project_name.strip())
        if match:
            issue_key = match.group(1)
            logger.debug(f"Extracted issue key '{issue_key}' from project '{project_name}'")
            return issue_key, True
        else:
            logger.warning(f"Could not extract issue key from project name: '{project_name}'")
            return None, False
    
    @staticmethod
    def is_valid_issue_key_format(issue_key):
        """
        Check if string is valid Jira issue key format.
        
        Args:
            issue_key: Potential issue key string
        
        Returns:
            True if valid format, False otherwise
        """
        if not issue_key:
            return False
        return Validator.ISSUE_KEY_PATTERN.match(issue_key) is not None
    
    @staticmethod
    def calculate_entry_hash(entry_data):
        """
        Calculate hash of entry to detect modifications.
        
        Args:
            entry_data: Toggle entry dict with start, duration, description
        
        Returns:
            Hash string
        """
        hash_input = f"{entry_data['id']}_{entry_data['start']}_{entry_data['duration']}_{entry_data.get('description', '')}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    @staticmethod
    def round_seconds_to_minutes(seconds):
        """
        Round seconds UP to whole minutes.
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Duration rounded up to whole minutes (in seconds)
        
        Examples:
            14267 (3h 57m 47s) → 14280 (3h 58m)
            14400 (4h 0m 0s) → 14400 (4h 0m, no change)
            30 (0m 30s) → 60 (1m)
        """
        return math.ceil(seconds / 60) * 60
    
    @staticmethod
    def format_seconds_to_jira_format(seconds):
        """
        Convert seconds to Jira-readable format (e.g., '1h 30m').
        Rounds seconds UP to whole minutes.
        
        Args:
            seconds: Duration in seconds
        
        Returns:
            Formatted string like '1h 30m'
        """
        # Round up seconds to whole minutes
        total_minutes = math.ceil(seconds / 60)
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)
    
    @staticmethod
    def convert_toggle_timestamp_to_jira(toggle_start_str):
        """
        Convert Toggle ISO 8601 timestamp to Jira format.
        
        Toggle: 2024-01-15T14:30:00Z (UTC)
        Jira: 2024-01-15T14:30:00.000+0000
        
        Args:
            toggle_start_str: ISO 8601 string from Toggle
        
        Returns:
            Jira-formatted timestamp string
        """
        try:
            # Parse Toggle timestamp (format: 2024-01-15T14:30:00Z)
            dt = datetime.fromisoformat(toggle_start_str.replace('Z', '+00:00'))
            
            # Format for Jira (format: 2024-01-15T14:30:00.000+0000)
            return dt.strftime('%Y-%m-%dT%H:%M:%S.000+0000')
        except Exception as e:
            logger.error(f"Failed to convert timestamp {toggle_start_str}: {e}")
            raise
    
    @staticmethod
    def format_entry_for_display(entry):
        """
        Format a Toggle entry for display in review UI.
        
        Args:
            entry: Toggle entry dict
        
        Returns:
            Formatted dict for display
        """
        return {
            'id': entry.get('id'),
            'project': entry.get('project_name', 'Unknown'),
            'description': entry.get('description', '(no description)'),
            'duration': Validator.format_seconds_to_jira_format(entry.get('duration', 0)),
            'start': entry.get('start', ''),
            'tags': ','.join(entry.get('tags', [])) if entry.get('tags') else '(none)',
        }


class ConflictDetector:
    """Detect conflicts and duplicates during sync."""
    
    @staticmethod
    def is_duplicate(toggle_id, existing_mapping):
        """
        Check if Toggle entry already synced.
        
        Args:
            toggle_id: Toggle entry ID
            existing_mapping: Row from worklog_map table or None
        
        Returns:
            True if already synced, False otherwise
        """
        return existing_mapping is not None
    
    @staticmethod
    def needs_update(current_hash, stored_hash):
        """
        Check if entry needs updating based on hash comparison.
        
        Args:
            current_hash: Hash of current entry
            stored_hash: Hash from last sync
        
        Returns:
            True if entry changed, False if same
        """
        return current_hash != stored_hash
    
    @staticmethod
    def detect_jira_conflict(issue_key, jira_worklog, toggle_id):
        """
        Detect if there's a conflict in Jira worklog.
        
        Args:
            issue_key: Jira issue key
            jira_worklog: Existing Jira worklog or None
            toggle_id: Toggle entry ID
        
        Returns:
            Tuple of (has_conflict, conflict_description)
        """
        if not jira_worklog:
            return False, None
        
        # Check if worklog has our Toggle ID marker
        # For now simplified - needs to be implemented with actual worklog comment parsing
        return False, None
