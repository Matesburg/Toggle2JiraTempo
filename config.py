"""
Configuration management for Toggle to Jira Tempo sync.
Loads credentials from .env file or environment variables.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration container for API credentials and settings."""
    
    def __init__(self):
        # Toggle Configuration
        self.toggle_api_token = os.getenv('TOGGLE_API_TOKEN')
        self.toggle_workspace_id = os.getenv('TOGGLE_WORKSPACE_ID')
        self.toggle_client_name = os.getenv('TOGGLE_CLIENT_NAME', 'CGC Consulting')
        
        # Jira Configuration
        self.jira_url = os.getenv('JIRA_URL')
        self.jira_email = os.getenv('JIRA_EMAIL')
        self.jira_api_token = os.getenv('JIRA_API_TOKEN')
        
        # Sync Configuration
        self.first_sync_date = os.getenv('FIRST_SYNC_DATE', '2024-01-01')
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Validate required configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate that all required credentials are present."""
        required_fields = {
            'TOGGLE_API_TOKEN': self.toggle_api_token,
            'TOGGLE_WORKSPACE_ID': self.toggle_workspace_id,
            'JIRA_URL': self.jira_url,
            'JIRA_EMAIL': self.jira_email,
            'JIRA_API_TOKEN': self.jira_api_token,
        }
        
        missing_fields = [name for name, value in required_fields.items() if not value]
        
        if missing_fields:
            missing_str = ', '.join(missing_fields)
            print(f"\n❌ Missing required configuration: {missing_str}")
            print(f"Please create a .env file with these fields. See .env.example for template.\n")
            raise ValueError(f"Missing configuration: {missing_str}")
    
    def to_dict(self):
        """Return configuration as dictionary."""
        return {
            'toggle_api_token': self.toggle_api_token,
            'toggle_workspace_id': self.toggle_workspace_id,
            'toggle_client_name': self.toggle_client_name,
            'jira_url': self.jira_url,
            'jira_email': self.jira_email,
            'jira_api_token': self.jira_api_token,
            'first_sync_date': self.first_sync_date,
            'log_level': self.log_level,
        }


def get_config():
    """Get global configuration instance."""
    return Config()
