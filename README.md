# Toggle to Jira Tempo Sync Tool

A Python CLI tool to automatically sync time entries from Toggle time tracking to Jira Cloud worklogs, with comprehensive validation, deduplication, and user control mechanisms.

## Features

✓ **Automatic Issue Key Extraction** - Parses Jira issue keys from Toggle project names (e.g., `VCGCC-65 Feature Name` → `VCGCC-65`)

✓ **Issue Validation** - Checks if Jira issues exist before syncing; warns user and allows corrections

✓ **Deduplication** - Prevents duplicate worklogs by tracking synced Toggle entries in SQLite database

✓ **Update Detection** - Automatically detects when Toggle entries are modified and updates Jira worklogs accordingly

✓ **Smart Time Rounding** - Rounds seconds UP to whole minutes (Jira Tempo doesn't support seconds)

✓ **Accurate Time Summaries** - Shows weekly breakdown and total time for entries that will actually be imported (skips duplicates/conflicts)

✓ **User Review UI** - CLI-based review interface to see all entries before sync, with options to skip or correct

✓ **Conflict Detection** - Warns about existing Jira worklogs; lets user decide to skip or overwrite

✓ **Rate Limit Handling** - Implements exponential backoff for Toggle API rate limiting

✓ **Comprehensive Logging** - All operations logged to files for audit trail and troubleshooting

## Installation

### Prerequisites
- Python 3.8+
- Toggle API token (from Toggle profile settings)
- Jira Cloud instance with API access
- Jira API token (from account settings)

### Setup

1. Clone or download this tool:
```bash
cd Toggle2JiraTempo
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file from template:
```bash
cp .env.example .env
```

4. Edit `.env` with your credentials:
```env
TOGGLE_API_TOKEN=your_toggle_token_here
TOGGLE_WORKSPACE_ID=your_workspace_id
TOGGLE_CLIENT_NAME=client_name

JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your_jira_api_token

FIRST_SYNC_DATE=2024-01-01
LOG_LEVEL=INFO
```

## Finding Your API Tokens

### Toggle API Token
1. Go to https://track.toggl.com/app/profile
2. Scroll to "API Token" section
3. Copy the token

### Toggle Workspace ID

**Method 1: From Workspace Dropdown (Easiest)**
1. Go to https://track.toggl.com/app
2. Look at **top-left** - click the workspace name dropdown (e.g., "Sám na sebe" or your workspace name)
3. This should show your workspace ID in the list

**Method 2: Using Toggle API (Most Reliable - v9)**
1. Get your Toggle API token first (see above)
2. Open PowerShell and run:
```powershell
$token = "YOUR_TOGGLE_API_TOKEN"
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${token}:api_token"))
$response = Invoke-RestMethod -Uri "https://api.track.toggl.com/api/v9/me" `
  -Headers @{Authorization = "Basic $auth"}
$response.workspace_id
```
3. This prints your workspace ID (usually 7-8 digits like `12345678`)

**Method 3: From Browser DevTools**
1. Go to https://track.toggl.com/app
2. Press **F12** to open Developer Tools
3. Go to **Network** tab
4. Refresh the page (F5)
5. Click on any Toggle API request
6. Look in **Request Headers** for `Workspace-ID`

**Note:** Workspace ID is typically a 7-8 digit number. If you only have one workspace, that's your ID.

### Jira API Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Copy the token

## Usage

### First Run (Initial Sync)

```bash
python main.py
```

You'll be prompted for:
1. Sync start date (e.g., `2024-01-01` to fetch all entries from that date forward)
2. Review of entries to be synced
3. Handle any invalid issue keys (correct, skip, or ignore)
4. Final approval before syncing

### Subsequent Runs

```bash
python main.py
```

The tool automatically syncs from the first day of the last synced month, ensuring no entries are missed while avoiding unnecessary re-fetching. It detects:
- **New entries** - Creates new Jira worklogs
- **Modified entries** - Updates existing Jira worklogs with new times/descriptions
- **Duplicates** - Skips entries already synced without any changes

### Dry-Run Mode

To test without making actual changes:
1. Run `python main.py`
2. At final approval prompt, type `dry-run`
3. See what would be synced without actually creating worklogs in Jira

## Workflow

### 1. Entry Preparation
- Fetches Toggle entries from start date (first day of last synced month, or user-specified date)
- Rounds all entry times UP to whole minutes (Jira Tempo limitation)
- Filters by client name
- Extracts Jira issue keys from project names
- Validates issue keys exist in Jira
- Detects new vs. modified vs. duplicate entries

### 2. User Review
- Displays all entries in formatted table, sorted by date (oldest first)
- Shows validation status (✓ valid, ✗ invalid, ⚠ parse error)
- Shows weekly time breakdown + total time for entries to be imported (excludes duplicates)
- Lists any entries with issues
- Provides options to:
  - Skip individual entries
  - Correct issue keys interactively
  - Ignore validation warnings

### 3. Conflict Resolution
- Detects if Jira worklog already exists
- Prompts user to skip or overwrite with Toggle data

### 4. Final Approval
- Shows summary of entries to be synced
- Offers dry-run option for testing
- Requests final confirmation

### 5. Sync Execution
- Creates new worklogs in Jira
- Updates existing worklogs if entries modified
- Logs each operation
- Saves sync state to database

### 6. Results & Logging
- Displays sync summary (synced, failed, skipped)
- Saves detailed log file with timestamp
- Records sync history in database for troubleshooting

## Issue Key Format Requirements

Toggle project names must start with Jira issue key in format: `KEY-123`

**Valid examples:**
- `VCGCC-65 Implement feature`
- `PROJ-123`
- `ABC-999 Bug fix`

**Invalid examples:**
- `Implement feature` (no issue key)
- `Feature VCGCC-65` (issue key not at start)
- `VCGCC65 Feature` (no hyphen between letters and numbers)

If a project doesn't match this pattern, the sync will warn you and allow correction before transfer.

## Database & State Management

### Sync State (SQLite)

The tool maintains `sync_state.db` with:

- **sync_state** - Last watermark timestamp for incremental syncs
- **toggle_entries** - Cached Toggle entries with hashes for change detection
- **worklog_map** - Mapping of Toggle entries to Jira worklogs (for deduplication)
- **sync_history** - History of all sync runs and results
- **issue_validation_cache** - Cached Jira issue existence checks (1-hour TTL)

### Logs

All operations logged to `logs/sync_YYYYMMDD_HHMMSS.log`

## Troubleshooting

### "Missing required configuration"
- Create `.env` file from `.env.example`
- Fill in all required fields
- Check that credentials are correct

### "Jira authentication failed"
- Verify JIRA_EMAIL and JIRA_API_TOKEN in `.env`
- Ensure API token wasn't revoked
- Check that token has `write:jira-work` scope

### "Toggle API rate limit exceeded"
- Tool implements automatic backoff, but retry later if persists
- Reduce sync frequency or fetch smaller date ranges

### "Issue not found in Jira"
- Confirm issue key exists in Jira
- Check project key is correct (case-sensitive)
- Sync will allow you to correct the issue key before transfer

### Duplicate worklogs in Jira
- This shouldn't happen due to deduplication, but if it does:
- Check logs for details
- Can manually delete duplicate from Jira
- Run sync again - deduplication will prevent re-creating

## Advanced Configuration

### Adjust Log Level
In `.env`, change `LOG_LEVEL` to:
- `DEBUG` - Verbose output, useful for troubleshooting
- `INFO` - Normal operation (default)
- `WARNING` - Only show warnings/errors
- `ERROR` - Only show errors

### Clear Issue Cache
If Jira issues were created after last sync:
```python
from db import get_db
db = get_db()
db.clear_issue_cache()
db.close()
```

## Architecture

- **main.py** - CLI entry point, user interaction flow
- **config.py** - Load credentials from .env
- **toggle_api.py** - Toggle API client with rate limiting
- **jira_api.py** - Jira Cloud API client with issue validation
- **db.py** - SQLite database for state management
- **sync_engine.py** - Core sync logic and orchestration
- **validator.py** - Issue key parsing, timestamp conversion, deduplication
- **ui.py** - CLI review interface and user prompts
- **sync_state.db** - SQLite database (auto-created)
- **logs/** - Directory with timestamped sync logs

## Security Notes

- `.env` file contains credentials - **DO NOT COMMIT TO GIT**
- Add `.env` and `sync_state.db` to `.gitignore`
- API tokens in logs - keep logs private
- Use least-privileged Jira API token (scope: `write:issue-worklog:jira`)

## Support & Issues

Check logs in `logs/` directory for detailed error messages.

For API credential issues, verify:
1. Toggle token works: https://api.track.toggl.com/api/v9/me
2. Jira token works: `https://your-domain.atlassian.net/rest/api/3/myself`

## Future Enhancements

- Web UI for review (instead of CLI)
- Scheduled sync runs (daemon mode)
- Bi-directional sync (detect Jira updates)
- Budget/billability rules
- Time rounding policies
- Customizable field mapping
