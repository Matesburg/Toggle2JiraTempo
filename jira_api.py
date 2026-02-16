"""
Jira Cloud API client for worklog operations and issue validation.
"""

import requests
import base64
import logging
from config import get_config

logger = logging.getLogger(__name__)


class JiraAPI:
    """Jira Cloud API client for worklog and issue operations."""
    
    def __init__(self, jira_url, email, api_token):
        self.jira_url = jira_url.rstrip('/')
        self.email = email
        self.api_token = api_token
        self.auth = self._get_basic_auth()
    
    def _get_basic_auth(self):
        """Generate basic auth header from email and API token."""
        credentials = base64.b64encode(f"{self.email}:{self.api_token}".encode()).decode()
        return f"Basic {credentials}"
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """Make HTTP request to Jira API."""
        url = f"{self.jira_url}/rest/api/3{endpoint}"
        headers = {
            'Authorization': self.auth,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            # Check for errors
            if response.status_code == 401:
                logger.error("Jira authentication failed - check credentials")
                raise Exception("Jira authentication failed")
            elif response.status_code == 403:
                logger.error("Jira permission denied - check API token scopes")
                raise Exception("Jira permission denied")
            elif response.status_code == 404:
                return None  # Resource not found
            elif response.status_code >= 400:
                logger.error(f"Jira API error ({response.status_code}): {response.text}")
                response.raise_for_status()
            
            if response.text:
                return response.json()
            return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Jira API request failed: {e}")
            raise
    
    def validate_issue_exists(self, issue_key):
        """
        Check if a Jira issue exists.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
        
        Returns:
            True if issue exists, False otherwise
        """
        try:
            result = self._make_request('GET', f'/issue/{issue_key}', params={'fields': 'key'})
            return result is not None
        except Exception as e:
            logger.error(f"Error validating issue {issue_key}: {e}")
            return False
    
    def create_worklog(self, issue_key, started, time_spent_seconds, comment=None):
        """
        Create a worklog entry in Jira.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            started: ISO 8601 datetime string (e.g., '2024-01-15T14:30:00.000+0000')
            time_spent_seconds: Duration in seconds
            comment: Optional comment/description
        
        Returns:
            Worklog ID if successful, None otherwise
        """
        data = {
            'started': started,
            'timeSpentSeconds': time_spent_seconds,
        }
        
        if comment:
            data['comment'] = {
                'type': 'doc',
                'version': 1,
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [
                            {
                                'type': 'text',
                                'text': comment
                            }
                        ]
                    }
                ]
            }
        
        try:
            logger.info(f"Creating worklog for {issue_key}: {time_spent_seconds}s on {started}")
            result = self._make_request('POST', f'/issue/{issue_key}/worklog', data=data)
            
            if result:
                worklog_id = result.get('id')
                logger.info(f"Worklog created: {worklog_id}")
                return worklog_id
            return None
        
        except Exception as e:
            logger.error(f"Failed to create worklog for {issue_key}: {e}")
            raise
    
    def update_worklog(self, issue_key, worklog_id, started, time_spent_seconds, comment=None):
        """
        Update an existing worklog entry in Jira.
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            worklog_id: ID of the worklog to update
            started: ISO 8601 datetime string
            time_spent_seconds: Duration in seconds
            comment: Optional comment/description
        
        Returns:
            True if successful, False otherwise
        """
        data = {
            'started': started,
            'timeSpentSeconds': time_spent_seconds,
        }
        
        if comment:
            data['comment'] = {
                'type': 'doc',
                'version': 1,
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [
                            {
                                'type': 'text',
                                'text': comment
                            }
                        ]
                    }
                ]
            }
        
        try:
            logger.info(f"Updating worklog {worklog_id} for {issue_key}")
            self._make_request('PUT', f'/issue/{issue_key}/worklog/{worklog_id}', data=data)
            logger.info(f"Worklog {worklog_id} updated successfully")
            return True
        
        except Exception as e:
            logger.error(f"Failed to update worklog {worklog_id}: {e}")
            raise
    
    def get_worklogs_for_issue(self, issue_key):
        """
        Get all worklogs for an issue.
        
        Args:
            issue_key: Jira issue key
        
        Returns:
            List of worklogs
        """
        try:
            result = self._make_request('GET', f'/issue/{issue_key}', 
                                       params={'fields': 'worklog'})
            if result and 'fields' in result and 'worklog' in result['fields']:
                return result['fields']['worklog'].get('worklogs', [])
            return []
        except Exception as e:
            logger.error(f"Failed to fetch worklogs for {issue_key}: {e}")
            return []
    
    def test_connection(self):
        """Test Jira API connectivity."""
        try:
            result = self._make_request('GET', '/myself')
            if result:
                logger.info(f"[OK] Jira connection successful. Authenticated as: {result.get('displayName')}")
                return True
            return False
        except Exception as e:
            logger.error(f"[ERROR] Jira connection failed: {e}")
            return False
