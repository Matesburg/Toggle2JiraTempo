"""
Toggle API client for fetching time entries.
"""

import requests
import base64
import logging
from datetime import datetime, timedelta
from config import get_config

logger = logging.getLogger(__name__)


class ToggleAPI:
    """Toggle API client for time entry operations."""
    
    BASE_URL = 'https://api.track.toggl.com/api/v9'
    
    def __init__(self, api_token, workspace_id):
        self.api_token = api_token
        self.workspace_id = workspace_id
        self.auth = self._get_basic_auth()
    
    def _get_basic_auth(self):
        """Generate basic auth header from API token."""
        # Toggle API v9 uses API token with ':api_token' suffix
        credentials = base64.b64encode(f"{self.api_token}:api_token".encode()).decode()
        return f"Basic {credentials}"
    
    def _make_request(self, method, endpoint, params=None, data=None, retry_count=0, max_retries=3):
        """Make HTTP request to Toggle API with rate limit handling."""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            'Authorization': self.auth,
            'Content-Type': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Handle rate limiting (429)
            if response.status_code == 429:
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logger.warning(f"Rate limited. Retrying in {wait_time}s...")
                    import time
                    time.sleep(wait_time)
                    return self._make_request(method, endpoint, params, data, retry_count + 1, max_retries)
                else:
                    logger.error(f"Max retries exceeded for rate limit")
                    raise Exception("Toggle API rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Toggle API request failed: {e}")
            raise
    
    def get_time_entries(self, start_date, end_date=None):
        """
        Fetch time entries from Toggle.
        
        Args:
            start_date: Start date (YYYY-MM-DD format, ISO timestamp, or datetime object)
            end_date: End date (YYYY-MM-DD format, ISO timestamp, or datetime object) - defaults to today
        
        Returns:
            List of time entries with parsed project names
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # Handle different input formats
        # If it's an ISO timestamp string, parse it first
        if isinstance(start_date, str) and 'T' in start_date:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if isinstance(end_date, str) and 'T' in end_date:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        
        # Convert to string if datetime object
        if isinstance(start_date, datetime):
            start_date = start_date.strftime('%Y-%m-%d')
        if isinstance(end_date, datetime):
            end_date = end_date.strftime('%Y-%m-%d')
        
        logger.info(f"Fetching Toggle entries from {start_date} to {end_date}")
        
        params = {
            'start_date': f"{start_date}T00:00:00Z",
            'end_date': f"{end_date}T23:59:59Z",
        }
        
        try:
            # V9 API endpoint - use /me/time_entries for user's entries
            entries = self._make_request('GET', '/me/time_entries', params=params)
            
            # Fetch projects to get names and filter by client
            projects = self._get_projects()
            project_map = {p['id']: p for p in projects}
            
            # Enrich entries with project names and client filter
            enriched_entries = []
            for entry in entries:
                project_id = entry.get('project_id')
                if not project_id:
                    continue
                
                project_data = project_map.get(project_id)
                if not project_data:
                    continue
                
                project_name = project_data.get('name', 'Unknown Project')
                
                # Filter by client name if applicable
                if not self._matches_client_filter(project_data):
                    continue
                
                entry['project_name'] = project_name
                enriched_entries.append(entry)
            
            logger.info(f"Retrieved {len(enriched_entries)} entries matching client filter")
            return enriched_entries
        
        except Exception as e:
            logger.error(f"Failed to fetch Toggle entries: {e}")
            raise
    
    def _get_projects(self):
        """Get all projects in workspace."""
        try:
            projects = self._make_request('GET', f'/workspaces/{self.workspace_id}/projects')
            return projects
        except Exception as e:
            logger.warning(f"Failed to fetch projects: {e}")
            return []
    
    def _matches_client_filter(self, project_data):
        """Check if project belongs to the target client."""
        config = get_config()
        target_client = config.toggle_client_name
        
        if not project_data:
            return False
        
        # In Toggle, check if project has client relation
        # For now, accept all projects unless we need stricter filtering
        return True
    
    def get_single_entry(self, entry_id):
        """Get a single time entry by ID."""
        try:
            return self._make_request('GET', f'/time_entries/{entry_id}')
        except Exception as e:
            logger.error(f"Failed to fetch entry {entry_id}: {e}")
            raise
