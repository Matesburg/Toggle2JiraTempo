# Setup Guide - Toggle to Jira Tempo Sync Tool

## Quick Start (5 minutes)

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create & Configure `.env` File

Copy the example template:
```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:
```env
# Toggle API Configuration
TOGGLE_API_TOKEN=YOUR_TOGGLE_API_TOKEN_HERE
TOGGLE_WORKSPACE_ID=YOUR_WORKSPACE_ID_HERE
TOGGLE_CLIENT_NAME=CGC Consulting

# Jira Cloud Configuration
JIRA_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=YOUR_JIRA_API_TOKEN_HERE

# Sync Configuration
FIRST_SYNC_DATE=2024-01-01
LOG_LEVEL=INFO
```

### 3. Run First Sync

```bash
python main.py
```

---

## Detailed Setup Instructions

### Getting Toggle API Token

1. Open Toggle: https://track.toggl.com/app
2. Click your **Profile** icon (top-right)
3. Select **Settings**
4. Scroll to **API Token** section
5. Copy the token (it's a long hex string)

**Note:** Keep this token secret - it gives access to your time entries!

### Finding Toggle Workspace ID

**Quick Method - From Dropdown:**
1. Go to https://track.toggl.com/app
2. Click the **workspace name** at the top-left (e.g., "Sám na sebe", "My Workspace", etc.)
3. Look for your workspace ID in the dropdown - it's a 7-8 digit number
4. Example: `12345678` ← that's your Workspace ID

**Most Reliable Method - Using PowerShell:**

Since Toggle's UI can be inconsistent, here's the guaranteed way:

1. First, get your Toggle API token (from https://track.toggl.com/app/profile)
2. Open PowerShell and run:
```powershell
$token = "YOUR_TOGGLE_API_TOKEN_HERE"
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${token}:api_token"))
$response = Invoke-RestMethod -Uri "https://api.track.toggl.com/api/v8/me" `
  -Headers @{Authorization = "Basic $auth"}
$response.workspaces[0].id
```
3. This prints a number like `12345678` - that's your Workspace ID!

**Browser DevTools Method:**
1. Go to https://track.toggl.com/app
2. Open Developer Tools (Press F12)
3. Go to **Network** tab
4. Refresh page (F5)
5. Click on any Toggle API request
6. Look in **Request Headers** for `Workspace-ID` header
7. Copy that number

### Getting Jira API Token

1. Open Jira: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click **Create API token**
3. Name it "Toggle Sync" or similar
4. Copy the token immediately (you can't view it again)

**Scopes needed:**
- `write:issue-worklog:jira` - Create/update worklogs

### Jira Cloud URL

Use your domain:
- If you access Jira at: `https://mycompany.atlassian.net/`
- Then `JIRA_URL` = `https://mycompany.atlassian.net`

---

## Verification Steps

### Test Toggle Connection

```bash
# Replace with your token
curl -H "Authorization: Basic $(echo -n 'YOUR_TOKEN:api_token' | base64)" \
     https://api.track.toggl.com/api/v8/me
```

Should return your Toggle profile info.

### Test Jira Connection

```bash
# Replace with your email and token
curl -H "Authorization: Basic $(echo -n 'email@company.com:YOUR_JIRA_TOKEN' | base64)" \
     https://your-domain.atlassian.net/rest/api/3/myself
```

Should return your Jira profile info.

### Verify Database Dependencies

The tool uses SQLite (built-in with Python), so no additional setup needed!

---

## First Sync Configuration

### Choosing Start Date

For `FIRST_SYNC_DATE` in `.env`:

**Option 1: Sync all entries since date**
```env
FIRST_SYNC_DATE=2024-01-01
```
On first run, you'll be asked to confirm this date.

**Option 2: Let script ask on first run**
Just leave the default, and the script will prompt you.

### Client Filter

The tool filters by client name. Make sure your Toggle client is named exactly:
```env
TOGGLE_CLIENT_NAME=CGC Consulting
```

If entries aren't showing up, check:
1. Is the client name correct in Toggle?
2. Are the projects assigned to this client?

---

## Troubleshooting Setup

### "Missing required configuration"

**Error:**
```
❌ Missing required configuration: TOGGLE_API_TOKEN, JIRA_API_TOKEN
```

**Fix:**
1. Create `.env` file: `cp .env.example .env`
2. Edit it with real values (not examples)
3. Don't use quotes around values

### "No module named 'requests'"

**Error:**
```
ModuleNotFoundError: No module named 'requests'
```

**Fix:**
```bash
pip install -r requirements.txt
```

### "Jira authentication failed"

**Symptoms:**
- Tool runs but fails on Jira connection test
- Error: "Jira authentication failed"

**Troubleshooting:**
1. Verify email is correct: `echo $JIRA_EMAIL`
2. Verify API token is correct (not password!)
3. Check token hasn't been revoked: https://id.atlassian.com/manage-profile/security/api-tokens
4. Ensure token has right scopes

**Test with curl:**
```bash
curl -u "your-email@example.com" https://your-domain.atlassian.net/rest/api/3/myself
# Enter API token as password when prompted
```

### "Toggle authentication failed"

**Symptoms:**
- Error when fetching Toggle entries
- "401 Unauthorized"

**Troubleshooting:**
1. Verify API token (not password!)
2. Check token hasn't expired
3. Get new token from: https://track.toggl.com/app/profile
4. Test with curl:
```bash
curl -H "Authorization: Basic $(echo -n 'YOUR_TOKEN:api_token' | base64)" \
     https://api.track.toggl.com/api/v8/me
```

### "No entries found"

**Symptoms:**
- Sync runs but finds 0 entries

**Troubleshooting:**
1. **Check client name**: Is it exactly `CGC Consulting` in Toggle?
   - Case-sensitive!
   - Must match exactly
2. **Check date range**: Do you have entries in that date range?
3. **Check projects**: Are projects assigned to the CGC Consulting client?
4. **Check project names**: Do they start with Jira issue key format?
   - Valid: `VCGCC-65 Feature`
   - Invalid: `Feature VCGCC-65` (wrong order)

### Logs Aren't Helpful

**To enable debug logging**, edit `.env`:
```env
LOG_LEVEL=DEBUG
```

Then run again and check `logs/sync_*.log` for detailed output.

---

## File Structure After Setup

```
Toggle2JiraTempo/
├── .env                    ← Your credentials (NOT in git!)
├── .env.example           ← Template (safe to commit)
├── .gitignore            ← Ignore .env, logs, db
├── requirements.txt       ← Python dependencies
├── main.py               ← Main entry point - RUN THIS
├── config.py             ← Load credentials
├── toggle_api.py         ← Toggle API client
├── jira_api.py           ← Jira API client
├── db.py                 ← SQLite database
├── sync_engine.py        ← Core sync logic
├── validator.py          ← Validation utilities
├── ui.py                 ← User interface
├── README.md             ← Full documentation
├── SETUP.md              ← This file
├── sync_state.db         ← SQLite db (auto-created on first run)
└── logs/                 ← Sync logs (auto-created)
    └── sync_20240115_143000.log
```

---

## Next Steps

1. ✓ Installed Python dependencies
2. ✓ Created and edited `.env` 
3. → Run `python main.py` to start first sync!

---

## Getting Help

1. **Check logs**: `ls logs/` - latest log file has detailed info
2. **Enable debug**: Set `LOG_LEVEL=DEBUG` in `.env`
3. **Test APIs manually**: Use curl commands above to verify credentials
4. **Read README.md**: Full documentation and troubleshooting

---

## Security Reminders

⚠️ **DO NOT:**
- Commit `.env` file to git
- Share your API tokens
- Expose `sync_state.db` (contains sync history)
- Post logs online without redacting tokens

✓ **DO:**
- Keep `.env` file locally only
- Regenerate tokens if accidentally exposed
- Add `.env` to `.gitignore` (already done)
- Keep logs private for troubleshooting
